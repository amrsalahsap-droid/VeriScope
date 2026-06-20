"""Tests for the separate manual evidence channel in the evidence graph."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.external_test_case_detailed import ExternalTestCase
from app.models.integration_connection import IntegrationConnection
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.manual_test_requirement_mapping import ManualTestRequirementMapping
from app.models.manual_test_execution import ManualTestExecution
from app.models.recommendation import RecommendationRun
from app.dependencies.auth import get_current_user, get_current_workspace_id
from app.services.evidence_graph.requirement_evidence_graph_service import RequirementEvidenceGraphService
from app.services.regression_evidence_classifier import EvidenceClassification


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
    email = f"test-channel-{uuid.uuid4().hex[:6]}@example.com"
    user = User(
        email=email,
        name="Channel Test User",
        auth_provider="github",
        provider_user_id=f"test-channel-{uuid.uuid4().hex[:6]}"
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
        created_by_user_id=test_user.id
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=test_user.id,
        role="OWNER"
    )
    db.add(member)
    db.commit()
    
    yield workspace
    db.delete(member)
    db.delete(workspace)
    db.commit()


@pytest.fixture
def test_repository(db: Session, test_workspace: Workspace):
    repo = Repository(
        name="channel-test-repo",
        full_name=f"test-owner/channel-repo-{uuid.uuid4().hex[:6]}",
        owner="test-owner",
        github_repo_id=int(uuid.uuid4().int % 10000000),
        workspace_id=test_workspace.id,
        is_active=True,
        selected_for_analysis=True
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
        title="Test PR for Manual Evidence Channel",
        author="test-author",
        source_branch="feature",
        target_branch="main",
        state="open",
        head_commit_sha="a" * 40,
        github_created_at=datetime.utcnow(),
        github_updated_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    yield pr
    db.delete(pr)
    db.commit()


@pytest.fixture
def test_integration_connection(db: Session, test_workspace: Workspace, test_repository: Repository):
    connection = IntegrationConnection(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        repository_id=test_repository.id,
        provider="MANUAL_CSV",
        display_name=f"Connection-{uuid.uuid4().hex[:6]}",
        status="CONNECTED",
        is_active=True
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    yield connection
    db.delete(connection)
    db.commit()


@pytest.fixture
def manual_test_case(db: Session, test_repository: Repository, test_integration_connection: IntegrationConnection):
    tc = ExternalTestCase(
        id=uuid.uuid4(),
        repository_id=test_repository.id,
        workspace_id=test_repository.workspace_id,
        integration_connection_id=test_integration_connection.id,
        provider="manual",
        external_id=f"ext-{uuid.uuid4().hex}",
        title="Verify multi-factor authentication fallback",
        external_key="TC-101",
        automation_status="MANUAL",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    yield tc
    db.delete(tc)
    db.commit()


@pytest.fixture
def test_ac(db: Session, test_repository: Repository, test_pr: PullRequest):
    ac = AcceptanceCriterion(
        id=uuid.uuid4(),
        repository_id=test_repository.id,
        pull_request_id=test_pr.id,
        source_number=12,
        text="Weak passwords are rejected during sign-up",
        label="AC-12 Weak passwords are rejected during sign-up",
        normalized_key="ac-12-weak-passwords-rejected",
        source="PR_DESCRIPTION",
        confidence=1.0
    )
    db.add(ac)
    db.commit()
    db.refresh(ac)
    yield ac
    db.delete(ac)
    db.commit()


@pytest.fixture
def test_run(db: Session, test_repository: Repository, test_pr: PullRequest):
    run = RecommendationRun(
        id=uuid.uuid4(),
        repository_id=test_repository.id,
        pull_request_id=test_pr.id,
        pr_id=str(test_pr.id),
        triggered_by="github-webhook",
        evidence_quality="HIGH",
        engine_version="v3",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="Manual channel test run",
        created_at=datetime.utcnow()
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    yield run
    db.delete(run)
    db.commit()


@pytest.fixture
def client_with_auth(test_user: User, test_workspace: Workspace):
    def override_get_current_user():
        return test_user

    def override_get_current_workspace_id():
        return str(test_workspace.id)

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_workspace_id] = override_get_current_workspace_id

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


class TestManualEvidenceChannel:
    """Backend test suite verifying Phase 6.2 manual evidence channel requirements."""

    @pytest.mark.parametrize("outcome,expected_status,expected_support_status", [
        ("PASSED", "PASSED", "MANUALLY_SUPPORTED"),
        ("FAILED", "FAILED", "MANUAL_FAILED"),
        ("BLOCKED", "BLOCKED", "MANUAL_BLOCKED"),
        ("SKIPPED", "SKIPPED", "MANUAL_SKIPPED"),
    ])
    def test_manual_execution_outcome_mapping(
        self, db: Session, test_repository: Repository, test_pr: PullRequest, test_run: RecommendationRun,
        manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion, test_user: User,
        outcome: str, expected_status: str, expected_support_status: str
    ):
        """Verify manual executions map to the correct status and supportStatus values in the graph."""
        # Create active mapping
        mapping = ManualTestRequirementMapping(
            id=uuid.uuid4(),
            external_test_case_id=manual_test_case.id,
            acceptance_criterion_id=test_ac.id,
            repository_id=test_repository.id,
            mapping_source="MANUAL",
            is_active=True
        )
        db.add(mapping)

        # Create active execution
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=manual_test_case.id,
            repository_id=test_repository.id,
            pull_request_id=test_pr.id,
            recommendation_run_id=test_run.id,
            outcome=outcome,
            executed_by_id=test_user.id,
            executed_by_name=test_user.name,
            executed_at=datetime.utcnow(),
            is_active=True
        )
        db.add(execution)
        db.commit()

        try:
            # Build the evidence graph
            service = RequirementEvidenceGraphService(db)
            view_model = service.build_evidence_graph(
                repository_id=str(test_repository.id),
                pull_request_id=str(test_pr.id),
                head_sha=test_pr.head_commit_sha,
                changed_files=[],
                pr_description=None,
                recommendation_run_id=str(test_run.id),
                canonical_ac_rows=[test_ac]
            )

            # Retrieve AC row from graph
            assert len(view_model.ac_traceability) == 1
            row = view_model.ac_traceability[0]

            assert row.manual_support_status == expected_support_status
            assert row.manual_validation["status"] == expected_status
            assert row.manual_validation["supportStatus"] == expected_support_status
            assert row.manual_validation["mappedManualTestsCount"] == 1
            assert row.manual_validation["executedManualTestsCount"] == 1
            assert row.manual_validation["passedManualTestsCount"] == (1 if outcome == "PASSED" else 0)
            assert row.manual_validation["failedManualTestsCount"] == (1 if outcome == "FAILED" else 0)
            assert row.manual_validation["blockedManualTestsCount"] == (1 if outcome == "BLOCKED" else 0)
            assert row.manual_validation["skippedManualTestsCount"] == (1 if outcome == "SKIPPED" else 0)
            assert row.manual_validation["latestOutcome"] == outcome

        finally:
            db.delete(mapping)
            db.delete(execution)
            db.commit()

    def test_manual_status_not_executed(
        self, db: Session, test_repository: Repository, test_pr: PullRequest, test_run: RecommendationRun,
        manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion
    ):
        """Verify mapped tests without executions return NOT_EXECUTED status."""
        mapping = ManualTestRequirementMapping(
            id=uuid.uuid4(),
            external_test_case_id=manual_test_case.id,
            acceptance_criterion_id=test_ac.id,
            repository_id=test_repository.id,
            mapping_source="MANUAL",
            is_active=True
        )
        db.add(mapping)
        db.commit()

        try:
            service = RequirementEvidenceGraphService(db)
            view_model = service.build_evidence_graph(
                repository_id=str(test_repository.id),
                pull_request_id=str(test_pr.id),
                head_sha=test_pr.head_commit_sha,
                changed_files=[],
                pr_description=None,
                recommendation_run_id=str(test_run.id),
                canonical_ac_rows=[test_ac]
            )

            assert len(view_model.ac_traceability) == 1
            row = view_model.ac_traceability[0]
            assert row.manual_support_status == "MANUAL_NOT_EXECUTED"
            assert row.manual_validation["status"] == "NOT_EXECUTED"
            assert row.manual_validation["supportStatus"] == "MANUAL_NOT_EXECUTED"

        finally:
            db.delete(mapping)
            db.commit()

    def test_manual_status_not_mapped(
        self, db: Session, test_repository: Repository, test_pr: PullRequest, test_run: RecommendationRun,
        test_ac: AcceptanceCriterion
    ):
        """Verify unmapped criteria return NOT_MAPPED status."""
        service = RequirementEvidenceGraphService(db)
        view_model = service.build_evidence_graph(
            repository_id=str(test_repository.id),
            pull_request_id=str(test_pr.id),
            head_sha=test_pr.head_commit_sha,
            changed_files=[],
            pr_description=None,
            recommendation_run_id=str(test_run.id),
            canonical_ac_rows=[test_ac]
        )

        assert len(view_model.ac_traceability) == 1
        row = view_model.ac_traceability[0]
        assert row.manual_support_status == "MANUAL_NOT_MAPPED"
        assert row.manual_validation["status"] == "NOT_MAPPED"
        assert row.manual_validation["supportStatus"] == "MANUAL_NOT_MAPPED"

    def test_invariance_under_manual_evidence(
        self, db: Session, test_repository: Repository, test_pr: PullRequest, test_run: RecommendationRun,
        manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion, test_user: User
    ):
        """Verify manual PASSED execution does NOT affect automated coverage, counts, or health status."""
        mapping = ManualTestRequirementMapping(
            id=uuid.uuid4(),
            external_test_case_id=manual_test_case.id,
            acceptance_criterion_id=test_ac.id,
            repository_id=test_repository.id,
            mapping_source="MANUAL",
            is_active=True
        )
        db.add(mapping)

        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=manual_test_case.id,
            repository_id=test_repository.id,
            pull_request_id=test_pr.id,
            recommendation_run_id=test_run.id,
            outcome="PASSED",
            executed_by_id=test_user.id,
            executed_by_name=test_user.name,
            executed_at=datetime.utcnow(),
            is_active=True
        )
        db.add(execution)
        db.commit()

        try:
            service = RequirementEvidenceGraphService(db)
            view_model = service.build_evidence_graph(
                repository_id=str(test_repository.id),
                pull_request_id=str(test_pr.id),
                head_sha=test_pr.head_commit_sha,
                changed_files=[],
                pr_description=None,
                recommendation_run_id=str(test_run.id),
                canonical_ac_rows=[test_ac]
            )

            # Verify that AC classification remains MISSING (since there is no automated test mapped)
            assert len(view_model.ac_traceability) == 1
            row = view_model.ac_traceability[0]
            assert row.coverage_status == "Missing"

            # Check that overall automated coverage metrics are completely unaffected
            assert view_model.counts["totalRequirements"] == 1
            assert view_model.counts["verifiedTests"] == 0
            assert view_model.counts["missingAutomatedCoverage"] == 1
            assert view_model.counts["uploadedPrTestsPassed"] == 0

        finally:
            db.delete(mapping)
            db.delete(execution)
            db.commit()

    def test_non_blocking_diagnostics_generation(
        self, db: Session, test_repository: Repository, test_pr: PullRequest, test_run: RecommendationRun,
        manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion, test_user: User
    ):
        """Verify generation of non-blocking manual diagnostics."""
        mapping = ManualTestRequirementMapping(
            id=uuid.uuid4(),
            external_test_case_id=manual_test_case.id,
            acceptance_criterion_id=test_ac.id,
            repository_id=test_repository.id,
            mapping_source="MANUAL",
            is_active=True
        )
        db.add(mapping)

        # 1. Active with mapping but NOT executed yet
        db.commit()
        try:
            service = RequirementEvidenceGraphService(db)
            view_model = service.build_evidence_graph(
                repository_id=str(test_repository.id),
                pull_request_id=str(test_pr.id),
                head_sha=test_pr.head_commit_sha,
                changed_files=[],
                pr_description=None,
                recommendation_run_id=str(test_run.id),
                canonical_ac_rows=[test_ac]
            )
            assert "MANUAL_EVIDENCE_CHANNEL_ACTIVE" in view_model.diagnostics["diagnostics"]
            assert "MANUAL_TEST_MAPPED_NOT_EXECUTED" in view_model.diagnostics["diagnostics"]

            # 2. Add FAILED execution
            exec_fail = ManualTestExecution(
                id=uuid.uuid4(),
                external_test_case_id=manual_test_case.id,
                repository_id=test_repository.id,
                pull_request_id=test_pr.id,
                recommendation_run_id=test_run.id,
                outcome="FAILED",
                executed_by_id=test_user.id,
                executed_by_name=test_user.name,
                executed_at=datetime.utcnow(),
                is_active=True
            )
            db.add(exec_fail)
            db.commit()

            view_model = service.build_evidence_graph(
                repository_id=str(test_repository.id),
                pull_request_id=str(test_pr.id),
                head_sha=test_pr.head_commit_sha,
                changed_files=[],
                pr_description=None,
                recommendation_run_id=str(test_run.id),
                canonical_ac_rows=[test_ac]
            )
            assert "MANUAL_EVIDENCE_CHANNEL_ACTIVE" in view_model.diagnostics["diagnostics"]
            assert "MANUAL_TEST_FAILED" in view_model.diagnostics["diagnostics"]
            assert "MANUAL_TEST_MAPPED_NOT_EXECUTED" not in view_model.diagnostics["diagnostics"]

            # 3. Add BLOCKED execution (newer than fail)
            import time
            time.sleep(0.1)
            exec_blocked = ManualTestExecution(
                id=uuid.uuid4(),
                external_test_case_id=manual_test_case.id,
                repository_id=test_repository.id,
                pull_request_id=test_pr.id,
                recommendation_run_id=test_run.id,
                outcome="BLOCKED",
                executed_by_id=test_user.id,
                executed_by_name=test_user.name,
                executed_at=datetime.utcnow(),
                is_active=True
            )
            db.add(exec_blocked)
            # Mark previous execution inactive
            exec_fail.is_active = False
            db.commit()

            view_model = service.build_evidence_graph(
                repository_id=str(test_repository.id),
                pull_request_id=str(test_pr.id),
                head_sha=test_pr.head_commit_sha,
                changed_files=[],
                pr_description=None,
                recommendation_run_id=str(test_run.id),
                canonical_ac_rows=[test_ac]
            )
            assert "MANUAL_EVIDENCE_CHANNEL_ACTIVE" in view_model.diagnostics["diagnostics"]
            assert "MANUAL_TEST_BLOCKED" in view_model.diagnostics["diagnostics"]
            assert "MANUAL_TEST_FAILED" not in view_model.diagnostics["diagnostics"]

        finally:
            db.delete(mapping)
            db.commit()

    def test_report_manual_validation_evidence_section(
        self, client_with_auth: TestClient, db: Session, test_repository: Repository, test_pr: PullRequest,
        test_run: RecommendationRun, manual_test_case: ExternalTestCase, test_ac: AcceptanceCriterion, test_user: User
    ):
        """Verify markdown report section is rendered and named 'Manual Validation Evidence'."""
        mapping = ManualTestRequirementMapping(
            id=uuid.uuid4(),
            external_test_case_id=manual_test_case.id,
            acceptance_criterion_id=test_ac.id,
            repository_id=test_repository.id,
            mapping_source="MANUAL",
            is_active=True
        )
        db.add(mapping)

        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=manual_test_case.id,
            repository_id=test_repository.id,
            pull_request_id=test_pr.id,
            recommendation_run_id=test_run.id,
            outcome="PASSED",
            executed_by_id=test_user.id,
            executed_by_name=test_user.name,
            executed_at=datetime.utcnow(),
            is_active=True
        )
        db.add(execution)
        db.commit()

        # Update the recommendation run to point to a persisted graph snapshot
        # (This simulates build_evidence_graph being run and persisted)
        service = RequirementEvidenceGraphService(db)
        view_model = service.build_evidence_graph(
            repository_id=str(test_repository.id),
            pull_request_id=str(test_pr.id),
            head_sha=test_pr.head_commit_sha,
            changed_files=[],
            pr_description=None,
            recommendation_run_id=str(test_run.id),
            canonical_ac_rows=[test_ac]
        )
        service.persist_graph_snapshot(
            recommendation_run_id=str(test_run.id),
            view_model=view_model
        )

        try:
            url = f"/api/recommendations/{test_run.id}/evidence-report?format=markdown"
            response = client_with_auth.get(url)
            assert response.status_code == 200, response.text
            report_data = response.json()
            
            markdown_content = report_data.get("markdown_content", "")
            assert "## Manual Validation Evidence" in markdown_content
            assert "Manual validation evidence is reported separately and does not modify automated coverage or readiness calculations." in markdown_content
            assert "Verify multi-factor authentication fallback" in markdown_content
            assert "PASSED" in markdown_content
            assert str(manual_test_case.id) in markdown_content
            
        finally:
            db.delete(mapping)
            db.delete(execution)
            db.commit()
