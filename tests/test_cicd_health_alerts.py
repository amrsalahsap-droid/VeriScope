"""
CI/CD Health Alerts Tests

Tests for the CICDAlertService alert creation and management functionality.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.pipeline_execution_job import PipelineExecutionJob, PipelineJobStatus
from app.models.pipeline_run import PipelineRun, PipelineRunStatus, QualityGateStatus
from app.models.repository import Repository
from app.models.cicd_alert import CICDAlert, AlertSeverity, AlertType
from app.services.cicd_alert_service import CICDAlertService


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


class TestCICDAlerts:
    """Tests for CI/CD alert creation and management."""
    
    def test_alert_created_for_high_backlog(self, db_session, repository):
        """Test that alert is created for high backlog."""
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
        
        service = CICDAlertService()
        new_alerts = service.evaluate_and_create_alerts(db_session, repository.id)
        
        # Should create an alert for high backlog
        backlog_alerts = [a for a in new_alerts if a.alert_type == AlertType.PIPELINE_BACKLOG_HIGH]
        assert len(backlog_alerts) > 0
        assert backlog_alerts[0].severity == AlertSeverity.WARNING
    
    def test_alert_created_for_dead_letter_jobs(self, db_session, repository):
        """Test that alert is created for dead-letter jobs."""
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
        
        service = CICDAlertService()
        new_alerts = service.evaluate_and_create_alerts(db_session, repository.id)
        
        # Should create an alert for dead-letter jobs
        dead_letter_alerts = [a for a in new_alerts if a.alert_type == AlertType.PIPELINE_DEAD_LETTER_PRESENT]
        assert len(dead_letter_alerts) > 0
        assert dead_letter_alerts[0].severity == AlertSeverity.CRITICAL
    
    def test_alert_created_for_github_publishing_failure_spike(self, db_session, repository):
        """Test that alert is created for GitHub publishing failure spike."""
        # Create many failed pipeline runs
        for i in range(20):
            run = PipelineRun(
                id=uuid.uuid4(),
                repository_id=repository.id,
                provider="GITHUB_ACTIONS",
                external_run_id=f"gh-run-{i}",
                commit_sha="abc123",
                status=PipelineRunStatus.FAILED,
                quality_gate=QualityGateStatus.FAILED
            )
            db_session.add(run)
        db_session.commit()
        
        service = CICDAlertService()
        new_alerts = service.evaluate_and_create_alerts(db_session, repository.id)
        
        # Should create an alert for publishing failures
        publishing_alerts = [a for a in new_alerts if a.alert_type == AlertType.GITHUB_PUBLISHING_FAILURE_SPIKE]
        assert len(publishing_alerts) > 0
    
    def test_alert_not_duplicated_for_same_issue(self, db_session, repository):
        """Test that alert is not duplicated for same issue."""
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
        
        service = CICDAlertService()
        
        # First evaluation should create alert
        new_alerts_1 = service.evaluate_and_create_alerts(db_session, repository.id)
        assert len(new_alerts_1) > 0
        
        # Second evaluation should not create duplicate alert
        new_alerts_2 = service.evaluate_and_create_alerts(db_session, repository.id)
        dead_letter_alerts_2 = [a for a in new_alerts_2 if a.alert_type == AlertType.PIPELINE_DEAD_LETTER_PRESENT]
        assert len(dead_letter_alerts_2) == 0
    
    def test_get_active_alerts_returns_unresolved_alerts(self, db_session, repository):
        """Test that get_active_alerts returns unresolved alerts."""
        service = CICDAlertService()
        
        # Create an alert
        alert = service.create_alert(
            db=db_session,
            repository_id=repository.id,
            alert_type=AlertType.PIPELINE_BACKLOG_HIGH,
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Test message"
        )
        
        # Get active alerts
        active_alerts = service.get_active_alerts(db_session, repository.id)
        
        assert len(active_alerts) > 0
        assert active_alerts[0].id == alert.id
        assert active_alerts[0].resolved_at is None
    
    def test_resolve_alert_marks_as_resolved(self, db_session, repository):
        """Test that resolve_alert marks alert as resolved."""
        service = CICDAlertService()
        
        # Create an alert
        alert = service.create_alert(
            db=db_session,
            repository_id=repository.id,
            alert_type=AlertType.PIPELINE_BACKLOG_HIGH,
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Test message"
        )
        
        # Resolve the alert
        resolved_alert = service.resolve_alert(db_session, alert.id)
        
        assert resolved_alert is not None
        assert resolved_alert.resolved_at is not None
        assert resolved_alert.is_resolved()
    
    def test_alert_includes_recommended_action(self, db_session, repository):
        """Test that alert includes recommended action."""
        service = CICDAlertService()
        
        # Create an alert with recommended action
        alert = service.create_alert(
            db=db_session,
            repository_id=repository.id,
            alert_type=AlertType.PIPELINE_BACKLOG_HIGH,
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Test message",
            recommended_action="Scale up worker capacity"
        )
        
        assert alert.recommended_action == "Scale up worker capacity"
    
    def test_alert_can_link_to_pipeline_run(self, db_session, repository):
        """Test that alert can link to pipeline run."""
        service = CICDAlertService()
        
        pipeline_run_id = uuid.uuid4()
        
        # Create an alert linked to pipeline run
        alert = service.create_alert(
            db=db_session,
            repository_id=repository.id,
            alert_type=AlertType.PIPELINE_BACKLOG_HIGH,
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Test message",
            pipeline_run_id=pipeline_run_id
        )
        
        assert alert.pipeline_run_id == pipeline_run_id
    
    def test_alert_can_link_to_pipeline_job(self, db_session, repository):
        """Test that alert can link to pipeline job."""
        service = CICDAlertService()
        
        pipeline_job_id = uuid.uuid4()
        
        # Create an alert linked to pipeline job
        alert = service.create_alert(
            db=db_session,
            repository_id=repository.id,
            alert_type=AlertType.PIPELINE_BACKLOG_HIGH,
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Test message",
            pipeline_job_id=pipeline_job_id
        )
        
        assert alert.pipeline_job_id == pipeline_job_id
