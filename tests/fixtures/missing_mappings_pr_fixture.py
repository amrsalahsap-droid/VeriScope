"""
Fixture E — Missing mappings

Impacted AC has no tests, must become REQUIRED / GAP, not SAFE_TO_SKIP.
Validates that missing evidence is not classified as safe.
"""

from datetime import datetime
from uuid import uuid4
from typing import Dict, Any


def get_missing_mappings_pr_fixture() -> Dict[str, Any]:
    """Get missing mappings PR fixture data.
    
    This fixture represents a PR where an impacted AC has no mapped tests,
    which should become REQUIRED / COVERAGE_GAP, not SAFE_TO_SKIP.
    
    Returns:
        Dictionary with fixture data
    """
    return {
        "fixture_name": "missing_mappings_pr",
        "description": "Missing mappings PR with impacted AC but no tests",
        "repository_id": str(uuid4()),
        "pull_request_id": str(uuid4()),
        "head_commit_sha": "missing-mappings-jkl012",
        
        "changed_files": [
            {
                "file_path": "src/services/shipping/shipping-service.ts",
                "status": "modified",
                "additions": 25,
                "deletions": 10,
            },
        ],
        
        "impacted_acs": [
            {
                "ac_id": "AC-SHIPPING-001",
                "ac_title": "Shipping cost calculation",
                "impacted": True,
                "linked_tests": [],  # No tests mapped
            },
        ],
        
        "expected_behavior": {
            "structural_impact": True,
            "impacted_acs": ["AC-SHIPPING-001"],
            "no_mapped_tests": True,
            "bucket": "COVERAGE_GAP",
            "must_not_be": "SAFE_TO_SKIP",
            "reason_code": "COVERAGE_GAP",
        },
    }
