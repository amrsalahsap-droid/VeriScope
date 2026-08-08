"""
Outcome Label Model

Stores human or system-applied labels indicating correctness, quality gate, or scope accuracy decisions.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class OutcomeLabel(Base):
    """Stores human or system-applied evaluation labels."""
    
    __tablename__ = "outcome_labels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outcome_event_id = Column(UUID(as_uuid=True), ForeignKey("outcome_events.id", ondelete="SET NULL"), nullable=True, index=True)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    label_type = Column(String, nullable=False, index=True)  # recommendation_correct, regression_scope_too_large, etc.
    label_value = Column(String, nullable=False)
    confidence = Column(Float, nullable=True)
    source = Column(String, nullable=False)  # human, system
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    metadata_json = Column(JSON, nullable=True)
