import uuid
from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine, text
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
from app.models.test_result import TestCase, TestResult, TestRun
from app.models.coverage import FileTestLink
from app.models.test_coverage_link import TestCoverageLink
from app.models.module_risk_profile import ModuleRiskProfile
from app.models.flaky_test import FlakyTestProfile
from app.models.user import Workspace
from app.models.domain_map import DomainMap
from app.models.dependency import FileDependency
from app.services.recommendation_logic_v3 import RecommendationLogicV3


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


def test_recommendation_engine_v3_multi_signal_ranking(db):
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    # Seed Workspace
    workspace = Workspace(id=workspace_id, name="Test Space", slug="test-space")
    db.add(workspace)
    db.flush()

    # Seed Repository (needed since pull_requests table has ForeignKey reference to repositories)
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=12345,
        name="test-repo",
        full_name="test-org/test-repo",
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
        number=1,
        title="Test PR",
        author="test-author",
        source_branch="feat",
        target_branch="main",
        state="open",
        head_commit_sha="eeddccbbaa00112233445566778899aa",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db.add(pr)

    # Seed Domain Map
    dm = DomainMap(
        id=uuid.uuid4(),
        repository_id=repo_id,
        domain="Authentication",
        files=["src/auth/middleware.py"],
        modules=["src/auth"],
        owners=[],
        created_at=datetime.utcnow()
    )
    db.add(dm)

    # 1. Seed Test Cases
    tc1_id = uuid.uuid4()
    tc1 = TestCase(
        id=tc1_id,
        repository_id=repo_id,
        suite_name="auth",
        test_name="should_allow_valid_token",
        stable_identity="auth.middleware::should_allow_valid_token",
        raw_test_name="should_allow_valid_token",
        normalized_test_name="should_allow_valid_token",
        normalized_identity_strategy="EXACT",
        framework_name="pytest",
        framework_version="1.0",
        identity_normalization_version="1.0",
        canonical_identity_hash="hash1",
        identity_lineage_root_hash="hash1",
        identity_version=1,
        identity_resolution_strategy="EXACT",
        created_at=datetime.utcnow()
    )

    tc2_id = uuid.uuid4()
    tc2 = TestCase(
        id=tc2_id,
        repository_id=repo_id,
        suite_name="auth",
        test_name="should_reject_invalid_token",
        stable_identity="auth.middleware::should_reject_invalid_token",
        raw_test_name="should_reject_invalid_token",
        normalized_test_name="should_reject_invalid_token",
        normalized_identity_strategy="EXACT",
        framework_name="pytest",
        framework_version="1.0",
        identity_normalization_version="1.0",
        canonical_identity_hash="hash2",
        identity_lineage_root_hash="hash2",
        identity_version=1,
        identity_resolution_strategy="EXACT",
        created_at=datetime.utcnow()
    )
    db.add(tc1)
    db.add(tc2)

    # Seed Pull Request Changed Files
    cf1 = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/auth/middleware.py",
        status="modified",
        additions=10,
        deletions=2,
        created_at=datetime.utcnow()
    )
    db.add(cf1)

    # Seed Test Run to satisfy test history check
    test_run = TestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        commit_sha="eeddccbbaa00112233445566778899aa",
        status="failed",
        evidence_health_status="HEALTHY",
        consistency_status="CONSISTENT",
        total_tests=1,
        passed_tests=0,
        failed_tests=1,
        skipped_tests=0,
        duration=5.2,
        file_hash="hash-fail-1",
        normalized_execution_fingerprint="fingerprint-fail-1",
        created_at=datetime.utcnow()
    )
    db.add(test_run)

    # Seed Coverage Link for tc1 (+40)
    ftl = FileTestLink(
        id=uuid.uuid4(),
        coverage_report_id=uuid.uuid4(),
        file_path="src/auth/middleware.py",
        test_case_id=tc1_id,
        mapping_type="DIRECT",
        confidence_score="HIGH"
    )
    db.add(ftl)

    # Seed TestCoverageLink for tc1 (+30) with manual overrides (+20) and escaped defects (+30)
    tcl = TestCoverageLink(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        repository_id=repo_id,
        test_identifier="auth.middleware::should_allow_valid_token",
        file_path="src/auth/middleware.py",
        override_count=1,
        defect_count=1
    )
    db.add(tcl)

    # Seed Module Risk Profile (+15)
    mrp = ModuleRiskProfile(
        id=uuid.uuid4(),
        repository_id=repo_id,
        module_path="src/auth/middleware.py",
        risk_score=50.0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(mrp)

    # Seed Historical Failure (+10)
    tr_fail = TestResult(
        id=uuid.uuid4(),
        test_run_id=test_run.id,
        test_case_id=tc1_id,
        status="failed",
        duration=5.2, # Runtime Cost (-5 points because round(5.2) = 5)
        created_at=datetime.utcnow()
    )
    db.add(tr_fail)

    db.commit()

    # Run Recommendation Engine V3
    recs = RecommendationLogicV3.generate_recommendations(
        db=db,
        repository_id=repo_id,
        pull_request_id=pr_id,
        workspace=workspace
    )

    assert len(recs) == 2
    rec = recs[0]

    # Verify scores:
    # Coverage Link: +40
    # Knowledge Graph: +30
    # Module Risk: +15
    # Historical Failure: +10
    # Manual Override History: +20
    # Escaped Defect Learning: +30
    # Domain Match Boost: +50
    # Architectural Impact Boost: +30
    # Module Match Boost: +30
    # Token Similarity Boost: +20
    # Runtime Cost: -5 (since rounded duration is 5)
    # Total Score: 40 + 30 + 15 + 10 + 20 + 30 + 50 + 30 + 30 + 20 - 5 = 270
    assert rec["test_identifier"] == "auth.middleware::should_allow_valid_token"
    assert rec["priority"] == 270.0
    assert rec["estimated_duration_seconds"] == 5.2
    assert rec["confidence"] == "80/100"

    # Verify formatting of reason
    reason = rec["reason"]
    assert "Confidence Score: 80/100" in reason
    assert "- Coverage: 40/40" in reason
    assert "- Graph: 30/30" in reason
    assert "- History: 5/10" in reason
    assert "- Overrides: 10/20" in reason

    assert "Coverage Link:\n+40" in reason
    assert "Knowledge Graph:\n+30" in reason
    assert "Module Risk:\n+15" in reason
    assert "Historical Failure:\n+10" in reason
    assert "Domain Match:\n+50" in reason
    assert "Architectural Impact:\n+30" in reason
    assert "Module Match:\n+30" in reason
    assert "Token Similarity:\n+20" in reason
    assert "Runtime Cost:\n-5" in reason
    assert "Total:\n270" in reason

    # Verify reason_details
    details = rec["reason_details"]
    assert details["coverage_link"] == 40
    assert details["knowledge_graph"] == 30
    assert details["module_risk"] == 15
    assert details["historical_failure"] == 10
    assert details["manual_override_history"] == 20
    assert details["escaped_defect_learning"] == 30
    assert details["domain_match"] == 50
    assert details["architectural_impact"] == 30
    assert details["module_match"] == 30
    assert details["token_similarity"] == 20
    assert details["runtime_cost"] == -5
    assert details["total"] == 270
