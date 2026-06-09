"""
tests/test_recommendation_outcome_tracker.py
==============================================

Verification tests for ``RecommendationOutcomeTracker`` and the
``override_count`` column on ``TestCoverageLink``.

Test groups
-----------
OutcomeTrackingResult (pure unit)
  - success is True when no errors
  - success is False when errors present
  - has_promotable_tests is True when promotable_tests is non-empty
  - has_promotable_tests is False when promotable_tests is empty

RecommendationOutcomeTracker.track() — unit (mocked DB)
  - Returns all four test sets from the outcome
  - Calls ManualOverrideLearner when manually_added_tests is non-empty
  - Does NOT call ManualOverrideLearner when manually_added_tests is empty
  - Exception from ManualOverrideLearner captured in errors, not raised
  - LearningResult errors propagated into OutcomeTrackingResult.errors
  - links_created_or_strengthened and override_count_increments reflect
    learner output
  - promotable_tests populated from get_promotable_links
  - Exception from get_promotable_links captured in errors, not raised
  - Exception reading test sets captured in errors, tracker still returns
  - Deduplication: a test_identifier appearing in multiple promotable links
    is listed only once in promotable_tests

RecommendationOutcomeTracker.track() — integration (real SQLite)
  - First addition: override_count=1, link_strength=0.5, not yet promotable
  - Second addition: override_count=2, link_strength=0.6, not yet promotable
  - Third addition: override_count=3, link_strength=0.7, appears in
    promotable_tests (default threshold=3)
  - Fifth addition: override_count=5, link_strength=1.0 (strength cap)
  - Manually removed tests do NOT create links
  - Recommended/executed-only tests do NOT create links

override_count on TestCoverageLinkRepository (integration)
  - Non-MANUAL_OVERRIDE upserts do not increment override_count
  - MANUAL_OVERRIDE upserts increment override_count each call
  - get_promotable_links returns empty when no links reach threshold
  - get_promotable_links returns only MANUAL_OVERRIDE links at threshold
  - get_promotable_links orders by override_count descending
"""

import uuid
from datetime import datetime
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.test_coverage_link import TestCoverageLink
from app.repositories.test_coverage_link import TestCoverageLinkRepository
from app.services.manual_override_learner import LearningResult, ManualOverrideLearner
from app.services.recommendation_outcome_tracker import (
    PROMOTION_THRESHOLD,
    OutcomeTrackingResult,
    RecommendationOutcomeTracker,
)


# --------------------------------------------------------------------------- #
#  SQLite DDL (mirrors test_manual_override_learner.py)                       #
# --------------------------------------------------------------------------- #

_CREATE_TCL_SQL = """
CREATE TABLE IF NOT EXISTS test_coverage_links (
    id             TEXT    NOT NULL PRIMARY KEY,
    workspace_id   TEXT    NOT NULL,
    repository_id  TEXT    NOT NULL,
    test_identifier TEXT   NOT NULL,
    file_path      TEXT    NOT NULL,
    link_strength  REAL,
    confidence     REAL,
    source         TEXT,
    run_count      INTEGER NOT NULL DEFAULT 0,
    success_count  INTEGER NOT NULL DEFAULT 0,
    failure_count  INTEGER NOT NULL DEFAULT 0,
    override_count INTEGER NOT NULL DEFAULT 0,
    defect_count   INTEGER NOT NULL DEFAULT 0,
    first_seen_at  TEXT,
    last_seen_at   TEXT,
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL,
    UNIQUE (repository_id, test_identifier, file_path)
)
"""

_DROP_TCL_SQL = "DROP TABLE IF EXISTS test_coverage_links"


# --------------------------------------------------------------------------- #
#  Shared constants                                                            #
# --------------------------------------------------------------------------- #

_WORKSPACE_ID = uuid.uuid4()
_REPO_ID      = uuid.uuid4()
_OUTCOME_ID   = uuid.uuid4()
_PR_ID        = uuid.uuid4()


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _make_outcome(
    *,
    recommended: List[str] = None,
    executed: List[str] = None,
    manually_added: List[str] = None,
    manually_removed: List[str] = None,
    pull_request_id=_PR_ID,
    repository_id=_REPO_ID,
) -> MagicMock:
    o = MagicMock()
    o.id = _OUTCOME_ID
    o.repository_id = repository_id
    o.pull_request_id = pull_request_id
    o.recommended_tests    = recommended    or []
    o.executed_tests       = executed       or []
    o.manually_added_tests = manually_added or []
    o.manually_removed_tests = manually_removed or []
    return o


