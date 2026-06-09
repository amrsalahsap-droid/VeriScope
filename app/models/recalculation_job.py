import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base

class FlakyRecalculationJob(Base):
    """Tracks active and historic flakiness recalculation jobs to protect against recalculation storms."""
    __tablename__ = "flaky_recalculation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, default="RUNNING") # RUNNING, COMPLETED, FAILED
    recalculation_scope = Column(String, nullable=False, default="FULL_REPOSITORY") # FULL_REPOSITORY, RECENT_TESTS, UNSTABLE_ONLY
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)

    # Relationships
    repository = relationship("Repository")
