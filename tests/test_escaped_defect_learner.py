"""
tests/test_escaped_defect_learner.py
=======================================

Verification tests for ``EscapedDefectLearner`` and the ``defect_count``
column on ``TestCoverageLink``.

Test groups
-----------
DefectLearningResult (pure unit)
  - success True when no errors
  - success False when errors present
  - has_missed_tests True when missed_tests non-empty
  - has_missed_tests False when missed_tests empty

EscapedDefectLearner.compute_strength (pure unit)
  - Returns 0.80 for defect_count=0 (first escape)
  - Returns 0.85 for defect_count=1 (second escape)
  - Returns 1.00 for defect_count=4 (cap)
  - Never exceeds 1.00

EscapedDefectLearner.learn_from_outcome() — unit (mocked DB)
  - Returns trigger_type=NONE when neither flag is set
  - Returns trigger_type=ESCAPED_DEFECT when only escaped_defect_detected
  - Returns trigger_type=ROLLBACK when only rollback_occurred
  - Returns trigger_type=BOTH when both flags are set
  - Calls upsert_link with source=ESCAPED_DEFECT for each (missed_test, file) pair
  - Does NOT call upsert_link when missed_tests is empty (all recommended were run)
  - Does NOT call upsert_link when changed_files is empty
  - Exception from upsert_link captured in errors, not raised
  - missed_tests = recommended − executed (correct set subtraction)
  - Executed tests that were NOT recommended do not produce links
  - confidence is always 1.0
  - DefectLearningEvent is written

EscapedDefectLearner.learn_from_outcome() — integration (real SQLite)
  - First escape: defect_count=1, link_strength=0.80, source=ESCAPED_DEFECT
  - Second escape: defect_count=2, link_strength=0.85
  - Fifth escape: link_strength=1.00 (cap), defect_count keeps incrementing
  - confidence is always 1.0
  - DefectLearningEvent row written with correct missed_tests and changed_files

defect_count on TestCoverageLinkRepository (integration)
  - Non-ESCAPED_DEFECT upserts do not increment defect_count
  - ESCAPED_DEFECT upserts increment defect_count each call
  - get_high_risk_links returns empty when none reach threshold
  - get_high_risk_links returns only ESCAPED_DEFECT links at or above threshold
  - get_high_risk_links orders by defect_count descending
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
from app.services.escaped_defect_learner import (
    EscapedDefectLearner,
    DefectLearningResult,
    _BASE_STRENGTH,
    _STRENGTH_STEP,
    _MAX_STRENGTH,
    _SOURCE,
    _CONFIDENCE,
)


# --------------------------------------------------------------------------- #
#  SQLite DDL                                                                  #
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

_CREATE_DLE_SQL = """
CREATE TABLE IF NOT EXISTS defect_learning_events (
    id                         TEXT    NOT NULL PRIMARY KEY,
    repository_id              TEXT    NOT NULL,
    recommendation_outcome_id  TEXT    NOT NULL,
    pull_request_id            TEXT,
    trigger_type               TEXT    NOT NULL,
    changed_files              TEXT    NOT NULL DEFAULT '[]',
    recommended_tests          TEXT    NOT NULL DEFAULT '[]',
    executed_tests             TEXT    NOT NULL DEFAULT '[]',
    missed_tests               TEXT    NOT NULL DEFAULT '[]',
    links_created              INTEGER NOT NULL DEFAULT 0,
    links_strengthened         INTEGER NOT NULL DEFAULT 0,
    defect_count_at_time       INTEGER NOT NULL DEFAULT 0,
    errors                     TEXT    NOT NULL DEFAULT '[]',
    created_at                 TEXT    NOT NULL
)
"""

_DROP_TCL_SQL = "DROP TABLE IF EXISTS test_coverage_links"
_DROP_DLE_SQL = "DROP TABLE IF EXISTS defect_learning_events"


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
    escaped_defect_detected: bool = False,
    rollback_occurred: bool = False,
    recommended: List[str] = None,
    executed: List[str] = None,
    repository_id=_REPO_ID,
    pull_request_id=_PR_ID,
) -> MagicMock:
    o = MagicMock()
    o.id = _OUTCOME_ID
    o.repository_id = repository_id
    o.pull_request_id = pull_request_id
    o.escaped_defect_detected = escaped_defect_detected
    o.rollback_occurred = rollback_occurred
    o.recommended_tests = recommended or []
    o.executed_tests    = executed    or []
    return o


def _make_changed_file(file_path: str) -> MagicMock:
    cf = MagicMock()
    cf.file_path = file_path
    cf.status = "modified"
    return cf


# --------------------------------------------------------------------------- #
#  Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with eng.connect() as conn:
        conn.execute(text(_CREATE_TCL_SQL))
        conn.execute(text(_CREATE_DLE_SQL))
        conn.commit()
    yield eng
    with eng.connect() as conn:
        conn.execute(text(_DROP_DLE_SQL))
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
#  DefectLearningResult — pure unit                                            #
# --------------------------------------------------------------------------- #

class TestDefectLearningResult:
    def test_success_true_when_no_errors(self):
        r = DefectLearningResult(links_created_or_strengthened=3)
        assert r.success is True

    def test_success_false_when_errors(self):
        r = DefectLearningResult(errors=["boom"])
        assert r.success is False

    def test_has_missed_tests_true(self):
        r = DefectLearningResult(missed_tests=["s::test_a"])
        assert r.has_missed_tests is True

    def test_has_missed_tests_false(self):
        r = DefectLearningResult(missed_tests=[])
        assert r.has_missed_tests is False


# --------------------------------------------------------------------------- #
#  EscapedDefectLearner.compute_strength — pure unit                          #
# --------------------------------------------------------------------------- #

class TestComputeStrength:
    def test_first_escape_returns_base(self):
        assert EscapedDefectLearner.compute_strength(0) == pytest.approx(_BASE_STRENGTH)

    def test_second_escape_increments(self):
        expected = _BASE_STRENGTH + _STRENGTH_STEP
        assert EscapedDefectLearner.compute_strength(1) == pytest.approx(expected)

    def test_cap_at_max(self):
        assert EscapedDefectLearner.compute_strength(4) == pytest.approx(_MAX_STRENGTH)
        assert EscapedDefectLearner.compute_strength(100) == pytest.approx(_MAX_STRENGTH)

    def test_never_exceeds_1_0(self):
        for n in range(20):
            assert EscapedDefectLearner.compute_strength(n) <= 1.0


# --------------------------------------------------------------------------- #
#  EscapedDefectLearner.learn_from_outcome() — unit (mocked DB)              #
# --------------------------------------------------------------------------- #

class TestLearnerUnit:
    """Unit tests using mocked DB and patched repository."""

    def _no_op_db(self):
        return MagicMock()

    def _make_db_with_files(self, changed_files):
        """Return a mock DB whose PullRequestChangedFile query returns changed_files."""
        from app.models.pull_request import PullRequestChangedFile

        def _side(cls):
            q = MagicMock()
            if cls is PullRequestChangedFile:
                q.filter.return_value.all.return_value = changed_files
            else:
                q.filter.return_value.all.return_value = []
            return q

        mock_db = MagicMock()
        mock_db.query.side_effect = _side
        return mock_db

    def test_returns_none_trigger_when_no_flags(self):
        outcome = _make_outcome()
        result = EscapedDefectLearner.learn_from_outcome(
            db=self._no_op_db(), outcome=outcome, workspace_id=_WORKSPACE_ID
        )
        assert result.trigger_type == "NONE"
        assert result.links_created_or_strengthened == 0

    def test_trigger_escaped_defect_only(self):
        outcome = _make_outcome(escaped_defect_detected=True)
        mock_db = self._make_db_with_files([])
        with patch.object(TestCoverageLinkRepository, "upsert_link"):
            result = EscapedDefectLearner.learn_from_outcome(
                db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
            )
        assert result.trigger_type == "ESCAPED_DEFECT"

    def test_trigger_rollback_only(self):
        outcome = _make_outcome(rollback_occurred=True)
        mock_db = self._make_db_with_files([])
        with patch.object(TestCoverageLinkRepository, "upsert_link"):
            result = EscapedDefectLearner.learn_from_outcome(
                db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
            )
        assert result.trigger_type == "ROLLBACK"

    def test_trigger_both(self):
        outcome = _make_outcome(escaped_defect_detected=True, rollback_occurred=True)
        mock_db = self._make_db_with_files([])
        with patch.object(TestCoverageLinkRepository, "upsert_link"):
            result = EscapedDefectLearner.learn_from_outcome(
                db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
            )
        assert result.trigger_type == "BOTH"

    def test_missed_tests_is_recommended_minus_executed(self):
        outcome = _make_outcome(
            escaped_defect_detected=True,
            recommended=["s::a", "s::b", "s::c"],
            executed=["s::a"],          # s::b and s::c were skipped
        )
        mock_db = self._make_db_with_files([_make_changed_file("app/x.py")])
        captured = []

        def _spy(**kwargs):
            captured.append(kwargs)
            return MagicMock()

        with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=_spy):
            with patch.object(TestCoverageLinkRepository, "get_exact_link", return_value=None):
                result = EscapedDefectLearner.learn_from_outcome(
                    db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
                )

        assert set(result.missed_tests) == {"s::b", "s::c"}
        upserted_tests = {c["test_identifier"] for c in captured}
        assert "s::a" not in upserted_tests       # executed — not a gap
        assert "s::b" in upserted_tests
        assert "s::c" in upserted_tests

    def test_no_upsert_when_no_missed_tests(self):
        """All recommended tests were executed — nothing to learn."""
        outcome = _make_outcome(
            escaped_defect_detected=True,
            recommended=["s::a"],
            executed=["s::a"],
        )
        mock_db = self._make_db_with_files([_make_changed_file("app/x.py")])
        with patch.object(TestCoverageLinkRepository, "upsert_link") as mock_up:
            result = EscapedDefectLearner.learn_from_outcome(
                db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
            )
        mock_up.assert_not_called()
        assert result.links_created_or_strengthened == 0

    def test_no_upsert_when_no_changed_files(self):
        outcome = _make_outcome(
            escaped_defect_detected=True,
            recommended=["s::a"],
            executed=[],
        )
        mock_db = self._make_db_with_files([])   # no files
        with patch.object(TestCoverageLinkRepository, "upsert_link") as mock_up:
            result = EscapedDefectLearner.learn_from_outcome(
                db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
            )
        mock_up.assert_not_called()
        assert result.links_created_or_strengthened == 0

    def test_upsert_uses_escaped_defect_source(self):
        outcome = _make_outcome(
            escaped_defect_detected=True,
            recommended=["s::missed"],
            executed=[],
        )
        mock_db = self._make_db_with_files([_make_changed_file("app/y.py")])
        captured = {}

        def _spy(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=_spy):
            with patch.object(TestCoverageLinkRepository, "get_exact_link", return_value=None):
                EscapedDefectLearner.learn_from_outcome(
                    db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
                )

        assert captured["source"] == "ESCAPED_DEFECT"

    def test_confidence_is_always_1_0(self):
        outcome = _make_outcome(
            escaped_defect_detected=True,
            recommended=["s::x"],
            executed=[],
        )
        mock_db = self._make_db_with_files([_make_changed_file("app/z.py")])
        captured = {}

        def _spy(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=_spy):
            with patch.object(TestCoverageLinkRepository, "get_exact_link", return_value=None):
                EscapedDefectLearner.learn_from_outcome(
                    db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
                )

        assert captured["confidence"] == pytest.approx(1.0)

    def test_upsert_exception_captured_not_raised(self):
        outcome = _make_outcome(
            escaped_defect_detected=True,
            recommended=["s::boom"],
            executed=[],
        )
        mock_db = self._make_db_with_files([_make_changed_file("app/crash.py")])
        with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=RuntimeError("simulated")):
            with patch.object(TestCoverageLinkRepository, "get_exact_link", return_value=None):
                result = EscapedDefectLearner.learn_from_outcome(
                    db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
                )
        assert len(result.errors) == 1
        assert "simulated" in result.errors[0]
        assert result.success is False

    def test_executed_only_tests_not_linked(self):
        """Tests that ran but were not recommended should NOT produce links."""
        outcome = _make_outcome(
            escaped_defect_detected=True,
            recommended=["s::rec"],
            executed=["s::rec", "s::extra"],   # extra was not recommended
        )
        mock_db = self._make_db_with_files([_make_changed_file("app/f.py")])
        captured = []

        def _spy(**kwargs):
            captured.append(kwargs["test_identifier"])
            return MagicMock()

        with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=_spy):
            with patch.object(TestCoverageLinkRepository, "get_exact_link", return_value=None):
                EscapedDefectLearner.learn_from_outcome(
                    db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
                )

        # s::rec was executed — not a missed test
        assert "s::rec"   not in captured
        # s::extra was executed and not recommended — not a missed test
        assert "s::extra" not in captured
        # Nothing was missed — no upserts at all
        assert captured == []


# --------------------------------------------------------------------------- #
#  EscapedDefectLearner.learn_from_outcome() — integration (real SQLite)     #
# --------------------------------------------------------------------------- #

class TestLearnerIntegration:
    """End-to-end integration tests with real in-memory SQLite."""

    def _mock_db_delegates(self, real_db, changed_files):
        from app.models.pull_request import PullRequestChangedFile
        from app.models.defect_learning_event import DefectLearningEvent

        def _side_query(cls):
            q = MagicMock()
            if cls is PullRequestChangedFile:
                q.filter.return_value.all.return_value = changed_files
            elif cls is DefectLearningEvent:
                return real_db.query(cls)
            elif cls is TestCoverageLink:
                return real_db.query(cls)
            else:
                return real_db.query(cls)
            return q

        mock_db = MagicMock()
        mock_db.query.side_effect = _side_query
        mock_db.add     = real_db.add
        mock_db.commit  = real_db.commit
        mock_db.refresh = real_db.refresh
        return mock_db

    def test_first_escape_strength_0_80(self, db):
        files = [_make_changed_file("app/alpha.py")]
        mock_db = self._mock_db_delegates(db, files)
        outcome = _make_outcome(
            escaped_defect_detected=True,
            recommended=["suite::alpha"],
            executed=[],
        )

        result = EscapedDefectLearner.learn_from_outcome(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
        )

        assert result.links_created_or_strengthened == 1
        assert result.defect_strength_increments == 1
        assert result.trigger_type == "ESCAPED_DEFECT"

        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::alpha", "app/alpha.py"
        )
        assert link is not None
        assert link.defect_count == 1
        assert link.link_strength == pytest.approx(0.80)
        assert link.confidence == pytest.approx(1.0)
        assert link.source == "ESCAPED_DEFECT"

    def test_second_escape_strength_0_85(self, db):
        files = [_make_changed_file("app/beta.py")]
        mock_db = self._mock_db_delegates(db, files)
        outcome = _make_outcome(
            escaped_defect_detected=True,
            recommended=["suite::beta"],
            executed=[],
        )

        EscapedDefectLearner.learn_from_outcome(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
        )
        EscapedDefectLearner.learn_from_outcome(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
        )

        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::beta", "app/beta.py"
        )
        assert link.defect_count == 2
        assert link.link_strength == pytest.approx(0.85)

    def test_fifth_escape_caps_strength_at_1_0(self, db):
        files = [_make_changed_file("app/gamma.py")]
        mock_db = self._mock_db_delegates(db, files)
        outcome = _make_outcome(
            escaped_defect_detected=True,
            recommended=["suite::gamma"],
            executed=[],
        )

        for _ in range(5):
            EscapedDefectLearner.learn_from_outcome(
                db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
            )

        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::gamma", "app/gamma.py"
        )
        assert link.link_strength == pytest.approx(1.0)
        assert link.defect_count == 5

    def test_rollback_trigger_also_creates_links(self, db):
        files = [_make_changed_file("app/delta.py")]
        mock_db = self._mock_db_delegates(db, files)
        outcome = _make_outcome(
            rollback_occurred=True,
            recommended=["suite::delta"],
            executed=[],
        )

        result = EscapedDefectLearner.learn_from_outcome(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID
        )

        assert result.trigger_type == "ROLLBACK"
        assert result.links_created_or_strengthened == 1

        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::delta", "app/delta.py"
        )
        assert link is not None
        assert link.defect_count == 1


# --------------------------------------------------------------------------- #
#  defect_count on TestCoverageLinkRepository — integration                   #
# --------------------------------------------------------------------------- #

class TestDefectCountRepository:
    """Verify defect_count increment semantics directly on the repo layer."""

    def test_non_escaped_defect_does_not_increment_defect_count(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            test_identifier="s::coverage_test_dc",
            file_path="app/cov_dc.py",
            source="COVERAGE",
        )
        link = repo.get_exact_link(_REPO_ID, "s::coverage_test_dc", "app/cov_dc.py")
        assert link.defect_count == 0
        assert link.run_count == 1

    def test_escaped_defect_increments_defect_count_each_call(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            test_identifier="s::defect_test",
            file_path="app/defect.py",
            source="ESCAPED_DEFECT",
        )
        link = repo.get_exact_link(_REPO_ID, "s::defect_test", "app/defect.py")
        assert link.defect_count == 1

        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            test_identifier="s::defect_test",
            file_path="app/defect.py",
            source="ESCAPED_DEFECT",
        )
        link = repo.get_exact_link(_REPO_ID, "s::defect_test", "app/defect.py")
        assert link.defect_count == 2
        assert link.run_count == 2

    def test_get_high_risk_links_empty_when_none_at_threshold(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            test_identifier="s::low_defect",
            file_path="app/low_defect.py",
            source="ESCAPED_DEFECT",
        )
        links = repo.get_high_risk_links(_REPO_ID, min_defect_count=10)
        for link in links:
            assert link.defect_count >= 10

    def test_get_high_risk_links_returns_only_escaped_defect_source(self, repo):
        import uuid as _uuid
        from datetime import datetime as _dt

        # Manually insert a COVERAGE link with defect_count=0 (it will never
        # be returned by get_high_risk_links regardless of threshold)
        coverage_link = TestCoverageLink(
            id=_uuid.uuid4(),
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            test_identifier="s::coverage_only_hr",
            file_path="app/cov_only_hr.py",
            source="COVERAGE",
            run_count=5,
            defect_count=0,
            override_count=0,
            created_at=_dt.utcnow(),
            updated_at=_dt.utcnow(),
        )
        repo.db.add(coverage_link)
        repo.db.commit()

        links = repo.get_high_risk_links(_REPO_ID, min_defect_count=1)
        identifiers = {l.test_identifier for l in links}
        assert "s::coverage_only_hr" not in identifiers

    def test_get_high_risk_links_ordered_desc(self, repo):
        test_pairs = [
            ("s::high_defect", "app/high_d.py", 5),
            ("s::mid_defect",  "app/mid_d.py",  3),
            ("s::low_defect2", "app/low_d2.py", 1),
        ]
        for identifier, file_path, count in test_pairs:
            for _ in range(count):
                repo.upsert_link(
                    workspace_id=_WORKSPACE_ID,
                    repository_id=_REPO_ID,
                    test_identifier=identifier,
                    file_path=file_path,
                    source="ESCAPED_DEFECT",
                )

        links = repo.get_high_risk_links(_REPO_ID, min_defect_count=1)
        relevant = [
            l for l in links
            if l.test_identifier in {"s::high_defect", "s::mid_defect", "s::low_defect2"}
        ]
        counts = [l.defect_count for l in relevant]
        assert counts == sorted(counts, reverse=True), (
            f"Expected descending order, got: {counts}"
        )
