"""
CI Token Audit Event Model

Tracks all CI token lifecycle and usage events for security auditing.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid
import enum


class AuditEventType(str, enum.Enum):
    """Types of CI token audit events."""
    CI_TOKEN_CREATED = "CI_TOKEN_CREATED"
    CI_TOKEN_USED = "CI_TOKEN_USED"
    CI_TOKEN_REVOKED = "CI_TOKEN_REVOKED"
    CI_TOKEN_REJECTED = "CI_TOKEN_REJECTED"
    PIPELINE_TRIGGERED_BY_CI = "PIPELINE_TRIGGERED_BY_CI"
    ARTIFACT_ACCESSED_BY_CI = "ARTIFACT_ACCESSED_BY_CI"
    ARTIFACT_ACCESS_REJECTED = "ARTIFACT_ACCESS_REJECTED"


class ActorType(str, enum.Enum):
    """Types of actors that trigger audit events."""
    CI = "CI"
    USER = "USER"
    SYSTEM = "SYSTEM"


class CITokenAuditEvent(Base):
    """CI Token Audit Event model."""
    
    __tablename__ = "ci_token_audit_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=True, index=True)
    token_id = Column(UUID(as_uuid=True), ForeignKey("repository_ci_tokens.id"), nullable=True, index=True)
    event_type = Column(SQLEnum(AuditEventType), nullable=False, index=True)
    actor_type = Column(SQLEnum(ActorType), nullable=False)
    source_ip = Column(String(45), nullable=True)  # IPv6 can be up to 45 chars
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)
    reason = Column(Text, nullable=True)  # Used for rejection events
    metadata_json = Column(JSON, nullable=True)
