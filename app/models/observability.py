import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base

class IngestionJob(Base):
    """Logs the asynchronous parsing jobs and pipeline health."""
    __tablename__ = "ingestion_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(String, nullable=False, index=True) # webhook_parsing, junit_parsing, coverage_ingestion
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, index=True) # PENDING, RUNNING, COMPLETED, FAILED
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    repository = relationship("Repository", back_populates="ingestion_jobs")

class SystemEvent(Base):
    """System event timeline for diagnostic audits."""
    __tablename__ = "system_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String, nullable=False, index=True) # pr, recommendation_run, deployment, rollback
    entity_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True) # pr_opened, recommendation_generated, deployed, rolled_back
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
