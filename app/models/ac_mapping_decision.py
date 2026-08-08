"""Lightweight AC-level mapping decision records for no-candidate gaps."""
from datetime import datetime
import uuid

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class ACMappingDecision(Base):
    """Stores explicit reviewer decisions on ACs with no test candidate."""

    __tablename__ = "ac_mapping_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    pull_request_id = Column(
        UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    acceptance_criterion_id = Column(
        UUID(as_uuid=True), ForeignKey("acceptance_criteria.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    decision_type = Column(
        String(50), nullable=False, default="ACCEPTED_GAP"
    )  # ACCEPTED_GAP | ACCEPTED_RISK | OUT_OF_SCOPE
    reason = Column(Text, nullable=False)
    risk_category = Column(String(100), nullable=True)
    out_of_scope = Column(Boolean, nullable=False, default=False)

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    audit_metadata = Column(JSON, nullable=True, default=dict)
