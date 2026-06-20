"""
Governance Access Review Item Model

Represents a single finding item generated during an access review run.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class GovernanceAccessReviewItem(Base):
    """Access review item finding model."""
    
    __tablename__ = "governance_access_review_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id = Column(UUID(as_uuid=True), ForeignKey("governance_access_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)
    scope_type = Column(String(50), nullable=False)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True, index=True)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("governance_role_assignments.id", ondelete="SET NULL"), nullable=True, index=True)
    risk_level = Column(String(50), nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW
    finding_type = Column(String(100), nullable=False)  # PRIVILEGED_ROLE, STALE_ROLE, etc.
    finding_message = Column(String(500), nullable=False)
    recommendation = Column(String(500), nullable=False)
    review_status = Column(String(50), nullable=False, default="PENDING")  # PENDING, APPROVED, REVOKE_RECOMMENDED, etc.
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    decision_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    review = relationship("GovernanceAccessReview", back_populates="items")
    workspace = relationship("Workspace", foreign_keys=[workspace_id])
    user = relationship("User", foreign_keys=[user_id])
    repository = relationship("Repository", foreign_keys=[repository_id])
    assignment = relationship("GovernanceRoleAssignment", foreign_keys=[assignment_id])
