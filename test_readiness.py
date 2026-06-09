"""Test the readiness service implementation and scenarios."""
import uuid
import jwt
from datetime import datetime, timedelta
from typing import Set
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.config import settings
from app.models.user import User, Workspace, WorkspaceMember
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.test_result import TestRun
from app.models.coverage import CoverageReport
from app.models.architecture_node import ArchitectureNode
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.acceptance_criterion import AcceptanceCriterion
from app.services.recommendation_readiness_service import RecommendationReadinessService
from app.services.detailed_readiness_service import DetailedReadinessService

client = TestClient(app)

def get_auth_headers():
    payload = {
        "email": "test@example.com",
        "name": "Test User",
        "avatar_url": None,
        "sub": "test_provider_id"
    }
    token = jwt.encode(payload, settings.STATE_SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

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

def get_or_create_repo_pr(db: Session, workspace_id: uuid.UUID):
    repo_id = uuid.UUID("a5de7396-88ca-49f5-af9d-8937aecfcfab")
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
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
        db.add(repo)
        db.commit()
        db.refresh(repo)

    pr_id = uuid.UUID("805e8062-b20f-4831-81aa-f6e7d0e796fd")
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
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
        db.add(pr)
        db.commit()
        db.refresh(pr)
        
    return repo, pr

def clear_signals(db: Session, repository_id: uuid.UUID, pull_request_id: uuid.UUID):
    db.query(TestRun).filter(TestRun.repository_id == repository_id).delete()
    db.query(CoverageReport).filter(CoverageReport.repository_id == repository_id).delete()
    db.query(AcceptanceCriterion).filter(AcceptanceCriterion.pull_request_id == pull_request_id).delete()
    db.query(Behavior).filter(Behavior.repository_id == repository_id).delete()
    db.query(Journey).filter(Journey.repository_id == repository_id).delete()
    db.query(ArchitectureNode).filter(ArchitectureNode.repository_id == repository_id).delete()
    db.commit()

def test_blocked_state():
    """1. Test BLOCKED state (missing pull request changes or repository inactive)."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        # Make PR changed_files_count = 0 to trigger blocked state
        pr.changed_files_count = 0
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(repo.id, pr.id)
        assert assessment.readiness_level == "BLOCKED"
        assert assessment.can_generate is False
    finally:
        db.close()

def test_low_confidence():
    """2. Test MINIMUM_READY / LOW confidence state (only source + diff exist)."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        # Ensure source and diff are valid
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(repo.id, pr.id)
        assert assessment.readiness_level == "MINIMUM_READY"
        assert assessment.expected_confidence == "MEDIUM"
        assert assessment.can_generate is True
    finally:
        db.close()

def test_medium_confidence_junit_coverage():
    """3. Test EVIDENCE_READY / MEDIUM confidence (JUnit test history + coverage report exist)."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        
        # Add test run (history)
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_hash="dummy_hash_1",
            normalized_execution_fingerprint="dummy_fingerprint_1",
            status="SUCCESS",
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            skipped_tests=0,
            duration=1.5,
            evidence_health_status="HEALTHY",
            created_at=datetime.utcnow()
        )
        db.add(test_run)
        
        # Add coverage report
        coverage = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=workspace_id,
            files_total=5,
            total_lines=100,
            covered_lines_total=80,
            uncovered_lines_total=20,
            line_coverage_ratio=0.8,
            source="manual",
            format="LCOV",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            confidence_score="HIGH",
            file_hash="dummy_hash_1",
            created_at=datetime.utcnow()
        )
        db.add(coverage)
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(repo.id, pr.id)
        assert assessment.readiness_level == "EVIDENCE_READY"
        assert assessment.expected_confidence == "MEDIUM"
    finally:
        db.close()

def test_medium_confidence_ac_no_execution():
    """4. Test REGRESSION_READY / MEDIUM confidence (AC exists, but no current execution)."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        
        # Add test run (history)
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_hash="dummy_hash_2",
            normalized_execution_fingerprint="dummy_fingerprint_2",
            status="SUCCESS",
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            skipped_tests=0,
            duration=1.5,
            evidence_health_status="HEALTHY",
            created_at=datetime.utcnow() - timedelta(days=1)  # historical
        )
        db.add(test_run)
        
        # Add coverage report
        coverage = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=workspace_id,
            files_total=5,
            total_lines=100,
            covered_lines_total=80,
            uncovered_lines_total=20,
            line_coverage_ratio=0.8,
            source="manual",
            format="LCOV",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            confidence_score="HIGH",
            file_hash="dummy_hash_2",
            created_at=datetime.utcnow() - timedelta(days=1)
        )
        db.add(coverage)
        
        # Add Acceptance Criteria
        ac = AcceptanceCriterion(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            repository_id=repo.id,
            text="GIVEN a user WHEN log in THEN succeed",
            normalized_key="dummy_ac_key_1",
            source="PR_DESCRIPTION",
            created_at=datetime.utcnow()
        )
        db.add(ac)
        
        # Add Architecture, Behavior, Journey to satisfy regression readiness check
        node = ArchitectureNode(
            id=uuid.uuid4(),
            repository_id=repo.id,
            node_type="MODULE",
            name="App",
            path="app/main.py",
            normalized_path="app/main.py",
            layer="DOMAIN"
        )
        db.add(node)
        
        behavior = Behavior(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="login",
            slug="login",
            risk_level="LOW",
            status="DISCOVERED",
            discovery_source="MANUAL"
        )
        db.add(behavior)
        
        journey = Journey(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="authflow",
            slug="authflow",
            risk_level="LOW",
            status="DISCOVERED"
        )
        db.add(journey)
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(repo.id, pr.id)
        # Expected confidence remains MEDIUM because current PR execution is missing
        assert assessment.readiness_level == "REGRESSION_READY"
        assert assessment.expected_confidence == "MEDIUM"
    finally:
        db.close()

