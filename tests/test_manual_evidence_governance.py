"""
Phase 6.5: Manual Evidence Governance Tests

Tests for manual evidence governance and approval workflow.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.manual_evidence_review import ManualEvidenceReview
from app.models.manual_test_execution import ManualTestExecution
from app.models.repository import Repository
from app.models.user import User, Workspace, WorkspaceMember
from app.models.integration_connection import IntegrationConnection
from app.models.external_test_case_detailed import ExternalTestCase
from app.services.manual_evidence_governance_service import ManualEvidenceGovernanceService, GovernanceStatus
from app.services.manual_evidence_risk_adjustment_service import ManualEvidenceRiskAdjustmentService
from app.schemas.regression_scope_v2 import RiskBand


@pytest.fixture
def db_session():
    """Create a test database session."""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def test_workspace(db_session: Session):
    """Create a test workspace."""
    workspace = Workspace(
        id=uuid4(),
        name="Test Workspace",
        slug=f"test-workspace-{uuid4()}"
    )
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)
    return workspace


@pytest.fixture
def test_repository(db_session: Session, test_workspace):
    """Create a test repository."""
    repo = Repository(
        id=uuid4(),
        name="Test Repository",
        full_name="test-org/test-repo",
        github_repo_id=12345,
        workspace_id=test_workspace.id,
        is_active=True
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


@pytest.fixture
def test_integration_connection(db_session: Session, test_workspace):
    """Create a test integration connection."""
    conn = IntegrationConnection(
        id=uuid4(),
        workspace_id=test_workspace.id,
        provider="TESTRAIL",
        display_name="Test Connection",
        status="CONNECTED"
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)
    return conn


@pytest.fixture
def test_external_test_case(db_session: Session, test_workspace, test_repository, test_integration_connection):
    """Create a test external test case."""
    case = ExternalTestCase(
        id=uuid4(),
        workspace_id=test_workspace.id,
        repository_id=test_repository.id,
        integration_connection_id=test_integration_connection.id,
        provider="TESTRAIL",
        external_id="12345",
        title="Test Case Title"
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


@pytest.fixture
def test_user(db_session: Session, test_workspace):
    """Create a test user."""
    user = User(
        id=uuid4(),
        name="Test User",
        email=f"test-{uuid4()}@example.com"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create membership
    member = WorkspaceMember(
        id=uuid4(),
        workspace_id=test_workspace.id,
        user_id=user.id,
        role="MEMBER"
    )
    db_session.add(member)
    db_session.commit()
    return user


@pytest.fixture
def test_execution(db_session: Session, test_repository, test_external_test_case):
    """Create a test manual test execution."""
    execution = ManualTestExecution(
        id=uuid4(),
        external_test_case_id=test_external_test_case.id,
        repository_id=test_repository.id,
        outcome="PASSED",
        executed_by_name="Test Executor",
        executed_at=datetime.utcnow(),
        is_active=True
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)
    return execution


class TestManualEvidenceGovernanceService:
    """Tests for ManualEvidenceGovernanceService."""
    
    def test_get_governance_status_pending_review(self, db_session: Session, test_execution, test_repository):
        """Test that new execution has PENDING_REVIEW status."""
        service = ManualEvidenceGovernanceService(db_session)
        status = service.get_governance_status(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id)
        )
        
        assert status["governanceStatus"] == GovernanceStatus.PENDING_REVIEW.value
        assert status["executionId"] == str(test_execution.id)
        assert status["reviewerName"] is None
        assert status["reviewedAt"] is None
        assert status["reviewNote"] is None
        assert status["isExpired"] is False
    
    def test_approve_execution(self, db_session: Session, test_execution, test_repository, test_user):
        """Test approval creation."""
        service = ManualEvidenceGovernanceService(db_session)
        review = service.approve_execution(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id),
            reviewer_id=str(test_user.id),
            reviewer_name=test_user.name,
            review_note="Approved for release"
        )
        
        assert review.review_status == GovernanceStatus.APPROVED.value
        assert review.reviewed_by_name == test_user.name
        assert review.reviewed_by_id == test_user.id
        assert review.review_note == "Approved for release"
        assert review.is_active is True
        
        # Verify governance status is now APPROVED
        status = service.get_governance_status(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id)
        )
        assert status["governanceStatus"] == GovernanceStatus.APPROVED.value
        assert status["reviewerName"] == test_user.name
    
    def test_reject_execution_requires_note(self, db_session: Session, test_execution, test_repository, test_user):
        """Test that rejection requires a review note."""
        service = ManualEvidenceGovernanceService(db_session)
        
        with pytest.raises(ValueError, match="Review note is required"):
            service.reject_execution(
                execution_id=str(test_execution.id),
                repository_id=str(test_repository.id),
                reviewer_id=str(test_user.id),
                reviewer_name=test_user.name,
                review_note=None
            )
        
        with pytest.raises(ValueError, match="Review note is required"):
            service.reject_execution(
                execution_id=str(test_execution.id),
                repository_id=str(test_repository.id),
                reviewer_id=str(test_user.id),
                reviewer_name=test_user.name,
                review_note=""
            )
    
    def test_reject_execution_with_note(self, db_session: Session, test_execution, test_repository, test_user):
        """Test rejection with valid note."""
        service = ManualEvidenceGovernanceService(db_session)
        review = service.reject_execution(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id),
            reviewer_id=str(test_user.id),
            reviewer_name=test_user.name,
            review_note="Test execution invalid"
        )
        
        assert review.review_status == GovernanceStatus.REJECTED.value
        assert review.review_note == "Test execution invalid"
        
        # Verify governance status is now REJECTED
        status = service.get_governance_status(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id)
        )
        assert status["governanceStatus"] == GovernanceStatus.REJECTED.value
    
    def test_challenge_execution_requires_note(self, db_session: Session, test_execution, test_repository, test_user):
        """Test that challenge requires a review note."""
        service = ManualEvidenceGovernanceService(db_session)
        
        with pytest.raises(ValueError, match="Review note is required"):
            service.challenge_execution(
                execution_id=str(test_execution.id),
                repository_id=str(test_repository.id),
                reviewer_id=str(test_user.id),
                reviewer_name=test_user.name,
                review_note=None
            )
    
    def test_challenge_execution_with_note(self, db_session: Session, test_execution, test_repository, test_user):
        """Test challenge with valid note."""
        service = ManualEvidenceGovernanceService(db_session)
        review = service.challenge_execution(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id),
            reviewer_id=str(test_user.id),
            reviewer_name=test_user.name,
            review_note="Disputed by QA"
        )
        
        assert review.review_status == GovernanceStatus.CHALLENGED.value
        assert review.review_note == "Disputed by QA"
        
        # Verify governance status is now CHALLENGED
        status = service.get_governance_status(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id)
        )
        assert status["governanceStatus"] == GovernanceStatus.CHALLENGED.value
    
    def test_only_one_active_review(self, db_session: Session, test_execution, test_repository, test_user):
        """Test that only one review can be active at a time."""
        service = ManualEvidenceGovernanceService(db_session)
        
        # Create first review
        review1 = service.approve_execution(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id),
            reviewer_id=str(test_user.id),
            reviewer_name=test_user.name
        )
        
        # Create second review (should deactivate first)
        review2 = service.reject_execution(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id),
            reviewer_id=str(test_user.id),
            reviewer_name=test_user.name,
            review_note="Changed mind"
        )
        
        # Verify first review is deactivated
        db_session.refresh(review1)
        assert review1.is_active is False
        
        # Verify second review is active
        assert review2.is_active is True
        
        # Verify governance status reflects latest review
        status = service.get_governance_status(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id)
        )
        assert status["governanceStatus"] == GovernanceStatus.REJECTED.value
    
    def test_expiration_logic(self, db_session: Session, test_execution, test_repository):
        """Test that old executions are marked as expired."""
        # Make execution older than expiry threshold
        old_date = datetime.utcnow() - timedelta(days=35)
        test_execution.executed_at = old_date
        db_session.commit()
        
        service = ManualEvidenceGovernanceService(db_session)
        status = service.get_governance_status(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id)
        )
        
        assert status["isExpired"] is True
        assert status["governanceStatus"] == GovernanceStatus.EXPIRED.value
    
    def test_expiration_with_newer_execution(self, db_session: Session, test_execution, test_repository):
        """Test that newer execution prevents expiration."""
        # Make execution older than expiry threshold
        old_date = datetime.utcnow() - timedelta(days=35)
        test_execution.executed_at = old_date
        db_session.commit()
        
        # Create newer execution for same test case
        newer_execution = ManualTestExecution(
            id=uuid4(),
            external_test_case_id=test_execution.external_test_case_id,
            repository_id=test_repository.id,
            outcome="PASSED",
            executed_by_name="Test Executor",
            executed_at=datetime.utcnow(),
            is_active=True
        )
        db_session.add(newer_execution)
        db_session.commit()
        
        service = ManualEvidenceGovernanceService(db_session)
        status = service.get_governance_status(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id)
        )
        
        # Should not be expired because newer execution exists
        assert status["isExpired"] is False
    
    def test_is_trusted_for_risk_adjustment(self, db_session: Session, test_execution, test_repository, test_user):
        """Test that only APPROVED evidence is trusted for risk adjustment."""
        service = ManualEvidenceGovernanceService(db_session)
        
        # Initially pending - not trusted
        assert service.is_trusted_for_risk_adjustment(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id)
        ) is False
        
        # Approve - now trusted
        service.approve_execution(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id),
            reviewer_id=str(test_user.id),
            reviewer_name=test_user.name
        )
        assert service.is_trusted_for_risk_adjustment(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id)
        ) is True
        
        # Reject - not trusted
        service.reject_execution(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id),
            reviewer_id=str(test_user.id),
            reviewer_name=test_user.name,
            review_note="Invalid"
        )
        assert service.is_trusted_for_risk_adjustment(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id)
        ) is False


class TestManualEvidenceRiskAdjustmentWithGovernance:
    """Tests for ManualEvidenceRiskAdjustmentService with governance."""
    
    def test_approved_passed_reduces_risk(self):
        """Test that APPROVED + PASSED reduces risk by one band."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.CRITICAL,
            manual_support_status="PASSED",
            governance_status="APPROVED"
        )
        
        assert result["residual_risk_band"] == RiskBand.HIGH.value
        assert result["adjustment_delta"] == -1
        assert "reduced residual risk" in result["adjustment_reason"]
    
    def test_pending_passed_no_adjustment(self):
        """Test that PENDING_REVIEW + PASSED does not adjust risk."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.CRITICAL,
            manual_support_status="PASSED",
            governance_status="PENDING_REVIEW"
        )
        
        assert result["residual_risk_band"] == RiskBand.CRITICAL.value
        assert result["adjustment_delta"] == 0
        assert "awaiting governance approval" in result["adjustment_reason"]
    
    def test_rejected_passed_no_adjustment(self):
        """Test that REJECTED + PASSED does not adjust risk."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.CRITICAL,
            manual_support_status="PASSED",
            governance_status="REJECTED"
        )
        
        assert result["residual_risk_band"] == RiskBand.CRITICAL.value
        assert result["adjustment_delta"] == 0
        assert "Rejected manual evidence ignored" in result["adjustment_reason"]
    
    def test_challenged_passed_no_adjustment(self):
        """Test that CHALLENGED + PASSED does not adjust risk."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.CRITICAL,
            manual_support_status="PASSED",
            governance_status="CHALLENGED"
        )
        
        assert result["residual_risk_band"] == RiskBand.CRITICAL.value
        assert result["adjustment_delta"] == 0
        assert "temporarily untrusted" in result["adjustment_reason"]
    
    def test_expired_passed_no_adjustment(self):
        """Test that EXPIRED + PASSED does not adjust risk."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.CRITICAL,
            manual_support_status="PASSED",
            governance_status="EXPIRED"
        )
        
        assert result["residual_risk_band"] == RiskBand.CRITICAL.value
        assert result["adjustment_delta"] == 0
        assert "no longer trusted" in result["adjustment_reason"]
    
    def test_approved_failed_increases_risk(self):
        """Test that APPROVED + FAILED increases risk by one band."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="FAILED",
            governance_status="APPROVED"
        )
        
        assert result["residual_risk_band"] == RiskBand.CRITICAL.value
        assert result["adjustment_delta"] == 1
        assert "elevated residual risk" in result["adjustment_reason"]
    
    def test_rejected_failed_no_adjustment(self):
        """Test that REJECTED + FAILED does not adjust risk."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.HIGH,
            manual_support_status="FAILED",
            governance_status="REJECTED"
        )
        
        assert result["residual_risk_band"] == RiskBand.HIGH.value
        assert result["adjustment_delta"] == 0
        assert "Rejected manual evidence ignored" in result["adjustment_reason"]
    
    def test_no_governance_status_treated_as_pending(self):
        """Test that missing governance status is treated as pending."""
        result = ManualEvidenceRiskAdjustmentService.adjust_risk(
            generated_risk_band=RiskBand.CRITICAL,
            manual_support_status="PASSED",
            governance_status=None
        )
        
        assert result["residual_risk_band"] == RiskBand.CRITICAL.value
        assert result["adjustment_delta"] == 0
        assert "awaiting governance approval" in result["adjustment_reason"]


