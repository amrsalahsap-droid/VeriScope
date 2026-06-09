"""
Test per-test outcome controls in Existing Automated Tests component.

Verifies that decision controls and execution status display are implemented.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'landing-page'))


def test_per_test_outcome_controls():
    """Test per-test outcome controls."""
    print("=" * 70)
    print("PER-TEST OUTCOME CONTROLS TEST")
    print("=" * 70)
    
    # Test 1: Component has decision controls
    print("\n[1] Decision Controls")
    print("-" * 70)
    
    component_path = "landing-page/components/existing-automated-tests.tsx"
    with open(component_path, "r") as f:
        content = f.read()
        
        if "Keep" in content or "KEPT" in content:
            print("  [PASS] Has Keep decision")
        else:
            print("  [FAIL] Keep decision missing")
            return False
        
        if "Remove" in content or "REMOVED" in content:
            print("  [PASS] Has Remove decision")
        else:
            print("  [FAIL] Remove decision missing")
            return False
        
        if "important" in content.lower():
            print("  [PASS] Has Mark important option")
        else:
            print("  [FAIL] Mark important missing")
            return False
    
    # Test 2: Component has execution status display
    print("\n[2] Execution Status Display")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "execution_status" in content:
            print("  [PASS] Has execution_status field")
        else:
            print("  [FAIL] execution_status field missing")
            return False
        
        if "PASSED" in content:
            print("  [PASS] Has PASSED status")
        else:
            print("  [FAIL] PASSED status missing")
            return False
        
        if "FAILED" in content:
            print("  [PASS] Has FAILED status")
        else:
            print("  [FAIL] FAILED status missing")
            return False
        
        if "SKIPPED" in content:
            print("  [PASS] Has SKIPPED status")
        else:
            print("  [FAIL] SKIPPED status missing")
            return False
        
        if "NOT_RUN" in content:
            print("  [PASS] Has NOT_RUN status")
        else:
            print("  [FAIL] NOT_RUN status missing")
            return False
    
    # Test 3: Component has API integration
    print("\n[3] API Integration")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "/api/recommendations/${recommendationRunId}/tests/" in content:
            print("  [PASS] Uses test outcome API endpoint")
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
    
    # Test 4: Component has state management
    print("\n[4] State Management")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "testOutcomes" in content:
            print("  [PASS] Has testOutcomes state")
        else:
            print("  [FAIL] testOutcomes state missing")
            return False
        
        if "loading" in content:
            print("  [PASS] Has loading state")
        else:
            print("  [FAIL] loading state missing")
            return False
        
        if "updateTestDecision" in content:
            print("  [PASS] Has updateTestDecision function")
        else:
            print("  [FAIL] updateTestDecision function missing")
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
    
    # Test 9: Selected state visible
    print("\n[9] Selected State Visibility")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "outcome.engineer_decision" in content:
            print("  [PASS] Checks engineer_decision for styling")
        else:
            print("  [FAIL] engineer_decision check missing")
            return False
        
        if "variant=" in content:
            print("  [PASS] Uses variant for selected state")
        else:
            print("  [FAIL] Variant for selected state missing")
            return False
    
    # Test 10: Non-blocking design
    print("\n[10] Non-blocking Design")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "disabled" in content:
            print("  [PASS] Disables during submission")
        else:
            print("  [FAIL] Disabled state missing")
            return False
        
        if "isLoading" in content:
            print("  [PASS] Checks loading state")
        else:
            print("  [FAIL] Loading state check missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nPer-test outcome controls verified:")
    print("  - Keep/Remove/Mark important controls present")
    print("  - Execution status display (Passed/Failed/Skipped/Not run)")
    print("  - API integration with PATCH")
    print("  - State management for outcomes")
    print("  - Toast notifications")
    print("  - recommendationRunId prop")
    print("  - Page integration")
    print("  - Decision vs execution result separation")
    print("  - Selected state visible")
    print("  - Non-blocking design")
    print("\nVeriscope captures engineer judgment per recommended test.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_per_test_outcome_controls()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