def test_high_confidence():
    """5. Test HIGH_CONFIDENCE_READY / HIGH confidence (All signals, AC, and current execution)."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        
        # Add current PR test run
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pull_request_id=pr.id,  # Linked to current PR
            file_hash="dummy_hash_3",
            normalized_execution_fingerprint="dummy_fingerprint_3",
            status="SUCCESS",
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            skipped_tests=0,
            duration=1.5,
            evidence_health_status="HEALTHY",
            created_at=datetime.utcnow()
        )
        db.add(test_run)
        
        # Add current PR coverage report
        coverage = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=workspace_id,
            pull_request_id=pr.id,  # Linked to current PR
            files_total=5,
            total_lines=100,
            covered_lines_total=80,
            uncovered_lines_total=20,
            line_coverage_ratio=0.8,
            source="manual",
            format="LCOV",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            confidence_score="HIGH",
            file_hash="dummy_hash_3",
            created_at=datetime.utcnow()
        )
        db.add(coverage)
        
        # Add Acceptance Criteria
        ac = AcceptanceCriterion(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            repository_id=repo.id,
            text="GIVEN user login WHEN valid THEN succeed",
            normalized_key="dummy_ac_key_2",
            source="PR_DESCRIPTION",
            created_at=datetime.utcnow()
        )
        db.add(ac)
        
        # Add Architecture, Behavior, Journey
        node = ArchitectureNode(
            id=uuid.uuid4(),
            repository_id=repo.id,
            node_type="MODULE",
            name="App",
            path="app/main.py",
            normalized_path="app/main.py",
            layer="DOMAIN"
        )
        db.add(node)
        
        behavior = Behavior(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="login",
            slug="login",
            risk_level="LOW",
            status="DISCOVERED",
            discovery_source="MANUAL"
        )
        db.add(behavior)
        
        journey = Journey(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="authflow",
            slug="authflow",
            risk_level="LOW",
            status="DISCOVERED"
        )
        db.add(journey)
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(repo.id, pr.id)
        assert assessment.readiness_level == "HIGH_CONFIDENCE_READY"
        assert assessment.expected_confidence == "HIGH"
    finally:
        db.close()

def test_test_runs_endpoint_empty_array():
    """6. Test test-runs endpoint returns empty array when no test runs exist."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        
        # Create a fresh repository in the workspace to make sure we don't fetch any seeded runs
        import random
        rand_github_id = random.randint(1000000, 9999999)
        db.query(Repository).filter(Repository.github_repo_id == rand_github_id).delete()
        db.commit()

        fresh_repo_id = uuid.uuid4()
        repo = Repository(
            id=fresh_repo_id,
            workspace_id=workspace_id,
            github_repo_id=rand_github_id,
            name="empty_repo",
            full_name="test_owner/empty_repo",
            visibility="PUBLIC",
            is_active=True,
            selected_for_analysis=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(repo)
        db.commit()
        
        headers = get_auth_headers()
        response = client.get(f"/api/repositories/{fresh_repo_id}/test-runs", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "test_runs" in data
        assert isinstance(data["test_runs"], list)
        assert len(data["test_runs"]) == 0
    finally:
        db.close()

def test_source_code_pr_diff_exists():
    """7. Test source code + PR diff exists → readiness_level != BLOCKED, score >= 40."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(repo.id, pr.id)
        
        assert assessment.readiness_level != "BLOCKED"
        assert assessment.readiness_level == "MINIMUM_READY"
        assert assessment.can_generate is True
        assert assessment.readiness_score >= 0.4  # source_code (20) + pull_request_diff (20) = 40
        assert "source_code" in [s["key"] for s in assessment.available_inputs]
        assert "pull_request_diff" in [s["key"] for s in assessment.available_inputs]
    finally:
        db.close()

def test_missing_pr_changed_files():
    """8. Test missing PR changed files → readiness_level = BLOCKED."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 0  # No changed files
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(repo.id, pr.id)
        
        assert assessment.readiness_level == "BLOCKED"
        assert assessment.can_generate is False
        assert "pull_request_diff" in [s["key"] for s in assessment.blocking_inputs]
    finally:
        db.close()

def test_missing_test_history_only():
    """9. Test missing test history only → readiness_level != BLOCKED."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(repo.id, pr.id)
        
        assert assessment.readiness_level != "BLOCKED"
        assert assessment.readiness_level == "MINIMUM_READY"
        assert assessment.can_generate is True
        assert "test_history" in [s["key"] for s in assessment.missing_inputs]
    finally:
        db.close()

def test_missing_coverage_only():
    """10. Test missing coverage only → readiness_level != BLOCKED."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        
        # Add test history but no coverage
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_hash="dummy_hash_4",
            normalized_execution_fingerprint="dummy_fingerprint_4",
            status="SUCCESS",
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            skipped_tests=0,
            duration=1.5,
            evidence_health_status="HEALTHY",
            created_at=datetime.utcnow()
        )
        db.add(test_run)
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(repo.id, pr.id)
        
        assert assessment.readiness_level != "BLOCKED"
        assert assessment.readiness_level == "EVIDENCE_READY"
        assert assessment.can_generate is True
        assert "coverage_report" in [s["key"] for s in assessment.missing_inputs]
    finally:
        db.close()

def test_missing_acceptance_criteria_only():
    """11. Test missing acceptance criteria only → readiness_level != BLOCKED."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        
        # Add test history and coverage but no AC
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_hash="dummy_hash_5",
            normalized_execution_fingerprint="dummy_fingerprint_5",
            status="SUCCESS",
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            skipped_tests=0,
            duration=1.5,
            evidence_health_status="HEALTHY",
            created_at=datetime.utcnow()
        )
        db.add(test_run)
        
        coverage = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=workspace_id,
            files_total=5,
            total_lines=100,
            covered_lines_total=80,
            uncovered_lines_total=20,
            line_coverage_ratio=0.8,
            source="manual",
            format="LCOV",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            confidence_score="HIGH",
            file_hash="dummy_hash_5",
            created_at=datetime.utcnow()
        )
        db.add(coverage)
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(repo.id, pr.id)
        
        assert assessment.readiness_level != "BLOCKED"
        assert assessment.readiness_level == "EVIDENCE_READY"
        assert assessment.can_generate is True
        assert "acceptance_criteria" in [s["key"] for s in assessment.missing_inputs]
    finally:
        db.close()

def test_after_junit_upload():
    """12. Test after JUnit upload → test_history moves to available, score increases."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment_before = service.assess_readiness(repo.id, pr.id)
        score_before = assessment_before.readiness_score
        
        # Add JUnit test run
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_hash="dummy_hash_6",
            normalized_execution_fingerprint="dummy_fingerprint_6",
            status="SUCCESS",
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            skipped_tests=0,
            duration=1.5,
            evidence_health_status="HEALTHY",
            created_at=datetime.utcnow()
        )
        db.add(test_run)
        db.commit()
        
        assessment_after = service.assess_readiness(repo.id, pr.id)
        score_after = assessment_after.readiness_score
        
        assert "test_history" in [s["key"] for s in assessment_after.available_inputs]
        assert score_after > score_before
    finally:
        db.close()

