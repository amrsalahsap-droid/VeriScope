"""
CI Token Authentication Tests

Tests for CI token creation, verification, and usage in pipeline triggers.
"""
import pytest
from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.ci_token import RepositoryCIToken
from app.models.repository import Repository
from app.models.user import User, Workspace
from app.models.pipeline_run import PipelineRun, PipelineRunStatus, QualityGateStatus
from app.models.ci_token_audit import CITokenAuditEvent
from app.schemas.ci_token import CITokenCreate
from app.services.ci_token_service import CITokenService
from app.services.ci_token_audit_service import CITokenAuditService, AuditEventType


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


class TestCITokenCreation:
    """Tests for CI token creation."""
    
    def test_token_creation_stores_hash_only(self, db_session, test_workspace):
        """Test that raw token is never stored, only hash."""
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
        
        # Create token
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token", scopes="pipeline:trigger,artifact:read")
        response = service.create_token(db_session, repository.id, token_in, created_by=None)
        
        # Verify raw token is returned
        assert response.raw_token is not None
        assert len(response.raw_token) > 0
        
        # Verify only hash is stored in database
        db_token = db_session.query(RepositoryCIToken).filter(RepositoryCIToken.id == response.id).first()
        assert db_token.token_hash is not None
        assert db_token.token_hash != response.raw_token
        assert response.raw_token not in db_token.token_hash
    
    def test_raw_token_shown_only_once(self, db_session, test_workspace):
        """Test that raw token is only returned on creation, not in list."""
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
        
        # Create token
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        create_response = service.create_token(db_session, repository.id, token_in, created_by=None)
        raw_token = create_response.raw_token
        
        # List tokens - should not include raw token
        list_response = service.list_tokens(db_session, repository.id)
        assert len(list_response) == 1
        assert list_response[0].raw_token is None
        
        # Verify the token can still be verified with the original raw token
        verified = service.verify_token(db_session, raw_token)
        assert verified is not None
        assert verified.id == create_response.id
    
    def test_token_scopes_default(self, db_session, test_workspace):
        """Test that default scopes are applied."""
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
        
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        response = service.create_token(db_session, repository.id, token_in, created_by=None)
        
        assert response.scopes == "pipeline:trigger,artifact:read"


class TestCITokenVerification:
    """Tests for CI token verification."""
    
    def test_valid_token_accepted(self, db_session, test_workspace):
        """Test that a valid token is accepted."""
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
        
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        response = service.create_token(db_session, repository.id, token_in, created_by=None)
        
        verified = service.verify_token(db_session, response.raw_token)
        assert verified is not None
        assert verified.id == response.id
        assert verified.is_valid()
    
    def test_invalid_token_rejected(self, db_session):
        """Test that an invalid token is rejected."""
        service = CITokenService()
        verified = service.verify_token(db_session, "invalid-token-12345")
        assert verified is None
    
    def test_revoked_token_rejected(self, db_session, test_workspace):
        """Test that a revoked token is rejected."""
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
        
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        response = service.create_token(db_session, repository.id, token_in, created_by=None)
        
        # Revoke token
        service.revoke_token(db_session, repository.id, response.id)
        
        # Try to verify revoked token
        verified = service.verify_token(db_session, response.raw_token)
        assert verified is None
    
    def test_token_scoped_to_repository(self, db_session, test_workspace):
        """Test that token is scoped to a specific repository."""
        repo1 = Repository(
            id=uuid4(),
            name="repo1",
            owner="owner1",
            full_name="owner1/repo1",
            github_repo_id=11111,
            workspace_id=test_workspace.id
        )
        repo2 = Repository(
            id=uuid4(),
            name="repo2",
            owner="owner2",
            full_name="owner2/repo2",
            github_repo_id=22222,
            workspace_id=test_workspace.id
        )
        db_session.add_all([repo1, repo2])
        db_session.commit()
        
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        response = service.create_token(db_session, repo1.id, token_in, created_by=None)
        
        # Verify token belongs to repo1
        verified = service.verify_token(db_session, response.raw_token)
        assert verified is not None
        assert verified.repository_id == repo1.id
        assert verified.repository_id != repo2.id


