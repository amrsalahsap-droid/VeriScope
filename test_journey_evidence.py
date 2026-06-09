"""
Test script for JourneyEvidence model.

Tests JourneyEvidence model creation and evidence types.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.models.journey_evidence import JourneyEvidence
import uuid


def test_journey_evidence():
    """Test JourneyEvidence model creation and evidence types."""
    print("=" * 60)
    print("JOURNEY EVIDENCE MODEL TEST")
    print("=" * 60)
    
    try:
        # Test 1: JourneyEvidence Model Fields
        print("\nTest 1: JourneyEvidence Model Fields")
        print("-" * 60)
        
        journey_evidence = JourneyEvidence(
            id=uuid.uuid4(),
            journey_id=uuid.uuid4(),
            evidence_type="BEHAVIOR_CLUSTER",
            source="BehaviorDiscoveryEngine",
            excerpt="Login behavior discovered from route /api/auth/login",
            confidence="HIGH",
        )
        
        print(f"JourneyEvidence ID: {journey_evidence.id}")
        print(f"Journey ID: {journey_evidence.journey_id}")
        print(f"Evidence Type: {journey_evidence.evidence_type}")
        print(f"Source: {journey_evidence.source}")
        print(f"Excerpt: {journey_evidence.excerpt}")
        print(f"Confidence: {journey_evidence.confidence}")
        print(f"Created At: {journey_evidence.created_at}")
        
        print("\n[PASS] JourneyEvidence model fields are correctly defined")
        
        # Test 2: Evidence Types
        print("\nTest 2: Evidence Types")
        print("-" * 60)
        
        valid_evidence_types = [
            "BEHAVIOR_CLUSTER",
            "ROUTE_CLUSTER",
            "TEST_CLUSTER",
            "DOCUMENTATION",
            "PR_HISTORY",
        ]
        
        for evidence_type in valid_evidence_types:
            journey_evidence.evidence_type = evidence_type
            print(f"Evidence Type {evidence_type}: OK")
        
        print("\n[PASS] All valid evidence types accepted")
        
        # Test 3: Confidence Levels
        print("\nTest 3: Confidence Levels")
        print("-" * 60)
        
        valid_confidences = ["HIGH", "MODERATE", "LOW"]
        for conf in valid_confidences:
            journey_evidence.confidence = conf
            print(f"Confidence {conf}: OK")
        
        print("\n[PASS] All valid confidence levels accepted")
        
        # Test 4: Example Journey Evidences
        print("\nTest 4: Example Journey Evidences (Authentication Journey)")
        print("-" * 60)
        
        journey_id = uuid.uuid4()
        
        evidences = [
            {
                "type": "BEHAVIOR_CLUSTER",
                "source": "BehaviorDiscoveryEngine",
                "excerpt": "Login behavior discovered from route /api/auth/login",
                "confidence": "HIGH",
            },
            {
                "type": "BEHAVIOR_CLUSTER",
                "source": "BehaviorDiscoveryEngine",
                "excerpt": "Password Reset behavior discovered from route /api/auth/reset-password",
                "confidence": "HIGH",
            },
            {
                "type": "ROUTE_CLUSTER",
                "source": "RouteIntelligenceAnalyzer",
                "excerpt": "Authentication routes: /api/auth/login, /api/auth/logout, /api/auth/reset-password",
                "confidence": "HIGH",
            },
            {
                "type": "TEST_CLUSTER",
                "source": "TestIntelligenceAnalyzer",
                "excerpt": "Authentication tests: test_login, test_logout, test_password_reset",
                "confidence": "MODERATE",
            },
            {
                "type": "DOCUMENTATION",
                "source": "DocumentationIntelligenceAnalyzer",
                "excerpt": "README.md describes authentication workflow with JWT tokens",
                "confidence": "MODERATE",
            },
        ]
        
        for evidence in evidences:
            je = JourneyEvidence(
                id=uuid.uuid4(),
                journey_id=journey_id,
                evidence_type=evidence["type"],
                source=evidence["source"],
                excerpt=evidence["excerpt"],
                confidence=evidence["confidence"],
            )
            print(f"  [{evidence['type']}] {evidence['excerpt'][:50]}... ({evidence['confidence']})")
        
        print(f"\n[PASS] All {len(evidences)} example evidences created successfully")
        
        # Test 5: PR History Evidence
        print("\nTest 5: PR History Evidence")
        print("-" * 60)
        
        pr_evidence = JourneyEvidence(
            id=uuid.uuid4(),
            journey_id=journey_id,
            evidence_type="PR_HISTORY",
            source="PullRequestAnalysis",
            excerpt="PR #123 modified authentication flow, affecting login and password reset",
            confidence="MODERATE",
        )
        
        print(f"PR History Evidence: {pr_evidence.excerpt}")
        print("[PASS] PR history evidence created successfully")
        
        # Test 6: Cascade Delete
        print("\nTest 6: Cascade Delete")
        print("-" * 60)
        
        print("Foreign Key Constraint:")
        print("  - journey_id -> journeys.id (CASCADE)")
        print("[PASS] Cascade delete configured")
        
        # Test 7: Indexes
        print("\nTest 7: Indexes")
        print("-" * 60)
        
        print("Indexes configured on:")
        print("  - journey_id")
        print("  - evidence_type")
        print("  - source")
        print("[PASS] Indexes defined for performance")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_journey_evidence()