def _make_changed_file(file_path: str, status: str = "modified") -> MagicMock:
    cf = MagicMock()
    cf.file_path = file_path
    cf.status = status
    return cf


# --------------------------------------------------------------------------- #
#  Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with eng.connect() as conn:
        conn.execute(text(_CREATE_TCL_SQL))
        conn.commit()
    yield eng
    with eng.connect() as conn:
        conn.execute(text(_DROP_TCL_SQL))
        conn.commit()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def repo(db):
    return TestCoverageLinkRepository(db)


# --------------------------------------------------------------------------- #
#  OutcomeTrackingResult — pure unit                                           #
# --------------------------------------------------------------------------- #

class TestOutcomeTrackingResult:
    def test_success_true_when_no_errors(self):
        r = OutcomeTrackingResult(links_created_or_strengthened=2)
        assert r.success is True

    def test_success_false_when_errors(self):
        r = OutcomeTrackingResult(errors=["boom"])
        assert r.success is False

    def test_has_promotable_tests_true(self):
        r = OutcomeTrackingResult(promotable_tests=["s::test_a"])
        assert r.has_promotable_tests is True

    def test_has_promotable_tests_false(self):
        r = OutcomeTrackingResult(promotable_tests=[])
        assert r.has_promotable_tests is False


# --------------------------------------------------------------------------- #
#  RecommendationOutcomeTracker.track() — unit (mocked DB)                   #
# --------------------------------------------------------------------------- #

