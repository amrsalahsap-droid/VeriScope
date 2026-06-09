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
from app.models.recommendation import RecommendationRun, RecommendationExplanation

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
        db.query(RecommendationExplanation).delete()
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


def run_change_impact_graph_verification():
    cleanup_database()
    print("Starting ChangeImpactGraph Verification...")

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

        # 3. Seed TestCase: tests.integration.auth-workflow.test.ts::should_reject_expired_token
        test_case_id = "tests.integration.auth-workflow.test.ts::should_reject_expired_token"
        tc = TestCase(
            id=uuid.uuid4(),
            repository_id=repo.id,
            suite_name="tests.integration.auth-workflow.test.ts",
            test_name="should_reject_expired_token",
            stable_identity=test_case_id,
            raw_test_name="should_reject_expired_token",
            normalized_test_name="should_reject_expired_token",
            normalized_identity_strategy="EXACT",
            framework_name="jest",
            framework_version="29.0",
            identity_normalization_version=1,
            canonical_identity_hash=hashlib.sha256(test_case_id.encode("utf-8")).hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(test_case_id.encode("utf-8")).hexdigest(),
            identity_version=1,
            identity_resolution_strategy="EXACT"
        )
        db.add(tc)

        # 4. Seed PullRequest and Changed File: src/app/api/auth/reset-password/route.ts
        pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo.id,
            github_pr_id=1212,
            number=42,
            title="Implement password reset endpoint",
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
            file_path=changed_file_path,
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
            test_identifier=test_case_id,
            file_path=changed_file_path,
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
            module_path=changed_file_path,
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
        print("ChangeImpactGraph verification test data seeded.")

        repo_uuid = repo.id
        pr_uuid = pr.id

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

    # 10. Call Generate Endpoint
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

    # Verify that RecommendationRun has impact_graph persisted in database
    db = SessionLocal()
    try:
        run = db.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()
        assert run.impact_graph is not None, "impact_graph was not persisted in database."
        print("[OK] Direct database verification: impact_graph is persisted.")
        
        g = run.impact_graph
        assert "nodes" in g and "edges" in g and "chains" in g
        assert len(g["chains"]) > 0
    finally:
        db.close()

    # 11. Call /api/recommendations/{recommendation_run_id}/impact-graph GET Endpoint
    print(f"\nCalling GET /api/recommendations/{run_id}/impact-graph API endpoint...")
    get_graph_resp = client.get(f"/api/recommendations/{run_id}/impact-graph")
    assert get_graph_resp.status_code == 200, f"GET impact-graph failed: {get_graph_resp.text}"
    get_graph_data = get_graph_resp.json()

    print("\n--- API Response (GET /api/recommendations/{id}/impact-graph) ---")
    import json
    print(json.dumps(get_graph_data, indent=2))

    # Assert Nodes
    node_map = {n["id"]: n for n in get_graph_data["nodes"]}
    assert f"file:{changed_file_path}" in node_map
    assert node_map[f"file:{changed_file_path}"]["type"] == "file"
    assert node_map[f"file:{changed_file_path}"]["label"] == changed_file_path

    assert "domain:Authentication" in node_map
    assert node_map["domain:Authentication"]["type"] == "domain"
    assert node_map["domain:Authentication"]["label"] == "Authentication"

    assert "risk:Security" in node_map
    assert node_map["risk:Security"]["type"] == "risk"
    assert node_map["risk:Security"]["label"] == "Security"

    assert "test_type:Security Testing" in node_map
    assert node_map["test_type:Security Testing"]["type"] == "testing_type"
    assert node_map["test_type:Security Testing"]["label"] == "Security Testing"

    assert f"test:{test_case_id}" in node_map
    assert node_map[f"test:{test_case_id}"]["type"] == "test"
    assert node_map[f"test:{test_case_id}"]["label"] == "should_reject_expired_token"

    print("[OK] Nodes list contains all required change segments with precise mapping values.")

    # Assert Edges
    edge_pairs = {(e["source"], e["target"]) for e in get_graph_data["edges"]}
    assert (f"file:{changed_file_path}", "domain:Authentication") in edge_pairs
    assert ("domain:Authentication", "risk:Security") in edge_pairs
    assert ("risk:Security", "test_type:Security Testing") in edge_pairs
    assert ("test_type:Security Testing", f"test:{test_case_id}") in edge_pairs
    print("[OK] Edges map visual connection chain (File -> Domain -> Risk -> Testing Type -> Test) perfectly.")

    # Assert Chains
    assert len(get_graph_data["chains"]) > 0
    expected_chain = {
        "file": changed_file_path,
        "domain": "Authentication",
        "risk": "Security",
        "testing_type": "Security Testing",
        "test": "should_reject_expired_token"
    }
    assert expected_chain in get_graph_data["chains"], f"Expected chain {expected_chain} not found in: {get_graph_data['chains']}"
    print("[OK] Chains contain flattened dictionary tracing exact impact paths.")

    # 12. Call /recommendations/{recommendation_run_id}/impact-graph Legacy GET Endpoint
    print(f"\nCalling GET legacy /recommendations/{run_id}/impact-graph API endpoint...")
    get_legacy_resp = client.get(f"/recommendations/{run_id}/impact-graph")
    assert get_legacy_resp.status_code == 200, f"GET legacy impact-graph failed: {get_legacy_resp.text}"
    get_legacy_data = get_legacy_resp.json()
    assert get_legacy_data == get_graph_data
    print("[OK] Legacy endpoint returns exactly identical visual relationship model.")

    print("\n=======================================================")
    print("ALL CHANGE IMPACT GRAPH VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=======================================================\n")


if __name__ == "__main__":
    try:
        run_change_impact_graph_verification()
    finally:
        cleanup_database()
