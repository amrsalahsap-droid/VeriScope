import os
import sys
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.github_comment_lifecycle_manager import GitHubCommentLifecycleManager

def run_lifecycle_manager_verification():
    print("======================================================================")
    print("STARTING GITHUB COMMENT LIFECYCLE MANAGER VERIFICATIONS")
    print("======================================================================\n")

    manager = GitHubCommentLifecycleManager()

    # ====================================================================
    # Test 1. Lineage Resolution (Preserves Oldest Canonical)
    # ====================================================================
    print("--- 1. Testing Lineage Resolution & Oldest Preservation ---")

    comments = [
        {"id": 401, "body": "some text\n<!-- veriscope:comment -->", "created_at": "2026-05-23T12:05:00Z"},
        {"id": 202, "body": "unrelated user comment", "created_at": "2026-05-23T12:00:00Z"},
        {"id": 101, "body": "oldest veriscope\n<!-- veriscope-pr-comment -->", "created_at": "2026-05-23T11:00:00Z"},
        {"id": 505, "body": "newest veriscope\n<!-- veriscope:comment -->", "created_at": "2026-05-23T13:00:00Z"}
    ]

    oldest, duplicates = manager.resolve_comments_lineage(comments)
    
    print(f"DEBUG: Identified Oldest ID: {oldest['id'] if oldest else None}")
    print(f"DEBUG: Duplicate IDs: {[d['id'] for d in duplicates]}")

    assert oldest is not None
    assert oldest["id"] == 101
    assert len(duplicates) == 2
    assert duplicates[0]["id"] == 401
    assert duplicates[1]["id"] == 505
    print("[OK] Deterministically preserved oldest canonical comment and separated all duplicates.")

    # ====================================================================
    # Test 2. Publish New Comment (No canonical comment found)
    # ====================================================================
    print("\n--- 2. Testing Publish New Comment ---")

    with patch.object(manager.client, "list_pr_comments", return_value=[{"id": 202, "body": "user comment"}]) as mock_list, \
         patch.object(manager.client, "create_pr_comment", return_value={"id": 999}) as mock_create, \
         patch.object(manager.client, "update_pr_comment") as mock_update, \
         patch.object(manager.client, "delete_pr_comment") as mock_delete:

        res = manager.publish_or_update_comment(
            installation_id=123,
            owner="org",
            repo="repo",
            pull_number=1,
            body_text="calm senior release engineer text"
        )

        assert res["status"] == "CREATED"
        assert res["comment_id"] == 999
        mock_list.assert_called_once()
        mock_create.assert_called_once()
        mock_update.assert_not_called()
        mock_delete.assert_not_called()

        # Check that tracking marker was appended
        posted_body = mock_create.call_args[1]["body_text"]
        assert "<!-- veriscope:comment -->" in posted_body
        print("[OK] Created new canonical comment successfully when none was found.")

    # ====================================================================
    # Test 3. In-Place Update (Comment found and body changed)
    # ====================================================================
    print("\n--- 3. Testing In-Place Update ---")

    existing_comments = [
        {"id": 101, "body": "old body text\n<!-- veriscope:comment -->", "created_at": "2026-05-23T11:00:00Z"}
    ]

    with patch.object(manager.client, "list_pr_comments", return_value=existing_comments) as mock_list, \
         patch.object(manager.client, "create_pr_comment") as mock_create, \
         patch.object(manager.client, "update_pr_comment", return_value={"id": 101}) as mock_update, \
         patch.object(manager.client, "delete_pr_comment") as mock_delete:

        res = manager.publish_or_update_comment(
            installation_id=123,
            owner="org",
            repo="repo",
            pull_number=1,
            body_text="new body text\n<!-- veriscope:comment -->"
        )

        assert res["status"] == "UPDATED"
        assert res["comment_id"] == 101
        mock_list.assert_called_once()
        mock_update.assert_called_once_with(
            installation_id=123,
            owner="org",
            repo="repo",
            comment_id=101,
            body_text="new body text\n<!-- veriscope:comment -->"
        )
        mock_create.assert_not_called()
        mock_delete.assert_not_called()
        print("[OK] Updated existing canonical comment in-place successfully.")

    # ====================================================================
    # Test 4. Skip/Storm Protection (Same body text bypasses API calls)
    # ====================================================================
    print("\n--- 4. Testing Skip & Storm Protection ---")

    existing_comments = [
        {"id": 101, "body": "identical body text\n<!-- veriscope:comment -->", "created_at": "2026-05-23T11:00:00Z"}
    ]

    with patch.object(manager.client, "list_pr_comments", return_value=existing_comments) as mock_list, \
         patch.object(manager.client, "create_pr_comment") as mock_create, \
         patch.object(manager.client, "update_pr_comment") as mock_update, \
         patch.object(manager.client, "delete_pr_comment") as mock_delete:

        res = manager.publish_or_update_comment(
            installation_id=123,
            owner="org",
            repo="repo",
            pull_number=1,
            body_text="identical body text\n<!-- veriscope:comment -->"
        )

        assert res["status"] == "SKIPPED_NO_CHANGE"
        assert res["comment_id"] == 101
        mock_list.assert_called_once()
        mock_create.assert_not_called()
        mock_update.assert_not_called()
        mock_delete.assert_not_called()
        print("[OK] Bypassed external API updates when body remains unchanged (storm prevention active!).")

    # ====================================================================
    # Test 5. Duplicate Cleanups & Auditing
    # ====================================================================
    print("\n--- 5. Testing Duplicate Cleanup and Deletion ---")

    existing_comments = [
        {"id": 401, "body": "duplicate veriscope\n<!-- veriscope:comment -->", "created_at": "2026-05-23T12:05:00Z"},
        {"id": 101, "body": "oldest veriscope\n<!-- veriscope-pr-comment -->", "created_at": "2026-05-23T11:00:00Z"},
        {"id": 505, "body": "another duplicate\n<!-- veriscope:comment -->", "created_at": "2026-05-23T13:00:00Z"}
    ]

    with patch.object(manager.client, "list_pr_comments", return_value=existing_comments) as mock_list, \
         patch.object(manager.client, "create_pr_comment") as mock_create, \
         patch.object(manager.client, "update_pr_comment", return_value={"id": 101}) as mock_update, \
         patch.object(manager.client, "delete_pr_comment") as mock_delete:

        res = manager.publish_or_update_comment(
            installation_id=123,
            owner="org",
            repo="repo",
            pull_number=1,
            body_text="new body text\n<!-- veriscope:comment -->",
            auto_cleanup_duplicates=True
        )

        assert res["status"] == "UPDATED"
        assert res["comment_id"] == 101
        assert res["cleaned_duplicates_count"] == 2
        mock_list.assert_called_once()
        mock_update.assert_called_once()
        mock_create.assert_not_called()
        
        # Deletion assertions for all duplicate IDs!
        assert mock_delete.call_count == 2
        mock_delete.assert_any_call(installation_id=123, owner="org", repo="repo", comment_id=401)
        mock_delete.assert_any_call(installation_id=123, owner="org", repo="repo", comment_id=505)
        print("[OK] Duplicate comments cleanly deleted, preventing PR clutter.")

    print("\n=======================================================")
    print("ALL GITHUB COMMENT LIFECYCLE MANAGER VERIFICATIONS PASSED!")
    print("=======================================================\n")

if __name__ == "__main__":
    run_lifecycle_manager_verification()
