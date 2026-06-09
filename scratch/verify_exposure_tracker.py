import os
import sys
import uuid
import time
import datetime
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestCommentState, PullRequestCommentDeliveryEvent
from app.models.github_installation import GitHubInstallation
from app.models.recommendation import RecommendationRun, RecommendationOutcome
from app.services.recommendation import RecommendationService
from app.services.pr_comment_service import PRCommentService
from app.services.recommendation_exposure_tracker import RecommendationExposureTracker
from app.services.github_api_client import GitHubApiClient


def cleanup_database():
    """Clean up database records after test runs."""
    db = SessionLocal()
    try:
        db.query(PullRequestCommentDeliveryEvent).delete()
        db.query(PullRequestCommentState).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationRun).delete()
        db.query(GitHubInstallation).delete()
        db.query(PullRequest).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("Database cleanup successful.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()


def run_exposure_tracker_verification():
    print("======================================================================")
    print("STARTING RECOMMENDATION EXPOSURE TRACKER VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_uuid = uuid.uuid4()

    # Save original settings for restore
    from app.config import settings
    orig_app_id = settings.GITHUB_APP_ID
    orig_pkey = settings.GITHUB_PRIVATE_KEY
    orig_list = GitHubApiClient.list_pr_comments
    orig_create = GitHubApiClient.create_pr_comment
    orig_update = GitHubApiClient.update_pr_comment

    try:
        # Mock credentials to pass PRCommentService checks
        settings.GITHUB_APP_ID = "mock-app-id"
        settings.GITHUB_PRIVATE_KEY = "mock-private-key"

        # 1. Seed base structures
        org = Organization(id=org_id, name="Exposure Tracker Labs", slug="exposure-labs")
        db.add(org)

        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=112233,
            name="exposure-core",
            full_name="exposure-labs/exposure-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)

        installation = GitHubInstallation(
            id=uuid.uuid4(),
            organization_id=org_id,
            github_installation_id=998877,
            account_login="exposure-labs",
            created_at=datetime.datetime.utcnow()
        )
        db.add(installation)

        pr = PullRequest(
            id=pr_uuid,
            repository_id=repo_id,
            github_pr_id=777,
            number=7,
            title="PR 7 - Exposure Tracking",
            author="engineer-exposure",
            source_branch="exposure-patch",
            target_branch="main",
            state="open",
            additions=5,
            deletions=1,
            changed_files_count=1,
            head_commit_sha="pr_7",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.commit()

        rec_service = RecommendationService(db)

        # 2. Rule 1: recommendation_presented_at is NULL in default placeholder
        print("--- 1. Testing Default Placeholder Has NULL presented_at ---")
        run_in = RecommendationRun.metadata  # Just generate using RecommendationService
        
        # We'll call create_recommendation_run using service
        from app.schemas.recommendation import RecommendationRunCreate
        create_schema = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id="pr_7",
            triggered_by="github-webhook",
            changed_files=["app/models/organization.py"]
        )
        # Prevent queueing RQ comment delivery during generation inside service
        orig_enqueue = PRCommentService.enqueue_delivery_task
        PRCommentService.enqueue_delivery_task = MagicMock()

        run_rec = rec_service.create_recommendation_run(create_schema)
        
        # Restore enqueue
        PRCommentService.enqueue_delivery_task = orig_enqueue

        # Assert initial placeholder outcome has NULL presented_at
        placeholder = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == run_rec.id
        ).first()

        assert placeholder is not None
        assert placeholder.recommendation_presented_at is None
        print("SUCCESS: RecommendationOutcome starts with presented_at = NULL in default placeholder!")

        # 3. Rule 3: Failed GitHub delivery must NOT mark recommendation as presented
        print("\n--- 2. Testing Failed GitHub Delivery Does NOT Set presented_at ---")
        
        # Mock transient error in GitHubApiClient
        GitHubApiClient.list_pr_comments = MagicMock(return_value=[])
        GitHubApiClient.create_pr_comment = MagicMock(side_effect=Exception("503 Service Unavailable"))

        pr_comment_service = PRCommentService(db)
        
        # Execute delivery which will fail and retry/fail
        try:
            pr_comment_service.deliver_pr_comment_for_run(run_rec.id)
        except Exception:
            pass  # It's expected to raise or log failure

        # Reload outcome and assert presented_at is still NULL
        db.refresh(placeholder)
        assert placeholder.recommendation_presented_at is None
        print("SUCCESS: Failed GitHub delivery correctly kept presented_at = NULL!")

        # 4. Rule 1: recommendation_presented_at set ONLY after successful GitHub comment delivery
        print("\n--- 3. Testing Successful GitHub Delivery Sets presented_at ---")
        
        # Mock successful GitHubApiClient calls
        GitHubApiClient.list_pr_comments = MagicMock(return_value=[])
        GitHubApiClient.create_pr_comment = MagicMock(return_value={"id": 88888})

        # Execute delivery which will succeed
        pr_comment_service.deliver_pr_comment_for_run(run_rec.id)

        # Reload outcome and assert presented_at is now set!
        db.refresh(placeholder)
        presented_time_1 = placeholder.recommendation_presented_at
        assert presented_time_1 is not None
        print(f"SUCCESS: Successful GitHub delivery correctly set presented_at to {presented_time_1}!")

        # 5. Rule 4: Replayability / Immutability of presented_at
        print("\n--- 4. Testing Replayability and Timestamp Immutability ---")
        
        time.sleep(1)  # Ensure a distinct timestamp in case it tries to change it
        
        # Direct tracker call simulating a replay or duplicate delivery
        tracker = RecommendationExposureTracker(db)
        tracker.track_presented(run_rec.id)

        db.refresh(placeholder)
        presented_time_2 = placeholder.recommendation_presented_at
        
        assert presented_time_1 == presented_time_2
        print(f"SUCCESS: Replayed presentation preserved original timestamp {presented_time_1} (Immutable)!")

        # 6. Rule 2: Acknowledgment flow (acknowledged_at) and status transition
        print("\n--- 5. Testing Acknowledgment Flow and Status Transition ---")
        
        # After a successful delivery, was_followed=True in the placeholder makes
        # the outcome_status "FOLLOWED" via the property setter. Acknowledge from that state.
        assert placeholder.outcome_status == "FOLLOWED"
        assert placeholder.recommendation_acknowledged_at is None

        # Call track_acknowledged
        tracker.track_acknowledged(run_rec.id)

        db.refresh(placeholder)
        ack_time_1 = placeholder.recommendation_acknowledged_at
        assert ack_time_1 is not None
        assert placeholder.outcome_status == "ACKNOWLEDGED"
        print(f"SUCCESS: Acknowledged tracked successfully at {ack_time_1} with state FOLLOWED -> ACKNOWLEDGED!")

        # Test acknowledgment immutability
        time.sleep(1)
        tracker.track_acknowledged(run_rec.id)
        db.refresh(placeholder)
        ack_time_2 = placeholder.recommendation_acknowledged_at
        assert ack_time_1 == ack_time_2
        print(f"SUCCESS: Replayed acknowledgment preserved original timestamp {ack_time_1} (Immutable)!")

    finally:
        # Restore original client properties
        settings.GITHUB_APP_ID = orig_app_id
        settings.GITHUB_PRIVATE_KEY = orig_pkey
        GitHubApiClient.list_pr_comments = orig_list
        GitHubApiClient.create_pr_comment = orig_create
        GitHubApiClient.update_pr_comment = orig_update
        db.close()

    print("\n=======================================================")
    print("ALL RECOMMENDATION EXPOSURE TRACKER TESTS PASSED!")
    print("=======================================================")


if __name__ == "__main__":
    cleanup_database()
    try:
        run_exposure_tracker_verification()
    finally:
        cleanup_database()
