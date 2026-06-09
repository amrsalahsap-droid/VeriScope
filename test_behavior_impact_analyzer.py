"""
Test script for BehaviorImpactAnalyzer.

Verifies PR changes are deterministic, evidence-backed and map properly to behaviors and journeys.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.behavior_impact_analyzer import BehaviorImpactAnalyzer
from app.models.behavior import Behavior
from app.models.behavior_evidence import BehaviorEvidence
from app.models.behavior_scenario import BehaviorScenario
from app.models.journey_behavior import JourneyBehavior
from app.models.journey import Journey
from app.models.journey_relationship import JourneyRelationship
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
class MockScenario:
    id: str
    behavior_id: str
    title: str
    priority: str
    scenario_type: str


@dataclass
class MockJourneyBehavior:
    journey_id: str
    behavior_id: str


@dataclass
class MockJourney:
    id: str
    name: str


@dataclass
class MockJourneyRelationship:
    source_journey_id: str
    target_journey_id: str
    relationship_type: str
    source_journey: Any = None
    target_journey: Any = None


def test_behavior_impact_analyzer():
    """Verify behavior impact discovery and scenario matching."""
    print("=" * 60)
    print("BEHAVIOR IMPACT ANALYZER TEST")
    print("=" * 60)
    
    analyzer = BehaviorImpactAnalyzer(db=None)
    
    # 1. Setup mock repository seed
    print("\nTest 1: Seeding Behaviors, Evidences, Scenarios and Journeys")
    print("-" * 60)
    
    # Journeys
    auth_journey = MockJourney(id=uuid.uuid4(), name="Authentication")
    billing_journey = MockJourney(id=uuid.uuid4(), name="Billing")
    journeys = [auth_journey, billing_journey]
    
    # Behaviors
    pwd_reset_b = MockBehavior(id=uuid.uuid4(), name="Password Reset", slug="password-reset", risk_level="HIGH")
    login_b = MockBehavior(id=uuid.uuid4(), name="Login", slug="login", risk_level="HIGH")
    subscription_b = MockBehavior(id=uuid.uuid4(), name="Subscription", slug="subscription", risk_level="CRITICAL")
    behaviors = [pwd_reset_b, login_b, subscription_b]
    
    # Journey-Behavior mappings
    journey_behaviors = [
        MockJourneyBehavior(journey_id=auth_journey.id, behavior_id=pwd_reset_b.id),
        MockJourneyBehavior(journey_id=auth_journey.id, behavior_id=login_b.id),
        MockJourneyBehavior(journey_id=billing_journey.id, behavior_id=subscription_b.id),
    ]
    
    # Evidences
    evidences = [
        MockEvidence(id=uuid.uuid4(), behavior_id=pwd_reset_b.id, evidence_type="ROUTE", source_path="auth/reset-password/api.py", confidence="HIGH", excerpt="POST /auth/reset-password"),
        MockEvidence(id=uuid.uuid4(), behavior_id=pwd_reset_b.id, evidence_type="PAGE", source_path="pages/auth/reset-password.tsx", confidence="HIGH", excerpt="Reset Password Page"),
        MockEvidence(id=uuid.uuid4(), behavior_id=login_b.id, evidence_type="ROUTE", source_path="auth/login/api.py", confidence="HIGH", excerpt="POST /auth/login"),
    ]
    
    # Scenarios
    scenarios = [
        MockScenario(id=uuid.uuid4(), behavior_id=pwd_reset_b.id, title="Validate password reset expired token rejection", priority="MUST", scenario_type="SECURITY"),
        MockScenario(id=uuid.uuid4(), behavior_id=pwd_reset_b.id, title="Validate reset flow password complexity rule", priority="SHOULD", scenario_type="EDGE"),
        MockScenario(id=uuid.uuid4(), behavior_id=login_b.id, title="Validate successful login creates session token", priority="MUST", scenario_type="POSITIVE"),
    ]
    
    # Journey relationships
    rel = MockJourneyRelationship(
        source_journey_id=billing_journey.id,
        target_journey_id=auth_journey.id,
        relationship_type="DEPENDS_ON",
        source_journey=billing_journey,
        target_journey=auth_journey,
    )
    relationships = [rel]
    
    print(f"Seeded:")
    print(f"  - Journeys: {', '.join([j.name for j in journeys])}")
    print(f"  - Behaviors: {', '.join([b.name for b in behaviors])}")
    print(f"  - Evidence sources: {[e.source_path for e in evidences]}")
    print(f"  - Scenarios: {[s.title for s in scenarios]}")
    
    # 2. Analyze PR changing reset-password route/page
    print("\n\nTest 2: Analyzing PR changing reset-password files")
    print("-" * 60)
    
    changed_files = ["auth/reset-password/api.py", "pages/auth/reset-password.tsx"]
    
    snapshot = analyzer.analyze_behavior_impact(
        repository_id=uuid.uuid4(),
        pull_request_id=uuid.uuid4(),
        changed_files=changed_files,
        behaviors=behaviors,
        behavior_evidences=evidences,
        behavior_scenarios=scenarios,
        journey_behaviors=journey_behaviors,
        journeys=journeys,
        journey_relationships=relationships,
        pr_title="Fix Password Reset Validation Expiry Flow",
        pr_description="This PR modifies the password reset API to strictly validate and reject expired recovery tokens.",
    )
    
    print("Behavior Impact Snapshot Output:")
    print(f"  - Repository ID: {snapshot['repository_id']}")
    print(f"  - Pull Request ID: {snapshot['pull_request_id']}")
    print(f"  - Confidence: {snapshot['confidence']}")
    print(f"  - Impact Summary: {snapshot['impact_summary']}")
    
    print("\nImpacted Behaviors:")
    for b in snapshot["impacted_behaviors"]:
        print(f"  - {b['behavior_name']} ({b['impact_level']} risk, confidence: {b['confidence']})")
        print(f"    Impact Reason: {b['impact_reason']}")
        print(f"    Impacted Files: {b['impacted_files']}")
        print(f"    Signals matched: {b['source_signals']}")
        print(f"    Affected Scenarios: {[s['title'] for s in b['affected_scenarios']]}")
        
    print("\nImpacted Journeys:")
    for j in snapshot["impacted_journeys"]:
        print(f"  - {j['journey_name']}")
        
    # Assertions
    pwd_reset_impact = next((b for b in snapshot["impacted_behaviors"] if b["behavior_name"] == "Password Reset"), None)
    assert pwd_reset_impact is not None, "Expected Password Reset to be impacted"
    assert pwd_reset_impact["impact_level"] in ["HIGH", "CRITICAL"], "Expected Password Reset impact risk to be high"
    assert "DIRECT_EVIDENCE" in pwd_reset_impact["source_signals"], "Expected DIRECT_EVIDENCE signal"
    
    # Password Reset behavior belongs to Authentication journey
    assert any(j["journey_name"] == "Authentication" for j in snapshot["impacted_journeys"]), "Expected Authentication journey to be impacted"
    
    print("\n[PASS] BehaviorImpactAnalyzer resolved Password Reset and Authentication journey correctly.")
    
    # 3. Analyze PR changing subscription (billing) to verify relationship expansion
    print("\n\nTest 3: Analyzing PR changing subscription (Billing -> Authentication dependency)")
    print("-" * 60)
    
    changed_files = ["billing/subscription/service.py"]
    
    snapshot_sub = analyzer.analyze_behavior_impact(
        repository_id=uuid.uuid4(),
        pull_request_id=uuid.uuid4(),
        changed_files=changed_files,
        behaviors=behaviors,
        behavior_evidences=evidences,
        behavior_scenarios=scenarios,
        journey_behaviors=journey_behaviors,
        journeys=journeys,
        journey_relationships=relationships,
        pr_title="Update Premium Plan Subscription webhooks",
        pr_description="Add webhook notification dispatch limits",
    )
    
    print("\nImpacted Behaviors:")
    for b in snapshot_sub["impacted_behaviors"]:
        print(f"  - {b['behavior_name']} ({b['impact_level']} risk, confidence: {b['confidence']})")
        
    print("\nImpacted Journeys:")
    for j in snapshot_sub["impacted_journeys"]:
        print(f"  - {j['journey_name']}")
        
    # Assertions for subscription
    assert len(snapshot_sub["impacted_behaviors"]) == 1, "Expected Subscription behavior to be impacted"
    assert snapshot_sub["impacted_behaviors"][0]["behavior_name"] == "Subscription"
    
    # Billing journey impacts Authentication journey because Billing DEPENDS_ON Authentication
    assert any(j["journey_name"] == "Billing" for j in snapshot_sub["impacted_journeys"])
    assert any(j["journey_name"] == "Authentication" for j in snapshot_sub["impacted_journeys"]), "Expected relationship to expand impact to Authentication journey"
    
    print("\n[PASS] Journey relationship expanded impact successfully.")
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    test_behavior_impact_analyzer()
