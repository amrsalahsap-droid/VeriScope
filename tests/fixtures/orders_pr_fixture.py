"""
Fixture C — Orders PR

Directed dependencies, tests covering changed file.
Validates directed dependency expansion correctness.
"""

from datetime import datetime
from uuid import uuid4
from typing import Dict, Any


def get_orders_pr_fixture() -> Dict[str, Any]:
    """Get orders PR fixture data.
    
    This fixture represents a PR that changes order-related files
    with directed dependencies and tests covering changed files.
    
    Returns:
        Dictionary with fixture data
    """
    return {
        "fixture_name": "orders_pr",
        "description": "Orders PR with directed dependencies and test coverage",
        "repository_id": str(uuid4()),
        "pull_request_id": str(uuid4()),
        "head_commit_sha": "orders-changes-def456",
        
        "changed_files": [
            {
                "file_path": "src/services/orders/order-service.ts",
                "status": "modified",
                "additions": 20,
                "deletions": 10,
            },
        ],
        
        "directed_dependencies": [
            {
                "source": "src/services/orders/order-service.ts",
                "target": "src/services/orders/order-validator.ts",
                "type": "imports",
            },
            {
                "source": "src/services/orders/order-validator.ts",
                "target": "src/services/orders/order-processor.ts",
                "type": "imports",
            },
        ],
        
        "order_tests": [
            {
                "stable_test_id": "test-order-service-001",
                "test_name": "Order service test",
                "file_path": "tests/orders/order-service.test.ts",
                "covers": ["src/services/orders/order-service.ts"],
            },
            {
                "stable_test_id": "test-order-validator-002",
                "test_name": "Order validator test",
                "file_path": "tests/orders/order-validator.test.ts",
                "covers": ["src/services/orders/order-validator.ts"],
            },
        ],
        
        "expected_behavior": {
            "structural_impact": True,
            "dependency_expansion": True,
            "impacted_files": [
                "src/services/orders/order-service.ts",
                "src/services/orders/order-validator.ts",
                "src/services/orders/order-processor.ts",
            ],
            "impacted_tests": ["test-order-service-001", "test-order-validator-002"],
        },
    }
