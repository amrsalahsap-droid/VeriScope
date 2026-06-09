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
from app.services.architectural_impact_engine import ArchitecturalImpactEngine


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


def test_empty_changed_files(db):
    repository_id = uuid.uuid4()
    commit_sha = "aabbcc"
    
    impact = ArchitecturalImpactEngine.analyze_impact(
        db,
        repository_id=repository_id,
        commit_sha=commit_sha,
        changed_files=[]
    )
    
    assert impact["impacted_files"] == []
    assert impact["discovered_services"] == []
    assert impact["impacted_domains"] == []
    assert impact["recommended_testing_types"] == []
    assert impact["explanation"] == "No changed files provided."


def test_transitive_reachability_and_cycle_safety(db):
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    commit_sha = "abc123commit"

    # Seed Workspace and Repository
    workspace = Workspace(id=workspace_id, name="Test Space", slug="test-space-arch")
    db.add(workspace)
    db.flush()

    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=12346,
        name="test-repo-arch",
        full_name="test-org/test-repo-arch",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)
    db.flush()

    # Seed dependencies:
    # 1. src/auth/reset-password.py -> src/auth/user.py
    # 2. src/users/profile.py -> src/auth/user.py
    # 3. src/auth/user.py -> shared/utils.py
    # 4. Cyclic dependency: file_A.py -> file_B.py -> file_A.py
    # 5. Outgoing / Incoming mix
    deps = [
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/auth/reset-password.py",
            depends_on_file_path="src/auth/user.py",
            dependency_type="import",
            commit_sha=commit_sha
        ),
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/users/profile.py",
            depends_on_file_path="src/auth/user.py",
            dependency_type="import",
            commit_sha=commit_sha
        ),
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/auth/user.py",
            depends_on_file_path="shared/utils.py",
            dependency_type="import",
            commit_sha=commit_sha
        ),
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="file_A.py",
            depends_on_file_path="file_B.py",
            dependency_type="import",
            commit_sha=commit_sha
        ),
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="file_B.py",
            depends_on_file_path="file_A.py",
            dependency_type="import",
            commit_sha=commit_sha
        )
    ]
    for d in deps:
        db.add(d)
    db.commit()

    # Test BFS and Transitive reachability starting from "src/auth/user.py"
    # Should traverse:
    # - outgoing to "shared/utils.py"
    # - incoming to "src/auth/reset-password.py" and "src/users/profile.py"
    impact1 = ArchitecturalImpactEngine.analyze_impact(
        db,
        repository_id=repo_id,
        commit_sha=commit_sha,
        changed_files=["src/auth/user.py"]
    )
    
    assert "src/auth/user.py" in impact1["impacted_files"]
    assert "src/auth/reset-password.py" in impact1["impacted_files"]
    assert "src/users/profile.py" in impact1["impacted_files"]
    assert "shared/utils.py" in impact1["impacted_files"]
    
    # Verify discovered services
    # "src/auth/user.py" and "src/auth/reset-password.py" -> auth service
    # "src/users/profile.py" -> user service
    assert "auth service" in impact1["discovered_services"]
    assert "user service" in impact1["discovered_services"]
    
    # Verify domains mapping
    # auth service -> Authentication
    # user service -> User Management
    assert "Authentication" in impact1["impacted_domains"]
    assert "User Management" in impact1["impacted_domains"]

    # Verify cycle safety
    impact2 = ArchitecturalImpactEngine.analyze_impact(
        db,
        repository_id=repo_id,
        commit_sha=commit_sha,
        changed_files=["file_A.py"]
    )
    # Both in cycle should be reached, but no infinite loops/recursion crashes
    assert sorted(impact2["impacted_files"]) == ["file_A.py", "file_B.py"]


def test_service_boundaries_and_testing_types(db):
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    commit_sha = "boundarycommit"

    workspace = Workspace(id=workspace_id, name="Test Space 2", slug="test-space-boundary")
    db.add(workspace)
    db.flush()

    repo = Repository(
        id=repo_id,
        workspace_id=workspace_id,
        github_repo_id=12347,
        name="test-repo-bound",
        full_name="test-org/test-repo-bound",
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(repo)
    db.flush()

    # Seed dependencies that cross service boundaries:
    # 1. api/router.py -> services/billing/charge.py
    # 2. services/billing/charge.py -> services/notifications/email.py
    # 3. services/notifications/email.py -> shared/util.py
    # 4. services/auth/login.py (isolated, not in graph)
    deps = [
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="api/router.py",
            depends_on_file_path="services/billing/charge.py",
            dependency_type="import",
            commit_sha=commit_sha
        ),
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="services/billing/charge.py",
            depends_on_file_path="services/notifications/email.py",
            dependency_type="import",
            commit_sha=commit_sha
        ),
        FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="services/notifications/email.py",
            depends_on_file_path="shared/util.py",
            dependency_type="import",
            commit_sha=commit_sha
        )
    ]
    for d in deps:
        db.add(d)
    db.commit()

    # Test starting from "services/billing/charge.py"
    impact = ArchitecturalImpactEngine.analyze_impact(
        db,
        repository_id=repo_id,
        commit_sha=commit_sha,
        changed_files=["services/billing/charge.py"]
    )

    # All files in the transitive tree should be impacted
    expected_files = {
        "services/billing/charge.py",
        "api/router.py",
        "services/notifications/email.py",
        "shared/util.py"
    }
    assert set(impact["impacted_files"]) == expected_files

    # Verify discovered services
    # api/router.py -> api service
    # services/billing/charge.py -> billing service
    # services/notifications/email.py -> notification service
    # shared/util.py does not match service keywords and prefix path is "shared", so it won't resolve to a service.
    expected_services = {"api service", "billing service", "notification service"}
    assert set(impact["discovered_services"]) == expected_services

    # Verify domains mapping
    expected_domains = {"API Endpoints", "Billing", "Email Notifications"}
    assert set(impact["impacted_domains"]) == expected_domains

    # Verify recommended testing types
    # - "Integration": >= 2 distinct services (we have 3) -> True
    # - "Workflow": api/router.py matches api/router/controller/route/endpoint -> True
    # - "Regression": shared/util.py has "shared", "common", "util" OR total impacted >= 5 -> True
    assert "Integration" in impact["recommended_testing_types"]
    assert "Workflow" in impact["recommended_testing_types"]
    assert "Regression" in impact["recommended_testing_types"]

    # Verify structured explanation contains expected substrings
    explanation = impact["explanation"]
    assert "api service" in explanation
    assert "billing service" in explanation
    assert "notification service" in explanation
    assert "API Endpoints" in explanation
    assert "Billing" in explanation
    assert "Email Notifications" in explanation
    assert "Integration" in explanation
    assert "Workflow" in explanation
    assert "Regression" in explanation
