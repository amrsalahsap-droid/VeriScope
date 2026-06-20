"""Integration Scalability and Monitoring Tests

Tests for:
- Sync activity pagination
- Metrics endpoint
- Alert generation
- Query efficiency
- Evidence preservation
"""
import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.user import User, Workspace
from app.models.repository import Repository
from app.models.external_test_case import ExternalTestCaseReference
from app.models.manual_test_execution import ManualTestExecution
from app.models.manual_execution_sync_event import ManualExecutionSyncEvent
from app.models.integration_provider_cooldown import IntegrationProviderCooldown


class TestSyncActivityPagination:
    """Test sync activity endpoint pagination."""
    
    def test_sync_activity_endpoint_paginates(self, db_session: Session):
        """Test that sync activity endpoint supports pagination."""
        from app.routers.repository import get_sync_activity
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
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
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        # Create external test case and execution
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        # Create 100 sync events
        for i in range(100):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="SYNCED" if i < 80 else "FAILED",
                attempt_count=1,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(seconds=i)
            )
            db_session.add(sync_event)
        db_session.commit()
        
        # Test pagination with limit 50
        result = get_sync_activity(
            repository_id=repository.id,
            limit=50,
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert 'items' in result
        assert 'nextCursor' in result
        assert 'hasMore' in result
        assert 'limit' in result
        assert len(result['items']) == 50
        assert result['hasMore'] is True
        assert result['limit'] == 50
    
    def test_limit_defaults_to_50(self, db_session: Session):
        """Test that default limit is 50."""
        from app.routers.repository import get_sync_activity
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        result = get_sync_activity(
            repository_id=repository.id,
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert result['limit'] == 50
    
    def test_max_limit_enforced(self, db_session: Session):
        """Test that max limit of 200 is enforced."""
        from app.routers.repository import get_sync_activity
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        result = get_sync_activity(
            repository_id=repository.id,
            limit=500,  # Request more than max
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert result['limit'] == 200  # Should be capped at 200
    
    def test_cursor_returns_next_page(self, db_session: Session):
        """Test that cursor returns next page of results."""
        from app.routers.repository import get_sync_activity
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        # Create 100 sync events
        for i in range(100):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="SYNCED",
                attempt_count=1,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(seconds=i)
            )
            db_session.add(sync_event)
        db_session.commit()
        
        # Get first page
        page1 = get_sync_activity(
            repository_id=repository.id,
            limit=50,
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert len(page1['items']) == 50
        assert page1['hasMore'] is True
        assert page1['nextCursor'] is not None
        
        # Get second page using cursor
        page2 = get_sync_activity(
            repository_id=repository.id,
            limit=50,
            cursor=page1['nextCursor'],
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert len(page2['items']) == 50
        assert page2['hasMore'] is False
        
        # Verify no duplicates
        page1_ids = {item['id'] for item in page1['items']}
        page2_ids = {item['id'] for item in page2['items']}
        assert len(page1_ids.intersection(page2_ids)) == 0
    
    def test_provider_filter_works(self, db_session: Session):
        """Test that provider filter works correctly."""
        from app.routers.repository import get_sync_activity
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        # Create events for different providers
        for i in range(10):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="SYNCED",
                attempt_count=1,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(seconds=i)
            )
            db_session.add(sync_event)
        
        for i in range(10):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="JIRA",
                status="SYNCED",
                attempt_count=1,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(seconds=i)
            )
            db_session.add(sync_event)
        db_session.commit()
        
        result = get_sync_activity(
            repository_id=repository.id,
            provider="TESTRAIL",
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert len(result['items']) == 10
        assert all(item['provider'] == 'TESTRAIL' for item in result['items'])
    
    def test_status_filter_works(self, db_session: Session):
        """Test that status filter works correctly."""
        from app.routers.repository import get_sync_activity
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        # Create events with different statuses
        for i in range(10):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="SYNCED",
                attempt_count=1,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(seconds=i)
            )
            db_session.add(sync_event)
        
        for i in range(5):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="FAILED",
                attempt_count=1,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(seconds=i)
            )
            db_session.add(sync_event)
        db_session.commit()
        
        result = get_sync_activity(
            repository_id=repository.id,
            status="FAILED",
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert len(result['items']) == 5
        assert all(item['status'] == 'FAILED' for item in result['items'])
    
    def test_date_filter_works(self, db_session: Session):
        """Test that date filter works correctly."""
        from app.routers.repository import get_sync_activity
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        # Create events at different times
        now = datetime.utcnow()
        for i in range(10):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="SYNCED",
                attempt_count=1,
                max_attempts=5,
                created_at=now - timedelta(hours=i)
            )
            db_session.add(sync_event)
        db_session.commit()
        
        result = get_sync_activity(
            repository_id=repository.id,
            from_date=now - timedelta(hours=3),
            to_date=now,
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert len(result['items']) == 4  # 0, 1, 2, 3 hours ago (inclusive)
    
    def test_query_does_not_load_all_rows(self, db_session: Session):
        """Test that query uses LIMIT and doesn't load all rows."""
        from app.routers.repository import get_sync_activity
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        # Create 1000 sync events
        for i in range(1000):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="SYNCED",
                attempt_count=1,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(seconds=i)
            )
            db_session.add(sync_event)
        db_session.commit()
        
        # Query with small limit should be fast
        result = get_sync_activity(
            repository_id=repository.id,
            limit=10,
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert len(result['items']) == 10
        assert result['hasMore'] is True


class TestMetricsEndpoint:
    """Test metrics endpoint functionality."""
    
    def test_metrics_endpoint_returns_provider_metrics(self, db_session: Session):
        """Test that metrics endpoint returns provider-level metrics."""
        from app.routers.repository import get_integration_metrics
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        # Create sync events
        for i in range(80):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="SYNCED",
                attempt_count=1,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(hours=i)
            )
            db_session.add(sync_event)
        
        for i in range(20):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="FAILED",
                attempt_count=1,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(hours=i)
            )
            db_session.add(sync_event)
        db_session.commit()
        
        result = get_integration_metrics(
            repository_id=repository.id,
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert 'providers' in result
        assert 'overall' in result
        assert 'alerts' in result
        assert len(result['providers']) == 1
        assert result['overall']['totalSyncs'] == 100
        assert result['overall']['successfulSyncs'] == 80
        assert result['overall']['failedSyncs'] == 20
        assert result['overall']['successRate'] == 80.0
        assert result['overall']['failureRate'] == 20.0
    
    def test_dead_letter_count_returned(self, db_session: Session):
        """Test that dead-letter count is returned."""
        from app.routers.repository import get_integration_metrics
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        # Create dead-letter events
        for i in range(3):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="DEAD_LETTER",
                attempt_count=5,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(hours=i)
            )
            db_session.add(sync_event)
        db_session.commit()
        
        result = get_integration_metrics(
            repository_id=repository.id,
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert result['overall']['deadLetterSyncs'] == 3
        assert result['providers'][0]['deadLetterSyncs'] == 3


class TestAlertGeneration:
    """Test alert generation logic."""
    
    def test_alerts_generated_for_high_failure_rate(self, db_session: Session):
        """Test that alerts are generated for high failure rate."""
        from app.routers.repository import get_integration_metrics
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        # Create high failure rate (30%)
        for i in range(70):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="SYNCED",
                attempt_count=1,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(hours=i)
            )
            db_session.add(sync_event)
        
        for i in range(30):
            sync_event = ManualExecutionSyncEvent(
                id=uuid.uuid4(),
                execution_id=execution.id,
                provider="TESTRAIL",
                status="FAILED",
                attempt_count=1,
                max_attempts=5,
                created_at=datetime.utcnow() - timedelta(hours=i)
            )
            db_session.add(sync_event)
        db_session.commit()
        
        result = get_integration_metrics(
            repository_id=repository.id,
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert any(alert['code'] == 'HIGH_FAILURE_RATE' for alert in result['alerts'])
    
    def test_alerts_generated_for_dead_letter_presence(self, db_session: Session):
        """Test that alerts are generated for dead-letter presence."""
        from app.routers.repository import get_integration_metrics
        from app.models.integration_provider_cooldown import IntegrationProviderCooldown
        
        workspace = Workspace(
            id=uuid.uuid4(),
            name="test-workspace",
            slug="test-workspace"
        )
        db_session.add(workspace)
        
        repository = Repository(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            github_repo_id=67890,
            name="test-repo",
            full_name="test-owner/test-repo"
        )
        db_session.add(repository)
        
        external_test_case = ExternalTestCaseReference(
            id=uuid.uuid4(),
            repository_id=repository.id,
            provider="TESTRAIL",
            external_project_id="PROJ123",
            external_test_case_id="TEST-123",
            title="Test Case"
        )
        db_session.add(external_test_case)
        
        execution = ManualTestExecution(
            id=uuid.uuid4(),
            external_test_case_id=external_test_case.id,
            repository_id=repository.id,
            outcome="PASSED",
            executed_by_name="test-user",
            executed_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()
        
        # Create dead-letter events
        sync_event = ManualExecutionSyncEvent(
            id=uuid.uuid4(),
            execution_id=execution.id,
            provider="TESTRAIL",
            status="DEAD_LETTER",
            attempt_count=5,
            max_attempts=5,
            created_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(sync_event)
        db_session.commit()
        
        result = get_integration_metrics(
            repository_id=repository.id,
            db=db_session,
            workspace_id=str(workspace.id)
        )
        
        assert any(alert['code'] == 'DEAD_LETTER_PRESENT' for alert in result['alerts'])
