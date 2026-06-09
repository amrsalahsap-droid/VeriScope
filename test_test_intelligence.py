"""
Test script for TestIntelligenceAnalyzer.

Tests test inference examples:
- should_reject_expired_token → Password Reset / Authentication
- should_allow_valid_token → Authentication
- should_create_subscription → Billing
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.test_intelligence_analyzer import TestIntelligenceAnalyzer


def test_test_inference():
    """Test test inference without database (using fallback patterns)."""
    print("=" * 60)
    print("TEST INTELLIGENCE ANALYZER TEST")
    print("=" * 60)
    
    # Initialize analyzer without database (will use fallback patterns)
    analyzer = TestIntelligenceAnalyzer(db=None)
    
    # Test names
    test_names = [
        "should_reject_expired_token",
        "should_allow_valid_token",
        "should_create_subscription",
        "test_password_reset_flow",
        "test_user_registration_success",
        "test_login_with_valid_credentials",
        "should_cancel_subscription",
        "test_send_notification_email",
        "e2e_billing_checkout_flow",
        "integration_auth_session_management",
    ]
    
    print("\nTesting test inference:")
    print("-" * 60)
    
    for test_name in test_names:
        # Analyze test
        evidence = analyzer.analyze_test(test_name)
        
        if evidence:
            print(f"[MATCH] {test_name}")
            print(f"  -> Behavior: {evidence.behavior}")
            print(f"  -> Confidence: {evidence.confidence}")
            print(f"  -> Test Type: {evidence.test_type or 'N/A'}")
            print(f"  -> Matched Alias: {evidence.matched_alias or 'N/A'}")
            print(f"  -> Tokens: {evidence.normalized_tokens}")
        else:
            print(f"[NO MATCH] {test_name}")
        print()
    
    # Test batch analysis
    print("\nBatch analysis:")
    print("-" * 60)
    evidences = analyzer.analyze_tests(test_names)
    print(f"Total evidences: {len(evidences)}")
    
    counts = analyzer.get_behavior_counts(evidences)
    print("Behavior counts:")
    for behavior, count in counts.items():
        print(f"  {behavior}: {count}")
    
    high_conf = analyzer.get_high_confidence_evidences(evidences)
    print(f"\nHigh confidence evidences: {len(high_conf)}")
    for evidence in high_conf:
        print(f"  - {evidence.behavior}: {evidence.test_identifier}")
    
    grouped = analyzer.get_evidences_by_test_type(evidences)
    print(f"\nEvidences by test type:")
    for test_type, type_evidences in grouped.items():
        print(f"  {test_type}: {len(type_evidences)}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_test_inference()
