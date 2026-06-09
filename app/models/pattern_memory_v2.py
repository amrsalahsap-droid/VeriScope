"""
PatternMemoryV2 Model

Durable memory for outcome learning signals.

This model stores learned associations from recommendation outcomes,
providing a unified memory for all signal types (manual additions,
scenario decisions, defects, rollbacks, execution results).
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Float,
    String,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class PatternMemoryV2(Base):
    """
    Durable memory for outcome learning signals.
    
    Stores learned associations from recommendation outcomes, providing
    a unified memory for all signal types including manual additions,
    scenario decisions, defects, rollbacks, and execution results.
    
    Attributes
    ----------
    id:
        UUID primary key.
    workspace_id:
        Workspace this pattern memory belongs to. Enforces tenant isolation.
    repository_id:
        Repository this pattern memory belongs to.
    pattern_key:
        Normalised signal pattern key for lookup.
    behavior_id:
        Optional behavior identifier for behavior-specific learning.
    journey_id:
        Optional journey identifier for journey-specific learning.
    scenario_intent_key:
        Optional scenario intent key for scenario-specific learning.
    test_identifier:
        Optional test identifier for test-specific learning.
    signal_type:
        Type of learning signal (MANUAL_ADDITION, MANUAL_REMOVAL, ACCEPTED_SCENARIO,
        DISMISSED_SCENARIO, ESCAPED_DEFECT, ROLLBACK, EXECUTION_RESULT).
    strength:
        Numerical strength of the signal in range [0, 1].
    confidence:
        Confidence in the signal in range [0, 1].
    usage_count:
        Number of times this pattern was observed.
    success_count:
        Number of successful outcomes.
    failure_count:
        Number of failed outcomes.
    dismissed_count:
        Number of times dismissed.
    defect_count:
        Number of associated defect occurrences.
    rollback_count:
        Number of associated rollback occurrences.
    last_seen_at:
        Last timestamp this pattern was observed.
    created_at:
        Row-creation timestamp (UTC).
    updated_at:
        Last-modification timestamp (UTC).
    """

    __tablename__ = "pattern_memories_v2"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    pattern_key = Column(String, nullable=False, index=True)
    
    # Optional target identifiers for different signal types
    behavior_id = Column(String, nullable=True, index=True)
    journey_id = Column(String, nullable=True, index=True)
    scenario_intent_key = Column(String, nullable=True, index=True)
    test_identifier = Column(String, nullable=True, index=True)

    # Signal type enum
    signal_type = Column(String, nullable=False, index=True)

    # Signal quality
    strength = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.0)

    # Counters for different outcome types
    usage_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    dismissed_count = Column(Integer, nullable=False, default=0)
    defect_count = Column(Integer, nullable=False, default=0)
    rollback_count = Column(Integer, nullable=False, default=0)

    # Temporal tracking
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    repository = relationship("Repository")
    workspace = relationship("Workspace")

    # Constraints
    __table_args__ = (
        # Upsert key: repository + pattern_key + signal target
        # At least one of behavior_id, journey_id, scenario_intent_key, or test_identifier must be set
        UniqueConstraint(
            "repository_id",
            "pattern_key",
            "behavior_id",
            "journey_id",
            "scenario_intent_key",
            "test_identifier",
            name="uq_pattern_memory_v2_repo_pattern_target",
        ),
        # Composite lookup by pattern key within a repo
        Index("ix_pattern_memory_v2_repo_key", "repository_id", "pattern_key"),
        # Composite lookup by signal type within a repo
        Index("ix_pattern_memory_v2_repo_signal", "repository_id", "signal_type"),
        # Composite lookup by test identifier within a repo
        Index("ix_pattern_memory_v2_repo_test", "repository_id", "test_identifier"),
        # Composite lookup by scenario intent key within a repo
        Index("ix_pattern_memory_v2_repo_scenario", "repository_id", "scenario_intent_key"),
        # Range checks for strength and confidence
        CheckConstraint("strength >= 0.0 AND strength <= 1.0", name="chk_pattern_memory_v2_strength"),
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="chk_pattern_memory_v2_confidence"),
        # Counters must be non-negative
        CheckConstraint("usage_count >= 0", name="chk_pattern_memory_v2_usage_count"),
        CheckConstraint("success_count >= 0", name="chk_pattern_memory_v2_success_count"),
        CheckConstraint("failure_count >= 0", name="chk_pattern_memory_v2_failure_count"),
        CheckConstraint("dismissed_count >= 0", name="chk_pattern_memory_v2_dismissed_count"),
        CheckConstraint("defect_count >= 0", name="chk_pattern_memory_v2_defect_count"),
        CheckConstraint("rollback_count >= 0", name="chk_pattern_memory_v2_rollback_count"),
    )

    def __repr__(self) -> str:
        return (
            f"<PatternMemoryV2 id={self.id} "
            f"pattern_key={self.pattern_key!r} "
            f"signal_type={self.signal_type!r} "
            f"strength={self.strength:.3f} "
            f"confidence={self.confidence:.3f} "
            f"usage={self.usage_count}>"
        )


# Signal type constants
SIGNAL_TYPE_MANUAL_ADDITION = "MANUAL_ADDITION"
SIGNAL_TYPE_MANUAL_REMOVAL = "MANUAL_REMOVAL"
SIGNAL_TYPE_ACCEPTED_SCENARIO = "ACCEPTED_SCENARIO"
SIGNAL_TYPE_DISMISSED_SCENARIO = "DISMISSED_SCENARIO"
SIGNAL_TYPE_ESCAPED_DEFECT = "ESCAPED_DEFECT"
SIGNAL_TYPE_ROLLBACK = "ROLLBACK"
SIGNAL_TYPE_EXECUTION_RESULT = "EXECUTION_RESULT"

SIGNAL_TYPES = [
    SIGNAL_TYPE_MANUAL_ADDITION,
    SIGNAL_TYPE_MANUAL_REMOVAL,
    SIGNAL_TYPE_ACCEPTED_SCENARIO,
    SIGNAL_TYPE_DISMISSED_SCENARIO,
    SIGNAL_TYPE_ESCAPED_DEFECT,
    SIGNAL_TYPE_ROLLBACK,
    SIGNAL_TYPE_EXECUTION_RESULT,
]
