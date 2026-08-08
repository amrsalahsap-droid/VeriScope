"""
Fixture F — Coverage levels

Aggregate LCOV only, per-test coverage, no coverage.
Validates coverage level handling.
"""

from datetime import datetime
from uuid import uuid4
from typing import Dict, Any


def get_coverage_levels_pr_fixture() -> Dict[str, Any]:
    """Get coverage levels PR fixture data.
    
    This fixture represents different coverage level scenarios:
    - aggregate LCOV only
    - per-test coverage
    - no coverage
    
    Returns:
        Dictionary with fixture data
    """
    return {
        "fixture_name": "coverage_levels_pr",
        "description": "Coverage levels PR with different coverage scenarios",
        "repository_id": str(uuid4()),
        "pull_request_id": str(uuid4()),
        "head_commit_sha": "coverage-levels-mno345",
        
        "changed_files": [
            {
                "file_path": "src/services/user/user-service.ts",
                "status": "modified",
                "additions": 12,
                "deletions": 6,
            },
        ],
        
        "coverage_scenarios": [
            {
                "scenario": "aggregate_lcov_only",
                "coverage_level": "RUN_LEVEL",
                "description": "Only aggregate LCOV coverage available",
                "has_per_test_coverage": False,
                "expected_behavior": "File-level evidence only, no exact test selection",
            },
            {
                "scenario": "per_test_coverage",
                "coverage_level": "TEST_CASE_LEVEL",
                "description": "Per-test coverage available",
                "has_per_test_coverage": True,
                "expected_behavior": "Exact test selection with stable_test_ids",
            },
            {
                "scenario": "no_coverage",
                "coverage_level": "NONE",
                "description": "No coverage data available",
                "has_per_test_coverage": False,
                "expected_behavior": "Coverage gap, no test selection",
            },
        ],
        
        "expected_behavior": {
            "aggregate_coverage_not_per_test": True,
            "per_test_coverage_selects_impacted_tests": True,
            "no_coverage_creates_gap": True,
        },
    }
