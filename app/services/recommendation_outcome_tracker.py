"""
app/services/recommendation_outcome_tracker.py
================================================

Orchestrates learning from a finalised ``RecommendationOutcome``.

Purpose
-------
After a ``RecommendationOutcome`` is finalised (all four test sets are
populated), this service:

1. Reads the four test sets:
   - **recommended_tests**  — what Veriscope suggested.
   - **executed_tests**     — what CI actually ran.
   - **manually_added_tests**  — engineer added beyond the recommendation.
   - **manually_removed_tests** — engineer removed from the recommendation.

2. Calls ``ManualOverrideLearner.learn_from_outcome()`` for manual additions
   to create or strengthen ``TestCoverageLink`` rows tagged
   ``source=MANUAL_OVERRIDE``.

3. Queries ``TestCoverageLinkRepository.get_promotable_links()`` to surface
   tests that have been manually added often enough to be considered future
   recommendation candidates.

4. Returns an ``OutcomeTrackingResult`` — never raises.

Signal model
------------
* Engineer additions are the strongest signal (``confidence=1.0``).
* ``link_strength`` starts at 0.5 on first addition, grows by 0.1 per
  additional addition (capped at 1.0).
* ``override_count`` on ``TestCoverageLink`` counts only MANUAL_OVERRIDE
  upserts — distinct from ``run_count`` which counts all sources.
* A test is considered **promotable** when its ``override_count`` reaches
  ``PROMOTION_THRESHOLD`` (default: 3).

Non-blocking
------------
All failures are captured in ``OutcomeTrackingResult.errors``.
``track()`` always returns; it never propagates exceptions to the caller.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationOutcome
from app.repositories.test_coverage_link import TestCoverageLinkRepository
from app.services.manual_override_learner import LearningResult, ManualOverrideLearner

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Constants                                                                   #
# --------------------------------------------------------------------------- #

# Minimum override_count for a test to be considered a future recommendation
# candidate.  "Frequently added" is defined as being manually added at least
# this many times across different PR outcomes.
PROMOTION_THRESHOLD: int = 3


# --------------------------------------------------------------------------- #
#  Result dataclass                                                            #
# --------------------------------------------------------------------------- #

@dataclass
class OutcomeTrackingResult:
    """Structured summary of a single outcome-tracking pass.

    Attributes
    ----------
    recommended_tests:
        Test identifiers that Veriscope originally recommended.
    executed_tests:
        Test identifiers that CI actually executed.
    manually_added_tests:
        Test identifiers the engineer added beyond the recommendation.
    manually_removed_tests:
        Test identifiers the engineer removed from the recommendation.
    links_created_or_strengthened:
        Number of ``TestCoverageLink`` rows created or updated (from the
        learning step).
    override_count_increments:
        Total ``override_count`` increments applied across all upserted links.
    promotable_tests:
        Test identifiers whose ``override_count`` has reached
        ``PROMOTION_THRESHOLD``.  These are candidates for future
        automated recommendations.
    errors:
        Non-fatal error messages.  A non-empty list means one or more steps
        partially failed but the tracker still completed.
    """

    recommended_tests:           List[str] = field(default_factory=list)
    executed_tests:              List[str] = field(default_factory=list)
    manually_added_tests:        List[str] = field(default_factory=list)
    manually_removed_tests:      List[str] = field(default_factory=list)
    links_created_or_strengthened: int = 0
    override_count_increments:   int = 0
    promotable_tests:            List[str] = field(default_factory=list)
    errors:                      List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True when no errors were recorded during tracking."""
        return len(self.errors) == 0

    @property
    def has_promotable_tests(self) -> bool:
        """True when at least one test has reached the promotion threshold."""
        return len(self.promotable_tests) > 0


# --------------------------------------------------------------------------- #
#  Service                                                                     #
# --------------------------------------------------------------------------- #

