"""
app/services/escaped_defect_learner.py
=========================================

Learns from production defects and rollbacks to strengthen future
recommendation conservatism.

Purpose
-------
When a ``RecommendationOutcome`` is flagged with ``escaped_defect_detected``
or ``rollback_occurred`` (or both), Veriscope has the strongest negative
signal available: something reached production that shouldn't have.

This service:

1. Reads the four sets from the outcome:
   - **recommended_tests** — what Veriscope suggested.
   - **executed_tests**    — what CI actually ran.
   - **missed_tests**      — ``recommended_tests − executed_tests``: the tests
     that were suggested but skipped while the defect slipped through.
   - **changed_files**     — files modified in the PR.

2. For every (missed_test, changed_file) pair, creates or strengthens a
   ``TestCoverageLink`` row tagged ``source=ESCAPED_DEFECT`` so future
   recommendations around the same file-test combination become more
   conservative.

3. Writes an append-only ``DefectLearningEvent`` audit record.

Signal model
------------
* Production escapes carry the highest signal weight — stronger baseline
  than manual overrides (0.80 vs 0.50).
* ``link_strength`` grows by 0.05 per additional escape, capped at 1.0.
* ``defect_count`` on ``TestCoverageLink`` counts only ESCAPED_DEFECT
  upserts — distinct from ``run_count`` and ``override_count``.
* ``confidence`` is always ``1.0`` (maximum) — production is ground truth.

Non-blocking
------------
``learn_from_outcome()`` always returns a ``DefectLearningResult``; it never
propagates exceptions to the caller.  All failures land in
``DefectLearningResult.errors``.

Immutability
------------
Historical ``RecommendationOutcome``, ``RecommendationRun``, and reasoning
entries are never mutated.  Only ``TestCoverageLink`` rows (forward-looking
knowledge-graph edges) and new ``DefectLearningEvent`` rows are written.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Set
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.defect_learning_event import DefectLearningEvent
from app.models.pull_request import PullRequestChangedFile
from app.models.recommendation import RecommendationOutcome
from app.repositories.test_coverage_link import TestCoverageLinkRepository

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Constants                                                                   #
# --------------------------------------------------------------------------- #

# source tag written on every TestCoverageLink created/updated by this learner
_SOURCE = "ESCAPED_DEFECT"

# Confidence is always maximum — production is ground truth
_CONFIDENCE = 1.0

# Strength formula: starts higher than manual-override (0.5) to reflect the
# severity of a production escape.
_BASE_STRENGTH  = 0.80
_STRENGTH_STEP  = 0.05
_MAX_STRENGTH   = 1.00


# --------------------------------------------------------------------------- #
#  Result dataclass                                                            #
# --------------------------------------------------------------------------- #

@dataclass
class DefectLearningResult:
    """Structured summary of a single defect-learning pass.

    Attributes
    ----------
    trigger_type:
        What triggered the pass.  One of ``ESCAPED_DEFECT``, ``ROLLBACK``,
        ``BOTH``, or ``NONE`` (when the outcome had neither flag set).
    changed_files:
        File paths that were changed in the PR.
    recommended_tests:
        Test identifiers that Veriscope originally recommended.
    executed_tests:
        Test identifiers that CI actually ran.
    missed_tests:
        ``recommended_tests − executed_tests``: the gap that let the defect
        through.
    links_created_or_strengthened:
        Total ``TestCoverageLink`` rows created or updated.
    defect_strength_increments:
        Total ``defect_count`` increments applied across all upserted links.
    errors:
        Non-fatal error messages.
    """

    trigger_type:                  str = "NONE"
    changed_files:                 List[str] = field(default_factory=list)
    recommended_tests:             List[str] = field(default_factory=list)
    executed_tests:                List[str] = field(default_factory=list)
    missed_tests:                  List[str] = field(default_factory=list)
    links_created_or_strengthened: int = 0
    defect_strength_increments:    int = 0
    errors:                        List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True when no errors were recorded during the pass."""
        return len(self.errors) == 0

    @property
    def has_missed_tests(self) -> bool:
        """True when at least one recommended test was not executed."""
        return len(self.missed_tests) > 0


# --------------------------------------------------------------------------- #
#  Service                                                                     #
# --------------------------------------------------------------------------- #

