"""Business Behavior Mapping model for mapping AC to behaviors and scenarios."""
from sqlalchemy import Column, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
from datetime import datetime
import uuid

from app.db.base import Base


class BusinessBehaviorMapping(Base):
    """Represents a mapping from acceptance criteria to behaviors and scenarios."""
    
    __tablename__ = "business_behavior_mappings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Source acceptance criterion (nullable if mapping from business intent directly)
    acceptance_criterion_id = Column(UUID(as_uuid=True), ForeignKey("acceptance_criteria.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Target behavior
    behavior_id = Column(UUID(as_uuid=True), ForeignKey("behaviors.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Target scenario (nullable if no matching scenario exists)
    behavior_scenario_id = Column(UUID(as_uuid=True), ForeignKey("behavior_scenarios.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Journey context
    journey_id = Column(UUID(as_uuid=True), ForeignKey("journeys.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Match confidence (0.0 to 1.0)
    match_confidence = Column(Float, nullable=False, default=0.5)
    
    # Terms that matched
    matched_terms = Column(JSON, nullable=False, default=list)
    
    # Reason for the mapping
    reason = Column(Text, nullable=True)
    
    # Whether this is a candidate missing scenario
    is_candidate_missing_scenario = Column(String, nullable=False, default="false")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    acceptance_criterion = relationship("AcceptanceCriterion", backref="behavior_mappings")
    behavior = relationship("Behavior", backref=backref("business_mappings", cascade="all, delete-orphan"))
    behavior_scenario = relationship("BehaviorScenario", backref="business_mappings")
    journey = relationship("Journey", backref="business_mappings")
    
    def __repr__(self):
        return f"<BusinessBehaviorMapping(id={self.id}, behavior_id={self.behavior_id}, confidence={self.match_confidence})>"
