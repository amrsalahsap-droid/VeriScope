"""
Test script for RouteIntelligenceAnalyzer.

Tests route inference examples:
- /reset-password → Password Reset
- /signup → User Registration
- /login → Authentication
- /subscriptions → Subscription Management
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.route_intelligence_analyzer import RouteIntelligenceAnalyzer


def test_route_inference():
    """Test route inference without database (using fallback patterns)."""
    print("=" * 60)
    print("ROUTE INTELLIGENCE ANALYZER TEST")
    print("=" * 60)
    
    # Initialize analyzer without database (will use fallback patterns)
    analyzer = RouteIntelligenceAnalyzer(db=None)
    
    # Test routes
    test_routes = [
        "/reset-password",
        "/signup",
        "/login",
        "/subscriptions",
        "POST /api/auth/login",
        "GET /api/v1/billing/subscriptions",
        "/forgot-password",
        "/register",
        "/auth/token",
    ]
    
    print("\nTesting route inference:")
    print("-" * 60)
    
    for route in test_routes:
        # Extract method and path
        http_method, route_path = analyzer._extract_method_and_path(route)
        
        # Analyze route
        evidence = analyzer.analyze_route(route_path, http_method)
        
        if evidence:
            print(f"[MATCH] {route}")
            print(f"  -> Behavior: {evidence.behavior}")
            print(f"  -> Confidence: {evidence.confidence}")
            print(f"  -> Method: {evidence.http_method or 'N/A'}")
            print(f"  -> Matched Alias: {evidence.matched_alias or 'N/A'}")
        else:
            print(f"[NO MATCH] {route}")
        print()
    
    # Test batch analysis
    print("\nBatch analysis:")
    print("-" * 60)
    evidences = analyzer.analyze_routes(test_routes)
    print(f"Total evidences: {len(evidences)}")
    
    counts = analyzer.get_behavior_counts(evidences)
    print("Behavior counts:")
    for behavior, count in counts.items():
        print(f"  {behavior}: {count}")
    
    high_conf = analyzer.get_high_confidence_evidences(evidences)
    print(f"\nHigh confidence evidences: {len(high_conf)}")
    for evidence in high_conf:
        print(f"  - {evidence.behavior}: {evidence.route}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_route_inference()
