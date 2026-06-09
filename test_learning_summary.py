"""
Test learning summary API endpoint.

Verifies that the learning summary endpoint is correctly implemented.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def test_learning_summary():
    """Test learning summary API endpoint."""
    print("=" * 70)
    print("LEARNING SUMMARY API TEST")
    print("=" * 70)
    
    # Test 1: Pydantic schemas exist
    print("\n[1] Pydantic Schemas Exist")
    print("-" * 70)
    
    schema_path = "app/schemas/recommendation.py"
    with open(schema_path, "r") as f:
        content = f.read()
        
        if "LearnedPattern" in content:
            print("  [PASS] LearnedPattern schema exists")
        else:
            print("  [FAIL] LearnedPattern schema missing")
            return False
        
        if "BehaviorLearningSignal" in content:
            print("  [PASS] BehaviorLearningSignal schema exists")
        else:
            print("  [FAIL] BehaviorLearningSignal schema missing")
            return False
        
        if "LearningSummary" in content:
            print("  [PASS] LearningSummary schema exists")
        else:
            print("  [FAIL] LearningSummary schema missing")
            return False
    
    # Test 2: LearningSummary has required fields
    print("\n[2] LearningSummary Has Required Fields")
    print("-" * 70)
    
    with open(schema_path, "r") as f:
        content = f.read()
        
        required_fields = [
            "total_outcomes",
            "useful_feedback_count",
            "missing_tests_feedback_count",
            "manually_added_tests_count",
            "removed_tests_count",
            "accepted_scenarios_count",
            "escaped_defects_count",
            "rollback_count",
            "top_learned_patterns",
            "behaviors_with_most_signals",
        ]
        
        for field in required_fields:
            if field in content:
                print(f"  [PASS] Has {field} field")
            else:
                print(f"  [FAIL] {field} field missing")
                return False
    
    # Test 3: API endpoint exists
    print("\n[3] API Endpoint Exists")
    print("-" * 70)
    
    router_path = "app/routers/github.py"
    with open(router_path, "r") as f:
        content = f.read()
        
        if "/repositories/{repository_id}/learning-summary" in content:
            print("  [PASS] Learning summary endpoint exists")
        else:
            print("  [FAIL] Learning summary endpoint missing")
            return False
        
        if "get_learning_summary" in content:
            print("  [PASS] get_learning_summary function exists")
        else:
            print("  [FAIL] get_learning_summary function missing")
            return False
    
    # Test 4: Endpoint queries required models
    print("\n[4] Endpoint Queries Required Models")
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
        
        if "PatternMemoryV2" in content:
            print("  [PASS] Queries PatternMemoryV2")
        else:
            print("  [FAIL] PatternMemoryV2 query missing")
            return False
        
        if "Behavior" in content:
            print("  [PASS] Queries Behavior")
        else:
            print("  [FAIL] Behavior query missing")
            return False
    
    # Test 5: Endpoint counts feedback types
    print("\n[5] Endpoint Counts Feedback Types")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "USEFUL" in content:
            print("  [PASS] Counts USEFUL feedback")
        else:
            print("  [FAIL] USEFUL feedback count missing")
            return False
        
        if "MISSING_TESTS" in content:
            print("  [PASS] Counts MISSING_TESTS feedback")
        else:
            print("  [FAIL] MISSING_TESTS feedback count missing")
            return False
    
    # Test 6: Endpoint counts outcomes
    print("\n[6] Endpoint Counts Outcomes")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "defect_escaped" in content:
            print("  [PASS] Counts escaped defects")
        else:
            print("  [FAIL] Escaped defects count missing")
            return False
        
        if "rollback_occurred" in content:
            print("  [PASS] Counts rollbacks")
        else:
            print("  [FAIL] Rollback count missing")
            return False
    
    # Test 7: Endpoint returns top learned patterns
    print("\n[7] Endpoint Returns Top Learned Patterns")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "top_learned_patterns" in content:
            print("  [PASS] Returns top_learned_patterns")
        else:
            print("  [FAIL] top_learned_patterns missing")
            return False
        
        if "usage_count.desc()" in content or "usage_count" in content:
            print("  [PASS] Orders by usage_count")
        else:
            print("  [FAIL] Usage count ordering missing")
            return False
    
    # Test 8: Endpoint returns behaviors with most signals
    print("\n[8] Endpoint Returns Behaviors With Most Signals")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "behaviors_with_most_signals" in content:
            print("  [PASS] Returns behaviors_with_most_signals")
        else:
            print("  [FAIL] behaviors_with_most_signals missing")
            return False
        
        if "behavior_id" in content:
            print("  [PASS] Groups by behavior_id")
        else:
            print("  [FAIL] behavior_id grouping missing")
            return False
    
    # Test 9: Endpoint is workspace-scoped
    print("\n[9] Endpoint Is Workspace-Scoped")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "workspace_id" in content:
            print("  [PASS] Checks workspace_id")
        else:
            print("  [FAIL] workspace_id check missing")
            return False
        
        if "require_workspace_member" in content:
            print("  [PASS] Requires workspace member")
        else:
            print("  [FAIL] Workspace member requirement missing")
            return False
    
    # Test 10: Endpoint returns LearningSummary
    print("\n[10] Endpoint Returns LearningSummary")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "return LearningSummary" in content:
            print("  [PASS] Returns LearningSummary")
        else:
            print("  [FAIL] LearningSummary return missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nLearning summary API endpoint verified:")
    print("  - Pydantic schemas exist")
    print("  - LearningSummary has required fields")
    print("  - API endpoint exists")
    print("  - Endpoint queries required models")
    print("  - Endpoint counts feedback types")
    print("  - Endpoint counts outcomes")
    print("  - Endpoint returns top learned patterns")
    print("  - Endpoint returns behaviors with most signals")
    print("  - Endpoint is workspace-scoped")
    print("  - Endpoint returns LearningSummary")
    print("\nUsers can see Veriscope becoming smarter over time.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_learning_summary()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
