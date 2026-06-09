import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, BigInteger, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint
from app.db.base import Base

class GitHubInstallation(Base):
    __tablename__ = "github_installations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # GitHub App installation details
    installation_id = Column(BigInteger, nullable=False, index=True)  # GitHub's installation ID
    github_installation_id = Column(BigInteger, nullable=False, unique=True, index=True)  # Legacy field, same as installation_id
    github_account_login = Column(String, nullable=False)  # Organization or user login
    github_account_id = Column(BigInteger, nullable=True)  # GitHub account ID
    github_account_type = Column(String, nullable=False)  # "Organization" or "User"
    
    # Installation permissions and selection
    permissions = Column(JSONB, nullable=True)  # GitHub App permissions granted
    repository_selection = Column(String, nullable=False, default="all")  # "all" or "selected"
    
    # Installation status
    installed_by = Column(String, nullable=True)  # User who installed
    installed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    suspended_at = Column(DateTime, nullable=True)  # When installation was suspended
    
    # Lifecycle status: PENDING_SYNC, ACTIVE, FAILED_SYNC, SUSPENDED, REMOVED
    status = Column(String, nullable=False, default="PENDING_SYNC")
    
    # Evidence Health: HEALTHY, DEGRADED, INSUFFICIENT
    evidence_health_status = Column(String, nullable=False, default="HEALTHY")
    
    # Lightweight Concurrency Sync Lock
    active_sync_job_id = Column(UUID(as_uuid=True), nullable=True)
    sync_lock_acquired_at = Column(DateTime, nullable=True)
    
    # Operational Sync History
    last_sync_started_at = Column(DateTime, nullable=True)
    last_sync_completed_at = Column(DateTime, nullable=True)
    last_successful_sync_at = Column(DateTime, nullable=True)
    consecutive_sync_failures = Column(Integer, nullable=False, default=0)
    last_sync_error = Column(String, nullable=True)
    last_github_event_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint: workspace_id + installation_id
    __table_args__ = (
        UniqueConstraint('workspace_id', 'installation_id', name='uq_workspace_installation'),
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="github_installation")
