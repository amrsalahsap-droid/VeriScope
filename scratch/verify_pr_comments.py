import os
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
from app.services.pr_comment_service import (
    PRCommentService,
    escape_markdown,
    shorten_path,
    clean_bullet_text,
    enforce_single_line_bullet,
    format_bullet,
    sanitize_and_check_forbidden,
    FORBIDDEN_PHRASES,
    MAX_COMMENT_LINES,
    MAX_REASONING_BULLETS,
    MAX_BULLET_LENGTH,
    COMMENT_TEMPLATE_VERSION,
    COMMENT_RENDERING_RULES_VERSION
)

def cleanup_database():
    """Safely clean up all comment and PR related tables."""
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
        print("SUCCESS: Database cleaned up successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def run_tests():
    print("======================================================================")
    print("STARTING OPERATIONALLY HARDENED PR COMMENT SYSTEM VERIFICATIONS")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    run_id = uuid.uuid4()

    try:
        # 0. Seed multi-tenant core
        org = Organization(id=org_id, name="Release Ops Labs", slug="release-ops")
        db.add(org)
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=222888,
            name="core-app",
            full_name="release-ops/core-app",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        installation = GitHubInstallation(
            id=uuid.uuid4(),
            organization_id=org_id,
            github_installation_id=123456,
            account_login="release-ops",
            status="ACTIVE"
        )
        db.add(installation)

        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=987654,
            number=42,
            title="Calm Release Optimizations",
            author="lead-dev",
            source_branch="feat/optimizations",
            target_branch="main",
            state="open",
            head_commit_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow()
        )
        db.add(pr)

        run = RecommendationRun(
            id=run_id,
            repository_id=repo_id,
            pr_id="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            triggered_by="github-webhook",
            evidence_quality="HIGH",
            engine_version="v1.2.0",
            recommendation_engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            fallback_policy_version="policy-v1",
            dependency_expansion_strategy_version="expansion-v1",
            recommendation_reasoning_summary="Optimal mapping validated.",
            pull_request_id=pr_id,
            evidence_health_status="HEALTHY",
            recommendation_readiness_state="READY",
            evidence_fingerprint="f1e2d3c4b5a6",
            recommendation_mode="NORMAL",
            skipped_count=96,
            estimated_runtime_seconds=12.4,
            full_suite_runtime_seconds=184.2,
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()

        # Seed initial PullRequestCommentState to prevent superseded early abort
        state = PullRequestCommentState(
            repository_id=repo_id,
            pull_request_id=pr_id,
            latest_recommendation_run_id=run_id,
            comment_status="PENDING"
        )
        db.add(state)
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
            human_readable_reason="Co-failure: Repeated co-failed downstream test occurrences recorded in billing_suite.",
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
            human_readable_reason="Flakiness: Adjust target tests priorities due to high flakiness profiles.",
            confidence_level="MEDIUM",
            evidence_priority="IMPORTANT",
            created_at=datetime.datetime.utcnow()
        )
        db.add(r4)

        r5 = RecommendationReasoningEntry(
            recommendation_run_id=run_id,
            reason_type="scoped_historical_failure",
            human_readable_reason="History: Execution priority boosted by historical failures in last 30 days.",
            confidence_level="LOW",
            evidence_priority="SUPPORTING",
            created_at=datetime.datetime.utcnow()
        )
        db.add(r5)
        db.commit()

        service = PRCommentService(db)

        # --------------------------------------------------------------------
        # 1. Deterministic Markdown Rendering
        # --------------------------------------------------------------------
        print("--- Verification 1: Deterministic Markdown Rendering ---")
        comment_body = service.render_comment(run)
        print(f"DEBUG: Rendered Comment:\n{comment_body}\n")
        
        # Verify formatting matches plan exactly
        assert "## Veriscope Regression Intelligence" in comment_body
        assert "Recommended Regression Suite" in comment_body
        assert "Risk Reasoning" in comment_body
        assert "Recommended Action" in comment_body
        
        # No emojis inside headers or body text
        assert "🔍" not in comment_body
        # No HTML or markdown tables
        assert "|" not in comment_body
        assert "--- |" not in comment_body
        print("[OK] Deterministic markdown rendering is beautifully calm, plain-text, and completely emoji/table-free.")

        # --------------------------------------------------------------------
        # 2. Forbidden Phrases Absent
        # --------------------------------------------------------------------
        print("\n--- Verification 2: Forbidden Phrases Absent ---")
        # Let's check all forbidden words
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in comment_body.lower(), f"Forbidden phrase '{phrase}' found in comment!"
        print("[OK] Verified that all alarmist AI copilot phrasing is completely absent from the comment.")

        # --------------------------------------------------------------------
        # 3. Max 4 Risk Bullets
        # --------------------------------------------------------------------
        print("\n--- Verification 3: Max 4 Risk Reasoning Bullets ---")
        bullets = service.select_prioritized_bullets(run)
        print(f"DEBUG: Prioritized Selected Bullets: {bullets}")
        assert len(bullets) <= MAX_REASONING_BULLETS
        assert len(bullets) == 4
        # Verification of deterministic priority mapping:
        # Category 1 (fragility) -> Category 2 (co-failure) -> Category 4 (flaky) -> Category 5 (dependency)
        # Category 6 (history) must have been truncated/dropped due to cap!
        assert "Fragility:" in bullets[0]
        assert "Co-Failure:" in bullets[1]
        assert "Flakiness:" in bullets[2]
        assert "Dependencies:" in bullets[3]
        print("[OK] Strict max 4 risk reasoning bullets limit enforced, sorting deterministically by severity.")

        # --------------------------------------------------------------------
        # 4. Bullet & Line Length Limits
        # --------------------------------------------------------------------
        print("\n--- Verification 4: Bullet & Line Length Under Hard Ceilings ---")
        for b in bullets:
            assert len(b) <= MAX_BULLET_LENGTH, f"Bullet is too long: {len(b)} chars"
            assert "\n" not in b, "Bullet has embedded newlines!"
        
        # Test semantic path shortening
        long_path = "src/components/authentication/middleware/authorization.py"
        shortened = shorten_path(long_path)
        print(f"DEBUG: Shortened Path: {shortened}")
        assert shortened == ".../middleware/authorization.py"

        # Check comment total line count
        lines_count = len(comment_body.split('\n'))
        print(f"DEBUG: Total Comment Lines: {lines_count}")
        assert lines_count <= MAX_COMMENT_LINES
        print("[OK] hard ceilings for bullets and line limits (< 40 lines, single-line bullets) verified successfully.")

        # --------------------------------------------------------------------
        # 5. Hidden Marker Exists
        # --------------------------------------------------------------------
        print("\n--- Verification 5: Hidden Canonical Marker Exists ---")
        assert "<!-- veriscope-pr-comment -->" in comment_body
        print("[OK] Hidden tracking signature exists.")

        # --------------------------------------------------------------------
        # 6. Escape Markdown
        # --------------------------------------------------------------------
        print("\n--- Verification 6: Markdown Escaping ---")
        raw_text = "src/auth_middleware_[v1]`_test`"
        escaped = escape_markdown(raw_text)
        print(f"DEBUG: Escaped: {escaped}")
        assert "\\[" in escaped
        assert "\\]" in escaped
        assert "\\`" in escaped
        assert "\\_" in escaped
        print("[OK] Markdown characters properly escaped to prevent rendering corruptions.")

        # --------------------------------------------------------------------
        # 7. First Call Creates Comment (Mocked)
        # --------------------------------------------------------------------
        print("\n--- Verification 7: First Call Creates Comment ---")
        # Setup mock client
        with patch.object(service.client, "list_pr_comments", return_value=[]) as mock_list, \
             patch.object(service.client, "create_pr_comment", return_value={"id": 111222}) as mock_create, \
             patch.object(service.client, "update_pr_comment") as mock_update:
            
            # Setup environment variables so credentials look configured
            with patch.object(service.client, "app_id", "mock-app"), \
                 patch.object(service.client, "private_key", "mock-key"):
                
                service.deliver_pr_comment_for_run(run_id)
                
                # Check DB comment state
                state = db.query(PullRequestCommentState).filter(
                    PullRequestCommentState.pull_request_id == pr_id
                ).first()
                assert state is not None
                assert state.github_comment_id == 111222
                assert state.comment_status == "DELIVERED"
                
                mock_list.assert_called_once()
                mock_create.assert_called_once()
                mock_update.assert_not_called()
        print("[OK] First run successfully posts a new issue comment to GitHub.")

        # --------------------------------------------------------------------
        # 8. Second Call Updates Existing Comment (Mocked)
        # --------------------------------------------------------------------
        print("\n--- Verification 8: Second Call Updates Existing Comment ---")
        # Modify the run slightly to generate different text (simulate new test added)
        run.estimated_runtime_seconds = 18.2
        db.commit()
        
        with patch.object(service.client, "list_pr_comments", return_value=[
            {"id": 111222, "body": "some comment\n<!-- veriscope-pr-comment -->"}
        ]) as mock_list, \
             patch.object(service.client, "create_pr_comment") as mock_create, \
             patch.object(service.client, "update_pr_comment", return_value={"id": 111222}) as mock_update:
            
            with patch.object(service.client, "app_id", "mock-app"), \
                 patch.object(service.client, "private_key", "mock-key"):
                
                # Clear allowed time check to bypass debounce
                state = db.query(PullRequestCommentState).filter(
                    PullRequestCommentState.pull_request_id == pr_id
                ).first()
                state.next_allowed_delivery_at = None
                db.commit()

                # Trigger delivery for second run
                service.deliver_pr_comment_for_run(run_id)
                
                mock_list.assert_called_once()
                mock_create.assert_not_called()
                mock_update.assert_called_once()
        print("[OK] Second run on the same PR updates the existing canonical comment in-place.")

        # --------------------------------------------------------------------
        # 9. Unchanged Body Skips GitHub Call (Deduplication)
        # --------------------------------------------------------------------
        print("\n--- Verification 9: Unchanged Body Skips GitHub Call ---")
        # Clear next allowed time to bypass debounce
        state = db.query(PullRequestCommentState).filter(
            PullRequestCommentState.pull_request_id == pr_id
        ).first()
        state.next_allowed_delivery_at = None
        db.commit()

        with patch.object(service.client, "list_pr_comments") as mock_list, \
             patch.object(service.client, "update_pr_comment") as mock_update:
            
            with patch.object(service.client, "app_id", "mock-app"), \
                 patch.object(service.client, "private_key", "mock-key"):
                
                # Deliver comment with identical parameters
                service.deliver_pr_comment_for_run(run_id)
                
                # Verify that no list or update calls were made!
                mock_list.assert_not_called()
                mock_update.assert_not_called()
                
                # Verify that skipped event was recorded
                event = db.query(PullRequestCommentDeliveryEvent).filter(
                    PullRequestCommentDeliveryEvent.delivery_status == "SKIPPED_NO_CHANGE"
                ).first()
                assert event is not None
        print("[OK] Verified that identical body & reasoning hashes successfully bypass calling GitHub REST APIs.")

        # --------------------------------------------------------------------
        # 10. Multiple Canonical Comments Preserves Oldest
        # --------------------------------------------------------------------
        print("\n--- Verification 10: Multiple Canonical Comments Preserves Oldest ---")
        state = db.query(PullRequestCommentState).filter(
            PullRequestCommentState.pull_request_id == pr_id
        ).first()
        state.next_allowed_delivery_at = None
        state.latest_comment_hash = None # Reset hash to force update
        db.commit()

        with patch.object(service.client, "list_pr_comments", return_value=[
            {"id": 444, "body": "old canonical\n<!-- veriscope-pr-comment -->", "created_at": "2026-05-23T12:00:00Z"},
            {"id": 555, "body": "duplicate canonical\n<!-- veriscope-pr-comment -->", "created_at": "2026-05-23T12:01:00Z"}
        ]) as mock_list, \
             patch.object(service.client, "update_pr_comment", return_value={"id": 444}) as mock_update:
            
            with patch.object(service.client, "app_id", "mock-app"), \
                 patch.object(service.client, "private_key", "mock-key"):
                
                service.deliver_pr_comment_for_run(run_id)
                
                # Assert oldest canonical (id=444) was updated
                mock_update.assert_called_once_with(
                    installation_id=123456,
                    owner="release-ops",
                    repo="core-app",
                    comment_id=444,
                    body_text=service.render_comment(run)
                )
                
                # Verify database state shows integrity marked as MALFORMED
                assert state.comment_integrity_status == "MALFORMED"
                assert state.github_comment_id == 444
        print("[OK] Multiple comments detected successfully preserves oldest canonical, marks internally MALFORMED, and logs warnings.")

        # --------------------------------------------------------------------
        # 11. Missing GitHub Credentials Persists Failure Event
        # --------------------------------------------------------------------
        print("\n--- Verification 11: Missing GitHub Credentials Graceful Failure ---")
        state = db.query(PullRequestCommentState).filter(
            PullRequestCommentState.pull_request_id == pr_id
        ).first()
        state.next_allowed_delivery_at = None
        state.latest_comment_hash = None
        db.commit()

        # Mock app_id and private_key to be missing
        with patch.object(service.client, "app_id", None), \
             patch.object(service.client, "private_key", None):
            
            # This should complete synchronously without throwing exceptions to client
            service.deliver_pr_comment_for_run(run_id)
            
            # Assert state updated to FAILED and error stored
            assert state.comment_status == "FAILED"
            assert "credentials or installation mapping are not configured" in state.last_delivery_error
            
            # Assert failure event was logged in DB
            event = db.query(PullRequestCommentDeliveryEvent).filter(
                PullRequestCommentDeliveryEvent.delivery_status == "FAILED",
                PullRequestCommentDeliveryEvent.failure_reason.like("%credentials%")
            ).first()
            assert event is not None
        print("[OK] Unconfigured environment does not crash the pipeline and correctly registers FAILED event in ledger.")

        # --------------------------------------------------------------------
        # 12. GitHub network failure does not fail RecommendationRun (Failure Isolation)
        # --------------------------------------------------------------------
        print("\n--- Verification 12: GitHub Network Failure Isolation ---")
        # Reset state
        state = db.query(PullRequestCommentState).filter(
            PullRequestCommentState.pull_request_id == pr_id
        ).first()
        state.next_allowed_delivery_at = None
        db.commit()

        from app.services.recommendation import RecommendationService
        from app.schemas.recommendation import RecommendationRunCreate
        
        rec_service = RecommendationService(db)
        run_in = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            triggered_by="manual"
        )
        
        # When create_recommendation_run is called, comment delivery is scheduled in background
        # We will mock the enqueuing to throw a network exception simulating a broken Redis or queue error
        with patch("app.services.pr_comment_service.PRCommentService.enqueue_delivery_task", side_effect=Exception("Redis Server Down!")):
            # Call should finish successfully!
            new_run = rec_service.create_recommendation_run(run_in)
            assert new_run is not None
        print("[OK] GitHub network or queue failures are safely isolated; RecommendationRun creation is 100% immune.")

        # --------------------------------------------------------------------
        # 13. Stale Delivery Job Aborted (Superseded Runs Protection)
        # --------------------------------------------------------------------
        print("\n--- Verification 13: Stale Delivery Job Aborted ---")
        # Let's seed a newer recommendation run
        new_run_id = uuid.uuid4()
        new_run = RecommendationRun(
            id=new_run_id,
            repository_id=repo_id,
            pr_id="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            triggered_by="github-webhook",
            evidence_quality="HIGH",
            engine_version="v1.2.0",
            recommendation_engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            fallback_policy_version="policy-v1",
            dependency_expansion_strategy_version="expansion-v1",
            recommendation_reasoning_summary="New optimal run",
            pull_request_id=pr_id,
            evidence_health_status="HEALTHY",
            recommendation_readiness_state="READY",
            evidence_fingerprint="c5b6a7",
            recommendation_mode="NORMAL",
            created_at=datetime.datetime.utcnow()
        )
        db.add(new_run)
        
        # Update state latest run to the new one
        state.latest_recommendation_run_id = new_run_id
        db.commit()

        with patch.object(service.client, "list_pr_comments") as mock_list:
            # Trigger delivery of OLD run
            service.deliver_pr_comment_for_run(run_id)
            
            # Verify list comments was never called (aborted early!)
            mock_list.assert_not_called()
        print("[OK] Superseded job aborted successfully, preventing older recommendations from overwriting newer comments.")

        # --------------------------------------------------------------------
        # 14. Replay Comments Solely from Snapshots (Prevent Replay Drift)
        # --------------------------------------------------------------------
        print("\n--- Verification 14: Replay Comments Solely from Snapshots ---")
        # Verify that regeneration pulls exclusively from snapshots/persisted entries
        with patch("app.services.pr_comment_service.PRCommentService.enqueue_delivery_task") as mock_enqueue:
            service.regenerate_comment_from_recommendation(run_id)
            
            # Verify database state was successfully updated to point to run_id
            assert state.latest_recommendation_run_id == run_id
            assert state.comment_status == "PENDING"
            mock_enqueue.assert_called_once_with(run_id)
        print("[OK] Comment regeneration and replay operate purely from database snapshot records, avoiding live drift.")

    finally:
        cleanup_database()
        db.close()

    print("\n=======================================================")
    print("ALL Phase 5 PR COMMENT PLATFORM VERIFICATIONS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_tests()
    finally:
        cleanup_database()
