"""Test suite for RequirementGapDetector."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.requirement_gap_detector import RequirementGapDetector
from app.schemas.requirement_gap import RequirementGap
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.behavior import Behavior
from app.models.business_behavior_mapping import BusinessBehaviorMapping
from app.schemas.acceptance_criteria import AcceptanceCriteriaCoverageStatus, AcceptanceCriteriaCoverageReport


def test_detect_empty_pr_description(db_session: Session):
    """Test detection of empty PR description."""
    
    detector = RequirementGapDetector(db=db_session)
    report = detector.detect_gaps(
        pr_description="",
        acceptance_criteria=[],
        affected_behaviors=[],
        business_behavior_mappings=[],
        ac_coverage_report=None,
        changed_files=None
    )
    
    assert report.total_gaps == 1
    assert report.critical_gaps == 1
    assert report.has_critical_gaps == True
    assert report.overall_trust_level == "VERY_LOW"
    
    gap = report.gaps[0]
    assert gap.gap_type == "MISSING_PR_DESCRIPTION"
    assert gap.severity == "CRITICAL"
    
    print(f"✓ Detected empty PR description")
    print(f"  Trust level: {report.overall_trust_level}")


def test_detect_missing_acceptance_criteria(db_session: Session):
    """Test detection of missing acceptance criteria."""
    
    detector = RequirementGapDetector(db=db_session)
    report = detector.detect_gaps(
        pr_description="This PR updates authentication",
        acceptance_criteria=[],
        affected_behaviors=[],
        business_behavior_mappings=[],
        ac_coverage_report=None,
        changed_files=None
    )
    
    assert report.total_gaps == 1
    assert report.high_gaps == 1
    
    gap = report.gaps[0]
    assert gap.gap_type == "MISSING_ACCEPTANCE_CRITERIA"
    assert gap.severity == "HIGH"
    
    print(f"✓ Detected missing acceptance criteria")


def test_detect_vague_requirement(db_session: Session):
    """Test detection of vague requirements."""
    
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="Maybe we could consider adding a feature",
        normalized_key="maybe we could consider adding a feature",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.3,
        evidence_excerpt="- Maybe we could consider adding a feature",
    )
    
    detector = RequirementGapDetector(db=db_session)
    report = detector.detect_gaps(
        pr_description="This PR updates authentication",
        acceptance_criteria=[ac],
        affected_behaviors=[],
        business_behavior_mappings=[],
        ac_coverage_report=None,
        changed_files=None
    )
    
    assert report.total_gaps == 1
    assert report.medium_gaps == 1
    
    gap = report.gaps[0]
    assert gap.gap_type == "VAGUE_REQUIREMENT"
    assert gap.severity == "MEDIUM"
    assert "maybe" in gap.message.lower()
    
    print(f"✓ Detected vague requirement")


def test_detect_unmapped_business_behavior(db_session: Session):
    """Test detection of unmapped business behavior."""
    
    # Create behavior
    behavior = Behavior(
        id=uuid4(),
        journey_id=uuid4(),
        repository_id=uuid4(),
        name="Password Reset",
        slug="password-reset",
        description="User can reset their password",
        risk_level="HIGH",
        is_deleted=False,
    )
    
    # No business behavior mapping
    
    detector = RequirementGapDetector(db=db_session)
    report = detector.detect_gaps(
        pr_description="This PR updates authentication",
        acceptance_criteria=[],
        affected_behaviors=[behavior],
        business_behavior_mappings=[],
        ac_coverage_report=None,
        changed_files=None
    )
    
    assert report.total_gaps == 1
    assert report.high_gaps == 1
    
    gap = report.gaps[0]
    assert gap.gap_type == "UNMAPPED_BUSINESS_BEHAVIOR"
    assert gap.severity == "HIGH"
    assert "Password Reset" in gap.message
    
    print(f"✓ Detected unmapped business behavior")


def test_detect_unmapped_critical_behavior(db_session: Session):
    """Test detection of unmapped CRITICAL risk behavior."""
    
    # Create CRITICAL risk behavior
    behavior = Behavior(
        id=uuid4(),
        journey_id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        slug="authentication",
        description="User authentication",
        risk_level="CRITICAL",
        is_deleted=False,
    )
    
    detector = RequirementGapDetector(db=db_session)
    report = detector.detect_gaps(
        pr_description="This PR updates authentication",
        acceptance_criteria=[],
        affected_behaviors=[behavior],
        business_behavior_mappings=[],
        ac_coverage_report=None,
        changed_files=None
    )
    
    assert report.total_gaps == 1
    gap = report.gaps[0]
    assert gap.gap_type == "UNMAPPED_BUSINESS_BEHAVIOR"
    assert gap.severity == "HIGH"  # CRITICAL behavior gets HIGH severity
    
    print(f"✓ Detected unmapped CRITICAL behavior with HIGH severity")


def test_detect_untested_acceptance_criterion(db_session: Session):
    """Test detection of untested acceptance criterion."""
    
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
    
    # Create AC coverage status (missing)
    ac_coverage_status = AcceptanceCriteriaCoverageStatus(
        acceptance_criterion_id=str(ac.id),
        coverage_status="MISSING_TEST_COVERAGE",
        existing_tests=[],
        suggested_scenarios=[],
        current_pr_execution_status="NOT_EXECUTED",
        confidence=0.5,
        reason="No test coverage"
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
    
    detector = RequirementGapDetector(db=db_session)
    report = detector.detect_gaps(
        pr_description="This PR updates authentication",
        acceptance_criteria=[ac],
        affected_behaviors=[],
        business_behavior_mappings=[],
        ac_coverage_report=ac_coverage_report,
        changed_files=None
    )
    
    assert report.total_gaps == 1
    gap = report.gaps[0]
    assert gap.gap_type == "UNTESTED_ACCEPTANCE_CRITERION"
    assert gap.severity == "HIGH"  # MUST priority gets HIGH severity
    
    print(f"✓ Detected untested acceptance criterion")


def test_detect_untested_optional_criterion(db_session: Session):
    """Test detection of untested OPTIONAL criterion (lower severity)."""
    
    ac = AcceptanceCriterion(
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
    
    ac_coverage_status = AcceptanceCriteriaCoverageStatus(
        acceptance_criterion_id=str(ac.id),
        coverage_status="MISSING_TEST_COVERAGE",
        existing_tests=[],
        suggested_scenarios=[],
        current_pr_execution_status="NOT_EXECUTED",
        confidence=0.5,
        reason="No test coverage"
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
    
    detector = RequirementGapDetector(db=db_session)
    report = detector.detect_gaps(
        pr_description="This PR updates authentication",
        acceptance_criteria=[ac],
        affected_behaviors=[],
        business_behavior_mappings=[],
        ac_coverage_report=ac_coverage_report,
        changed_files=None
    )
    
    assert report.total_gaps == 1
    gap = report.gaps[0]
    assert gap.gap_type == "UNTESTED_ACCEPTANCE_CRITERION"
    assert gap.severity == "MEDIUM"  # OPTIONAL gets MEDIUM severity
    
    print(f"✓ Detected untested OPTIONAL criterion with MEDIUM severity")


def test_no_gaps_detected(db_session: Session):
    """Test when no gaps are detected."""
    
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
    
    behavior = Behavior(
        id=uuid4(),
        journey_id=uuid4(),
        repository_id=uuid4(),
        name="Password Reset",
        slug="password-reset",
        description="User can reset their password",
        risk_level="HIGH",
        is_deleted=False,
    )
    
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac.id,
        behavior_id=behavior.id,
        behavior_scenario_id=uuid4(),
        journey_id=uuid4(),
        match_confidence=0.9,
        matched_terms=["password"],
        reason="Match",
        is_candidate_missing_scenario="false",
    )
    
    ac_coverage_status = AcceptanceCriteriaCoverageStatus(
        acceptance_criterion_id=str(ac.id),
        coverage_status="COVERED_BY_EXISTING_TEST",
        existing_tests=["test_1"],
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
    
    detector = RequirementGapDetector(db=db_session)
    report = detector.detect_gaps(
        pr_description="This PR updates authentication with clear requirements",
        acceptance_criteria=[ac],
        affected_behaviors=[behavior],
        business_behavior_mappings=[mapping],
        ac_coverage_report=ac_coverage_report,
        changed_files=None
    )
    
    assert report.total_gaps == 0
    assert report.overall_trust_level == "HIGH"
    
    print(f"✓ No gaps detected, trust level: {report.overall_trust_level}")


def test_multiple_gaps_detected(db_session: Session):
    """Test detection of multiple gaps."""
    
    # Empty PR description
    # Missing AC
    # Unmapped behavior
    
    behavior = Behavior(
        id=uuid4(),
        journey_id=uuid4(),
        repository_id=uuid4(),
        name="Password Reset",
        slug="password-reset",
        description="User can reset their password",
        risk_level="HIGH",
        is_deleted=False,
    )
    
    detector = RequirementGapDetector(db=db_session)
    report = detector.detect_gaps(
        pr_description="",
        acceptance_criteria=[],
        affected_behaviors=[behavior],
        business_behavior_mappings=[],
        ac_coverage_report=None,
        changed_files=None
    )
    
    assert report.total_gaps == 2  # Empty description + Missing AC (unmapped behavior needs AC to be detected)
    assert report.critical_gaps == 1
    assert report.high_gaps == 1
    assert report.overall_trust_level == "VERY_LOW"
    
    print(f"✓ Detected multiple gaps")
    print(f"  Total: {report.total_gaps}, Critical: {report.critical_gaps}, High: {report.high_gaps}")


def test_trust_level_calculation(db_session: Session):
    """Test trust level calculation based on gaps."""
    
    detector = RequirementGapDetector(db=db_session)
    
    # Critical gaps -> VERY_LOW
    assert detector._determine_trust_level(1, 0, 0, 0) == "VERY_LOW"
    
    # 2+ high gaps -> LOW
    assert detector._determine_trust_level(0, 2, 0, 0) == "LOW"
    
    # 1 high gap -> MEDIUM
    assert detector._determine_trust_level(0, 1, 0, 0) == "MEDIUM"
    
    # 3+ medium gaps -> MEDIUM
    assert detector._determine_trust_level(0, 0, 3, 0) == "MEDIUM"
    
    # 1-2 medium gaps -> HIGH
    assert detector._determine_trust_level(0, 0, 1, 0) == "HIGH"
    assert detector._determine_trust_level(0, 0, 2, 0) == "HIGH"
    
    # No gaps -> HIGH
    assert detector._determine_trust_level(0, 0, 0, 0) == "HIGH"
    
    print(f"✓ Trust level calculation works correctly")


def test_vague_requirement_detection(db_session: Session):
    """Test vague requirement detection logic."""
    
    detector = RequirementGapDetector(db=db_session)
    
    # Vague indicators
    assert detector._is_vague_requirement("Maybe we could add this") == True
    assert detector._is_vague_requirement("Might consider adding feature") == True
    assert detector._is_vague_requirement("Nice to have feature") == True
    assert detector._is_vague_requirement("Consider exploring this") == True
    
    # Not vague
    assert detector._is_vague_requirement("User must be able to reset password") == False
    assert detector._is_vague_requirement("System should validate input") == False
    
    # Very short
    assert detector._is_vague_requirement("Add feature") == True
    
    print(f"✓ Vague requirement detection works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
