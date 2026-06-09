import sys
import os
import uuid
from fastapi import HTTPException

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.user import Workspace
from app.models.recommendation import RecommendationRun, RecommendedTest
from app.models.test_result import TestRun
from app.models.coverage import CoverageReport, FileTestLink
from app.routers.repository import create_recommendation
from app.routers.recommendation import get_recommendation_run

def run_weak_evidence_verifications():
    db = SessionLocal()
    
    try:
        # Load the default repository "amrsalahsap-droid/trustdesk"
        repo = db.query(Repository).filter(Repository.full_name == "amrsalahsap-droid/trustdesk").first()
        if not repo:
            repo = db.query(Repository).filter(Repository.selected_for_analysis == True).first()
            
        if not repo:
            print("Setup error: No repository found in database.")
            sys.exit(1)
            
        pr = db.query(PullRequest).filter(
            PullRequest.repository_id == repo.id,
            PullRequest.state == "open"
        ).first()
        if not pr:
            print("Setup error: No open pull request found in database.")
            sys.exit(1)
            
        workspace = db.query(Workspace).filter(Workspace.id == repo.workspace_id).first()
        if not workspace:
            print("Setup error: Workspace not found.")
            sys.exit(1)
            
        print(f"--- Triggering Fallback Verifications for Repo: {repo.full_name} ---")

        # ========================================================
        # Case 3: No changed files -> Return controlled error
        # ========================================================
        print("\nVerifying Case 3: No changed files...")
        # Start a local sub-transaction to isolate database deletions
        db.begin_nested()
        db.query(PullRequestChangedFile).filter(PullRequestChangedFile.pull_request_id == pr.id).delete()
        db.flush()
        
        try:
            create_recommendation(
                repository_id=repo.id,
                pull_request_id=pr.id,
                workspace=workspace,
                db=db
            )
            raise AssertionError("Expected empty changed files error but it succeeded!")
        except HTTPException as exc:
            print(f"  Captured expected HTTPException: status_code={exc.status_code}, detail='{exc.detail}'")
            assert exc.status_code == 400, f"Unexpected status code: {exc.status_code}"
            assert "Pull request has no changed files available for analysis." in exc.detail
            print("  -> Case 3 Passed successfully.")
        
        db.rollback() # Restore changed files

        # ========================================================
        # Case 2: No test history -> Return controlled error
        # ========================================================
        print("\nVerifying Case 2: No test history...")
        db.begin_nested()
        db.query(TestRun).filter(TestRun.repository_id == repo.id).delete()
        db.flush()
        
        try:
            create_recommendation(
                repository_id=repo.id,
                pull_request_id=pr.id,
                workspace=workspace,
                db=db
            )
            raise AssertionError("Expected no test history error but it succeeded!")
        except HTTPException as exc:
            print(f"  Captured expected HTTPException: status_code={exc.status_code}, detail='{exc.detail}'")
            assert exc.status_code == 400, f"Unexpected status code: {exc.status_code}"
            assert "Repository requires test history before recommendations can run." in exc.detail
            print("  -> Case 2 Passed successfully.")
            
        db.rollback() # Restore test runs

        # ========================================================
        # Case 1: Changed files do not match coverage files -> low confidence
        # ========================================================
        print("\nVerifying Case 1: Changed files do not match coverage files...")
        db.begin_nested()
        # Temporarily wipe out all coverage mapping links
        db.query(FileTestLink).delete()
        db.flush()
        
        res = create_recommendation(
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace,
            db=db
        )
        run_id_str = res["recommendation_run_id"]
        run_id = uuid.UUID(run_id_str)
        
        # Verify all persisted tests have confidence LOW and the customized reason
        rec_tests = db.query(RecommendedTest).filter(
            RecommendedTest.recommendation_run_id == run_id
        ).all()
        
        print(f"  Generated {len(rec_tests)} fallback recommendations.")
        assert len(rec_tests) > 0, "Expected tests recommended during fallback"
        for t in rec_tests:
            print(f"  Test: '{t.test_identifier}' | Confidence: {t.confidence} | Reason: '{t.reason}'")
            assert t.confidence == "LOW", f"Expected confidence LOW but got {t.confidence}"
            assert t.reason == "No direct coverage match found; selected tests using historical/path fallback.", f"Unexpected reason: {t.reason}"
            
        print("  -> Case 1 Passed successfully.")
        db.rollback() # Restore coverage links

        # ========================================================
        # Case 4: Coverage confidence LOW -> Warning
        # ========================================================
        print("\nVerifying Case 4: Coverage confidence LOW warning...")
        db.begin_nested()
        cov = db.query(CoverageReport).filter(CoverageReport.repository_id == repo.id).first()
        if cov:
            cov.coverage_confidence = "LOW"
            db.flush()
            
        res = create_recommendation(
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace,
            db=db
        )
        run_id_str = res["recommendation_run_id"]
        run_id = uuid.UUID(run_id_str)
        
        get_res = get_recommendation_run(
            recommendation_run_id=run_id,
            workspace=workspace,
            db=db
        )
        
        print(f"  GET read response warnings: {get_res.get('warnings')}")
        assert "Coverage confidence is LOW." in get_res.get("warnings", []), "LOW confidence warning missing!"
        print("  -> Case 4 Passed successfully.")
        db.rollback() # Restore coverage confidence
        
        print("\n========================================================")
        print("ALL FALLBACK AND GRACEFUL ERROR VERIFICATIONS PASSED!")
        print("========================================================")

    except AssertionError as ae:
        print(f"\n[VERIFICATION FAILURE]: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR]: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
    finally:
        # Final cleanup rollback to keep the database completely untouched
        db.rollback()
        db.close()

if __name__ == "__main__":
    run_weak_evidence_verifications()
