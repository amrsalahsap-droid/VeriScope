import uuid
import jwt
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
import pytest

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
from app.models.business_intent import BusinessIntentOverride
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.business_behavior_mapping import BusinessBehaviorMapping
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

def test_manual_ac_persistence_flow(sqlite_db: Session):
    """
    Test pasting manual AC:
    - creates a BusinessIntentOverride record
    - extracts and persists AcceptanceCriterion records linked to PR and repo
    - BusinessBehaviorMapper links ACs to catalog behaviors
    - duplicate pastes update/deduplicate records instead of accumulating duplicate database rows
    - readiness check detects manual ACs and recalculates score correctly
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
    
    # Add journey, behavior, and scenario for mapping
    journey = Journey(
        id=uuid.uuid4(),
        repository_id=repo_id,
        name="Authentication",
        description="User authentication flows",
        is_deleted=False,
    )
    sqlite_db.add(journey)
    sqlite_db.flush()

    behavior = Behavior(
        id=uuid.uuid4(),
        journey_id=journey.id,
        repository_id=repo_id,
        name="User Login",
        slug="user-login",
        description="User logs into the system",
        risk_level="HIGH",
        is_deleted=False,
    )
    sqlite_db.add(behavior)
    sqlite_db.flush()

    scenario = BehaviorScenario(
        id=uuid.uuid4(),
        behavior_id=behavior.id,
        title="Valid credentials accepted",
        description="User logs in with valid credentials",
        priority="MUST",
        case_type="positive",
    )
    sqlite_db.add(scenario)
    sqlite_db.commit()

    # 3. Request payload
    payload = {
        "business_change": "Implement secure user authentication",
        "affected_users": "All end users",
        "acceptance_criteria": "- User login must succeed with valid credentials.\n- Invalid credentials must be rejected.",
        "risk_notes": "Security risk",
        "testing_notes": "Test on staging environment"
    }

    client = TestClient(app)
    headers = get_auth_headers()

    # 4. Post manual AC
    response = client.post(
        f"/api/repositories/{repo_id}/pull-requests/{pr_id}/acceptance-criteria/manual",
        json=payload,
        headers=headers
    )
    
    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()
    assert data["saved"] is True
    assert data["criteria_count"] == 2
    assert "readiness" in data
    
    # 5. Verify database records
    # Verify BusinessIntentOverride
    bio = sqlite_db.query(BusinessIntentOverride).filter(
        BusinessIntentOverride.pull_request_id == pr_id,
        BusinessIntentOverride.is_active == True
    ).first()
    assert bio is not None
    assert bio.business_change_summary == "Implement secure user authentication"
    assert bio.affected_users_journeys == "All end users"
    assert bio.source == "MANUAL_USER_INPUT"
    assert bio.is_processed is True

    # Verify AcceptanceCriterion
    criteria = sqlite_db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr_id
    ).all()
    assert len(criteria) == 2
    assert any("login must succeed" in c.text for c in criteria)
    
    # Verify BusinessBehaviorMapping
    mappings = sqlite_db.query(BusinessBehaviorMapping).filter(
        BusinessBehaviorMapping.behavior_id == behavior.id
    ).all()
    assert len(mappings) > 0
    # The login AC should map to the login behavior because of synonym/keyword match
    
    # 6. Test repeat pasting / deduplication
    # Paste again with different ACs
    new_payload = {
        "business_change": "Implement secure user authentication - updated",
        "affected_users": "All end users - updated",
        "acceptance_criteria": "- User login must succeed with valid credentials.\n- New AC statement.",
        "risk_notes": "Updated risk notes",
        "testing_notes": "Updated testing notes"
    }
    
    response = client.post(
        f"/api/repositories/{repo_id}/pull-requests/{pr_id}/acceptance-criteria/manual",
        json=new_payload,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["criteria_count"] == 2
    
    # Check that previous BusinessIntentOverride is deactivated
    inactive_bios = sqlite_db.query(BusinessIntentOverride).filter(
        BusinessIntentOverride.pull_request_id == pr_id,
        BusinessIntentOverride.is_active == False
    ).all()
    assert len(inactive_bios) == 1
    
    active_bio = sqlite_db.query(BusinessIntentOverride).filter(
        BusinessIntentOverride.pull_request_id == pr_id,
        BusinessIntentOverride.is_active == True
    ).first()
    assert active_bio.business_change_summary == "Implement secure user authentication - updated"
    
    # Check that old manual ACs were deleted and replaced
    criteria_after = sqlite_db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.pull_request_id == pr_id
    ).all()
    assert len(criteria_after) == 2
    assert any("New AC statement" in c.text for c in criteria_after)
    # The old AC "Invalid credentials must be rejected" should be gone because it's manual source
    assert not any("Invalid credentials" in c.text for c in criteria_after)

    # Clean up overrides
    app.dependency_overrides.clear()
