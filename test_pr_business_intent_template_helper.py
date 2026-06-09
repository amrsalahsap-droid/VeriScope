"""Test suite for PRBusinessIntentTemplateHelper."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.pr_business_intent_template_helper import PRBusinessIntentTemplateHelper
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.business_behavior_mapping import BusinessBehaviorMapping


def test_template_needed_for_empty_description(db_session: Session):
    """Test that template is suggested for empty PR description."""
    
    helper = PRBusinessIntentTemplateHelper(db=db_session)
    result = helper.generate_template_suggestion(
        current_pr_description="",
        acceptance_criteria=[],
        affected_behaviors=[],
        affected_journeys=[],
        business_behavior_mappings=[],
        changed_files=None
    )
    
    assert result["needs_template"] == True
    assert result["reason"] == "PR description is too short or missing"
    assert result["template"] is not None
    assert result["copyable"] == True
    
    print(f"✓ Template suggested for empty description")
    print(f"  Reason: {result['reason']}")


def test_template_needed_for_no_acceptance_criteria(db_session: Session):
    """Test that template is suggested when no acceptance criteria."""
    
    helper = PRBusinessIntentTemplateHelper(db=db_session)
    result = helper.generate_template_suggestion(
        current_pr_description="This PR updates authentication",
        acceptance_criteria=[],
        affected_behaviors=[],
        affected_journeys=[],
        business_behavior_mappings=[],
        changed_files=None
    )
    
    assert result["needs_template"] == True
    assert result["reason"] == "No acceptance criteria found in PR"
    assert result["template"] is not None
    
    print(f"✓ Template suggested for no acceptance criteria")


def test_template_needed_for_vague_description(db_session: Session):
    """Test that template is suggested for vague description."""
    
    helper = PRBusinessIntentTemplateHelper(db=db_session)
    result = helper.generate_template_suggestion(
        current_pr_description="Maybe we could consider adding a feature",
        acceptance_criteria=[],
        affected_behaviors=[],
        affected_journeys=[],
        business_behavior_mappings=[],
        changed_files=None
    )
    
    assert result["needs_template"] == True
    assert result["template"] is not None
    
    print(f"✓ Template suggested for vague description")


def test_template_not_needed_for_good_description(db_session: Session):
    """Test that template is not suggested for good description with AC."""
    
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
    
    helper = PRBusinessIntentTemplateHelper(db=db_session)
    result = helper.generate_template_suggestion(
        current_pr_description="This PR implements password reset functionality with clear acceptance criteria",
        acceptance_criteria=[ac],
        affected_behaviors=[],
        affected_journeys=[],
        business_behavior_mappings=[],
        changed_files=None
    )
    
    assert result["needs_template"] == False
    assert result["reason"] == "PR has sufficient business intent"
    
    print(f"✓ Template not suggested for good description")


def test_template_structure(db_session: Session):
    """Test that template has correct structure."""
    
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
    
    helper = PRBusinessIntentTemplateHelper(db=db_session)
    result = helper.generate_template_suggestion(
        current_pr_description="",
        acceptance_criteria=[ac],
        affected_behaviors=[behavior],
        affected_journeys=[journey],
        business_behavior_mappings=[],
        changed_files=["src/auth/password_reset.py"]
    )
    
    template = result["template"]
    
    # Check template sections
    assert "Business Change:" in template
    assert "Affected User/Journey:" in template
    assert "Expected Behavior:" in template
    assert "Acceptance Criteria:" in template
    assert "Risk Notes:" in template
    assert "Testing Notes:" in template
    
    # Check pre-filled content
    assert "Authentication" in template
    assert "Password Reset" in template
    assert "User must be able to reset password" in template
    assert "password_reset.py" in template
    
    print(f"✓ Template has correct structure")
    print(f"  Template preview:\n{template[:200]}...")


def test_template_with_changed_files(db_session: Session):
    """Test that template includes changed files in risk notes."""
    
    helper = PRBusinessIntentTemplateHelper(db=db_session)
    result = helper.generate_template_suggestion(
        current_pr_description="",
        acceptance_criteria=[],
        affected_behaviors=[],
        affected_journeys=[],
        business_behavior_mappings=[],
        changed_files=["src/auth/login.py", "src/auth/password.py", "src/auth/session.py"]
    )
    
    template = result["template"]
    
    assert "Changed files: 3" in template
    assert "login.py" in template
    assert "password.py" in template
    assert "session.py" in template
    
    print(f"✓ Template includes changed files")


def test_template_with_multiple_acceptance_criteria(db_session: Session):
    """Test that template includes all acceptance criteria."""
    
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
    
    helper = PRBusinessIntentTemplateHelper(db=db_session)
    result = helper.generate_template_suggestion(
        current_pr_description="",
        acceptance_criteria=[ac1, ac2],
        affected_behaviors=[],
        affected_journeys=[],
        business_behavior_mappings=[],
        changed_files=None
    )
    
    template = result["template"]
    
    assert "User must be able to reset password" in template
    assert "Weak passwords should be rejected" in template
    
    print(f"✓ Template includes multiple acceptance criteria")


def test_generate_improved_description(db_session: Session):
    """Test generate_improved_description method."""
    
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
    
    helper = PRBusinessIntentTemplateHelper(db=db_session)
    improved = helper.generate_improved_description(
        current_pr_description="",
        acceptance_criteria=[ac],
        affected_behaviors=[],
        affected_journeys=[],
        business_behavior_mappings=[],
        changed_files=None
    )
    
    assert "Business Change:" in improved
    assert "Acceptance Criteria:" in improved
    assert "User must be able to reset password" in improved
    
    print(f"✓ generate_improved_description works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
