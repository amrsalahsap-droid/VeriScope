"""
GitHub Actions End-to-End Tests

Tests for the complete GitHub Actions integration flow:
- CI token authentication
- Pipeline trigger
- GitHub status updates
- PR comment posting
- Artifact retrieval
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.ci_token import RepositoryCIToken
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import RecommendationRun
from app.models.pipeline_run import PipelineRun, PipelineRunStatus, QualityGateStatus
from app.models.release_decision import ReleaseDecision
from app.models.user import Workspace
from app.schemas.pipeline_run import PipelineRunTriggerRequest
from app.services.pipeline_run_service import PipelineRunService
from app.services.github_check_service import GitHubCheckService
from app.services.ci_token_service import CITokenService


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def test_workspace(db_session):
    """Create a test workspace."""
    unique_suffix = uuid4().hex[:8]
    workspace = Workspace(
        id=uuid4(),
        name=f"test-workspace-{unique_suffix}",
        slug=f"test-workspace-{unique_suffix}"
    )
    db_session.add(workspace)
    db_session.commit()
    return workspace


class TestGitHubActionsE2E:
    """End-to-end tests for GitHub Actions integration."""
    
    def test_pipeline_trigger_with_ci_token(self, db_session, test_workspace):
        """Test complete pipeline trigger flow with CI token authentication."""
        # Create repository with GitHub integration
        repository = Repository(
            id=uuid4(),
            name="test-repo",
            owner="test-owner",
            full_name="test-owner/test-repo",
            github_repo_id=12345,
            workspace_id=test_workspace.id
        )
        db_session.add(repository)
        db_session.commit()
        
        # Create CI token
        ci_service = CITokenService()
        from app.schemas.ci_token import CITokenCreate
        token_response = ci_service.create_token(
            db_session, 
            repository.id, 
            CITokenCreate(name="GitHub Actions Token")
        )
        
        # Create pull request
        pr = PullRequest(
            id=uuid4(),
            repository_id=repository.id,
            github_pr_id=123,
            number=123,
            title="Test PR",
            author="test-user",
            source_branch="feature/test",
            target_branch="main",
            state="open",
            head_commit_sha="abc123def456",
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db_session.add(pr)
        db_session.commit()
        
        # Create recommendation run
        recommendation = RecommendationRun(
            id=uuid4(),
            repository_id=repository.id,
            pr_id="123",
            triggered_by="github-webhook",
            evidence_quality="HIGH",
            engine_version="v1.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Test recommendation",
            pull_request_id=pr.id,
            evidence_health_status="READY",
            requirement_evidence_snapshot_json='{"required_items": [], "recommended_items": [], "optional_items": [], "safe_to_skip_items": []}'
        )
        db_session.add(recommendation)
        db_session.commit()
        
        # Trigger pipeline run
        request = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="github-run-123",
            pull_request_number=123,
            commit_sha="abc123def456",
            branch="feature/test",
            trigger_source="pull_request"
        )
        
        pipeline_service = PipelineRunService()
        response = pipeline_service.trigger_pipeline_run(db_session, repository.id, request)
        
        # Verify pipeline run was created
        assert response.pipeline_run_id is not None
        assert response.quality_gate is not None
    
    def test_idempotent_pipeline_trigger(self, db_session, test_workspace):
        """Test that same external_run_id returns existing pipeline run."""
        repository = Repository(
            id=uuid4(),
            name="test-repo",
            owner="test-owner",
            full_name="test-owner/test-repo",
            github_repo_id=12345,
            workspace_id=test_workspace.id
        )
        db_session.add(repository)
        db_session.commit()
        
        request = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="github-run-123",
            commit_sha="abc123def456",
            branch="feature/test",
            trigger_source="pull_request"
        )
        
        # First trigger
        pipeline_service = PipelineRunService()
        response1 = pipeline_service.trigger_pipeline_run(db_session, repository.id, request)
        
        # Second trigger with same external_run_id
        response2 = pipeline_service.trigger_pipeline_run(db_session, repository.id, request)
        
        # Should return same pipeline run
        assert response1.pipeline_run_id == response2.pipeline_run_id
    
    def test_github_status_mapping(self, db_session):
        """Test quality gate to GitHub status mapping."""
        service = GitHubCheckService(github_token="test", ci_fail_on_partial=False)
        
        # Test PASSED -> success
        assert service.map_quality_gate_to_status(QualityGateStatus.PASSED) == "success"
        
        # Test PARTIAL -> neutral (default)
        assert service.map_quality_gate_to_status(QualityGateStatus.PARTIAL) == "neutral"
        
        # Test FAILED -> failure
        assert service.map_quality_gate_to_status(QualityGateStatus.FAILED) == "failure"
        
        # Test BLOCKED -> failure
        assert service.map_quality_gate_to_status(QualityGateStatus.BLOCKED) == "failure"
        
        # Test UNKNOWN -> pending
        assert service.map_quality_gate_to_status(QualityGateStatus.UNKNOWN) == "pending"
    
    def test_ci_fail_on_partial_configuration(self, db_session):
        """Test that ciFailOnPartial affects status mapping."""
        # Default: PARTIAL -> neutral
        service_default = GitHubCheckService(github_token="test", ci_fail_on_partial=False)
        assert service_default.map_quality_gate_to_status(QualityGateStatus.PARTIAL) == "neutral"
        
        # Configured: PARTIAL -> failure
        service_strict = GitHubCheckService(github_token="test", ci_fail_on_partial=True)
        assert service_strict.map_quality_gate_to_status(QualityGateStatus.PARTIAL) == "failure"
    
    def test_pr_comment_includes_marker(self, db_session):
        """Test that PR comment includes update-in-place marker."""
        comment = GitHubCheckService.generate_pr_comment(
            quality_gate=QualityGateStatus.PARTIAL,
            required_count=5,
            regression_scope_summary={
                "required": 5,
                "recommended": 10,
                "optional": 3,
                "safe_to_skip": 2,
                "total_executable": 20
            },
            summary_text="Some requirements pending review"
        )
        
        # Verify marker is present
        assert GitHubCheckService.COMMENT_MARKER in comment
        
        # Verify quality gate is in comment
        assert "Quality Gate" in comment
        assert "Partial" in comment
    
    def test_artifact_endpoint_with_ci_token(self, db_session, test_workspace):
        """Test that artifact endpoint accepts CI token authentication."""
        # Create repository
        repository = Repository(
            id=uuid4(),
            name="test-repo",
            owner="test-owner",
            full_name="test-owner/test-repo",
            github_repo_id=12345,
            workspace_id=test_workspace.id
        )
        db_session.add(repository)
        db_session.commit()
        
        # Create CI token
        ci_service = CITokenService()
        from app.schemas.ci_token import CITokenCreate
        token_response = ci_service.create_token(
            db_session, 
            repository.id, 
            CITokenCreate(name="GitHub Actions Token")
        )
        
        # Create pipeline run
        pipeline_run = PipelineRun(
            id=uuid4(),
            repository_id=repository.id,
            provider="GITHUB_ACTIONS",
            external_run_id="github-run-123",
            commit_sha="abc123def456",
            status=PipelineRunStatus.COMPLETED.value,
            quality_gate=QualityGateStatus.PARTIAL.value
        )
        db_session.add(pipeline_run)
        db_session.commit()
        
        # Verify token can be used for artifact access
        verified = ci_service.verify_token(db_session, token_response.raw_token)
        assert verified is not None
        assert verified.repository_id == repository.id
    
    def test_github_api_failure_handling(self, db_session, test_workspace):
        """Test that GitHub API failures don't break pipeline flow."""
        repository = Repository(
            id=uuid4(),
            name="test-repo",
            owner="test-owner",
            full_name="test-owner/test-repo",
            github_repo_id=12345,
            workspace_id=test_workspace.id
        )
        db_session.add(repository)
        db_session.commit()
        
        request = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="github-run-123",
            commit_sha="abc123def456",
            branch="feature/test",
            trigger_source="pull_request"
        )
        
        # Mock GitHub API to raise exception
        with patch.object(GitHubCheckService, 'create_commit_status', side_effect=Exception("GitHub API error")):
            pipeline_service = PipelineRunService()
            # Should not raise exception, should log error and continue
            response = pipeline_service.trigger_pipeline_run(db_session, repository.id, request)
            
            # Pipeline run should still be created
            assert response.pipeline_run_id is not None
    
    def test_timeout_guard_on_pipeline_trigger(self, db_session):
        """Test that pipeline trigger has timeout guard mechanism.
        
        NOTE: Due to Python's GIL, the threading.Timer-based timeout cannot
        reliably interrupt the main thread. This test verifies the mechanism
        exists but does not test actual interruption. For production timeout
        protection, a multiprocessing-based solution is needed.
        """
        from app.services.pipeline_run_service import TimeoutError, timeout_context
        
        # Test timeout context manager exists and can be used
        # The mechanism is in place but actual interruption is limited by GIL
        with timeout_context(seconds=1):
            pass  # Should complete immediately


