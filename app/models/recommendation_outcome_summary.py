"""
Recommendation Outcome Summary Model

Derived view summarizing outcomes linked to each recommendation run.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class RecommendationOutcomeSummary(Base):
    """Derived summary representing outcomes linked to a RecommendationRun."""
    
    __tablename__ = "recommendation_outcome_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    pipeline_run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    github_pr_number = Column(Integer, nullable=True)
    commit_sha = Column(String, nullable=True)
    merged = Column(Boolean, nullable=False, default=False)
    reverted = Column(Boolean, nullable=False, default=False)
    deployment_failed = Column(Boolean, nullable=False, default=False)
    incident_found = Column(Boolean, nullable=False, default=False)
    bug_found = Column(Boolean, nullable=False, default=False)
    regression_found = Column(Boolean, nullable=False, default=False)
    missed_critical_test = Column(Boolean, nullable=False, default=False)
    missed_high_test = Column(Boolean, nullable=False, default=False)
    scope_accuracy = Column(String, nullable=True)  # too_large, too_small, accurate
    quality_gate_accuracy = Column(String, nullable=True)  # correct, incorrect
    learning_status = Column(String, nullable=False, default="PENDING")  # PENDING, PROCESSED, SKIPPED
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
