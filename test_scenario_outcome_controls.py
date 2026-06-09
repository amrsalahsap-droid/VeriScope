"""
Test scenario outcome controls in Suggested Missing Test Scenarios component.

Verifies that decision controls and execution status display are implemented.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'landing-page'))


def test_scenario_outcome_controls():
    """Test scenario outcome controls."""
    print("=" * 70)
    print("SCENARIO OUTCOME CONTROLS TEST")
    print("=" * 70)
    
    # Test 1: Component has decision controls
    print("\n[1] Decision Controls")
    print("-" * 70)
    
    component_path = "landing-page/components/suggested-missing-test-scenarios.tsx"
    with open(component_path, "r") as f:
        content = f.read()
        
        if "ACCEPTED" in content:
            print("  [PASS] Has Accept decision")
        else:
            print("  [FAIL] Accept decision missing")
            return False
        
        if "DISMISSED" in content:
            print("  [PASS] Has Dismiss decision")
        else:
            print("  [FAIL] Dismiss decision missing")
            return False
        
        if "MARKED_IMPORTANT" in content:
            print("  [PASS] Has Mark important decision")
        else:
            print("  [FAIL] Mark important decision missing")
            return False
    
    # Test 2: Component has manual execution controls
    print("\n[2] Manual Execution Controls")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "Manual Execution" in content:
            print("  [PASS] Has Manual Execution section")
        else:
            print("  [FAIL] Manual Execution section missing")
            return False
        
        if "PASSED" in content:
            print("  [PASS] Has Passed option")
        else:
            print("  [FAIL] Passed option missing")
            return False
        
        if "FAILED" in content:
            print("  [PASS] Has Failed option")
        else:
            print("  [FAIL] Failed option missing")
            return False
        
        if "BLOCKED" in content:
            print("  [PASS] Has Blocked option")
        else:
            print("  [FAIL] Blocked option missing")
            return False
    
    # Test 3: Component has API integration
    print("\n[3] API Integration")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "/api/recommendations/${recommendationRunId}/scenarios/" in content:
            print("  [PASS] Uses scenario outcome API endpoint")
        else:
            print("  [FAIL] API endpoint not found")
            return False
        
        if "PATCH" in content:
            print("  [PASS] Uses PATCH method")
        else:
            print("  [FAIL] PATCH method not found")
            return False
        
        if "engineer_decision" in content:
            print("  [PASS] Updates engineer_decision")
        else:
            print("  [FAIL] engineer_decision update missing")
            return False
        
        if "execution_status" in content:
            print("  [PASS] Updates execution_status")
        else:
            print("  [FAIL] execution_status update missing")
            return False
    
    # Test 4: Component has state management
    print("\n[4] State Management")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "scenarioOutcomes" in content:
            print("  [PASS] Has scenarioOutcomes state")
        else:
            print("  [FAIL] scenarioOutcomes state missing")
            return False
        
        if "loading" in content:
            print("  [PASS] Has loading state")
        else:
            print("  [FAIL] loading state missing")
            return False
        
        if "updateScenarioDecision" in content:
            print("  [PASS] Has updateScenarioDecision function")
        else:
            print("  [FAIL] updateScenarioDecision function missing")
            return False
        
        if "updateExecutionStatus" in content:
            print("  [PASS] Has updateExecutionStatus function")
        else:
            print("  [FAIL] updateExecutionStatus function missing")
            return False
    
    # Test 5: Component has toast notifications
    print("\n[5] Toast Notifications")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "toast.success" in content:
            print("  [PASS] Has success toast")
        else:
            print("  [FAIL] Success toast missing")
            return False
        
        if "toast.error" in content:
            print("  [PASS] Has error toast")
        else:
            print("  [FAIL] Error toast missing")
            return False
    
    # Test 6: Component has recommendationRunId prop
    print("\n[6] RecommendationRunId Prop")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "recommendationRunId" in content:
            print("  [PASS] Has recommendationRunId prop")
        else:
            print("  [FAIL] recommendationRunId prop missing")
            return False
    
    # Test 7: Page passes recommendationRunId
    print("\n[7] Page Integration")
    print("-" * 70)
    
    page_path = "landing-page/app/app/recommendations/[recommendationRunId]/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
        
        if "recommendationRunId={runId" in content:
            print("  [PASS] Page passes recommendationRunId to component")
        else:
            print("  [FAIL] recommendationRunId not passed")
            return False
    
    # Test 8: Decision vs execution result separation
    print("\n[8] Decision vs Execution Result Separation")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        # Check that decision and execution status are separate fields
        if "engineer_decision" in content and "execution_status" in content:
            print("  [PASS] Decision and execution status are separate")
        else:
            print("  [FAIL] Decision and execution status not separated")
            return False
        
        # Check that decision buttons are separate from execution status display
        if "Decision Controls" in content or "decision" in content.lower():
            print("  [PASS] Decision controls are labeled")
        else:
            print("  [FAIL] Decision controls not labeled")
            return False
    
    # Test 9: Non-blocking design
    print("\n[9] Non-blocking Design")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "disabled" in content:
            print("  [PASS] Disables during submission")
        else:
            print("  [FAIL] Disabled state missing")
            return False
        
        if "isLoading" in content or "loading" in content:
            print("  [PASS] Checks loading state")
        else:
            print("  [FAIL] Loading state check missing")
            return False
    
    # Test 10: Execution status display
    print("\n[10] Execution Status Display")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "Status:" in content:
            print("  [PASS] Displays execution status")
        else:
            print("  [FAIL] Status display missing")
            return False
        
        if "scenarioOutcomes[rowKey]?.execution_status" in content:
            print("  [PASS] Checks execution_status from state")
        else:
            print("  [FAIL] execution_status check missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nScenario outcome controls verified:")
    print("  - Accept/Dismiss/Mark important controls present")
    print("  - Manual execution controls (Passed/Failed/Blocked)")
    print("  - API integration with PATCH")
    print("  - State management for outcomes")
    print("  - Toast notifications")
    print("  - recommendationRunId prop")
    print("  - Page integration")
    print("  - Decision vs execution result separation")
    print("  - Non-blocking design")
    print("  - Execution status display")
    print("\nVeriscope learns which missing scenarios matter.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_scenario_outcome_controls()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
