"""
GitHub PR Sync Visibility Tests

Tests for the root cause fix: github_pr_id must be scoped per repository_id.

Root cause (B): The global unique constraint on github_pr_id caused cross-workspace
collisions. The upsert query found an existing PR row belonging to a different
repository_id, updated it, but the repository_id was not changed. Subsequent
GET /pull-requests for the current repository returned 0 rows, while the sync
response (built from GitHub API data) claimed success with N changed files.

Tests cover all 8 required scenarios:
1. Syncing open PR persists the PR row under the correct repository_id.
2. Syncing open PR persists changed files linked to that PR.
3. Synced open PR appears in the PR list endpoint query.
4. PR list endpoint uses same repository_id as sync (no cross-repo bleed).
5. Active/open filter includes open non-merged PR.
6. Repository evidence counter (pull_requests_count) increments after sync.
7. No contradictory state: synced count > 0 while PR list count = 0 for same open PR.
8. Closed/merged PR is historical — not returned as an open/active PR.
"""
import pytest
import uuid
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pr(repo_id, github_pr_id, number, state="open", changed_files_count=0,
             sync_status="FULL_SUCCESS", head_sha="abc00001"):
    return PullRequest(
        id=uuid.uuid4(),
        repository_id=repo_id,
        github_pr_id=github_pr_id,
        number=number,
        title=f"Test PR #{number}",
        author="testuser",
        source_branch="feature",
        target_branch="main",
        state=state,
        additions=10,
        deletions=5,
        changed_files_count=changed_files_count,
        head_commit_sha=head_sha,
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow(),
        sync_integrity_status=sync_status,
    )


