import uuid
from datetime import datetime, timedelta
import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestRun
from app.models.coverage import CoverageReport
from app.models.architecture_node import ArchitectureNode
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.business_intent import BusinessIntentOverride
from app.services.recommendation_readiness_gate import RecommendationReadinessGate

def setup_test_db_infrastructure(db: Session):
    # Seed user
    user = db.query(User).filter(User.email == "gate_test@example.com").first()
    if not user:
        user = User(
            id=uuid.uuid4(),
            email="gate_test@example.com",
            name="Gate User",
            auth_provider="github"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Seed workspace
    workspace = db.query(Workspace).filter(Workspace.slug == "gate-workspace").first()
    if not workspace:
        workspace = Workspace(
            id=uuid.UUID("461e6878-c1a7-4b71-b0db-b0352ef29b8c"),
            name="Gate Workspace",
            slug="gate-workspace",
            created_by_user_id=user.id
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

    # Seed workspace member
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

def create_gate_repo_pr(db: Session, workspace_id: uuid.UUID):
    repo_id = uuid.UUID("b5de7396-88ca-49f5-af9d-8937aecfcfab")
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        repo = Repository(
            id=repo_id,
            workspace_id=workspace_id,
            github_repo_id=1234567,
            name="gate_test_repo",
            full_name="gate_owner/gate_repo",
            visibility="PUBLIC",
            is_active=True,
            selected_for_analysis=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

    pr_id = uuid.UUID("905e8062-b20f-4831-81aa-f6e7d0e796fd")
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=543210,
            number=2,
            title="Gate Test PR",
            author="gate_author",
            source_branch="gate_feature",
            target_branch="main",
            state="open",
            changed_files_count=1,
            head_commit_sha="fedcba",
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(pr)
        db.commit()
        db.refresh(pr)

    return repo, pr

def clear_gate_signals(db: Session, repository_id: uuid.UUID, pull_request_id: uuid.UUID):
    db.query(TestRun).filter(TestRun.repository_id == repository_id).delete()
    db.query(CoverageReport).filter(CoverageReport.repository_id == repository_id).delete()
    db.query(AcceptanceCriterion).filter(AcceptanceCriterion.pull_request_id == pull_request_id).delete()
    db.query(Behavior).filter(Behavior.repository_id == repository_id).delete()
    db.query(Journey).filter(Journey.repository_id == repository_id).delete()
    db.query(ArchitectureNode).filter(ArchitectureNode.repository_id == repository_id).delete()
    db.query(BusinessIntentOverride).filter(BusinessIntentOverride.pull_request_id == pull_request_id).delete()
    db.query(PullRequestChangedFile).filter(PullRequestChangedFile.pull_request_id == pull_request_id).delete()
    db.commit()

def test_gate_blocked_level():
    """Verify BLOCKED level when required signals (source_code / pull_request_diff) are missing."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_db_infrastructure(db)
        repo, pr = create_gate_repo_pr(db, workspace_id)
        clear_gate_signals(db, repo.id, pr.id)

        # Make PR changed files 0 and deactivate repo to simulate blocked
        repo.is_active = False
        pr.changed_files_count = 0
        db.commit()

        gate = RecommendationReadinessGate()
        result = gate.assess(db, str(repo.id), str(pr.id))
        
        assert result.can_generate is False
        assert result.readiness_level == "BLOCKED"
        assert result.expected_confidence == "LOW"
        assert len(result.blocking_inputs) > 0
    finally:
        db.close()

def test_gate_minimum_ready_level():
    """Verify MINIMUM_READY level when only required signals are present."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_db_infrastructure(db)
        repo, pr = create_gate_repo_pr(db, workspace_id)
        clear_gate_signals(db, repo.id, pr.id)

        # Ensure repo has source code available by seeding an ArchitectureNode
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 2
        
        node = ArchitectureNode(
            id=uuid.uuid4(),
            repository_id=repo.id,
            node_type="MODULE",
            name="Core",
            path="core/mod.py",
            normalized_path="core/mod.py",
            layer="DOMAIN"
        )
        db.add(node)
        db.commit()

        gate = RecommendationReadinessGate()
        result = gate.assess(db, str(repo.id), str(pr.id))

        assert result.can_generate is True
        assert result.readiness_level == "MINIMUM_READY"
        assert result.expected_confidence == "LOW"
    finally:
        db.close()

def test_gate_evidence_ready_level():
    """Verify EVIDENCE_READY level when source, diff, and coverage report/test history exist."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_db_infrastructure(db)
        repo, pr = create_gate_repo_pr(db, workspace_id)
        clear_gate_signals(db, repo.id, pr.id)

        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 2

        node = ArchitectureNode(
            id=uuid.uuid4(),
            repository_id=repo.id,
            node_type="MODULE",
            name="Core",
            path="core/mod.py",
            normalized_path="core/mod.py",
            layer="DOMAIN"
        )
        db.add(node)

        # Add historical test run
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_hash="gate_hash_1",
            normalized_execution_fingerprint="gate_finger_1",
            status="SUCCESS",
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            skipped_tests=0,
            duration=1.0,
            evidence_health_status="HEALTHY",
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.add(test_run)
        db.commit()

        gate = RecommendationReadinessGate()
        result = gate.assess(db, str(repo.id), str(pr.id))

        assert result.can_generate is True
        assert result.readiness_level == "EVIDENCE_READY"
    finally:
        db.close()

def test_gate_regression_ready_level():
    """Verify REGRESSION_READY level when test history, coverage, behavior, journey, and architecture exist."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_db_infrastructure(db)
        repo, pr = create_gate_repo_pr(db, workspace_id)
        clear_gate_signals(db, repo.id, pr.id)

        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 2

        node = ArchitectureNode(
            id=uuid.uuid4(),
            repository_id=repo.id,
            node_type="MODULE",
            name="Core",
            path="core/mod.py",
            normalized_path="core/mod.py",
            layer="DOMAIN"
        )
        db.add(node)

        # Add historical test run
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_hash="gate_hash_2",
            normalized_execution_fingerprint="gate_finger_2",
            status="SUCCESS",
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            skipped_tests=0,
            duration=1.0,
            evidence_health_status="HEALTHY",
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.add(test_run)

        # Add coverage report
        coverage = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=workspace_id,
            files_total=2,
            total_lines=50,
            covered_lines_total=40,
            uncovered_lines_total=10,
            line_coverage_ratio=0.8,
            source="manual",
            format="LCOV",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            confidence_score="HIGH",
            file_hash="gate_cov_hash_2",
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.add(coverage)

        # Add behavior & journey
        behavior = Behavior(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="gate_behavior",
            slug="gate_behavior",
            risk_level="LOW",
            status="DISCOVERED",
            discovery_source="MANUAL"
        )
        db.add(behavior)

        journey = Journey(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="gate_journey",
            slug="gate_journey",
            risk_level="LOW",
            status="DISCOVERED"
        )
        db.add(journey)
        db.commit()

        gate = RecommendationReadinessGate()
        result = gate.assess(db, str(repo.id), str(pr.id))

        assert result.can_generate is True
        assert result.readiness_level == "REGRESSION_READY"
        assert result.expected_confidence == "MEDIUM"  # Ceiling limits to MEDIUM because AC and current execution are missing
    finally:
        db.close()

def test_gate_high_confidence_ready_level():
    """Verify HIGH_CONFIDENCE_READY when all criteria are met including AC and current execution."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_db_infrastructure(db)
        repo, pr = create_gate_repo_pr(db, workspace_id)
        clear_gate_signals(db, repo.id, pr.id)

        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 2

        node = ArchitectureNode(
            id=uuid.uuid4(),
            repository_id=repo.id,
            node_type="MODULE",
            name="Core",
            path="core/mod.py",
            normalized_path="core/mod.py",
            layer="DOMAIN"
        )
        db.add(node)

        # Add current PR test run
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pull_request_id=pr.id,
            file_hash="gate_hash_3",
            normalized_execution_fingerprint="gate_finger_3",
            status="SUCCESS",
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            skipped_tests=0,
            duration=1.0,
            evidence_health_status="HEALTHY",
            created_at=datetime.utcnow()
        )
        db.add(test_run)

        # Add current PR coverage report
        coverage = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=workspace_id,
            pull_request_id=pr.id,
            files_total=2,
            total_lines=50,
            covered_lines_total=40,
            uncovered_lines_total=10,
            line_coverage_ratio=0.8,
            source="manual",
            format="LCOV",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            confidence_score="HIGH",
            file_hash="gate_cov_hash_3",
            created_at=datetime.utcnow()
        )
        db.add(coverage)

        # Add behavior & journey
        behavior = Behavior(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="gate_behavior",
            slug="gate_behavior",
            risk_level="LOW",
            status="DISCOVERED",
            discovery_source="MANUAL"
        )
        db.add(behavior)

        journey = Journey(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="gate_journey",
            slug="gate_journey",
            risk_level="LOW",
            status="DISCOVERED"
        )
        db.add(journey)

        # Add AC
        ac = AcceptanceCriterion(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            repository_id=repo.id,
            text="GIVEN gate user WHEN running tests THEN succeed",
            normalized_key="gate_ac_key",
            source="PR_DESCRIPTION",
            created_at=datetime.utcnow()
        )
        db.add(ac)
        db.commit()

        gate = RecommendationReadinessGate()
        result = gate.assess(db, str(repo.id), str(pr.id))

        assert result.can_generate is True
        assert result.readiness_level == "HIGH_CONFIDENCE_READY"
        assert result.expected_confidence == "HIGH"
    finally:
        db.close()

def test_gate_ceilings_rules():
    """Verify confidence ceilings are correctly calculated (e.g. no AC limit)."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_db_infrastructure(db)
        repo, pr = create_gate_repo_pr(db, workspace_id)
        clear_gate_signals(db, repo.id, pr.id)

        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 2

        node = ArchitectureNode(
            id=uuid.uuid4(),
            repository_id=repo.id,
            node_type="MODULE",
            name="Core",
            path="core/mod.py",
            normalized_path="core/mod.py",
            layer="DOMAIN"
        )
        db.add(node)

        # Add current PR test run but NO Acceptance Criteria
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pull_request_id=pr.id,
            file_hash="gate_hash_4",
            normalized_execution_fingerprint="gate_finger_4",
            status="SUCCESS",
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            skipped_tests=0,
            duration=1.0,
            evidence_health_status="HEALTHY",
            created_at=datetime.utcnow()
        )
        db.add(test_run)

        # Add current PR coverage report
        coverage = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=workspace_id,
            pull_request_id=pr.id,
            files_total=2,
            total_lines=50,
            covered_lines_total=40,
            uncovered_lines_total=10,
            line_coverage_ratio=0.8,
            source="manual",
            format="LCOV",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            confidence_score="HIGH",
            file_hash="gate_cov_hash_4",
            created_at=datetime.utcnow()
        )
        db.add(coverage)

        # Add behavior, journey
        behavior = Behavior(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="gate_behavior",
            slug="gate_behavior",
            risk_level="LOW",
            status="DISCOVERED",
            discovery_source="MANUAL"
        )
        db.add(behavior)

        journey = Journey(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="gate_journey",
            slug="gate_journey",
            risk_level="LOW",
            status="DISCOVERED"
        )
        db.add(journey)
        db.commit()

        gate = RecommendationReadinessGate()
        result = gate.assess(db, str(repo.id), str(pr.id))

        assert result.can_generate is True
        # Without AC, ceiling is MEDIUM, so expected_confidence must be capped at MEDIUM
        assert result.release_confidence_ceiling == "MEDIUM"
        assert result.expected_confidence == "MEDIUM"
    finally:
        db.close()
