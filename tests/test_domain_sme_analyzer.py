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
from app.services.domain_sme_analyzer import DomainSMEAnalyzer
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

def test_domain_sme_analyzer_term_matching():
    """Verify that match_terms correctly matches reset-password with password recovery, and signup with registration."""
    # Standard synonym checks
    assert DomainSMEAnalyzer.match_terms("reset-password", "password recovery tests") is True
    assert DomainSMEAnalyzer.match_terms("signup", "registration tests") is True
    
    # Check that they reside in different clusters
    assert DomainSMEAnalyzer.match_terms("reset-password", "signup") is False
    assert DomainSMEAnalyzer.match_terms("login", "checkout") is False

    # Check custom terms/fallback overlap matching
    assert DomainSMEAnalyzer.match_terms("widget-service", "widget custom tester") is True
    assert DomainSMEAnalyzer.match_terms("custom-payment", "stripe payment processing") is True  # both belong to checkout cluster
    assert DomainSMEAnalyzer.match_terms("nothing", "something") is False

def test_domain_sme_analyzer_token_clustering(db):
    """Verify that vocabulary is deterministically collected and grouped into a DomainVocabulary structure."""
    changed_files = [
        "src/app/reset-password/page.tsx",
        "src/app/signup/sign-up-form.tsx"
    ]
    
    test_cases = [
        {"test_name": "test_password_recovery", "suite_name": "tests.auth", "stable_identity": "tests.auth::test_password_recovery"},
        {"test_name": "test_registration_success", "suite_name": "tests.auth", "stable_identity": "tests.auth::test_registration_success"}
    ]
    
    vocab = DomainSMEAnalyzer.analyze(
        context_index=None,
        changed_files=changed_files,
        pr_title="Upgrade registration flow & recover credentials form",
        test_cases=test_cases
    )
    
    # 1. Assert domain_terms contains extracted vocabulary
    assert "signup" in vocab["domain_terms"]
    assert "recovery" in vocab["domain_terms"]
    assert "password" in vocab["domain_terms"]
    assert "registration" in vocab["domain_terms"]
    assert "credentials" in vocab["domain_terms"]
    
    # 2. Assert synonyms list has expected clusters
    signup_syns = next((s for s in vocab["synonyms"] if s["cluster"] == "signup"), None)
    assert signup_syns is not None
    assert "register" in signup_syns["terms"]
    assert "signup" in signup_syns["terms"]
    
    # 3. Assert feature_aliases maps standard paths
    assert vocab["feature_aliases"]["src/app/reset-password/page.tsx"] == "password reset"
    assert vocab["feature_aliases"]["src/app/signup/sign-up-form.tsx"] == "signup"
    
    # 4. Assert test_term_map maps test identities
    assert "tests.auth::test_password_recovery" in vocab["test_term_map"]["password reset"]
    assert "tests.auth::test_registration_success" in vocab["test_term_map"]["signup"]

def test_domain_sme_analyzer_with_context_index(db):
    """Verify that DomainSMEAnalyzer leverages ProjectContextIndex route paths and journeys."""
    changed_files = ["src/custom-settings.ts"]
    
    mock_index = ProjectContextIndex(
        repository_id=uuid.uuid4(),
        user_journeys=[{
            "name": "Subscription Billing Flow",
            "source_files": ["src/custom-settings.ts"]
        }],
        domains=[{
            "name": "Authentication & Identity",
            "source_files": ["src/custom-settings.ts"]
        }],
        routes=[
            {"path": "/api/v1/auth/login", "name": "login"},
            {"path": "/api/v1/checkout/pay", "name": "checkout"}
        ]
    )
    
    vocab = DomainSMEAnalyzer.analyze(
        context_index=mock_index,
        changed_files=changed_files,
        pr_title="Tweak configurations",
        test_cases=[]
    )
    
    # Verify that routes paths and names are parsed
    assert "/api/v1/auth/login" in vocab["domain_terms"]
    assert "login" in vocab["domain_terms"]
    assert "checkout" in vocab["domain_terms"]
    
    # Verify feature alias maps custom-settings to standard domain (e.g. login/auth or subscription depending on lookup)
    assert "src/custom-settings.ts" in vocab["feature_aliases"]

def test_recommendation_integration_persists_domain_vocabulary(db):
    """Verify that DomainSMEAnalyzer is correctly executed during recommendation runs and persisted inside the impact profile."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="Security Workspace", slug="security-workspace")
    db.add(workspace)
    
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=200,
        name="secure-repo",
        full_name="org/secure-repo",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)

    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=300,
        number=7,
        title="Implement reset-password email token and registration recovery",
        author="engineer",
        source_branch="feat/reset",
        target_branch="main",
        state="open",
        head_commit_sha="ccddeeff00112233445566778899aabbccddeeff",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)

    pr_file = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/app/reset-password/page.tsx",
        status="modified"
    )
    db.add(pr_file)

    # Seed test run and test cases
    from app.models.test_result import TestCase as DBTestCase, TestRun as DBTestRun
    
    tc1 = DBTestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="tests.auth",
        test_name="test_password_recovery",
        stable_identity="tests.auth::test_password_recovery",
        canonical_identity_hash="hash_tc1",
        identity_lineage_root_hash="hash_tc1"
    )
    db.add(tc1)

    tc2 = DBTestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="tests.auth",
        test_name="test_registration_details",
        stable_identity="tests.auth::test_registration_details",
        canonical_identity_hash="hash_tc2",
        identity_lineage_root_hash="hash_tc2"
    )
    db.add(tc2)

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
        pr_id="7",
        triggered_by="github-webhook",
        engine_version="v3"
    )

    run = service.create_recommendation_run(run_in)
    assert run is not None
    
    # Retrieve persisted impact profile from run record
    run_record = db.query(RecommendationRun).filter(RecommendationRun.id == run.id).first()
    assert run_record is not None
    assert run_record.impact_profile is not None
    assert "domain_vocabulary" in run_record.impact_profile
    
    vocab = run_record.impact_profile["domain_vocabulary"]
    
    # Verify learned domain terms
    assert "recovery" in vocab["domain_terms"]
    assert "password" in vocab["domain_terms"]
    assert "registration" in vocab["domain_terms"]
    
    # Verify synonyms
    signup_syns = next((s for s in vocab["synonyms"] if s["cluster"] == "signup"), None)
    assert signup_syns is not None
    assert "register" in signup_syns["terms"]
    
    # Verify feature alias
    assert vocab["feature_aliases"]["src/app/reset-password/page.tsx"] == "password reset"
    
    # Verify test mapping
    assert "tests.auth::test_password_recovery" in vocab["test_term_map"]["password reset"]
    assert "tests.auth::test_registration_details" in vocab["test_term_map"]["signup"]
