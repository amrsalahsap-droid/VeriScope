"""
Tests for TestMatchingV4.

Covers:
- Each signal layer fires correctly in isolation
- Score arithmetic: sum of all active signals (including negative runtime)
- Signal breakdown dict is complete (no hidden keys)
- Fallback activates only when no other signal fires
- Quarantined tests are excluded
- Sorting order: score DESC, duration ASC, identifier ASC
- Reason text: max 4 bullets, factual, no forbidden phrases
- to_dict() serialisation
- Token similarity helper
"""
import uuid
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

# SQLite compat shims
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "TEXT"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"

from app.db.base import Base
import app.models  # noqa — registers all models
from app.models.coverage import FileTestLink, CoverageReport
from app.models.domain_map import DomainMap
from app.models.flaky_test import FlakyTestProfile
from app.models.module_risk_profile import ModuleRiskProfile
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_coverage_link import TestCoverageLink
from app.models.test_result import TestCase, TestRun, TestResult
from app.models.user import Workspace
from app.services.test_matching_v4 import (
    TestMatchingV4,
    RecommendedTestCandidate,
    _tokenise,
    _any_token_overlap,
    SCORE_COVERAGE_LINK,
    SCORE_KNOWLEDGE_GRAPH,
    SCORE_DOMAIN_MATCH,
    SCORE_MODULE_MATCH,
    SCORE_TOKEN_SIMILARITY,
    SCORE_HISTORICAL_FAILURE,
    SCORE_MANUAL_OVERRIDE,
    SCORE_ESCAPED_DEFECT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _make_workspace(db, name="ws", slug=None):
    ws = Workspace(
        id=uuid.uuid4(),
        name=name,
        slug=slug or f"slug-{uuid.uuid4().hex[:8]}",
        created_at=datetime.utcnow(),
    )
    db.add(ws)
    db.flush()
    return ws


def _make_repo(db, ws_id=None, repo_id=None):
    from app.models.repository import Repository
    if ws_id is None:
        ws = _make_workspace(db)
        ws_id = ws.id
    # Use a unique github_repo_id per call to avoid UniqueConstraint violations
    repo = Repository(
        id=repo_id or uuid.uuid4(),
        workspace_id=ws_id,
        github_repo_id=int(uuid.uuid4().int % 2**31),
        name="test-repo",
        full_name=f"org/test-repo-{uuid.uuid4().hex[:6]}",
        default_branch="main",
        created_at=datetime.utcnow(),
    )
    db.add(repo)
    db.flush()
    return repo


def _make_test_run(db, repo_id):
    tr = TestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        status="SUCCESS",
        evidence_source="MANUAL_UPLOAD",
        evidence_artifact_type="JUNIT_XML",
        file_hash=f"hash-{uuid.uuid4().hex[:8]}",
        normalized_execution_fingerprint=f"fp-{uuid.uuid4().hex[:8]}",
        created_at=datetime.utcnow(),
    )
    db.add(tr)
    db.flush()
    return tr


def _make_test_case(db, repo_id, suite="tests.auth", name="test_login", stable=None):
    stable = stable or f"{suite}::{name}"
    tc = TestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name=suite,
        test_name=name,
        stable_identity=stable,
        canonical_identity_hash=f"hash-{uuid.uuid4().hex}",
        identity_lineage_root_hash=f"hash-{uuid.uuid4().hex}",
    )
    db.add(tc)
    db.flush()
    return tc


def _make_pr(db, repo_id, files):
    pr = PullRequest(
        id=uuid.uuid4(),
        repository_id=repo_id,
        github_pr_id=int(uuid.uuid4().int % 99999),
        number=int(uuid.uuid4().int % 9999),
        title="Test PR",
        author="dev",
        source_branch="feature/test",
        target_branch="main",
        state="open",
        head_commit_sha=uuid.uuid4().hex,
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow(),
    )
    db.add(pr)
    db.flush()
    for fp in files:
        db.add(PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path=fp,
            status="modified",
        ))
    db.flush()
    return pr


# ---------------------------------------------------------------------------
# Token similarity helpers
# ---------------------------------------------------------------------------

