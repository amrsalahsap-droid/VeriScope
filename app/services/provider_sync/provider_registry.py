"""
Provider Sync Framework — Provider Registry

Single source of truth for which connector handles which provider.
No switch statements in application code — use registry.get_connector(provider).

Design rules:
- Registry is stateless. Connectors are instantiated on demand.
- Adding a new provider = add one entry to _REGISTRY. Nothing else.
- Registry never raises — unsupported providers return None / empty capability.
"""

import logging
from typing import Any, Dict, List, Optional, Type

from app.services.provider_sync.provider_sync_connector import (
    ProviderCapability,
    ProviderSyncConnector,
)
from app.services.provider_sync.providers.testrail_sync_connector import (
    TestRailSyncConnector,
)
from app.services.provider_sync.providers.xray_sync_connector import (
    XraySyncConnector,
)
from app.services.provider_sync.providers.zephyr_sync_connector import (
    ZephyrSyncConnector,
)
from app.services.provider_sync.providers.jira_sync_connector import (
    JiraSyncConnector,
)
from app.services.provider_sync.providers.azure_sync_connector import (
    AzureDevOpsSyncConnector,
)

logger = logging.getLogger("veriscope.provider_registry")


# ─────────────────────────────────────────────────────────────────────────────
# Registry mapping — the ONLY place a provider is registered.
# Key:   provider string identifier (must match IntegrationConnection.provider)
# Value: connector class (not instance)
# ─────────────────────────────────────────────────────────────────────────────
_REGISTRY: Dict[str, Type[ProviderSyncConnector]] = {
    "TESTRAIL": TestRailSyncConnector,
    "XRAY": XraySyncConnector,
    "ZEPHYR": ZephyrSyncConnector,
    "JIRA": JiraSyncConnector,
    "AZURE_DEVOPS": AzureDevOpsSyncConnector,
}


class ProviderRegistry:
    """
    Registry for provider sync connectors.

    Usage:
        registry = ProviderRegistry()
        connector = registry.get_connector("TESTRAIL", config)
        if connector and registry.is_execution_sync_supported("TESTRAIL"):
            result = connector.push_execution_result(...)
    """

    def get_connector(
        self,
        provider: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[ProviderSyncConnector]:
        """
        Instantiate and return the sync connector for a given provider.

        Args:
            provider: Provider identifier (e.g. "TESTRAIL").
            config: Provider-specific configuration dict from IntegrationConnection.

        Returns:
            Instantiated ProviderSyncConnector, or None if provider is unknown.
        """
        connector_class = _REGISTRY.get(provider)
        if connector_class is None:
            logger.warning(
                f"ProviderRegistry: no sync connector registered for provider '{provider}'"
            )
            return None

        try:
            return connector_class(config or {})
        except Exception as e:
            logger.error(
                f"ProviderRegistry: failed to instantiate connector for provider '{provider}': {e}"
            )
            return None

    def get_capability(self, provider: str) -> Optional[ProviderCapability]:
        """
        Return the ProviderCapability for a provider without instantiating config.

        Uses a zero-config connector instance to read capability properties.

        Args:
            provider: Provider identifier.

        Returns:
            ProviderCapability, or None if provider is unknown.
        """
        connector_class = _REGISTRY.get(provider)
        if connector_class is None:
            return None

        try:
            # Instantiate with empty config to read static capability properties
            connector = connector_class({})
            return connector.get_capability()
        except Exception as e:
            logger.error(
                f"ProviderRegistry: failed to read capability for provider '{provider}': {e}"
            )
            return None

    def list_capabilities(self) -> List[ProviderCapability]:
        """
        Return capability descriptors for all registered providers.

        Returns:
            List of ProviderCapability, one per registered provider.
            Order matches _REGISTRY insertion order (Python 3.7+).
        """
        capabilities = []
        for provider in _REGISTRY:
            cap = self.get_capability(provider)
            if cap is not None:
                capabilities.append(cap)
        return capabilities

    def is_execution_sync_supported(self, provider: str) -> bool:
        """
        Quick check: does this provider support execution sync?

        Args:
            provider: Provider identifier.

        Returns:
            True if the provider is registered and supports execution sync.
            False if provider is unknown or does not support sync.
        """
        cap = self.get_capability(provider)
        if cap is None:
            return False
        return cap.supports_execution_sync

    def list_registered_providers(self) -> List[str]:
        """Return the list of all registered provider identifiers."""
        return list(_REGISTRY.keys())
