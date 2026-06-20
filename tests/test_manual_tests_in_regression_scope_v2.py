"""Phase 6.3 - Manual tests as first-class MANUAL_TEST scope items in RegressionScopeV2.

These tests verify that manual tests appear as execution recommendations in the
unified regression scope V2, without ever changing automated coverage, evidence
counts, readiness, or release decisions.

The evidence snapshot is crafted directly so coverage status / manual outcome are
deterministic. The manual evidence channel itself (graph building) is covered by
tests/test_manual_evidence_channel.py.
"""

import json
import uuid
import copy
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import RecommendationRun
from app.services.regression_scope_v2_service import RegressionScopeV2Service
from app.schemas.regression_scope_v2 import ScopeMode, ScopeGroup, ScopeItemType


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

AC_MISSING_ID = str(uuid.uuid4())
AC_PARTIAL_ID = str(uuid.uuid4())
AC_COVERED_ID = str(uuid.uuid4())

MT_MISSING_ID = str(uuid.uuid4())
MT_PARTIAL_ID = str(uuid.uuid4())
MT_COVERED_ID = str(uuid.uuid4())


def _build_snapshot(include_manual: bool = True, duplicate_manual: bool = False) -> dict:
    """Build an evidence snapshot with 3 ACs (missing/partial/covered)."""
    ac_traceability = [
        {
            "requirementId": AC_MISSING_ID,
            "readableId": "AC-12",
            "title": "Verify password reset email",
            "fullText": "Verify password reset email",
            "coverageStatus": "Missing",
            "linkedExistingTests": [],
            "linkedMissingTest": "Password reset email test",
            "priority": "Must",
            "notes": "",
            "manualSupportStatus": "MANUAL_NOT_EXECUTED",
            "manualValidation": {},
        },
        {
            "requirementId": AC_PARTIAL_ID,
            "readableId": "AC-5",
            "title": "Validate session timeout",
            "fullText": "Validate session timeout",
            "coverageStatus": "Partially covered",
            "linkedExistingTests": ["test_session"],
            "linkedMissingTest": None,
            "priority": "Recommended",
            "notes": "",
            "manualSupportStatus": "MANUAL_NOT_EXECUTED",
            "manualValidation": {},
        },
        {
            "requirementId": AC_COVERED_ID,
            "readableId": "AC-3",
            "title": "Login with valid credentials",
            "fullText": "Login with valid credentials",
            "coverageStatus": "Covered",
            "linkedExistingTests": ["test_login"],
            "linkedMissingTest": None,
            "priority": "Recommended",
            "notes": "",
            "manualSupportStatus": "MANUALLY_SUPPORTED",
            "manualValidation": {},
        },
    ]

    manual_nodes = []
    if include_manual:
        manual_nodes = [
            {
                "manualTestId": MT_MISSING_ID,
                "manualTestTitle": "Verify password reset email",
                "externalKey": "MT-12",
                "provider": "MANUAL_CSV",
                "readableId": "MT-MT-12",
                "acceptanceCriterionId": AC_MISSING_ID,
                "sourceAcNumber": 12,
                "outcome": "NOT_EXECUTED",
                "executedBy": None,
                "executedAt": None,
                "notes": None,
                "evidenceUrl": None,
                "mappingSource": "MANUAL",
                "evidenceSource": "MANUAL",
            },
            {
                "manualTestId": MT_PARTIAL_ID,
                "manualTestTitle": "Validate session timeout manually",
                "externalKey": "MT-5",
                "provider": "TESTRAIL",
                "readableId": "MT-MT-5",
                "acceptanceCriterionId": AC_PARTIAL_ID,
                "sourceAcNumber": 5,
                "outcome": "NOT_EXECUTED",
                "executedBy": None,
                "executedAt": None,
                "notes": None,
                "evidenceUrl": None,
                "mappingSource": "MANUAL",
                "evidenceSource": "MANUAL",
            },
            {
                "manualTestId": MT_COVERED_ID,
                "manualTestTitle": "Login smoke check",
                "externalKey": "MT-3",
                "provider": "MANUAL_CSV",
                "readableId": "MT-MT-3",
                "acceptanceCriterionId": AC_COVERED_ID,
                "sourceAcNumber": 3,
                "outcome": "PASSED",
                "executedBy": "QA User",
                "executedAt": "2026-01-01T00:00:00Z",
                "notes": None,
                "evidenceUrl": None,
                "mappingSource": "MANUAL",
                "evidenceSource": "MANUAL",
            },
        ]
        if duplicate_manual:
            # Exact duplicate mapping for the missing AC (e.g. re-import)
            manual_nodes.append(copy.deepcopy(manual_nodes[0]))

    return {
        "health": "VALIDATION_PASSED_COVERAGE_INCOMPLETE",
        "counts": {
            "totalRequirements": 25,
            "uploadedPrTestsPassed": 18,
            "verifiedTests": 16,
            "partiallyCovered": 2,
            "missingAutomatedCoverage": 7,
        },
        "acTraceability": ac_traceability,
        "manualEvidenceNodes": manual_nodes,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def test_user(db: Session):
    user = User(
        email=f"scope-v2-{uuid.uuid4().hex[:6]}@example.com",
        name="Scope V2 User",
        auth_provider="github",
        provider_user_id=f"scope-v2-{uuid.uuid4().hex[:6]}",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.delete(user)
    db.commit()


@pytest.fixture
def test_workspace(db: Session, test_user: User):
    workspace = Workspace(
        name=f"Workspace-{uuid.uuid4().hex[:6]}",
        slug=f"workspace-{uuid.uuid4().hex[:6]}",
        created_by_user_id=test_user.id,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    member = WorkspaceMember(workspace_id=workspace.id, user_id=test_user.id, role="OWNER")
    db.add(member)
    db.commit()
    yield workspace
    db.delete(member)
    db.delete(workspace)
    db.commit()


@pytest.fixture
def test_repository(db: Session, test_workspace: Workspace):
    repo = Repository(
        name="scope-v2-repo",
        full_name=f"test-owner/scope-v2-{uuid.uuid4().hex[:6]}",
        owner="test-owner",
        github_repo_id=int(uuid.uuid4().int % 10000000),
        workspace_id=test_workspace.id,
        is_active=True,
        selected_for_analysis=True,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    yield repo
    db.delete(repo)
    db.commit()


@pytest.fixture
def test_pr(db: Session, test_repository: Repository):
    pr = PullRequest(
        id=uuid.uuid4(),
        repository_id=test_repository.id,
        github_pr_id=int(uuid.uuid4().int % 10000000),
        number=1,
        title="PR for Manual Scope V2",
        author="test-author",
        source_branch="feature",
        target_branch="main",
        state="open",
        head_commit_sha="b" * 40,
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    yield pr
    db.delete(pr)
    db.commit()


def _make_run(db: Session, repo: Repository, pr: PullRequest, snapshot: dict) -> RecommendationRun:
    run = RecommendationRun(
        id=uuid.uuid4(),
        repository_id=repo.id,
        pull_request_id=pr.id,
        pr_id=str(pr.id),
        triggered_by="github-webhook",
        evidence_quality="HIGH",
        engine_version="v3",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="Manual scope v2 test run",
        requirement_evidence_snapshot_json=json.dumps(snapshot),
        created_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@pytest.fixture
def run_with_manual(db: Session, test_repository: Repository, test_pr: PullRequest):
    run = _make_run(db, test_repository, test_pr, _build_snapshot(include_manual=True))
    yield run
    db.delete(run)
    db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _manual_items(scope):
    items = []
    for summary in scope.groups.values():
        for item in summary.items:
            if item.item_type == ScopeItemType.MANUAL_TEST:
                items.append(item)
    return items


def _group_items(scope, group: ScopeGroup):
    return scope.groups[group.value].items


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestManualTestsInRegressionScopeV2:

    def test_missing_critical_ac_manual_in_required(self, db, run_with_manual):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        required_manual = [i for i in _group_items(scope, ScopeGroup.REQUIRED) if i.item_type == ScopeItemType.MANUAL_TEST]
        assert any(i.source_ac_number == 12 for i in required_manual)

    def test_partial_ac_manual_in_recommended(self, db, run_with_manual):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        rec_manual = [i for i in _group_items(scope, ScopeGroup.RECOMMENDED) if i.item_type == ScopeItemType.MANUAL_TEST]
        assert any(i.source_ac_number == 5 for i in rec_manual)

    def test_covered_lowrisk_ac_manual_in_safe_to_skip(self, db, run_with_manual):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        sts_manual = [i for i in _group_items(scope, ScopeGroup.SAFE_TO_SKIP) if i.item_type == ScopeItemType.MANUAL_TEST]
        assert any(i.source_ac_number == 3 for i in sts_manual)

    def test_manual_item_type(self, db, run_with_manual):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        manual = _manual_items(scope)
        assert len(manual) == 3
        assert all(i.item_type == ScopeItemType.MANUAL_TEST for i in manual)

    def test_manual_is_manual_only(self, db, run_with_manual):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        assert all(i.is_manual_only is True for i in _manual_items(scope))

    def test_manual_cannot_auto_execute(self, db, run_with_manual):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        assert all(i.can_auto_execute is False for i in _manual_items(scope))

    def test_manual_includes_execution_status(self, db, run_with_manual):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        statuses = {i.source_ac_number: i.execution_status for i in _manual_items(scope)}
        assert statuses[12] == "NOT_EXECUTED"
        assert statuses[3] == "PASSED"

    def test_manual_includes_estimated_effort(self, db, run_with_manual):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        for i in _manual_items(scope):
            assert i.estimated_effort is not None
            assert "min" in i.estimated_effort

    def test_manual_includes_test_references(self, db, run_with_manual):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        for i in _manual_items(scope):
            assert len(i.test_references) >= 1
            assert i.provider is not None

    def test_duplicate_mappings_deduplicated(self, db, test_repository, test_pr):
        run = _make_run(db, test_repository, test_pr, _build_snapshot(include_manual=True, duplicate_manual=True))
        try:
            scope = RegressionScopeV2Service.generate_scope_v2(
                db=db, run_id=str(run.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
            )
            manual = _manual_items(scope)
            # Despite the duplicated mapping node, only 3 unique manual items exist
            keys = {(i.id, i.source_ac_number, i.group.value) for i in manual}
            assert len(keys) == len(manual)
            assert len(manual) == 3
        finally:
            db.delete(run)
            db.commit()

    def test_latest_execution_used(self, db, run_with_manual):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        covered_manual = [i for i in _manual_items(scope) if i.source_ac_number == 3][0]
        # Snapshot already encodes the latest active execution outcome
        assert covered_manual.execution_status == "PASSED"

    def test_automated_counts_unchanged(self, db, test_repository, test_pr):
        run_without = _make_run(db, test_repository, test_pr, _build_snapshot(include_manual=False))
        try:
            scope_without = RegressionScopeV2Service.generate_scope_v2(
                db=db, run_id=str(run_without.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
            )
        finally:
            base_required = scope_without.execution_plan.automated_required_count
            base_recommended = scope_without.execution_plan.automated_recommended_count
            db.delete(run_without)
            db.commit()

        run_with = _make_run(db, test_repository, test_pr, _build_snapshot(include_manual=True))
        try:
            scope_with = RegressionScopeV2Service.generate_scope_v2(
                db=db, run_id=str(run_with.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
            )
            # Automated portion of scope is identical regardless of manual mappings
            assert scope_with.execution_plan.automated_required_count == base_required
            assert scope_with.execution_plan.automated_recommended_count == base_recommended
            # Manual split is populated
            assert scope_with.execution_plan.manual_required_count == 1
            assert scope_with.execution_plan.manual_recommended_count == 1
            assert scope_with.execution_plan.manual_safe_to_skip_count == 1
            assert scope_with.execution_plan.manual_estimated_minutes == 20
        finally:
            db.delete(run_with)
            db.commit()

    def test_evidence_truth_unchanged(self, db, run_with_manual):
        # Snapshot counts must not be mutated by scope generation
        RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        db.refresh(run_with_manual)
        snapshot = json.loads(run_with_manual.requirement_evidence_snapshot_json)
        assert snapshot["counts"]["totalRequirements"] == 25
        assert snapshot["counts"]["uploadedPrTestsPassed"] == 18
        assert snapshot["counts"]["verifiedTests"] == 16
        assert snapshot["counts"]["missingAutomatedCoverage"] == 7
        assert snapshot["health"] == "VALIDATION_PASSED_COVERAGE_INCOMPLETE"

    def test_manual_items_do_not_mark_requirements_covered(self, db, run_with_manual):
        scope = RegressionScopeV2Service.generate_scope_v2(
            db=db, run_id=str(run_with_manual.id), mode=ScopeMode.TARGETED, include_safe_to_skip=True
        )
        # The missing AC's automated requirement item must remain MISSING
        required_reqs = [
            i for i in _group_items(scope, ScopeGroup.REQUIRED)
            if i.item_type == ScopeItemType.REQUIREMENT and i.readable_id == "AC-12"
        ]
        assert len(required_reqs) == 1
        assert required_reqs[0].evidence_classification.value == "MISSING"
        # The manual item for the same AC is never classified COVERED
        manual_missing = [i for i in _manual_items(scope) if i.source_ac_number == 12][0]
        assert manual_missing.evidence_classification.value != "COVERED"
