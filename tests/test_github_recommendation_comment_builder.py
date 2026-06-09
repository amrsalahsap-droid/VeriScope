import uuid
from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

# SQLite compilation helper for PostgreSQL JSONB columns
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

from app.db.base import Base
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.recommendation import RecommendationRun, RecommendedTest, RecommendationExplanation
from app.models.user import Workspace
from app.services.recommendation_report_generator import RecommendationReportGenerator
from app.services.github_recommendation_comment_builder import GitHubRecommendationCommentBuilder
from app.services.pr_comment_service import PRCommentService


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


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


def test_mock_report_comment_building():
    """Verify that build_comment correctly parses a report structure and formats it with all 6 required sections."""
    report = {
        "run_id": str(uuid.uuid4()),
        "change_summary": "Update token parsing middleware logic and credit card billing checkout workflow",
        "changed_files": ["src/auth/token.py", "src/billing/checkout.py"],
        "affected_domains": ["Auth", "Billing"],
        "affected_journeys": [
            {"journey": "Login", "severity": "HIGH", "reason": "Modifies core JWT security filters."},
            {"journey": "Checkout", "severity": "MODERATE", "reason": "Alters payments callback logic."}
        ],
        "risk_level": "HIGH",
        "risk_categories": ["Security", "Payments"],
        "testing_scope": {
            "must_test": [{"category": "Security", "item": "src/auth/token.py"}],
            "should_test": [{"category": "Payments", "item": "src/billing/checkout.py"}],
            "optional": []
        },
        "recommended_testing_types": ["SECURITY", "REGRESSION"],
        "recommended_tests": {
            "must_run": [
                {
                    "stable_identity": "tests.auth::test_token_generation",
                    "display_name": "test_token_generation",
                    "priority": 0.95,
                    "reason": "Directly covers JWT generation",
                    "source_signal": "DIRECT_COVERAGE"
                }
            ],
            "should_run": [
                {
                    "stable_identity": "tests.billing::test_checkout_charge",
                    "display_name": "test_checkout_charge",
                    "priority": 0.70,
                    "reason": "Indirectly triggers charge flow",
                    "source_signal": "TEST_COVERAGE_GRAPH"
                }
            ],
            "total_count": 2
        },
        "missing_coverage": [
            {
                "domain": "Auth",
                "feature": "AdminLockout",
                "reason": "No unit tests cover admin brute force security policies"
            }
        ],
        "evidence_gaps": [],
        "confidence_breakdown": {
            "score": 82,
            "tier": "STRONG",
            "breakdown": {
                "coverage_contribution": 0.50,
                "graph_contribution": 0.50,
                "domain_contribution": 0.0,
                "fallback_ratio": 0.0,
                "evidence_completeness": 1.00
            }
        }
    }

    class MockRun:
        evidence_quality = "HIGH"
        estimated_runtime_seconds = 14.5
        full_suite_runtime_seconds = 145.0

    comment = GitHubRecommendationCommentBuilder.build_comment(report, run=MockRun())

    # Assert comment is formatted with all 6 required sections
    assert "### 📋 Summary" in comment
    assert "### ⚠️ Risk" in comment
    assert "### 🎯 Testing Scope" in comment
    assert "### 🧪 Recommended Tests (2)" in comment
    assert "### 🛑 Missing Coverage" in comment
    assert "### 📊 Evidence Quality" in comment

    # Check Summary section details
    assert "Update token parsing middleware logic and credit card billing checkout workflow." in comment
    assert "touched `2` file(s) across `2` domain(s)" in comment
    assert "`14.5s`" in comment
    assert "`145.0s`" in comment

    # Check Risk section details
    assert "🔴 **HIGH**." in comment
    assert "`Security`, `Payments`" in comment

    # Check Testing Scope section details
    assert "**Must Test**: `Security: src/auth/token.py`." in comment
    assert "**Should Test**: `Payments: src/billing/checkout.py`." in comment
    assert "**Optional**: None." in comment

    # Check Recommended Tests section details (table format)
    assert "| Test Name | Priority | Source Signal | Reason |" in comment
    assert "|---|---|---|---|" in comment
    assert "| `test_token_generation` | 0.95 | `DIRECT_COVERAGE` | Directly covers JWT generation. |" in comment
    assert "| `test_checkout_charge` | 0.7 | `TEST_COVERAGE_GRAPH` | Indirectly triggers charge flow. |" in comment

    # Check Missing Coverage details
    assert "- **Auth** (Feature: `AdminLockout`): No unit tests cover admin brute force security policies." in comment

    # Check Evidence Quality details
    assert "**Overall Quality Score**: `82/100` (Tier: **STRONG**)." in comment
    assert "Direct Coverage Contribution: `50.0%`." in comment
    assert "Knowledge Graph Contribution: `50.0%`." in comment
    assert "Fallback Ratio (History): `0.0%`." in comment
    assert "Evidence Completeness: `100.0%`." in comment
    # Wilson interval successes=2, total=2, 95% confidence bounds
    assert "Statistical Trust Bounds (95% Wilson Score)" in comment
    assert "34.2%" in comment  # Wilson score lower bound is ~34.2% for x=2, n=2, 95% z=1.95996
    assert "100.0%" in comment  # upper bound is 100%


