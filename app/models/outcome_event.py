"""
Outcome Event Model

Stores events representing post-decision outcomes such as PR merges, deployments, CI failures, incidents, etc.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class OutcomeEvent(Base):
    """Immutable record of post-decision outcome events."""
    
    __tablename__ = "outcome_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    pipeline_run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    github_pr_number = Column(Integer, nullable=True)
    commit_sha = Column(String, nullable=True)
    event_type = Column(String, nullable=False, index=True)  # PR_MERGED, PR_REVERTED, CI_FAILED_AFTER_RECOMMENDATION, etc.
    event_source = Column(String, nullable=False)  # github, ci, manual
    event_status = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    external_event_id = Column(String, nullable=True, index=True)  # stable webhook delivery / event GUID
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
