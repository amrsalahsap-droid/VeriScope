import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base

class ProjectContextIndex(Base):
    """Structured, deterministic project understanding layer per repository."""
    __tablename__ = "project_context_indices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)

    detected_frameworks = Column(JSONB, nullable=False, default=list)
    routes = Column(JSONB, nullable=False, default=list)
    pages = Column(JSONB, nullable=False, default=list)
    api_endpoints = Column(JSONB, nullable=False, default=list)
    modules = Column(JSONB, nullable=False, default=list)
    domains = Column(JSONB, nullable=False, default=list)
    user_journeys = Column(JSONB, nullable=False, default=list)
    test_assets = Column(JSONB, nullable=False, default=list)
    security_sensitive_areas = Column(JSONB, nullable=False, default=list)

    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    confidence = Column(String, nullable=False) # e.g. "HIGH", "MODERATE", "LOW"

    # Relationships
    repository = relationship("Repository", back_populates="project_context_indices")
