"""
Zephyr Execution Sync Tests (Phase 7.3B)

Tests for Zephyr execution result sync through the provider sync framework.
"""

import pytest
from unittest.mock import Mock, patch
from app.services.provider_sync.provider_registry import ProviderRegistry
from app.services.provider_sync.providers.zephyr_sync_connector import ZephyrSyncConnector


class TestZephyrSyncConnector:
    """Test ZephyrSyncConnector implementation."""

    def test_zephyr_connector_registered(self):
        """Zephyr connector must be registered in the registry."""
        registry = ProviderRegistry()
        assert "ZEPHYR" in registry.list_registered_providers()

    def test_zephyr_supports_execution_sync(self):
        """Zephyr must report supports_execution_sync = True."""
        connector = ZephyrSyncConnector({})
        assert connector.supports_execution_sync is True

    def test_zephyr_does_not_support_bidirectional_sync(self):
        """Zephyr must report supports_bidirectional_sync = False."""
        connector = ZephyrSyncConnector({})
        assert connector.supports_bidirectional_sync is False

    def test_missing_test_cycle_key_returns_error(self):
        """Missing testCycleKey returns ZEPHYR_TEST_CYCLE_KEY_REQUIRED."""
        connector = ZephyrSyncConnector({})  # No default testCycleKey
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-123"},
            execution={"outcome": "PASSED"}
        )
        assert result["success"] is False
        assert result["error"] == "ZEPHYR_TEST_CYCLE_KEY_REQUIRED"

    def test_passed_maps_to_pass(self):
        """PASSED maps to Pass."""
        connector = ZephyrSyncConnector({"testCycleKey": "CYCLE-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "PASSED"}
        )
        assert result["success"] is True
        assert result["rawResponse"]["tests"][0]["status"] == "Pass"

    def test_failed_maps_to_fail(self):
        """FAILED maps to Fail."""
        connector = ZephyrSyncConnector({"testCycleKey": "CYCLE-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "FAILED"}
        )
        assert result["success"] is True
        assert result["rawResponse"]["tests"][0]["status"] == "Fail"

    def test_blocked_maps_to_blocked(self):
        """BLOCKED maps to Blocked."""
        connector = ZephyrSyncConnector({"testCycleKey": "CYCLE-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "BLOCKED"}
        )
        assert result["success"] is True
        assert result["rawResponse"]["tests"][0]["status"] == "Blocked"

    def test_skipped_maps_to_not_executed(self):
        """SKIPPED maps to Not Executed."""
        connector = ZephyrSyncConnector({"testCycleKey": "CYCLE-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "SKIPPED"}
        )
        assert result["success"] is True
        assert result["rawResponse"]["tests"][0]["status"] == "Not Executed"

    def test_custom_status_mapping_works(self):
        """Custom status mapping works."""
        connector = ZephyrSyncConnector({
            "testCycleKey": "CYCLE-123",
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

    def test_provider_metadata_test_cycle_key_overrides_default(self):
        """Provider metadata testCycleKey overrides default."""
        connector = ZephyrSyncConnector({"testCycleKey": "DEFAULT-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={
                "outcome": "PASSED",
                "provider_metadata": {"testCycleKey": "OVERRIDE-789"}
            }
        )
        assert result["success"] is True
        assert result["externalRunId"] == "OVERRIDE-789"

    def test_notes_included_in_comment(self):
        """Execution notes included in comment field."""
        connector = ZephyrSyncConnector({"testCycleKey": "CYCLE-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "PASSED", "notes": "Test passed successfully"}
        )
        assert result["success"] is True
        assert result["rawResponse"]["tests"][0]["comment"] == "Test passed successfully"

    def test_evidence_url_included_when_present(self):
        """Evidence URL included when present."""
        connector = ZephyrSyncConnector({"testCycleKey": "CYCLE-123"})
        result = connector.push_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "PASSED", "evidence_url": "https://example.com/evidence.png"}
        )
        assert result["success"] is True
        assert "evidence" in result["rawResponse"]["tests"][0]
        assert result["rawResponse"]["tests"][0]["evidence"][0]["url"] == "https://example.com/evidence.png"

    def test_retry_delegates_to_push(self):
        """retry_execution_result delegates to push_execution_result."""
        connector = ZephyrSyncConnector({"testCycleKey": "CYCLE-123"})
        result = connector.retry_execution_result(
            test_case_reference={"external_key": "TEST-456"},
            execution={"outcome": "PASSED"}
        )
        assert result["success"] is True
        assert result["externalRunId"] == "CYCLE-123"

    def test_fetch_execution_status_not_implemented(self):
        """fetch_execution_status returns NOT_IMPLEMENTED."""
        connector = ZephyrSyncConnector({})
        result = connector.fetch_execution_status("CYCLE-123-TEST-456")
        assert result["found"] is False
        assert result["error"] == "NOT_IMPLEMENTED"

    def test_validate_connection_checks_base_url(self):
        """validate_connection checks for base_url."""
        connector = ZephyrSyncConnector({"base_url": "https://example.atlassian.net"})
        assert connector.validate_connection() is True

    def test_validate_connection_fails_without_base_url(self):
        """validate_connection fails without base_url."""
        connector = ZephyrSyncConnector({})
        assert connector.validate_connection() is False


class TestZephyrIntegrationSync:
    """Test Zephyr sync through IntegrationSyncService."""

    @pytest.fixture
    def registry(self):
        """Shared ProviderRegistry instance."""
        return ProviderRegistry()

    def test_registry_returns_zephyr_connector(self, registry):
        """Registry.get_connector('ZEPHYR') must return ZephyrSyncConnector."""
        connector = registry.get_connector("ZEPHYR", {"testCycleKey": "CYCLE-123"})
        assert connector is not None
        assert isinstance(connector, ZephyrSyncConnector)

    def test_zephyr_capability_model(self, registry):
        """Zephyr ProviderCapability must have correct field values."""
        cap = registry.get_capability("ZEPHYR")
        assert cap is not None
        assert cap.provider == "ZEPHYR"
        assert cap.supports_execution_sync is True
        assert cap.supports_bidirectional_sync is False
