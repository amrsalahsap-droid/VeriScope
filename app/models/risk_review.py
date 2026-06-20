import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer, Index, text
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class RiskReview(Base):
    """Stores QA lead risk review and override decisions for advisory business risks."""
    __tablename__ = "risk_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_requirement_id = Column(String(100), nullable=True, index=True)
    source_ac_number = Column(Integer, nullable=True, index=True)
    readable_id = Column(String(255), nullable=True)
    original_risk_level = Column(String(50), nullable=False)
    original_priority = Column(String(50), nullable=False)
    reviewed_risk_level = Column(String(50), nullable=False)
    reviewed_priority = Column(String(50), nullable=False)
    review_status = Column(String(50), nullable=False, default="UNREVIEWED")
    reviewer_id = Column(String(100), nullable=True)
    reviewer_name = Column(String(255), nullable=True)
    review_note = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    source_snapshot_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index(
            "uq_active_risk_review_req",
            "recommendation_run_id",
            "source_requirement_id",
            unique=True,
            sqlite_where=text("is_active AND source_requirement_id IS NOT NULL"),
            postgresql_where=text("is_active AND source_requirement_id IS NOT NULL"),
        ),
        Index(
            "uq_active_risk_review_ac",
            "recommendation_run_id",
            "source_ac_number",
            unique=True,
            sqlite_where=text("is_active AND source_ac_number IS NOT NULL"),
            postgresql_where=text("is_active AND source_ac_number IS NOT NULL"),
        ),
    )

    def __repr__(self):
        return (
            f"<RiskReview(id={self.id}, recommendation_run_id={self.recommendation_run_id}, "
            f"source_ac_number={self.source_ac_number}, status={self.review_status}, "
            f"reviewed_risk_level={self.reviewed_risk_level})>"
        )

