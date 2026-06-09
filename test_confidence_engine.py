"""
Test script for BehaviorConfidenceEngine.

Tests explainable confidence calculation with examples.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.behavior_confidence_engine import BehaviorConfidenceEngine, ConfidenceBreakdown
from dataclasses import dataclass


# Mock evidence class for testing
@dataclass
class MockEvidence:
    source_type: str
    source_identifier: str
    confidence: str
    metadata: dict = None


def test_confidence_engine():
    """Test confidence engine with Password Reset example."""
    print("=" * 60)
    print("BEHAVIOR CONFIDENCE ENGINE TEST")
    print("=" * 60)
    
    # Initialize confidence engine
    engine = BehaviorConfidenceEngine(db=None)
    
    # Test Case 1: Password Reset with route, page, test (HIGH confidence)
    print("\nTest Case 1: Password Reset (Route + Page + Test)")
    print("-" * 60)
    
    password_reset_evidences = [
        MockEvidence(
            source_type="ROUTE",
            source_identifier="Password Reset",
            confidence="HIGH",
            metadata={"matched_alias": "reset-password"},
        ),
        MockEvidence(
            source_type="PAGE",
            source_identifier="Password Reset",
            confidence="HIGH",
            metadata={"matched_alias": "reset-password"},
        ),
        MockEvidence(
            source_type="TEST",
            source_identifier="Password Reset",
            confidence="HIGH",
            metadata={"matched_alias": "password"},
        ),
    ]
    
    breakdown = engine.calculate_confidence(
        password_reset_evidences,
        repository_total_files=100,
        repository_behavior_files=5,
    )
    
    print(f"Total Score: {breakdown.total_score:.2f}")
    print(f"Confidence Level: {breakdown.confidence_level}")
    print(f"\nComponent Scores:")
    print(f"  Evidence Count: {breakdown.evidence_count_score:.2f} (weight: {engine.EVIDENCE_COUNT_WEIGHT})")
    print(f"  Diversity: {breakdown.evidence_diversity_score:.2f} (weight: {engine.EVIDENCE_DIVERSITY_WEIGHT})")
    print(f"  Pattern Quality: {breakdown.pattern_quality_score:.2f} (weight: {engine.PATTERN_QUALITY_WEIGHT})")
    print(f"  Repository Coverage: {breakdown.repository_coverage_score:.2f} (weight: {engine.REPOSITORY_COVERAGE_WEIGHT})")
    print(f"\nDetails:")
    print(f"  Evidence Count: {breakdown.evidence_count}")
    print(f"  High Confidence Evidence: {breakdown.high_confidence_evidence_count}")
    print(f"  Evidence Sources: {breakdown.evidence_sources}")
    print(f"  Pattern Match Type: {breakdown.pattern_match_type}")
    print(f"  Coverage Percentage: {breakdown.coverage_percentage:.1f}%")
    
    print(f"\nExplanation:")
    print(engine.explain_confidence(breakdown))
    
    # Test Case 2: Low confidence behavior (single evidence)
    print("\n\nTest Case 2: Low Confidence (Single Evidence)")
    print("-" * 60)
    
    low_conf_evidences = [
        MockEvidence(
            source_type="MODULE",
            source_identifier="TestBehavior",
            confidence="LOW",
            metadata={"matched_alias": "test"},
        ),
    ]
    
    breakdown = engine.calculate_confidence(
        low_conf_evidences,
        repository_total_files=100,
        repository_behavior_files=1,
    )
    
    print(f"Total Score: {breakdown.total_score:.2f}")
    print(f"Confidence Level: {breakdown.confidence_level}")
    print(f"\nComponent Scores:")
    print(f"  Evidence Count: {breakdown.evidence_count_score:.2f}")
    print(f"  Diversity: {breakdown.evidence_diversity_score:.2f}")
    print(f"  Pattern Quality: {breakdown.pattern_quality_score:.2f}")
    print(f"  Repository Coverage: {breakdown.repository_coverage_score:.2f}")
    
    print(f"\nExplanation:")
    print(engine.explain_confidence(breakdown))
    
    # Test Case 3: Medium confidence (multiple sources, moderate count)
    print("\n\nTest Case 3: Medium Confidence (Multiple Sources)")
    print("-" * 60)
    
    medium_conf_evidences = [
        MockEvidence(
            source_type="ROUTE",
            source_identifier="Authentication",
            confidence="MODERATE",
            metadata={"matched_alias": "auth"},
        ),
        MockEvidence(
            source_type="TEST",
            source_identifier="Authentication",
            confidence="MODERATE",
            metadata={"matched_alias": "login"},
        ),
        MockEvidence(
            source_type="MODULE",
            source_identifier="Authentication",
            confidence="MODERATE",
            metadata={"matched_alias": "auth"},
        ),
    ]
    
    breakdown = engine.calculate_confidence(
        medium_conf_evidences,
        repository_total_files=100,
        repository_behavior_files=3,
    )
    
    print(f"Total Score: {breakdown.total_score:.2f}")
    print(f"Confidence Level: {breakdown.confidence_level}")
    print(f"\nComponent Scores:")
    print(f"  Evidence Count: {breakdown.evidence_count_score:.2f}")
    print(f"  Diversity: {breakdown.evidence_diversity_score:.2f}")
    print(f"  Pattern Quality: {breakdown.pattern_quality_score:.2f}")
    print(f"  Repository Coverage: {breakdown.repository_coverage_score:.2f}")
    
    print(f"\nExplanation:")
    print(engine.explain_confidence(breakdown))
    
    # Test Case 4: Maximum confidence (all sources, high count)
    print("\n\nTest Case 4: Maximum Confidence (All Sources)")
    print("-" * 60)
    
    max_conf_evidences = [
        MockEvidence("ROUTE", "Billing", "HIGH", {"matched_alias": "billing"}),
        MockEvidence("TEST", "Billing", "HIGH", {"matched_alias": "subscription"}),
        MockEvidence("MODULE", "Billing", "HIGH", {"matched_alias": "billing"}),
        MockEvidence("DOCUMENTATION", "Billing", "HIGH", {"matched_alias": "billing"}),
        MockEvidence("PAGE", "Billing", "HIGH", {"matched_alias": "billing"}),
        MockEvidence("SERVICE", "Billing", "HIGH", {"matched_alias": "subscription"}),
    ]
    
    breakdown = engine.calculate_confidence(
        max_conf_evidences,
        repository_total_files=100,
        repository_behavior_files=10,
    )
    
    print(f"Total Score: {breakdown.total_score:.2f}")
    print(f"Confidence Level: {breakdown.confidence_level}")
    print(f"\nComponent Scores:")
    print(f"  Evidence Count: {breakdown.evidence_count_score:.2f}")
    print(f"  Diversity: {breakdown.evidence_diversity_score:.2f}")
    print(f"  Pattern Quality: {breakdown.pattern_quality_score:.2f}")
    print(f"  Repository Coverage: {breakdown.repository_coverage_score:.2f}")
    
    print(f"\nExplanation:")
    print(engine.explain_confidence(breakdown))
    
    # Test serialization
    print("\n\nTest: Breakdown Serialization")
    print("-" * 60)
    breakdown_dict = breakdown.to_dict()
    print(f"Serialized breakdown keys: {list(breakdown_dict.keys())}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_confidence_engine()
