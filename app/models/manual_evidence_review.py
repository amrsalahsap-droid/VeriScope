"""
Manual Evidence Review Model

Governance and trust controls for manual evidence executions.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class ManualEvidenceReview(Base):
    """Governance review for manual test executions."""
    
    __tablename__ = "manual_evidence_reviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manual_test_execution_id = Column(UUID(as_uuid=True), ForeignKey("manual_test_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Governance status
    review_status = Column(String, nullable=False, default="PENDING_REVIEW")  # PENDING_REVIEW, APPROVED, REJECTED, CHALLENGED
    
    # Review metadata
    review_note = Column(Text, nullable=True)
    reviewed_by_id = Column(UUID(as_uuid=True), nullable=True)
    reviewed_by_name = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Active flag for history preservation
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    manual_test_execution = relationship("ManualTestExecution", backref="reviews")
    repository = relationship("Repository", backref="manual_evidence_reviews")
    
    def __repr__(self):
        return f"<ManualEvidenceReview(id={self.id}, status={self.review_status}, execution_id={self.manual_test_execution_id})>"
