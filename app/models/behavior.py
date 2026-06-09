import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class Behavior(Base):
    """Repository-scoped business behavior catalog for durable knowledge storage."""
    __tablename__ = "behaviors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    journey_id = Column(UUID(as_uuid=True), ForeignKey("journeys.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Core identity
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    journey_name = Column(String, nullable=True)  # Legacy field, kept for backward compatibility
    
    # Risk and status classification
    risk_level = Column(String, nullable=False, index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    risk_reason = Column(Text, nullable=True)  # Explainable reason for risk assignment
    risk_evidence = Column(Text, nullable=True)  # Evidence supporting risk classification
    status = Column(String, nullable=False, default="DISCOVERED", index=True)  # DISCOVERED, REVIEWED, CONFIRMED, ARCHIVED
    confidence = Column(String, nullable=True)  # HIGH, MODERATE, LOW
    
    # Discovery provenance
    discovery_source = Column(String, nullable=False, default="AUTO_DISCOVERED", index=True)  # AUTO_DISCOVERED, MANUAL, PR_INFERRED, TEST_INFERRED, ROUTE_INFERRED
    
    # Soft delete flag
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Audit timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("repository_id", "slug", name="uq_behaviors_repo_slug"),
        Index("ix_behaviors_repo_journey", "repository_id", "journey_id"),
        Index("ix_behaviors_repo_status", "repository_id", "status"),
    )
    
    # Relationships
    repository = relationship("Repository", back_populates="behaviors")
    journey = relationship("Journey", back_populates="behaviors")
    external_test_cases = relationship("ExternalTestCase", back_populates="behavior")
    work_item_mappings = relationship("WorkItemBehaviorMapping", back_populates="behavior")
    external_test_scenario_mappings = relationship("ExternalTestScenarioMapping", back_populates="behavior")
    evidences = relationship("BehaviorEvidence", back_populates="behavior", cascade="all, delete-orphan")
    scenarios = relationship("BehaviorScenario", back_populates="behavior", cascade="all, delete-orphan")
    journey_behaviors = relationship("JourneyBehavior", back_populates="behavior", cascade="all, delete-orphan")
    journey_steps = relationship("JourneyStep", back_populates="behavior")
