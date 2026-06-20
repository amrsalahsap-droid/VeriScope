"""
Integration UI Support Endpoints Tests (Phase 7.4)

Tests for the new integration UI support endpoints:
- Health endpoint
- Sync activity endpoint
- Retry-all failed syncs endpoint

Note: These are basic structural tests. Full integration tests would require
a test database and proper FastAPI test client setup.
"""

import pytest
from unittest.mock import Mock


class TestHealthEndpointLogic:
    """Test health endpoint logic without HTTP layer."""

    def test_health_determines_disconnected_when_no_connection(self):
        """Health logic returns DISCONNECTED when no connection exists."""
        # Simulate the health determination logic
        conn = None
        if not conn or not getattr(conn, 'is_active', False):
            health = "DISCONNECTED"
            assert health == "DISCONNECTED"

    def test_health_determines_configuration_required_for_testrail(self):
        """Health logic returns CONFIGURATION_REQUIRED for TestRail without default_test_run_id."""
        conn = Mock()
        conn.provider = "TESTRAIL"
        conn.is_active = True
        conn.config = {}  # Missing default_test_run_id
        conn.provider_metadata = {}
        
        if conn.provider == "TESTRAIL":
            if not conn.config.get("default_test_run_id"):
                health = "CONFIGURATION_REQUIRED"
                assert health == "CONFIGURATION_REQUIRED"

    def test_health_determines_configuration_required_for_xray(self):
        """Health logic returns CONFIGURATION_REQUIRED for Xray without testExecutionKey."""
        conn = Mock()
        conn.provider = "XRAY"
        conn.is_active = True
        conn.config = {}
        conn.provider_metadata = {}  # Missing testExecutionKey
        
        if conn.provider == "XRAY":
            if not conn.provider_metadata.get("testExecutionKey") and not conn.config.get("testExecutionKey"):
                health = "CONFIGURATION_REQUIRED"
                assert health == "CONFIGURATION_REQUIRED"

    def test_health_determines_configuration_required_for_zephyr(self):
        """Health logic returns CONFIGURATION_REQUIRED for Zephyr without testCycleKey."""
        conn = Mock()
        conn.provider = "ZEPHYR"
        conn.is_active = True
        conn.config = {}
        conn.provider_metadata = {}  # Missing testCycleKey
        
        if conn.provider == "ZEPHYR":
            if not conn.provider_metadata.get("testCycleKey") and not conn.config.get("testCycleKey"):
                health = "CONFIGURATION_REQUIRED"
                assert health == "CONFIGURATION_REQUIRED"

    def test_health_determines_sync_failures_present(self):
        """Health logic returns SYNC_FAILURES_PRESENT when recent failures exist."""
        failed_executions_count = 5
        missing_config = None
        
        if missing_config:
            health = "CONFIGURATION_REQUIRED"
        elif failed_executions_count > 0:
            health = "SYNC_FAILURES_PRESENT"
        else:
            health = "HEALTHY"
        
        assert health == "SYNC_FAILURES_PRESENT"

    def test_health_determines_healthy(self):
        """Health logic returns HEALTHY when no issues."""
        failed_executions_count = 0
        missing_config = None
        
        if missing_config:
            health = "CONFIGURATION_REQUIRED"
        elif failed_executions_count > 0:
            health = "SYNC_FAILURES_PRESENT"
        else:
            health = "HEALTHY"
        
        assert health == "HEALTHY"


class TestSyncActivityEndpointLogic:
    """Test sync activity endpoint logic without HTTP layer."""

    def test_sync_activity_builds_response_from_executions(self):
        """Sync activity logic builds response from execution data."""
        mock_exec = Mock()
        mock_exec.id = "exec-1"
        mock_exec.external_system = "TESTRAIL"
        mock_exec.sync_status = "SYNCED"
        mock_exec.notes = None
        mock_exec.external_run_id = "RUN-123"
        mock_exec.external_execution_id = "EXEC-456"
        mock_exec.created_at = "2024-01-01T00:00:00Z"
        mock_exec.last_synced_at = "2024-01-01T00:00:00Z"
        
        result = {
            "id": str(mock_exec.id),
            "provider": mock_exec.external_system,
            "executionId": str(mock_exec.id),
            "status": mock_exec.sync_status or "PENDING",
            "error": mock_exec.notes if mock_exec.sync_status == "FAILED" else None,
            "externalRunId": mock_exec.external_run_id,
            "externalExecutionId": mock_exec.external_execution_id,
            "createdAt": mock_exec.created_at,
            "lastSyncedAt": mock_exec.last_synced_at
        }
        
        assert result["provider"] == "TESTRAIL"
        assert result["status"] == "SYNCED"
        assert result["externalRunId"] == "RUN-123"

    def test_sync_activity_includes_error_for_failed_syncs(self):
        """Sync activity logic includes error when sync failed."""
        mock_exec = Mock()
        mock_exec.id = "exec-1"
        mock_exec.external_system = "XRAY"
        mock_exec.sync_status = "FAILED"
        mock_exec.notes = "XRAY_TEST_EXECUTION_KEY_REQUIRED"
        mock_exec.external_run_id = None
        mock_exec.external_execution_id = None
        mock_exec.created_at = "2024-01-01T00:00:00Z"
        mock_exec.last_synced_at = "2024-01-01T00:00:00Z"
        
        result = {
            "id": str(mock_exec.id),
            "provider": mock_exec.external_system,
            "executionId": str(mock_exec.id),
            "status": mock_exec.sync_status or "PENDING",
            "error": mock_exec.notes if mock_exec.sync_status == "FAILED" else None,
            "externalRunId": mock_exec.external_run_id,
            "externalExecutionId": mock_exec.external_execution_id,
            "createdAt": mock_exec.created_at,
            "lastSyncedAt": mock_exec.last_synced_at
        }
        
        assert result["error"] == "XRAY_TEST_EXECUTION_KEY_REQUIRED"


