import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.user import Workspace
from app.services.recommendation import RecommendationService
from app.schemas.recommendation import RecommendationRunCreate
from app.models.recommendation import RecommendationRun, RecommendedTest
import uuid

def test_durable_recommendation():
    db = SessionLocal()
    try:
        # 1. Find active repository, pull request, and workspace
        repo = db.query(Repository).filter(Repository.selected_for_analysis == True).first()
        if not repo:
            print("No selected repository found.")
            return

        pr = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).first()
        if not pr:
            print(f"No pull request found for repository {repo.full_name}.")
            return

        workspace = db.query(Workspace).filter(Workspace.id == repo.workspace_id).first()
        if not workspace:
            print(f"No workspace found for repository {repo.full_name}.")
            return

        print(f"--- Verification Run for Repo: {repo.full_name}, PR: #{pr.number} ---")

        # 2. Trigger recommendation run generation
        svc = RecommendationService(db)
        run = svc.create_recommendation_run(
            RecommendationRunCreate(
                repository_id=repo.id,
                pr_id=str(pr.id),
                changed_files=[],
                triggered_by="MANUAL_DRY_RUN"
            )
        )

        print("\nSUCCESS: Recommendation run generated.")
        print(f"Run ID: {run.id}")
        
        # Verify RecommendationRun fields
        print("\n--- Verifying RecommendationRun Fields ---")
        print(f"workspace_id: {run.workspace_id} (Expected: {workspace.id})")
        assert run.workspace_id == workspace.id, "Workspace ID mismatch"
        
        print(f"input_snapshot_hash: {run.input_snapshot_hash}")
        assert run.input_snapshot_hash is not None, "input_snapshot_hash is missing"
        assert len(run.input_snapshot_hash) == 64, "input_snapshot_hash is not a valid SHA-256 hash"
        
        print(f"recommendation_snapshot_hash: {run.recommendation_snapshot_hash}")
        assert run.recommendation_snapshot_hash is not None, "recommendation_snapshot_hash is missing"
        assert len(run.recommendation_snapshot_hash) == 64, "recommendation_snapshot_hash is not a valid SHA-256 hash"
        
        print(f"risk_level: {run.risk_level}")
        assert run.risk_level in ("HIGH", "MODERATE", "LOW"), f"Unexpected risk level: {run.risk_level}"
        
        print(f"recommended_tests_count: {run.recommended_tests_count}")
        assert run.recommended_tests_count is not None, "recommended_tests_count is missing"
        
        print(f"estimated_runtime_seconds: {run.estimated_runtime_seconds}s")
        print(f"full_suite_runtime_seconds: {run.full_suite_runtime_seconds}s")
        assert run.estimated_runtime_seconds is not None
        assert run.full_suite_runtime_seconds is not None

        # Verify RecommendedTest fields
        print("\n--- Verifying RecommendedTest Fields ---")
        recommended_tests = db.query(RecommendedTest).filter(
            RecommendedTest.recommendation_run_id == run.id
        ).all()
        
        print(f"Persisted RecommendedTests Count: {len(recommended_tests)}")
        assert len(recommended_tests) == run.recommended_tests_count, "Recommended tests count mismatch"
        
        for idx, t in enumerate(recommended_tests):
            print(f"Test #{idx+1}:")
            print(f"  test_identifier: {t.test_identifier}")
            print(f"  test_name: {t.test_name}")
            print(f"  class_name: {t.class_name}")
            print(f"  priority: {t.priority}")
            print(f"  confidence: {t.confidence}")
            print(f"  reason: {t.reason}")
            print(f"  source_signal: {t.source_signal}")
            print(f"  estimated_duration_seconds: {t.estimated_duration_seconds}")
            print(f"  included: {t.included}")
            print(f"  warning: {t.warning}")
            
            # Assertions
            assert t.test_identifier is not None, "test_identifier is missing"
            assert t.test_name is not None, "test_name is missing"
            assert t.priority is not None, "priority is missing"
            assert t.confidence in ("HIGH", "MEDIUM", "LOW"), f"Unexpected confidence: {t.confidence}"
            assert t.reason is not None and len(t.reason.strip()) > 0, "reason must be present and non-empty"
            assert t.source_signal is not None, "source_signal is missing"
            assert t.included is True or t.included is False, "included must be a boolean"

        # Verify Reloadability / PR Querying (Acceptance Criteria)
        print("\n--- Verifying Reloadability & Querying (Acceptance Criteria) ---")
        latest_run = db.query(RecommendationRun).filter(
            RecommendationRun.repository_id == repo.id,
            RecommendationRun.pull_request_id == pr.id
        ).order_by(RecommendationRun.created_at.desc()).first()
        
        assert latest_run is not None, "Failed to query run for PR"
        print(f"Queried latest run for PR. ID matches created run: {latest_run.id == run.id}")
        assert latest_run.id == run.id, "Latest queried run ID does not match"
        
        print(f"Successfully reloaded latest run after simulation. Tests present: {len(latest_run.recommended_tests)}")
        assert len(latest_run.recommended_tests) == len(recommended_tests)
        
        print("\nALL VERIFICATIONS PASSED SUCCESSFULLY.")

    except Exception as e:
        print(f"\nVERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nRolling back the transaction to preserve pure DB state...")
        db.rollback()
        db.close()

if __name__ == "__main__":
    test_durable_recommendation()
