"""Authenticated integration tests for Risk Review Workflow (Phase 2.2)

Uses FastAPI TestClient with dependency override for authenticated user/workspace.
Tests the complete end-to-end risk review workflow through real API endpoints.

Acceptance truth that must remain unchanged:
* total ACs: 25
* current PR tests: 18
* passed tests: 18
* covered ACs: 16
* partial ACs: 2
* missing ACs: 7
* traceability review: 0
* health: VALIDATION_PASSED_COVERAGE_INCOMPLETE
* Ready shown: no
* required scope items: 7
* review scope items: 2
* verified excluded: 16
* passed tests excluded: 18
* business gaps: 9
"""

import pytest
import uuid
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal, engine
from app.models.recommendation import RecommendationRun
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.risk_review import RiskReview
from app.services.risk_review_service import RiskReviewService
from app.dependencies.auth import get_current_user, get_current_workspace, require_workspace_member


# Test fixtures
@pytest.fixture
def db():
    """Database session fixture."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




@pytest.fixture
def test_user(db: Session):
    """Get existing test user from seeded data."""
    return db.query(User).first()


@pytest.fixture
def test_repository(db: Session):
    """Get existing test repository from seeded data."""
    repo = db.query(Repository).filter(Repository.name == "password-validation-demo").first()
    if not repo:
        repo = db.query(Repository).first()
    return repo


@pytest.fixture
def test_recommendation_run(db: Session, test_repository: Repository):
    """Get existing recommendation run from seeded data."""
    run = db.query(RecommendationRun).filter(RecommendationRun.repository_id == test_repository.id).order_by(RecommendationRun.created_at.desc()).first()
    if not run:
        run = db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).first()
    return run


@pytest.fixture
def test_workspace(db: Session, test_user: User, test_repository: Repository):
    """Get existing test workspace from seeded data."""
    workspace = db.query(Workspace).filter(Workspace.id == test_repository.workspace_id).first()
    if not workspace:
        workspace = db.query(Workspace).first()
    
    # Ensure user is a workspace member
    existing_member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace.id,
        WorkspaceMember.user_id == test_user.id
    ).first()
    if not existing_member:
        member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            user_id=test_user.id,
            role="owner"
        )
        db.add(member)
        db.commit()
    
    return workspace


@pytest.fixture
def client_with_auth(test_user: User, test_workspace: Workspace):
    """TestClient with auth dependency override."""
    db = SessionLocal()
    
    def override_get_current_user():
        # Re-query to get a fresh instance attached to session
        return db.query(User).filter(User.id == test_user.id).first()
    
    def override_get_current_workspace():
        # Re-query to get a fresh instance attached to session
        return db.query(Workspace).filter(Workspace.id == test_workspace.id).first()
    
    def override_require_workspace_member():
        return lambda: None  # Pass-through
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_workspace] = override_get_current_workspace
    app.dependency_overrides[require_workspace_member] = override_require_workspace_member
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()
    db.close()


class TestRiskReviewIntegration:
    """End-to-end integration tests for risk review workflow."""
    
    def test_baseline_risk_reviews_empty(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun):
        """Test baseline - no reviews exist initially."""
        run_id = test_recommendation_run.id
        
        response = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        assert response.status_code == 200
        
        data = response.json()
        assert data["recommendationRunId"] == str(run_id)
        assert data["totalReviewableGaps"] == 9  # 7 missing + 2 partial
        assert data["reviewedCount"] == 0
        assert data["unreviewedCount"] == 9
        assert len(data["items"]) == 9
    
    def test_accept_generated_risk(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Test accepting generated risk for a missing/partial item."""
        run_id = test_recommendation_run.id
        snapshot_hash = RiskReviewService.get_snapshot_hash(test_recommendation_run)
        
        # Clear any existing reviews for this run to avoid conflicts
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()
        
        # Get a reviewable gap
        response = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        assert response.status_code == 200
        items = response.json()["items"]
        first_gap = items[0]
        
        # Accept the risk using readableId for stable identification
        response = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews",
            json={
                "readableId": first_gap["readableId"],
                "reviewStatus": "ACCEPTED",
                "snapshotHash": snapshot_hash
            }
        )
        if response.status_code not in (200, 201):
            print(f"ERROR: Status {response.status_code}")
            print(f"Response: {response.text}")
        assert response.status_code in (200, 201)
        
        data = response.json()
        assert data["review_status"] == "ACCEPTED"
        assert data["reviewed_risk_level"] == data["original_risk_level"]
        assert data["reviewed_priority"] == data["original_priority"]
        
        # Verify review persisted
        reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run_id,
            RiskReview.readable_id == first_gap["readableId"],
            RiskReview.is_active == True
        ).all()
        assert len(reviews) == 1
        assert reviews[0].review_status == "ACCEPTED"
    
    def test_override_risk_with_note(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Test overriding risk with a note."""
        run_id = test_recommendation_run.id
        snapshot_hash = RiskReviewService.get_snapshot_hash(test_recommendation_run)
        
        # Clear any existing reviews for this run to avoid conflicts
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()
        
        # Get a reviewable gap
        response = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        items = response.json()["items"]
        # Find an unreviewed gap
        unreviewed = [i for i in items if i["reviewStatus"] == "UNREVIEWED"][0]
        
        # Override the risk using readableId
        response = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews",
            json={
                "readableId": unreviewed["readableId"],
                "reviewStatus": "OVERRIDDEN",
                "reviewedRiskLevel": "CRITICAL",
                "reviewedPriority": "P0",
                "reviewNote": "Manual QA lead escalation for release review.",
                "snapshotHash": snapshot_hash
            }
        )
        assert response.status_code in (200, 201)
        
        data = response.json()
        assert data["review_status"] == "OVERRIDDEN"
        assert data["reviewed_risk_level"] == "CRITICAL"
        assert data["reviewed_priority"] == "P0"
        assert data["review_note"] == "Manual QA lead escalation for release review."
        
        # Verify review persisted
        reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run_id,
            RiskReview.readable_id == unreviewed["readableId"],
            RiskReview.is_active == True
        ).all()
        assert len(reviews) == 1
        assert reviews[0].review_status == "OVERRIDDEN"
        assert reviews[0].reviewed_risk_level == "CRITICAL"
        assert reviews[0].review_note == "Manual QA lead escalation for release review."
    
    def test_override_without_note_rejected(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Test that override without note is rejected."""
        run_id = test_recommendation_run.id
        snapshot_hash = RiskReviewService.get_snapshot_hash(test_recommendation_run)
        
        # Clear any existing reviews for this run to avoid conflicts
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()
        
        # Get a reviewable gap
        response = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        items = response.json()["items"]
        unreviewed = [i for i in items if i["reviewStatus"] == "UNREVIEWED"][0]
        
        # Try override without note using readableId
        response = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews",
            json={
                "readableId": unreviewed["readableId"],
                "reviewStatus": "OVERRIDDEN",
                "reviewedRiskLevel": "MEDIUM",
                "reviewedPriority": "P2",
                "reviewNote": None,
                "snapshotHash": snapshot_hash
            }
        )
        assert response.status_code == 400
        
        # Verify no review saved
        reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run_id,
            RiskReview.readable_id == unreviewed["readableId"],
            RiskReview.is_active == True
        ).all()
        assert len(reviews) == 0
    
    def test_needs_discussion_with_note(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Test needs discussion with note."""
        run_id = test_recommendation_run.id
        snapshot_hash = RiskReviewService.get_snapshot_hash(test_recommendation_run)
        
        # Clear any existing reviews for this run to avoid conflicts
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()
        
        # Get a reviewable gap
        response = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        items = response.json()["items"]
        unreviewed = [i for i in items if i["reviewStatus"] == "UNREVIEWED"][0]
        
        # Mark as needs discussion using readableId
        response = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews",
            json={
                "readableId": unreviewed["readableId"],
                "reviewStatus": "NEEDS_DISCUSSION",
                "reviewNote": "Requires team discussion before release.",
                "snapshotHash": snapshot_hash
            }
        )
        assert response.status_code in (200, 201)
        
        data = response.json()
        assert data["review_status"] == "NEEDS_DISCUSSION"
        assert data["review_note"] == "Requires team discussion before release."
        
        # Verify review persisted
        reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run_id,
            RiskReview.readable_id == unreviewed["readableId"],
            RiskReview.is_active == True
        ).all()
        assert len(reviews) == 1
        assert reviews[0].review_status == "NEEDS_DISCUSSION"
    
    def test_needs_discussion_without_note_rejected(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Test that needs discussion without note is rejected."""
        run_id = test_recommendation_run.id
        snapshot_hash = RiskReviewService.get_snapshot_hash(test_recommendation_run)
        
        # Clear any existing reviews for this run to avoid conflicts
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()
        
        # Get a reviewable gap
        response = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        items = response.json()["items"]
        unreviewed = [i for i in items if i["reviewStatus"] == "UNREVIEWED"][0]
        
        # Try needs discussion without note using readableId
        response = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews",
            json={
                "readableId": unreviewed["readableId"],
                "reviewStatus": "NEEDS_DISCUSSION",
                "reviewNote": None,
                "snapshotHash": snapshot_hash
            }
        )
        assert response.status_code == 400
        
        # Verify no review saved
        reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run_id,
            RiskReview.readable_id == unreviewed["readableId"],
            RiskReview.is_active == True
        ).all()
        assert len(reviews) == 0
    
    def test_reset_review(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Test resetting a review."""
        run_id = test_recommendation_run.id
        snapshot_hash = RiskReviewService.get_snapshot_hash(test_recommendation_run)
        
        # Clear any existing reviews for this run to avoid conflicts
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()
        
        # Get a reviewable gap
        response = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        items = response.json()["items"]
        unreviewed = [i for i in items if i["reviewStatus"] == "UNREVIEWED"][0]
        
        # Create a review first using readableId
        response = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews",
            json={
                "readableId": unreviewed["readableId"],
                "reviewStatus": "OVERRIDDEN",
                "reviewedRiskLevel": "LOW",
                "reviewedPriority": "P3",
                "reviewNote": "Test note",
                "snapshotHash": snapshot_hash
            }
        )
        assert response.status_code in (200, 201)
        review_id = response.json()["id"]
        
        # Reset the review
        response = client_with_auth.delete(
            f"/api/recommendations/{run_id}/risk-reviews/{review_id}?snapshotHash={snapshot_hash}"
        )
        assert response.status_code == 200
        
        # Verify review deactivated
        reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run_id,
            RiskReview.readable_id == unreviewed["readableId"],
            RiskReview.is_active == True
        ).all()
        assert len(reviews) == 0
    
    def test_bulk_accept_all(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Test bulk accepting all reviewable gaps."""
        run_id = test_recommendation_run.id
        snapshot_hash = RiskReviewService.get_snapshot_hash(test_recommendation_run)
        
        # Clear existing reviews
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()
        
        # Bulk accept all
        response = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews/bulk-accept",
            json={"snapshotHash": snapshot_hash}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["acceptedCount"] == 9
        assert data["totalReviewableGaps"] == 9
        
        # Verify all reviews persisted
        reviews = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run_id,
            RiskReview.is_active == True
        ).all()
        assert len(reviews) == 9
        assert all(r.review_status == "ACCEPTED" for r in reviews)
    
    def test_snapshot_mismatch_blocked(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Test that stale snapshot hash is rejected."""
        run_id = test_recommendation_run.id
        
        # Clear any existing reviews for this run to avoid conflicts
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()
        
        # Get a reviewable gap
        response = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        items = response.json()["items"]
        first_gap = items[0]
        
        # Try with wrong snapshot hash using readableId
        response = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews",
            json={
                "readableId": first_gap["readableId"],
                "reviewStatus": "ACCEPTED",
                "snapshotHash": "invalid_hash_12345"
            }
        )
        assert response.status_code == 409
        assert "REQUIRES_REGENERATION" in response.text
    


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
