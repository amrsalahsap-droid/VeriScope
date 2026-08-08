"""
Governance Remediation Action Model
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class GovernanceRemediationAction(Base):
    """Governance remediation action model."""

    __tablename__ = "governance_remediation_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True, index=True)
    source_type = Column(String(50), nullable=False)  # ACCESS_REVIEW_ITEM, SECURITY_SIGNAL, POLICY_DRIFT, POLICY_EXCEPTION, ROLE_ASSIGNMENT, MANUAL
    source_id = Column(UUID(as_uuid=True), nullable=True)
    action_type = Column(String(50), nullable=False)  # REVOKE_ROLE, CHANGE_ROLE_SCOPE, EXTEND_ROLE_EXPIRY, REACTIVATE_ROLE, DEACTIVATE_ROLE, REMOVE_REPOSITORY_POLICY_OVERRIDE, APPLY_WORKSPACE_DEFAULT_POLICY, REVOKE_EXCEPTION, MARK_EXCEPTION_EXPIRED, ACKNOWLEDGE_FINDING, MARK_REMEDIATION_NOT_REQUIRED
    status = Column(String(50), nullable=False, default="DRAFT")  # DRAFT, PENDING_CONFIRMATION, CONFIRMED, EXECUTED, FAILED, CANCELLED
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    confirmed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    target_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    target_role = Column(String(50), nullable=True)
    target_assignment_id = Column(UUID(as_uuid=True), nullable=True)
    target_exception_id = Column(UUID(as_uuid=True), nullable=True)
    target_policy_id = Column(UUID(as_uuid=True), nullable=True)
    impact_preview_json = Column(JSON, nullable=False)
    execution_result_json = Column(JSON, nullable=True)
    failure_reason = Column(String(500), nullable=True)
    requires_confirmation = Column(Boolean, nullable=False, default=True)
    confirmation_message = Column(String(1000), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    workspace = relationship("Workspace", foreign_keys=[workspace_id])
    repository = relationship("Repository", foreign_keys=[repository_id])
    requested_by_user = relationship("User", foreign_keys=[requested_by])
    confirmed_by_user = relationship("User", foreign_keys=[confirmed_by])
    target_user = relationship("User", foreign_keys=[target_user_id])