class EscapedDefectLearner:
    """Learns from production escapes and rollbacks on a finalised outcome.

    Usage::

        result = EscapedDefectLearner.learn_from_outcome(
            db=db,
            outcome=outcome,
            workspace_id=workspace_id,
        )
        if result.has_missed_tests:
            logger.warning(
                "Defect escape: %d missed tests strengthened for %d files",
                len(result.missed_tests),
                len(result.changed_files),
            )
    """

    @staticmethod
    def compute_strength(defect_count: int) -> float:
        """Compute ``link_strength`` from accumulated escape evidence.

        ``defect_count`` is the current value on the existing link *before*
        this escape is applied (i.e., ``TestCoverageLink.defect_count``).

        Examples
        --------
        >>> EscapedDefectLearner.compute_strength(0)   # first escape
        0.8
        >>> EscapedDefectLearner.compute_strength(1)   # second escape
        0.85
        >>> EscapedDefectLearner.compute_strength(4)   # capped
        1.0
        """
        return min(_BASE_STRENGTH + defect_count * _STRENGTH_STEP, _MAX_STRENGTH)

    @staticmethod
    def learn_from_outcome(
        db: Session,
        *,
        outcome: RecommendationOutcome,
        workspace_id: UUID,
        observed_at: Optional[datetime] = None,
    ) -> DefectLearningResult:
        """Learn from a finalised outcome that carries an escape or rollback.

        Parameters
        ----------
        db:
            Active SQLAlchemy session.  Caller owns the transaction lifecycle.
        outcome:
            The ``RecommendationOutcome`` to learn from.  Must have
            ``escaped_defect_detected`` or ``rollback_occurred`` set to True,
            otherwise the method returns immediately with ``trigger_type=NONE``.
        workspace_id:
            Workspace that owns the repository — required for the
            ``TestCoverageLink`` upsert.
        observed_at:
            Timestamp to record as the observation time.  Defaults to now.

        Returns
        -------
        DefectLearningResult
            Always returns; never raises.
        """
        result = DefectLearningResult()
        now = observed_at or datetime.utcnow()

        # ------------------------------------------------------------------ #
        #  1. Validate trigger                                                 #
        # ------------------------------------------------------------------ #
        is_escape   = bool(outcome.escaped_defect_detected)
        is_rollback = bool(outcome.rollback_occurred)

        if not is_escape and not is_rollback:
            logger.debug(
                "EscapedDefectLearner: outcome %s has neither escaped_defect_detected "
                "nor rollback_occurred — skipping learning pass.",
                outcome.id,
            )
            result.trigger_type = "NONE"
            return result

        if is_escape and is_rollback:
            result.trigger_type = "BOTH"
        elif is_escape:
            result.trigger_type = "ESCAPED_DEFECT"
        else:
            result.trigger_type = "ROLLBACK"

        # ------------------------------------------------------------------ #
        #  2. Read recommended / executed / missed test sets                   #
        # ------------------------------------------------------------------ #
        try:
            recommended: List[str] = list(outcome.recommended_tests or [])
            executed:    List[str] = list(outcome.executed_tests or [])
        except Exception as exc:
            msg = (
                f"EscapedDefectLearner: failed to read test sets from "
                f"outcome {outcome.id}: {exc}"
            )
            logger.error(msg)
            result.errors.append(msg)
            return result

        result.recommended_tests = recommended
        result.executed_tests    = executed

        recommended_set: Set[str] = set(recommended)
        executed_set:    Set[str] = set(executed)

        # missed = tests Veriscope suggested but were skipped while defect escaped
        missed_set  = recommended_set - executed_set
        result.missed_tests = sorted(missed_set)

        # ------------------------------------------------------------------ #
        #  3. Load changed files from the PR                                   #
        # ------------------------------------------------------------------ #
        try:
            changed_file_rows = (
                db.query(PullRequestChangedFile)
                .filter(
                    PullRequestChangedFile.pull_request_id == outcome.pull_request_id
                )
                .all()
            )
            changed_files: List[str] = [
                row.file_path.replace("\\", "/")
                for row in changed_file_rows
            ]
            result.changed_files = changed_files

            # Record escaped defects and rollbacks in ModuleRiskProfile for all changed files
            try:
                from app.repositories.module_risk_profile import ModuleRiskProfileRepository
                profile_repo = ModuleRiskProfileRepository(db)
                for file_path in changed_files:
                    if is_escape:
                        profile_repo.record_escaped_defect(outcome.repository_id, file_path)
                    if is_rollback:
                        profile_repo.record_rollback(outcome.repository_id, file_path)
            except Exception as exc:
                logger.error(
                    "EscapedDefectLearner: failed to update ModuleRiskProfile "
                    "for outcome %s: %s",
                    outcome.id,
                    exc,
                )
        except Exception as exc:
            msg = (
                f"EscapedDefectLearner: failed to load changed files for "
                f"outcome {outcome.id} (pr={outcome.pull_request_id}): {exc}"
            )
            logger.error(msg)
            result.errors.append(msg)
            return result

        # ------------------------------------------------------------------ #
        #  4. Guard: nothing to learn if gap or files are empty               #
        # ------------------------------------------------------------------ #
        if not missed_set:
            logger.info(
                "EscapedDefectLearner: outcome %s (%s) — no missed tests "
                "(all recommended tests were executed). No links to create.",
                outcome.id,
                result.trigger_type,
            )
            _write_event(
                db=db,
                outcome=outcome,
                result=result,
                now=now,
            )
            return result

        if not changed_files:
            logger.info(
                "EscapedDefectLearner: outcome %s (%s) — no changed files found "
                "for PR %s. No links to create.",
                outcome.id,
                result.trigger_type,
                outcome.pull_request_id,
            )
            _write_event(db=db, outcome=outcome, result=result, now=now)
            return result

        # ------------------------------------------------------------------ #
        #  5. Upsert TestCoverageLink for each (missed_test, changed_file)    #
        # ------------------------------------------------------------------ #
        repo_layer = TestCoverageLinkRepository(db)
        max_defect_count_seen = 0

        for test_identifier in sorted(missed_set):
            for file_path in changed_files:
                try:
                    existing = repo_layer.get_exact_link(
                        outcome.repository_id, test_identifier, file_path
                    )
                    # Use defect_count (not run_count) — only count production escapes.
                    current_defect_count = (existing.defect_count if existing else 0)
                    strength = EscapedDefectLearner.compute_strength(current_defect_count)

                    repo_layer.upsert_link(
                        workspace_id=workspace_id,
                        repository_id=outcome.repository_id,
                        test_identifier=test_identifier,
                        file_path=file_path,
                        source=_SOURCE,
                        link_strength=strength,
                        confidence=_CONFIDENCE,
                        observed_at=now,
                        outcome=None,  # escape is not a pass/fail execution signal
                    )

                    result.links_created_or_strengthened += 1
                    result.defect_strength_increments += 1
                    max_defect_count_seen = max(
                        max_defect_count_seen, current_defect_count + 1
                    )

                except Exception as exc:
                    msg = (
                        f"EscapedDefectLearner: upsert failed for "
                        f"({test_identifier!r}, {file_path!r}) on outcome "
                        f"{outcome.id}: {exc}"
                    )
                    logger.warning(msg)
                    result.errors.append(msg)

        # ------------------------------------------------------------------ #
        #  6. Write append-only DefectLearningEvent audit record              #
        # ------------------------------------------------------------------ #
        _write_event(
            db=db,
            outcome=outcome,
            result=result,
            now=now,
            max_defect_count_seen=max_defect_count_seen,
        )

        # ------------------------------------------------------------------ #
        #  7. Log summary                                                      #
        # ------------------------------------------------------------------ #
        logger.info(
            "EscapedDefectLearner: outcome=%s trigger=%s "
            "missed=%d changed_files=%d links_updated=%d "
            "defect_increments=%d errors=%d",
            outcome.id,
            result.trigger_type,
            len(result.missed_tests),
            len(result.changed_files),
            result.links_created_or_strengthened,
            result.defect_strength_increments,
            len(result.errors),
        )

        return result


