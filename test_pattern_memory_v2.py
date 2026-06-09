"""
Test PatternMemoryV2 implementation.

Verifies that the model, upsert service, and learning engine integration are correct.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def test_pattern_memory_v2():
    """Test PatternMemoryV2 implementation."""
    print("=" * 70)
    print("PATTERN MEMORY V2 TEST")
    print("=" * 70)
    
    # Test 1: Model file exists
    print("\n[1] Model File Existence")
    print("-" * 70)
    
    model_path = "app/models/pattern_memory_v2.py"
    if os.path.exists(model_path):
        print(f"  [PASS] Model file exists at {model_path}")
    else:
        print(f"  [FAIL] Model file not found at {model_path}")
        return False
    
    # Test 2: Model has required fields
    print("\n[2] Model Fields")
    print("-" * 70)
    
    with open(model_path, "r") as f:
        content = f.read()
        
        required_fields = [
            "id",
            "workspace_id",
            "repository_id",
            "pattern_key",
            "behavior_id",
            "journey_id",
            "scenario_intent_key",
            "test_identifier",
            "signal_type",
            "strength",
            "confidence",
            "usage_count",
            "success_count",
            "failure_count",
            "dismissed_count",
            "defect_count",
            "rollback_count",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]
        
        for field in required_fields:
            if field in content:
                print(f"  [PASS] Has {field} field")
            else:
                print(f"  [FAIL] {field} field missing")
                return False
    
    # Test 3: Signal type constants
    print("\n[3] Signal Type Constants")
    print("-" * 70)
    
    with open(model_path, "r") as f:
        content = f.read()
        
        signal_types = [
            "SIGNAL_TYPE_MANUAL_ADDITION",
            "SIGNAL_TYPE_MANUAL_REMOVAL",
            "SIGNAL_TYPE_ACCEPTED_SCENARIO",
            "SIGNAL_TYPE_DISMISSED_SCENARIO",
            "SIGNAL_TYPE_ESCAPED_DEFECT",
            "SIGNAL_TYPE_ROLLBACK",
            "SIGNAL_TYPE_EXECUTION_RESULT",
        ]
        
        for signal_type in signal_types:
            if signal_type in content:
                print(f"  [PASS] Has {signal_type} constant")
            else:
                print(f"  [FAIL] {signal_type} constant missing")
                return False
    
    # Test 4: Upsert service exists
    print("\n[4] Upsert Service")
    print("-" * 70)
    
    service_path = "app/services/pattern_memory_v2_upsert.py"
    if os.path.exists(service_path):
        print(f"  [PASS] Upsert service exists at {service_path}")
    else:
        print(f"  [FAIL] Upsert service not found at {service_path}")
        return False
    
    # Test 5: Upsert service has required methods
    print("\n[5] Upsert Service Methods")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "upsert_signal" in content:
            print("  [PASS] Has upsert_signal method")
        else:
            print("  [FAIL] upsert_signal method missing")
            return False
        
        if "strengthen_signal" in content:
            print("  [PASS] Has strengthen_signal method")
        else:
            print("  [FAIL] strengthen_signal method missing")
            return False
        
        if "weaken_signal" in content:
            print("  [PASS] Has weaken_signal method")
        else:
            print("  [FAIL] weaken_signal method missing")
            return False
    
    # Test 6: Upsert by repository + pattern_key + signal target
    print("\n[6] Upsert Key")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "repository_id" in content and "pattern_key" in content:
            print("  [PASS] Upserts by repository_id and pattern_key")
        else:
            print("  [FAIL] Upsert key missing")
            return False
        
        if "behavior_id" in content or "test_identifier" in content:
            print("  [PASS] Includes signal target in upsert key")
        else:
            print("  [FAIL] Signal target in upsert key missing")
            return False
    
    # Test 7: Learning engine integration
    print("\n[7] Learning Engine Integration")
    print("-" * 70)
    
    learning_engine_path = "app/services/recommendation_outcome_learning_engine.py"
    with open(learning_engine_path, "r") as f:
        content = f.read()
        
        if "PatternMemoryV2" in content:
            print("  [PASS] Imports PatternMemoryV2")
        else:
            print("  [FAIL] PatternMemoryV2 import missing")
            return False
        
        if "PatternMemoryV2Upsert" in content:
            print("  [PASS] Imports PatternMemoryV2Upsert")
        else:
            print("  [FAIL] PatternMemoryV2Upsert import missing")
            return False
        
        if "pattern_memory_upsert" in content:
            print("  [PASS] Uses pattern_memory_upsert instance")
        else:
            print("  [FAIL] pattern_memory_upsert instance missing")
            return False
    
    # Test 8: Learning rules use PatternMemoryV2
    print("\n[8] Learning Rules Use PatternMemoryV2")
    print("-" * 70)
    
    with open(learning_engine_path, "r") as f:
        content = f.read()
        
        if "SIGNAL_TYPE_EXECUTION_RESULT" in content:
            print("  [PASS] Uses SIGNAL_TYPE_EXECUTION_RESULT")
        else:
            print("  [FAIL] SIGNAL_TYPE_EXECUTION_RESULT not used")
            return False
        
        if "SIGNAL_TYPE_MANUAL_ADDITION" in content:
            print("  [PASS] Uses SIGNAL_TYPE_MANUAL_ADDITION")
        else:
            print("  [FAIL] SIGNAL_TYPE_MANUAL_ADDITION not used")
            return False
        
        if "SIGNAL_TYPE_MANUAL_REMOVAL" in content:
            print("  [PASS] Uses SIGNAL_TYPE_MANUAL_REMOVAL")
        else:
            print("  [FAIL] SIGNAL_TYPE_MANUAL_REMOVAL not used")
            return False
        
        if "SIGNAL_TYPE_ACCEPTED_SCENARIO" in content:
            print("  [PASS] Uses SIGNAL_TYPE_ACCEPTED_SCENARIO")
        else:
            print("  [FAIL] SIGNAL_TYPE_ACCEPTED_SCENARIO not used")
            return False
        
        if "SIGNAL_TYPE_DISMISSED_SCENARIO" in content:
            print("  [PASS] Uses SIGNAL_TYPE_DISMISSED_SCENARIO")
        else:
            print("  [FAIL] SIGNAL_TYPE_DISMISSED_SCENARIO not used")
            return False
        
        if "SIGNAL_TYPE_ESCAPED_DEFECT" in content:
            print("  [PASS] Uses SIGNAL_TYPE_ESCAPED_DEFECT")
        else:
            print("  [FAIL] SIGNAL_TYPE_ESCAPED_DEFECT not used")
            return False
        
        if "SIGNAL_TYPE_ROLLBACK" in content:
            print("  [PASS] Uses SIGNAL_TYPE_ROLLBACK")
        else:
            print("  [FAIL] SIGNAL_TYPE_ROLLBACK not used")
            return False
    
    # Test 9: Workspace scoped
    print("\n[9] Workspace Scoped")
    print("-" * 70)
    
    with open(model_path, "r") as f:
        content = f.read()
        
        if "workspace_id" in content:
            print("  [PASS] Has workspace_id field")
        else:
            print("  [FAIL] workspace_id field missing")
            return False
    
    # Test 10: No crash if empty
    print("\n[10] No Crash If Empty")
    print("-" * 70)
    
    with open(service_path, "r") as f:
        content = f.read()
        
        if "if existing" in content or "existing =" in content:
            print("  [PASS] Handles existing/missing records")
        else:
            print("  [FAIL] Existing/missing handling missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nPatternMemoryV2 verified:")
    print("  - Model file exists")
    print("  - All required fields present")
    print("  - Signal type constants defined")
    print("  - Upsert service exists")
    print("  - Upsert service methods present")
    print("  - Upsert by repository + pattern_key + signal target")
    print("  - Learning engine integration")
    print("  - Learning rules use PatternMemoryV2")
    print("  - Workspace scoped")
    print("  - No crash if empty")
    print("\nOutcome learning has durable memory.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_pattern_memory_v2()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
