"""Tests for Manual Test Execution logic and endpoints."""

import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.external_test_case_detailed import ExternalTestCase
from app.models.integration_connection import IntegrationConnection
from app.models.manual_test_execution import ManualTestExecution
from app.models.test_result import TestRun, TestResult
from app.dependencies.auth import get_current_user, get_current_workspace_id


@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def test_user(db: Session):
    email = f"test-manual-exec-{uuid.uuid4().hex[:6]}@example.com"
    user = User(
        email=email,
        name="Test Manual User",
        auth_provider="github",
        provider_user_id=f"test-manual-{uuid.uuid4().hex[:6]}"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.delete(user)
    db.commit()


@pytest.fixture
def test_workspace(db: Session, test_user: User):
    workspace = Workspace(
        name=f"Workspace-{uuid.uuid4().hex[:6]}",
        slug=f"workspace-{uuid.uuid4().hex[:6]}",
        created_by_user_id=test_user.id
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=test_user.id,
        role="OWNER"
    )
    db.add(member)
    db.commit()
    
    yield workspace
    db.delete(member)
    db.delete(workspace)
    db.commit()


@pytest.fixture
def test_repository(db: Session, test_workspace: Workspace):
    repo = Repository(
        name="manual-test-repo",
        full_name=f"test-owner/manual-repo-{uuid.uuid4().hex[:6]}",
        owner="test-owner",
        github_repo_id=int(uuid.uuid4().int % 10000000),
        workspace_id=test_workspace.id,
        is_active=True,
        selected_for_analysis=True
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    yield repo
    db.delete(repo)
    db.commit()


@pytest.fixture
def test_pr(db: Session, test_repository: Repository):
    pr = PullRequest(
        id=uuid.uuid4(),
        repository_id=test_repository.id,
        github_pr_id=int(uuid.uuid4().int % 10000000),
        number=1,
        title="Test PR",
        author="test-author",
        source_branch="feature",
        target_branch="main",
        state="open",
        head_commit_sha="a" * 40,
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    yield pr
    db.delete(pr)
    db.commit()


@pytest.fixture
def test_integration_connection(db: Session, test_workspace: Workspace, test_repository: Repository):
    connection = IntegrationConnection(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        repository_id=test_repository.id,
        provider="MANUAL_CSV",
        display_name=f"Manual Connection-{uuid.uuid4().hex[:6]}",
        status="CONNECTED",
        is_active=True
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    yield connection
    db.delete(connection)
    db.commit()


@pytest.fixture
def manual_test_case(db: Session, test_repository: Repository, test_integration_connection: IntegrationConnection):
    tc = ExternalTestCase(
        id=uuid.uuid4(),
        repository_id=test_repository.id,
        workspace_id=test_repository.workspace_id,
        integration_connection_id=test_integration_connection.id,
        provider="manual",
        external_id=f"ext-{uuid.uuid4().hex}",
        title="Verify multi-factor authentication fallback",
        external_key="TC-101",
        automation_status="MANUAL",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    yield tc
    db.delete(tc)
    db.commit()


@pytest.fixture
def client_with_auth(test_user: User, test_workspace: Workspace):
    def override_get_current_user():
        return test_user

    def override_get_current_workspace_id():
        return str(test_workspace.id)

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_workspace_id] = override_get_current_workspace_id

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


class TestManualTestExecution:
    """Suite of tests covering backend requirements for Phase 6.0."""

    @pytest.mark.parametrize("outcome", ["PASSED", "FAILED", "SKIPPED", "BLOCKED"])
    def test_post_execution_success(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository, manual_test_case: ExternalTestCase, test_pr: PullRequest, outcome: str
    ):
        """Verify endpoint persists manual test execution and returns SUCCESS status."""
        url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/execution"
        payload = {
            "outcome": outcome,
            "notes": f"Executed manually with outcome {outcome}",
            "evidenceUrl": "https://jira.example.com/browse/TC-101",
            "pullRequestId": str(test_pr.id)
        }

        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        
        assert data["status"] == "SUCCESS"
        assert data["execution"]["outcome"] == outcome
        assert data["execution"]["notes"] == payload["notes"]
        assert data["execution"]["evidenceUrl"] == payload["evidenceUrl"]
        assert data["execution"]["executedByName"] == "Test Manual User"

        # Verify persisted record
        execution_id = data["execution"]["id"]
        record = db.query(ManualTestExecution).filter(ManualTestExecution.id == execution_id).first()
        assert record is not None
        assert record.outcome == outcome
        assert record.is_active is True
        assert record.pull_request_id == test_pr.id
        assert record.repository_id == test_repository.id
        assert record.executed_by_name == "Test Manual User"

    def test_post_execution_invalid_outcome(
        self, client_with_auth: TestClient, test_repository: Repository, manual_test_case: ExternalTestCase
    ):
        """Verify endpoint rejects invalid outcomes."""
        url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/execution"
        payload = {
            "outcome": "INVALID_OUTCOME",
            "notes": "Testing invalid outcome"
        }

        response = client_with_auth.post(url, json=payload)
        # Should raise validation error
        assert response.status_code == 422

    def test_executor_identity_from_auth(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository, manual_test_case: ExternalTestCase
    ):
        """Verify executor identity comes from auth/session, not request body."""
        url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/execution"
        # Try to pass executed_by_id or executed_by_name in request body (should be ignored)
        payload = {
            "outcome": "PASSED",
            "notes": "Checking executor override",
            "executed_by_id": "malicious-user-id",
            "executed_by_name": "Malicious User Name"
        }

        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["execution"]["executedByName"] == "Test Manual User"

        execution_id = data["execution"]["id"]
        record = db.query(ManualTestExecution).filter(ManualTestExecution.id == execution_id).first()
        assert record.executed_by_name == "Test Manual User"
        assert record.executed_by_id != "malicious-user-id"

    def test_prior_execution_deactivation_rule(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository, manual_test_case: ExternalTestCase, test_pr: PullRequest
    ):
        """Verify new execution deactivates prior active execution for same test and context."""
        url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/execution"
        
        # 1. Record first execution (FAILED)
        payload1 = {
            "outcome": "FAILED",
            "notes": "First attempt failed",
            "pullRequestId": str(test_pr.id)
        }
        res1 = client_with_auth.post(url, json=payload1)
        assert res1.status_code == 200
        id1 = res1.json()["execution"]["id"]

        # Verify first is active
        rec1 = db.query(ManualTestExecution).filter(ManualTestExecution.id == id1).first()
        assert rec1.is_active is True

        # 2. Record second execution (PASSED)
        payload2 = {
            "outcome": "PASSED",
            "notes": "Retried and passed",
            "pullRequestId": str(test_pr.id)
        }
        res2 = client_with_auth.post(url, json=payload2)
        assert res2.status_code == 200
        id2 = res2.json()["execution"]["id"]

        # Refresh database and verify first is now inactive, second is active
        db.refresh(rec1)
        assert rec1.is_active is False

        rec2 = db.query(ManualTestExecution).filter(ManualTestExecution.id == id2).first()
        assert rec2.is_active is True

    def test_get_manual_tests_latest_status_and_history(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository, manual_test_case: ExternalTestCase, test_pr: PullRequest
    ):
        """Verify GET manual-tests endpoint returns latest execution details and history count."""
        # Record two executions
        url_post = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/execution"
        client_with_auth.post(url_post, json={"outcome": "FAILED", "notes": "First attempt failed", "pullRequestId": str(test_pr.id)})
        client_with_auth.post(url_post, json={"outcome": "PASSED", "notes": "Second attempt passed", "evidenceUrl": "https://evidence.link", "pullRequestId": str(test_pr.id)})

        # Now call GET manual-tests
        url_get = f"/api/repositories/{test_repository.id}/pull-requests/{test_pr.id}/manual-tests"
        response = client_with_auth.get(url_get)
        assert response.status_code == 200
        data = response.json()
        
        tests = data["manual_tests"]
        assert len(tests) == 1
        test_info = tests[0]
        assert test_info["id"] == str(manual_test_case.id)
        assert test_info["execution_status"] == "PASSED"
        assert test_info["latestExecutionStatus"] == "PASSED"
        assert test_info["latestExecutionNotes"] == "Second attempt passed"
        assert test_info["latestEvidenceUrl"] == "https://evidence.link"
        assert test_info["latestExecutedByName"] == "Test Manual User"
        assert test_info["executionHistoryCount"] == 2

    def test_cross_workspace_blocked(
        self, client_with_auth: TestClient, db: Session, manual_test_case: ExternalTestCase
    ):
        """Verify users from other workspaces are blocked (403 MANUAL_TEST_WORKSPACE_ACCESS_DENIED)."""
        # Create a completely foreign repository/workspace
        other_workspace = Workspace(
            name="Foreign Workspace",
            slug=f"foreign-workspace-{uuid.uuid4().hex[:6]}"
        )
        db.add(other_workspace)
        db.commit()

        foreign_repo = Repository(
            name="foreign-repo",
            full_name="test-owner/foreign-repo",
            owner="test-owner",
            github_repo_id=9876543,
            workspace_id=other_workspace.id,
            is_active=True
        )
        db.add(foreign_repo)
        db.commit()

        url = f"/api/repositories/{foreign_repo.id}/manual-tests/{manual_test_case.id}/execution"
        payload = {"outcome": "PASSED", "notes": "Attempting cross-workspace edit"}

        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 403
        assert "MANUAL_TEST_WORKSPACE_ACCESS_DENIED" in response.json()["detail"]

        # Clean up foreign repo
        db.delete(foreign_repo)
        db.delete(other_workspace)
        db.commit()

    def test_legacy_path_behavior_with_resolvable_repository(
        self, client_with_auth: TestClient, db: Session, manual_test_case: ExternalTestCase
    ):
        """Verify legacy endpoint persists execution if repository can be safely derived from test case."""
        url = f"/api/repositories/manual-tests/{manual_test_case.id}/execution"
        payload = {"outcome": "PASSED", "notes": "Legacy path execution test"}

        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["execution"]["outcome"] == "PASSED"

    def test_legacy_path_behavior_unresolvable_repository(
        self, client_with_auth: TestClient, db: Session
    ):
        """Verify legacy endpoint returns 400 REPOSITORY_REQUIRED_FOR_MANUAL_EXECUTION if repository cannot be derived."""
        # Use a non-existent test case ID
        fake_id = uuid.uuid4()
        url = f"/api/repositories/manual-tests/{fake_id}/execution"
        payload = {"outcome": "PASSED", "notes": "Legacy path fake case"}

        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 400
        assert response.json()["detail"] == "REPOSITORY_REQUIRED_FOR_MANUAL_EXECUTION"

    def test_repository_test_mismatch_rejected(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository
    ):
        """Verify execution is rejected with 400 if test does not belong to specified repository."""
        # Create a second repository in the same workspace
        repo2 = Repository(
            name="another-repo",
            full_name="test-owner/another-repo",
            owner="test-owner",
            github_repo_id=7778889,
            workspace_id=test_repository.workspace_id,
            is_active=True
        )
        db.add(repo2)
        db.commit()
        db.refresh(repo2)

        # Create an integration connection for repo2
        connection2 = IntegrationConnection(
            id=uuid.uuid4(),
            workspace_id=repo2.workspace_id,
            repository_id=repo2.id,
            provider="MANUAL_CSV",
            display_name=f"Connection2-{uuid.uuid4().hex[:6]}",
            status="CONNECTED",
            is_active=True
        )
        db.add(connection2)
        db.commit()

        # Create a test case in repo2
        tc2 = ExternalTestCase(
            id=uuid.uuid4(),
            repository_id=repo2.id,
            workspace_id=repo2.workspace_id,
            integration_connection_id=connection2.id,
            external_id=f"ext2-{uuid.uuid4().hex}",
            title="Repo2 Test Case",
            provider="manual",
            external_key="TC-202",
            automation_status="MANUAL",
            is_active=True
        )
        db.add(tc2)
        db.commit()

        # Attempt to post to repository 1 with test case from repository 2
        url = f"/api/repositories/{test_repository.id}/manual-tests/{tc2.id}/execution"
        payload = {"outcome": "PASSED", "notes": "Mismatch test"}

        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 400
        assert "does not belong to the specified repository" in response.json()["detail"]

        # Clean up
        db.delete(tc2)
        db.delete(connection2)
        db.delete(repo2)
        db.commit()

    def test_runs_results_unchanged(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository, manual_test_case: ExternalTestCase
    ):
        """Verify manual test executions do not insert or alter TestRun or TestResult tables."""
        runs_before = db.query(TestRun).count()
        results_before = db.query(TestResult).count()

        url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/execution"
        payload = {"outcome": "PASSED", "notes": "Outcome validation"}
        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 200

        runs_after = db.query(TestRun).count()
        results_after = db.query(TestResult).count()

        assert runs_before == runs_after, "TestRun table must not change"
        assert results_before == results_after, "TestResult table must not change"