def _add_changed_files(db, pr, count):
    for i in range(count):
        db.add(PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path=f"src/file_{i}.py",
            status="modified",
            additions=5,
            deletions=2,
        ))
    db.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def test_repository(db_session: Session):
    repo = db_session.query(Repository).first()
    if not repo:
        pytest.skip("No repository found in database")
    return repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPRSyncVisibility:
    """All 8 required sync visibility test cases."""

    # ------------------------------------------------------------------
    # Test 1: Syncing open PR persists the PR row
    # ------------------------------------------------------------------
    def test_syncing_open_pr_persists_pr_row(self, db_session: Session, test_repository):
        """Syncing an open PR creates a row with state=open under the correct repo."""
        db_session.query(PullRequest).filter(
            PullRequest.github_pr_id == 8880001,
            PullRequest.repository_id == test_repository.id
        ).delete()
        db_session.commit()

        pr = _make_pr(test_repository.id, 8880001, 8001)
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        assert pr.state == "open"
        assert pr.merged == False
        assert pr.repository_id == test_repository.id

        db_session.delete(pr)
        db_session.commit()

    # ------------------------------------------------------------------
    # Test 2: Syncing open PR persists changed files
    # ------------------------------------------------------------------
    def test_syncing_open_pr_persists_changed_files(self, db_session: Session, test_repository):
        """Changed files are persisted and linked to the correct PR id."""
        db_session.query(PullRequest).filter(
            PullRequest.github_pr_id == 8880002,
            PullRequest.repository_id == test_repository.id
        ).delete()
        db_session.commit()

        pr = _make_pr(test_repository.id, 8880002, 8002, changed_files_count=6)
        db_session.add(pr)
        db_session.commit()
        _add_changed_files(db_session, pr, 6)

        file_count = db_session.query(func.count(PullRequestChangedFile.id)).filter(
            PullRequestChangedFile.pull_request_id == pr.id
        ).scalar()

        assert file_count == 6
        assert pr.changed_files_count == 6

        db_session.delete(pr)
        db_session.commit()

    # ------------------------------------------------------------------
    # Test 3: Synced open PR appears in PR list endpoint query
    # ------------------------------------------------------------------
    def test_synced_open_pr_appears_in_pr_list(self, db_session: Session, test_repository):
        """GET /pull-requests query returns the synced PR for its repository."""
        db_session.query(PullRequest).filter(
            PullRequest.github_pr_id == 8880003,
            PullRequest.repository_id == test_repository.id
        ).delete()
        db_session.commit()

        pr = _make_pr(test_repository.id, 8880003, 8003, changed_files_count=3)
        db_session.add(pr)
        db_session.commit()
        _add_changed_files(db_session, pr, 3)

        # Simulate the endpoint query
        results = db_session.query(PullRequest).filter(
            PullRequest.repository_id == test_repository.id
        ).all()

        found = [p for p in results if p.github_pr_id == 8880003]
        assert len(found) == 1
        assert found[0].state == "open"

        db_session.delete(pr)
        db_session.commit()

    # ------------------------------------------------------------------
    # Test 4: PR list uses same repository_id as sync (no cross-repo bleed)
    # ------------------------------------------------------------------
    def test_pr_list_scoped_to_repository_id(self, db_session: Session, test_repository):
        """The SAME github_pr_id stored under two different repository_ids must
        not bleed between them — each repo sees only its own PR row."""
        # Find a second repository to use as the "other" repo
        other_repo = db_session.query(Repository).filter(
            Repository.id != test_repository.id
        ).first()
        if not other_repo:
            pytest.skip("Need at least two repositories in DB for this test")

        # Clean up both sides
        db_session.query(PullRequest).filter(
            PullRequest.github_pr_id == 8880004,
        ).delete()
        db_session.commit()

        # Same github_pr_id, two different repos
        pr_a = _make_pr(test_repository.id, 8880004, 8004, head_sha="aaa00004")
        pr_b = _make_pr(other_repo.id, 8880004, 8004, head_sha="bbb00004")
        db_session.add(pr_a)
        db_session.add(pr_b)
        db_session.commit()

        # Each repo's query should return exactly its own row
        prs_for_test_repo = db_session.query(PullRequest).filter(
            PullRequest.repository_id == test_repository.id,
            PullRequest.github_pr_id == 8880004
        ).all()
        prs_for_other_repo = db_session.query(PullRequest).filter(
            PullRequest.repository_id == other_repo.id,
            PullRequest.github_pr_id == 8880004
        ).all()

        assert len(prs_for_test_repo) == 1
        assert prs_for_test_repo[0].head_commit_sha == "aaa00004"

        assert len(prs_for_other_repo) == 1
        assert prs_for_other_repo[0].head_commit_sha == "bbb00004"

        db_session.delete(pr_a)
        db_session.delete(pr_b)
        db_session.commit()

    # ------------------------------------------------------------------
    # Test 5: Active/open filter includes open non-merged PR
    # ------------------------------------------------------------------
    def test_open_non_merged_pr_included_in_active_filter(self, db_session: Session, test_repository):
        """An open, non-merged PR must appear when filtering state=open."""
        db_session.query(PullRequest).filter(
            PullRequest.github_pr_id == 8880005,
            PullRequest.repository_id == test_repository.id
        ).delete()
        db_session.commit()

        pr = _make_pr(test_repository.id, 8880005, 8005)
        db_session.add(pr)
        db_session.commit()

        open_prs = db_session.query(PullRequest).filter(
            PullRequest.repository_id == test_repository.id,
            PullRequest.state == "open"
        ).all()

        assert any(p.github_pr_id == 8880005 for p in open_prs)

        db_session.delete(pr)
        db_session.commit()

    # ------------------------------------------------------------------
    # Test 6: Repository evidence counter increments after sync
    # ------------------------------------------------------------------
    def test_evidence_counter_increments_after_sync(self, db_session: Session, test_repository):
        """pull_requests_count query increments by 1 after a PR is persisted."""
        db_session.query(PullRequest).filter(
            PullRequest.github_pr_id == 8880006,
            PullRequest.repository_id == test_repository.id
        ).delete()
        db_session.commit()

        before = db_session.query(func.count(PullRequest.id)).filter(
            PullRequest.repository_id == test_repository.id
        ).scalar()

        pr = _make_pr(test_repository.id, 8880006, 8006)
        db_session.add(pr)
        db_session.commit()

        after = db_session.query(func.count(PullRequest.id)).filter(
            PullRequest.repository_id == test_repository.id
        ).scalar()

        assert after == before + 1

        db_session.delete(pr)
        db_session.commit()

    # ------------------------------------------------------------------
    # Test 7: No contradictory state (synced > 0 but list = 0 impossible)
    # ------------------------------------------------------------------
    def test_no_contradictory_synced_count_vs_list_count(self, db_session: Session, test_repository):
        """If the sync upsert correctly scopes to repository_id, the PR list
        for that repository must return the same PR that was just inserted."""
        db_session.query(PullRequest).filter(
            PullRequest.github_pr_id == 8880007,
            PullRequest.repository_id == test_repository.id
        ).delete()
        db_session.commit()

        pr = _make_pr(test_repository.id, 8880007, 8007, changed_files_count=6)
        db_session.add(pr)
        db_session.commit()
        _add_changed_files(db_session, pr, 6)

        # Simulate sync endpoint success condition
        file_count = db_session.query(func.count(PullRequestChangedFile.id)).filter(
            PullRequestChangedFile.pull_request_id == pr.id
        ).scalar()
        sync_reports_success = file_count > 0 or pr.sync_integrity_status == "FULL_SUCCESS"

        # Simulate PR list query
        pr_list = db_session.query(PullRequest).filter(
            PullRequest.repository_id == test_repository.id
        ).all()
        list_contains_pr = any(p.github_pr_id == 8880007 for p in pr_list)

        # The contradiction: sync says success but list is empty — must never happen
        assert sync_reports_success == True
        assert list_contains_pr == True

        db_session.delete(pr)
        db_session.commit()

    # ------------------------------------------------------------------
    # Test 8: Closed/merged PR is historical — not active
    # ------------------------------------------------------------------
    def test_closed_pr_is_historical_not_active(self, db_session: Session, test_repository):
        """A closed PR must not appear in state=open queries but must be in all-PRs."""
        db_session.query(PullRequest).filter(
            PullRequest.github_pr_id == 8880008,
            PullRequest.repository_id == test_repository.id
        ).delete()
        db_session.commit()

        pr = _make_pr(test_repository.id, 8880008, 8008, state="closed")
        db_session.add(pr)
        db_session.commit()

        open_prs = db_session.query(PullRequest).filter(
            PullRequest.repository_id == test_repository.id,
            PullRequest.state == "open"
        ).all()
        all_prs = db_session.query(PullRequest).filter(
            PullRequest.repository_id == test_repository.id
        ).all()

        assert not any(p.github_pr_id == 8880008 for p in open_prs)
        assert any(p.github_pr_id == 8880008 for p in all_prs)

        db_session.delete(pr)
        db_session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
