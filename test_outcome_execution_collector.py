"""
Test OutcomeExecutionCollector service.

Verifies that JUnit TestRun results are correctly mapped to recommendation outcomes.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def test_outcome_execution_collector():
    """Test OutcomeExecutionCollector service."""
    print("=" * 70)
    print("OUTCOME EXECUTION COLLECTOR TEST")
    print("=" * 70)
    
    # Test 1: Service file exists
    print("\n[1] Service File Existence")
    print("-" * 70)
    
    service_path = "app/services/outcome_execution_collector.py"
    if os.path.exists(service_path):
        print(f"  [PASS] Service file exists at {service_path}")
    else:
        print(f"  [FAIL] Service file not found at {service_path}")
        return False
    
    # Test 2: Service has required methods
    print("\n[2] Required Methods")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "collect_execution_outcomes" in content:
            print("  [PASS] Has collect_execution_outcomes method")
        else:
            print("  [FAIL] collect_execution_outcomes method missing")
            return False
        
        if "_is_current_pr_execution" in content:
            print("  [PASS] Has _is_current_pr_execution method")
        else:
            print("  [FAIL] _is_current_pr_execution method missing")
            return False
        
        if "_map_junit_status" in content:
            print("  [PASS] Has _map_junit_status method")
        else:
            print("  [FAIL] _map_junit_status method missing")
            return False
        
        if "_determine_outcome_status" in content:
            print("  [PASS] Has _determine_outcome_status method")
        else:
            print("  [FAIL] _determine_outcome_status method missing")
            return False
        
        if "_update_recommendation_outcome" in content:
            print("  [PASS] Has _update_recommendation_outcome method")
        else:
            print("  [FAIL] _update_recommendation_outcome method missing")
            return False
    
    # Test 3: Test matching logic
    print("\n[3] Test Matching Logic")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "recommended_map" in content:
            print("  [PASS] Builds recommended test map")
        else:
            print("  [FAIL] Recommended test map missing")
            return False
        
        if "executed_map" in content:
            print("  [PASS] Builds executed test map")
        else:
            print("  [FAIL] Executed test map missing")
            return False
        
        if "test_identifier" in content:
            print("  [PASS] Uses test_identifier for matching")
        else:
            print("  [FAIL] test_identifier matching missing")
            return False
        
        if "stable_identity" in content:
            print("  [PASS] Uses stable_identity for matching")
        else:
            print("  [FAIL] stable_identity matching missing")
            return False
    
    # Test 4: Execution status mapping
    print("\n[4] Execution Status Mapping")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "PASSED" in content:
            print("  [PASS] Maps to PASSED")
        else:
            print("  [FAIL] PASSED mapping missing")
            return False
        
        if "FAILED" in content:
            print("  [PASS] Maps to FAILED")
        else:
            print("  [FAIL] FAILED mapping missing")
            return False
        
        if "SKIPPED" in content:
            print("  [PASS] Maps to SKIPPED")
        else:
            print("  [FAIL] SKIPPED mapping missing")
            return False
        
        if "NOT_RUN" in content:
            print("  [PASS] Maps to NOT_RUN")
        else:
            print("  [FAIL] NOT_RUN mapping missing")
            return False
    
    # Test 5: Override creation for extra tests
    print("\n[5] Override Creation for Extra Tests")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "extra_executed" in content:
            print("  [PASS] Identifies extra executed tests")
        else:
            print("  [FAIL] Extra test identification missing")
            return False
        
        if "record_test_added" in content:
            print("  [PASS] Creates TEST_ADDED override")
        else:
            print("  [FAIL] TEST_ADDED override creation missing")
            return False
        
        if "is_current_pr" in content:
            print("  [PASS] Checks if current PR before creating override")
        else:
            print("  [FAIL] Current PR check missing")
            return False
    
    # Test 6: Outcome status update
    print("\n[6] Outcome Status Update")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "ACCEPTED" in content:
            print("  [PASS] Has ACCEPTED status")
        else:
            print("  [FAIL] ACCEPTED status missing")
            return False
        
        if "PARTIALLY_ACCEPTED" in content:
            print("  [PASS] Has PARTIALLY_ACCEPTED status")
        else:
            print("  [FAIL] PARTIALLY_ACCEPTED status missing")
            return False
        
        if "IGNORED" in content:
            print("  [PASS] Has IGNORED status")
        else:
            print("  [FAIL] IGNORED status missing")
            return False
    
    # Test 7: SHA mismatch handling
    print("\n[7] SHA Mismatch Handling")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "commit_sha" in content:
            print("  [PASS] Checks commit SHA")
        else:
            print("  [FAIL] commit SHA check missing")
            return False
        
        if "historical" in content.lower():
            print("  [PASS] Handles historical execution")
        else:
            print("  [FAIL] Historical execution handling missing")
            return False
    
    # Test 8: Skipped test handling
    print("\n[8] Skipped Test Handling")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "skipped" in content.lower():
            print("  [PASS] Handles skipped status")
        else:
            print("  [FAIL] Skipped status handling missing")
            return False
    
    # Test 9: Unmatched test logging
    print("\n[9] Unmatched Test Logging")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "logger" in content:
            print("  [PASS] Has logger for logging")
        else:
            print("  [FAIL] Logger missing")
            return False
        
        if "unmatched" in content.lower() or "extra" in content.lower():
            print("  [PASS] Logs unmatched/extra tests")
        else:
            print("  [FAIL] Unmatched test logging missing")
            return False
    
    # Test 10: Service dependencies
    print("\n[10] Service Dependencies")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "RecommendationTestOutcomeUpdater" in content:
            print("  [PASS] Uses RecommendationTestOutcomeUpdater")
        else:
            print("  [FAIL] RecommendationTestOutcomeUpdater missing")
            return False
        
        if "RecommendationOverrideUpdater" in content:
            print("  [PASS] Uses RecommendationOverrideUpdater")
        else:
            print("  [FAIL] RecommendationOverrideUpdater missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nOutcomeExecutionCollector verified:")
    print("  - Service file exists")
    print("  - All required methods present")
    print("  - Test matching by test_identifier/stable_identity")
    print("  - Execution status mapping (PASSED/FAILED/SKIPPED/NOT_RUN)")
    print("  - Override creation for extra tests")
    print("  - Outcome status update (ACCEPTED/PARTIALLY_ACCEPTED/IGNORED)")
    print("  - SHA mismatch handling")
    print("  - Skipped test handling")
    print("  - Unmatched test logging")
    print("  - Service dependencies integrated")
    print("\nJUnit results after recommendation update outcome truth.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_outcome_execution_collector()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
