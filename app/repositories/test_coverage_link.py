"""
app/repositories/test_coverage_link.py
========================================

Repository access layer for the TestCoverageLink knowledge-graph edge table.

Design principles
-----------------
* **upsert_link** is the primary write path.  Callers describe an observed
  edge; this method either creates the row or updates counters / timestamps
  atomically so that the uniqueness constraint is never violated.
* All reads are narrow-scope and scoped to a single repository to keep query
  complexity low.
* No learning/ML logic lives here — this layer only provides CRUD and
  counter-increment primitives.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.test_coverage_link import TestCoverageLink


class TestCoverageLinkRepository:
    """Data-access layer for :class:`~app.models.test_coverage_link.TestCoverageLink`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    #  Writes                                                              #
    # ------------------------------------------------------------------ #

    def upsert_link(
        self,
        *,
        workspace_id: UUID,
        repository_id: UUID,
        test_identifier: str,
        file_path: str,
        source: Optional[str] = None,
        link_strength: Optional[float] = None,
        confidence: Optional[float] = None,
        observed_at: Optional[datetime] = None,
        outcome: Optional[str] = None,  # "success" | "failure" | None
    ) -> "TestCoverageLink":
        """Create or update a test→file coverage link.

        If no row exists for ``(repository_id, test_identifier, file_path)``
        a new one is inserted.  If one already exists the following fields
        are updated:

        * ``last_seen_at`` — set to ``observed_at`` (defaults to utcnow).
        * ``run_count`` — incremented by 1.
        * ``success_count`` / ``failure_count`` — incremented based on
          ``outcome`` ("success" / "failure").  Other values leave both
          counters unchanged.
        * ``link_strength`` / ``confidence`` / ``source`` — overwritten only
          when the caller provides non-``None`` values.

        Parameters
        ----------
        workspace_id:
            Workspace that owns the repository.
        repository_id:
            Repository the edge belongs to.
        test_identifier:
            Stable test identity string (e.g. ``"suite::test_name"``).
        file_path:
            Normalised source-file path.
        source:
            Optional discovery source tag.
        link_strength:
            Optional edge weight to store or overwrite.
        confidence:
            Optional confidence value to store or overwrite.
        observed_at:
            Timestamp of the observation; defaults to ``datetime.utcnow()``.
        outcome:
            ``"success"`` or ``"failure"`` — controls counter increments.

        Returns
        -------
        TestCoverageLink
            The created or updated row, refreshed from the database.
        """
        now = observed_at or datetime.utcnow()

        existing = self._get_exact(repository_id, test_identifier, file_path)

        if existing is None:
            link = TestCoverageLink(
                workspace_id=workspace_id,
                repository_id=repository_id,
                test_identifier=test_identifier,
                file_path=file_path,
                source=source,
                link_strength=link_strength,
                confidence=confidence,
                run_count=1,
                success_count=1 if outcome == "success" else 0,
                failure_count=1 if outcome == "failure" else 0,
                # First manual override — start override_count at 1.
                override_count=1 if source == "MANUAL_OVERRIDE" else 0,
                # First escaped-defect event — start defect_count at 1.
                defect_count=1 if source == "ESCAPED_DEFECT" else 0,
                first_seen_at=now,
                last_seen_at=now,
            )
            self.db.add(link)
            self.db.commit()
            self.db.refresh(link)
            return link

        # Existing row — update in-place
        existing.run_count += 1
        if outcome == "success":
            existing.success_count += 1
        elif outcome == "failure":
            existing.failure_count += 1

        # Track manual-override additions separately from generic run_count.
        if source == "MANUAL_OVERRIDE":
            existing.override_count += 1

        # Track escaped-defect events: each call is a new production gap instance.
        if source == "ESCAPED_DEFECT":
            existing.defect_count += 1

        existing.last_seen_at = now

        if link_strength is not None:
            existing.link_strength = link_strength
        if confidence is not None:
            existing.confidence = confidence
        if source is not None:
            existing.source = source

        self.db.add(existing)
        self.db.commit()
        self.db.refresh(existing)
        return existing

    def create_link(self, link: TestCoverageLink) -> TestCoverageLink:
        """Persist a pre-constructed :class:`TestCoverageLink` instance.

        Prefer :meth:`upsert_link` for normal ingestion.  This method is
        intended for bulk-loading scenarios where the caller manages
        deduplication externally.

        Raises
        ------
        sqlalchemy.exc.IntegrityError
            If a row with the same ``(repository_id, test_identifier,
            file_path)`` already exists.
        """
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link

    # ------------------------------------------------------------------ #
    #  Reads                                                               #
    # ------------------------------------------------------------------ #

    def get_by_id(self, link_id: UUID) -> Optional[TestCoverageLink]:
        """Fetch a single link by its surrogate primary key."""
        return (
            self.db.query(TestCoverageLink)
            .filter(TestCoverageLink.id == link_id)
            .first()
        )

    def get_links_for_file(
        self,
        repository_id: UUID,
        file_path: str,
    ) -> List[TestCoverageLink]:
        """Return all test links that cover a specific source file.

        Uses the ``ix_test_coverage_links_repo_file`` composite index.
        """
        return (
            self.db.query(TestCoverageLink)
            .filter(
                and_(
                    TestCoverageLink.repository_id == repository_id,
                    TestCoverageLink.file_path == file_path,
                )
            )
            .all()
        )

    def get_links_for_test(
        self,
        repository_id: UUID,
        test_identifier: str,
    ) -> List[TestCoverageLink]:
        """Return all file links covered by a specific test.

        Uses the ``ix_test_coverage_links_repo_test`` composite index.
        """
        return (
            self.db.query(TestCoverageLink)
            .filter(
                and_(
                    TestCoverageLink.repository_id == repository_id,
                    TestCoverageLink.test_identifier == test_identifier,
                )
            )
            .all()
        )

    def get_links_for_repository(
        self,
        repository_id: UUID,
        skip: int = 0,
        limit: int = 500,
    ) -> List[TestCoverageLink]:
        """Return a paginated list of all edges for a repository."""
        return (
            self.db.query(TestCoverageLink)
            .filter(TestCoverageLink.repository_id == repository_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_exact_link(
        self,
        repository_id: UUID,
        test_identifier: str,
        file_path: str,
    ) -> Optional["TestCoverageLink"]:
        """Return the unique edge for a (repository, test, file) triple, or None."""
        return self._get_exact(repository_id, test_identifier, file_path)

    def get_promotable_links(
        self,
        repository_id: UUID,
        min_override_count: int,
    ) -> List["TestCoverageLink"]:
        """Return all MANUAL_OVERRIDE links whose ``override_count`` meets or
        exceeds ``min_override_count``.

        These links represent tests that engineers have repeatedly added
        beyond Veriscope's recommendations and are candidates for promotion
        into future automated recommendations.

        Parameters
        ----------
        repository_id:
            Repository to scope the query.
        min_override_count:
            Minimum number of manual additions required (inclusive).  Pass
            ``1`` to retrieve all links with at least one manual addition.

        Returns
        -------
        List[TestCoverageLink]
            Links ordered by ``override_count`` descending (highest
            confidence engineers signals first).
        """
        return (
            self.db.query(TestCoverageLink)
            .filter(
                and_(
                    TestCoverageLink.repository_id == repository_id,
                    TestCoverageLink.source == "MANUAL_OVERRIDE",
                    TestCoverageLink.override_count >= min_override_count,
                )
            )
            .order_by(TestCoverageLink.override_count.desc())
            .all()
        )

    def get_high_risk_links(
        self,
        repository_id: UUID,
        min_defect_count: int,
    ) -> List["TestCoverageLink"]:
        """Return all ESCAPED_DEFECT links whose ``defect_count`` meets or
        exceeds ``min_defect_count``.

        These are the most dangerous file-test gaps: files that changed in PRs
        where a production defect escaped, and the associated test was NOT run.
        Future recommendations touching these files should include these tests
        more conservatively.

        Parameters
        ----------
        repository_id:
            Repository to scope the query.
        min_defect_count:
            Minimum number of escaped-defect events required (inclusive).  Pass
            ``1`` to retrieve every link with at least one escape event.

        Returns
        -------
        List[TestCoverageLink]
            Links ordered by ``defect_count`` descending (highest-risk gaps
            first).
        """
        return (
            self.db.query(TestCoverageLink)
            .filter(
                and_(
                    TestCoverageLink.repository_id == repository_id,
                    TestCoverageLink.source == "ESCAPED_DEFECT",
                    TestCoverageLink.defect_count >= min_defect_count,
                )
            )
            .order_by(TestCoverageLink.defect_count.desc())
            .all()
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _get_exact(
        self,
        repository_id: UUID,
        test_identifier: str,
        file_path: str,
    ) -> Optional["TestCoverageLink"]:
        return (
            self.db.query(TestCoverageLink)
            .filter(
                and_(
                    TestCoverageLink.repository_id == repository_id,
                    TestCoverageLink.test_identifier == test_identifier,
                    TestCoverageLink.file_path == file_path,
                )
            )
            .first()
        )
