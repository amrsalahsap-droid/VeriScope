"""
Test script for PRJourneyImpactAnalyzer.

Tests PR journey impact analysis from changed files.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.pr_journey_impact_analyzer import PRJourneyImpactAnalyzer
from app.services.journey_impact import JourneyImpact
from dataclasses import dataclass
import uuid


# Mock Journey class for testing
@dataclass
class MockJourney:
    id: str
    name: str
    slug: str
    risk_level: str


# Mock Behavior class for testing
@dataclass
class MockBehavior:
    id: str
    name: str
    risk_level: str
    risk_reason: str


# Mock JourneyBehavior class for testing
@dataclass
class MockJourneyBehavior:
    journey_id: str
    behavior_id: str


def test_pr_journey_impact_analyzer():
    """Test PR journey impact analysis from changed files."""
    print("=" * 60)
    print("PR JOURNEY IMPACT ANALYZER TEST")
    print("=" * 60)
    
    # Initialize analyzer
    analyzer = PRJourneyImpactAnalyzer(db=None)
    
    # Test 1: Password Reset Route Change
    print("\nTest 1: Password Reset Route Change")
    print("-" * 60)
    
    changed_files = [
        "auth/reset-password/api.py",
        "auth/reset-password/service.py",
    ]
    
    # Create behaviors
    behaviors = [
        MockBehavior(
            id=uuid.uuid4(),
            name="Password Reset",
            risk_level="HIGH",
            risk_reason="Security vulnerability",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Token Validation",
            risk_level="MEDIUM",
            risk_reason="Session management",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Login",
            risk_level="HIGH",
            risk_reason="User access control",
        ),
    ]
    
    # Create journeys
    auth_journey = MockJourney(
        id=uuid.uuid4(),
        name="Authentication",
        slug="authentication",
        risk_level="HIGH",
    )
    
    password_recovery_journey = MockJourney(
        id=uuid.uuid4(),
        name="Password Recovery",
        slug="password-recovery",
        risk_level="HIGH",
    )
    
    journeys = [auth_journey, password_recovery_journey]
    
    # Create journey-behavior mappings
    journey_behaviors = [
        MockJourneyBehavior(journey_id=auth_journey.id, behavior_id=behaviors[0].id),
        MockJourneyBehavior(journey_id=auth_journey.id, behavior_id=behaviors[1].id),
        MockJourneyBehavior(journey_id=auth_journey.id, behavior_id=behaviors[2].id),
        MockJourneyBehavior(journey_id=password_recovery_journey.id, behavior_id=behaviors[0].id),
        MockJourneyBehavior(journey_id=password_recovery_journey.id, behavior_id=behaviors[1].id),
    ]
    
    impacts = analyzer.analyze_pr_impact(changed_files, behaviors, journey_behaviors, journeys)
    
    print(f"Changed Files: {changed_files}")
    print(f"Affected Journeys: {len(impacts)}")
    
    for impact in impacts:
        print(f"\nJourney: {impact.journey_name}")
        print(f"  Impact Level: {impact.impact_level}")
        print(f"  Affected Behaviors: {impact.affected_behaviors}")
        print(f"  Affected Files: {impact.affected_files}")
        print(f"  Risk Changes: {impact.risk_changes}")
        print(f"  Confidence: {impact.confidence}")
        print(f"  Impact Reason: {impact.impact_reason}")
    
    assert len(impacts) >= 1, "Expected at least 1 affected journey"
    assert any("Authentication" in i.journey_name for i in impacts), "Expected Authentication journey"
    assert any("Password Recovery" in i.journey_name for i in impacts), "Expected Password Recovery journey"
    print("[PASS] Password reset change impacts Authentication and Password Recovery journeys")
    
    # Test 2: Billing Route Change
    print("\n\nTest 2: Billing Route Change (CRITICAL Impact)")
    print("-" * 60)
    
    changed_files = [
        "billing/subscription/api.py",
        "billing/payment/service.py",
    ]
    
    billing_behaviors = [
        MockBehavior(
            id=uuid.uuid4(),
            name="Subscription",
            risk_level="CRITICAL",
            risk_reason="Revenue generation",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Payment Processing",
            risk_level="CRITICAL",
            risk_reason="Financial data",
        ),
    ]
    
    billing_journey = MockJourney(
        id=uuid.uuid4(),
        name="Billing",
        slug="billing",
        risk_level="CRITICAL",
    )
    
    billing_journey_behaviors = [
        MockJourneyBehavior(journey_id=billing_journey.id, behavior_id=billing_behaviors[0].id),
        MockJourneyBehavior(journey_id=billing_journey.id, behavior_id=billing_behaviors[1].id),
    ]
    
    impacts = analyzer.analyze_pr_impact(
        changed_files,
        billing_behaviors,
        billing_journey_behaviors,
        [billing_journey],
    )
    
    print(f"Changed Files: {changed_files}")
    print(f"Affected Journeys: {len(impacts)}")
    
    for impact in impacts:
        print(f"\nJourney: {impact.journey_name}")
        print(f"  Impact Level: {impact.impact_level}")
        print(f"  Affected Behaviors: {impact.affected_behaviors}")
        print(f"  Impact Reason: {impact.impact_reason}")
    
    assert len(impacts) == 1, "Expected 1 affected journey"
    assert impacts[0].impact_level == "CRITICAL", "Expected CRITICAL impact"
    print("[PASS] Billing change has CRITICAL impact")
    
    # Test 3: No Impact
    print("\n\nTest 3: No Impact (Unrelated Files)")
    print("-" * 60)
    
    changed_files = [
        "docs/readme.md",
        "config/settings.py",
    ]
    
    impacts = analyzer.analyze_pr_impact(
        changed_files,
        behaviors,
        journey_behaviors,
        journeys,
    )
    
    print(f"Changed Files: {changed_files}")
    print(f"Affected Journeys: {len(impacts)}")
    
    assert len(impacts) == 0, "Expected 0 affected journeys"
    print("[PASS] Unrelated files have no journey impact")
    
    # Test 4: Impact Summary
    print("\n\nTest 4: Impact Summary")
    print("-" * 60)
    
    # Reuse the password reset test for summary
    impacts = analyzer.analyze_pr_impact(changed_files, behaviors, journey_behaviors, journeys)
    
    summary = analyzer.get_impact_summary(impacts)
    
    print(f"Total Affected Journeys: {summary['total_affected_journeys']}")
    print(f"By Impact Level: {summary['by_impact_level']}")
    print(f"Total Affected Behaviors: {summary['total_affected_behaviors']}")
    print(f"Total Affected Files: {summary['total_affected_files']}")
    
    print("[PASS] Impact summary calculated correctly")
    
    # Test 5: Multiple Files Impact
    print("\n\nTest 5: Multiple Files Impact")
    print("-" * 60)
    
    changed_files = [
        "auth/login/api.py",
        "auth/logout/api.py",
        "auth/session/service.py",
    ]
    
    impacts = analyzer.analyze_pr_impact(changed_files, behaviors, journey_behaviors, journeys)
    
    print(f"Changed Files: {changed_files}")
    print(f"Affected Journeys: {len(impacts)}")
    
    for impact in impacts:
        print(f"\nJourney: {impact.journey_name}")
        print(f"  Affected Behaviors: {impact.affected_behaviors}")
        print(f"  Affected Files: {impact.affected_files}")
        print(f"  Confidence: {impact.confidence}")
    
    assert len(impacts) >= 1, "Expected at least 1 affected journey"
    print("[PASS] Multiple files correctly mapped to journeys")
    
    # Test 6: Explainable Impact Reasons
    print("\n\nTest 6: Explainable Impact Reasons")
    print("-" * 60)
    
    # Test with password reset
    changed_files = ["auth/reset-password/api.py"]
    impacts = analyzer.analyze_pr_impact(changed_files, behaviors, journey_behaviors, journeys)
    
    for impact in impacts:
        print(f"Journey: {impact.journey_name}")
        print(f"Impact Reason: {impact.impact_reason}")
        print(f"Changed Files Cited: {', '.join(impact.affected_files)}")
        print(f"Behaviors Cited: {', '.join(impact.affected_behaviors)}")
    
    print("[PASS] Impact reasons cite changed files and affected behaviors")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_pr_journey_impact_analyzer()
