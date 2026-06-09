import uuid
import jwt
from datetime import datetime, timedelta
import pytest
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
from app.models.recommendation import RecommendationRun
from app.models.repository_semantic_entry import RepositorySemanticEntry

client = TestClient(app)

def get_auth_headers(email="gate_api_test@example.com"):
    payload = {
        "email": email,
        "name": "Gate API Test User",
        "avatar_url": None,
        "sub": "gate_api_test_provider"
    }
    token = jwt.encode(payload, settings.STATE_SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

def setup_test_infrastructure(db: Session):
    # Seed user
    user = db.query(User).filter(User.email == "gate_api_test@example.com").first()
    if not user:
        user = User(
            id=uuid.uuid4(),
            email="gate_api_test@example.com",
            name="Gate API Test User",
            auth_provider="github"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Seed workspace
    workspace = db.query(Workspace).filter(Workspace.slug == "gate-api-workspace").first()
    if not workspace:
        workspace = Workspace(
            id=uuid.UUID("761e6878-c1a7-4b71-b0db-b0352ef29b8c"),
            name="Gate API Workspace",
            slug="gate-api-workspace",
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

def create_repo_pr(db: Session, workspace_id: uuid.UUID):
    repo_id = uuid.UUID("c5de7396-88ca-49f5-af9d-8937aecfcfab")
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        repo = Repository(
            id=repo_id,
            workspace_id=workspace_id,
            github_repo_id=98765,
            name="gate_api_repo",
            full_name="gate_api_owner/gate_api_repo",
            visibility="PUBLIC",
            is_active=True,
            selected_for_analysis=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
    else:
        repo.is_active = True
        repo.selected_for_analysis = True
        db.commit()
        db.refresh(repo)

    pr_id = uuid.UUID("a05e8062-b20f-4831-81aa-f6e7d0e796fd")
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=9876543,
            number=42,
            title="Gate API Test PR",
            author="gate_api_author",
            source_branch="gate_api_feature",
            target_branch="main",
            state="open",
            changed_files_count=2,
            head_commit_sha="abcdef12",
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(pr)
        db.commit()
        db.refresh(pr)
    else:
        pr.changed_files_count = 2
        db.commit()
        db.refresh(pr)

    return repo, pr

def clear_gate_api_signals(db: Session, repository_id: uuid.UUID, pull_request_id: uuid.UUID):
    from app.models.business_intent import BusinessIntentOverride
    db.query(TestRun).filter(TestRun.repository_id == repository_id).delete()
    db.query(CoverageReport).filter(CoverageReport.repository_id == repository_id).delete()
    db.query(AcceptanceCriterion).filter(AcceptanceCriterion.pull_request_id == pull_request_id).delete()
    db.query(BusinessIntentOverride).filter(BusinessIntentOverride.pull_request_id == pull_request_id).delete()
    db.query(Behavior).filter(Behavior.repository_id == repository_id).delete()
    db.query(Journey).filter(Journey.repository_id == repository_id).delete()
    db.query(ArchitectureNode).filter(ArchitectureNode.repository_id == repository_id).delete()
    db.query(RepositorySemanticEntry).filter(RepositorySemanticEntry.repository_id == repository_id).delete()
    db.query(RecommendationRun).filter(RecommendationRun.repository_id == repository_id).delete()
    db.commit()


def test_get_pr_readiness_low_confidence():
    """Verify LOW expected confidence when required signals are present but no extras exist."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_infrastructure(db)
        repo, pr = create_repo_pr(db, workspace_id)
        clear_gate_api_signals(db, repo.id, pr.id)

        # Seed a semantic entry to satisfy source_code signal WITHOUT activating
        # architecture_graph (which would push score to 50 -> MEDIUM).
        # semantic_count > 0 satisfies source_code; node_count stays 0.
        entry = RepositorySemanticEntry(
            id=uuid.uuid4(),
            repository_id=repo.id,
            entry_type="MODULE",
            path="app/api.py",
            normalized_tokens=["api"],
            confidence="HIGH"
        )
        db.add(entry)
        db.commit()

        headers = get_auth_headers()
        url = f"/api/repositories/{repo.id}/pull-requests/{pr.id}/recommendation-readiness"
        response = client.get(url, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["can_generate"] is True
        assert data["expected_confidence"] == "LOW"
        assert data["readiness_level"] == "MINIMUM_READY"
        
        # Verify missing inputs contains acceptance_criteria and current_pr_execution
        missing_keys = [x["key"] for x in data["missing_inputs"]]
        assert "acceptance_criteria" in missing_keys
        assert "current_pr_execution" in missing_keys
    finally:
        db.close()


def test_get_pr_readiness_medium_confidence():
    """Verify MEDIUM expected confidence when historical test run/coverage is available but AC is missing."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_infrastructure(db)
        repo, pr = create_repo_pr(db, workspace_id)
        clear_gate_api_signals(db, repo.id, pr.id)

        # Seed required signals (architecture)
        node = ArchitectureNode(
            id=uuid.uuid4(),
            repository_id=repo.id,
            node_type="MODULE",
            name="API",
            path="app/api.py",
            normalized_path="app/api.py",
            layer="DOMAIN"
        )
        db.add(node)

        # Seed historical test run & coverage
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            file_hash="api_hash_1",
            normalized_execution_fingerprint="api_finger_1",
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

        coverage = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=workspace_id,
            files_total=1,
            total_lines=10,
            covered_lines_total=8,
            uncovered_lines_total=2,
            line_coverage_ratio=0.8,
            source="manual",
            format="LCOV",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            confidence_score="HIGH",
            file_hash="api_cov_hash",
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.add(coverage)

        # Seed behaviors and journeys to trigger REGRESSION_READY
        behavior = Behavior(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="api_behavior",
            slug="api_behavior",
            risk_level="LOW",
            status="DISCOVERED",
            discovery_source="MANUAL"
        )
        db.add(behavior)

        journey = Journey(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="api_journey",
            slug="api_journey",
            risk_level="LOW",
            status="DISCOVERED"
        )
        db.add(journey)
        db.commit()

        headers = get_auth_headers()
        url = f"/api/repositories/{repo.id}/pull-requests/{pr.id}/recommendation-readiness"
        response = client.get(url, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["can_generate"] is True
        assert data["expected_confidence"] == "MEDIUM"  # ceiling cuts to MEDIUM without AC
        assert data["readiness_level"] == "REGRESSION_READY"
    finally:
        db.close()


def test_get_pr_readiness_high_confidence():
    """Verify HIGH expected confidence when all criteria (including AC and current execution) are met."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_infrastructure(db)
        repo, pr = create_repo_pr(db, workspace_id)
        clear_gate_api_signals(db, repo.id, pr.id)

        # Seed required signals (architecture)
        node = ArchitectureNode(
            id=uuid.uuid4(),
            repository_id=repo.id,
            node_type="MODULE",
            name="API",
            path="app/api.py",
            normalized_path="app/api.py",
            layer="DOMAIN"
        )
        db.add(node)

        # Seed current PR execution & coverage
        test_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pull_request_id=pr.id,
            file_hash="api_hash_1",
            normalized_execution_fingerprint="api_finger_1",
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

        coverage = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo.id,
            workspace_id=workspace_id,
            pull_request_id=pr.id,
            files_total=1,
            total_lines=10,
            covered_lines_total=8,
            uncovered_lines_total=2,
            line_coverage_ratio=0.8,
            source="manual",
            format="LCOV",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            confidence_score="HIGH",
            file_hash="api_cov_hash",
            created_at=datetime.utcnow()
        )
        db.add(coverage)

        # Seed behaviors and journeys to trigger REGRESSION_READY
        behavior = Behavior(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="api_behavior",
            slug="api_behavior",
            risk_level="LOW",
            status="DISCOVERED",
            discovery_source="MANUAL"
        )
        db.add(behavior)

        journey = Journey(
            id=uuid.uuid4(),
            repository_id=repo.id,
            name="api_journey",
            slug="api_journey",
            risk_level="LOW",
            status="DISCOVERED"
        )
        db.add(journey)

        # Seed Acceptance Criteria
        ac = AcceptanceCriterion(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            repository_id=repo.id,
            text="The API must return HTTP 200.",
            normalized_key="api_must_return_200",
            source="PR_DESCRIPTION",
            created_at=datetime.utcnow()
        )
        db.add(ac)
        db.commit()

        headers = get_auth_headers()
        url = f"/api/repositories/{repo.id}/pull-requests/{pr.id}/recommendation-readiness"
        response = client.get(url, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["can_generate"] is True
        assert data["expected_confidence"] == "HIGH"
        assert data["readiness_level"] == "HIGH_CONFIDENCE_READY"
    finally:
        db.close()


def test_get_pr_readiness_blocked_missing_diff():
    """Verify can_generate is False when the PR changed files count is 0."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_infrastructure(db)
        repo, pr = create_repo_pr(db, workspace_id)
        clear_gate_api_signals(db, repo.id, pr.id)

        # Deactivate repo and zero changed files
        pr.changed_files_count = 0
        db.commit()

        headers = get_auth_headers()
        url = f"/api/repositories/{repo.id}/pull-requests/{pr.id}/recommendation-readiness"
        response = client.get(url, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["can_generate"] is False
        assert data["readiness_level"] == "BLOCKED"
    finally:
        db.close()


def test_get_recommendation_run_readiness():
    """Verify GET readiness for an existing recommendation run."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_infrastructure(db)
        repo, pr = create_repo_pr(db, workspace_id)
        clear_gate_api_signals(db, repo.id, pr.id)

        # Seed a semantic entry to satisfy source_code signal WITHOUT activating
        # architecture_graph (which would push score to 50 -> MEDIUM).
        entry = RepositorySemanticEntry(
            id=uuid.uuid4(),
            repository_id=repo.id,
            entry_type="MODULE",
            path="app/api.py",
            normalized_tokens=["api"],
            confidence="HIGH"
        )
        db.add(entry)
        db.commit()

        # Seed RecommendationRun
        rec_run = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pr_id=str(pr.number),
            triggered_by="engineer-manual",
            evidence_quality="LOW",
            engine_version="v1.0",
            ruleset_version="v1",
            degradation_policy_version="v1",
            recommendation_reasoning_summary="Test reasoning",
            pull_request_id=pr.id,
            created_at=datetime.utcnow()
        )
        db.add(rec_run)
        db.commit()

        headers = get_auth_headers()
        url = f"/api/recommendations/{rec_run.id}/readiness"
        response = client.get(url, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["can_generate"] is True
        assert data["expected_confidence"] == "LOW"
    finally:
        db.close()


def test_acknowledge_recommendation_readiness():
    """Verify POST acknowledge-readiness stores the user's bypass decision."""
    db = SessionLocal()
    try:
        workspace_id = setup_test_infrastructure(db)
        repo, pr = create_repo_pr(db, workspace_id)
        clear_gate_api_signals(db, repo.id, pr.id)

        # Seed RecommendationRun
        rec_run = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pr_id=str(pr.number),
            triggered_by="engineer-manual",
            evidence_quality="LOW",
            engine_version="v1.0",
            ruleset_version="v1",
            degradation_policy_version="v1",
            recommendation_reasoning_summary="Test reasoning",
            pull_request_id=pr.id,
            created_at=datetime.utcnow()
        )
        db.add(rec_run)
        db.commit()

        headers = get_auth_headers()
        url = f"/api/recommendations/{rec_run.id}/acknowledge-readiness"
        body = {
            "acknowledged_missing_inputs": ["acceptance_criteria", "current_pr_execution"],
            "decision": "CONTINUE_ANYWAY",
            "note": "User chose to continue with available evidence."
        }
        
        response = client.post(url, json=body, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Check DB
        db.refresh(rec_run)
        assert rec_run.readiness_acknowledged is True
        assert rec_run.readiness_acknowledged_at is not None
        assert rec_run.readiness_acknowledged_missing_inputs == ["acceptance_criteria", "current_pr_execution"]
        assert rec_run.readiness_decision == "CONTINUE_ANYWAY"
    finally:
        db.close()


def test_manual_acceptance_criteria_submission():
    """Verify manual submission of acceptance criteria recalculates readiness and updates DB correctly."""
    db = SessionLocal()
    try:
        from app.models.business_intent import BusinessIntentOverride
        from app.models.acceptance_criterion import AcceptanceCriterion

        workspace_id = setup_test_infrastructure(db)
        repo, pr = create_repo_pr(db, workspace_id)
        clear_gate_api_signals(db, repo.id, pr.id)

        # Seed minimal architecture node to allow MINIMUM_READY
        node = ArchitectureNode(
            id=uuid.uuid4(),
            repository_id=repo.id,
            node_type="MODULE",
            name="API",
            path="app/api.py",
            normalized_path="app/api.py",
            layer="DOMAIN"
        )
        db.add(node)

        # Seed RecommendationRun
        rec_run = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pr_id=str(pr.number),
            triggered_by="engineer-manual",
            evidence_quality="LOW",
            engine_version="v1.0",
            ruleset_version="v1",
            degradation_policy_version="v1",
            recommendation_reasoning_summary="Test reasoning",
            pull_request_id=pr.id,
            evidence_consistency_status="CONSISTENT",
            evidence_health_status="HEALTHY",
            created_at=datetime.utcnow()
        )
        db.add(rec_run)
        db.commit()

        # Submit manual acceptance criteria
        headers = get_auth_headers()
        url = f"/api/repositories/{repo.id}/pull-requests/{pr.id}/acceptance-criteria/manual"
        payload = {
            "business_change": "Implement password recovery functionality",
            "affected_users": "Users who forgot their password",
            "acceptance_criteria": "1. User receives recovery email.\n2. User reset token expires in 1 hour.",
            "risk_notes": "Token reuse risk",
            "testing_notes": "Verify expiration timer"
        }

        response = client.post(url, json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()

        # Assert returned readiness result
        assert data["readiness"]["repository_id"] == str(repo.id)
        assert data["readiness"]["pull_request_id"] == str(pr.id)
        
        # Verify signals in returned data
        available_keys = [sig["key"] for sig in data["readiness"]["available_inputs"]]
        assert "acceptance_criteria" in available_keys
        assert "business_intent" in available_keys

        # Check DB updates
        bio = db.query(BusinessIntentOverride).filter(
            BusinessIntentOverride.pull_request_id == pr.id,
            BusinessIntentOverride.is_active == True
        ).first()
        assert bio is not None
        assert bio.source == "MANUAL_USER_INPUT"
        assert bio.business_change_summary == "Implement password recovery functionality"
        assert bio.extracted_scenarios is not None
        assert bio.mapped_behaviors is not None
        assert len(bio.extracted_scenarios) > 0

        # Verify persisted AcceptanceCriterion records
        ac_records = db.query(AcceptanceCriterion).filter(AcceptanceCriterion.pull_request_id == pr.id).all()
        assert len(ac_records) > 0
        for ac in ac_records:
            assert ac.source == "MANUAL_USER_INPUT"

        # Verify existing run is marked stale
        db.refresh(rec_run)
        assert rec_run.evidence_consistency_status == "STALE"
        assert rec_run.evidence_health_status == "DEGRADED"

    finally:
        db.close()
