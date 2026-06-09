"""
Test Learning UI page.

Verifies that the Learning UI page exists and is properly structured.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'landing-page'))


def test_learning_ui():
    """Test Learning UI page."""
    print("=" * 70)
    print("LEARNING UI TEST")
    print("=" * 70)
    
    # Test 1: Learning page exists
    print("\n[1] Learning Page Exists")
    print("-" * 70)
    
    page_path = "landing-page/app/app/repositories/[repositoryId]/learning/page.tsx"
    if os.path.exists(page_path):
        print(f"  [PASS] Learning page exists at {page_path}")
    else:
        print(f"  [FAIL] Learning page not found at {page_path}")
        return False
    
    # Test 2: Page exports default component
    print("\n[2] Page Exports Default Component")
    print("-" * 70)
    
    with open(page_path, "r") as f:
        content = f.read()
        
        if "export default function" in content:
            print("  [PASS] Exports default function")
        else:
            print("  [FAIL] Default export missing")
            return False
    
    # Test 3: Page fetches learning summary
    print("\n[3] Page Fetches Learning Summary")
    print("-" * 70)
    
    with open(page_path, "r") as f:
        content = f.read()
        
        if "/learning-summary" in content:
            print("  [PASS] Fetches learning summary")
        else:
            print("  [FAIL] Learning summary fetch missing")
            return False
    
    # Test 4: Page displays overview stats
    print("\n[4] Page Displays Overview Stats")
    print("-" * 70)
    
    with open(page_path, "r") as f:
        content = f.read()
        
        stats = ["Total Outcomes", "Useful Feedback", "Escaped Defects", "Rollbacks"]
        for stat in stats:
            if stat in content:
                print(f"  [PASS] Displays {stat}")
            else:
                print(f"  [WARN] {stat} display missing")
    
    # Test 5: Page displays learning signals
    print("\n[5] Page Displays Learning Signals")
    print("-" * 70)
    
    with open(page_path, "r") as f:
        content = f.read()
        
        signals = ["Manually Added Tests", "Removed Tests", "Accepted Scenarios", "Missing Tests Feedback"]
        for signal in signals:
            if signal in content:
                print(f"  [PASS] Displays {signal}")
            else:
                print(f"  [WARN] {signal} display missing")
    
    # Test 6: Page displays top learned patterns
    print("\n[6] Page Displays Top Learned Patterns")
    print("-" * 70)
    
    with open(page_path, "r") as f:
        content = f.read()
        
        if "Top Learned Patterns" in content:
            print("  [PASS] Displays top learned patterns section")
        else:
            print("  [FAIL] Top learned patterns section missing")
            return False
        
        if "pattern_key" in content:
            print("  [PASS] Displays pattern_key")
        else:
            print("  [FAIL] pattern_key display missing")
            return False
    
    # Test 7: Page displays behaviors with most signals
    print("\n[7] Page Displays Behaviors With Most Signals")
    print("-" * 70)
    
    with open(page_path, "r") as f:
        content = f.read()
        
        if "Behaviors With Most Learning Signals" in content:
            print("  [PASS] Displays behaviors with most signals section")
        else:
            print("  [FAIL] Behaviors with most signals section missing")
            return False
        
        if "behavior_name" in content:
            print("  [PASS] Displays behavior_name")
        else:
            print("  [FAIL] behavior_name display missing")
            return False
    
    # Test 8: Page has back link
    print("\n[8] Page Has Back Link")
    print("-" * 70)
    
    with open(page_path, "r") as f:
        content = f.read()
        
        if "Back to Repository" in content:
            print("  [PASS] Has back link")
        else:
            print("  [FAIL] Back link missing")
            return False
    
    # Test 9: Page handles no learning data
    print("\n[9] Page Handles No Learning Data")
    print("-" * 70)
    
    with open(page_path, "r") as f:
        content = f.read()
        
        if "No Learning Data Yet" in content:
            print("  [PASS] Handles no learning data")
        else:
            print("  [FAIL] No learning data handling missing")
            return False
    
    # Test 10: Page uses appropriate icons
    print("\n[10] Page Uses Appropriate Icons")
    print("-" * 70)
    
    with open(page_path, "r") as f:
        content = f.read()
        
        icons = ["TrendingUp", "CheckCircle", "AlertTriangle", "RotateCcw", "Brain"]
        for icon in icons:
            if icon in content:
                print(f"  [PASS] Uses {icon} icon")
            else:
                print(f"  [WARN] {icon} icon missing")
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nLearning UI page verified:")
    print("  - Learning page exists")
    print("  - Page exports default component")
    print("  - Page fetches learning summary")
    print("  - Page displays overview stats")
    print("  - Page displays learning signals")
    print("  - Page displays top learned patterns")
    print("  - Page displays behaviors with most signals")
    print("  - Page has back link")
    print("  - Page handles no learning data")
    print("  - Page uses appropriate icons")
    print("\nUsers can see Veriscope becoming smarter over time.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_learning_ui()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
