import uuid
from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

# Register SQLite compilation helpers for PostgreSQL-specific columns
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"

from app.db.base import Base
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.recommendation import RecommendationRun, SuggestedTestScenario, RecommendedTest
from app.models.user import Workspace
from app.services.suggested_test_scenario_generator import SuggestedTestScenarioGenerator
from app.services.recommendation import RecommendationService
from app.routers.recommendation import get_recommendation_run


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


def test_suggested_test_scenario_generator(db):
    """Verify that SuggestedTestScenarioGenerator generates correct scenarios based on changed files."""
    run_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    # Seed Recommendation Run
    run = RecommendationRun(
        id=run_id,
        repository_id=repo_id,
        pr_id="123",
        triggered_by="github-webhook",
        evidence_quality="LOW",
        engine_version="v3",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="Weak automated coverage fallback",
        risk_level="HIGH",
        impact_profile={
            "affected_domains": ["auth", "billing"],
            "affected_features": ["signup", "reset-password"]
        },
        created_at=datetime.utcnow()
    )
    db.add(run)
    db.commit()

    changed_files = ["src/auth/signup.py", "src/billing/checkout.py"]

    # Generate suggested scenarios
    scenarios = SuggestedTestScenarioGenerator.generate_scenarios(db, run, changed_files)

    # Verify high-fidelity scenario fields
    assert len(scenarios) > 0
    
    signup_scenario = next((s for s in scenarios if "signup" in s.title.lower()), None)
    assert signup_scenario is not None
    assert signup_scenario.testing_type == "Security / UI"
    assert signup_scenario.impacted_area == "User Registration"
    assert signup_scenario.priority == "HIGH"
    assert "Email address is not registered in the system" in signup_scenario.preconditions
    assert signup_scenario.test_data.get("weak_password") == "123456"
    assert len(signup_scenario.steps) > 0
    assert signup_scenario.automation_candidate is True
    assert signup_scenario.related_changed_files == changed_files
    assert signup_scenario.source_signal == "MISSING_AUTOMATED_COVERAGE"


def test_service_integration_persists_scenarios(db):
    """Verify SuggestedTestScenarioGenerator integration in RecommendationService.create_recommendation_run."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    # Seed Workspace, Repository, Pull Request
    workspace = Workspace(id=workspace_id, name="Test Space", slug="test-space")
    db.add(workspace)
    
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=111,
        name="test-repo",
        full_name="org/test-repo",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)

    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=222,
        number=1,
        title="Upgrade login flow and payment system",
        author="engineer",
        source_branch="feat/auth-billing",
        target_branch="main",
        state="open",
        head_commit_sha="aabbccddee0011223344556677889900",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)

    pr_file = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/auth/login.py",
        status="modified"
    )
    db.add(pr_file)

    # Seed at least one TestCase and one TestRun to pass validation rules
    from app.models.test_result import TestCase as DBTestCase, TestRun as DBTestRun
    tc = DBTestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="tests.auth",
        test_name="test_login",
        stable_identity="tests.auth::test_login",
        canonical_identity_hash="hash1",
        identity_lineage_root_hash="hash1"
    )
    db.add(tc)

    tr = DBTestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        status="SUCCESS",
        evidence_source="MANUAL_UPLOAD",
        evidence_artifact_type="JUNIT_XML",
        file_hash="hash_tr",
        normalized_execution_fingerprint="fingerprint_tr",
        created_at=datetime.utcnow()
    )
    db.add(tr)

    db.commit()

    # Call RecommendationService to generate run
    from app.schemas.recommendation import RecommendationRunCreate
    service = RecommendationService(db)
    
    run_in = RecommendationRunCreate(
        repository_id=repo_id,
        pr_id="1",
        triggered_by="github-webhook",
        engine_version="v3"
    )
    
    run = service.create_recommendation_run(run_in)
    assert run is not None

    # Verify suggested test scenarios were generated and persisted
    db_scenarios = db.query(SuggestedTestScenario).filter(SuggestedTestScenario.recommendation_run_id == run.id).all()
    assert len(db_scenarios) > 0
    assert any("login" in s.title.lower() for s in db_scenarios)


def test_router_endpoint_exposes_scenarios(db):
    """Verify that get_recommendation_run API router exposes suggested test scenarios correctly."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    run_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="Secure Space", slug="secure-space")
    db.add(workspace)
    
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=333,
        name="secure-repo",
        full_name="org/secure-repo",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)

    run = RecommendationRun(
        id=run_id,
        repository_id=repo_id,
        pr_id="1",
        triggered_by="github-webhook",
        evidence_quality="LOW",
        engine_version="v3",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="Fallback reasons",
        created_at=datetime.utcnow()
    )
    db.add(run)

    scenario = SuggestedTestScenario(
        id=uuid.uuid4(),
        recommendation_run_id=run_id,
        title="Reject weak password during signup",
        testing_type="Security / UI",
        impacted_area="User Registration",
        priority="HIGH",
        preconditions=["Email is unregistered"],
        test_data={"password": "weak"},
        steps=["Step 1"],
        expected_result="Blocked",
        automation_candidate=True,
        related_changed_files=["src/auth/signup.py"],
        reason="No automated coverage",
        confidence="HIGH",
        source_signal="MISSING_AUTOMATED_COVERAGE",
        created_at=datetime.utcnow()
    )
    db.add(scenario)
    db.commit()

    # Call get_recommendation_run router directly
    res = get_recommendation_run(
        recommendation_run_id=run_id,
        workspace=workspace,
        db=db
    )

    # Verify that the suggested scenarios are exposed in the JSON response dict
    assert "suggested_test_scenarios" in res
    exposed = res["suggested_test_scenarios"]
    assert len(exposed) == 1
    assert exposed[0]["title"] == "Reject weak password during signup"
    assert exposed[0]["testing_type"] == "Security / UI"
    assert exposed[0]["impacted_area"] == "User Registration"
    assert exposed[0]["priority"] == "HIGH"
    assert exposed[0]["preconditions"] == ["Email is unregistered"]
    assert exposed[0]["test_data"] == {"password": "weak"}
    assert exposed[0]["expected_result"] == "Blocked"
    assert exposed[0]["automation_candidate"] is True


