"""
Test script for BehaviorEvidenceAggregator.

Tests evidence aggregation from all sources with confidence weighting.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.behavior_evidence_aggregator import BehaviorEvidenceAggregator, UnifiedEvidence
from dataclasses import dataclass


# Mock evidence classes for testing
@dataclass
class MockRouteEvidence:
    behavior: str
    route: str
    confidence: str
    http_method: str = None
    matched_alias: str = None


@dataclass
class MockTestEvidence:
    behavior: str
    test_identifier: str
    confidence: str
    test_type: str = None
    matched_alias: str = None
    normalized_tokens: list = None


@dataclass
class MockModuleEvidence:
    behavior: str
    module: str
    confidence: str
    module_type: str = None
    matched_alias: str = None
    normalized_tokens: list = None


@dataclass
class MockDocumentationEvidence:
    behavior: str
    source_document: str
    excerpt: str
    confidence: str
    document_type: str = None
    matched_alias: str = None
    line_number: int = None


@dataclass
class MockPageEvidence:
    behavior: str
    page: str
    confidence: str
    matched_alias: str = None


@dataclass
class MockServiceEvidence:
    behavior: str
    service: str
    confidence: str
    matched_alias: str = None


def test_evidence_aggregation():
    """Test evidence aggregation with mock data."""
    print("=" * 60)
    print("BEHAVIOR EVIDENCE AGGREGATOR TEST")
    print("=" * 60)
    
    # Initialize aggregator without database
    aggregator = BehaviorEvidenceAggregator(db=None)
    
    # Create mock route evidences
    route_evidences = [
        MockRouteEvidence("Authentication", "/api/auth/login", "HIGH", "POST", "auth"),
        MockRouteEvidence("Billing", "/api/billing/subscription", "HIGH", "POST", "subscription"),
        MockRouteEvidence("Password Reset", "/api/auth/reset-password", "HIGH", "POST", "reset-password"),
    ]
    
    # Create mock test evidences
    test_evidences = [
        MockTestEvidence("Authentication", "test_login_with_valid_credentials", "HIGH", "unit", "login", None),
        MockTestEvidence("Billing", "test_subscription_creation", "HIGH", "integration", "subscription", None),
        MockTestEvidence("Password Reset", "test_password_reset_flow", "HIGH", "e2e", "password", None),
        MockTestEvidence("User Registration", "test_user_registration_success", "HIGH", "unit", "register", None),
    ]
    
    # Create mock module evidences
    module_evidences = [
        MockModuleEvidence("Authentication", "services/auth/", "HIGH", "service", "auth", None),
        MockModuleEvidence("Billing", "services/billing/", "HIGH", "service", "billing", None),
        MockModuleEvidence("User Management", "services/user_management/", "HIGH", "service", "user", None),
    ]
    
    # Create mock documentation evidences
    documentation_evidences = [
        MockDocumentationEvidence("Authentication", "README.md", "Provides authentication with JWT tokens", "HIGH", "README", "auth", 8),
        MockDocumentationEvidence("Billing", "README.md", "Supports subscription billing with Stripe", "HIGH", "README", "billing", 6),
        MockDocumentationEvidence("Password Reset", "README.md", "Users can reset passwords via email", "HIGH", "README", "password", 5),
    ]
    
    # Create mock page evidences
    page_evidences = [
        MockPageEvidence("Authentication", "/login/page.tsx", "HIGH", "login"),
        MockPageEvidence("User Registration", "/signup/page.tsx", "HIGH", "signup"),
    ]
    
    # Create mock service evidences
    service_evidences = [
        MockServiceEvidence("Authentication", "AuthService", "HIGH", "auth"),
        MockServiceEvidence("Billing", "SubscriptionService", "HIGH", "subscription"),
    ]
    
    print("\nMock evidence counts:")
    print("-" * 60)
    print(f"Routes: {len(route_evidences)}")
    print(f"Tests: {len(test_evidences)}")
    print(f"Modules: {len(module_evidences)}")
    print(f"Documentation: {len(documentation_evidences)}")
    print(f"Pages: {len(page_evidences)}")
    print(f"Services: {len(service_evidences)}")
    
    # Aggregate evidence
    print("\nAggregating evidence...")
    print("-" * 60)
    candidates = aggregator.aggregate_evidence(
        route_evidences=route_evidences,
        test_evidences=test_evidences,
        module_evidences=module_evidences,
        documentation_evidences=documentation_evidences,
        page_evidences=page_evidences,
        service_evidences=service_evidences,
    )
    
    print(f"Total candidates: {len(candidates)}")
    
    # Display candidates
    print("\nBehavior Candidates:")
    print("-" * 60)
    for candidate in candidates:
        print(f"\nBehavior: {candidate.name}")
        print(f"  Journey: {candidate.journey or 'N/A'}")
        print(f"  Risk Level: {candidate.risk_level}")
        print(f"  Confidence: {candidate.confidence}")
        print(f"  Score: {candidate.source_confidence_score:.2f}")
        print(f"  Evidence Count: {len(candidate.evidences)}")
        
        source_counts = candidate.get_evidence_count_by_source()
        print(f"  Evidence by Source:")
        for source, count in source_counts.items():
            print(f"    {source}: {count}")
    
    # Get aggregation stats
    print("\nAggregation Statistics:")
    print("-" * 60)
    stats = aggregator.get_aggregation_stats(candidates)
    print(f"Total Candidates: {stats['total_candidates']}")
    print(f"Total Evidences: {stats['total_evidences']}")
    print(f"Average Score: {stats['average_score']:.2f}")
    print(f"By Confidence: {stats['by_confidence']}")
    print(f"By Source: {stats['by_source']}")
    
    # Verify confidence weighting
    print("\nConfidence Weighting Verification:")
    print("-" * 60)
    print("Source Weights:")
    for source, weight in aggregator.SOURCE_WEIGHTS.items():
        print(f"  {source}: {weight}")
    
    print("\nConfidence Values:")
    for level, value in aggregator.CONFIDENCE_VALUES.items():
        print(f"  {level}: {value}")
    
    print(f"\nThreshold: {aggregator.CONFIDENCE_THRESHOLD}")
    
    # Test threshold filtering
    print("\nThreshold Filtering Test:")
    print("-" * 60)
    low_score_candidate = UnifiedEvidence(
        source_type="SERVICE",
        source_identifier="TestBehavior",
        confidence="LOW",
    )
    low_score_candidates = aggregator.aggregate_evidence(
        service_evidences=[MockServiceEvidence("TestBehavior", "TestService", "LOW", "test")]
    )
    print(f"Low confidence candidate included: {len(low_score_candidates) > 0}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_evidence_aggregation()