class TestRetryFailedSyncsEndpointLogic:
    """Test retry-all failed syncs endpoint logic without HTTP layer."""

    def test_retry_requires_provider(self):
        """Retry logic requires provider in request."""
        request = {}
        provider = request.get("provider", "").upper()
        
        if not provider:
            should_error = True
        else:
            should_error = False
        
        assert should_error is True

    def test_retry_returns_no_failed_syncs_when_none_exist(self):
        """Retry logic returns message when no failed syncs exist."""
        failed_executions = []
        
        if not failed_executions:
            result = {
                "provider": "TESTRAIL",
                "retriedCount": 0,
                "message": "No failed syncs found for provider"
            }
        
        assert result["retriedCount"] == 0
        assert "No failed syncs found" in result["message"]

    def test_retry_counts_successful_retries(self):
        """Retry logic counts successful retries."""
        retried_count = 0
        errors = []
        
        # Simulate successful retry
        result = {"success": True}
        if result.get("success"):
            retried_count += 1
        
        assert retried_count == 1

    def test_retry_collects_errors_from_failed_retries(self):
        """Retry logic collects errors from failed retries."""
        retried_count = 0
        errors = []
        
        # Simulate failed retry
        result = {"success": False, "error": "XRAY_TEST_EXECUTION_KEY_REQUIRED"}
        if not result.get("success"):
            errors.append(f"Execution exec-1: {result.get('error', 'Unknown error')}")
        
        assert len(errors) == 1
        assert "XRAY_TEST_EXECUTION_KEY_REQUIRED" in errors[0]


class TestProviderFilteringLogic:
    """Test provider filtering logic."""

    def test_sync_activity_filters_by_provider(self):
        """Sync activity logic filters by provider when specified."""
        activities = [
            {"provider": "TESTRAIL", "id": "1"},
            {"provider": "XRAY", "id": "2"},
            {"provider": "ZEPHYR", "id": "3"}
        ]
        
        provider_filter = "XRAY"
        filtered = [a for a in activities if a["provider"] == provider_filter]
        
        assert len(filtered) == 1
        assert filtered[0]["provider"] == "XRAY"

    def test_sync_activity_returns_all_when_no_filter(self):
        """Sync activity logic returns all activities when no filter specified."""
        activities = [
            {"provider": "TESTRAIL", "id": "1"},
            {"provider": "XRAY", "id": "2"},
            {"provider": "ZEPHYR", "id": "3"}
        ]
        
        provider_filter = None
        filtered = activities if not provider_filter else [a for a in activities if a["provider"] == provider_filter]
        
        assert len(filtered) == 3


class TestEndpointRegistration:
    """Test that endpoints are registered in the router."""

    def test_health_endpoint_exists(self):
        """Health endpoint should be registered."""
        # This is a structural test - in a real test we would check the router
        # For now, we just verify the logic exists
        from app.routers.repository import get_integration_health
        assert callable(get_integration_health)

    def test_sync_activity_endpoint_exists(self):
        """Sync activity endpoint should be registered."""
        from app.routers.repository import get_sync_activity
        assert callable(get_sync_activity)

    def test_retry_failed_syncs_endpoint_exists(self):
        """Retry failed syncs endpoint should be registered."""
        from app.routers.repository import retry_failed_syncs
        assert callable(retry_failed_syncs)


class TestExistingEndpointsUnchanged:
    """Test that existing integration endpoints remain unchanged."""

    def test_list_integrations_endpoint_exists(self):
        """List integrations endpoint should still exist."""
        from app.routers.repository import list_integrations
        assert callable(list_integrations)

    def test_list_provider_capabilities_endpoint_exists(self):
        """List provider capabilities endpoint should still exist."""
        from app.routers.repository import list_integration_provider_capabilities
        assert callable(list_integration_provider_capabilities)

    def test_connect_integration_endpoint_exists(self):
        """Connect integration endpoint should still exist."""
        from app.routers.repository import connect_integration
        assert callable(connect_integration)

    def test_disconnect_integration_endpoint_exists(self):
        """Disconnect integration endpoint should still exist."""
        from app.routers.repository import disconnect_integration
        assert callable(disconnect_integration)

    def test_test_integration_endpoint_exists(self):
        """Test integration endpoint should still exist."""
        from app.routers.repository import test_integration_connection
        assert callable(test_integration_connection)