def test_test_data_suggestion_engine():
    """Verify that TestDataSuggestionEngine dynamically generates valid, safe, non-sensitive, and deterministic test data."""
    from app.services.test_data_suggestion_engine import TestDataSuggestionEngine

    impact_profile = {}
    risk_assessment = None
    changed_files = []
    testing_scope = {}

    # Test case 1: Password validation domain (no evidence)
    pwd_data = TestDataSuggestionEngine.generate_test_data(
        impact_profile=impact_profile,
        risk_assessment=risk_assessment,
        changed_files=changed_files,
        testing_scope=testing_scope,
        domain_or_feature="Password Validation"
    )
    assert pwd_data["weak_password"] == "123456"
    assert pwd_data["missing_uppercase"] == "password123!"
    assert pwd_data["missing_number"] == "Password!"
    assert pwd_data["valid_password"] == "StrongPass123!"
    assert pwd_data["_metadata"]["label"] == "suggested data"
    assert "not verified against local application runtime validation rules" in pwd_data["_metadata"]["rule_validation_caveat"]

    # Verify evidenced caveat
    pwd_data_evidenced = TestDataSuggestionEngine.generate_test_data(
        impact_profile=impact_profile,
        risk_assessment=risk_assessment,
        changed_files=["src/auth/validation.py"],
        testing_scope=testing_scope,
        domain_or_feature="Password Validation"
    )
    assert "should be calibrated with local runtime rules" in pwd_data_evidenced["_metadata"]["rule_validation_caveat"]

    # Test case 2: Reset password domain
    reset_data = TestDataSuggestionEngine.generate_test_data(
        impact_profile=impact_profile,
        risk_assessment=risk_assessment,
        changed_files=changed_files,
        testing_scope=testing_scope,
        domain_or_feature="Reset Password"
    )
    assert reset_data["expired_token"] == "expired-reset-token-999"
    assert reset_data["invalid_token"] == "invalid-token-111"
    assert reset_data["reused_token"] == "reused-token-222"
    assert reset_data["valid_token"] == "valid-reset-token-777"
    assert reset_data["_metadata"]["label"] == "suggested data"

    # Test case 3: Signup domain
    signup_data = TestDataSuggestionEngine.generate_test_data(
        impact_profile=impact_profile,
        risk_assessment=risk_assessment,
        changed_files=changed_files,
        testing_scope=testing_scope,
        domain_or_feature="Signup"
    )
    assert signup_data["existing_email"] == "existing@example.com"
    assert signup_data["invalid_email"] == "invalid-email"
    assert signup_data["weak_password"] == "123456"
    assert signup_data["valid_signup"]["email"] == "newuser@example.com"
    assert signup_data["valid_signup"]["password"] == "StrongPass123!"
    assert signup_data["_metadata"]["label"] == "suggested data"

