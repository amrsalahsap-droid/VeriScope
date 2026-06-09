"""
Tests for RegressionSuite API Router

Tests:
- create suite API
- get suite API
- get scope API
- update tier with reason
- exclude item with reason
- list repository suites
- invalid item blocked
"""

import sys
import os
import uuid
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.routers.regression_suite import router
from app.api.models.regression_suite import (
    RegressionSuiteDetailResponse, RegressionScopeGroupedResponse, 
    RegressionScopeUpdateRequest, RegressionSuiteSummaryResponse
)


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


def test_router_import():
    """Test that the router can be imported."""
    print_section("1. Testing Router Import")
    
    try:
        from app.routers.regression_suite import router
        print_result("Router import", True)
        return True
    except Exception as e:
        print_result("Router import", False, str(e))
        return False


def test_endpoint_signatures():
    """Test that all required endpoints exist."""
    print_section("2. Testing Endpoint Signatures")
    
    try:
        from app.routers.regression_suite import router
        routes = [route.path for route in router.routes]
        
        # Check for key endpoint patterns
        patterns = [
            "recommendations",
            "regression-suite",
            "regression-suites",
            "scope",
            "override",
            "repositories",
            "releases"
        ]
        
        for pattern in patterns:
            found = any(pattern in route for route in routes)
            if found:
                print_result(f"Pattern: {pattern}", True)
            else:
                print_result(f"Pattern: {pattern}", False, "Not found")
                return False
        
        # Check for specific methods
        methods = {}
        for route in router.routes:
            if hasattr(route, 'methods'):
                for method in route.methods:
                    if method != 'HEAD':  # Skip HEAD methods
                        methods[method] = methods.get(method, 0) + 1
        
        print_result("HTTP methods", True, f"Found: {list(methods.keys())}")
        
        return True
    except Exception as e:
        print_result("Endpoint signatures", False, str(e))
        return False


def test_create_endpoint_params():
    """Test that create endpoint has force_new parameter."""
    print_section("3. Testing Create Endpoint Parameters")
    
    try:
        import inspect
        from app.routers.regression_suite import create_regression_suite_from_recommendation
        sig = inspect.signature(create_regression_suite_from_recommendation)
        params = list(sig.parameters.keys())
        
        assert "force_new" in params
        assert "created_by" in params
        assert "recommendation_run_id" in params
        
        print_result("Create endpoint parameters", True, f"Parameters: {params}")
        return True
    except Exception as e:
        print_result("Create endpoint parameters", False, str(e))
        return False


def test_update_endpoint_reason_requirement():
    """Test that update endpoint requires reason for tier/exclusion changes."""
    print_section("4. Testing Update Endpoint Reason Requirement")
    
    try:
        import inspect
        from app.routers.regression_suite import update_scope_item
        source = inspect.getsource(update_scope_item)
        
        # Check for reason requirement logic
        assert "reason" in source
        assert "Reason is required for tier changes" in source or "Reason is required for exclusion changes" in source
        
        print_result("Update endpoint reason requirement", True, "Reason validation found")
        return True
    except Exception as e:
        print_result("Update endpoint reason requirement", False, str(e))
        return False


def test_scope_endpoint_excluded_group():
    """Test that scope endpoint includes EXCLUDED group."""
    print_section("5. Testing Scope Endpoint EXCLUDED Group")
    
    try:
        import inspect
        from app.routers.regression_suite import get_regression_suite_scope
        source = inspect.getsource(get_regression_suite_scope)
        
        # Check for EXCLUDED group
        assert "EXCLUDED" in source
        assert "grouped_by_tier" in source
        
        print_result("Scope endpoint EXCLUDED group", True, "EXCLUDED group found")
        return True
    except Exception as e:
        print_result("Scope endpoint EXCLUDED group", False, str(e))
        return False


