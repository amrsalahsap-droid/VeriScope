import uuid
from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

# SQLite compilation helper for PostgreSQL JSONB columns
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

from app.db.base import Base
from app.models.repository import Repository
from app.models.dependency import FileDependency
from app.models.user import Workspace
from app.models.test_result import TestCase
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.recommendation import RecommendationRun
from app.services.dependency_impact_engine import DependencyImpactEngine
from app.services.recommendation_logic_v3 import RecommendationLogicV3
from app.services.recommendation_reasoning_engine import RecommendationReasoningEngine


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


def test_component_mapping():
    # Test router mapping
    assert DependencyImpactEngine.map_path_to_component("app/routers/auth.py") == "auth route"
    assert DependencyImpactEngine.map_path_to_component("src/routers/reset-password.ts") == "reset-password route"
    assert DependencyImpactEngine.map_path_to_component("api/routers/billing_router.py") == "billing route"
    
    # Test service mapping
    assert DependencyImpactEngine.map_path_to_component("app/services/auth_service.py") == "auth service"
    assert DependencyImpactEngine.map_path_to_component("src/services/notification.py") == "notification service"
    
    # Test model mapping
    assert DependencyImpactEngine.map_path_to_component("app/models/user.py") == "user model"


def test_dependency_impact_traces(db):
    repository_id = uuid.uuid4()
    commit_sha = "mock_commit_sha"

    # Seed some fake file dependency mappings to test the reachability
    deps = [
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repository_id,
            file_path="src/routers/reset-password.ts",
            depends_on_file_path="src/services/auth_service.py",
            dependency_type="import",
            commit_sha=commit_sha
        ),
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repository_id,
            file_path="src/services/auth_service.py",
            depends_on_file_path="src/services/notification.py",
            dependency_type="import",
            commit_sha=commit_sha
        )
    ]
    for d in deps:
        db.add(d)
    db.commit()

    impact = DependencyImpactEngine.analyze_dependency_impact(
        db,
        repository_id=repository_id,
        commit_sha=commit_sha,
        changed_files=["src/routers/reset-password.ts"]
    )

    # 1. Assert Direct Impact resolves correctly
    assert len(impact["direct_impacts"]) == 1
    assert impact["direct_impacts"][0]["source"] == "reset-password route"
    assert impact["direct_impacts"][0]["target"] == "auth service"

    # 2. Assert Indirect Impact (multi-hop) resolves correctly
    assert len(impact["indirect_impacts"]) >= 1
    indirect_target_services = [imp["target"] for imp in impact["indirect_impacts"]]
    assert "notification service" in indirect_target_services

    # 3. Assert Trace paths format cleanly and correctly match example
    expected_trace = "reset-password route → auth service → notification service"
    assert expected_trace in impact["traces"]


def test_v3_recommendations_and_reasoning_integration(db):
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    commit_sha = "recommendation_commit"

    workspace = Workspace(id=workspace_id, name="Test Space v3", slug="test-space-v3")
    db.add(workspace)
    db.flush()

    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=98765,
        name="test-repo-v3",
        full_name="test-org/test-repo-v3",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)
    db.flush()

    # Seed PR changed files
    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=12345,
        number=1,
        title="Test PR",
        author="test-author",
        source_branch="feat",
        target_branch="main",
        state="OPEN",
        head_commit_sha=commit_sha,
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(pr)
    db.flush()

    changed_file = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="src/routers/reset-password.ts",
        additions=10,
        deletions=2,
        status="modified"
    )
    db.add(changed_file)
    db.flush()

    # Seed FileDependency to trigger the indirect risk
    deps = [
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/routers/reset-password.ts",
            depends_on_file_path="src/services/auth_service.py",
            dependency_type="import",
            commit_sha=commit_sha
        ),
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/services/auth_service.py",
            depends_on_file_path="src/services/notification.py",
            dependency_type="import",
            commit_sha=commit_sha
        )
    ]
    for d in deps:
        db.add(d)
    db.flush()

    # Seed TestCase that maps to the transitively impacted service file
    tc = TestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        stable_identity="tests/services/test_notification.ts::test_send_email",
        test_name="test_send_email",
        suite_name="test_notification",
        framework_name="jest",
        canonical_identity_hash="mock_hash",
        identity_lineage_root_hash="mock_root_hash"
    )
    db.add(tc)
    db.flush()

    # Seed historical test run to make sure test runs count > 0 is satisfied
    from app.models.test_result import TestRun
    tr = TestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        commit_sha=commit_sha,
        status="passed",
        file_hash="mock_file_hash",
        normalized_execution_fingerprint="mock_fingerprint",
        created_at=datetime.utcnow()
    )
    db.add(tr)
    db.flush()

    # Integrate CoverageReport and FileTestLink so Veriscope maps this test case to the notification service file
    from app.models.coverage import CoverageReport, FileTestLink
    cov_report = CoverageReport(
        id=uuid.uuid4(),
        repository_id=repo_id,
        workspace_id=workspace_id,
        format="LCOV",
        source="MANUAL_UPLOAD",
        coverage_confidence="HIGH",
        evidence_health_status="HEALTHY",
        file_hash="mock_cov_file_hash",
        confidence_score="HIGH",
        commit_sha=commit_sha
    )
    db.add(cov_report)
    db.flush()

    link = FileTestLink(
        id=uuid.uuid4(),
        coverage_report_id=cov_report.id,
        test_case_id=tc.id,
        file_path="src/services/notification.py",
        mapping_type="DIRECT",
        confidence_score="HIGH"
    )
    db.add(link)
    db.commit()

    # Generate V3 recommendations
    recs = RecommendationLogicV3.generate_recommendations(
        db=db,
        repository_id=repo_id,
        pull_request_id=pr_id,
        workspace=workspace
    )

    # 1. Assert indirect dependency boost (+25 points) was applied
    assert len(recs) == 1
    rec_entry = recs[0]
    assert rec_entry["source_signal"] == "INDIRECT_DEPENDENCY_IMPACT"
    assert rec_entry["reason_details"]["indirect_dependency_impact"] == 25
    assert "reset-password route → auth service → notification service" in rec_entry["reason_details"]["dependency_impact_trace"]

    # Assert mathematical confidence scoring yields exactly 33% (10/30) and contains the correct breakdown in reason
    assert rec_entry["confidence"] == "33/100"
    assert "Confidence Score: 33/100" in rec_entry["reason"]
    assert "- Dependency: 10/30" in rec_entry["reason"]

    # 2. Verify plain English reasoning output from ReasoningEngine
    signals = rec_entry["reason_details"]
    bullets = RecommendationReasoningEngine.generate_explanation(signals)
    assert len(bullets) >= 1
    
    # 3. Assert trace appears inside the bullet point reasoning
    expected_bullet_substring = "Indirect dependency risk: This test covers components with indirect exposure to reset-password route → auth service → notification service."
    assert expected_bullet_substring in bullets
