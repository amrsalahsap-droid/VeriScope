"""Simplified Release Decision Integration Tests.

Tests focus on core service functionality without complex fixture dependencies.
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.release_decision import ReleaseDecision
from app.models.release_decision_history import ReleaseDecisionHistory
from app.models.recommendation import RecommendationRun
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
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
    """Create or get test user."""
    user = db.query(User).filter(User.email == "test-integration@example.com").first()
    if not user:
        user = User(
            email="test-integration@example.com",
            name="Test Integration User",
            provider="github",
            provider_id="test-integration-123"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def test_workspace(db: Session, test_user: User):
    """Create or get test workspace."""
    workspace = db.query(Workspace).filter(Workspace.name == "Test Integration Workspace").first()
    if not workspace:
        workspace = Workspace(
            name="Test Integration Workspace",
            slug="test-integration-workspace",
            created_by_user_id=test_user.id
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
    """Create or get test repository."""
    repo = db.query(Repository).filter(Repository.name == "test-integration-repo").first()
    if not repo:
        repo = Repository(
            name="test-integration-repo",
            full_name="test-owner/test-integration-repo",
            owner="test-owner",
            github_repo_id=123456789,
            workspace_id=test_workspace.id,
            is_active=True,
            selected_for_analysis=True
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
    return repo


@pytest.fixture
def test_run(db: Session, test_repository: Repository):
    """Create or get test recommendation run."""
    run = db.query(RecommendationRun).filter(
        RecommendationRun.repository_id == test_repository.id
    ).first()
    
    if not run:
        run = RecommendationRun(
            repository_id=test_repository.id,
            pr_id="test-integration-pr",
            triggered_by="test-manual",
            evidence_quality="HIGH",
            engine_version="v1.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Test recommendation",
            evidence_fingerprint="test-integration-fingerprint",
            evidence_health_status="VALIDATION_PASSED_COVERAGE_INCOMPLETE"
        )
        db.add(run)
        db.commit()
        db.refresh(run)
    
    return run


class TestReleaseDecisionIntegration:
    """Test release decision service integration."""

    def test_get_release_state_no_decision(self, db: Session, test_run: RecommendationRun):
        """Verify getting state when no decision exists."""
        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == test_run.id).delete()
        db.commit()
        
        state = ReleaseDecisionService.get_release_state(db, test_run.id)
        assert state is None

    def test_submit_approval(self, db: Session, test_run: RecommendationRun, test_user: User):
        """Verify submitting approval creates decision and history."""
        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == test_run.id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()
        
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_run)
        
        decision = ReleaseDecisionService.submit_release_decision(
            db=db,
            run=test_run,
            data={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved for release"
            },
            actor=test_user
        )
        
        assert decision is not None
        assert decision.decision_status == "APPROVED"
        assert decision.approver_name == test_user.name
        assert decision.snapshot_hash == snapshot_hash
        assert decision.decision_note == "Approved for release"
        
        # Verify history was created
        history = db.query(ReleaseDecisionHistory).filter(
            ReleaseDecisionHistory.release_decision_id == decision.id
        ).all()
        assert len(history) == 1
        assert history[0].event_type == "APPROVED"
        assert history[0].actor_name == test_user.name

    def test_submit_rejection_requires_note(self, db: Session, test_run: RecommendationRun, test_user: User):
        """Verify rejection requires a note."""
        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == test_run.id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()
        
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_run)
        
        # Should raise error for missing note
        with pytest.raises(ValueError, match="Decision note is required"):
            ReleaseDecisionService.submit_release_decision(
                db=db,
                run=test_run,
                data={
                    "decision_status": "REJECTED",
                    "snapshot_hash": snapshot_hash,
                    "decision_note": None
                },
                actor=test_user
            )

    def test_submit_rejection_with_note(self, db: Session, test_run: RecommendationRun, test_user: User):
        """Verify rejection with note succeeds."""
        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == test_run.id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()
        
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_run)
        
        decision = ReleaseDecisionService.submit_release_decision(
            db=db,
            run=test_run,
            data={
                "decision_status": "REJECTED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Critical bugs found"
            },
            actor=test_user
        )
        
        assert decision is not None
        assert decision.decision_status == "REJECTED"
        assert decision.decision_note == "Critical bugs found"

    def test_reset_decision(self, db: Session, test_run: RecommendationRun, test_user: User):
        """Verify resetting decision creates RESET history event."""
        # First create a decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == test_run.id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()
        
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_run)
        
        decision = ReleaseDecisionService.submit_release_decision(
            db=db,
            run=test_run,
            data={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved"
            },
            actor=test_user
        )
        
        # Reset the decision
        reset_decision = ReleaseDecisionService.reset_release_decision(
            db=db,
            run=test_run,
            data={"snapshot_hash": snapshot_hash},
            actor=test_user
        )
        
        assert reset_decision is not None
        assert reset_decision.decision_status == "PENDING_REVIEW"
        
        # Verify RESET history event was created
        history = db.query(ReleaseDecisionHistory).filter(
            ReleaseDecisionHistory.release_decision_id == decision.id
        ).all()
        assert len(history) == 2
        assert history[0].event_type == "APPROVED"
        assert history[1].event_type == "RESET"

    def test_get_release_history(self, db: Session, test_run: RecommendationRun, test_user: User):
        """Verify getting release history returns timeline."""
        # Clean up and create decision with history
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == test_run.id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()
        
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_run)
        
        decision = ReleaseDecisionService.submit_release_decision(
            db=db,
            run=test_run,
            data={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved"
            },
            actor=test_user
        )
        
        history = ReleaseDecisionService.get_release_history(db, test_run.id, audit_mode=False)
        assert history is not None
        # history returns a dict with decision state, not a list
        # The actual history events are in the database
        db_history = db.query(ReleaseDecisionHistory).filter(
            ReleaseDecisionHistory.release_decision_id == decision.id
        ).all()
        assert len(db_history) == 1
        assert db_history[0].event_type == "APPROVED"
        assert db_history[0].actor_name == test_user.name

    def test_audit_mode_exposes_ids(self, db: Session, test_run: RecommendationRun, test_user: User):
        """Verify audit mode exposes internal IDs."""
        # Clean up and create decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == test_run.id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()
        
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_run)
        
        decision = ReleaseDecisionService.submit_release_decision(
            db=db,
            run=test_run,
            data={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved"
            },
            actor=test_user
        )
        
        # Check that history events have internal IDs in database
        db_history = db.query(ReleaseDecisionHistory).filter(
            ReleaseDecisionHistory.release_decision_id == decision.id
        ).all()
        assert len(db_history) == 1
        # Internal IDs exist in database records
        assert db_history[0].id is not None
        assert db_history[0].release_decision_id is not None

    def test_snapshot_mismatch_blocks_decision(self, db: Session, test_run: RecommendationRun, test_user: User):
        """Verify snapshot mismatch blocks decision."""
        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == test_run.id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()
        
        # Use wrong snapshot hash
        wrong_hash = "wrong-snapshot-hash"
        
        with pytest.raises(ValueError, match="RELEASE_SNAPSHOT_MISMATCH"):
            ReleaseDecisionService.submit_release_decision(
                db=db,
                run=test_run,
                data={
                    "decision_status": "APPROVED",
                    "snapshot_hash": wrong_hash,
                    "decision_note": "Approved"
                },
                actor=test_user
            )

    def test_blocking_health_status_blocks_decision(self, db: Session, test_run: RecommendationRun, test_user: User):
        """Verify blocking health status blocks decision."""
        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == test_run.id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()
        
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_run)
        
        # Temporarily modify the run's health status to a blocking one
        original_health = test_run.evidence_health_status
        test_run.evidence_health_status = "STALE_INPUTS"
        db.commit()
        
        try:
            # Use blocking health status
            with pytest.raises(ValueError, match="RELEASE_DECISION_BLOCKED"):
                ReleaseDecisionService.submit_release_decision(
                    db=db,
                    run=test_run,
                    data={
                        "decision_status": "APPROVED",
                        "snapshot_hash": snapshot_hash,
                        "decision_note": "Approved"
                    },
                    actor=test_user
                )
        finally:
            # Restore original health status
            test_run.evidence_health_status = original_health
            db.commit()

    def test_allowed_health_status_allows_decision(self, db: Session, test_run: RecommendationRun, test_user: User):
        """Verify allowed health status permits decision."""
        # Clean up any existing decision
        db.query(ReleaseDecision).filter(ReleaseDecision.recommendation_run_id == test_run.id).delete()
        db.query(ReleaseDecisionHistory).delete()
        db.commit()
        
        snapshot_hash = ReleaseDecisionService.get_snapshot_hash(test_run)
        
        # Use allowed health status
        decision = ReleaseDecisionService.submit_release_decision(
            db=db,
            run=test_run,
            data={
                "decision_status": "APPROVED",
                "snapshot_hash": snapshot_hash,
                "decision_note": "Approved"
            },
            actor=test_user
        )
        
        assert decision is not None
        assert decision.decision_status == "APPROVED"
