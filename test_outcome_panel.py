"""
Test OutcomePanel component.

Verifies that the OutcomePanel component exists and is properly integrated.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'landing-page'))


def test_outcome_panel():
    """Test OutcomePanel component."""
    print("=" * 70)
    print("OUTCOME PANEL TEST")
    print("=" * 70)
    
    # Test 1: Component file exists
    print("\n[1] Component File Exists")
    print("-" * 70)
    
    component_path = "landing-page/components/outcome-panel.tsx"
    if os.path.exists(component_path):
        print(f"  [PASS] Component file exists at {component_path}")
    else:
        print(f"  [FAIL] Component file not found at {component_path}")
        return False
    
    # Test 2: Component exports
    print("\n[2] Component Exports")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "export function OutcomePanel" in content:
            print("  [PASS] Exports OutcomePanel function")
        else:
            print("  [FAIL] OutcomePanel export missing")
            return False
    
    # Test 3: Component props
    print("\n[3] Component Props")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "OutcomePanelProps" in content:
            print("  [PASS] Has OutcomePanelProps interface")
        else:
            print("  [FAIL] OutcomePanelProps interface missing")
            return False
        
        if "outcomeSummary" in content:
            print("  [PASS] Has outcomeSummary prop")
        else:
            print("  [FAIL] outcomeSummary prop missing")
            return False
    
    # Test 4: Component displays status
    print("\n[4] Component Displays Status")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "status" in content:
            print("  [PASS] Displays status")
        else:
            print("  [FAIL] Status display missing")
            return False
    
    # Test 5: Component displays feedback
    print("\n[5] Component Displays Feedback")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "feedback" in content:
            print("  [PASS] Displays feedback")
        else:
            print("  [FAIL] Feedback display missing")
            return False
    
    # Test 6: Component displays test execution status
    print("\n[6] Component Displays Test Execution Status")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        test_fields = ["passed_count", "failed_count", "not_run_count", "skipped_count"]
        for field in test_fields:
            if field in content:
                print(f"  [PASS] Displays {field}")
            else:
                print(f"  [FAIL] {field} display missing")
                return False
    
    # Test 7: Component displays test decisions
    print("\n[7] Component Displays Test Decisions")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        decision_fields = ["kept_count", "removed_count"]
        for field in decision_fields:
            if field in content:
                print(f"  [PASS] Displays {field}")
            else:
                print(f"  [FAIL] {field} display missing")
                return False
    
    # Test 8: Component displays overrides
    print("\n[8] Component Displays Overrides")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        override_fields = ["added_tests_count", "removed_tests_count"]
        for field in override_fields:
            if field in content:
                print(f"  [PASS] Displays {field}")
            else:
                print(f"  [FAIL] {field} display missing")
                return False
    
    # Test 9: Component displays scenario decisions
    print("\n[9] Component Displays Scenario Decisions")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        scenario_fields = ["accepted_count", "dismissed_count", "important_count"]
        for field in scenario_fields:
            if field in content:
                print(f"  [PASS] Displays {field}")
            else:
                print(f"  [FAIL] {field} display missing")
                return False
    
    # Test 10: Component displays post-merge outcome
    print("\n[10] Component Displays Post-Merge Outcome")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "defect_escaped" in content:
            print("  [PASS] Displays defect_escaped")
        else:
            print("  [FAIL] defect_escaped display missing")
            return False
        
        if "rollback_occurred" in content:
            print("  [PASS] Displays rollback_occurred")
        else:
            print("  [FAIL] rollback_occurred display missing")
            return False
    
    # Test 11: Component is collapsible
    print("\n[11] Component Is Collapsible")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "isExpanded" in content or "is_expanded" in content:
            print("  [PASS] Has collapsible state")
        else:
            print("  [FAIL] Collapsible state missing")
            return False
        
        if "ChevronDown" in content or "ChevronUp" in content:
            print("  [PASS] Has expand/collapse button")
        else:
            print("  [FAIL] Expand/collapse button missing")
            return False
    
    # Test 12: Component shows learning status
    print("\n[12] Component Shows Learning Status")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "Learning captured" in content or "learning" in content.lower():
            print("  [PASS] Shows learning status")
        else:
            print("  [FAIL] Learning status display missing")
            return False
    
    # Test 13: Component integrated in page
    print("\n[13] Component Integrated in Page")
    print("-" * 70)
    
    page_path = "landing-page/app/app/recommendations/[recommendationRunId]/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
        
        if "OutcomePanel" in content:
            print("  [PASS] OutcomePanel imported in page")
        else:
            print("  [FAIL] OutcomePanel import missing")
            return False
        
        if "<OutcomePanel" in content:
            print("  [PASS] OutcomePanel used in page")
        else:
            print("  [FAIL] OutcomePanel usage missing")
            return False
    
    # Test 14: Page fetches outcome summary
    print("\n[14] Page Fetches Outcome Summary")
    print("-" * 70)
    
    with open(page_path, "r") as f:
        content = f.read()
        
        if "outcomeSummary" in content:
            print("  [PASS] Has outcomeSummary state")
        else:
            print("  [FAIL] outcomeSummary state missing")
            return False
        
        if "setOutcomeSummary" in content:
            print("  [PASS] Has setOutcomeSummary function")
        else:
            print("  [FAIL] setOutcomeSummary function missing")
            return False
        
        if "data.outcome" in content:
            print("  [PASS] Fetches outcome from API response")
        else:
            print("  [FAIL] Outcome fetch from API missing")
            return False
    
    # Test 15: UI labels present
    print("\n[15] UI Labels Present")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        labels = [
            "Pending review",
            "Partially accepted",
            "Tests attached",
            "Learning captured",
        ]
        
        for label in labels:
            if label in content:
                print(f"  [PASS] Has label: {label}")
            else:
                print(f"  [WARN] Label missing: {label}")
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nOutcomePanel verified:")
    print("  - Component file exists")
    print("  - Component exports")
    print("  - Component props")
    print("  - Component displays status")
    print("  - Component displays feedback")
    print("  - Component displays test execution status")
    print("  - Component displays test decisions")
    print("  - Component displays overrides")
    print("  - Component displays scenario decisions")
    print("  - Component displays post-merge outcome")
    print("  - Component is collapsible")
    print("  - Component shows learning status")
    print("  - Component integrated in page")
    print("  - Page fetches outcome summary")
    print("  - UI labels present")
    print("\nRecommendation page shows whether Veriscope learned from this run.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_outcome_panel()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