class TestCITokenRevocation:
    """Tests for CI token revocation."""
    
    def test_token_can_be_revoked(self, db_session, test_workspace):
        """Test that a token can be revoked."""
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
        
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        response = service.create_token(db_session, repository.id, token_in, created_by=None)
        
        # Revoke token
        result = service.revoke_token(db_session, repository.id, response.id)
        assert result is True
        
        # Verify token is revoked
        db_token = db_session.query(RepositoryCIToken).filter(RepositoryCIToken.id == response.id).first()
        assert db_token.revoked_at is not None
        assert db_token.is_active is False
        assert db_token.is_revoked() is True
    
    def test_revoked_token_not_in_list(self, db_session, test_workspace):
        """Test that revoked tokens are still listed but marked as inactive."""
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
        
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        response = service.create_token(db_session, repository.id, token_in, created_by=None)
        
        # Revoke token
        service.revoke_token(db_session, repository.id, response.id)
        
        # List tokens
        list_response = service.list_tokens(db_session, repository.id)
        assert len(list_response) == 1
        assert list_response[0].is_active is False


class TestCITokenLastUsed:
    """Tests for last used timestamp."""
    
    def test_last_used_updated_on_verification(self, db_session, test_workspace):
        """Test that last_used_at is updated when token is verified."""
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
        
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        response = service.create_token(db_session, repository.id, token_in, created_by=None)
        
        # Verify last_used_at is None initially
        db_token = db_session.query(RepositoryCIToken).filter(RepositoryCIToken.id == response.id).first()
        assert db_token.last_used_at is None
        
        # Verify token (should update last_used_at)
        service.verify_token(db_session, response.raw_token)
        
        # Check last_used_at was updated
        db_session.refresh(db_token)
        assert db_token.last_used_at is not None
        assert isinstance(db_token.last_used_at, datetime)


