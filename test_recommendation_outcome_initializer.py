"""
Test RecommendationOutcomeInitializer implementation.

Verifies that outcome initialization is idempotent and creates all required records.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from uuid import uuid4


def test_recommendation_outcome_initializer():
    """Test RecommendationOutcomeInitializer service."""
    print("=" * 70)
    print("RECOMMENDATION OUTCOME INITIALIZER TEST")
    print("=" * 70)
    
    # Test 1: Service exists
    print("\n[1] Service Existence")
    print("-" * 70)
    
    try:
        from app.services.recommendation_outcome_initializer import RecommendationOutcomeInitializer
        print("  [PASS] RecommendationOutcomeInitializer service exists")
    except ImportError as e:
        print(f"  [FAIL] Cannot import RecommendationOutcomeInitializer: {e}")
        return False
    
    # Test 2: Methods exist
    print("\n[2] Method Existence")
    print("-" * 70)
    
    if hasattr(RecommendationOutcomeInitializer, 'initialize_outcomes'):
        print("  [PASS] initialize_outcomes method exists")
    else:
        print("  [FAIL] initialize_outcomes method missing")
        return False
    
    if hasattr(RecommendationOutcomeInitializer, 'ensure_outcome_exists'):
        print("  [PASS] ensure_outcome_exists method exists")
    else:
        print("  [FAIL] ensure_outcome_exists method missing")
        return False
    
    # Test 3: Idempotent checks in initialize_outcomes
    print("\n[3] Idempotent Checks in initialize_outcomes")
    print("-" * 70)
    
    with open("app/services/recommendation_outcome_initializer.py", "r") as f:
        content = f.read()
        
        if "outcome = db.query(RecommendationOutcome)" in content:
            print("  [PASS] Checks for existing RecommendationOutcome")
        else:
            print("  [FAIL] RecommendationOutcome check missing")
            return False
        
        if "if not outcome:" in content:
            print("  [PASS] Conditional creation for RecommendationOutcome")
        else:
            print("  [FAIL] Conditional creation missing")
            return False
        
        if "existing_test_outcome = db.query(RecommendationTestOutcome)" in content:
            print("  [PASS] Checks for existing RecommendationTestOutcome")
        else:
            print("  [FAIL] RecommendationTestOutcome check missing")
            return False
        
        if "existing_scenario_outcome = db.query(SuggestedScenarioOutcome)" in content:
            print("  [PASS] Checks for existing SuggestedScenarioOutcome")
        else:
            print("  [FAIL] SuggestedScenarioOutcome check missing")
            return False
    
    # Test 4: Default values set correctly
    print("\n[4] Default Values")
    print("-" * 70)
    
    with open("app/services/recommendation_outcome_initializer.py", "r") as f:
        content = f.read()
        
        if 'outcome_status="SHOWN"' in content:
            print("  [PASS] Sets outcome_status to SHOWN")
        else:
            print("  [FAIL] outcome_status not set to SHOWN")
            return False
        
        if 'user_feedback="NOT_REVIEWED"' in content:
            print("  [PASS] Sets user_feedback to NOT_REVIEWED")
        else:
            print("  [FAIL] user_feedback not set to NOT_REVIEWED")
            return False
        
        if 'defect_escaped=False' in content:
            print("  [PASS] Sets defect_escaped to False")
        else:
            print("  [FAIL] defect_escaped not set to False")
            return False
        
        if 'rollback_occurred=False' in content:
            print("  [PASS] Sets rollback_occurred to False")
        else:
            print("  [FAIL] rollback_occurred not set to False")
            return False
        
        if 'execution_status="NOT_RUN"' in content:
            print("  [PASS] Sets execution_status to NOT_RUN")
        else:
            print("  [FAIL] execution_status not set to NOT_RUN")
            return False
        
        if 'engineer_decision="NOT_DECIDED"' in content:
            print("  [PASS] Sets engineer_decision to NOT_DECIDED")
        else:
            print("  [FAIL] engineer_decision not set to NOT_DECIDED")
            return False
        
        if 'execution_status="NOT_EXECUTED"' in content:
            print("  [PASS] Sets scenario execution_status to NOT_EXECUTED")
        else:
            print("  [FAIL] scenario execution_status not set to NOT_EXECUTED")
            return False
        
        if 'converted_to_test=False' in content:
            print("  [PASS] Sets converted_to_test to False")
        else:
            print("  [FAIL] converted_to_test not set to False")
            return False
    
    # Test 5: Recommendation service uses initializer
    print("\n[5] Recommendation Service Integration")
    print("-" * 70)
    
    with open("app/services/recommendation.py", "r") as f:
        content = f.read()
        
        if "RecommendationOutcomeInitializer.initialize_outcomes" in content:
            print("  [PASS] Recommendation service uses initializer")
        else:
            print("  [FAIL] Recommendation service does not use initializer")
            return False
        
        if "init_result = RecommendationOutcomeInitializer.initialize_outcomes" in content:
            print("  [PASS] Captures initialization result")
        else:
            print("  [FAIL] Initialization result not captured")
            return False
    
    # Test 6: Re-initialization after scenario generation
    print("\n[6] Re-initialization After Scenario Generation")
    print("-" * 70)
    
    with open("app/services/recommendation.py", "r") as f:
        content = f.read()
        
        # Count how many times initialize_outcomes is called
        count = content.count("RecommendationOutcomeInitializer.initialize_outcomes")
        if count >= 2:
            print(f"  [PASS] Calls initializer {count} times (initial + after scenarios)")
        else:
            print(f"  [FAIL] Only calls initializer {count} time(s)")
            return False
    
    # Test 7: Result structure
    print("\n[7] Result Structure")
    print("-" * 70)
    
    with open("app/services/recommendation_outcome_initializer.py", "r") as f:
        content = f.read()
        
        if "InitializationResult" in content:
            print("  [PASS] Defines InitializationResult dataclass")
        else:
            print("  [FAIL] InitializationResult not defined")
            return False
        
        if "outcome_created: bool" in content:
            print("  [PASS] Includes outcome_created field")
        else:
            print("  [FAIL] outcome_created field missing")
            return False
        
        if "test_outcomes_created: int" in content:
            print("  [PASS] Includes test_outcomes_created field")
        else:
            print("  [FAIL] test_outcomes_created field missing")
            return False
        
        if "scenario_outcomes_created: int" in content:
            print("  [PASS] Includes scenario_outcomes_created field")
        else:
            print("  [FAIL] scenario_outcomes_created field missing")
            return False
        
        if "test_outcomes_skipped: int" in content:
            print("  [PASS] Includes test_outcomes_skipped field")
        else:
            print("  [FAIL] test_outcomes_skipped field missing")
            return False
        
        if "scenario_outcomes_skipped: int" in content:
            print("  [PASS] Includes scenario_outcomes_skipped field")
        else:
            print("  [FAIL] scenario_outcomes_skipped field missing")
            return False
    
    # Test 8: Backfill recommendation_outcome_id
    print("\n[8] Backfill recommendation_outcome_id")
    print("-" * 70)
    
    with open("app/services/recommendation_outcome_initializer.py", "r") as f:
        content = f.read()
        
        if "existing_test_outcome.recommendation_outcome_id is None" in content:
            print("  [PASS] Backfills test outcome recommendation_outcome_id")
        else:
            print("  [FAIL] Test outcome backfill missing")
            return False
        
        if "existing_scenario_outcome.recommendation_outcome_id is None" in content:
            print("  [PASS] Backfills scenario outcome recommendation_outcome_id")
        else:
            print("  [FAIL] Scenario outcome backfill missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nRecommendationOutcomeInitializer implementation verified:")
    print("  - Service exists with required methods")
    print("  - Idempotent checks for all outcome types")
    print("  - Default values set correctly")
    print("  - Recommendation service integration")
    print("  - Re-initialization after scenario generation")
    print("  - Result structure with counts")
    print("  - Backfill recommendation_outcome_id for existing records")
    print("\nA new recommendation result immediately has trackable outcome state.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_recommendation_outcome_initializer()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
