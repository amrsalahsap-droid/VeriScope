"""
app/services/coverage_link_expander.py
=======================================

Expands the TestCoverageLink knowledge graph from coverage report evidence.

Responsibility
--------------
After a CoverageReport has been ingested and its FileTestLink rows have been
resolved, this service translates those per-report links into persistent,
repository-scoped TestCoverageLink rows via the upsert pattern.

Design principles
-----------------
* **Coverage evidence is authoritative.** Links derived from actual coverage
  instrumentation (``DIRECT``) always produce the strongest ``link_strength``
  value and override weaker previously stored values.
* **Idempotent.** Every call upserts rather than inserts, so re-uploading the
  same or an updated coverage report is safe.
* **Non-blocking.** Failures in graph expansion are logged and surfaced via the
  returned ``ExpansionResult`` but never prevent the parent ingestion from
  completing. The caller decides whether to raise.
* **No duplicates.** The underlying ``TestCoverageLinkRepository.upsert_link``
  guarantees the uniqueness constraint is never violated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.coverage import FileTestLink
from app.models.test_result import TestCase
from app.repositories.test_coverage_link import TestCoverageLinkRepository

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Constants                                                                   #
# --------------------------------------------------------------------------- #

# Source tag stored on every coverage-derived TestCoverageLink.
_SOURCE_COVERAGE = "COVERAGE"

# Confidence stored for all coverage-derived links.
_CONFIDENCE_HIGH = 1.0

# link_strength values per mapping type.
# Coverage evidence is always stronger than heuristic learning.
_STRENGTH_BY_MAPPING_TYPE: dict[str, float] = {
    "DIRECT":          1.0,   # Exact test-name match from TN: tag
    "HEURISTIC_NAMING": 0.7,  # Naming convention match
    "HEURISTIC_PATH":  0.4,   # Parent-directory similarity match
}

# Outcome from the ingestion service — coverage tells us the test *ran* but
# gives no pass/fail signal for individual files.  We record the observation
# without a success/failure outcome so only run_count is incremented.
_OUTCOME_OBSERVED: Optional[str] = None


# --------------------------------------------------------------------------- #
#  Result dataclass                                                            #
# --------------------------------------------------------------------------- #

@dataclass
class ExpansionResult:
    """Summary of a single knowledge-graph expansion run.

    Attributes
    ----------
    links_upserted:
        Number of TestCoverageLink rows that were created or updated.
    links_skipped:
        Number of FileTestLink rows that were skipped (e.g. test case not
        found, unknown mapping type).
    errors:
        List of error messages encountered during expansion.  Non-empty
        indicates a partial expansion.
    """
    links_upserted: int = 0
    links_skipped: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def partial(self) -> bool:
        return self.links_skipped > 0 and self.links_upserted > 0


# --------------------------------------------------------------------------- #
#  Service                                                                     #
# --------------------------------------------------------------------------- #

class CoverageLinkExpander:
    """Expands the TestCoverageLink knowledge graph from a freshly ingested
    CoverageReport.

    Usage::

        result = CoverageLinkExpander.expand_from_report(
            db=db,
            workspace_id=workspace_id,
            repository_id=repository_id,
            coverage_report_id=report.id,
            observed_at=report.created_at,
        )
    """

    @staticmethod
    def expand_from_report(
        db: Session,
        *,
        workspace_id: UUID,
        repository_id: UUID,
        coverage_report_id: UUID,
        observed_at: Optional[datetime] = None,
    ) -> ExpansionResult:
        """Create or update TestCoverageLink rows from a coverage report's
        resolved FileTestLink records.

        This method:

        1. Fetches all ``FileTestLink`` rows for ``coverage_report_id``.
        2. For each link resolves the associated ``TestCase.stable_identity``.
        3. Determines ``link_strength`` from the mapping type.
        4. Calls ``upsert_link`` — this safely creates or updates the
           persistent edge without violating the uniqueness constraint.

        Parameters
        ----------
        db:
            Active SQLAlchemy session.  The caller is responsible for
            committing or rolling back.
        workspace_id:
            Workspace that owns the repository.
        repository_id:
            Repository the coverage report belongs to.
        coverage_report_id:
            ID of the ``CoverageReport`` whose ``FileTestLink`` rows should
            be translated into ``TestCoverageLink`` rows.
        observed_at:
            Timestamp of the observation.  Defaults to ``datetime.utcnow()``.

        Returns
        -------
        ExpansionResult
            Summary of the expansion with counts and any errors.
        """
        result = ExpansionResult()
        now = observed_at or datetime.utcnow()
        repo_layer = TestCoverageLinkRepository(db)

        # ------------------------------------------------------------------ #
        #  1. Fetch all FileTestLink rows for this report                     #
        # ------------------------------------------------------------------ #
        try:
            file_test_links: list[FileTestLink] = (
                db.query(FileTestLink)
                .filter(FileTestLink.coverage_report_id == coverage_report_id)
                .all()
            )
        except Exception as exc:
            msg = f"Failed to query FileTestLink for report {coverage_report_id}: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            return result

        if not file_test_links:
            logger.debug(
                "CoverageLinkExpander: no FileTestLink rows found for report %s — "
                "knowledge graph not expanded.",
                coverage_report_id,
            )
            return result

        # ------------------------------------------------------------------ #
        #  2. Build a test_case_id → stable_identity lookup (batch)          #
        # ------------------------------------------------------------------ #
        test_case_ids = list({lnk.test_case_id for lnk in file_test_links})
        try:
            test_cases: list[TestCase] = (
                db.query(TestCase)
                .filter(TestCase.id.in_(test_case_ids))
                .all()
            )
        except Exception as exc:
            msg = f"Failed to batch-load TestCase rows for report {coverage_report_id}: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            return result

        identity_by_id: dict[UUID, str] = {
            tc.id: tc.stable_identity for tc in test_cases
        }

        # ------------------------------------------------------------------ #
        #  3. Upsert one TestCoverageLink per (test_identifier, file_path)   #
        # ------------------------------------------------------------------ #
        for ftl in file_test_links:
            test_identifier = identity_by_id.get(ftl.test_case_id)
            if not test_identifier:
                logger.warning(
                    "CoverageLinkExpander: TestCase %s not found — "
                    "skipping FileTestLink %s.",
                    ftl.test_case_id,
                    ftl.id,
                )
                result.links_skipped += 1
                continue

            link_strength = _STRENGTH_BY_MAPPING_TYPE.get(ftl.mapping_type)
            if link_strength is None:
                logger.warning(
                    "CoverageLinkExpander: Unknown mapping_type %r on FileTestLink %s — "
                    "defaulting link_strength to 0.0.",
                    ftl.mapping_type,
                    ftl.id,
                )
                link_strength = 0.0

            try:
                repo_layer.upsert_link(
                    workspace_id=workspace_id,
                    repository_id=repository_id,
                    test_identifier=test_identifier,
                    file_path=ftl.file_path,
                    source=_SOURCE_COVERAGE,
                    link_strength=link_strength,
                    confidence=_CONFIDENCE_HIGH,
                    observed_at=now,
                    outcome=_OUTCOME_OBSERVED,
                )
                result.links_upserted += 1
            except Exception as exc:
                msg = (
                    f"Failed to upsert TestCoverageLink for test={test_identifier!r} "
                    f"file={ftl.file_path!r}: {exc}"
                )
                logger.error(msg)
                result.errors.append(msg)
                result.links_skipped += 1
                continue

        logger.info(
            "CoverageLinkExpander: report=%s upserted=%d skipped=%d errors=%d",
            coverage_report_id,
            result.links_upserted,
            result.links_skipped,
            len(result.errors),
        )
        return result
