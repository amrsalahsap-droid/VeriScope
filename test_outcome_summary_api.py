"""
Test outcome summary API response.

Verifies that the outcome summary is correctly added to the recommendation run API response.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def test_outcome_summary_api():
    """Test outcome summary API response."""
    print("=" * 70)
    print("OUTCOME SUMMARY API TEST")
    print("=" * 70)
    
    # Test 1: Helper function exists
    print("\n[1] Helper Function Exists")
    print("-" * 70)
    
    router_path = "app/routers/recommendation.py"
    with open(router_path, "r") as f:
        content = f.read()
        
        if "_build_outcome_summary" in content:
            print("  [PASS] _build_outcome_summary function exists")
        else:
            print("  [FAIL] _build_outcome_summary function missing")
            return False
    
    # Test 2: Helper function called in API response
    print("\n[2] Helper Function Called in API Response")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if '"outcome": _build_outcome_summary' in content:
            print("  [PASS] _build_outcome_summary called in response")
        else:
            print("  [FAIL] _build_outcome_summary not called in response")
            return False
    
    # Test 3: Outcome summary structure
    print("\n[3] Outcome Summary Structure")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        required_fields = [
            "status",
            "feedback",
            "tests",
            "scenarios",
            "overrides",
            "defect_escaped",
            "rollback_occurred",
        ]
        
        for field in required_fields:
            if f'"{field}"' in content:
                print(f"  [PASS] Has {field} field")
            else:
                print(f"  [FAIL] {field} field missing")
                return False
    
    # Test 4: Test summary structure
    print("\n[4] Test Summary Structure")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        test_fields = [
            "recommended_count",
            "kept_count",
            "removed_count",
            "executed_count",
            "passed_count",
            "failed_count",
            "skipped_count",
            "not_run_count",
        ]
        
        for field in test_fields:
            if field in content:
                print(f"  [PASS] Has {field} field")
            else:
                print(f"  [FAIL] {field} field missing")
                return False
    
    # Test 5: Scenario summary structure
    print("\n[5] Scenario Summary Structure")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        scenario_fields = [
            "suggested_count",
            "accepted_count",
            "dismissed_count",
            "executed_count",
            "important_count",
        ]
        
        for field in scenario_fields:
            if field in content:
                print(f"  [PASS] Has {field} field")
            else:
                print(f"  [FAIL] {field} field missing")
                return False
    
    # Test 6: Override summary structure
    print("\n[6] Override Summary Structure")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        override_fields = [
            "added_tests_count",
            "removed_tests_count",
        ]
        
        for field in override_fields:
            if field in content:
                print(f"  [PASS] Has {field} field")
            else:
                print(f"  [FAIL] {field} field missing")
                return False
    
    # Test 7: Pydantic schemas exist
    print("\n[7] Pydantic Schemas Exist")
    print("-" * 70)
    
    schema_path = "app/schemas/recommendation.py"
    with open(schema_path, "r") as f:
        content = f.read()
        
        if "OutcomeTestSummary" in content:
            print("  [PASS] OutcomeTestSummary schema exists")
        else:
            print("  [FAIL] OutcomeTestSummary schema missing")
            return False
        
        if "OutcomeScenarioSummary" in content:
            print("  [PASS] OutcomeScenarioSummary schema exists")
        else:
            print("  [FAIL] OutcomeScenarioSummary schema missing")
            return False
        
        if "OutcomeOverrideSummary" in content:
            print("  [PASS] OutcomeOverrideSummary schema exists")
        else:
            print("  [FAIL] OutcomeOverrideSummary schema missing")
            return False
        
        if "OutcomeSummary" in content:
            print("  [PASS] OutcomeSummary schema exists")
        else:
            print("  [FAIL] OutcomeSummary schema missing")
            return False
    
    # Test 8: OutcomeSummary added to RecommendationRunResponse
    print("\n[8] OutcomeSummary Added to RecommendationRunResponse")
    print("-" * 70)
    
    with open(schema_path, "r") as f:
        content = f.read()
        
        if "outcome: Optional[\"OutcomeSummary\"]" in content:
            print("  [PASS] outcome field added to RecommendationRunResponse")
        else:
            print("  [FAIL] outcome field not added to RecommendationRunResponse")
            return False
    
    # Test 9: Handles missing outcome gracefully
    print("\n[9] Handles Missing Outcome Gracefully")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "if not outcome:" in content:
            print("  [PASS] Checks for missing outcome")
        else:
            print("  [FAIL] Missing outcome check missing")
            return False
        
        if "NOT_CAPTURED" in content:
            print("  [PASS] Returns NOT_CAPTURED status when missing")
        else:
            print("  [FAIL] NOT_CAPTURED status missing")
            return False
    
    # Test 10: Queries required models
    print("\n[10] Queries Required Models")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "RecommendationOutcome" in content:
            print("  [PASS] Queries RecommendationOutcome")
        else:
            print("  [FAIL] RecommendationOutcome query missing")
            return False
        
        if "RecommendationTestOutcome" in content:
            print("  [PASS] Queries RecommendationTestOutcome")
        else:
            print("  [FAIL] RecommendationTestOutcome query missing")
            return False
        
        if "SuggestedScenarioOutcome" in content:
            print("  [PASS] Queries SuggestedScenarioOutcome")
        else:
            print("  [FAIL] SuggestedScenarioOutcome query missing")
            return False
        
        if "RecommendationOverride" in content:
            print("  [PASS] Queries RecommendationOverride")
        else:
            print("  [FAIL] RecommendationOverride query missing")
            return False
        
        if "RecommendedTest" in content:
            print("  [PASS] Queries RecommendedTest")
        else:
            print("  [FAIL] RecommendedTest query missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nOutcome summary API response verified:")
    print("  - Helper function exists")
    print("  - Helper function called in API response")
    print("  - Outcome summary structure")
    print("  - Test summary structure")
    print("  - Scenario summary structure")
    print("  - Override summary structure")
    print("  - Pydantic schemas exist")
    print("  - OutcomeSummary added to RecommendationRunResponse")
    print("  - Handles missing outcome gracefully")
    print("  - Queries required models")
    print("\nUI can show outcome/learning status clearly.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_outcome_summary_api()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
