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
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationOutcome,
    RecommendationReasoningEntry,
)
from app.models.artifact import RawArtifact
from app.models.observability import IngestionJob, SystemEvent
from app.models.dependency import FileDependency
from app.models.pull_request import (
    PullRequest,
    PullRequestCommit,
    PullRequestChangedFile,
    PullRequestSyncJob,
    PullRequestSnapshot
)
from app.models.test_result import TestCase
from app.models.coverage import CoverageReport, FileTestLink

client = TestClient(app)

def cleanup_database():
    db = SessionLocal()
    try:
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationTest).delete()
        db.query(RecommendationRun).delete()
        db.query(RawArtifact).delete()
        db.query(IngestionJob).delete()
        db.query(SystemEvent).delete()
        db.query(FileDependency).delete()
        db.query(FileTestLink).delete()
        db.query(CoverageReport).delete()
        db.query(TestCase).delete()
        db.query(PullRequestSnapshot).delete()
        db.query(PullRequestCommit).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequestSyncJob).delete()
        db.query(PullRequest).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def test_new_generate_endpoint():
    cleanup_database()
    print("Starting targeted generate API tests...")

    # 1. Setup Base Data
    db = SessionLocal()
    try:
        org = Organization(name="Test Org", slug="test-org")
        db.add(org)
        db.commit()

        repo = Repository(
            organization_id=org.id,
            github_repo_id=12345,
            name="test-repo",
            full_name="org/test-repo",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # Seed test cases
        tc = TestCase(
            id=uuid.uuid4(),
            repository_id=repo.id,
            suite_name="auth",
            test_name="test_login",
            stable_identity="test_login",
            canonical_identity_hash=hashlib.sha256(b"test_login").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"test_login").hexdigest()
        )
        db.add(tc)

        # Seed Pull Request
        pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo.id,
            github_pr_id=1010,
            number=1,
            title="Update Auth Flow",
            author="alice",
            source_branch="auth-update",
            target_branch="main",
            state="open",
            additions=5,
            deletions=1,
            changed_files_count=1,
            head_commit_sha="abcdef123",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)

        cf = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path="src/auth.py",
            status="modified",
            additions=5,
            deletions=1
        )
        db.add(cf)

        # Snapshot
        artifact = RawArtifact(
            id=uuid.uuid4(),
            repository_id=repo.id,
            artifact_type="github_pull_request",
            storage_path="s3://veriscope-artifacts/raw_pr",
            artifact_metadata={},
            created_at=datetime.datetime.utcnow()
        )
        db.add(artifact)
        db.commit()

        snap = PullRequestSnapshot(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            repository_id=repo.id,
            head_commit_sha="abcdef123",
            github_pr_updated_at=datetime.datetime.utcnow(),
            snapshot_reason="WEBHOOK_SYNCHRONIZE",
            normalization_engine_version="v1",
            evidence_fingerprint="fingerprint-abcdef123",
            snapshot_artifact_id=artifact.id,
            evidence_health_status="HEALTHY",
            sync_integrity_status="FULL_SUCCESS",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(snap)

        # Coverage report
        cov = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            commit_sha="abcdef123",
            overall_coverage_pct=0.85,
            total_lines=10,
            covered_lines_count=8,
            uncovered_lines_count=2,
            confidence_score="HIGH",
            confidence_logic="Targeted unit test coverage",
            file_hash="hash-abcdef123"
        )
        db.add(cov)
        db.commit()

        link = FileTestLink(
            id=uuid.uuid4(),
            coverage_report_id=cov.id,
            file_path="src/auth.py",
            test_case_id=tc.id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link)

        dep = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_path="src/auth.py",
            depends_on_file_path="src/utils.py",
            dependency_type="import",
            commit_sha="abcdef123"
        )
        db.add(dep)
        db.commit()

        repo_id = repo.id
        pr_sha = "abcdef123"
    finally:
        db.close()

    # 2. Test Success Flow for POST /api/recommendations/generate
    print("Testing /api/recommendations/generate success flow...")
    payload = {
        "repository_id": str(repo_id),
        "pull_request_id": pr_sha,
        "triggered_by": "pr_webhook",
        "changed_files": ["src/auth.py"]
    }
    response = client.post("/api/recommendations/generate", json=payload)
    assert response.status_code == 201, f"Failed generation: {response.text}"
    data = response.json()
    assert data["evidence_quality"] == "HIGH"
    assert data["correlation_id"] == "fingerprint-abcdef123"
    assert len(data["tests"]) == 1
    assert data["tests"][0]["test_case_id"] == "test_login"
    assert data["tests"][0]["priority_score"] > 0
    print("[OK] Successful generate flow verified.")

    # 3. Test Determinism (Second request with same input returns same result)
    print("Testing determinism...")
    response2 = client.post("/api/recommendations/generate", json=payload)
    assert response2.status_code == 201
    data2 = response2.json()
    assert data["tests"][0]["test_case_id"] == data2["tests"][0]["test_case_id"]
    assert data["tests"][0]["priority_score"] == data2["tests"][0]["priority_score"]
    print("[OK] Determinism verified.")

    # 4. Test Invalid Repository ID (returns 404)
    print("Testing invalid repository ID...")
    bad_payload = payload.copy()
    bad_payload["repository_id"] = str(uuid.uuid4())
    response_bad_repo = client.post("/api/recommendations/generate", json=bad_payload)
    assert response_bad_repo.status_code == 404, f"Expected 404, got {response_bad_repo.status_code}"
    print("[OK] Invalid repository ID handled cleanly with 404.")

    # 5. Test Invalid Pull Request (returns 400)
    print("Testing invalid pull request...")
    bad_payload2 = payload.copy()
    bad_payload2["pull_request_id"] = "non-existent-sha"
    response_bad_pr = client.post("/api/recommendations/generate", json=bad_payload2)
    assert response_bad_pr.status_code == 400, f"Expected 400, got {response_bad_pr.status_code}"
    print("[OK] Invalid pull request handled safely with 400.")

    print("\nALL TARGETED GENERATE API TESTS PASSED SUCCESSFULLY!")
    cleanup_database()

if __name__ == "__main__":
    try:
        test_new_generate_endpoint()
    except Exception as e:
        cleanup_database()
        raise e