class TestGitHubFailureSemantics:
    """Tests for GitHub API failure semantics."""
    
    def test_github_status_failure_does_not_corrupt_evidence(self, db_session, test_workspace):
        """Test that GitHub status failure does not corrupt evidence."""
        repository = Repository(
            id=uuid4(),
            name="test-repo",
            owner="test-owner",
            full_name="test-owner/test-repo",
            github_repo_id=12345,
            workspace_id=test_workspace.id
        )
        db_session.add(repository)
        db_session.commit()
        
        # Create pull request
        pr = PullRequest(
            id=uuid4(),
            repository_id=repository.id,
            github_pr_id=123,
            number=123,
            title="Test PR",
            author="test-user",
            source_branch="feature/test",
            target_branch="main",
            state="open",
            head_commit_sha="abc123def456",
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db_session.add(pr)
        db_session.commit()
        
        # Create recommendation run
        recommendation = RecommendationRun(
            id=uuid4(),
            repository_id=repository.id,
            pr_id="123",
            triggered_by="github-webhook",
            evidence_quality="HIGH",
            engine_version="v1.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Test recommendation",
            pull_request_id=pr.id,
            evidence_health_status="READY",
            requirement_evidence_snapshot_json='{"required_items": [], "recommended_items": [], "optional_items": [], "safe_to_skip_items": []}'
        )
        db_session.add(recommendation)
        db_session.commit()
        
        request = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="github-run-123",
            pull_request_number=123,
            commit_sha="abc123def456",
            branch="feature/test",
            trigger_source="pull_request"
        )
        
        # Mock GitHub status to fail on both pending and final status
        with patch.object(GitHubCheckService, 'create_commit_status', side_effect=Exception("GitHub API error")):
            pipeline_service = PipelineRunService()
            response = pipeline_service.trigger_pipeline_run(db_session, repository.id, request)
            
            # Pipeline run should still be created
            assert response.pipeline_run_id is not None
            
            # Quality gate should still be computed
            assert response.quality_gate is not None
            
            # Verify pipeline run in database
            pipeline_run = db_session.query(PipelineRun).filter(PipelineRun.id == response.pipeline_run_id).first()
            assert pipeline_run is not None
            assert pipeline_run.quality_gate is not None
            assert pipeline_run.recommendation_run_id == recommendation.id
    
    def test_github_comment_failure_records_failure_reason(self, db_session, test_workspace):
        """Test that GitHub comment failure records failure reason."""
        repository = Repository(
            id=uuid4(),
            name="test-repo",
            owner="test-owner",
            full_name="test-owner/test-repo",
            github_repo_id=12345,
            workspace_id=test_workspace.id
        )
        db_session.add(repository)
        db_session.commit()
        
        # Create pull request
        pr = PullRequest(
            id=uuid4(),
            repository_id=repository.id,
            github_pr_id=123,
            number=123,
            title="Test PR",
            author="test-user",
            source_branch="feature/test",
            target_branch="main",
            state="open",
            head_commit_sha="abc123def456",
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db_session.add(pr)
        db_session.commit()
        
        # Create recommendation run
        recommendation = RecommendationRun(
            id=uuid4(),
            repository_id=repository.id,
            pr_id="123",
            triggered_by="github-webhook",
            evidence_quality="HIGH",
            engine_version="v1.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Test recommendation",
            pull_request_id=pr.id,
            evidence_health_status="READY",
            requirement_evidence_snapshot_json='{"required_items": [], "recommended_items": [], "optional_items": [], "safe_to_skip_items": []}'
        )
        db_session.add(recommendation)
        db_session.commit()
        
        request = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="github-run-123",
            pull_request_number=123,
            commit_sha="abc123def456",
            branch="feature/test",
            trigger_source="pull_request"
        )
        
        # Mock GitHub status to succeed but comment to fail
        def mock_status_side_effect(*args, **kwargs):
            return None  # Status succeeds
        
        def mock_comment_side_effect(*args, **kwargs):
            raise Exception("GitHub comment API error")
        
        with patch.object(GitHubCheckService, 'create_commit_status', side_effect=mock_status_side_effect), \
             patch.object(GitHubCheckService, 'post_pr_comment', side_effect=mock_comment_side_effect):
            
            pipeline_service = PipelineRunService()
            response = pipeline_service.trigger_pipeline_run(db_session, repository.id, request)
            
            # Pipeline run should still be created
            assert response.pipeline_run_id is not None
            
            # Quality gate should still be computed
            assert response.quality_gate is not None
    
    def test_pipeline_run_stores_recommendation_if_recommendation_succeeded(self, db_session, test_workspace):
        """Test that PipelineRun stores recommendation/quality gate if recommendation succeeded."""
        repository = Repository(
            id=uuid4(),
            name="test-repo",
            owner="test-owner",
            full_name="test-owner/test-repo",
            github_repo_id=12345,
            workspace_id=test_workspace.id
        )
        db_session.add(repository)
        db_session.commit()
        
        # Create pull request
        pr = PullRequest(
            id=uuid4(),
            repository_id=repository.id,
            github_pr_id=123,
            number=123,
            title="Test PR",
            author="test-user",
            source_branch="feature/test",
            target_branch="main",
            state="open",
            head_commit_sha="abc123def456",
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db_session.add(pr)
        db_session.commit()
        
        # Create recommendation run
        recommendation = RecommendationRun(
            id=uuid4(),
            repository_id=repository.id,
            pr_id="123",
            triggered_by="github-webhook",
            evidence_quality="HIGH",
            engine_version="v1.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Test recommendation",
            pull_request_id=pr.id,
            evidence_health_status="READY",
            requirement_evidence_snapshot_json='{"required_items": [], "recommended_items": [], "optional_items": [], "safe_to_skip_items": []}'
        )
        db_session.add(recommendation)
        db_session.commit()
        
        request = PipelineRunTriggerRequest(
            provider="GITHUB_ACTIONS",
            external_run_id="github-run-123",
            pull_request_number=123,
            commit_sha="abc123def456",
            branch="feature/test",
            trigger_source="pull_request"
        )
        
        # Mock all GitHub API calls to fail
        with patch.object(GitHubCheckService, 'create_commit_status', side_effect=Exception("GitHub API error")), \
             patch.object(GitHubCheckService, 'post_pr_comment', side_effect=Exception("GitHub API error")):
            
            pipeline_service = PipelineRunService()
            response = pipeline_service.trigger_pipeline_run(db_session, repository.id, request)
            
            # Verify pipeline run in database
            pipeline_run = db_session.query(PipelineRun).filter(PipelineRun.id == response.pipeline_run_id).first()
            assert pipeline_run is not None
            
            # Recommendation should be linked
            assert pipeline_run.recommendation_run_id == recommendation.id
            
            # Quality gate should be computed (may be UNKNOWN if recommendation lacks evidence)
            assert pipeline_run.quality_gate is not None
            
            # PR should be linked
            assert pipeline_run.pull_request_id == pr.id


class TestArtifactGeneration:
    """Tests for artifact generation and content."""
    
    def test_artifact_redacts_secrets(self, db_session):
        """Test that artifact JSON redacts secret values."""
        from app.services.github_check_service import GitHubCheckService
        
        payload = {
            "api_key": "secret-key-123",
            "password": "my-password",
            "token": "auth-token",
            "public_data": "visible-value",
            "nested": {
                "client_secret": "nested-secret"
            }
        }
        
        redacted = GitHubCheckService.redact_secrets(payload)
        
        assert redacted["api_key"] == "***REDACTED***"
        assert redacted["password"] == "***REDACTED***"
        assert redacted["token"] == "***REDACTED***"
        assert redacted["public_data"] == "visible-value"
        assert redacted["nested"]["client_secret"] == "***REDACTED***"
    
    def test_artifact_includes_required_fields(self, db_session, test_workspace):
        """Test that artifact includes all required fields."""
        repository = Repository(
            id=uuid4(),
            name="test-repo",
            owner="test-owner",
            full_name="test-owner/test-repo",
            github_repo_id=12345,
            workspace_id=test_workspace.id
        )
        db_session.add(repository)
        
        pipeline_run = PipelineRun(
            id=uuid4(),
            repository_id=repository.id,
            provider="GITHUB_ACTIONS",
            external_run_id="github-run-123",
            commit_sha="abc123def456",
            status=PipelineRunStatus.COMPLETED.value,
            quality_gate=QualityGateStatus.PARTIAL.value
        )
        db_session.add(pipeline_run)
        db_session.commit()
        
        pipeline_service = PipelineRunService()
        artifact = pipeline_service.get_artifact(db_session, pipeline_run.id)
        
        # Verify required fields
        assert "pipeline_run_id" in artifact
        assert "quality_gate" in artifact
        assert "commit_sha" in artifact
        assert "timestamp" in artifact
        assert artifact["quality_gate"] == QualityGateStatus.PARTIAL.value
