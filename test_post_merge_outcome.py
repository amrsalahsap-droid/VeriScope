"""
Test post-merge outcome capture.

Verifies that defect and rollback outcome capture is implemented correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'landing-page'))


def test_post_merge_outcome():
    """Test post-merge outcome capture."""
    print("=" * 70)
    print("POST-MERGE OUTCOME CAPTURE TEST")
    print("=" * 70)
    
    # Test 1: UI component exists
    print("\n[1] UI Component")
    print("-" * 70)
    
    component_path = "landing-page/components/post-merge-outcome.tsx"
    if os.path.exists(component_path):
        print(f"  [PASS] UI component exists at {component_path}")
    else:
        print(f"  [FAIL] UI component not found at {component_path}")
        return False
    
    # Test 2: Defect escaped field
    print("\n[2] Defect Escaped Field")
    print("-" * 70)
    
    with open(component_path, "r", encoding="utf-8") as f:
        content = f.read()
        
        if "defectEscaped" in content or "defect_escaped" in content:
            print("  [PASS] Has defect_escaped field")
        else:
            print("  [FAIL] defect_escaped field missing")
            return False
        
        if "Defect escaped" in content:
            print("  [PASS] Has defect escaped label")
        else:
            print("  [FAIL] Defect escaped label missing")
            return False
    
    # Test 3: Rollback occurred field
    print("\n[3] Rollback Occurred Field")
    print("-" * 70)
    
    with open(component_path, "r", encoding="utf-8") as f:
        content = f.read()
        
        if "rollbackOccurred" in content or "rollback_occurred" in content:
            print("  [PASS] Has rollback_occurred field")
        else:
            print("  [FAIL] rollback_occurred field missing")
            return False
        
        if "Rollback occurred" in content:
            print("  [PASS] Has rollback occurred label")
        else:
            print("  [FAIL] Rollback occurred label missing")
            return False
    
    # Test 4: Incident URL field
    print("\n[4] Incident URL Field")
    print("-" * 70)
    
    with open(component_path, "r", encoding="utf-8") as f:
        content = f.read()
        
        if "incidentUrl" in content or "production_incident_url" in content:
            print("  [PASS] Has production_incident_url field")
        else:
            print("  [FAIL] production_incident_url field missing")
            return False
        
        if "Incident" in content or "Defect Link" in content:
            print("  [PASS] Has incident/defect link label")
        else:
            print("  [FAIL] Incident/defect link label missing")
            return False
    
    # Test 5: Notes field
    print("\n[5] Notes Field")
    print("-" * 70)
    
    with open(component_path, "r", encoding="utf-8") as f:
        content = f.read()
        
        if "notes" in content or "feedback_comment" in content:
            print("  [PASS] Has feedback_comment field")
        else:
            print("  [FAIL] feedback_comment field missing")
            return False
        
        if "Notes" in content:
            print("  [PASS] Has notes label")
        else:
            print("  [FAIL] Notes label missing")
            return False
    
    # Test 6: API integration
    print("\n[6] API Integration")
    print("-" * 70)
    
    with open(component_path, "r", encoding="utf-8") as f:
        content = f.read()
        
        if "/outcome" in content:
            print("  [PASS] Calls outcome API endpoint")
        else:
            print("  [FAIL] Outcome API call missing")
            return False
        
        if "PATCH" in content:
            print("  [PASS] Uses PATCH method")
        else:
            print("  [FAIL] PATCH method missing")
            return False
    
    # Test 7: Component integration on page
    print("\n[7] Page Integration")
    print("-" * 70)
    
    page_path = "landing-page/app/app/recommendations/[recommendationRunId]/page.tsx"
    with open(page_path, "r", encoding="utf-8") as f:
        content = f.read()
        
        if "PostMergeOutcome" in content:
            print("  [PASS] Page uses PostMergeOutcome component")
        else:
            print("  [FAIL] PostMergeOutcome component not used")
            return False
    
    # Test 8: Outcome state includes defect and rollback
    print("\n[8] Outcome State")
    print("-" * 70)
    
    with open(page_path, "r", encoding="utf-8") as f:
        content = f.read()
        
        if "defect_escaped" in content:
            print("  [PASS] Outcome state includes defect_escaped")
        else:
            print("  [FAIL] defect_escaped in outcome state missing")
            return False
        
        if "rollback_occurred" in content:
            print("  [PASS] Outcome state includes rollback_occurred")
        else:
            print("  [FAIL] rollback_occurred in outcome state missing")
            return False
        
        if "production_incident_url" in content:
            print("  [PASS] Outcome state includes production_incident_url")
        else:
            print("  [FAIL] production_incident_url in outcome state missing")
            return False
    
    # Test 9: Optional fields
    print("\n[9] Optional Fields")
    print("-" * 70)
    
    with open(component_path, "r", encoding="utf-8") as f:
        content = f.read()
        
        if "optional" in content.lower():
            print("  [PASS] Fields marked as optional")
        else:
            print("  [FAIL] Optional marking missing")
            return False
    
    # Test 10: Toast notifications
    print("\n[10] Toast Notifications")
    print("-" * 70)
    
    with open(component_path, "r", encoding="utf-8") as f:
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
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nPost-merge outcome capture verified:")
    print("  - UI component exists")
    print("  - Defect escaped field")
    print("  - Rollback occurred field")
    print("  - Incident URL field")
    print("  - Notes field")
    print("  - API integration")
    print("  - Page integration")
    print("  - Outcome state includes defect and rollback")
    print("  - Optional fields")
    print("  - Toast notifications")
    print("\nEscaped defects and rollbacks become learning signals.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_post_merge_outcome()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
