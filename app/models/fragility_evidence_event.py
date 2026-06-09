"""
FragilityEvidenceEvent Model

Append-only evidence ledger for fragility memory.
Every fragility signal change must be auditable and replayable.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates
from app.db.base import Base


class FragilityEvidenceEvent(Base):
    """
    Append-only evidence event for fragility memory.
    
    Every fragility pattern change must be explained by evidence events.
    This model provides an immutable audit trail for:
    - Why a fragility pattern was created
    - Why a fragility score changed
    - What historical data supports the fragility assessment
    
    Rules:
    - Append-only (never mutate historical evidence)
    - Evidence event must explain why memory changed
    - Every fragility pattern can be replayed/explained from evidence
    """
    __tablename__ = "fragility_evidence_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fragility_memory_id = Column(UUID(as_uuid=True), ForeignKey("fragility_memory_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Type of evidence
    evidence_type = Column(String, nullable=False, index=True)
    # TEST_FAILURE, REPEATED_FAILURE, MANUAL_OVERRIDE, ESCAPED_DEFECT, ROLLBACK,
    # INCIDENT, CO_FAILURE, MISSING_COVERAGE, OUTCOME_FEEDBACK
    
    # Source entity that generated this evidence
    source_entity_type = Column(String, nullable=False, index=True)
    # TEST_RUN, TEST_RESULT, RECOMMENDATION_RUN, PULL_REQUEST, INCIDENT, ROLLBACK,
    # MANUAL_OVERRIDE, OUTCOME
    
    source_entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Traceability links
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    test_run_id = Column(UUID(as_uuid=True), ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    test_result_id = Column(UUID(as_uuid=True), ForeignKey("test_results.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # External incident tracking
    incident_url = Column(String, nullable=True)
    rollback_url = Column(String, nullable=True)
    
    # Context data
    changed_files = Column(JSONB, nullable=False, default=list)
    affected_behaviors = Column(JSONB, nullable=False, default=list)
    affected_journeys = Column(JSONB, nullable=False, default=list)
    
    # Evidence details
    evidence_summary = Column(Text, nullable=False)
    evidence_weight = Column(Float, nullable=False, default=1.0)
    # Weight of this evidence in fragility calculation (0-1)
    
    # Timing
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    fragility_memory = relationship("FragilityMemoryV2", backref="evidence_events")
    repository = relationship("Repository")
    workspace = relationship("Workspace")
    pull_request = relationship("PullRequest")
    recommendation_run = relationship("RecommendationRun")
    test_run = relationship("TestRun")
    test_result = relationship("TestResult")

    __table_args__ = (
        Index("ix_fragility_evidence_events_repo_type", "repository_id", "evidence_type"),
        Index("ix_fragility_evidence_events_repo_source", "repository_id", "source_entity_type"),
        Index("ix_fragility_evidence_events_memory_occurred", "fragility_memory_id", "occurred_at"),
        Index("ix_fragility_evidence_events_pr_occurred", "pull_request_id", "occurred_at"),
    )

    @validates("evidence_type")
    def validate_evidence_type(self, key, value):
        allowed = {
            "TEST_FAILURE",
            "REPEATED_FAILURE",
            "MANUAL_OVERRIDE",
            "ESCAPED_DEFECT",
            "ROLLBACK",
            "INCIDENT",
            "CO_FAILURE",
            "MISSING_COVERAGE",
            "OUTCOME_FEEDBACK",
        }
        if value not in allowed:
            raise ValueError(f"Invalid evidence_type: '{value}'. Allowed: {allowed}")
        return value

    @validates("source_entity_type")
    def validate_source_entity_type(self, key, value):
        allowed = {
            "TEST_RUN",
            "TEST_RESULT",
            "RECOMMENDATION_RUN",
            "PULL_REQUEST",
            "INCIDENT",
            "ROLLBACK",
            "MANUAL_OVERRIDE",
            "OUTCOME",
        }
        if value not in allowed:
            raise ValueError(f"Invalid source_entity_type: '{value}'. Allowed: {allowed}")
        return value

    @validates("evidence_weight")
    def validate_evidence_weight(self, key, value):
        if value < 0.0 or value > 1.0:
            raise ValueError(f"evidence_weight must be between 0 and 1, got {value}")
        return value

    def __repr__(self) -> str:
        return (
            f"<FragilityEvidenceEvent id={self.id} "
            f"evidence_type={self.evidence_type!r} "
            f"source_entity_type={self.source_entity_type!r} "
            f"evidence_weight={self.evidence_weight:.2f} "
            f"occurred_at={self.occurred_at.isoformat()}>"
        )
