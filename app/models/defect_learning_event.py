"""
app/models/defect_learning_event.py
=====================================

Append-only audit ledger for every escaped-defect learning pass.

Each time ``EscapedDefectLearner.learn_from_outcome()`` processes a
``RecommendationOutcome`` that carries ``escaped_defect_detected=True`` or
``rollback_occurred=True`` (or both), one ``DefectLearningEvent`` row is
created to record exactly what was learned and why.

Immutability
------------
SQLAlchemy ORM event listeners prevent mutation or deletion of existing rows,
matching the convention established by ``RecommendationOutcomeEvidence`` and
``RecommendationOutcomeSnapshot``.

Schema notes
------------
* ``missed_tests``   — ``recommended_tests − executed_tests`` at the time of
  the escape.  These are the tests that Veriscope suggested but were NOT run,
  and a defect still reached production.
* ``trigger_type``   — ``ESCAPED_DEFECT``, ``ROLLBACK``, or ``BOTH``.
* ``defect_count_at_time`` — cumulative value of ``TestCoverageLink.defect_count``
  on the most-impacted link at the time of the learning pass (snapshot for
  auditability).
* ``errors``         — non-fatal errors encountered during the pass (JSONB list
  of strings).  A non-empty list does NOT mean the row failed; it means the
  pass completed but with partial failures.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class DefectLearningEvent(Base):
    """Append-only record of a single defect-learning pass.

    Attributes
    ----------
    id:
        Surrogate UUID primary key.
    repository_id:
        Repository that owns the outcome (CASCADE-deleted with repository).
    recommendation_outcome_id:
        The ``RecommendationOutcome`` that triggered learning.
    pull_request_id:
        Pull request associated with the outcome (nullable — may be absent on
        legacy or synthetic outcomes).
    trigger_type:
        What triggered this learning pass.  One of:

        * ``ESCAPED_DEFECT`` — ``outcome.escaped_defect_detected`` is True.
        * ``ROLLBACK``       — ``outcome.rollback_occurred`` is True.
        * ``BOTH``           — both flags are True simultaneously.

    changed_files:
        JSON list of file paths that were changed in the PR.  These are the
        files for which new ``TestCoverageLink`` edges may be created.
    recommended_tests:
        JSON list of test identifiers that Veriscope recommended for this PR.
    executed_tests:
        JSON list of test identifiers that CI actually ran.
    missed_tests:
        JSON list of ``recommended_tests − executed_tests``.  These are the
        tests that were suggested but skipped — the knowledge-graph gap that
        allowed the defect to escape.
    links_created:
        Number of new ``TestCoverageLink`` rows inserted during this pass.
    links_strengthened:
        Number of existing ``TestCoverageLink`` rows updated (strength raised).
    defect_count_at_time:
        Snapshot of the maximum ``TestCoverageLink.defect_count`` observed
        across all (missed_test, changed_file) pairs at the time of this pass.
        Useful for trend analysis without re-joining to the live link table.
    errors:
        JSON list of non-fatal error messages.  Empty list on a clean pass.
    created_at:
        UTC timestamp when this event was written.  Immutable.
    """

    __tablename__ = "defect_learning_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ------------------------------------------------------------------ #
    #  Scoping                                                             #
    # ------------------------------------------------------------------ #
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recommendation_outcome_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recommendation_outcomes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pull_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pull_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ------------------------------------------------------------------ #
    #  Trigger classification                                              #
    # ------------------------------------------------------------------ #
    # ESCAPED_DEFECT | ROLLBACK | BOTH
    trigger_type = Column(String, nullable=False)

    # ------------------------------------------------------------------ #
    #  Evidence snapshot (frozen at event creation time)                  #
    # ------------------------------------------------------------------ #
    changed_files     = Column(JSONB, nullable=False, default=list)
    recommended_tests = Column(JSONB, nullable=False, default=list)
    executed_tests    = Column(JSONB, nullable=False, default=list)
    # recommended_tests − executed_tests: the gap that let the defect through
    missed_tests      = Column(JSONB, nullable=False, default=list)

    # ------------------------------------------------------------------ #
    #  Learning outcome counters                                           #
    # ------------------------------------------------------------------ #
    links_created     = Column(Integer, nullable=False, default=0)
    links_strengthened = Column(Integer, nullable=False, default=0)

    # Snapshot of the maximum defect_count on any affected link at the time
    # of this pass.  Enables trend queries without live joins.
    defect_count_at_time = Column(Integer, nullable=False, default=0)

    # ------------------------------------------------------------------ #
    #  Error ledger                                                        #
    # ------------------------------------------------------------------ #
    errors = Column(JSONB, nullable=False, default=list)

    # ------------------------------------------------------------------ #
    #  Temporal                                                            #
    # ------------------------------------------------------------------ #
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # ------------------------------------------------------------------ #
    #  Relationships                                                       #
    # ------------------------------------------------------------------ #
    repository           = relationship("Repository")
    recommendation_outcome = relationship("RecommendationOutcome")
    pull_request         = relationship("PullRequest")

    def __repr__(self) -> str:
        return (
            f"<DefectLearningEvent id={self.id} "
            f"trigger={self.trigger_type} "
            f"missed={len(self.missed_tests or [])} "
            f"links_created={self.links_created} "
            f"links_strengthened={self.links_strengthened}>"
        )


# --------------------------------------------------------------------------- #
#  Immutability guards (same pattern as RecommendationOutcomeEvidence)        #
# --------------------------------------------------------------------------- #

@event.listens_for(DefectLearningEvent, "before_update")
def _prevent_defect_event_mutation(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError(
        "Forensic Immutability Violation: DefectLearningEvent is append-only "
        "and cannot be mutated after creation."
    )


@event.listens_for(DefectLearningEvent, "before_delete")
def _prevent_defect_event_deletion(mapper, connection, target):
    from app.models.immutability import bypass_immutability
    if bypass_immutability:
        return
    raise RuntimeError(
        "Forensic Immutability Violation: DefectLearningEvent is append-only "
        "and cannot be deleted."
    )
