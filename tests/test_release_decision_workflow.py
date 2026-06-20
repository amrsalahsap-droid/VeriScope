"""Release Decision Workflow Integration Tests.

Tests must prove:
- approve release
- reject release
- conditional approval
- reset decision
- snapshot mismatch rejection
- history generation
- immutable audit trail
- evidence counts remain unchanged
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.recommendation import RecommendationRun
from app.models.release_decision import ReleaseDecision
from app.models.release_decision_history import ReleaseDecisionHistory
from app.models.user import User, WorkspaceMember
from app.services.release_decision_service import ReleaseDecisionService


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
    """Create a test user."""
    user = db.query(User).filter(User.email == "test-release-decision@example.com").first()
    if not user:
        user = User(
            email="test-release-decision@example.com",
            name="Test Release Decision User",
            provider="github",
            provider_id="test-release-decision-123"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def test_workspace(db: Session, test_user: User):
    """Create a test workspace."""
    from app.models.user import Workspace
    workspace = db.query(Workspace).filter(Workspace.name == "Test Release Decision Workspace").first()
    if not workspace:
        workspace = Workspace(
            name="Test Release Decision Workspace",
            owner_id=test_user.id
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
    
    # Ensure user is owner
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace.id,
        WorkspaceMember.user_id == test_user.id
    ).first()
    if not member:
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=test_user.id,
            role="OWNER"
        )
        db.add(member)
        db.commit()
    
    return workspace


@pytest.fixture
def test_repository(db: Session, test_workspace: Workspace):
    """Create a test repository."""
    from app.models.repository import Repository
    repo = db.query(Repository).filter(Repository.name == "test-release-decision-repo").first()
    if not repo:
        repo = Repository(
            name="test-release-decision-repo",
            owner="test-owner",
            workspace_id=test_workspace.id,
            provider="github",
            provider_id="test-repo-123"
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
    return repo


@pytest.fixture
def test_recommendation_run(db: Session, test_repository: Repository):
    """Create a test recommendation run."""
    run = db.query(RecommendationRun).filter(
        RecommendationRun.repository_id == test_repository.id
    ).order_by(RecommendationRun.created_at.desc()).first()
    
    if not run:
        run = RecommendationRun(
            repository_id=test_repository.id,
            pull_request_id="test-pr-123",
            pull_request_number=1,
            head_sha="abc123def456",
            base_sha="def456abc123",
            status="COMPLETED",
            evidence_fingerprint="test-fingerprint-123",
            evidence_health_status="VALIDATION_PASSED_COVERAGE_INCOMPLETE"
        )
        db.add(run)
        db.commit()
        db.refresh(run)
    
    return run


@pytest.fixture
def client_with_auth(db: Session, test_user: User, test_recommendation_run: RecommendationRun, test_workspace: Workspace):
    from app.dependencies.auth import get_current_user
    from app.dependencies.authorization import validate_recommendation_run_access
    from app.dependencies.workspace import get_current_workspace

    def override_get_current_user():
        return test_user

    def override_get_current_workspace():
        return test_workspace

    def override_validate_access(db_session, run_id, user):
        run = db_session.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()
        if not run:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_workspace] = override_get_current_workspace
    app.dependency_overrides[validate_recommendation_run_access] = override_validate_access

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


class TestReleaseDecisionWorkflow:
    """Test release decision workflow end-to-end."""

    def test_approve_release(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session, test_user: User):
        """Verify release can be approved with valid snapshot hash."""
        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()

        res = client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved for release"
            }
        )
        assert res.status_code == 201

        data = res.json()
        assert data["decision_status"] == "APPROVED"
        assert data["approver_name"] == test_user.name
        assert data["snapshot_hash"] == snapshot_hash
        assert data["decision_note"] == "Approved for release"

        # Verify history was created
        decision = db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).first()
        assert decision is not None
        assert decision.decision_status == "APPROVED"

        history = db.query(ReleaseDecisionHistory).filter(ReleaseDecisionHistory.release_decision_id == decision.id).all()
        assert len(history) == 1
        assert history[0].event_type == "APPROVED"
        assert history[0].actor_name == test_user.name

    def test_reject_release_requires_note(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Verify rejection requires a decision note."""
        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()

        res = client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "REJECTED",
                "snapshot_hash": snapshot_hash
            }
        )
        assert res.status_code == 400
        assert "DECISION_NOTE_REQUIRED" in res.json()["detail"]

    def test_reject_release_with_note(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session, test_user: User):
        """Verify release can be rejected with a note."""
        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()

        res = client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "REJECTED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Rejected due to incomplete coverage"
            }
        )
        assert res.status_code == 201

        data = res.json()
        assert data["decision_status"] == "REJECTED"
        assert data["decision_note"] == "Rejected due to incomplete coverage"

    def test_conditional_approval_requires_note(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Verify conditional approval requires a decision note."""
        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()

        res = client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "CONDITIONALLY_APPROVED",
                "snapshot_hash": snapshot_hash
            }
        )
        assert res.status_code == 400
        assert "DECISION_NOTE_REQUIRED" in res.json()["detail"]

    def test_conditional_approval_with_note(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session, test_user: User):
        """Verify release can be conditionally approved with conditions."""
        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()

        res = client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "CONDITIONALLY_APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved pending manual QA review"
            }
        )
        assert res.status_code == 201

        data = res.json()
        assert data["decision_status"] == "CONDITIONALLY_APPROVED"
        assert data["decision_note"] == "Approved pending manual QA review"

    def test_reset_release_decision(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session, test_user: User):
        """Verify release decision can be reset to PENDING_REVIEW."""
        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # First approve
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()

        client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved for release"
            }
        )

        # Then reset
        res = client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision/reset",
            json={
                "snapshot_hash": snapshot_hash,
                "note": "Reset for re-evaluation"
            }
        )
        assert res.status_code == 200

        data = res.json()
        assert data["decision_status"] == "PENDING_REVIEW"
        assert data["approver_name"] is None
        assert data["decision_note"] is None

        # Verify history includes both APPROVED and RESET events
        decision = db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).first()
        history = db.query(ReleaseDecisionHistory).filter(ReleaseDecisionHistory.release_decision_id == decision.id).all()
        assert len(history) == 2
        assert history[0].event_type == "APPROVED"
        assert history[1].event_type == "RESET"

    def test_snapshot_mismatch_blocks_decision(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Verify snapshot mismatch blocks decision submission."""
        run_id = test_recommendation_run.id

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()

        res = client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "APPROVED",
                "snapshot_hash": "invalid-snapshot-hash",
                "decision_note": "Should fail"
            }
        )
        assert res.status_code == 409
        assert "RELEASE_SNAPSHOT_MISMATCH" in res.json()["detail"]

    def test_get_release_state(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Verify release state can be retrieved."""
        run_id = test_recommendation_run.id

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()

        # Initially should return None (no decision)
        res = client_with_auth.get(f"/api/recommendations/{run_id}/release-decision")
        assert res.status_code == 200
        assert res.json() is None

        # After creating a decision, should return state
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)
        client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved"
            }
        )

        res = client_with_auth.get(f"/api/recommendations/{run_id}/release-decision")
        assert res.status_code == 200
        data = res.json()
        assert data["decisionStatus"] == "APPROVED"
        assert data["approverName"] is not None

    def test_get_release_history(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Verify release history can be retrieved."""
        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()

        # Create decision with history
        client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "First approval"
            }
        )

        # Reset
        client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision/reset",
            json={
                "snapshot_hash": snapshot_hash,
                "note": "Reset"
            }
        )

        # Re-approve
        client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Second approval"
            }
        )

        # Get history
        res = client_with_auth.get(f"/api/recommendations/{run_id}/release-decision/history")
        assert res.status_code == 200
        data = res.json()
        assert data["totalEvents"] == 3
        assert data["decisionStatus"] == "APPROVED"

        # Verify timeline order
        events = data["history"]
        assert events[0]["eventType"] == "APPROVED"
        assert events[1]["eventType"] == "RESET"
        assert events[2]["eventType"] == "APPROVED"

    def test_audit_mode_exposes_ids(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Verify audit mode exposes internal IDs in history."""
        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()

        client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved"
            }
        )

        # Normal mode - IDs hidden
        res = client_with_auth.get(f"/api/recommendations/{run_id}/release-decision/history?audit=false")
        assert res.status_code == 200
        data = res.json()
        assert data["history"][0]["historyId"] is None
        assert data["history"][0]["actorId"] is None
        assert data["history"][0]["snapshotHash"] is None

        # Audit mode - IDs exposed
        res = client_with_auth.get(f"/api/recommendations/{run_id}/release-decision/history?audit=true")
        assert res.status_code == 200
        data = res.json()
        assert data["history"][0]["historyId"] is not None
        assert data["history"][0]["actorId"] is not None
        assert data["history"][0]["snapshotHash"] is not None

    def test_evidence_counts_unchanged_after_approval(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Verify evidence counts remain unchanged after release approval."""
        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Get baseline evidence counts
        res = client_with_auth.get(f"/api/recommendations/{run_id}/regression-evidence")
        assert res.status_code == 200
        baseline = res.json()
        baseline_counts = baseline["decisionSummary"]["counts"]

        # Approve release
        client_with_auth.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved"
            }
        )

        # Verify counts unchanged
        res = client_with_auth.get(f"/api/recommendations/{run_id}/regression-evidence")
        assert res.status_code == 200
        after = res.json()
        after_counts = after["decisionSummary"]["counts"]

        assert baseline_counts["totalRequirements"] == after_counts["totalRequirements"]
        assert baseline_counts["verifiedTests"] == after_counts["verifiedTests"]
        assert baseline_counts["missingAutomatedCoverage"] == after_counts["missingAutomatedCoverage"]
        assert baseline_counts["partiallySupported"] == after_counts["partiallySupported"]

    def test_blocking_health_status_blocks_decision(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Verify blocking health status blocks release decision."""
        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Temporarily set health status to blocking
        original_health = test_recommendation_run.evidence_health_status
        test_recommendation_run.evidence_health_status = "STALE_INPUTS"
        db.commit()

        try:
            res = client_with_auth.post(
                f"/api/recommendations/{run_id}/release-decision",
                json={
                    "decision_status": "APPROVED",
                    "snapshot_hash": snapshot_hash,
                    "decision_note": "Should fail"
                }
            )
            assert res.status_code == 400
            assert "RELEASE_DECISION_BLOCKED" in res.json()["detail"]
        finally:
            # Restore original health status
            test_recommendation_run.evidence_health_status = original_health
            db.commit()

    def test_allowed_health_status_allows_decision(self, client_with_auth: TestClient, test_recommendation_run: RecommendationRun, db: Session):
        """Verify allowed health status permits release decision."""
        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Set health status to allowed
        original_health = test_recommendation_run.evidence_health_status
        test_recommendation_run.evidence_health_status = "VALIDATION_PASSED_COVERAGE_INCOMPLETE"
        db.commit()

        try:
            res = client_with_auth.post(
                f"/api/recommendations/{run_id}/release-decision",
                json={
                    "decision_status": "APPROVED",
                    "snapshot_hash": snapshot_hash,
                    "decision_note": "Approved despite incomplete coverage"
                }
            )
            assert res.status_code == 201
        finally:
            # Restore original health status
            test_recommendation_run.evidence_health_status = original_health
            db.commit()
