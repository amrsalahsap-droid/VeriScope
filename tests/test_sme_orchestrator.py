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
from app.services.sme_orchestrator import SMEOrchestrator
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

def test_sme_orchestrator_orchestration():
    """Verify that SMEOrchestrator runs all five analyzers and produces a unified ProjectUnderstandingSnapshot."""
    changed_files = [
        "src/app/reset-password/page.tsx",
        "src/app/signup/sign-up-form.tsx"
    ]
    test_cases = [
        {"test_name": "test_password_recovery", "suite_name": "tests.auth", "stable_identity": "tests.auth::test_password_recovery"},
        {"test_name": "test_registration_success", "suite_name": "tests.auth", "stable_identity": "tests.auth::test_registration_success"}
    ]
    
    orchestrated = SMEOrchestrator.orchestrate(
        context_index=None,
        changed_files=changed_files,
        pr_title="Upgrade registration and support password recover",
        pr_description="Reset password flow upgrades",
        test_cases=test_cases,
        risk_assessment="HIGH"
    )

    # 1. Assert all individual keys are present
    assert "product_impact" in orchestrated
    assert "qa_scope_assessment" in orchestrated
    assert "security_assessment" in orchestrated
    assert "architecture_impact" in orchestrated
    assert "domain_vocabulary" in orchestrated
    assert "project_understanding_snapshot" in orchestrated

    # 2. Verify snapshot fields
    snapshot = orchestrated["project_understanding_snapshot"]
    assert "affected_journeys" in snapshot
    assert "affected_domains" in snapshot
    assert "touched_layers" in snapshot
    assert "testing_scope" in snapshot
    assert "security_assessment" in snapshot
    assert "architecture_impact" in snapshot
    assert "missing_scenarios" in snapshot
    assert "evidence" in snapshot
    assert "confidence" in snapshot

    # 3. Assert specific values inside snapshot
    assert "password reset" in snapshot["affected_domains"]
    assert "signup" in snapshot["affected_domains"]
    assert any("UI" in layer for layer in snapshot["touched_layers"])
    assert len(snapshot["evidence"]) > 0
    assert snapshot["confidence"] == "HIGH"

