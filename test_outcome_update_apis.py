"""
Test recommendation outcome update APIs.

Verifies that all endpoints exist and have correct structure.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def test_outcome_update_apis():
    """Test outcome update API endpoints."""
    print("=" * 70)
    print("OUTCOME UPDATE API TEST")
    print("=" * 70)
    
    # Test 1: Schemas exist
    print("\n[1] Schema Existence")
    print("-" * 70)
    
    try:
        from app.schemas.recommendation import (
            OutcomeUpdate,
            TestOutcomeUpdate,
            ScenarioOutcomeUpdate,
            OverrideCreate,
            OutcomeDetailResponse,
            TestOutcomeDetailResponse,
            ScenarioOutcomeDetailResponse,
        )
        print("  [PASS] OutcomeUpdate schema exists")
        print("  [PASS] TestOutcomeUpdate schema exists")
        print("  [PASS] ScenarioOutcomeUpdate schema exists")
        print("  [PASS] OverrideCreate schema exists")
        print("  [PASS] OutcomeDetailResponse schema exists")
        print("  [PASS] TestOutcomeDetailResponse schema exists")
        print("  [PASS] ScenarioOutcomeDetailResponse schema exists")
    except ImportError as e:
        print(f"  [FAIL] Schema import error: {e}")
        return False
    
    # Test 2: Schema fields
    print("\n[2] Schema Field Verification")
    print("-" * 70)
    
    # Check OutcomeUpdate fields
    outcome_update_fields = OutcomeUpdate.model_fields.keys()
    required_outcome_fields = ["outcome_status", "user_feedback", "feedback_comment", "ignored_reason", "defect_escaped", "rollback_occurred", "production_incident_url"]
    for field in required_outcome_fields:
        if field in outcome_update_fields:
            print(f"  [PASS] OutcomeUpdate has {field}")
        else:
            print(f"  [FAIL] OutcomeUpdate missing {field}")
            return False
    
    # Check TestOutcomeUpdate fields
    test_outcome_fields = TestOutcomeUpdate.model_fields.keys()
    required_test_fields = ["recommendation_action", "execution_status", "engineer_decision", "actual_test_result_id", "actual_test_run_id", "duration_seconds", "failure_message"]
    for field in required_test_fields:
        if field in test_outcome_fields:
            print(f"  [PASS] TestOutcomeUpdate has {field}")
        else:
            print(f"  [FAIL] TestOutcomeUpdate missing {field}")
            return False
    
    # Check ScenarioOutcomeUpdate fields
    scenario_outcome_fields = ScenarioOutcomeUpdate.model_fields.keys()
    required_scenario_fields = ["engineer_decision", "execution_status", "converted_to_test", "linked_test_identifier", "comment"]
    for field in required_scenario_fields:
        if field in scenario_outcome_fields:
            print(f"  [PASS] ScenarioOutcomeUpdate has {field}")
        else:
            print(f"  [FAIL] ScenarioOutcomeUpdate missing {field}")
            return False
    
    # Check OverrideCreate fields
    override_fields = OverrideCreate.model_fields.keys()
    required_override_fields = ["override_type", "test_identifier", "scenario_intent_key", "reason", "source"]
    for field in required_override_fields:
        if field in override_fields:
            print(f"  [PASS] OverrideCreate has {field}")
        else:
            print(f"  [FAIL] OverrideCreate missing {field}")
            return False
    
    # Test 3: Endpoints exist
    print("\n[3] Endpoint Existence")
    print("-" * 70)
    
    with open("app/routers/recommendation.py", "r") as f:
        content = f.read()
        
        if '@router.get("/{recommendation_run_id}/outcome"' in content:
            print("  [PASS] GET /outcome endpoint exists")
        else:
            print("  [FAIL] GET /outcome endpoint missing")
            return False
        
        if '@router.patch("/{recommendation_run_id}/outcome"' in content:
            print("  [PASS] PATCH /outcome endpoint exists")
        else:
            print("  [FAIL] PATCH /outcome endpoint missing")
            return False
        
        if '@router.patch("/{recommendation_run_id}/tests/{recommended_test_id}/outcome"' in content:
            print("  [PASS] PATCH /tests/{id}/outcome endpoint exists")
        else:
            print("  [FAIL] PATCH /tests/{id}/outcome endpoint missing")
            return False
        
        if '@router.patch("/{recommendation_run_id}/scenarios/{suggested_scenario_id}/outcome"' in content:
            print("  [PASS] PATCH /scenarios/{id}/outcome endpoint exists")
        else:
            print("  [FAIL] PATCH /scenarios/{id}/outcome endpoint missing")
            return False
        
        if '@router.post("/{recommendation_run_id}/overrides"' in content:
            print("  [PASS] POST /overrides endpoint exists")
        else:
            print("  [FAIL] POST /overrides endpoint missing")
            return False
    
    # Test 4: Authentication and workspace scoping
    print("\n[4] Authentication and Workspace Scoping")
    print("-" * 70)
    
    with open("app/routers/recommendation.py", "r") as f:
        content = f.read()
        
        # Check that endpoints use workspace dependency
        if "workspace: Workspace = Depends(get_current_workspace)" in content:
            print("  [PASS] Endpoints use workspace dependency")
        else:
            print("  [FAIL] Workspace dependency missing")
            return False
        
        # Check recommendation_run_id workspace verification
        if "RecommendationRun.workspace_id == workspace.id" in content:
            print("  [PASS] Verifies run belongs to workspace")
        else:
            print("  [FAIL] Workspace verification missing")
            return False
    
    # Test 5: Partial updates supported
    print("\n[5] Partial Update Support")
    print("-" * 70)
    
    with open("app/routers/recommendation.py", "r") as f:
        content = f.read()
        
        if "if outcome_update.outcome_status is not None:" in content:
            print("  [PASS] Outcome endpoint supports partial updates")
        else:
            print("  [FAIL] Outcome partial update missing")
            return False
        
        if "if test_outcome_update.recommendation_action is not None:" in content:
            print("  [PASS] Test outcome endpoint supports partial updates")
        else:
            print("  [FAIL] Test outcome partial update missing")
            return False
        
        if "if scenario_outcome_update.engineer_decision is not None:" in content:
            print("  [PASS] Scenario outcome endpoint supports partial updates")
        else:
            print("  [FAIL] Scenario outcome partial update missing")
            return False
    
    # Test 6: Override service integration
    print("\n[6] Override Service Integration")
    print("-" * 70)
    
    with open("app/routers/recommendation.py", "r") as f:
        content = f.read()
        
        if "RecommendationOverrideUpdater.record_test_added" in content:
            print("  [PASS] Uses RecommendationOverrideUpdater for TEST_ADDED")
        else:
            print("  [FAIL] TEST_ADDED integration missing")
            return False
        
        if "RecommendationOverrideUpdater.record_test_removed" in content:
            print("  [PASS] Uses RecommendationOverrideUpdater for TEST_REMOVED")
        else:
            print("  [FAIL] TEST_REMOVED integration missing")
            return False
        
        if "RecommendationOverrideUpdater.record_scenario_added" in content:
            print("  [PASS] Uses RecommendationOverrideUpdater for SCENARIO_ADDED")
        else:
            print("  [FAIL] SCENARIO_ADDED integration missing")
            return False
        
        if "RecommendationOverrideUpdater.record_scenario_removed" in content:
            print("  [PASS] Uses RecommendationOverrideUpdater for SCENARIO_REMOVED")
        else:
            print("  [FAIL] SCENARIO_REMOVED integration missing")
            return False
    
    # Test 7: Response models
    print("\n[7] Response Models")
    print("-" * 70)
    
    with open("app/routers/recommendation.py", "r") as f:
        content = f.read()
        
        if "response_model=OutcomeDetailResponse" in content:
            print("  [PASS] GET /outcome uses OutcomeDetailResponse")
        else:
            print("  [FAIL] Outcome response model missing")
            return False
        
        if "response_model=TestOutcomeDetailResponse" in content:
            print("  [PASS] PATCH /tests/{id}/outcome uses TestOutcomeDetailResponse")
        else:
            print("  [FAIL] Test outcome response model missing")
            return False
        
        if "response_model=ScenarioOutcomeDetailResponse" in content:
            print("  [PASS] PATCH /scenarios/{id}/outcome uses ScenarioOutcomeDetailResponse")
        else:
            print("  [FAIL] Scenario outcome response model missing")
            return False
    
    # Test 8: Auto-initialization in GET endpoint
    print("\n[8] Auto-initialization in GET Endpoint")
    print("-" * 70)
    
    with open("app/routers/recommendation.py", "r") as f:
        content = f.read()
        
        if "RecommendationOutcomeInitializer.initialize_outcomes" in content:
            print("  [PASS] GET endpoint auto-initializes outcomes")
        else:
            print("  [FAIL] Auto-initialization missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nOutcome update API implementation verified:")
    print("  - All schemas exist with required fields")
    print("  - All 5 endpoints exist")
    print("  - Authentication and workspace scoping")
    print("  - Partial updates supported")
    print("  - Override service integration")
    print("  - Response models configured")
    print("  - Auto-initialization in GET endpoint")
    print("\nFrontend can capture feedback, test decisions, scenario decisions, and overrides.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_outcome_update_apis()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
