"""Test coverage gap linking and severity rules."""
import pytest
from app.services.regression_evidence_classifier import (
    RequirementNode,
    TestNode,
    CoverageNode,
    EvidenceClassification,
)
from app.services.evidence_graph.recommendation_view_model_builder import (
    RecommendationViewModelBuilder,
    CoverageGapCard,
)


def test_signup_block_on_reset_password_gaps():
    """Test that reset-password coverage gaps do not link to sign-up tests unless shared policy validation exists."""
    builder = RecommendationViewModelBuilder()
    
    # Create a reset-password coverage gap
    reset_gap = CoverageNode(
        file_path="app/routes/password_reset.py",
        line_coverage=45.0,
        branch_coverage=30.0,
        coverage_strength="weak",
        related_flows=["password_reset"],
        related_requirement_ids=["req-1"],
        uncovered_lines=[10, 15, 20],
        partially_covered_branches=["branch-1"],
    )
    
    # Create a sign-up test (should be blocked)
    signup_test = TestNode(
        test_id="test-1",
        title="test_user_signup",
        classname="TestSignup",
        file_path="tests/test_signup.py",
        mapped_requirement_ids=["req-2"],
    )
    
    # Create a password policy test (should be allowed via shared policy)
    policy_test = TestNode(
        test_id="test-2",
        title="test_password_policy_validation",
        classname="TestPasswordPolicy",
        file_path="tests/test_password_policy.py",
        mapped_requirement_ids=["req-1"],
    )
    
    # Build coverage gaps
    builder.view_model.coverage_gaps = []
    builder._build_coverage_gaps([reset_gap], [], [signup_test, policy_test])
    
    # Should have one coverage gap
    assert len(builder.view_model.coverage_gaps) == 1
    
    gap = builder.view_model.coverage_gaps[0]
    
    # Should link to password policy test, not signup test
    assert gap.linked_test_id == "test-2"
    assert gap.linked_test_title == "test_password_policy_validation"
    assert gap.why_link_relevant == "Linked through shared password policy validation logic."
    assert gap.mapping_method == "shared_password_policy"


def test_optional_severity_for_verified_behaviors():
    """Test that coverage gaps get Optional severity if related requirement is already verified."""
    builder = RecommendationViewModelBuilder()
    
    # Create a verified requirement
    verified_req = RequirementNode(
        requirement_id="req-1",
        title="Password reset requirement",
        classification=EvidenceClassification.VERIFIED_BY_CURRENT_PR_EXECUTION,
        risk_level="high",
    )
    
    # Create a coverage gap related to the verified requirement
    gap = CoverageNode(
        file_path="app/routes/password_reset.py",
        line_coverage=45.0,
        branch_coverage=30.0,
        coverage_strength="weak",
        related_flows=["password_reset"],
        related_requirement_ids=["req-1"],
        uncovered_lines=[10, 15, 20],
        partially_covered_branches=["branch-1"],
    )
    
    # Build coverage gaps
    builder.view_model.coverage_gaps = []
    builder._build_coverage_gaps([gap], [verified_req], [])
    
    # Should have one coverage gap
    assert len(builder.view_model.coverage_gaps) == 1
    
    coverage_gap = builder.view_model.coverage_gaps[0]
    
    # Should be Optional severity since requirement is verified
    assert coverage_gap.severity == "Optional"


def test_critical_severity_for_high_risk_no_tests():
    """Test that coverage gaps get Critical/Must severity for high-risk requirements with no tests."""
    builder = RecommendationViewModelBuilder()
    
    # Create a high-risk requirement with no tests
    high_risk_req = RequirementNode(
        requirement_id="req-1",
        title="Critical security requirement",
        classification=EvidenceClassification.MISSING_AUTOMATED_COVERAGE,
        risk_level="high",
    )
    
    # Create a coverage gap related to the high-risk requirement
    gap = CoverageNode(
        file_path="app/routes/auth.py",
        line_coverage=20.0,
        branch_coverage=10.0,
        coverage_strength="weak",
        related_flows=["login"],
        related_requirement_ids=["req-1"],
        uncovered_lines=[5, 10, 15],
        partially_covered_branches=["branch-1"],
    )
    
    # Build coverage gaps
    builder.view_model.coverage_gaps = []
    builder._build_coverage_gaps([gap], [high_risk_req], [])
    
    # Should have one coverage gap
    assert len(builder.view_model.coverage_gaps) == 1
    
    coverage_gap = builder.view_model.coverage_gaps[0]
    
    # Should be Must severity for high-risk with no tests
    assert coverage_gap.severity == "Must"


