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
from app.services.product_sme_analyzer import ProductSMEAnalyzer
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

def test_product_sme_analyzer_capabilities(db):
    """Verify that ProductSMEAnalyzer correctly identifies standard capabilities and user journeys."""
    
    # 1. Test changed files detection (e.g. reset-password, signup)
    changed_files = [
        "src/app/reset-password/page.tsx",
        "src/app/signup/sign-up-form.tsx"
    ]
    
    impact = ProductSMEAnalyzer.analyze(
        context_index=None,
        changed_files=changed_files,
        pr_title="Some general title",
        pr_description="Some general description"
    )
    
    assert "password reset" in impact["affected_capabilities"]
    assert "signup" in impact["affected_capabilities"]
    
    # Verify citations and exact mapping
    reset_journey = next((j for j in impact["affected_user_journeys"] if "Password Recovery Flow" in j["journey"]), None)
    assert reset_journey is not None
    assert reset_journey["source_file"] == "src/app/reset-password/page.tsx"
    assert reset_journey["confidence"] == "HIGH"
    
    signup_journey = next((j for j in impact["affected_user_journeys"] if "User Registration Flow" in j["journey"]), None)
    assert signup_journey is not None
    assert signup_journey["source_file"] == "src/app/signup/sign-up-form.tsx"
    assert signup_journey["confidence"] == "HIGH"
    
    assert impact["confidence"] == "HIGH"

def test_product_sme_analyzer_pr_metadata(db):
    """Verify that ProductSMEAnalyzer correctly identifies capabilities from PR title and description."""
    changed_files = ["src/core/main.py"]
    
    impact = ProductSMEAnalyzer.analyze(
        context_index=None,
        changed_files=changed_files,
        pr_title="Enforce secure subscription billing checkout",
        pr_description="This PR upgrades checkout page styling and enforces billing trial rules."
    )
    
    assert "subscription" in impact["affected_capabilities"]
    assert "checkout" in impact["affected_capabilities"]
    
    # Verify moderate confidence for metadata matches when no files directly match
    billing_journey = next((j for j in impact["affected_user_journeys"] if "Subscription Billing Flow" in j["journey"]), None)
    assert billing_journey is not None
    assert billing_journey["confidence"] == "MODERATE"
    assert billing_journey["source_file"] == "None"
    
    assert impact["confidence"] == "MODERATE"

def test_product_sme_analyzer_context_index(db):
    """Verify that ProductSMEAnalyzer leverages ProjectContextIndex domain and journey mappings."""
    changed_files = ["src/custom-billing-utils.ts"]
    
    # Mock a ProjectContextIndex with relevant user journey and domain mappings
    mock_index = ProjectContextIndex(
        repository_id=uuid.uuid4(),
        user_journeys=[{
            "name": "Subscription Billing Flow",
            "source_files": ["src/custom-billing-utils.ts"]
        }],
        domains=[{
            "name": "Billing & Subscription",
            "source_files": ["src/custom-billing-utils.ts"]
        }]
    )
    
    impact = ProductSMEAnalyzer.analyze(
        context_index=mock_index,
        changed_files=changed_files,
        pr_title="Change minor styles",
        pr_description=""
    )
    
    assert "subscription" in impact["affected_capabilities"]
    billing_journey = next((j for j in impact["affected_user_journeys"] if "Subscription Billing Flow" in j["journey"]), None)
    assert billing_journey is not None
    assert billing_journey["source_file"] == "src/custom-billing-utils.ts"
    assert billing_journey["confidence"] == "HIGH"

def test_product_sme_analyzer_unknown_fallback(db):
    """Verify that ProductSMEAnalyzer falls back gracefully to unknown when no matches are detected."""
    changed_files = ["src/core/utils/helper.py"]
    
    impact = ProductSMEAnalyzer.analyze(
        context_index=None,
        changed_files=changed_files,
        pr_title="Minor refactoring",
        pr_description="Just restructuring helpers"
    )
    
    assert "unknown" in impact["affected_capabilities"]
    unknown_journey = impact["affected_user_journeys"][0]
    assert unknown_journey["journey"] == "unknown"
    assert unknown_journey["source_file"] == "None"
    assert unknown_journey["confidence"] == "LOW"
    assert impact["confidence"] == "LOW"

def test_recommendation_integration_persists_product_impact(db):
    """Verify that ProductSMEAnalyzer is correctly executed during recommendation runs and persisted."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="Test Space", slug="test-space")
    db.add(workspace)
    
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=113,
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
        github_pr_id=224,
        number=3,
        title="Implement email verification and password reset page",
        author="engineer",
        source_branch="feat/auth",
        target_branch="main",
        state="open",
        head_commit_sha="aabbccddee0011223344556677889922",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)

    # Seed files matching reset-password and notification capabilities
    pr_file1 = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/app/reset-password/page.tsx",
        status="modified"
    )
    db.add(pr_file1)
    
    pr_file2 = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/services/notification.py",
        status="modified"
    )
    db.add(pr_file2)

    # Seed test run and test case to satisfy pre-requisites
    from app.models.test_result import TestCase as DBTestCase, TestRun as DBTestRun
    tc = DBTestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="tests.auth",
        test_name="test_reset",
        stable_identity="tests.auth::test_reset",
        canonical_identity_hash="hash3",
        identity_lineage_root_hash="hash3"
    )
    db.add(tc)

    tr = DBTestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        status="SUCCESS",
        evidence_source="MANUAL_UPLOAD",
        evidence_artifact_type="JUNIT_XML",
        file_hash="hash_tr_3",
        normalized_execution_fingerprint="fingerprint_tr_3",
        created_at=datetime.utcnow()
    )
    db.add(tr)
    db.commit()

    # Call recommendation service
    from app.schemas.recommendation import RecommendationRunCreate
    service = RecommendationService(db)
    
    run_in = RecommendationRunCreate(
        repository_id=repo_id,
        pr_id="3",
        triggered_by="github-webhook",
        engine_version="v3"
    )

    run = service.create_recommendation_run(run_in)
    assert run is not None
    
    # Retrieve persisted impact profile from run
    run_record = db.query(RecommendationRun).filter(RecommendationRun.id == run.id).first()
    assert run_record is not None
    assert run_record.impact_profile is not None
    assert "product_impact" in run_record.impact_profile
    
    prod_impact = run_record.impact_profile["product_impact"]
    assert "password reset" in prod_impact["affected_capabilities"]
    assert "notifications" in prod_impact["affected_capabilities"]
    assert prod_impact["confidence"] == "HIGH"
    
    # Confirm business summary exists
    assert "critical user journeys" in prod_impact["business_impact_summary"]
