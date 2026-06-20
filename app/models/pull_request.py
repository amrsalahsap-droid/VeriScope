import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, BigInteger, Boolean, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base

class PullRequest(Base):
    """Authoritative state of a GitHub Pull Request."""
    __tablename__ = "pull_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    github_pr_id = Column(BigInteger, index=True, nullable=False)
    number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    author = Column(String, nullable=False)
    source_branch = Column(String, nullable=False)
    target_branch = Column(String, nullable=False)
    state = Column(String, nullable=False) # "open", "closed"
    additions = Column(Integer, nullable=False, default=0)
    deletions = Column(Integer, nullable=False, default=0)
    changed_files_count = Column(Integer, nullable=False, default=0)
    head_commit_sha = Column(String, nullable=False)
    merged = Column(Boolean, nullable=False, default=False)
    merged_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    github_created_at = Column(DateTime, nullable=False)
    github_updated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync integrity & calibration health fields
    sync_integrity_status = Column(String, nullable=False, default="UNKNOWN") # FULL_SUCCESS, PARTIAL_FAILURE, FAILED, UNKNOWN
    evidence_health_status = Column(String, nullable=False, default="HEALTHY") # HEALTHY, DEGRADED, INSUFFICIENT
    evidence_consistency_status = Column(String, nullable=False, default="UNKNOWN") # CONSISTENT, PARTIALLY_INCONSISTENT, BROKEN, UNKNOWN
    last_sync_started_at = Column(DateTime, nullable=True)
    last_sync_completed_at = Column(DateTime, nullable=True)
    last_successful_sync_at = Column(DateTime, nullable=True)
    last_sync_error = Column(String, nullable=True)
    active_sync_job_id = Column(UUID(as_uuid=True), nullable=True)
    evidence_truncated = Column(Boolean, nullable=False, default=False)
    truncation_reason = Column(String, nullable=True)
    unsafe_for_optimization = Column(Boolean, nullable=False, default=False)
    
    # Event Ordering and Resync Clock
    last_github_updated_at = Column(DateTime, nullable=True)
    last_processed_delivery_id = Column(String, nullable=True)
    reconciliation_required = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("repository_id", "github_pr_id", name="uq_pull_request_repo_github_pr_id"),
    )

    # Relationships
    repository = relationship("Repository", back_populates="pull_requests")
    commits = relationship("PullRequestCommit", back_populates="pull_request", cascade="all, delete-orphan")
    changed_files = relationship("PullRequestChangedFile", back_populates="pull_request", cascade="all, delete-orphan")
    sync_jobs = relationship("PullRequestSyncJob", back_populates="pull_request", cascade="all, delete-orphan")
    snapshots = relationship("PullRequestSnapshot", back_populates="pull_request", cascade="all, delete-orphan")
    acceptance_criteria = relationship("AcceptanceCriterion", back_populates="pull_request", cascade="all, delete-orphan")
    work_item_links = relationship("PullRequestWorkItemLink", back_populates="pull_request", cascade="all, delete-orphan")
    pipeline_runs = relationship("PipelineRun", back_populates="pull_request", cascade="all, delete-orphan")


class PullRequestCommit(Base):
    """Authoritative list of commits for a pull request."""
    __tablename__ = "pull_request_commits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    sha = Column(String, index=True, nullable=False)
    message = Column(String, nullable=False)
    author = Column(String, nullable=False)
    author_email = Column(String, nullable=True)
    commit_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    pull_request = relationship("PullRequest", back_populates="commits")


class PullRequestChangedFile(Base):
    """Authoritative list of changed files for a pull request."""
    __tablename__ = "pull_request_changed_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String, index=True, nullable=False)
    status = Column(String, nullable=False) # "added", "modified", "removed", "renamed"
    additions = Column(Integer, nullable=False, default=0)
    deletions = Column(Integer, nullable=False, default=0)
    previous_filename = Column(String, nullable=True)
    patch_summary = Column(String, nullable=True)
    file_sha = Column(String, nullable=True)
    patch_hash = Column(String, nullable=True)
    patch_size = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    pull_request = relationship("PullRequest", back_populates="changed_files")


