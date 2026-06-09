"""
Test script for DocumentationIntelligenceAnalyzer.

Tests documentation inference examples:
- "Users can reset passwords" → Password Reset
- "Supports subscription billing" → Subscription Management
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.documentation_intelligence_analyzer import DocumentationIntelligenceAnalyzer


def test_documentation_inference():
    """Test documentation inference without database (using fallback patterns)."""
    print("=" * 60)
    print("DOCUMENTATION INTELLIGENCE ANALYZER TEST")
    print("=" * 60)
    
    # Initialize analyzer without database (will use fallback patterns)
    analyzer = DocumentationIntelligenceAnalyzer(db=None)
    
    # Sample documentation content
    readme_content = """
# Application Features

Features:
- Users can reset passwords via email
- Supports subscription billing with Stripe
- Allows users to register new accounts
- Provides authentication with JWT tokens
- Sends email notifications for important events

Capabilities:
- User profile management
- Password recovery flow
- Subscription plan management
- Session-based authentication
- Multi-factor authentication support
"""
    
    adr_content = """
# ADR: Authentication System

We support multiple authentication methods:
- JWT token-based authentication
- Session-based authentication
- OAuth integration
- Password reset functionality
"""
    
    print("\nTesting README analysis:")
    print("-" * 60)
    readme_evidences = analyzer.analyze_document("README.md", readme_content, "README")
    print(f"Total evidences: {len(readme_evidences)}")
    
    for evidence in readme_evidences:
        print(f"[MATCH] Line {evidence.line_number}")
        print(f"  -> Behavior: {evidence.behavior}")
        print(f"  -> Confidence: {evidence.confidence}")
        print(f"  -> Document Type: {evidence.document_type}")
        print(f"  -> Matched Alias: {evidence.matched_alias or 'N/A'}")
        print(f"  -> Excerpt: {evidence.excerpt[:80]}...")
        print()
    
    print("\nTesting ADR analysis:")
    print("-" * 60)
    adr_evidences = analyzer.analyze_document("docs/adr/001-authentication.md", adr_content, "ADR")
    print(f"Total evidences: {len(adr_evidences)}")
    
    for evidence in adr_evidences:
        print(f"[MATCH] Line {evidence.line_number}")
        print(f"  -> Behavior: {evidence.behavior}")
        print(f"  -> Confidence: {evidence.confidence}")
        print(f"  -> Document Type: {evidence.document_type}")
        print(f"  -> Matched Alias: {evidence.matched_alias or 'N/A'}")
        print(f"  -> Excerpt: {evidence.excerpt[:80]}...")
        print()
    
    # Test specific lines
    print("\nTesting specific lines:")
    print("-" * 60)
    test_lines = [
        "Users can reset passwords via email",
        "Supports subscription billing with Stripe",
        "Allows users to register new accounts",
        "Provides authentication with JWT tokens",
        "Sends email notifications for important events",
    ]
    
    for line in test_lines:
        evidence = analyzer.analyze_line(line, "README.md", "README")
        if evidence:
            print(f"[MATCH] {line[:60]}...")
            print(f"  -> Behavior: {evidence.behavior}")
            print(f"  -> Confidence: {evidence.confidence}")
        else:
            print(f"[NO MATCH] {line[:60]}...")
        print()
    
    # Combined analysis
    print("\nCombined analysis:")
    print("-" * 60)
    all_evidences = readme_evidences + adr_evidences
    print(f"Total evidences: {len(all_evidences)}")
    
    counts = analyzer.get_behavior_counts(all_evidences)
    print("Behavior counts:")
    for behavior, count in counts.items():
        print(f"  {behavior}: {count}")
    
    high_conf = analyzer.get_high_confidence_evidences(all_evidences)
    print(f"\nHigh confidence evidences: {len(high_conf)}")
    for evidence in high_conf:
        print(f"  - {evidence.behavior}: {evidence.excerpt[:60]}...")
    
    grouped = analyzer.get_evidences_by_document_type(all_evidences)
    print(f"\nEvidences by document type:")
    for doc_type, type_evidences in grouped.items():
        print(f"  {doc_type}: {len(type_evidences)}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_documentation_inference()
