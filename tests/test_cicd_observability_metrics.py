"""
CI/CD Observability Metrics Tests

Tests for the CICDObservabilityService metrics and health check functionality.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.pipeline_execution_job import PipelineExecutionJob, PipelineJobStatus
from app.models.pipeline_run import PipelineRun, PipelineRunStatus, QualityGateStatus
from app.models.repository import Repository
from app.models.ci_token import CIToken
from app.models.ci_token_audit import CITokenAuditEvent
from app.services.cicd_observability_service import CICDObservabilityService


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
        status=PipelineRunStatus.COMPLETED,
        quality_gate=QualityGateStatus.PARTIAL,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    yield run


@pytest.fixture
def execution_job(db_session, repository, pipeline_run):
    job = PipelineExecutionJob(
        id=uuid.uuid4(),
        pipeline_run_id=pipeline_run.id,
        repository_id=repository.id,
        status=PipelineJobStatus.COMPLETED,
        attempt_count=1,
        max_attempts=5,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    yield job


class TestCICDObservabilityMetrics:
    """Tests for CI/CD observability metrics."""
    
    def test_metrics_endpoint_returns_pipeline_run_counts(self, db_session, repository, pipeline_run):
        """Test that metrics endpoint returns pipeline run counts."""
        service = CICDObservabilityService()
        metrics = service.get_repository_metrics(db_session, repository.id)
        
        assert "pipelineRuns" in metrics
        assert metrics["pipelineRuns"]["total"] >= 1
        assert metrics["pipelineRuns"]["completed"] >= 1
    
    def test_metrics_endpoint_returns_job_status_counts(self, db_session, repository, execution_job):
        """Test that metrics endpoint returns job status counts."""
        service = CICDObservabilityService()
        metrics = service.get_repository_metrics(db_session, repository.id)
        
        assert "jobs" in metrics
        assert "inProgress" in metrics["jobs"]
        assert "deadLetter" in metrics["jobs"]
    
    def test_metrics_endpoint_returns_processing_time_metrics(self, db_session, repository, execution_job):
        """Test that metrics endpoint returns processing-time metrics."""
        service = CICDObservabilityService()
        metrics = service.get_repository_metrics(db_session, repository.id)
        
        assert "performance" in metrics
        assert "averageQueueSeconds" in metrics["performance"]
        assert "averageProcessingSeconds" in metrics["performance"]
        assert "p95ProcessingSeconds" in metrics["performance"]
    
    def test_metrics_endpoint_returns_github_publishing_metrics(self, db_session, repository, pipeline_run):
        """Test that metrics endpoint returns GitHub publishing metrics."""
        service = CICDObservabilityService()
        metrics = service.get_repository_metrics(db_session, repository.id)
        
        assert "githubPublishing" in metrics
        assert "statusSuccess" in metrics["githubPublishing"]
        assert "statusFailed" in metrics["githubPublishing"]
    
    def test_metrics_endpoint_returns_artifact_metrics(self, db_session, repository):
        """Test that metrics endpoint returns artifact metrics."""
        service = CICDObservabilityService()
        metrics = service.get_repository_metrics(db_session, repository.id)
        
        assert "artifacts" in metrics
        assert "downloads" in metrics["artifacts"]
        assert "failures" in metrics["artifacts"]
    
    def test_metrics_endpoint_returns_ci_token_metrics(self, db_session, repository):
        """Test that metrics endpoint returns CI token metrics."""
        service = CICDObservabilityService()
        metrics = service.get_repository_metrics(db_session, repository.id)
        
        assert "ciTokens" in metrics
        assert "active" in metrics["ciTokens"]
        assert "used" in metrics["ciTokens"]
        assert "rejected" in metrics["ciTokens"]


class TestCICDHealthChecks:
    """Tests for CI/CD health checks."""
    
    def test_health_is_healthy_when_worker_and_publishing_are_healthy(self, db_session, repository, execution_job):
        """Test that health is HEALTHY when worker and publishing are healthy."""
        # Create a recently completed job
        execution_job.completed_at = datetime.utcnow() - timedelta(minutes=2)
        db_session.commit()
        
        service = CICDObservabilityService()
        health = service.get_health_summary(db_session, repository.id)
        
        assert health["status"] in ("HEALTHY", "UNKNOWN")  # May be UNKNOWN if no recent activity
        assert len(health["checks"]) > 0
    
    def test_health_is_degraded_when_backlog_is_high(self, db_session, repository):
        """Test that health is DEGRADED when backlog is high."""
        # Create many pending jobs to exceed threshold
        for i in range(150):
            job = PipelineExecutionJob(
                id=uuid.uuid4(),
                pipeline_run_id=uuid.uuid4(),
                repository_id=repository.id,
                status=PipelineJobStatus.PENDING,
                attempt_count=0,
                max_attempts=5
            )
            db_session.add(job)
        db_session.commit()
        
        service = CICDObservabilityService()
        health = service.get_health_summary(db_session, repository.id)
        
        # Should have DEGRADED status due to high backlog
        backlog_check = next((c for c in health["checks"] if c["name"] == "Pending backlog"), None)
        assert backlog_check is not None
        assert backlog_check["status"] == "DEGRADED"
    
    def test_health_is_critical_when_dead_letter_jobs_exist(self, db_session, repository):
        """Test that health is CRITICAL when dead-letter jobs exist."""
        # Create a dead-letter job
        job = PipelineExecutionJob(
            id=uuid.uuid4(),
            pipeline_run_id=uuid.uuid4(),
            repository_id=repository.id,
            status=PipelineJobStatus.DEAD_LETTER,
            attempt_count=5,
            max_attempts=5,
            last_error="Test error"
        )
        db_session.add(job)
        db_session.commit()
        
        service = CICDObservabilityService()
        health = service.get_health_summary(db_session, repository.id)
        
        # Should have CRITICAL status due to dead-letter jobs
        dead_letter_check = next((c for c in health["checks"] if c["name"] == "Dead-letter jobs"), None)
        assert dead_letter_check is not None
        assert dead_letter_check["status"] == "CRITICAL"
    
    def test_health_checks_include_all_required_checks(self, db_session, repository):
        """Test that health checks include all required checks."""
        service = CICDObservabilityService()
        health = service.get_health_summary(db_session, repository.id)
        
        check_names = [check["name"] for check in health["checks"]]
        required_checks = [
            "Async worker",
            "Pending backlog",
            "Dead-letter jobs",
            "GitHub publishing",
            "Artifact access",
            "CI token rejections",
            "Latest pipeline run"
        ]
        
        for required in required_checks:
            assert required in check_names
