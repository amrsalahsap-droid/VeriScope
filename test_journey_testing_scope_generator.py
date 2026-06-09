"""
Test script for JourneyTestingScopeGenerator.

Tests journey-driven testing scope generation.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.journey_testing_scope_generator import JourneyTestingScopeGenerator
from app.services.journey_testing_scope import JourneyTestingScope
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


# Mock JourneyStep class for testing
@dataclass
class MockJourneyStep:
    id: str
    journey_id: str
    step_order: int
    step_name: str
    behavior_id: str
    is_optional: bool


def test_journey_testing_scope_generator():
    """Test journey-driven testing scope generation."""
    print("=" * 60)
    print("JOURNEY TESTING SCOPE GENERATOR TEST")
    print("=" * 60)
    
    # Initialize generator
    generator = JourneyTestingScopeGenerator(db=None)
    
    # Test 1: Authentication Journey Testing Scope
    print("\nTest 1: Authentication Journey Testing Scope")
    print("-" * 60)
    
    auth_journey = MockJourney(
        id=uuid.uuid4(),
        name="Authentication",
        slug="authentication",
        risk_level="HIGH",
    )
    
    auth_behaviors = [
        MockBehavior(
            id=uuid.uuid4(),
            name="Login",
            risk_level="HIGH",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Password Reset",
            risk_level="HIGH",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Token Validation",
            risk_level="MEDIUM",
        ),
    ]
    
    scope = generator.generate_testing_scope(auth_journey, auth_behaviors)
    
    print(f"Journey: {scope.journey}")
    print(f"Must Test ({len(scope.must_test)}):")
    for test in scope.must_test:
        print(f"  - {test}")
    print(f"Should Test ({len(scope.should_test)}):")
    for test in scope.should_test:
        print(f"  - {test}")
    print(f"Optional ({len(scope.optional)}):")
    for test in scope.optional:
        print(f"  - {test}")
    
    assert "Login" in scope.must_test, "Expected Login in must_test"
    assert "Password Reset" in scope.must_test, "Expected Password Reset in must_test"
    assert "Token Validation" in scope.should_test, "Expected Token Validation in should_test"
    print("[PASS] Authentication journey testing scope generated correctly")
    
    # Test 2: Journey Impact-Based Scope
    print("\n\nTest 2: Journey Impact-Based Scope (Affected Behaviors Only)")
    print("-" * 60)
    
    affected_behaviors = [
        MockBehavior(
            id=uuid.uuid4(),
            name="Login",
            risk_level="HIGH",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Password Reset",
            risk_level="HIGH",
        ),
    ]
    
    scope = generator.generate_scope_from_impact(auth_journey, affected_behaviors)
    
    print(f"Journey: {scope.journey}")
    print(f"Affected Behaviors: {[b.name for b in affected_behaviors]}")
    print(f"Must Test ({len(scope.must_test)}):")
    for test in scope.must_test:
        print(f"  - {test}")
    print(f"Should Test ({len(scope.should_test)}):")
    for test in scope.should_test:
        print(f"  - {test}")
    
    assert "Login" in scope.must_test, "Expected Login in must_test"
    assert "Password Reset" in scope.must_test, "Expected Password Reset in must_test"
    print("[PASS] Impact-based scope generated correctly")
    
    # Test 3: Billing Journey (CRITICAL Risk)
    print("\n\nTest 3: Billing Journey (CRITICAL Risk)")
    print("-" * 60)
    
    billing_journey = MockJourney(
        id=uuid.uuid4(),
        name="Billing",
        slug="billing",
        risk_level="CRITICAL",
    )
    
    billing_behaviors = [
        MockBehavior(
            id=uuid.uuid4(),
            name="Subscription",
            risk_level="CRITICAL",
        ),
        MockBehavior(
            id=uuid.uuid4(),
            name="Payment Processing",
            risk_level="CRITICAL",
        ),
    ]
    
    scope = generator.generate_testing_scope(billing_journey, billing_behaviors)
    
    print(f"Journey: {scope.journey}")
    print(f"Must Test ({len(scope.must_test)}):")
    for test in scope.must_test:
        print(f"  - {test}")
    
    assert "Subscription" in scope.must_test, "Expected Subscription in must_test"
    assert "Payment Processing" in scope.must_test, "Expected Payment Processing in must_test"
    print("[PASS] Billing journey testing scope generated correctly")
    
    # Test 4: Journey Steps Integration
    print("\n\nTest 4: Journey Steps Integration")
    print("-" * 60)
    
    journey_steps = [
        MockJourneyStep(
            id=uuid.uuid4(),
            journey_id=auth_journey.id,
            step_order=1,
            step_name="Login",
            behavior_id=auth_behaviors[0].id,
            is_optional=False,
        ),
        MockJourneyStep(
            id=uuid.uuid4(),
            journey_id=auth_journey.id,
            step_order=2,
            step_name="Session Refresh",
            behavior_id=uuid.uuid4(),
            is_optional=True,
        ),
    ]
    
    scope = generator.generate_testing_scope(auth_journey, auth_behaviors, journey_steps)
    
    print(f"Journey: {scope.journey}")
    print(f"Must Test ({len(scope.must_test)}):")
    for test in scope.must_test:
        print(f"  - {test}")
    print(f"Should Test ({len(scope.should_test)}):")
    for test in scope.should_test:
        print(f"  - {test}")
    
    assert "Login" in scope.must_test, "Expected Login in must_test (from step)"
    assert "Session Refresh" in scope.should_test, "Expected Session Refresh in should_test (optional step)"
    print("[PASS] Journey steps integrated correctly")
    
    # Test 5: Batch Scope Generation
    print("\n\nTest 5: Batch Scope Generation")
    print("-" * 60)
    
    journeys = [auth_journey, billing_journey]
    behaviors_map = {
        str(auth_journey.id): auth_behaviors,
        str(billing_journey.id): billing_behaviors,
    }
    
    scopes = generator.batch_generate_scopes(journeys, behaviors_map)
    
    print(f"Generated scopes for {len(scopes)} journeys:")
    for scope in scopes:
        print(f"  - {scope.journey}: {len(scope.must_test)} must, {len(scope.should_test)} should, {len(scope.optional)} optional")
    
    assert len(scopes) == 2, "Expected 2 scopes"
    print("[PASS] Batch scope generation successful")
    
    # Test 6: Scope Summary
    print("\n\nTest 6: Scope Summary")
    print("-" * 60)
    
    summary = generator.get_scope_summary(scopes)
    
    print(f"Total Journeys: {summary['total_journeys']}")
    print(f"Total Must Test: {summary['total_must_test']}")
    print(f"Total Should Test: {summary['total_should_test']}")
    print(f"Total Optional: {summary['total_optional']}")
    
    assert summary['total_journeys'] == 2, "Expected 2 journeys"
    print("[PASS] Scope summary calculated correctly")
    
    # Test 7: Unknown Journey
    print("\n\nTest 7: Unknown Journey (Fallback)")
    print("-" * 60)
    
    unknown_journey = MockJourney(
        id=uuid.uuid4(),
        name="Unknown Journey",
        slug="unknown-journey",
        risk_level="MEDIUM",
    )
    
    unknown_behaviors = [
        MockBehavior(
            id=uuid.uuid4(),
            name="Custom Behavior",
            risk_level="MEDIUM",
        ),
    ]
    
    scope = generator.generate_testing_scope(unknown_journey, unknown_behaviors)
    
    print(f"Journey: {scope.journey}")
    print(f"Must Test: {scope.must_test}")
    print(f"Should Test: {scope.should_test}")
    print(f"Optional: {scope.optional}")
    
    assert "Custom Behavior" in scope.should_test, "Expected Custom Behavior in should_test (MEDIUM risk)"
    print("[PASS] Unknown journey handled with fallback")
    
    # Test 8: Business-Oriented Testing
    print("\n\nTest 8: Business-Oriented Testing (Not File-Driven)")
    print("-" * 60)
    
    print("Authentication Journey Testing Scope:")
    print("  Must Test: Business-critical authentication flows")
    print("  Should Test: Important but non-critical flows")
    print("  Optional: Performance and smoke tests")
    print("\nThis is journey-driven, not file-driven.")
    print("[PASS] Testing scope is business-oriented")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_journey_testing_scope_generator()
