import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class JourneyRelationship(Base):
    """Cross-journey dependency relationships with evidence backing."""
    __tablename__ = "journey_relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_journey_id = Column(UUID(as_uuid=True), ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False, index=True)
    target_journey_id = Column(UUID(as_uuid=True), ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationship type
    relationship_type = Column(String, nullable=False)  # DEPENDS_ON, TRIGGERS, EXTENDS
    
    # Evidence backing
    evidence_type = Column(String, nullable=False)  # CODE_REFERENCE, BEHAVIOR_LINK, FLOW_TRANSITION, USER_FLOW
    evidence_source = Column(String, nullable=False)  # File path, behavior name, etc.
    evidence_excerpt = Column(String, nullable=True)  # Supporting code/text excerpt
    confidence = Column(String, nullable=False)  # HIGH, MODERATE, LOW
    
    # Additional context
    relationship_description = Column(String, nullable=True)
    impact_analysis = Column(JSONB, nullable=True)  # Impact analysis for cross-journey scenarios
    
    # Audit
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    source_journey = relationship("Journey", foreign_keys=[source_journey_id])
    target_journey = relationship("Journey", foreign_keys=[target_journey_id])
