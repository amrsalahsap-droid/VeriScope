"""Authorization/BOLA integration tests for Risk Review and evidence endpoints.

Ensures that foreign workspace access is blocked on:
- all 5 risk review endpoints
- all 3 endpoints exposing risk review data (regression-evidence, create-targeted-scope, evidence-report)
returning HTTP 403 REVIEW_WORKSPACE_ACCESS_DENIED.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.recommendation import RecommendationRun
from app.models.user import User, Workspace
from app.models.repository import Repository
from app.dependencies.auth import get_current_user, get_current_workspace, require_workspace_member


@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




@pytest.fixture
def test_user(db: Session):
    return db.query(User).first()


@pytest.fixture
def foreign_run(db: Session):
    """Temporarily move the repository of a real recommendation run to a foreign workspace."""
    run = db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).first()
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    original_workspace_id = repo.workspace_id
    
    # Create a foreign workspace
    fw = Workspace(
        id=uuid.uuid4(),
        name="Foreign Workspace",
        slug="foreign-workspace"
    )
    db.add(fw)
    db.commit()
    
    # Temporarily associate the repository with the foreign workspace
    repo.workspace_id = fw.id
    db.commit()
    
    try:
        yield run
    finally:
        # Revert the association
        repo.workspace_id = original_workspace_id
        db.commit()
        db.delete(fw)
        db.commit()



@pytest.fixture
def client_with_auth(test_user: User):
    def override_get_current_user():
        db = SessionLocal()
        try:
            return db.query(User).filter(User.id == test_user.id).first()
        finally:
            db.close()

    def override_require_workspace_member():
        return lambda: None  # bypass global workspace checks

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_workspace_member] = override_require_workspace_member

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


class TestRiskReviewAuthorization:
    def test_get_risk_reviews_blocked(self, client_with_auth: TestClient, foreign_run: RecommendationRun):
        response = client_with_auth.get(f"/api/recommendations/{foreign_run.id}/risk-reviews")
        assert response.status_code == 403
        assert response.json()["detail"] == "REVIEW_WORKSPACE_ACCESS_DENIED"

    def test_submit_risk_review_blocked(self, client_with_auth: TestClient, foreign_run: RecommendationRun):
        response = client_with_auth.post(
            f"/api/recommendations/{foreign_run.id}/risk-reviews",
            json={
                "readableId": "AC-1",
                "reviewStatus": "ACCEPTED",
                "snapshotHash": "some_hash"
            }
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "REVIEW_WORKSPACE_ACCESS_DENIED"

    def test_bulk_accept_blocked(self, client_with_auth: TestClient, foreign_run: RecommendationRun):
        response = client_with_auth.post(
            f"/api/recommendations/{foreign_run.id}/risk-reviews/bulk-accept",
            json={
                "snapshotHash": "some_hash"
            }
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "REVIEW_WORKSPACE_ACCESS_DENIED"

    def test_delete_risk_review_blocked(self, client_with_auth: TestClient, foreign_run: RecommendationRun):
        review_id = uuid.uuid4()
        response = client_with_auth.delete(
            f"/api/recommendations/{foreign_run.id}/risk-reviews/{review_id}"
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "REVIEW_WORKSPACE_ACCESS_DENIED"

    def test_reset_risk_review_blocked(self, client_with_auth: TestClient, foreign_run: RecommendationRun):
        response = client_with_auth.post(
            f"/api/recommendations/{foreign_run.id}/risk-reviews/reset",
            json={
                "sourceRequirementId": "req-1",
                "snapshotHash": "some_hash"
            }
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "REVIEW_WORKSPACE_ACCESS_DENIED"

    def test_regression_evidence_blocked(self, client_with_auth: TestClient, foreign_run: RecommendationRun):
        response = client_with_auth.get(f"/api/recommendations/{foreign_run.id}/regression-evidence")
        assert response.status_code == 403
        assert response.json()["detail"] == "REVIEW_WORKSPACE_ACCESS_DENIED"

    def test_create_targeted_scope_blocked(self, client_with_auth: TestClient, foreign_run: RecommendationRun):
        response = client_with_auth.post(
            f"/api/recommendations/{foreign_run.id}/create-targeted-scope",
            json={
                "scope_type": "REQUIRED_ONLY",
                "include_business_context": True
            }
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "REVIEW_WORKSPACE_ACCESS_DENIED"

    def test_evidence_report_blocked(self, client_with_auth: TestClient, foreign_run: RecommendationRun):
        response = client_with_auth.get(f"/api/recommendations/{foreign_run.id}/evidence-report")
        assert response.status_code == 403
        assert response.json()["detail"] == "REVIEW_WORKSPACE_ACCESS_DENIED"
