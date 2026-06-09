import sys
import uuid
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import (
    PullRequest,
    PullRequestCommentState,
    PullRequestCommentDeliveryEvent
)
from app.models.recommendation import RecommendationRun
from app.models.github_installation import GitHubInstallation
from app.services.pr_comment_service import PRCommentService, classify_github_error
from app.services.github_api_client import (
    GitHubRateLimitExceededError,
    GitHubServiceUnavailableError,
    GitHubAuthPermissionError,
    GitHubNotFoundError,
    GitHubValidationError
)

def cleanup_database():
    """Safely clean up database records."""
    db = SessionLocal()
    try:
        db.query(PullRequestCommentDeliveryEvent).delete()
        db.query(PullRequestCommentState).delete()
        db.query(RecommendationRun).delete()
        db.query(PullRequest).delete()
        db.query(GitHubInstallation).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error cleaning database: {e}")
    finally:
        db.close()

def run_tests():
    print("==================================================")
    print("STARTING ASYNC COMMENT DELIVERY INTEGRATION TESTS...")
    print("==================================================")
    
    db = SessionLocal()
    
    # 1. Setup multi-tenant core models
    org = Organization(name="Async Ops", slug="async-ops")
    db.add(org)
    db.commit()
    db.refresh(org)
    
    installation_id = 998811
    installation = GitHubInstallation(
        organization_id=org.id,
        github_installation_id=installation_id,
        account_login="async-ops",
        status="ACTIVE",
        evidence_health_status="HEALTHY"
    )
    db.add(installation)
    
    repo = Repository(
        organization_id=org.id,
        github_repo_id=90999,
        name="async-service",
        full_name="async-ops/async-service",
        default_branch="main",
        is_active=True
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    
    pr = PullRequest(
        repository_id=repo.id,
        github_pr_id=883377,
        number=101,
        title="Async Delivery PR",
        author="async-dev",
        source_branch="feat-async",
        target_branch="main",
        state="open",
        head_commit_sha="headsha_async",
        github_created_at=datetime.datetime.utcnow(),
        github_updated_at=datetime.datetime.utcnow()
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    
    run = RecommendationRun(
        repository_id=repo.id,
        pull_request_id=pr.id,
        pr_id="headsha_async",
        triggered_by="manual",
        evidence_quality="HIGH",
        engine_version="v1.2.0",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        fallback_policy_version="policy-v1",
        dependency_expansion_strategy_version="expansion-v1",
        recommendation_reasoning_summary="Async run verified.",
        evidence_health_status="HEALTHY",
        recommendation_readiness_state="READY",
        evidence_fingerprint="async_fingerprint_1",
        recommendation_mode="NORMAL",
        skipped_count=10,
        estimated_runtime_seconds=5.0,
        created_at=datetime.datetime.utcnow()
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    
    state = PullRequestCommentState(
        repository_id=repo.id,
        pull_request_id=pr.id,
        latest_recommendation_run_id=run.id,
        comment_status="PENDING",
        delivery_attempt_count=0
    )
    db.add(state)
    db.commit()
    db.refresh(state)
    
    print("Database seeded successfully.")
    
    service = PRCommentService(db)

    # ----------------------------------------------------
    # Verification A: Error Classification
    # ----------------------------------------------------
    print("\n--- Testing Exception Classification ---")
    assert classify_github_error(GitHubRateLimitExceededError("Rate Limit")) is True
    assert classify_github_error(GitHubServiceUnavailableError("503")) is True
    assert classify_github_error(TimeoutError("Connection timed out")) is True
    assert classify_github_error(GitHubAuthPermissionError("Invalid key")) is False
    assert classify_github_error(GitHubNotFoundError("PR deleted")) is False
    assert classify_github_error(GitHubValidationError("Malformed JSON")) is False
    print("[OK] Error classification rules successfully validated.")

    # ----------------------------------------------------
    # Verification B: Retryable Error on Attempt 1 Schedules Attempt 2
    # ----------------------------------------------------
    print("\n--- Testing Retryable Error (Attempt 1) ---")
    state.delivery_attempt_count = 0  # Before claim_delivery (will become 1)
    state.comment_status = "PENDING"
    db.commit()
    
    with patch("app.services.github_app.get_rq_queue") as mock_rq, \
         patch("app.services.github_api_client.GitHubApiClient.list_pr_comments", side_effect=GitHubRateLimitExceededError("Too Many Requests")):
         
         mock_queue = MagicMock()
         mock_rq.return_value = mock_queue
         
         # Mock credentials to bypass missing key guard
         with patch.object(service.client, "app_id", "mock-app"), \
              patch.object(service.client, "private_key", "mock-key"):
              
              service.deliver_pr_comment_for_run(run.id)
              
              # Verify state is still PENDING (marked to retry)
              db.refresh(state)
              assert state.comment_status == "PENDING"
              assert "Retryable Failure" in state.last_delivery_error
              assert state.delivery_attempt_count == 1
              
              # Verify next attempt was enqueued with 2 seconds backoff (2 ** 1 = 2 seconds)
              mock_queue.enqueue_in.assert_called_once()
              args, kwargs = mock_queue.enqueue_in.call_args
              delay = args[0]
              assert delay.total_seconds() == 2.0
              print(f"[OK] Scheduled async retry attempt 2 with {delay.total_seconds()}s backoff successfully.")
              
              # Verify lineage event logged
              event = db.query(PullRequestCommentDeliveryEvent).filter(
                  PullRequestCommentDeliveryEvent.delivery_status == "FAILED_RETRYING"
              ).first()
              assert event is not None
              assert event.failure_reason == "Too Many Requests"
              print("[OK] FAILED_RETRYING lineage event successfully recorded.")

    # ----------------------------------------------------
    # Verification C: Non-Retryable Error immediately fails
    # ----------------------------------------------------
    print("\n--- Testing Non-Retryable Error (Attempt 1) ---")
    # Clean old event
    db.query(PullRequestCommentDeliveryEvent).delete()
    state.delivery_attempt_count = 0
    state.comment_status = "PENDING"
    db.commit()
    
    with patch("app.services.github_app.get_rq_queue") as mock_rq, \
         patch("app.services.github_api_client.GitHubApiClient.list_pr_comments", side_effect=GitHubNotFoundError("Pull Request Deleted")):
         
         mock_queue = MagicMock()
         mock_rq.return_value = mock_queue
         
         with patch.object(service.client, "app_id", "mock-app"), \
              patch.object(service.client, "private_key", "mock-key"):
              
              service.deliver_pr_comment_for_run(run.id)
              
              # Verify state is FAILED
              db.refresh(state)
              assert state.comment_status == "FAILED"
              assert "Pull Request Deleted" in state.last_delivery_error
              
              # Verify no retries enqueued
              mock_queue.enqueue_in.assert_not_called()
              print("[OK] Non-retryable error aborted immediately without enqueuing any retry.")
              
              # Verify lineage event logged
              event = db.query(PullRequestCommentDeliveryEvent).filter(
                  PullRequestCommentDeliveryEvent.delivery_status == "FAILED"
              ).first()
              assert event is not None
              assert "max_retries_exceeded" in event.request_payload
              assert event.request_payload["max_retries_exceeded"] is False
              print("[OK] Non-retryable failure lineage event recorded.")

    # ----------------------------------------------------
    # Verification D: Max 5 Retries Enforced
    # ----------------------------------------------------
    print("\n--- Testing Max 5 Retries Enforced ---")
    db.query(PullRequestCommentDeliveryEvent).delete()
    state.delivery_attempt_count = 4  # Claim will increment to 5
    state.comment_status = "PENDING"
    db.commit()
    
    with patch("app.services.github_app.get_rq_queue") as mock_rq, \
         patch("app.services.github_api_client.GitHubApiClient.list_pr_comments", side_effect=GitHubRateLimitExceededError("Rate Limit")):
         
         mock_queue = MagicMock()
         mock_rq.return_value = mock_queue
         
         with patch.object(service.client, "app_id", "mock-app"), \
              patch.object(service.client, "private_key", "mock-key"):
              
              service.deliver_pr_comment_for_run(run.id)
              
              # Verify state is FAILED because attempt 5 failed
              db.refresh(state)
              assert state.comment_status == "FAILED"
              assert "Rate Limit" in state.last_delivery_error
              
              # Verify no retries enqueued
              mock_queue.enqueue_in.assert_not_called()
              print("[OK] Max retries cap successfully enforced; did not schedule 6th attempt.")
              
              # Verify lineage event logged
              event = db.query(PullRequestCommentDeliveryEvent).filter(
                  PullRequestCommentDeliveryEvent.delivery_status == "FAILED"
              ).first()
              assert event is not None
              assert event.request_payload["max_retries_exceeded"] is True
              print("[OK] Final failure event with max_retries_exceeded=True successfully recorded.")

    db.close()
    print("\n==================================================")
    print("ALL ASYNC COMMENT DELIVERY TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_tests()
    finally:
        cleanup_database()
