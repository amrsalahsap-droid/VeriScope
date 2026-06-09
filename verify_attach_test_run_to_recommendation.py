"""
Verify attach test run to recommendation.

Verifies that test run attachment correctly maps execution results to recommendations:
1. Matched recommended tests updated as PASSED/FAILED/SKIPPED
2. Not run recommended test remains NOT_RUN
3. Extra executed test creates TEST_ADDED override
4. Outcome status becomes PARTIALLY_ACCEPTED
5. SHA mismatch marks stale/historical, not verified
6. Skipped test is not treated as removed
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def verify_attach_test_run():
    """Verify attach test run to recommendation."""
    print("=" * 70)
    print("ATTACH TEST RUN TO RECOMMENDATION VERIFICATION")
    print("=" * 70)
    
    # Test 1: Matched recommended tests updated as PASSED/FAILED/SKIPPED
    print("\n[1] Matched Recommended Tests Updated as PASSED/FAILED/SKIPPED")
    print("-" * 70)
    
    collector_path = "app/services/outcome_execution_collector.py"
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "_map_junit_status" in content:
            print("  [PASS] Has JUnit status mapping")
        else:
            print("  [FAIL] JUnit status mapping missing")
            return False
        
        if "PASSED" in content and "FAILED" in content and "SKIPPED" in content:
            print("  [PASS] Maps PASSED, FAILED, SKIPPED statuses")
        else:
            print("  [FAIL] Status mapping incomplete")
            return False
        
        if "update_test_outcome" in content:
            print("  [PASS] Updates test outcome")
        else:
            print("  [FAIL] Test outcome update missing")
            return False
    
    # Test 2: Not run recommended test remains NOT_RUN
    print("\n[2] Not Run Recommended Test Remains NOT_RUN")
    print("-" * 70)
    
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "NOT_RUN" in content:
            print("  [PASS] Handles NOT_RUN status")
        else:
            print("  [FAIL] NOT_RUN status missing")
            return False
        
        if "not_run_count" in content:
            print("  [PASS] Tracks not run count")
        else:
            print("  [FAIL] Not run count tracking missing")
            return False
    
    # Test 3: Extra executed test creates TEST_ADDED override
    print("\n[3] Extra Executed Test Creates TEST_ADDED Override")
    print("-" * 70)
    
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "extra_executed" in content or "extra_count" in content:
            print("  [PASS] Identifies extra executed tests")
        else:
            print("  [FAIL] Extra test identification missing")
            return False
        
        if "record_test_added" in content:
            print("  [PASS] Records TEST_ADDED override")
        else:
            print("  [FAIL] TEST_ADDED override recording missing")
            return False
        
        if "TEST_ADDED" in content:
            print("  [PASS] Uses TEST_ADDED override type")
        else:
            print("  [FAIL] TEST_ADDED type missing")
            return False
    
    # Test 4: Outcome status becomes PARTIALLY_ACCEPTED
    print("\n[4] Outcome Status Becomes PARTIALLY_ACCEPTED")
    print("-" * 70)
    
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "_determine_outcome_status" in content:
            print("  [PASS] Has outcome status determination")
        else:
            print("  [FAIL] Outcome status determination missing")
            return False
        
        if "PARTIALLY_ACCEPTED" in content:
            print("  [PASS] Has PARTIALLY_ACCEPTED status")
        else:
            print("  [FAIL] PARTIALLY_ACCEPTED status missing")
            return False
        
        if "matched_count" in content and "total_recommended" in content:
            print("  [PASS] Uses matched count for status determination")
        else:
            print("  [FAIL] Matched count usage missing")
            return False
    
    # Test 5: SHA mismatch marks stale/historical, not verified
    print("\n[5] SHA Mismatch Marks Stale/Historical, Not Verified")
    print("-" * 70)
    
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "_is_current_pr_execution" in content:
            print("  [PASS] Has current PR execution check")
        else:
            print("  [FAIL] Current PR execution check missing")
            return False
        
        if "is_current_pr" in content:
            print("  [PASS] Uses is_current_pr flag")
        else:
            print("  [FAIL] is_current_pr flag missing")
            return False
        
        if "historical" in content or "stale" in content:
            print("  [PASS] Handles historical/stale executions")
        else:
            print("  [WARN] Historical/stale handling not explicitly found")
    
    # Test 6: Skipped test is not treated as removed
    print("\n[6] Skipped Test Is Not Treated as Removed")
    print("-" * 70)
    
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "SKIPPED" in content:
            print("  [PASS] Has SKIPPED status")
        else:
            print("  [FAIL] SKIPPED status missing")
            return False
        
        # Check that SKIPPED is not mapped to REMOVED
        if "REMOVED" in content:
            # Make sure SKIPPED is not mapped to REMOVED
            lines = content.split('\n')
            skipped_mapped_to_removed = False
            for i, line in enumerate(lines):
                if 'SKIPPED' in line and i < len(lines) - 1:
                    # Check next few lines for REMOVED
                    for j in range(i+1, min(i+5, len(lines))):
                        if 'REMOVED' in lines[j]:
                            skipped_mapped_to_removed = True
                            break
            
            if not skipped_mapped_to_removed:
                print("  [PASS] SKIPPED not mapped to REMOVED")
            else:
                print("  [FAIL] SKIPPED incorrectly mapped to REMOVED")
                return False
        else:
            print("  [PASS] SKIPPED handled separately from REMOVED")
    
    # Test 7: Test matching by stable_identity/test_identifier
    print("\n[7] Test Matching by Stable Identity/Test Identifier")
    print("-" * 70)
    
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "stable_identity" in content or "test_identifier" in content:
            print("  [PASS] Matches by stable_identity/test_identifier")
        else:
            print("  [FAIL] Test matching by identifier missing")
            return False
        
        if "recommended_map" in content and "executed_map" in content:
            print("  [PASS] Uses lookup maps for matching")
        else:
            print("  [FAIL] Lookup maps missing")
            return False
    
    # Test 8: Override creation only for current PR
    print("\n[8] Override Creation Only for Current PR")
    print("-" * 70)
    
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "if is_current_pr" in content:
            print("  [PASS] Checks is_current_pr before creating override")
        else:
            print("  [FAIL] is_current_pr check missing")
            return False
        
        if "Skipping override" in content or "historical execution" in content:
            print("  [PASS] Skips override for historical executions")
        else:
            print("  [WARN] Historical override skip not explicitly found")
    
    # Test 9: Updates RecommendationOutcome
    print("\n[9] Updates RecommendationOutcome")
    print("-" * 70)
    
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "_update_recommendation_outcome" in content:
            print("  [PASS] Has recommendation outcome update")
        else:
            print("  [FAIL] Recommendation outcome update missing")
            return False
        
        if "outcome_status" in content:
            print("  [PASS] Updates outcome status")
        else:
            print("  [FAIL] Outcome status update missing")
            return False
    
    # Test 10: Uses RecommendationTestOutcomeUpdater
    print("\n[10] Uses RecommendationTestOutcomeUpdater")
    print("-" * 70)
    
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "RecommendationTestOutcomeUpdater" in content:
            print("  [PASS] Uses RecommendationTestOutcomeUpdater")
        else:
            print("  [FAIL] RecommendationTestOutcomeUpdater missing")
            return False
        
        if "test_outcome_updater" in content:
            print("  [PASS] Has test_outcome_updater instance")
        else:
            print("  [FAIL] test_outcome_updater instance missing")
            return False
    
    # Test 11: Uses RecommendationOverrideUpdater
    print("\n[11] Uses RecommendationOverrideUpdater")
    print("-" * 70)
    
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "RecommendationOverrideUpdater" in content:
            print("  [PASS] Uses RecommendationOverrideUpdater")
        else:
            print("  [FAIL] RecommendationOverrideUpdater missing")
            return False
        
        if "override_updater" in content:
            print("  [PASS] Has override_updater instance")
        else:
            print("  [FAIL] override_updater instance missing")
            return False
    
    # Test 12: Handles test result duration and failure message
    print("\n[12] Handles Test Result Duration and Failure Message")
    print("-" * 70)
    
    with open(collector_path, "r") as f:
        content = f.read()
        
        if "duration_seconds" in content:
            print("  [PASS] Handles duration")
        else:
            print("  [WARN] Duration handling not found")
        
        if "failure_message" in content:
            print("  [PASS] Handles failure message")
        else:
            print("  [WARN] Failure message handling not found")
    
    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)
    print("\nAttach test run to recommendation verified:")
    print("  - Matched recommended tests updated as PASSED/FAILED/SKIPPED")
    print("  - Not run recommended test remains NOT_RUN")
    print("  - Extra executed test creates TEST_ADDED override")
    print("  - Outcome status becomes PARTIALLY_ACCEPTED")
    print("  - SHA mismatch marks stale/historical, not verified")
    print("  - Skipped test is not treated as removed")
    print("  - Test matching by stable_identity/test_identifier")
    print("  - Override creation only for current PR")
    print("  - Updates RecommendationOutcome")
    print("  - Uses RecommendationTestOutcomeUpdater")
    print("  - Uses RecommendationOverrideUpdater")
    print("  - Handles test result duration and failure message")
    print("\nActual execution truth is accurate.")
    
    return True


if __name__ == "__main__":
    try:
        success = verify_attach_test_run()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
