"""Verification test for BehaviorImpactAnalyzer determinism and evidence backing.

This test verifies that the behavior impact analyzer produces deterministic,
evidence-backed results for a specific set of changed files and behaviors.

Seed Data:
- Changed files: auth/reset-password, reset-password page, signup form, users sign-up
- Expected impacted behaviors: Password Reset, User Registration, Authentication
- Expected journey: Authentication
- NOT expected: Billing or other unrelated behaviors
"""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.behavior_impact_analyzer import BehaviorImpactAnalyzer
from app.models.behavior import Behavior
from app.models.behavior_evidence import BehaviorEvidence
from app.models.behavior_scenario import BehaviorScenario
from app.models.journey_behavior import JourneyBehavior
from app.models.journey import Journey
from app.models.journey_relationship import JourneyRelationship


def test_behavior_impact_deterministic_and_evidence_backed(db_session: Session):
    """Verify behavior impact analysis is deterministic and evidence-backed."""
    
    # Create repository
    repository_id = uuid4()
    
    # Create Journey: Authentication
    auth_journey = Journey(
        id=uuid4(),
        repository_id=repository_id,
        name="Authentication",
        description="User authentication, login, logout, and password management",
        is_deleted=False,
    )
    db_session.add(auth_journey)
    
    # Create Journey: Billing (unrelated, should NOT be impacted)
    billing_journey = Journey(
        id=uuid4(),
        repository_id=repository_id,
        name="Billing",
        description="Subscription, invoicing, and payment processing",
        is_deleted=False,
    )
    db_session.add(billing_journey)
    db_session.commit()
    
    # Create Behavior: Password Reset
    password_reset_behavior = Behavior(
        id=uuid4(),
        journey_id=auth_journey.id,
        repository_id=repository_id,
        name="Password Reset",
        slug="password-reset",
        description="User requests and completes password reset flow",
        risk_level="HIGH",
        is_deleted=False,
    )
    db_session.add(password_reset_behavior)
    
    # Create Behavior: User Registration
    user_registration_behavior = Behavior(
        id=uuid4(),
        journey_id=auth_journey.id,
        repository_id=repository_id,
        name="User Registration",
        slug="user-registration",
        description="New user signs up and creates account",
        risk_level="HIGH",
        is_deleted=False,
    )
    db_session.add(user_registration_behavior)
    
    # Create Behavior: Authentication (general)
    authentication_behavior = Behavior(
        id=uuid4(),
        journey_id=auth_journey.id,
        repository_id=repository_id,
        name="Authentication",
        slug="authentication",
        description="User login and session management",
        risk_level="CRITICAL",
        is_deleted=False,
    )
    db_session.add(authentication_behavior)
    
    # Create Behavior: Billing (unrelated, should NOT be impacted)
    billing_behavior = Behavior(
        id=uuid4(),
        journey_id=billing_journey.id,
        repository_id=repository_id,
        name="Subscription Management",
        slug="subscription-management",
        description="User manages subscription and billing",
        risk_level="MEDIUM",
        is_deleted=False,
    )
    db_session.add(billing_behavior)
    db_session.commit()
    
    # Create JourneyBehavior mappings
    db_session.add(JourneyBehavior(
        id=uuid4(),
        journey_id=auth_journey.id,
        behavior_id=password_reset_behavior.id,
    ))
    db_session.add(JourneyBehavior(
        id=uuid4(),
        journey_id=auth_journey.id,
        behavior_id=user_registration_behavior.id,
    ))
    db_session.add(JourneyBehavior(
        id=uuid4(),
        journey_id=auth_journey.id,
        behavior_id=authentication_behavior.id,
    ))
    db_session.add(JourneyBehavior(
        id=uuid4(),
        journey_id=billing_journey.id,
        behavior_id=billing_behavior.id,
    ))
    db_session.commit()
    
    # Create Behavior Evidence for Password Reset
    db_session.add(BehaviorEvidence(
        id=uuid4(),
        behavior_id=password_reset_behavior.id,
        source_path="src/app/api/auth/reset-password/route.ts",
        evidence_type="file_path",
        confidence="HIGH",
    ))
    db_session.add(BehaviorEvidence(
        id=uuid4(),
        behavior_id=password_reset_behavior.id,
        source_path="src/app/reset-password/page.tsx",
        evidence_type="file_path",
        confidence="HIGH",
    ))
    
    # Create Behavior Evidence for User Registration
    db_session.add(BehaviorEvidence(
        id=uuid4(),
        behavior_id=user_registration_behavior.id,
        source_path="src/app/signup/sign-up-form.tsx",
        evidence_type="file_path",
        confidence="HIGH",
    ))
    db_session.add(BehaviorEvidence(
        id=uuid4(),
        behavior_id=user_registration_behavior.id,
        source_path="src/modules/users/sign-up.ts",
        evidence_type="file_path",
        confidence="HIGH",
    ))
    
    # Create Behavior Evidence for Authentication (general)
    db_session.add(BehaviorEvidence(
        id=uuid4(),
        behavior_id=authentication_behavior.id,
        source_path="src/app/api/auth/reset-password/route.ts",
        evidence_type="file_path",
        confidence="HIGH",
    ))
    
    # Create Behavior Evidence for Billing (unrelated)
    db_session.add(BehaviorEvidence(
        id=uuid4(),
        behavior_id=billing_behavior.id,
        source_path="src/app/billing/invoice.ts",
        evidence_type="file_path",
        confidence="HIGH",
    ))
    db_session.commit()
    
    # Create Behavior Scenarios
    db_session.add(BehaviorScenario(
        id=uuid4(),
        behavior_id=password_reset_behavior.id,
        title="Valid password reset token",
        description="User resets password with valid token",
        priority="MUST",
        case_type="positive",
    ))
    db_session.add(BehaviorScenario(
        id=uuid4(),
        behavior_id=user_registration_behavior.id,
        title="Successful user registration",
        description="User creates account with valid credentials",
        priority="MUST",
        case_type="positive",
    ))
    db_session.add(BehaviorScenario(
        id=uuid4(),
        behavior_id=authentication_behavior.id,
        title="User login with valid credentials",
        description="User logs in with correct username and password",
        priority="MUST",
        case_type="positive",
    ))
    db_session.commit()
    
    # Changed files from the PR
    changed_files = [
        "src/app/api/auth/reset-password/route.ts",
        "src/app/reset-password/page.tsx",
        "src/app/signup/sign-up-form.tsx",
        "src/modules/users/sign-up.ts",
    ]
    
    # Get all behaviors
    behaviors = db_session.query(Behavior).filter(
        Behavior.repository_id == repository_id
    ).all()
    
    # Get all behavior evidences
    behavior_evidences = db_session.query(BehaviorEvidence).filter(
        BehaviorEvidence.behavior_id.in_([b.id for b in behaviors])
    ).all()
    
    # Get all behavior scenarios
    behavior_scenarios = db_session.query(BehaviorScenario).filter(
        BehaviorScenario.behavior_id.in_([b.id for b in behaviors])
    ).all()
    
    # Get all journey behaviors
    journey_behaviors = db_session.query(JourneyBehavior).filter(
        JourneyBehavior.behavior_id.in_([b.id for b in behaviors])
    ).all()
    
    # Get all journeys
    journeys = db_session.query(Journey).filter(
        Journey.id.in_([jb.journey_id for jb in journey_behaviors])
    ).all()
    
    # Run behavior impact analysis
    analyzer = BehaviorImpactAnalyzer(db=db_session)
    result = analyzer.analyze_behavior_impact(
        repository_id=repository_id,
        pull_request_id=None,
        changed_files=changed_files,
        behaviors=behaviors,
        behavior_evidences=behavior_evidences,
        behavior_scenarios=behavior_scenarios,
        journey_behaviors=journey_behaviors,
        journeys=journeys,
        journey_relationships=[],
        pr_title="Update auth and signup flows",
        pr_description="Improve password reset and user registration",
    )
    
    impacted_behaviors = result["impacted_behaviors"]
    impacted_behavior_ids = {b["behavior_id"] for b in impacted_behaviors}
    
    # VERIFICATION 1: Password Reset is impacted
    password_reset_impacted = any(
        b["behavior_id"] == str(password_reset_behavior.id)
        for b in impacted_behaviors
    )
    assert password_reset_impacted, "Password Reset behavior should be impacted"
    print("✓ Password Reset is impacted")
    
    # VERIFICATION 2: User Registration is impacted
    user_registration_impacted = any(
        b["behavior_id"] == str(user_registration_behavior.id)
        for b in impacted_behaviors
    )
    assert user_registration_impacted, "User Registration behavior should be impacted"
    print("✓ User Registration is impacted")
    
    # VERIFICATION 3: Authentication journey is impacted
    impacted_journey_ids = set()
    for b in impacted_behaviors:
        if b.get("journey_id"):
            impacted_journey_ids.add(b["journey_id"])
    
    auth_journey_impacted = str(auth_journey.id) in impacted_journey_ids
    assert auth_journey_impacted, "Authentication journey should be impacted"
    print("✓ Authentication journey is impacted")
    
    # VERIFICATION 4: Impact levels assigned correctly
    password_reset_impact = next(
        (b for b in impacted_behaviors if b["behavior_id"] == str(password_reset_behavior.id)),
        None
    )
    assert password_reset_impact is not None, "Password Reset should have impact data"
    assert password_reset_impact["impact_level"] in ["HIGH", "CRITICAL"], \
        f"Password Reset impact level should be HIGH or CRITICAL, got {password_reset_impact['impact_level']}"
    print(f"✓ Password Reset impact level: {password_reset_impact['impact_level']}")
    
    user_registration_impact = next(
        (b for b in impacted_behaviors if b["behavior_id"] == str(user_registration_behavior.id)),
        None
    )
    assert user_registration_impact is not None, "User Registration should have impact data"
    assert user_registration_impact["impact_level"] in ["HIGH", "CRITICAL"], \
        f"User Registration impact level should be HIGH or CRITICAL, got {user_registration_impact['impact_level']}"
    print(f"✓ User Registration impact level: {user_registration_impact['impact_level']}")
    
    # VERIFICATION 5: Changed files linked to behavior
    password_reset_files = password_reset_impact.get("impacted_files", [])
    assert "src/app/api/auth/reset-password/route.ts" in password_reset_files, \
        "Password reset route should be in impacted files"
    assert "src/app/reset-password/page.tsx" in password_reset_files, \
        "Password reset page should be in impacted files"
    print(f"✓ Password Reset linked to {len(password_reset_files)} changed files")
    
    user_registration_files = user_registration_impact.get("impacted_files", [])
    assert "src/app/signup/sign-up-form.tsx" in user_registration_files, \
        "Signup form should be in impacted files"
    assert "src/modules/users/sign-up.ts" in user_registration_files, \
        "Sign-up module should be in impacted files"
    print(f"✓ User Registration linked to {len(user_registration_files)} changed files")
    
    # VERIFICATION 6: Behavior evidence present
    assert password_reset_impact.get("source_signals") is not None, \
        "Password Reset should have source signals (evidence)"
    assert len(password_reset_impact["source_signals"]) > 0, \
        "Password Reset should have at least one source signal"
    print(f"✓ Password Reset has {len(password_reset_impact['source_signals'])} source signals")
    
    assert user_registration_impact.get("source_signals") is not None, \
        "User Registration should have source signals (evidence)"
    assert len(user_registration_impact["source_signals"]) > 0, \
        "User Registration should have at least one source signal"
    print(f"✓ User Registration has {len(user_registration_impact['source_signals'])} source signals")
    
    # VERIFICATION 7: Impact reasons explainable
    password_reset_reason = password_reset_impact.get("impact_reason", "")
    assert password_reset_reason, "Password Reset should have an impact reason"
    assert len(password_reset_reason) > 10, "Impact reason should be descriptive"
    print(f"✓ Password Reset impact reason: {password_reset_reason[:50]}...")
    
    user_registration_reason = user_registration_impact.get("impact_reason", "")
    assert user_registration_reason, "User Registration should have an impact reason"
    assert len(user_registration_reason) > 10, "Impact reason should be descriptive"
    print(f"✓ User Registration impact reason: {user_registration_reason[:50]}...")
    
    # VERIFICATION 8: No unrelated Billing behavior impacted
    billing_impacted = any(
        b["behavior_id"] == str(billing_behavior.id)
        for b in impacted_behaviors
    )
    assert not billing_impacted, "Billing behavior should NOT be impacted (unrelated to changed files)"
    print("✓ Billing behavior NOT impacted (correctly excluded)")
    
    # Additional verification: Confidence levels
    for b in impacted_behaviors:
        assert b["confidence"] in ["HIGH", "MODERATE", "LOW"], \
            f"Confidence should be valid, got {b['confidence']}"
    print(f"✓ All impacted behaviors have valid confidence levels")
    
    # Additional verification: Affected scenarios
    for b in impacted_behaviors:
        assert "affected_scenarios" in b, "Each impacted behavior should list affected scenarios"
        assert isinstance(b["affected_scenarios"], list), "Affected scenarios should be a list"
    print(f"✓ All impacted behaviors list affected scenarios")
    
    # Summary
    print("\n" + "="*60)
    print("BEHAVIOR IMPACT ANALYZER VERIFICATION PASSED")
    print("="*60)
    print(f"Total impacted behaviors: {len(impacted_behaviors)}")
    print(f"Impacted behavior names: {[b['behavior_name'] for b in impacted_behaviors]}")
    print(f"Impacted journeys: {len(impacted_journey_ids)}")
    print(f"Analysis confidence: {result['confidence']}")
    print("="*60)
    print("The behavior impact analyzer is deterministic and evidence-backed.")