def test_empty_recommended_tests_comment():
    """Verify comment builder output when no tests are recommended and coverage has gaps."""
    report = {
        "run_id": str(uuid.uuid4()),
        "change_summary": "Minor config documentation update",
        "changed_files": ["docs/config.md"],
        "affected_domains": ["General"],
        "affected_journeys": [],
        "risk_level": "LOW",
        "risk_categories": [],
        "testing_scope": {
            "must_test": [],
            "should_test": [],
            "optional": []
        },
        "recommended_testing_types": [],
        "recommended_tests": {
            "must_run": [],
            "should_run": [],
            "total_count": 0
        },
        "missing_coverage": [],
        "evidence_gaps": [],
        "confidence_breakdown": {
            "score": 0,
            "tier": "POOR",
            "breakdown": {
                "coverage_contribution": 0.0,
                "graph_contribution": 0.0,
                "domain_contribution": 0.0,
                "fallback_ratio": 0.0,
                "evidence_completeness": 0.0
            }
        }
    }

    comment = GitHubRecommendationCommentBuilder.build_comment(report, run=None)

    assert "### 📋 Summary" in comment
    assert "Minor config documentation update." in comment
    assert "### ⚠️ Risk" in comment
    assert "🟢 **LOW**." in comment
    assert "### 🎯 Testing Scope" in comment
    assert "**Must Test**: None." in comment
    assert "**Should Test**: None." in comment
    assert "**Optional**: None." in comment
    assert "### 🧪 Recommended Tests (0)" in comment
    assert "No tests recommended." in comment
    assert "### 🛑 Missing Coverage" in comment
    assert "- No critical coverage gaps detected in modified directories." in comment
    assert "### 📊 Evidence Quality" in comment
    assert "**Overall Quality Score**: `0/100` (Tier: **POOR**)." in comment
    assert "- **Statistical Trust Bounds (95% Wilson Score)**: [`0.0%`, `0.0%`]." in comment


def test_pr_comment_service_full_integration(db):
    """Verify integration between RecommendationReportGenerator, GitHubRecommendationCommentBuilder, and PRCommentService."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    run_id = uuid.uuid4()

    # Seed Workspace and Repository
    workspace = Workspace(id=workspace_id, name="Test Space", slug="test-space")
    db.add(workspace)
    db.flush()

    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=98765,
        name="test-repo",
        full_name="org/test-repo",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)
    db.flush()

    # Seed Pull Request
    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=98765,
        number=102,
        title="Upgrade auth subsystem and database adapter",
        author="test-engineer",
        source_branch="feat/auth-db",
        target_branch="main",
        state="open",
        head_commit_sha="11223344556677889900aabbccddee00",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)
    db.flush()

    cf = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/auth/login.py",
        status="modified"
    )
    db.add(cf)
    db.flush()

    # Seed Recommendation Run
    impact_profile = {
        "impact_summary": "Update credential matching security protocols.",
        "affected_domains": ["auth"],
        "risk_categories": ["auth", "security"],
        "recommended_testing_types": ["security", "regression"]
    }

    run = RecommendationRun(
        id=run_id,
        repository_id=repo_id,
        pr_id="102",
        triggered_by="github-webhook",
        evidence_quality="HIGH",
        engine_version="v3",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="Tested with direct security and login credentials coverage",
        pull_request_id=pr_id,
        risk_level="HIGH",
        impact_profile=impact_profile,
        estimated_runtime_seconds=5.5,
        full_suite_runtime_seconds=55.0,
        created_at=datetime.utcnow()
    )
    db.add(run)
    db.flush()

    # Seed Recommended Tests
    t = RecommendedTest(
        id=uuid.uuid4(),
        recommendation_run_id=run_id,
        test_identifier="tests.auth::test_login_success",
        test_name="test_login_success",
        class_name="tests.auth",
        priority=0.92,
        confidence="HIGH",
        reason="Covers auth login matching flow",
        source_signal="DIRECT_COVERAGE"
    )
    db.add(t)
    db.flush()

    db.commit()

    # Render comment using PRCommentService
    service = PRCommentService(db)
    comment = service.render_comment(run)

    # Verify report-based comment rendering via PRCommentService.render_comment
    assert "## 🔍 Veriscope Scoping Intelligence Report" in comment
    assert "### 📋 Summary" in comment
    assert "Upgrade auth subsystem and database adapter" in comment
    assert "`5.5s`" in comment
    assert "### ⚠️ Risk" in comment
    assert "🔴 **HIGH**." in comment
    assert "### 🎯 Testing Scope" in comment
    assert "### 🧪 Recommended Tests (1)" in comment
    assert "`test_login_success`" in comment
    assert "### 🛑 Missing Coverage" in comment
    assert "### 📊 Evidence Quality" in comment
    assert "<!-- veriscope-pr-comment -->" in comment
