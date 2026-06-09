import sys
import uuid
import datetime
import hashlib
import asyncio
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
from app.models.webhook_event import WebhookEvent
from app.models.recommendation import RecommendationRun, RecommendationReasoningEntry, RecommendationTest
from app.models.github_installation import GitHubInstallation
from app.services.pr_comment_service import PRCommentService, classify_github_error
from app.services.github_api_client import (
    GitHubRateLimitExceededError,
    GitHubServiceUnavailableError,
    GitHubAuthPermissionError,
    GitHubNotFoundError,
    GitHubValidationError
)
from app.services.pr_comment_update_strategy import PRCommentUpdateStrategy

def cleanup_database():
    """Safely clean up database records."""
    db = SessionLocal()
    try:
        db.query(WebhookEvent).delete()
        db.query(PullRequestCommentDeliveryEvent).delete()
        db.query(PullRequestCommentState).delete()
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationTest).delete()
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

def run_hardening_tests():
    print("======================================================================")
    print("STARTING PRODUCTION HARDENING PR COMMENT PIPELINE VERIFICATIONS")
    print("======================================================================\n")
    
    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    run_id = uuid.uuid4()
    
    try:
        # ─────────────────────────────────────────────────────────────
        # Seed Base Data
        # ─────────────────────────────────────────────────────────────
        org = Organization(id=org_id, name="Hardening Verify", slug="hardening-verify")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=999888,
            name="hardened-service",
            full_name="hardening-verify/hardened-service",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        installation = GitHubInstallation(
            organization_id=org_id,
            github_installation_id=121212,
            account_login="hardening-verify",
            status="ACTIVE"
        )
        db.add(installation)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=777666,
            number=42,
            title="Hardened Delivery Verification",
            author="lead-ops",
            source_branch="feat-harden",
            target_branch="main",
            state="open",
            head_commit_sha="headsha_harden",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow()
        )
        db.add(pr)
        
        run = RecommendationRun(
            id=run_id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            pr_id="headsha_harden",
            triggered_by="manual",
            evidence_quality="HIGH",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            fallback_policy_version="policy-v1",
            dependency_expansion_strategy_version="expansion-v1",
            recommendation_reasoning_summary="Hardening verification verified.",
            evidence_health_status="HEALTHY",
            recommendation_readiness_state="READY",
            evidence_fingerprint="verify_fingerprint_harden",
            recommendation_mode="NORMAL",
            skipped_count=90,
            estimated_runtime_seconds=1080.0,
            full_suite_runtime_seconds=8040.0,
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        
        state = PullRequestCommentState(
            repository_id=repo_id,
            pull_request_id=pr_id,
            latest_recommendation_run_id=run.id,
            comment_status="PENDING"
        )
        db.add(state)
        db.commit()

        service = PRCommentService(db)

        # ─────────────────────────────────────────────────────────────
        # 1. Rate Limit Handling: Retry-After Override
        # ─────────────────────────────────────────────────────────────
        print("--- Verification 1: Rate Limit Handling with Retry-After ---")
        
        # Test Case A: Explicit Exception Attribute
        rate_limit_err = GitHubRateLimitExceededError("Too Many Requests", retry_after=45)
        assert rate_limit_err.retry_after == 45
        
        # Test Case B: Delayed enqueueing captures retry_after correctly (with safety buffer)
        state.comment_status = "PENDING"
        state.delivery_attempt_count = 1
        db.commit()
        
        with patch("app.services.github_app.get_rq_queue") as mock_rq, \
             patch.object(service.client, "app_id", "mock-app"), \
             patch.object(service.client, "private_key", "mock-key"), \
             patch.object(service.client, "list_pr_comments", side_effect=rate_limit_err):
             
             mock_queue = MagicMock()
             mock_rq.return_value = mock_queue
             
             service.deliver_pr_comment_for_run(run.id)
             
             db.refresh(state)
             assert state.comment_status == "PENDING"
             
             mock_queue.enqueue_in.assert_called_once()
             args, kwargs = mock_queue.enqueue_in.call_args
             delay = args[0]
             # Assert 45 + 2 safety buffer = 47 seconds
             assert delay.total_seconds() == 47.0, f"Expected 47s, got {delay.total_seconds()}"
             print("[OK] Parsed Retry-After: 45 successfully and scheduled delayed task with 47s delay.")

        # Test Case C: Parse Retry-After from string message fallback
        string_rate_limit_err = Exception("Rate limit exhausted. Retry-after: 60")
        state.delivery_attempt_count = 1
        db.commit()
        
        with patch("app.services.github_app.get_rq_queue") as mock_rq, \
             patch.object(service.client, "app_id", "mock-app"), \
             patch.object(service.client, "private_key", "mock-key"), \
             patch.object(service.client, "list_pr_comments", side_effect=string_rate_limit_err):
             
             mock_queue = MagicMock()
             mock_rq.return_value = mock_queue
             
             service.deliver_pr_comment_for_run(run.id)
             
             mock_queue.enqueue_in.assert_called_once()
             args, kwargs = mock_queue.enqueue_in.call_args
             delay = args[0]
             # Assert 60 + 2 safety buffer = 62 seconds
             assert delay.total_seconds() == 62.0, f"Expected 62s, got {delay.total_seconds()}"
             print("[OK] Fallback string parser extracted Retry-after: 60 and scheduled task with 62s delay.")

        # ─────────────────────────────────────────────────────────────
        # 2. Webhook Storm Idempotency
        # ─────────────────────────────────────────────────────────────
        print("\n--- Verification 2: Webhook Storm Idempotency via unique savepoint rollback ---")
        from app.routers.github import webhook_handler
        from fastapi import Request
        
        # We simulate concurrent database commits raising unique constraint exceptions
        from unittest.mock import AsyncMock
        request_mock = MagicMock(spec=Request)
        request_mock.body = AsyncMock(return_value=b"mock-body")
        request_mock.json = AsyncMock(return_value={"action": "opened", "testing_mode": True, "installation": {"id": 121212}, "repository": {"id": 999888}, "pull_request": {"id": 777666, "number": 42, "state": "open", "head": {"sha": "headsha_harden"}}})
        request_mock.query_params = {}

        # First webhook handler call runs normally and succeeds
        with patch("app.routers.github.verify_signature", return_value=True), \
             patch("app.routers.github.settings") as settings_mock, \
             patch("app.routers.github.GitHubAppService.enqueue_pull_request_sync", return_value=uuid.uuid4()):
             
             settings_mock.GITHUB_WEBHOOK_SECRET = "secret"
             settings_mock.GITHUB_WEBHOOK_MAX_AGE_SECONDS = 600
             
             # Call first time -> inserts WebhookEvent successfully
             res1 = asyncio.run(webhook_handler(request_mock, x_github_delivery="storm_delivery_101", x_github_event="pull_request", x_hub_signature_256="sha256=mock", db=db))
             assert res1["status"] in ("processed", "ignored")
             
             # Call second time with same x_github_delivery -> raises IntegrityError and catches it gracefully, returning duplicate warning
             res2 = asyncio.run(webhook_handler(request_mock, x_github_delivery="storm_delivery_101", x_github_event="pull_request", x_hub_signature_256="sha256=mock", db=db))
             assert res2["status"] == "ignored"
             assert "Duplicate webhook" in res2["detail"]
             print("[OK] Concurrent webhook storms sharing identical delivery IDs safely ignored (200 OK, no 500 error).")

        # ─────────────────────────────────────────────────────────────
        # 3. Dead-Letter Queue (DLQ) transitions
        # ─────────────────────────────────────────────────────────────
        print("\n--- Verification 3: Dead-Letter Queue (DLQ) Transitions ---")
        
        # Reset state retries to 5 (exhausted)
        state.comment_status = "PENDING"
        state.delivery_attempt_count = 5
        db.commit()
        
        with patch.object(service.client, "app_id", "mock-app"), \
             patch.object(service.client, "private_key", "mock-key"), \
             patch.object(service.client, "list_pr_comments", side_effect=GitHubRateLimitExceededError("Rate Limit")):
             
             service.deliver_pr_comment_for_run(run.id)
             
             db.refresh(state)
             # Should be transitioned to DEAD_LETTER
             assert state.comment_status == "DEAD_LETTER"
             assert "DEAD_LETTER" in state.comment_status
             print("[OK] Exhausted retries successfully promoted comment state to 'DEAD_LETTER'.")
             
             # Verify list_dead_letter_comments retrieval
             dlq_list = service.list_dead_letter_comments()
             assert len(dlq_list) > 0
             assert dlq_list[0].id == state.id
             print("[OK] list_dead_letter_comments successfully listed the DLQ record.")

        # ─────────────────────────────────────────────────────────────
        # 4. Observability & Delivery Metrics
        # ─────────────────────────────────────────────────────────────
        print("\n--- Verification 4: Observability & Metrics calculations ---")
        
        # Seed several mock events
        db.query(PullRequestCommentDeliveryEvent).delete()
        db.commit()
        
        # Success event
        service._record_event(state.id, run.id, "CREATED", {"latency": 150}, None, 150)
        # Skipped event
        service._record_event(state.id, run.id, "SKIPPED_NO_CHANGE", {}, None, 50)
        # Failure retry event
        service._record_event(state.id, run.id, "FAILED_RETRYING", {}, None, 80)
        # Permanently failed event
        service._record_event(state.id, run.id, "DEAD_LETTER", {}, None, 120)
        db.commit()
        
        metrics = service.get_delivery_metrics()
        assert metrics["total_attempts"] == 4
        assert metrics["retry_counts"] == 1
        assert metrics["skipped_no_change_counts"] == 1
        assert metrics["latency_stats"]["min"] == 50
        assert metrics["latency_stats"]["max"] == 150
        assert metrics["latency_stats"]["avg"] == 100.0
        print("[OK] Aggregated metrics are completely accurate (Latencies, Retries, Ratios, Skips).")

        # ─────────────────────────────────────────────────────────────
        # 5. Comment Corruption Self-Healing (Malformed / Duplicates)
        # ─────────────────────────────────────────────────────────────
        print("\n--- Verification 5: Self-Healing of Corrupted & Duplicate comments ---")
        
        # Test Case A: Multiple canonical comments exist on GitHub -> prune duplicates
        state.comment_status = "PENDING"
        state.latest_comment_hash = None
        db.commit()
        
        with patch.object(service.client, "app_id", "mock-app"), \
             patch.object(service.client, "private_key", "mock-key"), \
             patch.object(service.client, "list_pr_comments", return_value=[
                 {"id": 3001, "body": "old canonical\n<!-- veriscope-pr-comment -->"},
                 {"id": 3002, "body": "duplicate canonical\n<!-- veriscope-pr-comment -->"},
                 {"id": 3003, "body": "triplicate canonical\n<!-- veriscope-pr-comment -->"}
             ]) as mock_list, \
             patch.object(service.client, "delete_pr_comment") as mock_delete, \
             patch.object(service.client, "update_pr_comment", return_value={"id": 3001}) as mock_update:
             
             service.deliver_pr_comment_for_run(run.id)
             
             # Assert all but the oldest (3001) were deleted
             assert mock_delete.call_count == 2
             mock_delete.assert_any_call(installation_id=121212, owner="hardening-verify", repo="hardened-service", comment_id=3002)
             mock_delete.assert_any_call(installation_id=121212, owner="hardening-verify", repo="hardened-service", comment_id=3003)
             
             # Assert the oldest (3001) was patched/updated in-place
             mock_update.assert_called_once()
             print("[OK] Multiple duplicates identified on GitHub: extra canonical comments deleted, oldest kept and updated.")

        # Test Case B: Stored comment ID not found on GitHub (Corrupted State Reference) -> Recreate cleanly
        state.github_comment_id = 999999
        state.comment_status = "PENDING"
        state.latest_comment_hash = None
        state.next_allowed_delivery_at = None
        db.commit()
        
        # When querying GitHub, no comments exist. Our stored ID (999999) is corrupted/missing.
        with patch.object(service.client, "app_id", "mock-app"), \
             patch.object(service.client, "private_key", "mock-key"), \
             patch.object(service.client, "list_pr_comments", return_value=[]) as mock_list, \
             patch.object(service.client, "create_pr_comment", return_value={"id": 4001}) as mock_create:
             
             service.deliver_pr_comment_for_run(run.id)
             
             # Assert a brand new comment was created
             mock_create.assert_called_once()
             db.refresh(state)
             assert state.github_comment_id == 4001
             print("[OK] Missing/corrupted comment ID on GitHub safely handled: brand new comment recreated safely.")
             
             # Assert recreation lineage event exists
             recreate_event = db.query(PullRequestCommentDeliveryEvent).filter(
                 PullRequestCommentDeliveryEvent.delivery_status == "RECREATED"
             ).first()
             assert recreate_event is not None
             print("[OK] Recreated lineage successfully preserved in database audit log.")

        # ─────────────────────────────────────────────────────────────
        # 6. Failure Recovery Tooling (Replay / Repair / Regenerate)
        # ─────────────────────────────────────────────────────────────
        print("\n--- Verification 6: Manual Recovery flows (Replay, Repair, Regenerate) ---")
        
        # Test Case A: Replay Comment Delivery
        with patch.object(service, "enqueue_delivery_task") as mock_enqueue:
             msg = service.replay_comment_delivery(state.id)
             assert "delivery replay queued" in msg.lower()
             db.refresh(state)
             assert state.comment_status == "PENDING"
             assert state.delivery_attempt_count == 0
             mock_enqueue.assert_called_once_with(run.id)
             print("[OK] Manual comment delivery replay correctly resets metrics and enqueues task.")

        # Test Case B: Regenerate Comment from snapshot
        with patch.object(service, "enqueue_delivery_task") as mock_enqueue:
             msg = service.regenerate_comment_from_recommendation(run.id)
             assert "comment regeneration queued" in msg.lower()
             db.refresh(state)
             assert state.comment_status == "PENDING"
             assert state.delivery_attempt_count == 0
             mock_enqueue.assert_called_once_with(run.id)
             print("[OK] Manual comment regeneration from snapshot correctly resets metrics and enqueues task.")

        # Test Case C: Repair Stale Comment State (Align ID, prune duplicates, advance status)
        state.comment_status = "DEAD_LETTER"
        state.github_comment_id = None
        db.commit()
        
        with patch.object(service.client, "app_id", "mock-app"), \
             patch.object(service.client, "private_key", "mock-key"), \
             patch.object(service.client, "list_pr_comments", return_value=[
                 {"id": 5001, "body": "old canonical\n<!-- veriscope-pr-comment -->"},
                 {"id": 5002, "body": "duplicate canonical\n<!-- veriscope-pr-comment -->"}
             ]) as mock_list, \
             patch.object(service.client, "delete_pr_comment") as mock_delete:
             
             msg = service.repair_stale_comment_state(pr.id)
             assert "repaired" in msg.lower()
             
             db.refresh(state)
             assert state.github_comment_id == 5001
             assert state.comment_status == "DELIVERED"
             assert state.comment_integrity_status == "VALID"
             
             # Assert duplicate 5002 deleted
             mock_delete.assert_called_once_with(installation_id=121212, owner="hardening-verify", repo="hardened-service", comment_id=5002)
             print("[OK] Manual Repair aligns database ID, deletes duplicate canonicals, and advances status to DELIVERED.")

    finally:
        cleanup_database()
        db.close()

    print("\n======================================================================")
    print("ALL PRODUCTION HARDENING PR COMMENT PIPELINE VERIFICATIONS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_hardening_tests()
    finally:
        cleanup_database()
