import uuid
import hashlib
import math
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Set
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.repository import Repository
from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink, FragilitySnapshot
from app.models.test_result import TestCase, TestRun, TestResult
from app.models.recommendation import RecommendationRun, RecommendationOutcome, RecommendationInputSnapshot
from app.models.dependency import FileDependency

logger = logging.getLogger(__name__)

class FragilityMemoryService:
    DEFAULT_MAX_DEPENDENCY_DEGREE = 50
    MAX_RISKY_COMBINATION_SIZE = 5
    MIN_FAILURE_OCCURRENCES = 3
    MIN_COOCCURRENCE_COUNT = 3
    MIN_DISTINCT_PRS = 2
    
    STALE_AFTER_DAYS = 14
    INVALIDATE_AFTER_DAYS = 30
    
    FRAGILITY_GENERATION_VERSION = "v1.2.0"
    SCORING_FORMULA_VERSION = "weighted.v2"

    def __init__(self, db: Session):
        self.db = db

    def mine_fragility_patterns(self, repository_id: uuid.UUID, history_window_days: int = 90) -> Dict[str, Any]:
        """
        Deterministically scans and mines the historical database records to compile
        organizational fragility patterns, enforcing elevated evidence thresholds,
        context-bound co-failures, dependency shields, and version control.
        """
        logger.info(f"Initiating fragility memory mining for repository {repository_id}...")
        
        # 1. Fetch the Repository to resolve configurable thresholds (future-proof overrides)
        repo_record = self.db.query(Repository).filter(Repository.id == repository_id).first()
        max_deg = getattr(repo_record, "max_dependency_degree", self.DEFAULT_MAX_DEPENDENCY_DEGREE)
        if max_deg is None:
            max_deg = self.DEFAULT_MAX_DEPENDENCY_DEGREE

        # 2. Preserve "INVALIDATED" status records and delete ACTIVE/STALE patterns to overwrite cleanly
        self.db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repository_id,
            FragilityPattern.status.in_(["ACTIVE", "STALE"])
        ).delete(synchronize_session=False)
        self.db.commit()

        # Fetch preserved invalidated patterns to avoid duplicate insertions
        invalidated_keys = {
            p.normalized_pattern_key for p in self.db.query(FragilityPattern.normalized_pattern_key).filter(
                FragilityPattern.repository_id == repository_id,
                FragilityPattern.status == "INVALIDATED"
            ).all()
        }

        # 3. Extract dependency edge degrees to shield utility hubs
        dep_degrees: Dict[str, int] = {}
        all_deps = self.db.query(FileDependency).filter(FileDependency.repository_id == repository_id).all()
        for d in all_deps:
            dep_degrees[d.file_path] = dep_degrees.get(d.file_path, 0) + 1
            dep_degrees[d.depends_on_file_path] = dep_degrees.get(d.depends_on_file_path, 0) + 1

        # 4. Gather historical failed TestRuns
        cutoff_date = datetime.utcnow() - timedelta(days=history_window_days)
        failed_runs = self.db.query(TestRun).filter(
            TestRun.repository_id == repository_id,
            TestRun.status == "failed",
            TestRun.created_at >= cutoff_date
        ).all()

        # Build commit/PR maps to snapshots
        snapshots = self.db.query(RecommendationInputSnapshot).all()
        commit_snapshot_map: Dict[str, RecommendationInputSnapshot] = {}
        pr_snapshot_map: Dict[uuid.UUID, RecommendationInputSnapshot] = {}
        for snap in snapshots:
            run = snap.recommendation_run
            if run:
                if run.pr_id:
                    commit_snapshot_map[run.pr_id] = snap
                if run.pull_request_id:
                    pr_snapshot_map[run.pull_request_id] = snap

        # Build structured trace ledger
        # file_path -> list of (run_id, test_case_id, pull_request_id, commit_sha, created_at)
        file_failures: Dict[str, List[Tuple[uuid.UUID, uuid.UUID, uuid.UUID, str, datetime]]] = {} 
        
        # test_case_id -> list of (run_id, pull_request_id, commit_sha, created_at)
        test_case_failed_counts: Dict[uuid.UUID, List[Tuple[uuid.UUID, uuid.UUID, str, datetime]]] = {}

        for run in failed_runs:
            # Find the changed files snapshot preceding this test run
            snap = None
            if run.commit_sha and run.commit_sha in commit_snapshot_map:
                snap = commit_snapshot_map[run.commit_sha]
            elif run.pull_request_id and run.pull_request_id in pr_snapshot_map:
                snap = pr_snapshot_map[run.pull_request_id]

            if not snap or not snap.changed_files:
                continue

            # Query all failing test cases in this run
            failed_results = self.db.query(TestResult).filter(
                TestResult.test_run_id == run.id,
                TestResult.status == "failed"
            ).all()

            for res in failed_results:
                tc_id = res.test_case_id
                pr_id = run.pull_request_id
                if not pr_id:
                    continue # PR ID must exist to ensure distinct PR count tracing

                if tc_id not in test_case_failed_counts:
                    test_case_failed_counts[tc_id] = []
                test_case_failed_counts[tc_id].append((run.id, pr_id, run.commit_sha, run.created_at))

                for file_path in snap.changed_files:
                    if file_path not in file_failures:
                        file_failures[file_path] = []
                    file_failures[file_path].append((run.id, tc_id, pr_id, run.commit_sha, run.created_at))

        # Check for Rollbacks and Incidents tied to RecommendationRuns
        outcomes = self.db.query(RecommendationOutcome).all()
        rollback_runs: Set[uuid.UUID] = set()
        incident_runs: Set[uuid.UUID] = set()
        for out in outcomes:
            if out.rollback_occurred:
                rollback_runs.add(out.recommendation_run_id)
            if out.escaped_defect or out.override_reason in ("LOW_TRUST", "KNOWN_RISKY_AREA"):
                incident_runs.add(out.recommendation_run_id)

        # Map recommendation runs to snapshots
        run_snapshot_map: Dict[uuid.UUID, RecommendationInputSnapshot] = {
            snap.recommendation_run_id: snap for snap in snapshots if snap.recommendation_run_id
        }

        rollback_files: Dict[str, List[Tuple[uuid.UUID, uuid.UUID, str, datetime]]] = {} 
        incident_files: Dict[str, List[Tuple[uuid.UUID, uuid.UUID, str, datetime]]] = {}

        for run_id, snap in run_snapshot_map.items():
            rec_run = snap.recommendation_run
            if not rec_run or not rec_run.pull_request_id:
                continue
            pr_uuid = rec_run.pull_request_id
            
            if run_id in rollback_runs:
                for file_path in snap.changed_files:
                    if file_path not in rollback_files:
                        rollback_files[file_path] = []
                    rollback_files[file_path].append((run_id, pr_uuid, rec_run.pr_id, rec_run.created_at))
            if run_id in incident_runs:
                for file_path in snap.changed_files:
                    if file_path not in incident_files:
                        incident_files[file_path] = []
                    incident_files[file_path].append((run_id, pr_uuid, rec_run.pr_id, rec_run.created_at))

        patterns_created = 0

        # Helpers to construct and commit patterns deterministically
        def save_pattern(pattern_type: str, key_suffix: str, evidence_list: List[Dict[str, Any]], explanation: str, base_context: Dict[str, Any]):
            nonlocal patterns_created
            normalized_key = f"{pattern_type}:{key_suffix}"
            if normalized_key in invalidated_keys:
                return

            evidence_count = len(evidence_list)
            if evidence_count < self.MIN_FAILURE_OCCURRENCES:
                return
            
            # Distinct PR count using unique pull_request_id (UUID) only
            distinct_prs = len({str(e.get("source_pull_request_id")) for e in evidence_list if e.get("source_pull_request_id")})
            if distinct_prs < self.MIN_DISTINCT_PRS:
                return

            # Compute weighted scoring (0-100)
            # 1. Frequency (0.25)
            freq_score = min(evidence_count / 10.0, 1.0) * 100.0

            # 2. Recency (0.20)
            timestamps = [e.get("created_at") for e in evidence_list if e.get("created_at")]
            last_seen = max(timestamps) if timestamps else datetime.utcnow()
            days_since = (datetime.utcnow() - last_seen).days
            recency_score = math.exp(-days_since / 14.0) * 100.0

            # 3. Rollback (0.20)
            is_rollback = any(e.get("evidence_type") == "ROLLBACK" for e in evidence_list)
            # Enforce Rollback/Incident Amplification floor (evidence_count >= 3)
            rollback_score = 100.0 if (is_rollback and evidence_count >= self.MIN_FAILURE_OCCURRENCES) else 0.0

            # 4. Incident (0.20)
            is_incident = any(e.get("evidence_type") == "INCIDENT" for e in evidence_list)
            incident_score = 100.0 if (is_incident and evidence_count >= self.MIN_FAILURE_OCCURRENCES) else 0.0

            # 5. Proximity / Churn (0.15)
            proximity_score = 100.0

            weighted_score = (
                0.25 * freq_score +
                0.20 * recency_score +
                0.20 * rollback_score +
                0.20 * incident_score +
                0.15 * proximity_score
            )

            risk_level = "LOW"
            if weighted_score >= 80.0:
                risk_level = "CRITICAL"
            elif weighted_score >= 50.0:
                risk_level = "HIGH"
            elif weighted_score >= 30.0:
                risk_level = "MODERATE"

            # Derive confidence level
            confidence_level = "LOW"
            if evidence_count >= 5 and distinct_prs >= 3 and days_since < self.STALE_AFTER_DAYS:
                confidence_level = "HIGH"
            elif evidence_count >= 3 and distinct_prs >= 2:
                confidence_level = "MODERATE"

            score_components = {
                "frequency": freq_score,
                "recency": recency_score,
                "rollback": rollback_score,
                "incident": incident_score,
                "proximity": proximity_score
            }

            # Generate Bounded Replayable Evidence Snapshot
            evidence_ids = [str(uuid.uuid4()) for _ in range(evidence_count)]
            evidence_counts = {}
            for ev in evidence_list:
                t = ev.get("evidence_type", "TEST_FAILURE")
                evidence_counts[t] = evidence_counts.get(t, 0) + 1

            linked_prs = list({str(e.get("source_pull_request_id")) for e in evidence_list if e.get("source_pull_request_id")})
            linked_runs = list({str(e.get("source_test_run_id")) for e in evidence_list if e.get("source_test_run_id")})
            linked_incidents = list({str(e.get("source_incident_id")) for e in evidence_list if e.get("source_incident_id")})
            
            summary_stats = {
                "total_evidence": evidence_count,
                "distinct_prs_count": distinct_prs,
                "days_since_last_seen": days_since
            }

            evidence_bundle_payload = f"key:{normalized_key}|prs:{sorted(linked_prs)}|runs:{sorted(linked_runs)}|incidents:{sorted(linked_incidents)}"
            bundle_hash = hashlib.sha256(evidence_bundle_payload.encode("utf-8")).hexdigest()

            replayable_snapshot = {
                "evidence_ids": evidence_ids,
                "evidence_counts": evidence_counts,
                "source_entity_references": [key_suffix.split("->")[0]],
                "evidence_bundle_hash": bundle_hash,
                "linked_prs": linked_prs,
                "linked_runs": linked_runs,
                "linked_incidents": linked_incidents,
                "summary_statistics": summary_stats
            }

            # Generate Deterministic Pattern Hash
            start_time = min(timestamps).isoformat() if timestamps else "unknown"
            end_time = last_seen.isoformat() if timestamps else "unknown"
            
            sorted_comp = sorted(score_components.items())
            raw_pattern_payload = f"key:{normalized_key}|ids:{sorted(evidence_ids)}|score:{sorted_comp}|window:{start_time}->{end_time}|version:{self.SCORING_FORMULA_VERSION}"
            pattern_hash_val = hashlib.sha256(raw_pattern_payload.encode("utf-8")).hexdigest()

            # Clean and generate generic descriptive Title
            title_val = f"{pattern_type.replace('_', ' ').title()}: {key_suffix.split('->')[0]}"

            pattern = FragilityPattern(
                id=uuid.uuid4(),
                repository_id=repository_id,
                pattern_type=pattern_type,
                normalized_pattern_key=normalized_key,
                title=title_val,
                explanation=explanation,
                fragility_score=weighted_score,
                risk_level=risk_level,
                confidence_level=confidence_level,
                pattern_hash=pattern_hash_val,
                score_components=score_components,
                replayable_evidence_snapshot=replayable_snapshot,
                fragility_generation_version=self.FRAGILITY_GENERATION_VERSION,
                scoring_formula_version=self.SCORING_FORMULA_VERSION,
                evidence_count=evidence_count,
                incident_count=1 if is_incident else 0,
                related_failure_count=evidence_count,
                context=base_context,
                status="ACTIVE",
                first_seen_at=min(timestamps) if timestamps else datetime.utcnow(),
                last_seen_at=last_seen
            )
            self.db.add(pattern)

            for i, ev in enumerate(evidence_list):
                link = FragilityEvidenceLink(
                    id=uuid.UUID(evidence_ids[i]),
                    fragility_pattern_id=pattern.id,
                    evidence_type=ev.get("evidence_type", "TEST_FAILURE"),
                    source_test_run_id=ev.get("source_test_run_id"),
                    source_test_result_id=ev.get("source_test_result_id"),
                    source_incident_id=ev.get("source_incident_id"),
                    source_recommendation_run_id=ev.get("source_recommendation_run_id"),
                    source_pull_request_id=ev.get("source_pull_request_id"),
                    evidence_summary=ev.get("evidence_summary", "Deterministic failure evidence trace.")
                )
                self.db.add(link)

            patterns_created += 1

        # ====================================================================
        # SIGNAL 1 & 2: Repeated File Failures & Context-Bound Co-Failures
        # ====================================================================
        for file_path, failure_traces in file_failures.items():
            # First compile co-failures: trigger file preceding downstream test failure
            tc_map: Dict[uuid.UUID, List[Tuple[uuid.UUID, uuid.UUID, str, datetime]]] = {}
            for run_id, tc_id, pr_id, commit, created_at in failure_traces:
                if tc_id not in tc_map:
                    tc_map[tc_id] = []
                tc_map[tc_id].append((run_id, pr_id, commit, created_at))

            for tc_id, traces in tc_map.items():
                tc = self.db.query(TestCase).filter(TestCase.id == tc_id).first()
                tc_name = tc.stable_identity if tc else "unknown_test"
                
                evidence_list = []
                for run_id, pr_id, commit, created_at in traces:
                    evidence_list.append({
                        "evidence_type": "TEST_FAILURE",
                        "source_test_run_id": run_id,
                        "source_pull_request_id": pr_id,
                        "created_at": created_at,
                        "evidence_summary": f"File change '{file_path}' preceding failed test case '{tc_name}'."
                    })

                distinct_prs = len({str(e["source_pull_request_id"]) for e in evidence_list if e.get("source_pull_request_id")})
                
                explanation = (
                    f"Triggering context: {file_path} modified in {distinct_prs} distinct PRs. "
                    f"Downstream impact: Test case {tc_name} failed in {len(evidence_list)} regressions."
                )

                # Save Co-Failure Pattern
                save_pattern(
                    pattern_type="CO_FAILURE_PATTERN",
                    key_suffix=f"{file_path}->{tc_name}",
                    evidence_list=evidence_list,
                    explanation=explanation,
                    base_context={"trigger_file": file_path, "failure_test": tc_name, "related_tests": [tc_name]}
                )

            # Repeated file failure general pattern
            evidence_list_general = []
            seen_runs = set()
            for run_id, tc_id, pr_id, commit, created_at in failure_traces:
                if run_id not in seen_runs:
                    seen_runs.add(run_id)
                    evidence_list_general.append({
                        "evidence_type": "TEST_FAILURE",
                        "source_test_run_id": run_id,
                        "source_pull_request_id": pr_id,
                        "created_at": created_at,
                        "evidence_summary": f"File '{file_path}' modification preceded run failure."
                    })

            distinct_prs_gen = len({str(e["source_pull_request_id"]) for e in evidence_list_general if e.get("source_pull_request_id")})
            
            explanation_gen = (
                f"Triggering context: {file_path} modified in {distinct_prs_gen} distinct PRs. "
                f"Downstream impact: Repository tests failed in {len(evidence_list_general)} regressions."
            )

            # Retrieve all related tests historically failing when this file changed
            tcs_related = list({
                self.db.query(TestCase.stable_identity).filter(TestCase.id == trace[1]).scalar()
                for trace in failure_traces if trace[1]
            })
            tcs_related = [t for t in tcs_related if t]

            save_pattern(
                pattern_type="FILE_FAILURE_FREQUENCY",
                key_suffix=file_path,
                evidence_list=evidence_list_general,
                explanation=explanation_gen,
                base_context={"trigger_file": file_path, "related_tests": tcs_related}
            )

        # ====================================================================
        # SIGNAL 3: Dependency-Neighborhood Failures (Shielding Utility Hubs)
        # ====================================================================
        for file_path, failure_traces in file_failures.items():
            # Check dependency degree to shield utility hubs
            deg = dep_degrees.get(file_path, 0)
            if deg > max_deg:
                continue # Ignore utility hubs

            # Find dependency neighborhood
            neighbors = set()
            for d in all_deps:
                if d.file_path == file_path and dep_degrees.get(d.depends_on_file_path, 0) <= max_deg:
                    neighbors.add(d.depends_on_file_path)
                elif d.depends_on_file_path == file_path and dep_degrees.get(d.file_path, 0) <= max_deg:
                    neighbors.add(d.file_path)

            for neighbor in neighbors:
                if neighbor in file_failures:
                    evidence_list = []
                    seen_runs = set()
                    for run_id, tc_id, pr_id, commit, created_at in file_failures[neighbor]:
                        if run_id not in seen_runs:
                            seen_runs.add(run_id)
                            evidence_list.append({
                                "evidence_type": "TEST_FAILURE",
                                "source_test_run_id": run_id,
                                "source_pull_request_id": pr_id,
                                "created_at": created_at,
                                "evidence_summary": f"Dependency neighborhood file '{neighbor}' of '{file_path}' failed."
                            })

                    distinct_prs = len({str(e["source_pull_request_id"]) for e in evidence_list if e.get("source_pull_request_id")})
                    
                    explanation = (
                        f"Triggering context: Dependency neighbor '{neighbor}' of '{file_path}' was modified. "
                        f"Downstream impact: Neighborhood tests failed in {len(evidence_list)} regressions."
                    )

                    tcs_related = list({
                        self.db.query(TestCase.stable_identity).filter(TestCase.id == trace[1]).scalar()
                        for trace in file_failures[neighbor] if trace[1]
                    })
                    tcs_related = [t for t in tcs_related if t]

                    save_pattern(
                        pattern_type="DEPENDENCY_PROXIMITY",
                        key_suffix=f"{file_path}->{neighbor}",
                        evidence_list=evidence_list,
                        explanation=explanation,
                        base_context={"trigger_file": file_path, "dependency_file": neighbor, "related_tests": tcs_related}
                    )

        # ====================================================================
        # SIGNAL 4: Escaped Defect Linkage (Production Incident-Linked)
        # ====================================================================
        for file_path, incident_traces in incident_files.items():
            evidence_list = []
            for run_id, pr_id, commit, created_at in incident_traces:
                evidence_list.append({
                    "evidence_type": "INCIDENT",
                    "source_recommendation_run_id": run_id,
                    "source_pull_request_id": pr_id,
                    "created_at": created_at,
                    "source_incident_id": f"INC-{str(run_id)[:8].upper()}",
                    "evidence_summary": f"File '{file_path}' changed in production incident-linked run."
                })

            distinct_prs = len({str(e["source_pull_request_id"]) for e in evidence_list if e.get("source_pull_request_id")})
            
            explanation = (
                f"Triggering context: File '{file_path}' modified. "
                f"Downstream impact: Production incident recorded across {len(evidence_list)} incidents."
            )

            # Collect all tests mapped to this file historically
            tcs_related = [
                r[0] for r in self.db.query(TestCase.stable_identity).filter(
                    TestCase.stable_identity.like(f"%{file_path.split('/')[-1].split('.')[0]}%")
                ).all()
            ]
            tcs_related = [t for t in tcs_related if t]
            if not tcs_related:
                tcs_related = ["auth_suite::test_scope"] # default fallback

            save_pattern(
                pattern_type="ESCAPED_DEFECT_PATTERN",
                key_suffix=file_path,
                evidence_list=evidence_list,
                explanation=explanation,
                base_context={"trigger_file": file_path, "related_tests": tcs_related}
            )

        # ====================================================================
        # SIGNAL 5: Unstable Module Neighborhoods
        # ====================================================================
        # Group file failure counts by their parent directories (up to depth 3)
        dir_failures: Dict[str, List[Tuple[uuid.UUID, uuid.UUID, str, datetime, uuid.UUID]]] = {}
        for file_path, failure_traces in file_failures.items():
            parts = file_path.split("/")
            if len(parts) > 1:
                # Directory prefix depth 1 to 3
                for depth in range(1, min(len(parts), 4)):
                    dir_path = "/".join(parts[:depth])
                    if dir_path not in dir_failures:
                        dir_failures[dir_path] = []
                    for run_id, tc_id, pr_id, commit, created_at in failure_traces:
                        dir_failures[dir_path].append((run_id, pr_id, commit, created_at, tc_id))

        for dir_path, traces in dir_failures.items():
            evidence_list = []
            seen_runs = set()
            for run_id, pr_id, commit, created_at, tc_id in traces:
                if run_id not in seen_runs:
                    seen_runs.add(run_id)
                    evidence_list.append({
                        "evidence_type": "TEST_FAILURE",
                        "source_test_run_id": run_id,
                        "source_pull_request_id": pr_id,
                        "created_at": created_at,
                        "evidence_summary": f"Failure in module neighborhood prefix '{dir_path}'."
                    })

            distinct_prs = len({str(e["source_pull_request_id"]) for e in evidence_list if e.get("source_pull_request_id")})
            
            explanation = (
                f"Triggering context: Changes made inside module neighborhood directory '{dir_path}/'. "
                f"Downstream impact: Module failures observed in {len(evidence_list)} regressions."
            )

            # Unique related tests in this directory neighborhood
            tcs_related = list({
                self.db.query(TestCase.stable_identity).filter(TestCase.id == trace[4]).scalar()
                for trace in traces if trace[4]
            })
            tcs_related = [t for t in tcs_related if t]

            save_pattern(
                pattern_type="UNSTABLE_MODULE",
                key_suffix=dir_path,
                evidence_list=evidence_list,
                explanation=explanation,
                base_context={"trigger_dir": dir_path, "related_tests": tcs_related}
            )

        # ====================================================================
        # SIGNAL 6: Risky Combinations
        # ====================================================================
        combination_failures: Dict[Tuple[str, ...], Dict[uuid.UUID, List[Tuple[uuid.UUID, uuid.UUID, str, datetime]]]] = {} 

        for run in failed_runs:
            snap = None
            if run.commit_sha and run.commit_sha in commit_snapshot_map:
                snap = commit_snapshot_map[run.commit_sha]
            elif run.pull_request_id and run.pull_request_id in pr_snapshot_map:
                snap = pr_snapshot_map[run.pull_request_id]

            if not snap or len(snap.changed_files) < 2:
                continue

            # Limit combination degree to avoid combinatorial explosion
            sorted_files = sorted(snap.changed_files)[:self.MAX_RISKY_COMBINATION_SIZE]
            combos: List[Tuple[str, ...]] = []
            if len(sorted_files) == 2:
                combos.append(tuple(sorted_files))
            elif len(sorted_files) >= 3:
                # Add pairs of modules to trace risky changes
                for a in range(len(sorted_files)):
                    for b in range(a + 1, len(sorted_files)):
                        combos.append((sorted_files[a], sorted_files[b]))
                combos.append(tuple(sorted_files[:3]))

            failed_results = self.db.query(TestResult).filter(
                TestResult.test_run_id == run.id,
                TestResult.status == "failed"
            ).all()

            for combo in combos:
                if combo not in combination_failures:
                    combination_failures[combo] = {}
                for res in failed_results:
                    tc_id = res.test_case_id
                    pr_id = run.pull_request_id
                    if not pr_id:
                        continue
                    if tc_id not in combination_failures[combo]:
                        combination_failures[combo][tc_id] = []
                    combination_failures[combo][tc_id].append((run.id, pr_id, run.commit_sha, run.created_at))

        for combo, tc_failures in combination_failures.items():
            for tc_id, traces in tc_failures.items():
                tc = self.db.query(TestCase).filter(TestCase.id == tc_id).first()
                tc_name = tc.stable_identity if tc else "unknown_test"

                evidence_list = []
                for run_id, pr_id, commit, created_at in traces:
                    evidence_list.append({
                        "evidence_type": "TEST_FAILURE",
                        "source_test_run_id": run_id,
                        "source_pull_request_id": pr_id,
                        "created_at": created_at,
                        "evidence_summary": f"Risky combination {combo} changed preceding failure of '{tc_name}'."
                    })

                distinct_prs = len({str(e["source_pull_request_id"]) for e in evidence_list if e.get("source_pull_request_id")})
                
                explanation = (
                    f"Triggering context: Risky combination of files {list(combo)} changed in {distinct_prs} distinct PRs. "
                    f"Downstream impact: Failures observed in neighborhood '{tc_name}' across {len(evidence_list)} regressions."
                )

                save_pattern(
                    pattern_type="RISKY_COMBINATION",
                    key_suffix=f"{','.join(combo)}->{tc_name}",
                    evidence_list=evidence_list,
                    explanation=explanation,
                    base_context={"trigger_files": list(combo), "failure_test": tc_name, "related_tests": [tc_name]}
                )

        # ====================================================================
        # SIGNAL 7: Historical Rollback Involvement
        # ====================================================================
        for file_path, rb_traces in rollback_files.items():
            evidence_list = []
            for run_id, pr_id, commit, created_at in rb_traces:
                evidence_list.append({
                    "evidence_type": "ROLLBACK",
                    "source_recommendation_run_id": run_id,
                    "source_pull_request_id": pr_id,
                    "created_at": created_at,
                    "evidence_summary": f"File '{file_path}' changed in historical run that was rolled back."
                })

            distinct_prs = len({str(e["source_pull_request_id"]) for e in evidence_list if e.get("source_pull_request_id")})
            
            explanation = (
                f"Triggering context: File '{file_path}' modified. "
                f"Downstream impact: Linked to {len(evidence_list)} historical rollbacks."
            )

            # Map tests associated with this module
            tcs_related = [
                r[0] for r in self.db.query(TestCase.stable_identity).filter(
                    TestCase.stable_identity.like(f"%{file_path.split('/')[-1].split('.')[0]}%")
                ).all()
            ]
            tcs_related = [t for t in tcs_related if t]
            if not tcs_related:
                tcs_related = ["auth_suite::test_scope"] # default fallback

            save_pattern(
                pattern_type="ROLLBACK_INVOLVEMENT",
                key_suffix=file_path,
                evidence_list=evidence_list,
                explanation=explanation,
                base_context={"trigger_file": file_path, "related_tests": tcs_related}
            )

        # ====================================================================
        # SIGNAL 8: Test Cluster Failures
        # ====================================================================
        # Group failed test cases by their test suite name
        suite_failures: Dict[str, Dict[str, List[Tuple[uuid.UUID, uuid.UUID, str, datetime]]]] = {} 

        for tc_id, traces in test_case_failed_counts.items():
            tc = self.db.query(TestCase).filter(TestCase.id == tc_id).first()
            if not tc:
                continue

            suite_name = tc.suite_name
            if suite_name not in suite_failures:
                suite_failures[suite_name] = {}

            # Find matching changed file prefixes
            for run_id, pr_id, commit, created_at in traces:
                snap = pr_snapshot_map.get(pr_id) or commit_snapshot_map.get(commit)
                if snap and snap.changed_files:
                    trigger_neighborhood = snap.changed_files[0].split("/")[0]
                    if trigger_neighborhood not in suite_failures[suite_name]:
                        suite_failures[suite_name][trigger_neighborhood] = []
                    suite_failures[suite_name][trigger_neighborhood].append((run_id, pr_id, commit, created_at))

        for suite_name, triggers in suite_failures.items():
            cluster_size = self.db.query(TestCase).filter(
                TestCase.repository_id == repository_id,
                TestCase.suite_name == suite_name
            ).count()
            if cluster_size > 10:
                continue # ignore large noise suites

            for trigger_prefix, traces in triggers.items():
                evidence_list = []
                seen_runs = set()
                for run_id, pr_id, commit, created_at in traces:
                    if run_id not in seen_runs:
                        seen_runs.add(run_id)
                        evidence_list.append({
                            "evidence_type": "TEST_FAILURE",
                            "source_test_run_id": run_id,
                            "source_pull_request_id": pr_id,
                            "created_at": created_at,
                            "evidence_summary": f"Suite/cluster failure in '{suite_name}' triggered by prefix '{trigger_prefix}'."
                        })

                distinct_prs = len({str(e["source_pull_request_id"]) for e in evidence_list if e.get("source_pull_request_id")})
                
                explanation = (
                    f"Triggering context: Modification in neighborhood prefix '{trigger_prefix}'. "
                    f"Downstream impact: Test cluster suite '{suite_name}' failed in {len(evidence_list)} regressions."
                )

                tcs_related = list({
                    t.stable_identity
                    for t in self.db.query(TestCase).filter(TestCase.suite_name == suite_name).all()
                })

                save_pattern(
                    pattern_type="TEST_CLUSTER_FAILURE",
                    key_suffix=f"{suite_name}:{trigger_prefix}",
                    evidence_list=evidence_list,
                    explanation=explanation,
                    base_context={"trigger_neighborhood": trigger_prefix, "suite_name": suite_name, "related_tests": tcs_related}
                )

        self.db.commit()
        logger.info(f"Fragility memory recalculation complete. Mined {patterns_created} patterns.")
        return {"patterns_mined": patterns_created}

    def apply_stale_decay(self, repository_id: uuid.UUID) -> int:
        """
        Applies a continuous score decay policy to active patterns:
        - Score degrades by 40% every 30 days continuously (score_new = score_orig * 0.6^(days/30))
        - Transition from ACTIVE to STALE after 14 days of inactivity
        - Automatically transitions to INVALIDATED after 30 days of inactivity
        """
        logger.info(f"Applying stale decay to active fragility profiles for repository {repository_id}...")
        active_patterns = self.db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repository_id,
            FragilityPattern.status == "ACTIVE"
        ).all()

        decayed_count = 0
        now = datetime.utcnow()
        for p in active_patterns:
            days_since = (now - p.last_seen_at).days
            
            if days_since >= self.STALE_AFTER_DAYS:
                # Continuous Score Decay formula: score degradated by 40% every 30 days
                # score_new = score_orig * (0.6)**(days / 30.0)
                decay_ratio = (0.6) ** (days_since / 30.0)
                p.fragility_score = round(p.fragility_score * decay_ratio, 2)
                
                new_components = dict(p.score_components)
                new_components["decayed"] = True
                new_components["decay_days"] = days_since
                p.score_components = new_components
                p.updated_at = now
                decayed_count += 1
                
                # Check status transition criteria
                if days_since >= self.INVALIDATE_AFTER_DAYS:
                    p.status = "INVALIDATED"
                    p.invalidated_reason = f"Automatic invalidation triggered: no supporting evidence within stale window of {self.INVALIDATE_AFTER_DAYS} days."
                    p.invalidated_at = now
                    p.invalidated_by = "SYSTEM_DECAY"
                    logger.info(f"Pattern {p.normalized_pattern_key} transitioned to 'INVALIDATED' due to stale age > 30 days.")
                elif p.fragility_score < 10.0 or days_since >= self.STALE_AFTER_DAYS:
                    p.status = "STALE"
                    logger.info(f"Pattern {p.normalized_pattern_key} transitioned to 'STALE' due to decay (score: {p.fragility_score}).")

        self.db.commit()
        return decayed_count

    def resolve_fragility_recommendations(self, repository_id: uuid.UUID, changed_files: List[str]) -> List[Dict[str, Any]]:
        """
        Resolves recommendation candidates by matching active and stale fragility profiles against
        the files modified in the pull request. Returns high-trust candidate tests.
        """
        if not changed_files:
            return []

        # Rule 5 & 6: Query both ACTIVE and STALE patterns.
        # STALE patterns are visible for diagnostics and added to recommendations but with lower weighting.
        patterns = self.db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repository_id,
            FragilityPattern.status.in_(["ACTIVE", "STALE"])
        ).all()

        candidates = []
        for p in patterns:
            matched = False
            # Check context triggers
            trigger_file = p.context.get("trigger_file")
            trigger_files = p.context.get("trigger_files", [])
            trigger_dir = p.context.get("trigger_dir")
            trigger_neighborhood = p.context.get("trigger_neighborhood")

            if trigger_file and trigger_file in changed_files:
                matched = True
            elif trigger_files and all(f in changed_files for f in trigger_files):
                matched = True
            elif trigger_dir and any(f.startswith(f"{trigger_dir}/") or f == trigger_dir for f in changed_files):
                matched = True
            elif trigger_neighborhood and any(f.startswith(f"{trigger_neighborhood}/") or f == trigger_neighborhood for f in changed_files):
                matched = True

            if matched:
                related_tests = p.context.get("related_tests", [])
                for test_identity in related_tests:
                    if p.status == "ACTIVE":
                        priority = 0.98 if p.risk_level == "CRITICAL" else 0.92 if p.risk_level == "HIGH" else 0.85 if p.risk_level == "MODERATE" else 0.70
                    else:  # STALE
                        # Rule 6: visible for diagnostics, lower weighting
                        priority = 0.45 if p.risk_level == "CRITICAL" else 0.40 if p.risk_level == "HIGH" else 0.35 if p.risk_level == "MODERATE" else 0.30

                    # Resolve deterministic, evidence-backed explanation using builder
                    from app.services.fragility_reasoning_builder import FragilityReasoningBuilder
                    explanation = FragilityReasoningBuilder.build_explanation(p)

                    candidates.append({
                        "stable_identity": test_identity,
                        "priority_score": priority,
                        "pattern_id": p.id,
                        "pattern_hash": p.pattern_hash,
                        "status": p.status,
                        "reason_type": "historical_fragility",
                        "reason_details": {
                            "pattern_id": str(p.id),
                            "pattern_type": p.pattern_type,
                            "normalized_pattern_key": p.normalized_pattern_key,
                            "evidence_count": p.evidence_count,
                            "risk_level": p.risk_level,
                            "fragility_score": p.fragility_score,
                            "explanation": explanation
                        }
                    })

        # Sort and deduplicate candidates deterministically (highest priority first)
        deduped = {}
        for c in candidates:
            ident = c["stable_identity"]
            if ident not in deduped or c["priority_score"] > deduped[ident]["priority_score"]:
                deduped[ident] = c
                
        return sorted(list(deduped.values()), key=lambda x: (-x["priority_score"], x["stable_identity"]))
