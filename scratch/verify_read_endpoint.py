import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.user import Workspace, User, WorkspaceMember
from app.services.recommendation import RecommendationService
from app.schemas.recommendation import RecommendationRunCreate
from app.main import app
from fastapi.testclient import TestClient
from app.dependencies.auth import get_current_workspace, get_current_user, get_current_workspace_id
import uuid

def test_read_endpoint():
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

        print(f"--- Verification of GET Read Endpoint for Repo: {repo.full_name}, PR: #{pr.number} ---")

        # Resolve or seed an active user and workspace member to satisfy require_workspace_member
        member = db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == workspace.id).first()
        if not member:
            user = User(
                id=uuid.uuid4(),
                email="api-test@ingestion.com",
                name="API Tester",
                auth_provider="github",
                provider_user_id=f"github-{uuid.uuid4().hex[:6]}"
            )
            db.add(user)
            db.flush()
            member = WorkspaceMember(
                user_id=user.id,
                workspace_id=workspace.id,
                role="OWNER"
            )
            db.add(member)
            db.flush()
        else:
            user = db.query(User).filter(User.id == member.user_id).first()

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
        print(f"Generated Run ID: {run.id}")

        # 3. Setup TestClient with FastAPI app
        client = TestClient(app)

        # 4. Override auth dependencies
        def override_get_current_user():
            return user

        def override_get_current_workspace():
            return workspace

        def override_get_current_workspace_id():
            return str(workspace.id)

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_current_workspace] = override_get_current_workspace
        app.dependency_overrides[get_current_workspace_id] = override_get_current_workspace_id

        # 5. Hit GET /api/recommendations/{recommendation_run_id}
        url = f"/api/recommendations/{run.id}"
        print(f"\nPerforming GET request to {url}...")
        response = client.get(url)

        print(f"Response Status Code: {response.status_code}")
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"

        payload = response.json()
        print("\n--- Response Payload Schema ---")
        import json
        print(json.dumps(payload, indent=2))

        # 6. Verify response schema keys and values
        print("\nAsserting response payload keys and types...")
        assert payload["id"] == str(run.id)
        assert payload["repository"]["id"] == str(repo.id)
        assert payload["repository"]["full_name"] == repo.full_name
        assert payload["pull_request"]["id"] == str(pr.id)
        assert payload["pull_request"]["number"] == pr.number
        assert payload["pull_request"]["title"] == pr.title

        summary = payload["summary"]
        assert summary["recommended_tests_count"] == run.recommended_tests_count
        assert summary["estimated_runtime_seconds"] == run.estimated_runtime_seconds
        assert summary["full_suite_runtime_seconds"] == run.full_suite_runtime_seconds
        assert summary["coverage_confidence"] == run.evidence_quality
        assert summary["risk_level"] == run.risk_level
        assert summary["recommendation_mode"] == run.recommendation_mode

        assert isinstance(payload["recommended_tests"], list)
        assert len(payload["recommended_tests"]) == len(run.recommended_tests)

        for t in payload["recommended_tests"]:
            assert "test_identifier" in t
            assert "test_name" in t
            assert "priority" in t
            assert "confidence" in t
            assert "reason" in t
            assert "source_signal" in t

        assert isinstance(payload["warnings"], list)
        print("SUCCESS: Endpoint returned the exact required response schema.")

        # 7. Verify Cross-Workspace access is blocked (403 Forbidden)
        print("\n--- Verifying Workspace Isolation / Cross-Workspace Access Check ---")
        different_workspace = Workspace(
            id=uuid.uuid4(),
            name="Different Workspace",
            slug=f"diff-workspace-{uuid.uuid4().hex[:6]}"
        )
        db.add(different_workspace)
        different_member = WorkspaceMember(
            user_id=user.id,
            workspace_id=different_workspace.id,
            role="MEMBER"
        )
        db.add(different_member)
        db.flush()

        def override_get_different_workspace():
            return different_workspace

        app.dependency_overrides[get_current_workspace] = override_get_different_workspace

        print(f"Performing cross-workspace GET request to {url} (Workspace ID: {different_workspace.id})...")
        cross_response = client.get(url)

        print(f"Cross-Workspace Response Status Code: {cross_response.status_code}")
        assert cross_response.status_code == 403, f"Expected 403 Forbidden, got {cross_response.status_code}"
        print(f"Cross-Workspace Error Detail: {cross_response.json()['detail']}")
        print("SUCCESS: Cross-workspace access was successfully blocked with a 403 response.")

        print("\nALL VERIFICATIONS PASSED SUCCESSFULLY.")

    except Exception as e:
        print(f"\nVERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clear dependency overrides after test
        app.dependency_overrides.clear()
        print("\nRolling back the transaction to preserve pure DB state...")
        db.rollback()
        db.close()

if __name__ == "__main__":
    test_read_endpoint()
