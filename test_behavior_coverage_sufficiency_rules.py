"""
Test script for BehaviorCoverageSufficiencyRules.

Tests sufficiency evaluation logic including SUFFICIENT, PARTIAL, INSUFFICIENT, and UNKNOWN states.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.behavior_coverage_sufficiency_rules import BehaviorCoverageSufficiencyRules


def test_behavior_coverage_sufficiency_rules():
    """Verify sufficiency calculations against policy rules and acceptance criteria."""
    print("=" * 60)
    print("BEHAVIOR COVERAGE SUFFICIENCY RULES TEST")
    print("=" * 60)
    
    evaluator = BehaviorCoverageSufficiencyRules()
    
    # Test Case 1: Auth/Password Reset with missing Token Reuse scenario MUST fail (INSUFFICIENT)
    print("\nTest 1: Password Reset with Missing MUST/BLOCKER Scenario")
    print("-" * 60)
    
    scenarios1 = [
        {"title": "Validate reset token reuse rejection", "priority": "MUST", "coverage_status": "MISSING_AUTOMATED_COVERAGE"},
        {"title": "Validate successful login session", "priority": "MUST", "coverage_status": "VERIFIED_ON_CURRENT_PR"},
    ]
    
    res1 = evaluator.evaluate_sufficiency(
        behavior_name="Password Reset",
        behavior_risk_level="HIGH",
        impact_level="HIGH",
        scenarios=scenarios1,
        coverage_confidence="HIGH",
    )
    
    print(f"Sufficiency: {res1['sufficiency']} (expected INSUFFICIENT)")
    print(f"Reason: {res1['sufficiency_reason']}")
    assert res1["sufficiency"] == "INSUFFICIENT"
    assert "MUST/BLOCKER scenario missing" in res1["sufficiency_reason"]
    
    # Test Case 2: Fully Covered scenario with HIGH confidence becomes SUFFICIENT
    print("\n\nTest 2: All MUST Scenarios Covered (SUFFICIENT)")
    print("-" * 60)
    
    scenarios2 = [
        {"title": "Validate reset token reuse rejection", "priority": "MUST", "coverage_status": "VERIFIED_ON_CURRENT_PR"},
        {"title": "Validate successful login session", "priority": "MUST", "coverage_status": "COVERED_BY_EXISTING_TEST"},
    ]
    
    res2 = evaluator.evaluate_sufficiency(
        behavior_name="Password Reset",
        behavior_risk_level="HIGH",
        impact_level="HIGH",
        scenarios=scenarios2,
        coverage_confidence="HIGH",
    )
    
    print(f"Sufficiency: {res2['sufficiency']} (expected SUFFICIENT)")
    print(f"Reason: {res2['sufficiency_reason']}")
    assert res2["sufficiency"] == "SUFFICIENT"
    
    # Test Case 3: Missing optional/SHOULD scenario becomes PARTIAL, not INSUFFICIENT
    print("\n\nTest 3: Missing Optional Scenario (PARTIAL)")
    print("-" * 60)
    
    scenarios3 = [
        {"title": "Validate reset token reuse rejection", "priority": "MUST", "coverage_status": "VERIFIED_ON_CURRENT_PR"},
        {"title": "Validate UI styling layout design", "priority": "SHOULD", "coverage_status": "MISSING_AUTOMATED_COVERAGE"},
    ]
    
    res3 = evaluator.evaluate_sufficiency(
        behavior_name="Password Reset",
        behavior_risk_level="HIGH",
        impact_level="HIGH",
        scenarios=scenarios3,
        coverage_confidence="HIGH",
    )
    
    print(f"Sufficiency: {res3['sufficiency']} (expected PARTIAL)")
    print(f"Reason: {res3['sufficiency_reason']}")
    assert res3["sufficiency"] == "PARTIAL"
    
    # Test Case 4: Cannot call sufficient from raw code coverage alone
    print("\n\nTest 4: Raw Code Coverage Only (PARTIAL)")
    print("-" * 60)
    
    scenarios4 = [
        {"title": "Validate reset token reuse rejection", "priority": "MUST", "coverage_status": "PARTIALLY_COVERED"},
    ]
    
    res4 = evaluator.evaluate_sufficiency(
        behavior_name="Password Reset",
        behavior_risk_level="MEDIUM",
        impact_level="MEDIUM",
        scenarios=scenarios4,
        coverage_confidence="HIGH",
        has_direct_code_coverage_only=True,
    )
    
    print(f"Sufficiency: {res4['sufficiency']} (expected PARTIAL)")
    print(f"Reason: {res4['sufficiency_reason']}")
    assert res4["sufficiency"] == "PARTIAL"
    assert "Code coverage alone cannot prove behavior" in res4["sufficiency_reason"] or "only backed by raw file-level" in res4["sufficiency_reason"]
    
    # Test Case 5: Low confidence degrades full SUFFICIENT into PARTIAL
    print("\n\nTest 5: Low Confidence Mappings (PARTIAL)")
    print("-" * 60)
    
    res5 = evaluator.evaluate_sufficiency(
        behavior_name="Password Reset",
        behavior_risk_level="HIGH",
        impact_level="HIGH",
        scenarios=scenarios2, # All covered but low confidence
        coverage_confidence="LOW",
    )
    
    print(f"Sufficiency: {res5['sufficiency']} (expected PARTIAL)")
    print(f"Reason: {res5['sufficiency_reason']}")
    assert res5["sufficiency"] == "PARTIAL"
    assert "Low coverage confidence prevents full" in res5["sufficiency_reason"]
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    test_behavior_coverage_sufficiency_rules()
