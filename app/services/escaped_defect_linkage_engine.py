import uuid
import math
import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink
from app.schemas.failure_evidence import (
    FailureEvidenceBundle,
    FailureEvidenceRecommendationOutcome,
    FailureEvidenceRecommendationRun,
)

logger = logging.getLogger(__name__)

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: RepositoryCalibrationProfile
# ====================================================================
# Future calibration profiles should support repository-specific tuning:
# - Incident severity tiers: Differentiate P0/P1/P2 production incidents
#   to escalate scores proportionally.
# - Rollback recency weighting: Faster decay for orgs with high rollback
#   cadence (noise suppression).
# - Module ownership mapping: Tie escaped defects to squad ownership for
#   targeted alerting.
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: Evidence-Source Weighting
# ====================================================================
# Escaped defect evidence carries the highest organizational trust:
# - INCIDENT  (Weight: 1.0 / Highest priority — confirmed prod regression)
# - ROLLBACK  (Weight: 0.8 / Strong — deployed change was reverted)
#
# Test failures alone do NOT qualify as escaped defect evidence.
# No inferred sources are accepted.
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================


class EscapedDefectLinkageEngine:
    """
    Teaches Veriscope which modules historically participated in escaped
    defects or rollback events.

    Evidence sources (exclusive — no inference allowed):
      1. Rollback-linked recommendation runs (``rollback_occurred=True``)
      2. Incident-linked recommendation runs  (``escaped_defect=True``)
      3. Production failure-linked PRs (PRs whose recommendation outcome
         carries either flag)

    Pattern type:  ESCAPED_DEFECT_PATTERN
    Key format:    ESCAPED_DEFECT_PATTERN:<file_path>

    A pattern is only persisted when at least one of the two hard gates
    is satisfied:
      - confirmed incident linkage  (escaped_defect=True outcome), OR
      - rollback evidence           (rollback_occurred=True outcome)

    Scoring escalation rules:
      - Incident-linked patterns escalate faster (higher incident weight).
      - Repeated rollbacks increase score heavily (progressive rollback weight).
    """

    # ------------------------------------------------------------------ #
    # Evidence thresholds                                                  #
    # ------------------------------------------------------------------ #
    MIN_EVIDENCE_LINKS = 2   # At least 2 qualifying events per module
    MIN_DISTINCT_PRS = 1     # At least 1 distinct PR (single catastrophic incident counts)

    # ------------------------------------------------------------------ #
    # Scoring constants                                                    #
    # ------------------------------------------------------------------ #
    # Incident evidence saturates score at 3 events (progressive)
    INCIDENT_SATURATION = 3.0
    # Rollback evidence saturates score at 3 events (progressive)
    ROLLBACK_SATURATION = 3.0

    # Weighted formula coefficients (must sum to 1.0)
    W_INCIDENT = 0.35   # Confirmed prod regression — highest weight
    W_ROLLBACK = 0.30   # Deployed rollback — strong signal
    W_RECENCY  = 0.20   # Time-decay recency
    W_FREQ     = 0.10   # Raw event frequency
    W_DENSITY  = 0.05   # Density within the evidence window

    # ------------------------------------------------------------------ #
    # Versioning                                                           #
    # ------------------------------------------------------------------ #
    GENERATION_VERSION        = "v1.2.0"
    SCORING_VERSION           = "weighted.v2"
    NORMALIZATION_RULES_VERSION = "rules.v1"

    # ------------------------------------------------------------------ #
    # Actuarial lifecycle                                                  #
    # ------------------------------------------------------------------ #
    STALE_AFTER_DAYS      = 90
    INVALIDATE_AFTER_DAYS = 180

    def __init__(self, db: Session) -> None:
        self.db = db

    # ================================================================== #
    # Public API                                                           #
    # ================================================================== #

    def detect_escaped_defect_patterns(
        self,
        db: Session,
        repository_id: uuid.UUID,
        evidence_bundle: FailureEvidenceBundle,
        ignore_migrations: bool = True,
    ) -> Dict[str, Any]:
        """
        Scans the evidence bundle for confirmed incidents and rollback events
        and persists ESCAPED_DEFECT_PATTERN fragility records for every module
        that was involved.

        Rules enforced:
          1. Only ``rollback_occurred=True`` OR ``escaped_defect=True``
             outcomes qualify as evidence.  No test-failure inference.
          2. Each pattern must capture: affected files/modules,
             linked recommendation IDs, linked incident IDs (derived from
             the outcome IDs), and rollback timestamps.
          3. Incident-linked evidence escalates the score faster than
             rollback-only evidence.
          4. Repeated rollbacks accumulate a progressive rollback score.

        Returns a summary dict with ``patterns_mined`` and ``diagnostics``.
        """
        logger.info(
            "EscapedDefectLinkageEngine starting for repository %s…",
            repository_id,
        )

        # ---------------------------------------------------------------- #
        # 1. Preserve manually invalidated pattern keys                     #
        # ---------------------------------------------------------------- #
        invalidated_keys: Set[str] = {
            p.normalized_pattern_key
            for p in db.query(FragilityPattern.normalized_pattern_key).filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.pattern_type == "ESCAPED_DEFECT_PATTERN",
                FragilityPattern.status == "INVALIDATED",
            ).all()
        }

        # ---------------------------------------------------------------- #
        # 2. Index recommendation runs by their ID for fast lookups         #
        # ---------------------------------------------------------------- #
        rec_by_id: Dict[uuid.UUID, FailureEvidenceRecommendationRun] = {
            r.recommendation_run_id: r
            for r in evidence_bundle.linked_recommendations
        }

        # ---------------------------------------------------------------- #
        # 3. Partition qualifying outcomes into rollback vs incident buckets #
        # ---------------------------------------------------------------- #
        # outcome is qualifying if rollback_occurred OR escaped_defect is True
        rollback_outcomes: List[FailureEvidenceRecommendationOutcome] = []
        incident_outcomes: List[FailureEvidenceRecommendationOutcome] = []

        for out in evidence_bundle.linked_incidents:
            if out.rollback_occurred:
                rollback_outcomes.append(out)
            if out.escaped_defect:
                incident_outcomes.append(out)

        qualifying_outcome_ids: Set[uuid.UUID] = {
            o.recommendation_outcome_id
            for o in rollback_outcomes + incident_outcomes
        }

        if not qualifying_outcome_ids:
            logger.info(
                "EscapedDefectLinkageEngine: no qualifying incidents or rollbacks "
                "found in evidence bundle for repository %s — no patterns to mine.",
                repository_id,
            )
            return {
                "patterns_mined": 0,
                "diagnostics": {"reason": "no_qualifying_evidence"},
            }

        # ---------------------------------------------------------------- #
        # 4. Build a per-file evidence map                                  #
        #                                                                   #
        # For each qualifying outcome we look up its recommendation run and #
        # from there the PR's changed files.  Each changed file gets one    #
        # evidence entry per qualifying outcome that touched it.            #
        # ---------------------------------------------------------------- #

        # pr_id → list of changed file paths (normalised)
        pr_to_files: Dict[uuid.UUID, List[str]] = defaultdict(list)
        for cf in evidence_bundle.related_changed_files:
            pr_to_files[cf.pull_request_id].append(
                cf.file_path.replace("\\", "/")
            )

        # file_path → list of evidence dicts
        file_evidence: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        def _collect_evidence(
            outcomes: List[FailureEvidenceRecommendationOutcome],
            evidence_type: str,
        ) -> None:
            for out in outcomes:
                rec = rec_by_id.get(out.recommendation_run_id)
                if not rec:
                    continue
                pr_id = rec.pull_request_id
                if not pr_id:
                    continue

                files = pr_to_files.get(pr_id, [])
                if not files:
                    continue

                # Derive a synthetic incident identifier from the outcome ID
                incident_id = f"INC-{str(out.recommendation_outcome_id)[:8].upper()}"

                # Rollback timestamp: use the outcome creation timestamp if available
                rollback_ts: Optional[datetime] = out.created_at

                for file_path in files:
                    low_f = file_path.lower()

                    # Skip generated files
                    if any(
                        p in low_f
                        for p in [
                            "generated", ".gen.", "_gen.", "_generated.",
                            "proto", ".pb.", ".grpc.",
                        ]
                    ):
                        continue

                    # Skip vendor/third-party directories
                    if any(
                        low_f.startswith(v) or f"/{v}" in low_f
                        for v in [
                            "vendor/", "node_modules/", "bower_components/",
                            ".venv/", "venv/", "env/",
                            "third-party/", "third_party/",
                        ]
                    ):
                        continue

                    # Skip migrations (optional)
                    if ignore_migrations and any(
                        p in low_f
                        for p in ["migrations/", "/migrations/", "/migrate/", "db/migrate/"]
                    ):
                        continue

                    file_evidence[file_path].append({
                        "evidence_type": evidence_type,
                        "recommendation_run_id": out.recommendation_run_id,
                        "recommendation_outcome_id": out.recommendation_outcome_id,
                        "pull_request_id": pr_id,
                        "incident_id": incident_id,
                        "rollback_ts": rollback_ts,
                        "created_at": rollback_ts or rec.created_at,
                        "rollback_occurred": out.rollback_occurred,
                        "escaped_defect": out.escaped_defect,
                    })

        _collect_evidence(rollback_outcomes, "ROLLBACK")
        _collect_evidence(incident_outcomes, "INCIDENT")

        # ---------------------------------------------------------------- #
        # 5. Filter, score, and persist patterns                            #
        # ---------------------------------------------------------------- #
        patterns_mined = 0
        skipped_no_hard_gate = 0
        skipped_below_threshold = 0

        for file_path in sorted(file_evidence.keys()):
            raw_items = file_evidence[file_path]

            # Deduplicate: one entry per (recommendation_run_id, evidence_type)
            seen_keys: Set[Tuple[uuid.UUID, str]] = set()
            deduped: List[Dict[str, Any]] = []
            for ev in raw_items:
                key = (ev["recommendation_run_id"], ev["evidence_type"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    deduped.append(ev)

            # ---------------------------------------------------------- #
            # Hard gate: pattern MUST have at least one confirmed incident #
            # linkage OR rollback evidence (no inference accepted)         #
            # ---------------------------------------------------------- #
            has_incident = any(ev["escaped_defect"] for ev in deduped)
            has_rollback = any(ev["rollback_occurred"] for ev in deduped)

            if not has_incident and not has_rollback:
                skipped_no_hard_gate += 1
                continue

            # Minimum evidence threshold
            evidence_count = len(deduped)
            distinct_prs = {ev["pull_request_id"] for ev in deduped}
            distinct_prs_count = len(distinct_prs)

            if (
                evidence_count < self.MIN_EVIDENCE_LINKS
                or distinct_prs_count < self.MIN_DISTINCT_PRS
            ):
                skipped_below_threshold += 1
                continue

            normalized_pattern_key = f"ESCAPED_DEFECT_PATTERN:{file_path}"

            # Honour manual invalidation overrides
            if normalized_pattern_key in invalidated_keys:
                continue

            # ---------------------------------------------------------- #
            # Scoring                                                      #
            # ---------------------------------------------------------- #
            rollback_count = sum(1 for ev in deduped if ev["rollback_occurred"])
            incident_count = sum(1 for ev in deduped if ev["escaped_defect"])

            # 1. Incident score  (escalates fastest — saturates at 3 events)
            incident_score = min(incident_count / self.INCIDENT_SATURATION, 1.0) * 100.0

            # 2. Rollback score  (progressive — repeated rollbacks increase heavily)
            rollback_score = min(rollback_count / self.ROLLBACK_SATURATION, 1.0) * 100.0

            # 3. Recency score  (exponential decay, half-life 14 days)
            timestamps = [
                ev["created_at"]
                for ev in deduped
                if ev.get("created_at")
            ]
            last_seen = max(timestamps) if timestamps else datetime.utcnow()
            days_since = max(
                (evidence_bundle.evidence_window_end - last_seen).days, 0
            )
            recency_score = math.exp(-days_since / 14.0) * 100.0

            # 4. Frequency score (raw event count, saturates at 10)
            freq_score = min(evidence_count / 10.0, 1.0) * 100.0

            # 5. Density score  (events relative to total runs in the window)
            effective_total = max(evidence_bundle.total_runs_in_window, 20)
            density_score = (evidence_count / effective_total) * 100.0

            # Weighted composite
            weighted_score = round(
                self.W_INCIDENT * incident_score
                + self.W_ROLLBACK * rollback_score
                + self.W_RECENCY  * recency_score
                + self.W_FREQ     * freq_score
                + self.W_DENSITY  * density_score,
                2,
            )

            # ---------------------------------------------------------- #
            # Risk classification                                          #
            # ---------------------------------------------------------- #
            # Incident-linked patterns escalate faster:
            # incident events push the score toward CRITICAL more aggressively
            # than rollback-only events (already encoded via W_INCIDENT > W_ROLLBACK).
            if weighted_score >= 80.0:
                risk_level = "CRITICAL"
            elif weighted_score >= 50.0:
                risk_level = "HIGH"
            elif weighted_score >= 30.0:
                risk_level = "MODERATE"
            else:
                risk_level = "LOW"

            # ---------------------------------------------------------- #
            # Confidence level                                             #
            # ---------------------------------------------------------- #
            if evidence_count >= 5 and distinct_prs_count >= 3 and days_since < 30:
                confidence_level = "HIGH"
            elif evidence_count >= 2 and distinct_prs_count >= 1 and days_since < 90:
                confidence_level = "MODERATE"
            else:
                confidence_level = "LOW"

            # ---------------------------------------------------------- #
            # Human-readable explanation (Rule 3 template)                 #
            # ---------------------------------------------------------- #
            module_label = file_path
            event_parts: List[str] = []
            if rollback_count:
                event_parts.append(
                    f"{rollback_count} rollback-linked production regression"
                    + ("s" if rollback_count != 1 else "")
                )
            if incident_count:
                event_parts.append(
                    f"{incident_count} confirmed production incident"
                    + ("s" if incident_count != 1 else "")
                )
            event_summary = " and ".join(event_parts)
            explanation = (
                f"Changes involving {module_label} contributed to "
                f"{event_summary} in the last "
                f"{evidence_bundle.history_window_days} days."
            )

            # ---------------------------------------------------------- #
            # Overwrite protection                                          #
            # ---------------------------------------------------------- #
            existing = (
                db.query(FragilityPattern)
                .filter(
                    FragilityPattern.repository_id == repository_id,
                    FragilityPattern.normalized_pattern_key == normalized_pattern_key,
                )
                .first()
            )

            if existing:
                existing_window_end_str = existing.replayable_evidence_snapshot.get(
                    "evidence_window_end"
                )
                is_newer_window = True
                if existing_window_end_str:
                    try:
                        existing_window_end = datetime.fromisoformat(
                            existing_window_end_str
                        )
                        is_newer_window = (
                            evidence_bundle.evidence_window_end > existing_window_end
                        )
                    except Exception:
                        pass

                is_stronger = evidence_count > existing.evidence_count
                is_newer_version = self.SCORING_VERSION != existing.scoring_formula_version

                if is_newer_window or is_stronger or is_newer_version:
                    db.delete(existing)
                    db.commit()
                else:
                    continue

            # ---------------------------------------------------------- #
            # Deterministic evidence IDs (UUID v5)                         #
            # ---------------------------------------------------------- #
            sorted_deduped = sorted(
                deduped,
                key=lambda x: (
                    x.get("created_at") or datetime.min,
                    str(x.get("recommendation_run_id") or ""),
                    str(x.get("recommendation_outcome_id") or ""),
                ),
            )

            evidence_ids: List[str] = []
            for ev in sorted_deduped:
                namespace_payload = (
                    f"{normalized_pattern_key}|{ev['evidence_type']}|"
                    f"{ev['recommendation_run_id']}|{ev['pull_request_id']}|"
                    f"{self.NORMALIZATION_RULES_VERSION}|{self.SCORING_VERSION}|"
                    f"{evidence_bundle.evidence_window_start.isoformat()}->"
                    f"{evidence_bundle.evidence_window_end.isoformat()}"
                )
                det_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, namespace_payload))
                evidence_ids.append(det_uuid)

            # ---------------------------------------------------------- #
            # Replayable evidence snapshot                                 #
            # ---------------------------------------------------------- #
            linked_prs = sorted({str(ev["pull_request_id"]) for ev in sorted_deduped})
            linked_rec_ids = sorted(
                {str(ev["recommendation_run_id"]) for ev in sorted_deduped}
            )
            linked_incident_ids = sorted(
                {ev["incident_id"] for ev in sorted_deduped if ev.get("incident_id")}
            )
            rollback_timestamps = sorted(
                {
                    ev["rollback_ts"].isoformat()
                    for ev in sorted_deduped
                    if ev.get("rollback_occurred") and ev.get("rollback_ts")
                }
            )

            evidence_counts_by_type: Dict[str, int] = {}
            for ev in sorted_deduped:
                evidence_counts_by_type[ev["evidence_type"]] = (
                    evidence_counts_by_type.get(ev["evidence_type"], 0) + 1
                )

            summary_stats = {
                "total_evidence": evidence_count,
                "distinct_prs_count": distinct_prs_count,
                "days_since_last_seen": days_since,
                "rollback_count": rollback_count,
                "incident_count": incident_count,
            }

            evidence_bundle_payload = (
                f"key:{normalized_pattern_key}|prs:{linked_prs}|"
                f"recs:{linked_rec_ids}|incidents:{linked_incident_ids}"
            )
            bundle_hash = hashlib.sha256(
                evidence_bundle_payload.encode("utf-8")
            ).hexdigest()

            replayable_snapshot = {
                # Pattern 2 requirements — all four fields present
                "affected_files": [file_path],
                "linked_recommendation_ids": linked_rec_ids,
                "linked_incidents": linked_incident_ids,
                "rollback_timestamps": rollback_timestamps,
                # Standard replayability fields
                "evidence_ids": sorted(evidence_ids),
                "evidence_counts": evidence_counts_by_type,
                "source_entity_references": [file_path],
                "evidence_bundle_hash": bundle_hash,
                "linked_prs": linked_prs,
                "summary_statistics": summary_stats,
                "evidence_window_start": evidence_bundle.evidence_window_start.isoformat(),
                "evidence_window_end": evidence_bundle.evidence_window_end.isoformat(),
            }

            score_components = {
                "incident": incident_score,
                "rollback": rollback_score,
                "recency": recency_score,
                "frequency": freq_score,
                "density": density_score,
            }

            # Deterministic pattern hash
            hash_payload = {
                "normalized_pattern_key": normalized_pattern_key,
                "evidence_ids": sorted(evidence_ids),
                "score_components": score_components,
                "evidence_window_start": evidence_bundle.evidence_window_start.isoformat(),
                "evidence_window_end": evidence_bundle.evidence_window_end.isoformat(),
                "scoring_formula_version": self.SCORING_VERSION,
            }
            serialized = json.dumps(hash_payload, sort_keys=True, separators=(",", ":"))
            pattern_hash_val = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

            # Supplementary context metadata
            context = {
                "affected_file": file_path,
                "rollback_count": rollback_count,
                "incident_count": incident_count,
                "linked_recommendation_ids": linked_rec_ids,
                "linked_incident_ids": linked_incident_ids,
                "rollback_timestamps": rollback_timestamps,
            }

            # ---------------------------------------------------------- #
            # Persist pattern                                               #
            # ---------------------------------------------------------- #
            file_basename = file_path.split("/")[-1].split(".")[0]

            pattern = FragilityPattern(
                id=uuid.uuid4(),
                repository_id=repository_id,
                pattern_type="ESCAPED_DEFECT_PATTERN",
                normalized_pattern_key=normalized_pattern_key,
                title=f"Escaped Defect: {file_basename}",
                explanation=explanation,
                fragility_score=weighted_score,
                risk_level=risk_level,
                confidence_level=confidence_level,
                pattern_hash=pattern_hash_val,
                score_components=score_components,
                replayable_evidence_snapshot=replayable_snapshot,
                fragility_generation_version=self.GENERATION_VERSION,
                scoring_formula_version=self.SCORING_VERSION,
                evidence_count=evidence_count,
                incident_count=incident_count,
                related_failure_count=evidence_count,
                status="ACTIVE",
                context=context,
                first_seen_at=min(timestamps) if timestamps else datetime.utcnow(),
                last_seen_at=last_seen,
            )
            db.add(pattern)
            db.flush()

            # Persist evidence links
            for idx, ev in enumerate(sorted_deduped):
                rollback_note = (
                    f" Rollback occurred at {ev['rollback_ts'].isoformat()}."
                    if ev.get("rollback_occurred") and ev.get("rollback_ts")
                    else ""
                )
                incident_note = (
                    f" Incident ID: {ev['incident_id']}."
                    if ev.get("escaped_defect") and ev.get("incident_id")
                    else ""
                )
                link_summary = (
                    f"File '{file_path}' was modified in recommendation run "
                    f"'{ev['recommendation_run_id']}' (PR: {ev['pull_request_id']}) "
                    f"which produced a confirmed {ev['evidence_type'].lower()} event."
                    f"{rollback_note}{incident_note}"
                )
                link = FragilityEvidenceLink(
                    id=uuid.UUID(evidence_ids[idx]),
                    fragility_pattern_id=pattern.id,
                    evidence_type=ev["evidence_type"],
                    source_recommendation_run_id=ev["recommendation_run_id"],
                    source_pull_request_id=ev["pull_request_id"],
                    source_incident_id=ev.get("incident_id"),
                    evidence_summary=link_summary,
                )
                db.add(link)

            patterns_mined += 1

        db.commit()

        logger.info(
            "EscapedDefectLinkageEngine finished: %d patterns mined, "
            "%d skipped (no hard gate), %d skipped (below threshold).",
            patterns_mined,
            skipped_no_hard_gate,
            skipped_below_threshold,
        )

        return {
            "patterns_mined": patterns_mined,
            "diagnostics": {
                "skipped_no_hard_gate": skipped_no_hard_gate,
                "skipped_below_threshold": skipped_below_threshold,
            },
        }

    # ================================================================== #
    # Lifecycle: stale decay                                               #
    # ================================================================== #

    def apply_stale_decay(
        self,
        repository_id: uuid.UUID,
        now: Optional[datetime] = None,
    ) -> int:
        """
        Applies a cautious stale decay of 10 % every 30 days to active
        ESCAPED_DEFECT_PATTERN patterns:
          - score_new = score_orig × 0.9^(days/30)
          - Transition to STALE after 90 days of inactivity.
          - Transition to INVALIDATED with reason STALE_NO_RECENT_EVIDENCE
            after 180 days.

        Escaped-defect patterns are intentionally kept alive longer than
        most other pattern types because organizational memory of production
        regressions must not decay prematurely.
        """
        now_time = now or datetime.utcnow()
        active_patterns = (
            self.db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.pattern_type == "ESCAPED_DEFECT_PATTERN",
                FragilityPattern.status == "ACTIVE",
            )
            .all()
        )

        decayed_count = 0
        for p in active_patterns:
            days_since = max((now_time - p.last_seen_at).days, 0)

            if days_since >= self.STALE_AFTER_DAYS:
                decay_ratio = 0.9 ** (days_since / 30.0)
                p.fragility_score = round(p.fragility_score * decay_ratio, 2)

                new_components = dict(p.score_components)
                new_components["decayed"] = True
                new_components["decay_days"] = days_since
                p.score_components = new_components
                p.updated_at = now_time
                decayed_count += 1

                if days_since >= self.INVALIDATE_AFTER_DAYS:
                    p.status = "INVALIDATED"
                    p.invalidated_reason = "STALE_NO_RECENT_EVIDENCE"
                    p.invalidated_at = now_time
                    p.invalidated_by = "SYSTEM_DECAY"
                    logger.info(
                        "Pattern %s transitioned to INVALIDATED (age > %d days).",
                        p.normalized_pattern_key,
                        self.INVALIDATE_AFTER_DAYS,
                    )
                else:
                    p.status = "STALE"
                    logger.info(
                        "Pattern %s transitioned to STALE (age > %d days).",
                        p.normalized_pattern_key,
                        self.STALE_AFTER_DAYS,
                    )

        self.db.commit()
        return decayed_count
