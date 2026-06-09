import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates
from app.db.base import Base


class ModuleRiskProfile(Base):
    """
    Per-module risk ledger for a repository.

    Tracks historically observed signals (change frequency, failure frequency,
    escaped defects, rollback involvement, recommendation accuracy) and derives
    a deterministic risk_score used exclusively as a ranking input.

    Design rules
    ------------
    - risk_score is a plain weighted integer count: no fake percentages, no ML.
    - risk_score is only meaningful relative to other modules in the same repo.
    - All counters are append-only; the scoring engine reads them without any
      normalisation against a moving baseline — the score can grow unbounded,
      which is intentional: historically fragile modules accumulate signal.
    - recommendation_accuracy is stored as a raw ratio (accepted / presented)
      so the ranking engine can penalise modules where recommendations were
      consistently ignored (low accuracy → higher relative risk weight).
    """
    __tablename__ = "module_risk_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Canonical, normalised path within the repository (e.g. "src/auth/login.py")
    module_path = Column(String, nullable=False, index=True)

    # ------------------------------------------------------------------ #
    # Evidence counters — incremented by service layer on each event      #
    # ------------------------------------------------------------------ #

    # Number of PRs / commits that touched this module
    change_frequency = Column(Integer, nullable=False, default=0)

    # Number of test runs (across any run) where at least one test covering
    # this module failed
    failure_frequency = Column(Integer, nullable=False, default=0)

    # Number of escaped-defect learning events linked to this module
    # (recommendation_outcome.escaped_defect = True and module was in scope)
    escaped_defects = Column(Integer, nullable=False, default=0)

    # Number of rollback outcomes linked to PRs that touched this module
    rollback_count = Column(Integer, nullable=False, default=0)

    # Recommendation accuracy: ratio of accepted recommendations over all
    # recommendations presented for this module.
    # Stored as two raw counters so accuracy can be recomputed without
    # lossy floating-point accumulation.
    recommendations_presented = Column(Integer, nullable=False, default=0)
    recommendations_accepted  = Column(Integer, nullable=False, default=0)

    # ------------------------------------------------------------------ #
    # Derived ranking signal — recomputed by ModuleRiskScoringEngine      #
    # ------------------------------------------------------------------ #

    # Evidence-based risk score (unbounded positive integer).
    # Not a percentage. Meaningful only as a relative ranking key.
    risk_score = Column(Float, nullable=False, default=0.0)

    # Decomposed score components for explainability / audit replay
    score_components = Column(JSONB, nullable=False, default=dict)

    # Formula version so stored scores remain replayable after formula changes
    scoring_formula_version = Column(String, nullable=False, default="module_risk.v1")

    # ------------------------------------------------------------------ #
    # Auditability                                                         #
    # ------------------------------------------------------------------ #
    last_scored_at = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at     = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("repository_id", "module_path", name="uq_repo_module_path"),
    )

    # Relationships
    repository = relationship("Repository")

    @validates("module_path")
    def validate_module_path(self, key: str, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("module_path must be a non-empty string.")
        # Normalise separators so Windows paths don't create duplicate entries
        return value.strip().replace("\\", "/")
