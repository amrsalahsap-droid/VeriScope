import sys
import uuid
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
from app.models.test_result import TestCase, TestRun
from app.models.recommendation import RecommendationRun, RecommendationExplanation, RecommendationOutcome

client = TestClient(app)

from fastapi import Depends
from sqlalchemy.orm import Session
from app.db.session import get_db

def get_mock_user(db: Session = Depends(get_db)):
    return db.query(User).filter(User.email == "developer@example.com").first()

def get_mock_workspace(db: Session = Depends(get_db)):
    return db.query(Workspace).filter(Workspace.slug == "dev-workspace").first()

# Hook overrides
app.dependency_overrides[get_current_user] = get_mock_user
app.dependency_overrides[get_current_workspace] = get_mock_workspace


def cleanup_database():
    db = SessionLocal()
    try:
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationExplanation).delete()
        db.query(RecommendationRun).delete()
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


def run_gaps_verification():
    cleanup_database()
    print("Starting Evidence Gaps and Potential Missing Coverage Verification...")

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

        # 3. Seed PullRequest and Changed File: src/app/api/auth/reset-password/route.ts
        # Note: We seed ZERO test cases and ZERO coverage files to trigger the gaps and missing coverage!
        pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo.id,
            github_pr_id=1212,
            number=42,
            title="Implement password reset token generation",
            author="alice",
            source_branch="feat-reset-password",
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

        changed_file_path = "src/app/api/auth/reset-password/route.ts"
        cf = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path=changed_file_path,
            status="modified",
            additions=50,
            deletions=5,
            created_at=datetime.datetime.utcnow()
        )
        db.add(cf)
        db.flush()

        # Seed a historical TestRun to satisfy the test history check
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            commit_sha="ccbbaaee11223344",
            pull_request_id=pr.id,
            status="SUCCESS",
            file_hash="dummy_file_hash_for_gaps_test",
            normalized_execution_fingerprint="dummy_fingerprint_for_gaps_test",
            total_tests=1,
            passed_tests=1,
            failed_tests=0
        )
        db.add(test_run)
        db.flush()

        # Seed an unrelated TestCase to verify MissingCoverageAnalyzer rules
        import hashlib
        stable_identity = "billing.checkout::should_charge_card"
        identity_hash = hashlib.sha256(stable_identity.encode("utf-8")).hexdigest()
        tc = TestCase(
            id=uuid.uuid4(),
            repository_id=repo.id,
            suite_name="billing",
            test_name="should_charge_card",
            stable_identity=stable_identity,
            canonical_identity_hash=identity_hash,
            identity_lineage_root_hash=identity_hash
        )
        db.add(tc)

        db.commit()
        print("Gaps verification test data seeded (Zero authentication test cases and coverage reports are present).")

        repo_uuid = repo.id
        pr_uuid = pr.id

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

    # 4. Call Generate Endpoint
    payload = {
        "repository_id": str(repo_uuid),
        "pull_request_id": str(pr_uuid),
        "triggered_by": "api_verification",
        "changed_files": [changed_file_path],
        "engine_version": "v3.0.0"
    }

    print("\nTriggering /api/recommendations/generate endpoint...")
    response = client.post("/api/recommendations/generate", json=payload)
    assert response.status_code == 201, f"Failed generation: {response.text}"
    run_data = response.json()
    run_id = run_data["id"]
    print(f"Created Recommendation Run ID: {run_id}")

    # 5. Call GET Endpoint to retrieve enriched gaps and missing coverage lists
    print(f"\nCalling GET /api/recommendations/{run_id} API endpoint...")
    get_resp = client.get(f"/api/recommendations/{run_id}")
    assert get_resp.status_code == 200, f"GET run details failed: {get_resp.text}"
    get_data = get_resp.json()

    print("\n--- API Response (GET /api/recommendations/{id}) Evidence Gaps & Missing Coverage ---")
    import json
    print("Evidence Gaps:")
    print(json.dumps(get_data.get("evidence_gaps"), indent=2))
    print("\nMissing Coverage Items:")
    print(json.dumps(get_data.get("missing_coverage"), indent=2))

    # Assert Gaps
    gaps = get_data.get("evidence_gaps") or []
    assert len(gaps) > 0, "No evidence gaps returned."
    
    # Check direct coverage mapping gap
    cov_gap = [g for g in gaps if "direct coverage mapping" in g["message"].lower()]
    assert len(cov_gap) > 0
    assert cov_gap[0]["severity"] == "HIGH"
    assert "no direct coverage mapping exists" in cov_gap[0]["message"].lower()
    
    # Check stale coverage gap
    stale_gap = [g for g in gaps if "stale" in g["message"].lower()]
    assert len(stale_gap) > 0
    assert stale_gap[0]["severity"] == "WARNING"

    # Check missing test history gap
    history_gap = [g for g in gaps if "test history" in g["message"].lower()]
    assert len(history_gap) > 0
    assert history_gap[0]["severity"] == "WARNING"

    # Check low graph confidence gap
    graph_gap = [g for g in gaps if "dependency graph" in g["message"].lower()]
    assert len(graph_gap) > 0
    assert graph_gap[0]["severity"] == "WARNING"

    # Check no outcome data gap
    outcome_gap = [g for g in gaps if "outcome data" in g["message"].lower()]
    assert len(outcome_gap) > 0
    assert outcome_gap[0]["severity"] == "INFO"

    # Check weak token matching gap
    token_gap = [g for g in gaps if "token" in g["message"].lower()]
    assert len(token_gap) > 0
    assert token_gap[0]["severity"] == "WARNING"

    print("[OK] EvidenceGaps correctly detects all 6 evidence verification gaps with appropriate severities.")

    # Assert Missing Coverage Items
    missing_items = get_data.get("missing_coverage") or []
    assert len(missing_items) > 0, "No missing coverage items returned."
    
    pwd_gap = [m for m in missing_items if "password reset" in m["feature"].lower() or "password" in m["feature"].lower()]
    assert len(pwd_gap) > 0
    assert pwd_gap[0]["domain"] == "Authentication"
    assert pwd_gap[0]["reason"] == "Password reset token generation has no detected automated tests."
    print("[OK] MissingCoverageAnalyzer correctly detects missing test gaps for Password Reset flows.")

    print("\n=======================================================")
    print("ALL EVIDENCE GAP AND MISSING COVERAGE VERIFICATIONS PASSED!")
    print("=======================================================\n")


if __name__ == "__main__":
    try:
        run_gaps_verification()
    finally:
        cleanup_database()
