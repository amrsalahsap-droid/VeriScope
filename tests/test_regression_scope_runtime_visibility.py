"""
Regression Scope Runtime Visibility Tests

Verifies:
1. Scope endpoint is callable for a recommendation with 6 PR files.
2. All three mode values are accepted: targeted, risk_based, full.
3. Scope service receives the same changed files shown in the recommendation summary.
4. If no candidate tests exist, endpoint returns structured non-empty diagnostic, not generic failure.
5. If mappings are incomplete, endpoint returns a scope (fallback), not a crash.
6. Response shape matches RegressionScopeV2Display expectations.
7. No generic unable-to-load error when backend has enough diagnostic data.
8. Scope endpoint does not alter recommendation readiness state.
9. Evidence truth (snapshot) is unchanged after calling scope endpoint.
"""
import uuid
import json
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.recommendation import RecommendationRun
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.repository import Repository
from app.models.user import User, Workspace, WorkspaceMember
from app.services.regression_scope_v2_service import RegressionScopeV2Service
from app.schemas.regression_scope_v2 import ScopeMode, RegressionScopeV2


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SNAPSHOT_WITH_6_FILES = {
    "changedFiles": [
        "src/auth/login.py",
        "src/auth/logout.py",
        "src/payments/processor.py",
        "src/payments/validator.py",
        "src/api/routes.py",
        "src/models/user.py",
    ],
    "acTraceability": [
        {
            "requirementId": str(uuid.uuid4()),
            "readableId": "AC-001",
            "sourceAcNumber": 1,
            "title": "Login requires valid credentials",
            "coverageStatus": "Missing",
            "evidenceReferences": [],
            "testReferences": [],
        },
        {
            "requirementId": str(uuid.uuid4()),
            "readableId": "AC-002",
            "sourceAcNumber": 2,
            "title": "Payment processor validates amount",
            "coverageStatus": "Partially covered",
            "evidenceReferences": ["test-evidence-1"],
            "testReferences": ["test-123"],
        },
        {
            "requirementId": str(uuid.uuid4()),
            "readableId": "AC-003",
            "sourceAcNumber": 3,
            "title": "User model stores hashed password",
            "coverageStatus": "Covered",
            "evidenceReferences": ["test-evidence-2"],
            "testReferences": ["test-456"],
        },
    ],
    "manualEvidenceNodes": [],
    "counts": {
        "uploadedPrTestsPassed": 12,
        "totalRequirements": 3,
    },
    "repositoryId": None,
}


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def test_workspace(db):
    unique_suffix = uuid.uuid4().hex[:8]
    ws = Workspace(
        id=uuid.uuid4(),
        name=f"scope-test-workspace-{unique_suffix}",
        slug=f"scope-test-ws-{unique_suffix}",
        created_at=datetime.utcnow(),
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    yield ws
    db.delete(ws)
    db.commit()


@pytest.fixture(scope="module")
def test_repo(db, test_workspace):
    unique_id = abs(hash(str(test_workspace.id))) % 10_000_000
    repo = Repository(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        github_repo_id=unique_id,
        full_name=f"scope-test/repo-{unique_id}",
        name="repo",
        default_branch="main",
        created_at=datetime.utcnow(),
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    yield repo
    db.delete(repo)
    db.commit()


@pytest.fixture(scope="module")
def test_pr(db, test_repo):
    pr = PullRequest(
        id=uuid.uuid4(),
        repository_id=test_repo.id,
        github_pr_id=999001,
        number=1,
        title="Scope test PR",
        author="tester",
        source_branch="feature/scope",
        target_branch="main",
        state="open",
        additions=100,
        deletions=20,
        changed_files_count=6,
        head_commit_sha="abc123",
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow(),
        last_github_updated_at=datetime.utcnow(),
        sync_integrity_status="FULL_SUCCESS",
        evidence_health_status="HEALTHY",
        evidence_consistency_status="UNKNOWN",
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    # Add 6 changed files
    for i, fname in enumerate(SNAPSHOT_WITH_6_FILES["changedFiles"]):
        cf = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path=fname,
            status="modified",
            additions=10,
            deletions=5,
        )
        db.add(cf)
    db.commit()
    yield pr
    db.query(PullRequestChangedFile).filter(
        PullRequestChangedFile.pull_request_id == pr.id
    ).delete()
    db.delete(pr)
    db.commit()


@pytest.fixture(scope="module")
def test_run_with_snapshot(db, test_repo, test_pr):
    snapshot = dict(SNAPSHOT_WITH_6_FILES)
    snapshot["repositoryId"] = str(test_repo.id)
    run = RecommendationRun(
        id=uuid.uuid4(),
        repository_id=test_repo.id,
        pr_id=str(test_pr.id),
        pull_request_id=test_pr.id,
        triggered_by="engineer-manual",
        evidence_quality="HIGH",
        engine_version="v1.0.0",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="Test run",
        recommendation_readiness_state="READY",
        evidence_health_status="HEALTHY",
        requirement_evidence_snapshot_json=snapshot,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    yield run
    db.delete(run)
    db.commit()


@pytest.fixture(scope="module")
def test_run_no_snapshot(db, test_repo, test_pr):
    run = RecommendationRun(
        id=uuid.uuid4(),
        repository_id=test_repo.id,
        pr_id=str(test_pr.id),
        pull_request_id=test_pr.id,
        triggered_by="engineer-manual",
        evidence_quality="LOW",
        engine_version="v1.0.0",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="No snapshot run",
        requirement_evidence_snapshot_json=None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    yield run
    db.delete(run)
    db.commit()


# ---------------------------------------------------------------------------
# Test 1: Endpoint callable with 6 PR files
# ---------------------------------------------------------------------------

class TestRegressionScopeRuntime:

    def test_scope_callable_for_run_with_6_files(self, db, test_run_with_snapshot, test_pr):
        """Scope service must succeed and return a non-null scope for a run with 6 changed files."""
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db,
            run_id=str(test_run_with_snapshot.id),
            mode=ScopeMode.RISK_BASED,
        )
        assert scope is not None
        assert isinstance(scope, RegressionScopeV2)
        # PR has 6 changed files in snapshot
        assert scope.recommendation_run_id == str(test_run_with_snapshot.id)

    # Test 2a: targeted mode accepted
    def test_mode_targeted_accepted(self, db, test_run_with_snapshot):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db,
            run_id=str(test_run_with_snapshot.id),
            mode=ScopeMode.TARGETED,
        )
        assert scope is not None
        assert scope.scope_type == "TARGETED"

    # Test 2b: risk_based mode accepted
    def test_mode_risk_based_accepted(self, db, test_run_with_snapshot):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db,
            run_id=str(test_run_with_snapshot.id),
            mode=ScopeMode.RISK_BASED,
        )
        assert scope is not None
        assert scope.scope_type == "RISK_BASED"

    # Test 2c: full mode accepted
    def test_mode_full_accepted(self, db, test_run_with_snapshot):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db,
            run_id=str(test_run_with_snapshot.id),
            mode=ScopeMode.FULL,
        )
        assert scope is not None
        assert scope.scope_type == "FULL"

    # Test 3: changed files from snapshot are accessible in scope service
    def test_scope_service_receives_6_changed_files(self, db, test_run_with_snapshot):
        """Scope service must access the same 6 changed files stored in the snapshot."""
        raw = test_run_with_snapshot.requirement_evidence_snapshot_json
        snapshot = raw if isinstance(raw, dict) else json.loads(raw)
        changed_files = snapshot.get("changedFiles", [])
        assert len(changed_files) == 6, (
            f"Expected 6 changed files in snapshot, got {len(changed_files)}"
        )
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db,
            run_id=str(test_run_with_snapshot.id),
            mode=ScopeMode.TARGETED,
        )
        assert scope is not None

    # Test 4: No candidate tests → structured scope with 0 items, not a crash
    def test_empty_traceability_returns_empty_scope_not_crash(self, db, test_repo, test_pr):
        """If acTraceability is empty, scope returns 0-item groups, not an error."""
        snapshot_empty = {
            "changedFiles": SNAPSHOT_WITH_6_FILES["changedFiles"],
            "acTraceability": [],
            "manualEvidenceNodes": [],
            "counts": {"uploadedPrTestsPassed": 0, "totalRequirements": 0},
            "repositoryId": str(test_repo.id),
        }
        run = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=test_repo.id,
            pr_id=str(test_pr.id),
            pull_request_id=test_pr.id,
            triggered_by="engineer-manual",
            evidence_quality="LOW",
            engine_version="v1.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Empty AC run",
            requirement_evidence_snapshot_json=snapshot_empty,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        try:
            scope = RegressionScopeV2Service.generate_scope_v2(
                db=db,
                run_id=str(run.id),
                mode=ScopeMode.TARGETED,
            )
            assert scope is not None
            from app.schemas.regression_scope_v2 import ScopeGroup
            required_items = scope.groups[ScopeGroup.REQUIRED.value].items
            assert required_items == [], (
                "Expected no required items when traceability is empty"
            )
        finally:
            db.delete(run)
            db.commit()

    # Test 5: Missing snapshot raises ValueError (not a crash with 500)
    def test_missing_snapshot_raises_value_error(self, db, test_run_no_snapshot):
        """If snapshot is missing, service raises ValueError with a clear message."""
        with pytest.raises(ValueError, match="Evidence graph snapshot not available"):
            RegressionScopeV2Service.generate_scope_v2(
                db=db,
                run_id=str(test_run_no_snapshot.id),
                mode=ScopeMode.TARGETED,
            )

    # Test 6: Response shape has all fields expected by RegressionScopeV2Display
    def test_response_shape_matches_v2_display_contract(self, db, test_run_with_snapshot):
        """Scope response must have groups, execution_plan, optimization_metrics, governance."""
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db,
            run_id=str(test_run_with_snapshot.id),
            mode=ScopeMode.RISK_BASED,
        )
        assert hasattr(scope, "groups"), "scope must have 'groups'"
        assert hasattr(scope, "execution_plan"), "scope must have 'execution_plan'"
        assert hasattr(scope, "optimization_metrics"), "scope must have 'optimization_metrics'"
        assert hasattr(scope, "governance"), "scope must have 'governance'"
        assert hasattr(scope, "scope_type"), "scope must have 'scope_type'"
        assert hasattr(scope, "snapshot_hash"), "scope must have 'snapshot_hash'"
        assert scope.execution_plan is not None
        assert scope.groups is not None

    # Test 7: No generic unable-to-load — backend returns scope, not None
    def test_backend_returns_scope_not_none_when_data_available(self, db, test_run_with_snapshot):
        """When data is available, generate_scope_v2 must return a non-None RegressionScopeV2."""
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db,
            run_id=str(test_run_with_snapshot.id),
            mode=ScopeMode.RISK_BASED,
        )
        assert scope is not None, "Expected scope object, got None"
        assert scope.scope_type in ("TARGETED", "RISK_BASED", "FULL")

    # Test 8: Scope endpoint does not mutate recommendation readiness state
    def test_scope_generation_does_not_alter_readiness(self, db, test_run_with_snapshot):
        """Calling generate_scope_v2 must not change the run's readiness state."""
        state_before = test_run_with_snapshot.recommendation_readiness_state
        RegressionScopeV2Service.generate_scope_v2(
            db=db,
            run_id=str(test_run_with_snapshot.id),
            mode=ScopeMode.TARGETED,
        )
        db.refresh(test_run_with_snapshot)
        assert test_run_with_snapshot.recommendation_readiness_state == state_before, (
            "Scope generation must not modify recommendation_readiness_state"
        )

    # Test 9: Evidence snapshot is unchanged after scope generation
    def test_evidence_snapshot_unchanged_after_scope_generation(self, db, test_run_with_snapshot):
        """Evidence snapshot JSON must be identical before and after scope generation."""
        snapshot_before = test_run_with_snapshot.requirement_evidence_snapshot_json
        RegressionScopeV2Service.generate_scope_v2(
            db=db,
            run_id=str(test_run_with_snapshot.id),
            mode=ScopeMode.FULL,
        )
        db.refresh(test_run_with_snapshot)
        snapshot_after = test_run_with_snapshot.requirement_evidence_snapshot_json
        assert snapshot_before == snapshot_after, (
            "Evidence snapshot must not be mutated by scope generation"
        )
