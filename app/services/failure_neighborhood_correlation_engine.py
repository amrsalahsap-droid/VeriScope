import uuid
import math
import hashlib
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional, Set
from sqlalchemy.orm import Session

from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink
from app.models.test_result import TestCase, TestRun
from app.models.dependency import FileDependency
from app.models.flaky_test import FlakyTestProfile
from app.schemas.failure_evidence import FailureEvidenceBundle

logger = logging.getLogger(__name__)

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: RepositoryCalibrationProfile
# ====================================================================
# Future calibration profiles should support repository-specific calibrations:
# - CI noisiness: Adjust thresholds based on how noisy or clean the test executions are.
# - Integration density: Account for how highly interconnected different modules are.
# - Deployment cadence: Fine-tune decay rates based on slow vs fast development cycles.
# - Repo complexity: Down-weight massive directory neighborhoods.
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================

# ====================================================================
# FUTURE ARCHITECTURAL DESIGN NOTE: Evidence-Source Weighting
# ====================================================================
# Future engines should assign customizable, non-linear weights to different 
# evidence source classifications:
# - INCIDENT (Weight: 1.0)
# - ROLLBACK (Weight: 0.8)
# - TEST_FAILURE (Weight: 0.5)
# - QUARANTINED_FAILURE (Weight: 0.1)
#
# No implementation yet. Architectural acknowledgement only.
# ====================================================================

class TestAreaResolver:
    def __init__(self, db: Session, repository_id: uuid.UUID):
        self.db = db
        self.repository_id = repository_id
        # Explicit mappings dictionary for core domains
        self.explicit_mappings = {
            "auth": "auth",
            "session": "auth",
            "billing": "billing",
            "payment": "billing",
            "checkout": "billing",
            "core": "core",
            "utils": "utils"
        }

    def resolve_test_area(self, tc: TestCase) -> Tuple[str, str, float]:
        """
        Resolves affected_area using hierarchy:
        1. Explicit module mapping
        2. Suite metadata
        3. Path inference
        4. Naming cleanup fallback
        Returns: (affected_area, resolution_source, resolution_confidence)
        """
        # 1. Explicit module mapping
        stable_id_low = tc.stable_identity.lower()
        for key, area in self.explicit_mappings.items():
            if key in stable_id_low:
                return area, "EXPLICIT_MAPPING", 1.0

        # 2. Suite metadata
        suite_name = tc.suite_name.lower()
        if suite_name:
            clean_suite = suite_name.replace("_suite", "").replace("_tests", "").replace("test_", "").replace("_test", "")
            if clean_suite:
                return clean_suite, "SUITE_METADATA", 0.9

        # 3. Path inference
        if "::" in tc.stable_identity:
            parts = tc.stable_identity.split("::")
            clean_part = parts[0].replace("_suite", "").replace("_tests", "").replace("test_", "").replace("_test", "")
            if clean_part:
                return clean_part.lower(), "PATH_INFERENCE", 0.8

        # 4. Fallback cleanup
        fallback_area = tc.suite_name.lower()
        fallback_area = fallback_area.replace("test_", "").replace("_test", "")
        if not fallback_area:
            fallback_area = "general"
        return fallback_area, "NAMING_CLEANUP_FALLBACK", 0.6


