import uuid
from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

# Register SQLite compilation helpers for PostgreSQL-specific columns in tests
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"

from app.db.base import Base
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.recommendation import RecommendationRun
from app.models.user import Workspace
from app.models.project_context_index import ProjectContextIndex
from app.services.qa_lead_sme_analyzer import QALeadSMEAnalyzer
from app.services.recommendation import RecommendationService

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

def test_qa_lead_sme_analyzer_capabilities():
    """Verify QALeadSMEAnalyzer correctly identifies standard capabilities and produces structured QA scope."""
    product_impact = {
        "affected_capabilities": ["signup", "login"],
        "affected_user_journeys": [
            {"journey": "User Registration Flow", "source_file": "src/signup.py", "confidence": "HIGH"},
            {"journey": "User Authentication Flow", "source_file": "src/login.py", "confidence": "HIGH"}
        ],
        "business_impact_summary": "signup and login changed",
        "confidence": "HIGH",
        "evidence": []
    }

    result = QALeadSMEAnalyzer.analyze(
        product_impact=product_impact,
        risk_assessment="HIGH",
        changed_files=["src/signup.py", "src/login.py"],
        context_index=None,
        db=None,
        repository_id=None
    )

    assert len(result["must_test"]) > 0
    assert len(result["should_test"]) > 0
    assert len(result["optional_test"]) > 0
    assert len(result["negative_cases"]) > 0
    assert len(result["regression_areas"]) > 0
    
    # Assert that everything has expected fields
    for field in ["must_test", "should_test", "optional_test", "negative_cases"]:
        for item in result[field]:
            assert "scenario" in item
            assert "expected_result" in item
            assert "suggested_test_data" in item
            assert "is_automated" in item
            # By default, since no test is seeded, it must be False
            assert item["is_automated"] is False

    for item in result["regression_areas"]:
        assert "area" in item
        assert "description" in item
        assert "is_automated" in item
        assert item["is_automated"] is False

def test_qa_lead_sme_analyzer_is_automated_evaluation(db):
    """Verify is_automated flag is set dynamically and accurately based on DB tests or ProjectContextIndex."""
    repo_id = uuid.uuid4()
    
    # Context Index with test assets
    context_index = ProjectContextIndex(
        repository_id=repo_id,
        test_assets=[
            {"name": "test_signup.py", "source_files": ["tests/test_signup.py"]}
        ]
    )

    # 1. Test via ProjectContextIndex
    product_impact = {"affected_capabilities": ["signup"]}
    result = QALeadSMEAnalyzer.analyze(
        product_impact=product_impact,
        risk_assessment="LOW",
        changed_files=["src/signup.py"],
        context_index=context_index,
        db=None,
        repository_id=None
    )
    # signup has tests in context index, so is_automated must be True
    assert result["must_test"][0]["is_automated"] is True
    assert len(result["missing_test_scenarios"]) == 0

    # 2. Test via Database TestCase
    from app.models.test_result import TestCase
    tc = TestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="tests.login",
        test_name="test_user_login",
        stable_identity="tests.login::test_user_login",
        canonical_identity_hash="hash_login",
        identity_lineage_root_hash="hash_login"
    )
    db.add(tc)
    db.commit()

    product_impact = {"affected_capabilities": ["login"]}
    result_db = QALeadSMEAnalyzer.analyze(
        product_impact=product_impact,
        risk_assessment="LOW",
        changed_files=["src/login.py"],
        context_index=None,
        db=db,
        repository_id=repo_id
    )
    # login has tests in DB, so is_automated must be True
    assert result_db["must_test"][0]["is_automated"] is True
    assert len(result_db["missing_test_scenarios"]) == 0

    # 3. Test missing capability has False and suggests missing test scenarios
    product_impact = {"affected_capabilities": ["password reset"]}
    result_missing = QALeadSMEAnalyzer.analyze(
        product_impact=product_impact,
        risk_assessment="LOW",
        changed_files=["src/reset.py"],
        context_index=None,
        db=db,
        repository_id=repo_id
    )
    assert result_missing["must_test"][0]["is_automated"] is False
    assert len(result_missing["missing_test_scenarios"]) > 0
    assert result_missing["missing_test_scenarios"][0]["scenario"] == "Automated boundary check for password reset token generation expiration"

