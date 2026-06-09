import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class Journey(Base):
    """Repository-scoped user journey catalog for standardized business flows."""
    __tablename__ = "journeys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Core identity
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True, default=lambda: str(uuid.uuid4())[:8])
    description = Column(Text, nullable=True)
    
    # Business value
    business_value = Column(Text, nullable=True)
    
    # Risk classification
    risk_level = Column(String, nullable=False, index=True, default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Status
    status = Column(String, nullable=False, default="DISCOVERED", index=True)  # DISCOVERED, REVIEWED, CONFIRMED, ARCHIVED
    
    # Soft delete
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    
    # Audit timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("repository_id", "slug", name="uq_journeys_repo_slug"),
    )
    
    # Relationships
    repository = relationship("Repository", back_populates="journeys")
    behaviors = relationship("Behavior", back_populates="journey")
    journey_behaviors = relationship("JourneyBehavior", back_populates="journey", cascade="all, delete-orphan")
    evidences = relationship("JourneyEvidence", back_populates="journey", cascade="all, delete-orphan")
    steps = relationship("JourneyStep", back_populates="journey", cascade="all, delete-orphan")
    outgoing_relationships = relationship("JourneyRelationship", foreign_keys="JourneyRelationship.source_journey_id", back_populates="source_journey", cascade="all, delete-orphan")
    incoming_relationships = relationship("JourneyRelationship", foreign_keys="JourneyRelationship.target_journey_id", back_populates="target_journey", cascade="all, delete-orphan")
    external_test_cases = relationship("ExternalTestCase", back_populates="journey")
    work_item_mappings = relationship("WorkItemBehaviorMapping", back_populates="journey")
