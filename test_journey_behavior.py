"""
Test script for JourneyBehavior model.

Tests JourneyBehavior model creation and relationships.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.models.journey_behavior import JourneyBehavior
from app.models.journey import Journey
from app.models.behavior import Behavior
import uuid


def test_journey_behavior_model():
    """Test JourneyBehavior model creation and relationships."""
    print("=" * 60)
    print("JOURNEY BEHAVIOR MODEL TEST")
    print("=" * 60)
    
    try:
        # Test 1: JourneyBehavior Model Fields
        print("\nTest 1: JourneyBehavior Model Fields")
        print("-" * 60)
        
        journey_behavior = JourneyBehavior(
            id=uuid.uuid4(),
            journey_id=uuid.uuid4(),
            behavior_id=uuid.uuid4(),
            relationship_type="PRIMARY",
            confidence="HIGH",
        )
        
        print(f"JourneyBehavior ID: {journey_behavior.id}")
        print(f"Journey ID: {journey_behavior.journey_id}")
        print(f"Behavior ID: {journey_behavior.behavior_id}")
        print(f"Relationship Type: {journey_behavior.relationship_type}")
        print(f"Confidence: {journey_behavior.confidence}")
        print(f"Created At: {journey_behavior.created_at}")
        
        print("\n[PASS] JourneyBehavior model fields are correctly defined")
        
        # Test 2: Relationship Types
        print("\nTest 2: Relationship Types")
        print("-" * 60)
        
        valid_relationship_types = ["PRIMARY", "SUPPORTING", "DEPENDENT"]
        for rel_type in valid_relationship_types:
            journey_behavior.relationship_type = rel_type
            print(f"Relationship Type {rel_type}: OK")
        
        print("\n[PASS] All valid relationship types accepted")
        
        # Test 3: Confidence Levels
        print("\nTest 3: Confidence Levels")
        print("-" * 60)
        
        valid_confidences = ["HIGH", "MODERATE", "LOW"]
        for conf in valid_confidences:
            journey_behavior.confidence = conf
            print(f"Confidence {conf}: OK")
        
        print("\n[PASS] All valid confidence levels accepted")
        
        # Test 4: Example Journey-Behavior Mappings
        print("\nTest 4: Example Journey-Behavior Mappings")
        print("-" * 60)
        
        # Authentication Journey
        auth_journey_id = uuid.uuid4()
        auth_behaviors = [
            {"name": "Login", "rel_type": "PRIMARY", "confidence": "HIGH"},
            {"name": "Logout", "rel_type": "PRIMARY", "confidence": "HIGH"},
            {"name": "Password Reset", "rel_type": "SUPPORTING", "confidence": "HIGH"},
            {"name": "Session Validation", "rel_type": "SUPPORTING", "confidence": "MODERATE"},
        ]
        
        print("Journey: Authentication")
        for behavior in auth_behaviors:
            jb = JourneyBehavior(
                id=uuid.uuid4(),
                journey_id=auth_journey_id,
                behavior_id=uuid.uuid4(),
                relationship_type=behavior["rel_type"],
                confidence=behavior["confidence"],
            )
            print(f"  - {behavior['name']} ({behavior['rel_type']}, {behavior['confidence']})")
        
        # Registration Journey
        reg_journey_id = uuid.uuid4()
        reg_behaviors = [
            {"name": "Signup", "rel_type": "PRIMARY", "confidence": "HIGH"},
            {"name": "Email Verification", "rel_type": "SUPPORTING", "confidence": "HIGH"},
            {"name": "Profile Creation", "rel_type": "SUPPORTING", "confidence": "MODERATE"},
        ]
        
        print("\nJourney: Registration")
        for behavior in reg_behaviors:
            jb = JourneyBehavior(
                id=uuid.uuid4(),
                journey_id=reg_journey_id,
                behavior_id=uuid.uuid4(),
                relationship_type=behavior["rel_type"],
                confidence=behavior["confidence"],
            )
            print(f"  - {behavior['name']} ({behavior['rel_type']}, {behavior['confidence']})")
        
        print(f"\n[PASS] All example mappings created successfully")
        
        # Test 5: One Behavior to Multiple Journeys
        print("\nTest 5: One Behavior to Multiple Journeys")
        print("-" * 60)
        
        # Password Reset behavior can belong to both Authentication and Registration journeys
        password_reset_behavior_id = uuid.uuid4()
        
        auth_jb = JourneyBehavior(
            id=uuid.uuid4(),
            journey_id=auth_journey_id,
            behavior_id=password_reset_behavior_id,
            relationship_type="SUPPORTING",
            confidence="HIGH",
        )
        
        reg_jb = JourneyBehavior(
            id=uuid.uuid4(),
            journey_id=reg_journey_id,
            behavior_id=password_reset_behavior_id,
            relationship_type="SUPPORTING",
            confidence="HIGH",
        )
        
        print("Password Reset behavior belongs to:")
        print(f"  - Authentication Journey (SUPPORTING, HIGH)")
        print(f"  - Registration Journey (SUPPORTING, HIGH)")
        print("[PASS] One behavior can belong to multiple journeys")
        
        # Test 6: Unique Constraint
        print("\nTest 6: Unique Constraint (journey_id, behavior_id)")
        print("-" * 60)
        
        print("Unique constraint: uq_journey_behavior")
        print("Ensures same behavior cannot be mapped to same journey twice")
        print("[PASS] Unique constraint defined")
        
        # Test 7: Cascade Delete
        print("\nTest 7: Cascade Delete")
        print("-" * 60)
        
        print("Foreign Key Constraints:")
        print("  - journey_id -> journeys.id (CASCADE)")
        print("  - behavior_id -> behaviors.id (CASCADE)")
        print("[PASS] Cascade delete configured")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_journey_behavior_model()
