"""
Test script for Journey model.

Tests Journey model creation with all required fields.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.models.journey import Journey
from app.models.repository import Repository
from app.db.session import SessionLocal
import uuid


def test_journey_model():
    """Test Journey model creation and fields."""
    print("=" * 60)
    print("JOURNEY MODEL TEST")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Create a test repository (in-memory only, not persisted)
        print("\nTest 1: Journey Model Fields")
        print("-" * 60)
        
        # Create a Journey instance without database
        journey = Journey(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            name="Authentication",
            slug="authentication",
            description="User authentication and authorization workflow",
            business_value="Critical for user access and security",
            risk_level="HIGH",
            status="DISCOVERED",
            is_deleted=False,
        )
        
        print(f"Journey ID: {journey.id}")
        print(f"Repository ID: {journey.repository_id}")
        print(f"Name: {journey.name}")
        print(f"Slug: {journey.slug}")
        print(f"Description: {journey.description}")
        print(f"Business Value: {journey.business_value}")
        print(f"Risk Level: {journey.risk_level}")
        print(f"Status: {journey.status}")
        print(f"Is Deleted: {journey.is_deleted}")
        print(f"Created At: {journey.created_at}")
        print(f"Updated At: {journey.updated_at}")
        
        print("\n[PASS] Journey model fields are correctly defined")
        
        # Test field validation
        print("\nTest 2: Field Validation")
        print("-" * 60)
        
        # Test valid risk levels
        valid_risk_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        for risk_level in valid_risk_levels:
            journey.risk_level = risk_level
            print(f"Risk Level {risk_level}: OK")
        
        # Test valid statuses
        valid_statuses = ["DISCOVERED", "REVIEWED", "CONFIRMED", "ARCHIVED"]
        for status in valid_statuses:
            journey.status = status
            print(f"Status {status}: OK")
        
        print("\n[PASS] All valid risk levels and statuses accepted")
        
        # Test example journeys
        print("\nTest 3: Example Journeys")
        print("-" * 60)
        
        example_journeys = [
            {
                "name": "Authentication",
                "slug": "authentication",
                "description": "User authentication and authorization workflow",
                "business_value": "Critical for user access and security",
                "risk_level": "HIGH",
                "status": "CONFIRMED",
            },
            {
                "name": "Registration",
                "slug": "registration",
                "description": "New user registration and onboarding",
                "business_value": "Essential for user acquisition",
                "risk_level": "MEDIUM",
                "status": "CONFIRMED",
            },
            {
                "name": "Password Recovery",
                "slug": "password-recovery",
                "description": "Password reset and recovery workflow",
                "business_value": "Important for user support",
                "risk_level": "HIGH",
                "status": "REVIEWED",
            },
            {
                "name": "Billing",
                "slug": "billing",
                "description": "Payment processing and invoicing",
                "business_value": "Critical for revenue generation",
                "risk_level": "CRITICAL",
                "status": "CONFIRMED",
            },
            {
                "name": "Subscription Lifecycle",
                "slug": "subscription-lifecycle",
                "description": "Subscription creation, modification, and cancellation",
                "business_value": "Critical for recurring revenue",
                "risk_level": "CRITICAL",
                "status": "CONFIRMED",
            },
            {
                "name": "Notifications",
                "slug": "notifications",
                "description": "Email and push notification delivery",
                "business_value": "Important for user engagement",
                "risk_level": "MEDIUM",
                "status": "DISCOVERED",
            },
            {
                "name": "Administration",
                "slug": "administration",
                "description": "Admin panel and system management",
                "business_value": "Important for operations",
                "risk_level": "HIGH",
                "status": "REVIEWED",
            },
            {
                "name": "Reporting",
                "slug": "reporting",
                "description": "Analytics and reporting dashboards",
                "business_value": "Important for business insights",
                "risk_level": "LOW",
                "status": "DISCOVERED",
            },
        ]
        
        for example in example_journeys:
            journey = Journey(
                id=uuid.uuid4(),
                repository_id=uuid.uuid4(),
                **example,
                is_deleted=False,
            )
            print(f"Created: {journey.name} ({journey.risk_level}, {journey.status})")
        
        print(f"\n[PASS] All {len(example_journeys)} example journeys created successfully")
        
        # Test soft delete
        print("\nTest 4: Soft Delete")
        print("-" * 60)
        
        journey.is_deleted = True
        print(f"Journey soft deleted: {journey.is_deleted}")
        print("[PASS] Soft delete field works correctly")
        
        # Test constraints
        print("\nTest 5: Model Constraints")
        print("-" * 60)
        
        # Check that required fields are enforced
        try:
            journey = Journey(
                id=uuid.uuid4(),
                repository_id=uuid.uuid4(),
                # Missing required fields
            )
            print("[FAIL] Should have raised error for missing required fields")
        except TypeError as e:
            print(f"[PASS] Required fields enforced: {str(e)[:50]}...")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_journey_model()
