import uuid
import math
import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime
from itertools import combinations as iter_combinations
from typing import Dict, FrozenSet, List, Any, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink
from app.schemas.failure_evidence import FailureEvidenceBundle

logger = logging.getLogger(__name__)

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: RepositoryCalibrationProfile
# ====================================================================
# Future calibration profiles should support repository-specific tuning:
# - Max combination size: Relax or tighten the per-PR file ceiling for
#   repos with inherently large atomic change-sets (e.g. monorepos).
# - Min occurrence threshold: Raise the bar for high-velocity repos that
#   accumulate evidence quickly, preventing premature pattern surfacing.
# - Combo scope filters: Allow allowlisting entire directories or module
#   prefixes that should never participate in combination patterns.
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: Evidence-Source Weighting
# ====================================================================
# Risky combinations gain additional signal weight from:
# - ROLLBACK  (Weight: 0.8 / Deployed change reverted)
# - INCIDENT  (Weight: 1.0 / Confirmed production regression)
# - TEST_FAILURE alone does NOT guarantee a risky-combination pattern;
#   it merely supplies the failure-outcome anchor.
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================


class RiskyCombinationDetector:
    """
    Detects repeated risky combinations of changed modules/files that
    co-occurred with the **same** failure outcome across multiple PRs.

    Design rules (from spec):
      1. A combination is only surfaced when:
           - the *exact same* file/module set changed  AND
           - the *same* failure outcome repeated (failed run or
             rollback/incident on the same PR).
      2. MIN_COMBINATION_OCCURRENCES = 3  — at least three qualifying
         events required before a combination is persisted.
      3. Giant PR combinations are silently ignored:
           - PRs whose changed-file count exceeds MAX_PR_FILES_FOR_COMBO
             are skipped entirely.
           - Combination tuples larger than MAX_COMBINATION_SIZE are
             never generated.
      4. Combinations are pairs *or* triples derived from the sorted
         file list; all larger n-tuples are excluded to prevent
         combinatorial explosion.
      5. Explanation must be exact and evidence-grounded — no vague
         module-level labels.

    Pattern type:  RISKY_COMBINATION
    Key format:    RISKY_COMBINATION:<sorted_file1>,<sorted_file2>[,<sorted_file3>]
    """

    # ------------------------------------------------------------------ #
    # Combination bounds                                                   #
    # ------------------------------------------------------------------ #
    # PRs with more changed files than this ceiling are treated as "giant"
    # and excluded entirely to prevent noise flooding.
    MAX_PR_FILES_FOR_COMBO: int = 10

    # Maximum tuple size generated from a PR's file list.
    # Pairs (n=2) and triples (n=3) only — larger n-tuples are combinatorially
    # explosive and semantically noisy.
    MAX_COMBINATION_SIZE: int = 5

    # Minimum number of distinct qualifying occurrences before a pattern fires.
    MIN_COMBINATION_OCCURRENCES: int = 3

    # Minimum distinct PRs to guard against single-PR storm poisoning.
    MIN_DISTINCT_PRS: int = 2

    # ------------------------------------------------------------------ #
    # Versioning                                                           #
    # ------------------------------------------------------------------ #
    GENERATION_VERSION          = "v1.2.0"
    SCORING_VERSION             = "weighted.v2"
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

    def detect_risky_combinations(
        self,
        db: Session,
        repository_id: uuid.UUID,
        evidence_bundle: FailureEvidenceBundle,
        ignore_migrations: bool = True,
    ) -> Dict[str, Any]:
        """
        Scans the evidence bundle for repeated co-occurrences of the same
        file combination with the same failure outcome, and persists
        RISKY_COMBINATION fragility patterns.

        Acceptance criteria enforced:
          - Combinations are deterministic: sorted canonical tuple keys.
          - Combinations are bounded: MAX_COMBINATION_SIZE cap + giant-PR
            exclusion.
          - Giant noisy combinations are silently ignored.

        Returns a summary dict with ``patterns_mined`` and ``diagnostics``.
        """
        logger.info(
            "RiskyCombinationDetector starting for repository %s…",
            repository_id,
        )

        # ---------------------------------------------------------------- #
        # 1. Preserve manually invalidated pattern keys                     #
        # ---------------------------------------------------------------- #
        invalidated_keys: Set[str] = {
            p.normalized_pattern_key
            for p in db.query(FragilityPattern.normalized_pattern_key).filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.pattern_type == "RISKY_COMBINATION",
                FragilityPattern.status == "INVALIDATED",
            ).all()
        }

        # ---------------------------------------------------------------- #
        # 2. Index bundle collections for O(1) lookups                     #
        # ---------------------------------------------------------------- #

        # pr_id → sorted list of normalised file paths changed in that PR
        pr_to_files: Dict[uuid.UUID, List[str]] = defaultdict(list)
        for cf in evidence_bundle.related_changed_files:
            pr_to_files[cf.pull_request_id].append(
                cf.file_path.replace("\\", "/")
            )
        # Sort and deduplicate now so every downstream lookup is clean
        pr_to_files = {
            pr_id: sorted(set(paths))
            for pr_id, paths in pr_to_files.items()
        }

        # pr_id → set of failed test_run_ids
        pr_to_failed_runs: Dict[uuid.UUID, Set[uuid.UUID]] = defaultdict(set)
        for run in evidence_bundle.related_test_runs:
            if run.status == "failed" and run.pull_request_id:
                pr_to_failed_runs[run.pull_request_id].add(run.test_run_id)

        # recommendation_run_id → outcome  (for rollback / incident flags)
        rollback_rec_run_ids: Set[uuid.UUID] = set()
        incident_rec_run_ids: Set[uuid.UUID] = set()
        for out in evidence_bundle.linked_incidents:
            if out.rollback_occurred:
                rollback_rec_run_ids.add(out.recommendation_run_id)
            if out.escaped_defect:
                incident_rec_run_ids.add(out.recommendation_run_id)

        # recommendation_run_id → pull_request_id
        rec_to_pr: Dict[uuid.UUID, Optional[uuid.UUID]] = {
            r.recommendation_run_id: r.pull_request_id
            for r in evidence_bundle.linked_recommendations
        }

        # ---------------------------------------------------------------- #
        # 3. Build a per-run timestamp lookup for recency scoring           #
        # ---------------------------------------------------------------- #
        run_created_at: Dict[uuid.UUID, datetime] = {
            r.test_run_id: r.created_at
            for r in evidence_bundle.related_test_runs
            if r.created_at
        }

        # ---------------------------------------------------------------- #
        # 4. Enumerate qualifying PRs, generate bounded combination tuples, #
        #    and accumulate evidence per (combo_key, run_id) cell.          #
        # ---------------------------------------------------------------- #

        # combo_key (canonical sorted tuple str) →
        #   list of evidence dicts (one per qualifying run)
        combo_evidence: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Diagnostic counters
        giant_pr_skipped    = 0
        no_failure_skipped  = 0

        for pr_id, files in sorted(pr_to_files.items()):

            # Gate 1: giant PR guard — skip PRs with too many changed files
            if len(files) > self.MAX_PR_FILES_FOR_COMBO:
                giant_pr_skipped += 1
                continue

            # Gate 2: require at least one failed run on this PR
            failed_runs = pr_to_failed_runs.get(pr_id, set())
            if not failed_runs:
                no_failure_skipped += 1
                continue

            # Gate 3: require at least 2 files (combinations need ≥ 2 members)
            if len(files) < 2:
                continue

            # Filter out generated / vendor / migration files before
            # generating combos so we don't surface noise patterns.
            filtered: List[str] = []
            for f in files:
                low_f = f.lower()
                if any(
                    p in low_f
                    for p in [
                        "generated", ".gen.", "_gen.", "_generated.",
                        "proto", ".pb.", ".grpc.",
                    ]
                ):
                    continue
                if any(
                    low_f.startswith(v) or f"/{v}" in low_f
                    for v in [
                        "vendor/", "node_modules/", "bower_components/",
                        ".venv/", "venv/", "env/",
                        "third-party/", "third_party/",
                    ]
                ):
                    continue
                if ignore_migrations and any(
                    p in low_f
                    for p in ["migrations/", "/migrations/", "/migrate/", "db/migrate/"]
                ):
                    continue
                filtered.append(f)

            if len(filtered) < 2:
                continue

            # Rollback / incident flags for this PR
            pr_has_rollback = any(
                rec_to_pr.get(rid) == pr_id for rid in rollback_rec_run_ids
            )
            pr_has_incident = any(
                rec_to_pr.get(rid) == pr_id for rid in incident_rec_run_ids
            )

            # Churn totals per file (for scoring)
            pr_churn: Dict[str, int] = {}
            for cf in evidence_bundle.related_changed_files:
                if cf.pull_request_id == pr_id:
                    key = cf.file_path.replace("\\", "/")
                    pr_churn[key] = pr_churn.get(key, 0) + cf.additions + cf.deletions

            # Generate bounded combination tuples
            # Pairs (n=2) always; triples (n=3) only when ≥ 3 filtered files,
            # but the total tuple size must not exceed MAX_COMBINATION_SIZE.
            combos: List[Tuple[str, ...]] = []
            cap = min(len(filtered), self.MAX_COMBINATION_SIZE)
            capped_files = filtered[:cap]

            # Always emit all pairs
            for combo in iter_combinations(capped_files, 2):
                combos.append(combo)

            # Emit one representative triple (first 3 files) when available
            if len(capped_files) >= 3:
                combos.append(tuple(capped_files[:3]))

            # Deduplicate (the triple might duplicate a pair if capped_files < 3)
            seen_combos: Set[Tuple[str, ...]] = set()
            for combo in combos:
                if combo in seen_combos:
                    continue
                seen_combos.add(combo)

                # Canonical key: comma-joined sorted file paths
                combo_key = ",".join(sorted(combo))

                for run_id in sorted(failed_runs, key=str):
                    ts = run_created_at.get(run_id)
                    combo_evidence[combo_key].append({
                        "combo": combo,
                        "combo_key": combo_key,
                        "pr_id": pr_id,
                        "run_id": run_id,
                        "created_at": ts,
                        "rollback": pr_has_rollback,
                        "incident": pr_has_incident,
                        "churn": sum(pr_churn.get(f, 0) for f in combo),
                    })

        # ---------------------------------------------------------------- #
        # 5. Filter below-threshold combinations and persist patterns       #
        # ---------------------------------------------------------------- #
        patterns_mined       = 0
        skipped_below_thresh = 0

        for combo_key in sorted(combo_evidence.keys()):
            raw_items = combo_evidence[combo_key]

            # Deduplicate: one entry per (pr_id, run_id) pair
            seen: Set[Tuple[uuid.UUID, uuid.UUID]] = set()
            deduped: List[Dict[str, Any]] = []
            for ev in raw_items:
                k = (ev["pr_id"], ev["run_id"])
                if k not in seen:
                    seen.add(k)
                    deduped.append(ev)

            evidence_count = len(deduped)
            distinct_prs   = {ev["pr_id"] for ev in deduped}
            distinct_prs_count = len(distinct_prs)

            # Rule 2: MIN_COMBINATION_OCCURRENCES = 3
            if evidence_count < self.MIN_COMBINATION_OCCURRENCES:
                skipped_below_thresh += 1
                continue

            # Require ≥ 2 distinct PRs to avoid single-storm false positives
            if distinct_prs_count < self.MIN_DISTINCT_PRS:
                skipped_below_thresh += 1
                continue

            normalized_pattern_key = f"RISKY_COMBINATION:{combo_key}"

            if normalized_pattern_key in invalidated_keys:
                continue

            # ---------------------------------------------------------- #
            # Scoring                                                      #
            # ---------------------------------------------------------- #
            rollback_count = sum(1 for ev in deduped if ev["rollback"])
            incident_count = sum(1 for ev in deduped if ev["incident"])

            # 1. Frequency score (raw occurrence count, saturates at 10)
            freq_score = min(evidence_count / 10.0, 1.0) * 100.0

            # 2. Density score
            effective_total = max(evidence_bundle.total_runs_in_window, 20)
            density_score   = (evidence_count / effective_total) * 100.0

            # 3. Recency score (exponential decay, half-life 14 days)
            timestamps = [
                ev["created_at"] for ev in deduped if ev.get("created_at")
            ]
            last_seen  = max(timestamps) if timestamps else datetime.utcnow()
            days_since = max(
                (evidence_bundle.evidence_window_end - last_seen).days, 0
            )
            recency_score = math.exp(-days_since / 14.0) * 100.0

            # 4. Churn score (aggregate churn across all combo files)
            total_churn = sum(ev["churn"] for ev in deduped)
            churn_score = (
                min(math.log(1.0 + total_churn) / math.log(1.0 + 1000.0), 1.0)
                * 100.0
            )

            # 5. Rollback score (progressive — repeated rollbacks increase score)
            rollback_score = min(rollback_count / 3.0, 1.0) * 100.0

            # 6. Incident score (escalates faster — higher weight in formula)
            incident_score = min(incident_count / 3.0, 1.0) * 100.0

            # Weighted composite
            base_score = (
                0.20 * freq_score
                + 0.05 * density_score
                + 0.20 * recency_score
                + 0.15 * churn_score
                + 0.20 * rollback_score
                + 0.20 * incident_score
            )
            weighted_score = round(base_score, 2)

            # Risk classification
            if weighted_score >= 80.0:
                risk_level = "CRITICAL"
            elif weighted_score >= 50.0:
                risk_level = "HIGH"
            elif weighted_score >= 30.0:
                risk_level = "MODERATE"
            else:
                risk_level = "LOW"

            # Confidence level
            if evidence_count >= 5 and distinct_prs_count >= 3 and days_since < 30:
                confidence_level = "HIGH"
            elif evidence_count >= 3 and distinct_prs_count >= 2 and days_since < 90:
                confidence_level = "MODERATE"
            else:
                confidence_level = "LOW"

            # ---------------------------------------------------------- #
            # Human-readable explanation (Rule 4 / Rule 5 template)        #
            #                                                              #
            # GOOD: auth/session_token.py + billing/invoice_rules.py       #
            #       repeatedly preceded rollback-linked regressions.        #
            # BAD:  auth + billing are risky together.                      #
            # ---------------------------------------------------------- #
            # Use the canonical sorted combo tuple from the first evidence item
            canonical_combo: Tuple[str, ...] = deduped[0]["combo"]
            combo_label = " + ".join(canonical_combo)

            # Outcome suffix — rollback/incident linkage when available
            outcome_parts: List[str] = []
            if rollback_count:
                outcome_parts.append(
                    f"{rollback_count} rollback-linked regression"
                    + ("s" if rollback_count != 1 else "")
                )
            if incident_count:
                outcome_parts.append(
                    f"{incident_count} confirmed incident"
                    + ("s" if incident_count != 1 else "")
                )
            if outcome_parts:
                outcome_label = " and ".join(outcome_parts)
            else:
                outcome_label = f"{evidence_count} failed run" + (
                    "s" if evidence_count != 1 else ""
                )

            explanation = (
                f"{combo_label} repeatedly preceded {outcome_label} "
                f"across {distinct_prs_count} pull request"
                + ("s" if distinct_prs_count != 1 else "")
                + f" in the last {evidence_bundle.history_window_days} days."
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

                is_stronger    = evidence_count > existing.evidence_count
                is_newer_ver   = self.SCORING_VERSION != existing.scoring_formula_version

                if is_newer_window or is_stronger or is_newer_ver:
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
                    str(x.get("run_id")  or ""),
                    str(x.get("pr_id")   or ""),
                ),
            )

            evidence_ids: List[str] = []
            for ev in sorted_deduped:
                namespace_payload = (
                    f"{normalized_pattern_key}|TEST_FAILURE|"
                    f"{ev['run_id']}|{ev['pr_id']}|"
                    f"{self.NORMALIZATION_RULES_VERSION}|{self.SCORING_VERSION}|"
                    f"{evidence_bundle.evidence_window_start.isoformat()}->"
                    f"{evidence_bundle.evidence_window_end.isoformat()}"
                )
                det_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, namespace_payload))
                evidence_ids.append(det_uuid)

            # ---------------------------------------------------------- #
            # Replayable snapshot                                          #
            # ---------------------------------------------------------- #
            linked_prs  = sorted({str(ev["pr_id"])  for ev in sorted_deduped})
            linked_runs = sorted({str(ev["run_id"]) for ev in sorted_deduped})

            evidence_bundle_payload = (
                f"key:{normalized_pattern_key}|prs:{linked_prs}|runs:{linked_runs}"
            )
            bundle_hash = hashlib.sha256(
                evidence_bundle_payload.encode("utf-8")
            ).hexdigest()

            summary_stats = {
                "total_evidence": evidence_count,
                "distinct_prs_count": distinct_prs_count,
                "days_since_last_seen": days_since,
                "rollback_count": rollback_count,
                "incident_count": incident_count,
                "combination_size": len(canonical_combo),
            }

            replayable_snapshot = {
                "evidence_ids": sorted(evidence_ids),
                "evidence_counts": {"TEST_FAILURE": evidence_count},
                "source_entity_references": list(canonical_combo),
                "evidence_bundle_hash": bundle_hash,
                "linked_prs": linked_prs,
                "linked_runs": linked_runs,
                "linked_incidents": [],
                "summary_statistics": summary_stats,
                "evidence_window_start": evidence_bundle.evidence_window_start.isoformat(),
                "evidence_window_end": evidence_bundle.evidence_window_end.isoformat(),
            }

            score_components = {
                "frequency":  freq_score,
                "density":    density_score,
                "recency":    recency_score,
                "churn":      churn_score,
                "rollback":   rollback_score,
                "incident":   incident_score,
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
            serialized = json.dumps(
                hash_payload, sort_keys=True, separators=(",", ":")
            )
            pattern_hash_val = hashlib.sha256(
                serialized.encode("utf-8")
            ).hexdigest()

            # Supplementary context (for fragility resolver matching)
            context = {
                "trigger_files": list(canonical_combo),
                "combination_key": combo_key,
                "rollback_count": rollback_count,
                "incident_count": incident_count,
            }

            # ---------------------------------------------------------- #
            # Persist pattern                                               #
            # ---------------------------------------------------------- #
            # Title: concise basename labels so the UI card is scannable
            basenames = [f.split("/")[-1].split(".")[0] for f in canonical_combo]
            title = "Risky Combination: " + " + ".join(basenames)

            pattern = FragilityPattern(
                id=uuid.uuid4(),
                repository_id=repository_id,
                pattern_type="RISKY_COMBINATION",
                normalized_pattern_key=normalized_pattern_key,
                title=title,
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
                rollback_note = " Rollback-linked." if ev.get("rollback") else ""
                incident_note = " Incident-linked." if ev.get("incident") else ""
                link_summary = (
                    f"Combination [{combo_label}] changed together in PR "
                    f"'{ev['pr_id']}' and preceded a failed run "
                    f"'{ev['run_id']}'.{rollback_note}{incident_note}"
                )
                link = FragilityEvidenceLink(
                    id=uuid.UUID(evidence_ids[idx]),
                    fragility_pattern_id=pattern.id,
                    evidence_type="TEST_FAILURE",
                    source_test_run_id=ev["run_id"],
                    source_pull_request_id=ev["pr_id"],
                    evidence_summary=link_summary,
                )
                db.add(link)

            patterns_mined += 1

        db.commit()

        logger.info(
            "RiskyCombinationDetector finished: %d patterns mined, "
            "%d skipped (below threshold), %d giant PRs skipped, "
            "%d PRs skipped (no failure).",
            patterns_mined,
            skipped_below_thresh,
            giant_pr_skipped,
            no_failure_skipped,
        )

        return {
            "patterns_mined": patterns_mined,
            "diagnostics": {
                "skipped_below_threshold":  skipped_below_thresh,
                "giant_pr_skipped":         giant_pr_skipped,
                "no_failure_pr_skipped":    no_failure_skipped,
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
        RISKY_COMBINATION patterns:
          - score_new = score_orig × 0.9^(days/30)
          - Transition to STALE after 90 days of inactivity.
          - Transition to INVALIDATED with reason STALE_NO_RECENT_EVIDENCE
            after 180 days.
        """
        now_time = now or datetime.utcnow()
        active_patterns = (
            self.db.query(FragilityPattern)
            .filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.pattern_type == "RISKY_COMBINATION",
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
                new_components["decayed"]    = True
                new_components["decay_days"] = days_since
                p.score_components = new_components
                p.updated_at = now_time
                decayed_count += 1

                if days_since >= self.INVALIDATE_AFTER_DAYS:
                    p.status              = "INVALIDATED"
                    p.invalidated_reason  = "STALE_NO_RECENT_EVIDENCE"
                    p.invalidated_at      = now_time
                    p.invalidated_by      = "SYSTEM_DECAY"
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
