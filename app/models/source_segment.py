"""Source Segment model for storing structured source text segments."""
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.base import Base


class SegmentDisposition:
    """Disposition of a source segment."""
    ACCEPTANCE_CRITERION = "ACCEPTANCE_CRITERION"
    SECURITY_NOTE = "SECURITY_NOTE"
    ARCHITECTURE_NOTE = "ARCHITECTURE_NOTE"
    TEST_DATA = "TEST_DATA"
    TEST_DATA_LABEL = "TEST_DATA_LABEL"
    HEADING = "HEADING"
    FRAGMENT = "FRAGMENT"
    IMPLEMENTATION_NOTE = "IMPLEMENTATION_NOTE"
    UNKNOWN = "UNKNOWN"


class SourceSegment(Base):
    """Represents a structured segment from source text (PR description, AC artifact, etc.)."""
    
    __tablename__ = "source_segments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=True, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id"), nullable=True, index=True)
    raw_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id"), nullable=True, index=True)
    
    # Source section where this segment was found
    source_section = Column(String(100), nullable=True, index=True)  # "Acceptance Criteria", "Security Notes", "Test Data", etc.
    
    # Index within the source section
    source_index = Column(Integer, nullable=True)
    
    # Original source number if present (e.g., AC-03 would have source_number=3)
    source_number = Column(Integer, nullable=True, index=True)
    
    # Raw text from source
    raw_text = Column(Text, nullable=False)
    
    # Normalized text (cleaned, trimmed)
    normalized_text = Column(Text, nullable=True)
    
    # Disposition classification
    disposition = Column(String(50), nullable=False, default=SegmentDisposition.UNKNOWN, index=True)
    
    # Source hash for deduplication
    source_hash = Column(String(64), nullable=True, index=True)
    
    # Line number in original source
    line_number = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    repository = relationship("Repository", backref="source_segments")
    pull_request = relationship("PullRequest", backref="source_segments")
    raw_artifact = relationship("RawArtifact", backref="source_segments")
    
    def __repr__(self):
        return f"<SourceSegment(id={self.id}, disposition={self.disposition}, source_number={self.source_number}, text='{self.raw_text[:30]}...')>"