class RecommendationOutcomeTracker:
    """Learns from engineer behaviour on a finalised ``RecommendationOutcome``.

    Usage::

        result = RecommendationOutcomeTracker.track(
            db=db,
            outcome=outcome,
            workspace_id=workspace_id,
        )
        if result.has_promotable_tests:
            # Surface result.promotable_tests as future recommendation seeds
            ...
    """

    @staticmethod
    def track(
        db: Session,
        *,
        outcome: RecommendationOutcome,
        workspace_id: UUID,
        observed_at: Optional[datetime] = None,
        promotion_threshold: int = PROMOTION_THRESHOLD,
    ) -> OutcomeTrackingResult:
        """Learn from all four test sets on a finalised outcome.

        Parameters
        ----------
        db:
            Active SQLAlchemy session.  Caller owns the transaction lifecycle.
        outcome:
            The ``RecommendationOutcome`` to process.  All four test-set
            properties (``recommended_tests``, ``executed_tests``,
            ``manually_added_tests``, ``manually_removed_tests``) must be
            accessible.
        workspace_id:
            Workspace that owns the repository — required for the
            ``TestCoverageLink`` upsert.
        observed_at:
            Timestamp to record as the observation time.  Defaults to now.
        promotion_threshold:
            Minimum ``override_count`` for a test to be included in
            ``promotable_tests``.  Defaults to :data:`PROMOTION_THRESHOLD`.

        Returns
        -------
        OutcomeTrackingResult
            Structured summary.  Always returns; never raises.
        """
        result = OutcomeTrackingResult()
        now = observed_at or datetime.utcnow()

        # ------------------------------------------------------------------ #
        #  1. Read all four test sets                                          #
        # ------------------------------------------------------------------ #
        try:
            result.recommended_tests    = list(outcome.recommended_tests or [])
            result.executed_tests       = list(outcome.executed_tests or [])
            result.manually_added_tests = list(outcome.manually_added_tests or [])
            result.manually_removed_tests = list(outcome.manually_removed_tests or [])
        except Exception as exc:
            msg = (
                f"RecommendationOutcomeTracker: failed to read test sets "
                f"from outcome {outcome.id}: {exc}"
            )
            logger.error(msg)
            result.errors.append(msg)
            return result

        logger.debug(
            "RecommendationOutcomeTracker: outcome=%s recommended=%d executed=%d "
            "manually_added=%d manually_removed=%d",
            outcome.id,
            len(result.recommended_tests),
            len(result.executed_tests),
            len(result.manually_added_tests),
            len(result.manually_removed_tests),
        )

        # ------------------------------------------------------------------ #
        #  2. Learn from manual additions                                      #
        # ------------------------------------------------------------------ #
        if result.manually_added_tests:
            try:
                learn_result: LearningResult = ManualOverrideLearner.learn_from_outcome(
                    db=db,
                    outcome=outcome,
                    workspace_id=workspace_id,
                    observed_at=now,
                )
                result.links_created_or_strengthened = learn_result.links_upserted
                result.override_count_increments     = learn_result.override_count_increments
                if not learn_result.success:
                    for err in learn_result.errors:
                        logger.warning(
                            "RecommendationOutcomeTracker: learner error for outcome %s: %s",
                            outcome.id,
                            err,
                        )
                    result.errors.extend(learn_result.errors)
            except Exception as exc:
                msg = (
                    f"RecommendationOutcomeTracker: ManualOverrideLearner raised "
                    f"an unexpected exception for outcome {outcome.id}: {exc}"
                )
                logger.error(msg)
                result.errors.append(msg)
        else:
            logger.debug(
                "RecommendationOutcomeTracker: outcome %s has no manually_added_tests "
                "— skipping learning step.",
                outcome.id,
            )

        # ------------------------------------------------------------------ #
        #  2.5. Learn from outcome tracking (LearningEngineV2)               #
        # ------------------------------------------------------------------ #
        try:
            from app.services.learning_engine_v2 import LearningEngineV2
            v2_result = LearningEngineV2.learn(
                db=db,
                outcome=outcome,
                workspace_id=workspace_id,
                observed_at=now,
            )
            if not v2_result.success:
                result.errors.extend(v2_result.errors)
        except Exception as exc:
            msg = f"RecommendationOutcomeTracker: LearningEngineV2 raised an unexpected exception: {exc}"
            logger.error(msg)
            result.errors.append(msg)

        # ------------------------------------------------------------------ #
        #  3. Query promotable tests                                           #
        # ------------------------------------------------------------------ #
        try:
            repo_layer = TestCoverageLinkRepository(db)
            promotable_links = repo_layer.get_promotable_links(
                repository_id=outcome.repository_id,
                min_override_count=promotion_threshold,
            )
            # Return stable test identifiers, deduplicated and sorted for determinism.
            seen: set = set()
            for link in promotable_links:
                if link.test_identifier not in seen:
                    result.promotable_tests.append(link.test_identifier)
                    seen.add(link.test_identifier)
        except Exception as exc:
            msg = (
                f"RecommendationOutcomeTracker: failed to query promotable links "
                f"for outcome {outcome.id}: {exc}"
            )
            logger.error(msg)
            result.errors.append(msg)

        # Record recommendation presented and accepted events in ModuleRiskProfile
        try:
            from app.repositories.module_risk_profile import ModuleRiskProfileRepository
            from app.models.test_coverage_link import TestCoverageLink
            from app.models.coverage import FileTestLink
            from app.models.test_result import TestCase
            
            profile_repo = ModuleRiskProfileRepository(db)
            all_tests_of_interest = set(result.recommended_tests)
            
            if all_tests_of_interest:
                # 1. Fetch mapping from TestCoverageLink
                tcl_links = db.query(TestCoverageLink.test_identifier, TestCoverageLink.file_path).filter(
                    TestCoverageLink.repository_id == outcome.repository_id,
                    TestCoverageLink.test_identifier.in_(all_tests_of_interest)
                ).all()
                
                # 2. Fetch mapping from FileTestLink
                ftl_links = db.query(TestCase.stable_identity, FileTestLink.file_path).join(
                    FileTestLink, TestCase.id == FileTestLink.test_case_id
                ).filter(
                    TestCase.repository_id == outcome.repository_id,
                    TestCase.stable_identity.in_(all_tests_of_interest)
                ).all()
                
                # Merge mappings
                test_to_files = {}
                for test_id, file_path in tcl_links + ftl_links:
                    test_to_files.setdefault(test_id, set()).add(file_path)
                
                # Record presented/accepted outcomes for each file path
                for test_id in result.recommended_tests:
                    files = test_to_files.get(test_id, set())
                    was_accepted = test_id in result.executed_tests
                    for file_path in files:
                        profile_repo.record_recommendation_outcome(
                            repository_id=outcome.repository_id,
                            module_path=file_path,
                            was_accepted=was_accepted
                        )
        except Exception as exc:
            msg = f"RecommendationOutcomeTracker: failed to track recommendation outcome accuracy: {exc}"
            logger.error(msg)
            result.errors.append(msg)

        # ------------------------------------------------------------------ #
        #  4. Log summary                                                      #
        # ------------------------------------------------------------------ #
        logger.info(
            "RecommendationOutcomeTracker: outcome=%s "
            "recommended=%d executed=%d manually_added=%d manually_removed=%d "
            "links_updated=%d override_increments=%d promotable=%d errors=%d",
            outcome.id,
            len(result.recommended_tests),
            len(result.executed_tests),
            len(result.manually_added_tests),
            len(result.manually_removed_tests),
            result.links_created_or_strengthened,
            result.override_count_increments,
            len(result.promotable_tests),
            len(result.errors),
        )

        return result