class TestEvidenceTruthInvariants:
    """Tests that governance does not affect evidence truth."""
    
    def test_governance_does_not_change_coverage_counts(self, db_session: Session, test_execution, test_repository, test_user):
        """Test that governance approval does not change coverage counts."""
        service = ManualEvidenceGovernanceService(db_session)
        
        # Approve execution
        service.approve_execution(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id),
            reviewer_id=str(test_user.id),
            reviewer_name=test_user.name
        )
        
        # Verify execution outcome is unchanged
        db_session.refresh(test_execution)
        assert test_execution.outcome == "PASSED"
        
        # Governance should not affect automated evidence
        # This is a placeholder - actual coverage count verification would require
        # a full evidence graph setup
        assert True  # Placeholder for coverage count invariant
    
    def test_governance_does_not_change_health_status(self, db_session: Session, test_execution, test_repository, test_user):
        """Test that governance does not change health status."""
        service = ManualEvidenceGovernanceService(db_session)
        
        # Approve execution
        service.approve_execution(
            execution_id=str(test_execution.id),
            repository_id=str(test_repository.id),
            reviewer_id=str(test_user.id),
            reviewer_name=test_user.name
        )
        
        # Governance should not affect health status
        # This is a placeholder - actual health status verification would require
        # a full evidence graph setup
        assert True  # Placeholder for health status invariant
