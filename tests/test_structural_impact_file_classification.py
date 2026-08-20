"""Regression tests for structural impact file classification and coverage gaps."""
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import SessionLocal as ProductionSessionLocal
from app.models.user import Workspace
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.coverage import CoverageReport
from app.schemas.structural_impact import StructuralImpactSelectionRequest
from app.services.structural_impact_selection import StructuralImpactSelectionService
from app.services.regression_scope_v2_service import RegressionScopeV2Service
from app.schemas.regression_scope_v2 import ScopeMode, ScopeGroup, ScopeItemType
from app.utils.file_classifier import classify_changed_file


def _patch_sqlite_for_generic_types():
    import sqlalchemy.dialects.sqlite.base as sqlite_base
    sqlite_base.SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "TEXT"
    sqlite_base.SQLiteTypeCompiler.visit_ARRAY = lambda self, type_, **kw: "TEXT"


@pytest.fixture
def db():
    _patch_sqlite_for_generic_types()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    assert "veriscope" not in str(engine.url)
    Base.metadata.create_all(engine)
    SessionClass = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionClass()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def repo(db):
    ws = Workspace(id=uuid4(), name="fc probe", slug="fc-probe")
    db.add(ws)
    db.flush()
    r = Repository(
        id=uuid4(), workspace_id=ws.id, github_repo_id=1,
        name="fc", full_name="o/fc", default_branch="main",
    )
    db.add(r)
    db.commit()
    return r


