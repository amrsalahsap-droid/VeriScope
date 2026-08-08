"""Acceptance Criterion model for extracting and storing acceptance criteria from PRs."""
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, ForeignKey
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
    requirement_group_id = Column(UUID(as_uuid=True), ForeignKey("requirement_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Source section where this AC was found
    source_section = Column(String(100), nullable=True, index=True)  # "Acceptance Criteria", etc.
    
    # Original source number (e.g., AC-03 would have source_number=3)
    source_number = Column(Integer, nullable=True, index=True)
    
    # Expanded requirement-group AC properties
    ac_number = Column(Integer, nullable=True)
    stable_ac_key = Column(String(500), nullable=True, index=True)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    source_type = Column(String(100), nullable=True)
    source_id = Column(String(200), nullable=True)
    priority = Column(String(50), nullable=True)
    criticality = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, default="NEEDS_REVIEW") # NEEDS_REVIEW, ACCEPTED, REJECTED
    version = Column(Integer, nullable=False, default=1)
    
    # Original criterion text
    text = Column(Text, nullable=False)
    
    # Human-readable label (e.g., "AC-01 Weak passwords are rejected during sign-up")
    label = Column(String(500), nullable=True)
    
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
    group = relationship("RequirementGroup", back_populates="acceptance_criteria")
    testable_scenarios = relationship("TestableScenario", back_populates="acceptance_criterion", cascade="all, delete-orphan")
    mapping_candidates = relationship("MappingCandidate", foreign_keys="[MappingCandidate.acceptance_criterion_id]", cascade="all, delete-orphan")
    semantic_match_candidates = relationship("MappingCandidate", foreign_keys="[MappingCandidate.semantic_best_match_ac_id]", cascade="all, delete-orphan")
    
    @property
    def identifier(self) -> str:
        """Returns AC-XX format identifier."""
        if self.source_number is not None:
            return f"AC-{str(self.source_number).zfill(2)}"
        if self.ac_number is not None:
            return f"AC-{str(self.ac_number).zfill(2)}"
        # Fallback: use database ID
        return f"AC-{self.id}"

    @property
    def ac_id(self) -> str:
        return self.stable_ac_key or self.identifier

    @property
    def statement(self) -> str:
        return self.text or self.description or ""
        
    def __repr__(self):
        return f"<AcceptanceCriterion(id={self.id}, source_number={self.source_number}, text='{self.text[:50]}...', type={self.criterion_type})>"

