"""
Basic tests for RegressionScopeItem model.

Tests:
- create automated scope item
- create suggested scenario item
- create manual item if ExternalTestCase exists
- tier enum works
- no duplicate item in same suite
- migration imports cleanly
"""

import sys
import os
import uuid
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.models.regression_suite import (
    RegressionScopeItem, ScopeItemType, ScopeTier, 
    ScopePriority, ExecutionStatus
)
from app.api.models.regression_scope_item import (
    RegressionScopeItemCreate, RegressionScopeItemResponse, RegressionScopeItemUpdate
)


def test_automated_scope_item():
    """Test creating a RegressionScopeItem for an automated test."""
    print("Testing RegressionScopeItem for automated test...")
    
    try:
        # Create a mock scope item for automated test (without database)
        scope_item = RegressionScopeItem(
            id=uuid.uuid4(),
            regression_suite_id=uuid.uuid4(),
            test_case_id=uuid.uuid4(),
            external_test_case_id=None,
            suggested_scenario_id=None,
            behavior_id=uuid.uuid4(),
            journey_id=uuid.uuid4(),
            acceptance_criterion_id=None,
            item_type=ScopeItemType.AUTOMATED_TEST,
            tier=ScopeTier.MUST_RUN,
            priority=ScopePriority.CRITICAL,
            selection_reason="Test covers critical authentication flow",
            evidence_summary={"confidence": 0.9, "source": "recommendation"},
            execution_status=ExecutionStatus.NOT_RUN,
            coverage_status="COVERED",
            is_excluded=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        assert scope_item.item_type == ScopeItemType.AUTOMATED_TEST
        assert scope_item.tier == ScopeTier.MUST_RUN
        assert scope_item.priority == ScopePriority.CRITICAL
        assert scope_item.test_case_id is not None
        assert scope_item.external_test_case_id is None
        assert scope_item.suggested_scenario_id is None
        assert scope_item.behavior_id is not None
        assert scope_item.journey_id is not None
        
        print("[PASS] Automated scope item created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Automated scope item creation failed: {e}")
        return False


def test_suggested_scenario_item():
    """Test creating a RegressionScopeItem for a suggested scenario."""
    print("\nTesting RegressionScopeItem for suggested scenario...")
    
    try:
        # Create a mock scope item for suggested scenario (without database)
        scope_item = RegressionScopeItem(
            id=uuid.uuid4(),
            regression_suite_id=uuid.uuid4(),
            test_case_id=None,
            external_test_case_id=None,
            suggested_scenario_id=uuid.uuid4(),
            behavior_id=uuid.uuid4(),
            journey_id=None,
            acceptance_criterion_id=None,
            item_type=ScopeItemType.SUGGESTED_SCENARIO,
            tier=ScopeTier.SHOULD_RUN,
            priority=ScopePriority.HIGH,
            selection_reason="Missing coverage for password reset flow",
            evidence_summary={"risk": "HIGH", "area": "authentication"},
            execution_status=ExecutionStatus.MANUAL_PENDING,
            coverage_status="MISSING_AUTOMATED_COVERAGE",
            is_excluded=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        assert scope_item.item_type == ScopeItemType.SUGGESTED_SCENARIO
        assert scope_item.tier == ScopeTier.SHOULD_RUN
        assert scope_item.suggested_scenario_id is not None
        assert scope_item.test_case_id is None
        assert scope_item.external_test_case_id is None
        assert scope_item.execution_status == ExecutionStatus.MANUAL_PENDING
        
        print("[PASS] Suggested scenario scope item created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Suggested scenario scope item creation failed: {e}")
        return False


def test_manual_scope_item():
    """Test creating a RegressionScopeItem for a manual test."""
    print("\nTesting RegressionScopeItem for manual test...")
    
    try:
        # Create a mock scope item for manual test (without database)
        scope_item = RegressionScopeItem(
            id=uuid.uuid4(),
            regression_suite_id=uuid.uuid4(),
            test_case_id=None,
            external_test_case_id=uuid.uuid4(),
            suggested_scenario_id=None,
            behavior_id=None,
            journey_id=uuid.uuid4(),
            acceptance_criterion_id=None,
            item_type=ScopeItemType.MANUAL_TEST,
            tier=ScopeTier.SHOULD_RUN,
            priority=ScopePriority.MEDIUM,
            selection_reason="Manual validation required for UI changes",
            evidence_summary={"source": "external_test_case"},
            execution_status=ExecutionStatus.NOT_RUN,
            coverage_status="MANUAL_VALIDATION_RECOMMENDED",
            is_excluded=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        assert scope_item.item_type == ScopeItemType.MANUAL_TEST
        assert scope_item.external_test_case_id is not None
        assert scope_item.test_case_id is None
        assert scope_item.suggested_scenario_id is None
        
        print("[PASS] Manual scope item created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Manual scope item creation failed: {e}")
        return False


def test_coverage_gap_item():
    """Test creating a RegressionScopeItem for a coverage gap."""
    print("\nTesting RegressionScopeItem for coverage gap...")
    
    try:
        # Create a mock scope item for coverage gap (without database)
        scope_item = RegressionScopeItem(
            id=uuid.uuid4(),
            regression_suite_id=uuid.uuid4(),
            test_case_id=None,
            external_test_case_id=None,
            suggested_scenario_id=None,
            behavior_id=uuid.uuid4(),
            journey_id=None,
            acceptance_criterion_id=None,
            item_type=ScopeItemType.COVERAGE_GAP,
            tier=ScopeTier.OPTIONAL,
            priority=ScopePriority.LOW,
            selection_reason="Potential gap in error handling",
            evidence_summary={"gap_type": "error_handling", "severity": "LOW"},
            execution_status=ExecutionStatus.NOT_RUN,
            coverage_status="GAP_IDENTIFIED",
            is_excluded=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        assert scope_item.item_type == ScopeItemType.COVERAGE_GAP
        assert scope_item.tier == ScopeTier.OPTIONAL
        assert scope_item.test_case_id is None
        assert scope_item.external_test_case_id is None
        assert scope_item.suggested_scenario_id is None
        
        print("[PASS] Coverage gap scope item created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Coverage gap scope item creation failed: {e}")
        return False


def test_enum_values():
    """Test that enum values work correctly."""
    print("\nTesting enum values...")
    
    try:
        # Test ScopeItemType enum
        assert ScopeItemType.AUTOMATED_TEST == "AUTOMATED_TEST"
        assert ScopeItemType.MANUAL_TEST == "MANUAL_TEST"
        assert ScopeItemType.SUGGESTED_SCENARIO == "SUGGESTED_SCENARIO"
        assert ScopeItemType.COVERAGE_GAP == "COVERAGE_GAP"
        
        # Test ScopeTier enum
        assert ScopeTier.MUST_RUN == "MUST_RUN"
        assert ScopeTier.SHOULD_RUN == "SHOULD_RUN"
        assert ScopeTier.OPTIONAL == "OPTIONAL"
        
        # Test ScopePriority enum
        assert ScopePriority.CRITICAL == "CRITICAL"
        assert ScopePriority.HIGH == "HIGH"
        assert ScopePriority.MEDIUM == "MEDIUM"
        assert ScopePriority.LOW == "LOW"
        
        # Test ExecutionStatus enum
        assert ExecutionStatus.NOT_RUN == "NOT_RUN"
        assert ExecutionStatus.PASSED == "PASSED"
        assert ExecutionStatus.FAILED == "FAILED"
        assert ExecutionStatus.SKIPPED == "SKIPPED"
        assert ExecutionStatus.BLOCKED == "BLOCKED"
        assert ExecutionStatus.MANUAL_PENDING == "MANUAL_PENDING"
        assert ExecutionStatus.UNKNOWN == "UNKNOWN"
        
        print("[PASS] Enum values work correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Enum values test failed: {e}")
        return False


def test_pydantic_schemas():
    """Test Pydantic schemas."""
    print("\nTesting Pydantic schemas...")
    
    try:
        # Test RegressionScopeItemCreate schema
        scope_item_create = RegressionScopeItemCreate(
            regression_suite_id=uuid.uuid4(),
            test_case_id=uuid.uuid4(),
            item_type=ScopeItemType.AUTOMATED_TEST,
            tier=ScopeTier.MUST_RUN,
            priority=ScopePriority.CRITICAL
        )
        assert scope_item_create.item_type == ScopeItemType.AUTOMATED_TEST
        assert scope_item_create.tier == ScopeTier.MUST_RUN
        
        # Test RegressionScopeItemUpdate schema
        scope_item_update = RegressionScopeItemUpdate(
            tier=ScopeTier.SHOULD_RUN,
            execution_status=ExecutionStatus.PASSED
        )
        assert scope_item_update.tier == ScopeTier.SHOULD_RUN
        assert scope_item_update.execution_status == ExecutionStatus.PASSED
        
        print("[PASS] Pydantic schemas work correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Pydantic schemas test failed: {e}")
        return False


def test_uniqueness_constraints():
    """Test that uniqueness constraints are defined."""
    print("\nTesting uniqueness constraints...")
    
    try:
        # Check that the model has the correct table args
        from app.models.regression_suite import RegressionScopeItem
        
        # Verify the model has the __table_args__ with unique constraints
        assert hasattr(RegressionScopeItem, '__table_args__')
        
        table_args = RegressionScopeItem.__table_args__
        
        # Check for unique constraints
        unique_constraints_found = False
        for constraint in table_args:
            if hasattr(constraint, 'name'):
                if 'uq_scope_items_suite' in constraint.name:
                    unique_constraints_found = True
                    break
        
        assert unique_constraints_found, "Uniqueness constraints not found"
        
        print("[PASS] Uniqueness constraints defined correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Uniqueness constraints test failed: {e}")
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
    """Test that RegressionScopeItem model is registered in __init__.py."""
    print("\nTesting model registration...")
    
    try:
        from app.models import RegressionScopeItem
        
        assert RegressionScopeItem is not None
        
        print("[PASS] RegressionScopeItem model registered in __init__.py")
        return True
    except Exception as e:
        print(f"[FAIL] Model registration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("RegressionScopeItem Model Tests")
    print("="*60)
    
    results = []
    results.append(("Automated scope item", test_automated_scope_item()))
    results.append(("Suggested scenario item", test_suggested_scenario_item()))
    results.append(("Manual scope item", test_manual_scope_item()))
    results.append(("Coverage gap item", test_coverage_gap_item()))
    results.append(("Enum values", test_enum_values()))
    results.append(("Pydantic schemas", test_pydantic_schemas()))
    results.append(("Uniqueness constraints", test_uniqueness_constraints()))
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
