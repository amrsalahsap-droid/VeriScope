"""
tests/test_coverage_link_expander.py
======================================

Verification tests for CoverageLinkExpander and the knowledge-graph expansion
hook in CoverageIngestionService.

Test groups
-----------
CoverageLinkExpander (unit)
  - No-op when no FileTestLink rows exist
  - DIRECT mapping produces link_strength=1.0, confidence=1.0, source=COVERAGE
  - HEURISTIC_NAMING mapping produces link_strength=0.7
  - HEURISTIC_PATH mapping produces link_strength=0.4
  - Multiple links from the same report are all upserted
  - Same report re-expanded increments run_count (idempotency)
  - Different report same test+file increments run_count and updates strength
  - Missing TestCase is skipped gracefully (links_skipped += 1)
  - Unknown mapping_type defaults link_strength to 0.0 and is not fatal
  - DB error on FileTestLink query is captured in result.errors
  - Stronger link_strength from DIRECT overrides weaker stored value

CoverageIngestionService integration (unit, mocked dependencies)
  - expand_from_report is called after FileTestLink flush
  - expand_from_report exception does NOT prevent ingestion from returning
  - expand_from_report result with errors logs a warning but does not raise
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.test_coverage_link import TestCoverageLink
from app.repositories.test_coverage_link import TestCoverageLinkRepository
from app.services.coverage_link_expander import (
    CoverageLinkExpander,
    ExpansionResult,
    _SOURCE_COVERAGE,
    _CONFIDENCE_HIGH,
    _STRENGTH_BY_MAPPING_TYPE,
)


# --------------------------------------------------------------------------- #
#  Helpers / DDL                                                               #
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
#  Shared fake objects                                                         #
# --------------------------------------------------------------------------- #

_WORKSPACE_ID  = uuid.uuid4()
_REPO_ID       = uuid.uuid4()
_REPORT_ID     = uuid.uuid4()
_TC_ID_1       = uuid.uuid4()
_TC_ID_2       = uuid.uuid4()
_TC_ID_3       = uuid.uuid4()


def _make_ftl(
    test_case_id: uuid.UUID,
    file_path: str,
    mapping_type: str,
    report_id: uuid.UUID = _REPORT_ID,
) -> MagicMock:
    """Construct a FileTestLink-shaped MagicMock."""
    ftl = MagicMock()
    ftl.id = uuid.uuid4()
    ftl.coverage_report_id = report_id
    ftl.test_case_id = test_case_id
    ftl.file_path = file_path
    ftl.mapping_type = mapping_type
    return ftl


def _make_tc(tc_id: uuid.UUID, stable_identity: str) -> MagicMock:
    """Construct a TestCase-shaped MagicMock."""
    tc = MagicMock()
    tc.id = tc_id
    tc.stable_identity = stable_identity
    return tc


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
def tcl_repo(db):
    return TestCoverageLinkRepository(db)


# --------------------------------------------------------------------------- #
#  Helper: mock the db.query chain for expand_from_report                     #
# --------------------------------------------------------------------------- #

def _patch_queries(mock_db, file_test_links, test_cases):
    """Wire mock_db.query to return ftl list and tc list in order."""
    mock_db.query.side_effect = _make_query_side_effect(file_test_links, test_cases)


def _make_query_side_effect(file_test_links, test_cases):
    """Returns a side_effect function that dispatches on the queried class."""
    from app.models.coverage import FileTestLink
    from app.models.test_result import TestCase

    def _side_effect(model_class):
        q = MagicMock()
        if model_class is FileTestLink:
            q.filter.return_value.all.return_value = file_test_links
        elif model_class is TestCase:
            q.filter.return_value.all.return_value = test_cases
        else:
            q.filter.return_value.all.return_value = []
        return q

    return _side_effect


# --------------------------------------------------------------------------- #
#  CoverageLinkExpander — unit tests (mocked DB)                              #
# --------------------------------------------------------------------------- #

class TestExpanderNoLinks:
    def test_noop_when_no_file_test_links(self, db):
        """When no FileTestLink rows exist the graph is not touched."""
        mock_db = MagicMock()
        _patch_queries(mock_db, [], [])

        result = CoverageLinkExpander.expand_from_report(
            db=mock_db,
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            coverage_report_id=_REPORT_ID,
        )

        assert result.links_upserted == 0
        assert result.links_skipped  == 0
        assert result.errors         == []
        assert result.success        is True


class TestExpanderStrengthMapping:
    """One FileTestLink of each mapping type → correct link_strength."""

    def _run_single_link(self, db, mapping_type: str, expected_strength: float):
        ftl = _make_ftl(_TC_ID_1, "app/foo.py", mapping_type)
        tc  = _make_tc(_TC_ID_1, "suite::test_foo")

        mock_db = MagicMock()
        _patch_queries(mock_db, [ftl], [tc])

        # Intercept upsert_link so we can inspect what it was called with.
        captured = {}
        real_repo = TestCoverageLinkRepository(mock_db)

        def _upsert_spy(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=_upsert_spy):
            result = CoverageLinkExpander.expand_from_report(
                db=mock_db,
                workspace_id=_WORKSPACE_ID,
                repository_id=_REPO_ID,
                coverage_report_id=_REPORT_ID,
            )

        assert result.links_upserted == 1
        assert captured["link_strength"] == expected_strength
        assert captured["confidence"]    == _CONFIDENCE_HIGH
        assert captured["source"]        == _SOURCE_COVERAGE

    def test_direct_mapping_strength_1_0(self, db):
        self._run_single_link(db, "DIRECT", 1.0)

    def test_heuristic_naming_strength_0_7(self, db):
        self._run_single_link(db, "HEURISTIC_NAMING", 0.7)

    def test_heuristic_path_strength_0_4(self, db):
        self._run_single_link(db, "HEURISTIC_PATH", 0.4)


class TestExpanderMissingTestCase:
    def test_skips_gracefully_when_test_case_not_found(self):
        """FileTestLink referencing a non-existent TestCase is skipped."""
        ftl = _make_ftl(uuid.uuid4(), "app/bar.py", "DIRECT")

        mock_db = MagicMock()
        _patch_queries(mock_db, [ftl], [])   # empty test_cases list

        with patch.object(TestCoverageLinkRepository, "upsert_link") as mock_upsert:
            result = CoverageLinkExpander.expand_from_report(
                db=mock_db,
                workspace_id=_WORKSPACE_ID,
                repository_id=_REPO_ID,
                coverage_report_id=_REPORT_ID,
            )

        mock_upsert.assert_not_called()
        assert result.links_upserted == 0
        assert result.links_skipped  == 1
        assert result.success        is True   # skip is not an error


class TestExpanderUnknownMappingType:
    def test_unknown_mapping_type_defaults_to_zero_strength(self):
        """An unknown mapping_type produces link_strength=0.0 and is not fatal."""
        ftl = _make_ftl(_TC_ID_1, "app/baz.py", "UNKNOWN_TYPE")
        tc  = _make_tc(_TC_ID_1, "suite::test_baz")

        mock_db = MagicMock()
        _patch_queries(mock_db, [ftl], [tc])

        captured = {}

        def _upsert_spy(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=_upsert_spy):
            result = CoverageLinkExpander.expand_from_report(
                db=mock_db,
                workspace_id=_WORKSPACE_ID,
                repository_id=_REPO_ID,
                coverage_report_id=_REPORT_ID,
            )

        assert result.links_upserted == 1
        assert captured["link_strength"] == 0.0


class TestExpanderMultipleLinks:
    def test_all_links_are_upserted(self):
        """Three FileTestLink rows → three upsert_link calls."""
        ftls = [
            _make_ftl(_TC_ID_1, "app/a.py", "DIRECT"),
            _make_ftl(_TC_ID_2, "app/b.py", "HEURISTIC_NAMING"),
            _make_ftl(_TC_ID_3, "app/c.py", "HEURISTIC_PATH"),
        ]
        tcs = [
            _make_tc(_TC_ID_1, "s::test_a"),
            _make_tc(_TC_ID_2, "s::test_b"),
            _make_tc(_TC_ID_3, "s::test_c"),
        ]

        mock_db = MagicMock()
        _patch_queries(mock_db, ftls, tcs)

        with patch.object(TestCoverageLinkRepository, "upsert_link", return_value=MagicMock()) as mock_up:
            result = CoverageLinkExpander.expand_from_report(
                db=mock_db,
                workspace_id=_WORKSPACE_ID,
                repository_id=_REPO_ID,
                coverage_report_id=_REPORT_ID,
            )

        assert result.links_upserted == 3
        assert mock_up.call_count    == 3


class TestExpanderDbError:
    def test_db_error_on_query_captured_in_result(self):
        """A DB error querying FileTestLink is captured, not raised."""
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("DB connection lost")

        result = CoverageLinkExpander.expand_from_report(
            db=mock_db,
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            coverage_report_id=_REPORT_ID,
        )

        assert result.links_upserted == 0
        assert len(result.errors)    == 1
        assert "DB connection lost" in result.errors[0]
        assert result.success        is False


class TestExpanderUpsertError:
    def test_upsert_error_is_skipped_not_fatal(self):
        """An error on one upsert_link call does not prevent others."""
        ftls = [
            _make_ftl(_TC_ID_1, "app/good.py", "DIRECT"),
            _make_ftl(_TC_ID_2, "app/bad.py",  "DIRECT"),
        ]
        tcs = [
            _make_tc(_TC_ID_1, "s::test_good"),
            _make_tc(_TC_ID_2, "s::test_bad"),
        ]

        mock_db = MagicMock()
        _patch_queries(mock_db, ftls, tcs)

        call_count = {"n": 0}

        def _flaky_upsert(**kwargs):
            call_count["n"] += 1
            if kwargs["file_path"] == "app/bad.py":
                raise RuntimeError("Simulated constraint error")
            return MagicMock()

        with patch.object(TestCoverageLinkRepository, "upsert_link", side_effect=_flaky_upsert):
            result = CoverageLinkExpander.expand_from_report(
                db=mock_db,
                workspace_id=_WORKSPACE_ID,
                repository_id=_REPO_ID,
                coverage_report_id=_REPORT_ID,
            )

        # One upserted successfully, one failed
        assert result.links_upserted == 1
        assert result.links_skipped  == 1
        assert len(result.errors)    == 1
        assert result.partial        is True


# --------------------------------------------------------------------------- #
#  Integration: idempotency via real in-memory SQLite                         #
# --------------------------------------------------------------------------- #

class TestExpanderIdempotency:
    """Re-expanding the same report increments run_count exactly once."""

    def _mock_db_for_real_repo(self, real_db, file_test_links, test_cases):
        """Build a mock_db whose query chain delegates to the real db for
        TestCoverageLink queries (via the real repo) but returns mocks for
        FileTestLink and TestCase queries."""
        from app.models.coverage import FileTestLink
        from app.models.test_result import TestCase

        def _side_effect(model_class):
            q = MagicMock()
            if model_class is FileTestLink:
                q.filter.return_value.all.return_value = file_test_links
            elif model_class is TestCase:
                q.filter.return_value.all.return_value = test_cases
            else:
                # Delegate to real db for TestCoverageLink
                return real_db.query(model_class)
            return q

        mock_db = MagicMock()
        mock_db.query.side_effect = _side_effect
        mock_db.add = real_db.add
        mock_db.commit = real_db.commit
        mock_db.refresh = real_db.refresh
        return mock_db

    def test_run_count_increments_on_repeat_expansion(self, db):
        ftl = _make_ftl(_TC_ID_1, "app/idem.py", "DIRECT")
        tc  = _make_tc(_TC_ID_1, "suite::test_idem")

        mock_db = self._mock_db_for_real_repo(db, [ftl], [tc])

        # First expansion — creates the row
        CoverageLinkExpander.expand_from_report(
            db=mock_db,
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            coverage_report_id=_REPORT_ID,
        )

        link_after_first = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::test_idem", "app/idem.py"
        )
        assert link_after_first is not None
        assert link_after_first.run_count == 1

        # Second expansion (same report data) — increments run_count
        CoverageLinkExpander.expand_from_report(
            db=mock_db,
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            coverage_report_id=_REPORT_ID,
        )

        link_after_second = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::test_idem", "app/idem.py"
        )
        assert link_after_second.run_count == 2

    def test_stronger_mapping_overwrites_link_strength(self, db):
        """A DIRECT link (1.0) replaces a previously stored HEURISTIC (0.4)."""
        test_id = "suite::test_strength_update"
        file_p  = "app/strength.py"

        # Seed a weak link
        TestCoverageLinkRepository(db).upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            test_identifier=test_id,
            file_path=file_p,
            source="HEURISTIC",
            link_strength=0.4,
            confidence=0.5,
        )

        weak = TestCoverageLinkRepository(db).get_exact_link(_REPO_ID, test_id, file_p)
        assert weak.link_strength == 0.4

        # Now expand with a DIRECT link
        ftl = _make_ftl(_TC_ID_2, file_p, "DIRECT")
        tc  = _make_tc(_TC_ID_2, test_id)

        mock_db = self._mock_db_for_real_repo(db, [ftl], [tc])
        CoverageLinkExpander.expand_from_report(
            db=mock_db,
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            coverage_report_id=uuid.uuid4(),
        )

        strong = TestCoverageLinkRepository(db).get_exact_link(_REPO_ID, test_id, file_p)
        assert strong.link_strength == 1.0
        assert strong.confidence    == _CONFIDENCE_HIGH
        assert strong.source        == _SOURCE_COVERAGE

    def test_source_is_always_set_to_coverage(self, db):
        """Every link written by the expander has source=COVERAGE."""
        ftl = _make_ftl(_TC_ID_3, "app/src.py", "HEURISTIC_NAMING")
        tc  = _make_tc(_TC_ID_3, "suite::test_src")

        mock_db = self._mock_db_for_real_repo(db, [ftl], [tc])
        CoverageLinkExpander.expand_from_report(
            db=mock_db,
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPO_ID,
            coverage_report_id=uuid.uuid4(),
        )

        link = TestCoverageLinkRepository(db).get_exact_link(
            _REPO_ID, "suite::test_src", "app/src.py"
        )
        assert link.source == "COVERAGE"


# --------------------------------------------------------------------------- #
#  CoverageIngestionService integration — mock-based                          #
# --------------------------------------------------------------------------- #

class TestIngestionServiceHook:
    """Verify expand_from_report is called within ingest_coverage and that
    failures are silently absorbed."""

    def _make_mock_db(self):
        """Minimal mock that makes ingest_coverage skip through I/O paths."""
        mock_db = MagicMock()
        # Repository lookup
        mock_repo = MagicMock()
        mock_repo.workspace_id = _WORKSPACE_ID
        # idempotency guard: no existing report
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,       # idempotency check (no existing report)
            mock_repo,  # Repository lookup
        ]
        return mock_db

    @patch("app.services.coverage_ingestion.ObjectStorageService")
    @patch("app.services.coverage_ingestion.SafeLCOVParser")
    @patch("app.services.coverage_ingestion.CoverageLinkExpander.expand_from_report")
    def test_expand_is_called_after_flush(self, mock_expand, mock_parser, mock_storage):
        """expand_from_report must be called exactly once per ingest_coverage call."""
        from app.services.coverage_ingestion import CoverageIngestionService

        mock_parser.parse_lcov.return_value = [{
            "file_path": "app/foo.py",
            "test_name": "",
            "covered_lines": [1, 2],
            "uncovered_lines": [3],
            "total_lines_count": 3,
            "covered_lines_count": 2,
            "uncovered_lines_count": 1,
            "total_lines": 3,
            "line_coverage_ratio": 0.67,
            "branch_coverage_ratio": None,
            "functions_covered": None,
            "functions_total": None,
            "brf": None,
            "brh": None,
        }]

        mock_artifact = MagicMock()
        mock_artifact.id = uuid.uuid4()
        mock_storage.return_value.upload_coverage_report.return_value = mock_artifact

        mock_expand.return_value = ExpansionResult(links_upserted=1)

        mock_db = self._make_mock_db()

        CoverageIngestionService.ingest_coverage(
            db=mock_db,
            repository_id=_REPO_ID,
            commit_sha="abc123",
            payload_bytes=b"TN:\nSF:app/foo.py\nDA:1,1\nDA:2,1\nDA:3,0\nLF:3\nLH:2\nend_of_record\n",
            file_name="coverage.info",
        )

        mock_expand.assert_called_once()
        call_kwargs = mock_expand.call_args.kwargs
        assert call_kwargs["workspace_id"] == _WORKSPACE_ID
        assert call_kwargs["repository_id"] == _REPO_ID

    @patch("app.services.coverage_ingestion.ObjectStorageService")
    @patch("app.services.coverage_ingestion.SafeLCOVParser")
    @patch("app.services.coverage_ingestion.CoverageLinkExpander.expand_from_report")
    def test_expander_exception_does_not_propagate(self, mock_expand, mock_parser, mock_storage):
        """An unexpected exception from expand_from_report must not prevent
        ingest_coverage from returning successfully."""
        from app.services.coverage_ingestion import CoverageIngestionService

        mock_parser.parse_lcov.return_value = [{
            "file_path": "app/bar.py",
            "test_name": "",
            "covered_lines": [1],
            "uncovered_lines": [],
            "total_lines_count": 1,
            "covered_lines_count": 1,
            "uncovered_lines_count": 0,
            "total_lines": 1,
            "line_coverage_ratio": 1.0,
            "branch_coverage_ratio": None,
            "functions_covered": None,
            "functions_total": None,
            "brf": None,
            "brh": None,
        }]

        mock_artifact = MagicMock()
        mock_artifact.id = uuid.uuid4()
        mock_storage.return_value.upload_coverage_report.return_value = mock_artifact

        # Simulate a hard crash in expand_from_report
        mock_expand.side_effect = RuntimeError("Unexpected expansion failure")

        mock_db = self._make_mock_db()

        # Should NOT raise
        result = CoverageIngestionService.ingest_coverage(
            db=mock_db,
            repository_id=_REPO_ID,
            commit_sha="def456",
            payload_bytes=b"TN:\nSF:app/bar.py\nDA:1,1\nLF:1\nLH:1\nend_of_record\n",
            file_name="coverage.info",
        )

        assert result is not None

    @patch("app.services.coverage_ingestion.ObjectStorageService")
    @patch("app.services.coverage_ingestion.SafeLCOVParser")
    @patch("app.services.coverage_ingestion.CoverageLinkExpander.expand_from_report")
    def test_expander_partial_errors_log_warning(
        self, mock_expand, mock_parser, mock_storage, caplog
    ):
        """Partial expansion errors are logged as warnings, not exceptions."""
        import logging
        from app.services.coverage_ingestion import CoverageIngestionService

        mock_parser.parse_lcov.return_value = [{
            "file_path": "app/baz.py",
            "test_name": "",
            "covered_lines": [],
            "uncovered_lines": [1],
            "total_lines_count": 1,
            "covered_lines_count": 0,
            "uncovered_lines_count": 1,
            "total_lines": 1,
            "line_coverage_ratio": 0.0,
            "branch_coverage_ratio": None,
            "functions_covered": None,
            "functions_total": None,
            "brf": None,
            "brh": None,
        }]

        mock_artifact = MagicMock()
        mock_artifact.id = uuid.uuid4()
        mock_storage.return_value.upload_coverage_report.return_value = mock_artifact

        mock_expand.return_value = ExpansionResult(
            links_upserted=0,
            links_skipped=1,
            errors=["upsert failed for some reason"],
        )

        mock_db = self._make_mock_db()

        with caplog.at_level(logging.WARNING):
            CoverageIngestionService.ingest_coverage(
                db=mock_db,
                repository_id=_REPO_ID,
                commit_sha="ghi789",
                payload_bytes=b"TN:\nSF:app/baz.py\nDA:1,0\nLF:1\nLH:0\nend_of_record\n",
                file_name="coverage.info",
            )

        assert any("CoverageLinkExpander" in r.message for r in caplog.records)


# --------------------------------------------------------------------------- #
#  ExpansionResult dataclass                                                   #
# --------------------------------------------------------------------------- #

class TestExpansionResultProperties:
    def test_success_true_when_no_errors(self):
        r = ExpansionResult(links_upserted=5, links_skipped=0, errors=[])
        assert r.success is True

    def test_success_false_when_errors_present(self):
        r = ExpansionResult(links_upserted=0, errors=["boom"])
        assert r.success is False

    def test_partial_true_when_some_upserted_some_skipped(self):
        r = ExpansionResult(links_upserted=2, links_skipped=1, errors=[])
        assert r.partial is True

    def test_partial_false_when_all_upserted(self):
        r = ExpansionResult(links_upserted=3, links_skipped=0, errors=[])
        assert r.partial is False

    def test_partial_false_when_none_upserted(self):
        r = ExpansionResult(links_upserted=0, links_skipped=3, errors=[])
        assert r.partial is False
