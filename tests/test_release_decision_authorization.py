"""Release Decision Authorization Tests.

Tests must prove:
- OWNER allowed to approve/reject
- ADMIN allowed to approve/reject
- MEMBER blocked from approval
- workspace isolation enforced
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
from app.models.repository import Repository


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
def owner_user(db: Session, test_recommendation_run: RecommendationRun):
    """Create or get an OWNER user for the workspace."""
    repo = db.query(Repository).filter(Repository.id == test_recommendation_run.repository_id).first()
    if not repo:
        return None

    # Get or create OWNER member
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == repo.workspace_id,
        WorkspaceMember.role == "OWNER"
    ).first()

    if member:
        return db.query(User).filter(User.id == member.user_id).first()

    # Create a new user as OWNER
    from app.models.user import User
    owner = User(
        email="owner@example.com",
        name="Owner User",
        auth_provider="github",
        provider_user_id="github-owner-123"
    )
    db.add(owner)
    db.flush()

    member = WorkspaceMember(
        workspace_id=repo.workspace_id,
        user_id=owner.id,
        role="OWNER"
    )
    db.add(member)
    db.commit()

    return owner


@pytest.fixture
def admin_user(db: Session, test_recommendation_run: RecommendationRun):
    """Create or get an ADMIN user for the workspace."""
    repo = db.query(Repository).filter(Repository.id == test_recommendation_run.repository_id).first()
    if not repo:
        return None

    # Get or create ADMIN member
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == repo.workspace_id,
        WorkspaceMember.role == "ADMIN"
    ).first()

    if member:
        return db.query(User).filter(User.id == member.user_id).first()

    # Create a new user as ADMIN
    from app.models.user import User
    admin = User(
        email="admin@example.com",
        name="Admin User",
        auth_provider="github",
        provider_user_id="github-admin-123"
    )
    db.add(admin)
    db.flush()

    member = WorkspaceMember(
        workspace_id=repo.workspace_id,
        user_id=admin.id,
        role="ADMIN"
    )
    db.add(member)
    db.commit()

    return admin


@pytest.fixture
def member_user(db: Session, test_recommendation_run: RecommendationRun):
    """Create or get a MEMBER user for the workspace."""
    repo = db.query(Repository).filter(Repository.id == test_recommendation_run.repository_id).first()
    if not repo:
        return None

    # Get or create MEMBER member
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == repo.workspace_id,
        WorkspaceMember.role == "MEMBER"
    ).first()

    if member:
        return db.query(User).filter(User.id == member.user_id).first()

    # Create a new user as MEMBER
    from app.models.user import User
    member_user = User(
        email="member@example.com",
        name="Member User",
        auth_provider="github",
        provider_user_id="github-member-123"
    )
    db.add(member_user)
    db.flush()

    member = WorkspaceMember(
        workspace_id=repo.workspace_id,
        user_id=member_user.id,
        role="MEMBER"
    )
    db.add(member)
    db.commit()

    return member_user


def create_client_with_user(db: Session, user: User):
    """Create a test client with a specific user override."""
    from app.dependencies.auth import get_current_user
    from app.dependencies.authorization import validate_recommendation_run_access
    from app.models.recommendation import RecommendationRun
    from fastapi import HTTPException

    def override_get_current_user():
        return user

    def override_validate_access(db_session, run_id, requesting_user):
        run = db_session.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[validate_recommendation_run_access] = override_validate_access

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


class TestReleaseDecisionAuthorization:
    """Test release decision authorization rules."""

    def test_owner_can_approve_release(self, db: Session, test_recommendation_run: RecommendationRun, owner_user):
        """Verify OWNER role can approve release decisions."""
        if not owner_user:
            pytest.skip("No owner user available")

        from app.services.release_decision_service import ReleaseDecisionService

        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.commit()

        client = create_client_with_user(db, owner_user)

        res = client.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved by owner"
            }
        )
        assert res.status_code == 201
        assert res.json()["decision_status"] == "APPROVED"

    def test_admin_can_approve_release(self, db: Session, test_recommendation_run: RecommendationRun, admin_user):
        """Verify ADMIN role can approve release decisions."""
        if not admin_user:
            pytest.skip("No admin user available")

        from app.services.release_decision_service import ReleaseDecisionService

        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.commit()

        client = create_client_with_user(db, admin_user)

        res = client.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved by admin"
            }
        )
        assert res.status_code == 201
        assert res.json()["decision_status"] == "APPROVED"

    def test_member_cannot_approve_release(self, db: Session, test_recommendation_run: RecommendationRun, member_user):
        """Verify MEMBER role cannot approve release decisions."""
        if not member_user:
            pytest.skip("No member user available")

        from app.services.release_decision_service import ReleaseDecisionService

        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.commit()

        client = create_client_with_user(db, member_user)

        res = client.post(
            f"/api/recommendations/{run_id}/release-decision",
            json={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Should fail"
            }
        )
        assert res.status_code == 403
        assert "RELEASE_APPROVAL_ACCESS_DENIED" in res.json()["detail"]

    def test_member_can_view_release_decision(self, db: Session, test_recommendation_run: RecommendationRun, member_user):
        """Verify MEMBER role can view release decisions."""
        if not member_user:
            pytest.skip("No member user available")

        from app.services.release_decision_service import ReleaseDecisionService

        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.commit()

        # First create a decision as owner
        repo = db.query(Repository).filter(Repository.id == test_recommendation_run.repository_id).first()
        owner_member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == repo.workspace_id,
            WorkspaceMember.role == "OWNER"
        ).first()
        if owner_member:
            owner = db.query(User).filter(User.id == owner_member.user_id).first()
            if owner:
                owner_client = create_client_with_user(db, owner)
                owner_client.post(
                    f"/api/recommendations/{run_id}/release-decision",
                    json={
                        "decision_status": "APPROVED",
                        "snapshot_hash": snapshot_hash,
                        "decision_note": "Approved by owner"
                    }
                )

        # Now member should be able to view
        client = create_client_with_user(db, member_user)
        res = client.get(f"/api/recommendations/{run_id}/release-decision")
        assert res.status_code == 200
        assert res.json()["decisionStatus"] == "APPROVED"

    def test_member_cannot_reset_release_decision(self, db: Session, test_recommendation_run: RecommendationRun, member_user):
        """Verify MEMBER role cannot reset release decisions."""
        if not member_user:
            pytest.skip("No member user available")

        from app.services.release_decision_service import ReleaseDecisionService

        run_id = test_recommendation_run.id
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_recommendation_run)

        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == run_id).delete()
        db.commit()

        client = create_client_with_user(db, member_user)

        res = client.post(
            f"/api/recommendations/{run_id}/release-decision/reset",
            json={
                "snapshot_hash": snapshot_hash,
                "note": "Should fail"
            }
        )
        assert res.status_code == 403
        assert "RELEASE_APPROVAL_ACCESS_DENIED" in res.json()["detail"]

    def test_workspace_isolation_enforced(self, db: Session, test_recommendation_run: RecommendationRun):
        """Verify users from other workspaces cannot access release decisions."""
        from app.models.user import User, Workspace, WorkspaceMember
        from app.models.repository import Repository

        # Create a user in a different workspace
        other_workspace = Workspace(
            name="Other Workspace",
            slug="other-workspace",
            created_by_user_id=None
        )
        db.add(other_workspace)
        db.flush()

        other_user = User(
            email="other@example.com",
            name="Other User",
            auth_provider="github",
            provider_user_id="github-other-123"
        )
        db.add(other_user)
        db.flush()

        other_member = WorkspaceMember(
            workspace_id=other_workspace.id,
            user_id=other_user.id,
            role="OWNER"
        )
        db.add(other_member)
        db.commit()

        # Try to access release decision with other user
        run_id = test_recommendation_run.id
        client = create_client_with_user(db, other_user)

        res = client.get(f"/api/recommendations/{run_id}/release-decision")
        # Should fail due to workspace isolation
        assert res.status_code == 403

        # Clean up
        db.delete(other_member)
        db.delete(other_user)
        db.delete(other_workspace)
        db.commit()
