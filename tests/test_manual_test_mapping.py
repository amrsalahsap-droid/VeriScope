"""Tests for Manual Test to Acceptance Criteria Mapping endpoints."""

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
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.manual_test_requirement_mapping import ManualTestRequirementMapping
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
    email = f"test-manual-map-{uuid.uuid4().hex[:6]}@example.com"
    user = User(
        email=email,
        name="Test Mapping User",
        auth_provider="github",
        provider_user_id=f"test-map-{uuid.uuid4().hex[:6]}"
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
        name="manual-map-repo",
        full_name=f"test-owner/map-repo-{uuid.uuid4().hex[:6]}",
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
def test_ac(db: Session, test_repository: Repository, test_pr: PullRequest):
    ac = AcceptanceCriterion(
        id=uuid.uuid4(),
        repository_id=test_repository.id,
        pull_request_id=test_pr.id,
        source_number=12,
        text="Weak passwords are rejected during sign-up",
        label="AC-12 Weak passwords are rejected during sign-up",
        normalized_key="ac-12-weak-passwords-rejected",
        source="PR_DESCRIPTION",
        confidence=1.0
    )
    db.add(ac)
    db.commit()
    db.refresh(ac)
    yield ac
    db.delete(ac)
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


class TestManualTestMapping:
    """Suite of tests covering backend requirements for Phase 6.1 manual mapping."""

    def test_create_mapping_success_uuid(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository, manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion
    ):
        """Verify endpoint creates manual test mapping using UUID successfully."""
        url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/mappings"
        payload = {
            "acceptanceCriterionId": str(test_ac.id)
        }

        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 200, response.text
        data = response.json()

        assert "id" in data
        assert data["testCaseId"] == str(manual_test_case.id)
        assert data["acceptanceCriterionId"] == str(test_ac.id)
        assert data["readableRequirementId"] == test_ac.label
        assert data["requirementText"] == test_ac.text
        assert data["mappingSource"] == "MANUAL"

        # Cleanup created mapping
        mapping = db.query(ManualTestRequirementMapping).filter(ManualTestRequirementMapping.id == data["id"]).first()
        if mapping:
            db.delete(mapping)
            db.commit()

    def test_create_mapping_success_source_number(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository, manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion
    ):
        """Verify endpoint creates mapping by source AC number fallbacks."""
        # Try with "AC-12"
        url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/mappings"
        payload = {
            "acceptanceCriterionId": "AC-12"
        }

        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["acceptanceCriterionId"] == str(test_ac.id)

        # Cleanup
        mapping = db.query(ManualTestRequirementMapping).filter(ManualTestRequirementMapping.id == data["id"]).first()
        if mapping:
            db.delete(mapping)
            db.commit()

        # Try with plain number "12"
        payload = {
            "acceptanceCriterionId": "12"
        }
        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["acceptanceCriterionId"] == str(test_ac.id)

        # Cleanup
        mapping = db.query(ManualTestRequirementMapping).filter(ManualTestRequirementMapping.id == data["id"]).first()
        if mapping:
            db.delete(mapping)
            db.commit()

    def test_create_mapping_success_label(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository, manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion
    ):
        """Verify endpoint creates mapping using label fallback."""
        url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/mappings"
        payload = {
            "acceptanceCriterionId": test_ac.label
        }

        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["acceptanceCriterionId"] == str(test_ac.id)

        # Cleanup
        mapping = db.query(ManualTestRequirementMapping).filter(ManualTestRequirementMapping.id == data["id"]).first()
        if mapping:
            db.delete(mapping)
            db.commit()

    def test_create_mapping_workspace_access_denied(
        self, client_with_auth: TestClient, db: Session, manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion
    ):
        """Verify workspace isolation check (403)."""
        random_repo_uuid = uuid.uuid4()
        url = f"/api/repositories/{random_repo_uuid}/manual-tests/{manual_test_case.id}/mappings"
        payload = {
            "acceptanceCriterionId": str(test_ac.id)
        }

        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 403
        assert "MANUAL_TEST_WORKSPACE_ACCESS_DENIED" in response.text

    def test_create_mapping_duplicate_blocked(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository, manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion
    ):
        """Verify duplicate active mapping is blocked (400)."""
        # Create first mapping
        url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/mappings"
        payload = {
            "acceptanceCriterionId": str(test_ac.id)
        }

        response = client_with_auth.post(url, json=payload)
        assert response.status_code == 200
        mapping_id = response.json()["id"]

        try:
            # Try to create exact same mapping again
            response2 = client_with_auth.post(url, json=payload)
            assert response2.status_code == 400
            assert "already exists" in response2.json()["detail"]
        finally:
            # Cleanup
            mapping = db.query(ManualTestRequirementMapping).filter(ManualTestRequirementMapping.id == mapping_id).first()
            if mapping:
                db.delete(mapping)
                db.commit()

    def test_create_mapping_cross_repo_blocked(
        self, client_with_auth: TestClient, db: Session, test_workspace: Workspace, test_repository: Repository, manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion
    ):
        """Verify cross repository mapping is blocked."""
        # Create another repository in the same workspace
        other_repo = Repository(
            name="other-repo",
            full_name=f"test-owner/other-repo-{uuid.uuid4().hex[:6]}",
            owner="test-owner",
            github_repo_id=int(uuid.uuid4().int % 10000000),
            workspace_id=test_workspace.id,
            is_active=True,
            selected_for_analysis=True
        )
        db.add(other_repo)
        db.commit()
        db.refresh(other_repo)

        try:
            # Try mapping to other repository via URL repository id of repo 1
            url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/mappings"
            
            # Create AC belonging to other repo
            other_ac = AcceptanceCriterion(
                id=uuid.uuid4(),
                repository_id=other_repo.id,
                pull_request_id=None,
                source_number=1,
                text="Some other criterion text",
                normalized_key="other-ac-norm",
                source="LINKED_STORY",
                confidence=1.0
            )
            db.add(other_ac)
            db.commit()

            try:
                payload = {
                    "acceptanceCriterionId": str(other_ac.id)
                }
                response = client_with_auth.post(url, json=payload)
                assert response.status_code == 400
                assert "does not belong to the specified repository" in response.json()["detail"]
            finally:
                db.delete(other_ac)
                db.commit()
        finally:
            db.delete(other_repo)
            db.commit()

    def test_get_and_delete_mappings(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository, manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion
    ):
        """Verify retrieving and deactivating (soft-deleting) mappings."""
        # Create a mapping
        mapping = ManualTestRequirementMapping(
            id=uuid.uuid4(),
            external_test_case_id=manual_test_case.id,
            acceptance_criterion_id=test_ac.id,
            repository_id=test_repository.id,
            mapping_source="MANUAL",
            is_active=True
        )
        db.add(mapping)
        db.commit()

        try:
            # Verify GET endpoint
            get_url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/mappings"
            response = client_with_auth.get(get_url)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == str(mapping.id)
            assert data[0]["readableRequirementId"] == test_ac.label

            # Verify DELETE endpoint (soft-delete)
            delete_url = f"/api/repositories/{test_repository.id}/manual-tests/{manual_test_case.id}/mappings/{mapping.id}"
            del_response = client_with_auth.delete(delete_url)
            assert del_response.status_code == 200
            assert del_response.json()["status"] == "SUCCESS"

            # Check that it is no longer returned by GET
            response_after = client_with_auth.get(get_url)
            assert response_after.status_code == 200
            assert len(response_after.json()) == 0

            # Double check in DB that is_active is now False
            db.refresh(mapping)
            assert mapping.is_active is False

        finally:
            db.delete(mapping)
            db.commit()
