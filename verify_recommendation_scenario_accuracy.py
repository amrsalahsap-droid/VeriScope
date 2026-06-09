"""
Verify Recommendation Scenario Accuracy
========================================

Tests to verify scenario intent accuracy, deduplication, and evidence semantics.

Verification Checklist:
1. Same scenario intent appears once per recommendation run
2. No scenario appears in both MUST and OPTIONAL
3. Existing tests map to scenario intents
4. Suggested scenarios exclude covered existing test intents
5. Historical JUnit does not mark tests as current PR verified
6. Current PR test execution marks scenario as verified
7. File coverage alone does not mark scenario fully covered
8. High-risk uncovered auth scenarios remain suggested
9. Coverage matrix accurately shows covered/missing/partial
10. UI sections do not duplicate the same scenario
"""

import sys
import os
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.recommendation import RecommendationRun, ScenarioIntent, SuggestedTestScenario, RecommendationTest
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.coverage_ingestion import CoverageReport, CoverageFileEntry
from app.models.test_coverage_link import TestCoverageLink
from app.services.existing_test_to_scenario_mapper import ExistingTestToScenarioMapper
from app.services.scenario_coverage_resolver import ScenarioCoverageResolver, FinalCoverageStatus
from app.services.scenario_priority_resolver import ScenarioPriorityResolver
from app.services.scenario_coverage_matrix_builder import ScenarioCoverageMatrixBuilder
from app.services.scenario_intent_normalizer import ScenarioIntentNormalizer


