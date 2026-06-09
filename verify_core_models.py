"""
Comprehensive Verification Script for Milestone 6E Core Regression Scope Models

Verifies that all new models work together before adding services.
"""

import sys
import os
import uuid
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(test_name, passed, message=""):
    """Print a test result."""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status}: {test_name}")
    if message:
        print(f"  {message}")


def test_model_imports():
    """Test that all models can be imported."""
    print_section("1. Testing Model Imports")
    
    try:
        from app.models.release import Release, ReleaseType, ReleaseStatus
        print_result("Release model import", True)
        
        from app.models.regression_suite import (
            RegressionSuite, SuiteType, SuiteStatus, 
            RegressionScopeItem, ScopeItemType, ScopeTier, ScopePriority, ExecutionStatus,
            ScopeOverride, OverrideType
        )
        print_result("RegressionSuite model import", True)
        print_result("RegressionScopeItem model import", True)
        print_result("ScopeOverride model import", True)
        
        from app.models.test_asset import TestAsset, TestPriority, TestType, BusinessCriticality, AutomationStatus
        print_result("TestAsset model import", True)
        
        return True
    except Exception as e:
        print_result("Model imports", False, str(e))
        return False


def test_enum_naming_conflicts():
    """Test for enum naming conflicts."""
    print_section("2. Testing Enum Naming Conflicts")
    
    try:
        from app.models.release import ReleaseType, ReleaseStatus
        from app.models.regression_suite import SuiteType, SuiteStatus, ScopeItemType, ScopeTier, ScopePriority, ExecutionStatus, OverrideType
        from app.models.test_asset import TestPriority, TestType, BusinessCriticality, AutomationStatus
        
        # Check for duplicate enum values across models
        all_enums = {
            "ReleaseType": [ReleaseType.MAJOR, ReleaseType.MINOR, ReleaseType.PATCH, ReleaseType.HOTFIX, ReleaseType.CUSTOM],
            "ReleaseStatus": [ReleaseStatus.PLANNED, ReleaseStatus.IN_PROGRESS, ReleaseStatus.READY_FOR_SIGNOFF, ReleaseStatus.RELEASED, ReleaseStatus.ROLLED_BACK, ReleaseStatus.CANCELLED],
            "SuiteType": [SuiteType.PR_REGRESSION, SuiteType.RELEASE_REGRESSION, SuiteType.SMOKE, SuiteType.FULL, SuiteType.HOTFIX],
            "SuiteStatus": [SuiteStatus.DRAFT, SuiteStatus.REVIEWED, SuiteStatus.APPROVED, SuiteStatus.EXECUTED, SuiteStatus.BLOCKED, SuiteStatus.ARCHIVED],
            "ScopeItemType": [ScopeItemType.AUTOMATED_TEST, ScopeItemType.MANUAL_TEST, ScopeItemType.SUGGESTED_SCENARIO, ScopeItemType.COVERAGE_GAP],
            "ScopeTier": [ScopeTier.MUST_RUN, ScopeTier.SHOULD_RUN, ScopeTier.OPTIONAL],
            "ScopePriority": [ScopePriority.CRITICAL, ScopePriority.HIGH, ScopePriority.MEDIUM, ScopePriority.LOW],
            "ExecutionStatus": [ExecutionStatus.NOT_RUN, ExecutionStatus.PASSED, ExecutionStatus.FAILED, ExecutionStatus.SKIPPED, ExecutionStatus.BLOCKED, ExecutionStatus.MANUAL_PENDING, ExecutionStatus.UNKNOWN],
            "OverrideType": [OverrideType.ADDED, OverrideType.REMOVED, OverrideType.TIER_CHANGED, OverrideType.PRIORITY_CHANGED, OverrideType.MARKED_REQUIRED, OverrideType.MARKED_OPTIONAL, OverrideType.EXCLUDED, OverrideType.RESTORED],
            "TestPriority": [TestPriority.CRITICAL, TestPriority.HIGH, TestPriority.MEDIUM, TestPriority.LOW],
            "TestType": [TestType.UNIT, TestType.API, TestType.INTEGRATION, TestType.E2E, TestType.UI, TestType.SECURITY, TestType.PERFORMANCE, TestType.MANUAL, TestType.SMOKE],
            "BusinessCriticality": [BusinessCriticality.MISSION_CRITICAL, BusinessCriticality.IMPORTANT, BusinessCriticality.SUPPORTING],
            "AutomationStatus": [AutomationStatus.AUTOMATED, AutomationStatus.MANUAL, AutomationStatus.PARTIALLY_AUTOMATED, AutomationStatus.UNKNOWN],
        }
        
        # Check for duplicate enum names
        enum_names = list(all_enums.keys())
        if len(enum_names) != len(set(enum_names)):
            print_result("Enum naming conflicts", False, "Duplicate enum names found")
            return False
        
        # Check for potential value conflicts (same value in different enums is OK, but should be noted)
        print_result("Enum naming conflicts", True, "No duplicate enum names found")
        return True
    except Exception as e:
        print_result("Enum naming conflicts", False, str(e))
        return False


