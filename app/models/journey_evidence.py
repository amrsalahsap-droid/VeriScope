import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class JourneyEvidence(Base):
    """Evidence supporting journey discovery and validation."""
    __tablename__ = "journey_evidences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journey_id = Column(UUID(as_uuid=True), ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Evidence classification
    evidence_type = Column(String, nullable=False, index=True)  # BEHAVIOR_CLUSTER, ROUTE_CLUSTER, TEST_CLUSTER, DOCUMENTATION, PR_HISTORY
    
    # Source information
    source = Column(String, nullable=True, index=True)  # Where the evidence came from
    
    # Evidence content
    excerpt = Column(Text, nullable=True)  # Relevant excerpt or description
    
    # Confidence in this evidence
    confidence = Column(String, nullable=False)  # HIGH, MODERATE, LOW
    
    # Audit timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    journey = relationship("Journey", back_populates="evidences")
