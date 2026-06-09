"""
Test script for ExistingTestToBehaviorScenarioMapper.

Tests mapping uploaded JUnit test outcomes directly to database behavior scenarios.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.existing_test_to_behavior_scenario_mapper import ExistingTestToBehaviorScenarioMapper
from app.models.behavior import Behavior
from app.models.behavior_scenario import BehaviorScenario
from app.models.test_result import TestCase
from app.models.test_coverage_link import TestCoverageLink
from dataclasses import dataclass
import uuid


@dataclass
class MockTestCase:
    id: str
    stable_identity: str


@dataclass
class MockBehavior:
    id: str
    name: str


@dataclass
class MockScenario:
    id: str
    behavior_id: str
    title: str
    priority: str


@dataclass
class MockCoverageLink:
    id: str
    test_identifier: str
    file_path: str


def test_existing_test_to_behavior_scenario_mapper():
    """Verify ingested test cases map correctly to scenarios."""
    print("=" * 60)
    print("EXISTING TEST TO BEHAVIOR SCENARIO MAPPER TEST")
    print("=" * 60)
    
    mapper = ExistingTestToBehaviorScenarioMapper(db=None)
    
    # 1. Setup mock models
    pwd_reset_b = MockBehavior(id=uuid.uuid4(), name="Password Reset")
    register_b = MockBehavior(id=uuid.uuid4(), name="User Registration")
    behaviors = [pwd_reset_b, register_b]
    
    scenarios = [
        MockScenario(id=uuid.uuid4(), behavior_id=pwd_reset_b.id, title="Validate password reset expired token rejection", priority="MUST"),
        MockScenario(id=uuid.uuid4(), behavior_id=pwd_reset_b.id, title="Validate reset flow password complexity rules", priority="SHOULD"),
        MockScenario(id=uuid.uuid4(), behavior_id=register_b.id, title="Validate user signup flow password complexity rules", priority="MUST"),
    ]
    
    test_cases = [
        # Match Password Reset Expired Token Rejection
        MockTestCase(id=uuid.uuid4(), stable_identity="auth.middleware::should_reject_expired_token"),
        # Match Reset Flow Password Complexity
        MockTestCase(id=uuid.uuid4(), stable_identity="auth.reset::test_password_reset_complexity_validation"),
        # Match User Registration Signup flow
        MockTestCase(id=uuid.uuid4(), stable_identity="users.signup::should_reject_weak_password"),
    ]
    
    # Run mapping
    mappings = mapper.map_tests_to_scenarios(
        test_cases=test_cases,
        behaviors=behaviors,
        scenarios=scenarios,
        test_coverage_links=[],
    )
    
    print(f"Discovered {len(mappings)} test-to-scenario mappings:")
    for m in mappings:
        test = m["test_identifier"]
        b = next((x for x in behaviors if str(x.id) == m["behavior_id"]), None)
        s = next((x for x in scenarios if str(x.id) == m["behavior_scenario_id"]), None)
        print(f"\n  Test: {test}")
        print(f"    -> Mapped Behavior: {b.name if b else 'Unknown'}")
        print(f"    -> Mapped Scenario: {s.title if s else 'Unknown'}")
        print(f"    -> Confidence: {m['confidence']}")
        print(f"    -> Signals: {m['source_signal']}")
        print(f"    -> Matched terms: {m['matched_terms']}")
        print(f"    -> Reason: {m['reason']}")

    # Verification Assertions
    # should_reject_expired_token maps to password reset expired token rejection
    assert any(
        "should_reject_expired_token" in m["test_identifier"] and m["confidence"] == "MEDIUM"
        for m in mappings
    ), "Expected auth expired token rejection test to map to Password Reset"
    
    # should_reject_weak_password maps to user signup password complexity rule (signup synonym)
    assert any(
        "should_reject_weak_password" in m["test_identifier"] and "User Registration" in next((x.name for x in behaviors if str(x.id) == m["behavior_id"]), "")
        for m in mappings
    ), "Expected signup weak password test to map to User Registration"

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    test_existing_test_to_behavior_scenario_mapper()