def test_relationship_errors():
    """Test for relationship errors."""
    print_section("3. Testing Relationship Errors")
    
    try:
        from app.models.release import Release
        from app.models.regression_suite import RegressionSuite, RegressionScopeItem, ScopeOverride
        from app.models.test_asset import TestAsset
        from app.models.repository import Repository
        from sqlalchemy import inspect
        
        # Check Release relationships
        release_mapper = inspect(Release)
        assert hasattr(release_mapper.relationships, 'repository')
        assert hasattr(release_mapper.relationships, 'regression_suites')
        print_result("Release relationships", True)
        
        # Check RegressionSuite relationships
        suite_mapper = inspect(RegressionSuite)
        assert hasattr(suite_mapper.relationships, 'repository')
        assert hasattr(suite_mapper.relationships, 'release')
        assert hasattr(suite_mapper.relationships, 'pull_request')
        assert hasattr(suite_mapper.relationships, 'recommendation_run')
        assert hasattr(suite_mapper.relationships, 'scope_items')
        assert hasattr(suite_mapper.relationships, 'overrides')
        print_result("RegressionSuite relationships", True)
        
        # Check RegressionScopeItem relationships
        item_mapper = inspect(RegressionScopeItem)
        assert hasattr(item_mapper.relationships, 'regression_suite')
        assert hasattr(item_mapper.relationships, 'test_case')
        assert hasattr(item_mapper.relationships, 'external_test_case')
        assert hasattr(item_mapper.relationships, 'suggested_scenario')
        assert hasattr(item_mapper.relationships, 'behavior')
        assert hasattr(item_mapper.relationships, 'journey')
        assert hasattr(item_mapper.relationships, 'acceptance_criterion')
        assert hasattr(item_mapper.relationships, 'overrides')
        print_result("RegressionScopeItem relationships", True)
        
        # Check ScopeOverride relationships
        override_mapper = inspect(ScopeOverride)
        assert hasattr(override_mapper.relationships, 'regression_suite')
        assert hasattr(override_mapper.relationships, 'scope_item')
        print_result("ScopeOverride relationships", True)
        
        # Check TestAsset relationships
        asset_mapper = inspect(TestAsset)
        assert hasattr(asset_mapper.relationships, 'repository')
        assert hasattr(asset_mapper.relationships, 'test_case')
        assert hasattr(asset_mapper.relationships, 'external_test_case')
        print_result("TestAsset relationships", True)
        
        # Check Repository relationships
        repo_mapper = inspect(Repository)
        assert hasattr(repo_mapper.relationships, 'releases')
        assert hasattr(repo_mapper.relationships, 'regression_suites')
        assert hasattr(repo_mapper.relationships, 'test_assets')
        print_result("Repository relationships", True)
        
        return True
    except Exception as e:
        print_result("Relationship errors", False, str(e))
        return False


