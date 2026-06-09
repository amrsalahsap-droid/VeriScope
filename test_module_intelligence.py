"""
Test script for ModuleIntelligenceAnalyzer.

Tests module inference examples:
- users/ → User Management
- subscriptions/ → Billing
- notifications/ → Notifications
- auth/ → Authentication
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.module_intelligence_analyzer import ModuleIntelligenceAnalyzer


def test_module_inference():
    """Test module inference without database (using fallback patterns)."""
    print("=" * 60)
    print("MODULE INTELLIGENCE ANALYZER TEST")
    print("=" * 60)
    
    # Initialize analyzer without database (will use fallback patterns)
    analyzer = ModuleIntelligenceAnalyzer(db=None)
    
    # Module names
    module_names = [
        "users/",
        "subscriptions/",
        "notifications/",
        "auth/",
        "services/auth/",
        "controllers/billing/",
        "services/user_management/",
        "services/password_reset/",
        "services/subscription/",
        "handlers/notification/",
    ]
    
    print("\nTesting module inference:")
    print("-" * 60)
    
    for module_name in module_names:
        # Analyze module
        evidence = analyzer.analyze_module(module_name)
        
        if evidence:
            print(f"[MATCH] {module_name}")
            print(f"  -> Behavior: {evidence.behavior}")
            print(f"  -> Confidence: {evidence.confidence}")
            print(f"  -> Module Type: {evidence.module_type or 'N/A'}")
            print(f"  -> Matched Alias: {evidence.matched_alias or 'N/A'}")
            print(f"  -> Tokens: {evidence.normalized_tokens}")
        else:
            print(f"[NO MATCH] {module_name}")
        print()
    
    # Test batch analysis
    print("\nBatch analysis:")
    print("-" * 60)
    evidences = analyzer.analyze_modules(module_names)
    print(f"Total evidences: {len(evidences)}")
    
    counts = analyzer.get_behavior_counts(evidences)
    print("Behavior counts:")
    for behavior, count in counts.items():
        print(f"  {behavior}: {count}")
    
    high_conf = analyzer.get_high_confidence_evidences(evidences)
    print(f"\nHigh confidence evidences: {len(high_conf)}")
    for evidence in high_conf:
        print(f"  - {evidence.behavior}: {evidence.module}")
    
    grouped = analyzer.get_evidences_by_module_type(evidences)
    print(f"\nEvidences by module type:")
    for module_type, type_evidences in grouped.items():
        print(f"  {module_type}: {len(type_evidences)}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_module_inference()
