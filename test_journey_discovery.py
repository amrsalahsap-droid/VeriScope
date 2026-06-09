"""
Test script for JourneyDiscoveryEngine.

Tests automatic journey inference from behaviors.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.journey_discovery_engine import JourneyDiscoveryEngine
from app.services.journey_candidate import JourneyCandidate
from dataclasses import dataclass
import uuid


# Mock Behavior class for testing
@dataclass
class MockBehavior:
    id: str
    name: str
    confidence: str
    risk_level: str
    discovery_source: str


def test_journey_discovery():
    """Test journey discovery from behaviors."""
    print("=" * 60)
    print("JOURNEY DISCOVERY ENGINE TEST")
    print("=" * 60)
    
    # Initialize engine
    engine = JourneyDiscoveryEngine(db=None)
    
    # Test 1: Authentication Journey Discovery
    print("\nTest 1: Authentication Journey Discovery")
    print("-" * 60)
    
    auth_behaviors = [
        MockBehavior(
            id=str(uuid.uuid4()),
            name="Login",
            confidence="HIGH",
            risk_level="HIGH",
            discovery_source="ROUTE_INFERRED",
        ),
        MockBehavior(
            id=str(uuid.uuid4()),
            name="Logout",
            confidence="HIGH",
            risk_level="MEDIUM",
            discovery_source="ROUTE_INFERRED",
        ),
        MockBehavior(
            id=str(uuid.uuid4()),
            name="Password Reset",
            confidence="HIGH",
            risk_level="HIGH",
            discovery_source="TEST_INFERRED",
        ),
        MockBehavior(
            id=str(uuid.uuid4()),
            name="Session Validation",
            confidence="MODERATE",
            risk_level="MEDIUM",
            discovery_source="AUTO_DISCOVERED",
        ),
    ]
    
    candidates = engine.discover_journeys(auth_behaviors, str(uuid.uuid4()))
    
    print(f"Journey Candidates: {len(candidates)}")
    for candidate in candidates:
        print(f"\nJourney: {candidate.name}")
        print(f"  Confidence: {candidate.confidence}")
        print(f"  Score: {candidate.source_confidence_score:.2f}")
        print(f"  Behaviors: {candidate.behaviors}")
        print(f"  Evidence Count: {candidate.get_evidence_count()}")
        print(f"  Risk Level: {candidate.risk_level}")
        print(f"  Description: {candidate.description}")
        print(f"  Business Value: {candidate.business_value}")
        print(f"  Evidence:")
        for evidence in candidate.evidence:
            print(f"    - {evidence}")
    
    # Test 2: Registration Journey Discovery
    print("\n\nTest 2: Registration Journey Discovery")
    print("-" * 60)
    
    reg_behaviors = [
        MockBehavior(
            id=str(uuid.uuid4()),
            name="Signup",
            confidence="HIGH",
            risk_level="HIGH",
            discovery_source="ROUTE_INFERRED",
        ),
        MockBehavior(
            id=str(uuid.uuid4()),
            name="Email Verification",
            confidence="HIGH",
            risk_level="MEDIUM",
            discovery_source="TEST_INFERRED",
        ),
    ]
    
    candidates = engine.discover_journeys(reg_behaviors, str(uuid.uuid4()))
    
    print(f"Journey Candidates: {len(candidates)}")
    for candidate in candidates:
        print(f"\nJourney: {candidate.name}")
        print(f"  Confidence: {candidate.confidence}")
        print(f"  Behaviors: {candidate.behaviors}")
        print(f"  Evidence:")
        for evidence in candidate.evidence:
            print(f"    - {evidence}")
    
    # Test 3: Billing Journey Discovery
    print("\n\nTest 3: Billing Journey Discovery")
    print("-" * 60)
    
    billing_behaviors = [
        MockBehavior(
            id=str(uuid.uuid4()),
            name="Subscription",
            confidence="HIGH",
            risk_level="CRITICAL",
            discovery_source="ROUTE_INFERRED",
        ),
        MockBehavior(
            id=str(uuid.uuid4()),
            name="Invoice",
            confidence="MODERATE",
            risk_level="HIGH",
            discovery_source="AUTO_DISCOVERED",
        ),
        MockBehavior(
            id=str(uuid.uuid4()),
            name="Payment Retry",
            confidence="MODERATE",
            risk_level="HIGH",
            discovery_source="TEST_INFERRED",
        ),
    ]
    
    candidates = engine.discover_journeys(billing_behaviors, str(uuid.uuid4()))
    
    print(f"Journey Candidates: {len(candidates)}")
    for candidate in candidates:
        print(f"\nJourney: {candidate.name}")
        print(f"  Confidence: {candidate.confidence}")
        print(f"  Risk Level: {candidate.risk_level}")
        print(f"  Behaviors: {candidate.behaviors}")
    
    # Test 4: Mixed Behaviors (Multiple Journeys)
    print("\n\nTest 4: Mixed Behaviors (Multiple Journeys)")
    print("-" * 60)
    
    mixed_behaviors = [
        MockBehavior(uuid.uuid4(), "Login", "HIGH", "HIGH", "ROUTE_INFERRED"),
        MockBehavior(uuid.uuid4(), "Logout", "HIGH", "MEDIUM", "ROUTE_INFERRED"),
        MockBehavior(uuid.uuid4(), "Signup", "HIGH", "HIGH", "ROUTE_INFERRED"),
        MockBehavior(uuid.uuid4(), "Email Verification", "HIGH", "MEDIUM", "TEST_INFERRED"),
        MockBehavior(uuid.uuid4(), "Subscription", "HIGH", "CRITICAL", "ROUTE_INFERRED"),
        MockBehavior(uuid.uuid4(), "Invoice", "MODERATE", "HIGH", "AUTO_DISCOVERED"),
    ]
    
    candidates = engine.discover_journeys(mixed_behaviors, str(uuid.uuid4()))
    
    print(f"Journey Candidates: {len(candidates)}")
    for candidate in candidates:
        print(f"\nJourney: {candidate.name}")
        print(f"  Behaviors: {candidate.behaviors}")
        print(f"  Confidence: {candidate.confidence}")
    
    # Test 5: Discovery Statistics
    print("\n\nTest 5: Discovery Statistics")
    print("-" * 60)
    
    stats = engine.get_discovery_stats(candidates)
    print(f"Total Candidates: {stats['total_candidates']}")
    print(f"Total Behaviors: {stats['total_behaviors']}")
    print(f"Average Score: {stats['average_score']:.2f}")
    print(f"By Confidence: {stats['by_confidence']}")
    print(f"By Risk: {stats['by_risk']}")
    
    # Test 6: Single Behavior (Should not form journey)
    print("\n\nTest 6: Single Behavior (Should not form journey)")
    print("-" * 60)
    
    single_behavior = [
        MockBehavior(uuid.uuid4(), "Login", "HIGH", "HIGH", "ROUTE_INFERRED"),
    ]
    
    candidates = engine.discover_journeys(single_behavior, str(uuid.uuid4()))
    print(f"Journey Candidates: {len(candidates)}")
    print("[PASS] Single behavior does not form a journey (requires at least 2)")
    
    # Test 7: Unknown Behavior
    print("\n\nTest 7: Unknown Behavior (Should not form journey)")
    print("-" * 60)
    
    unknown_behavior = [
        MockBehavior(uuid.uuid4(), "Random Feature", "HIGH", "MEDIUM", "AUTO_DISCOVERED"),
    ]
    
    candidates = engine.discover_journeys(unknown_behavior, str(uuid.uuid4()))
    print(f"Journey Candidates: {len(candidates)}")
    print("[PASS] Unknown behavior does not form a journey")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_journey_discovery()
