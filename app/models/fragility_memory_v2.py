"""
FragilityMemoryV2 Model

Represents fragility across files, tests, behaviors, journeys, scenarios, and incidents.
This model extends fragility tracking beyond file/test level to include behavior/journey/scenario-level fragility.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from app.db.base import Base


class FragilityMemoryV2(Base):
    """
    Represents fragility memory across multiple subject types.
    
    Stores fragility signals for:
    - Files (FILE_FAILURE_HOTSPOT)
    - Tests (REPEATED_TEST_FAILURE)
    - Behaviors (BEHAVIOR_FRAGILITY)
    - Journeys (JOURNEY_FRAGILITY)
    - Scenarios (ESCAPED_DEFECT_PATTERN, ROLLBACK_PATTERN)
    - Modules (CO_FAILURE_PATTERN, RISKY_CHANGE_COMBINATION)
    - PR patterns (MISSING_COVERAGE_PATTERN)
    
    Rules:
    - Repository scoped
    - Deterministic memory_key
    - No duplicate active memory for same subject/type
    - Every memory must have evidence
    - No fake fragility without historical data
    """
    __tablename__ = "fragility_memory_v2"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Deterministic key for upsert and deduplication
    memory_key = Column(String, nullable=False, index=True)
    
    # Type of fragility memory
    memory_type = Column(String, nullable=False, index=True)
    # REPEATED_TEST_FAILURE, FILE_FAILURE_HOTSPOT, BEHAVIOR_FRAGILITY, JOURNEY_FRAGILITY,
    # ESCAPED_DEFECT_PATTERN, ROLLBACK_PATTERN, CO_FAILURE_PATTERN, RISKY_CHANGE_COMBINATION,
    # MISSING_COVERAGE_PATTERN
    
    # Subject of the fragility
    subject_type = Column(String, nullable=False, index=True)
    # FILE, TEST, BEHAVIOR, JOURNEY, SCENARIO, MODULE, PR_PATTERN
    
    subject_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    subject_name = Column(String, nullable=False, index=True)
    
    # Risk scoring
    risk_level = Column(String, nullable=False, default="LOW", index=True)
    # LOW, MODERATE, HIGH, CRITICAL
    
    fragility_score = Column(Float, nullable=False, default=0.0)
    # Normalized 0-100 score
    
    confidence = Column(Float, nullable=False, default=0.0)
    # Normalized 0-1 confidence based on evidence count
    
    status = Column(String, nullable=False, default="ACTIVE", index=True)
    # ACTIVE, STALE, INVALIDATED
    
    # Tracking
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    repository = relationship("Repository")
    workspace = relationship("Workspace")

    __table_args__ = (
        # Ensure no duplicate active memory for same repository, memory_key, subject_type, subject_id
        UniqueConstraint(
            "repository_id",
            "memory_key",
            "subject_type",
            "subject_id",
            name="uq_fragility_memory_v2_repo_key_subject",
        ),
        Index("ix_fragility_memory_v2_repo_memory_type", "repository_id", "memory_type"),
        Index("ix_fragility_memory_v2_repo_subject_type", "repository_id", "subject_type"),
        Index("ix_fragility_memory_v2_repo_status", "repository_id", "status"),
    )

    @validates("memory_type")
    def validate_memory_type(self, key, value):
        allowed = {
            "REPEATED_TEST_FAILURE",
            "FILE_FAILURE_HOTSPOT",
            "BEHAVIOR_FRAGILITY",
            "JOURNEY_FRAGILITY",
            "ESCAPED_DEFECT_PATTERN",
            "ROLLBACK_PATTERN",
            "CO_FAILURE_PATTERN",
            "RISKY_CHANGE_COMBINATION",
            "MISSING_COVERAGE_PATTERN",
        }
        if value not in allowed:
            raise ValueError(f"Invalid memory_type: '{value}'. Allowed: {allowed}")
        return value

    @validates("subject_type")
    def validate_subject_type(self, key, value):
        allowed = {
            "FILE",
            "TEST",
            "BEHAVIOR",
            "JOURNEY",
            "SCENARIO",
            "MODULE",
            "PR_PATTERN",
        }
        if value not in allowed:
            raise ValueError(f"Invalid subject_type: '{value}'. Allowed: {allowed}")
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

    @validates("fragility_score")
    def validate_fragility_score(self, key, value):
        if value < 0.0 or value > 100.0:
            raise ValueError(f"fragility_score must be between 0 and 100, got {value}")
        return value

    @validates("confidence")
    def validate_confidence(self, key, value):
        if value < 0.0 or value > 1.0:
            raise ValueError(f"confidence must be between 0 and 1, got {value}")
        return value

    def __repr__(self) -> str:
        return (
            f"<FragilityMemoryV2 id={self.id} "
            f"memory_type={self.memory_type!r} "
            f"subject_type={self.subject_type!r} "
            f"subject_name={self.subject_name!r} "
            f"risk_level={self.risk_level!r} "
            f"fragility_score={self.fragility_score:.2f} "
            f"confidence={self.confidence:.2f} "
            f"status={self.status!r}>"
        )
