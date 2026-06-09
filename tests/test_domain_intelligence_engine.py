import uuid
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

# Register custom SQLite type compilers for PostgreSQL-specific types
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "TEXT"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"

from app.db.base import Base
# Make sure all models are imported so they are registered on Base
import app.models  # noqa
from app.models.domain_map import DomainMap
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestCase, TestRun, TestResult
from app.models.coverage import CoverageReport, CoverageFileEntry
from app.models.user import Workspace
from app.services.domain_intelligence_engine import DomainIntelligenceEngine
from app.services.recommendation_logic_v3 import RecommendationLogicV3


@pytest.fixture(scope="module")
def db_session():
    """Sets up an in-memory SQLite database and registers all schemas."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_domain_intelligence_learning(db_session):
    """Verify that DomainIntelligenceEngine successfully matches folders, filenames, and historical PRs."""
    # Seed repository and workspace
    repo_id = uuid.uuid4()
    
    # 1. Seed CoverageFileEntry records
    cov_report_id = uuid.uuid4()
    
    # We will seed files with 'auth', 'billing', 'notifications' keywords
    files_to_seed = [
        "app/services/auth_service.py",
        "app/api/billing/checkout.py",
        "app/components/notifications/alert_banner.tsx",
        "app/models/users.py",
        "app/utils/unrelated.py"
    ]
    
    for fp in files_to_seed:
        entry = CoverageFileEntry(
            id=uuid.uuid4(),
            coverage_report_id=cov_report_id,
            repository_id=repo_id,
            file_path=fp,
            total_lines=10,
            covered_lines_count=8,
            uncovered_lines_count=2
        )
        db_session.add(entry)
        
    # 2. Seed historical Pull Requests and their changed files
    # PR 1 title mentions 'Authentication'
    pr1_id = uuid.uuid4()
    pr1 = PullRequest(
        id=pr1_id,
        repository_id=repo_id,
        github_pr_id=12345,
        number=1,
        title="Authentication: Upgrade token verification system",
        author="engineer1",
        source_branch="feature/auth-token",
        target_branch="main",
        state="closed",
        head_commit_sha="sha1",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db_session.add(pr1)
    
    # File in PR 1 that gets associated with Authentication domain
    pr1_file = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr1_id,
        file_path="app/middleware/auth_token_validator.py",
        status="modified"
    )
    db_session.add(pr1_file)
    
    # 3. Seed TestCase and TestResult for test runs
    tc1_id = uuid.uuid4()
    tc1 = TestCase(
        id=tc1_id,
        repository_id=repo_id,
        suite_name="app.services.test_auth_service",
        test_name="test_login_success",
        stable_identity="app.services.test_auth_service::test_login_success",
        canonical_identity_hash="hash1",
        identity_lineage_root_hash="hash1"
    )
    db_session.add(tc1)
    
    db_session.commit()
    
    # Trigger dynamic domain learning
    learned_maps = DomainIntelligenceEngine.learn_domains(db_session, repo_id)
    
    # Verify Authentication domain
    auth_map = next((m for m in learned_maps if m.domain == "Authentication"), None)
    assert auth_map is not None
    assert "app/services/auth_service.py" in auth_map.files
    assert "app/middleware/auth_token_validator.py" in auth_map.files
    assert "app.services.auth_service" in auth_map.modules
    
    # Verify Billing domain
    billing_map = next((m for m in learned_maps if m.domain == "Billing"), None)
    assert billing_map is not None
    assert "app/api/billing/checkout.py" in billing_map.files
    
    # Verify User Management domain
    users_map = next((m for m in learned_maps if m.domain == "User Management"), None)
    assert users_map is not None
    assert "app/models/users.py" in users_map.files
    
    # Verify unrelated files are NOT in learned domains
    for m in learned_maps:
        assert "app/utils/unrelated.py" not in m.files


def test_recommendation_logic_v3_domain_prioritization(db_session):
    """Verify that RecommendationLogicV3 correctly boosts test case prioritization using domain maps."""
    repo_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    
    workspace = Workspace(
        id=workspace_id,
        name="Veriscope Team Workspace",
        slug="veriscope-team",
        created_at=datetime.utcnow()
    )
    db_session.add(workspace)
    
    # Pre-populate some historical test cases and runs so V3 logic runs (required)
    tr = TestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        status="SUCCESS",
        evidence_source="MANUAL_UPLOAD",
        evidence_artifact_type="JUNIT_XML",
        file_hash="hash1",
        normalized_execution_fingerprint="fingerprint1",
        created_at=datetime.utcnow()
    )
    db_session.add(tr)
    
    # Test case sharing the active Billing domain
    tc_billing_id = uuid.uuid4()
    tc_billing = TestCase(
        id=tc_billing_id,
        repository_id=repo_id,
        suite_name="tests.billing.test_pricing",
        test_name="test_checkout_slider",
        stable_identity="tests.billing.test_pricing::test_checkout_slider",
        canonical_identity_hash="hash_billing",
        identity_lineage_root_hash="hash_billing"
    )
    db_session.add(tc_billing)
    
    # Test case not sharing the active Billing domain (unrelated)
    tc_other_id = uuid.uuid4()
    tc_other = TestCase(
        id=tc_other_id,
        repository_id=repo_id,
        suite_name="tests.utils.test_helpers",
        test_name="test_uuid_parser",
        stable_identity="tests.utils.test_helpers::test_uuid_parser",
        canonical_identity_hash="hash_helpers",
        identity_lineage_root_hash="hash_helpers"
    )
    db_session.add(tc_other)
    
    # Add a historical failure in the last 30 days to make BOTH tests recommendable,
    # or ensure they have at least one valid signal so they are not discarded.
    cutoff = datetime.utcnow() - timedelta(days=5)
    tr_fail = TestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        status="FAILURE",
        evidence_source="MANUAL_UPLOAD",
        evidence_artifact_type="JUNIT_XML",
        file_hash="hash2",
        normalized_execution_fingerprint="fingerprint2",
        created_at=cutoff
    )
    db_session.add(tr_fail)
    
    res_billing = TestResult(
        id=uuid.uuid4(),
        test_run_id=tr_fail.id,
        test_case_id=tc_billing_id,
        status="failed",
        duration=1.2,
        created_at=cutoff
    )
    db_session.add(res_billing)
    
    res_other = TestResult(
        id=uuid.uuid4(),
        test_run_id=tr_fail.id,
        test_case_id=tc_other_id,
        status="failed",
        duration=0.8,
        created_at=cutoff
    )
    db_session.add(res_other)
    
    # Active changed file belongs to Billing domain
    pr_id = uuid.uuid4()
    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=54321,
        number=2,
        title="Add custom checkout slider component",
        author="developer",
        source_branch="feature/checkout-slider",
        target_branch="main",
        state="open",
        head_commit_sha="sha2",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow()
    )
    db_session.add(pr)
    
    pr_file = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/modules/billing/subscription.ts",
        status="modified"
    )
    db_session.add(pr_file)
    
    # Manually create the Billing DomainMap record in database
    domain_map = DomainMap(
        id=uuid.uuid4(),
        repository_id=repo_id,
        domain="Billing",
        files=["src/modules/billing/subscription.ts"],
        modules=["tests.billing.test_pricing"],
        owners=[]
    )
    db_session.add(domain_map)
    
    db_session.commit()
    
    # Generate recommendations
    recommendations = RecommendationLogicV3.generate_recommendations(
        db=db_session,
        repository_id=repo_id,
        pull_request_id=pr_id,
        workspace=workspace
    )
    
    # Billing test case should be boosted by +50 points
    rec_billing = next((r for r in recommendations if r["test_identifier"] == tc_billing.stable_identity), None)
    assert rec_billing is not None
    assert rec_billing["reason_details"]["domain_match"] == 50
    # Total priority score should include: 10 (historical failure) - 1 (duration round) + 50 (domain match) + 30 (module match) + 20 (token similarity) = 109
    assert rec_billing["priority"] == 109
    
    # Unrelated test case should NOT be boosted (0 domain match)
    rec_other = next((r for r in recommendations if r["test_identifier"] == tc_other.stable_identity), None)
    assert rec_other is not None
    assert rec_other["reason_details"]["domain_match"] == 0
    # Total priority score should include: 10 (historical failure) - 1 (duration round) = 9
    assert rec_other["priority"] == 9
    
    # Ensure explanation bullet is formatted and prepended first
    assert "Domain match: Test and changed files both reside in the 'Billing' business domain." in rec_billing["reason"]
    # The domain match bullet should be the very first line of the explanation
    lines = rec_billing["reason"].split("\n")
    assert lines[0] == "- Domain match: Test and changed files both reside in the 'Billing' business domain."
