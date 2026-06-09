import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, backref
from app.db.base import Base


class BehaviorScenarioCoverage(Base):
    """Tracks coverage status, execution trace and test mappings for business behavior scenarios."""
    __tablename__ = "behavior_scenario_coverages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    behavior_id = Column(UUID(as_uuid=True), ForeignKey("behaviors.id", ondelete="CASCADE"), nullable=False, index=True)
    behavior_scenario_id = Column(UUID(as_uuid=True), ForeignKey("behavior_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="SET NULL"), nullable=True, index=True)

    # Coverage Status
    # Expected: COVERED_BY_EXISTING_TEST, PARTIALLY_COVERED, MISSING_AUTOMATED_COVERAGE,
    #           VERIFIED_ON_CURRENT_PR, MANUAL_VALIDATION_RECOMMENDED, UNKNOWN
    coverage_status = Column(String, nullable=False, index=True)
    current_pr_execution_status = Column(String, nullable=True)  # passed, failed, skipped, None
    confidence = Column(String, nullable=False)                  # HIGH, MODERATE, LOW
    reason = Column(Text, nullable=True)

    # Metadata & Lineage traces
    existing_tests = Column(JSONB, nullable=False, default=list)       # Mapped existing test suites/names
    suggested_scenarios = Column(JSONB, nullable=False, default=list)  # Suggested replacement validation scenarios
    coverage_files = Column(JSONB, nullable=False, default=list)       # Files associated with coverage trace

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository")
    behavior = relationship("Behavior")
    scenario = relationship("BehaviorScenario", backref=backref("coverages", cascade="all, delete-orphan"))
    recommendation_run = relationship("RecommendationRun", back_populates="behavior_scenario_coverages")