def test_recommended_severity_for_security_sensitive():
    """Test that coverage gaps get Recommended severity for security-sensitive logic with weak branch coverage."""
    builder = RecommendationViewModelBuilder()
    
    # Create a coverage gap in auth module with weak branch coverage
    gap = CoverageNode(
        file_path="app/routes/auth.py",
        line_coverage=70.0,
        branch_coverage=55.0,  # Below 60% threshold
        coverage_strength="partial",
        related_flows=["login"],
        related_requirement_ids=[],
        uncovered_lines=[10, 15],
        partially_covered_branches=["branch-1"],
    )
    
    # Build coverage gaps
    builder.view_model.coverage_gaps = []
    builder._build_coverage_gaps([gap], [], [])
    
    # Should have one coverage gap
    assert len(builder.view_model.coverage_gaps) == 1
    
    coverage_gap = builder.view_model.coverage_gaps[0]
    
    # Should be Recommended severity for security-sensitive with weak branch coverage
    assert coverage_gap.severity == "Recommended"


def test_mapping_score_and_method_diagnostics():
    """Test that coverage gaps include correct mapping score and method in diagnostics."""
    builder = RecommendationViewModelBuilder()
    
    # Create a coverage gap
    gap = CoverageNode(
        file_path="app/routes/password_reset.py",
        line_coverage=45.0,
        branch_coverage=30.0,
        coverage_strength="weak",
        related_flows=["password_reset"],
        related_requirement_ids=["req-1"],
        uncovered_lines=[10, 15, 20],
        partially_covered_branches=["branch-1"],
    )
    
    # Create a test with matching parent requirement
    test = TestNode(
        test_id="test-1",
        title="test_unrelated_flow",
        classname="TestUnrelatedClass",
        file_path="tests/test_unrelated.py",
        mapped_requirement_ids=["req-1"],
    )
    
    # Build coverage gaps
    builder.view_model.coverage_gaps = []
    builder._build_coverage_gaps([gap], [], [test])
    
    # Should have one coverage gap
    assert len(builder.view_model.coverage_gaps) == 1
    
    coverage_gap = builder.view_model.coverage_gaps[0]
    
    # Should have mapping score > 0
    assert coverage_gap.mapping_score > 0
    
    # Should have mapping method
    assert coverage_gap.mapping_method == "parent_requirement"
    
    # Should have link relevance explanation
    assert coverage_gap.why_link_relevant == "Linked through same parent requirement."


def test_no_linked_test_when_no_relevance():
    """Test that coverage gaps show 'No directly linked test' when no relevant test is found."""
    builder = RecommendationViewModelBuilder()
    
    # Create a coverage gap
    gap = CoverageNode(
        file_path="app/routes/user_profile.py",
        line_coverage=45.0,
        branch_coverage=30.0,
        coverage_strength="weak",
        related_flows=["profile"],
        related_requirement_ids=["req-1"],
        uncovered_lines=[10, 15, 20],
        partially_covered_branches=["branch-1"],
    )
    
    # Create an unrelated test
    test = TestNode(
        test_id="test-1",
        title="test_user_signup",
        classname="TestSignup",
        file_path="tests/test_signup.py",
        mapped_requirement_ids=["req-2"],
    )
    
    # Build coverage gaps
    builder.view_model.coverage_gaps = []
    builder._build_coverage_gaps([gap], [], [test])
    
    # Should have one coverage gap
    assert len(builder.view_model.coverage_gaps) == 1
    
    coverage_gap = builder.view_model.coverage_gaps[0]
    
    # Should have no linked test
    assert coverage_gap.linked_test_id is None
    assert coverage_gap.linked_test_title == "No directly linked test"
    assert coverage_gap.why_link_relevant is None
    assert coverage_gap.mapping_score == 0.0
    assert coverage_gap.mapping_method == "unmapped"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
