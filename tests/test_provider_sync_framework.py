"""
Phase 7.2/7.3A/7.3B — Provider Sync Framework Tests

Tests for the provider-agnostic sync framework:
1. Registry returns correct connector.
2. TestRail connector supports execution sync.
3. Xray connector supports execution sync (Phase 7.3A).
4. Zephyr connector supports execution sync (Phase 7.3B).
5. Jira connector registered.
6. Azure connector registered.
7. Unsupported providers (Jira, Azure) return UNSUPPORTED_PROVIDER_OPERATION.
8. ProviderCapability model has correct fields for TestRail.
9. Registry list_capabilities() returns all 5 providers.
10. Capability snapshot (drift prevention test).
"""

import pytest
from unittest.mock import patch, Mock
from app.services.provider_sync.provider_registry import ProviderRegistry
from app.services.provider_sync.provider_sync_connector import ProviderCapability
from app.services.provider_sync.providers.xray_sync_connector import XraySyncConnector
from app.services.provider_sync.providers.zephyr_sync_connector import ZephyrSyncConnector
from app.services.provider_sync.providers.jira_sync_connector import JiraSyncConnector
from app.services.provider_sync.providers.azure_sync_connector import AzureDevOpsSyncConnector


@pytest.fixture
def registry():
    """Shared ProviderRegistry instance for all tests."""
    return ProviderRegistry()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Registry returns correct connector type
# ─────────────────────────────────────────────────────────────────────────────

@patch('app.services.provider_sync.providers.testrail_sync_connector.TestRailConnector')
def test_registry_returns_testrail_connector(mock_testrail, registry):
    """Registry.get_connector('TESTRAIL') must return a TestRailSyncConnector."""
    from app.services.provider_sync.providers.testrail_sync_connector import TestRailSyncConnector

    # Mock TestRailConnector to avoid abstract method errors
    mock_testrail.return_value = Mock()

    connector = registry.get_connector("TESTRAIL", {
        "base_url": "https://example.testrail.io",
        "username": "test@example.com",
        "api_key": "test-key"
    })
    assert connector is not None
    assert isinstance(connector, TestRailSyncConnector)


def test_registry_returns_xray_connector(registry):
    """Registry.get_connector('XRAY') must return an XraySyncConnector."""
    connector = registry.get_connector("XRAY", {})
    assert connector is not None
    assert isinstance(connector, XraySyncConnector)


def test_registry_returns_zephyr_connector(registry):
    """Registry.get_connector('ZEPHYR') must return a ZephyrSyncConnector."""
    connector = registry.get_connector("ZEPHYR", {})
    assert connector is not None
    assert isinstance(connector, ZephyrSyncConnector)


def test_registry_returns_jira_connector(registry):
    """Registry.get_connector('JIRA') must return a JiraSyncConnector."""
    connector = registry.get_connector("JIRA", {})
    assert connector is not None
    assert isinstance(connector, JiraSyncConnector)


def test_registry_returns_azure_connector(registry):
    """Registry.get_connector('AZURE_DEVOPS') must return an AzureDevOpsSyncConnector."""
    connector = registry.get_connector("AZURE_DEVOPS", {})
    assert connector is not None
    assert isinstance(connector, AzureDevOpsSyncConnector)


def test_registry_returns_none_for_unknown_provider(registry):
    """Registry.get_connector() must return None for an unknown provider."""
    connector = registry.get_connector("UNKNOWN_PROVIDER", {})
    assert connector is None


# ─────────────────────────────────────────────────────────────────────────────
# 2. TestRail connector supports execution sync
# ─────────────────────────────────────────────────────────────────────────────

@patch('app.services.provider_sync.providers.testrail_sync_connector.TestRailConnector')
def test_testrail_supports_execution_sync(mock_testrail, registry):
    """TestRail must report supports_execution_sync = True."""
    mock_testrail.return_value = Mock()
    assert registry.is_execution_sync_supported("TESTRAIL") is True


@patch('app.services.provider_sync.providers.testrail_sync_connector.TestRailConnector')
def test_testrail_connector_supports_execution_sync_property(mock_testrail):
    """TestRailSyncConnector.supports_execution_sync property must return True."""
    from app.services.provider_sync.providers.testrail_sync_connector import TestRailSyncConnector

    mock_testrail.return_value = Mock()
    connector = TestRailSyncConnector({
        "base_url": "https://example.testrail.io",
        "username": "user",
        "api_key": "key"
    })
    assert connector.supports_execution_sync is True


@patch('app.services.provider_sync.providers.testrail_sync_connector.TestRailConnector')
def test_testrail_connector_does_not_support_bidirectional(mock_testrail):
    """TestRailSyncConnector.supports_bidirectional_sync must return False in Phase 7.2."""
    from app.services.provider_sync.providers.testrail_sync_connector import TestRailSyncConnector

    mock_testrail.return_value = Mock()
    connector = TestRailSyncConnector({
        "base_url": "https://example.testrail.io",
        "username": "user",
        "api_key": "key"
    })
    assert connector.supports_bidirectional_sync is False