# --------------------------------------------------------------------------- #
#  Internal helpers                                                            #
# --------------------------------------------------------------------------- #

def _write_event(
    db: Session,
    outcome: RecommendationOutcome,
    result: DefectLearningResult,
    now: datetime,
    max_defect_count_seen: int = 0,
) -> None:
    """Write an append-only DefectLearningEvent row.

    Failures are logged but do not propagate — the learning result is already
    populated and the caller should not be blocked by an audit-write failure.
    """
    try:
        event = DefectLearningEvent(
            repository_id=outcome.repository_id,
            recommendation_outcome_id=outcome.id,
            pull_request_id=outcome.pull_request_id,
            trigger_type=result.trigger_type,
            changed_files=result.changed_files,
            recommended_tests=result.recommended_tests,
            executed_tests=result.executed_tests,
            missed_tests=result.missed_tests,
            links_created=result.links_created_or_strengthened,
            links_strengthened=result.links_created_or_strengthened,
            defect_count_at_time=max_defect_count_seen,
            errors=result.errors,
            created_at=now,
        )
        db.add(event)
        db.commit()
    except Exception as exc:
        logger.error(
            "EscapedDefectLearner: failed to write DefectLearningEvent "
            "for outcome %s: %s",
            outcome.id,
            exc,
        )
