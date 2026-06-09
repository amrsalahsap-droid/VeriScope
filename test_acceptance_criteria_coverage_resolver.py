"""Test suite for AcceptanceCriteriaCoverageResolver."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.acceptance_criteria_coverage_resolver import AcceptanceCriteriaCoverageResolver
from app.schemas.acceptance_criteria import AcceptanceCriteriaCoverageStatus
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.test_result import TestCase, TestResult
from app.models.behavior_scenario_coverage import BehaviorScenarioCoverage
from app.models.recommendation import SuggestedTestScenario
from app.models.test_coverage_link import TestCoverageLink
from app.models.business_behavior_mapping import BusinessBehaviorMapping


def test_resolve_ac_covered_by_existing_test(db_session: Session):
    """Test AC covered by existing test (not executed on current PR)."""
    
    # Create acceptance criterion
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User must be able to reset password",
        normalized_key="user must be able to reset password",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User must be able to reset password",
    )
    
    # Create business behavior mapping
    scenario_id = uuid4()
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac.id,
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id,
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password", "reset"],
        reason="Direct match",
        is_candidate_missing_scenario="false",
    )
    
    # Create scenario coverage with existing tests
    test_id = uuid4()
    scenario_coverage = BehaviorScenarioCoverage(
        id=uuid4(),
        repository_id=uuid4(),
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id,
        recommendation_run_id=uuid4(),
        coverage_status="COVERED_BY_EXISTING_TEST",
        current_pr_execution_status="NOT_EXECUTED",
        confidence="HIGH",
        reason="Test exists",
        existing_tests={"test_ids": [str(test_id)]},
        suggested_scenarios=[],
        coverage_files=[],
    )
    
    resolver = AcceptanceCriteriaCoverageResolver(db=db_session)
    report = resolver.resolve_coverage(
        acceptance_criteria=[ac],
        existing_tests=[],
        behavior_scenario_coverages=[scenario_coverage],
        suggested_scenarios=[],
        test_coverage_links=[],
        business_behavior_mappings=[mapping],
        current_pr_test_runs=None,
        repository_id=None
    )
    
    assert len(report.coverage_statuses) == 1
    status = report.coverage_statuses[0]
    assert status.coverage_status == "COVERED_BY_EXISTING_TEST"
    assert status.current_pr_execution_status == "NOT_EXECUTED"
    assert str(test_id) in status.existing_tests
    assert status.confidence >= 0.7
    
    print(f"✓ AC covered by existing test: {status.coverage_status}")
    print(f"  Reason: {status.reason}")


def test_resolve_ac_verified_on_current_pr(db_session: Session):
    """Test AC verified on current PR (test executed)."""
    
    # Create acceptance criterion
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User must be able to reset password",
        normalized_key="user must be able to reset password",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User must be able to reset password",
    )
    
    # Create business behavior mapping
    scenario_id = uuid4()
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac.id,
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id,
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password", "reset"],
        reason="Direct match",
        is_candidate_missing_scenario="false",
    )
    
    # Create scenario coverage with existing tests
    test_id = uuid4()
    scenario_coverage = BehaviorScenarioCoverage(
        id=uuid4(),
        repository_id=uuid4(),
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id,
        recommendation_run_id=uuid4(),
        coverage_status="COVERED_BY_EXISTING_TEST",
        current_pr_execution_status="NOT_EXECUTED",
        confidence="HIGH",
        reason="Test exists",
        existing_tests={"test_ids": [str(test_id)]},
        suggested_scenarios=[],
        coverage_files=[],
    )
    
    # Create current PR test run (test passed)
    test_run = TestResult(
        id=uuid4(),
        test_case_id=test_id,
        test_run_id=uuid4(),
        status="passed",
        duration=1.5,
    )
    
    resolver = AcceptanceCriteriaCoverageResolver(db=db_session)
    report = resolver.resolve_coverage(
        acceptance_criteria=[ac],
        existing_tests=[],
        behavior_scenario_coverages=[scenario_coverage],
        suggested_scenarios=[],
        test_coverage_links=[],
        business_behavior_mappings=[mapping],
        current_pr_test_runs=[test_run],
        repository_id=None
    )
    
    assert len(report.coverage_statuses) == 1
    status = report.coverage_statuses[0]
    assert status.coverage_status == "VERIFIED_ON_CURRENT_PR"
    assert status.current_pr_execution_status == "EXECUTED"
    assert status.confidence >= 0.8
    
    print(f"✓ AC verified on current PR: {status.coverage_status}")
    print(f"  Reason: {status.reason}")


def test_resolve_ac_partially_covered(db_session: Session):
    """Test AC with partial coverage (scenario match but no direct test)."""
    
    # Create acceptance criterion
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User must be able to reset password",
        normalized_key="user must be able to reset password",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User must be able to reset password",
    )
    
    # Create business behavior mapping
    scenario_id = uuid4()
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac.id,
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id,
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password", "reset"],
        reason="Direct match",
        is_candidate_missing_scenario="false",
    )
    
    # Create scenario coverage with partial coverage
    scenario_coverage = BehaviorScenarioCoverage(
        id=uuid4(),
        repository_id=uuid4(),
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id,
        recommendation_run_id=uuid4(),
        coverage_status="PARTIALLY_COVERED",
        current_pr_execution_status="NOT_EXECUTED",
        confidence="MODERATE",
        reason="Partial coverage from file coverage",
        existing_tests={"test_ids": []},
        suggested_scenarios=[],
        coverage_files=[],
    )
    
    resolver = AcceptanceCriteriaCoverageResolver(db=db_session)
    report = resolver.resolve_coverage(
        acceptance_criteria=[ac],
        existing_tests=[],
        behavior_scenario_coverages=[scenario_coverage],
        suggested_scenarios=[],
        test_coverage_links=[],
        business_behavior_mappings=[mapping],
        current_pr_test_runs=None,
        repository_id=None
    )
    
    assert len(report.coverage_statuses) == 1
    status = report.coverage_statuses[0]
    assert status.coverage_status == "PARTIALLY_COVERED"
    assert status.confidence >= 0.5
    
    print(f"✓ AC partially covered: {status.coverage_status}")
    print(f"  Reason: {status.reason}")


def test_resolve_ac_missing_test_coverage(db_session: Session):
    """Test AC with no test coverage."""
    
    # Create acceptance criterion
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User must be able to reset password",
        normalized_key="user must be able to reset password",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User must be able to reset password",
    )
    
    # No business behavior mapping (no scenario match)
    
    resolver = AcceptanceCriteriaCoverageResolver(db=db_session)
    report = resolver.resolve_coverage(
        acceptance_criteria=[ac],
        existing_tests=[],
        behavior_scenario_coverages=[],
        suggested_scenarios=[],
        test_coverage_links=[],
        business_behavior_mappings=[],
        current_pr_test_runs=None,
        repository_id=None
    )
    
    assert len(report.coverage_statuses) == 1
    status = report.coverage_statuses[0]
    assert status.coverage_status == "MISSING_TEST_COVERAGE"
    assert len(status.existing_tests) == 0
    assert len(status.suggested_scenarios) == 0
    
    print(f"✓ AC missing test coverage: {status.coverage_status}")
    print(f"  Reason: {status.reason}")


def test_resolve_ac_with_suggested_scenarios(db_session: Session):
    """Test AC with suggested scenarios available."""
    
    # Create acceptance criterion
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User must be able to reset password",
        normalized_key="user must be able to reset password",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User must be able to reset password",
    )
    
    # No business behavior mapping
    
    # Create suggested scenario
    suggested_scenario = SuggestedTestScenario(
        id=uuid4(),
        recommendation_run_id=uuid4(),
        title="Test password reset",
        description="Test password reset functionality",
        priority="MUST",
        test_data={},
        acceptance_criterion_id=ac.id,
    )
    
    resolver = AcceptanceCriteriaCoverageResolver(db=db_session)
    report = resolver.resolve_coverage(
        acceptance_criteria=[ac],
        existing_tests=[],
        behavior_scenario_coverages=[],
        suggested_scenarios=[suggested_scenario],
        test_coverage_links=[],
        business_behavior_mappings=[],
        current_pr_test_runs=None,
        repository_id=None
    )
    
    assert len(report.coverage_statuses) == 1
    status = report.coverage_statuses[0]
    assert status.coverage_status == "MISSING_TEST_COVERAGE"
    assert len(status.suggested_scenarios) == 1
    assert str(suggested_scenario.id) in status.suggested_scenarios
    
    print(f"✓ AC with suggested scenarios: {status.coverage_status}")
    print(f"  Suggested scenarios: {len(status.suggested_scenarios)}")


def test_resolve_multiple_ac(db_session: Session):
    """Test resolving multiple acceptance criteria."""
    
    # Create multiple ACs
    ac1 = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User must be able to reset password",
        normalized_key="user must be able to reset password",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User must be able to reset password",
    )
    
    ac2 = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="Weak passwords should be rejected",
        normalized_key="weak passwords should be rejected",
        criterion_type="VALIDATION",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- Weak passwords should be rejected",
    )
    
    ac3 = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="It would be nice to show password strength",
        normalized_key="it would be nice to show password strength",
        criterion_type="UI",
        source="PR_DESCRIPTION",
        confidence=0.6,
        evidence_excerpt="- It would be nice to show password strength",
    )
    
    # Create mappings and coverage for AC1 (covered)
    scenario_id1 = uuid4()
    mapping1 = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac1.id,
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id1,
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="false",
    )
    
    test_id1 = uuid4()
    scenario_coverage1 = BehaviorScenarioCoverage(
        id=uuid4(),
        repository_id=uuid4(),
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id1,
        recommendation_run_id=uuid4(),
        coverage_status="COVERED_BY_EXISTING_TEST",
        current_pr_execution_status="NOT_EXECUTED",
        confidence="HIGH",
        reason="Test exists",
        existing_tests={"test_ids": [str(test_id1)]},
        suggested_scenarios=[],
        coverage_files=[],
    )
    
    # AC2 and AC3 have no coverage
    
    resolver = AcceptanceCriteriaCoverageResolver(db=db_session)
    report = resolver.resolve_coverage(
        acceptance_criteria=[ac1, ac2, ac3],
        existing_tests=[],
        behavior_scenario_coverages=[scenario_coverage1],
        suggested_scenarios=[],
        test_coverage_links=[],
        business_behavior_mappings=[mapping1],
        current_pr_test_runs=None,
        repository_id=None
    )
    
    assert report.total_criteria == 3
    assert report.covered_by_existing_test == 1
    assert report.missing_test_coverage == 2
    assert len(report.coverage_statuses) == 3
    
    print(f"✓ Resolved {report.total_criteria} ACs")
    print(f"  Covered: {report.covered_by_existing_test}")
    print(f"  Missing: {report.missing_test_coverage}")


def test_historical_junit_not_verified_on_current_pr(db_session: Session):
    """Test that historical JUnit does not equal verified on current PR."""
    
    # Create acceptance criterion
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User must be able to reset password",
        normalized_key="user must be able to reset password",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User must be able to reset password",
    )
    
    # Create business behavior mapping
    scenario_id = uuid4()
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac.id,
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id,
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="false",
    )
    
    # Create scenario coverage with existing tests (historical JUnit)
    test_id = uuid4()
    scenario_coverage = BehaviorScenarioCoverage(
        id=uuid4(),
        repository_id=uuid4(),
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id,
        recommendation_run_id=uuid4(),
        coverage_status="COVERED_BY_EXISTING_TEST",
        current_pr_execution_status="NOT_EXECUTED",
        confidence="HIGH",
        reason="Historical JUnit exists",
        existing_tests={"test_ids": [str(test_id)]},
        suggested_scenarios=[],
        coverage_files=[],
    )
    
    # No current PR test runs (test not executed on current PR)
    
    resolver = AcceptanceCriteriaCoverageResolver(db=db_session)
    report = resolver.resolve_coverage(
        acceptance_criteria=[ac],
        existing_tests=[],
        behavior_scenario_coverages=[scenario_coverage],
        suggested_scenarios=[],
        test_coverage_links=[],
        business_behavior_mappings=[mapping],
        current_pr_test_runs=None,  # No current PR runs
        repository_id=None
    )
    
    assert len(report.coverage_statuses) == 1
    status = report.coverage_statuses[0]
    assert status.coverage_status == "COVERED_BY_EXISTING_TEST"
    assert status.coverage_status != "VERIFIED_ON_CURRENT_PR"
    assert status.current_pr_execution_status == "NOT_EXECUTED"
    
    print(f"✓ Historical JUnit ≠ verified on current PR")
    print(f"  Status: {status.coverage_status} (not VERIFIED_ON_CURRENT_PR)")


def test_code_coverage_alone_does_not_prove_ac_coverage(db_session: Session):
    """Test that code coverage alone does not prove AC coverage."""
    
    # Create acceptance criterion
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User must be able to reset password",
        normalized_key="user must be able to reset password",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User must be able to reset password",
    )
    
    # Create business behavior mapping
    scenario_id = uuid4()
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac.id,
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id,
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="false",
    )
    
    # Create scenario coverage with only file coverage (no test mappings)
    scenario_coverage = BehaviorScenarioCoverage(
        id=uuid4(),
        repository_id=uuid4(),
        behavior_id=uuid4(),
        behavior_scenario_id=scenario_id,
        recommendation_run_id=uuid4(),
        coverage_status="PARTIALLY_COVERED",
        current_pr_execution_status="NOT_EXECUTED",
        confidence="MODERATE",
        reason="File coverage only",
        existing_tests={"test_ids": []},  # No test mappings
        suggested_scenarios=[],
        coverage_files=[],
    )
    
    resolver = AcceptanceCriteriaCoverageResolver(db=db_session)
    report = resolver.resolve_coverage(
        acceptance_criteria=[ac],
        existing_tests=[],
        behavior_scenario_coverages=[scenario_coverage],
        suggested_scenarios=[],
        test_coverage_links=[],
        business_behavior_mappings=[mapping],
        current_pr_test_runs=None,
        repository_id=None
    )
    
    assert len(report.coverage_statuses) == 1
    status = report.coverage_statuses[0]
    assert status.coverage_status == "PARTIALLY_COVERED"
    assert status.coverage_status != "COVERED_BY_EXISTING_TEST"
    assert len(status.existing_tests) == 0
    
    print(f"✓ Code coverage alone does not prove AC coverage")
    print(f"  Status: {status.coverage_status} (not COVERED_BY_EXISTING_TEST)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
