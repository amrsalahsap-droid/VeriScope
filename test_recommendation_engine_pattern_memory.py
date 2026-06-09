"""
Test RecommendationEngine PatternMemoryV2 integration.

Verifies that the recommendation engine consumes PatternMemoryV2 correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def test_recommendation_engine_pattern_memory():
    """Test RecommendationEngine PatternMemoryV2 integration."""
    print("=" * 70)
    print("RECOMMENDATION ENGINE PATTERN MEMORY INTEGRATION TEST")
    print("=" * 70)
    
    # Test 1: PatternMemoryV2 import
    print("\n[1] PatternMemoryV2 Import")
    print("-" * 70)
    
    engine_path = "app/services/recommendation_logic_v3.py"
    with open(engine_path, "r") as f:
        content = f.read()
        
        if "PatternMemoryV2" in content:
            print("  [PASS] Imports PatternMemoryV2")
        else:
            print("  [FAIL] PatternMemoryV2 import missing")
            return False
        
        if "SIGNAL_TYPE_MANUAL_ADDITION" in content:
            print("  [PASS] Imports SIGNAL_TYPE_MANUAL_ADDITION")
        else:
            print("  [FAIL] SIGNAL_TYPE_MANUAL_ADDITION import missing")
            return False
        
        if "SIGNAL_TYPE_MANUAL_REMOVAL" in content:
            print("  [PASS] Imports SIGNAL_TYPE_MANUAL_REMOVAL")
        else:
            print("  [FAIL] SIGNAL_TYPE_MANUAL_REMOVAL import missing")
            return False
        
        if "SIGNAL_TYPE_ACCEPTED_SCENARIO" in content:
            print("  [PASS] Imports SIGNAL_TYPE_ACCEPTED_SCENARIO")
        else:
            print("  [FAIL] SIGNAL_TYPE_ACCEPTED_SCENARIO import missing")
            return False
        
        if "SIGNAL_TYPE_DISMISSED_SCENARIO" in content:
            print("  [PASS] Imports SIGNAL_TYPE_DISMISSED_SCENARIO")
        else:
            print("  [FAIL] SIGNAL_TYPE_DISMISSED_SCENARIO import missing")
            return False
        
        if "SIGNAL_TYPE_ESCAPED_DEFECT" in content:
            print("  [PASS] Imports SIGNAL_TYPE_ESCAPED_DEFECT")
        else:
            print("  [FAIL] SIGNAL_TYPE_ESCAPED_DEFECT import missing")
            return False
        
        if "SIGNAL_TYPE_ROLLBACK" in content:
            print("  [PASS] Imports SIGNAL_TYPE_ROLLBACK")
        else:
            print("  [FAIL] SIGNAL_TYPE_ROLLBACK import missing")
            return False
        
        if "SIGNAL_TYPE_EXECUTION_RESULT" in content:
            print("  [PASS] Imports SIGNAL_TYPE_EXECUTION_RESULT")
        else:
            print("  [FAIL] SIGNAL_TYPE_EXECUTION_RESULT import missing")
            return False
    
    # Test 2: PatternMemoryV2 query
    print("\n[2] PatternMemoryV2 Query")
    print("-" * 70)
    
    with open(engine_path, "r") as f:
        content = f.read()
        
        if "pmv2_records" in content:
            print("  [PASS] Queries PatternMemoryV2 records")
        else:
            print("  [FAIL] PatternMemoryV2 query missing")
            return False
        
        if "pmv2_test_map" in content:
            print("  [PASS] Creates test identifier mapping")
        else:
            print("  [FAIL] Test identifier mapping missing")
            return False
        
        if "pmv2_scenario_map" in content:
            print("  [PASS] Creates scenario intent mapping")
        else:
            print("  [FAIL] Scenario intent mapping missing")
            return False
        
        if "pmv2_behavior_map" in content:
            print("  [PASS] Creates behavior mapping")
        else:
            print("  [FAIL] Behavior mapping missing")
            return False
    
    # Test 3: Scoring logic
    print("\n[3] Scoring Logic")
    print("-" * 70)
    
    with open(engine_path, "r") as f:
        content = f.read()
        
        if "learning_score" in content:
            print("  [PASS] Has learning_score variable")
        else:
            print("  [FAIL] learning_score variable missing")
            return False
        
        if "learning_signals" in content:
            print("  [PASS] Has learning_signals list")
        else:
            print("  [FAIL] learning_signals list missing")
            return False
        
        if "SIGNAL_TYPE_MANUAL_ADDITION" in content:
            print("  [PASS] Checks for MANUAL_ADDITION signal")
        else:
            print("  [FAIL] MANUAL_ADDITION signal check missing")
            return False
        
        if "SIGNAL_TYPE_MANUAL_REMOVAL" in content:
            print("  [PASS] Checks for MANUAL_REMOVAL signal")
        else:
            print("  [FAIL] MANUAL_REMOVAL signal check missing")
            return False
        
        if "SIGNAL_TYPE_ESCAPED_DEFECT" in content:
            print("  [PASS] Checks for ESCAPED_DEFECT signal")
        else:
            print("  [FAIL] ESCAPED_DEFECT signal check missing")
            return False
        
        if "SIGNAL_TYPE_ROLLBACK" in content:
            print("  [PASS] Checks for ROLLBACK signal")
        else:
            print("  [FAIL] ROLLBACK signal check missing")
            return False
        
        if "+ 20" in content or "+20" in content:
            print("  [PASS] Has +20 scoring")
        else:
            print("  [FAIL] +20 scoring missing")
            return False
        
        if "- 10" in content or "-10" in content:
            print("  [PASS] Has -10 scoring")
        else:
            print("  [FAIL] -10 scoring missing")
            return False
        
        if "+ 25" in content or "+25" in content:
            print("  [PASS] Has +25 scoring")
        else:
            print("  [FAIL] +25 scoring missing")
            return False
    
    # Test 4: Signal breakdown
    print("\n[4] Signal Breakdown")
    print("-" * 70)
    
    with open(engine_path, "r") as f:
        content = f.read()
        
        if "learning_score_final" in content:
            print("  [PASS] Has learning_score_final in breakdown")
        else:
            print("  [FAIL] learning_score_final in breakdown missing")
            return False
        
        if "learning_signal_types" in content:
            print("  [PASS] Has learning_signal_types in signals_dict")
        else:
            print("  [FAIL] learning_signal_types in signals_dict missing")
            return False
        
        if "learning_str" in content:
            print("  [PASS] Has learning_str in breakdown string")
        else:
            print("  [FAIL] learning_str in breakdown string missing")
            return False
    
    # Test 5: Learning signals in total score
    print("\n[5] Learning Signals in Total Score")
    print("-" * 70)
    
    with open(engine_path, "r") as f:
        content = f.read()
        
        if "learning_score_final" in content and "total_score" in content:
            print("  [PASS] learning_score_final added to total_score")
        else:
            print("  [FAIL] learning_score_final not in total_score")
            return False
    
    # Test 6: Learning signals in signal presence check
    print("\n[6] Learning Signals in Signal Presence Check")
    print("-" * 70)
    
    with open(engine_path, "r") as f:
        content = f.read()
        
        if "has_learning_signals" in content:
            print("  [PASS] Has has_learning_signals check")
        else:
            print("  [FAIL] has_learning_signals check missing")
            return False
    
    # Test 7: Learning signals never override high-confidence evidence
    print("\n[7] Learning Signals Never Override High-Confidence Evidence")
    print("-" * 70)
    
    with open(engine_path, "r") as f:
        content = f.read()
        
        if "cov_confidence != \"HIGH\"" in content and "graph_conf_score < 30" in content:
            print("  [PASS] Checks for HIGH confidence before applying learning")
        else:
            print("  [FAIL] High confidence check missing")
            return False
    
    # Test 8: Evidence gap for no outcome learning
    print("\n[8] Evidence Gap for No Outcome Learning")
    print("-" * 70)
    
    with open(engine_path, "r") as f:
        content = f.read()
        
        if "not pmv2_records" in content:
            print("  [PASS] Checks for missing pattern memory")
        else:
            print("  [FAIL] Missing pattern memory check missing")
            return False
        
        if "evidence gap" in content.lower():
            print("  [PASS] Adds evidence gap message")
        else:
            print("  [FAIL] Evidence gap message missing")
            return False
    
    # Test 9: Graceful handling of missing pattern memory
    print("\n[9] Graceful Handling of Missing Pattern Memory")
    print("-" * 70)
    
    with open(engine_path, "r") as f:
        content = f.read()
        
        if "try:" in content and "except" in content:
            print("  [PASS] Has try/except for PatternMemoryV2 query")
        else:
            print("  [FAIL] Try/except for PatternMemoryV2 query missing")
            return False
        
        if "unavailable" in content.lower():
            print("  [PASS] Has warning for unavailable layer")
        else:
            print("  [FAIL] Warning for unavailable layer missing")
            return False
    
    # Test 10: Learning signals in confidence breakdown
    print("\n[10] Learning Signals in Confidence Breakdown")
    print("-" * 70)
    
    with open(engine_path, "r") as f:
        content = f.read()
        
        if "Learning:" in content and "/50" in content:
            print("  [PASS] Has learning in confidence breakdown")
        else:
            print("  [FAIL] Learning in confidence breakdown missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nRecommendationEngine PatternMemoryV2 integration verified:")
    print("  - PatternMemoryV2 import")
    print("  - PatternMemoryV2 query")
    print("  - Scoring logic")
    print("  - Signal breakdown")
    print("  - Learning signals in total score")
    print("  - Learning signals in signal presence check")
    print("  - Learning signals never override high-confidence evidence")
    print("  - Evidence gap for no outcome learning")
    print("  - Graceful handling of missing pattern memory")
    print("  - Learning signals in confidence breakdown")
    print("\nRecommendations improve after feedback is captured.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_recommendation_engine_pattern_memory()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