# ─────────────────────────────────────────────────────────────────────────────
# 3–6. Provider registration checks
# ─────────────────────────────────────────────────────────────────────────────

def test_xray_registered(registry):
    """Xray must be registered in the registry."""
    assert "XRAY" in registry.list_registered_providers()


def test_zephyr_registered(registry):
    """Zephyr must be registered in the registry."""
    assert "ZEPHYR" in registry.list_registered_providers()


def test_jira_registered(registry):
    """Jira must be registered in the registry."""
    assert "JIRA" in registry.list_registered_providers()


def test_azure_registered(registry):
    """Azure DevOps must be registered in the registry."""
    assert "AZURE_DEVOPS" in registry.list_registered_providers()


# ─────────────────────────────────────────────────────────────────────────────
# 7. Xray provider (Phase 7.3A - now supports execution sync)
# ─────────────────────────────────────────────────────────────────────────────

def test_xray_supports_execution_sync(registry):
    """Xray must report supports_execution_sync = True (Phase 7.3A)."""
    assert registry.is_execution_sync_supported("XRAY") is True


def test_xray_push_with_test_execution_key():
    """XraySyncConnector.push_execution_result succeeds with testExecutionKey."""
    connector = XraySyncConnector({
        "testExecutionKey": "XRAY-123"
    })
    result = connector.push_execution_result(
        test_case_reference={"external_id": "1", "external_key": "TEST-456"},
        execution={"outcome": "PASSED", "notes": "Test passed"}
    )
    assert result["success"] is True
    assert result["provider"] == "XRAY"
    assert result["externalRunId"] == "XRAY-123"
    assert result["externalExecutionId"] == "XRAY-123-TEST-456"


def test_xray_push_fails_without_test_execution_key():
    """XraySyncConnector.push_execution_result fails without testExecutionKey."""
    connector = XraySyncConnector({})  # No default testExecutionKey
    result = connector.push_execution_result(
        test_case_reference={"external_id": "1", "external_key": "TEST-456"},
        execution={"outcome": "PASSED"}
    )
    assert result["success"] is False
    assert result["error"] == "XRAY_TEST_EXECUTION_KEY_REQUIRED"


def test_xray_push_fails_without_test_key():
    """XraySyncConnector.push_execution_result fails without test key."""
    connector = XraySyncConnector({"testExecutionKey": "XRAY-123"})
    result = connector.push_execution_result(
        test_case_reference={"external_id": "1"},  # No external_key
        execution={"outcome": "PASSED"}
    )
    assert result["success"] is False
    assert result["error"] == "XRAY_TEST_KEY_REQUIRED"


def test_zephyr_supports_execution_sync(registry):
    """Zephyr must report supports_execution_sync = True (Phase 7.3B)."""
    assert registry.is_execution_sync_supported("ZEPHYR") is True


def test_zephyr_push_with_test_cycle_key():
    """ZephyrSyncConnector.push_execution_result succeeds with testCycleKey."""
    connector = ZephyrSyncConnector({
        "testCycleKey": "CYCLE-123"
    })
    result = connector.push_execution_result(
        test_case_reference={"external_id": "1", "external_key": "TEST-456"},
        execution={"outcome": "PASSED", "notes": "Test passed"}
    )
    assert result["success"] is True
    assert result["provider"] == "ZEPHYR"
    assert result["externalRunId"] == "CYCLE-123"
    assert result["externalExecutionId"] == "CYCLE-123-TEST-456"


def test_zephyr_push_fails_without_test_cycle_key():
    """ZephyrSyncConnector.push_execution_result fails without testCycleKey."""
    connector = ZephyrSyncConnector({})  # No default testCycleKey
    result = connector.push_execution_result(
        test_case_reference={"external_id": "1", "external_key": "TEST-456"},
        execution={"outcome": "PASSED"}
    )
    assert result["success"] is False
    assert result["error"] == "ZEPHYR_TEST_CYCLE_KEY_REQUIRED"


def test_zephyr_push_fails_without_test_case_key():
    """ZephyrSyncConnector.push_execution_result fails without test case key."""
    connector = ZephyrSyncConnector({"testCycleKey": "CYCLE-123"})
    result = connector.push_execution_result(
        test_case_reference={"external_id": "1"},  # No external_key
        execution={"outcome": "PASSED"}
    )
    assert result["success"] is False
    assert result["error"] == "ZEPHYR_TEST_CASE_KEY_REQUIRED"


# ─────────────────────────────────────────────────────────────────────────────
# 8. UNSUPPORTED_PROVIDER_OPERATION providers (Jira, Azure)
# ─────────────────────────────────────────────────────────────────────────────

