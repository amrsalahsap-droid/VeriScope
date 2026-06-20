"""Integration tests for Risk Review history endpoint and audit trailing.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.recommendation import RecommendationRun
from app.models.risk_review import RiskReview
from app.models.user import User, Workspace, WorkspaceMember
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
def foreign_run(db: Session):
    run = db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).first()
    repo = db.query(Repository).filter(Repository.id == run.repository_id).first()
    original_workspace_id = repo.workspace_id
    
    fw = Workspace(
        id=uuid.uuid4(),
        name="Foreign Workspace History",
        slug="foreign-workspace-history"
    )
    db.add(fw)
    db.commit()
    
    repo.workspace_id = fw.id
    db.commit()
    
    try:
        yield run
    finally:
        repo.workspace_id = original_workspace_id
        db.commit()
        db.delete(fw)
        db.commit()


@pytest.fixture
def client_with_auth(db: Session, test_user: User, test_recommendation_run: RecommendationRun):
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
        return lambda: None

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_workspace_member] = override_require_workspace_member

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


class TestRiskReviewHistory:
    def test_history_all_review_events_for_all_gaps(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session, test_user: User):
        run_id = test_recommendation_run.id
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()

        # Get gaps
        res = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        gaps_data = res.json()
        items = gaps_data["items"]
        snapshot_hash = gaps_data["snapshotHash"]
        assert len(items) > 0
        gap = items[0]

        # Submit active override
        payload = {
            "sourceRequirementId": gap["sourceRequirementId"],
            "sourceAcNumber": gap["sourceAcNumber"],
            "readableId": gap["readableId"],
            "reviewStatus": "OVERRIDDEN",
            "reviewedRiskLevel": "CRITICAL",
            "reviewedPriority": "P0",
            "reviewNote": "Overridden note",
            "snapshotHash": snapshot_hash
        }
        res_post = client_with_auth.post(f"/api/recommendations/{run_id}/risk-reviews", json=payload)
        assert res_post.status_code == 201

        # Accept
        payload["reviewStatus"] = "ACCEPTED"
        payload["reviewNote"] = None
        client_with_auth.post(f"/api/recommendations/{run_id}/risk-reviews", json=payload)

        # Needs discussion
        payload["reviewStatus"] = "NEEDS_DISCUSSION"
        payload["reviewNote"] = "Needs discussion note"
        client_with_auth.post(f"/api/recommendations/{run_id}/risk-reviews", json=payload)

        # Reset
        reset_payload = {
            "sourceRequirementId": gap["sourceRequirementId"],
            "sourceAcNumber": gap["sourceAcNumber"],
            "snapshotHash": snapshot_hash,
            "reviewNote": "Resetting it"
        }
        client_with_auth.post(f"/api/recommendations/{run_id}/risk-reviews/reset", json=reset_payload)

        # Fetch history
        res_history = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews/history")
        assert res_history.status_code == 200
        history_data = res_history.json()

        # Find the gap item in history
        history_item = next((item for item in history_data["items"] if item["readableId"] == gap["readableId"]), None)
        assert history_item is not None
        assert len(history_item["history"]) == 4

        event_types = [h["eventType"] for h in history_item["history"]]
        assert "OVERRIDDEN" in event_types
        assert "ACCEPTED" in event_types
        assert "NEEDS_DISCUSSION" in event_types
        assert "RESET" in event_types

        # Clean up
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()

    def test_history_filter_by_source_ac_number(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        run_id = test_recommendation_run.id
        res = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        items = res.json()["items"]
        gap = next((item for item in items if item["sourceAcNumber"] is not None), None)
        assert gap is not None

        ac_num = gap["sourceAcNumber"]
        res_history = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews/history?sourceAcNumber={ac_num}")
        assert res_history.status_code == 200
        history_data = res_history.json()
        assert len(history_data["items"]) == 1
        assert history_data["items"][0]["sourceAcNumber"] == ac_num

    def test_history_filter_by_readable_id(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        run_id = test_recommendation_run.id
        res = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        items = res.json()["items"]
        gap = items[0]
        readable_id = gap["readableId"]

        res_history = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews/history?readableId={readable_id}")
        assert res_history.status_code == 200
        history_data = res_history.json()
        assert len(history_data["items"]) == 1
        assert history_data["items"][0]["readableId"] == readable_id

    def test_history_reset_is_inactive(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        run_id = test_recommendation_run.id
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()

        res = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        gap = res.json()["items"][0]
        snapshot_hash = res.json()["snapshotHash"]

        # Post override
        payload = {
            "sourceRequirementId": gap["sourceRequirementId"],
            "sourceAcNumber": gap["sourceAcNumber"],
            "readableId": gap["readableId"],
            "reviewStatus": "OVERRIDDEN",
            "reviewedRiskLevel": "CRITICAL",
            "reviewedPriority": "P0",
            "reviewNote": "Overridden note",
            "snapshotHash": snapshot_hash
        }
        client_with_auth.post(f"/api/recommendations/{run_id}/risk-reviews", json=payload)

        # Reset
        reset_payload = {
            "sourceRequirementId": gap["sourceRequirementId"],
            "sourceAcNumber": gap["sourceAcNumber"],
            "snapshotHash": snapshot_hash
        }
        client_with_auth.post(f"/api/recommendations/{run_id}/risk-reviews/reset", json=reset_payload)

        res_history = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews/history")
        history_item = next((item for item in res_history.json()["items"] if item["readableId"] == gap["readableId"]), None)
        assert history_item is not None
        
        reset_event = next((e for e in history_item["history"] if e["eventType"] == "RESET"), None)
        assert reset_event is not None
        assert reset_event["isActive"] is False

        # Clean up
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()

    def test_effective_risk_returns_to_generated_after_reset(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        run_id = test_recommendation_run.id
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()

        res = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        gap = res.json()["items"][0]
        snapshot_hash = res.json()["snapshotHash"]
        original_risk = gap["originalRiskLevel"]

        # Post override
        payload = {
            "sourceRequirementId": gap["sourceRequirementId"],
            "sourceAcNumber": gap["sourceAcNumber"],
            "readableId": gap["readableId"],
            "reviewStatus": "OVERRIDDEN",
            "reviewedRiskLevel": "CRITICAL",
            "reviewedPriority": "P0",
            "reviewNote": "Overridden note",
            "snapshotHash": snapshot_hash
        }
        client_with_auth.post(f"/api/recommendations/{run_id}/risk-reviews", json=payload)

        # Reset
        reset_payload = {
            "sourceRequirementId": gap["sourceRequirementId"],
            "sourceAcNumber": gap["sourceAcNumber"],
            "snapshotHash": snapshot_hash
        }
        client_with_auth.post(f"/api/recommendations/{run_id}/risk-reviews/reset", json=reset_payload)

        # Fetch history and check effective risk
        res_history = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews/history")
        history_item = next((item for item in res_history.json()["items"] if item["readableId"] == gap["readableId"]), None)
        assert history_item is not None
        assert history_item["currentEffectiveRiskLevel"] == original_risk
        assert history_item["currentReviewStatus"] == "UNREVIEWED"

        # Clean up
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()

    def test_transition_summary_counts(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        run_id = test_recommendation_run.id
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()

        res = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews")
        gap = res.json()["items"][0]
        snapshot_hash = res.json()["snapshotHash"]

        # Post override
        payload = {
            "sourceRequirementId": gap["sourceRequirementId"],
            "sourceAcNumber": gap["sourceAcNumber"],
            "readableId": gap["readableId"],
            "reviewStatus": "OVERRIDDEN",
            "reviewedRiskLevel": "CRITICAL",
            "reviewedPriority": "P0",
            "reviewNote": "Overridden note",
            "snapshotHash": snapshot_hash
        }
        client_with_auth.post(f"/api/recommendations/{run_id}/risk-reviews", json=payload)

        # Reset
        reset_payload = {
            "sourceRequirementId": gap["sourceRequirementId"],
            "sourceAcNumber": gap["sourceAcNumber"],
            "snapshotHash": snapshot_hash
        }
        client_with_auth.post(f"/api/recommendations/{run_id}/risk-reviews/reset", json=reset_payload)

        # Fetch history
        res_history = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews/history")
        history_item = next((item for item in res_history.json()["items"] if item["readableId"] == gap["readableId"]), None)
        assert history_item is not None
        assert history_item["totalEvents"] == 2
        assert history_item["resetCount"] == 1
        assert history_item["overrideCount"] == 1
        assert history_item["needsDiscussionCount"] == 0
        assert history_item["acceptedCount"] == 0
        assert history_item["firstReviewedAt"] is not None
        assert history_item["lastReviewedAt"] is not None
        assert history_item["lastReviewerName"] is not None

        # Clean up
        db.query(RiskReview).filter(RiskReview.recommendation_run_id == run_id).delete()
        db.commit()

    def test_normal_mode_hides_ids(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        run_id = test_recommendation_run.id
        res_history = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews/history?audit=false")
        assert res_history.status_code == 200
        data = res_history.json()

        assert data["recommendationRunId"] is None
        assert data["snapshotHash"] is None
        for item in data["items"]:
            assert item["sourceRequirementId"] is None
            for event in item["history"]:
                assert event["reviewId"] is None
                assert event["reviewerId"] is None
                assert event["sourceSnapshotHash"] is None

    def test_audit_mode_exposes_ids(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        run_id = test_recommendation_run.id
        res_history = client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews/history?audit=true")
        assert res_history.status_code == 200
        data = res_history.json()

        assert data["recommendationRunId"] == str(run_id)
        assert data["snapshotHash"] is not None
        for item in data["items"]:
            if item["history"]:
                assert item["sourceRequirementId"] is not None
                for event in item["history"]:
                    assert event["reviewId"] is not None
                    assert event["reviewerId"] is not None
                    assert event["sourceSnapshotHash"] is not None

    def test_foreign_workspace_access_blocked(self, client_with_auth: TestClient, foreign_run: RecommendationRun):
        res = client_with_auth.get(f"/api/recommendations/{foreign_run.id}/risk-reviews/history")
        assert res.status_code == 403
        assert res.json()["detail"] == "REVIEW_WORKSPACE_ACCESS_DENIED"

    def test_history_endpoint_does_not_change_evidence_counts(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun):
        run_id = test_recommendation_run.id
        
        # 1. Get evidence report counts before fetching history
        res_report1 = client_with_auth.get(f"/api/recommendations/{run_id}/evidence-report?format=json")
        data1 = res_report1.json()["report"]
        count1 = data1["acceptance_criteria_coverage"]["total"]

        # 2. Fetch history
        client_with_auth.get(f"/api/recommendations/{run_id}/risk-reviews/history")

        # 3. Get evidence report counts after fetching history
        res_report2 = client_with_auth.get(f"/api/recommendations/{run_id}/evidence-report?format=json")
        data2 = res_report2.json()["report"]
        count2 = data2["acceptance_criteria_coverage"]["total"]

        assert count1 == count2

    def test_report_includes_history_timeline(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun):
        run_id = test_recommendation_run.id
        res_report = client_with_auth.get(f"/api/recommendations/{run_id}/evidence-report?format=markdown")
        assert res_report.status_code == 200
        markdown = res_report.json()["markdown_content"]

        assert "## Business Risk Review Decisions" in markdown
        assert "Advisory Warning:" in markdown
        assert "Governance Summary" in markdown
        assert "History Timeline" in markdown

    def test_report_says_ready_no(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun):
        run_id = test_recommendation_run.id
        res_report = client_with_auth.get(f"/api/recommendations/{run_id}/evidence-report?format=markdown")
        markdown = res_report.json()["markdown_content"]
        assert "Ready: yes" not in markdown
