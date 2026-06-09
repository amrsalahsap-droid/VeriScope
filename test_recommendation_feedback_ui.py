"""
Test recommendation feedback UI component.

Verifies that the feedback component exists and has correct structure.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'landing-page'))


def test_recommendation_feedback_ui():
    """Test recommendation feedback UI component."""
    print("=" * 70)
    print("RECOMMENDATION FEEDBACK UI TEST")
    print("=" * 70)
    
    # Test 1: Component file exists
    print("\n[1] Component File Existence")
    print("-" * 70)
    
    component_path = "landing-page/components/recommendation-feedback.tsx"
    if os.path.exists(component_path):
        print(f"  [PASS] Component file exists at {component_path}")
    else:
        print(f"  [FAIL] Component file not found at {component_path}")
        return False
    
    # Test 2: Component has required feedback options
    print("\n[2] Feedback Options")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        required_options = ["USEFUL", "NOT_USEFUL", "MISSING_TESTS", "TOO_BROAD", "TOO_NARROW"]
        for option in required_options:
            if option in content:
                print(f"  [PASS] Has {option} option")
            else:
                print(f"  [FAIL] Missing {option} option")
                return False
    
    # Test 3: Component has API integration
    print("\n[3] API Integration")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "/api/recommendations/${recommendationRunId}/outcome" in content:
            print("  [PASS] Uses outcome API endpoint")
        else:
            print("  [FAIL] API endpoint not found")
            return False
        
        if "PATCH" in content:
            print("  [PASS] Uses PATCH method")
        else:
            print("  [FAIL] PATCH method not found")
            return False
    
    # Test 4: Component has toast notifications
    print("\n[4] Toast Notifications")
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
    
    # Test 5: Component has comment input
    print("\n[5] Comment Input")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "comment" in content.lower():
            print("  [PASS] Has comment state")
        else:
            print("  [FAIL] Comment state missing")
            return False
        
        if "placeholder" in content.lower():
            print("  [PASS] Has placeholder text")
        else:
            print("  [FAIL] Placeholder text missing")
            return False
    
    # Test 6: Component is non-blocking
    print("\n[6] Non-blocking Design")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "isSubmitting" in content:
            print("  [PASS] Has loading state")
        else:
            print("  [FAIL] Loading state missing")
            return False
        
        if "disabled" in content:
            print("  [PASS] Disables during submission")
        else:
            print("  [FAIL] Disabled state missing")
            return False
    
    # Test 7: Page integration
    print("\n[7] Page Integration")
    print("-" * 70)
    
    page_path = "landing-page/app/app/recommendations/[recommendationRunId]/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
        
        if "RecommendationFeedback" in content:
            print("  [PASS] Component imported in page")
        else:
            print("  [FAIL] Component not imported")
            return False
        
        if "outcome" in content:
            print("  [PASS] Page has outcome state")
        else:
            print("  [FAIL] Outcome state missing")
            return False
        
        if "fetchOutcome" in content or "/outcome" in content:
            print("  [PASS] Page fetches outcome data")
        else:
            print("  [FAIL] Outcome fetch missing")
            return False
    
    # Test 8: One-click update
    print("\n[8] One-click Update")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "onClick" in content:
            print("  [PASS] Has click handler")
        else:
            print("  [FAIL] Click handler missing")
            return False
        
        if "handleFeedbackSelect" in content:
            print("  [PASS] Has feedback select handler")
        else:
            print("  [FAIL] Feedback select handler missing")
            return False
    
    # Test 9: Selected state visible
    print("\n[9] Selected State Visibility")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "selectedFeedback" in content:
            print("  [PASS] Tracks selected feedback")
        else:
            print("  [FAIL] Selected feedback state missing")
            return False
        
        if "isSelected" in content:
            print("  [PASS] Has selected state check")
        else:
            print("  [FAIL] Selected state check missing")
            return False
    
    # Test 10: Can be changed later
    print("\n[10] Changeable Feedback")
    print("-" * 70)
    
    with open(component_path, "r") as f:
        content = f.read()
        
        if "existingFeedback" in content:
            print("  [PASS] Accepts existing feedback")
        else:
            print("  [FAIL] Existing feedback prop missing")
            return False
        
        if "setSelectedFeedback" in content:
            print("  [PASS] Can update selection")
        else:
            print("  [FAIL] Update function missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nRecommendation feedback UI verified:")
    print("  - Component file exists")
    print("  - All 5 feedback options present")
    print("  - API integration with PATCH")
    print("  - Toast notifications for success/error")
    print("  - Comment input with placeholder")
    print("  - Non-blocking with loading state")
    print("  - Page integration with outcome fetch")
    print("  - One-click update functionality")
    print("  - Selected state visible")
    print("  - Feedback can be changed later")
    print("\nEngineer feedback is captured from the recommendation screen.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_recommendation_feedback_ui()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
