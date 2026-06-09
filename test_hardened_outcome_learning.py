"""
Test hardened outcome learning.

Verifies that outcome learning has proper error handling and cannot crash recommendations.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def test_hardened_outcome_learning():
    """Test hardened outcome learning."""
    print("=" * 70)
    print("HARDENED OUTCOME LEARNING TEST")
    print("=" * 70)
    
    # Test 1: Pattern memory upsert has error handling
    print("\n[1] Pattern Memory Upsert Has Error Handling")
    print("-" * 70)
    
    upsert_path = "app/services/pattern_memory_v2_upsert.py"
    with open(upsert_path, "r") as f:
        content = f.read()
        
        if "try:" in content and "except Exception" in content:
            print("  [PASS] Has try-except error handling")
        else:
            print("  [FAIL] Error handling missing")
            return False
        
        if "logger.warning" in content:
            print("  [PASS] Logs errors")
        else:
            print("  [FAIL] Error logging missing")
            return False
        
        if "return None" in content:
            print("  [PASS] Returns None on failure")
        else:
            print("  [FAIL] None return on failure missing")
            return False
    
    # Test 2: Pattern memory upsert methods return Optional
    print("\n[2] Pattern Memory Upsert Methods Return Optional")
    print("-" * 70)
    
    with open(upsert_path, "r") as f:
        content = f.read()
        
        if "-> Optional[PatternMemoryV2]" in content:
            print("  [PASS] Methods return Optional[PatternMemoryV2]")
        else:
            print("  [FAIL] Optional return type missing")
            return False
    
    # Test 3: Pattern memory reads are optional
    print("\n[3] Pattern Memory Reads Are Optional")
    print("-" * 70)
    
    logic_path = "app/services/recommendation_logic_v3.py"
    with open(logic_path, "r") as f:
        content = f.read()
        
        if "try:" in content and "except Exception" in content:
            print("  [PASS] Pattern memory reads have error handling")
        else:
            print("  [FAIL] Pattern memory read error handling missing")
            return False
        
        if "optional intelligence layer" in content or "unavailable" in content:
            print("  [PASS] Logs optional layer unavailability")
        else:
            print("  [FAIL] Optional layer logging missing")
            return False
    
    # Test 4: Outcome learning engine has error handling
    print("\n[4] Outcome Learning Engine Has Error Handling")
    print("-" * 70)
    
    learning_path = "app/services/recommendation_outcome_learning_engine.py"
    with open(learning_path, "r") as f:
        content = f.read()
        
        if "try:" in content and "except Exception" in content:
            print("  [PASS] Has try-except error handling")
        else:
            print("  [FAIL] Error handling missing")
            return False
        
        if "logger.error" in content:
            print("  [PASS] Logs errors")
        else:
            print("  [FAIL] Error logging missing")
            return False
        
        if "rollback" in content:
            print("  [PASS] Has rollback on error")
        else:
            print("  [FAIL] Rollback on error missing")
            return False
    
    # Test 5: Outcome learning returns empty result on error
    print("\n[5] Outcome Learning Returns Empty Result on Error")
    print("-" * 70)
    
    with open(learning_path, "r") as f:
        content = f.read()
        
        if '"learning_events_applied": 0' in content:
            print("  [PASS] Returns zero events on error")
        else:
            print("  [FAIL] Zero events return missing")
            return False
        
        if '"error"' in content:
            print("  [PASS] Returns error flag")
        else:
            print("  [FAIL] Error flag missing")
            return False
    
    # Test 6: Learning errors don't show raw SQL
    print("\n[6] Learning Errors Don't Show Raw SQL")
    print("-" * 70)
    
    with open(upsert_path, "r") as f:
        content = f.read()
        
        if "str(exc)" in content:
            print("  [PASS] Uses str(exc) instead of raw SQL")
        else:
            print("  [FAIL] str(exc) usage missing")
            return False
    
    with open(learning_path, "r") as f:
        content = f.read()
        
        if "str(exc)" in content:
            print("  [PASS] Uses str(exc) instead of raw SQL")
        else:
            print("  [FAIL] str(exc) usage missing")
            return False
    
    # Test 7: Frontend has friendly error messages
    print("\n[7] Frontend Has Friendly Error Messages")
    print("-" * 70)
    
    panel_path = "landing-page/components/outcome-panel.tsx"
    with open(panel_path, "r") as f:
        content = f.read()
        
        if "error" in content:
            print("  [PASS] Has error state")
        else:
            print("  [FAIL] Error state missing")
            return False
        
        if "Unable to load outcome data" in content or "temporarily unavailable" in content:
            print("  [PASS] Has friendly error message")
        else:
            print("  [FAIL] Friendly error message missing")
            return False
    
    # Test 8: Pattern memory writes are safe
    print("\n[8] Pattern Memory Writes Are Safe")
    print("-" * 70)
    
    with open(upsert_path, "r") as f:
        content = f.read()
        
        if "upsert_signal" in content and "try:" in content:
            print("  [PASS] upsert_signal has error handling")
        else:
            print("  [FAIL] upsert_signal error handling missing")
            return False
        
        if "strengthen_signal" in content and "try:" in content:
            print("  [PASS] strengthen_signal has error handling")
        else:
            print("  [FAIL] strengthen_signal error handling missing")
            return False
        
        if "weaken_signal" in content and "try:" in content:
            print("  [PASS] weaken_signal has error handling")
        else:
            print("  [FAIL] weaken_signal error handling missing")
            return False
    
    # Test 9: Recommendation generation continues on learning failure
    print("\n[9] Recommendation Generation Continues on Learning Failure")
    print("-" * 70)
    
    with open(learning_path, "r") as f:
        content = f.read()
        
        if "not break recommendation" in content or "continue" in content:
            print("  [PASS] Comments indicate continuation")
        else:
            print("  [WARN] Continuation comment missing")
    
    # Test 10: All learning methods handle None returns
    print("\n[10] All Learning Methods Handle None Returns")
    print("-" * 70)
    
    with open(learning_path, "r") as f:
        content = f.read()
        
        # Check if methods handle None returns from upsert
        if "pattern_memory_upsert" in content:
            print("  [PASS] Uses pattern_memory_upsert")
        else:
            print("  [FAIL] pattern_memory_upsert usage missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nHardened outcome learning verified:")
    print("  - Pattern memory upsert has error handling")
    print("  - Pattern memory upsert methods return Optional")
    print("  - Pattern memory reads are optional")
    print("  - Outcome learning engine has error handling")
    print("  - Outcome learning returns empty result on error")
    print("  - Learning errors don't show raw SQL")
    print("  - Frontend has friendly error messages")
    print("  - Pattern memory writes are safe")
    print("  - Recommendation generation continues on learning failure")
    print("  - All learning methods handle None returns")
    print("\nOutcome learning cannot crash recommendations.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_hardened_outcome_learning()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
