import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.test_result import TestResult, TestRun, TestCase
from app.models.coverage import FileTestLink
from app.models.flaky_test import FlakyTestProfile
from app.schemas.recommendation import HistoricalFailureTest, HistoricalFailureBundle


class HistoricalFailureResolver:
    @staticmethod
    def resolve_historical_failures(
        db: Session,
        repository_id: uuid.UUID,
        changed_files: List[str],
        dependency_files: List[str],
        history_window_days: int = 30
    ) -> HistoricalFailureBundle:
        """
        Boost tests that recently failed and are relevant to the changed/dependency neighborhood.
        """
        # Calculate time window (Rule 2)
        test_history_window_end = datetime.utcnow()
        test_history_window_start = test_history_window_end - timedelta(days=history_window_days)

        # Query failed / error test results in the window
        results_db = db.query(TestResult).join(
            TestRun, TestResult.test_run_id == TestRun.id
        ).join(
            TestCase, TestResult.test_case_id == TestCase.id
        ).filter(
            TestCase.repository_id == repository_id,
            TestResult.status.in_(["failed", "error"]),
            TestRun.created_at >= test_history_window_start,
            TestRun.created_at <= test_history_window_end
        ).all()

        reasons = []

        # If no failures are found, return early
        if not results_db:
            reasons.append("No historical failures found in the window.")
            return HistoricalFailureBundle(
                historical_failure_tests=[],
                test_history_window_start=test_history_window_start,
                test_history_window_end=test_history_window_end,
                reasons=reasons
            )

        # Group results by test_case_id to compute count and failed_at
        grouped_results = {}
        for r in results_db:
            tc_id = r.test_case_id
            if tc_id not in grouped_results:
                grouped_results[tc_id] = []
            grouped_results[tc_id].append(r)

        # Query all FileTestLink records mapping to changed or dependency files
        all_target_files = set(changed_files) | set(dependency_files)
        links = db.query(FileTestLink).filter(
            FileTestLink.file_path.in_(list(all_target_files))
        ).all()

        # Map test_case_id -> set of covered files
        test_to_files = {}
        for link in links:
            tc_id_str = str(link.test_case_id)
            if tc_id_str not in test_to_files:
                test_to_files[tc_id_str] = set()
            test_to_files[tc_id_str].add(link.file_path)

        # Query FlakyTestProfile records for exclusions (Rule 4)
        flaky_profiles = db.query(FlakyTestProfile).filter(
            FlakyTestProfile.repository_id == repository_id
        ).all()
        flaky_map = {str(fp.test_case_id): fp for fp in flaky_profiles}

        # Parent directory folders of changed files (Rule 3 & 6 same module)
        module_folders = set()
        for f in changed_files:
            parts = Path(f).parts
            for part in parts[:-1]:
                if part.lower() not in ("", "src", "app", "lib", "test", "tests"):
                    module_folders.add(part.lower())

        candidates = []

        for tc_id, r_list in grouped_results.items():
            tc = r_list[0].test_case
            tc_id_str = str(tc_id)

            # Determine relevance and priority
            relevance_type = None
            priority_score = 0.0

            covered_files = test_to_files.get(tc_id_str, set())

            # A. DIRECT (covers a changed file directly)
            has_direct = any(f in changed_files for f in covered_files)
            if has_direct:
                relevance_type = "DIRECT"
                priority_score = 0.90
            
            # B. DEPENDENCY_NEIGHBORHOOD (covers a dependency file)
            else:
                has_dep = any(f in dependency_files for f in covered_files)
                if has_dep:
                    relevance_type = "DEPENDENCY_NEIGHBORHOOD"
                    priority_score = 0.80
                
                # C. SAME_MODULE (suite name or test name containing parent folder of a changed file)
                else:
                    tc_suite_lower = tc.suite_name.lower()
                    tc_test_lower = tc.test_name.lower()
                    in_same_module = False
                    for folder in module_folders:
                        if folder in tc_suite_lower or folder in tc_test_lower:
                            in_same_module = True
                            break
                    if in_same_module:
                        relevance_type = "SAME_MODULE"
                        priority_score = 0.70

            # If not relevant to neighborhood, ignore it (Rule 1: not global noise)
            if not relevance_type:
                continue

            # Check flakiness status (Rule 4)
            is_flaky = False
            fp = flaky_map.get(tc_id_str)
            if fp and fp.status in ("unstable", "quarantined"):
                is_flaky = True

            # Exclude if flaky and not DIRECT
            if is_flaky and relevance_type != "DIRECT":
                continue

            # Calculate failure metrics in the window
            failure_count = len(r_list)
            failed_at = max(r.created_at for r in r_list)

            # Build candidate reason
            if is_flaky:
                reason = f"Test failed {failure_count} time(s), recently at {failed_at.isoformat()}. WARNING: Test is flaky (status: {fp.status}). Included because it directly covers changed files."
            else:
                reason = f"Test failed {failure_count} time(s), recently at {failed_at.isoformat()}. Scope relevance: {relevance_type}."

            candidates.append(
                HistoricalFailureTest(
                    test_case_id=tc_id,
                    stable_identity=tc.stable_identity,
                    priority_score=priority_score,
                    failed_at=failed_at,
                    failure_count=failure_count,
                    relevance_type=relevance_type,
                    reason=reason
                )
            )

        # Sort candidates deterministically (Rule 8)
        # 1. priority_score descending
        # 2. failed_at descending
        # 3. stable_identity ascending
        def sort_key(c):
            return (-c.priority_score, -c.failed_at.timestamp(), c.stable_identity)

        candidates.sort(key=sort_key)

        # Limit output candidates to MAX_HISTORICAL_FAILURE_TESTS = 25 (Rule 5)
        MAX_HISTORICAL_FAILURE_TESTS = 25
        capped_candidates = candidates[:MAX_HISTORICAL_FAILURE_TESTS]

        # Populate verbose reason summary
        reasons.append(f"Analyzed {len(grouped_results)} historical failure test case(s). Boosted {len(capped_candidates)} relevant neighborhood failure(s).")

        return HistoricalFailureBundle(
            historical_failure_tests=capped_candidates,
            test_history_window_start=test_history_window_start,
            test_history_window_end=test_history_window_end,
            reasons=reasons
        )
