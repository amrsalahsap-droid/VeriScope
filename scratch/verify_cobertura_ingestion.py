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
from app.services.cobertura_parser import SafeCoberturaParser, CoberturaParsingError
from app.services.coverage_ingestion import CoverageIngestionService, CoverageIngestionError

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
    print("   VERISCOPE HARDENED COBERTURA INGESTION & SECURITY VERIFICATION")
    print("======================================================================\n")

    cleanup_database()

    db = SessionLocal()

    try:
        # Setup Workspace & Repository
        ws = Workspace(id=uuid.uuid4(), name="Cobertura Trust Corp", slug=f"cobertura-trust-{uuid.uuid4().hex[:6]}")
        db.add(ws)
        db.flush()

        repo = Repository(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            github_repo_id=987654,
            installation_id=123456,
            name="veriscope",
            full_name="cobertura-trust/veriscope",
            default_branch="main",
            is_active=True,
            selected_for_analysis=True
        )
        db.add(repo)
        db.flush()

        # Seed TestCase to check heuristic mapping
        tc = TestCase(
            id=uuid.uuid4(),
            repository_id=repo.id,
            suite_name="tests.services.test_auth",
            test_name="test_login",
            stable_identity="tests.services.test_auth::test_login",
            canonical_identity_hash=hashlib.sha256(b"tests.services.test_auth::test_login").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"tests.services.test_auth::test_login").hexdigest()
        )
        tc_dummy = TestCase(
            id=uuid.uuid4(),
            repository_id=repo.id,
            suite_name="tests.utils.test_dummy",
            test_name="test_dummy",
            stable_identity="tests.utils.test_dummy::test_dummy",
            canonical_identity_hash=hashlib.sha256(b"tests.utils.test_dummy::test_dummy").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"tests.utils.test_dummy::test_dummy").hexdigest()
        )
        db.add(tc)
        db.add(tc_dummy)
        db.commit()

        print(f"Created Workspace ID: {ws.id}")
        print(f"Created Repo ID: {repo.id}")
        print(f"Pre-populated TestCase ID: {tc.id}\n")

        # ----------------------------------------------------
        # 1. Test Well-Formed Cobertura Parsing & Ingestion
        # ----------------------------------------------------
        print("--- Step 1: Testing Well-Formed Cobertura Ingestion ---")
        
        dummy_lines_xml = "\n".join(f'<line number="{i}" hits="1" branch="false"/>' for i in range(1, 61))
        xml_payload = f"""<?xml version="1.0"?>
<!DOCTYPE coverage SYSTEM "http://cobertura.sourceforge.net/xml/coverage-04.dtd">
<coverage line-rate="0.75" branch-rate="0.50" version="2.0.3" timestamp="1405869400000">
  <sources>
    <source>/Users/amrsa/Downloads/veriscope</source>
  </sources>
  <packages>
    <package name="app.services" line-rate="0.75" branch-rate="0.50">
      <classes>
        <class name="app.services.auth" filename="app/services/auth.py" line-rate="0.75" branch-rate="0.50">
          <methods>
            <method name="login" signature="()V" line-rate="1.0">
              <lines>
                <line number="1" hits="1"/>
                <line number="2" hits="1"/>
              </lines>
            </method>
            <method name="logout" signature="()V" line-rate="0.0">
              <lines>
                <line number="3" hits="0"/>
              </lines>
            </method>
          </methods>
          <lines>
            <line number="1" hits="1" branch="false"/>
            <line number="2" hits="1" branch="false"/>
            <line number="3" hits="0" branch="false"/>
            <line number="4" hits="0" branch="false"/>
            <line number="5" hits="1" branch="true" condition-coverage="50% (1/2)"/>
          </lines>
        </class>
        <class name="app.utils.dummy" filename="app/utils/dummy.py" line-rate="1.0" branch-rate="1.0">
          <lines>
            {dummy_lines_xml}
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""

        response = client.post(
            "/api/coverage/upload",
            data={
                "repository_id": str(repo.id),
                "commit_sha": "cobertura1234567890abcdef",
                "branch": "main"
            },
            files={"file": ("coverage.xml", xml_payload, "application/xml")}
        )
        
        assert response.status_code == 201, f"Ingestion failed: {response.text}"
        data = response.json()
        assert "coverage_report_id" in data
        
        report_id = data["coverage_report_id"]
        print(f"[OK] Cobertura ingestion endpoint successfully accepted XML payload, generated ID: {report_id}")

        # Fetch and verify record fields in the database
        db.expire_all()
        report_db = db.query(CoverageReport).filter(CoverageReport.id == report_id).first()
        assert report_db is not None
        assert report_db.workspace_id == ws.id, "Workspace ID mismatch"
        assert report_db.repository_id == repo.id, "Repository ID mismatch"
        assert report_db.format == "COBERTURA", f"Expected format COBERTURA, got {report_db.format}"
        assert report_db.source == "MANUAL_UPLOAD", f"Expected source MANUAL_UPLOAD, got {report_db.source}"
        assert report_db.files_total == 2, f"Expected 2 files, got {report_db.files_total}"
        assert report_db.covered_lines_total == 63, f"Expected 63 covered lines, got {report_db.covered_lines_total}"
        assert report_db.uncovered_lines_total == 2, f"Expected 2 uncovered lines, got {report_db.uncovered_lines_total}"
        assert report_db.total_lines == 65, f"Expected 65 total lines, got {report_db.total_lines}"
        assert abs(report_db.line_coverage_ratio - 63/65) < 0.01, f"Expected 63/65 line coverage, got {report_db.line_coverage_ratio}"
        assert abs(report_db.branch_coverage_ratio - 0.50) < 0.01, f"Expected 0.50 branch coverage, got {report_db.branch_coverage_ratio}"
        assert report_db.coverage_confidence == "HIGH", f"Expected HIGH confidence, got {report_db.coverage_confidence}"
        assert report_db.evidence_health_status == "HEALTHY", f"Expected HEALTHY health, got {report_db.evidence_health_status}"

        # Verify CoverageFileEntry database columns
        assert len(report_db.file_entries) == 2
        fe = report_db.file_entries[0]
        assert fe.file_path == "app/services/auth.py", f"Expected normalized path, got {fe.file_path}"
        assert fe.repository_id == repo.id, "File entry Repository ID mismatch"
        assert fe.total_lines == 5, f"Expected 5 total lines, got {fe.total_lines}"
        assert abs(fe.line_coverage_ratio - 0.60) < 0.01, f"Expected 0.60 line coverage ratio, got {fe.line_coverage_ratio}"
        assert abs(fe.branch_coverage_ratio - 0.50) < 0.01, f"Expected 0.50 branch coverage ratio, got {fe.branch_coverage_ratio}"
        assert fe.functions_covered == 1, f"Expected 1 covered function, got {fe.functions_covered}"
        assert fe.functions_total == 2, f"Expected 2 total functions, got {fe.functions_total}"
        assert fe.covered_lines == [1, 2, 5], f"Expected covered lines list, got {fe.covered_lines}"
        assert fe.uncovered_lines == [3, 4], f"Expected uncovered lines list, got {fe.uncovered_lines}"
        print("[OK] All final contract columns parsed, scoped, and stored correctly in database.")

        # ----------------------------------------------------
        # 2. Test Malformed Cobertura XML Ingestion & Transaction Rollback
        # ----------------------------------------------------
        print("\n--- Step 2: Testing Malformed Cobertura Ingestion & Transaction Rollback ---")
        
        malformed_xml = """<?xml version="1.0"?>
