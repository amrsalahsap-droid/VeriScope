"""Test suite for BusinessBehaviorMapper."""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.business_behavior_mapper import BusinessBehaviorMapper
from app.models.business_behavior_mapping import BusinessBehaviorMapping
from app.models.behavior import Behavior
from app.models.behavior_scenario import BehaviorScenario
from app.models.journey import Journey
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.repository import Repository
from app.models.user import Workspace


def test_map_ac_to_behavior_strong_match(db_session: Session):
    """Test mapping AC to behavior with strong name match."""
    
    # Create journey
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    db_session.add(journey)
    db_session.commit()
    
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
    db_session.add(behavior)
    db_session.commit()
    
    # Create scenario
    scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=behavior.id,
        title="Weak password rejected",
        description="System rejects weak passwords",
        priority="MUST",
        case_type="negative",
    )
    db_session.add(scenario)
    db_session.commit()
    
    # Create acceptance criterion
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
    
    # Map
    mapper = BusinessBehaviorMapper(db=db_session)
    mappings = mapper.map_acceptance_criteria_to_behaviors(
        acceptance_criteria=[ac],
        behaviors=[behavior],
        scenarios=[scenario],
        journeys=[journey],
        domain_vocabulary=None
    )
    
    assert len(mappings) == 1, f"Expected 1 mapping, got {len(mappings)}"
    
    mapping = mappings[0]
    assert str(mapping.behavior_id) == str(behavior.id)
    assert str(mapping.behavior_scenario_id) == str(scenario.id)
    assert mapping.match_confidence >= 0.5
    assert mapping.is_candidate_missing_scenario == "false"
    assert "password" in str(mapping.matched_terms).lower() or "weak" in str(mapping.matched_terms).lower()
    
    print(f"✓ Strong behavior match: confidence={mapping.match_confidence:.2f}")
    print(f"  Matched terms: {mapping.matched_terms}")
    print(f"  Reason: {mapping.reason}")


def test_map_ac_to_behavior_synonym_match(db_session: Session):
    """Test mapping AC to behavior using synonym matching."""
    
    # Create journey
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    db_session.add(journey)
    db_session.commit()
    
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
    db_session.add(behavior)
    db_session.commit()
    
    # Create scenario
    scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=behavior.id,
        title="Credential recovery",
        description="User recovers credentials",
        priority="MUST",
        case_type="positive",
    )
    db_session.add(scenario)
    db_session.commit()
    
    # Create acceptance criterion with synonym
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User can recover their credentials",
        normalized_key="user can recover their credentials",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.8,
        evidence_excerpt="- User can recover their credentials",
    )
    db_session.add(ac)
    db_session.commit()
    
    # Map
    mapper = BusinessBehaviorMapper(db=db_session)
    mappings = mapper.map_acceptance_criteria_to_behaviors(
        acceptance_criteria=[ac],
        behaviors=[behavior],
        scenarios=[scenario],
        journeys=[journey],
        domain_vocabulary=None
    )
    
    assert len(mappings) == 1, f"Expected 1 mapping, got {len(mappings)}"
    
    mapping = mappings[0]
    assert str(mapping.behavior_id) == str(behavior.id)
    assert mapping.match_confidence >= 0.3
    assert "credential" in str(mapping.matched_terms).lower() or "recover" in str(mapping.matched_terms).lower()
    
    print(f"✓ Synonym match: confidence={mapping.match_confidence:.2f}")
    print(f"  Matched terms: {mapping.matched_terms}")


