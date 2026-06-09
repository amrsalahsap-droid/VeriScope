import uuid
import math
import hashlib
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink
from app.schemas.failure_evidence import FailureEvidenceBundle

logger = logging.getLogger(__name__)

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: RepositoryCalibrationProfile
# ====================================================================
# Future calibration profiles should support repository-specific calibrations:
# - CI noisiness: Down-weight patterns if CI is highly flakey or noisy.
# - Deployment cadence: Adjust stale time limits for fast continuous deployment vs slow release cycles.
# - Flake rates: Dynamically filter out test failures that have high flaky probability.
# - Incident tolerance: Adjust critical threshold boundaries for highly sensitive repos.
# - Repo volatility: Compensate for high-volatility files in active refactoring branches.
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: Evidence-Source Weighting
# ====================================================================
# Future engines should assign customizable, non-linear weights to different 
# evidence source classifications:
# - INCIDENT (Weight: 1.0 / Highest priority)
# - ROLLBACK (Weight: 0.8)
# - TEST_FAILURE (Weight: 0.5)
# - FLAKY_FAILURE (Weight: 0.1 / Low priority/noise filtered)
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================

class FileFailureFrequencyEngine:
    MIN_FAILURE_OCCURRENCES = 3
    MIN_DISTINCT_RUNS = 2
    GENERATION_VERSION = "v1.2.0"
    SCORING_VERSION = "weighted.v2"
    
    # Actuarial Lifecycles (Relaxed to avoid organizational amnesia)
    STALE_AFTER_DAYS = 90
    INVALIDATE_AFTER_DAYS = 180

    def __init__(self, db: Session):
        self.db = db

    def detect_file_failure_patterns(
        self,
        repository_id: uuid.UUID,
        evidence_bundle: FailureEvidenceBundle,
        ignore_migrations: bool = True
    ) -> Dict[str, Any]:
        """
        Scans failure evidence and compiles deterministic, evidence-backed file failure frequency patterns.
        Enforces defensive overwrite protections, progressive incident weights, and logarithmic churn normalization.
        """
        logger.info(f"FileFailureFrequencyEngine starting detection for repository {repository_id}...")

        # Initialize skipped diagnostics trackers
        generated_ignored_count = 0
        vendor_ignored_count = 0
        migration_ignored_count = 0

        # Fetch preserved invalidated keys to avoid duplicate insertions/overwrites
        invalidated_keys = {
            p.normalized_pattern_key for p in self.db.query(FragilityPattern.normalized_pattern_key).filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.pattern_type == "FILE_FAILURE_FREQUENCY",
                FragilityPattern.status == "INVALIDATED"
            ).all()
        }

        # Group changed files by file_path
        files_map: Dict[str, List[Any]] = {}
        for cf in evidence_bundle.related_changed_files:
            files_map.setdefault(cf.file_path, []).append(cf)

        patterns_created = 0

        # Process each file path deterministically
        for file_path in sorted(files_map.keys()):
            low_path = file_path.lower()

            # 1. Generated check
            if any(p in low_path for p in ["generated", ".gen.", "_gen.", "_generated.", "proto", ".pb.", ".grpc."]):
                generated_ignored_count += 1
                continue

            # 2. Vendor check
            if any(low_path.startswith(v) or f"/{v}" in low_path for v in ["vendor/", "node_modules/", "bower_components/", ".venv/", "venv/", "env/", "third-party/", "third_party/"]):
                vendor_ignored_count += 1
                continue

            # 3. Migrations check
            if ignore_migrations and any(p in low_path for p in ["migrations/", "/migrations/", "/migrate/", "db/migrate/"]):
                migration_ignored_count += 1
                continue

            file_changed_records = files_map[file_path]
            pr_ids = {cf.pull_request_id for cf in file_changed_records}

            # Map occurrences
            evidence_items = []
            
            # Failed runs
            seen_run_ids = set()
            for run in evidence_bundle.related_test_runs:
                if run.pull_request_id in pr_ids and run.status == "failed":
                    if run.test_run_id not in seen_run_ids:
                        seen_run_ids.add(run.test_run_id)
                        # Find matching failed test result (if available)
                        res_id = next((r.test_result_id for r in evidence_bundle.failed_test_results if r.test_run_id == run.test_run_id), None)
                        evidence_items.append({
                            "evidence_type": "TEST_FAILURE",
                            "source_test_run_id": run.test_run_id,
                            "source_test_result_id": res_id,
                            "source_pull_request_id": run.pull_request_id,
                            "created_at": run.created_at,
                            "evidence_summary": f"File '{file_path}' modified in failed test run.",
                            "run_id": run.test_run_id
                        })

            # Rollbacks
            seen_rollback_run_ids = set()
            for out in evidence_bundle.linked_incidents:
                if out.rollback_occurred:
                    rec = next((r for r in evidence_bundle.linked_recommendations if r.recommendation_run_id == out.recommendation_run_id), None)
                    if rec and rec.pull_request_id in pr_ids:
                        if rec.recommendation_run_id not in seen_rollback_run_ids:
                            seen_rollback_run_ids.add(rec.recommendation_run_id)
                            evidence_items.append({
                                "evidence_type": "ROLLBACK",
                                "source_recommendation_run_id": rec.recommendation_run_id,
                                "source_pull_request_id": rec.pull_request_id,
                                "created_at": out.created_at or rec.created_at,
                                "evidence_summary": f"File '{file_path}' modified in rollback-linked recommendation.",
                                "run_id": rec.recommendation_run_id
                            })

            # Incidents
            seen_incident_run_ids = set()
            for out in evidence_bundle.linked_incidents:
                if out.escaped_defect:
                    rec = next((r for r in evidence_bundle.linked_recommendations if r.recommendation_run_id == out.recommendation_run_id), None)
                    if rec and rec.pull_request_id in pr_ids:
                        if rec.recommendation_run_id not in seen_incident_run_ids:
                            seen_incident_run_ids.add(rec.recommendation_run_id)
                            evidence_items.append({
                                "evidence_type": "INCIDENT",
                                "source_recommendation_run_id": rec.recommendation_run_id,
                                "source_pull_request_id": rec.pull_request_id,
                                "created_at": out.created_at or rec.created_at,
                                "evidence_summary": f"File '{file_path}' modified in incident-linked recommendation.",
                                "run_id": rec.recommendation_run_id
                            })

            # Threshold check
            evidence_count = len(evidence_items)
            distinct_runs = {e["run_id"] for e in evidence_items}
            distinct_runs_count = len(distinct_runs)

            if evidence_count < self.MIN_FAILURE_OCCURRENCES or distinct_runs_count < self.MIN_DISTINCT_RUNS:
                continue

            normalized_pattern_key = f"FILE_FAILURE_FREQUENCY:{file_path}"

            # Preserve manual invalidation overrides
            if normalized_pattern_key in invalidated_keys:
                continue

            # Distinct PR count
            distinct_prs_count = len({e["source_pull_request_id"] for e in evidence_items if e.get("source_pull_request_id")})

            # Metrics
            failed_runs_count = len([e for e in evidence_items if e["evidence_type"] == "TEST_FAILURE"])
            rollback_recs_count = len([e for e in evidence_items if e["evidence_type"] == "ROLLBACK"])
            incident_runs_count = len([e for e in evidence_items if e["evidence_type"] == "INCIDENT"])

            # 1. Failure Frequency Score
            freq_score = min(failed_runs_count / 10.0, 1.0) * 100.0

            # 2. Failure Density Score (Floor to avoid catastrophic tiny-repo inflation)
            effective_total_runs = max(evidence_bundle.total_runs_in_window, 20)
            failure_density = failed_runs_count / effective_total_runs
            density_score = failure_density * 100.0

            # 3. Recency Weight
            timestamps = [e["created_at"] for e in evidence_items if e.get("created_at")]
            last_seen = max(timestamps) if timestamps else datetime.utcnow()
            days_since = (evidence_bundle.evidence_window_end - last_seen).days
            days_since = max(days_since, 0)
            recency_score = math.exp(-days_since / 14.0) * 100.0

            # 4. Logarithmic Churn Score (Cap giant PR poisoning)
            churn_sum = sum(cf.additions + cf.deletions for cf in file_changed_records)
            normalized_churn = math.log(1.0 + churn_sum)
            churn_score = min(normalized_churn / math.log(1.0 + 1000.0), 1.0) * 100.0

            # 5. Progressive Rollback Score
            rollback_score = min(rollback_recs_count / 3.0, 1.0) * 100.0

            # 6. Progressive Incident Score
            incident_score = min(incident_runs_count / 3.0, 1.0) * 100.0

            # Weighted Formula
            weighted_score = (
                0.20 * freq_score +
                0.05 * density_score +
                0.20 * recency_score +
                0.15 * churn_score +
                0.20 * rollback_score +
                0.20 * incident_score
            )
            weighted_score = round(weighted_score, 2)

            # Risk Classification
            if weighted_score >= 80.0:
                risk_level = "CRITICAL"
            elif weighted_score >= 50.0:
                risk_level = "HIGH"
            elif weighted_score >= 30.0:
                risk_level = "MODERATE"
            else:
                risk_level = "LOW"

            # Confidence Level
            if evidence_count >= 5 and distinct_prs_count >= 3 and days_since < 30:
                confidence_level = "HIGH"
            elif evidence_count >= 3 and distinct_prs_count >= 2 and days_since < 90:
                confidence_level = "MODERATE"
            else:
                confidence_level = "LOW"

            # Strict Active voice explanation
            explanation = f"Changes involving {file_path} preceded {failed_runs_count} failed runs and {rollback_recs_count} rollback-linked recommendations during the last {evidence_bundle.history_window_days} days."

            # Replay Overwrite Protections
            existing = self.db.query(FragilityPattern).filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.normalized_pattern_key == normalized_pattern_key
            ).first()

            if existing:
                # If existing is active or stale, evaluate overwrite conditions
                existing_window_end_str = existing.replayable_evidence_snapshot.get("evidence_window_end")
                is_newer_window = True
                if existing_window_end_str:
                    try:
                        existing_window_end = datetime.fromisoformat(existing_window_end_str)
                        is_newer_window = evidence_bundle.evidence_window_end > existing_window_end
                    except Exception:
                        pass

                is_stronger_evidence = evidence_count > existing.evidence_count
                is_newer_version = self.SCORING_VERSION != existing.scoring_formula_version

                # Overwrite only if window is newer, evidence is stronger, or scoring version is different
                if is_newer_window or is_stronger_evidence or is_newer_version:
                    self.db.delete(existing)
                    self.db.commit()
                else:
                    # Keep existing as is
                    continue

            # Deterministically sort evidence items first
            sorted_evidence_items = sorted(
                evidence_items,
                key=lambda x: (
                    x.get("created_at") or datetime.min,
                    str(x.get("source_test_run_id") or ""),
                    str(x.get("source_recommendation_run_id") or "")
                )
            )

            # Generate fully deterministic evidence IDs using UUID v5 to prevent replay drift
            evidence_ids = []
            for ev in sorted_evidence_items:
                unique_name = f"{normalized_pattern_key}|{ev['evidence_type']}|{ev.get('run_id')}|{ev.get('source_pull_request_id')}"
                det_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_name))
                evidence_ids.append(det_uuid)

            evidence_counts = {}
            for e in sorted_evidence_items:
                evidence_counts[e["evidence_type"]] = evidence_counts.get(e["evidence_type"], 0) + 1

            linked_prs = sorted(list({str(e["source_pull_request_id"]) for e in sorted_evidence_items if e.get("source_pull_request_id")}))
            linked_runs = sorted(list({str(e["source_test_run_id"]) for e in sorted_evidence_items if e.get("source_test_run_id")}))
            linked_incidents = sorted(list({str(e["source_incident_id"]) for e in sorted_evidence_items if e.get("source_incident_id")}))

            summary_stats = {
                "total_evidence": evidence_count,
                "distinct_prs_count": distinct_prs_count,
                "days_since_last_seen": days_since,
                "failed_runs_count": failed_runs_count,
                "rollback_recs_count": rollback_recs_count,
                "incident_runs_count": incident_runs_count
            }

            # Stable Evidence Hash
            evidence_bundle_payload = f"key:{normalized_pattern_key}|prs:{linked_prs}|runs:{linked_runs}|incidents:{linked_incidents}"
            bundle_hash = hashlib.sha256(evidence_bundle_payload.encode("utf-8")).hexdigest()

            replayable_snapshot = {
                "evidence_ids": sorted(evidence_ids),
                "evidence_counts": evidence_counts,
                "source_entity_references": [file_path],
                "evidence_bundle_hash": bundle_hash,
                "linked_prs": linked_prs,
                "linked_runs": linked_runs,
                "linked_incidents": linked_incidents,
                "summary_statistics": summary_stats,
                "evidence_window_start": evidence_bundle.evidence_window_start.isoformat(),
                "evidence_window_end": evidence_bundle.evidence_window_end.isoformat()
            }

            score_components = {
                "frequency": freq_score,
                "density": density_score,
                "recency": recency_score,
                "churn": churn_score,
                "rollback": rollback_score,
                "incident": incident_score
            }

            # Deterministic payload hashing with sorted keys
            hash_payload = {
                "normalized_pattern_key": normalized_pattern_key,
                "evidence_ids": sorted(evidence_ids),
                "score_components": score_components,
                "evidence_window_start": evidence_bundle.evidence_window_start.isoformat(),
                "evidence_window_end": evidence_bundle.evidence_window_end.isoformat(),
                "scoring_formula_version": self.SCORING_VERSION
            }
            serialized_payload = json.dumps(hash_payload, sort_keys=True, separators=(",", ":"))
            pattern_hash_val = hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()

            # Persist pattern
            pattern = FragilityPattern(
                id=uuid.uuid4(),
                repository_id=repository_id,
                pattern_type="FILE_FAILURE_FREQUENCY",
                normalized_pattern_key=normalized_pattern_key,
                title=f"File Failure Frequency: {file_path}",
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
                incident_count=incident_runs_count,
                related_failure_count=failed_runs_count,
                status="ACTIVE",
                first_seen_at=min(timestamps) if timestamps else datetime.utcnow(),
                last_seen_at=last_seen
            )
            self.db.add(pattern)
            self.db.flush()

            for idx, ev in enumerate(sorted_evidence_items):
                link = FragilityEvidenceLink(
                    id=uuid.UUID(evidence_ids[idx]),
                    fragility_pattern_id=pattern.id,
                    evidence_type=ev["evidence_type"],
                    source_test_run_id=ev.get("source_test_run_id"),
                    source_test_result_id=ev.get("source_test_result_id"),
                    source_incident_id=ev.get("source_incident_id"),
                    source_recommendation_run_id=ev.get("source_recommendation_run_id"),
                    source_pull_request_id=ev.get("source_pull_request_id"),
                    evidence_summary=ev["evidence_summary"]
                )
                self.db.add(link)


            patterns_created += 1

        self.db.commit()

        return {
            "patterns_mined": patterns_created,
            "diagnostics": {
                "generated_ignored_count": generated_ignored_count,
                "vendor_ignored_count": vendor_ignored_count,
                "migration_ignored_count": migration_ignored_count
            }
        }

    def apply_stale_decay(self, repository_id: uuid.UUID, now: Optional[datetime] = None) -> int:
        """
        Applies a cautious stale decay of 10% every 30 days to active FILE_FAILURE_FREQUENCY patterns:
        - score_new = score_orig * 0.9^(days/30)
        - Transition to STALE after 90 days of inactivity
        - Transitions to INVALIDATED with code STALE_NO_RECENT_EVIDENCE after 180 days
        """
        now_time = now or datetime.utcnow()
        active_patterns = self.db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repository_id,
            FragilityPattern.pattern_type == "FILE_FAILURE_FREQUENCY",
            FragilityPattern.status == "ACTIVE"
        ).all()

        decayed_count = 0
        for p in active_patterns:
            days_since = (now_time - p.last_seen_at).days
            days_since = max(days_since, 0)

            if days_since >= self.STALE_AFTER_DAYS:
                # 10% decay every 30 days continuous decay
                decay_ratio = 0.9 ** (days_since / 30.0)
                p.fragility_score = round(p.fragility_score * decay_ratio, 2)

                new_components = dict(p.score_components)
                new_components["decayed"] = True
                new_components["decay_days"] = days_since
                p.score_components = new_components
                p.updated_at = now_time
                decayed_count += 1

                # Lifecycle Transitions
                if days_since >= self.INVALIDATE_AFTER_DAYS:
                    p.status = "INVALIDATED"
                    p.invalidated_reason = "STALE_NO_RECENT_EVIDENCE"
                    p.invalidated_at = now_time
                    p.invalidated_by = "SYSTEM_DECAY"
                    logger.info(f"Pattern {p.normalized_pattern_key} transitioned to 'INVALIDATED' due to stale age > {self.INVALIDATE_AFTER_DAYS} days.")
                else:
                    p.status = "STALE"
                    logger.info(f"Pattern {p.normalized_pattern_key} transitioned to 'STALE' due to decay age > {self.STALE_AFTER_DAYS} days.")

        self.db.commit()
        return decayed_count
