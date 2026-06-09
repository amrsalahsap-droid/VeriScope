import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class BehaviorImpactRun(Base):
    """Immutable collection of business behavior impacts generated for a PR or run."""
    __tablename__ = "behavior_impact_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    
    impact_summary = Column(Text, nullable=True)
    confidence = Column(String, nullable=False)  # HIGH, MODERATE, LOW
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository")
    pull_request = relationship("PullRequest")
    recommendation_run = relationship("RecommendationRun", back_populates="behavior_impact_run")
    items = relationship("BehaviorImpactItem", back_populates="behavior_impact_run", cascade="all, delete-orphan")


class BehaviorImpactItem(Base):
    """Detailed record of impact on a single business behavior."""
    __tablename__ = "behavior_impact_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    behavior_impact_run_id = Column(UUID(as_uuid=True), ForeignKey("behavior_impact_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    behavior_id = Column(UUID(as_uuid=True), ForeignKey("behaviors.id", ondelete="CASCADE"), nullable=False, index=True)
    journey_id = Column(UUID(as_uuid=True), ForeignKey("journeys.id", ondelete="SET NULL"), nullable=True, index=True)
    
    impact_level = Column(String, nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    confidence = Column(String, nullable=False)    # HIGH, MODERATE, LOW
    impact_reason = Column(Text, nullable=True)
    
    source_signals = Column(JSONB, nullable=False, default=list)    # e.g., ["EVIDENCE_PATH_MATCH"]
    impacted_files = Column(JSONB, nullable=False, default=list)    # e.g., ["auth/reset-password/api.py"]
    affected_scenarios = Column(JSONB, nullable=False, default=list) # List of affected scenarios
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    behavior_impact_run = relationship("BehaviorImpactRun", back_populates="items")
    behavior = relationship("Behavior")
    journey = relationship("Journey")
