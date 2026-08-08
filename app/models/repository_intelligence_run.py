import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base

class RepositoryIntelligenceRun(Base):
    """Tracks history, status, and metadata of repository intelligence refreshes."""
    __tablename__ = "repository_intelligence_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    head_commit_sha = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="PENDING")  # PENDING, SUCCESS, PARTIAL, FAILED
    error_message = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    partial_errors_json = Column(JSONB, nullable=True)
    completed_steps_json = Column(JSONB, nullable=True)
    failed_steps_json = Column(JSONB, nullable=True)

    # Relationships
    repository = relationship("Repository", back_populates="intelligence_runs")
    pull_request = relationship("PullRequest")
