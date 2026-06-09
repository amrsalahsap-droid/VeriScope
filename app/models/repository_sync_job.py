import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, BigInteger, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class RepositorySyncJob(Base):
    __tablename__ = "repository_sync_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    github_installation_id = Column(BigInteger, nullable=False, index=True)
    
    # Statuses: PENDING, PROCESSING, COMPLETED, FAILED, RETRYING
    status = Column(String, nullable=False, default="PENDING", index=True)
    
    # Reasons: INSTALLATION_CALLBACK, INSTALLATION_REPOSITORIES_EVENT, MANUAL_RETRY, PERIODIC_RECONCILIATION
    sync_reason = Column(String, nullable=False, index=True)
    
    # Evidence Health: HEALTHY, DEGRADED, INSUFFICIENT
    evidence_health_status = Column(String, nullable=False, default="HEALTHY", index=True)
    
    # Timing
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Diagnostics & Retries
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    
    # Metrics
    total_repositories_seen = Column(Integer, nullable=False, default=0)
    repositories_created = Column(Integer, nullable=False, default=0)
    repositories_updated = Column(Integer, nullable=False, default=0)
    repositories_marked_inactive = Column(Integer, nullable=False, default=0)
    
    # Pagination Integrity
    pagination_completed = Column(Boolean, nullable=False, default=False)
    pages_expected = Column(Integer, nullable=True)
    pages_received = Column(Integer, nullable=False, default=0)
    last_page_url = Column(String, nullable=True)
    
    # Forensic Snapshot Link
    repository_sync_snapshot_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id", ondelete="SET NULL"), nullable=True)
    
    # Integrity: NOT_STARTED, FULL_SUCCESS, PARTIAL_FAILURE, FAILED_BEFORE_COMPLETION
    integrity_status = Column(String, nullable=False, default="NOT_STARTED", index=True)