def test_jira_does_not_support_execution_sync(registry):
    """Jira must report supports_execution_sync = False."""
    assert registry.is_execution_sync_supported("JIRA") is False


def test_jira_push_returns_unsupported():
    """JiraSyncConnector.push_execution_result must return UNSUPPORTED_PROVIDER_OPERATION."""
    connector = JiraSyncConnector({})
    result = connector.push_execution_result(
        test_case_reference={"external_id": "PROJ-1"},
        execution={"outcome": "PASSED"}
    )
    assert result["success"] is False
    assert result["status"] == "UNSUPPORTED_PROVIDER_OPERATION"


def test_azure_does_not_support_execution_sync(registry):
    """Azure DevOps must report supports_execution_sync = False."""
    assert registry.is_execution_sync_supported("AZURE_DEVOPS") is False


def test_azure_push_returns_unsupported():
    """AzureDevOpsSyncConnector.push_execution_result must return UNSUPPORTED_PROVIDER_OPERATION."""
    connector = AzureDevOpsSyncConnector({})
    result = connector.push_execution_result(
        test_case_reference={"external_id": "AB#123"},
        execution={"outcome": "PASSED"}
    )
    assert result["success"] is False
    assert result["status"] == "UNSUPPORTED_PROVIDER_OPERATION"


# ─────────────────────────────────────────────────────────────────────────────
# 9. ProviderCapability model correctness
# ─────────────────────────────────────────────────────────────────────────────

@patch('app.services.provider_sync.providers.testrail_sync_connector.TestRailConnector')
def test_testrail_capability_model(mock_testrail, registry):
    """TestRail ProviderCapability must have correct field values."""
    mock_testrail.return_value = Mock()
    cap = registry.get_capability("TESTRAIL")
    assert cap is not None
    assert isinstance(cap, ProviderCapability)
    assert cap.provider == "TESTRAIL"
    assert cap.supports_execution_sync is True
    assert cap.supports_bidirectional_sync is False
    assert cap.supports_test_import is True
    assert cap.supports_work_item_import is False


@patch('app.services.provider_sync.providers.testrail_sync_connector.TestRailConnector')
def test_capability_to_dict_shape(mock_testrail, registry):
    """ProviderCapability.to_dict() must include all API-expected keys."""
    mock_testrail.return_value = Mock()
    cap = registry.get_capability("TESTRAIL")
    d = cap.to_dict()
    assert "provider" in d
    assert "supportsExecutionSync" in d
    assert "supportsBidirectionalSync" in d
    assert "supportsTestImport" in d
    assert "supportsWorkItemImport" in d
    assert "supportsWebhooks" in d


def test_unknown_provider_capability_returns_none(registry):
    """Registry.get_capability() must return None for unknown providers."""
    assert registry.get_capability("UNKNOWN") is None


# ─────────────────────────────────────────────────────────────────────────────
# 10. list_capabilities() returns all providers
# ─────────────────────────────────────────────────────────────────────────────

@patch('app.services.provider_sync.providers.testrail_sync_connector.TestRailConnector')
def test_list_capabilities_returns_all_providers(mock_testrail, registry):
    """Registry.list_capabilities() must return exactly 5 providers."""
    mock_testrail.return_value = Mock()
    capabilities = registry.list_capabilities()
    providers = {cap.provider for cap in capabilities}
    assert "TESTRAIL" in providers
    assert "XRAY" in providers
    assert "ZEPHYR" in providers
    assert "JIRA" in providers
    assert "AZURE_DEVOPS" in providers
    assert len(capabilities) == 5


# ─────────────────────────────────────────────────────────────────────────────
# 11. Capability snapshot — drift prevention
# ─────────────────────────────────────────────────────────────────────────────

@patch('app.services.provider_sync.providers.testrail_sync_connector.TestRailConnector')
def test_provider_capabilities_snapshot(mock_testrail, registry):
    """
    Snapshot test: capability matrix must exactly match Phase 7.3B specification.

    This test prevents accidental capability drift when future phases
    implement Xray, Zephyr, or other providers. To deliberately change
    capabilities, update this snapshot explicitly.
    """
    mock_testrail.return_value = Mock()
    capabilities = registry.list_capabilities()

    assert {
        c.provider: {
            "execution": c.supports_execution_sync,
            "bidirectional": c.supports_bidirectional_sync,
        }
        for c in capabilities
    } == {
        "TESTRAIL": {"execution": True, "bidirectional": False},
        "XRAY": {"execution": True, "bidirectional": False},  # Phase 7.3A
        "ZEPHYR": {"execution": True, "bidirectional": False},  # Phase 7.3B
        "JIRA": {"execution": False, "bidirectional": False},
        "AZURE_DEVOPS": {"execution": False, "bidirectional": False},
    }
