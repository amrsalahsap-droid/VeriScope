"""
tests/test_test_coverage_link.py
==================================

Verification tests for the TestCoverageLink model and repository layer.

All tests use in-memory SQLite so no live database or migrations are required.
The table is created via raw DDL to avoid SQLite incompatibilities with
PostgreSQL-specific column types (UUID, JSONB) used in other models.

Tested behaviours
-----------------
Model
  - Row instantiation with correct defaults (after insert)
  - __repr__ is human-readable

Repository — writes
  - upsert_link creates a new row on first call
  - upsert_link increments run / success / failure counters on repeat call
  - upsert_link only overwrites quality signals when caller provides them
  - upsert_link handles concurrent-safe None outcome (no counter increment)
  - create_link persists a pre-built instance
  - create_link raises IntegrityError on duplicate (repo, test, file)

Repository — reads
  - get_by_id returns the correct row
  - get_by_id returns None for unknown id
  - get_links_for_file returns only rows matching that file path
  - get_links_for_test returns only rows matching that test_identifier
  - get_links_for_repository respects skip/limit pagination
  - get_exact_link returns the single matching row
  - get_exact_link returns None for unknown triple

Constraint
  - UniqueConstraint prevents duplicate (repository_id, test_identifier, file_path)
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models.test_coverage_link import TestCoverageLink
from app.repositories.test_coverage_link import TestCoverageLinkRepository


# --------------------------------------------------------------------------- #
#  DDL — SQLite-compatible table definition                                    #
# --------------------------------------------------------------------------- #

_CREATE_TABLE_SQL = """
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

_DROP_TABLE_SQL = "DROP TABLE IF EXISTS test_coverage_links"


