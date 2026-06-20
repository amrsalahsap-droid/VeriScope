import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class BehaviorEvidence(Base):
    """Evidence rows supporting behavior discovery and validation."""
    __tablename__ = "behavior_evidences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    behavior_id = Column(UUID(as_uuid=True), ForeignKey("behaviors.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Evidence classification
    evidence_type = Column(String, nullable=False, index=True)  # ROUTE, PAGE, MODULE, TEST, PR_TITLE, PR_DESCRIPTION, README, CONFIG, MANUAL
    
    # Source identification
    source_path = Column(String, nullable=True)  # File path or URL
    source_name = Column(String, nullable=True)  # Human-readable source name
    
    # Evidence content
    excerpt = Column(Text, nullable=True)  # Relevant code excerpt or text snippet
    
    # Confidence assessment
    confidence = Column(String, nullable=False)  # HIGH, MODERATE, LOW
    
    # Audit timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        Index("ix_behavior_evidences_behavior_type", "behavior_id", "evidence_type"),
        Index("ix_behavior_evidences_source_path", "source_path"),
    )
    
    # Relationships
    behavior = relationship("Behavior", back_populates="evidences")
