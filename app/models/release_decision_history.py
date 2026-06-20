"""Release Decision History Domain Models."""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
from app.db.base import Base

# Enums
HistoryEventType = ENUM(
    'REQUESTED',
    'APPROVED',
    'REJECTED',
    'CONDITIONALLY_APPROVED',
    'RESET',
    'CANCELLED',
    name='history_event_type'
)


class ReleaseDecisionHistory(Base):
    """Immutable audit trail for release decision transitions."""
    __tablename__ = "release_decision_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    release_decision_id = Column(
        UUID(as_uuid=True),
        ForeignKey("release_decisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Event type
    event_type = Column(HistoryEventType, nullable=False)
    
    # Actor information
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    actor_name = Column(String, nullable=True)
    
    # State transition
    previous_status = Column(String, nullable=True)
    new_status = Column(String, nullable=True)
    
    # Event context
    note = Column(Text, nullable=True)
    snapshot_hash = Column(String, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    release_decision = relationship("ReleaseDecision", back_populates="history")

    def __repr__(self):
        return f"<ReleaseDecisionHistory(decision_id={self.release_decision_id}, event={self.event_type}, actor={self.actor_name})>"