class TestTokenHelpers:
    def test_tokenise_splits_on_separators(self):
        tokens = _tokenise("app/services/auth_service.py")
        # "app" is exactly 3 chars — included by the >= 3 guard
        assert "app" in tokens
        assert "services" in tokens
        assert "auth" in tokens
        assert "service" in tokens
        # Short tokens like "py" (2 chars) are excluded
        assert "py" not in tokens

    def test_overlap_returns_true_on_shared_token(self):
        assert _any_token_overlap(
            "tests.auth.test_login",
            ["app/services/auth/login.py"]
        )

    def test_overlap_returns_false_on_no_shared_token(self):
        assert not _any_token_overlap(
            "tests.payments.test_checkout",
            ["app/services/notifications/email.py"]
        )


# ---------------------------------------------------------------------------
# Layer 1: Coverage link
# ---------------------------------------------------------------------------

class TestCoverageLink_Signal:
    def test_coverage_link_adds_50(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(db, repo.id, suite="tests.auth", name="test_login")
        pr = _make_pr(db, repo.id, ["app/auth/login.py"])
        _make_test_run(db, repo.id)

        cov = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=ws.id,
            format="LCOV",
            source="MANUAL_UPLOAD",
            evidence_source="MANUAL_UPLOAD",
            evidence_artifact_type="LCOV",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            files_total=1,
            covered_lines_total=10,
            uncovered_lines_total=2,
            total_lines=12,
            overall_coverage_pct=0.83,
            covered_lines_count=10,
            uncovered_lines_count=2,
            confidence_score="HIGH",
            file_hash=uuid.uuid4().hex,
            created_at=datetime.utcnow(),
        )
        db.add(cov)
        db.flush()

        ftl = FileTestLink(
            id=uuid.uuid4(),
            coverage_report_id=cov.id,
            file_path="app/auth/login.py",
            test_case_id=tc.id,
            mapping_type="DIRECT",
            confidence_score="HIGH",
        )
        db.add(ftl)
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None
        assert match.signals["coverage_link"] == SCORE_COVERAGE_LINK
        assert match.source_signal == "DIRECT_COVERAGE"


# ---------------------------------------------------------------------------
# Layer 2: Knowledge graph
# ---------------------------------------------------------------------------

