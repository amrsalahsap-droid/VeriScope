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
from app.models.pull_request import PullRequest
from app.models.recommendation import RecommendationRun, RecommendedTest
from app.models.user import Workspace
from app.services.intelligence_report_generator import IntelligenceReportGenerator


@pytest.fixture(scope="module")
def engine():
    # SQLite memory engine
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    
    # Create all tables using SQLAlchemy metadata
    Base.metadata.create_all(bind=eng)
    
    yield eng
    
    # Clean up all tables
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


def test_intelligence_report_generation_high_evidence(db):
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    run_id = uuid.uuid4()

    # Seed Workspace and Repository
    workspace = Workspace(id=workspace_id, name="Test Space", slug="test-space-intel")
    db.add(workspace)
    db.flush()

    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=12345,
        name="test-repo-intel",
        full_name="test-org/test-repo-intel",
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
        github_pr_id=12345,
        number=42,
        title="Reset password security validation",
        author="test-author",
        source_branch="feat",
        target_branch="main",
        state="open",
        head_commit_sha="eeddccbbaa00112233445566778899aa",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)
    db.flush()

    # Seed Recommendation Run with high evidence quality and impact profile
    impact_profile = {
        "impact_summary": "Password validation workflow modification.",
        "affected_domains": ["auth", "users"],
        "risk_categories": ["auth", "security"],
        "recommended_testing_types": ["security", "integration", "regression"]
    }

    run = RecommendationRun(
        id=run_id,
        repository_id=repo_id,
        pr_id="42",
        triggered_by="github-webhook",
        evidence_quality="HIGH",
        engine_version="v3",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="Tested with HIGH confidence coverage link",
        pull_request_id=pr.id,
        risk_level="HIGH",
        impact_profile=impact_profile,
        created_at=datetime.utcnow()
    )
    db.add(run)
    db.flush()

    # Seed Recommended Tests:
    # 3 Must Run tests (priority >= 0.80)
    # 2 Should Run tests (priority < 0.80)
    tests = [
        RecommendedTest(
            id=uuid.uuid4(),
            recommendation_run_id=run_id,
            test_identifier="auth.validation::test_password_strength",
            test_name="test_password_strength",
            class_name="auth.validation",
            priority=0.95,
            confidence="HIGH",
            reason="Covers critical security logic",
            source_signal="DIRECT_COVERAGE"
        ),
        RecommendedTest(
            id=uuid.uuid4(),
            recommendation_run_id=run_id,
            test_identifier="auth.validation::test_reset_token",
            test_name="test_reset_token",
            class_name="auth.validation",
            priority=0.88,
            confidence="HIGH",
            reason="Covers token generation",
            source_signal="TEST_COVERAGE_GRAPH"
        ),
        RecommendedTest(
            id=uuid.uuid4(),
            recommendation_run_id=run_id,
            test_identifier="auth.validation::test_expiry",
            test_name="test_expiry",
            class_name="auth.validation",
            priority=0.80,
            confidence="HIGH",
            reason="Covers expiry logic",
            source_signal="HISTORICAL_FAILURE"
        ),
        RecommendedTest(
            id=uuid.uuid4(),
            recommendation_run_id=run_id,
            test_identifier="users.profile::test_profile_update",
            test_name="test_profile_update",
            class_name="users.profile",
            priority=0.72,
            confidence="MEDIUM",
            reason="Covers user profiles",
            source_signal="DOMAIN_MATCH"
        ),
        RecommendedTest(
            id=uuid.uuid4(),
            recommendation_run_id=run_id,
            test_identifier="shared.utils::test_hashing",
            test_name="test_hashing",
            class_name="shared.utils",
            priority=0.65,
            confidence="MEDIUM",
            reason="Covers common hashing",
            source_signal="ARCHITECTURAL_IMPACT"
        ),
    ]
    for t in tests:
        db.add(t)
    db.commit()

    # Generate Report
    report = IntelligenceReportGenerator.generate_report(db, run_id)

    # 1. Verify Structured Report Data
    assert report["run_id"] == str(run_id)
    assert "Reset password security validation" in report["change_summary"]
    assert "Password validation workflow modification." in report["change_summary"]
    assert report["affected_domains"] == ["Auth", "Users"]
    assert report["risk_level"] == "High"
    assert report["risk_categories"] == ["Auth", "Security"]
    assert report["recommended_testing_types"] == ["INTEGRATION", "REGRESSION", "SECURITY"]
    assert report["must_run_count"] == 3
    assert report["should_run_count"] == 2
    # Verify mapped evidence sources
    # DIRECT_COVERAGE -> Coverage
    # TEST_COVERAGE_GRAPH -> Knowledge Graph
    # HISTORICAL_FAILURE -> Historical Failures
    # DOMAIN_MATCH -> Domain Map
    # ARCHITECTURAL_IMPACT -> Architectural Impact
    assert set(report["evidence_sources"]) == {
        "Coverage",
        "Knowledge Graph",
        "Historical Failures",
        "Domain Map",
        "Architectural Impact"
    }
    assert "High confidence is assigned based on complete code coverage mapping" in report["confidence_explanation"]

    # 2. Verify Markdown Rendering
    md = IntelligenceReportGenerator.render_as_markdown(report)
    assert "# Veriscope Scoping Intelligence Report" in md
    assert "### Change Summary" in md
    assert "Reset password security validation" in md
    assert "### Affected Domains\n- Auth\n- Users" in md
    assert "### Risk Areas\n- **Risk Level**: High (Auth, Security)" in md
    assert "### Recommended Testing Types\n- INTEGRATION\n- REGRESSION\n- SECURITY" in md
    assert "### Recommended Tests\n- **Must Run**: 3 tests\n- **Should Run**: 2 tests" in md
    assert "### Evidence Sources" in md
    assert "- Coverage" in md
    assert "- Knowledge Graph" in md
    assert "- Historical Failures" in md
    assert "### Confidence Explanation" in md

    # 3. Verify HTML Rendering
    html = IntelligenceReportGenerator.render_as_html(report)
    assert "<div class='veriscope-intelligence-report'" in html
    assert "Veriscope Scoping Intelligence Report" in html
    assert "Change Summary" in html
    assert "Reset password security validation" in html
    assert "Risk Level: <span style='font-weight: 600; color: #ef4444;'>High</span> (Auth, Security)" in html
    assert "Must Run: <strong>3</strong>" in html
    assert "Should Run: <strong>2</strong>" in html
    assert "Confidence Explanation" in html
    assert "High confidence is assigned" in html


