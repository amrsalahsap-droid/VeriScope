"""
Test script for BehaviorCoverageGapGenerator.

Tests converting missing/partial coverage states into structured, actionable business-driven gaps.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.behavior_coverage_gap_generator import BehaviorCoverageGapGenerator


def test_behavior_coverage_gap_generator():
    """Verify conversion of resolved scenario coverages into actionable gaps."""
    print("=" * 60)
    print("BEHAVIOR COVERAGE GAP GENERATOR TEST")
    print("=" * 60)
    
    generator = BehaviorCoverageGapGenerator()
    
    # Setup analyzed coverage list
    behavior_coverages = [
        {
            "behavior_id": "b1",
            "behavior_name": "Password Reset",
            "scenarios": [
                # Verified: Should NOT generate a gap
                {
                    "scenario_id": "s1",
                    "title": "Validate password reset expired token rejection",
                    "priority": "MUST",
                    "coverage_status": "VERIFIED_ON_CURRENT_PR",
                    "confidence": "HIGH",
                    "reason": "Successfully run",
                    "existing_tests": [{"test_identifier": "auth.reset::test_expired_token"}],
                    "coverage_support": [],
                },
                # Covered historically: RUN_EXISTING_TEST, not ADD_TEST
                {
                    "scenario_id": "s2",
                    "title": "Validate reset flow password complexity rules",
                    "priority": "MUST",
                    "coverage_status": "COVERED_BY_EXISTING_TEST",
                    "confidence": "HIGH",
                    "reason": "Covered historically",
                    "existing_tests": [{"test_identifier": "auth.reset::test_password_reset_complexity_validation"}],
                    "coverage_support": [],
                },
                # Partially covered (files only): BIND_EXISTING_TEST
                {
                    "scenario_id": "s3",
                    "title": "Validate reset flow UI styling layout",
                    "priority": "SHOULD",
                    "coverage_status": "PARTIALLY_COVERED",
                    "confidence": "MODERATE",
                    "reason": "Files touched",
                    "existing_tests": [],
                    "coverage_support": [{"file_path": "pages/auth/reset-password.tsx", "support_type": "DIRECT_FILE", "confidence": "HIGH"}],
                },
                # Missing (high-risk): MANUAL_VALIDATION_RECOMMENDED
                {
                    "scenario_id": "s4",
                    "title": "Validate reset webhook trigger dispatch",
                    "priority": "SHOULD",
                    "coverage_status": "MANUAL_VALIDATION_RECOMMENDED",
                    "confidence": "LOW",
                    "reason": "Missing coverage",
                    "suggested_action": "Execute Manual Checkout Validation: Verify 'Validate reset webhook trigger dispatch' immediately",
                    "existing_tests": [],
                    "coverage_support": [],
                },
                # Missing (low-risk Edge case): MISSING_EDGE_CASE -> ADD_AUTOMATED_TEST
                {
                    "scenario_id": "s5",
                    "title": "Validate resets on trailing dots emails",
                    "priority": "OPTIONAL",
                    "scenario_type": "EDGE",
                    "coverage_status": "MISSING_AUTOMATED_COVERAGE",
                    "confidence": "LOW",
                    "reason": "Missing",
                    "existing_tests": [],
                    "coverage_support": [],
                }
            ]
        }
    ]
    
    # Generate gaps
    gaps = generator.generate_coverage_gaps(behavior_coverages)
    
    print(f"Generated {len(gaps)} actionable gaps:")
    for gap in gaps:
        print(f"\n  - Scenario: '{gap['scenario_title']}'")
        print(f"    Gap Type: {gap['gap_type']}")
        print(f"    Priority: {gap['priority']}")
        print(f"    Suggested Action: {gap['suggested_action']}")
        print(f"    Reason: {gap['reason']}")
        print(f"    Related Files: {gap['related_changed_files']}")
        print(f"    Existing Tests: {gap['existing_related_tests']}")
        
    # Assertions
    # Verified should not be in gaps
    assert not any(g["scenario_title"] == "Validate password reset expired token rejection" for g in gaps)
    
    # Historic covered maps to NO_CURRENT_PR_EXECUTION / RUN_EXISTING_TEST
    g2 = next((g for g in gaps if g["scenario_title"] == "Validate reset flow password complexity rules"), None)
    assert g2 is not None
    assert g2["gap_type"] == "NO_CURRENT_PR_EXECUTION"
    assert "RUN_EXISTING_TEST" in g2["suggested_action"]
    
    # Partial coverage maps to PARTIAL_TEST_COVERAGE / BIND_EXISTING_TEST
    g3 = next((g for g in gaps if g["scenario_title"] == "Validate reset flow UI styling layout"), None)
    assert g3 is not None
    assert g3["gap_type"] == "PARTIAL_TEST_COVERAGE"
    assert "BIND_EXISTING_TEST" in g3["suggested_action"]
    
    # Missing high-risk maps to MANUAL_VALIDATION_RECOMMENDED
    g4 = next((g for g in gaps if g["scenario_title"] == "Validate reset webhook trigger dispatch"), None)
    assert g4 is not None
    assert g4["gap_type"] == "NO_EXISTING_TEST"
    assert "Execute Manual Checkout Validation" in g4["suggested_action"]
    
    # Edge case missing maps to MISSING_EDGE_CASE
    g5 = next((g for g in gaps if g["scenario_title"] == "Validate resets on trailing dots emails"), None)
    assert g5 is not None
    assert g5["gap_type"] == "MISSING_EDGE_CASE"
    assert "ADD_AUTOMATED_TEST" in g5["suggested_action"]
    
    # Ensure no duplicates
    assert len(gaps) == 4, "Expected exactly 4 gaps"
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    test_behavior_coverage_gap_generator()