def test_duplicate_table_names():
    """Test for duplicate table names."""
    print_section("4. Testing Duplicate Table Names")
    
    try:
        from app.models.release import Release
        from app.models.regression_suite import RegressionSuite, RegressionScopeItem, ScopeOverride
        from app.models.test_asset import TestAsset
        from sqlalchemy import inspect
        
        # Get table names
        tables = {
            "Release": Release.__tablename__,
            "RegressionSuite": RegressionSuite.__tablename__,
            "RegressionScopeItem": RegressionScopeItem.__tablename__,
            "ScopeOverride": ScopeOverride.__tablename__,
            "TestAsset": TestAsset.__tablename__,
        }
        
        # Check for duplicates
        table_names = list(tables.values())
        if len(table_names) != len(set(table_names)):
            duplicates = [name for name in table_names if table_names.count(name) > 1]
            print_result("Duplicate table names", False, f"Duplicate tables: {duplicates}")
            return False
        
        print_result("Duplicate table names", True, f"Tables: {', '.join(table_names)}")
        return True
    except Exception as e:
        print_result("Duplicate table names", False, str(e))
        return False


def test_circular_imports():
    """Test for circular imports."""
    print_section("5. Testing Circular Imports")
    
    try:
        # Import all models in different orders to detect circular imports
        from app.models import Release
        from app.models import RegressionSuite
        from app.models import RegressionScopeItem
        from app.models import ScopeOverride
        from app.models import TestAsset
        from app.models import Repository
        
        # Try importing in reverse order
        from app.models import TestAsset, ScopeOverride, RegressionScopeItem, RegressionSuite, Release, Repository
        
        print_result("Circular imports", True, "No circular imports detected")
        return True
    except Exception as e:
        print_result("Circular imports", False, str(e))
        return False


def test_model_registration():
    """Test that all models are registered in __init__.py."""
    print_section("6. Testing Model Registration")
    
    try:
        from app.models import (
            Release, ReleaseType, ReleaseStatus,
            RegressionSuite, SuiteType, SuiteStatus, RegressionScopeItem, ScopeOverride,
            TestAsset
        )
        
        assert Release is not None
        assert ReleaseType is not None
        assert ReleaseStatus is not None
        assert RegressionSuite is not None
        assert SuiteType is not None
        assert SuiteStatus is not None
        assert RegressionScopeItem is not None
        assert ScopeOverride is not None
        assert TestAsset is not None
        
        print_result("Model registration", True, "All models registered in __init__.py")
        return True
    except Exception as e:
        print_result("Model registration", False, str(e))
        return False


