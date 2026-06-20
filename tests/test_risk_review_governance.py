"""Governance integration tests for Risk Review.

Tests must prove:
- reset creates history row with reviewer attribution
- reset does not remain active
- effective risk returns to generated risk after reset
- multiple active reviews are blocked
- evidence truth remains unchanged
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.recommendation import RecommendationRun
from app.models.risk_review import RiskReview
from app.models.user import User, WorkspaceMember
from app.models.repository import Repository
from app.services.risk_review_service import RiskReviewService
from app.dependencies.auth import get_current_user, require_workspace_member


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
def test_recommendation_run(db: Session):
    return db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).first()


@pytest.fixture
def client_with_auth(db: Session, test_user: User, test_recommendation_run: RecommendationRun):
    # Ensure user is a member of the run's repository workspace
    repo = db.query(Repository).filter(Repository.id == test_recommendation_run.repository_id).first()
    if repo:
        existing_member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == repo.workspace_id,
            WorkspaceMember.user_id == test_user.id
        ).first()
        if not existing_member:
            member = WorkspaceMember(
                id=uuid.uuid4(),
                workspace_id=repo.workspace_id,
                user_id=test_user.id,
                role="owner"
            )
            db.add(member)
            db.commit()

    def override_get_current_user():
        db_sess = SessionLocal()
        try:
            return db_sess.query(User).filter(User.id == test_user.id).first()
        finally:
            db_sess.close()

    def override_require_workspace_member():
        return lambda: None  # bypass global workspace checks

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_workspace_member] = override_require_workspace_member

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


class TestRiskReviewGovernance:
    def test_reset_creates_inactive_history_row(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session, test_user: User):
        """Verify reset deactivates current review and inserts an inactive RESET row with attribution."""
        run_id = test_recommendation_run.id
        snapshot_hash = RiskReviewService.get_snapshot_hash(test_recommendation_run)
        
        # Clear existing reviews
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()
        
        # Get reviewable gaps
        res = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        items = res.json()["items"]
        gap = items[0]
        
        # Submit active override
        res = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews",
            json={
                "readableId": gap["readableId"],
                "reviewStatus": "OVERRIDDEN",
                "reviewedRiskLevel": "LOW",
                "reviewedPriority": "P3",
                "reviewNote": "Overriding risk for testing resets",
                "snapshotHash": snapshot_hash
            }
        )
        assert res.status_code == 201
        review_id = res.json()["id"]
        
        # Verify it is active in DB
        active_db = db.query(RiskReview).filter(RiskReview.id == review_id).one()
        assert active_db.is_active is True
        
        # Reset via DELETE endpoint
        res = client_with_auth.delete(
            f"/api/recommendations/{run_id}/risk-reviews/{review_id}?snapshotHash={snapshot_hash}"
        )
        assert res.status_code == 200
        
        # Verify the original review is no longer active
        db.refresh(active_db)
        assert active_db.is_active is False
        
        # Verify a new history row was created with review_status="RESET" and is_active=False
        reset_row = db.query(RiskReview).filter(
            RiskReview.recommendation_run_id == run_id,
            RiskReview.review_status == "RESET"
        ).order_by(RiskReview.created_at.desc()).first()
        
        assert reset_row is not None
        assert reset_row.is_active is False
        assert reset_row.reviewer_id == str(test_user.id)
        assert reset_row.reviewer_name == (test_user.name or test_user.email)
        assert reset_row.source_snapshot_hash == snapshot_hash
        assert reset_row.created_at is not None

    def test_effective_risk_returns_to_generated_after_reset(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Verify that after reset, the effective risk of the item returns to generated (original) risk."""
        run_id = test_recommendation_run.id
        snapshot_hash = RiskReviewService.get_snapshot_hash(test_recommendation_run)
        
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()
        
        # Get baseline gaps
        res = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        items = res.json()["items"]
        gap = items[0]
        
        orig_risk = gap["originalRiskLevel"]
        orig_priority = gap["originalPriority"]
        
        # Override to something else
        temp_risk = "LOW" if orig_risk != "LOW" else "HIGH"
        temp_priority = "P3" if orig_priority != "P3" else "P1"
        
        res = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews",
            json={
                "readableId": gap["readableId"],
                "reviewStatus": "OVERRIDDEN",
                "reviewedRiskLevel": temp_risk,
                "reviewedPriority": temp_priority,
                "reviewNote": "Temporary override note",
                "snapshotHash": snapshot_hash
            }
        )
        print("POST STATUS:", res.status_code)
        print("POST RESPONSE:", res.json())
        assert res.status_code == 201
        
        # Verify effective risk is overridden
        res = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        print("GET STATUS:", res.status_code)
        print("GET RESPONSE:", res.json())
        gap_after_override = [i for i in res.json()["items"] if i["readableId"] == gap["readableId"]][0]
        assert gap_after_override["effectiveRiskLevel"] == temp_risk
        assert gap_after_override["effectivePriority"] == temp_priority
        assert gap_after_override["reviewStatus"] == "OVERRIDDEN"
        
        # Reset by item POST endpoint
        res = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews/reset",
            json={
                "sourceRequirementId": gap["sourceRequirementId"],
                "snapshotHash": snapshot_hash
            }
        )
        assert res.status_code == 200
        
        # Verify it returned to original generated risk and status is UNREVIEWED
        res = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        gap_after_reset = [i for i in res.json()["items"] if i["readableId"] == gap["readableId"]][0]
        assert gap_after_reset["effectiveRiskLevel"] == orig_risk
        assert gap_after_reset["effectivePriority"] == orig_priority
        assert gap_after_reset["reviewStatus"] == "UNREVIEWED"

    def test_multiple_active_reviews_blocked(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session, test_user: User):
        """Verify that mutations are blocked (returning HTTP 500) if multiple active reviews exist for a requirement."""
        run_id = test_recommendation_run.id
        snapshot_hash = RiskReviewService.get_snapshot_hash(test_recommendation_run)
        
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()
        
        res = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        items = res.json()["items"]
        gap = items[0]
        
        # Manually bypass safety checks to insert multiple active reviews in the DB (simulating a DB corruption or race condition)
        rev1 = RiskReview(
            id=uuid.uuid4(),
            recommendation_run_id=run_id,
            source_requirement_id=gap["sourceRequirementId"],
            original_risk_level=gap["originalRiskLevel"],
            original_priority=gap["originalPriority"],
            reviewed_risk_level="LOW",
            reviewed_priority="P3",
            review_status="ACCEPTED",
            reviewer_id=str(test_user.id),
            reviewer_name=test_user.name,
            source_snapshot_hash=snapshot_hash,
            is_active=True
        )
        rev2 = RiskReview(
            id=uuid.uuid4(),
            recommendation_run_id=run_id,
            source_requirement_id=gap["sourceRequirementId"],
            original_risk_level=gap["originalRiskLevel"],
            original_priority=gap["originalPriority"],
            reviewed_risk_level="HIGH",
            reviewed_priority="P1",
            review_status="OVERRIDDEN",
            reviewer_id=str(test_user.id),
            reviewer_name=test_user.name,
            source_snapshot_hash=snapshot_hash,
            is_active=True
        )
        
        db_blocked = False
        try:
            db.add_all([rev1, rev2])
            db.commit()
        except Exception as e:
            db.rollback()
            db_blocked = True
            
        if db_blocked:
            # The database level unique index successfully blocked multiple active reviews!
            return
            
        # Now try to submit a new review for the same requirement
        res = client_with_auth.post(
            f"/api/recommendations/{run_id}/risk-reviews",
            json={
                "readableId": gap["readableId"],
                "reviewStatus": "ACCEPTED",
                "snapshotHash": snapshot_hash
            }
        )
        assert res.status_code == 500
        assert "MULTIPLE_ACTIVE_REVIEWS_DETECTED" in res.json()["detail"]
        assert "REVIEW_HISTORY_INCONSISTENT" in res.json()["detail"]
        
        # Clean up
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()

    def test_evidence_truth_remains_unchanged(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Verify evidence report counts remain exactly as baseline."""
        run_id = test_recommendation_run.id
        
        res = client_with_auth.get(f"/api/recommendations/{run_id}/evidence-report?format=json")
        assert res.status_code == 200
        data = res.json()
        report_data = data["report"]
        
        # Verify baseline counts
        coverage = report_data["acceptance_criteria_coverage"]
        assert coverage["total"] == 25
        assert coverage["covered"] == 16
        assert coverage["partially_supported"] == 2
        assert coverage["missing"] == 7
        assert coverage["traceability_review_needed"] == 0
        assert report_data["health"] == "VALIDATION_PASSED_COVERAGE_INCOMPLETE"
