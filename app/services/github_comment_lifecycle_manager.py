import logging
from typing import List, Dict, Any, Optional, Tuple
from app.services.github_api_client import GitHubApiClient
from app.services.comment_deduplication_engine import CommentDeduplicationEngine

logger = logging.getLogger("veriscope.github_comment_lifecycle_manager")

TRACKING_MARKERS = ["<!-- veriscope:comment -->", "<!-- veriscope-pr-comment -->"]

class GitHubCommentLifecycleManager:
    def __init__(self, client: Optional[GitHubApiClient] = None):
        self.client = client or GitHubApiClient()

    @classmethod
    def is_canonical_comment(cls, body: str) -> bool:
        """Check if comment body contains any of the tracking markers."""
        if not body:
            return False
        return any(marker in body for marker in TRACKING_MARKERS)

    @classmethod
    def resolve_comments_lineage(
        cls,
        comments: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """Process a list of PR comments to identify the oldest canonical comment
        and any duplicate canonical comments.
        """
        canonicals = []
        for c in comments:
            if cls.is_canonical_comment(c.get("body", "")):
                canonicals.append(c)

        if not canonicals:
            return None, []

        # Sort chronologically by id or created_at (API returns chronologically by default,
        # but sorting explicitly by ID or created_at guarantees deterministic behavior)
        # Handle created_at string sort or fallback to ID
        canonicals.sort(key=lambda x: (x.get("created_at", ""), x.get("id", 0)))

        oldest_canonical = canonicals[0]
        duplicates = canonicals[1:]
        
        return oldest_canonical, duplicates

    def publish_or_update_comment(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        pull_number: int,
        body_text: str,
        auto_cleanup_duplicates: bool = True
    ) -> Dict[str, Any]:
        """Orchestrate the PR comment delivery lifecycle:
        - Lists existing PR comments.
        - Identifies oldest canonical comment and duplicates.
        - If oldest canonical comment body matches body_text exactly, skips API updates to prevent spam.
        - Updates oldest canonical in-place, or creates a new one if missing.
        - Cleans up duplicate comments automatically to avoid thread clutter.
        """
        # 1. Fetch comments paginated
        comments = self.client.list_pr_comments(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            pull_number=pull_number
        )

        oldest_canonical, duplicates = self.resolve_comments_lineage(comments)

        # 2. Prevent comment storms / duplicates
        if oldest_canonical:
            existing_body = oldest_canonical.get("body", "")

            # Use CommentDeduplicationEngine for timestamp-stable normalized comparison
            if not CommentDeduplicationEngine.should_update_comment(existing_body, body_text):
                logger.info(
                    f"Skipping update: normalized body hash unchanged for canonical comment "
                    f"{oldest_canonical['id']}."
                )

                # Still log duplicate presence even when skipping main update
                if duplicates:
                    logger.warning(
                        f"{len(duplicates)} duplicate Veriscope comment(s) found on PR {pull_number}. "
                        f"Marked stale internally. No deletion performed."
                    )

                return {
                    "status": "SKIPPED_NO_CHANGE",
                    "comment_id": oldest_canonical["id"],
                    "comment": oldest_canonical,
                    "duplicate_count": len(duplicates)
                }

            # 3. Update oldest canonical comment in-place
            logger.info(f"Updating existing canonical comment {oldest_canonical['id']} in-place.")
            res = self.client.update_pr_comment(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                comment_id=oldest_canonical["id"],
                body_text=body_text
            )
            
            # Clean up duplicates
            if auto_cleanup_duplicates and duplicates:
                self._cleanup_duplicates(installation_id, owner, repo, duplicates)

            return {
                "status": "UPDATED",
                "comment_id": oldest_canonical["id"],
                "comment": res,
                "cleaned_duplicates_count": len(duplicates)
            }

        else:
            # 4. Create new canonical comment
            logger.info(f"No existing canonical comment found on PR {pull_number}. Posting new comment.")
            
            # Ensure the tracking marker is appended if not present
            if not any(marker in body_text for marker in TRACKING_MARKERS):
                body_text += "\n<!-- veriscope:comment -->"

            res = self.client.create_pr_comment(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                pull_number=pull_number,
                body_text=body_text
            )

            return {
                "status": "CREATED",
                "comment_id": res["id"],
                "comment": res,
                "cleaned_duplicates_count": 0
            }

    def _cleanup_duplicates(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        duplicates: List[Dict[str, Any]]
    ):
        """Optionally clean up duplicate comments to preserve thread formatting."""
        for dup in duplicates:
            try:
                dup_id = dup.get("id")
                if dup_id:
                    logger.warning(f"Cleaning up duplicate canonical comment {dup_id}.")
                    # Call delete PR comment endpoint if client supports it,
                    # or update it to be marked stale to avoid clutter.
                    # Let's delete it if a delete method is supported on client, 
                    # otherwise mark it as stale/deleted text to cleanly clean it up.
                    if hasattr(self.client, "delete_pr_comment"):
                        self.client.delete_pr_comment(
                            installation_id=installation_id,
                            owner=owner,
                            repo=repo,
                            comment_id=dup_id
                        )
                    else:
                        # Fallback stale placeholder update if delete is unavailable
                        stale_marker = f"*(duplicate comment marked stale and replaced)*\n<!-- veriscope_duplicate_stale -->"
                        self.client.update_pr_comment(
                            installation_id=installation_id,
                            owner=owner,
                            repo=repo,
                            comment_id=dup_id,
                            body_text=stale_marker
                        )
            except Exception as e:
                logger.error(f"Error during duplicate comment cleanup {dup.get('id')}: {e}")
