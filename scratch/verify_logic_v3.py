import sys
import uuid
import hashlib
import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.dependencies.auth import get_current_user, get_current_workspace
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestCase, TestRun, TestResult
from app.models.coverage import CoverageReport, FileTestLink
from app.models.test_coverage_link import TestCoverageLink
from app.models.module_risk_profile import ModuleRiskProfile
from app.models.recommendation import RecommendationRun

client = TestClient(app)

from fastapi import Depends
from sqlalchemy.orm import Session
from app.db.session import get_db

def get_mock_user(db: Session = Depends(get_db)):
    return db.query(User).first()

def get_mock_workspace(db: Session = Depends(get_db)):
    return db.query(Workspace).first()

# Hook overrides
app.dependency_overrides[get_current_user] = get_mock_user
app.dependency_overrides[get_current_workspace] = get_mock_workspace


def cleanup_database():
    db = SessionLocal()
    try:
        db.query(RecommendationRun).delete()
        db.query(TestResult).delete()
        db.query(TestRun).delete()
        db.query(FileTestLink).delete()
        db.query(TestCoverageLink).delete()
        db.query(ModuleRiskProfile).delete()
        db.query(TestCase).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequest).delete()
        db.query(Repository).delete()
        db.query(WorkspaceMember).delete()
        db.query(Workspace).delete()
        db.query(User).delete()
        db.commit()
        print("Database cleaned up.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()


def run_e2e_verification():
    global seeded_user, seeded_workspace
    
    cleanup_database()
    print("Starting Recommendation Engine V3 E2E API Verification...")

    db = SessionLocal()
    try:
        # 1. Seed Authentication Scoping
        user = User(
            email="developer@example.com",
            name="Alice Dev",
            auth_provider="github",
            provider_user_id="git-12345"
        )
        db.add(user)
        db.flush()

        workspace = Workspace(
            name="Development Workspace",
            slug="dev-workspace",
            created_by_user_id=user.id
        )
        db.add(workspace)
        db.flush()

        member = WorkspaceMember(
            user_id=user.id,
            workspace_id=workspace.id,
            role="OWNER"
        )
        db.add(member)
        db.flush()

        # Set globals for FastAPI dependency overrides
        seeded_user = user
        seeded_workspace = workspace

        # 2. Seed Repository under Workspace
        repo = Repository(
            workspace_id=workspace.id,
            github_repo_id=77777,
            name="veriscope-app",
            full_name="acme/veriscope-app",
            default_branch="main",
            is_active=True,
            selected_for_analysis=True
        )
        db.add(repo)
        db.flush()

        # 3. Seed TestCase
        tc = TestCase(
            id=uuid.uuid4(),
            repository_id=repo.id,
            suite_name="auth",
            test_name="should_allow_valid_token",
            stable_identity="auth.middleware::should_allow_valid_token",
            raw_test_name="should_allow_valid_token",
            normalized_test_name="should_allow_valid_token",
            normalized_identity_strategy="EXACT",
            framework_name="pytest",
            framework_version="1.0",
            identity_normalization_version=1,
            canonical_identity_hash=hashlib.sha256(b"auth.middleware::should_allow_valid_token").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"auth.middleware::should_allow_valid_token").hexdigest(),
            identity_version=1,
            identity_resolution_strategy="EXACT"
        )
        db.add(tc)

        # 4. Seed PullRequest and Changed File
        pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo.id,
            github_pr_id=1212,
            number=42,
            title="Implement V3 Engine Routing",
            author="alice",
            source_branch="feat-v3",
            target_branch="main",
            state="open",
            additions=50,
            deletions=5,
            changed_files_count=1,
            head_commit_sha="ccbbaaee11223344",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.flush()

        cf = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path="src/auth/middleware.py",
            status="modified",
            additions=50,
            deletions=5,
            created_at=datetime.datetime.utcnow()
        )
        db.add(cf)

        # 5. Seed Test History to satisfy checks
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            commit_sha="ccbbaaee11223344",
            status="failed",
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            total_tests=1,
            passed_tests=0,
            failed_tests=1,
            skipped_tests=0,
            duration=5.2,
            file_hash="hash-1",
            normalized_execution_fingerprint="fingerprint-1",
            created_at=datetime.datetime.utcnow()
        )
        db.add(test_run)
        db.flush()

        # 6. Seed Coverage Link (+40)
        # We need a CoverageReport
        cov = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=workspace.id,
            commit_sha="ccbbaaee11223344",
            format="COBERTURA",
            source="MANUAL_UPLOAD",
            files_total=1,
            covered_lines_total=90,
            uncovered_lines_total=10,
            total_lines=100,
            overall_coverage_pct=0.90,
            covered_lines_count=90,
            uncovered_lines_count=10,
            confidence_score="HIGH",
            confidence_logic="Targeted unit test coverage",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            file_hash="hash-cov-1"
        )
        db.add(cov)
        db.flush()

        ftl = FileTestLink(
            id=uuid.uuid4(),
            coverage_report_id=cov.id,
            file_path="src/auth/middleware.py",
            test_case_id=tc.id,
            mapping_type="DIRECT",
            confidence_score="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(ftl)

        # 7. Seed TestCoverageLink Graph edge (+30) with manual overrides (+20) and escaped defects (+30)
        tcl = TestCoverageLink(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            repository_id=repo.id,
            test_identifier="auth.middleware::should_allow_valid_token",
            file_path="src/auth/middleware.py",
            override_count=1,
            defect_count=1,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        db.add(tcl)

        # 8. Seed Module Risk Profile (+15)
        mrp = ModuleRiskProfile(
            id=uuid.uuid4(),
            repository_id=repo.id,
            module_path="src/auth/middleware.py",
            risk_score=50.0,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        db.add(mrp)

        # 9. Seed Historical Failure (+10) and Runtime Cost (-5)
        tr_fail = TestResult(
            id=uuid.uuid4(),
            test_run_id=test_run.id,
            test_case_id=tc.id,
            status="failed",
            duration=5.2,
            created_at=datetime.datetime.utcnow()
        )
        db.add(tr_fail)

        db.commit()
        print("Test data successfully seeded.")

        # Save variables for HTTP request
        repo_uuid = repo.id
        pr_uuid = pr.id

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

    # 10. Call the Endpoint
    payload = {
        "repository_id": str(repo_uuid),
        "pull_request_id": str(pr_uuid),
        "triggered_by": "api_verification",
        "changed_files": ["src/auth/middleware.py"],
        "engine_version": "v3.0.0"
    }

    print("\nSending POST request to /api/recommendations/generate...")
    response = client.post("/api/recommendations/generate", json=payload)
    
    assert response.status_code == 201, f"Failed generation: {response.text}"
    data = response.json()
    
    print("\n--- API Generate Response ---")
    import json
    print(json.dumps(data, indent=2))

    # 11. Call the GET Endpoint to retrieve the RecommendedTests
    run_id = data["id"]
    print(f"\nSending GET request to /api/recommendations/{run_id}...")
    get_response = client.get(f"/api/recommendations/{run_id}")
    
    assert get_response.status_code == 200, f"Failed retrieval: {get_response.text}"
    get_data = get_response.json()
    
    print("\n--- API Retrieval Response ---")
    print(json.dumps(get_data, indent=2))

    # 12. Assert Output correctness
    print("\nVerifying V3 recommendation details...")
    assert len(get_data["recommended_tests"]) == 1, "Expected exactly 1 recommended test."
    rec = get_data["recommended_tests"][0]
    
    assert rec["test_identifier"] == "auth.middleware::should_allow_valid_token", f"Unexpected test_identifier: {rec['test_identifier']}"
    assert rec["priority"] == 140.0, f"Expected priority 140.0, got {rec['priority']}"
    assert rec["confidence"] == "HIGH", f"Expected HIGH confidence, got {rec['confidence']}"
    assert rec["source_signal"] == "DIRECT_COVERAGE", f"Expected DIRECT_COVERAGE source signal, got {rec['source_signal']}"
    assert rec["estimated_duration_seconds"] == 5.2, f"Expected 5.2 seconds runtime, got {rec['estimated_duration_seconds']}"
    
    reason = rec["reason"]
    print(f"\nBreakdown String:\n{reason}")
    assert "Coverage Link:\n+40" in reason
    assert "Knowledge Graph:\n+30" in reason
    assert "Module Risk:\n+15" in reason
    assert "Historical Failure:\n+10" in reason
    assert "Runtime Cost:\n-5" in reason
    assert "Total:\n140" in reason

    print("\nSUCCESS: All V3 API end-to-end assertions passed!")


if __name__ == "__main__":
    try:
        run_e2e_verification()
    finally:
        cleanup_database()
