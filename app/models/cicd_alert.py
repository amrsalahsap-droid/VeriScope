"""
CI/CD Alert Model

Represents operational alerts for CI/CD integration health and failures.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, JSON, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class AlertSeverity(str, Enum):
    """Severity level of an alert."""
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(str, Enum):
    """Type of CI/CD alert."""
    PIPELINE_BACKLOG_HIGH = "PIPELINE_BACKLOG_HIGH"
    PIPELINE_DEAD_LETTER_PRESENT = "PIPELINE_DEAD_LETTER_PRESENT"
    GITHUB_PUBLISHING_FAILURE_SPIKE = "GITHUB_PUBLISHING_FAILURE_SPIKE"
    PR_COMMENT_FAILURE_SPIKE = "PR_COMMENT_FAILURE_SPIKE"
    ARTIFACT_FAILURE_SPIKE = "ARTIFACT_FAILURE_SPIKE"
    CI_TOKEN_REJECTION_SPIKE = "CI_TOKEN_REJECTION_SPIKE"
    WEBHOOK_FAILURE_SPIKE = "WEBHOOK_FAILURE_SPIKE"
    GITHUB_RATE_LIMIT_ACTIVE = "GITHUB_RATE_LIMIT_ACTIVE"
    NO_RECENT_SUCCESSFUL_PIPELINE = "NO_RECENT_SUCCESSFUL_PIPELINE"
    WORKER_STALE_OR_INACTIVE = "WORKER_STALE_OR_INACTIVE"


class CICDAlert(Base):
    """Operational alert for CI/CD integration."""
    
    __tablename__ = "cicd_alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    
    alert_type = Column(SQLEnum(AlertType), nullable=False, index=True)
    severity = Column(SQLEnum(AlertSeverity), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=True)
    
    # Optional links to related entities
    pipeline_run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=True, index=True)
    pipeline_job_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_execution_jobs.id"), nullable=True, index=True)
    
    # Additional metadata
    metadata_json = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    repository = relationship("Repository", backref="cicd_alerts")
    pipeline_run = relationship("PipelineRun", backref="cicd_alerts")
    pipeline_job = relationship("PipelineExecutionJob", backref="cicd_alerts")
    
    def __repr__(self):
        return f"<CICDAlert(id={self.id}, type={self.alert_type}, severity={self.severity}, title={self.title})>"
    
    def is_resolved(self) -> bool:
        """Check if alert is resolved."""
        return self.resolved_at is not None
    
    def resolve(self):
        """Mark alert as resolved."""
        self.resolved_at = datetime.utcnow()
