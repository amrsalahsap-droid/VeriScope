"""Release Decision Domain Models."""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
from app.db.base import Base

# Enums
DecisionStatus = ENUM(
    'PENDING_REVIEW',
    'APPROVED',
    'REJECTED',
    'CONDITIONALLY_APPROVED',
    name='decision_status'
)


class ReleaseDecision(Base):
    """Governance decision for release approval/rejection."""
    __tablename__ = "release_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recommendation_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Decision status
    decision_status = Column(DecisionStatus, nullable=False, default="PENDING_REVIEW")
    
    # Approver information
    approver_id = Column(UUID(as_uuid=True), nullable=True)
    approver_name = Column(String, nullable=True)
    
    # Decision context
    decision_note = Column(Text, nullable=True)
    snapshot_hash = Column(String, nullable=True)
    evidence_health_status = Column(String, nullable=True)
    readiness_state = Column(String, nullable=True)
    
    # Risk-aware decision recommendations (Phase 3.3)
    decision_recommendations = Column(JSON, nullable=True)
    decision_reasoning = Column(JSON, nullable=True)
    required_before_release = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Active flag for historical preservation
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    recommendation_run = relationship("RecommendationRun")
    history = relationship("ReleaseDecisionHistory", back_populates="release_decision", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ReleaseDecision(run_id={self.recommendation_run_id}, status={self.decision_status}, approver={self.approver_name})>"