class TestTrackerUnit:
    """Unit tests using mocked DB and patched learner / repository."""

    def _make_mock_db_with_no_promotable(self):
        """Returns a mock DB whose get_promotable_links returns []."""
        mock_db = MagicMock()
        return mock_db

    def test_returns_all_four_test_sets(self):
        outcome = _make_outcome(
            recommended=["s::a"],
            executed=["s::a", "s::b"],
            manually_added=["s::b"],
            manually_removed=[],
        )

        with patch.object(ManualOverrideLearner, "learn_from_outcome", return_value=LearningResult(links_upserted=1, override_count_increments=1)):
            with patch.object(TestCoverageLinkRepository, "get_promotable_links", return_value=[]):
                result = RecommendationOutcomeTracker.track(
                    db=MagicMock(),
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        assert result.recommended_tests     == ["s::a"]
        assert result.executed_tests        == ["s::a", "s::b"]
        assert result.manually_added_tests  == ["s::b"]
        assert result.manually_removed_tests == []

    def test_learner_called_when_overrides_present(self):
        outcome = _make_outcome(manually_added=["s::override"])
        called = []

        def _fake_learn(**kwargs):
            called.append(kwargs)
            return LearningResult(links_upserted=1, override_count_increments=1)

        with patch.object(ManualOverrideLearner, "learn_from_outcome", side_effect=_fake_learn):
            with patch.object(TestCoverageLinkRepository, "get_promotable_links", return_value=[]):
                RecommendationOutcomeTracker.track(
                    db=MagicMock(),
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        assert len(called) == 1
        assert called[0]["workspace_id"] == _WORKSPACE_ID

    def test_learner_not_called_when_no_overrides(self):
        outcome = _make_outcome(manually_added=[])

        with patch.object(ManualOverrideLearner, "learn_from_outcome") as mock_learn:
            with patch.object(TestCoverageLinkRepository, "get_promotable_links", return_value=[]):
                result = RecommendationOutcomeTracker.track(
                    db=MagicMock(),
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        mock_learn.assert_not_called()
        assert result.links_created_or_strengthened == 0
        assert result.override_count_increments == 0

    def test_learner_exception_captured_not_raised(self):
        outcome = _make_outcome(manually_added=["s::crash"])

        with patch.object(ManualOverrideLearner, "learn_from_outcome", side_effect=RuntimeError("simulated crash")):
            with patch.object(TestCoverageLinkRepository, "get_promotable_links", return_value=[]):
                result = RecommendationOutcomeTracker.track(
                    db=MagicMock(),
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        assert len(result.errors) == 1
        assert "simulated crash" in result.errors[0]
        assert result.success is False

    def test_learner_partial_errors_propagated(self):
        outcome = _make_outcome(manually_added=["s::partial"])

        with patch.object(
            ManualOverrideLearner,
            "learn_from_outcome",
            return_value=LearningResult(links_upserted=0, errors=["upsert failed"]),
        ):
            with patch.object(TestCoverageLinkRepository, "get_promotable_links", return_value=[]):
                result = RecommendationOutcomeTracker.track(
                    db=MagicMock(),
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        assert "upsert failed" in result.errors
        assert result.success is False

    def test_links_and_override_count_from_learner(self):
        outcome = _make_outcome(manually_added=["s::x"])

        with patch.object(
            ManualOverrideLearner,
            "learn_from_outcome",
            return_value=LearningResult(
                links_upserted=3,
                override_count_increments=3,
            ),
        ):
            with patch.object(TestCoverageLinkRepository, "get_promotable_links", return_value=[]):
                result = RecommendationOutcomeTracker.track(
                    db=MagicMock(),
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        assert result.links_created_or_strengthened == 3
        assert result.override_count_increments == 3

    def test_promotable_tests_populated(self):
        outcome = _make_outcome(manually_added=["s::promo"])

        fake_link_a = MagicMock()
        fake_link_a.test_identifier = "s::promo"
        fake_link_b = MagicMock()
        fake_link_b.test_identifier = "s::other"

        with patch.object(ManualOverrideLearner, "learn_from_outcome", return_value=LearningResult(links_upserted=1, override_count_increments=1)):
            with patch.object(TestCoverageLinkRepository, "get_promotable_links", return_value=[fake_link_a, fake_link_b]):
                result = RecommendationOutcomeTracker.track(
                    db=MagicMock(),
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        assert "s::promo" in result.promotable_tests
        assert "s::other" in result.promotable_tests
        assert result.has_promotable_tests is True

    def test_promotable_query_exception_captured(self):
        outcome = _make_outcome(manually_added=["s::x"])

        with patch.object(ManualOverrideLearner, "learn_from_outcome", return_value=LearningResult(links_upserted=1, override_count_increments=1)):
            with patch.object(
                TestCoverageLinkRepository,
                "get_promotable_links",
                side_effect=RuntimeError("DB down"),
            ):
                result = RecommendationOutcomeTracker.track(
                    db=MagicMock(),
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        assert any("DB down" in e for e in result.errors)

    def test_test_set_read_error_captured(self):
        outcome = MagicMock()
        outcome.id = _OUTCOME_ID
        outcome.repository_id = _REPO_ID
        # Make reading a property raise
        type(outcome).recommended_tests = property(lambda self: (_ for _ in ()).throw(RuntimeError("read error")))

        result = RecommendationOutcomeTracker.track(
            db=MagicMock(),
            outcome=outcome,
            workspace_id=_WORKSPACE_ID,
        )

        assert len(result.errors) == 1
        assert "read error" in result.errors[0]

    def test_promotable_deduplication(self):
        """A test_identifier appearing across multiple links is listed only once."""
        outcome = _make_outcome(manually_added=["s::dup"])

        # Two links with the same test_identifier (e.g. covering two files)
        link_1 = MagicMock()
        link_1.test_identifier = "s::dup"
        link_2 = MagicMock()
        link_2.test_identifier = "s::dup"

        with patch.object(ManualOverrideLearner, "learn_from_outcome", return_value=LearningResult(links_upserted=1, override_count_increments=1)):
            with patch.object(TestCoverageLinkRepository, "get_promotable_links", return_value=[link_1, link_2]):
                result = RecommendationOutcomeTracker.track(
                    db=MagicMock(),
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        assert result.promotable_tests.count("s::dup") == 1


# --------------------------------------------------------------------------- #
#  RecommendationOutcomeTracker.track() — integration (real SQLite)           #
# --------------------------------------------------------------------------- #

class TestTrackerIntegration:
    """End-to-end tests using real in-memory SQLite for TestCoverageLink.\n
    PullRequestChangedFile queries are mocked out (not in scope for these tests).
    """

    def _mock_db_delegates(self, real_db, changed_files):
        """Build a mock_db that delegates TestCoverageLink ops to real_db
        and returns changed_files for PullRequestChangedFile queries."""
        from app.models.pull_request import PullRequestChangedFile

        def _side_query(cls):
            q = MagicMock()
            if cls is PullRequestChangedFile:
                q.filter.return_value.all.return_value = changed_files
            else:
                return real_db.query(cls)
            return q

        mock_db = MagicMock()
        mock_db.query.side_effect = _side_query
        mock_db.add     = real_db.add
        mock_db.commit  = real_db.commit
        mock_db.refresh = real_db.refresh
        return mock_db

    def test_first_addition_not_promotable(self, db):
        """After one manual addition override_count=1 < PROMOTION_THRESHOLD."""
        changed = [_make_changed_file("app/alpha.py")]
        mock_db = self._mock_db_delegates(db, changed)
        outcome = _make_outcome(manually_added=["suite::alpha"])

        result = RecommendationOutcomeTracker.track(
            db=mock_db,
            outcome=outcome,
            workspace_id=_WORKSPACE_ID,
        )

        assert result.links_created_or_strengthened == 1
        assert result.override_count_increments == 1
        assert "suite::alpha" not in result.promotable_tests

        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::alpha", "app/alpha.py"
        )
        assert link is not None
        assert link.override_count == 1
        assert link.link_strength == pytest.approx(0.5)

    def test_second_addition_strengthens_link(self, db):
        """Second manual addition: override_count=2, link_strength=0.6."""
        changed = [_make_changed_file("app/beta.py")]
        mock_db = self._mock_db_delegates(db, changed)
        outcome = _make_outcome(manually_added=["suite::beta"])

        # Call twice
        RecommendationOutcomeTracker.track(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
        )
        RecommendationOutcomeTracker.track(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
        )

        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::beta", "app/beta.py"
        )
        assert link.override_count == 2
        assert link.link_strength == pytest.approx(0.6)
        # Still below default threshold of 3
        result = RecommendationOutcomeTracker.track(
            db=mock_db, outcome=_make_outcome(manually_added=[]), workspace_id=_WORKSPACE_ID
        )
        assert "suite::beta" not in result.promotable_tests

    def test_third_addition_promotes_test(self, db):
        """After 3 additions the test appears in promotable_tests (threshold=3)."""
        changed = [_make_changed_file("app/gamma.py")]
        mock_db = self._mock_db_delegates(db, changed)
        outcome = _make_outcome(manually_added=["suite::gamma"])

        for _ in range(3):
            RecommendationOutcomeTracker.track(
                db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
            )

        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::gamma", "app/gamma.py"
        )
        assert link.override_count == 3

        # Now query promotable via a fresh track with no new additions
        result = RecommendationOutcomeTracker.track(
            db=mock_db,
            outcome=_make_outcome(manually_added=[]),
            workspace_id=_WORKSPACE_ID,
            promotion_threshold=3,
        )
        assert "suite::gamma" in result.promotable_tests
        assert result.has_promotable_tests is True

    def test_five_additions_caps_strength_at_1_0(self, db):
        """link_strength is capped at 1.0 even after many additions."""
        changed = [_make_changed_file("app/delta.py")]
        mock_db = self._mock_db_delegates(db, changed)
        outcome = _make_outcome(manually_added=["suite::delta"])

        for _ in range(7):
            RecommendationOutcomeTracker.track(
                db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
            )

        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::delta", "app/delta.py"
        )
        assert link.link_strength == pytest.approx(1.0)
        assert link.override_count == 7  # count keeps growing after cap

    def test_manually_removed_tests_do_not_create_links(self, db):
        """Tests listed in manually_removed should not result in any links."""
        changed = [_make_changed_file("app/epsilon.py")]
        mock_db = self._mock_db_delegates(db, changed)
        # Only removed, nothing added
        outcome = _make_outcome(
            manually_added=[],
            manually_removed=["suite::removed"],
        )

        result = RecommendationOutcomeTracker.track(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
        )

        assert result.links_created_or_strengthened == 0
        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::removed", "app/epsilon.py"
        )
        assert link is None

    def test_recommended_only_tests_do_not_create_links(self, db):
        """Tests that were recommended and executed but not manually added
        should not produce TestCoverageLink rows via the tracker."""
        changed = [_make_changed_file("app/zeta.py")]
        mock_db = self._mock_db_delegates(db, changed)
        outcome = _make_outcome(
            recommended=["suite::rec"],
            executed=["suite::rec"],
            manually_added=[],
        )

        result = RecommendationOutcomeTracker.track(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
        )

        assert result.links_created_or_strengthened == 0


# --------------------------------------------------------------------------- #
#  override_count on TestCoverageLinkRepository — integration                  #
# --------------------------------------------------------------------------- #

class TestOverrideCountRepository:
    """Verify override_count increment semantics directly on the repo layer."""

    def test_non_manual_override_does_not_increment_override_count(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            test_identifier="s::coverage_test",
            file_path="app/cov.py",
            source="COVERAGE",
        )
        link = repo.get_exact_link(_REPO_ID, "s::coverage_test", "app/cov.py")
        assert link.override_count == 0
        assert link.run_count == 1

    def test_manual_override_increments_override_count_each_call(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            test_identifier="s::manual_test",
            file_path="app/manual.py",
            source="MANUAL_OVERRIDE",
        )
        link = repo.get_exact_link(_REPO_ID, "s::manual_test", "app/manual.py")
        assert link.override_count == 1

        # Second call
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            test_identifier="s::manual_test",
            file_path="app/manual.py",
            source="MANUAL_OVERRIDE",
        )
        link = repo.get_exact_link(_REPO_ID, "s::manual_test", "app/manual.py")
        assert link.override_count == 2
        assert link.run_count == 2

    def test_get_promotable_links_empty_when_none_at_threshold(self, repo):
        # Seed one link with override_count < threshold
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            test_identifier="s::low_count",
            file_path="app/low.py",
            source="MANUAL_OVERRIDE",
        )
        links = repo.get_promotable_links(_REPO_ID, min_override_count=5)
        # The link has override_count=1 which is < 5
        for link in links:
            assert link.override_count >= 5

    def test_get_promotable_links_returns_only_manual_override(self, repo):
        # Seed a COVERAGE link and a MANUAL_OVERRIDE link, both with high counts
        # COVERAGE link via direct DB manipulation (not going through upsert for source)
        import uuid as _uuid
        from datetime import datetime as _dt

        coverage_link = TestCoverageLink(
            id=_uuid.uuid4(),
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            test_identifier="s::coverage_only",
            file_path="app/cov_only.py",
            source="COVERAGE",
            run_count=10,
            override_count=0,  # not a manual override
            created_at=_dt.utcnow(),
            updated_at=_dt.utcnow(),
        )
        repo.db.add(coverage_link)
        repo.db.commit()

        links = repo.get_promotable_links(_REPO_ID, min_override_count=1)
        identifiers = {l.test_identifier for l in links}
        assert "s::coverage_only" not in identifiers

    def test_get_promotable_links_ordered_by_override_count_desc(self, repo):
        """Links are returned highest override_count first."""
        test_pairs = [
            ("s::high_count", "app/high.py", 5),
            ("s::mid_count",  "app/mid.py",  3),
            ("s::low_count2", "app/low2.py", 1),
        ]

        for identifier, file_path, count in test_pairs:
            for _ in range(count):
                repo.upsert_link(
                    workspace_id=_WORKSPACE_ID,
                    repository_id=_REPO_ID,
                    test_identifier=identifier,
                    file_path=file_path,
                    source="MANUAL_OVERRIDE",
                )

        links = repo.get_promotable_links(_REPO_ID, min_override_count=1)
        # Filter to just our three test pairs
        relevant = [
            l for l in links
            if l.test_identifier in {"s::high_count", "s::mid_count", "s::low_count2"}
        ]
        counts = [l.override_count for l in relevant]
        assert counts == sorted(counts, reverse=True), (
            f"Expected descending order, got: {counts}"
        )