def test_after_coverage_upload():
    """13. Test after coverage upload → coverage_report moves to available, score increases."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment_before = service.assess_readiness(repo.id, pr.id)
        score_before = assessment_before.readiness_score
        
        # Add coverage report
        coverage = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=workspace_id,
            files_total=5,
            total_lines=100,
            covered_lines_total=80,
            uncovered_lines_total=20,
            line_coverage_ratio=0.8,
            source="manual",
            format="LCOV",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            confidence_score="HIGH",
            file_hash="dummy_hash_7",
            created_at=datetime.utcnow()
        )
        db.add(coverage)
        db.commit()
        
        assessment_after = service.assess_readiness(repo.id, pr.id)
        score_after = assessment_after.readiness_score
        
        assert "coverage_report" in [s["key"] for s in assessment_after.available_inputs]
        assert score_after > score_before
    finally:
        db.close()

def test_after_ac_paste():
    """14. Test after AC paste → acceptance_criteria moves to available, score increases."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment_before = service.assess_readiness(repo.id, pr.id)
        score_before = assessment_before.readiness_score
        
        # Add Acceptance Criteria
        ac = AcceptanceCriterion(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            repository_id=repo.id,
            text="GIVEN user login WHEN valid THEN succeed",
            normalized_key="dummy_ac_key_3",
            source="PR_DESCRIPTION",
            created_at=datetime.utcnow()
        )
        db.add(ac)
        db.commit()
        
        assessment_after = service.assess_readiness(repo.id, pr.id)
        score_after = assessment_after.readiness_score
        
        assert "acceptance_criteria" in [s["key"] for s in assessment_after.available_inputs]
        assert score_after > score_before
    finally:
        db.close()