def test_qa_lead_sme_analyzer_unknown_fallback():
    """Verify QALeadSMEAnalyzer graceful fallback behavior for unknown changes."""
    product_impact = {
        "affected_capabilities": ["unknown"],
        "affected_user_journeys": [{"journey": "unknown", "source_file": "None", "confidence": "LOW"}],
        "business_impact_summary": "unknown capability changed",
        "confidence": "LOW"
    }

    result = QALeadSMEAnalyzer.analyze(
        product_impact=product_impact,
        risk_assessment="LOW",
        changed_files=["src/utils/helpers.py"],
        context_index=None,
        db=None,
        repository_id=None
    )

    assert len(result["must_test"]) == 1
    assert result["must_test"][0]["scenario"] == "Verify changed file paths for basic regression"
    assert result["must_test"][0]["is_automated"] is False
    assert result["regression_areas"][0]["area"] == "Changed modules regression"

def test_qa_lead_sme_analyzer_recommendation_integration(db):
    """Verify integration of QALeadSMEAnalyzer inside RecommendationService.create_recommendation_run."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    # Seed Workspace, Repository, Pull Request
    workspace = Workspace(id=workspace_id, name="QA Space", slug="qa-space")
    db.add(workspace)
    
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=777,
        name="qa-repo",
        full_name="org/qa-repo",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)

    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=888,
        number=4,
        title="Secure system password reset behavior",
        author="engineer",
        source_branch="feat/reset",
        target_branch="main",
        state="open",
        head_commit_sha="aabbccddee0011223344556677889944",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)

    # Seed changed file matching password reset capability
    pr_file = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/app/reset-password/page.tsx",
        status="modified"
    )
    db.add(pr_file)

    # Seed at least one TestCase and one TestRun to pass validation rules
    from app.models.test_result import TestCase as DBTestCase, TestRun as DBTestRun
    tc = DBTestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="tests.auth",
        test_name="test_reset",
        stable_identity="tests.auth::test_reset",
        canonical_identity_hash="hash4",
        identity_lineage_root_hash="hash4"
    )
    db.add(tc)

    tr = DBTestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        status="SUCCESS",
        evidence_source="MANUAL_UPLOAD",
        evidence_artifact_type="JUNIT_XML",
        file_hash="hash_tr_4",
        normalized_execution_fingerprint="fingerprint_tr_4",
        created_at=datetime.utcnow()
    )
    db.add(tr)
    db.commit()

    # Call recommendation service
    from app.schemas.recommendation import RecommendationRunCreate
    service = RecommendationService(db)
    
    run_in = RecommendationRunCreate(
        repository_id=repo_id,
        pr_id="4",
        triggered_by="github-webhook",
        engine_version="v3"
    )

    run = service.create_recommendation_run(run_in)
    assert run is not None

    # Verify that QA Lead SME QAScopeAssessment was persisted correctly in impact_profile
    run_record = db.query(RecommendationRun).filter(RecommendationRun.id == run.id).first()
    assert run_record is not None
    assert run_record.impact_profile is not None
    assert "qa_scope_assessment" in run_record.impact_profile

    qa_assessment = run_record.impact_profile["qa_scope_assessment"]
    assert "must_test" in qa_assessment
    assert "should_test" in qa_assessment
    assert "optional_test" in qa_assessment
    assert "negative_cases" in qa_assessment
    assert "regression_areas" in qa_assessment
    assert "missing_test_scenarios" in qa_assessment

    # Assert that is_automated matches the DB test match (test_reset matches password reset keywords)
    # The seeded test is tests.auth::test_reset, which contains "reset" and matches "password reset" keywords.
    assert qa_assessment["must_test"][0]["is_automated"] is True
