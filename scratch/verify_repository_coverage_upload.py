import sys
import os
import uuid
import hashlib
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.config import settings
from app.models.user import Workspace, User, WorkspaceMember
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.test_result import TestCase
from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.artifact import RawArtifact

client = TestClient(app)

def cleanup_database():
    """Clean up test records to ensure fresh validation runs."""
    db = SessionLocal()
    try:
        # Delete Coverage records
        db.query(FileTestLink).delete()
        db.query(CoverageFileEntry).delete()
        db.query(CoverageReport).delete()
        
        # Delete related entities
        db.query(TestCase).delete()
        db.query(RawArtifact).delete()
        db.query(PullRequest).delete()
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
    print("  VERISCOPE REPOSITORY-SCOPED COVERAGE UPLOAD ENDPOINT VERIFICATION")
    print("======================================================================\n")

    cleanup_database()

    db = SessionLocal()

    try:
        # Setup Workspace & Repository
        ws = Workspace(id=uuid.uuid4(), name="API Ingestion Corp", slug=f"api-ingestion-{uuid.uuid4().hex[:6]}")
        db.add(ws)
        db.flush()

        repo = Repository(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            github_repo_id=987654,
            installation_id=123456,
            name="api-veriscope",
            full_name="api-ingestion/api-veriscope",
            default_branch="main",
            is_active=True,
            selected_for_analysis=True
        )
        db.add(repo)
        
        # Setup another repo in a different workspace to test cross-workspace isolation (403)
        ws_other = Workspace(id=uuid.uuid4(), name="Other Corp", slug=f"other-corp-{uuid.uuid4().hex[:6]}")
        db.add(ws_other)
        db.flush()
        
        repo_other = Repository(
            id=uuid.uuid4(),
            workspace_id=ws_other.id,
            github_repo_id=111111,
            installation_id=222222,
            name="other-repo",
            full_name="other-corp/other-repo",
            default_branch="main",
            is_active=True,
            selected_for_analysis=True
        )
        db.add(repo_other)

        # Setup a repository that is NOT_SELECTED for analysis (400)
        repo_not_selected = Repository(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            github_repo_id=333333,
            installation_id=444444,
            name="not-selected-repo",
            full_name="api-ingestion/not-selected-repo",
            default_branch="main",
            is_active=True,
            selected_for_analysis=False
        )
        db.add(repo_not_selected)

        # Seed test User and WorkspaceMember to satisfy require_workspace_member for ws
        user = User(
            id=uuid.uuid4(),
            email="api-test@ingestion.com",
            name="API Tester",
            auth_provider="github",
            provider_user_id="github-9999"
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
        print(f"Created Repo ID (Selected): {repo.id}")
        print(f"Created Repo ID (Not Selected): {repo_not_selected.id}")
        print(f"Created Repo ID (Other Workspace): {repo_other.id}\n")

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

        # Sample XML Cobertura payload
        xml_payload = """<?xml version="1.0"?>
<coverage line-rate="0.80" branch-rate="0.60">
  <packages>
    <package name="app.services">
      <classes>
        <class name="app.services.auth" filename="app/services/auth.py">
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="1"/>
            <line number="3" hits="0"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""

        # Sample LCOV payload containing functions and branch totals
        lcov_payload = """SF:app/services/auth.py
FNF:2
FNH:1
BRF:4
BRH:2
DA:1,1
DA:2,1
DA:3,0
LF:3
LH:2
end_of_record
"""

        # ----------------------------------------------------
        # TEST 1: Valid LCOV creates CoverageReport and CoverageFileEntry
        # ----------------------------------------------------
        print("--- TEST 1: Valid LCOV Ingestion ---")
        response_lcov = client.post(
            f"/api/repositories/{repo.id}/coverage/upload",
            data={
                "format": "LCOV",
                "commit_sha": "lcovsha123456",
                "branch": "main"
            },
            files={"file": ("coverage.info", lcov_payload, "text/plain")}
        )
        assert response_lcov.status_code == 201, f"LCOV upload failed: {response_lcov.text}"
        data_lcov = response_lcov.json()
        assert data_lcov["format"] == "LCOV"
        assert data_lcov["files_total"] == 1
        assert data_lcov["total_lines"] == 3
        assert data_lcov["covered_lines_total"] == 2
        assert data_lcov["uncovered_lines_total"] == 1
        assert abs(data_lcov["line_coverage_ratio"] - 0.6667) < 0.001
        
        # Verify db persistence of newly parsed LCOV contract fields
        db.expire_all()
        rep_db = db.query(CoverageReport).filter(CoverageReport.id == data_lcov["coverage_report_id"]).first()
        assert rep_db is not None
        assert abs(rep_db.branch_coverage_ratio - 0.5) < 0.01
        assert len(rep_db.file_entries) == 1
        fe_db = rep_db.file_entries[0]
        assert fe_db.functions_covered == 1
        assert fe_db.functions_total == 2
        assert abs(fe_db.branch_coverage_ratio - 0.5) < 0.01
        
        assert "repository_readiness" in data_lcov
        print("[OK] Valid LCOV upload created correct CoverageReport and response summary.")

        # ----------------------------------------------------
        # TEST 2: Valid Cobertura creates CoverageReport and CoverageFileEntry
        # ----------------------------------------------------
        print("\n--- TEST 2: Valid Cobertura Ingestion ---")
        response_xml = client.post(
            f"/api/repositories/{repo.id}/coverage/upload",
            data={
                "format": "COBERTURA",
                "commit_sha": "xmlsha123456",
                "branch": "develop"
            },
            files={"file": ("coverage.xml", xml_payload, "application/xml")}
        )
        assert response_xml.status_code == 201, f"Cobertura upload failed: {response_xml.text}"
        data_xml = response_xml.json()
        assert data_xml["format"] == "COBERTURA"
        assert data_xml["files_total"] == 1
        assert data_xml["total_lines"] == 3
        assert data_xml["covered_lines_total"] == 2
        assert data_xml["uncovered_lines_total"] == 1
        assert abs(data_xml["line_coverage_ratio"] - 0.6667) < 0.001
        assert data_xml["parser_version"] == "cobertura_parser.v1"
        assert data_xml["normalization_schema_version"] == "cobertura_result.v1"
        print("[OK] Valid Cobertura upload created correct CoverageReport and response summary.")

        # ----------------------------------------------------
        # TEST 3: Unsupported format raises 400
        # ----------------------------------------------------
        print("\n--- TEST 3: Unsupported Format ---")
        response_format = client.post(
            f"/api/repositories/{repo.id}/coverage/upload",
            data={"format": "JACOCO"},
            files={"file": ("coverage.xml", xml_payload, "application/xml")}
        )
        assert response_format.status_code == 400
        assert "unsupported coverage format" in response_format.json()["detail"]
        print("[OK] Unsupported format JACOCO correctly rejected with 400.")

        # ----------------------------------------------------
        # TEST 4: Missing file raises 400
        # ----------------------------------------------------
        print("\n--- TEST 4: Missing File ---")
        response_missing = client.post(
            f"/api/repositories/{repo.id}/coverage/upload",
            data={"format": "LCOV"}
        )
        assert response_missing.status_code == 400
        assert "missing file" in response_missing.json()["detail"]
        print("[OK] Missing file correctly rejected with 400.")

        # ----------------------------------------------------
        # TEST 5: Invalid coverage file raises 400
        # ----------------------------------------------------
        print("\n--- TEST 5: Empty/Invalid File ---")
        response_empty = client.post(
            f"/api/repositories/{repo.id}/coverage/upload",
            data={"format": "LCOV"},
            files={"file": ("coverage.info", "", "text/plain")}
        )
        assert response_empty.status_code == 400
        assert "invalid coverage file" in response_empty.json()["detail"]
        print("[OK] Empty file correctly rejected with 400.")

        # ----------------------------------------------------
        # TEST 6: Malformed content raises 422
        # ----------------------------------------------------
        print("\n--- TEST 6: Malformed Coverage Content ---")
        malformed_xml = "<?xml version='1.0'?><invalid_xml>"
        response_malformed = client.post(
            f"/api/repositories/{repo.id}/coverage/upload",
            data={"format": "COBERTURA"},
            files={"file": ("coverage.xml", malformed_xml, "application/xml")}
        )
        assert response_malformed.status_code == 422
        assert "malformed coverage content" in response_malformed.json()["detail"]
        print("[OK] Malformed XML content correctly rejected with 422.")

        # ----------------------------------------------------
        # TEST 7: Cross-workspace access raises 403
        # ----------------------------------------------------
        print("\n--- TEST 7: Cross-Workspace Isolation ---")
        response_cross = client.post(
            f"/api/repositories/{repo_other.id}/coverage/upload",
            data={"format": "LCOV"},
            files={"file": ("coverage.info", lcov_payload, "text/plain")}
        )
        assert response_cross.status_code == 403
        assert "repository not in workspace" in response_cross.json()["detail"]
        print("[OK] Repository belonging to other workspace correctly rejected with 403.")

        # ----------------------------------------------------
        # TEST 8: Repository not selected for analysis raises 400
        # ----------------------------------------------------
        print("\n--- TEST 8: Repository Not Selected for Analysis ---")
        response_not_sel = client.post(
            f"/api/repositories/{repo_not_selected.id}/coverage/upload",
            data={"format": "LCOV"},
            files={"file": ("coverage.info", lcov_payload, "text/plain")}
        )
        assert response_not_sel.status_code == 400
        assert "not selected for analysis" in response_not_sel.json()["detail"]
        print("[OK] Repository not enabled for analysis correctly rejected with 400.")

        # ----------------------------------------------------
        # TEST 9: Duplicate upload raises 409
        # ----------------------------------------------------
        print("\n--- TEST 9: Duplicate Upload (Idempotency Shield -> 409 Conflict) ---")
        response_dup = client.post(
            f"/api/repositories/{repo.id}/coverage/upload",
            data={
                "format": "LCOV",
                "commit_sha": "lcovsha123456",
                "branch": "main"
            },
            files={"file": ("coverage.info", lcov_payload, "text/plain")}
        )
        assert response_dup.status_code == 409
        assert "duplicate artifact" in response_dup.json()["detail"]
        print("[OK] Duplicate upload successfully prevented and rejected with 409.")

    finally:
        # Clean up overrides
        app.dependency_overrides.clear()
        cleanup_database()

    print("\n======================================================================")
    print(" ALL SCOPED COVERAGE ENDPOINT VERIFICATIONS PASSED SUCCESSFULLY!")
    print("======================================================================")

if __name__ == "__main__":
    run_verification()