def test_intelligence_report_low_evidence_fallback(db):
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    run_id = uuid.uuid4()

    # Seed Workspace and Repository
    workspace = Workspace(id=workspace_id, name="Test Space 2", slug="test-space-fallback")
    db.add(workspace)
    db.flush()

    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=12346,
        name="test-repo-fallback",
        full_name="test-org/test-repo-fallback",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)
    db.flush()

    # Seed Recommendation Run with LOW evidence and empty impact profile
    run = RecommendationRun(
        id=run_id,
        repository_id=repo_id,
        pr_id="99",
        triggered_by="github-webhook",
        evidence_quality="LOW",
        engine_version="v3",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="Pipeline fallback triggered due to missing coverage",
        pull_request_id=None,  # No PR relationship
        risk_level="LOW",
        impact_profile=None,  # No impact profile
        created_at=datetime.utcnow()
    )
    db.add(run)
    db.flush()

    # Seed 1 test (Should Run)
    t = RecommendedTest(
        id=uuid.uuid4(),
        recommendation_run_id=run_id,
        test_identifier="fallback.test::test_fallback",
        test_name="test_fallback",
        class_name="fallback.test",
        priority=0.45,
        confidence="LOW",
        reason="Selected by historical fallback",
        source_signal="HISTORICAL_FAILURE"
    )
    db.add(t)
    db.commit()

    # Generate Report
    report = IntelligenceReportGenerator.generate_report(db, run_id)

    assert report["change_summary"] == "Pipeline fallback triggered due to missing coverage"
    assert report["affected_domains"] == ["General"]
    assert report["risk_level"] == "Low"
    assert report["risk_categories"] == []
    assert report["recommended_testing_types"] == ["REGRESSION", "UNIT"]
    assert report["must_run_count"] == 0
    assert report["should_run_count"] == 1
    assert report["evidence_sources"] == ["Historical Failures"]
    assert "Low confidence is assigned as targeted coverage evidence is sparse" in report["confidence_explanation"]


def test_intelligence_report_generator_not_found(db):
    with pytest.raises(ValueError, match="RecommendationRun with ID .* not found"):
        IntelligenceReportGenerator.generate_report(db, uuid.uuid4())