def _make_pr(db, repo, number, head_sha):
    pr = PullRequest(
        id=uuid4(), repository_id=repo.id, github_pr_id=number, number=number,
        title=f"PR-{number}", author="a", source_branch=f"f{number}",
        target_branch="main", state="open", head_commit_sha=head_sha,
        github_created_at=datetime.utcnow(), github_updated_at=datetime.utcnow(),
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db.add(pr)
    db.commit()
    return pr


def _select(db, repo, pr, changed_files):
    request = StructuralImpactSelectionRequest(
        repository_id=repo.id,
        pull_request_id=pr.id,
        head_commit_sha=pr.head_commit_sha,
        changed_files=changed_files,
        max_expansion_depth=0,
        require_test_level=False,
    )
    return StructuralImpactSelectionService.select_structural_impact(db, request)


class TestFileClassifier:
    def test_existing_classifier_reused_for_test_files(self):
        assert classify_changed_file("src/modules/users/__tests__/sign-up.test.ts") == "test"
        assert classify_changed_file("src/components/Button.test.tsx") == "test"
        assert classify_changed_file("tests/test_auth.py") == "test"
        assert classify_changed_file("src/auth_test.py") == "test"

    def test_existing_classifier_reused_for_non_coverable_files(self):
        assert classify_changed_file("README.md") == "non_coverable"
        assert classify_changed_file(".github/workflows/ci.yml") == "non_coverable"
        assert classify_changed_file("package-lock.json") == "non_coverable"
        assert classify_changed_file("dockerfile") == "non_coverable"

    def test_existing_classifier_reused_for_source_files(self):
        assert classify_changed_file("src/app/api/auth/route.ts") == "source"
        assert classify_changed_file("src/app/foo.ts") == "source"

    def test_test_like_names_are_not_false_positives(self):
        assert classify_changed_file("src/testing-utils.ts") == "source"
        assert classify_changed_file("src/testimonials.ts") == "source"
        assert classify_changed_file("src/models/something.specification.ts") == "source"


class TestStructuralCoverageGaps:
    def test_changed_test_file_is_not_unmapped_source_coverage_gap(self, db, repo):
        pr = _make_pr(db, repo, 1, "sha-1")
        result = _select(db, repo, pr, ["src/modules/users/__tests__/sign-up.test.ts"])
        assert "src/modules/users/__tests__/sign-up.test.ts" not in result.unmapped_impacted_files
        assert all(g["file_path"] != "src/modules/users/__tests__/sign-up.test.ts" for g in result.coverage_gaps)

    def test_dot_test_file_is_classified_as_test(self, db, repo):
        pr = _make_pr(db, repo, 2, "sha-2")
        result = _select(db, repo, pr, ["src/components/Button.test.tsx"])
        assert "src/components/Button.test.tsx" in result.impacted_files
        assert "src/components/Button.test.tsx" not in result.unmapped_impacted_files

    def test_changed_test_file_without_lcov_does_not_create_review_needed(self, db, repo):
        pr = _make_pr(db, repo, 3, "sha-3")
        result = _select(db, repo, pr, ["src/tests/integration/auth-workflow.test.ts"])
        assert result.unmapped_impacted_files == []
        assert result.coverage_gaps == []

    def test_changed_test_file_without_execution_still_does_not_create_lcov_gap(self, db, repo):
        pr = _make_pr(db, repo, 4, "sha-4")
        result = _select(db, repo, pr, ["src/e2e/login.spec.js"])
        assert "src/e2e/login.spec.js" not in result.unmapped_impacted_files

    def test_non_coverable_file_does_not_create_source_coverage_gap(self, db, repo):
        pr = _make_pr(db, repo, 5, "sha-5")
        result = _select(db, repo, pr, ["README.md", ".github/workflows/ci.yml"])
        assert result.unmapped_impacted_files == []
        assert result.coverage_gaps == []

    def test_production_source_without_coverage_still_creates_gap(self, db, repo):
        pr = _make_pr(db, repo, 6, "sha-6")
        # Add a coverage report with no entry for src/app/foo.ts
        report = CoverageReport(
            id=uuid4(),
            repository_id=repo.id,
            workspace_id=repo.workspace_id,
            commit_sha=pr.head_commit_sha,
            coverage_level="TEST_CASE_LEVEL",
            coverage_confidence="HIGH",
            format="LCOV",
            source="MANUAL_UPLOAD",
            evidence_health_status="HEALTHY",
            file_hash="hash",
            confidence_score="HIGH",
            confidence_logic="test",
        )
        db.add(report)
        db.commit()
        result = _select(db, repo, pr, ["src/app/foo.ts"])
        assert "src/app/foo.ts" in result.unmapped_impacted_files
        gap_files = [g["file_path"] for g in result.coverage_gaps]
        assert "src/app/foo.ts" in gap_files

    def test_test_file_remains_in_impacted_files_for_diagnostics(self, db, repo):
        pr = _make_pr(db, repo, 7, "sha-7")
        result = _select(db, repo, pr, ["src/modules/users/__tests__/sign-up.test.ts"])
        assert "src/modules/users/__tests__/sign-up.test.ts" in result.impacted_files

    def test_existing_file_classifier_semantics_are_reused(self, db, repo):
        # This test verifies the service actually calls the shared classifier:
        # a path classified as source by the helper must still produce a gap
        # when uncovered, and a test path must not.
        pr = _make_pr(db, repo, 8, "sha-8")
        result = _select(
            db, repo, pr,
            ["src/app/bar.ts", "src/bar.test.ts"],
        )
        assert "src/app/bar.ts" in result.unmapped_impacted_files
        assert "src/bar.test.ts" not in result.unmapped_impacted_files


class TestCleanFixture:
    RUN_ID = "12e5e6a7-5842-4e6a-970f-da4de93dffde"

    def _generate_scope(self):
        db = ProductionSessionLocal()
        try:
            from app.models.recommendation import RecommendationRun
            run = db.query(RecommendationRun).filter(
                RecommendationRun.id == self.RUN_ID
            ).first()
            if run is None:
                pytest.skip("Seeded clean fixture not available")
            return RegressionScopeV2Service.generate_scope_v2(
                db=db,
                run_id=self.RUN_ID,
                mode=ScopeMode.FULL,
                include_safe_to_skip=True,
                include_diagnostics=False,
                audit=False,
            )
        finally:
            db.close()

    def test_clean_fixture_review_needed_count_is_zero(self):
        scope = self._generate_scope()
        review = [
            i for g in scope.groups.values() for i in g.items
            if i.group == ScopeGroup.REVIEW_NEEDED
        ]
        assert len(review) == 0

    def test_clean_fixture_required_count_is_zero(self):
        scope = self._generate_scope()
        required = [
            i for g in scope.groups.values() for i in g.items
            if i.group == ScopeGroup.REQUIRED
        ]
        assert len(required) == 0

    def test_clean_fixture_total_executable_is_zero(self):
        scope = self._generate_scope()
        executable = [
            i for g in scope.groups.values() for i in g.items
            if i.item_type in (ScopeItemType.TEST, ScopeItemType.REQUIREMENT)
            and i.group in (ScopeGroup.REQUIRED, ScopeGroup.REVIEW_NEEDED)
        ]
        assert len(executable) == 0
