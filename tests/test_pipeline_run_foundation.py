"""
Pipeline Run Foundation Tests (Phase 8.0)

Tests for CI/CD pipeline run integration including:
- Pipeline run creation for repository and PR
- PR and changed files resolution
- Recommendation linking
- Idempotency with external_run_id
- Quality gate mapping
- Artifact export
- Secret redaction
- Evidence preservation
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.pipeline_run import PipelineRun, PipelineRunStatus, QualityGateStatus, TriggerSource
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import RecommendationRun
from app.models.release_decision import ReleaseDecision
from app.models.user import Workspace
from app.schemas.pipeline_run import PipelineRunTriggerRequest
from app.services.pipeline_run_service import PipelineRunService
from app.services.quality_gate_service import QualityGateService
from app.services.github_check_service import GitHubCheckService


class TestPipelineRunModel:
    """Test the pipeline run model fields."""
    
    def test_pipeline_run_has_all_fields(self, db_session):
        """Test that pipeline run has all required fields."""
        pipeline_run = PipelineRun(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            provider="GITHUB_ACTIONS",
            external_run_id="12345",
            commit_sha="abc123",
            branch="feature/test",
            status=PipelineRunStatus.RUNNING.value,
            quality_gate=QualityGateStatus.UNKNOWN.value,
            trigger_source=TriggerSource.PULL_REQUEST.value
        )
        
        db_session.add(pipeline_run)
        db_session.commit()
        
        retrieved = db_session.query(PipelineRun).filter(
            PipelineRun.id == pipeline_run.id
        ).first()
        
        assert retrieved is not None
        assert retrieved.provider == "GITHUB_ACTIONS"
        assert retrieved.external_run_id == "12345"
        assert retrieved.status == PipelineRunStatus.RUNNING.value
        assert retrieved.quality_gate == QualityGateStatus.UNKNOWN.value
    
    def test_pipeline_run_status_values(self, db_session):
        """Test that pipeline run accepts all status values."""
        valid_statuses = [
            PipelineRunStatus.PENDING.value,
            PipelineRunStatus.RUNNING.value,
            PipelineRunStatus.COMPLETED.value,
            PipelineRunStatus.FAILED.value,
            PipelineRunStatus.CANCELLED.value
        ]
        
        for status in valid_statuses:
            pipeline_run = PipelineRun(
                id=uuid.uuid4(),
                repository_id=uuid.uuid4(),
                provider="GITHUB_ACTIONS",
                external_run_id=str(uuid.uuid4()),
                commit_sha="abc123",
                status=status,
                quality_gate=QualityGateStatus.UNKNOWN.value
            )
            db_session.add(pipeline_run)
            db_session.commit()
            db_session.delete(pipeline_run)
            db_session.commit()
    
    def test_quality_gate_status_values(self, db_session):
        """Test that quality gate accepts all status values."""
        valid_gates = [
            QualityGateStatus.PASSED.value,
            QualityGateStatus.PARTIAL.value,
            QualityGateStatus.FAILED.value,
            QualityGateStatus.BLOCKED.value,
            QualityGateStatus.UNKNOWN.value
        ]
        
        for gate in valid_gates:
            pipeline_run = PipelineRun(
                id=uuid.uuid4(),
                repository_id=uuid.uuid4(),
                provider="GITHUB_ACTIONS",
                external_run_id=str(uuid.uuid4()),
                commit_sha="abc123",
                status=PipelineRunStatus.RUNNING.value,
                quality_gate=gate
            )
            db_session.add(pipeline_run)
            db_session.commit()
            db_session.delete(pipeline_run)
            db_session.commit()


class TestPipelineRunTrigger:
    """Test pipeline run trigger functionality."""
    
    def test_pipeline_run_created_for_repository_and_pr(self, db_session):
        """Test that pipeline run can be created for repository and PR."""
        # Create workspace and repository
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=12345,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        # Create PR
        pull_request = PullRequest(
            id=uuid.uuid4(),
            repository_id=repository.id,
            github_pr_id=1,
            number=1,
            title="Test PR",
            author="testuser",
            source_branch="feature",
            target_branch="main",
            state="open",
            head_commit_sha="abc123",
            changed_files_count=6,
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db_session.add(pull_request)
        db_session.commit()
        
        # Trigger pipeline run
        service = PipelineRunService()
        request = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="run-123",
            pull_request_number=1,
            commit_sha="abc123",
            branch="feature",
            trigger_source="pull_request"
        )
        
        response = service.trigger_pipeline_run(db_session, repository.id, request)
        
        assert response.pipeline_run_id is not None
        assert response.status == PipelineRunStatus.RUNNING.value
        assert response.quality_gate == QualityGateStatus.UNKNOWN.value
        assert response.changed_files == 6
    
    def test_pipeline_run_resolves_pr_changed_files(self, db_session):
        """Test that pipeline run resolves PR changed files."""
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=12345,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        pull_request = PullRequest(
            id=uuid.uuid4(),
            repository_id=repository.id,
            github_pr_id=1,
            number=1,
            title="Test PR",
            author="testuser",
            source_branch="feature",
            target_branch="main",
            state="open",
            head_commit_sha="abc123",
            changed_files_count=10,
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db_session.add(pull_request)
        db_session.commit()
        
        service = PipelineRunService()
        request = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="run-123",
            pull_request_number=1,
            commit_sha="abc123",
            branch="feature"
        )
        
        response = service.trigger_pipeline_run(db_session, repository.id, request)
        
        assert response.changed_files == 10
    
    def test_pipeline_run_links_to_recommendation(self, db_session):
        """Test that pipeline run links to existing recommendation."""
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=12345,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        pull_request = PullRequest(
            id=uuid.uuid4(),
            repository_id=repository.id,
            github_pr_id=1,
            number=1,
            title="Test PR",
            author="testuser",
            source_branch="feature",
            target_branch="main",
            state="open",
            head_commit_sha="abc123",
            changed_files_count=6,
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db_session.add(pull_request)
        
        # Create recommendation
        recommendation = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repository.id,
            pr_id="pr-1",
            triggered_by="manual",
            evidence_quality="HIGH",
            engine_version="v1.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Test recommendation",
            pull_request_id=pull_request.id
        )
        db_session.add(recommendation)
        db_session.commit()
        
        service = PipelineRunService()
        request = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="run-123",
            pull_request_number=1,
            commit_sha="abc123",
            branch="feature"
        )
        
        response = service.trigger_pipeline_run(db_session, repository.id, request)
        
        assert response.recommendation_run_id == recommendation.id


class TestPipelineRunIdempotency:
    """Test pipeline run idempotency."""
    
    def test_same_external_run_id_returns_existing_pipeline_run(self, db_session):
        """Test that same external_run_id returns existing PipelineRun."""
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=12345,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        pull_request = PullRequest(
            id=uuid.uuid4(),
            repository_id=repository.id,
            github_pr_id=1,
            number=1,
            title="Test PR",
            author="testuser",
            source_branch="feature",
            target_branch="main",
            state="open",
            head_commit_sha="abc123",
            changed_files_count=6,
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db_session.add(pull_request)
        db_session.commit()
        
        service = PipelineRunService()
        request = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="run-123",
            pull_request_number=1,
            commit_sha="abc123",
            branch="feature"
        )
        
        # First call
        response1 = service.trigger_pipeline_run(db_session, repository.id, request)
        
        # Second call with same external_run_id
        response2 = service.trigger_pipeline_run(db_session, repository.id, request)
        
        # Should return same pipeline run
        assert response1.pipeline_run_id == response2.pipeline_run_id
    
    def test_new_external_run_id_creates_new_pipeline_run(self, db_session):
        """Test that new external_run_id creates new PipelineRun attempt."""
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=12345,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        pull_request = PullRequest(
            id=uuid.uuid4(),
            repository_id=repository.id,
            github_pr_id=1,
            number=1,
            title="Test PR",
            author="testuser",
            source_branch="feature",
            target_branch="main",
            state="open",
            head_commit_sha="abc123",
            changed_files_count=6,
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db_session.add(pull_request)
        db_session.commit()
        
        service = PipelineRunService()
        
        # First call
        request1 = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="run-123",
            pull_request_number=1,
            commit_sha="abc123",
            branch="feature"
        )
        response1 = service.trigger_pipeline_run(db_session, repository.id, request1)
        
        # Second call with different external_run_id
        request2 = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="run-456",
            pull_request_number=1,
            commit_sha="abc123",
            branch="feature"
        )
        response2 = service.trigger_pipeline_run(db_session, repository.id, request2)
        
        # Should create new pipeline run
        assert response1.pipeline_run_id != response2.pipeline_run_id


class TestQualityGateMapping:
    """Test quality gate mapping logic."""
    
    def test_quality_gate_maps_verified_to_passed(self):
        """Test that Verified release decision maps to PASSED."""
        release_decision = ReleaseDecision(
            id=uuid.uuid4(),
            recommendation_run_id=uuid.uuid4(),
            decision_status="APPROVED"
        )
        
        quality_gate = QualityGateService.compute_quality_gate(
            release_decision=release_decision,
            recommendation_health="READY",
            required_before_release_count=0
        )
        
        assert quality_gate == QualityGateStatus.PASSED
    
    def test_quality_gate_maps_partially_verified_with_required_to_partial(self):
        """Test that Partially Verified with required items maps to PARTIAL."""
        release_decision = ReleaseDecision(
            id=uuid.uuid4(),
            recommendation_run_id=uuid.uuid4(),
            decision_status="PARTIALLY_VERIFIED"
        )
        
        quality_gate = QualityGateService.compute_quality_gate(
            release_decision=release_decision,
            recommendation_health="READY",
            required_before_release_count=6
        )
        
        assert quality_gate == QualityGateStatus.PARTIAL
    
    def test_quality_gate_maps_failed_validation_to_failed(self):
        """Test that failed validation maps to FAILED."""
        quality_gate = QualityGateService.compute_quality_gate(
            release_decision=None,
            recommendation_health="READY",
            required_before_release_count=0,
            has_blocking_failed_tests=True
        )
        
        assert quality_gate == QualityGateStatus.FAILED
    
    def test_recommendation_health_ready_alone_does_not_produce_passed(self):
        """Test that Recommendation Health Ready alone does NOT produce PASSED."""
        quality_gate = QualityGateService.compute_quality_gate(
            release_decision=None,
            recommendation_health="READY",
            required_before_release_count=0
        )
        
        # Should be UNKNOWN without release decision
        assert quality_gate == QualityGateStatus.UNKNOWN
    
    def test_quality_gate_maps_generation_failed_to_blocked(self):
        """Test that generation failure maps to BLOCKED."""
        quality_gate = QualityGateService.compute_quality_gate(
            release_decision=None,
            recommendation_health="READY",
            required_before_release_count=0,
            recommendation_generation_failed=True
        )
        
        assert quality_gate == QualityGateStatus.BLOCKED


class TestArtifactExport:
    """Test artifact export functionality."""
    
    def test_artifact_endpoint_returns_ci_safe_json(self, db_session):
        """Test that artifact endpoint returns CI-safe JSON."""
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=12345,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        pull_request = PullRequest(
            id=uuid.uuid4(),
            repository_id=repository.id,
            github_pr_id=1,
            number=1,
            title="Test PR",
            author="testuser",
            source_branch="feature",
            target_branch="main",
            state="open",
            head_commit_sha="abc123",
            changed_files_count=6,
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db_session.add(pull_request)
        
        pipeline_run = PipelineRun(
            id=uuid.uuid4(),
            repository_id=repository.id,
            pull_request_id=pull_request.id,
            provider="GITHUB_ACTIONS",
            external_run_id="run-123",
            commit_sha="abc123",
            status=PipelineRunStatus.COMPLETED.value,
            quality_gate=QualityGateStatus.PARTIAL.value
        )
        db_session.add(pipeline_run)
        db_session.commit()
        
        service = PipelineRunService()
        artifact = service.get_artifact(db_session, pipeline_run.id)
        
        assert artifact["pipeline_run_id"] == str(pipeline_run.id)
        assert artifact["commit_sha"] == "abc123"
        assert artifact["changed_files"] == 6
        assert artifact["quality_gate"] == QualityGateStatus.PARTIAL.value
        assert "timestamp" in artifact


class TestGitHubCheckService:
    """Test GitHub check service."""
    
    def test_github_status_mapping_works(self):
        """Test that GitHub status mapping works correctly."""
        service = GitHubCheckService(github_token="test")
        assert service.map_quality_gate_to_status(QualityGateStatus.PASSED) == "success"
        assert service.map_quality_gate_to_status(QualityGateStatus.PARTIAL) == "neutral"
        assert service.map_quality_gate_to_status(QualityGateStatus.FAILED) == "failure"
        assert service.map_quality_gate_to_status(QualityGateStatus.BLOCKED) == "failure"
        assert service.map_quality_gate_to_status(QualityGateStatus.UNKNOWN) == "pending"
    
    def test_github_comment_markdown_generated(self):
        """Test that GitHub comment markdown is generated."""
        regression_scope = {
            "required": 6,
            "recommended": 0,
            "optional": 2,
            "safe_to_skip": 16,
            "total_executable": 8
        }
        
        comment = GitHubCheckService.generate_pr_comment(
            QualityGateStatus.PARTIAL,
            6,
            regression_scope,
            "Core tests passed, but 6 critical requirements still require review."
        )
        
        assert "Quality Gate: Partial" in comment
        assert "**Required:** 6" in comment
        assert "**Optional:** 2" in comment
        assert "**Safe to Skip:** 16" in comment
        assert "**Total Executable:** 8" in comment
    
    def test_no_secret_values_exposed_in_artifact(self):
        """Test that secret values are redacted from artifacts."""
        payload = {
            "api_key": "secret-key-123",
            "password": "my-password",
            "normal_field": "public-value"
        }
        
        redacted = GitHubCheckService.redact_secrets(payload)
        
        assert redacted["api_key"] == "***REDACTED***"
        assert redacted["password"] == "***REDACTED***"
        assert redacted["normal_field"] == "public-value"


class TestEvidencePreservation:
    """Test that evidence preservation invariants are maintained."""
    
    def test_evidence_truth_unchanged(self, db_session):
        """Test that evidence truth is unchanged by pipeline operations."""
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=12345,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        pull_request = PullRequest(
            id=uuid.uuid4(),
            repository_id=repository.id,
            github_pr_id=1,
            number=1,
            title="Test PR",
            author="testuser",
            source_branch="feature",
            target_branch="main",
            state="open",
            head_commit_sha="abc123",
            changed_files_count=6,
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db_session.add(pull_request)
        
        # Create recommendation with evidence snapshot
        recommendation = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repository.id,
            pr_id="pr-1",
            triggered_by="manual",
            evidence_quality="HIGH",
            engine_version="v1.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Test recommendation",
            pull_request_id=pull_request.id,
            requirement_evidence_snapshot_json='{"required_items": [{"id": "1"}, {"id": "2"}]}'
        )
        db_session.add(recommendation)
        db_session.commit()
        
        # Trigger pipeline run
        service = PipelineRunService()
        request = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="run-123",
            pull_request_number=1,
            commit_sha="abc123",
            branch="feature"
        )
        
        response = service.trigger_pipeline_run(db_session, repository.id, request)
        
        # Verify evidence snapshot unchanged
        retrieved = db_session.query(RecommendationRun).filter(
            RecommendationRun.id == recommendation.id
        ).first()
        
        assert retrieved.requirement_evidence_snapshot_json == '{"required_items": [{"id": "1"}, {"id": "2"}]}'