<coverage line-rate="0.9">
  <packages>
    <package name="app">
      <classes>
        <class filename="app/services/auth.py">
          <lines>
            <line number="not_an_integer" hits="1"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""
        reports_count_before = db.query(CoverageReport).count()
        entries_count_before = db.query(CoverageFileEntry).count()

        response_malformed = client.post(
            "/api/coverage/upload",
            data={
                "repository_id": str(repo.id),
                "commit_sha": "malformed123456"
            },
            files={"file": ("coverage.xml", malformed_xml, "application/xml")}
        )
        assert response_malformed.status_code == 400
        assert "Malformed" in response_malformed.json()["detail"] or "Invalid" in response_malformed.json()["detail"]
        
        reports_count_after = db.query(CoverageReport).count()
        entries_count_after = db.query(CoverageFileEntry).count()
        
        assert reports_count_before == reports_count_after, "Failed transaction was not rolled back (report created)!"
        assert entries_count_before == entries_count_after, "Failed transaction was not rolled back (entries created)!"
        print("[OK] Malformed payload successfully failed fast and rolled back cleanly without writing any records.")

        # ----------------------------------------------------
        # 3. Test XXE External Entity Attack Protection
        # ----------------------------------------------------
        print("\n--- Step 3: Testing XXE Protection ---")
        
        xxe_xml = """<?xml version="1.0" encoding="ISO-8859-1"?>
<!DOCTYPE coverage [
  <!ENTITY xxe SYSTEM "http://localhost:9999/does-not-exist">
]>
<coverage line-rate="0.9">
  <sources>
    <source>&xxe;</source>
  </sources>
  <packages>
    <package name="app">
      <classes>
        <class name="app.auth" filename="app/services/auth.py">
          <lines>
            <line number="1" hits="1"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""
        response_xxe = client.post(
            "/api/coverage/upload",
            data={
                "repository_id": str(repo.id),
                "commit_sha": "xxe123456"
            },
            files={"file": ("coverage.xml", xxe_xml, "application/xml")}
        )
        assert response_xxe.status_code == 400
        assert "Security" in response_xxe.json()["detail"] or "EntitiesForbidden" in response_xxe.json()["detail"] or "Malformed" in response_xxe.json()["detail"]
        
        reports_count_xxe = db.query(CoverageReport).count()
        assert reports_count_before == reports_count_xxe, "XXE payload transaction was not rolled back!"
        print("[OK] XXE payload successfully blocked and transaction rolled back safely.")

        # ----------------------------------------------------
        # 4. Test Ingestion via repository upload endpoint
        # ----------------------------------------------------
        print("\n--- Step 4: Testing Ingestion via Workspace Scoped Endpoint ---")
        
        # Seed test User and WorkspaceMember to satisfy require_workspace_member
        test_user = User(
            id=uuid.uuid4(),
            email="test@coberturatrust.com",
            name="Cobertura Tester",
            auth_provider="github",
            provider_user_id="github-12345"
        )
        db.add(test_user)
        db.flush()
        
        test_member = WorkspaceMember(
            user_id=test_user.id,
            workspace_id=ws.id,
            role="OWNER"
        )
        db.add(test_member)
        db.commit()

        # Import leaf dependencies to override
        from app.dependencies.auth import get_current_user, get_current_workspace, get_current_workspace_id
        
        def mock_get_current_user():
            return test_user

        def mock_get_current_workspace():
            return ws

        def mock_get_current_workspace_id():
            return str(ws.id)

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_current_workspace] = mock_get_current_workspace
        app.dependency_overrides[get_current_workspace_id] = mock_get_current_workspace_id

        try:
            response_repo_endpoint = client.post(
                f"/repositories/{repo.id}/coverage/upload",
                data={
                    "format": "COBERTURA",
                    "commit_sha": "scoped1234567890abcdef",
                    "source": "MANUAL_UPLOAD"
                },
                files={"file": ("coverage.xml", xml_payload, "application/xml")}
            )
            assert response_repo_endpoint.status_code == 201, f"Scoped ingestion failed: {response_repo_endpoint.text}"
            scoped_data = response_repo_endpoint.json()
            assert scoped_data["format"] == "COBERTURA"
            assert scoped_data["parser_version"] == "cobertura_parser.v1"
            assert scoped_data["normalization_schema_version"] == "cobertura_result.v1"
            print("[OK] Ingestion via workspace-scoped router endpoint succeeded and returned correct parser/normalization tags.")
        finally:
            # Clean up overrides
            app.dependency_overrides.clear()

    finally:
        db.close()
        cleanup_database()

    print("\n======================================================================")
    print("  ALL COBERTURA INGESTION & SECURITY VERIFICATIONS PASSED SUCCESSFULLY!")
    print("======================================================================")

if __name__ == "__main__":
    run_verification()
