import sys
import os
import uuid
from datetime import datetime
from fastapi import HTTPException

# Add parent directory to path so imports work correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile, PullRequestCommentDeliveryEvent
from app.models.user import Workspace
from app.models.recommendation import RecommendationRun, RecommendedTest
from app.models.test_result import TestRun
from app.models.coverage import CoverageReport
from app.services.repository_readiness import RepositoryReadinessService
from app.routers.repository import create_recommendation
from app.routers.recommendation import get_recommendation_run

def verify_all_rules():
    db = SessionLocal()
    run_id_to_cleanup = None
    run_id_to_cleanup2 = None
    
    try:
        # Load the default repository "amrsalahsap-droid/trustdesk"
        repo = db.query(Repository).filter(Repository.full_name == "amrsalahsap-droid/trustdesk").first()
        if not repo:
            # Fallback to any repository selected for analysis
            repo = db.query(Repository).filter(Repository.selected_for_analysis == True).first()
        
        if not repo:
            raise AssertionError("Rule 1-5 Broken: No Repository found in database.")
            
        print(f"Using Repository: {repo.full_name} (ID: {repo.id})")

        # 1. Verify repository is READY
        readiness_svc = RepositoryReadinessService(db)
        readiness = readiness_svc.calculate_readiness(repo.id, repo.workspace_id)
        print(f"Rule 1 Check - Readiness State: {readiness.readiness_state}")
        if readiness.readiness_state != "READY":
            raise AssertionError(
                f"Rule 1 Broken: Repository readiness state is '{readiness.readiness_state}' instead of 'READY'. "
                f"Reasons: {readiness.readiness_reasons}"
            )

        # 2. Verify repository has at least one TestRun
        test_run_count = db.query(TestRun).filter(TestRun.repository_id == repo.id).count()
        print(f"Rule 2 Check - Test Runs Count: {test_run_count}")
        if test_run_count < 1:
            raise AssertionError(f"Rule 2 Broken: Repository {repo.full_name} has no TestRun records.")

        # 3. Verify repository has at least one CoverageReport
        coverage_report_count = db.query(CoverageReport).filter(CoverageReport.repository_id == repo.id).count()
        print(f"Rule 3 Check - Coverage Reports Count: {coverage_report_count}")
        if coverage_report_count < 1:
            raise AssertionError(f"Rule 3 Broken: Repository {repo.full_name} has no CoverageReport records.")

        # 4. Verify repository has one open PullRequest
        pr = db.query(PullRequest).filter(
            PullRequest.repository_id == repo.id,
            PullRequest.state == "open"
        ).first()
        if not pr:
            raise AssertionError(f"Rule 4 Broken: No open PullRequest records found for Repository {repo.full_name}.")
        print(f"Rule 4 Check - Found Open PR: #{pr.number} (ID: {pr.id}) - Title: '{pr.title}'")

        # 5. PullRequestChangedFile records exist
        changed_files_count = db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == pr.id
        ).count()
        print(f"Rule 5 Check - PR Changed Files Count: {changed_files_count}")
        if changed_files_count < 1:
            raise AssertionError(f"Rule 5 Broken: 0 PullRequestChangedFile records found for PR #{pr.number}.")

        # 13. Pre-run check for comment delivery events
        comments_before = db.query(PullRequestCommentDeliveryEvent).count()

        # Resolve active workspace
        workspace = db.query(Workspace).filter(Workspace.id == repo.workspace_id).first()
        if not workspace:
            raise AssertionError(f"Setup Issue: Workspace {repo.workspace_id} not found.")

        # 6. POST recommendation endpoint creates RecommendationRun
        print("\nRule 6 Check - Triggering dry-run recommendation via POST endpoint handler...")
        response = create_recommendation(
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace,
            db=db
        )
        
        run_id_str = response.get("recommendation_run_id")
        if not run_id_str:
            raise AssertionError("Rule 6 Broken: POST endpoint response does not contain 'recommendation_run_id'.")
            
        run_id = uuid.UUID(run_id_str)
        run_id_to_cleanup = run_id
        
        run = db.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()
        if not run:
            raise AssertionError(f"Rule 6 Broken: RecommendationRun {run_id} was NOT persisted in the database.")
        print(f"Rule 6 Check - Persistent RecommendationRun Created: {run.id}")

        # 7. RecommendedTest rows are created
        rec_tests = db.query(RecommendedTest).filter(
            RecommendedTest.recommendation_run_id == run_id
        ).all()
        print(f"Rule 7 Check - Recommended Tests Created: {len(rec_tests)}")
        if len(rec_tests) < 1:
            raise AssertionError(f"Rule 7 Broken: No RecommendedTest rows were persisted in the database for run {run_id}.")

        # 8. every recommended test has a reason
        print("Rule 8 Check - Verifying reasons for each recommended test...")
        for idx, t in enumerate(rec_tests):
            if not t.reason or len(t.reason.strip()) == 0:
                raise AssertionError(f"Rule 8 Broken: Persisted recommended test '{t.test_name}' has no reasoning reason statement.")

        # 9. recommendation includes coverage_confidence
        coverage_confidence = response.get("coverage_confidence")
        print(f"Rule 9 Check - Response coverage_confidence: {coverage_confidence}")
        if "coverage_confidence" not in response or coverage_confidence is None:
            raise AssertionError("Rule 9 Broken: Response payload does not include 'coverage_confidence'.")

        # 10. recommendation includes risk_level
        risk_level = response.get("risk_level")
        print(f"Rule 10 Check - Response risk_level: {risk_level}")
        if "risk_level" not in response or risk_level is None:
            raise AssertionError("Rule 10 Broken: Response payload does not include 'risk_level'.")

        # 11. recommendation result endpoint returns persisted data
        print("\nRule 11 Check - Verifying read endpoint data persistence...")
        get_response = get_recommendation_run(
            recommendation_run_id=run_id,
            workspace=workspace,
            db=db
        )
        if str(get_response.get("id")) != run_id_str:
            raise AssertionError(f"Rule 11 Broken: GET read endpoint returned ID {get_response.get('id')} instead of {run_id_str}.")
        
        get_summary = get_response.get("summary", {})
        if get_summary.get("recommended_tests_count") != len(rec_tests):
            raise AssertionError(
                f"Rule 11 Broken: GET response recommended_tests_count ({get_summary.get('recommended_tests_count')}) "
                f"does not match actual database tests count ({len(rec_tests)})."
            )
        print("Rule 11 Check - GET read endpoint returned verified persisted data successfully.")

        # 12. repeated run is deterministic or versioned safely
        print("\nRule 12 Check - Triggering repeated run for determinism verification...")
        response2 = create_recommendation(
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace,
            db=db
        )
        run_id_str2 = response2.get("recommendation_run_id")
        run_id2 = uuid.UUID(run_id_str2)
        run_id_to_cleanup2 = run_id2
        
        run2 = db.query(RecommendationRun).filter(RecommendationRun.id == run_id2).first()
        if not run2:
            raise AssertionError("Rule 12 Broken: Repeated run failed to persist RecommendationRun.")
            
        print(f"Run 1 Hash: {run.input_snapshot_hash}")
        print(f"Run 2 Hash: {run2.input_snapshot_hash}")
        if run.input_snapshot_hash != run2.input_snapshot_hash:
            raise AssertionError(
                f"Rule 12 Broken: Input snapshot hash changed for identical database state. "
                f"Hash 1: {run.input_snapshot_hash}, Hash 2: {run2.input_snapshot_hash}"
            )
        print("Rule 12 Check - Repeated run input snapshot hashes are identical.")

        # 13. no GitHub PR comment is posted during dry run
        comments_after = db.query(PullRequestCommentDeliveryEvent).count()
        print(f"Rule 13 Check - PR Comment Delivery Events Before: {comments_before}, After: {comments_after}")
        if comments_after > comments_before:
            raise AssertionError(
                f"Rule 13 Broken: A GitHub comment delivery event was triggered during the dry run. "
                f"Comment events before: {comments_before}, After: {comments_after}"
            )

        # 14. workspace isolation is enforced
        print("\nRule 14 Check - Verifying workspace isolation constraints...")
        # Create a temporary fake workspace
        fake_workspace = Workspace(
            id=uuid.uuid4(),
            name="isolated-dummy-workspace-test",
            slug="isolated-dummy-workspace-test",
            created_at=datetime.utcnow()
        )
        db.add(fake_workspace)
        db.flush()
        
        # Verify isolation during generation
        try:
            create_recommendation(
                repository_id=repo.id,
                pull_request_id=pr.id,
                workspace=fake_workspace,
                db=db
            )
            raise AssertionError("Rule 14 Broken: POST dry-run succeeded for unauthorized workspace member.")
        except HTTPException as exc:
            if exc.status_code != 404:
                raise AssertionError(f"Rule 14 Broken: POST dry-run returned unexpected HTTP code {exc.status_code} for unauthorized workspace.")
            print("  -> Workspace isolation successfully blocked unauthorized recommendation creation (returned 404).")

        # Verify isolation during detailed reading
        try:
            get_recommendation_run(
                recommendation_run_id=run_id,
                workspace=fake_workspace,
                db=db
            )
            raise AssertionError("Rule 14 Broken: GET read endpoint succeeded for unauthorized workspace member.")
        except HTTPException as exc:
            if exc.status_code != 403:
                raise AssertionError(f"Rule 14 Broken: GET endpoint returned unexpected HTTP code {exc.status_code} for unauthorized workspace.")
            print("  -> Workspace isolation successfully blocked unauthorized recommendation access (returned 403).")

        # 15. UI can render recommendation result
        print("\nRule 15 Check - Validating result payload schemas against UI rendering needs...")
        required_root_keys = ["id", "repository", "pull_request", "summary", "recommended_tests", "reasons", "warnings"]
        for k in required_root_keys:
            if k not in get_response:
                raise AssertionError(f"Rule 15 Broken: Result payload missing required root key '{k}'.")
        
        for k in ["id", "full_name"]:
            if k not in get_response["repository"]:
                raise AssertionError(f"Rule 15 Broken: Result repository sub-object missing key '{k}'.")
                
        for k in ["id", "number", "title"]:
            if get_response["pull_request"] and k not in get_response["pull_request"]:
                raise AssertionError(f"Rule 15 Broken: Result pull_request sub-object missing key '{k}'.")
                
        for k in ["recommended_tests_count", "estimated_runtime_seconds", "full_suite_runtime_seconds", "coverage_confidence", "risk_level", "recommendation_mode"]:
            if k not in get_response["summary"]:
                raise AssertionError(f"Rule 15 Broken: Result summary sub-object missing key '{k}'.")
                
        for t in get_response["recommended_tests"]:
            for k in ["test_identifier", "test_name", "priority", "confidence", "reason", "source_signal", "estimated_duration_seconds"]:
                if k not in t:
                    raise AssertionError(f"Rule 15 Broken: Test item is missing key '{k}'.")
        print("Rule 15 Check - All result payload schemas verified and are fully ready for frontend UI rendering.")

        print("\n========================================================")
        print("ALL 15 VERIFICATION RULES PASSED SUCCESSFULLY!")
        print("========================================================")

    except AssertionError as ae:
        print(f"\n[RULE COMPLIANCE FAILURE]: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[UNEXPECTED VERIFICATION ERROR]: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
    finally:
        # Rollback alt_workspace and any in-memory session changes
        db.rollback()
        
        # Purge generated run rows explicitly to ensure 100% DB hygiene
        clean_db = SessionLocal()
        try:
            for rid in (run_id_to_cleanup, run_id_to_cleanup2):
                if rid:
                    # Cascade relationships are handled by the ORM or database cascades.
                    # We explicitly purge recommended tests first to be fully robust.
                    clean_db.query(RecommendedTest).filter(RecommendedTest.recommendation_run_id == rid).delete()
                    clean_db.query(RecommendationRun).filter(RecommendationRun.id == rid).delete()
                    clean_db.commit()
                    print(f"Database Hygiene: Cleaned up run record {rid} successfully.")
        except Exception as cleanup_err:
            clean_db.rollback()
            print(f"Hygiene Warning: Cleanup encountered an error: {cleanup_err}")
        finally:
            clean_db.close()
            db.close()

if __name__ == "__main__":
    verify_all_rules()
