import uuid
import jwt
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
import pytest
from unittest.mock import MagicMock, patch

# Monkeypatch UUID bind/result processors for SQLite compatibility
from sqlalchemy.dialects.postgresql import UUID
original_bind_processor = UUID.bind_processor
original_result_processor = UUID.result_processor

def patched_bind_processor(self, dialect):
    if dialect.name == 'sqlite':
        return lambda value: str(value) if value is not None else None
    return original_bind_processor(self, dialect)

def patched_result_processor(self, dialect, coltype):
    if dialect.name == 'sqlite':
        return lambda value: uuid.UUID(value) if isinstance(value, str) else value
    return original_result_processor(self, dialect, coltype)

UUID.bind_processor = patched_bind_processor
UUID.result_processor = patched_result_processor

from app.main import app
from app.db.session import get_db
from app.config import settings
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import RecommendationRun
from app.models.business_intent import BusinessIntentOverride
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.behavior import Behavior
from app.models.behavior_scenario import BehaviorScenario
from app.models.journey import Journey
from app.db.base import Base

def get_auth_headers():
    payload = {
        "email": "test@example.com",
        "name": "Test User",
        "avatar_url": None,
        "sub": "test_provider_id"
    }
    token = jwt.encode(payload, settings.STATE_SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def sqlite_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    
    # Deduplicate indexes to avoid sqlite3.OperationalError: index already exists
    for table in Base.metadata.tables.values():
        seen_names = set()
        to_remove = []
        for index in table.indexes:
            if index.name in seen_names:
                to_remove.append(index)
            else:
                seen_names.add(index.name)
        for index in to_remove:
            table.indexes.remove(index)
            
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def setup_test_auth_db(db: Session):
    user = db.query(User).filter(User.email == "test@example.com").first()
    if not user:
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            name="Test User",
            auth_provider="github"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
    workspace = db.query(Workspace).filter(Workspace.slug == "test-workspace").first()
    if not workspace:
        workspace = Workspace(
            id=uuid.UUID("361e6878-c1a7-4b71-b0db-b0352ef29b8c"),
            name="Test Workspace",
            slug="test-workspace",
            created_by_user_id=user.id
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        
    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.user_id == user.id,
        WorkspaceMember.workspace_id == workspace.id
    ).first()
    if not member:
        member = WorkspaceMember(
            id=uuid.uuid4(),
            user_id=user.id,
            workspace_id=workspace.id,
            role="OWNER"
        )
        db.add(member)
        db.commit()
        
    return workspace.id

def test_recommendation_staleness_flow(sqlite_db: Session):
    """
    Verify recommendation staleness behavior:
    1. Pasting manual AC marks the latest recommendation run stale.
    2. GET recommendation APIs expose the staleness fields.
    3. Regenerating creates a new fresh recommendation, leaving the old one stale.
    """
    # 1. Setup DB override for FastAPI
    app.dependency_overrides[get_db] = lambda: sqlite_db

    # 2. Setup auth, repo, and PR
    workspace_id = setup_test_auth_db(sqlite_db)
    
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=12345,
        name="test_repo",
        full_name="test_owner/test_repo",
        visibility="PUBLIC",
        is_active=True,
        selected_for_analysis=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    sqlite_db.add(repo)
    
    pr_id = uuid.uuid4()
    pr = PullRequest(
        id=pr_id,
        repository_id=repo_id,
        github_pr_id=54321,
        number=1,
        title="Test PR",
        author="test_author",
        source_branch="main",
        target_branch="main",
        state="open",
        changed_files_count=1,
        head_commit_sha="abcdef",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    sqlite_db.add(pr)
    sqlite_db.flush()

    from app.models.pull_request import PullRequestChangedFile
    cf = PullRequestChangedFile(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        file_path="app/services/dependency_extraction.py",
        status="modified",
        additions=1,
        deletions=1,
        created_at=datetime.utcnow()
    )
    sqlite_db.add(cf)
    sqlite_db.flush()

    from app.models.test_result import TestRun
    tr = TestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        commit_sha="abcdef",
        pull_request_id=pr_id,
        file_hash="dummy_hash",
        normalized_execution_fingerprint="dummy_fingerprint",
        status="SUCCESS",
        total_tests=1,
        passed_tests=1,
        failed_tests=0,
        skipped_tests=0,
        created_at=datetime.utcnow()
    )
    sqlite_db.add(tr)
    sqlite_db.flush()

    # 3. Create an initial historical RecommendationRun (before AC is added)
    initial_run_id = uuid.uuid4()
    initial_run = RecommendationRun(
        id=initial_run_id,
        repository_id=repo_id,
        pr_id=str(pr_id),
        pull_request_id=pr_id,
        triggered_by="MANUAL_DRY_RUN",
        evidence_quality="HIGH",
        engine_version="v3.0.0",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="Original recommendation reasoning summary.",
        created_at=datetime.utcnow() - timedelta(minutes=5),  # Generated 5 minutes ago
        input_stale=False
    )
    sqlite_db.add(initial_run)
    sqlite_db.commit()

    client = TestClient(app)
    headers = get_auth_headers()

    # 4. Verify initial run is NOT stale
    res = client.get(f"/api/recommendations/{initial_run_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["input_stale"] is False
    assert data["stale_reason"] is None

    # 5. Paste manual AC (this should mark the historical run stale)
    payload = {
        "business_change": "Implement secure user authentication",
        "affected_users": "All end users",
        "acceptance_criteria": "- User login must succeed with valid credentials.\n- Invalid credentials must be rejected.",
        "risk_notes": "Security risk",
        "testing_notes": "Test on staging environment"
    }
    
    response = client.post(
        f"/api/repositories/{repo_id}/pull-requests/{pr_id}/acceptance-criteria/manual",
        json=payload,
        headers=headers
    )
    assert response.status_code == 200
    assert response.json()["saved"] is True

    # 6. Verify historical run is now STALE in DB
    sqlite_db.refresh(initial_run)
    assert initial_run.input_stale is True
    assert initial_run.stale_reason == "Acceptance criteria were added after this recommendation was generated."
    assert "acceptance_criteria" in initial_run.stale_input_types

    # 7. Verify GET /api/recommendations/{id} returns stale info
    res = client.get(f"/api/recommendations/{initial_run_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["input_stale"] is True
    assert data["stale_reason"] == "Acceptance criteria were added after this recommendation was generated."
    assert data["stale_input_types"] == ["acceptance_criteria"]

    # 8. Verify GET /api/repositories/{repo_id}/pull-requests/{pr_id}/recommendation returns stale info
    res = client.get(f"/api/repositories/{repo_id}/pull-requests/{pr_id}/recommendation", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["input_stale"] is True
    assert data["stale_reason"] == "Acceptance criteria were added after this recommendation was generated."

    # 9. Regenerate recommendation and check that the new run is NOT stale
    mock_readiness = MagicMock()
    mock_readiness.readiness_state = "READY"
    mock_readiness.readiness_reasons = []

    with patch("app.services.repository_readiness.RepositoryReadinessService.calculate_readiness", return_value=mock_readiness):
        res = client.post(
            f"/api/repositories/{repo_id}/pull-requests/{pr_id}/recommendation",
            json={"readiness_acknowledged": True},
            headers=headers
        )
        assert res.status_code == 200, f"Response was: {res.status_code} - {res.json()}"
        new_run_data = res.json()
        new_run_id = uuid.UUID(new_run_data["recommendation_run_id"])
        
        # Verify the new run is NOT stale
        new_run = sqlite_db.query(RecommendationRun).filter(RecommendationRun.id == new_run_id).first()
        assert new_run is not None
        assert new_run.input_stale is False
        assert new_run.stale_reason is None

        # Verify old run remains stale
        sqlite_db.refresh(initial_run)
        assert initial_run.input_stale is True

    # Clean up overrides
    app.dependency_overrides.clear()
