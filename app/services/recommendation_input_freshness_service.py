import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationRun
from app.models.pull_request import PullRequest

logger = logging.getLogger("veriscope.recommendation_input_freshness")


class RecommendationInputFreshnessService:
    """Service for evaluating recommendation input freshness and detecting stale recommendations."""
    
    @staticmethod
    def evaluate_recommendation_input_freshness(
        db: Session,
        recommendation_run: RecommendationRun,
        current_pull_request: Optional[PullRequest] = None
    ) -> Dict[str, Any]:
        """
        Evaluate if a recommendation run's inputs are still fresh or have become stale.
        
        Rules:
        - If recommendation_run.head_commit_sha_at_generation is missing: STALE
        - If current_pull_request.head_commit_sha != recommendation_run.head_commit_sha_at_generation: STALE
        - If current changed files hash != snapshot changed files hash: STALE
        - Otherwise: FRESH
        
        Returns:
            Dict with:
            - input_stale: bool
            - stale_reason: str or None
            - current_head_sha: str or None
            - snapshot_head_sha: str or None
            - can_generate_confident_regression_plan: bool
        """
        if not recommendation_run:
            return {
                "input_stale": True,
                "stale_reason": "RECOMMENDATION_RUN_MISSING",
                "current_head_sha": None,
                "snapshot_head_sha": None,
                "can_generate_confident_regression_plan": False
            }
        
        # Rule 1: Check if head_commit_sha_at_generation exists
        if not recommendation_run.head_commit_sha_at_generation:
            logger.warning(
                f"RecommendationRun {recommendation_run.id} has no head_commit_sha_at_generation. "
                "Marking as stale."
            )
            return {
                "input_stale": True,
                "stale_reason": "HEAD_SHA_SNAPSHOT_MISSING",
                "current_head_sha": current_pull_request.head_commit_sha if current_pull_request else None,
                "snapshot_head_sha": None,
                "can_generate_confident_regression_plan": False
            }
        
        # Rule 2: Compare current PR head SHA with snapshot head SHA
        if current_pull_request:
            current_head_sha = current_pull_request.head_commit_sha
            snapshot_head_sha = recommendation_run.head_commit_sha_at_generation
            
            if current_head_sha != snapshot_head_sha:
                logger.info(
                    f"RecommendationRun {recommendation_run.id} is stale: "
                    f"current PR head SHA {current_head_sha} != snapshot head SHA {snapshot_head_sha}"
                )
                return {
                    "input_stale": True,
                    "stale_reason": "PR_UPDATED_AFTER_RECOMMENDATION",
                    "current_head_sha": current_head_sha,
                    "snapshot_head_sha": snapshot_head_sha,
                    "can_generate_confident_regression_plan": False
                }
            
            # Rule 3: Compare changed files if possible
            if recommendation_run.changed_files_snapshot_json:
                from app.models.pull_request import PullRequestChangedFile
                current_files = db.query(PullRequestChangedFile).filter(
                    PullRequestChangedFile.pull_request_id == current_pull_request.id
                ).all()
                
                current_file_paths = sorted([f.file_path for f in current_files])
                snapshot_file_paths = sorted([f["file_path"] for f in recommendation_run.changed_files_snapshot_json])
                
                if current_file_paths != snapshot_file_paths:
                    logger.info(
                        f"RecommendationRun {recommendation_run.id} is stale: "
                        f"changed files have changed since generation"
                    )
                    return {
                        "input_stale": True,
                        "stale_reason": "PR_CHANGED_FILES_UPDATED",
                        "current_head_sha": current_head_sha,
                        "snapshot_head_sha": snapshot_head_sha,
                        "can_generate_confident_regression_plan": False
                    }
        
        # All checks passed - recommendation is fresh
        return {
            "input_stale": False,
            "stale_reason": None,
            "current_head_sha": current_pull_request.head_commit_sha if current_pull_request else None,
            "snapshot_head_sha": recommendation_run.head_commit_sha_at_generation,
            "can_generate_confident_regression_plan": True
        }
    
    @staticmethod
    def update_recommendation_staleness(
        db: Session,
        recommendation_run: RecommendationRun,
        current_pull_request: Optional[PullRequest] = None
    ) -> None:
        """
        Update the recommendation run's staleness status in the database.
        
        This should be called when:
        - Recommendation page is loaded
        - Regression scope endpoint is called
        - Recommendation summary endpoint is called
        - PR is synced
        """
        freshness_result = RecommendationInputFreshnessService.evaluate_recommendation_input_freshness(
            db, recommendation_run, current_pull_request
        )
        
        # Update the recommendation run
        recommendation_run.input_stale = freshness_result["input_stale"]
        recommendation_run.stale_reason = freshness_result["stale_reason"]
        
        if freshness_result["input_stale"]:
            recommendation_run.stale_since = datetime.utcnow()
            recommendation_run.stale_input_types = ["PR_PACKAGE"]
        else:
            recommendation_run.stale_since = None
            recommendation_run.stale_input_types = None
        
        db.commit()
        logger.info(
            f"Updated RecommendationRun {recommendation_run.id} staleness: "
            f"input_stale={freshness_result['input_stale']}, "
            f"stale_reason={freshness_result['stale_reason']}"
        )