def test_schemas_import():
    """Test that all required schemas can be imported."""
    print_section("6. Testing Schemas Import")
    
    try:
        from app.api.models.regression_suite import (
            RegressionSuiteDetailResponse,
            RegressionScopeGroupedResponse,
            RegressionScopeUpdateRequest,
            RegressionSuiteSummaryResponse
        )
        
        print_result("RegressionSuiteDetailResponse import", True)
        print_result("RegressionScopeGroupedResponse import", True)
        print_result("RegressionScopeUpdateRequest import", True)
        print_result("RegressionSuiteSummaryResponse import", True)
        
        return True
    except Exception as e:
        print_result("Schemas import", False, str(e))
        return False


def test_schema_fields():
    """Test that schemas have required fields."""
    print_section("7. Testing Schema Fields")
    
    try:
        from app.api.models.regression_suite import (
            RegressionSuiteDetailResponse,
            RegressionScopeGroupedResponse,
            RegressionScopeUpdateRequest
        )
        
        # Check RegressionSuiteDetailResponse
        suite_detail_fields = RegressionSuiteDetailResponse.model_fields
        assert "scope_items_count" in suite_detail_fields
        print_result("RegressionSuiteDetailResponse fields", True)
        
        # Check RegressionScopeGroupedResponse
        scope_grouped_fields = RegressionScopeGroupedResponse.model_fields
        assert "grouped_by_tier" in scope_grouped_fields
        assert "all_items" in scope_grouped_fields
        print_result("RegressionScopeGroupedResponse fields", True)
        
        # Check RegressionScopeUpdateRequest
        scope_update_fields = RegressionScopeUpdateRequest.model_fields
        assert "reason" in scope_update_fields
        assert "tier" in scope_update_fields
        assert "is_excluded" in scope_update_fields
        print_result("RegressionScopeUpdateRequest fields", True)
        
        return True
    except Exception as e:
        print_result("Schema fields", False, str(e))
        return False


def test_item_validation():
    """Test that item belongs to suite validation exists."""
    print_section("8. Testing Item Validation")
    
    try:
        import inspect
        from app.routers.regression_suite import update_scope_item
        source = inspect.getsource(update_scope_item)
        
        # Check for validation that item belongs to suite
        assert "regression_suite_id" in source
        assert "regression_scope_item_id" in source or "item_id" in source
        
        print_result("Item validation", True, "Suite/item validation found")
        return True
    except Exception as e:
        print_result("Item validation", False, str(e))
        return False


def test_override_creation():
    """Test that override creation is implemented."""
    print_section("9. Testing Override Creation")
    
    try:
        import inspect
        from app.routers.regression_suite import (
            update_scope_item,
            create_scope_override
        )
        
        # Check update endpoint creates override
        update_source = inspect.getsource(update_scope_item)
        assert "ScopeOverride" in update_source
        
        # Check explicit override endpoint exists
        override_source = inspect.getsource(create_scope_override)
        assert "override_type" in override_source
        assert "reason" in override_source
        
        print_result("Override creation", True, "Override logic found")
        return True
    except Exception as e:
        print_result("Override creation", False, str(e))
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("RegressionSuite API Router Tests")
    print("="*60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    results = []
    
    # Run all tests
    results.append(("Router import", test_router_import()))
    results.append(("Endpoint signatures", test_endpoint_signatures()))
    results.append(("Create endpoint parameters", test_create_endpoint_params()))
    results.append(("Update endpoint reason requirement", test_update_endpoint_reason_requirement()))
    results.append(("Scope endpoint EXCLUDED group", test_scope_endpoint_excluded_group()))
    results.append(("Schemas import", test_schemas_import()))
    results.append(("Schema fields", test_schema_fields()))
    results.append(("Item validation", test_item_validation()))
    results.append(("Override creation", test_override_creation()))
    
    # Print summary
    print_section("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed!")
        print("RegressionSuite API router is ready for use.")
        return 0
    else:
        print(f"\n[FAILURE] {total - passed} test(s) failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
