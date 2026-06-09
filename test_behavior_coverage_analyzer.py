"""
Test script for BehaviorCoverageAnalyzer.

Tests scenario-level coverage truth calculations, precedence hierarchies, and missing high-risk scenario rules.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.behavior_coverage_analyzer import BehaviorCoverageAnalyzer
from app.models.behavior_scenario import BehaviorScenario
from dataclasses import dataclass
import uuid


@dataclass
class MockScenario:
    id: str
    behavior_id: str
    title: str
    priority: str


def test_behavior_coverage_analyzer():
    """Verify precise scenario coverage truth resolution and suggested actions."""
    print("=" * 60)
    print("BEHAVIOR COVERAGE ANALYZER TEST")
    print("=" * 60)
    
    analyzer = BehaviorCoverageAnalyzer(db=None)
    
    # 1. Setup mock models
    b_id = str(uuid.uuid4())
    impacted_behaviors = [
        {"behavior_id": b_id, "behavior_name": "Password Reset", "impact_level": "HIGH"},
    ]
    
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())
    s3_id = str(uuid.uuid4())
    s4_id = str(uuid.uuid4())
    
    scenarios = [
        MockScenario(id=s1_id, behavior_id=b_id, title="Validate password reset expired token rejection", priority="MUST"),
        MockScenario(id=s2_id, behavior_id=b_id, title="Validate reset flow password complexity rules", priority="MUST"),
        MockScenario(id=s3_id, behavior_id=b_id, title="Validate reset flow UI styling layout", priority="SHOULD"),
        MockScenario(id=s4_id, behavior_id=b_id, title="Validate reset webhook trigger dispatch", priority="SHOULD"),
    ]
    
    # Test Inputs:
    # Scenario 1: Mapped + Verified in Current PR (Rule: Verified on current PR outranks historical)
    # Scenario 2: Covered historically but NOT run in current PR (Rule: Covered historically, not verified)
    # Scenario 3: Mapped with code coverage only (Rule: Partial support)
    # Scenario 4: Missing entirely with high business impact (Rule: Missing high risk MUST suggest manual check)
    
    test_mappings = [
        # Historic mapping for Scenario 1
        {
            "test_identifier": "auth.reset::test_expired_token",
            "behavior_id": b_id,
            "behavior_scenario_id": s1_id,
            "confidence": "HIGH",
            "source_signal": "TEST_NAME_MAPPING",
        },
        # Historic mapping for Scenario 2
        {
            "test_identifier": "auth.reset::test_reset_password_complexity",
            "behavior_id": b_id,
            "behavior_scenario_id": s2_id,
            "confidence": "HIGH",
            "source_signal": "TEST_NAME_MAPPING",
        }
    ]
    
    coverage_supports = [
        # Coverage file support for Scenario 3
        {
            "behavior_id": b_id,
            "behavior_scenario_id": s3_id,
            "coverage_file_path": "pages/auth/reset-password.tsx",
            "support_type": "DIRECT_FILE",
            "confidence": "HIGH",
        }
    ]
    
    current_pr_runs = [
        # Executed test run on current PR verifying Scenario 1
        {
            "test_name": "test_password_reset_expired_token_rejection_passed",
            "status": "passed",
        }
    ]
    
    # Run analysis
    res = analyzer.analyze_behavior_coverage(
        impacted_behaviors=impacted_behaviors,
        scenarios=scenarios,
        test_mappings=test_mappings,
        coverage_supports=coverage_supports,
        current_pr_runs=current_pr_runs,
    )
    
    print(f"Discovered coverage analysis results:")
    assert len(res["behavior_coverages"]) == 1
    bc = res["behavior_coverages"][0]
    
    print(f"\nBehavior: {bc['behavior_name']}")
    print(f"  - Total Scenarios: {bc['total_scenarios']}")
    print(f"  - Covered Scenarios: {bc['covered_scenarios']}")
    print(f"  - Verified Scenarios: {bc['verified_on_current_pr']}")
    print(f"  - Partially Covered Scenarios: {bc['partially_covered_scenarios']}")
    print(f"  - Missing Scenarios: {bc['missing_scenarios']}")
    print(f"  - Coverage Score: {bc['coverage_score']:.1f}%")
    print(f"  - Confidence: {bc['coverage_confidence']}")
    print(f"  - Summary Reason: {bc['coverage_reason']}")
    
    print("\nScenario Coverage Detail:")
    for s in bc["scenarios"]:
        print(f"\n  - Title: '{s['title']}' ({s['priority']})")
        print(f"    Status: {s['coverage_status']}")
        print(f"    Confidence: {s['confidence']}")
        print(f"    Suggested Action: {s['suggested_action']}")
        print(f"    Reason: {s['reason']}")

    # Verification Assertions:
    
    # Assert Scenario 1: VERIFIED_ON_CURRENT_PR
    s1_out = next((s for s in bc["scenarios"] if s["scenario_id"] == s1_id), None)
    assert s1_out["coverage_status"] == "VERIFIED_ON_CURRENT_PR"
    assert s1_out["suggested_action"] == "None (Fully Verified)"
    
    # Assert Scenario 2: COVERED_BY_EXISTING_TEST
    s2_out = next((s for s in bc["scenarios"] if s["scenario_id"] == s2_id), None)
    assert s2_out["coverage_status"] == "COVERED_BY_EXISTING_TEST"
    assert s2_out["suggested_action"] == "Add test to current PR run scope"
    
    # Assert Scenario 3: PARTIALLY_COVERED
    s3_out = next((s for s in bc["scenarios"] if s["scenario_id"] == s3_id), None)
    assert s3_out["coverage_status"] == "PARTIALLY_COVERED"
    
    # Assert Scenario 4: MANUAL_VALIDATION_RECOMMENDED (MUST priority on HIGH impact behavior)
    s4_out = next((s for s in bc["scenarios"] if s["scenario_id"] == s4_id), None)
    assert s4_out["coverage_status"] == "MANUAL_VALIDATION_RECOMMENDED"
    assert "Execute Manual Checkout Validation" in s4_out["suggested_action"]

    # Assert Coverage Score (1 verified + 1 covered + 0.5 partial) / 4 = 62.5%
    assert abs(bc["coverage_score"] - 62.5) < 1e-5
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    test_behavior_coverage_analyzer()
