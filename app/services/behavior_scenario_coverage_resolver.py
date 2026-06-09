from typing import List, Dict, Any, Optional
import uuid

from app.models.behavior import Behavior
from app.models.behavior_scenario import BehaviorScenario
from app.models.behavior_scenario_coverage import BehaviorScenarioCoverage


class BehaviorScenarioCoverageResolver:
    """Resolves and populates coverage state for business behavior scenarios based on explicit telemetry rules."""

    def __init__(self, db: Optional[Any] = None):
        """Initialize resolver with optional database session."""
        self.db = db

    def resolve_scenario_coverage(
        self,
        repository_id: Any,
        behavior: Behavior,
        scenario: BehaviorScenario,
        recommendation_run_id: Optional[Any] = None,
        existing_test_mappings: Optional[List[Dict[str, Any]]] = None, # [{ "test_name": "test_reset_expired", "confidence": "HIGH", "coverage_files": [...] }]
        current_pr_test_runs: Optional[List[Dict[str, Any]]] = None,    # [{ "test_name": "test_reset_expired", "status": "passed" }]
        file_coverage_data: Optional[Dict[str, float]] = None,          # file_path -> coverage_pct
    ) -> BehaviorScenarioCoverage:
        """Resolve precise coverage status for a single business behavior scenario."""
        coverage_status = "UNKNOWN"
        existing_tests = []
        suggested_scenarios = []
        coverage_files = []
        current_pr_status = None
        confidence = "LOW"
        reason_parts = []

        # 1. Search mappings for matching existing tests
        test_mappings = existing_test_mappings or []
        scenario_title_lower = scenario.title.lower()

        matched_mappings = []
        for m in test_mappings:
            test_name = m.get("test_name", "").lower()
            # Direct/Heuristic mapping based on token match between test name and scenario title
            if any(token in test_name for token in scenario_title_lower.split() if len(token) > 3):
                matched_mappings.append(m)

        if matched_mappings:
            for m in matched_mappings:
                existing_tests.append({
                    "test_name": m["test_name"],
                    "confidence": m.get("confidence", "MODERATE"),
                    "source": m.get("source", "STATIC_TRACE"),
                })
                coverage_files.extend(m.get("coverage_files", []))
            coverage_files = list(set(coverage_files))

        # 2. Check if verified on current PR
        pr_test_runs = current_pr_test_runs or []
        matched_pr_runs = []
        for run in pr_test_runs:
            run_name = run.get("test_name", "").lower()
            if any(token in run_name for token in scenario_title_lower.split() if len(token) > 3):
                matched_pr_runs.append(run)

        if matched_pr_runs:
            # Map the execution status (prefer passed > failed > skipped)
            statuses = [r["status"] for r in matched_pr_runs]
            if "passed" in statuses:
                current_pr_status = "passed"
            elif "failed" in statuses:
                current_pr_status = "failed"
            else:
                current_pr_status = "skipped"

        # 3. Handle File Coverage Support for Confidence
        file_cov_p_list = []
        if file_coverage_data and coverage_files:
            for f in coverage_files:
                if f in file_coverage_data:
                    file_cov_p_list.append(file_coverage_data[f])

        avg_file_cov = sum(file_cov_p_list) / len(file_cov_p_list) if file_cov_p_list else 0.0

        # 4. Resolve exact coverage status based on rules
        if current_pr_status == "passed":
            coverage_status = "VERIFIED_ON_CURRENT_PR"
            confidence = "HIGH"
            reason_parts.append("Scenario successfully executed and verified on current Pull Request execution run")
        elif existing_tests:
            # Historically covered
            coverage_status = "COVERED_BY_EXISTING_TEST"
            confidence = "HIGH" if avg_file_cov >= 80.0 else "MODERATE"
            reason_parts.append(f"Covered historically by {len(existing_tests)} existing test cases")
            if avg_file_cov > 0:
                reason_parts.append(f"Supporting file coverage is {avg_file_cov:.1f}%")
        elif avg_file_cov >= 50.0:
            coverage_status = "PARTIALLY_COVERE" # Suffix truncated to fit PARTIALLY_COVERED, let's keep exact spec: PARTIALLY_COVERED
            coverage_status = "PARTIALLY_COVERED"
            confidence = "MODERATE"
            reason_parts.append("Supporting source files are partially covered, but no explicit matching test case has been traced")
        elif scenario.priority in ["BLOCKER", "MUST"] or behavior.risk_level in ["CRITICAL", "HIGH"]:
            coverage_status = "MANUAL_VALIDATION_RECOMMENDED"
            confidence = "MODERATE"
            reason_parts.append("High-priority scenario with no automated test mapping; manual checkout recommended")
            suggested_scenarios.append({
                "title": f"Manual Validation: {scenario.title}",
                "priority": scenario.priority,
                "preconditions": ["System deployed to isolated staging"],
                "steps": ["Validate workflow against expected outcome manually"],
                "expected_result": "Scenario validated and recorded successfully.",
            })
        else:
            coverage_status = "MISSING_AUTOMATED_COVERAGE"
            confidence = "LOW"
            reason_parts.append("No mapped automated tests or trace evidence detected for this scenario")
            suggested_scenarios.append({
                "title": f"Automate: {scenario.title}",
                "priority": scenario.priority,
                "preconditions": ["Staging environment active"],
                "steps": ["Create automated test asserting expected validation boundaries"],
                "expected_result": "Automated test runs and covers behavior.",
            })

        # Return scenario coverage record
        coverage = BehaviorScenarioCoverage(
            id=uuid.uuid4(),
            repository_id=repository_id,
            behavior_id=behavior.id,
            behavior_scenario_id=scenario.id,
            recommendation_run_id=recommendation_run_id,
            coverage_status=coverage_status,
            current_pr_execution_status=current_pr_status,
            confidence=confidence,
            reason=" / ".join(reason_parts),
            existing_tests=existing_tests,
            suggested_scenarios=suggested_scenarios,
            coverage_files=coverage_files,
        )

        if self.db:
            self.db.add(coverage)
            self.db.commit()

        return coverage
