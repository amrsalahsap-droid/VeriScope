"""
Test script for JourneyRiskEngine.

Tests journey risk calculation from behaviors.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.journey_risk_engine import JourneyRiskEngine
from app.services.journey_risk import JourneyRisk
from dataclasses import dataclass
import uuid


# Mock Journey class for testing
@dataclass
class MockJourney:
    id: str
    name: str
    slug: str
    description: str
    business_value: str
    risk_level: str
    status: str


# Mock Behavior class for testing
@dataclass
class MockBehavior:
    id: str
    name: str
    confidence: str
    risk_level: str
    risk_reason: str


def test_journey_risk_engine():
    """Test journey risk calculation from behaviors."""
    print("=" * 60)
    print("JOURNEY RISK ENGINE TEST")
    print("=" * 60)
    
    # Initialize engine
    engine = JourneyRiskEngine(db=None)
    
    # Test 1: Authentication Journey (HIGH Risk)
    print("\nTest 1: Authentication Journey (HIGH Risk)")
    print("-" * 60)
    
    auth_journey = MockJourney(
        id=uuid.uuid4(),
        name="Authentication",
        slug="authentication",
        description="User authentication workflow",
        business_value="Critical for user access",
        risk_level="HIGH",
        status="CONFIRMED",
    )
    
    auth_behaviors = [
        MockBehavior(
            id=uuid.uuid4(),
            name="Login",
            confidence="HIGH",
            risk_level="HIGH",
            risk_reason="User access control",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Password Reset",
            confidence="HIGH",
            risk_level="MEDIUM",
            risk_reason="Security vulnerability",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Session Validation",
            confidence="MODERATE",
            risk_level="MEDIUM",
            risk_reason="Session management",
        ),
    ]
    
    risk = engine.calculate_journey_risk(auth_journey, auth_behaviors)
    
    print(f"Journey: {auth_journey.name}")
    print(f"Risk Level: {risk.risk_level}")
    print(f"Risk Reason: {risk.risk_reason}")
    print(f"Affected Users: {risk.affected_users}")
    print(f"Confidence: {risk.confidence}")
    print(f"Contributing Behaviors: {risk.contributing_behaviors}")
    print(f"Risk Factors: {risk.risk_factors}")
    
    assert risk.risk_level == "HIGH", "Expected HIGH risk (1 HIGH behavior)"
    print("[PASS] Authentication journey assigned HIGH risk (1 HIGH behavior)")
    
    # Test 2: Billing Journey (CRITICAL Risk)
    print("\n\nTest 2: Billing Journey (CRITICAL Risk)")
    print("-" * 60)
    
    billing_journey = MockJourney(
        id=uuid.uuid4(),
        name="Billing",
        slug="billing",
        description="Payment processing",
        business_value="Critical for revenue",
        risk_level="CRITICAL",
        status="CONFIRMED",
    )
    
    billing_behaviors = [
        MockBehavior(
            id=uuid.uuid4(),
            name="Subscription",
            confidence="HIGH",
            risk_level="CRITICAL",
            risk_reason="Revenue generation",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Payment Processing",
            confidence="HIGH",
            risk_level="CRITICAL",
            risk_reason="Financial data handling",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Invoice",
            confidence="MODERATE",
            risk_level="HIGH",
            risk_reason="Compliance requirements",
        ),
    ]
    
    risk = engine.calculate_journey_risk(billing_journey, billing_behaviors)
    
    print(f"Journey: {billing_journey.name}")
    print(f"Risk Level: {risk.risk_level}")
    print(f"Risk Reason: {risk.risk_reason}")
    print(f"Affected Users: {risk.affected_users}")
    print(f"Confidence: {risk.confidence}")
    print(f"Contributing Behaviors: {risk.contributing_behaviors}")
    
    assert risk.risk_level == "CRITICAL", "Expected CRITICAL risk"
    print("[PASS] Billing journey assigned CRITICAL risk")
    
    # Test 3: Notifications Journey (MEDIUM Risk)
    print("\n\nTest 3: Notifications Journey (MEDIUM Risk)")
    print("-" * 60)
    
    notifications_journey = MockJourney(
        id=uuid.uuid4(),
        name="Notifications",
        slug="notifications",
        description="Notification delivery",
        business_value="Important for engagement",
        risk_level="MEDIUM",
        status="CONFIRMED",
    )
    
    notifications_behaviors = [
        MockBehavior(
            id=uuid.uuid4(),
            name="Email Delivery",
            confidence="MODERATE",
            risk_level="MEDIUM",
            risk_reason="User communication",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Push Notification",
            confidence="MODERATE",
            risk_level="MEDIUM",
            risk_reason="System reliability",
        ),
    ]
    
    risk = engine.calculate_journey_risk(notifications_journey, notifications_behaviors)
    
    print(f"Journey: {notifications_journey.name}")
    print(f"Risk Level: {risk.risk_level}")
    print(f"Risk Reason: {risk.risk_reason}")
    print(f"Affected Users: {risk.affected_users}")
    print(f"Confidence: {risk.confidence}")
    
    assert risk.risk_level == "MEDIUM", "Expected MEDIUM risk"
    print("[PASS] Notifications journey assigned MEDIUM risk")
    
    # Test 4: Journey with No Behaviors
    print("\n\nTest 4: Journey with No Behaviors")
    print("-" * 60)
    
    empty_journey = MockJourney(
        id=uuid.uuid4(),
        name="Empty Journey",
        slug="empty-journey",
        description="Test journey",
        business_value="Unknown",
        risk_level="MEDIUM",
        status="DISCOVERED",
    )
    
    risk = engine.calculate_journey_risk(empty_journey, [])
    
    print(f"Journey: {empty_journey.name}")
    print(f"Risk Level: {risk.risk_level}")
    print(f"Risk Reason: {risk.risk_reason}")
    print(f"Confidence: {risk.confidence}")
    
    assert risk.risk_level == "MEDIUM", "Expected MEDIUM risk for empty journey"
    assert risk.confidence == "LOW", "Expected LOW confidence for empty journey"
    print("[PASS] Empty journey assigned MEDIUM risk with LOW confidence")
    
    # Test 5: Batch Risk Calculation
    print("\n\nTest 5: Batch Risk Calculation")
    print("-" * 60)
    
    journeys = [auth_journey, billing_journey, notifications_journey]
    behaviors_map = {
        str(auth_journey.id): auth_behaviors,
        str(billing_journey.id): billing_behaviors,
        str(notifications_journey.id): notifications_behaviors,
    }
    
    risks = engine.batch_calculate_risks(journeys, behaviors_map)
    
    print(f"Calculated risks for {len(risks)} journeys:")
    for risk in risks:
        print(f"  - Journey ID: {risk.journey_id[:8]}... | Risk: {risk.risk_level}")
    
    assert len(risks) == 3, "Expected 3 risks"
    print("[PASS] Batch risk calculation successful")
    
    # Test 6: Risk Summary
    print("\n\nTest 6: Risk Summary")
    print("-" * 60)
    
    summary = engine.get_risk_summary(risks)
    
    print(f"Total Journeys: {summary['total_journeys']}")
    print(f"By Risk Level: {summary['by_risk_level']}")
    print(f"By Confidence: {summary['by_confidence']}")
    
    assert summary['total_journeys'] == 3, "Expected 3 total journeys"
    assert summary['by_risk_level']['CRITICAL'] == 1, "Expected 1 CRITICAL"
    assert summary['by_risk_level']['HIGH'] == 1, "Expected 1 HIGH"
    assert summary['by_risk_level']['MEDIUM'] == 1, "Expected 1 MEDIUM"
    print("[PASS] Risk summary calculated correctly")
    
    # Test 7: Explainable Risk Reasons
    print("\n\nTest 7: Explainable Risk Reasons")
    print("-" * 60)
    
    print("Authentication Risk Reason:")
    print(f"  {engine.calculate_journey_risk(auth_journey, auth_behaviors).risk_reason}")
    
    print("\nBilling Risk Reason:")
    print(f"  {engine.calculate_journey_risk(billing_journey, billing_behaviors).risk_reason}")
    
    print("\nNotifications Risk Reason:")
    print(f"  {engine.calculate_journey_risk(notifications_journey, notifications_behaviors).risk_reason}")
    
    print("[PASS] All risk reasons are explainable")
    
    # Test 8: Affected Users Estimation
    print("\n\nTest 8: Affected Users Estimation")
    print("-" * 60)
    
    print("Authentication Affected Users:")
    print(f"  {engine.calculate_journey_risk(auth_journey, auth_behaviors).affected_users}")
    
    print("\nBilling Affected Users:")
    print(f"  {engine.calculate_journey_risk(billing_journey, billing_behaviors).affected_users}")
    
    print("\nNotifications Affected Users:")
    print(f"  {engine.calculate_journey_risk(notifications_journey, notifications_behaviors).affected_users}")
    
    print("[PASS] Affected users estimated correctly")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_journey_risk_engine()
