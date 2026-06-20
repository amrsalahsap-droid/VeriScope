"""
Pipeline Dead-Letter Operations Tests

Tests for dead-letter job management operations (list, retry, cancel).
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.pipeline_execution_job import PipelineExecutionJob, PipelineJobStatus
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.repository import Repository
from app.models.ci_token_audit import CITokenAuditEvent
from app.api.models.user import User


@pytest.fixture
def db_session():
    """Create a transaction-isolated database session for testing."""
    from app.db.session import engine
    from sqlalchemy.orm import sessionmaker
    
    connection = engine.connect()
    transaction = connection.begin()
    
    TestSessionLocal = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    db = TestSessionLocal()
    
    nested = connection.begin_nested()
    
    @event.listens_for(db, "after_transaction_end")
    def restart_savepoint(session, transaction_):
        nonlocal nested
        if nested.is_active:
            return
        nested = connection.begin_nested()
    
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def repository(db_session):
    repo = Repository(
        id=uuid.uuid4(),
        name="test-repo",
        owner="test-owner",
        provider="github",
        external_id="12345"
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    yield repo


@pytest.fixture
def pipeline_run(db_session, repository):
    run = PipelineRun(
        id=uuid.uuid4(),
        repository_id=repository.id,
        provider="GITHUB_ACTIONS",
        external_run_id="gh-run-123",
        commit_sha="abc123",
        status=PipelineRunStatus.RUNNING
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    yield run


@pytest.fixture
def dead_letter_job(db_session, repository, pipeline_run):
    job = PipelineExecutionJob(
        id=uuid.uuid4(),
        pipeline_run_id=pipeline_run.id,
        repository_id=repository.id,
        status=PipelineJobStatus.DEAD_LETTER,
        attempt_count=5,
        max_attempts=5,
        last_error="Test error",
        last_error_type="TestError"
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    yield job


@pytest.fixture
def failed_job(db_session, repository, pipeline_run):
    job = PipelineExecutionJob(
        id=uuid.uuid4(),
        pipeline_run_id=pipeline_run.id,
        repository_id=repository.id,
        status=PipelineJobStatus.FAILED,
        attempt_count=3,
        max_attempts=5,
        last_error="Test error"
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    yield job


@pytest.fixture
def mock_user():
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User"
    )
    return user


class TestDeadLetterJobOperations:
    """Tests for dead-letter job operations."""
    
    def test_list_dead_letter_jobs_returns_only_dead_letter_status(self, db_session, repository, dead_letter_job, failed_job):
        """Test that list endpoint returns only jobs in DEAD_LETTER status."""
        from app.routers.cicd_observability import get_dead_letter_jobs
        
        jobs = get_dead_letter_jobs(repository.id, db_session, mock_user())
        
        # Should only return dead-letter job, not failed job
        job_ids = [job["id"] for job in jobs]
        assert str(dead_letter_job.id) in job_ids
        assert str(failed_job.id) not in job_ids
    
    def test_list_dead_letter_jobs_includes_error_details(self, db_session, repository, dead_letter_job):
        """Test that list endpoint includes error details."""
        from app.routers.cicd_observability import get_dead_letter_jobs
        
        jobs = get_dead_letter_jobs(repository.id, db_session, mock_user())
        
        assert len(jobs) > 0
        assert jobs[0]["last_error"] == "Test error"
        assert jobs[0]["last_error_type"] == "TestError"
        assert jobs[0]["attempt_count"] == 5
    
    def test_retry_dead_letter_job_moves_to_retry_pending(self, db_session, repository, dead_letter_job, mock_user):
        """Test that retry moves dead-letter job to RETRY_PENDING."""
        from app.routers.cicd_observability import retry_dead_letter_job
        
        result = retry_dead_letter_job(repository.id, dead_letter_job.id, db_session, mock_user())
        
        assert result["status"] == "RETRY_PENDING"
        assert result["message"] == "Job moved to RETRY_PENDING"
        
        # Verify job status in database
        db_session.refresh(dead_letter_job)
        assert dead_letter_job.status == PipelineJobStatus.RETRY_PENDING
        assert dead_letter_job.next_attempt_at is not None
    
    def test_retry_failed_job_moves_to_retry_pending(self, db_session, repository, failed_job, mock_user):
        """Test that retry moves failed job to RETRY_PENDING."""
        from app.routers.cicd_observability import retry_dead_letter_job
        
        result = retry_dead_letter_job(repository.id, failed_job.id, db_session, mock_user())
        
        assert result["status"] == "RETRY_PENDING"
        
        # Verify job status in database
        db_session.refresh(failed_job)
        assert failed_job.status == PipelineJobStatus.RETRY_PENDING
    
    def test_retry_creates_audit_event(self, db_session, repository, dead_letter_job, mock_user):
        """Test that retry creates an audit event."""
        from app.routers.cicd_observability import retry_dead_letter_job
        
        retry_dead_letter_job(repository.id, dead_letter_job.id, db_session, mock_user())
        
        # Verify audit event was created
        audit_events = db_session.query(CITokenAuditEvent).filter(
            CITokenAuditEvent.repository_id == repository.id,
            CITokenAuditEvent.event_type == "PIPELINE_JOB_RETRIED"
        ).all()
        
        assert len(audit_events) > 0
        assert audit_events[0].actor_id == str(mock_user().id)
        assert str(dead_letter_job.id) in audit_events[0].reason
    
    def test_retry_nonexistent_job_returns_404(self, db_session, repository, mock_user):
        """Test that retry of nonexistent job returns 404."""
        from fastapi import HTTPException
        from app.routers.cicd_observability import retry_dead_letter_job
        
        with pytest.raises(HTTPException) as exc_info:
            retry_dead_letter_job(repository.id, uuid.uuid4(), db_session, mock_user())
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()
    
    def test_retry_non_retryable_job_returns_400(self, db_session, repository, pipeline_run, mock_user):
        """Test that retry of non-retryable job returns 400."""
        from fastapi import HTTPException
        from app.routers.cicd_observability import retry_dead_letter_job
        
        # Create a completed job (not retryable)
        completed_job = PipelineExecutionJob(
            id=uuid.uuid4(),
            pipeline_run_id=pipeline_run.id,
            repository_id=repository.id,
            status=PipelineJobStatus.COMPLETED,
            attempt_count=1,
            max_attempts=5
        )
        db_session.add(completed_job)
        db_session.commit()
        
        with pytest.raises(HTTPException) as exc_info:
            retry_dead_letter_job(repository.id, completed_job.id, db_session, mock_user())
        
        assert exc_info.value.status_code == 400
        assert "not in a retryable state" in exc_info.value.detail.lower()
    
    def test_cancel_job_moves_to_cancelled(self, db_session, repository, dead_letter_job, mock_user):
        """Test that cancel moves job to CANCELLED."""
        from app.routers.cicd_observability import cancel_pipeline_job
        
        result = cancel_pipeline_job(repository.id, dead_letter_job.id, db_session, mock_user())
        
        assert result["status"] == "CANCELLED"
        assert result["message"] == "Job cancelled"
        
        # Verify job status in database
        db_session.refresh(dead_letter_job)
        assert dead_letter_job.status == PipelineJobStatus.CANCELLED
        assert dead_letter_job.completed_at is not None
    
    def test_cancel_creates_audit_event(self, db_session, repository, dead_letter_job, mock_user):
        """Test that cancel creates an audit event."""
        from app.routers.cicd_observability import cancel_pipeline_job
        
        cancel_pipeline_job(repository.id, dead_letter_job.id, db_session, mock_user())
        
        # Verify audit event was created
        audit_events = db_session.query(CITokenAuditEvent).filter(
            CITokenAuditEvent.repository_id == repository.id,
            CITokenAuditEvent.event_type == "PIPELINE_JOB_CANCELLED"
        ).all()
        
        assert len(audit_events) > 0
        assert audit_events[0].actor_id == str(mock_user().id)
        assert str(dead_letter_job.id) in audit_events[0].reason
    
    def test_cancel_nonexistent_job_returns_404(self, db_session, repository, mock_user):
        """Test that cancel of nonexistent job returns 404."""
        from fastapi import HTTPException
        from app.routers.cicd_observability import cancel_pipeline_job
        
        with pytest.raises(HTTPException) as exc_info:
            cancel_pipeline_job(repository.id, uuid.uuid4(), db_session, mock_user())
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()
    
    def test_cancel_completed_job_returns_400(self, db_session, repository, pipeline_run, mock_user):
        """Test that cancel of completed job returns 400."""
        from fastapi import HTTPException
        from app.routers.cicd_observability import cancel_pipeline_job
        
        # Create a completed job
        completed_job = PipelineExecutionJob(
            id=uuid.uuid4(),
            pipeline_run_id=pipeline_run.id,
            repository_id=repository.id,
            status=PipelineJobStatus.COMPLETED,
            attempt_count=1,
            max_attempts=5
        )
        db_session.add(completed_job)
        db_session.commit()
        
        with pytest.raises(HTTPException) as exc_info:
            cancel_pipeline_job(repository.id, completed_job.id, db_session, mock_user())
        
        assert exc_info.value.status_code == 400
        assert "cannot cancel completed job" in exc_info.value.detail.lower()