class FailureNeighborhoodCorrelationEngine:
    MIN_COOCCURRENCE_COUNT = 3
    MIN_DISTINCT_PRS = 2
    GENERATION_VERSION = "v1.2.0"
    SCORING_VERSION = "weighted.v2"
    NORMALIZATION_RULES_VERSION = "rules.v1"
    
    # Storm Suppression
    MAX_FAILURES_PER_RUN_FOR_COFLOW_ANALYSIS = 25
    
    # Actuarial Lifecycles
    STALE_AFTER_DAYS = 90
    INVALIDATE_AFTER_DAYS = 180

    def __init__(self, db: Session):
        self.db = db

    def detect_cofailure_patterns(
        self,
        repository_id: uuid.UUID,
        evidence_bundle: FailureEvidenceBundle,
        ignore_migrations: bool = True
    ) -> Dict[str, Any]:
        """
        Detects repeated co-failure patterns with contextual trigger file evidence,
        preventing storm/flaky test poisoning and applying progressive expansions.
        """
        logger.info(f"FailureNeighborhoodCorrelationEngine starting co-failure analysis for repository {repository_id}...")

        # Skip diagnostic stats
        suppressed_storm_runs = 0

        # Visited invalidated keys preservation
        invalidated_keys = {
            p.normalized_pattern_key for p in self.db.query(FragilityPattern.normalized_pattern_key).filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.pattern_type == "CO_FAILURE_PATTERN",
                FragilityPattern.status == "INVALIDATED"
            ).all()
        }

        # 1. Fetch Flaky/Quarantined Test Cases for suppression
        flaky_profiles = self.db.query(FlakyTestProfile).filter(
            FlakyTestProfile.repository_id == repository_id
        ).all()
        
        excluded_test_cases = set()
        for fp in flaky_profiles:
            if fp.status in ("quarantined", "unstable") or fp.failure_rate > 0.2 or fp.instability_score > 0.2:
                excluded_test_cases.add(fp.test_case_id)

        # 2. Build local dependency graph for trigger expansion BFS
        all_deps = self.db.query(FileDependency).filter(FileDependency.repository_id == repository_id).all()
        adj: Dict[str, Set[str]] = {}
        for d in all_deps:
            adj.setdefault(d.file_path, set()).add(d.depends_on_file_path)
            adj.setdefault(d.depends_on_file_path, set()).add(d.file_path)

        # Initialize TestAreaResolver
        resolver = TestAreaResolver(self.db, repository_id)

        # 3. Resolve trigger candidates per PR in the bundle using BFS up to depth 2
        # pull_request_id -> list of trigger dict: {file_path, weight, expansion_source, expansion_distance, expansion_path}
        pr_triggers: Dict[uuid.UUID, List[Dict[str, Any]]] = {}
        
        # Group changed files by PR
        pr_changed_files: Dict[uuid.UUID, List[str]] = {}
        for cf in evidence_bundle.related_changed_files:
            pr_changed_files.setdefault(cf.pull_request_id, []).append(cf.file_path)

        for pr_id, files in pr_changed_files.items():
            visited: Dict[str, Tuple[int, str]] = {}
            
            # Seed BFS queue: (file_path, distance, path_string)
            queue = []
            for f in files:
                visited[f] = (0, f)
                queue.append((f, 0, f))

            while queue:
                curr, dist, path = queue.pop(0)
                if dist >= 2:
                    continue
                for neighbor in adj.get(curr, []):
                    if neighbor not in visited or dist + 1 < visited[neighbor][0]:
                        visited[neighbor] = (dist + 1, f"{path} -> {neighbor}")
                        queue.append((neighbor, dist + 1, f"{path} -> {neighbor}"))

            # Save trigger list
            trigger_list = []
            for f_path, (distance, exp_path) in visited.items():
                low_f = f_path.lower()
                
                # Exclude generated/vendor/migrations files from triggers
                if any(p in low_f for p in ["generated", ".gen.", "_gen.", "_generated.", "proto", ".pb.", ".grpc."]):
                    continue
                if any(low_f.startswith(v) or f"/{v}" in low_f for v in ["vendor/", "node_modules/", "bower_components/", ".venv/", "venv/", "env/", "third-party/", "third_party/"]):
                    continue
                if ignore_migrations and any(p in low_f for p in ["migrations/", "/migrations/", "/migrate/", "db/migrate/"]):
                    continue

                # Weight assignments
                if distance == 0:
                    weight = 1.0
                elif distance == 1:
                    weight = 0.7
                else:
                    weight = 0.4

                # Find which direct changed file triggered this expansion
                orig_trigger = exp_path.split(" -> ")[0]

                trigger_list.append({
                    "file_path": f_path,
                    "weight": weight,
                    "expansion_source": orig_trigger,
                    "expansion_distance": distance,
                    "expansion_path": exp_path
                })
            
            pr_triggers[pr_id] = trigger_list

        # Map co-occurrence failures
        # (trigger_file, affected_area) -> list of co-occurrence occurrences
        cooccurrences_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

        # Query all TestCases in the failed results to map their models
        test_case_ids = {r.test_case_id for r in evidence_bundle.failed_test_results}
        test_cases_map: Dict[uuid.UUID, TestCase] = {}
        if test_case_ids:
            test_cases = self.db.query(TestCase).filter(TestCase.id.in_(test_case_ids)).all()
            test_cases_map = {tc.id: tc for tc in test_cases}

        print(f"DEBUG: pr_triggers keys: {list(pr_triggers.keys())}")
        for k, v in pr_triggers.items():
            print(f"DEBUG: pr_triggers[{k}] = {v}")

        for run in evidence_bundle.related_test_runs:
            if run.status != "failed" or not run.pull_request_id:
                continue

            # Co-Failure Storm Suppression
            if run.failed_tests > self.MAX_FAILURES_PER_RUN_FOR_COFLOW_ANALYSIS:
                suppressed_storm_runs += 1
                continue

            pr_id = run.pull_request_id
            triggers = pr_triggers.get(pr_id, [])
            if not triggers:
                continue

            # Failing results in this run
            run_results = [r for r in evidence_bundle.failed_test_results if r.test_run_id == run.test_run_id]
            print(f"DEBUG: Run {run.test_run_id} (PR {run.pull_request_id}) has failing results: {[res.test_case_id for res in run_results]}")
            for res in run_results:
                tc = test_cases_map.get(res.test_case_id)
                if not tc:
                    continue

                # Exclude noisy/flaky test case
                if tc.id in excluded_test_cases:
                    print(f"DEBUG: Test case {tc.stable_identity} is excluded because it is flaky/quarantined.")
                    continue

                # Resolve test area using resolver hierarchy
                affected_area, res_source, res_confidence = resolver.resolve_test_area(tc)
                print(f"DEBUG: Resolved test case {tc.stable_identity} as {affected_area} via {res_source} (confidence: {res_confidence})")

                # Correlate with each trigger file candidate
                for t in triggers:
                    key = (t["file_path"], affected_area)
                    cooccurrences_map.setdefault(key, []).append({
                        "run": run,
                        "test_result_id": res.test_result_id,
                        "test_case_id": tc.id,
                        "trigger": t,
                        "resolution": {
                            "affected_area": affected_area,
                            "resolution_source": res_source,
                            "resolution_confidence": res_confidence
                        }
                    })

        print(f"DEBUG: cooccurrences_map keys: {list(cooccurrences_map.keys())}")
        for k, v in cooccurrences_map.items():
            print(f"DEBUG: cooccurrences_map[{k}] length = {len(v)}")

        patterns_created = 0

        # 5. Threshold checks & Persistence
        for (trigger_file, affected_area), occurrences in sorted(cooccurrences_map.items()):
            cooccurrence_count = len(occurrences)
            
            # Distinct PR count
            distinct_prs = {o["run"].pull_request_id for o in occurrences if o["run"].pull_request_id}
            distinct_prs_count = len(distinct_prs)

            if cooccurrence_count < self.MIN_COOCCURRENCE_COUNT or distinct_prs_count < self.MIN_DISTINCT_PRS:
                continue
            parts = trigger_file.split("/")
            trigger_file_basename = parts[-1].split(".")[0]
            trigger_area = "/".join(parts[:-1])
            normalized_pattern_key = f"CO_FAILURE_PATTERN:{trigger_area}->{affected_area}:{trigger_file_basename}"

            if normalized_pattern_key in invalidated_keys:
                continue

            # Determine the primary driver (highest path weight)
            primary_occurrence = max(occurrences, key=lambda x: x["trigger"]["weight"])
            trigger_file_weight = primary_occurrence["trigger"]["weight"]

            # Diagnostics & resolution metadata
            res_meta = primary_occurrence["resolution"]

            # Actuarial Scoring Components
            failed_runs_count = len(occurrences)
            
            # 1. Failure Frequency Score
            freq_score = min(failed_runs_count / 10.0, 1.0) * 100.0

            # 2. Density Score (Floor 20)
            effective_total_runs = max(evidence_bundle.total_runs_in_window, 20)
            density_score = (failed_runs_count / effective_total_runs) * 100.0

            # 3. Recency Weight
            timestamps = [o["run"].created_at for o in occurrences if o["run"].created_at]
            last_seen = max(timestamps) if timestamps else datetime.utcnow()
            days_since = (evidence_bundle.evidence_window_end - last_seen).days
            days_since = max(days_since, 0)
            recency_score = math.exp(-days_since / 14.0) * 100.0

            # 4. Log Churn Score
            # Churn of the trigger file F
            file_changed_records = [cf for cf in evidence_bundle.related_changed_files if cf.file_path == trigger_file]
            churn_sum = sum(cf.additions + cf.deletions for cf in file_changed_records)
            normalized_churn = math.log(1.0 + churn_sum)
            churn_score = min(normalized_churn / math.log(1.0 + 1000.0), 1.0) * 100.0

            # 5. Progressive Rollback/Incident scaling
            # Rollbacks & incidents tied to the recommendation runs matching our co-occurrences
            rollback_recs_count = 0
            incident_runs_count = 0
            
            seen_rec_runs = set()
            for o in occurrences:
                run_pr_id = o["run"].pull_request_id
                # Find outcomes linked to this PR
                for out in evidence_bundle.linked_incidents:
                    rec = next((r for r in evidence_bundle.linked_recommendations if r.recommendation_run_id == out.recommendation_run_id), None)
                    if rec and rec.pull_request_id == run_pr_id:
                        if rec.recommendation_run_id not in seen_rec_runs:
                            seen_rec_runs.add(rec.recommendation_run_id)
                            if out.rollback_occurred:
                                rollback_recs_count += 1
                            if out.escaped_defect:
                                incident_runs_count += 1

            rollback_score = min(rollback_recs_count / 3.0, 1.0) * 100.0
            incident_score = min(incident_runs_count / 3.0, 1.0) * 100.0

            # Base Weighted Score
            base_weighted_score = (
                0.20 * freq_score +
                0.05 * density_score +
                0.20 * recency_score +
                0.15 * churn_score +
                0.20 * rollback_score +
                0.20 * incident_score
            )
            
            # Apply dependency-expansion confidence decay
            weighted_score = base_weighted_score * trigger_file_weight
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
            if failed_runs_count >= 5 and distinct_prs_count >= 3 and days_since < 30:
                confidence_level = "HIGH"
            elif failed_runs_count >= 3 and distinct_prs_count >= 2 and days_since < 90:
                confidence_level = "MODERATE"
            else:
                confidence_level = "LOW"

            # Strong Explanation template
            explanation = f"Changes touching {trigger_file} repeatedly preceded {affected_area}-related test failures in {failed_runs_count} regressions across {distinct_prs_count} pull requests during the last {evidence_bundle.history_window_days} days."

            # Overwrite checks
            existing = self.db.query(FragilityPattern).filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.normalized_pattern_key == normalized_pattern_key
            ).first()

            if existing:
                existing_window_end_str = existing.replayable_evidence_snapshot.get("evidence_window_end")
                is_newer_window = True
                if existing_window_end_str:
                    try:
                        existing_window_end = datetime.fromisoformat(existing_window_end_str)
                        is_newer_window = evidence_bundle.evidence_window_end > existing_window_end
                    except Exception:
                        pass

                is_stronger_evidence = failed_runs_count > existing.evidence_count
                is_newer_version = self.SCORING_VERSION != existing.scoring_formula_version

                if is_newer_window or is_stronger_evidence or is_newer_version:
                    self.db.delete(existing)
                    self.db.commit()
                else:
                    # Retain as is
                    continue

            # Deterministic evidence IDs
            # Sort occurrences deterministically
            sorted_occurrences = sorted(
                occurrences,
                key=lambda x: (
                    x["run"].created_at or datetime.min,
                    str(x["run"].test_run_id or ""),
                    str(x["test_result_id"] or "")
                )
            )

            # Generate fully deterministic UUID namespace
            evidence_ids = []
            for o in sorted_occurrences:
                # Include normalization rules version, scoring version, and evidence window for absolute replay consistency
                namespace_payload = (
                    f"{normalized_pattern_key}|TEST_FAILURE|{o['run'].test_run_id}|"
                    f"{o['run'].pull_request_id}|{self.NORMALIZATION_RULES_VERSION}|"
                    f"{self.SCORING_VERSION}|{evidence_bundle.evidence_window_start.isoformat()}->"
                    f"{evidence_bundle.evidence_window_end.isoformat()}"
                )
                det_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, namespace_payload))
                evidence_ids.append(det_uuid)

            evidence_counts = {"TEST_FAILURE": failed_runs_count}

            linked_prs = sorted(list({str(o["run"].pull_request_id) for o in sorted_occurrences if o["run"].pull_request_id}))
            linked_runs = sorted(list({str(o["run"].test_run_id) for o in sorted_occurrences if o["run"].test_run_id}))
            
            summary_stats = {
                "total_evidence": failed_runs_count,
                "distinct_prs_count": distinct_prs_count,
                "days_since_last_seen": days_since,
                "rollback_recs_count": rollback_recs_count,
                "incident_runs_count": incident_runs_count,
                "trigger_file_weight": trigger_file_weight
            }

            evidence_bundle_payload = f"key:{normalized_pattern_key}|prs:{linked_prs}|runs:{linked_runs}|incidents:[]"
            bundle_hash = hashlib.sha256(evidence_bundle_payload.encode("utf-8")).hexdigest()

            replayable_snapshot = {
                "evidence_ids": sorted(evidence_ids),
                "evidence_counts": evidence_counts,
                "source_entity_references": [trigger_file],
                "evidence_bundle_hash": bundle_hash,
                "linked_prs": linked_prs,
                "linked_runs": linked_runs,
                "linked_incidents": [],
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

            # Stable hash payload
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

            # Context contains mapping metadata for future auditing and explainability
            context = {
                "trigger_file": trigger_file,
                "affected_area": affected_area,
                "resolution_source": res_meta["resolution_source"],
                "resolution_confidence": res_meta["resolution_confidence"],
                "primary_trigger_weight": trigger_file_weight
            }

            # Persist pattern
            pattern = FragilityPattern(
                id=uuid.uuid4(),
                repository_id=repository_id,
                pattern_type="CO_FAILURE_PATTERN",
                normalized_pattern_key=normalized_pattern_key,
                title=f"Co Failure Pattern: {trigger_file_basename}",
                explanation=explanation,
                fragility_score=weighted_score,
                risk_level=risk_level,
                confidence_level=confidence_level,
                pattern_hash=pattern_hash_val,
                score_components=score_components,
                replayable_evidence_snapshot=replayable_snapshot,
                fragility_generation_version=self.GENERATION_VERSION,
                scoring_formula_version=self.SCORING_VERSION,
                evidence_count=failed_runs_count,
                incident_count=incident_runs_count,
                related_failure_count=failed_runs_count,
                status="ACTIVE",
                context=context,
                first_seen_at=min(timestamps) if timestamps else datetime.utcnow(),
                last_seen_at=last_seen
            )
            self.db.add(pattern)
            self.db.flush()

            # Persist links
            for idx, o in enumerate(sorted_occurrences):
                tr_trig = o["trigger"]
                
                # Diagnostic summary contains path details
                link_summary = (
                    f"Trigger changed file '{tr_trig['expansion_source']}' "
                    f"expanded via path '{tr_trig['expansion_path']}' "
                    f"(distance: {tr_trig['expansion_distance']}). Followed by {affected_area} failure."
                )

                link = FragilityEvidenceLink(
                    id=uuid.UUID(evidence_ids[idx]),
                    fragility_pattern_id=pattern.id,
                    evidence_type="TEST_FAILURE",
                    source_test_run_id=o["run"].test_run_id,
                    source_test_result_id=o["test_result_id"],
                    source_pull_request_id=o["run"].pull_request_id,
                    evidence_summary=link_summary
                )
                self.db.add(link)

            patterns_created += 1

        self.db.commit()

        return {
            "patterns_mined": patterns_created,
            "diagnostics": {
                "suppressed_storm_runs": suppressed_storm_runs
            }
        }

    def apply_stale_decay(self, repository_id: uuid.UUID, now: Optional[datetime] = None) -> int:
        """
        Applies a cautious stale decay of 10% every 30 days to active CO_FAILURE_PATTERN patterns:
        - score_new = score_orig * 0.9^(days/30)
        - Transition to STALE after 90 days of inactivity
        - Transitions to INVALIDATED with code STALE_NO_RECENT_EVIDENCE after 180 days
        """
        now_time = now or datetime.utcnow()
        active_patterns = self.db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repository_id,
            FragilityPattern.pattern_type == "CO_FAILURE_PATTERN",
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
