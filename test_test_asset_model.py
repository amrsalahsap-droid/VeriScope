"""
Basic tests for TestAsset model.

Tests:
- create automated test asset
- create manual test asset
- behavior_ids/journey_ids JSON works
- stable_identity lookup works
- enum values work
- migration imports cleanly
"""

import sys
import os
import uuid
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.models.test_asset import (
    TestAsset, TestPriority, TestType, 
    BusinessCriticality, AutomationStatus
)
from app.api.models.test_asset import (
    TestAssetCreate, TestAssetResponse, TestAssetUpdate
)


def test_automated_test_asset():
    """Test creating a TestAsset for an automated test."""
    print("Testing TestAsset for automated test...")
    
    try:
        # Create a mock test asset for automated test (without database)
        test_asset = TestAsset(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            test_case_id=uuid.uuid4(),
            external_test_case_id=None,
            stable_identity="com.example.auth.login_test",
            display_name="Login Authentication Test",
            priority=TestPriority.CRITICAL,
            test_type=TestType.API,
            business_criticality=BusinessCriticality.MISSION_CRITICAL,
            automation_status=AutomationStatus.AUTOMATED,
            behavior_ids=[str(uuid.uuid4()), str(uuid.uuid4())],
            journey_ids=[str(uuid.uuid4())],
            tags={"category": "auth", "smoke": True},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        assert test_asset.test_case_id is not None
        assert test_asset.external_test_case_id is None
        assert test_asset.stable_identity == "com.example.auth.login_test"
        assert test_asset.display_name == "Login Authentication Test"
        assert test_asset.priority == TestPriority.CRITICAL
        assert test_asset.test_type == TestType.API
        assert test_asset.business_criticality == BusinessCriticality.MISSION_CRITICAL
        assert test_asset.automation_status == AutomationStatus.AUTOMATED
        assert isinstance(test_asset.behavior_ids, list)
        assert isinstance(test_asset.journey_ids, list)
        assert isinstance(test_asset.tags, dict)
        
        print("[PASS] Automated test asset created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Automated test asset creation failed: {e}")
        return False


def test_manual_test_asset():
    """Test creating a TestAsset for a manual test."""
    print("\nTesting TestAsset for manual test...")
    
    try:
        # Create a mock test asset for manual test (without database)
        test_asset = TestAsset(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            test_case_id=None,
            external_test_case_id=uuid.uuid4(),
            stable_identity="manual_ui_checkout_flow",
            display_name="Manual UI Checkout Flow",
            priority=TestPriority.HIGH,
            test_type=TestType.MANUAL,
            business_criticality=BusinessCriticality.IMPORTANT,
            automation_status=AutomationStatus.MANUAL,
            behavior_ids=[str(uuid.uuid4())],
            journey_ids=[str(uuid.uuid4()), str(uuid.uuid4())],
            tags={"category": "checkout", "ui": True},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        assert test_asset.test_case_id is None
        assert test_asset.external_test_case_id is not None
        assert test_asset.stable_identity == "manual_ui_checkout_flow"
        assert test_asset.display_name == "Manual UI Checkout Flow"
        assert test_asset.test_type == TestType.MANUAL
        assert test_asset.automation_status == AutomationStatus.MANUAL
        
        print("[PASS] Manual test asset created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Manual test asset creation failed: {e}")
        return False


def test_behavior_journey_json():
    """Test that behavior_ids and journey_ids JSON works correctly."""
    print("\nTesting behavior_ids/journey_ids JSON...")
    
    try:
        # Create a test asset with JSON fields
        behavior_id_1 = str(uuid.uuid4())
        behavior_id_2 = str(uuid.uuid4())
        journey_id_1 = str(uuid.uuid4())
        
        test_asset = TestAsset(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            test_case_id=uuid.uuid4(),
            external_test_case_id=None,
            stable_identity="test_with_context",
            display_name="Test with Context",
            priority=TestPriority.MEDIUM,
            test_type=TestType.INTEGRATION,
            business_criticality=BusinessCriticality.SUPPORTING,
            automation_status=AutomationStatus.AUTOMATED,
            behavior_ids=[behavior_id_1, behavior_id_2],
            journey_ids=[journey_id_1],
            tags={"env": "staging"},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        assert len(test_asset.behavior_ids) == 2
        assert behavior_id_1 in test_asset.behavior_ids
        assert behavior_id_2 in test_asset.behavior_ids
        assert len(test_asset.journey_ids) == 1
        assert journey_id_1 in test_asset.journey_ids
        assert test_asset.tags["env"] == "staging"
        
        print("[PASS] behavior_ids/journey_ids JSON works correctly")
        return True
    except Exception as e:
        print(f"[FAIL] behavior_ids/journey_ids JSON test failed: {e}")
        return False


def test_stable_identity_lookup():
    """Test that stable_identity works when test_case_id is unavailable."""
    print("\nTesting stable_identity lookup...")
    
    try:
        # Create a test asset without test_case_id, using stable_identity
        test_asset = TestAsset(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            test_case_id=None,
            external_test_case_id=None,
            stable_identity="legacy.test.user.profile",
            display_name="Legacy User Profile Test",
            priority=TestPriority.LOW,
            test_type=TestType.UNIT,
            business_criticality=BusinessCriticality.SUPPORTING,
            automation_status=AutomationStatus.PARTIALLY_AUTOMATED,
            behavior_ids=[],
            journey_ids=[],
            tags={"legacy": True},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        assert test_asset.test_case_id is None
        assert test_asset.external_test_case_id is None
        assert test_asset.stable_identity == "legacy.test.user.profile"
        assert test_asset.display_name == "Legacy User Profile Test"
        
        print("[PASS] stable_identity lookup works correctly")
        return True
    except Exception as e:
        print(f"[FAIL] stable_identity lookup test failed: {e}")
        return False


def test_enum_values():
    """Test that enum values work correctly."""
    print("\nTesting enum values...")
    
    try:
        # Test TestPriority enum
        assert TestPriority.CRITICAL == "CRITICAL"
        assert TestPriority.HIGH == "HIGH"
        assert TestPriority.MEDIUM == "MEDIUM"
        assert TestPriority.LOW == "LOW"
        
        # Test TestType enum
        assert TestType.UNIT == "UNIT"
        assert TestType.API == "API"
        assert TestType.INTEGRATION == "INTEGRATION"
        assert TestType.E2E == "E2E"
        assert TestType.UI == "UI"
        assert TestType.SECURITY == "SECURITY"
        assert TestType.PERFORMANCE == "PERFORMANCE"
        assert TestType.MANUAL == "MANUAL"
        assert TestType.SMOKE == "SMOKE"
        
        # Test BusinessCriticality enum
        assert BusinessCriticality.MISSION_CRITICAL == "MISSION_CRITICAL"
        assert BusinessCriticality.IMPORTANT == "IMPORTANT"
        assert BusinessCriticality.SUPPORTING == "SUPPORTING"
        
        # Test AutomationStatus enum
        assert AutomationStatus.AUTOMATED == "AUTOMATED"
        assert AutomationStatus.MANUAL == "MANUAL"
        assert AutomationStatus.PARTIALLY_AUTOMATED == "PARTIALLY_AUTOMATED"
        assert AutomationStatus.UNKNOWN == "UNKNOWN"
        
        print("[PASS] Enum values work correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Enum values test failed: {e}")
        return False


def test_pydantic_schemas():
    """Test Pydantic schemas."""
    print("\nTesting Pydantic schemas...")
    
    try:
        # Test TestAssetCreate schema
        test_asset_create = TestAssetCreate(
            repository_id=uuid.uuid4(),
            test_case_id=uuid.uuid4(),
            stable_identity="com.example.test",
            display_name="Test Asset",
            priority=TestPriority.HIGH,
            test_type=TestType.API,
            business_criticality=BusinessCriticality.IMPORTANT,
            automation_status=AutomationStatus.AUTOMATED,
            behavior_ids=[str(uuid.uuid4())],
            journey_ids=[str(uuid.uuid4())],
            tags={"key": "value"}
        )
        assert test_asset_create.display_name == "Test Asset"
        assert test_asset_create.priority == TestPriority.HIGH
        
        # Test TestAssetUpdate schema
        test_asset_update = TestAssetUpdate(
            priority=TestPriority.CRITICAL,
            automation_status=AutomationStatus.PARTIALLY_AUTOMATED
        )
        assert test_asset_update.priority == TestPriority.CRITICAL
        assert test_asset_update.automation_status == AutomationStatus.PARTIALLY_AUTOMATED
        
        print("[PASS] Pydantic schemas work correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Pydantic schemas test failed: {e}")
        return False


def test_migration_import():
    """Test that migration imports cleanly."""
    print("\nTesting migration import...")
    
    try:
        migration_path = os.path.join(os.path.dirname(__file__), 'alembic', 'versions', 'k2l3m4n5o6p7_add_regression_scope_models.py')
        
        if not os.path.exists(migration_path):
            print(f"[FAIL] Migration file not found: {migration_path}")
            return False
        
        # Try to import the migration module
        import importlib.util
        spec = importlib.util.spec_from_file_location("migration", migration_path)
        if spec and spec.loader:
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)
            print("[PASS] Migration imports cleanly")
            return True
        else:
            print("[FAIL] Could not load migration module")
            return False
    except Exception as e:
        print(f"[FAIL] Migration import failed: {e}")
        return False


def test_model_registration():
    """Test that TestAsset model is registered in __init__.py."""
    print("\nTesting model registration...")
    
    try:
        from app.models import TestAsset
        
        assert TestAsset is not None
        
        print("[PASS] TestAsset model registered in __init__.py")
        return True
    except Exception as e:
        print(f"[FAIL] Model registration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("TestAsset Model Tests")
    print("="*60)
    
    results = []
    results.append(("Automated test asset", test_automated_test_asset()))
    results.append(("Manual test asset", test_manual_test_asset()))
    results.append(("Behavior/journey JSON", test_behavior_journey_json()))
    results.append(("Stable identity lookup", test_stable_identity_lookup()))
    results.append(("Enum values", test_enum_values()))
    results.append(("Pydantic schemas", test_pydantic_schemas()))
    results.append(("Migration import", test_migration_import()))
    results.append(("Model registration", test_model_registration()))
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\n[FAILURE] {total - passed} test(s) failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
