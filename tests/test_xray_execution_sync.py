"""
Xray Execution Sync Tests (Phase 7.3A)

Tests for Xray execution result sync through the provider sync framework.
"""

import pytest
from unittest.mock import Mock, patch
from app.services.provider_sync.provider_registry import ProviderRegistry
from app.services.provider_sync.providers.xray_sync_connector import XraySyncConnector


class TestXraySyncConnector:
    """Test XraySyncConnector implementation."""

    def test_xray_connector_registered(self):
        """Xray connector must be registered in the registry."""
        registry = ProviderRegistry()
        assert "XRAY" in registry.list_registered_providers()

    def test_xray_supports_execution_sync(self):
        """Xray must report supports_execution_sync = True."""
        connector = XraySyncConnector({})
        assert connector.supports_execution_sync is True

    def test_xray_does_not_support_bidirectional_sync(self):
        """Xray must report supports_bidirectional_sync = False."""
        connector = XraySyncConnector({})
        assert connector.supports_bidirectional_sync is False

    def test_missing_test_execution_key_returns_error(self):
        """Missing testExecutionKey returns XRAY_TEST_EXECUTION_KEY_REQUIRED."""
        connector = XraySyncConnector({})  # No default testExecutionKey
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-123"},
            execution={"outcome": "PASSED"}
        )
        assert result["success"] is False
        assert result["error"] == "XRAY_TEST_EXECUTION_KEY_REQUIRED"

    def test_passed_maps_to_passed(self):
        """PASSED maps to PASSED."""
        connector = XraySyncConnector({"testExecutionKey": "XRAY-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "PASSED"}
        )
        assert result["success"] is True
        assert result["rawResponse"]["tests"][0]["status"] == "PASSED"

    def test_failed_maps_to_failed(self):
        """FAILED maps to FAILED."""
        connector = XraySyncConnector({"testExecutionKey": "XRAY-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "FAILED"}
        )
        assert result["success"] is True
        assert result["rawResponse"]["tests"][0]["status"] == "FAILED"

    def test_blocked_maps_to_todo_by_default(self):
        """BLOCKED maps to TODO by default."""
        connector = XraySyncConnector({"testExecutionKey": "XRAY-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "BLOCKED"}
        )
        assert result["success"] is True
        assert result["rawResponse"]["tests"][0]["status"] == "TODO"

    def test_skipped_maps_to_todo_by_default(self):
        """SKIPPED maps to TODO by default."""
        connector = XraySyncConnector({"testExecutionKey": "XRAY-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "SKIPPED"}
        )
        assert result["success"] is True
        assert result["rawResponse"]["tests"][0]["status"] == "TODO"

    def test_custom_status_mapping_works(self):
        """Custom status mapping works."""
        connector = XraySyncConnector({
            "testExecutionKey": "XRAY-123",
            "statusMapping": {
                "PASSED": "PASS",
                "FAILED": "FAIL",
                "BLOCKED": "BLOCK",
                "SKIPPED": "SKIP"
            }
        })
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "BLOCKED"}
        )
        assert result["success"] is True
        assert result["rawResponse"]["tests"][0]["status"] == "BLOCK"

    def test_provider_metadata_test_execution_key_overrides_default(self):
        """Provider metadata testExecutionKey overrides default."""
        connector = XraySyncConnector({"testExecutionKey": "DEFAULT-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={
                "outcome": "PASSED",
                "provider_metadata": {"testExecutionKey": "OVERRIDE-789"}
            }
        )
        assert result["success"] is True
        assert result["externalRunId"] == "OVERRIDE-789"

    def test_notes_included_in_comment(self):
        """Execution notes included in comment field."""
        connector = XraySyncConnector({"testExecutionKey": "XRAY-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "PASSED", "notes": "Test passed successfully"}
        )
        assert result["success"] is True
        assert result["rawResponse"]["tests"][0]["comment"] == "Test passed successfully"

    def test_evidence_url_included_when_present(self):
        """Evidence URL included when present."""
        connector = XraySyncConnector({"testExecutionKey": "XRAY-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "PASSED", "evidence_url": "https://example.com/evidence.png"}
        )
        assert result["success"] is True
        assert "evidence" in result["rawResponse"]["tests"][0]
        assert result["rawResponse"]["tests"][0]["evidence"][0]["url"] == "https://example.com/evidence.png"

    def test_retry_delegates_to_push(self):
        """retry_execution_result delegates to push_execution_result."""
        connector = XraySyncConnector({"testExecutionKey": "XRAY-123"})
        result = connector.retry_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "PASSED"}
        )
        assert result["success"] is True
        assert result["externalRunId"] == "XRAY-123"

    def test_fetch_execution_status_not_implemented(self):
        """fetch_execution_status returns NOT_IMPLEMENTED."""
        connector = XraySyncConnector({})
        result = connector.fetch_execution_status("XRAY-123-TEST-456")
        assert result["found"] is False
        assert result["error"] == "NOT_IMPLEMENTED"

    def test_validate_connection_checks_base_url(self):
        """validate_connection checks for base_url."""
        connector = XraySyncConnector({"base_url": "https://example.atlassian.net"})
        assert connector.validate_connection() is True

    def test_validate_connection_fails_without_base_url(self):
        """validate_connection fails without base_url."""
        connector = XraySyncConnector({})
        assert connector.validate_connection() is False


class TestXrayIntegrationSync:
    """Test Xray sync through IntegrationSyncService."""

    @pytest.fixture
    def registry(self):
        """Shared ProviderRegistry instance."""
        return ProviderRegistry()

    def test_registry_returns_xray_connector(self, registry):
        """Registry.get_connector('XRAY') must return XraySyncConnector."""
        connector = registry.get_connector("XRAY", {"testExecutionKey": "XRAY-123"})
        assert connector is not None
        assert isinstance(connector, XraySyncConnector)

    def test_xray_capability_model(self, registry):
        """Xray ProviderCapability must have correct field values."""
        cap = registry.get_capability("XRAY")
        assert cap is not None
        assert cap.provider == "XRAY"
        assert cap.supports_execution_sync is True
        assert cap.supports_bidirectional_sync is False