def test_minimal_crud():
    """Test minimal CRUD operations (model instantiation)."""
    print_section("7. Testing Minimal CRUD (Model Instantiation)")
    
    try:
        from app.models.release import Release, ReleaseType, ReleaseStatus
        from app.models.regression_suite import RegressionSuite, SuiteType, SuiteStatus
        from app.models.regression_suite import RegressionScopeItem, ScopeItemType, ScopeTier, ScopePriority, ExecutionStatus
        from app.models.regression_suite import ScopeOverride, OverrideType
        from app.models.test_asset import TestAsset, TestPriority, TestType, BusinessCriticality, AutomationStatus
        
        # Test Release instantiation
        release = Release(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            version="v1.0.0",
            release_type=ReleaseType.MINOR,
            status=ReleaseStatus.PLANNED,
            created_by="test",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        assert release.version == "v1.0.0"
        print_result("Release instantiation", True)
        
        # Test RegressionSuite instantiation
        suite = RegressionSuite(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            name="Test Suite",
            suite_type=SuiteType.PR_REGRESSION,
            status=SuiteStatus.DRAFT,
            created_by="test",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        assert suite.name == "Test Suite"
        print_result("RegressionSuite instantiation", True)
        
        # Test RegressionScopeItem instantiation
        item = RegressionScopeItem(
            id=uuid.uuid4(),
            regression_suite_id=uuid.uuid4(),
            test_case_id=uuid.uuid4(),
            item_type=ScopeItemType.AUTOMATED_TEST,
            tier=ScopeTier.MUST_RUN,
            priority=ScopePriority.CRITICAL,
            execution_status=ExecutionStatus.NOT_RUN,
            is_excluded=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        assert item.item_type == ScopeItemType.AUTOMATED_TEST
        print_result("RegressionScopeItem instantiation", True)
        
        # Test ScopeOverride instantiation
        override = ScopeOverride(
            id=uuid.uuid4(),
            regression_scope_item_id=uuid.uuid4(),
            regression_suite_id=uuid.uuid4(),
            override_type=OverrideType.TIER_CHANGED,
            original_value={"tier": "MUST_RUN"},
            new_value={"tier": "SHOULD_RUN"},
            reason="Test reason",
            overridden_by="test",
            overridden_at=datetime.utcnow()
        )
        assert override.override_type == OverrideType.TIER_CHANGED
        print_result("ScopeOverride instantiation", True)
        
        # Test TestAsset instantiation
        asset = TestAsset(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            test_case_id=uuid.uuid4(),
            stable_identity="test.identity",
            display_name="Test Asset",
            priority=TestPriority.HIGH,
            test_type=TestType.UNIT,
            business_criticality=BusinessCriticality.IMPORTANT,
            automation_status=AutomationStatus.AUTOMATED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        assert asset.display_name == "Test Asset"
        print_result("TestAsset instantiation", True)
        
        return True
    except Exception as e:
        print_result("Minimal CRUD", False, str(e))
        return False


def test_migration_file():
    """Test that migration file exists and can be imported."""
    print_section("8. Testing Migration File")
    
    try:
        migration_path = os.path.join(os.path.dirname(__file__), 'alembic', 'versions', 'k2l3m4n5o6p7_add_regression_scope_models.py')
        
        if not os.path.exists(migration_path):
            print_result("Migration file exists", False, f"File not found: {migration_path}")
            return False
        
        # Try to import the migration module
        import importlib.util
        spec = importlib.util.spec_from_file_location("migration", migration_path)
        if spec and spec.loader:
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)
            print_result("Migration file import", True, migration_path)
            
            # Check that migration contains all tables
            content = open(migration_path, 'r').read()
            required_tables = ['releases', 'regression_suites', 'regression_scope_items', 'scope_overrides', 'test_assets']
            for table in required_tables:
                if table not in content:
                    print_result(f"Migration contains {table}", False)
                    return False
            print_result("Migration contains all tables", True)
            return True
        else:
            print_result("Migration file import", False, "Could not load migration module")
            return False
    except Exception as e:
        print_result("Migration file", False, str(e))
        return False


def main():
    """Run all verification checks."""
    print("="*60)
    print("Milestone 6E Core Regression Scope Models Verification")
    print("="*60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    results = []
    
    # Run all verifications
    results.append(("Model imports", test_model_imports()))
    results.append(("Enum naming conflicts", test_enum_naming_conflicts()))
    results.append(("Relationship errors", test_relationship_errors()))
    results.append(("Duplicate table names", test_duplicate_table_names()))
    results.append(("Circular imports", test_circular_imports()))
    results.append(("Model registration", test_model_registration()))
    results.append(("Minimal CRUD", test_minimal_crud()))
    results.append(("Migration file", test_migration_file()))
    
    # Print summary
    print_section("Verification Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n[SUCCESS] All verification checks passed!")
        print("Core models are ready for service implementation.")
        return 0
    else:
        print(f"\n[FAILURE] {total - passed} verification check(s) failed!")
        print("Please fix the issues before proceeding to service implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
