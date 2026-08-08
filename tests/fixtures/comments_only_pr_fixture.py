"""
Fixture D — Comments-only PR

AST says non-semantic changes only.
Validates non-semantic change detection.
"""

from datetime import datetime
from uuid import uuid4
from typing import Dict, Any


def get_comments_only_pr_fixture() -> Dict[str, Any]:
    """Get comments-only PR fixture data.
    
    This fixture represents a PR with only comment changes,
    which should be detected as non-semantic by AST analysis.
    
    Returns:
        Dictionary with fixture data
    """
    return {
        "fixture_name": "comments_only_pr",
        "description": "Comments-only PR with non-semantic changes",
        "repository_id": str(uuid4()),
        "pull_request_id": str(uuid4()),
        "head_commit_sha": "comments-only-ghi789",
        
        "changed_files": [
            {
                "file_path": "src/services/auth/auth-service.ts",
                "status": "modified",
                "additions": 5,
                "deletions": 3,
                "content_before": """
function validatePassword(password) {
    // Check password length
    if (password.length >= 8) {
        return true;
    }
    return false;
}
""",
                "content_after": """
function validatePassword(password) {
    // Validate password length requirement
    if (password.length >= 8) {
        return true;
    }
    return false;
}
""",
            },
        ],
        
        "expected_behavior": {
            "structural_impact": True,
            "non_semantic_changes_only": True,
            "comments_only": True,
            "semantic_change_count": 0,
            "bucket": "SAFE_TO_SKIP",
        },
    }
