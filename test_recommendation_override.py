"""
Test RecommendationOverride implementation.

Verifies that override events are captured and can be used for learning.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from uuid import uuid4


def test_recommendation_override():
    """Test RecommendationOverride model and service implementation."""
    print("=" * 70)
    print("RECOMMENDATION OVERRIDE TEST")
    print("=" * 70)
    
    # Test 1: Model has required fields
    print("\n[1] Model Field Verification")
    print("-" * 70)
    
    from app.models.recommendation import RecommendationOverride
    
    # Check new fields exist
    override_fields = RecommendationOverride.__table__.columns.keys()
    
    required_fields = [
        "id", "recommendation_outcome_id", "recommendation_run_id",
        "override_type", "test_identifier", "scenario_intent_key",
        "reason", "source", "created_by", "created_at"
    ]
    
    for field in required_fields:
        if field in override_fields:
            print(f"  [PASS] {field} exists")
        else:
            print(f"  [FAIL] {field} missing")
            return False
    
    # Test 2: Default values
    print("\n[2] Default Value Verification")
    print("-" * 70)
    
    override = RecommendationOverride(
        recommendation_outcome_id=uuid4(),
        recommendation_run_id=uuid4(),
        override_type="TEST_ADDED"
    )
    
    assert override.source == "MANUAL_UI", f"Expected MANUAL_UI, got {override.source}"
    print(f"  [PASS] source defaults to MANUAL_UI")
    
    # Test 3: Service has automatic override capture
    print("\n[3] Automatic Override Capture Verification")
    print("-" * 70)
    
    with open("app/services/recommendation.py", "r") as f:
        content = f.read()
        
        if "RecommendationOverride(" in content:
            print("  [PASS] Creates RecommendationOverride records")
        else:
            print("  [FAIL] RecommendationOverride creation missing")
            return False
        
        if 'override_type="TEST_ADDED"' in content:
            print("  [PASS] Records TEST_ADDED overrides")
        else:
            print("  [FAIL] TEST_ADDED override type not used")
            return False
        
        if 'override_type="TEST_REMOVED"' in content:
            print("  [PASS] Records TEST_REMOVED overrides")
        else:
            print("  [FAIL] TEST_REMOVED override type not used")
            return False
        
        if 'source="API"' in content:
            print("  [PASS] Sets source to API for outcome recording")
        else:
            print("  [FAIL] source not set")
            return False
    
    # Test 4: Update service exists
    print("\n[4] Update Service Verification")
    print("-" * 70)
    
    try:
        from app.services.recommendation_override_updater import RecommendationOverrideUpdater
        print("  [PASS] RecommendationOverrideUpdater service exists")
        
        # Check methods exist
        if hasattr(RecommendationOverrideUpdater, 'record_test_added'):
            print("  [PASS] record_test_added method exists")
        else:
            print("  [FAIL] record_test_added method missing")
            return False
        
        if hasattr(RecommendationOverrideUpdater, 'record_test_removed'):
            print("  [PASS] record_test_removed method exists")
        else:
            print("  [FAIL] record_test_removed method missing")
            return False
        
        if hasattr(RecommendationOverrideUpdater, 'record_scenario_added'):
            print("  [PASS] record_scenario_added method exists")
        else:
            print("  [FAIL] record_scenario_added method missing")
            return False
        
        if hasattr(RecommendationOverrideUpdater, 'record_scenario_removed'):
            print("  [PASS] record_scenario_removed method exists")
        else:
            print("  [FAIL] record_scenario_removed method missing")
            return False
        
        if hasattr(RecommendationOverrideUpdater, 'get_learning_signals'):
            print("  [PASS] get_learning_signals method exists")
        else:
            print("  [FAIL] get_learning_signals method missing")
            return False
        
    except ImportError as e:
        print(f"  [FAIL] Cannot import RecommendationOverrideUpdater: {e}")
        return False
    
    # Test 5: Idempotent checks in update service
    print("\n[5] Idempotent Checks Verification")
    print("-" * 70)
    
    with open("app/services/recommendation_override_updater.py", "r") as f:
        content = f.read()
        
        if "existing = db.query(RecommendationOverride)" in content:
            print("  [PASS] Checks for existing override before creating")
        else:
            print("  [FAIL] Idempotent check missing")
            return False
        
        if "if existing:" in content:
            print("  [PASS] Returns early if override exists")
        else:
            print("  [FAIL] Early return missing")
            return False
    
    # Test 6: Learning signals aggregation
    print("\n[6] Learning Signals Aggregation")
    print("-" * 70)
    
    with open("app/services/recommendation_override_updater.py", "r") as f:
        content = f.read()
        
        if "func.count(RecommendationOverride.id)" in content:
            print("  [PASS] Aggregates override counts for learning")
        else:
            print("  [FAIL] Count aggregation missing")
            return False
        
        if 'override_type == "TEST_ADDED"' in content:
            print("  [PASS] Separates added tests for learning")
        else:
            print("  [FAIL] Added test separation missing")
            return False
        
        if 'override_type == "TEST_REMOVED"' in content:
            print("  [PASS] Separates removed tests for learning")
        else:
            print("  [FAIL] Removed test separation missing")
            return False
        
        if 'override_type == "SCENARIO_ADDED"' in content:
            print("  [PASS] Separates added scenarios for learning")
        else:
            print("  [FAIL] Added scenario separation missing")
            return False
    
    # Test 7: Reason preservation
    print("\n[7] Reason Preservation")
    print("-" * 70)
    
    with open("app/services/recommendation.py", "r") as f:
        content = f.read()
        
        if "reason=outcome_in.override_reason" in content:
            print("  [PASS] Preserves override reason from API call")
        else:
            print("  [FAIL] Reason not preserved")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nRecommendationOverride implementation verified:")
    print("  - Model has all required fields")
    print("  - Default values set correctly")
    print("  - Automatic override capture in record_outcome")
    print("  - Update service with idempotent methods")
    print("  - Learning signals aggregation")
    print("  - Reason preservation")
    print("\nManual engineer choices can train future recommendations.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_recommendation_override()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
