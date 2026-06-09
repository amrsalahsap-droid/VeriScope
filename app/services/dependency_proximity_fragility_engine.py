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
from app.models.dependency import FileDependency
from app.schemas.failure_evidence import FailureEvidenceBundle

logger = logging.getLogger(__name__)

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: RepositoryCalibrationProfile
# ====================================================================
# Future calibration profiles should support repository-specific calibrations:
# - Dependency graph density: Relax or tighten proximity scoring for
#   highly interconnected vs loosely coupled repos.
# - Module churn velocity: Adjust fragility thresholds for repos with
#   high baseline churn.
# - Incident severity weighting: Allow per-repo tuning of incident
#   contribution to the proximity score.
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================


class DependencyProximityFragilityEngine:
    """
    Detects unstable dependency neighborhoods by identifying files/modules
    that are repeatedly involved in:
      - dependency-expanded recommendation runs
      - failed downstream test executions
      - rollback-linked recommendation outcomes

    All evidence is derived exclusively from existing FileDependency records
    and the provided FailureEvidenceBundle — no dependency assumptions are
    introduced outside of stored evidence.

    Pattern type: DEPENDENCY_PROXIMITY
    Key format:   DEPENDENCY_PROXIMITY:<source_file>-><downstream_file>
    """

    # Minimum number of evidence links required to surface a pattern
    MIN_EVIDENCE_LINKS = 3

    # Minimum distinct PRs to avoid single-incident noise
    MIN_DISTINCT_PRS = 2

    # BFS expansion depth cap (mirrors FailureNeighborhoodCorrelationEngine)
    MAX_EXPANSION_DEPTH = 2

    # Weight decay per BFS hop (distance 0→1.0, 1→0.7, 2→0.4)
    DISTANCE_WEIGHTS = {0: 1.0, 1: 0.7, 2: 0.4}

    GENERATION_VERSION = "v1.2.0"
    SCORING_VERSION = "weighted.v2"
    NORMALIZATION_RULES_VERSION = "rules.v1"

    # Lifecycle
    STALE_AFTER_DAYS = 90
    INVALIDATE_AFTER_DAYS = 180

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_dependency_fragility(
        self,
        db: Session,
        repository_id: uuid.UUID,
        evidence_bundle: FailureEvidenceBundle,
        ignore_migrations: bool = True,
    ) -> Dict[str, Any]:
        """
        Main detection entry point.

        Scans the evidence bundle and existing FileDependency records to
        identify files whose dependency neighborhoods are repeatedly involved
        in downstream failures and rollback incidents.

        Returns a summary dict with ``patterns_mined`` and ``diagnostics``.
        """
        logger.info(
            "DependencyProximityFragilityEngine starting for repository %s…",
            repository_id,
        )

        # -----------------------------------------------------------------
        # 1. Preserve manually invalidated pattern keys so we never overwrite
        # -----------------------------------------------------------------
        invalidated_keys: Set[str] = {
            p.normalized_pattern_key
            for p in self.db.query(FragilityPattern.normalized_pattern_key).filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY",
                FragilityPattern.status == "INVALIDATED",
            ).all()
        }

        # -----------------------------------------------------------------
        # 2. Build an adjacency map from stored FileDependency records only
        #    (bidirectional so we capture both "imports" and "imported-by")
        # -----------------------------------------------------------------
        all_deps = (
            db.query(FileDependency)
            .filter(FileDependency.repository_id == repository_id)
            .all()
        )

        if not all_deps:
            logger.info(
                "No FileDependency records found for repository %s — "
                "DependencyProximityFragilityEngine has nothing to analyse.",
                repository_id,
            )
            return {
                "patterns_mined": 0,
                "diagnostics": {"reason": "no_dependency_data"},
            }

        # adj[source] → set of neighbours (bidirectional)
        adj: Dict[str, Set[str]] = defaultdict(set)
        for dep in all_deps:
            u = dep.file_path.replace("\\", "/")
            v = dep.depends_on_file_path.replace("\\", "/")
            adj[u].add(v)
            adj[v].add(u)

        # -----------------------------------------------------------------
        # 3. Build PR → changed files index from the evidence bundle
        # -----------------------------------------------------------------
        pr_to_changed_files: Dict[uuid.UUID, List[str]] = defaultdict(list)
        for cf in evidence_bundle.related_changed_files:
            pr_to_changed_files[cf.pull_request_id].append(
                cf.file_path.replace("\\", "/")
            )

        # pr → set of run_ids that ended in a failure
        pr_to_failed_run_ids: Dict[uuid.UUID, Set[uuid.UUID]] = defaultdict(set)
        for run in evidence_bundle.related_test_runs:
            if run.status == "failed" and run.pull_request_id:
                pr_to_failed_run_ids[run.pull_request_id].add(run.test_run_id)

        # recommendation_run_id → outcome (rollback / escaped defect)
        rollback_rec_ids: Set[uuid.UUID] = set()
        incident_rec_ids: Set[uuid.UUID] = set()
        for out in evidence_bundle.linked_incidents:
            if out.rollback_occurred:
                rollback_rec_ids.add(out.recommendation_run_id)
            if out.escaped_defect:
                incident_rec_ids.add(out.recommendation_run_id)

        # recommendation_run_id → pull_request_id (for linking outcomes to PRs)
        rec_to_pr: Dict[uuid.UUID, Optional[uuid.UUID]] = {
            r.recommendation_run_id: r.pull_request_id
            for r in evidence_bundle.linked_recommendations
        }

        # -----------------------------------------------------------------
        # 4. BFS expansion per PR: source file → downstream neighbourhood
        #    Returns {downstream_file: (distance, expansion_path, origin_file)}
        # -----------------------------------------------------------------

        def _bfs_expand(
            source_files: List[str],
        ) -> Dict[str, Tuple[int, str, str]]:
            """BFS from source_files up to MAX_EXPANSION_DEPTH hops."""
            visited: Dict[str, Tuple[int, str, str]] = {}
            queue: List[Tuple[str, int, str, str]] = []

            for f in source_files:
                visited[f] = (0, f, f)
                queue.append((f, 0, f, f))

            while queue:
                curr, dist, path, origin = queue.pop(0)
                if dist >= self.MAX_EXPANSION_DEPTH:
                    continue
                for neighbour in sorted(adj.get(curr, [])):
                    new_dist = dist + 1
                    new_path = f"{path} -> {neighbour}"
                    if neighbour not in visited or new_dist < visited[neighbour][0]:
                        visited[neighbour] = (new_dist, new_path, origin)
                        queue.append((neighbour, new_dist, new_path, origin))

            return visited

        # -----------------------------------------------------------------
        # 5. Accumulate evidence per (source_file, downstream_file) pair
        #
        # For each PR that has at least one failed run we:
        #   a. BFS-expand from its changed files using stored dependency data
        #   b. For each downstream file in the expansion that is *different*
        #      from the changed file, record an evidence hit with:
        #       - the failed run IDs
        #       - any rollback / incident linked to a rec-run on the same PR
        # -----------------------------------------------------------------

        # key: (source_file, downstream_file)
        # value: list of evidence dicts
        neighborhood_evidence: Dict[
            Tuple[str, str], List[Dict[str, Any]]
        ] = defaultdict(list)

        for pr_id, changed_files in pr_to_changed_files.items():
            failed_run_ids = pr_to_failed_run_ids.get(pr_id, set())
            if not failed_run_ids:
                # No downstream failure on this PR → skip (Rule: only evidence
                # from failed downstream runs counts)
                continue

            expansion = _bfs_expand(changed_files)

            # Rollback / incident flags for this PR
            pr_has_rollback = any(
                rec_to_pr.get(rid) == pr_id for rid in rollback_rec_ids
            )
            pr_has_incident = any(
                rec_to_pr.get(rid) == pr_id for rid in incident_rec_ids
            )

            # Churn for changed files in this PR
            pr_churn: Dict[str, int] = {}
            for cf in evidence_bundle.related_changed_files:
                if cf.pull_request_id == pr_id:
                    key = cf.file_path.replace("\\", "/")
                    pr_churn[key] = (
                        pr_churn.get(key, 0) + cf.additions + cf.deletions
                    )

            for downstream_file, (distance, exp_path, origin_file) in expansion.items():
                # Skip distance-0 entries (the changed file itself is not a
                # "downstream" node in the proximity sense)
                if distance == 0:
                    continue

                # Skip generated / vendor / migration paths
                low_d = downstream_file.lower()
                if any(
                    p in low_d
                    for p in [
                        "generated",
                        ".gen.",
                        "_gen.",
                        "_generated.",
                        "proto",
                        ".pb.",
                        ".grpc.",
                    ]
                ):
                    continue
                if any(
                    low_d.startswith(v) or f"/{v}" in low_d
                    for v in [
                        "vendor/",
                        "node_modules/",
                        "bower_components/",
                        ".venv/",
                        "venv/",
                        "env/",
                        "third-party/",
                        "third_party/",
                    ]
                ):
                    continue
                if ignore_migrations and any(
                    p in low_d
                    for p in ["migrations/", "/migrations/", "/migrate/", "db/migrate/"]
                ):
                    continue

                # Also skip generated / vendor / migration on origin_file
                low_o = origin_file.lower()
                if any(
                    p in low_o
                    for p in [
                        "generated",
                        ".gen.",
                        "_gen.",
                        "_generated.",
                        "proto",
                        ".pb.",
                        ".grpc.",
                    ]
                ):
                    continue
                if any(
                    low_o.startswith(v) or f"/{v}" in low_o
                    for v in [
                        "vendor/",
                        "node_modules/",
                        "bower_components/",
                        ".venv/",
                        "venv/",
                        "env/",
                        "third-party/",
                        "third_party/",
                    ]
                ):
                    continue

                weight = self.DISTANCE_WEIGHTS.get(distance, 0.4)

                for run_id in sorted(failed_run_ids, key=str):
                    # Find the test run object to get its created_at timestamp
                    run_obj = next(
                        (
                            r
                            for r in evidence_bundle.related_test_runs
                            if r.test_run_id == run_id
                        ),
                        None,
                    )
                    ev: Dict[str, Any] = {
                        "pr_id": pr_id,
                        "run_id": run_id,
                        "run_created_at": run_obj.created_at if run_obj else None,
                        "distance": distance,
                        "expansion_path": exp_path,
                        "origin_file": origin_file,
                        "weight": weight,
                        "rollback": pr_has_rollback,
                        "incident": pr_has_incident,
                        "churn": pr_churn.get(origin_file, 0),
                        "evidence_type": "DEPENDENCY_EXPANSION",
                    }
                    neighborhood_evidence[(origin_file, downstream_file)].append(ev)

        # -----------------------------------------------------------------
        # 6. Filter pairs below the minimum evidence threshold and persist
        # -----------------------------------------------------------------
        patterns_mined = 0
        skipped_below_threshold = 0

        for (source_file, downstream_file), evidence_items in sorted(
            neighborhood_evidence.items()
        ):
            # Deduplicate: one entry per (pr_id, run_id) to avoid double-counting
            seen_keys: Set[Tuple[uuid.UUID, uuid.UUID]] = set()
            deduped: List[Dict[str, Any]] = []
            for ev in evidence_items:
                key = (ev["pr_id"], ev["run_id"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    deduped.append(ev)

            evidence_count = len(deduped)
            distinct_prs = {ev["pr_id"] for ev in deduped}
            distinct_prs_count = len(distinct_prs)

            # Rule: minimum 3 evidence links + minimum 2 distinct PRs
            if evidence_count < self.MIN_EVIDENCE_LINKS:
                skipped_below_threshold += 1
                continue
            if distinct_prs_count < self.MIN_DISTINCT_PRS:
                skipped_below_threshold += 1
                continue

            normalized_pattern_key = (
                f"DEPENDENCY_PROXIMITY:{source_file}->{downstream_file}"
            )

            # Honour manual invalidation overrides
            if normalized_pattern_key in invalidated_keys:
                continue

            # -----------------------------------------------------------------
            # Scoring
            # -----------------------------------------------------------------
            # Primary weight: highest proximity weight in the evidence set
            primary_weight = max(ev["weight"] for ev in deduped)

            # 1. Frequency score
            freq_score = min(evidence_count / 10.0, 1.0) * 100.0

            # 2. Density score
            effective_total = max(evidence_bundle.total_runs_in_window, 20)
            density_score = (evidence_count / effective_total) * 100.0

            # 3. Recency score
            timestamps = [
                ev["run_created_at"]
                for ev in deduped
                if ev.get("run_created_at")
            ]
            last_seen = max(timestamps) if timestamps else datetime.utcnow()
            days_since = max(
                (evidence_bundle.evidence_window_end - last_seen).days, 0
            )
            recency_score = math.exp(-days_since / 14.0) * 100.0

            # 4. Churn score (aggregate churn for the source file)
            total_churn = sum(ev["churn"] for ev in deduped)
            churn_score = (
                min(math.log(1.0 + total_churn) / math.log(1.0 + 1000.0), 1.0)
                * 100.0
            )

            # 5. Rollback score
            rollback_count = sum(1 for ev in deduped if ev["rollback"])
            rollback_score = min(rollback_count / 3.0, 1.0) * 100.0

            # 6. Incident score
            incident_count = sum(1 for ev in deduped if ev["incident"])
            incident_score = min(incident_count / 3.0, 1.0) * 100.0

            # 7. Dependency proximity penalty — closer hops score higher
            #    already captured by primary_weight; apply it last
            base_score = (
                0.20 * freq_score
                + 0.05 * density_score
                + 0.20 * recency_score
                + 0.15 * churn_score
                + 0.20 * rollback_score
                + 0.20 * incident_score
            )
            weighted_score = round(base_score * primary_weight, 2)

            # Risk level
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

            # Human-readable explanation (Rule 4 template)
            representative = deduped[0]
            explanation = (
                f"Changes in {source_file} repeatedly expanded into "
                f"{downstream_file} before failed executions "
                f"({evidence_count} times across {distinct_prs_count} pull requests "
                f"in the last {evidence_bundle.history_window_days} days)."
            )

            # -----------------------------------------------------------------
            # Overwrite protection
            # -----------------------------------------------------------------
            existing = (
                self.db.query(FragilityPattern)
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
                    self.db.delete(existing)
                    self.db.commit()
                else:
                    continue

            # -----------------------------------------------------------------
            # Deterministic evidence IDs (UUID v5)
            # -----------------------------------------------------------------
            sorted_deduped = sorted(
                deduped,
                key=lambda x: (
                    x.get("run_created_at") or datetime.min,
                    str(x.get("run_id") or ""),
                    str(x.get("pr_id") or ""),
                ),
            )

            evidence_ids: List[str] = []
            for ev in sorted_deduped:
                namespace_payload = (
                    f"{normalized_pattern_key}|DEPENDENCY_EXPANSION|"
                    f"{ev['run_id']}|{ev['pr_id']}|"
                    f"{self.NORMALIZATION_RULES_VERSION}|{self.SCORING_VERSION}|"
                    f"{evidence_bundle.evidence_window_start.isoformat()}->"
                    f"{evidence_bundle.evidence_window_end.isoformat()}"
                )
                det_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, namespace_payload))
                evidence_ids.append(det_uuid)

            # -----------------------------------------------------------------
            # Replayable snapshot
            # -----------------------------------------------------------------
            linked_prs = sorted({str(ev["pr_id"]) for ev in sorted_deduped})
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
                "primary_weight": primary_weight,
            }

            replayable_snapshot = {
                "evidence_ids": sorted(evidence_ids),
                "evidence_counts": {"DEPENDENCY_EXPANSION": evidence_count},
                "source_entity_references": [source_file, downstream_file],
                "evidence_bundle_hash": bundle_hash,
                "linked_prs": linked_prs,
                "linked_runs": linked_runs,
                "linked_incidents": [],
                "summary_statistics": summary_stats,
                "evidence_window_start": evidence_bundle.evidence_window_start.isoformat(),
                "evidence_window_end": evidence_bundle.evidence_window_end.isoformat(),
            }

            score_components = {
                "frequency": freq_score,
                "density": density_score,
                "recency": recency_score,
                "churn": churn_score,
                "rollback": rollback_score,
                "incident": incident_score,
                "proximity_weight": primary_weight,
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

            # Context
            context = {
                "source_file": source_file,
                "downstream_file": downstream_file,
                "primary_weight": primary_weight,
                "expansion_path_sample": representative["expansion_path"],
                "expansion_distance_sample": representative["distance"],
            }

            # -----------------------------------------------------------------
            # Persist pattern
            # -----------------------------------------------------------------
            source_basename = source_file.split("/")[-1].split(".")[0]
            downstream_basename = downstream_file.split("/")[-1].split(".")[0]

            pattern = FragilityPattern(
                id=uuid.uuid4(),
                repository_id=repository_id,
                pattern_type="DEPENDENCY_PROXIMITY",
                normalized_pattern_key=normalized_pattern_key,
                title=f"Dependency Proximity: {source_basename} → {downstream_basename}",
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
            self.db.add(pattern)
            self.db.flush()

            # Persist evidence links
            for idx, ev in enumerate(sorted_deduped):
                link_summary = (
                    f"Changes in '{ev['origin_file']}' expanded via dependency path "
                    f"'{ev['expansion_path']}' (distance: {ev['distance']}) "
                    f"into '{downstream_file}' before a failed run. "
                    f"Rollback: {ev['rollback']}. Incident: {ev['incident']}."
                )
                link = FragilityEvidenceLink(
                    id=uuid.UUID(evidence_ids[idx]),
                    fragility_pattern_id=pattern.id,
                    evidence_type="DEPENDENCY_EXPANSION",
                    source_test_run_id=ev["run_id"],
                    source_recommendation_run_id=None,
                    source_pull_request_id=ev["pr_id"],
                    evidence_summary=link_summary,
                )
                self.db.add(link)

            patterns_mined += 1

        self.db.commit()

        logger.info(
            "DependencyProximityFragilityEngine finished: %d patterns mined, "
            "%d pairs skipped (below threshold).",
            patterns_mined,
            skipped_below_threshold,
        )

        return {
            "patterns_mined": patterns_mined,
            "diagnostics": {
                "skipped_below_threshold": skipped_below_threshold,
            },
        }

    # ------------------------------------------------------------------
    # Lifecycle: stale decay (mirrors other engines)
    # ------------------------------------------------------------------

    def apply_stale_decay(
        self, repository_id: uuid.UUID, now: Optional[datetime] = None
    ) -> int:
        """
        Applies a cautious stale decay of 10 % every 30 days to active
        DEPENDENCY_PROXIMITY patterns:
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
                FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY",
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