# --------------------------------------------------------------------------- #
#  Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine.

    The table is created via raw DDL to stay clear of PostgreSQL dialect types
    used in the full model metadata.
    """
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    with eng.connect() as conn:
        conn.execute(text(_CREATE_TABLE_SQL))
        conn.commit()
    yield eng
    with eng.connect() as conn:
        conn.execute(text(_DROP_TABLE_SQL))
        conn.commit()


@pytest.fixture()
def db(engine):
    """Session-scoped transaction that rolls back after each test."""
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


# Stable UUIDs reused across all tests — stored as strings in SQLite.
_WORKSPACE_ID   = uuid.uuid4()
_REPOSITORY_ID  = uuid.uuid4()
_REPOSITORY_ID2 = uuid.uuid4()


# --------------------------------------------------------------------------- #
#  Model tests                                                                 #
# --------------------------------------------------------------------------- #

class TestTestCoverageLinkModel:
    """Unit tests for the ORM model itself."""

    def test_default_counters_are_zero_after_insert(self, db):
        """Counters should be 0 after the row is flushed to the DB."""
        link = TestCoverageLink(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::test_a",
            file_path="app/foo.py",
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        assert link.run_count     == 0
        assert link.success_count == 0
        assert link.failure_count == 0

    def test_default_quality_signals_are_none(self):
        link = TestCoverageLink(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::test_b",
            file_path="app/bar.py",
        )
        assert link.link_strength is None
        assert link.confidence    is None
        assert link.source        is None

    def test_default_temporal_fields_are_none(self):
        link = TestCoverageLink(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::test_c",
            file_path="app/baz.py",
        )
        assert link.first_seen_at is None
        assert link.last_seen_at  is None

    def test_repr_is_readable(self):
        link = TestCoverageLink(
            id=uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"),
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="my_suite::my_test",
            file_path="src/module.py",
        )
        r = repr(link)
        assert "TestCoverageLink" in r
        assert "my_suite::my_test" in r
        assert "src/module.py" in r

    def test_created_at_defaults_to_utcnow(self, db):
        before = datetime.utcnow()
        link = TestCoverageLink(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::time_test",
            file_path="app/time.py",
        )
        db.add(link)
        db.commit()
        after = datetime.utcnow()
        assert before <= link.created_at <= after


# --------------------------------------------------------------------------- #
#  Repository — write tests                                                    #
# --------------------------------------------------------------------------- #

class TestUpsertLink:
    """Tests for TestCoverageLinkRepository.upsert_link."""

    def test_creates_new_row_on_first_call(self, repo, db):
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::test_new",
            file_path="app/new.py",
            source="STATIC",
            outcome="success",
        )

        assert link.id is not None
        assert link.test_identifier == "suite::test_new"
        assert link.file_path       == "app/new.py"
        assert link.source          == "STATIC"
        assert link.run_count       == 1
        assert link.success_count   == 1
        assert link.failure_count   == 0

    def test_increments_run_count_on_repeat(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::counter_test",
            file_path="app/counter.py",
        )
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::counter_test",
            file_path="app/counter.py",
        )
        assert link.run_count == 2

    def test_increments_success_count(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::success_test",
            file_path="app/s.py",
            outcome="success",
        )
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::success_test",
            file_path="app/s.py",
            outcome="success",
        )
        assert link.success_count == 2
        assert link.failure_count == 0

    def test_increments_failure_count(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::fail_test",
            file_path="app/f.py",
            outcome="failure",
        )
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::fail_test",
            file_path="app/f.py",
            outcome="success",
        )
        assert link.failure_count == 1
        assert link.success_count == 1
        assert link.run_count     == 2

    def test_none_outcome_does_not_change_counters(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::neutral_test",
            file_path="app/n.py",
            outcome="success",
        )
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::neutral_test",
            file_path="app/n.py",
            outcome=None,   # should not touch either counter
        )
        # run_count still goes up; individual counters should remain at 1
        assert link.run_count     == 2
        assert link.success_count == 1
        assert link.failure_count == 0

    def test_does_not_overwrite_link_strength_when_not_provided(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::strength_test",
            file_path="app/st.py",
            link_strength=0.8,
        )
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::strength_test",
            file_path="app/st.py",
            # link_strength intentionally omitted
        )
        assert link.link_strength == 0.8  # preserved

    def test_overwrites_link_strength_when_provided(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::overwrite_test",
            file_path="app/ow.py",
            link_strength=0.4,
        )
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::overwrite_test",
            file_path="app/ow.py",
            link_strength=0.9,
        )
        assert link.link_strength == 0.9

    def test_sets_first_seen_at_only_on_creation(self, repo):
        t0 = datetime(2026, 1, 1, 0, 0, 0)
        t1 = datetime(2026, 1, 2, 0, 0, 0)

        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::time_edge",
            file_path="app/te.py",
            observed_at=t0,
        )
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::time_edge",
            file_path="app/te.py",
            observed_at=t1,
        )
        assert link.first_seen_at == t0   # unchanged on update
        assert link.last_seen_at  == t1   # advances on each update

    def test_upsert_returns_persisted_row(self, repo):
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::persist_check",
            file_path="app/pc.py",
        )
        assert link.id is not None
        fetched = repo.get_by_id(link.id)
        assert fetched is not None
        assert fetched.test_identifier == "suite::persist_check"


class TestCreateLink:
    """Tests for TestCoverageLinkRepository.create_link."""

    def test_creates_link_from_instance(self, repo):
        link = TestCoverageLink(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::raw_create",
            file_path="app/rc.py",
            run_count=5,
            success_count=4,
            failure_count=1,
        )
        saved = repo.create_link(link)
        assert saved.id is not None
        assert saved.run_count == 5

    def test_raises_integrity_error_on_duplicate(self, repo, db):
        repo.create_link(TestCoverageLink(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::dup_test",
            file_path="app/dup.py",
        ))

        with pytest.raises(IntegrityError):
            repo.create_link(TestCoverageLink(
                workspace_id=_WORKSPACE_ID,
                repository_id=_REPOSITORY_ID,
                test_identifier="suite::dup_test",
                file_path="app/dup.py",
            ))


# --------------------------------------------------------------------------- #
#  Repository — read tests                                                     #
# --------------------------------------------------------------------------- #

class TestGetById:
    def test_returns_correct_row(self, repo):
        created = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::get_id",
            file_path="app/gi.py",
        )
        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_returns_none_for_unknown_id(self, repo):
        result = repo.get_by_id(uuid.uuid4())
        assert result is None


class TestGetLinksForFile:
    def test_returns_only_matching_file(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::file_test_1",
            file_path="app/target.py",
        )
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::file_test_2",
            file_path="app/target.py",
        )
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::other_test",
            file_path="app/other.py",
        )

        links = repo.get_links_for_file(_REPOSITORY_ID, "app/target.py")

        assert len(links) == 2
        for lnk in links:
            assert lnk.file_path == "app/target.py"

    def test_returns_empty_list_when_no_match(self, repo):
        links = repo.get_links_for_file(_REPOSITORY_ID, "nonexistent/path.py")
        assert links == []

    def test_does_not_return_rows_from_other_repos(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::cross_repo",
            file_path="app/cross.py",
        )
        links = repo.get_links_for_file(_REPOSITORY_ID2, "app/cross.py")
        assert links == []


class TestGetLinksForTest:
    def test_returns_only_matching_test(self, repo):
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::multi_file_test",
            file_path="app/a.py",
        )
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::multi_file_test",
            file_path="app/b.py",
        )
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::other_test_x",
            file_path="app/a.py",
        )

        links = repo.get_links_for_test(_REPOSITORY_ID, "suite::multi_file_test")

        assert len(links) == 2
        for lnk in links:
            assert lnk.test_identifier == "suite::multi_file_test"

    def test_returns_empty_list_when_no_match(self, repo):
        links = repo.get_links_for_test(_REPOSITORY_ID, "suite::nonexistent_test")
        assert links == []


class TestGetLinksForRepository:
    def test_returns_all_repo_links(self, repo):
        for i in range(3):
            repo.upsert_link(
                workspace_id=_WORKSPACE_ID,
                repository_id=_REPOSITORY_ID,
                test_identifier=f"suite::repo_test_{i}",
                file_path=f"app/repo_file_{i}.py",
            )

        links = repo.get_links_for_repository(_REPOSITORY_ID, skip=0, limit=500)
        identifiers = {lnk.test_identifier for lnk in links}
        for i in range(3):
            assert f"suite::repo_test_{i}" in identifiers

    def test_skip_and_limit_pagination(self, repo):
        for i in range(10):
            repo.upsert_link(
                workspace_id=_WORKSPACE_ID,
                repository_id=_REPOSITORY_ID,
                test_identifier=f"suite::paged_test_{i}",
                file_path=f"app/paged_{i}.py",
            )

        page1 = repo.get_links_for_repository(_REPOSITORY_ID, skip=0, limit=3)
        page2 = repo.get_links_for_repository(_REPOSITORY_ID, skip=3, limit=3)

        assert len(page1) == 3
        assert len(page2) == 3
        ids1 = {lnk.id for lnk in page1}
        ids2 = {lnk.id for lnk in page2}
        assert ids1.isdisjoint(ids2)


class TestGetExactLink:
    def test_returns_matching_row(self, repo):
        created = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::exact_test",
            file_path="app/exact.py",
        )
        found = repo.get_exact_link(
            _REPOSITORY_ID,
            "suite::exact_test",
            "app/exact.py",
        )
        assert found is not None
        assert found.id == created.id

    def test_returns_none_for_unknown_triple(self, repo):
        result = repo.get_exact_link(
            _REPOSITORY_ID,
            "suite::ghost_test",
            "app/ghost.py",
        )
        assert result is None


# --------------------------------------------------------------------------- #
#  Constraint tests                                                            #
# --------------------------------------------------------------------------- #

class TestUniqueConstraint:
    def test_unique_constraint_on_repo_test_file(self, repo, db):
        """Direct DB inserts must respect the uniqueness rule."""
        link1 = TestCoverageLink(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::constraint_test",
            file_path="app/c.py",
        )
        db.add(link1)
        db.commit()

        link2 = TestCoverageLink(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::constraint_test",
            file_path="app/c.py",
        )
        db.add(link2)

        with pytest.raises(IntegrityError):
            db.commit()

    def test_different_file_same_test_is_allowed(self, repo):
        """Same test, different file path → different edge, no constraint."""
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::multi_edge_test",
            file_path="app/edge1.py",
        )
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::multi_edge_test",
            file_path="app/edge2.py",
        )
        assert link.id is not None

    def test_different_test_same_file_is_allowed(self, repo):
        """Same file, different test → different edge, no constraint."""
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::file_edge_a",
            file_path="app/shared.py",
        )
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::file_edge_b",
            file_path="app/shared.py",
        )
        assert link.id is not None

    def test_same_triple_different_repo_is_allowed(self, repo):
        """Same (test, file) in a different repo is a different edge."""
        repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID,
            test_identifier="suite::cross_repo_test",
            file_path="app/cr.py",
        )
        link = repo.upsert_link(
            workspace_id=_WORKSPACE_ID,
            repository_id=_REPOSITORY_ID2,
            test_identifier="suite::cross_repo_test",
            file_path="app/cr.py",
        )
        assert link.id is not None
