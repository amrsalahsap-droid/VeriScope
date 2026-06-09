import uuid
import os
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
from app.services.architecture_sme_analyzer import ArchitectureSMEAnalyzer
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

def test_architecture_sme_analyzer_layers():
    """Verify that ArchitectureSMEAnalyzer correctly identifies standard layers and boundaries from file paths."""
    changed_files = [
        "src/app/api/route.ts",
        "src/app/reset-password/page.tsx",
        "src/db/models/user.py",
        "src/app/services/auth_service.py",
        "tests/test_auth.py"
    ]

    result = ArchitectureSMEAnalyzer.analyze(
        changed_files=changed_files,
        context_index=None
    )

    # Verifies classification across all 4 mapped layers
    assert "API Layer" in result["touched_layers"]
    assert "UI Layer" in result["touched_layers"]
    assert "Database/Config/Dependency" in result["touched_layers"]
    assert "Test Infrastructure" in result["touched_layers"]
    
    # Asserts that risks are generated for multi-layer touch (coupling UI and API, etc.)
    assert len(result["architectural_risks"]) > 0
    assert any("High coupling threat" in r for r in result["architectural_risks"])
    assert any("Persistence dependency risk" in r for r in result["architectural_risks"])
    assert any("belongs to UI Layer" in e or "classified as UI Layer" in e for e in result["evidence"])

def test_architecture_sme_analyzer_imports():
    """Verify that ArchitectureSMEAnalyzer correctly parses import statements from a physical file."""
    # Write a temporary python script to verify import extraction
    temp_path = "src/temp_test_imports.py"
    abs_temp = os.path.join("c:/Users/amrsa/Downloads/veriscope", temp_path)
    os.makedirs(os.path.dirname(abs_temp), exist_ok=True)
    
    with open(abs_temp, "w", encoding="utf-8") as f:
        f.write("import stripe\nfrom sqlalchemy.orm import Session\nimport app.services.product_sme_analyzer\n")

    try:
        result = ArchitectureSMEAnalyzer.analyze(
            changed_files=[temp_path],
            context_index=None
        )

        assert "stripe" in result["direct_dependencies"]
        assert "sqlalchemy" in result["direct_dependencies"]
        assert "app" in result["direct_dependencies"]
        assert "Stripe Payment Gateway" in result["integration_boundaries"]
        assert "Relational Database Engine" in result["integration_boundaries"]
    finally:
        if os.path.isfile(abs_temp):
            os.remove(abs_temp)

def test_architecture_sme_analyzer_fallback():
    """Verify that ArchitectureSMEAnalyzer gracefully falls back when no technical layers are recognized."""
    changed_files = ["src/utils/simple_helper.py"]

    result = ArchitectureSMEAnalyzer.analyze(
        changed_files=changed_files,
        context_index=None
    )

    assert result["touched_layers"] == ["Service/Module Layer"]
    assert len(result["architectural_risks"]) == 1
    assert "Isolated regression risk" in result["architectural_risks"][0]

def test_architecture_sme_analyzer_recommendation_integration(db):
    """Verify integration of ArchitectureSMEAnalyzer inside RecommendationService.create_recommendation_run."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="Arch Space", slug="arch-space")
    db.add(workspace)
    
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=8888,
        name="arch-repo",
        full_name="org/arch-repo",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)

    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=8889,
        number=6,
        title="Upgrade boundary API layer and frontend pages",
        author="engineer",
        source_branch="feat/arch",
        target_branch="main",
        state="open",
        head_commit_sha="aabbccddee0011223344556677889966",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)

    pr_file1 = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/app/api/route.ts",
        status="modified"
    )
    db.add(pr_file1)

    pr_file2 = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/app/reset-password/page.tsx",
        status="modified"
    )
    db.add(pr_file2)

    from app.models.test_result import TestCase as DBTestCase, TestRun as DBTestRun
    tc = DBTestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="tests.auth",
        test_name="test_reset",
        stable_identity="tests.auth::test_reset",
        canonical_identity_hash="hash6",
        identity_lineage_root_hash="hash6"
    )
    db.add(tc)

    tr = DBTestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        status="SUCCESS",
        evidence_source="MANUAL_UPLOAD",
        evidence_artifact_type="JUNIT_XML",
        file_hash="hash_tr_6",
        normalized_execution_fingerprint="fingerprint_tr_6",
        created_at=datetime.utcnow()
    )
    db.add(tr)
    db.commit()

    # Create recommendation run
    from app.schemas.recommendation import RecommendationRunCreate
    service = RecommendationService(db)
    
    run_in = RecommendationRunCreate(
        repository_id=repo_id,
        pr_id="6",
        triggered_by="github-webhook",
        engine_version="v3"
    )

    run = service.create_recommendation_run(run_in)
    assert run is not None

    # Retrieve and verify stored architecture_impact in impact_profile
    run_record = db.query(RecommendationRun).filter(RecommendationRun.id == run.id).first()
    assert run_record is not None
    assert run_record.impact_profile is not None
    assert "architecture_impact" in run_record.impact_profile

    arch_impact = run_record.impact_profile["architecture_impact"]
    assert "touched_layers" in arch_impact
    assert "direct_dependencies" in arch_impact
    assert "indirect_dependencies" in arch_impact
    assert "integration_boundaries" in arch_impact
    assert "architectural_risks" in arch_impact
    assert "evidence" in arch_impact

    # Verify layer matches
    assert "API Layer" in arch_impact["touched_layers"]
    assert "UI Layer" in arch_impact["touched_layers"]
    assert any("High coupling threat" in r for r in arch_impact["architectural_risks"])
