"""
Fixture B — Billing PR

Changed billing service, billing tests, no auth keywords.
Validates non-auth domain works correctly.
"""

from datetime import datetime
from uuid import uuid4
from typing import Dict, Any


def get_billing_pr_fixture() -> Dict[str, Any]:
    """Get billing PR fixture data.
    
    This fixture represents a PR that changes billing service files
    with billing tests and no auth keywords.
    
    Returns:
        Dictionary with fixture data
    """
    return {
        "fixture_name": "billing_pr",
        "description": "Billing PR with billing service changes and billing tests",
        "repository_id": str(uuid4()),
        "pull_request_id": str(uuid4()),
        "head_commit_sha": "billing-changes-abc123",
        
        "changed_files": [
            {
                "file_path": "src/services/billing/invoice-service.ts",
                "status": "modified",
                "additions": 15,
                "deletions": 5,
            },
            {
                "file_path": "src/services/billing/payment-processor.ts",
                "status": "modified",
                "additions": 8,
                "deletions": 3,
            },
        ],
        
        "billing_tests": [
            {
                "stable_test_id": "test-billing-invoice-001",
                "test_name": "Invoice generation test",
                "file_path": "tests/billing/invoice.test.ts",
            },
            {
                "stable_test_id": "test-billing-payment-002",
                "test_name": "Payment processing test",
                "file_path": "tests/billing/payment.test.ts",
            },
        ],
        
        "expected_behavior": {
            "structural_impact": True,
            "impacted_tests": ["test-billing-invoice-001", "test-billing-payment-002"],
            "no_auth_keywords": True,
            "domain": "billing",
        },
    }
