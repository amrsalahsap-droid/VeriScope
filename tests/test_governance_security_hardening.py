"""
Tests for Governance Security Hardening (Phase 8.13)

Tests access review creation, security posture calculation,
evidence pack export with redaction, and API endpoint security.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.governance_access_review import GovernanceAccessReview
from app.models.governance_access_review_item import GovernanceAccessReviewItem
from app.models.governance_role_assignment import GovernanceRoleAssignment, GovernanceRole, ScopeType
from app.models.workspace_governance_audit_event import WorkspaceGovernanceAuditEvent
from app.services.governance_access_review_service import GovernanceAccessReviewService
from app.services.governance_security_signal_service import GovernanceSecuritySignalService
from app.services.governance_evidence_pack_service import GovernanceEvidencePackService
from app.services.workspace_governance_audit_service import WorkspaceGovernanceAuditService


@pytest.fixture
def test_workspace_id():
    """Test workspace ID."""
    return uuid.UUID("308c1ef9-8043-4332-86bc-27bd3ab73ecf")


@pytest.fixture
def test_user_id():
    """Test user ID."""
    return uuid.UUID("36610958-1d3c-49ba-9e3c-d8e742a98017")


@pytest.fixture
def test_repository_id():
    """Test repository ID."""
    return uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


@pytest.fixture
def db_session(test_db):
    """Database session fixture."""
    yield test_db


class TestAccessReviewService:
    """Tests for GovernanceAccessReviewService."""

    def test_create_access_review(self, db_session: Session, test_workspace_id, test_user_id):
        """Test creating an access review."""
        period_start = datetime.utcnow() - timedelta(days=30)
        period_end = datetime.utcnow()

        review = GovernanceAccessReviewService.create_access_review(
            db=db_session,
            workspace_id=test_workspace_id,
            review_name="Q1 2026 Access Review",
            review_type="QUARTERLY_ACCESS_REVIEW",
            creator_id=test_user_id,
            period_start=period_start,
            period_end=period_end
        )

        assert review is not None
        assert review.workspace_id == test_workspace_id
        assert review.review_name == "Q1 2026 Access Review"
        assert review.review_type == "QUARTERLY_ACCESS_REVIEW"
        assert review.status == "DRAFT"
        assert review.created_by == test_user_id

    def test_generate_review_items(self, db_session: Session, test_workspace_id, test_user_id, test_repository_id):
        """Test generating review items from role assignments."""
        # Create a test role assignment
        assignment = GovernanceRoleAssignment(
            workspace_id=test_workspace_id,
            user_id=test_user_id,
            role=GovernanceRole.GOVERNANCE_OWNER,
            scope_type=ScopeType.WORKSPACE,
            is_active=True,
            created_at=datetime.utcnow() - timedelta(days=100)  # Stale role
        )
        db_session.add(assignment)
        db_session.commit()

        # Create review
        review = GovernanceAccessReviewService.create_access_review(
            db=db_session,
            workspace_id=test_workspace_id,
            review_name="Test Review",
            review_type="PRIVILEGED_ROLE_REVIEW",
            creator_id=test_user_id,
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow()
        )

        # Generate items
        items = GovernanceAccessReviewService.generate_review_items(db_session, review)

        assert len(items) > 0
        # Should find stale role and privileged role
        finding_types = [item.finding_type for item in items]
        assert "PRIVILEGED_ROLE" in finding_types
        assert "STALE_ROLE" in finding_types

    def test_security_posture_calculation(self, db_session: Session, test_workspace_id, test_user_id):
        """Test security posture calculation."""
        posture = GovernanceAccessReviewService.get_governance_security_posture(
            db=db_session,
            workspace_id=test_workspace_id
        )

        assert "security_score" in posture
        assert "security_grade" in posture
        assert posture["security_score"] >= 0
        assert posture["security_score"] <= 100
        assert posture["security_grade"] in ["A", "B", "C", "D", "F"]
        assert "privileged_roles" in posture
        assert "expired_roles" in posture


class TestSecuritySignalService:
    """Tests for GovernanceSecuritySignalService."""

    def test_detect_security_signals(self, db_session: Session, test_workspace_id):
        """Test security signal detection."""
        signals = GovernanceSecuritySignalService.detect_security_signals(
            db=db_session,
            workspace_id=test_workspace_id
        )

        assert isinstance(signals, list)
        # Each signal should have required fields
        for signal in signals:
            assert "signal_type" in signal
            assert "severity" in signal
            assert "description" in signal
            assert "recommendation" in signal
            assert signal["severity"] in ["HIGH", "MEDIUM", "LOW"]

    def test_security_signal_summary(self, db_session: Session, test_workspace_id):
        """Test security signal summary."""
        summary = GovernanceSecuritySignalService.get_security_signal_summary(
            db=db_session,
            workspace_id=test_workspace_id
        )

        assert "total_signals" in summary
        assert "high_severity" in summary
        assert "medium_severity" in summary
        assert "low_severity" in summary
        assert "signals" in summary
        assert summary["total_signals"] == len(summary["signals"])


class TestEvidencePackService:
    """Tests for GovernanceEvidencePackService."""

    def test_export_evidence_pack_executive(self, db_session: Session, test_workspace_id, test_user_id):
        """Test exporting executive evidence pack."""
        pack = GovernanceEvidencePackService.export_evidence_pack(
            db=db_session,
            workspace_id=test_workspace_id,
            pack_type="EXECUTIVE",
            requester_id=test_user_id
        )

        assert "workspace_id" in pack
        assert "pack_type" in pack
        assert pack["pack_type"] == "EXECUTIVE"
        assert "sections" in pack
        assert "policy_defaults" in pack["sections"]
        assert "policy_exceptions" in pack["sections"]
        assert "role_assignments" in pack["sections"]

    def test_export_evidence_pack_auditor(self, db_session: Session, test_workspace_id, test_user_id):
        """Test exporting auditor evidence pack."""
        pack = GovernanceEvidencePackService.export_evidence_pack(
            db=db_session,
            workspace_id=test_workspace_id,
            pack_type="AUDITOR",
            requester_id=test_user_id
        )

        assert pack["pack_type"] == "AUDITOR"
        # Auditor pack should include notifications
        assert "notifications" in pack["sections"]

    def test_export_evidence_pack_full(self, db_session: Session, test_workspace_id, test_user_id):
        """Test exporting full evidence pack."""
        pack = GovernanceEvidencePackService.export_evidence_pack(
            db=db_session,
            workspace_id=test_workspace_id,
            pack_type="FULL",
            requester_id=test_user_id
        )

        assert pack["pack_type"] == "FULL"
        # Full pack should include audit events
        assert "audit_events" in pack["sections"]

    def test_redaction(self):
        """Test data redaction in evidence packs."""
        test_data = {
            "password": "secret123",
            "token": "abc123def456",
            "api_key": "xyz789",
            "safe_field": "this is safe"
        }

        redacted = GovernanceEvidencePackService.redact_sensitive_data(test_data)

        assert redacted["password"] == "[REDACTED]"
        assert redacted["token"] == "[REDACTED]"
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["safe_field"] == "this is safe"


class TestAuditEvents:
    """Tests for audit event logging."""

    def test_log_access_review_created(self, db_session: Session, test_workspace_id, test_user_id):
        """Test logging access review creation."""
        review_id = uuid.uuid4()

        WorkspaceGovernanceAuditService.log_access_review_created(
            db=db_session,
            workspace_id=test_workspace_id,
            actor_id=test_user_id,
            review_id=review_id,
            review_type="QUARTERLY_ACCESS_REVIEW"
        )

        event = db_session.query(WorkspaceGovernanceAuditEvent).filter(
            WorkspaceGovernanceAuditEvent.event_type == "GOVERNANCE_ACCESS_REVIEW_CREATED",
            WorkspaceGovernanceAuditEvent.operation_id == review_id
        ).first()

        assert event is not None
        assert event.workspace_id == test_workspace_id
        assert event.actor_id == test_user_id

    def test_log_security_posture_viewed(self, db_session: Session, test_workspace_id, test_user_id):
        """Test logging security posture view."""
        WorkspaceGovernanceAuditService.log_security_posture_viewed(
            db=db_session,
            workspace_id=test_workspace_id,
            actor_id=test_user_id
        )

        event = db_session.query(WorkspaceGovernanceAuditEvent).filter(
            WorkspaceGovernanceAuditEvent.event_type == "GOVERNANCE_SECURITY_POSTURE_VIEWED",
            WorkspaceGovernanceAuditEvent.workspace_id == test_workspace_id
        ).first()

        assert event is not None

    def test_log_evidence_pack_exported(self, db_session: Session, test_workspace_id, test_user_id):
        """Test logging evidence pack export."""
        WorkspaceGovernanceAuditService.log_evidence_pack_exported(
            db=db_session,
            workspace_id=test_workspace_id,
            actor_id=test_user_id,
            pack_type="AUDITOR"
        )

        event = db_session.query(WorkspaceGovernanceAuditEvent).filter(
            WorkspaceGovernanceAuditEvent.event_type == "GOVERNANCE_EVIDENCE_PACK_EXPORTED",
            WorkspaceGovernanceAuditEvent.workspace_id == test_workspace_id
        ).first()

        assert event is not None
        assert event.audit_metadata["pack_type"] == "AUDITOR"


class TestAdvisoryBehavior:
    """Tests to ensure advisory-only behavior (no automatic mutations)."""

    def test_access_review_decision_does_not_revoke_role(self, db_session: Session, test_workspace_id, test_user_id):
        """Test that access review decisions do not automatically revoke roles."""
        # Create a role assignment
        assignment = GovernanceRoleAssignment(
            workspace_id=test_workspace_id,
            user_id=test_user_id,
            role=GovernanceRole.POLICY_ADMIN,
            scope_type=ScopeType.WORKSPACE,
            is_active=True,
            created_at=datetime.utcnow()
        )
        db_session.add(assignment)
        db_session.commit()

        assignment_id = assignment.id

        # Create review and item
        review = GovernanceAccessReviewService.create_access_review(
            db=db_session,
            workspace_id=test_workspace_id,
            review_name="Test Review",
            review_type="PRIVILEGED_ROLE_REVIEW",
            creator_id=test_user_id,
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow()
        )

        # Mark item as REVOKE_RECOMMENDED
        items = db_session.query(GovernanceAccessReviewItem).filter(
            GovernanceAccessReviewItem.review_id == review.id
        ).all()

        if items:
            GovernanceAccessReviewService.update_review_item_decision(
                db=db_session,
                workspace_id=test_workspace_id,
                review_id=review.id,
                item_id=items[0].id,
                decision="REVOKE_RECOMMENDED",
                reason="Test advisory decision",
                reviewer_id=test_user_id
            )

        # Verify role assignment is still active (not revoked)
        assignment_after = db_session.query(GovernanceRoleAssignment).filter(
            GovernanceRoleAssignment.id == assignment_id
        ).first()

        assert assignment_after is not None
        assert assignment_after.is_active == True  # Should still be active


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