class PullRequestSyncJob(Base):
    """Operational status and parameters of PR synchronization runs."""
    __tablename__ = "pull_request_sync_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    github_installation_id = Column(BigInteger, nullable=False)
    status = Column(String, nullable=False) # PENDING, PROCESSING, COMPLETED, FAILED, RETRYING, SUPERSEDED
    sync_reason = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    error_message = Column(String, nullable=True)
    
    commits_fetch_status = Column(String, nullable=False, default="NOT_STARTED") # NOT_STARTED, SUCCESS, PARTIAL_FAILURE, FAILED
    files_fetch_status = Column(String, nullable=False, default="NOT_STARTED") # NOT_STARTED, SUCCESS, PARTIAL_FAILURE, FAILED
    integrity_status = Column(String, nullable=False, default="FAILED") # FULL_SUCCESS, PARTIAL_FAILURE, FAILED
    evidence_health_status = Column(String, nullable=False, default="HEALTHY")
    evidence_consistency_status = Column(String, nullable=False, default="UNKNOWN")
    
    commits_count = Column(Integer, nullable=False, default=0)
    changed_files_count = Column(Integer, nullable=False, default=0)
    pagination_completed = Column(Boolean, nullable=False, default=False)
    pages_received = Column(Integer, nullable=False, default=0)
    snapshot_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id", ondelete="CASCADE"), nullable=True)
    evidence_truncated = Column(Boolean, nullable=False, default=False)
    truncation_reason = Column(String, nullable=True)
    unsafe_for_optimization = Column(Boolean, nullable=False, default=False)

    head_commit_sha = Column(String, nullable=True)
    superseded_by_job_id = Column(UUID(as_uuid=True), ForeignKey("pull_request_sync_jobs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    pull_request = relationship("PullRequest", back_populates="sync_jobs")


class PullRequestSnapshot(Base):
    """Historical immutable state snapshot for PR replayability and forensics."""
    __tablename__ = "pull_request_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    head_commit_sha = Column(String, nullable=False)
    github_pr_updated_at = Column(DateTime, nullable=False)
    snapshot_reason = Column(String, nullable=False) # WEBHOOK_OPENED, WEBHOOK_SYNCHRONIZE, etc.
    
    # Evolution tracking
    snapshot_schema_version = Column(String, nullable=False, default="pr_snapshot.v1")
    normalization_engine_version = Column(String, nullable=False)
    evidence_fingerprint = Column(String, nullable=True) # Deterministic caching hash
    
    # Raw JSON mappings
    snapshot_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id", ondelete="CASCADE"), nullable=False)
    webhook_raw_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id", ondelete="SET NULL"), nullable=True)
    commits_raw_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id", ondelete="SET NULL"), nullable=True)
    files_raw_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id", ondelete="SET NULL"), nullable=True)
    dependency_subset_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id", ondelete="SET NULL"), nullable=True)

    # Health and consistency snapshot states
    evidence_health_status = Column(String, nullable=False)
    sync_integrity_status = Column(String, nullable=False)
    evidence_consistency_status = Column(String, nullable=False, default="UNKNOWN")
    evidence_truncated = Column(Boolean, nullable=False, default=False)
    truncation_reason = Column(String, nullable=True)
    unsafe_for_optimization = Column(Boolean, nullable=False, default=False)

    evidence_generated_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    evidence_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    pull_request = relationship("PullRequest", back_populates="snapshots")


class PullRequestCommentState(Base):
    """Authoritative canonical tracking of the Veriscope comment on a PR."""
    __tablename__ = "pull_request_comment_states"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    github_comment_id = Column(BigInteger, nullable=True)
    latest_recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="SET NULL"), nullable=True)
    latest_comment_hash = Column(String, nullable=True)
    
    latest_comment_version = Column(String, nullable=False, default="template.v1")
    latest_comment_body_hash = Column(String, nullable=True)
    latest_rendering_rules_version = Column(String, nullable=False, default="rules.v1")
    
    comment_status = Column(String, nullable=False, default="PENDING")  # PENDING, DELIVERED, FAILED, STALE
    comment_integrity_status = Column(String, nullable=False, default="VALID")  # VALID, MALFORMED, CORRUPTED, MISSING
    
    comment_last_updated_at = Column(DateTime, nullable=True)
    last_delivery_attempt_at = Column(DateTime, nullable=True)
    delivery_attempt_count = Column(Integer, nullable=False, default=0)
    last_delivery_error = Column(String, nullable=True)
    
    next_allowed_delivery_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("repository_id", "pull_request_id", name="uq_repo_pr_comment_state"),
    )

    repository = relationship("Repository")
    pull_request = relationship("PullRequest")
    latest_recommendation_run = relationship("RecommendationRun")


class PullRequestCommentDeliveryEvent(Base):
    """Audit ledger capturing every single GitHub API delivery attempt."""
    __tablename__ = "pull_request_comment_delivery_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_state_id = Column(UUID(as_uuid=True), ForeignKey("pull_request_comment_states.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    github_comment_id = Column(BigInteger, nullable=True)
    delivery_status = Column(String, nullable=False)  # CREATED, UPDATED, SKIPPED_NO_CHANGE, FAILED, RATE_LIMITED
    
    request_payload = Column(JSONB, nullable=False)
    response_payload = Column(JSONB, nullable=True)
    failure_reason = Column(String, nullable=True)
    delivery_latency_ms = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    comment_state = relationship("PullRequestCommentState")
    recommendation_run = relationship("RecommendationRun")