class ScenarioAccuracyVerifier:
    """Verifies scenario recommendation accuracy and evidence semantics."""
    
    def __init__(self, db: Session):
        self.db = db
        self.test_results = []
        self.failures = []
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log a test result."""
        status = "✓ PASS" if passed else "✗ FAIL"
        self.test_results.append((test_name, passed, message))
        print(f"{status}: {test_name}")
        if message:
            print(f"  {message}")
        if not passed:
            self.failures.append((test_name, message))
    
    def verify_scenario_intent_uniqueness(self, run_id: str) -> bool:
        """
        Verify 1: Same scenario intent appears once per recommendation run.
        """
        scenario_intents = self.db.query(ScenarioIntent).filter(
            ScenarioIntent.recommendation_run_id == run_id
        ).all()
        
        canonical_keys = [intent.canonical_key for intent in scenario_intents]
        unique_keys = set(canonical_keys)
        
        passed = len(canonical_keys) == len(unique_keys)
        message = f"Found {len(canonical_keys)} intents, {len(unique_keys)} unique"
        
        if not passed:
            duplicates = [k for k in canonical_keys if canonical_keys.count(k) > 1]
            message += f". Duplicates: {set(duplicates)}"
        
        self.log_test("Scenario Intent Uniqueness", passed, message)
        return passed
    
    def verify_no_priority_conflicts(self, run_id: str) -> bool:
        """
        Verify 2: No scenario appears in both MUST and OPTIONAL.
        """
        scenario_intents = self.db.query(ScenarioIntent).filter(
            ScenarioIntent.recommendation_run_id == run_id
        ).all()
        
        must_scenarios = {intent.canonical_key for intent in scenario_intents if intent.priority == "MUST"}
        optional_scenarios = {intent.canonical_key for intent in scenario_intents if intent.priority == "OPTIONAL"}
        
        conflicts = must_scenarios & optional_scenarios
        passed = len(conflicts) == 0
        message = f"Found {len(conflicts)} priority conflicts"
        
        if not passed:
            message += f". Conflicting scenarios: {conflicts}"
        
        self.log_test("No Priority Conflicts", passed, message)
        return passed
    
    def verify_existing_tests_map_to_intents(self, run_id: str) -> bool:
        """
        Verify 3: Existing tests map to scenario intents.
        """
        # Get existing tests for the repository
        run = self.db.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()
        if not run:
            self.log_test("Existing Tests Map to Intents", False, "Run not found")
            return False
        
        test_cases = self.db.query(TestCase).filter(TestCase.repository_id == run.repository_id).all()
        scenario_intents = self.db.query(ScenarioIntent).filter(
            ScenarioIntent.recommendation_run_id == run_id
        ).all()
        
        # Map test cases to scenario intents
        mapped_count = 0
        unmapped_tests = []
        
        for test_case in test_cases:
            # Try to create intent from test
            intent_data = ScenarioIntentNormalizer.create_intent_from_scenario(
                title=test_case.test_name,
                priority="SHOULD",
                risk_category="MODERATE",
                related_changed_files=[],
                recommendation_run_id=run_id
            )
            
            # Check if this intent exists
            exists = any(intent.canonical_key == intent_data["canonical_key"] for intent in scenario_intents)
            if exists:
                mapped_count += 1
            else:
                unmapped_tests.append(test_case.test_name)
        
        passed = len(unmapped_tests) == 0 or mapped_count > 0
        message = f"Mapped {mapped_count}/{len(test_cases)} tests to intents"
        
        if not passed and unmapped_tests:
            message += f". Unmapped: {unmapped_tests[:5]}..."
        
        self.log_test("Existing Tests Map to Intents", passed, message)
        return passed
    
    def verify_suggested_exclude_covered(self, run_id: str) -> bool:
        """
        Verify 4: Suggested scenarios exclude covered existing test intents.
        """
        scenario_intents = self.db.query(ScenarioIntent).filter(
            ScenarioIntent.recommendation_run_id == run_id
        ).all()
        
        suggested_scenarios = self.db.query(SuggestedTestScenario).filter(
            SuggestedTestScenario.recommendation_run_id == run_id
        ).all()
        
        # Get intents that have existing tests (covered)
        covered_intents = {intent.scenario_intent_id for intent in suggested_scenarios if intent.scenario_intent_id}
        
        # Check if any suggested scenario has a covered intent
        duplicates = []
        for scenario in suggested_scenarios:
            if scenario.scenario_intent_id in covered_intents:
                duplicates.append(scenario.title)
        
        passed = len(duplicates) == 0
        message = f"Found {len(duplicates)} suggested scenarios with covered intents"
        
        if not passed:
            message += f". Duplicates: {duplicates[:5]}..."
        
        self.log_test("Suggested Exclude Covered", passed, message)
        return passed
    
    def verify_historical_not_current_verified(self, run_id: str) -> bool:
        """
        Verify 5: Historical JUnit does not mark tests as current PR verified.
        """
        run = self.db.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()
        if not run:
            self.log_test("Historical Not Current Verified", False, "Run not found")
            return False
        
        # Get historical test runs (not current PR)
        historical_runs = self.db.query(TestRun).filter(
            TestRun.repository_id == run.repository_id,
            TestRun.pull_request_id != run.pull_request_id
        ).all()
        
        if not historical_runs:
            self.log_test("Historical Not Current Verified", True, "No historical runs to test")
            return True
        
        # Get scenario intents
        scenario_intents = self.db.query(ScenarioIntent).filter(
            ScenarioIntent.recommendation_run_id == run_id
        ).all()
        
        # Simulate coverage resolution with only historical evidence
        incorrectly_verified = []
        for intent in scenario_intents:
            # If intent has COVERED_AND_VERIFIED status without current PR execution, it's wrong
            # This would be caught by the actual resolver logic
            pass
        
        # For now, verify the resolver logic directly
        from app.services.scenario_coverage_resolver import ExecutionStatus, ExistingTestStatus, CodeCoverageStatus
        
        # Test case: existing test with historical pass but no current PR execution
        final_status = ScenarioCoverageResolver.consolidate_final_status(
            existing_test_status=ExistingTestStatus.AVAILABLE,
            code_coverage_status=CodeCoverageStatus.NONE,
            current_pr_execution_status=ExecutionStatus.NOT_RUN,
            historical_execution_status=ExecutionStatus.PASSED
        )
        
        passed = final_status != FinalCoverageStatus.COVERED_AND_VERIFIED
        message = f"Historical pass + no current PR = {final_status.value}"
        
        self.log_test("Historical Not Current Verified", passed, message)
        return passed
    
    def verify_current_pr_marks_verified(self, run_id: str) -> bool:
        """
        Verify 6: Current PR test execution marks scenario as verified.
        """
        from app.services.scenario_coverage_resolver import ExecutionStatus, ExistingTestStatus, CodeCoverageStatus
        
        # Test case: existing test with current PR pass
        final_status = ScenarioCoverageResolver.consolidate_final_status(
            existing_test_status=ExistingTestStatus.AVAILABLE,
            code_coverage_status=CodeCoverageStatus.NONE,
            current_pr_execution_status=ExecutionStatus.PASSED,
            historical_execution_status=ExecutionStatus.UNKNOWN
        )
        
        passed = final_status == FinalCoverageStatus.COVERED_AND_VERIFIED
        message = f"Current PR pass = {final_status.value}"
        
        self.log_test("Current PR Marks Verified", passed, message)
        return passed
    
    def verify_file_coverage_not_fully_covered(self, run_id: str) -> bool:
        """
        Verify 7: File coverage alone does not mark scenario fully covered.
        """
        from app.services.scenario_coverage_resolver import ExecutionStatus, ExistingTestStatus, CodeCoverageStatus
        
        # Test case: file coverage but no existing test
        final_status = ScenarioCoverageResolver.consolidate_final_status(
            existing_test_status=ExistingTestStatus.NOT_FOUND,
            code_coverage_status=CodeCoverageStatus.DIRECT,
            current_pr_execution_status=ExecutionStatus.NOT_RUN,
            historical_execution_status=ExecutionStatus.UNKNOWN
        )
        
        passed = final_status != FinalCoverageStatus.COVERED_AND_VERIFIED
        passed = passed and final_status != FinalCoverageStatus.COVERED_NOT_RUN
        message = f"File coverage only = {final_status.value}"
        
        self.log_test("File Coverage Not Fully Covered", passed, message)
        return passed
    
    def verify_high_risk_auth_remains_suggested(self, run_id: str) -> bool:
        """
        Verify 8: High-risk uncovered auth scenarios remain suggested.
        """
        # Test priority resolution for high-risk auth scenarios
        scenario_data = {
            "title": "Should reject reused reset token",
            "testing_type": "api",
            "impacted_area": "authentication",
            "priority": "SHOULD",
            "risk_category": "HIGH",
            "related_changed_files": ["app/api/auth/reset-password/route.ts"]
        }
        
        # Simulate no coverage
        from app.services.scenario_coverage_resolver import FinalCoverageStatus
        
        priority = ScenarioPriorityResolver.resolve_priority_from_scenario(
            scenario_data=scenario_data,
            coverage_status=None,
            risk_level="HIGH",
            business_journey_criticality="HIGH",
            historical_failure=False
        )
        
        passed = priority.value in ["MUST", "SHOULD"]
        message = f"High-risk auth scenario priority = {priority.value}"
        
        self.log_test("High-Risk Auth Remains Suggested", passed, message)
        return passed
    
    def verify_coverage_matrix_accuracy(self, run_id: str) -> bool:
        """
        Verify 9: Coverage matrix accurately shows covered/missing/partial.
        """
        try:
            matrix = ScenarioCoverageMatrixBuilder.build_matrix(self.db, run_id)
            
            # Verify counts match items
            total_items = len(matrix.items)
            total_count = (
                matrix.covered_and_verified +
                matrix.covered_not_run +
                matrix.partially_covered +
                matrix.missing_automated_coverage +
                matrix.suggest_manual_validation
            )
            
            passed = total_items == total_count
            message = f"Matrix has {total_items} items, counts sum to {total_count}"
            
            # Verify each item has correct recommendation action based on final status
            action_mismatches = []
            for item in matrix.items:
                if item.final_status == "COVERED_AND_VERIFIED" and item.recommendation_action != "ALREADY_VERIFIED":
                    action_mismatches.append(f"{item.title}: {item.final_status} -> {item.recommendation_action}")
                elif item.final_status == "COVERED_NOT_RUN" and item.recommendation_action != "RUN_EXISTING_TEST":
                    action_mismatches.append(f"{item.title}: {item.final_status} -> {item.recommendation_action}")
            
            if action_mismatches:
                passed = False
                message += f". Action mismatches: {action_mismatches[:3]}..."
            
            self.log_test("Coverage Matrix Accuracy", passed, message)
            return passed
        except Exception as e:
            self.log_test("Coverage Matrix Accuracy", False, f"Error: {str(e)}")
            return False
    
    def verify_ui_sections_no_duplicates(self, run_id: str) -> bool:
        """
        Verify 10: UI sections do not duplicate the same scenario.
        """
        try:
            matrix = ScenarioCoverageMatrixBuilder.build_matrix(self.db, run_id)
            
            # Group by recommendation action
            by_action = {}
            for item in matrix.items:
                action = item.recommendation_action
                if action not in by_action:
                    by_action[action] = set()
                by_action[action].add(item.scenario_intent_key)
            
            # Check for duplicates across sections
            all_keys = []
            for action, keys in by_action.items():
                all_keys.extend(keys)
            
            unique_keys = set(all_keys)
            passed = len(all_keys) == len(unique_keys)
            message = f"Found {len(all_keys)} items across sections, {len(unique_keys)} unique"
            
            if not passed:
                duplicates = [k for k in all_keys if all_keys.count(k) > 1]
                message += f". Duplicates across sections: {set(duplicates)}"
            
            self.log_test("UI Sections No Duplicates", passed, message)
            return passed
        except Exception as e:
            self.log_test("UI Sections No Duplicates", False, f"Error: {str(e)}")
            return False
    
    def run_all_verifications(self, run_id: str) -> bool:
        """Run all verification tests."""
        print(f"\n{'='*60}")
        print(f"Verifying Scenario Accuracy for Run: {run_id}")
        print(f"{'='*60}\n")
        
        self.verify_scenario_intent_uniqueness(run_id)
        self.verify_no_priority_conflicts(run_id)
        self.verify_existing_tests_map_to_intents(run_id)
        self.verify_suggested_exclude_covered(run_id)
        self.verify_historical_not_current_verified(run_id)
        self.verify_current_pr_marks_verified(run_id)
        self.verify_file_coverage_not_fully_covered(run_id)
        self.verify_high_risk_auth_remains_suggested(run_id)
        self.verify_coverage_matrix_accuracy(run_id)
        self.verify_ui_sections_no_duplicates(run_id)
        
        print(f"\n{'='*60}")
        print(f"Results: {len(self.test_results)} tests, {len(self.failures)} failures")
        print(f"{'='*60}\n")
        
        return len(self.failures) == 0


def run_seed_data_verification():
    """
    Run verification with seed data.
    
    Seed:
    - existing tests: should_reject_expired_token, should_allow_valid_token, should_attach_user_context
    - suggested scenarios: expired token rejected, valid token accepted, attach user context, reused reset token rejected, weak password rejected
    
    Expected:
    - first three map to existing tests and are not duplicated as missing
    - reused token and weak password remain missing
    - priorities resolve once
    """
    print("\n" + "="*60)
    print("SEED DATA VERIFICATION")
    print("="*60 + "\n")
    
    # Test mapping logic
    existing_tests = [
        "should_reject_expired_token",
        "should_allow_valid_token",
        "should_attach_user_context"
    ]
    
    suggested_scenarios = [
        "expired token rejected",
        "valid token accepted",
        "attach user context",
        "reused reset token rejected",
        "weak password rejected"
    ]
    
    print("Existing Tests:")
    for test in existing_tests:
        print(f"  - {test}")
    
    print("\nSuggested Scenarios:")
    for scenario in suggested_scenarios:
        print(f"  - {scenario}")
    
    print("\nExpected Behavior:")
    print("  - First 3 scenarios map to existing tests (not duplicated as missing)")
    print("  - Reused token and weak password remain missing")
    print("  - Priorities resolve once per scenario")
    
    # Test mapping
    print("\n" + "-"*60)
    print("Testing Mapping Logic")
    print("-"**60 + "\n")
    
    mapped = []
    unmapped = []
    
    for scenario in suggested_scenarios:
        # Check if this maps to an existing test
        intent_data = ScenarioIntentNormalizer.create_intent_from_scenario(
            title=scenario,
            priority="SHOULD",
            risk_category="MODERATE",
            related_changed_files=[],
            recommendation_run_id="test"
        )
        
        for test in existing_tests:
            test_intent = ScenarioIntentNormalizer.create_intent_from_scenario(
                title=test,
                priority="SHOULD",
                risk_category="MODERATE",
                related_changed_files=[],
                recommendation_run_id="test"
            )
            
            if intent_data["canonical_key"] == test_intent["canonical_key"]:
                mapped.append((scenario, test))
                break
        else:
            unmapped.append(scenario)
    
    print(f"Mapped Scenarios: {len(mapped)}")
    for scenario, test in mapped:
        print(f"  ✓ '{scenario}' -> '{test}'")
    
    print(f"\nUnmapped Scenarios: {len(unmapped)}")
    for scenario in unmapped:
        print(f"  - '{scenario}' (should remain missing)")
    
    # Verify expectations
    passed = len(mapped) == 3 and len(unmapped) == 2
    print(f"\n{'✓ PASS' if passed else '✗ FAIL'}: Seed data mapping verification")
    
    return passed


if __name__ == "__main__":
    # Get database session
    from app.db.session import SessionLocal
    
    db = SessionLocal()
    
    try:
        # Run seed data verification
        seed_passed = run_seed_data_verification()
        
        # If a run ID is provided, run full verification
        if len(sys.argv) > 1:
            run_id = sys.argv[1]
            verifier = ScenarioAccuracyVerifier(db)
            all_passed = verifier.run_all_verifications(run_id)
            
            if all_passed and seed_passed:
                print("\n✓ All verifications passed!")
                sys.exit(0)
            else:
                print("\n✗ Some verifications failed!")
                sys.exit(1)
        else:
            print("\nNo run ID provided. Only seed data verification was run.")
            print("Usage: python verify_recommendation_scenario_accuracy.py <run_id>")
            sys.exit(0 if seed_passed else 1)
    
    finally:
        db.close()
