import sys
import uuid
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.user import Workspace, User, WorkspaceMember
from app.models.repository import Repository
from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.artifact import RawArtifact

client = TestClient(app)

def cleanup_database():
    """Clean up test records to ensure fresh validation runs."""
    db = SessionLocal()
    try:
        db.query(FileTestLink).delete()
        db.query(CoverageFileEntry).delete()
        db.query(CoverageReport).delete()
        db.query(RawArtifact).delete()
        db.query(WorkspaceMember).delete()
        db.query(Repository).delete()
        db.query(Workspace).delete()
        db.query(User).delete()
        db.commit()
        print("Database clean up successful.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def run_verification():
    print("======================================================================")
    print("  VERISCOPE REPOSITORY COVERAGE SUMMARY GET ENDPOINT VERIFICATION")
    print("======================================================================\n")

    cleanup_database()

    db = SessionLocal()

    try:
        # Setup Workspace & Repository
        ws = Workspace(id=uuid.uuid4(), name="Summary API Corp", slug=f"summary-api-{uuid.uuid4().hex[:6]}")
        db.add(ws)
        db.flush()

        repo = Repository(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            github_repo_id=987654,
            installation_id=123456,
            name="summary-veriscope",
            full_name="summary-api/summary-veriscope",
            default_branch="main",
            is_active=True,
            selected_for_analysis=True
        )
        db.add(repo)
        
        # Setup another repo in a different workspace to test cross-workspace isolation (403)
        ws_other = Workspace(id=uuid.uuid4(), name="Other Summary Corp", slug=f"other-summary-{uuid.uuid4().hex[:6]}")
        db.add(ws_other)
        db.flush()
        
        repo_other = Repository(
            id=uuid.uuid4(),
            workspace_id=ws_other.id,
            github_repo_id=111111,
            installation_id=222222,
            name="other-summary-repo",
            full_name="other-summary/other-summary-repo",
            default_branch="main",
            is_active=True,
            selected_for_analysis=True
        )
        db.add(repo_other)

        # Seed test User and WorkspaceMember to satisfy require_workspace_member for ws
        user = User(
            id=uuid.uuid4(),
            email="summary-test@ingestion.com",
            name="Summary Tester",
            auth_provider="github",
            provider_user_id="github-8888"
        )
        db.add(user)
        db.flush()
        
        member = WorkspaceMember(
            user_id=user.id,
            workspace_id=ws.id,
            role="OWNER"
        )
        db.add(member)
        db.commit()

        print(f"Created Workspace ID: {ws.id}")
        print(f"Created Repo ID: {repo.id}")
        print(f"Created Other Repo ID (Workspace Isolation Check): {repo_other.id}\n")

        # Mock authentication dependencies to return the active test user & workspace
        from app.dependencies.auth import get_current_user, get_current_workspace, get_current_workspace_id
        
        def mock_get_current_user():
            return user

        def mock_get_current_workspace():
            return ws

        def mock_get_current_workspace_id():
            return str(ws.id)

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_current_workspace] = mock_get_current_workspace
        app.dependency_overrides[get_current_workspace_id] = mock_get_current_workspace_id

        # ----------------------------------------------------
        # TEST 1: Empty summary when no coverage report exists
        # ----------------------------------------------------
        print("--- TEST 1: Empty Coverage Summary ---")
        response_empty = client.get(f"/api/repositories/{repo.id}/coverage/summary")
        assert response_empty.status_code == 200, f"Empty summary call failed: {response_empty.text}"
        data_empty = response_empty.json()
        assert data_empty["repository_id"] == str(repo.id)
        assert data_empty["coverage_reports_count"] == 0
        assert data_empty["latest_coverage_at"] is None
        assert data_empty["latest_report"] is None
        print("[OK] Correctly returned 0 counts and null entries for clean repository.")

        # ----------------------------------------------------
        # TEST 2: Summary details for a single uploaded report
        # ----------------------------------------------------
        print("\n--- TEST 2: Single Coverage Report Summary ---")
        # Persist a manual report directly
        report_1 = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=ws.id,
            commit_sha="commit_first_sha",
            pull_request_id=None,
            raw_artifact_id=None,
            format="LCOV",
            source="MANUAL_UPLOAD",
            branch="main",
            files_total=3,
            covered_lines_total=30,
            uncovered_lines_total=10,
            total_lines=40,
            line_coverage_ratio=0.75,
            branch_coverage_ratio=0.50,
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            parser_version="1.0.0",
            normalization_schema_version="1.0.0",
            file_hash="hash_1",
            confidence_score="HIGH",
            created_at=datetime.utcnow() - timedelta(minutes=10) # older
        )
        db.add(report_1)
        db.commit()

        response_single = client.get(f"/api/repositories/{repo.id}/coverage/summary")
        assert response_single.status_code == 200
        data_single = response_single.json()
        assert data_single["coverage_reports_count"] == 1
        assert data_single["latest_coverage_at"] is not None
        assert data_single["latest_report"] is not None
        
        lr = data_single["latest_report"]
        assert lr["commit_sha"] == "commit_first_sha"
        assert lr["branch"] == "main"
        assert lr["format"] == "LCOV"
        assert lr["files_total"] == 3
        assert lr["total_lines"] == 40
        assert lr["line_coverage_ratio"] == 0.75
        assert lr["coverage_confidence"] == "HIGH"
        assert lr["evidence_health_status"] == "HEALTHY"
        assert lr["source"] == "MANUAL_UPLOAD"
        print("[OK] Correctly returned exact metrics and details for single report.")

        # ----------------------------------------------------
        # TEST 3: Multi-report summary returns the latest (deterministic desc order)
        # ----------------------------------------------------
        print("\n--- TEST 3: Multi-report Summary (Latest Sorting) ---")
        # Persist a newer manual report directly
        report_2 = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=ws.id,
            commit_sha="commit_latest_sha",
            pull_request_id=None,
            raw_artifact_id=None,
            format="COBERTURA",
            source="MANUAL_UPLOAD",
            branch="develop",
            files_total=5,
            covered_lines_total=80,
            uncovered_lines_total=20,
            total_lines=100,
            line_coverage_ratio=0.80,
            branch_coverage_ratio=0.70,
            coverage_confidence="MODERATE",
            evidence_health_status="HEALTHY",
            parser_version="1.0.0",
            normalization_schema_version="1.0.0",
            file_hash="hash_2",
            confidence_score="MODERATE",
            created_at=datetime.utcnow() # newer
        )
        db.add(report_2)
        db.commit()

        response_multi = client.get(f"/api/repositories/{repo.id}/coverage/summary")
        assert response_multi.status_code == 200
        data_multi = response_multi.json()
        assert data_multi["coverage_reports_count"] == 2
        assert data_multi["latest_report"] is not None
        
        lr_multi = data_multi["latest_report"]
        assert lr_multi["commit_sha"] == "commit_latest_sha"
        assert lr_multi["branch"] == "develop"
        assert lr_multi["format"] == "COBERTURA"
        assert lr_multi["total_lines"] == 100
        assert lr_multi["line_coverage_ratio"] == 0.80
        assert lr_multi["coverage_confidence"] == "MODERATE"
        print("[OK] Correctly returned count of 2 and selected newer Cobertura report details.")

        # ----------------------------------------------------
        # TEST 4: Cross-workspace summary isolation (raises 403)
        # ----------------------------------------------------
        print("\n--- TEST 4: Workspace Isolation Check ---")
        response_iso = client.get(f"/api/repositories/{repo_other.id}/coverage/summary")
        assert response_iso.status_code == 403
        assert "repository not in workspace" in response_iso.json()["detail"]
        print("[OK] Correctly isolated access to other workspace repositories with 403 Forbidden.")

    finally:
        # Clean up overrides
        app.dependency_overrides.clear()
        cleanup_database()

    print("\n======================================================================")
    print(" ALL COVERAGE SUMMARY ENDPOINT VERIFICATIONS PASSED SUCCESSFULLY!")
    print("======================================================================")

if __name__ == "__main__":
    run_verification()
