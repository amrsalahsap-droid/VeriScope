"""
CI/CD Policy Audit Model

Stores audit events for CI/CD policy changes and manual overrides.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class CICDPolicyAuditEvent(Base):
    """Audit event for CI/CD policy changes."""
    
    __tablename__ = "ci_cd_policy_audit_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Event type: CREATED, UPDATED, PREVIEWED, MANUAL_OVERRIDE
    event_type = Column(String(50), nullable=False)
    
    # Actor information
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_type = Column(String(50), nullable=True)  # USER, SYSTEM
    
    # Policy state before and after
    before_policy = Column(JSON, nullable=True)
    after_policy = Column(JSON, nullable=True)
    changed_fields = Column(JSON, nullable=True)  # List of field names
    
    # Override information
    original_quality_gate = Column(String(50), nullable=True)
    override_decision = Column(String(50), nullable=True)
    override_reason = Column(Text, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
