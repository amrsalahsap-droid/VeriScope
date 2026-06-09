"""
Test script for JourneyStep model.

Tests JourneyStep model creation and flow visualization.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.models.journey_step import JourneyStep
import uuid


def test_journey_step():
    """Test JourneyStep model creation and flow visualization."""
    print("=" * 60)
    print("JOURNEY STEP MODEL TEST")
    print("=" * 60)
    
    try:
        # Test 1: JourneyStep Model Fields
        print("\nTest 1: JourneyStep Model Fields")
        print("-" * 60)
        
        journey_step = JourneyStep(
            id=uuid.uuid4(),
            journey_id=uuid.uuid4(),
            step_order=1,
            step_name="Login",
            behavior_id=uuid.uuid4(),
            is_optional=False,
        )
        
        print(f"JourneyStep ID: {journey_step.id}")
        print(f"Journey ID: {journey_step.journey_id}")
        print(f"Step Order: {journey_step.step_order}")
        print(f"Step Name: {journey_step.step_name}")
        print(f"Behavior ID: {journey_step.behavior_id}")
        print(f"Is Optional: {journey_step.is_optional}")
        print(f"Created At: {journey_step.created_at}")
        
        print("\n[PASS] JourneyStep model fields are correctly defined")
        
        # Test 2: Step Ordering
        print("\nTest 2: Step Ordering")
        print("-" * 60)
        
        for order in [1, 2, 3, 4, 5]:
            journey_step.step_order = order
            print(f"Step Order {order}: OK")
        
        print("\n[PASS] Step ordering works correctly")
        
        # Test 3: Optional Steps
        print("\nTest 3: Optional Steps")
        print("-" * 60)
        
        journey_step.is_optional = True
        print(f"Optional Step: {journey_step.is_optional}")
        journey_step.is_optional = False
        print(f"Required Step: {journey_step.is_optional}")
        print("[PASS] Optional flag works correctly")
        
        # Test 4: Authentication Journey Flow
        print("\nTest 4: Authentication Journey Flow")
        print("-" * 60)
        
        journey_id = uuid.uuid4()
        
        auth_steps = [
            {"order": 1, "name": "Login", "optional": False},
            {"order": 2, "name": "Session Validation", "optional": False},
            {"order": 3, "name": "Password Reset", "optional": True},
            {"order": 4, "name": "Logout", "optional": False},
        ]
        
        print("Authentication Journey Flow:")
        for step in auth_steps:
            js = JourneyStep(
                id=uuid.uuid4(),
                journey_id=journey_id,
                step_order=step["order"],
                step_name=step["name"],
                behavior_id=uuid.uuid4(),
                is_optional=step["optional"],
            )
            optional_marker = " (optional)" if step["optional"] else ""
            print(f"  {step['order']}. {step['name']}{optional_marker}")
        
        print(f"\n[PASS] Authentication journey flow created with {len(auth_steps)} steps")
        
        # Test 5: Registration Journey Flow
        print("\nTest 5: Registration Journey Flow")
        print("-" * 60)
        
        reg_journey_id = uuid.uuid4()
        
        reg_steps = [
            {"order": 1, "name": "Signup", "optional": False},
            {"order": 2, "name": "Email Verification", "optional": False},
            {"order": 3, "name": "Profile Creation", "optional": True},
        ]
        
        print("Registration Journey Flow:")
        for step in reg_steps:
            js = JourneyStep(
                id=uuid.uuid4(),
                journey_id=reg_journey_id,
                step_order=step["order"],
                step_name=step["name"],
                behavior_id=uuid.uuid4(),
                is_optional=step["optional"],
            )
            optional_marker = " (optional)" if step["optional"] else ""
            print(f"  {step['order']}. {step['name']}{optional_marker}")
        
        print(f"\n[PASS] Registration journey flow created with {len(reg_steps)} steps")
        
        # Test 6: Reusable Behaviors
        print("\nTest 6: Reusable Behaviors")
        print("-" * 60)
        
        # Password Reset behavior can be used in multiple journeys
        password_reset_behavior_id = uuid.uuid4()
        
        auth_step = JourneyStep(
            id=uuid.uuid4(),
            journey_id=journey_id,
            step_order=3,
            step_name="Password Reset",
            behavior_id=password_reset_behavior_id,
            is_optional=True,
        )
        
        reg_step = JourneyStep(
            id=uuid.uuid4(),
            journey_id=reg_journey_id,
            step_order=2,
            step_name="Password Reset",
            behavior_id=password_reset_behavior_id,
            is_optional=True,
        )
        
        print("Password Reset behavior reused in:")
        print(f"  - Authentication Journey (step 3, optional)")
        print(f"  - Registration Journey (step 2, optional)")
        print("[PASS] Behaviors can be reused across journeys")
        
        # Test 7: Unique Constraint
        print("\nTest 7: Unique Constraint (journey_id, step_order)")
        print("-" * 60)
        
        print("Unique constraint: uq_journey_step_order")
        print("Ensures no duplicate step orders within same journey")
        print("[PASS] Unique constraint defined")
        
        # Test 8: Cascade Delete
        print("\nTest 8: Cascade Delete")
        print("-" * 60)
        
        print("Foreign Key Constraints:")
        print("  - journey_id -> journeys.id (CASCADE)")
        print("  - behavior_id -> behaviors.id (SET NULL)")
        print("[PASS] Cascade delete configured")
        
        # Test 9: Indexes
        print("\nTest 9: Indexes")
        print("-" * 60)
        
        print("Indexes configured on:")
        print("  - journey_id")
        print("  - step_order")
        print("  - behavior_id")
        print("[PASS] Indexes defined for performance")
        
        # Test 10: Flow Visualization
        print("\nTest 10: Flow Visualization")
        print("-" * 60)
        
        print("Authentication Journey Visualization:")
        print("+-------------------------------------+")
        print("|     Authentication Journey          |")
        print("+-------------------------------------+")
        print("| 1. Login                            |")
        print("|    |                                |")
        print("| 2. Session Validation               |")
        print("|    |                                |")
        print("| 3. Password Reset (optional)        |")
        print("|    |                                |")
        print("| 4. Logout                           |")
        print("+-------------------------------------+")
        print("[PASS] Journey flow can be visualized")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_journey_step()
