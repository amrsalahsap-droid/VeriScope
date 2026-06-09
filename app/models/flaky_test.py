import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base

class FlakyTestProfile(Base):
    """Represents a flaky, unstable, or quarantined test case within a repository."""
    __tablename__ = "flaky_test_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    test_case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Environment-Dependent Fields (Future-Proof)
    execution_environment = Column(String, nullable=True) # e.g. browser, OS
    runner_type = Column(String, nullable=True) # e.g. github-hosted, self-hosted
    ci_provider = Column(String, nullable=True) # e.g. github_actions, gitlab_ci
    test_framework = Column(String, nullable=True) # e.g. jest, pytest

    # Flakiness Metric Fields
    failure_rate = Column(Float, nullable=False, default=0.0)
    recent_failure_rate = Column(Float, nullable=False, default=0.0)
    instability_score = Column(Float, nullable=False, default=0.0)
    sample_size = Column(Integer, nullable=False, default=0)
    confidence_level = Column(String, nullable=False, default="LOW") # "LOW", "MODERATE", "HIGH"

    # Classification & Status Fields
    status = Column(String, nullable=False, default="stable") # stable, unstable, quarantined
    last_failure_at = Column(DateTime, nullable=True)
    stability_recovered_at = Column(DateTime, nullable=True)
    last_recalculated_at = Column(DateTime, nullable=True)
    stale_profile = Column(Boolean, nullable=False, default=False)
    failure_mode_distribution = Column(JSONB, nullable=True) # {"assertion_failure": X, "timeout": Y, "infra_error": Z, "unknown": W}

    # Quarantine Lifecycle Fields
    quarantined_at = Column(DateTime, nullable=True)
    quarantine_reason = Column(String, nullable=True)
    quarantine_review_due_at = Column(DateTime, nullable=True)
    quarantined_by = Column(String, nullable=True)

    # Auditability & Explainability Fields
    flakiness_calculation_version = Column(String, nullable=False, default="flaky_calc.v1")
    rationale = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    repository = relationship("Repository")
    test_case = relationship("TestCase")
