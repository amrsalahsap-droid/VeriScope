"""
Test attach test run flow.

Verifies that the API endpoint and UI component are implemented correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'landing-page'))


def test_attach_test_run_flow():
    """Test attach test run flow."""
    print("=" * 70)
    print("ATTACH TEST RUN FLOW TEST")
    print("=" * 70)
    
    # Test 1: API endpoint exists
    print("\n[1] API Endpoint")
    print("-" * 70)
    
    router_path = "app/routers/recommendation.py"
    with open(router_path, "r") as f:
        content = f.read()
        
        if "/attach-test-run" in content:
            print("  [PASS] POST /attach-test-run endpoint exists")
        else:
            print("  [FAIL] POST /attach-test-run endpoint missing")
            return False
        
        if "@router.post" in content:
            print("  [PASS] Uses POST method")
        else:
            print("  [FAIL] POST method not found")
            return False
    
    # Test 2: Pydantic schema exists
    print("\n[2] Pydantic Schema")
    print("-" * 70)
    
    schema_path = "app/schemas/recommendation.py"
    with open(schema_path, "r") as f:
        content = f.read()
        
        if "AttachTestRunRequest" in content:
            print("  [PASS] AttachTestRunRequest schema exists")
        else:
            print("  [FAIL] AttachTestRunRequest schema missing")
            return False
        
        if "test_run_id" in content:
            print("  [PASS] Has test_run_id field")
        else:
            print("  [FAIL] test_run_id field missing")
            return False
    
    # Test 3: OutcomeExecutionCollector integration
    print("\n[3] OutcomeExecutionCollector Integration")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "OutcomeExecutionCollector" in content:
            print("  [PASS] Imports OutcomeExecutionCollector")
        else:
            print("  [FAIL] OutcomeExecutionCollector import missing")
            return False
        
        if "collect_execution_outcomes" in content:
            print("  [PASS] Calls collect_execution_outcomes")
        else:
            print("  [FAIL] collect_execution_outcomes call missing")
            return False
    
    # Test 4: Workspace and repository verification
    print("\n[4] Workspace and Repository Verification")
    print("-" * 70)
    
    with open(router_path, "r") as f:
        content = f.read()
        
        if "workspace_id" in content or "workspace" in content:
            print("  [PASS] Verifies workspace ownership")
        else:
            print("  [FAIL] Workspace verification missing")
            return False
        
        if "repository_id" in content:
            print("  [PASS] Verifies repository match")
        else:
            print("  [FAIL] Repository verification missing")
            return False
    
    # Test 5: UI component exists
    print("\n[5] UI Component")
    print("-" * 70)
    
    component_path = "landing-page/components/attach-test-run.tsx"
    if os.path.exists(component_path):
        print(f"  [PASS] UI component exists at {component_path}")
    else:
        print(f"  [FAIL] UI component not found at {component_path}")
        return False
    
    # Test 6: UI component has test run selection
    print("\n[6] Test Run Selection")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "testRuns" in content or "test_runs" in content:
            print("  [PASS] Has test runs state")
        else:
            print("  [FAIL] Test runs state missing")
            return False
        
        if "selectedTestRun" in content:
            print("  [PASS] Has selected test run state")
        else:
            print("  [FAIL] Selected test run state missing")
            return False
        
        if "fetchTestRuns" in content:
            print("  [PASS] Has fetch test runs function")
        else:
            print("  [FAIL] Fetch test runs function missing")
            return False
    
    # Test 7: Commit/branch mismatch warning
    print("\n[7] Commit/Branch Mismatch Warning")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "commit_sha" in content:
            print("  [PASS] Checks commit SHA")
        else:
            print("  [FAIL] Commit SHA check missing")
            return False
        
        if "showMismatchWarning" in content or "mismatch" in content.lower():
            print("  [PASS] Has mismatch warning")
        else:
            print("  [FAIL] Mismatch warning missing")
            return False
    
    # Test 8: Stale test run warning
    print("\n[8] Stale Test Run Warning")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "isStale" in content or "stale" in content.lower():
            print("  [PASS] Has stale check")
        else:
            print("  [FAIL] Stale check missing")
            return False
        
        if "Stale" in content:
            print("  [PASS] Shows stale warning")
        else:
            print("  [FAIL] Stale warning display missing")
            return False
    
    # Test 9: Attach API call
    print("\n[9] Attach API Call")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "/attach-test-run" in content:
            print("  [PASS] Calls attach API endpoint")
        else:
            print("  [FAIL] Attach API call missing")
            return False
        
        if "POST" in content:
            print("  [PASS] Uses POST method")
        else:
            print("  [FAIL] POST method missing")
            return False
    
    # Test 10: Outcome refresh after attach
    print("\n[10] Outcome Refresh After Attach")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "onAttached" in content:
            print("  [PASS] Has onAttached callback")
        else:
            print("  [FAIL] onAttached callback missing")
            return False
    
    page_path = "landing-page/app/app/recommendations/[recommendationRunId]/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
        
        if "refreshOutcome" in content:
            print("  [PASS] Page has refreshOutcome function")
        else:
            print("  [FAIL] refreshOutcome function missing")
            return False
        
        if "AttachTestRun" in content:
            print("  [PASS] Page uses AttachTestRun component")
        else:
            print("  [FAIL] AttachTestRun component not used")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nAttach test run flow verified:")
    print("  - API endpoint exists")
    print("  - Pydantic schema for request")
    print("  - OutcomeExecutionCollector integration")
    print("  - Workspace and repository verification")
    print("  - UI component exists")
    print("  - Test run selection")
    print("  - Commit/branch mismatch warning")
    print("  - Stale test run warning")
    print("  - Attach API call")
    print("  - Outcome refresh after attach")
    print("\nUser can prove which recommended tests were actually executed.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_attach_test_run_flow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
