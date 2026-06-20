"""
Governance Access Review Model

Represents a scheduled or on-demand governance access review run.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class GovernanceAccessReview(Base):
    """Access review run model."""
    
    __tablename__ = "governance_access_reviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    review_name = Column(String(100), nullable=False)
    review_type = Column(String(50), nullable=False)  # QUARTERLY_ACCESS_REVIEW, PRIVILEGED_ROLE_REVIEW, etc.
    status = Column(String(50), nullable=False, default="DRAFT")  # DRAFT, IN_PROGRESS, COMPLETED, CANCELLED
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    summary_json = Column(JSON, nullable=True)
    
    # Relationships
    workspace = relationship("Workspace", foreign_keys=[workspace_id])
    items = relationship("GovernanceAccessReviewItem", back_populates="review", cascade="all, delete-orphan")
