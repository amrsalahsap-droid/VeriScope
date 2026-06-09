import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, synonym
from app.db.base import Base


class BehaviorScenario(Base):
    """Expected business behavior validation scenarios."""
    __tablename__ = "behavior_scenarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    behavior_id = Column(UUID(as_uuid=True), ForeignKey("behaviors.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Scenario definition
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Classification
    priority = Column(String, nullable=False, index=True)  # BLOCKER, MUST, SHOULD, OPTIONAL
    scenario_type = Column(String, nullable=False, default="POSITIVE", index=True)  # POSITIVE, NEGATIVE, EDGE, SECURITY, REGRESSION
    case_type = synonym("scenario_type")
    status = Column(String, nullable=False, default="ACTIVE", index=True)  # ACTIVE, DEPRECATED, ARCHIVED
    
    # Audit timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        Index("ix_behavior_scenarios_behavior_priority", "behavior_id", "priority"),
        Index("ix_behavior_scenarios_behavior_type", "behavior_id", "scenario_type"),
    )
    
    # Relationships
    behavior = relationship("Behavior", back_populates="scenarios")
    external_test_mappings = relationship("ExternalTestScenarioMapping", back_populates="behavior_scenario")
