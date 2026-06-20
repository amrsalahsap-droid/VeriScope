"""
CI/CD Policy Exception Model

Stores policy exceptions for repositories that intentionally deviate from workspace default.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid


class CICDPolicyException(Base):
    """Policy exception for repository deviation from workspace default."""
    
    __tablename__ = "ci_cd_policy_exceptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    requested_by = Column(UUID(as_uuid=True), nullable=False)
    approved_by = Column(UUID(as_uuid=True), nullable=True)
    status = Column(String, nullable=False, default="PENDING", index=True)  # PENDING, APPROVED, REJECTED, EXPIRED, REVOKED
    reason = Column(Text, nullable=False)
    exception_fields = Column(JSON, nullable=False)  # List of fields this exception covers
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    decision_reason = Column(Text, nullable=True)
    
    # Relationships
    workspace = relationship("Workspace", backref="policy_exceptions")
    repository = relationship("Repository", backref="policy_exceptions")