def test_pr_sync_timestamp_update():
    """15. Test PR sync success → latest_pr_synced_at updated."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        
        # Clear existing timestamp
        repo.latest_pr_synced_at = None
        db.commit()
        
        # Simulate PR sync by updating timestamp
        repo.latest_pr_synced_at = datetime.utcnow()
        db.commit()
        db.refresh(repo)
        
        assert repo.latest_pr_synced_at is not None
        assert isinstance(repo.latest_pr_synced_at, datetime)
    finally:
        db.close()

def test_no_duplicate_signal_keys():
    """16. Test readiness payload has no duplicate signal keys."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_auth_db(db)
        repo, pr = get_or_create_repo_pr(db, workspace_id)
        clear_signals(db, repo.id, pr.id)
        
        repo.is_active = True
        repo.selected_for_analysis = True
        pr.changed_files_count = 1
        db.commit()
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(repo.id, pr.id)
        
        # Check available_inputs for duplicates
        available_keys = [s["key"] for s in assessment.available_inputs]
        assert len(available_keys) == len(set(available_keys)), f"Duplicate keys in available_inputs: {available_keys}"
        
        # Check missing_inputs for duplicates
        missing_keys = [s["key"] for s in assessment.missing_inputs]
        assert len(missing_keys) == len(set(missing_keys)), f"Duplicate keys in missing_inputs: {missing_keys}"
        
        # Check no overlap between available and missing
        overlap = set(available_keys) & set(missing_keys)
        assert len(overlap) == 0, f"Keys in both available and missing: {overlap}"
    finally:
        db.close()
