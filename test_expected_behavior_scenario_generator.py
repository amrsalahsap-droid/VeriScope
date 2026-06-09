"""Test suite for ExpectedBehaviorScenarioGenerator."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.expected_behavior_scenario_generator import ExpectedBehaviorScenarioGenerator
from app.models.expected_behavior_scenario import ExpectedBehaviorScenario
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.repository import Repository
from app.models.user import Workspace


def test_generate_from_acceptance_criteria_must_priority(db_session: Session):
    """Test generating scenario from AC with MUST priority."""
    
    # Create acceptance criterion
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User must be able to reset their password",
        normalized_key="user must be able to reset their password",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User must be able to reset their password",
    )
    db_session.add(ac)
    db_session.commit()
    
    # Generate scenarios
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_acceptance_criteria(
        acceptance_criteria=[ac],
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(scenarios) == 1, f"Expected 1 scenario, got {len(scenarios)}"
    
    scenario = scenarios[0]
    assert scenario.priority == "MUST"
    assert scenario.source == "ACCEPTANCE_CRITERIA"
    assert scenario.acceptance_criterion_id == ac.id
    assert scenario.confidence >= 0.9, "AC-derived scenarios should have high confidence"
    assert "password" in scenario.title.lower()
    
    print(f"✓ Generated MUST priority scenario: {scenario.title}")
    print(f"  Confidence: {scenario.confidence}")
    print(f"  Steps: {scenario.steps}")


def test_generate_from_acceptance_criteria_should_priority(db_session: Session):
    """Test generating scenario from AC with SHOULD priority."""
    
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User should receive email notification",
        normalized_key="user should receive email notification",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.8,
        evidence_excerpt="- User should receive email notification",
    )
    db_session.add(ac)
    db_session.commit()
    
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_acceptance_criteria(
        acceptance_criteria=[ac],
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.priority == "SHOULD"
    assert "email" in scenario.title.lower()
    
    print(f"✓ Generated SHOULD priority scenario: {scenario.title}")


def test_generate_from_acceptance_criteria_optional_priority(db_session: Session):
    """Test generating scenario from AC with OPTIONAL priority."""
    
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="It would be nice to show user avatar",
        normalized_key="it would be nice to show user avatar",
        criterion_type="UI",
        source="PR_DESCRIPTION",
        confidence=0.6,
        evidence_excerpt="- It would be nice to show user avatar",
    )
    db_session.add(ac)
    db_session.commit()
    
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_acceptance_criteria(
        acceptance_criteria=[ac],
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.priority == "OPTIONAL"
    
    print(f"✓ Generated OPTIONAL priority scenario: {scenario.title}")


def test_generate_from_acceptance_criteria_security_type(db_session: Session):
    """Test generating scenario with SECURITY type."""
    
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="Password must be encrypted before storage",
        normalized_key="password must be encrypted before storage",
        criterion_type="SECURITY",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- Password must be encrypted before storage",
    )
    db_session.add(ac)
    db_session.commit()
    
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_acceptance_criteria(
        acceptance_criteria=[ac],
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.scenario_type == "SECURITY"
    assert "encrypt" in scenario.title.lower() or "password" in scenario.title.lower()
    
    print(f"✓ Generated SECURITY type scenario: {scenario.title}")


def test_generate_from_acceptance_criteria_validation_type(db_session: Session):
    """Test generating scenario with VALIDATION type."""
    
    ac = AcceptanceCriterion(
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
    db_session.add(ac)
    db_session.commit()
    
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_acceptance_criteria(
        acceptance_criteria=[ac],
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.scenario_type == "VALIDATION"
    assert "reject" in scenario.expected_result.lower()
    
    print(f"✓ Generated VALIDATION type scenario: {scenario.title}")
    print(f"  Expected result: {scenario.expected_result}")


def test_generate_from_acceptance_criteria_with_test_data(db_session: Session):
    """Test generating scenario with test data."""
    
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User can reset password with email and token",
        normalized_key="user can reset password with email and token",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User can reset password with email and token",
    )
    db_session.add(ac)
    db_session.commit()
    
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_acceptance_criteria(
        acceptance_criteria=[ac],
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.test_data is not None
    assert "email" in scenario.test_data
    assert "password" in scenario.test_data
    
    print(f"✓ Generated scenario with test data: {scenario.test_data}")


def test_generate_from_acceptance_criteria_with_preconditions(db_session: Session):
    """Test generating scenario with preconditions."""
    
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User can reset their password",
        normalized_key="user can reset their password",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User can reset their password",
    )
    db_session.add(ac)
    db_session.commit()
    
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_acceptance_criteria(
        acceptance_criteria=[ac],
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert len(scenario.preconditions) > 0
    assert any("account" in p.lower() for p in scenario.preconditions)
    
    print(f"✓ Generated scenario with preconditions: {scenario.preconditions}")


def test_generate_from_business_intent(db_session: Session):
    """Test generating scenarios from business intent (inferred)."""
    
    business_intent = {
        "description": "Update authentication and password reset flows",
        "changed_files": [
            "src/app/api/auth/reset-password/route.ts",
            "src/app/reset-password/page.tsx",
        ]
    }
    
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_business_intent(
        business_intent=business_intent,
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(scenarios) >= 2, f"Expected at least 2 scenarios, got {len(scenarios)}"
    
    # Verify inferred scenarios have lower confidence
    for scenario in scenarios:
        assert scenario.source == "BUSINESS_INTENT"
        assert scenario.confidence < 0.5, "Inferred scenarios should have lower confidence"
        assert scenario.priority == "SHOULD", "Inferred scenarios default to SHOULD"
    
    print(f"✓ Generated {len(scenarios)} inferred scenarios from business intent")
    for scenario in scenarios:
        print(f"  - {scenario.title} (confidence: {scenario.confidence})")


def test_generate_from_business_intent_api_file(db_session: Session):
    """Test generating scenario from API file path."""
    
    business_intent = {
        "description": "Add user registration API",
        "changed_files": [
            "src/app/api/users/register/route.ts",
        ]
    }
    
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_business_intent(
        business_intent=business_intent,
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert "api" in scenario.title.lower() or "endpoint" in scenario.title.lower()
    assert scenario.scenario_type == "API"
    assert scenario.testing_type == "AUTOMATED"
    
    print(f"✓ Generated API scenario: {scenario.title}")


def test_generate_from_business_intent_ui_file(db_session: Session):
    """Test generating scenario from UI file path."""
    
    business_intent = {
        "description": "Update password reset page",
        "changed_files": [
            "src/app/reset-password/page.tsx",
        ]
    }
    
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_business_intent(
        business_intent=business_intent,
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert "page" in scenario.title.lower()
    assert scenario.scenario_type == "UI"
    
    print(f"✓ Generated UI scenario: {scenario.title}")


def test_generate_multiple_acceptance_criteria(db_session: Session):
    """Test generating scenarios from multiple AC."""
    
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
        text="It would be nice to show password strength indicator",
        normalized_key="it would be nice to show password strength indicator",
        criterion_type="UI",
        source="PR_DESCRIPTION",
        confidence=0.6,
        evidence_excerpt="- It would be nice to show password strength indicator",
    )
    
    db_session.add_all([ac1, ac2, ac3])
    db_session.commit()
    
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_acceptance_criteria(
        acceptance_criteria=[ac1, ac2, ac3],
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(scenarios) == 3, f"Expected 3 scenarios, got {len(scenarios)}"
    
    # Verify priorities
    must_scenarios = [s for s in scenarios if s.priority == "MUST"]
    should_scenarios = [s for s in scenarios if s.priority == "SHOULD"]
    optional_scenarios = [s for s in scenarios if s.priority == "OPTIONAL"]
    
    assert len(must_scenarios) == 1
    assert len(should_scenarios) == 1
    assert len(optional_scenarios) == 1
    
    print(f"✓ Generated 3 scenarios with different priorities")
    print(f"  MUST: {len(must_scenarios)}, SHOULD: {len(should_scenarios)}, OPTIONAL: {len(optional_scenarios)}")


def test_persist_scenarios(db_session: Session):
    """Test that scenarios can be persisted to database."""
    
    # Create workspace and repository
    workspace = Workspace(id=uuid4(), name="test", slug="test")
    db_session.add(workspace)
    db_session.commit()
    
    repo = Repository(
        id=uuid4(),
        name="test-repo",
        url="https://github.com/test/repo",
        workspace_id=workspace.id,
        github_repo_id=12345,
    )
    db_session.add(repo)
    db_session.commit()
    
    # Create acceptance criterion
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=repo.id,
        pull_request_id=uuid4(),
        text="User must be able to reset password",
        normalized_key="user must be able to reset password",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- User must be able to reset password",
    )
    db_session.add(ac)
    db_session.commit()
    
    # Generate scenario
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    scenarios = generator.generate_from_acceptance_criteria(
        acceptance_criteria=[ac],
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    # Persist
    persisted = generator.persist_scenarios(scenarios, db_session)
    
    assert len(persisted) == 1
    
    # Verify persistence
    db_scenarios = db_session.query(ExpectedBehaviorScenario).filter(
        ExpectedBehaviorScenario.acceptance_criterion_id == ac.id
    ).all()
    
    assert len(db_scenarios) == 1
    assert db_scenarios[0].title == scenarios[0].title
    
    print("✓ Scenario persisted to database successfully")


def test_ac_derived_higher_confidence_than_inferred(db_session: Session):
    """Test that AC-derived scenarios have higher confidence than inferred scenarios."""
    
    # AC-derived
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
    db_session.add(ac)
    db_session.commit()
    
    generator = ExpectedBehaviorScenarioGenerator(db=db_session)
    
    ac_scenarios = generator.generate_from_acceptance_criteria(
        acceptance_criteria=[ac],
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    # Inferred
    business_intent = {
        "description": "Update auth",
        "changed_files": ["src/app/api/auth/route.ts"],
    }
    
    inferred_scenarios = generator.generate_from_business_intent(
        business_intent=business_intent,
        affected_behaviors=[],
        affected_journeys=[],
        recommendation_run_id=None
    )
    
    assert len(ac_scenarios) == 1
    assert len(inferred_scenarios) == 1
    
    assert ac_scenarios[0].confidence > inferred_scenarios[0].confidence, \
        "AC-derived scenarios should have higher confidence than inferred"
    
    print(f"✓ AC-derived confidence ({ac_scenarios[0].confidence}) > Inferred confidence ({inferred_scenarios[0].confidence})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
