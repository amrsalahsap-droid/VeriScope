"""Release Decision Canonical Health Tests

Tests for the canonical health resolution in release decision service.
Verifies that live evidence health is used instead of stale DB columns.
"""
import pytest
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.recommendation import RecommendationRun
from app.models.release_decision import ReleaseDecision
from app.models.release_decision_history import ReleaseDecisionHistory
from app.services.release_decision_service import ReleaseDecisionService


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user."""
    user = db_session.query(User).filter(User.email == "test-canonical-health@example.com").first()
    if not user:
        user = User(
            email="test-canonical-health@example.com",
            name="Test Canonical Health User",
            auth_provider="github",
            provider_user_id="test-canonical-health-123"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture
def test_workspace(db_session: Session, test_user: User):
    """Create a test workspace."""
    workspace = db_session.query(Workspace).filter(Workspace.name == "Test Canonical Health Workspace").first()
    if not workspace:
        workspace = Workspace(
            name="Test Canonical Health Workspace",
            slug="test-canonical-health-workspace"
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)
    
    # Ensure user is a member
    member = db_session.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace.id,
        WorkspaceMember.user_id == test_user.id
    ).first()
    if not member:
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=test_user.id,
            role="OWNER"
        )
        db_session.add(member)
        db_session.commit()
    
    return workspace


@pytest.fixture
def test_repository(db_session: Session, test_workspace: Workspace):
    """Create a test repository."""
    repo = db_session.query(Repository).filter(Repository.name == "test-canonical-health-repo").first()
    if not repo:
        repo = Repository(
            name="test-canonical-health-repo",
            workspace_id=test_workspace.id,
            github_repo_id=99999,
            full_name="test/test-canonical-health-repo"
        )
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)
    return repo


@pytest.fixture
def test_run(db_session: Session, test_repository: Repository):
    """Create a test recommendation run."""
    # Delete any existing run with this pr_id to ensure clean state
    db_session.query(RecommendationRun).filter(
        RecommendationRun.pr_id == "test-canonical-health-pr"
    ).delete()
    db_session.commit()
    
    run = RecommendationRun(
        repository_id=test_repository.id,
        pr_id="test-canonical-health-pr",
        triggered_by="test",
        evidence_quality="HIGH",
        engine_version="v1.0.0",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="Test",
        evidence_health_status="READY",
        recommendation_readiness_state="READY",
        evidence_fingerprint="test-fingerprint"
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


class TestReleaseDecisionCanonicalHealth:
    """Test canonical health resolution in release decision service."""

    def test_passing_live_evidence_health_stores_it(self, db_session: Session, test_run: RecommendationRun, test_user: User):
        """Test that passing live_evidence_health stores it instead of stale column."""
        # Submit release decision with live VALIDATION_PASSED_COVERAGE_INCOMPLETE health
        decision = ReleaseDecisionService.submit_release_decision(
            db=db_session,
            run=test_run,
            data={
                "decision_status": "APPROVED",
                "snapshot_hash": "test-fingerprint",
                "decision_note": "Test approval"
            },
            actor=test_user,
            live_evidence_health="VALIDATION_PASSED_COVERAGE_INCOMPLETE"  # Live health
        )
        
        # Verify live health was stored, not stale column
        assert decision.evidence_health_status == "VALIDATION_PASSED_COVERAGE_INCOMPLETE"
        assert decision.evidence_health_status != test_run.evidence_health_status
        
        # Verify readiness_state was derived from live health
        assert decision.readiness_state == "NOT_READY"
        assert decision.readiness_state != test_run.recommendation_readiness_state

    def test_stale_ready_column_overridden_by_live_non_ready_health(self, db_session: Session, test_run: RecommendationRun, test_user: User):
        """Test that stale READY column is overridden by VALIDATION_PASSED_COVERAGE_INCOMPLETE live health."""
        # Submit with live non-ready health
        decision = ReleaseDecisionService.submit_release_decision(
            db=db_session,
            run=test_run,
            data={
                "decision_status": "APPROVED",
                "snapshot_hash": "test-fingerprint",
                "decision_note": "Test"
            },
            actor=test_user,
            live_evidence_health="VALIDATION_PASSED_COVERAGE_INCOMPLETE"
        )
        
        # Verify live health overrode stale
        assert decision.evidence_health_status == "VALIDATION_PASSED_COVERAGE_INCOMPLETE"
        assert decision.readiness_state == "NOT_READY"

    def test_not_passing_live_evidence_health_falls_back_to_stale_column(self, db_session: Session, test_run: RecommendationRun, test_user: User):
        """Test backward compatibility: not passing live_evidence_health falls back to run.evidence_health_status."""
        # Update run to have non-ready health
        test_run.evidence_health_status = "VALIDATION_PASSED_COVERAGE_INCOMPLETE"
        test_run.recommendation_readiness_state = "NOT_READY"
        db_session.commit()
        
        # Submit WITHOUT live_evidence_health (backward compat)
        decision = ReleaseDecisionService.submit_release_decision(
            db=db_session,
            run=test_run,
            data={
                "decision_status": "APPROVED",
                "snapshot_hash": "test-fingerprint",
                "decision_note": "Test"
            },
            actor=test_user
            # No live_evidence_health parameter
        )
        
        # Should fall back to stale column
        assert decision.evidence_health_status == test_run.evidence_health_status
        assert decision.readiness_state == test_run.recommendation_readiness_state

    def test_existing_get_release_state_method_unaffected(self, db_session: Session, test_run: RecommendationRun, test_user: User):
        """Test that existing get_release_state method is unaffected by changes."""
        # Create a release decision
        decision = ReleaseDecisionService.submit_release_decision(
            db=db_session,
            run=test_run,
            data={
                "decision_status": "APPROVED",
                "snapshot_hash": "test-fingerprint",
                "decision_note": "Test"
            },
            actor=test_user
        )
        
        # get_release_state should still work
        state = ReleaseDecisionService.get_release_state(db_session, test_run.id)
        
        assert state is not None
        assert state["decisionId"] == str(decision.id)
        assert state["decisionStatus"] == "APPROVED"
        assert state["evidenceHealthStatus"] == decision.evidence_health_status
        assert state["readinessState"] == decision.readiness_state

    def test_reset_release_decision_accepts_and_stores_live_health(self, db_session: Session, test_run: RecommendationRun, test_user: User):
        """Test that reset_release_decision also accepts and stores live health."""
        # Create initial decision
        initial_decision = ReleaseDecisionService.submit_release_decision(
            db=db_session,
            run=test_run,
            data={
                "decision_status": "APPROVED",
                "snapshot_hash": "test-fingerprint",
                "decision_note": "Initial approval"
            },
            actor=test_user
        )
        
        # Reset with live health
        reset_decision = ReleaseDecisionService.reset_release_decision(
            db=db_session,
            run=test_run,
            data={
                "snapshot_hash": "test-fingerprint",
                "note": "Reset for review"
            },
            actor=test_user,
            live_evidence_health="VALIDATION_PASSED_TRACEABILITY_INCOMPLETE"
        )
        
        # Verify live health was stored
        assert reset_decision.evidence_health_status == "VALIDATION_PASSED_TRACEABILITY_INCOMPLETE"
        assert reset_decision.readiness_state == "NOT_READY"
        assert reset_decision.decision_status == "PENDING_REVIEW"

    def test_derive_readiness_state_from_health_mapping(self):
        """Test the derive_readiness_state_from_health mapping."""
        # READY states
        assert ReleaseDecisionService.derive_readiness_state_from_health("READY") == "READY"
        assert ReleaseDecisionService.derive_readiness_state_from_health("READY_WITH_GAPS") == "READY"
        assert ReleaseDecisionService.derive_readiness_state_from_health("READY_WITH_TRACEABILITY_ISSUES") == "READY"
        
        # NOT_READY states
        assert ReleaseDecisionService.derive_readiness_state_from_health("VALIDATION_PASSED_COVERAGE_INCOMPLETE") == "NOT_READY"
        assert ReleaseDecisionService.derive_readiness_state_from_health("VALIDATION_PASSED_TRACEABILITY_INCOMPLETE") == "NOT_READY"
        assert ReleaseDecisionService.derive_readiness_state_from_health("INSUFFICIENT_INPUT") == "NOT_READY"
        
        # NEEDS_REVIEW states
        assert ReleaseDecisionService.derive_readiness_state_from_health("NEEDS_TRACEABILITY_REVIEW") == "NEEDS_REVIEW"
        
        # BLOCKED states
        assert ReleaseDecisionService.derive_readiness_state_from_health("BLOCKED_BY_FAILED_TESTS") == "BLOCKED"
        assert ReleaseDecisionService.derive_readiness_state_from_health("BLOCKED_BY_SKIPPED_REQUIRED_TESTS") == "BLOCKED"
        assert ReleaseDecisionService.derive_readiness_state_from_health("BLOCKED_BY_FAILED_OR_SKIPPED_TESTS") == "BLOCKED"
        assert ReleaseDecisionService.derive_readiness_state_from_health("VALIDATION_FAILED") == "BLOCKED"
        assert ReleaseDecisionService.derive_readiness_state_from_health("STALE_INPUTS") == "BLOCKED"
        assert ReleaseDecisionService.derive_readiness_state_from_health("INTERNAL_EVIDENCE_MODEL_INCONSISTENT") == "BLOCKED"
        assert ReleaseDecisionService.derive_readiness_state_from_health("BLOCKED") == "BLOCKED"
        
        # Unknown health with fallback
        assert ReleaseDecisionService.derive_readiness_state_from_health("UNKNOWN", fallback="CUSTOM") == "CUSTOM"
        assert ReleaseDecisionService.derive_readiness_state_from_health("UNKNOWN") == "NEEDS_REVIEW"
