"""
Test script for ChangedFileBehaviorMatcher.

Tests multi-stage path matching, tokenization and synonym resolution.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.changed_file_behavior_matcher import ChangedFileBehaviorMatcher
from app.models.behavior import Behavior
from app.models.behavior_evidence import BehaviorEvidence
from app.models.journey_behavior import JourneyBehavior
from app.models.journey import Journey
from dataclasses import dataclass
import uuid


@dataclass
class MockBehavior:
    id: str
    name: str
    slug: str
    risk_level: str


@dataclass
class MockEvidence:
    id: str
    behavior_id: str
    evidence_type: str
    source_path: str
    confidence: str
    excerpt: str


@dataclass
class MockJourneyBehavior:
    journey_id: str
    behavior_id: str


@dataclass
class MockJourney:
    id: str
    name: str


def test_changed_file_behavior_matcher():
    """Verify multi-stage matches on changed file structures."""
    print("=" * 60)
    print("CHANGED FILE BEHAVIOR MATCHER TEST")
    print("=" * 60)
    
    matcher = ChangedFileBehaviorMatcher(db=None)
    
    # Setup test vectors
    auth_journey = MockJourney(id=uuid.uuid4(), name="Authentication")
    billing_journey = MockJourney(id=uuid.uuid4(), name="Billing")
    journeys = [auth_journey, billing_journey]
    
    pwd_reset_b = MockBehavior(id=uuid.uuid4(), name="Password Reset", slug="reset-password", risk_level="HIGH")
    login_b = MockBehavior(id=uuid.uuid4(), name="Login", slug="login", risk_level="HIGH")
    register_b = MockBehavior(id=uuid.uuid4(), name="User Registration", slug="user-registration", risk_level="HIGH")
    subscription_b = MockBehavior(id=uuid.uuid4(), name="Subscription Plan", slug="subscription-plan", risk_level="CRITICAL")
    behaviors = [pwd_reset_b, login_b, register_b, subscription_b]
    
    journey_behaviors = [
        MockJourneyBehavior(journey_id=auth_journey.id, behavior_id=pwd_reset_b.id),
        MockJourneyBehavior(journey_id=auth_journey.id, behavior_id=login_b.id),
        MockJourneyBehavior(journey_id=auth_journey.id, behavior_id=register_b.id),
        MockJourneyBehavior(journey_id=billing_journey.id, behavior_id=subscription_b.id),
    ]
    
    evidences = [
        MockEvidence(id=uuid.uuid4(), behavior_id=pwd_reset_b.id, evidence_type="ROUTE", source_path="auth/reset-password/api.py", confidence="HIGH", excerpt="POST /auth/reset-password"),
    ]
    
    # Test cases
    test_cases = [
        # Direct Evidence Path Match (Score 1.0)
        {
            "file": "auth/reset-password/api.py",
            "expected_behavior": "Password Reset",
            "expected_signal": "DIRECT_EVIDENCE",
            "expected_score": 1.0,
        },
        # Path Suffix Match (Score 0.9)
        {
            "file": "src/app/api/auth/reset-password",
            "expected_behavior": "Password Reset",
            "expected_signal": "PATH_SUFFIX",
            "expected_score": 0.9,
        },
        # Route/Page/Module Match (Score 0.8)
        {
            "file": "src/app/api/auth/reset-password/route.ts",
            "expected_behavior": "Password Reset",
            "expected_signal": "ROUTE_PAGE_MODULE",
            "expected_score": 0.8,
        },
        # Token Match (Score 0.7)
        {
            "file": "src/services/password-validator.ts",
            "expected_behavior": "Password Reset",
            "expected_signal": "TOKEN_MATCH",
            "expected_score": 0.7,
        },
        # Alias/Synonym Match (Score 0.6)
        {
            "file": "src/app/signup/sign-up-form.tsx",
            "expected_behavior": "User Registration",
            "expected_signal": "ALIAS_SYNONYM",
            "expected_score": 0.6,
        },
        # Journey Expansion Match (Score 0.5)
        {
            "file": "src/app/billing/index.ts",
            "expected_behavior": "Subscription Plan",
            "expected_signal": "JOURNEY_EXPANSION",
            "expected_score": 0.5,
        }
    ]
    
    print("Evaluating matches:")
    for tc in test_cases:
        print(f"\nEvaluating file: '{tc['file']}'")
        matches = matcher.match_changed_files(
            changed_files=[tc["file"]],
            behaviors=behaviors,
            evidences=evidences,
            journey_behaviors=journey_behaviors,
            journeys=journeys,
        )
        
        # Find match for expected behavior
        match = next((m for m in matches if m["behavior_name"] == tc["expected_behavior"]), None)
        assert match is not None, f"Expected match not found for {tc['expected_behavior']}"
        
        print(f"  - Matched behavior: {match['behavior_name']}")
        print(f"  - Signal: {match['signal_type']} (expected {tc['expected_signal']})")
        print(f"  - Score: {match['score']} (expected {tc['expected_score']})")
        print(f"  - Reason: {match['reason']}")
        
        assert match["signal_type"] == tc["expected_signal"], f"Expected signal {tc['expected_signal']}, got {match['signal_type']}"
        assert abs(match["score"] - tc["expected_score"]) < 1e-5, f"Expected score {tc['expected_score']}, got {match['score']}"
        
    print("\n\nTest 2: Generic token exclusion check")
    print("-" * 60)
    
    generic_file = "src/app/page/index.tsx"
    matches_generic = matcher.match_changed_files(
        changed_files=[generic_file],
        behaviors=behaviors,
        evidences=evidences,
        journey_behaviors=journey_behaviors,
        journeys=journeys,
    )
    
    print(f"File: '{generic_file}' produces {len(matches_generic)} matches.")
    assert len(matches_generic) == 0, "Expected zero matches for generic tokens only"
    print("[PASS] Generic tokens filtered correctly.")
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    test_changed_file_behavior_matcher()
