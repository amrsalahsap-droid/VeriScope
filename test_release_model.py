"""
Basic tests for Release model.

Tests:
- create release model instance
- enum values work
- migration imports cleanly
"""

import sys
import os
import uuid
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.models.release import Release, ReleaseType, ReleaseStatus
from app.api.models.release import ReleaseCreate, ReleaseResponse, ReleaseUpdate


def test_release_model_instance():
    """Test creating a Release model instance."""
    print("Testing Release model instance creation...")
    
    try:
        # Create a mock release instance (without database)
        release = Release(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            version="v1.2.0",
            release_type=ReleaseType.MINOR,
            status=ReleaseStatus.PLANNED,
            planned_date=datetime(2024, 6, 15),
            actual_date=None,
            release_notes="Test release notes",
            created_by="test_user",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        assert release.version == "v1.2.0"
        assert release.release_type == ReleaseType.MINOR
        assert release.status == ReleaseStatus.PLANNED
        assert release.created_by == "test_user"
        
        print("[PASS] Release model instance created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Release model instance creation failed: {e}")
        return False


def test_enum_values():
    """Test that enum values work correctly."""
    print("\nTesting enum values...")
    
    try:
        # Test ReleaseType enum
        assert ReleaseType.MAJOR == "MAJOR"
        assert ReleaseType.MINOR == "MINOR"
        assert ReleaseType.PATCH == "PATCH"
        assert ReleaseType.HOTFIX == "HOTFIX"
        assert ReleaseType.CUSTOM == "CUSTOM"
        
        # Test ReleaseStatus enum
        assert ReleaseStatus.PLANNED == "PLANNED"
        assert ReleaseStatus.IN_PROGRESS == "IN_PROGRESS"
        assert ReleaseStatus.READY_FOR_SIGNOFF == "READY_FOR_SIGNOFF"
        assert ReleaseStatus.RELEASED == "RELEASED"
        assert ReleaseStatus.ROLLED_BACK == "ROLLED_BACK"
        assert ReleaseStatus.CANCELLED == "CANCELLED"
        
        print("[PASS] Enum values work correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Enum values test failed: {e}")
        return False


def test_pydantic_schemas():
    """Test Pydantic schemas."""
    print("\nTesting Pydantic schemas...")
    
    try:
        # Test ReleaseCreate schema
        release_create = ReleaseCreate(
            repository_id=uuid.uuid4(),
            version="v1.0.0",
            release_type=ReleaseType.MAJOR,
            status=ReleaseStatus.PLANNED,
            created_by="test_user"
        )
        assert release_create.version == "v1.0.0"
        assert release_create.release_type == ReleaseType.MAJOR
        
        # Test ReleaseUpdate schema
        release_update = ReleaseUpdate(
            version="v1.0.1",
            status=ReleaseStatus.IN_PROGRESS
        )
        assert release_update.version == "v1.0.1"
        assert release_update.status == ReleaseStatus.IN_PROGRESS
        
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
    """Test that Release model is registered in __init__.py."""
    print("\nTesting model registration...")
    
    try:
        from app.models import Release, ReleaseType, ReleaseStatus
        
        assert Release is not None
        assert ReleaseType is not None
        assert ReleaseStatus is not None
        
        print("[PASS] Release model registered in __init__.py")
        return True
    except Exception as e:
        print(f"[FAIL] Model registration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("Release Model Tests")
    print("="*60)
    
    results = []
    results.append(("Release model instance", test_release_model_instance()))
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
