import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class RepositorySemanticEntry(Base):
    """Repository-scoped semantic metadata for behavior discovery and SME engines."""
    __tablename__ = "repository_semantic_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)

    # Entry classification
    entry_type = Column(String, nullable=False, index=True)  # ROUTE, PAGE, MODULE, SERVICE, TEST, README, DOC, CONFIG
    path = Column(Text, nullable=False, index=True)  # File path or identifier

    # Semantic tokens (deterministically tokenized)
    normalized_tokens = Column(ARRAY(String), nullable=False)  # Array of normalized tokens

    # Confidence score for this entry
    confidence = Column(String, nullable=False, index=True)  # HIGH, MODERATE, LOW

    # Additional metadata (optional)
    entry_metadata = Column(JSONB, nullable=True)  # Flexible metadata for different entry types

    # Audit timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        Index("ix_semantic_entries_repo_type", "repository_id", "entry_type"),
        Index("ix_semantic_entries_tokens", "normalized_tokens", postgresql_using="gin"),
    )

    # Relationships
    repository = relationship("Repository", back_populates="semantic_entries")