def test_map_ac_to_behavior_journey_match(db_session: Session):
    """Test mapping AC to behavior using journey context (broad match)."""
    
    # Create journey
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    db_session.add(journey)
    db_session.commit()
    
    # Create behavior
    behavior = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=uuid4(),
        name="User Login",
        slug="user-login",
        description="User logs into the system",
        risk_level="HIGH",
        is_deleted=False,
    )
    db_session.add(behavior)
    db_session.commit()
    
    # Create scenario
    scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=behavior.id,
        title="Valid credentials accepted",
        description="User logs in with valid credentials",
        priority="MUST",
        case_type="positive",
    )
    db_session.add(scenario)
    db_session.commit()
    
    # Create acceptance criterion with broad authentication term
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User authentication should be secure",
        normalized_key="user authentication should be secure",
        criterion_type="SECURITY",
        source="PR_DESCRIPTION",
        confidence=0.7,
        evidence_excerpt="- User authentication should be secure",
    )
    db_session.add(ac)
    db_session.commit()
    
    # Map
    mapper = BusinessBehaviorMapper(db=db_session)
    mappings = mapper.map_acceptance_criteria_to_behaviors(
        acceptance_criteria=[ac],
        behaviors=[behavior],
        scenarios=[scenario],
        journeys=[journey],
        domain_vocabulary=None
    )
    
    assert len(mappings) == 1, f"Expected 1 mapping, got {len(mappings)}"
    
    mapping = mappings[0]
    assert str(mapping.behavior_id) == str(behavior.id)
    assert mapping.match_confidence >= 0.2
    assert "authentication" in str(mapping.matched_terms).lower()
    
    print(f"✓ Journey/broad match: confidence={mapping.match_confidence:.2f}")


def test_map_ac_no_matching_scenario(db_session: Session):
    """Test mapping AC when no matching scenario exists (candidate missing scenario)."""
    
    # Create journey
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    db_session.add(journey)
    db_session.commit()
    
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
    db_session.add(behavior)
    db_session.commit()
    
    # Create unrelated scenario
    scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=behavior.id,
        title="Valid token accepted",
        description="User resets with valid token",
        priority="MUST",
        case_type="positive",
    )
    db_session.add(scenario)
    db_session.commit()
    
    # Create acceptance criterion for missing scenario
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="Password reset email should be sent within 5 minutes",
        normalized_key="password reset email should be sent within 5 minutes",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.8,
        evidence_excerpt="- Password reset email should be sent within 5 minutes",
    )
    db_session.add(ac)
    db_session.commit()
    
    # Map
    mapper = BusinessBehaviorMapper(db=db_session)
    mappings = mapper.map_acceptance_criteria_to_behaviors(
        acceptance_criteria=[ac],
        behaviors=[behavior],
        scenarios=[scenario],
        journeys=[journey],
        domain_vocabulary=None
    )
    
    assert len(mappings) == 1, f"Expected 1 mapping, got {len(mappings)}"
    
    mapping = mappings[0]
    assert str(mapping.behavior_id) == str(behavior.id)
    assert mapping.behavior_scenario_id is None, "Scenario ID should be None (no match)"
    assert mapping.is_candidate_missing_scenario == "true"
    assert "candidate missing scenario" in mapping.reason.lower()
    
    print(f"✓ Candidate missing scenario created")
    print(f"  Confidence: {mapping.match_confidence:.2f}")
    print(f"  Reason: {mapping.reason}")


def test_map_ac_negative_case_match(db_session: Session):
    """Test mapping AC to negative scenario."""
    
    # Create journey
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    db_session.add(journey)
    db_session.commit()
    
    # Create behavior
    behavior = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=uuid4(),
        name="Password Validation",
        slug="password-validation",
        description="System validates passwords",
        risk_level="HIGH",
        is_deleted=False,
    )
    db_session.add(behavior)
    db_session.commit()
    
    # Create negative scenario
    scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=behavior.id,
        title="Weak password rejected",
        description="System rejects weak passwords",
        priority="MUST",
        case_type="negative",
    )
    db_session.add(scenario)
    db_session.commit()
    
    # Create acceptance criterion with negative language
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="Invalid passwords must be rejected",
        normalized_key="invalid passwords must be rejected",
        criterion_type="VALIDATION",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- Invalid passwords must be rejected",
    )
    db_session.add(ac)
    db_session.commit()
    
    # Map
    mapper = BusinessBehaviorMapper(db=db_session)
    mappings = mapper.map_acceptance_criteria_to_behaviors(
        acceptance_criteria=[ac],
        behaviors=[behavior],
        scenarios=[scenario],
        journeys=[journey],
        domain_vocabulary=None
    )
    
    assert len(mappings) == 1, f"Expected 1 mapping, got {len(mappings)}"
    
    mapping = mappings[0]
    assert str(mapping.behavior_scenario_id) == str(scenario.id)
    assert mapping.match_confidence >= 0.4
    assert "negative" in str(mapping.matched_terms).lower() or "reject" in str(mapping.matched_terms).lower()
    
    print(f"✓ Negative case match: confidence={mapping.match_confidence:.2f}")


