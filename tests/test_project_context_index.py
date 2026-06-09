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
from app.services.project_context_index_extractor import ProjectContextIndexExtractor
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

def test_project_context_index_extraction(db):
    """Verify that ProjectContextIndexExtractor correctly populates all indices and mappings."""
    repo_id = uuid.uuid4()
    
    # Extract using local veriscope folder
    extractor = ProjectContextIndexExtractor(db)
    checkout_dir = "c:/Users/amrsa/Downloads/veriscope"
    
    index_record = extractor.extract_and_persist(repo_id, checkout_dir)
    
    # Retrieve persisted record
    persisted = db.query(ProjectContextIndex).filter(ProjectContextIndex.repository_id == repo_id).first()
    assert persisted is not None
    assert persisted.id == index_record.id
    
    # Verify Frameworks
    assert len(persisted.detected_frameworks) > 0
    names = [f["name"] for f in persisted.detected_frameworks]
    assert "FastAPI" in names
    
    # Verify exact traceability
    fastapi_framework = next((f for f in persisted.detected_frameworks if f["name"] == "FastAPI"), None)
    assert fastapi_framework is not None
    assert len(fastapi_framework["source_files"]) > 0
    assert any("requirements.txt" in f or "main.py" in f for f in fastapi_framework["source_files"])
    
    # Verify Routes and Pages
    assert len(persisted.routes) > 0
    assert len(persisted.pages) > 0
    assert len(persisted.api_endpoints) > 0
    
    # Verify Domains keyword mapping (e.g. auth, billing, recommendation)
    domain_names = [d["name"] for d in persisted.domains]
    assert "Authentication & Identity" in domain_names
    assert "Test Recommendations" in domain_names
    
    auth_domain = next((d for d in persisted.domains if d["name"] == "Authentication & Identity"), None)
    assert auth_domain is not None
    assert any("auth.py" in f or "user.py" in f for f in auth_domain["source_files"])
    
    # Verify Test Assets
    assert len(persisted.test_assets) > 0
    assert any("test_suggested_test_scenario.py" in a["name"] for a in persisted.test_assets)
    
    # Verify Security Sensitive Areas
    assert len(persisted.security_sensitive_areas) > 0
    sec_area = persisted.security_sensitive_areas[0]
    assert sec_area["name"] == "Authentication & Cryptographic Secrets"
    assert any("auth" in f or "security" in f for f in sec_area["source_files"])
    
    # Verify Confidence
    assert persisted.confidence == "HIGH"

def test_recommendation_run_integration(db):
    """Verify that ProjectContextIndex is automatically generated and updated during recommendation runs."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="Test Space", slug="test-space")
    db.add(workspace)
    
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=112,
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
        github_pr_id=223,
        number=2,
        title="Upgrade billing integration",
        author="engineer",
        source_branch="feat/billing",
        target_branch="main",
        state="open",
        head_commit_sha="aabbccddee0011223344556677889911",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)

    pr_file = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/billing/payment.py",
        status="modified"
    )
    db.add(pr_file)

    # Seed test run and test case to satisfy pre-requisites
    from app.models.test_result import TestCase as DBTestCase, TestRun as DBTestRun
    tc = DBTestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="tests.billing",
        test_name="test_checkout",
        stable_identity="tests.billing::test_checkout",
        canonical_identity_hash="hash2",
        identity_lineage_root_hash="hash2"
    )
    db.add(tc)

    tr = DBTestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        status="SUCCESS",
        evidence_source="MANUAL_UPLOAD",
        evidence_artifact_type="JUNIT_XML",
        file_hash="hash_tr_2",
        normalized_execution_fingerprint="fingerprint_tr_2",
        created_at=datetime.utcnow()
    )
    db.add(tr)
    db.commit()

    # Verify no ProjectContextIndex exists for repo yet
    existing = db.query(ProjectContextIndex).filter(ProjectContextIndex.repository_id == repo_id).first()
    assert existing is None

    # Call create_recommendation_run which triggers the extractor hook
    from app.schemas.recommendation import RecommendationRunCreate
    service = RecommendationService(db)
    
    run_in = RecommendationRunCreate(
        repository_id=repo_id,
        pr_id="2",
        triggered_by="github-webhook",
        engine_version="v3"
    )

    run = service.create_recommendation_run(run_in)
    assert run is not None

    # Verify ProjectContextIndex is now created and persisted for repo
    persisted = db.query(ProjectContextIndex).filter(ProjectContextIndex.repository_id == repo_id).first()
    assert persisted is not None
    assert persisted.confidence == "HIGH"
    
    # Confirm billing domain is detected with trace info
    billing_domain = next((d for d in persisted.domains if d["name"] == "Billing & Subscription"), None)
    assert billing_domain is not None
    assert any("verify_flaky_adjustments.py" in f or "billing" in f.lower() for f in billing_domain["source_files"])
