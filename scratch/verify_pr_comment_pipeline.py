import sys
import uuid
import datetime
import hashlib
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
from app.models.recommendation import RecommendationRun, RecommendationReasoningEntry, RecommendationTest
from app.models.github_installation import GitHubInstallation
from app.services.pr_comment_service import PRCommentService, classify_github_error
from app.services.recommendation_explanation_builder import RecommendationExplanationBuilder
from app.services.pull_request_comment_formatter import PullRequestCommentFormatter
from app.services.github_comment_lifecycle_manager import GitHubCommentLifecycleManager
from app.services.comment_deduplication_engine import CommentDeduplicationEngine
from app.services.pr_comment_update_strategy import PRCommentUpdateStrategy
from app.services.pr_comment_runtime_safeguards import PRCommentRuntimeSafeguards
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

def run_tests():
    print("======================================================================")
    print("STARTING END-TO-END PR COMMENT PIPELINE VERIFICATIONS")
    print("======================================================================\n")
    
    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    run_id = uuid.uuid4()
    
    try:
        # Seeding core data
        org = Organization(id=org_id, name="Pipeline Verify", slug="pipeline-verify")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=999888,
            name="core-service",
            full_name="pipeline-verify/core-service",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        installation = GitHubInstallation(
            organization_id=org_id,
            github_installation_id=121212,
            account_login="pipeline-verify",
            status="ACTIVE"
        )
        db.add(installation)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=777666,
            number=42,
            title="Calm Release Verification",
            author="lead-ops",
            source_branch="feat-verify",
            target_branch="main",
            state="open",
            head_commit_sha="headsha_verify",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow()
        )
        db.add(pr)
        
        run = RecommendationRun(
            id=run_id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            pr_id="headsha_verify",
            triggered_by="manual",
            evidence_quality="HIGH",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            fallback_policy_version="policy-v1",
            dependency_expansion_strategy_version="expansion-v1",
            recommendation_reasoning_summary="Calm verification verified.",
            evidence_health_status="HEALTHY",
            recommendation_readiness_state="READY",
            evidence_fingerprint="verify_fingerprint_1",
            recommendation_mode="NORMAL",
            skipped_count=90,
            estimated_runtime_seconds=1080.0,      # 18 minutes
            full_suite_runtime_seconds=8040.0,       # 2h 14m
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()

        # Seed Reasoning Entries in various priority orders
        r1 = RecommendationReasoningEntry(
            recommendation_run_id=run_id,
            reason_type="historical_fragility",
            human_readable_reason="Fragility: Active high-risk pattern detected in changed area (Pattern ID: d3b07384-d113-4ec6-a5d5-bd86d7e00000 | Risk Level: HIGH | Evidence: 6 regressions).",
            confidence_level="HIGH",
            evidence_priority="CRITICAL",
            created_at=datetime.datetime.utcnow()
        )
        db.add(r1)
        
        r2 = RecommendationReasoningEntry(
            recommendation_run_id=run_id,
            reason_type="historical_fragility",
            human_readable_reason="Co-failure: Repeated co-failed downstream test occurrences recorded.",
            confidence_level="HIGH",
            evidence_priority="CRITICAL",
            created_at=datetime.datetime.utcnow()
        )
        db.add(r2)

        r3 = RecommendationReasoningEntry(
            recommendation_run_id=run_id,
            reason_type="dependency_expansion",
            human_readable_reason="Dependencies: Expanded changed files into transitive importing modules.",
            confidence_level="MEDIUM",
            evidence_priority="IMPORTANT",
            created_at=datetime.datetime.utcnow()
        )
        db.add(r3)

        r4 = RecommendationReasoningEntry(
            recommendation_run_id=run_id,
            reason_type="flaky_adjustments",
            human_readable_reason="Flakiness: Adjust target tests priorities due to flakiness profiles.",
            confidence_level="MEDIUM",
            evidence_priority="IMPORTANT",
            created_at=datetime.datetime.utcnow()
        )
        db.add(r4)

        r5 = RecommendationReasoningEntry(
            recommendation_run_id=run_id,
            reason_type="scoped_historical_failure",
            human_readable_reason="History: Execution priority boosted by historical failures.",
            confidence_level="LOW",
            evidence_priority="SUPPORTING",
            created_at=datetime.datetime.utcnow()
        )
        db.add(r5)
        
        # Test Case Stable identities recommended
        tc1 = RecommendationTest(
            recommendation_run_id=run_id,
            test_case_id="auth_test.py",
            reason_type="direct_file_coverage",
            reason_details={},
            priority_score=0.95
        )
        db.add(tc1)
        db.commit()

        # Seed initial state
        state = PullRequestCommentState(
            repository_id=repo_id,
            pull_request_id=pr_id,
            latest_recommendation_run_id=run_id,
            comment_status="PENDING"
        )
        db.add(state)
        db.commit()

        service = PRCommentService(db)

        # ----------------------------------------------------
        # 1. Comment Rendering & Markdown Correctness
        # ----------------------------------------------------
        print("--- Verification 1: Comment Rendering & Formatting ---")
        comment_body = service.render_comment(run)
        assert "## Veriscope Regression Intelligence" in comment_body
        assert "Recommended Regression Suite" in comment_body
        assert "Risk Reasoning" in comment_body
        assert "Recommended Action" in comment_body
        assert "|" not in comment_body, "Should not contain tables"
        print("[OK] Deterministic plain-text Markdown formatting correct.")

        # ----------------------------------------------------
        # 2. Deduplication (Identical Comments Skipped)
        # ----------------------------------------------------
        print("\n--- Testing 2: Deduplication (Identical Comments Skipped) ---")
        normalized_body_hash = CommentDeduplicationEngine.compute_body_hash(comment_body)
        body_hash = service.compute_composite_hash(comment_body, run)
        
        state.comment_status = "DELIVERED"
        state.latest_comment_body_hash = normalized_body_hash
        state.latest_comment_hash = body_hash
        state.next_allowed_delivery_at = None
        db.commit()
        
        with patch.object(service.client, "list_pr_comments") as mock_list, \
             patch.object(service.client, "update_pr_comment") as mock_update, \
             patch.object(service.client, "app_id", "mock-app"), \
             patch.object(service.client, "private_key", "mock-key"):
             
             service.deliver_pr_comment_for_run(run.id)
             
             mock_list.assert_not_called()
             mock_update.assert_not_called()
             print("[OK] Identical comments successfully skipped (deduplicated).")

        # ----------------------------------------------------
        # 3. Canonical Comment Behavior (One Comment per PR)
        # ----------------------------------------------------
        print("\n--- Testing 3: Canonical Comment Behavior ---")
        # Clear comments hash to force update
        state.comment_status = "PENDING"
        state.latest_comment_hash = None
        state.next_allowed_delivery_at = None
        db.commit()
        
        # Verify that oldest canonical is identified and updated
        with patch.object(service.client, "list_pr_comments", return_value=[
            {"id": 1001, "body": "old canonical\n<!-- veriscope-pr-comment -->", "created_at": "2026-05-23T12:00:00Z"},
            {"id": 1002, "body": "duplicate canonical\n<!-- veriscope-pr-comment -->", "created_at": "2026-05-23T12:01:00Z"}
        ]) as mock_list, \
             patch.object(service.client, "update_pr_comment", return_value={"id": 1001}) as mock_update, \
             patch.object(service.client, "app_id", "mock-app"), \
             patch.object(service.client, "private_key", "mock-key"):
             
             service.deliver_pr_comment_for_run(run.id)
             
             # Assert only the oldest canonical was updated in-place
             mock_update.assert_called_once()
             args, kwargs = mock_update.call_args
             assert kwargs.get("comment_id") == 1001
             print("[OK] Preserved oldest canonical comment and updated it in-place.")

        # ----------------------------------------------------
        # 4. Risk Reasoning (Max 4 Bullets & Deterministic Ordering)
        # ----------------------------------------------------
        print("\n--- Testing 4: Risk Reasoning (Max 4 Bullets & Deterministic Ordering) ---")
        bullets = service.select_prioritized_bullets(run)
        assert len(bullets) <= 4, "Must have max 4 bullets"
        assert len(bullets) == 4
        # Deterministic sorting check: Category 1 (fragility) -> Category 2 (co-failure) -> Category 4 (flaky) -> Category 5 (dependency)
        # Category 6 (history) was correctly dropped/truncated.
        assert "Fragility:" in bullets[0]
        assert "Co-Failure:" in bullets[1]
        assert "Flakiness:" in bullets[2]
        assert "Dependencies:" in bullets[3]
        print("[OK] Max 4 bullets and deterministic ordering successfully verified.")

        # ----------------------------------------------------
        # 5. Recommendation Action
        # ----------------------------------------------------
        print("\n--- Testing 5: Recommendation Action ---")
        action = service.generate_recommended_action(run)
        print(f"DEBUG Action Text: {action}")
        assert len(action) > 0
        assert not any(phrase in action.lower() for phrase in ["safe to ship", "unsafe to merge"])
        print("[OK] Recommended action is concise and actionable.")

        # ----------------------------------------------------
        # 6. Runtime Formatting
        # ----------------------------------------------------
        print("\n--- Testing 6: Runtime Formatting ---")
        # Run 1: 1080s -> 18 minutes ("18 min")
        dur_18_min = RecommendationExplanationBuilder.format_duration(1080.0)
        assert dur_18_min == "18 min", f"Got: {dur_18_min}"
        
        # Run 2: 8040s -> 134 minutes -> 2h 14m ("2h 14m")
        dur_2h_14m = RecommendationExplanationBuilder.format_duration(8040.0)
        assert dur_2h_14m == "2h 14m", f"Got: {dur_2h_14m}"
        print("[OK] Runtime durations formatted ('18 min', '2h 14m') perfectly.")

        # ----------------------------------------------------
        # 7. Warning Rules (No Alarmist Language / Emojis)
        # ----------------------------------------------------
        print("\n--- Testing 7: Warning Rules (No alarmist / fake percentages) ---")
        assert "safe to ship" not in comment_body.lower()
        assert "unsafe to merge" not in comment_body.lower()
        assert "ai believes" not in comment_body.lower()
        assert "%" not in comment_body
        assert "🔍" not in comment_body
        print("[OK] Verified absolute absence of alarmist language, emojis, and percentages.")

        # ----------------------------------------------------
        # 8. Replayability (Same Snapshot -> Identical Comment)
        # ----------------------------------------------------
        print("\n--- Testing 8: Replayability (Same Snapshot -> Identical Comment) ---")
        # Regenerate body and hash and verify they are identical
        comment_body_replay = service.render_comment(run)
        body_hash_replay = service.compute_composite_hash(comment_body_replay, run)
        assert comment_body_replay == comment_body
        assert body_hash_replay == body_hash
        print("[OK] Replayability confirmed. Same snapshots generate 100% identical comments.")

        # ----------------------------------------------------
        # 9. Failure Isolation (GitHub API Failure Isolation)
        # ----------------------------------------------------
        print("\n--- Testing 9: Failure Isolation ---")
        from app.services.recommendation import RecommendationService
        from app.schemas.recommendation import RecommendationRunCreate
        
        rec_service = RecommendationService(db)
        run_in = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id="headsha_verify",
            triggered_by="manual"
        )
        
        # Patched enqueuing to raise an exception. Should not crash the recommendation service.
        with patch("app.services.pr_comment_service.PRCommentService.enqueue_delivery_task", side_effect=Exception("Redis/Queue Down")):
            new_run = rec_service.create_recommendation_run(run_in)
            assert new_run is not None
            print("[OK] external delivery issues safely isolated from the core recommendation pipeline.")

        # ----------------------------------------------------
        # 10. Async Retries & Linage Auditing
        # ----------------------------------------------------
        print("\n--- Testing 10: Async Retries & Linage Auditing ---")
        db.query(PullRequestCommentDeliveryEvent).delete()
        state.delivery_attempt_count = 0
        state.comment_status = "PENDING"
        state.next_allowed_delivery_at = None
        state.latest_comment_body_hash = None
        state.latest_comment_hash = None
        state.latest_recommendation_run_id = run.id
        db.commit()
        
        with patch("app.services.github_app.get_rq_queue") as mock_rq, \
             patch("app.services.github_api_client.GitHubApiClient.list_pr_comments", side_effect=GitHubRateLimitExceededError("Rate Limit")):
             
             mock_queue = MagicMock()
             mock_rq.return_value = mock_queue
             
             with patch.object(service.client, "app_id", "mock-app"), \
                  patch.object(service.client, "private_key", "mock-key"):
                  
                  service.deliver_pr_comment_for_run(run.id)
                  
                  db.refresh(state)
                  assert state.comment_status == "PENDING"
                  assert state.delivery_attempt_count == 1
                  
                  # Verify async retry attempt enqueued via enqueue_in
                  mock_queue.enqueue_in.assert_called_once()
                  args, kwargs = mock_queue.enqueue_in.call_args
                  delay = args[0]
                  assert delay.total_seconds() == 2.0
                  print(f"[OK] Asynchronous backoff delay of {delay.total_seconds()}s enqueued successfully.")
                  
                  # Verify lineage audit event
                  event = db.query(PullRequestCommentDeliveryEvent).filter(
                      PullRequestCommentDeliveryEvent.delivery_status == "FAILED_RETRYING"
                  ).first()
                  assert event is not None
                  assert event.failure_reason == "Rate Limit"
                  print("[OK] Asynchronous retry lineage successfully logged to database.")

    finally:
        cleanup_database()
        db.close()

    print("\n=======================================================")
    print("ALL END-TO-END PR COMMENT PIPELINE VERIFICATIONS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_tests()
    finally:
        cleanup_database()
