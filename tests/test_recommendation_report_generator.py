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


def test_recommendation_report_generation_full(db):
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    run_id = uuid.uuid4()

    # Seed Workspace and Repository
    workspace = Workspace(id=workspace_id, name="Corporate Space", slug="corp-space")
    db.add(workspace)
    db.flush()

    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=98765,
        name="finance-core",
        full_name="org/finance-core",
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
        number=101,
        title="Upgrade JWT auth token middleware and billing checks",
        author="lead-engineer",
        source_branch="feat/auth-billing",
        target_branch="main",
        state="open",
        head_commit_sha="aabbccddee0011223344556677889900",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)
    db.flush()

    cf1 = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/auth/token.py",
        status="modified"
    )
    cf2 = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/billing/checkout.py",
        status="modified"
    )
    db.add(cf1)
    db.add(cf2)
    db.flush()

    # Seed Recommendation Run
    impact_profile = {
        "impact_summary": "Core authentication and billing checkout upgrades.",
        "affected_domains": ["auth", "billing"],
        "risk_categories": ["auth", "billing", "security", "payments"],
        "recommended_testing_types": ["security", "integration", "regression"]
    }

    run = RecommendationRun(
        id=run_id,
        repository_id=repo_id,
        pr_id="101",
        triggered_by="github-webhook",
        evidence_quality="HIGH",
        engine_version="v3",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="Tested with direct security and payments coverage",
        pull_request_id=pr_id,
        risk_level="HIGH",
        impact_profile=impact_profile,
        created_at=datetime.utcnow()
    )
    db.add(run)
    db.flush()

    # Seed Recommended Tests
    t1 = RecommendedTest(
        id=uuid.uuid4(),
        recommendation_run_id=run_id,
        test_identifier="tests.auth::test_token_generation",
        test_name="test_token_generation",
        class_name="tests.auth",
        priority=0.90,
        confidence="HIGH",
        reason="Directly covers token logic",
        source_signal="DIRECT_COVERAGE"
    )
    t2 = RecommendedTest(
        id=uuid.uuid4(),
        recommendation_run_id=run_id,
        test_identifier="tests.billing::test_checkout_charge",
        test_name="test_checkout_charge",
        class_name="tests.billing",
        priority=0.75,
        confidence="MEDIUM",
        reason="Covers payments integration",
        source_signal="TEST_COVERAGE_GRAPH"
    )
    db.add(t1)
    db.add(t2)
    db.flush()

    # Seed Explanation for Evidence Gaps
    exp = RecommendationExplanation(
        id=uuid.uuid4(),
        recommendation_run_id=run_id,
        test_id="tests.auth::test_token_generation",
        triggered_files=["src/auth/token.py"],
        domains=["auth"],
        testing_types=["security"],
        signals=["coverage match"],
        reason="Verifies security credentials",
        created_at=datetime.utcnow()
    )
    db.add(exp)
    db.commit()

    # 1. Generate Report
    report = RecommendationReportGenerator.generate_report(db, run_id)

    # Assert 9 sections exist
    assert report["run_id"] == str(run_id)
    # What Changed
    assert "Upgrade JWT auth token" in report["change_summary"]
    assert "src/auth/token.py" in report["changed_files"]
    # Impacted Domains
    assert "Auth" in report["affected_domains"]
    assert "Billing" in report["affected_domains"]
    # Affected User Journeys (from UserJourneyImpactEngine)
    assert any(j["journey"] == "Login" for j in report["affected_journeys"])
    assert any(j["journey"] == "Checkout" for j in report["affected_journeys"])
    # Risk Areas
    assert report["risk_level"] == "HIGH"
    assert "Security" in report["risk_categories"]
    # Testing Scope (from TestingScopeGenerator)
    assert any(s["category"] == "Security" for s in report["testing_scope"]["must_test"])
    # Recommended Tests
    assert len(report["recommended_tests"]["must_run"]) == 1
    assert len(report["recommended_tests"]["should_run"]) == 1
    assert report["recommended_tests"]["total_count"] == 2
    # Missing Coverage (from MissingCoverageAnalyzer)
    # Gaps should not be active since we have tests matching auth/billing
    assert isinstance(report["missing_coverage"], list)
    # Evidence Gaps (from EvidenceGapDetector)
    assert isinstance(report["evidence_gaps"], list)
    # Confidence Breakdown
    assert report["confidence_breakdown"]["score"] > 0
    assert report["confidence_breakdown"]["tier"] in ("STRONG", "GOOD", "FAIR")

    # 2. Verify UI Rendering
    ui = RecommendationReportGenerator.render_as_ui(report)
    assert "report" in ui
    assert "html" in ui
    html = ui["html"]
    assert "Regression Scoping Report" in html
    assert "Upgrade JWT auth token" in html
    assert "Login" in html
    assert "Checkout" in html
    assert "Quality Score" in html

    # 3. Verify Markdown Rendering
    md = RecommendationReportGenerator.render_as_github_comment(report)
    assert "## 🔍 Veriscope Scoping Intelligence Report" in md
    assert "Upgrade JWT auth token" in md
    assert "Login" in md
    assert "test_token_generation" in md
    assert "Quality Score" in md

    # 4. Verify PDF Rendering
    pdf = RecommendationReportGenerator.render_as_pdf(report)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-1.4")
    assert pdf.endswith(b"%%EOF\n")
    # Verify PDF contains drawn text sections
    assert b"VERISCOPE SCOPING" in pdf
    assert b"WHAT CHANGED" in pdf
    assert b"AFFECTED USER JOURNEYS" in pdf


def test_recommendation_report_not_found(db):
    with pytest.raises(ValueError, match="RecommendationRun with ID .* not found"):
        RecommendationReportGenerator.generate_report(db, uuid.uuid4())
