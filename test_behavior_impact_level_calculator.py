"""
Test script for BehaviorImpactLevelCalculator.

Tests converting code metadata and matches into exact risk-calibrated impact levels.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.behavior_impact_level_calculator import BehaviorImpactLevelCalculator


def test_behavior_impact_level_calculator():
    """Verify impact level calculations across risk, file type, status, and layer scenarios."""
    print("=" * 60)
    print("BEHAVIOR IMPACT LEVEL CALCULATOR TEST")
    print("=" * 60)
    
    calculator = BehaviorImpactLevelCalculator()
    
    # Test 1: Password Reset API change becomes HIGH
    print("\nTest 1: Password Reset API Change")
    print("-" * 60)
    
    res1 = calculator.calculate_impact_level(
        behavior_name="Password Reset",
        behavior_risk_level="HIGH",
        impacted_files=["src/app/api/auth/reset-password/route.ts"],
        touched_layers=["API"],
        related_journey_risk="HIGH",
        security_sensitivity=True,
        historical_fragility=True,
        match_signal_type="ROUTE_PAGE_MODULE",
    )
    
    print(f"Impact Level: {res1['impact_level']} (expected HIGH)")
    print(f"Reason: {res1['impact_reason']}")
    print(f"Confidence: {res1['confidence']}")
    assert res1["impact_level"] == "HIGH", "Expected Password Reset API change to be HIGH"
    
    # Test 2: Signup Form Validation Change becomes MEDIUM
    print("\n\nTest 2: Signup Form Validation Change")
    print("-" * 60)
    
    res2 = calculator.calculate_impact_level(
        behavior_name="User Registration",
        behavior_risk_level="MEDIUM",
        impacted_files=["src/app/signup/signup-form.tsx"],
        touched_layers=["UI"],
        related_journey_risk="HIGH",
        security_sensitivity=False,
        historical_fragility=False,
        match_signal_type="TOKEN_MATCH",
    )
    
    print(f"Impact Level: {res2['impact_level']} (expected MEDIUM)")
    print(f"Reason: {res2['impact_reason']}")
    print(f"Confidence: {res2['confidence']}")
    assert res2["impact_level"] == "MEDIUM", "Expected Signup UI validation change to be MEDIUM"
    
    # Test 3: Tests-only Change becomes LOW
    print("\n\nTest 3: Tests-only Change")
    print("-" * 60)
    
    res3 = calculator.calculate_impact_level(
        behavior_name="Password Reset",
        behavior_risk_level="HIGH",
        impacted_files=["tests/test_password_reset.py"],
        touched_layers=[],
        related_journey_risk="HIGH",
        security_sensitivity=False,
        historical_fragility=False,
        match_signal_type="TOKEN_MATCH",
    )
    
    print(f"Impact Level: {res3['impact_level']} (expected LOW)")
    print(f"Reason: {res3['impact_reason']}")
    print(f"Confidence: {res3['confidence']}")
    assert res3["impact_level"] == "LOW", "Expected tests-only changes to be LOW"
    
    # Test 4: Critical Core Business Change becomes CRITICAL
    print("\n\nTest 4: Billing Core Backend Logic Change")
    print("-" * 60)
    
    res4 = calculator.calculate_impact_level(
        behavior_name="Subscription Billing",
        behavior_risk_level="CRITICAL",
        impacted_files=["src/services/billing/charge_processor.py"],
        touched_layers=["DATABASE", "SERVICE"],
        related_journey_risk="CRITICAL",
        security_sensitivity=True,
        historical_fragility=True,
        match_signal_type="DIRECT_EVIDENCE",
    )
    
    print(f"Impact Level: {res4['impact_level']} (expected CRITICAL)")
    print(f"Reason: {res4['impact_reason']}")
    print(f"Confidence: {res4['confidence']}")
    assert res4["impact_level"] == "CRITICAL", "Expected core subscription logic changes to be CRITICAL"
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    test_behavior_impact_level_calculator()