def test_map_ac_positive_case_match(db_session: Session):
    """Test mapping AC to positive scenario."""
    
    # Create journey
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    db_session.add(journey)
    db_session.commit()
    
    # Create behavior
    behavior = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=uuid4(),
        name="User Registration",
        slug="user-registration",
        description="User creates account",
        risk_level="HIGH",
        is_deleted=False,
    )
    db_session.add(behavior)
    db_session.commit()
    
    # Create positive scenario
    scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=behavior.id,
        title="Valid signup succeeds",
        description="User successfully creates account",
        priority="MUST",
        case_type="positive",
    )
    db_session.add(scenario)
    db_session.commit()
    
    # Create acceptance criterion with positive language
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="Valid user registration should succeed",
        normalized_key="valid user registration should succeed",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- Valid registration should succeed",
    )
    db_session.add(ac)
    db_session.commit()
    
    # Map
    mapper = BusinessBehaviorMapper(db=db_session)
    mappings = mapper.map_acceptance_criteria_to_behaviors(
        acceptance_criteria=[ac],
        behaviors=[behavior],
        scenarios=[scenario],
        journeys=[journey],
        domain_vocabulary=None
    )
    
    assert len(mappings) == 1, f"Expected 1 mapping, got {len(mappings)}"
    
    mapping = mappings[0]
    assert str(mapping.behavior_scenario_id) == str(scenario.id)
    assert mapping.match_confidence >= BusinessBehaviorMapper.MEDIUM_CONFIDENCE_THRESHOLD
    assert "positive" in str(mapping.matched_terms).lower() or "success" in str(mapping.matched_terms).lower()
    
    print(f"✓ Positive case match: confidence={mapping.match_confidence:.2f}")


def test_map_ac_domain_vocabulary(db_session: Session):
    """Test mapping AC using domain vocabulary."""
    
    # Create journey
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    db_session.add(journey)
    db_session.commit()
    
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
    db_session.add(behavior)
    db_session.commit()
    
    # Create scenario
    scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=behavior.id,
        title="Token sent via email",
        description="Reset token sent to user email",
        priority="MUST",
        case_type="positive",
    )
    db_session.add(scenario)
    db_session.commit()
    
    # Create acceptance criterion
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="User receives recovery link via email",
        normalized_key="user receives recovery link via email",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.8,
        evidence_excerpt="- User receives recovery link via email",
    )
    db_session.add(ac)
    db_session.commit()
    
    # Domain vocabulary
    domain_vocabulary = {
        "password": ["recovery", "reset", "credential"],
        "email": ["notification", "message", "link"],
    }
    
    # Map
    mapper = BusinessBehaviorMapper(db=db_session)
    mappings = mapper.map_acceptance_criteria_to_behaviors(
        acceptance_criteria=[ac],
        behaviors=[behavior],
        scenarios=[scenario],
        journeys=[journey],
        domain_vocabulary=domain_vocabulary
    )
    
    assert len(mappings) == 1, f"Expected 1 mapping, got {len(mappings)}"
    
    mapping = mappings[0]
    assert str(mapping.behavior_id) == str(behavior.id)
    assert mapping.match_confidence >= 0.25
    
    print(f"✓ Domain vocabulary match: confidence={mapping.match_confidence:.2f}")
    print(f"  Matched terms: {mapping.matched_terms}")


