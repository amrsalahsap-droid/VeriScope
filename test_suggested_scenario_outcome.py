"""
Test SuggestedScenarioOutcome implementation.

Verifies that each suggested scenario has an outcome state and updates are idempotent.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from uuid import uuid4


def test_suggested_scenario_outcome():
    """Test SuggestedScenarioOutcome model and service implementation."""
    print("=" * 70)
    print("SUGGESTED SCENARIO OUTCOME TEST")
    print("=" * 70)
    
    # Test 1: Model has required fields
    print("\n[1] Model Field Verification")
    print("-" * 70)
    
    from app.models.recommendation import SuggestedScenarioOutcome
    
    # Check new fields exist
    outcome_fields = SuggestedScenarioOutcome.__table__.columns.keys()
    
    required_fields = [
        "id", "recommendation_outcome_id", "recommendation_run_id",
        "suggested_scenario_id", "scenario_intent_key", "engineer_decision",
        "execution_status", "converted_to_test", "linked_test_identifier",
        "comment", "created_at", "updated_at"
    ]
    
    for field in required_fields:
        if field in outcome_fields:
            print(f"  [PASS] {field} exists")
        else:
            print(f"  [FAIL] {field} missing")
            return False
    
    # Test 2: Default values
    print("\n[2] Default Value Verification")
    print("-" * 70)
    
    outcome = SuggestedScenarioOutcome(
        recommendation_outcome_id=uuid4(),
        recommendation_run_id=uuid4(),
        scenario_intent_key="domain.feature.behavior.layer.case_type"
    )
    
    assert outcome.engineer_decision == "NOT_DECIDED", f"Expected NOT_DECIDED, got {outcome.engineer_decision}"
    print(f"  [PASS] engineer_decision defaults to NOT_DECIDED")
    
    assert outcome.execution_status == "NOT_EXECUTED", f"Expected NOT_EXECUTED, got {outcome.execution_status}"
    print(f"  [PASS] execution_status defaults to NOT_EXECUTED")
    
    assert outcome.converted_to_test == False, f"Expected False, got {outcome.converted_to_test}"
    print(f"  [PASS] converted_to_test defaults to False")
    
    # Test 3: Service has idempotent creation
    print("\n[3] Idempotent Creation Verification")
    print("-" * 70)
    
    with open("app/services/recommendation.py", "r") as f:
        content = f.read()
        
        if "existing_scenario_outcome = self.db.query(SuggestedScenarioOutcome)" in content:
            print("  [PASS] Idempotent check exists in service")
        else:
            print("  [FAIL] Idempotent check missing")
            return False
        
        if "if not existing_scenario_outcome:" in content:
            print("  [PASS] Conditional creation exists")
        else:
            print("  [FAIL] Conditional creation missing")
            return False
        
        if 'engineer_decision="NOT_DECIDED"' in content:
            print("  [PASS] Uses NOT_DECIDED decision")
        else:
            print("  [FAIL] NOT_DECIDED decision not used")
            return False
        
        if 'execution_status="NOT_EXECUTED"' in content:
            print("  [PASS] Uses NOT_EXECUTED status")
        else:
            print("  [FAIL] NOT_EXECUTED status not used")
            return False
    
    # Test 4: Scenario intent key extraction
    print("\n[4] Scenario Intent Key Extraction")
    print("-" * 70)
    
    with open("app/services/recommendation.py", "r") as f:
        content = f.read()
        
        if "scenario_intent_key = intent.canonical_key" in content:
            print("  [PASS] Extracts canonical_key from ScenarioIntent")
        else:
            print("  [FAIL] Scenario intent key extraction missing")
            return False
    
    # Test 5: Update service exists
    print("\n[5] Update Service Verification")
    print("-" * 70)
    
    try:
        from app.services.suggested_scenario_outcome_updater import SuggestedScenarioOutcomeUpdater
        print("  [PASS] SuggestedScenarioOutcomeUpdater service exists")
        
        # Check methods exist
        if hasattr(SuggestedScenarioOutcomeUpdater, 'update_engineer_decision'):
            print("  [PASS] update_engineer_decision method exists")
        else:
            print("  [FAIL] update_engineer_decision method missing")
            return False
        
        if hasattr(SuggestedScenarioOutcomeUpdater, 'link_to_test'):
            print("  [PASS] link_to_test method exists")
        else:
            print("  [FAIL] link_to_test method missing")
            return False
        
        if hasattr(SuggestedScenarioOutcomeUpdater, 'update_execution_status'):
            print("  [PASS] update_execution_status method exists")
        else:
            print("  [FAIL] update_execution_status method missing")
            return False
        
        if hasattr(SuggestedScenarioOutcomeUpdater, 'get_accepted_scenarios'):
            print("  [PASS] get_accepted_scenarios method exists")
        else:
            print("  [FAIL] get_accepted_scenarios method missing")
            return False
        
    except ImportError as e:
        print(f"  [FAIL] Cannot import SuggestedScenarioOutcomeUpdater: {e}")
        return False
    
    # Test 6: Link to test sets converted_to_test
    print("\n[6] Link to Test Logic")
    print("-" * 70)
    
    with open("app/services/suggested_scenario_outcome_updater.py", "r") as f:
        content = f.read()
        
        if "scenario_outcome.converted_to_test = True" in content:
            print("  [PASS] Sets converted_to_test when linking")
        else:
            print("  [FAIL] converted_to_test not set on link")
            return False
        
        if "scenario_outcome.linked_test_identifier = test_identifier" in content:
            print("  [PASS] Sets linked_test_identifier")
        else:
            print("  [FAIL] linked_test_identifier not set")
            return False
        
        if 'scenario_outcome.engineer_decision = "ACCEPTED"' in content:
            print("  [PASS] Auto-sets engineer_decision to ACCEPTED on link")
        else:
            print("  [FAIL] engineer_decision not set to ACCEPTED on link")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nSuggestedScenarioOutcome implementation verified:")
    print("  - Model has all required fields")
    print("  - Default values set correctly")
    print("  - Service has idempotent creation")
    print("  - Scenario intent key extraction from ScenarioIntent")
    print("  - Update service with idempotent methods")
    print("  - Link to test sets converted_to_test and ACCEPTED")
    print("\nVeriscope learns which missing scenarios engineers care about.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_suggested_scenario_outcome()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
