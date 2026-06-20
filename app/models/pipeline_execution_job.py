"""
Pipeline Execution Job Model

Represents an async job for processing pipeline runs in the background.
Provides durable queue with retry, backoff, and recovery capabilities.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, JSON, Enum as SQLEnum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class PipelineJobStatus(str, Enum):
    """Status of a pipeline execution job."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    RETRY_PENDING = "RETRY_PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"
    CANCELLED = "CANCELLED"


class PipelineExecutionJob(Base):
    """Async job for processing pipeline runs."""
    
    __tablename__ = "pipeline_execution_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id"), nullable=True, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id"), nullable=True, index=True)
    
    status = Column(SQLEnum(PipelineJobStatus), default=PipelineJobStatus.PENDING, nullable=False, index=True)
    
    # Retry and backoff fields
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Locking for atomic claiming
    locked_at = Column(DateTime(timezone=True), nullable=True)
    locked_by = Column(String(255), nullable=True)  # Worker identifier
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    last_error_type = Column(String(255), nullable=True)
    
    # Additional metadata
    metadata_json = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    pipeline_run = relationship("PipelineRun", backref="execution_jobs")
    repository = relationship("Repository", backref="pipeline_execution_jobs")
    pull_request = relationship("PullRequest", backref="pipeline_execution_jobs")
    recommendation_run = relationship("RecommendationRun", backref="pipeline_execution_jobs")
    
    def __repr__(self):
        return f"<PipelineExecutionJob(id={self.id}, pipeline_run_id={self.pipeline_run_id}, status={self.status}, attempt_count={self.attempt_count})>"
    
    def is_claimable(self):
        """Check if job can be claimed by a worker."""
        if self.status in (PipelineJobStatus.PENDING, PipelineJobStatus.RETRY_PENDING):
            if self.next_attempt_at is None or self.next_attempt_at <= datetime.utcnow():
                return True
        return False
    
    def is_stale(self, threshold_minutes=10):
        """Check if job is stale (locked too long without completion)."""
        if self.status == PipelineJobStatus.IN_PROGRESS and self.locked_at:
            threshold = datetime.utcnow() - threshold_minutes
            return self.locked_at < threshold
        return False
    
    def should_retry(self):
        """Check if job should be retried."""
        return self.attempt_count < self.max_attempts and self.status == PipelineJobStatus.RETRY_PENDING
