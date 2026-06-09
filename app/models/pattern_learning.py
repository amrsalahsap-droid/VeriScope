"""
app/models/pattern_learning.py
================================

PatternLearning — incremental learning record linking a PR change pattern
to the tests that proved useful for it.

Design principles
-----------------
* One row per (repository_id, pattern_key, test_identifier).
* Rows are never deleted — only updated incrementally.
* ``strength`` and ``confidence`` grow monotonically toward 1.0 as more
  evidence accumulates; they never decrease automatically.
* ``usage_count`` counts how many times this (pattern, test) pair has been
  observed as useful across distinct PR outcomes.
* Engineer behavior (manual additions, defect escapes) outweighs heuristics:
  - MANUAL_OVERRIDE source starts at strength 0.60
  - ESCAPED_DEFECT source starts at strength 0.80
  - FOLLOWED (recommendation accepted) starts at strength 0.40
  - HEURISTIC starts at strength 0.20
* ``last_seen_at`` is updated on every increment so stale patterns can be
  identified without destroying history.

Immutability note
-----------------
Unlike the forensic audit models (RecommendationReasoningEntry, etc.),
PatternLearning rows ARE mutable — they accumulate evidence over time.
The append-only audit trail is provided by the source learner services
(DefectLearningEvent, ManualOverrideLearner logs, etc.).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class PatternLearning(Base):
    """Incremental learning record: PR change pattern → useful test.

    Attributes
    ----------
    id:
        Surrogate UUID primary key.
    repository_id:
        Repository this learning belongs to.
    pattern_key:
        Normalised string key identifying the PR change pattern.
        Format: ``"<signal_type>:<normalised_path>"``, e.g.
        ``"file_change:app/services/auth.py"`` or
        ``"domain:authentication"``.
    test_identifier:
        Stable test identity (matches ``TestCase.stable_identity``).
    source:
        What signal produced this learning entry.
        One of: ``MANUAL_OVERRIDE | ESCAPED_DEFECT | FOLLOWED | HEURISTIC``.
    strength:
        Accumulated evidence weight in [0, 1].  Starts at a source-dependent
        base and grows by ``strength_step`` per additional observation.
    confidence:
        Confidence in the strength value, in [0, 1].  Grows with usage_count.
    usage_count:
        Number of distinct PR outcomes where this (pattern, test) pair was
        observed as useful.
    last_outcome_id:
        UUID of the most recent ``RecommendationOutcome`` that contributed to
        this record (for traceability).
    context:
        Optional JSONB bag for supplementary metadata (e.g. changed file list,
        PR number, domain label).  Never used for scoring — informational only.
    first_seen_at:
        Timestamp of the first observation.
    last_seen_at:
        Timestamp of the most recent observation.
    created_at:
        Row-creation timestamp (UTC).
    updated_at:
        Last-modification timestamp (UTC).
    """

    __tablename__ = "pattern_learnings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Normalised pattern key — identifies the PR change signal
    pattern_key = Column(String, nullable=False, index=True)

    # Stable test identity
    test_identifier = Column(String, nullable=False, index=True)

    # Signal source — determines base strength
    # MANUAL_OVERRIDE | ESCAPED_DEFECT | FOLLOWED | HEURISTIC
    source = Column(
        SAEnum(
            "ESCAPED_DEFECT", "MANUAL_OVERRIDE", "FOLLOWED", "HEURISTIC",
            name="pattern_learning_source",
        ),
        nullable=False,
    )

    # Accumulated evidence weight [0, 1]
    strength = Column(Numeric(precision=6, scale=5), nullable=False, default=0.0)

    # Confidence in the strength value [0, 1]
    confidence = Column(Numeric(precision=6, scale=5), nullable=False, default=0.0)

    # Number of distinct outcomes where this pair was useful
    usage_count = Column(Integer, nullable=False, default=0)

    # Most recent contributing outcome (for traceability)
    last_outcome_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recommendation_outcomes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Supplementary metadata — informational only, not used for scoring
    context = Column(JSONB, nullable=True, default=dict)

    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at  = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at    = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at    = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    repository    = relationship("Repository")
    last_outcome  = relationship("RecommendationOutcome", foreign_keys=[last_outcome_id])

    # Constraints
    __table_args__ = (
        # One row per (repository, pattern, test, source)
        UniqueConstraint(
            "repository_id",
            "pattern_key",
            "test_identifier",
            "source",
            name="uq_pattern_learning_repo_pattern_test_source",
        ),
        Index("ix_pattern_learning_repo_pattern", "repository_id", "pattern_key"),
        Index("ix_pattern_learning_repo_test",    "repository_id", "test_identifier"),
        CheckConstraint("strength >= 0.0 AND strength <= 1.0",   name="chk_pattern_learning_strength"),
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="chk_pattern_learning_confidence"),
    )

    def __repr__(self) -> str:
        return (
            f"<PatternLearning id={self.id} "
            f"pattern={self.pattern_key!r} "
            f"test={self.test_identifier!r} "
            f"source={self.source!r} "
            f"strength={self.strength:.3f} "
            f"usage={self.usage_count}>"
        )
