import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class RiskAssessment(Base):
    """
    Persisted risk assessment derived deterministically from an ImpactProfile.

    One assessment per pull request per recommendation run context.
    Risk level, areas, and reasons are all evidence-backed — no speculative
    scoring, no fake percentages, no alarmist language.

    risk_level values: LOW | MODERATE | HIGH | CRITICAL
    """
    __tablename__ = "risk_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pull_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Denormalised reference to the ImpactProfile input that produced this assessment
    impact_profile = Column(JSONB, nullable=False)

    # Core outputs
    risk_level = Column(String, nullable=False)          # LOW | MODERATE | HIGH | CRITICAL
    risk_areas = Column(JSONB, nullable=False)            # List[str]
    risk_reasons = Column(JSONB, nullable=False)          # List[str]

    # Audit
    engine_version = Column(String, nullable=False, default="v1")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository")
    pull_request = relationship("PullRequest")
