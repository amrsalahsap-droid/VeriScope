import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates
from app.db.base import Base

class FragilityPattern(Base):
    """Represents a historically validated organizational fragility pattern."""
    __tablename__ = "fragility_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)

    pattern_type = Column(String, nullable=False, index=True)
    # FILE_FAILURE_FREQUENCY, CO_FAILURE_PATTERN, DEPENDENCY_PROXIMITY, ESCAPED_DEFECT_PATTERN,
    # TEST_CLUSTER_FAILURE, RISKY_COMBINATION, UNSTABLE_MODULE, ROLLBACK_INVOLVEMENT

    normalized_pattern_key = Column(String, nullable=False, index=True)
    
    title = Column(String, nullable=False, default="")
    explanation = Column(String, nullable=False)
    
    # Deterministic Scoring & Risk Classification
    fragility_score = Column(Float, nullable=False, default=0.0) # Normalized 0-100
    risk_level = Column(String, nullable=False, default="LOW") # LOW, MODERATE, HIGH, CRITICAL
    status = Column(String, nullable=False, default="ACTIVE") # ACTIVE, STALE, INVALIDATED
    confidence_level = Column(String, nullable=False, default="LOW") # LOW, MODERATE, HIGH
    pattern_hash = Column(String, nullable=False, index=True, default="")
    
    score_components = Column(JSONB, nullable=False, default=dict) 
    replayable_evidence_snapshot = Column(JSONB, nullable=False, default=dict)

    # Invalidation Auditability
    invalidated_reason = Column(String, nullable=True)
    invalidated_at = Column(DateTime, nullable=True)
    invalidated_by = Column(String, nullable=True)

    # Recalculation Determinism Versioning
    fragility_generation_version = Column(String, nullable=False, default="v1.2.0")
    scoring_formula_version = Column(String, nullable=False, default="weighted.v2")

    # Tracking & Metrics
    evidence_count = Column(Integer, nullable=False, default=0)
    incident_count = Column(Integer, nullable=False, default=0)
    related_failure_count = Column(Integer, nullable=False, default=0)
    
    context = Column(JSONB, nullable=True, default=dict) # Supplementary metadata only
    
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("repository_id", "normalized_pattern_key", name="uq_repo_pattern_key"),
    )

    # Relationships
    repository = relationship("Repository")
    evidence_links = relationship("FragilityEvidenceLink", back_populates="fragility_pattern", cascade="all, delete-orphan")

    @validates("pattern_type")
    def validate_pattern_type(self, key, value):
        allowed = {
            "FILE_FAILURE_FREQUENCY",
            "CO_FAILURE_PATTERN",
            "DEPENDENCY_PROXIMITY",
            "ESCAPED_DEFECT_PATTERN",
            "TEST_CLUSTER_FAILURE",
            "RISKY_COMBINATION",
            "UNSTABLE_MODULE",
            "ROLLBACK_INVOLVEMENT"
        }
        if value not in allowed:
            raise ValueError(f"Invalid pattern_type: '{value}'. Allowed: {allowed}")
        return value

    @validates("risk_level")
    def validate_risk_level(self, key, value):
        allowed = {"LOW", "MODERATE", "HIGH", "CRITICAL"}
        if value not in allowed:
            raise ValueError(f"Invalid risk_level: '{value}'. Allowed: {allowed}")
        return value

    @validates("status")
    def validate_status(self, key, value):
        allowed = {"ACTIVE", "STALE", "INVALIDATED"}
        if value not in allowed:
            raise ValueError(f"Invalid status: '{value}'. Allowed: {allowed}")
        return value

    @validates("confidence_level")
    def validate_confidence_level(self, key, value):
        allowed = {"LOW", "MODERATE", "HIGH"}
        if value not in allowed:
            raise ValueError(f"Invalid confidence_level: '{value}'. Allowed: {allowed}")
        return value


class FragilityEvidenceLink(Base):
    """Forensic evidence ledger trace linking a fragility pattern to its historical origins."""
    __tablename__ = "fragility_evidence_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fragility_pattern_id = Column(UUID(as_uuid=True), ForeignKey("fragility_patterns.id", ondelete="CASCADE"), nullable=False, index=True)
    
    evidence_type = Column(String, nullable=False) # e.g. TEST_FAILURE, INCIDENT, ROLLBACK...
    
    # Explicit Forensic Traces
    source_test_run_id = Column(UUID(as_uuid=True), ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True)
    source_test_result_id = Column(UUID(as_uuid=True), ForeignKey("test_results.id", ondelete="SET NULL"), nullable=True)
    source_incident_id = Column(String, nullable=True)
    source_recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="SET NULL"), nullable=True)
    source_pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True)
    
    evidence_summary = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    fragility_pattern = relationship("FragilityPattern", back_populates="evidence_links")

    @validates("evidence_type")
    def validate_evidence_type(self, key, value):
        allowed = {
            "TEST_FAILURE",
            "INCIDENT",
            "ROLLBACK",
            "RECOMMENDATION_DEGRADATION",
            "DEPENDENCY_EXPANSION",
            "QUARANTINED_TEST"
        }
        if value not in allowed:
            raise ValueError(f"Invalid evidence_type: '{value}'. Allowed: {allowed}")
        return value


class FragilitySnapshot(Base):
    """Immutable generalized ledger of active fragility patterns for standalone generation and replay audits."""
    __tablename__ = "fragility_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    
    snapshot_hash = Column(String, nullable=False, index=True, default="")
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    total_patterns = Column(Integer, nullable=False, default=0)
    active_patterns = Column(Integer, nullable=False, default=0)
    stale_patterns = Column(Integer, nullable=False, default=0)
    
    generation_version = Column(String, nullable=False, default="v1.2.0")
    scoring_version = Column(String, nullable=False, default="weighted.v2")
    evidence_window = Column(JSONB, nullable=False, default=dict)
    
    generation_trigger = Column(String, nullable=False, default="MANUAL_RECALCULATION")
    # MANUAL_RECALCULATION, SCHEDULED_RECALCULATION, RECOMMENDATION_RUN, DEBUG_REPLAY

    snapshot_metadata = Column(JSONB, nullable=False, default=dict)
    
    active_pattern_ids = Column(JSONB, nullable=False, default=list) # List of UUID strings (for backwards compatibility)
    pattern_hashes = Column(JSONB, nullable=False, default=list) # List of SHA256 hashes of patterns (for backwards compatibility)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository")
    recommendation_run = relationship("RecommendationRun")

    @validates("generation_trigger")
    def validate_generation_trigger(self, key, value):
        allowed = {
            "MANUAL_RECALCULATION",
            "SCHEDULED_RECALCULATION",
            "RECOMMENDATION_RUN",
            "DEBUG_REPLAY"
        }
        if value not in allowed:
            raise ValueError(f"Invalid generation_trigger: '{value}'. Allowed: {allowed}")
        return value
