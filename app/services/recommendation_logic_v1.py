import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from fastapi import HTTPException
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestRun, TestResult, TestCase
from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.flaky_test import FlakyTestProfile
from app.models.user import Workspace
from app.services.repository_readiness import RepositoryReadinessService


class RecommendationLogicV1:
    @classmethod
    def generate_recommendations(
        cls,
        db: Session,
        repository_id: UUID,
        pull_request_id: UUID,
        workspace: Workspace
    ) -> List[Dict[str, Any]]:
        """
        Executes the 5-step scoped recommendation algorithm and MVP fallback,
        returning a list of deterministic recommended test entries.
        """
        # 1. Load changed files
        changed_files_db = (
            db.query(PullRequestChangedFile)
            .filter(PullRequestChangedFile.pull_request_id == pull_request_id)
            .order_by(PullRequestChangedFile.file_path.asc())
            .all()
        )

        # Check for empty changed files list (Case 3)
        if not changed_files_db:
            raise HTTPException(
                status_code=400,
                detail="Pull request has no changed files available for analysis."
            )

        # Check for missing test history (Case 2)
        test_runs_count = db.query(func.count(TestRun.id)).filter(
            TestRun.repository_id == repository_id
        ).scalar() or 0
        if test_runs_count == 0:
            raise HTTPException(
                status_code=400,
                detail="Repository requires test history before recommendations can run."
            )

        changed_paths = [f.file_path for f in changed_files_db]

        # Get all test cases for repository
        test_cases = (
            db.query(TestCase)
            .filter(TestCase.repository_id == repository_id)
            .order_by(TestCase.stable_identity.asc())
            .all()
        )
        tc_map = {str(tc.id): tc for tc in test_cases}
        tc_by_identity = {tc.stable_identity: tc for tc in test_cases}

        # 2. Get flaky profiles
        flaky_profiles = (
            db.query(FlakyTestProfile)
            .filter(FlakyTestProfile.repository_id == repository_id)
            .all()
        )
        flaky_map = {str(p.test_case_id): p.status for p in flaky_profiles}

        # 3. Load historical failures (last 30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        recent_failures = (
            db.query(TestResult)
            .join(TestRun, TestResult.test_run_id == TestRun.id)
            .filter(
                TestRun.repository_id == repository_id,
                TestResult.status == "failed",
                TestResult.created_at >= cutoff
            )
            .all()
        )
        failed_test_case_ids = set(str(res.test_case_id) for res in recent_failures)
        failed_suites = set(res.test_case.suite_name for res in recent_failures if res.test_case)

        # 4. Load average test execution cost
        avg_durations_db = (
            db.query(TestResult.test_case_id, func.avg(TestResult.duration))
            .join(TestRun, TestResult.test_run_id == TestRun.id)
            .filter(TestRun.repository_id == repository_id)
            .group_by(TestResult.test_case_id)
            .all()
        )
        duration_map = {
            str(row[0]): float(row[1]) for row in avg_durations_db if row[1] is not None
        }

        # Map candidate risk values and tracing details
        candidates: Dict[str, Dict[str, Any]] = {}
        has_any_direct_match = False

        for f in changed_files_db:
            file_path = f.file_path
            
            # Step 1: Direct coverage matching via FileTestLink
            direct_links = (
                db.query(FileTestLink)
                .filter(FileTestLink.file_path == file_path)
                .all()
            )

            matched_any_direct = False
            for link in direct_links:
                tc_id_str = str(link.test_case_id)
                tc = tc_map.get(tc_id_str)
                if not tc:
                    continue
                matched_any_direct = True
                has_any_direct_match = True
                
                if tc_id_str not in candidates:
                    candidates[tc_id_str] = {
                        "test_case": tc,
                        "risk_value": 0.95,
                        "source_signal": "DIRECT_COVERAGE",
                        "reason": f"Changed file '{file_path}' has direct coverage link.",
                        "confidence": "HIGH"
                    }
                else:
                    candidates[tc_id_str]["risk_value"] = max(candidates[tc_id_str]["risk_value"], 0.95)
                    if "direct" not in candidates[tc_id_str]["source_signal"].lower():
                        candidates[tc_id_str]["source_signal"] = "DIRECT_COVERAGE"
                        candidates[tc_id_str]["reason"] = f"Changed file '{file_path}' has direct coverage link."
                        candidates[tc_id_str]["confidence"] = "HIGH"

            # Step 2: Path heuristic fallback if no direct mappings exist
            if not matched_any_direct:
                file_stem = file_path.split("/")[-1].split(".")[0]
                dir_tokens = file_path.lower().split("/")[:-1]

                for tc in test_cases:
                    tc_id_str = str(tc.id)
                    matched_heuristic = False
                    heuristic_type = None

                    # A. Match filename stem to test name
                    if file_stem.lower() in tc.test_name.lower() or file_stem.lower() in tc.suite_name.lower():
                        matched_heuristic = True
                        heuristic_type = "STEM_MATCH"
                    
                    # B. Match directory tokens to suite name
                    elif any(token in tc.suite_name.lower() for token in dir_tokens if token not in ("src", "app", "tests", "test")):
                        matched_heuristic = True
                        heuristic_type = "DIR_MATCH"

                    # C. Match module name similarity
                    elif any(token in tc.test_name.lower() for token in dir_tokens if token not in ("src", "app", "tests", "test")):
                        matched_heuristic = True
                        heuristic_type = "MODULE_MATCH"

                    if matched_heuristic:
                        base_priority = 0.60 if heuristic_type == "STEM_MATCH" else 0.45
                        reason = f"Heuristic fallback '{heuristic_type}' match for changed file '{file_path}'."
                        
                        if tc_id_str not in candidates:
                            candidates[tc_id_str] = {
                                "test_case": tc,
                                "risk_value": base_priority,
                                "source_signal": "PATH_HEURISTIC",
                                "reason": reason,
                                "confidence": "MEDIUM"
                            }
                        else:
                            candidates[tc_id_str]["risk_value"] = max(candidates[tc_id_str]["risk_value"], base_priority)

        # Step 3: Historical failure boost
        for tc_id_str, cand in candidates.items():
            tc = cand["test_case"]
            boost = 0.0
            reasons_boost = []

            # Boost failed tests
            if tc_id_str in failed_test_case_ids:
                boost += 0.20
                reasons_boost.append("failed recently")

            # Boost tests from recently failed suites
            if tc.suite_name in failed_suites:
                boost += 0.10
                reasons_boost.append("suite has recent failures")

            # Boost tests matching changed module names
            changed_modules = set(p.split("/")[0] for p in changed_paths if "/" in p)
            if any(m.lower() in tc.suite_name.lower() for m in changed_modules if m not in ("src", "app", "tests", "test")):
                boost += 0.15
                reasons_boost.append("matches changed module failure context")

            if boost > 0.0:
                cand["risk_value"] = round(cand["risk_value"] + boost, 2)
                cand["source_signal"] = cand["source_signal"] + "+HISTORICAL_FAILURE"
                cand["reason"] = cand["reason"] + f" [Boosted: {', '.join(reasons_boost)}]"

        # Step 4: Flaky/quarantine handling
        executable_candidates = []
        for tc_id_str, cand in candidates.items():
            flaky_status = flaky_map.get(tc_id_str)
            tc = cand["test_case"]

            # Quarantined tests: exclude by default
            if flaky_status == "quarantined":
                # Exclude from main execution list
                continue

            # Unstable tests: include but flag
            if flaky_status == "unstable":
                cand["reason"] = cand["reason"] + " [FLAKY WARNING: Test is unstable]"
                cand["confidence"] = "MEDIUM"

            executable_candidates.append(cand)

        # Step 5: Runtime ordering and deterministic sorting
        recommended_tests = []
        for cand in executable_candidates:
            tc = cand["test_case"]
            tc_id_str = str(tc.id)

            # execution_cost
            avg_dur = duration_map.get(tc_id_str)
            estimated_duration = avg_dur if (avg_dur is not None and avg_dur > 0) else 5.0

            # priority score (risk_value / execution_cost)
            priority = round(cand["risk_value"] / estimated_duration, 4)

            recommended_tests.append({
                "test_identifier": tc.stable_identity,
                "test_name": tc.test_name,
                "class_name/module": tc.suite_name,
                "priority": priority,
                "risk_value": cand["risk_value"], # kept for sorting tiebreakers
                "estimated_duration_seconds": round(estimated_duration, 2),
                "reason": cand["reason"],
                "confidence": cand["confidence"],
                "source_signal": cand["source_signal"]
            })

        # MVP Fallback: If no strong mapping exists but history exists
        test_runs_count = db.query(func.count(TestRun.id)).filter(TestRun.repository_id == repository_id).scalar() or 0
        if not recommended_tests and test_runs_count > 0 and test_cases:
            # Select up to 5 conservative historical test cases (deterministically sorted by identity)
            fallback_tcs = test_cases[:5]
            for tc in fallback_tcs:
                tc_id_str = str(tc.id)
                avg_dur = duration_map.get(tc_id_str)
                estimated_duration = avg_dur if (avg_dur is not None and avg_dur > 0) else 5.0
                
                # Low risk default
                risk_value = 0.20
                priority = round(risk_value / estimated_duration, 4)

                recommended_tests.append({
                    "test_identifier": tc.stable_identity,
                    "test_name": tc.test_name,
                    "class_name/module": tc.suite_name,
                    "priority": priority,
                    "risk_value": risk_value,
                    "estimated_duration_seconds": round(estimated_duration, 2),
                    "reason": "Fallback recommendation due to missing direct/heuristic mappings. Selected conservative subset from historical executions.",
                    "confidence": "LOW",
                    "source_signal": "HISTORICAL_FAILURE_FALLBACK"
                })

        # Enforce Case 1 fallback if no direct coverage matches were found
        if not has_any_direct_match:
            for t in recommended_tests:
                t["confidence"] = "LOW"
                t["reason"] = "No direct coverage match found; selected tests using historical/path fallback."

        # Sort deterministically:
        # - priority desc
        # - risk_value desc
        # - estimated_duration_seconds asc
        # - test_identifier asc
        def sort_key(t):
            return (-t["priority"], -t["risk_value"], t["estimated_duration_seconds"], t["test_identifier"])

        recommended_tests.sort(key=sort_key)

        # Remove risk_value helper key from final output dictionary list
        for t in recommended_tests:
            t.pop("risk_value", None)

        return recommended_tests
