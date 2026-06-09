"""
app/services/manual_override_learner.py
=========================================

Learns from engineer manual test additions and encodes them as persistent
TestCoverageLink knowledge-graph edges.

Context
-------
When an engineer adds tests beyond Veriscope's recommendation for a PR, it is
a deliberate signal: those tests cover the changed files.  This service
translates that action into ``TestCoverageLink`` rows tagged with
``source=MANUAL_OVERRIDE``.

Signal model
------------
* **Stronger than heuristics, weaker than direct coverage.**  A single manual
  addition starts with ``link_strength=0.5`` — above any path heuristic (0.4)
  but below direct coverage (1.0).
* **Repetition increases confidence.**  Every subsequent addition of the same
  test for the same file increments the strength by 0.1 (capped at 1.0),
  modelling the rule "frequently added tests become future recommendations."
* **Confidence is always HIGH** (1.0) — the engineer is the ground truth.
* **``override_count``** is tracked naturally via ``TestCoverageLink.run_count``
  which ``upsert_link`` increments on every call.

Link target — changed files
---------------------------
A manual addition means "I need this test for this PR's changed files."
We therefore create one TestCoverageLink per (test, changed_file) pair.
Changed files are read from ``PullRequestChangedFile`` on the outcome's PR.
If no PR is linked, no links can be created (we don't know which files).

Idempotency
-----------
All writes go through ``TestCoverageLinkRepository.upsert_link`` which
enforces the uniqueness constraint and only updates when called again.

Non-blocking
------------
Any failure is captured in ``LearningResult.errors`` and never propagates
to the caller (``collect()`` must always complete successfully).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationOutcome
from app.models.pull_request import PullRequestChangedFile
from app.models.test_result import TestCase
from app.repositories.test_coverage_link import TestCoverageLinkRepository

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Constants                                                                   #
# --------------------------------------------------------------------------- #

_SOURCE = "MANUAL_OVERRIDE"
_CONFIDENCE = 1.0          # Engineer action is ground truth

# Base link_strength for first manual addition.
# Above any path-heuristic (0.4) but below direct coverage (1.0).
_BASE_STRENGTH    = 0.5
_STRENGTH_STEP    = 0.1    # Additional strength per repeated override
_MAX_STRENGTH     = 1.0

# File extensions that indicate non-source-code assets — skip them.
_SKIP_EXTENSIONS = frozenset({
    ".md", ".rst", ".txt", ".yml", ".yaml", ".json", ".toml",
    ".lock", ".cfg", ".ini", ".png", ".jpg", ".svg", ".ico",
})


# --------------------------------------------------------------------------- #
#  Result dataclass                                                            #
# --------------------------------------------------------------------------- #

@dataclass
class LearningResult:
    """Summary of a single manual-override learning pass.

    Attributes
    ----------
    links_upserted:
        Total ``TestCoverageLink`` rows created or updated.
    tests_processed:
        Number of distinct manually-added test identifiers processed.
    tests_skipped:
        Number of tests that could not be resolved or had no file targets.
    override_count_increments:
        Total number of ``override_count`` field increments written across
        all upserted links.  One increment per (test, file) pair processed.
    errors:
        Non-fatal error messages encountered during the run.
    """
    links_upserted:           int = 0
    tests_processed:          int = 0
    tests_skipped:            int = 0
    override_count_increments: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def had_overrides(self) -> bool:
        return self.tests_processed > 0


# --------------------------------------------------------------------------- #
#  Service                                                                     #
# --------------------------------------------------------------------------- #

class ManualOverrideLearner:
    """Learns from engineer manual test additions after outcome collection.

    Usage::

        result = ManualOverrideLearner.learn_from_outcome(
            db=db,
            outcome=outcome,
            workspace_id=workspace_id,
        )
    """

    @staticmethod
    def learn_from_outcome(
        db: Session,
        *,
        outcome: RecommendationOutcome,
        workspace_id: UUID,
        observed_at: Optional[datetime] = None,
    ) -> LearningResult:
        """Create or strengthen TestCoverageLink rows from manually-added tests.

        Parameters
        ----------
        db:
            Active SQLAlchemy session.  Caller owns the transaction lifecycle.
        outcome:
            The ``RecommendationOutcome`` whose ``manually_added_tests`` list
            should be processed.  Must be already committed (so that
            ``test_outcomes`` rows are visible).
        workspace_id:
            Workspace that owns the repository — required for ``upsert_link``.
        observed_at:
            Timestamp to record as the observation time.  Defaults to now.

        Returns
        -------
        LearningResult
            Summary of what was written, skipped, or failed.
        """
        result = LearningResult()
        now = observed_at or datetime.utcnow()

        # ------------------------------------------------------------------ #
        #  1. Collect manually-added test stable identities                   #
        # ------------------------------------------------------------------ #
        try:
            manually_added: List[str] = outcome.manually_added_tests
        except Exception as exc:
            msg = f"ManualOverrideLearner: failed to read manually_added_tests from outcome {outcome.id}: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            return result

        if not manually_added:
            logger.debug(
                "ManualOverrideLearner: outcome %s has no manually_added_tests — no-op.",
                outcome.id,
            )
            return result

        # ------------------------------------------------------------------ #
        #  2. Resolve changed files from the linked PR                        #
        # ------------------------------------------------------------------ #
        repository_id: UUID = outcome.repository_id

        if not outcome.pull_request_id:
            logger.info(
                "ManualOverrideLearner: outcome %s has no pull_request_id — "
                "cannot determine changed files; skipping %d tests.",
                outcome.id,
                len(manually_added),
            )
            result.tests_skipped += len(manually_added)
            return result

        try:
            changed_file_rows = (
                db.query(PullRequestChangedFile)
                .filter(
                    PullRequestChangedFile.pull_request_id == outcome.pull_request_id,
                    PullRequestChangedFile.status != "removed",
                )
                .all()
            )
        except Exception as exc:
            msg = (
                f"ManualOverrideLearner: failed to query PullRequestChangedFile "
                f"for PR {outcome.pull_request_id}: {exc}"
            )
            logger.error(msg)
            result.errors.append(msg)
            return result

        # Filter to source-code files only
        target_files: List[str] = [
            row.file_path
            for row in changed_file_rows
            if not any(row.file_path.endswith(ext) for ext in _SKIP_EXTENSIONS)
        ]

        if not target_files:
            logger.info(
                "ManualOverrideLearner: PR %s has no source-code changed files "
                "after filtering — skipping %d manually-added tests.",
                outcome.pull_request_id,
                len(manually_added),
            )
            result.tests_skipped += len(manually_added)
            return result

        # ------------------------------------------------------------------ #
        #  3. For each manually-added test, upsert links to every target file #
        # ------------------------------------------------------------------ #
        repo_layer = TestCoverageLinkRepository(db)

        for test_identifier in manually_added:
            if not test_identifier:
                result.tests_skipped += 1
                continue

            links_for_this_test = 0

            for file_path in target_files:
                # Compute strength based on existing override_count.
                # override_count is surfaced via run_count on the existing link
                # (if any) before the upsert.
                existing = repo_layer.get_exact_link(
                    repository_id, test_identifier, file_path
                )
                # Use override_count (not run_count) — we only want to know
                # how many times an engineer explicitly added this test, not
                # the total number of executions from all sources.
                override_count = (existing.override_count if existing else 0)
                strength = min(
                    _BASE_STRENGTH + override_count * _STRENGTH_STEP,
                    _MAX_STRENGTH,
                )

                try:
                    repo_layer.upsert_link(
                        workspace_id=workspace_id,
                        repository_id=repository_id,
                        test_identifier=test_identifier,
                        file_path=file_path,
                        source=_SOURCE,
                        link_strength=strength,
                        confidence=_CONFIDENCE,
                        observed_at=now,
                        outcome=None,   # override adds no pass/fail signal
                    )
                    links_for_this_test += 1
                    result.links_upserted += 1
                    result.override_count_increments += 1
                except Exception as exc:
                    msg = (
                        f"ManualOverrideLearner: failed upsert for "
                        f"test={test_identifier!r} file={file_path!r}: {exc}"
                    )
                    logger.error(msg)
                    result.errors.append(msg)

            if links_for_this_test > 0:
                result.tests_processed += 1
            else:
                result.tests_skipped += 1

        logger.info(
            "ManualOverrideLearner: outcome=%s tests_processed=%d "
            "links_upserted=%d override_count_increments=%d "
            "tests_skipped=%d errors=%d",
            outcome.id,
            result.tests_processed,
            result.links_upserted,
            result.override_count_increments,
            result.tests_skipped,
            len(result.errors),
        )
        return result

    # ---------------------------------------------------------------------- #
    #  Strength formula (exposed for testing)                                 #
    # ---------------------------------------------------------------------- #

    @staticmethod
    def compute_strength(override_count: int) -> float:
        """Compute link_strength from the number of times this test has been
        manually added for the same file.

        ``override_count`` is the current ``override_count`` on the existing
        link *before* this addition is applied (i.e., the value from
        ``TestCoverageLink.override_count``, not ``run_count``).

        Examples
        --------
        >>> ManualOverrideLearner.compute_strength(0)   # first addition
        0.5
        >>> ManualOverrideLearner.compute_strength(1)   # second addition
        0.6
        >>> ManualOverrideLearner.compute_strength(5)
        1.0
        """
        return min(_BASE_STRENGTH + override_count * _STRENGTH_STEP, _MAX_STRENGTH)
