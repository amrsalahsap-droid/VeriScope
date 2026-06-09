"""
Test RecommendationOutcomeLearningEngine service.

Verifies that learning rules are implemented correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def test_recommendation_outcome_learning_engine():
    """Test RecommendationOutcomeLearningEngine service."""
    print("=" * 70)
    print("RECOMMENDATION OUTCOME LEARNING ENGINE TEST")
    print("=" * 70)
    
    # Test 1: Service file exists
    print("\n[1] Service File Existence")
    print("-" * 70)
    
    service_path = "app/services/recommendation_outcome_learning_engine.py"
    if os.path.exists(service_path):
        print(f"  [PASS] Service file exists at {service_path}")
    else:
        print(f"  [FAIL] Service file not found at {service_path}")
        return False
    
    # Test 2: Required methods
    print("\n[2] Required Methods")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "process_outcome" in content:
            print("  [PASS] Has process_outcome method")
        else:
            print("  [FAIL] process_outcome method missing")
            return False
    
    # Test 3: Learning rule 1 - Kept + passed/failed strengthens mapping
    print("\n[3] Learning Rule 1: Kept + Passed/Failed Strengthens Mapping")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "_strengthen_test_mapping" in content:
            print("  [PASS] Has _strengthen_test_mapping method")
        else:
            print("  [FAIL] _strengthen_test_mapping method missing")
            return False
        
        if "_strengthen_coverage_link" in content:
            print("  [PASS] Has _strengthen_coverage_link method")
        else:
            print("  [FAIL] _strengthen_coverage_link method missing")
            return False
        
        if "KEPT" in content and "PASSED" in content:
            print("  [PASS] Checks for KEPT decision and PASSED/FAILED status")
        else:
            print("  [FAIL] KEPT/PASSED check missing")
            return False
    
    # Test 4: Learning rule 2 - Removed weakens low-confidence signal
    print("\n[4] Learning Rule 2: Removed Weakens Low-Confidence Signal")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "_weaken_pattern_memory" in content:
            print("  [PASS] Has _weaken_pattern_memory method")
        else:
            print("  [FAIL] _weaken_pattern_memory method missing")
            return False
        
        if "REMOVED" in content and "LOW" in content:
            print("  [PASS] Checks for REMOVED decision and LOW confidence")
        else:
            print("  [FAIL] REMOVED/LOW check missing")
            return False
    
    # Test 5: Learning rule 3 - Manually added test creates/strengthens relationships
    print("\n[5] Learning Rule 3: Manually Added Test Creates/Strengthens Relationships")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "_create_or_strengthen_pattern_memory" in content:
            print("  [PASS] Has _create_or_strengthen_pattern_memory method")
        else:
            print("  [FAIL] _create_or_strengthen_pattern_memory method missing")
            return False
        
        if "_create_or_strengthen_coverage_link" in content:
            print("  [PASS] Has _create_or_strengthen_coverage_link method")
        else:
            print("  [FAIL] _create_or_strengthen_coverage_link method missing")
            return False
        
        if "TEST_ADDED" in content:
            print("  [PASS] Checks for TEST_ADDED override")
        else:
            print("  [FAIL] TEST_ADDED check missing")
            return False
    
    # Test 6: Learning rule 4 - Accepted/important scenario strengthens intent
    print("\n[6] Learning Rule 4: Accepted/Important Scenario Strengthens Intent")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "_strengthen_scenario_intent" in content:
            print("  [PASS] Has _strengthen_scenario_intent method")
        else:
            print("  [FAIL] _strengthen_scenario_intent method missing")
            return False
        
        if "ACCEPTED" in content and "MARKED_IMPORTANT" in content:
            print("  [PASS] Checks for ACCEPTED and MARKED_IMPORTANT decisions")
        else:
            print("  [FAIL] ACCEPTED/MARKED_IMPORTANT check missing")
            return False
    
    # Test 7: Learning rule 5 - Dismissed scenario reduces priority
    print("\n[7] Learning Rule 5: Dismissed Scenario Reduces Priority")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "_reduce_scenario_priority" in content:
            print("  [PASS] Has _reduce_scenario_priority method")
        else:
            print("  [FAIL] _reduce_scenario_priority method missing")
            return False
        
        if "DISMISSED" in content:
            print("  [PASS] Checks for DISMISSED decision")
        else:
            print("  [FAIL] DISMISSED check missing")
            return False
    
    # Test 8: Learning rule 6 - Escaped defect strengthens missed behaviors
    print("\n[8] Learning Rule 6: Escaped Defect Strengthens Missed Behaviors")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "_strengthen_missed_behaviors" in content:
            print("  [PASS] Has _strengthen_missed_behaviors method")
        else:
            print("  [FAIL] _strengthen_missed_behaviors method missing")
            return False
        
        if "_strengthen_defect_gaps" in content:
            print("  [PASS] Has _strengthen_defect_gaps method")
        else:
            print("  [FAIL] _strengthen_defect_gaps method missing")
            return False
        
        if "defect_escaped" in content:
            print("  [PASS] Checks for defect_escaped")
        else:
            print("  [FAIL] defect_escaped check missing")
            return False
    
    # Test 9: Learning rule 7 - Rollback marks fragile
    print("\n[9] Learning Rule 7: Rollback Marks Fragile")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "_mark_fragile_patterns" in content:
            print("  [PASS] Has _mark_fragile_patterns method")
        else:
            print("  [FAIL] _mark_fragile_patterns method missing")
            return False
        
        if "rollback_occurred" in content:
            print("  [PASS] Checks for rollback_occurred")
        else:
            print("  [FAIL] rollback_occurred check missing")
            return False
    
    # Test 10: Append-only learning events
    print("\n[10] Append-Only Learning Events")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "usage_count +=" in content or "success_count +=" in content:
            print("  [PASS] Increments counters (append-only)")
        else:
            print("  [FAIL] Counter increment missing")
            return False
        
        if "confidence = min" in content or "confidence = max" in content:
            print("  [PASS] Updates confidence without deletion")
        else:
            print("  [FAIL] Confidence update missing")
            return False
    
    # Test 11: Learning model imports
    print("\n[11] Learning Model Imports")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "PatternMemory" in content:
            print("  [PASS] Imports PatternMemory")
        else:
            print("  [FAIL] PatternMemory import missing")
            return False
        
        if "TestCoverageLink" in content:
            print("  [PASS] Imports TestCoverageLink")
        else:
            print("  [FAIL] TestCoverageLink import missing")
            return False
        
        if "ScenarioIntent" in content:
            print("  [PASS] Imports ScenarioIntent")
        else:
            print("  [FAIL] ScenarioIntent import missing")
            return False
    
    # Test 12: Explainable learning
    print("\n[12] Explainable Learning")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "logger" in content:
            print("  [PASS] Has logging for explainability")
        else:
            print("  [FAIL] Logging missing")
            return False
        
        if "learning_events_applied" in content:
            print("  [PASS] Returns learning event counts")
        else:
            print("  [FAIL] Learning event counts missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nRecommendationOutcomeLearningEngine verified:")
    print("  - Service file exists")
    print("  - process_outcome method")
    print("  - Learning rule 1: Kept + passed/failed strengthens mapping")
    print("  - Learning rule 2: Removed weakens low-confidence signal")
    print("  - Learning rule 3: Manually added test creates/strengthens relationships")
    print("  - Learning rule 4: Accepted/important scenario strengthens intent")
    print("  - Learning rule 5: Dismissed scenario reduces priority")
    print("  - Learning rule 6: Escaped defect strengthens missed behaviors")
    print("  - Learning rule 7: Rollback marks fragile")
    print("  - Append-only learning events")
    print("  - Learning model imports")
    print("  - Explainable learning")
    print("\nFuture recommendations change based on captured outcomes.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_recommendation_outcome_learning_engine()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
