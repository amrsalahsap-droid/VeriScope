import sys
sys.path.insert(0, ".")
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"

from app.db.base import Base
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.recommendation import RecommendationRun, SuggestedTestScenario, RecommendedTest
from app.models.user import Workspace
from app.services.recommendation import RecommendationService
from app.schemas.recommendation import RecommendationRunCreate
from app.models.test_result import TestCase as DBTestCase, TestRun as DBTestRun

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
db = Session()

workspace_id = uuid.uuid4()
repo_id = uuid.uuid4()
pr_id = uuid.uuid4()

workspace = Workspace(id=workspace_id, name="Test Space", slug="test-space")
db.add(workspace)

repo = Repository(
    id=repo_id,
    workspace_id=workspace_id,
    github_repo_id=111,
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
    github_pr_id=222,
    number=1,
    title="Upgrade login flow and payment system",
    author="engineer",
    source_branch="feat/auth-billing",
    target_branch="main",
    state="open",
    head_commit_sha="aabbccddee0011223344556677889900",
    github_created_at=datetime.utcnow(),
    github_updated_at=datetime.utcnow()
)
db.add(pr)

pr_file = PullRequestChangedFile(
    id=uuid.uuid4(),
    pull_request_id=pr_id,
    file_path="src/auth/login.py",
    status="modified"
)
db.add(pr_file)

tc = DBTestCase(
    id=uuid.uuid4(),
    repository_id=repo_id,
    suite_name="tests.auth",
    test_name="test_login",
    stable_identity="tests.auth::test_login",
    canonical_identity_hash="hash1",
    identity_lineage_root_hash="hash1"
)
db.add(tc)

tr = DBTestRun(
    id=uuid.uuid4(),
    repository_id=repo_id,
    status="SUCCESS",
    evidence_source="MANUAL_UPLOAD",
    evidence_artifact_type="JUNIT_XML",
    file_hash="hash_tr",
    normalized_execution_fingerprint="fingerprint_tr",
    created_at=datetime.utcnow()
)
db.add(tr)
db.commit()

service = RecommendationService(db)
run_in = RecommendationRunCreate(
    repository_id=repo_id,
    pr_id="1",
    triggered_by="github-webhook",
    engine_version="v3"
)

try:
    run = service.create_recommendation_run(run_in)
    print("Success! Suggested scenarios count:", len(run.suggested_scenarios))
except Exception as e:
    import traceback
    traceback.print_exc()
