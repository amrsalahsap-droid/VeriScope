"""
Workspace Governance Audit Event Model

Stores workspace-level governance audit events for bulk operations and other governance actions.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid


class WorkspaceGovernanceAuditEvent(Base):
    """Workspace-level governance audit event."""
    
    __tablename__ = "workspace_governance_audit_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    target_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)  # CI_CD_BULK_POLICY_PREVIEWED, CI_CD_BULK_POLICY_APPLIED, etc.
    operation_id = Column(UUID(as_uuid=True), nullable=True)  # For bulk operations
    permission = Column(String, nullable=True)
    role = Column(String, nullable=True)
    decision = Column(String, nullable=True)
    requested_count = Column(Integer, nullable=True)
    succeeded_count = Column(Integer, nullable=True)
    failed_count = Column(Integer, nullable=True)
    skipped_count = Column(Integer, nullable=True)
    reason = Column(String, nullable=True)
    audit_metadata = Column(JSON, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    workspace = relationship("Workspace", backref="governance_audit_events")

    @property
    def actor_user_id(self):
        return self.actor_id

    @actor_user_id.setter
    def actor_user_id(self, value):
        self.actor_id = value
