"""Test suite for BusinessIntentCoverageMatrixGenerator."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.business_intent_coverage_matrix_generator import BusinessIntentCoverageMatrixGenerator
from app.schemas.business_intent import BusinessIntentCoverageMatrix
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.business_behavior_mapping import BusinessBehaviorMapping
from app.models.expected_behavior_scenario import ExpectedBehaviorScenario
from app.schemas.acceptance_criteria import AcceptanceCriteriaCoverageStatus, AcceptanceCriteriaCoverageReport


def test_generate_matrix_with_business_intent(db_session: Session):
    """Test generating matrix with business intent (AC present)."""
    
    # Create journey
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    
    # Create behavior
    behavior = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=uuid4(),
        name="Password Reset",
        slug="password-reset",
        description="User can reset their password",
        risk_level="HIGH",
        is_deleted=False,
    )
    
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
        behavior_id=behavior.id,
        behavior_scenario_id=scenario_id,
        journey_id=journey.id,
        match_confidence=0.9,
        matched_terms=["password", "reset"],
        reason="Direct match",
        is_candidate_missing_scenario="false",
    )
    
    # Create AC coverage status
    ac_coverage_status = AcceptanceCriteriaCoverageStatus(
        acceptance_criterion_id=str(ac.id),
        coverage_status="COVERED_BY_EXISTING_TEST",
        existing_tests=["test_1", "test_2"],
        suggested_scenarios=[],
        current_pr_execution_status="NOT_EXECUTED",
        confidence=0.8,
        reason="Covered by existing tests"
    )
    
    ac_coverage_report = AcceptanceCriteriaCoverageReport(
        total_criteria=1,
        covered_by_existing_test=1,
        partially_covered=0,
        missing_test_coverage=0,
        verified_on_current_pr=0,
        manual_validation_required=0,
        unknown=0,
        coverage_statuses=[ac_coverage_status]
    )
    
    generator = BusinessIntentCoverageMatrixGenerator(db=db_session)
    matrix = generator.generate_matrix(
        acceptance_criteria=[ac],
        business_intent=None,
        affected_behaviors=[behavior],
        affected_journeys=[journey],
        business_behavior_mappings=[mapping],
        expected_scenarios=[],
        ac_coverage_report=ac_coverage_report,
        repository_id=None
    )
    
    assert matrix.has_business_intent == True
    assert matrix.total_intents == 1
    assert len(matrix.rows) == 1
    
    row = matrix.rows[0]
    assert row.acceptance_criterion_id == str(ac.id)
    assert row.business_intent_text == ac.text
    assert row.affected_behavior_id == str(behavior.id)
    assert row.affected_behavior_name == behavior.name
    assert row.affected_journey_id == str(journey.id)
    assert row.affected_journey_name == journey.name
    assert row.status == "COVERED"
    assert row.recommended_action == "RUN_EXISTING_TEST"
    assert len(row.existing_test_coverage) == 2
    
    print(f"✓ Matrix generated with business intent")
    print(f"  Total intents: {matrix.total_intents}")
    print(f"  Covered: {matrix.covered}")
    print(f"  Confidence impact: {matrix.confidence_impact}")


def test_generate_matrix_without_business_intent(db_session: Session):
    """Test generating matrix without business intent (AC missing)."""
    
    generator = BusinessIntentCoverageMatrixGenerator(db=db_session)
    matrix = generator.generate_matrix(
        acceptance_criteria=[],
        business_intent=None,
        affected_behaviors=[],
        affected_journeys=[],
        business_behavior_mappings=[],
        expected_scenarios=[],
        ac_coverage_report=None,
        repository_id=None
    )
    
    assert matrix.has_business_intent == False
    assert matrix.total_intents == 0
    assert len(matrix.rows) == 1
    
    row = matrix.rows[0]
    assert row.business_intent_text == "No business intent or acceptance criteria found"
    assert row.status == "UNKNOWN"
    assert row.recommended_action == "CLARIFY_REQUIREMENT"
    assert matrix.confidence_impact == "REDUCED"
    
    print(f"✓ Matrix generated without business intent")
    print(f"  Confidence impact: {matrix.confidence_impact}")


def test_generate_matrix_verified_on_current_pr(db_session: Session):
    """Test generating matrix with AC verified on current PR."""
    
    # Create journey and behavior
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    
    behavior = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=uuid4(),
        name="Password Reset",
        slug="password-reset",
        description="User can reset their password",
        risk_level="HIGH",
        is_deleted=False,
    )
    
    # Create AC
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
    
    # Create mapping
    scenario_id = uuid4()
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac.id,
        behavior_id=behavior.id,
        behavior_scenario_id=scenario_id,
        journey_id=journey.id,
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="false",
    )
    
    # Create AC coverage status (verified on current PR)
    ac_coverage_status = AcceptanceCriteriaCoverageStatus(
        acceptance_criterion_id=str(ac.id),
        coverage_status="VERIFIED_ON_CURRENT_PR",
        existing_tests=["test_1"],
        suggested_scenarios=[],
        current_pr_execution_status="EXECUTED",
        confidence=0.95,
        reason="Verified on current PR"
    )
    
    ac_coverage_report = AcceptanceCriteriaCoverageReport(
        total_criteria=1,
        covered_by_existing_test=0,
        partially_covered=0,
        missing_test_coverage=0,
        verified_on_current_pr=1,
        manual_validation_required=0,
        unknown=0,
        coverage_statuses=[ac_coverage_status]
    )
    
    generator = BusinessIntentCoverageMatrixGenerator(db=db_session)
    matrix = generator.generate_matrix(
        acceptance_criteria=[ac],
        business_intent=None,
        affected_behaviors=[behavior],
        affected_journeys=[journey],
        business_behavior_mappings=[mapping],
        expected_scenarios=[],
        ac_coverage_report=ac_coverage_report,
        repository_id=None
    )
    
    assert matrix.verified == 1
    row = matrix.rows[0]
    assert row.status == "VERIFIED"
    assert row.recommended_action == "ALREADY_VERIFIED"
    assert row.current_pr_execution_status == "EXECUTED"
    
    print(f"✓ Matrix with verified AC on current PR")
    print(f"  Status: {row.status}")
    print(f"  Action: {row.recommended_action}")


def test_generate_matrix_missing_coverage_with_suggested_scenario(db_session: Session):
    """Test generating matrix with missing coverage and suggested scenario."""
    
    # Create journey and behavior
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    
    behavior = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=uuid4(),
        name="Password Reset",
        slug="password-reset",
        description="User can reset their password",
        risk_level="HIGH",
        is_deleted=False,
    )
    
    # Create AC
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
    
    # Create mapping (candidate missing scenario)
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac.id,
        behavior_id=behavior.id,
        behavior_scenario_id=None,  # No scenario match
        journey_id=journey.id,
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="true",
    )
    
    # Create expected scenario
    expected_scenario = ExpectedBehaviorScenario(
        id=uuid4(),
        title="Test password reset",
        behavior_id=behavior.id,
        journey_id=journey.id,
        acceptance_criterion_id=ac.id,
        priority="MUST",
        testing_type="AUTOMATED",
        scenario_type="FUNCTIONAL",
        preconditions=[],
        test_data=None,
        steps=["Perform reset", "Verify success"],
        expected_result="Password reset succeeds",
        source="ACCEPTANCE_CRITERIA",
        confidence=0.9,
        matches_existing_test="false",
        recommendation_run_id=None,
    )
    
    # Create AC coverage status (missing)
    ac_coverage_status = AcceptanceCriteriaCoverageStatus(
        acceptance_criterion_id=str(ac.id),
        coverage_status="MISSING_TEST_COVERAGE",
        existing_tests=[],
        suggested_scenarios=[str(expected_scenario.id)],
        current_pr_execution_status="NOT_EXECUTED",
        confidence=0.7,
        reason="No test coverage found"
    )
    
    ac_coverage_report = AcceptanceCriteriaCoverageReport(
        total_criteria=1,
        covered_by_existing_test=0,
        partially_covered=0,
        missing_test_coverage=1,
        verified_on_current_pr=0,
        manual_validation_required=0,
        unknown=0,
        coverage_statuses=[ac_coverage_status]
    )
    
    generator = BusinessIntentCoverageMatrixGenerator(db=db_session)
    matrix = generator.generate_matrix(
        acceptance_criteria=[ac],
        business_intent=None,
        affected_behaviors=[behavior],
        affected_journeys=[journey],
        business_behavior_mappings=[mapping],
        expected_scenarios=[expected_scenario],
        ac_coverage_report=ac_coverage_report,
        repository_id=None
    )
    
    assert matrix.missing == 1
    row = matrix.rows[0]
    assert row.status == "MISSING"
    assert row.recommended_action == "ADD_AUTOMATED_TEST"
    assert row.suggested_scenario_id == str(expected_scenario.id)
    assert row.suggested_scenario_title == expected_scenario.title
    
    print(f"✓ Matrix with missing coverage and suggested scenario")
    print(f"  Suggested scenario: {row.suggested_scenario_title}")


def test_generate_matrix_multiple_ac(db_session: Session):
    """Test generating matrix with multiple ACs."""
    
    # Create journey and behavior
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    
    behavior = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=uuid4(),
        name="Password Reset",
        slug="password-reset",
        description="User can reset their password",
        risk_level="HIGH",
        is_deleted=False,
    )
    
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
    
    # Create mappings
    scenario_id1 = uuid4()
    mapping1 = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac1.id,
        behavior_id=behavior.id,
        behavior_scenario_id=scenario_id1,
        journey_id=journey.id,
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="false",
    )
    
    scenario_id2 = uuid4()
    mapping2 = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac2.id,
        behavior_id=behavior.id,
        behavior_scenario_id=scenario_id2,
        journey_id=journey.id,
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="false",
    )
    
    # AC3 has no mapping (missing)
    
    # Create AC coverage statuses
    ac_coverage_status1 = AcceptanceCriteriaCoverageStatus(
        acceptance_criterion_id=str(ac1.id),
        coverage_status="COVERED_BY_EXISTING_TEST",
        existing_tests=["test_1"],
        suggested_scenarios=[],
        current_pr_execution_status="NOT_EXECUTED",
        confidence=0.8,
        reason="Covered by existing tests"
    )
    
    ac_coverage_status2 = AcceptanceCriteriaCoverageStatus(
        acceptance_criterion_id=str(ac2.id),
        coverage_status="PARTIALLY_COVERED",
        existing_tests=[],
        suggested_scenarios=[],
        current_pr_execution_status="NOT_EXECUTED",
        confidence=0.6,
        reason="Partial coverage"
    )
    
    ac_coverage_status3 = AcceptanceCriteriaCoverageStatus(
        acceptance_criterion_id=str(ac3.id),
        coverage_status="MISSING_TEST_COVERAGE",
        existing_tests=[],
        suggested_scenarios=[],
        current_pr_execution_status="NOT_EXECUTED",
        confidence=0.5,
        reason="No coverage"
    )
    
    ac_coverage_report = AcceptanceCriteriaCoverageReport(
        total_criteria=3,
        covered_by_existing_test=1,
        partially_covered=1,
        missing_test_coverage=1,
        verified_on_current_pr=0,
        manual_validation_required=0,
        unknown=0,
        coverage_statuses=[ac_coverage_status1, ac_coverage_status2, ac_coverage_status3]
    )
    
    generator = BusinessIntentCoverageMatrixGenerator(db=db_session)
    matrix = generator.generate_matrix(
        acceptance_criteria=[ac1, ac2, ac3],
        business_intent=None,
        affected_behaviors=[behavior],
        affected_journeys=[journey],
        business_behavior_mappings=[mapping1, mapping2],
        expected_scenarios=[],
        ac_coverage_report=ac_coverage_report,
        repository_id=None
    )
    
    assert matrix.total_intents == 3
    assert matrix.covered == 1
    assert matrix.partially_covered == 1
    assert matrix.missing == 1
    
    print(f"✓ Matrix with multiple ACs")
    print(f"  Total: {matrix.total_intents}, Covered: {matrix.covered}, Partial: {matrix.partially_covered}, Missing: {matrix.missing}")


def test_confidence_impact_calculation(db_session: Session):
    """Test confidence impact calculation based on coverage."""
    
    # High coverage (>= 80%)
    generator = BusinessIntentCoverageMatrixGenerator(db=db_session)
    
    # Test high coverage
    assert generator._determine_confidence_impact(5, 4, 0, 1, 0) == "NONE"
    
    # Medium coverage (>= 50%)
    assert generator._determine_confidence_impact(5, 2, 1, 2, 0) == "REDUCED"
    
    # Low coverage (< 50%)
    assert generator._determine_confidence_impact(5, 1, 0, 4, 0) == "SIGNIFICANTLY_REDUCED"
    
    # No coverage
    assert generator._determine_confidence_impact(0, 0, 0, 0, 0) == "SIGNIFICANTLY_REDUCED"
    
    print(f"✓ Confidence impact calculation works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
