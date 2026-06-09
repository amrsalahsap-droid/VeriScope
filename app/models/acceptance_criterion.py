"""Acceptance Criterion model for extracting and storing acceptance criteria from PRs."""
from sqlalchemy import Column, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.base import Base


class AcceptanceCriterion(Base):
    """Represents an acceptance criterion extracted from a PR description or linked story."""
    
    __tablename__ = "acceptance_criteria"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id"), nullable=True, index=True)
    
    # Original criterion text
    text = Column(Text, nullable=False)
    
    # Normalized key for deduplication
    normalized_key = Column(String(500), nullable=False, index=True)
    
    # Type of criterion
    criterion_type = Column(
        String(50),
        nullable=False,
        default="UNKNOWN"
    )  # FUNCTIONAL, VALIDATION, SECURITY, UI, API, INTEGRATION, PERFORMANCE, DATABASE, UNKNOWN
    
    # Source of the criterion
    source = Column(String(100), nullable=False)  # PR_DESCRIPTION, LINKED_STORY, COMMIT_MESSAGE, etc.
    
    # Confidence in extraction (0.0 to 1.0)
    confidence = Column(Float, nullable=False, default=0.5)
    
    # Excerpt from source text for evidence
    evidence_excerpt = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    repository = relationship("Repository", back_populates="acceptance_criteria")
    pull_request = relationship("PullRequest", back_populates="acceptance_criteria")
    
    def __repr__(self):
        return f"<AcceptanceCriterion(id={self.id}, text='{self.text[:50]}...', type={self.criterion_type})>"
