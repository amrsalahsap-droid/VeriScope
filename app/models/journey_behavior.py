import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class JourneyBehavior(Base):
    """Mapping between journeys and behaviors with relationship classification."""
    __tablename__ = "journey_behaviors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journey_id = Column(UUID(as_uuid=True), ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False, index=True)
    behavior_id = Column(UUID(as_uuid=True), ForeignKey("behaviors.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationship classification
    relationship_type = Column(String, nullable=False, index=True)  # PRIMARY, SUPPORTING, DEPENDENT
    
    # Confidence in this mapping
    confidence = Column(String, nullable=False)  # HIGH, MODERATE, LOW
    
    # Audit timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("journey_id", "behavior_id", name="uq_journey_behavior"),
    )
    
    # Relationships
    journey = relationship("Journey", back_populates="journey_behaviors")
    behavior = relationship("Behavior", back_populates="journey_behaviors")