def test_persist_mappings(db_session: Session):
    """Test that mappings can be persisted to database."""
    
    # Create workspace and repository
    workspace = Workspace(id=uuid4(), name="test", slug="test")
    db_session.add(workspace)
    db_session.commit()
    
    repo = Repository(
        id=uuid4(),
        name="test-repo",
        full_name="test/test-repo",
        workspace_id=workspace.id,
        github_repo_id=12345,
    )
    db_session.add(repo)
    db_session.commit()
    
    # Create journey
    journey = Journey(
        id=uuid4(),
        repository_id=repo.id,
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    db_session.add(journey)
    db_session.commit()
    
    # Create behavior
    behavior = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=repo.id,
        name="Password Reset",
        slug="password-reset",
        description="User can reset their password",
        risk_level="HIGH",
        is_deleted=False,
    )
    db_session.add(behavior)
    db_session.commit()
    
    # Create scenario
    scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=behavior.id,
        title="Weak password rejected",
        description="System rejects weak passwords",
        priority="MUST",
        case_type="negative",
    )
    db_session.add(scenario)
    db_session.commit()
    
    # Create acceptance criterion
    ac = AcceptanceCriterion(
        id=uuid4(),
        repository_id=repo.id,
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
    
    # Create mapping
    mapping = BusinessBehaviorMapping(
        id=uuid4(),
        acceptance_criterion_id=ac.id,
        behavior_id=behavior.id,
        behavior_scenario_id=scenario.id,
        journey_id=journey.id,
        match_confidence=0.9,
        matched_terms=["weak", "password", "rejected"],
        reason="Direct behavior and scenario match",
        is_candidate_missing_scenario="false",
    )
    
    # Persist
    mapper = BusinessBehaviorMapper(db=db_session)
    persisted = mapper.persist_mappings([mapping], db_session)
    
    assert len(persisted) == 1, f"Expected 1 persisted mapping, got {len(persisted)}"
    
    # Verify persistence
    db_mappings = db_session.query(BusinessBehaviorMapping).filter(
        BusinessBehaviorMapping.acceptance_criterion_id == ac.id
    ).all()
    
    assert len(db_mappings) == 1, f"Expected 1 mapping in DB, got {len(db_mappings)}"
    
    print("✓ Mapping persisted to database successfully")


def test_map_multiple_ac(db_session: Session):
    """Test mapping multiple acceptance criteria."""
    
    # Create journey
    journey = Journey(
        id=uuid4(),
        repository_id=uuid4(),
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    db_session.add(journey)
    db_session.commit()
    
    # Create behaviors
    password_reset = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=uuid4(),
        name="Password Reset",
        slug="password-reset",
        description="User can reset their password",
        risk_level="HIGH",
        is_deleted=False,
    )
    db_session.add(password_reset)
    
    user_registration = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=uuid4(),
        name="User Registration",
        slug="user-registration",
        description="User creates account",
        risk_level="HIGH",
        is_deleted=False,
    )
    db_session.add(user_registration)
    db_session.commit()
    
    # Create scenarios
    weak_password_scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=password_reset.id,
        title="Weak password rejected",
        description="System rejects weak passwords",
        priority="MUST",
        case_type="negative",
    )
    db_session.add(weak_password_scenario)
    
    valid_signup_scenario = BehaviorScenario(
        id=uuid4(),
        behavior_id=user_registration.id,
        title="Valid signup succeeds",
        description="User successfully creates account",
        priority="MUST",
        case_type="positive",
    )
    db_session.add(valid_signup_scenario)
    db_session.commit()
    
    # Create acceptance criteria
    ac1 = AcceptanceCriterion(
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
    db_session.add(ac1)
    
    ac2 = AcceptanceCriterion(
        id=uuid4(),
        repository_id=uuid4(),
        pull_request_id=uuid4(),
        text="Valid user registration should succeed",
        normalized_key="valid user registration should succeed",
        criterion_type="FUNCTIONAL",
        source="PR_DESCRIPTION",
        confidence=0.9,
        evidence_excerpt="- Valid registration should succeed",
    )
    db_session.add(ac2)
    db_session.commit()
    
    # Map
    mapper = BusinessBehaviorMapper(db=db_session)
    mappings = mapper.map_acceptance_criteria_to_behaviors(
        acceptance_criteria=[ac1, ac2],
        behaviors=[password_reset, user_registration],
        scenarios=[weak_password_scenario, valid_signup_scenario],
        journeys=[journey],
        domain_vocabulary=None
    )
    
    assert len(mappings) == 2, f"Expected 2 mappings, got {len(mappings)}"
    
    # Verify each mapping
    password_reset_mapping = next(
        (m for m in mappings if str(m.behavior_id) == str(password_reset.id)),
        None
    )
    assert password_reset_mapping is not None
    assert str(password_reset_mapping.behavior_scenario_id) == str(weak_password_scenario.id)
    
    registration_mapping = next(
        (m for m in mappings if str(m.behavior_id) == str(user_registration.id)),
        None
    )
    assert registration_mapping is not None
    assert str(registration_mapping.behavior_scenario_id) == str(valid_signup_scenario.id)
    
    print(f"✓ Mapped {len(mappings)} acceptance criteria to behaviors")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
