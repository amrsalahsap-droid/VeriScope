import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class JourneyStep(Base):
    """Ordered step in a user journey flow."""
    __tablename__ = "journey_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journey_id = Column(UUID(as_uuid=True), ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Step ordering
    step_order = Column(Integer, nullable=False, index=True)  # 1, 2, 3, ...
    
    # Step identity
    step_name = Column(String, nullable=False)  # Human-readable step name
    
    # Link to behavior
    behavior_id = Column(UUID(as_uuid=True), ForeignKey("behaviors.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Step properties
    is_optional = Column(Boolean, nullable=False, default=False)
    
    # Audit timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("journey_id", "step_order", name="uq_journey_step_order"),
    )
    
    # Relationships
    journey = relationship("Journey", back_populates="steps")
    behavior = relationship("Behavior", back_populates="journey_steps")
