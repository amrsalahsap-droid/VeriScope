"""
Basic tests for ScopeOverride model.

Tests:
- create tier change override
- create exclusion override
- reason required
- original/new values stored
- enum values work
- migration imports cleanly
"""

import sys
import os
import uuid
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.models.regression_suite import ScopeOverride, OverrideType
from app.api.models.scope_override import ScopeOverrideCreate, ScopeOverrideResponse


def test_tier_change_override():
    """Test creating a ScopeOverride for tier change."""
    print("Testing ScopeOverride for tier change...")
    
    try:
        # Create a mock scope override for tier change (without database)
        scope_override = ScopeOverride(
            id=uuid.uuid4(),
            regression_scope_item_id=uuid.uuid4(),
            regression_suite_id=uuid.uuid4(),
            override_type=OverrideType.TIER_CHANGED,
            original_value={"tier": "MUST_RUN"},
            new_value={"tier": "SHOULD_RUN"},
            reason="Test is not critical for this release",
            overridden_by="qa_lead",
            overridden_at=datetime.utcnow()
        )
        
        assert scope_override.override_type == OverrideType.TIER_CHANGED
        assert scope_override.original_value == {"tier": "MUST_RUN"}
        assert scope_override.new_value == {"tier": "SHOULD_RUN"}
        assert scope_override.reason == "Test is not critical for this release"
        assert scope_override.overridden_by == "qa_lead"
        
        print("[PASS] Tier change override created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Tier change override creation failed: {e}")
        return False


def test_exclusion_override():
    """Test creating a ScopeOverride for exclusion."""
    print("\nTesting ScopeOverride for exclusion...")
    
    try:
        # Create a mock scope override for exclusion (without database)
        scope_override = ScopeOverride(
            id=uuid.uuid4(),
            regression_scope_item_id=uuid.uuid4(),
            regression_suite_id=uuid.uuid4(),
            override_type=OverrideType.EXCLUDED,
            original_value={"is_excluded": False},
            new_value={"is_excluded": True},
            reason="Test is not applicable to this PR scope",
            overridden_by="qa_lead",
            overridden_at=datetime.utcnow()
        )
        
        assert scope_override.override_type == OverrideType.EXCLUDED
        assert scope_override.original_value == {"is_excluded": False}
        assert scope_override.new_value == {"is_excluded": True}
        assert scope_override.reason == "Test is not applicable to this PR scope"
        
        print("[PASS] Exclusion override created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Exclusion override creation failed: {e}")
        return False


def test_reason_required():
    """Test that reason is required for overrides."""
    print("\nTesting reason required...")
    
    try:
        # Try to create an override without reason (should fail at database level)
        # For this test, we'll just verify the model has reason as non-nullable
        from app.models.regression_suite import ScopeOverride
        from sqlalchemy import inspect
        
        mapper = inspect(ScopeOverride)
        reason_column = mapper.columns['reason']
        
        # Verify reason column is not nullable
        assert not reason_column.nullable, "Reason should be required (non-nullable)"
        
        print("[PASS] Reason is required (non-nullable)")
        return True
    except Exception as e:
        print(f"[FAIL] Reason required test failed: {e}")
        return False


def test_original_new_values_stored():
    """Test that original and new values are stored correctly."""
    print("\nTesting original/new values storage...")
    
    try:
        # Create a mock override with complex JSON values
        original_value = {
            "tier": "MUST_RUN",
            "priority": "CRITICAL",
            "execution_status": "NOT_RUN"
        }
        new_value = {
            "tier": "SHOULD_RUN",
            "priority": "HIGH",
            "execution_status": "NOT_RUN"
        }
        
        scope_override = ScopeOverride(
            id=uuid.uuid4(),
            regression_scope_item_id=uuid.uuid4(),
            regression_suite_id=uuid.uuid4(),
            override_type=OverrideType.PRIORITY_CHANGED,
            original_value=original_value,
            new_value=new_value,
            reason="Lowering priority based on risk assessment",
            overridden_by="qa_lead",
            overridden_at=datetime.utcnow()
        )
        
        assert scope_override.original_value == original_value
        assert scope_override.new_value == new_value
        assert scope_override.original_value["tier"] == "MUST_RUN"
        assert scope_override.new_value["priority"] == "HIGH"
        
        print("[PASS] Original/new values stored correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Original/new values storage test failed: {e}")
        return False


def test_enum_values():
    """Test that enum values work correctly."""
    print("\nTesting enum values...")
    
    try:
        # Test OverrideType enum
        assert OverrideType.ADDED == "ADDED"
        assert OverrideType.REMOVED == "REMOVED"
        assert OverrideType.TIER_CHANGED == "TIER_CHANGED"
        assert OverrideType.PRIORITY_CHANGED == "PRIORITY_CHANGED"
        assert OverrideType.MARKED_REQUIRED == "MARKED_REQUIRED"
        assert OverrideType.MARKED_OPTIONAL == "MARKED_OPTIONAL"
        assert OverrideType.EXCLUDED == "EXCLUDED"
        assert OverrideType.RESTORED == "RESTORED"
        
        print("[PASS] Enum values work correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Enum values test failed: {e}")
        return False


def test_pydantic_schemas():
    """Test Pydantic schemas."""
    print("\nTesting Pydantic schemas...")
    
    try:
        # Test ScopeOverrideCreate schema
        scope_override_create = ScopeOverrideCreate(
            regression_scope_item_id=uuid.uuid4(),
            regression_suite_id=uuid.uuid4(),
            override_type=OverrideType.TIER_CHANGED,
            original_value={"tier": "MUST_RUN"},
            new_value={"tier": "SHOULD_RUN"},
            reason="Lowering priority",
            overridden_by="qa_lead"
        )
        assert scope_override_create.override_type == OverrideType.TIER_CHANGED
        assert scope_override_create.reason == "Lowering priority"
        
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
    """Test that ScopeOverride model is registered in __init__.py."""
    print("\nTesting model registration...")
    
    try:
        from app.models import ScopeOverride
        
        assert ScopeOverride is not None
        
        print("[PASS] ScopeOverride model registered in __init__.py")
        return True
    except Exception as e:
        print(f"[FAIL] Model registration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("ScopeOverride Model Tests")
    print("="*60)
    
    results = []
    results.append(("Tier change override", test_tier_change_override()))
    results.append(("Exclusion override", test_exclusion_override()))
    results.append(("Reason required", test_reason_required()))
    results.append(("Original/new values stored", test_original_new_values_stored()))
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
