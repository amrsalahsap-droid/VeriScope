"""
Pipeline Run Model

Represents a CI/CD pipeline run that triggers or is linked to a Veriscope recommendation.
Used for GitHub Actions and other CI providers.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, JSON, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class PipelineRunStatus(str, Enum):
    """Status of a pipeline run."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class QualityGateStatus(str, Enum):
    """Quality gate result for CI/CD."""
    PASSED = "PASSED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class TriggerSource(str, Enum):
    """Source that triggered the pipeline run."""
    PULL_REQUEST = "pull_request"
    PUSH = "push"
    MANUAL = "manual"
    WEBHOOK = "webhook"


class PipelineRun(Base):
    """CI/CD pipeline run linked to a Veriscope recommendation."""
    
    __tablename__ = "pipeline_runs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id"), nullable=True, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id"), nullable=True, index=True)
    
    provider = Column(String(50), nullable=False)  # e.g., "GITHUB_ACTIONS", "GITLAB_CI"
    external_run_id = Column(String(255), nullable=False, index=True)  # External CI run ID
    commit_sha = Column(String(255), nullable=False)
    branch = Column(String(255), nullable=True)
    
    status = Column(SQLEnum(PipelineRunStatus), default=PipelineRunStatus.PENDING, nullable=False, index=True)
    quality_gate = Column(SQLEnum(QualityGateStatus), default=QualityGateStatus.UNKNOWN, nullable=False)
    trigger_source = Column(SQLEnum(TriggerSource), default=TriggerSource.PULL_REQUEST, nullable=False)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    metadata_json = Column(JSON, nullable=True)  # Additional CI metadata
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    repository = relationship("Repository", back_populates="pipeline_runs")
    recommendation_run = relationship("RecommendationRun", back_populates="pipeline_runs")
    pull_request = relationship("PullRequest", back_populates="pipeline_runs")
    
    def __repr__(self):
        return f"<PipelineRun(id={self.id}, provider={self.provider}, external_run_id={self.external_run_id}, status={self.status}, quality_gate={self.quality_gate})>"