def test_behavior_impact_determinism_multiple_runs(db_session: Session):
    """Verify that running the analysis multiple times produces identical results."""
    
    # Setup minimal data
    repository_id = uuid4()
    journey = Journey(
        id=uuid4(),
        repository_id=repository_id,
        name="Test Journey",
        description="Test",
        is_deleted=False,
    )
    db_session.add(journey)
    db_session.commit()
    
    behavior = Behavior(
        id=uuid4(),
        journey_id=journey.id,
        repository_id=repository_id,
        name="Test Behavior",
        slug="test-behavior",
        description="Test",
        risk_level="MEDIUM",
        is_deleted=False,
    )
    db_session.add(behavior)
    db_session.commit()
    
    db_session.add(JourneyBehavior(
        id=uuid4(),
        journey_id=journey.id,
        behavior_id=behavior.id,
    ))
    db_session.add(BehaviorEvidence(
        id=uuid4(),
        behavior_id=behavior.id,
        source_path="src/app/test.ts",
        evidence_type="file_path",
        confidence="HIGH",
    ))
    db_session.add(BehaviorScenario(
        id=uuid4(),
        behavior_id=behavior.id,
        title="Test Scenario",
        description="Test",
        priority="MUST",
        case_type="positive",
    ))
    db_session.commit()
    
    changed_files = ["src/app/test.ts"]
    
    behaviors = db_session.query(Behavior).filter(Behavior.repository_id == repository_id).all()
    behavior_evidences = db_session.query(BehaviorEvidence).all()
    behavior_scenarios = db_session.query(BehaviorScenario).all()
    journey_behaviors = db_session.query(JourneyBehavior).all()
    journeys = db_session.query(Journey).all()
    
    # Run analysis twice
    analyzer = BehaviorImpactAnalyzer(db=db_session)
    result1 = analyzer.analyze_behavior_impact(
        repository_id=repository_id,
        pull_request_id=None,
        changed_files=changed_files,
        behaviors=behaviors,
        behavior_evidences=behavior_evidences,
        behavior_scenarios=behavior_scenarios,
        journey_behaviors=journey_behaviors,
        journeys=journeys,
    )
    
    result2 = analyzer.analyze_behavior_impact(
        repository_id=repository_id,
        pull_request_id=None,
        changed_files=changed_files,
        behaviors=behaviors,
        behavior_evidences=behavior_evidences,
        behavior_scenarios=behavior_scenarios,
        journey_behaviors=journey_behaviors,
        journeys=journeys,
    )
    
    # Compare results
    assert result1["confidence"] == result2["confidence"], "Confidence should be identical"
    assert len(result1["impacted_behaviors"]) == len(result2["impacted_behaviors"]), \
        "Number of impacted behaviors should be identical"
    
    # Compare each impacted behavior
    for b1, b2 in zip(result1["impacted_behaviors"], result2["impacted_behaviors"]):
        assert b1["behavior_id"] == b2["behavior_id"], "Behavior ID should match"
        assert b1["impact_level"] == b2["impact_level"], "Impact level should match"
        assert b1["confidence"] == b2["confidence"], "Confidence should match"
        assert set(b1["impacted_files"]) == set(b2["impacted_files"]), "Impacted files should match"
    
    print("✓ Behavior impact analysis is deterministic (identical results on multiple runs)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
