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
from app.services.security_sme_analyzer import SecuritySMEAnalyzer
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

def test_security_sme_analyzer_keywords():
    """Verify that SecuritySMEAnalyzer correctly identifies security categories from file paths."""
    changed_files = ["src/app/reset-password/page.tsx"]
    product_impact = {"affected_capabilities": []}
    
    result = SecuritySMEAnalyzer.analyze(
        changed_files=changed_files,
        product_impact=product_impact,
        context_index=None
    )

    # Verifies matching password reset keywords triggers standard reset risks
    assert len(result["security_risks"]) > 0
    assert any("expired reset tokens are rejected in file: src/app/reset-password/page.tsx" in r for r in result["security_risks"])
    assert any("An attacker attempts to brute force or guess reset tokens to hijack user accounts" in a for a in result["abuse_cases"])
    assert "Token lifecycle validation (verifying expired, invalid, and single-use/reused reset token rejection)" in result["required_security_tests"]
    assert result["suggested_test_data"]["weak_password"] == "123"
    assert result["suggested_test_data"]["expired_token"] == "expired-reset-token-999"
    assert any("Keyword match for security category" in e for e in result["evidence"])

def test_security_sme_analyzer_product_impact():
    """Verify that SecuritySMEAnalyzer leverages capabilities from ProductImpact."""
    changed_files = ["src/some_other_file.py"]
    product_impact = {"affected_capabilities": ["signup"]}

    result = SecuritySMEAnalyzer.analyze(
        changed_files=changed_files,
        product_impact=product_impact,
        context_index=None
    )

    assert any("registration with a pre-existing email is rejected in file: src/some_other_file.py" in r for r in result["security_risks"])
    assert "Duplicate email constraint testing in signup flow" in result["required_security_tests"]
    assert result["suggested_test_data"]["existing_email"] == "existing@example.com"
    assert "Capability 'signup' affected in ProductImpact" in result["evidence"]

def test_security_sme_analyzer_context_index():
    """Verify that SecuritySMEAnalyzer leverages ProjectContextIndex security-sensitive areas."""
    changed_files = ["src/sensitive/credentials.py"]
    product_impact = {"affected_capabilities": []}

    mock_index = ProjectContextIndex(
        repository_id=uuid.uuid4(),
        security_sensitive_areas=[{
            "name": "Authentication & Cryptographic Secrets",
            "source_files": ["src/sensitive/credentials.py"]
        }]
    )

    result = SecuritySMEAnalyzer.analyze(
        changed_files=changed_files,
        product_impact=product_impact,
        context_index=mock_index
    )

    assert any("session/JWT tokens are securely signed with strong keys in file: src/sensitive/credentials.py" in r for r in result["security_risks"])
    assert "JWT integrity and signature validation testing" in result["required_security_tests"]
    assert "invalid_jwt" in result["suggested_test_data"]
    assert any("Context index mapped file src/sensitive/credentials.py" in e for e in result["evidence"])

def test_security_sme_analyzer_fallback():
    """Verify that SecuritySMEAnalyzer gracefully falls back when no security indicators are present."""
    changed_files = ["src/utils/math_helpers.py"]
    product_impact = {"affected_capabilities": []}

    result = SecuritySMEAnalyzer.analyze(
        changed_files=changed_files,
        product_impact=product_impact,
        context_index=None
    )

    assert result["security_risks"] == ["should verify that modified files adhere to general secure coding standards"]
    assert result["abuse_cases"] == ["An attacker exploits unspecified parameter validation gaps in modified modules to execute arbitrary logic"]
    assert result["required_security_tests"] == ["Static Application Security Testing (SAST) linter checks"]
    assert result["suggested_test_data"] == {}
    assert result["evidence"] == ["Fallback: No explicit security-sensitive keywords or API boundaries detected in changed files or ProductImpact"]

def test_security_sme_analyzer_recommendation_integration(db):
    """Verify integration of SecuritySMEAnalyzer inside RecommendationService.create_recommendation_run."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="Security Space", slug="security-space")
    db.add(workspace)
    
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=999,
        name="sec-repo",
        full_name="org/sec-repo",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)

    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=1000,
        number=5,
        title="Implement secure reset token authentication",
        author="engineer",
        source_branch="feat/reset-auth",
        target_branch="main",
        state="open",
        head_commit_sha="aabbccddee0011223344556677889955",
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

    from app.models.test_result import TestCase as DBTestCase, TestRun as DBTestRun
    tc = DBTestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="tests.auth",
        test_name="test_reset",
        stable_identity="tests.auth::test_reset",
        canonical_identity_hash="hash5",
        identity_lineage_root_hash="hash5"
    )
    db.add(tc)

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

    # Create recommendation run
    from app.schemas.recommendation import RecommendationRunCreate
    service = RecommendationService(db)
    
    run_in = RecommendationRunCreate(
        repository_id=repo_id,
        pr_id="5",
        triggered_by="github-webhook",
        engine_version="v3"
    )

    run = service.create_recommendation_run(run_in)
    assert run is not None

    # Retrieve and verify stored security_assessment in impact_profile
    run_record = db.query(RecommendationRun).filter(RecommendationRun.id == run.id).first()
    assert run_record is not None
    assert run_record.impact_profile is not None
    assert "security_assessment" in run_record.impact_profile

    sec_assessment = run_record.impact_profile["security_assessment"]
    assert "security_risks" in sec_assessment
    assert "abuse_cases" in sec_assessment
    assert "required_security_tests" in sec_assessment
    assert "suggested_test_data" in sec_assessment
    assert "evidence" in sec_assessment

    # Verify presence of password reset constraints
    assert any("expired reset tokens are rejected" in r for r in sec_assessment["security_risks"])
    assert any("reused reset tokens are rejected" in r for r in sec_assessment["security_risks"])
    assert any("invalid reset tokens are rejected" in r for r in sec_assessment["security_risks"])
    assert any("account enumeration is prevented" in r for r in sec_assessment["security_risks"])
    assert any("old password is invalid after reset" in r for r in sec_assessment["security_risks"])
    assert any("weak passwords are rejected" in r for r in sec_assessment["security_risks"])