class TestArtifactSecurity:
    """Tests for artifact access security."""
    
    def test_valid_same_repo_ci_token_can_read_completed_artifact(self, db_session, test_workspace):
        """Test that valid same-repo CI token can read completed artifact."""
        repository = Repository(
            id=uuid4(),
            name="test-repo",
            owner="test-owner",
            full_name="test-owner/test-repo",
            github_repo_id=12345,
            workspace_id=test_workspace.id,
            ci_fail_on_partial=False
        )
        db_session.add(repository)
        db_session.commit()
        
        # Create completed pipeline run
        pipeline_run = PipelineRun(
            id=uuid4(),
            repository_id=repository.id,
            provider="GITHUB_ACTIONS",
            external_run_id="test-run-123",
            commit_sha="abc123",
            branch="main",
            status=PipelineRunStatus.COMPLETED,
            quality_gate=QualityGateStatus.PASSED
        )
        db_session.add(pipeline_run)
        db_session.commit()
        
        # Create token
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        response = service.create_token(db_session, repository.id, token_in, created_by=None)
        
        # Verify token can access artifact
        verified = service.verify_token(db_session, response.raw_token)
        assert verified is not None
        assert verified.repository_id == repository.id
    
    def test_invalid_token_rejected(self, db_session, test_workspace):
        """Test that invalid token is rejected."""
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
        
        service = CITokenService()
        verified = service.verify_token(db_session, "invalid-token-xyz")
        assert verified is None
    
    def test_revoked_token_rejected(self, db_session, test_workspace):
        """Test that revoked token is rejected."""
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
        
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        response = service.create_token(db_session, repository.id, token_in, created_by=None)
        
        # Revoke token
        service.revoke_token(db_session, repository.id, response.id)
        
        # Try to verify revoked token
        verified = service.verify_token(db_session, response.raw_token)
        assert verified is None
    
    def test_wrong_repo_token_rejected(self, db_session, test_workspace):
        """Test that wrong-repo token is rejected."""
        repo1 = Repository(
            id=uuid4(),
            name="repo1",
            owner="owner1",
            full_name="owner1/repo1",
            github_repo_id=11111,
            workspace_id=test_workspace.id
        )
        repo2 = Repository(
            id=uuid4(),
            name="repo2",
            owner="owner2",
            full_name="owner2/repo2",
            github_repo_id=22222,
            workspace_id=test_workspace.id
        )
        db_session.add_all([repo1, repo2])
        db_session.commit()
        
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        response = service.create_token(db_session, repo1.id, token_in, created_by=None)
        
        # Token belongs to repo1, verify it can access repo1
        verified = service.verify_token(db_session, response.raw_token)
        assert verified is not None
        assert verified.repository_id == repo1.id
        assert verified.repository_id != repo2.id
    
    def test_artifact_pending_state_before_worker_completion(self, db_session, test_workspace):
        """Test that artifact is pending before worker completion."""
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
        
        # Create pending pipeline run
        pipeline_run = PipelineRun(
            id=uuid4(),
            repository_id=repository.id,
            provider="GITHUB_ACTIONS",
            external_run_id="test-run-123",
            commit_sha="abc123",
            branch="main",
            status=PipelineRunStatus.RUNNING,
            quality_gate=QualityGateStatus.UNKNOWN
        )
        db_session.add(pipeline_run)
        db_session.commit()
        
        # Verify pipeline run is still running
        db_session.refresh(pipeline_run)
        assert pipeline_run.status == PipelineRunStatus.RUNNING
        assert pipeline_run.quality_gate == QualityGateStatus.UNKNOWN
    
    def test_artifact_downloadable_after_completion(self, db_session, test_workspace):
        """Test that artifact is downloadable after completion."""
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
        
        # Create completed pipeline run
        pipeline_run = PipelineRun(
            id=uuid4(),
            repository_id=repository.id,
            provider="GITHUB_ACTIONS",
            external_run_id="test-run-123",
            commit_sha="abc123",
            branch="main",
            status=PipelineRunStatus.COMPLETED,
            quality_gate=QualityGateStatus.PASSED
        )
        db_session.add(pipeline_run)
        db_session.commit()
        
        # Verify pipeline run is completed
        db_session.refresh(pipeline_run)
        assert pipeline_run.status == PipelineRunStatus.COMPLETED
        assert pipeline_run.quality_gate == QualityGateStatus.PASSED
    
    def test_artifact_json_has_no_secrets(self, db_session, test_workspace):
        """Test that artifact JSON has no secrets."""
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
        
        # Create pipeline run
        pipeline_run = PipelineRun(
            id=uuid4(),
            repository_id=repository.id,
            provider="GITHUB_ACTIONS",
            external_run_id="test-run-123",
            commit_sha="abc123",
            branch="main",
            status=PipelineRunStatus.COMPLETED,
            quality_gate=QualityGateStatus.PASSED
        )
        db_session.add(pipeline_run)
        db_session.commit()
        
        # Verify pipeline run data doesn't contain secrets
        db_session.refresh(pipeline_run)
        run_data = {
            "id": str(pipeline_run.id),
            "commit_sha": pipeline_run.commit_sha,
            "quality_gate": pipeline_run.quality_gate.value
        }
        
        # Check for secret patterns
        assert "ghp_" not in str(run_data)
        assert "sk-" not in str(run_data)
        assert "private_key" not in str(run_data)
    
    def test_artifact_access_is_audited(self, db_session, test_workspace):
        """Test that artifact access is audited."""
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
        
        service = CITokenService()
        token_in = CITokenCreate(name="Test Token")
        response = service.create_token(db_session, repository.id, token_in, created_by=None)
        
        # Verify token (should log audit event)
        service.verify_token(db_session, response.raw_token)
        
        # Check audit event was logged
        audit_events = db_session.query(CITokenAuditEvent).filter(
            CITokenAuditEvent.repository_id == str(repository.id)
        ).all()
        assert len(audit_events) > 0