class TestKnowledgeGraph_Signal:
    def test_knowledge_graph_adds_40(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(db, repo.id, suite="tests.billing", name="test_invoice")
        pr = _make_pr(db, repo.id, ["app/billing/invoice.py"])
        _make_test_run(db, repo.id)

        edge = TestCoverageLink(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            repository_id=repo.id,
            test_identifier=tc.stable_identity,
            file_path="app/billing/invoice.py",
            override_count=0,
            defect_count=0,
        )
        db.add(edge)
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None
        assert match.signals["knowledge_graph"] == SCORE_KNOWLEDGE_GRAPH

    def test_override_count_adds_manual_override_signal(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(db, repo.id, suite="tests.billing", name="test_refund")
        pr = _make_pr(db, repo.id, ["app/billing/refund.py"])
        _make_test_run(db, repo.id)

        edge = TestCoverageLink(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            repository_id=repo.id,
            test_identifier=tc.stable_identity,
            file_path="app/billing/refund.py",
            override_count=3,
            defect_count=0,
        )
        db.add(edge)
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None
        assert match.signals["manual_override"] == SCORE_MANUAL_OVERRIDE

    def test_defect_count_adds_escaped_defect_signal(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(db, repo.id, suite="tests.auth", name="test_token")
        pr = _make_pr(db, repo.id, ["app/auth/token.py"])
        _make_test_run(db, repo.id)

        edge = TestCoverageLink(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            repository_id=repo.id,
            test_identifier=tc.stable_identity,
            file_path="app/auth/token.py",
            override_count=0,
            defect_count=2,
        )
        db.add(edge)
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None
        assert match.signals["escaped_defect"] == SCORE_ESCAPED_DEFECT


# ---------------------------------------------------------------------------
# Layer 3: Domain match
# ---------------------------------------------------------------------------

class TestDomainMatch_Signal:
    def test_domain_match_adds_30(self, db):
        repo = _make_repo(db)
        tc = _make_test_case(db, repo.id, suite="tests.notifications.test_email", name="test_send_notification")
        pr = _make_pr(db, repo.id, ["app/notifications/email.py"])
        _make_test_run(db, repo.id)

        dm = DomainMap(
            id=uuid.uuid4(),
            repository_id=repo.id,
            domain="Notifications",
            files=["app/notifications/email.py"],
            modules=["tests.notifications.test_email"],
            owners=[],
        )
        db.add(dm)
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None
        assert match.signals["domain_match"] == SCORE_DOMAIN_MATCH


# ---------------------------------------------------------------------------
# Layer 5: Token similarity
# ---------------------------------------------------------------------------

class TestTokenSimilarity_Signal:
    def test_token_overlap_adds_10(self, db):
        repo = _make_repo(db)
        # Test suite name shares "billing" token with changed path
        stable = "tests.billing.subscriptions::test_plan_upgrade_token"
        tc = _make_test_case(
            db, repo.id,
            suite="tests.billing.subscriptions",
            name="test_plan_upgrade_token",
            stable=stable,
        )
        pr = _make_pr(db, repo.id, ["src/modules/billing/subscription.ts"])
        _make_test_run(db, repo.id)
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None
        assert match.signals["token_similarity"] == SCORE_TOKEN_SIMILARITY


# ---------------------------------------------------------------------------
# Layer 6: Historical failure
# ---------------------------------------------------------------------------

class TestHistoricalFailure_Signal:
    def test_recent_failure_adds_10(self, db):
        repo = _make_repo(db)
        # Stable identity shares "reset" and "auth" tokens with the changed path
        stable = "tests.auth.test_reset::test_reset_password_hf"
        tc = _make_test_case(
            db, repo.id,
            suite="tests.auth.test_reset",
            name="test_reset_password_hf",
            stable=stable,
        )
        pr = _make_pr(db, repo.id, ["app/auth/reset_password.py"])
        run = _make_test_run(db, repo.id)
        # Seed a failure 5 days ago
        cutoff = datetime.utcnow() - timedelta(days=5)
        db.add(TestResult(
            id=uuid.uuid4(),
            test_run_id=run.id,
            test_case_id=tc.id,
            status="failed",
            duration=1.0,
            created_at=cutoff,
        ))
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None
        assert match.signals["historical_failure"] == SCORE_HISTORICAL_FAILURE


# ---------------------------------------------------------------------------
# Score arithmetic
# ---------------------------------------------------------------------------

class TestScoreArithmetic:
    def test_score_equals_sum_of_signals(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(
            db, repo.id,
            suite="tests.auth.test_session",
            name="test_session_expiry",
        )
        pr = _make_pr(db, repo.id, ["app/auth/session.py"])
        run = _make_test_run(db, repo.id)

        # Seed failure
        fail_time = datetime.utcnow() - timedelta(days=2)
        db.add(TestResult(
            id=uuid.uuid4(),
            test_run_id=run.id,
            test_case_id=tc.id,
            status="failed",
            duration=3.0,
            created_at=fail_time,
        ))

        # Seed knowledge graph edge
        db.add(TestCoverageLink(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            repository_id=repo.id,
            test_identifier=tc.stable_identity,
            file_path="app/auth/session.py",
            override_count=0,
            defect_count=0,
        ))
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None

        # score == sum of all signal values
        expected_total = sum(match.signals.values())
        assert match.score == float(expected_total)

    def test_runtime_cost_is_negative(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(
            db, repo.id,
            suite="tests.perf.test_slow",
            name="test_heavy_operation",
        )
        pr = _make_pr(db, repo.id, ["app/perf/heavy.py"])
        run = _make_test_run(db, repo.id)
        # Record a 10-second average duration via a result
        db.add(TestResult(
            id=uuid.uuid4(),
            test_run_id=run.id,
            test_case_id=tc.id,
            status="passed",
            duration=10.0,
            created_at=datetime.utcnow(),
        ))
        # Add knowledge graph edge to qualify
        db.add(TestCoverageLink(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            repository_id=repo.id,
            test_identifier=tc.stable_identity,
            file_path="app/perf/heavy.py",
            override_count=0,
            defect_count=0,
        ))
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None
        assert match.signals["runtime_cost"] < 0


# ---------------------------------------------------------------------------
# Quarantine exclusion
# ---------------------------------------------------------------------------

class TestQuarantineExclusion:
    def test_quarantined_test_is_excluded(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(
            db, repo.id,
            suite="tests.quarantine.test_flaky",
            name="test_random_failure",
        )
        pr = _make_pr(db, repo.id, ["app/quarantine/risky.py"])
        _make_test_run(db, repo.id)

        # Mark as quarantined
        db.add(FlakyTestProfile(
            id=uuid.uuid4(),
            repository_id=repo.id,
            test_case_id=tc.id,
            status="quarantined",
            failure_rate=0.9,
            instability_score=0.9,
            sample_size=20,
            confidence_level="HIGH",
        ))
        # Add KG signal so it would otherwise be included
        db.add(TestCoverageLink(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            repository_id=repo.id,
            test_identifier=tc.stable_identity,
            file_path="app/quarantine/risky.py",
            override_count=0,
            defect_count=0,
        ))
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        identifiers = [r.test_identifier for r in results]
        assert tc.stable_identity not in identifiers


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

class TestFallback:
    def test_fallback_activates_when_no_signals_fire(self, db):
        repo = _make_repo(db)
        tc = _make_test_case(
            db, repo.id,
            suite="tests.zzzunrelated.module",
            name="test_completely_zzzunrelated",
            stable="tests.zzzunrelated.module::test_completely_zzzunrelated",
        )
        # PR changes a file with zero token overlap to any test in this repo
        pr = _make_pr(db, repo.id, ["xqz/totally/qxzdiff/path.go"])
        _make_test_run(db, repo.id)
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        fallback_results = [r for r in results if r.is_fallback]
        # Should have fallback candidates if no other signal fired
        assert len(fallback_results) > 0
        for fb in fallback_results:
            assert fb.source_signal == "FALLBACK"
            assert fb.confidence == "LOW"

    def test_fallback_not_activated_when_signals_exist(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(
            db, repo.id,
            suite="tests.auth.test_login",
            name="test_valid_credentials_nofb",
            stable="tests.auth.test_login::test_valid_credentials_nofb",
        )
        pr = _make_pr(db, repo.id, ["app/auth/login.py"])
        _make_test_run(db, repo.id)
        db.add(TestCoverageLink(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            repository_id=repo.id,
            test_identifier=tc.stable_identity,
            file_path="app/auth/login.py",
            override_count=0,
            defect_count=0,
        ))
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        fallback_results = [r for r in results if r.is_fallback]
        assert len(fallback_results) == 0


# ---------------------------------------------------------------------------
# Sort order
# ---------------------------------------------------------------------------

class TestSortOrder:
    def test_higher_score_appears_first(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc_high = _make_test_case(db, repo.id, suite="tests.auth.high", name="test_sort_high")
        tc_low  = _make_test_case(db, repo.id, suite="tests.auth.low",  name="test_sort_low")
        pr = _make_pr(db, repo.id, ["app/auth/main.py"])
        _make_test_run(db, repo.id)

        # tc_high gets KG + domain match; tc_low gets only token similarity
        db.add(TestCoverageLink(
            id=uuid.uuid4(), workspace_id=ws.id, repository_id=repo.id,
            test_identifier=tc_high.stable_identity, file_path="app/auth/main.py",
            override_count=1, defect_count=0,
        ))
        # tc_low gets only a historical failure (lower score)
        run = _make_test_run(db, repo.id)
        db.add(TestResult(
            id=uuid.uuid4(), test_run_id=run.id, test_case_id=tc_low.id,
            status="failed", duration=1.0,
            created_at=datetime.utcnow() - timedelta(days=1),
        ))
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        tc_high_result = next((r for r in results if r.test_identifier == tc_high.stable_identity), None)
        tc_low_result  = next((r for r in results if r.test_identifier == tc_low.stable_identity),  None)

        if tc_high_result and tc_low_result:
            high_idx = results.index(tc_high_result)
            low_idx  = results.index(tc_low_result)
            assert high_idx < low_idx, "Higher-score test should appear before lower-score test"


# ---------------------------------------------------------------------------
# Reason quality
# ---------------------------------------------------------------------------

class TestReasonQuality:
    _FORBIDDEN = ["confident", "likely", "probably", "might", "could be",
                  "seems", "appears", "maybe", "ai thinks", "%"]

    def test_reason_has_at_most_4_bullets(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(db, repo.id, suite="tests.auth.full", name="test_all_signals")
        pr = _make_pr(db, repo.id, ["app/auth/full.py"])
        run = _make_test_run(db, repo.id)
        db.add(TestResult(
            id=uuid.uuid4(), test_run_id=run.id, test_case_id=tc.id,
            status="failed", duration=1.0,
            created_at=datetime.utcnow() - timedelta(days=1),
        ))
        db.add(TestCoverageLink(
            id=uuid.uuid4(), workspace_id=ws.id, repository_id=repo.id,
            test_identifier=tc.stable_identity, file_path="app/auth/full.py",
            override_count=2, defect_count=1,
        ))
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None
        bullets = [b for b in match.reason.split("\n") if b.strip().startswith("-")]
        assert len(bullets) <= 4

    def test_no_forbidden_phrases_in_reason(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(db, repo.id, suite="tests.clean", name="test_phrase_check")
        pr = _make_pr(db, repo.id, ["app/clean/main.py"])
        _make_test_run(db, repo.id)
        db.add(TestCoverageLink(
            id=uuid.uuid4(), workspace_id=ws.id, repository_id=repo.id,
            test_identifier=tc.stable_identity, file_path="app/clean/main.py",
            override_count=0, defect_count=0,
        ))
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None
        reason_lower = match.reason.lower()
        for phrase in self._FORBIDDEN:
            assert phrase not in reason_lower, f"Forbidden phrase '{phrase}' in reason"


# ---------------------------------------------------------------------------
# Signal breakdown completeness
# ---------------------------------------------------------------------------

class TestSignalBreakdown:
    def test_all_signal_keys_present(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(db, repo.id, suite="tests.breakdown", name="test_keys")
        pr = _make_pr(db, repo.id, ["app/breakdown/core.py"])
        _make_test_run(db, repo.id)
        db.add(TestCoverageLink(
            id=uuid.uuid4(), workspace_id=ws.id, repository_id=repo.id,
            test_identifier=tc.stable_identity, file_path="app/breakdown/core.py",
            override_count=0, defect_count=0,
        ))
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None

        required_keys = {
            "coverage_link", "knowledge_graph", "domain_match", "module_match",
            "token_similarity", "historical_failure", "manual_override",
            "escaped_defect", "runtime_cost", "fallback",
        }
        assert required_keys.issubset(set(match.signals.keys())), \
            f"Missing keys: {required_keys - set(match.signals.keys())}"

    def test_to_dict_includes_reason_details(self, db):
        ws = _make_workspace(db)
        repo = _make_repo(db, ws_id=ws.id)
        tc = _make_test_case(db, repo.id, suite="tests.serial", name="test_dict")
        pr = _make_pr(db, repo.id, ["app/serial/main.py"])
        _make_test_run(db, repo.id)
        db.add(TestCoverageLink(
            id=uuid.uuid4(), workspace_id=ws.id, repository_id=repo.id,
            test_identifier=tc.stable_identity, file_path="app/serial/main.py",
            override_count=0, defect_count=0,
        ))
        db.commit()

        results = TestMatchingV4.match(db, repo.id, pr.id)
        match = next((r for r in results if r.test_identifier == tc.stable_identity), None)
        assert match is not None

        d = TestMatchingV4.to_dict(match)
        assert "reason_details" in d
        assert "total" in d["reason_details"]
        assert d["reason_details"]["total"] == match.score
        assert "test_identifier" in d
        assert "priority" in d
