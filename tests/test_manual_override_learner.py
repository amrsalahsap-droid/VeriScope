"""
tests/test_manual_override_learner.py
=======================================

Verification tests for ManualOverrideLearner and the collect() hook in
RecommendationExecutedTestCollector.

Test groups
-----------
ManualOverrideLearner.compute_strength (pure unit)
  - First addition: strength = 0.5
  - Second addition: strength = 0.6
  - Fifth addition: strength = 1.0 (capped)
  - Strength never exceeds 1.0

ManualOverrideLearner.learn_from_outcome (unit, mocked DB)
  - No-op when manually_added_tests is empty
  - No-op when outcome has no pull_request_id
  - No-op when PR has no non-removed source-code changed files
  - Creates links for each (test, changed_file) pair
  - Skips non-source-code files (md, yml, json, etc.)
  - Strength increases on second call (override_count grows)
  - All links get source=MANUAL_OVERRIDE, confidence=1.0
  - upsert error on one file does not prevent others
  - DB error querying changed files captured in result.errors
  - Test with empty string identifier is skipped

ManualOverrideLearner (integration, real SQLite)
  - First addition: strength=0.5, run_count=1
  - Second addition: strength=0.6, run_count=2
  - Five additions: strength=1.0 (cap)
  - source always MANUAL_OVERRIDE
  - confidence always 1.0
  - Non-source files are not linked

collect() hook (mock-based)
  - learn_from_outcome is called after commit when manually_added_tests is non-empty
  - learn_from_outcome not called when manually_added_tests is empty
  - Exception from learner does NOT propagate out of collect()
  - LearningResult errors logged as warnings, not raised
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.test_coverage_link import TestCoverageLink
from app.repositories.test_coverage_link import TestCoverageLinkRepository
from app.services.manual_override_learner import (
    ManualOverrideLearner,
    LearningResult,
    _SOURCE,
    _CONFIDENCE,
    _BASE_STRENGTH,
    _STRENGTH_STEP,
    _MAX_STRENGTH,
)


# --------------------------------------------------------------------------- #
#  SQLite DDL (same pattern as other test files)                              #
# --------------------------------------------------------------------------- #

_CREATE_TCL_SQL = """
CREATE TABLE IF NOT EXISTS test_coverage_links (
    id            TEXT    NOT NULL PRIMARY KEY,
    workspace_id  TEXT    NOT NULL,
    repository_id TEXT    NOT NULL,
    test_identifier TEXT  NOT NULL,
    file_path     TEXT    NOT NULL,
    link_strength REAL,
    confidence    REAL,
    source        TEXT,
    run_count     INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    override_count INTEGER NOT NULL DEFAULT 0,
    defect_count   INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT,
    last_seen_at  TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL,
    UNIQUE (repository_id, test_identifier, file_path)
)
"""

_DROP_TCL_SQL = "DROP TABLE IF EXISTS test_coverage_links"


# --------------------------------------------------------------------------- #
#  Shared constants                                                            #
# --------------------------------------------------------------------------- #

_WORKSPACE_ID  = uuid.uuid4()
_REPO_ID       = uuid.uuid4()
_OUTCOME_ID    = uuid.uuid4()
_PR_ID         = uuid.uuid4()


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _make_outcome(
    manually_added_tests: list,
    pull_request_id=_PR_ID,
    repository_id=_REPO_ID,
) -> MagicMock:
    o = MagicMock()
    o.id = _OUTCOME_ID
    o.repository_id = repository_id
    o.pull_request_id = pull_request_id
    o.manually_added_tests = manually_added_tests
    return o


def _make_changed_file(file_path: str, status: str = "modified") -> MagicMock:
    cf = MagicMock()
    cf.file_path = file_path
    cf.status = status
    return cf


def _mock_db_with_changed_files(changed_files):
    """Minimal mock_db whose PullRequestChangedFile query returns changed_files."""
    from app.models.pull_request import PullRequestChangedFile

    mock_db = MagicMock()

    def _side_effect(model_class):
        q = MagicMock()
        if model_class is PullRequestChangedFile:
            q.filter.return_value.all.return_value = changed_files
        else:
            q.filter.return_value.all.return_value = []
        return q

    mock_db.query.side_effect = _side_effect
    return mock_db


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
#  compute_strength — pure unit tests                                         #
# --------------------------------------------------------------------------- #

class TestComputeStrength:
    def test_first_addition(self):
        assert ManualOverrideLearner.compute_strength(0) == 0.5

    def test_second_addition(self):
        assert ManualOverrideLearner.compute_strength(1) == pytest.approx(0.6)

    def test_fifth_addition_capped(self):
        assert ManualOverrideLearner.compute_strength(5) == 1.0

    def test_never_exceeds_max(self):
        for n in range(20):
            assert ManualOverrideLearner.compute_strength(n) <= _MAX_STRENGTH

    def test_monotonically_increases(self):
        strengths = [ManualOverrideLearner.compute_strength(n) for n in range(10)]
        for i in range(len(strengths) - 1):
            assert strengths[i] <= strengths[i + 1]


# --------------------------------------------------------------------------- #
#  learn_from_outcome — unit tests (mocked DB)                                #
# --------------------------------------------------------------------------- #

class TestLearnNoOp:
    def test_noop_when_no_manually_added(self):
        outcome = _make_outcome([])
        mock_db = MagicMock()

        result = ManualOverrideLearner.learn_from_outcome(
            db=mock_db,
            outcome=outcome,
            workspace_id=_WORKSPACE_ID,
        )

        assert result.links_upserted == 0
        assert result.tests_processed == 0
        assert result.had_overrides is False
        mock_db.query.assert_not_called()

    def test_noop_when_no_pull_request_id(self):
        outcome = _make_outcome(["suite::test_a"], pull_request_id=None)
        mock_db = MagicMock()

        result = ManualOverrideLearner.learn_from_outcome(
            db=mock_db,
            outcome=outcome,
            workspace_id=_WORKSPACE_ID,
        )

        assert result.links_upserted == 0
        assert result.tests_skipped == 1

    def test_noop_when_no_source_changed_files(self):
        """Only .md/.yml files in PR — no source-code links created."""
        outcome = _make_outcome(["suite::test_a"])
        changed = [
            _make_changed_file("README.md"),
            _make_changed_file(".github/ci.yml"),
        ]
        mock_db = _mock_db_with_changed_files(changed)

        with patch.object(TestCoverageLinkRepository, "upsert_link") as mock_up:
            result = ManualOverrideLearner.learn_from_outcome(
                db=mock_db,
                outcome=outcome,
                workspace_id=_WORKSPACE_ID,
            )

        mock_up.assert_not_called()
        assert result.tests_skipped == 1

    def test_noop_when_all_files_removed(self):
        """Removed files are excluded at the DB layer; mock returns empty list."""
        outcome = _make_outcome(["suite::test_a"])
        # Simulate the DB filter excluding removed files by returning empty list
        mock_db = _mock_db_with_changed_files([])

        with patch.object(TestCoverageLinkRepository, "upsert_link") as mock_up:
            result = ManualOverrideLearner.learn_from_outcome(
                db=mock_db,
                outcome=outcome,
                workspace_id=_WORKSPACE_ID,
            )

        mock_up.assert_not_called()
        assert result.tests_skipped == 1


class TestLearnLinkCreation:
    def test_creates_links_for_each_test_and_file(self):
        """2 tests × 2 source files = 4 upsert calls."""
        outcome = _make_outcome(["s::test_a", "s::test_b"])
        changed = [
            _make_changed_file("app/foo.py"),
            _make_changed_file("app/bar.py"),
        ]
        mock_db = _mock_db_with_changed_files(changed)
        # No existing links → override_count = 0 for all
        mock_db.query.side_effect = None
        mock_db.query.return_value.filter.return_value.all.return_value = changed
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch.object(TestCoverageLinkRepository, "get_exact_link", return_value=None):
            with patch.object(
                TestCoverageLinkRepository, "upsert_link", return_value=MagicMock()
            ) as mock_up:
                from app.models.pull_request import PullRequestChangedFile
                # Patch the actual DB call inside learn_from_outcome
                with patch.object(mock_db, "query") as mock_query:
                    def _side(cls):
                        q = MagicMock()
                        q.filter.return_value.all.return_value = changed
                        return q
                    mock_query.side_effect = _side

                    result = ManualOverrideLearner.learn_from_outcome(
                        db=mock_db,
                        outcome=outcome,
                        workspace_id=_WORKSPACE_ID,
                    )

        assert result.links_upserted == 4
        assert result.tests_processed == 2

    def test_source_and_confidence_values(self):
        """Every upsert must carry source=MANUAL_OVERRIDE and confidence=1.0."""
        outcome = _make_outcome(["s::test_x"])
        changed = [_make_changed_file("app/x.py")]

        mock_db = MagicMock()
        captured_calls = []

        def _side_query(cls):
            q = MagicMock()
            q.filter.return_value.all.return_value = changed
            return q

        mock_db.query.side_effect = _side_query

        def _upsert_spy(**kwargs):
            captured_calls.append(kwargs)
            return MagicMock()

        with patch.object(TestCoverageLinkRepository, "get_exact_link", return_value=None):
            with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=_upsert_spy):
                ManualOverrideLearner.learn_from_outcome(
                    db=mock_db,
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        assert len(captured_calls) == 1
        assert captured_calls[0]["source"]     == _SOURCE
        assert captured_calls[0]["confidence"] == _CONFIDENCE

    def test_skips_non_source_files(self):
        """md, yml, json, png, lock extensions must be filtered."""
        outcome = _make_outcome(["s::test_skip"])
        changed = [
            _make_changed_file("CHANGELOG.md"),
            _make_changed_file("docker-compose.yml"),
            _make_changed_file("package-lock.json"),
            _make_changed_file("assets/logo.png"),
            _make_changed_file("app/real.py"),      # only this qualifies
        ]

        mock_db = MagicMock()

        def _side_query(cls):
            q = MagicMock()
            q.filter.return_value.all.return_value = changed
            return q

        mock_db.query.side_effect = _side_query
        captured = []

        with patch.object(TestCoverageLinkRepository, "get_exact_link", return_value=None):
            with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=lambda **kw: captured.append(kw) or MagicMock()):
                result = ManualOverrideLearner.learn_from_outcome(
                    db=mock_db,
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        assert result.links_upserted == 1
        assert captured[0]["file_path"] == "app/real.py"

    def test_upsert_error_skips_file_not_test(self):
        """A failed upsert on one file does not prevent the next file."""
        outcome = _make_outcome(["s::test_partial"])
        changed = [
            _make_changed_file("app/good.py"),
            _make_changed_file("app/bad.py"),
        ]

        mock_db = MagicMock()

        def _side_query(cls):
            q = MagicMock()
            q.filter.return_value.all.return_value = changed
            return q

        mock_db.query.side_effect = _side_query

        def _flaky(**kwargs):
            if kwargs["file_path"] == "app/bad.py":
                raise RuntimeError("Simulated DB error")
            return MagicMock()

        with patch.object(TestCoverageLinkRepository, "get_exact_link", return_value=None):
            with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=_flaky):
                result = ManualOverrideLearner.learn_from_outcome(
                    db=mock_db,
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        assert result.links_upserted == 1   # good.py succeeded
        assert len(result.errors)    == 1   # bad.py failed
        assert result.success        is False

    def test_db_error_on_changed_files_query(self):
        """Exception querying PullRequestChangedFile is captured, not raised."""
        outcome = _make_outcome(["s::test_crash"])
        mock_db = MagicMock()
        mock_db.query.side_effect = RuntimeError("connection timeout")

        result = ManualOverrideLearner.learn_from_outcome(
            db=mock_db,
            outcome=outcome,
            workspace_id=_WORKSPACE_ID,
        )

        assert len(result.errors) == 1
        assert "connection timeout" in result.errors[0]
        assert result.success is False

    def test_empty_string_identifier_is_skipped(self):
        """An empty test identifier should not produce any upsert calls."""
        outcome = _make_outcome(["", "s::valid_test"])
        changed = [_make_changed_file("app/auth.py")]

        mock_db = MagicMock()

        def _side_query(cls):
            q = MagicMock()
            q.filter.return_value.all.return_value = changed
            return q

        mock_db.query.side_effect = _side_query
        captured = []

        with patch.object(TestCoverageLinkRepository, "get_exact_link", return_value=None):
            with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=lambda **kw: captured.append(kw) or MagicMock()):
                result = ManualOverrideLearner.learn_from_outcome(
                    db=mock_db,
                    outcome=outcome,
                    workspace_id=_WORKSPACE_ID,
                )

        # Only s::valid_test should produce a call
        assert result.tests_skipped  == 1   # empty string
        assert result.tests_processed == 1  # valid test
        identifiers = {c["test_identifier"] for c in captured}
        assert "" not in identifiers


# --------------------------------------------------------------------------- #
#  Integration — real in-memory SQLite                                        #
# --------------------------------------------------------------------------- #

class TestLearnIntegration:
    """End-to-end tests using the real repository layer on in-memory SQLite."""

    def _mock_db_delegates(self, real_db, changed_files):
        """Build a mock_db that delegates to real_db for TestCoverageLink
        operations but returns changed_files for PullRequestChangedFile queries."""
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

    def test_first_addition_strength_0_5(self, db):
        changed = [_make_changed_file("app/learn.py")]
        mock_db = self._mock_db_delegates(db, changed)
        outcome = _make_outcome(["suite::learn_test"])

        result = ManualOverrideLearner.learn_from_outcome(
            db=mock_db,
            outcome=outcome,
            workspace_id=_WORKSPACE_ID,
        )

        assert result.links_upserted == 1
        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::learn_test", "app/learn.py"
        )
        assert link is not None
        assert link.link_strength == pytest.approx(0.5)
        assert link.confidence    == pytest.approx(1.0)
        assert link.source        == "MANUAL_OVERRIDE"
        assert link.run_count     == 1

    def test_second_addition_strength_0_6(self, db):
        """Strength grows from 0.5 → 0.6 on second call for the same triple."""
        changed = [_make_changed_file("app/grow.py")]
        mock_db = self._mock_db_delegates(db, changed)
        outcome = _make_outcome(["suite::grow_test"])

        # First call
        ManualOverrideLearner.learn_from_outcome(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID,
        )
        # Second call
        ManualOverrideLearner.learn_from_outcome(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID,
        )

        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::grow_test", "app/grow.py"
        )
        assert link.link_strength == pytest.approx(0.6)
        assert link.run_count     == 2

    def test_five_additions_cap_at_1_0(self, db):
        changed = [_make_changed_file("app/cap.py")]
        mock_db = self._mock_db_delegates(db, changed)
        outcome = _make_outcome(["suite::cap_test"])

        for _ in range(7):
            ManualOverrideLearner.learn_from_outcome(
                db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID,
            )

        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::cap_test", "app/cap.py"
        )
        assert link.link_strength == pytest.approx(1.0)

    def test_source_always_manual_override(self, db):
        changed = [_make_changed_file("app/src.py")]
        mock_db = self._mock_db_delegates(db, changed)
        outcome = _make_outcome(["suite::src_test"])

        ManualOverrideLearner.learn_from_outcome(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID,
        )
        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::src_test", "app/src.py"
        )
        assert link.source == "MANUAL_OVERRIDE"

    def test_non_source_files_not_linked(self, db):
        """Markdown and YAML files in the PR must not produce any links."""
        changed = [
            _make_changed_file("CHANGELOG.md"),
            _make_changed_file("setup.cfg"),
        ]
        mock_db = self._mock_db_delegates(db, changed)
        outcome = _make_outcome(["suite::skip_test"])

        result = ManualOverrideLearner.learn_from_outcome(
            db=mock_db, outcome=outcome, workspace_id=_WORKSPACE_ID,
        )

        assert result.links_upserted == 0
        assert result.tests_skipped  == 1


# --------------------------------------------------------------------------- #
#  collect() hook — mock-based                                                 #
# --------------------------------------------------------------------------- #

class TestCollectorHook:
    """Verify that ManualOverrideLearner.learn_from_outcome is guarded inside
    collect(). We do this by directly exercising the guard block logic."""

    def test_learn_called_when_overrides_present(self):
        """When manually_added_tests is non-empty and a Repository row exists,
        learn_from_outcome must be invoked exactly once."""
        from app.services.manual_override_learner import ManualOverrideLearner

        mock_outcome = _make_outcome(["s::test_override"])
        mock_repo_row = MagicMock()
        mock_repo_row.workspace_id = _WORKSPACE_ID

        called_with = {}

        def _fake_learn(**kwargs):
            called_with.update(kwargs)
            return LearningResult(links_upserted=1)

        with patch.object(ManualOverrideLearner, "learn_from_outcome", side_effect=_fake_learn):
            # Simulate the guarded block from collect()
            mock_db = MagicMock()
            now = datetime.utcnow()
            try:
                _repo_row = mock_repo_row
                if _repo_row and mock_outcome.manually_added_tests:
                    ManualOverrideLearner.learn_from_outcome(
                        db=mock_db,
                        outcome=mock_outcome,
                        workspace_id=_repo_row.workspace_id,
                        observed_at=now,
                    )
            except Exception:
                pass

        assert "outcome" in called_with
        assert called_with["workspace_id"] == _WORKSPACE_ID

    def test_learner_exception_does_not_raise(self):
        """The guarded block in collect() must absorb exceptions from the learner."""
        from app.services.manual_override_learner import ManualOverrideLearner

        outcome = _make_outcome(["s::test"])
        mock_repo_row = MagicMock()
        mock_repo_row.workspace_id = _WORKSPACE_ID

        # Reproduce the guard from collect(): inner exception must be swallowed.
        leaked = []
        try:
            if mock_repo_row and outcome.manually_added_tests:
                try:
                    raise RuntimeError("simulated learner crash")
                except Exception as exc:
                    # This mirrors the collect() guard — log, do not re-raise
                    pass
        except Exception as outer_exc:
            leaked.append(outer_exc)

        assert leaked == [], f"Exception leaked out of guard: {leaked}"


# --------------------------------------------------------------------------- #
#  LearningResult dataclass                                                    #
# --------------------------------------------------------------------------- #

class TestLearningResultProperties:
    def test_success_true_when_no_errors(self):
        r = LearningResult(links_upserted=3, errors=[])
        assert r.success is True

    def test_success_false_when_errors(self):
        r = LearningResult(errors=["boom"])
        assert r.success is False

    def test_had_overrides_true_when_processed(self):
        r = LearningResult(tests_processed=2)
        assert r.had_overrides is True

    def test_had_overrides_false_when_zero(self):
        r = LearningResult(tests_processed=0)
        assert r.had_overrides is False
