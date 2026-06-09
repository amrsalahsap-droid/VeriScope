"""
Basic tests for RegressionSuite model.

Tests:
- create suite for PR
- create suite for Release
- create suite from recommendation_run_id nullable
- enum values work
- migration imports cleanly
"""

import sys
import os
import uuid
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.models.regression_suite import RegressionSuite, SuiteType, SuiteStatus
from app.api.models.regression_suite import RegressionSuiteCreate, RegressionSuiteResponse, RegressionSuiteUpdate


def test_suite_for_pr():
    """Test creating a RegressionSuite for a PR."""
    print("Testing RegressionSuite for PR...")
    
    try:
        # Create a mock suite instance for PR (without database)
        suite = RegressionSuite(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            release_id=None,
            pull_request_id=uuid.uuid4(),
            recommendation_run_id=None,
            name="PR Regression Suite",
            description="Regression suite for PR #123",
            suite_type=SuiteType.PR_REGRESSION,
            status=SuiteStatus.DRAFT,
            confidence_level="HIGH",
            scope_score=0.85,
            created_by="test_user",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        assert suite.name == "PR Regression Suite"
        assert suite.suite_type == SuiteType.PR_REGRESSION
        assert suite.status == SuiteStatus.DRAFT
        assert suite.pull_request_id is not None
        assert suite.release_id is None
        assert suite.recommendation_run_id is None
        
        print("[PASS] RegressionSuite for PR created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] RegressionSuite for PR creation failed: {e}")
        return False


def test_suite_for_release():
    """Test creating a RegressionSuite for a Release."""
    print("\nTesting RegressionSuite for Release...")
    
    try:
        # Create a mock suite instance for Release (without database)
        suite = RegressionSuite(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            release_id=uuid.uuid4(),
            pull_request_id=None,
            recommendation_run_id=None,
            name="Release Regression Suite",
            description="Regression suite for v1.2.0",
            suite_type=SuiteType.RELEASE_REGRESSION,
            status=SuiteStatus.APPROVED,
            confidence_level="MODERATE",
            scope_score=0.75,
            created_by="test_user",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        assert suite.name == "Release Regression Suite"
        assert suite.suite_type == SuiteType.RELEASE_REGRESSION
        assert suite.status == SuiteStatus.APPROVED
        assert suite.release_id is not None
        assert suite.pull_request_id is None
        assert suite.recommendation_run_id is None
        
        print("[PASS] RegressionSuite for Release created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] RegressionSuite for Release creation failed: {e}")
        return False


def test_suite_from_recommendation_run():
    """Test creating a RegressionSuite from a recommendation_run_id (nullable)."""
    print("\nTesting RegressionSuite from recommendation_run_id...")
    
    try:
        # Create a mock suite instance from recommendation run (without database)
        suite = RegressionSuite(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            release_id=None,
            pull_request_id=None,
            recommendation_run_id=uuid.uuid4(),
            name="Recommendation-based Suite",
            description="Suite generated from recommendation run",
            suite_type=SuiteType.PR_REGRESSION,
            status=SuiteStatus.DRAFT,
            confidence_level="HIGH",
            scope_score=0.9,
            created_by="system",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        assert suite.name == "Recommendation-based Suite"
        assert suite.recommendation_run_id is not None
        assert suite.release_id is None
        assert suite.pull_request_id is None
        
        print("[PASS] RegressionSuite from recommendation_run_id created successfully")
        return True
    except Exception as e:
        print(f"[FAIL] RegressionSuite from recommendation_run_id creation failed: {e}")
        return False


def test_enum_values():
    """Test that enum values work correctly."""
    print("\nTesting enum values...")
    
    try:
        # Test SuiteType enum
        assert SuiteType.PR_REGRESSION == "PR_REGRESSION"
        assert SuiteType.RELEASE_REGRESSION == "RELEASE_REGRESSION"
        assert SuiteType.SMOKE == "SMOKE"
        assert SuiteType.FULL == "FULL"
        assert SuiteType.HOTFIX == "HOTFIX"
        
        # Test SuiteStatus enum
        assert SuiteStatus.DRAFT == "DRAFT"
        assert SuiteStatus.REVIEWED == "REVIEWED"
        assert SuiteStatus.APPROVED == "APPROVED"
        assert SuiteStatus.EXECUTED == "EXECUTED"
        assert SuiteStatus.BLOCKED == "BLOCKED"
        assert SuiteStatus.ARCHIVED == "ARCHIVED"
        
        print("[PASS] Enum values work correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Enum values test failed: {e}")
        return False


def test_pydantic_schemas():
    """Test Pydantic schemas."""
    print("\nTesting Pydantic schemas...")
    
    try:
        # Test RegressionSuiteCreate schema
        suite_create = RegressionSuiteCreate(
            repository_id=uuid.uuid4(),
            pull_request_id=uuid.uuid4(),
            name="Test Suite",
            suite_type=SuiteType.PR_REGRESSION,
            status=SuiteStatus.DRAFT,
            created_by="test_user"
        )
        assert suite_create.name == "Test Suite"
        assert suite_create.suite_type == SuiteType.PR_REGRESSION
        
        # Test RegressionSuiteUpdate schema
        suite_update = RegressionSuiteUpdate(
            status=SuiteStatus.REVIEWED,
            confidence_level="HIGH"
        )
        assert suite_update.status == SuiteStatus.REVIEWED
        assert suite_update.confidence_level == "HIGH"
        
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
    """Test that RegressionSuite model is registered in __init__.py."""
    print("\nTesting model registration...")
    
    try:
        from app.models import RegressionSuite, SuiteType, SuiteStatus
        
        assert RegressionSuite is not None
        assert SuiteType is not None
        assert SuiteStatus is not None
        
        print("[PASS] RegressionSuite model registered in __init__.py")
        return True
    except Exception as e:
        print(f"[FAIL] Model registration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("RegressionSuite Model Tests")
    print("="*60)
    
    results = []
    results.append(("Suite for PR", test_suite_for_pr()))
    results.append(("Suite for Release", test_suite_for_release()))
    results.append(("Suite from recommendation_run_id", test_suite_from_recommendation_run()))
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