def test_recommendation_integration_persists_project_understanding_snapshot(db):
    """Verify that RecommendationService successfully invokes SMEOrchestrator and persists the snapshot."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="Orchestrated Workspace", slug="orchestrated-workspace")
    db.add(workspace)
    
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=500,
        name="orchestrated-repo",
        full_name="org/orchestrated-repo",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)

    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=600,
        number=12,
        title="Upgrade billing subscription plans and checkout flow",
        author="engineer",
        source_branch="feat/billing",
        target_branch="main",
        state="open",
        head_commit_sha="ddeeff00112233445566778899aabbccddeeff00",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)

    pr_file1 = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/services/billing.py",
        status="modified"
    )
    db.add(pr_file1)

    pr_file2 = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/app/checkout/page.tsx",
        status="modified"
    )
    db.add(pr_file2)

    # Seed test run and test cases
    from app.models.test_result import TestCase as DBTestCase, TestRun as DBTestRun
    
    tc1 = DBTestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="tests.billing",
        test_name="test_checkout_stripe",
        stable_identity="tests.billing::test_checkout_stripe",
        canonical_identity_hash="hash_tc1_o",
        identity_lineage_root_hash="hash_tc1_o"
    )
    db.add(tc1)

    tr = DBTestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        status="SUCCESS",
        evidence_source="MANUAL_UPLOAD",
        evidence_artifact_type="JUNIT_XML",
        file_hash="hash_tr_5",
        normalized_execution_fingerprint="fingerprint_tr_5",
        created_at=datetime.utcnow()
    )
    db.add(tr)
    db.commit()

    # Call recommendation service
    from app.schemas.recommendation import RecommendationRunCreate
    service = RecommendationService(db)
    
    run_in = RecommendationRunCreate(
        repository_id=repo_id,
        pr_id="12",
        triggered_by="github-webhook",
        engine_version="v3"
    )

    run = service.create_recommendation_run(run_in)
    assert run is not None
    
    # Retrieve persisted impact profile from run record
    run_record = db.query(RecommendationRun).filter(RecommendationRun.id == run.id).first()
    assert run_record is not None
    assert run_record.impact_profile is not None
    
    # Check that individual outputs are present
    assert "product_impact" in run_record.impact_profile
    assert "qa_scope_assessment" in run_record.impact_profile
    assert "security_assessment" in run_record.impact_profile
    assert "architecture_impact" in run_record.impact_profile
    assert "domain_vocabulary" in run_record.impact_profile
    
    # Check that project_understanding_snapshot is present
    assert "project_understanding_snapshot" in run_record.impact_profile
    snapshot = run_record.impact_profile["project_understanding_snapshot"]
    
    assert "subscription" in snapshot["affected_domains"]
    assert "checkout" in snapshot["affected_domains"]
    assert any("Service" in layer for layer in snapshot["touched_layers"])
    assert any("UI" in layer for layer in snapshot["touched_layers"])
    assert len(snapshot["evidence"]) > 0

def test_recommendation_engine_consumes_sme_snapshot(db):
    """Verify that RecommendationEngine consumes the SME snapshot and boosts auth/security tests with stronger reasoning even under weak coverage."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="SME Workspace", slug="sme-workspace")
    db.add(workspace)
    
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=900,
        name="sme-repo",
        full_name="org/sme-repo",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)

    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=1000,
        number=45,
        title="Upgrade auth password-reset secure policy",
        author="engineer",
        source_branch="feat/auth-security",
        target_branch="main",
        state="open",
        head_commit_sha="abcdef1234567890abcdef1234567890abcdef12",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)

    # File with weak/no direct automated coverage link, but has path matching password-reset
    pr_file = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/app/reset-password/page.tsx",
        status="modified"
    )
    db.add(pr_file)

    # Seed test case that matches auth/security/password-reset
    from app.models.test_result import TestCase as DBTestCase, TestRun as DBTestRun
    
    tc = DBTestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="tests.security",
        test_name="test_reset_password_strength",
        stable_identity="tests.security::test_reset_password_strength",
        canonical_identity_hash="hash_tc_sme_sec",
        identity_lineage_root_hash="hash_tc_sme_sec"
    )
    db.add(tc)

    tr = DBTestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        status="SUCCESS",
        evidence_source="MANUAL_UPLOAD",
        evidence_artifact_type="JUNIT_XML",
        file_hash="hash_tr_sme_sec",
        normalized_execution_fingerprint="fingerprint_tr_sme_sec",
        created_at=datetime.utcnow()
    )
    db.add(tr)
    db.commit()

    # Call recommendation service
    from app.schemas.recommendation import RecommendationRunCreate
    service = RecommendationService(db)
    
    run_in = RecommendationRunCreate(
        repository_id=repo_id,
        pr_id="45",
        triggered_by="github-webhook",
        engine_version="v3"
    )

    run = service.create_recommendation_run(run_in)
    assert run is not None
    
    # Check recommended test details
    rec_test = run.recommended_tests[0]
    assert rec_test.test_identifier == "tests.security::test_reset_password_strength"
    
    # Verify the test received dynamic SME boosts
    assert rec_test.priority > 0.0
    assert "SME Signals" in rec_test.reason
    assert "Domain match from SME" in rec_test.reason
    assert "User journey match from SME" in rec_test.reason
    assert "Security-required test from SME" in rec_test.reason
    
    # Verify persisted explanations and signals breakdown
    from app.models.recommendation import RecommendationExplanation
    explanation = db.query(RecommendationExplanation).filter(
        RecommendationExplanation.recommendation_run_id == run.id,
        RecommendationExplanation.test_id == "tests.security::test_reset_password_strength"
    ).first()
    assert explanation is not None
    assert "sme domain match" in explanation.score_breakdown
    assert "sme security required" in explanation.score_breakdown
    assert "sme journey match" in explanation.score_breakdown
