"""
Provider Sync Framework — Abstract Connector Contract

Defines the abstract base class and capability model for provider-agnostic
execution synchronization. Every provider must implement this contract.

Design rules:
- ProviderSyncConnector is separate from TestManagementConnector (import-focused).
- Execution sync is a separate concern from test case import.
- Providers that do not support execution sync must still conform to this
  interface and return appropriate NOT_IMPLEMENTED / UNSUPPORTED responses.
- No provider logic lives in this file.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("veriscope.provider_sync_connector")


@dataclass
class ProviderCapability:
    """
    Describes what an external provider supports in the sync framework.

    Fields:
        provider: Provider identifier (TESTRAIL, XRAY, ZEPHYR, JIRA, AZURE_DEVOPS)
        supports_execution_sync: Provider can receive pushed execution results.
        supports_bidirectional_sync: Provider can send results back to Veriscope.
        supports_test_import: Provider supports structured test case import.
        supports_work_item_import: Provider supports work item / requirement import.
        supports_webhooks: Provider can push events via webhooks.
    """
    provider: str
    supports_execution_sync: bool
    supports_bidirectional_sync: bool
    supports_test_import: bool = False
    supports_work_item_import: bool = False
    supports_webhooks: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize capability to API-ready dictionary."""
        return {
            "provider": self.provider,
            "supportsExecutionSync": self.supports_execution_sync,
            "supportsBidirectionalSync": self.supports_bidirectional_sync,
            "supportsTestImport": self.supports_test_import,
            "supportsWorkItemImport": self.supports_work_item_import,
            "supportsWebhooks": self.supports_webhooks,
        }


class ProviderSyncConnector(ABC):
    """
    Abstract base class for provider-specific execution sync adapters.

    Every provider supported by the sync framework must implement this
    interface. Providers that do not yet support execution sync must still
    conform to the contract and return NOT_IMPLEMENTED or
    UNSUPPORTED_PROVIDER_OPERATION responses.

    Separation of concerns:
    - This class handles EXECUTION SYNC only.
    - TestManagementConnector handles test case import.
    - These are parallel hierarchies and must not be merged.

    Required implementations:
        validate_connection()
        push_execution_result()
        retry_execution_result()
        fetch_execution_status()
        supports_execution_sync (property)
        supports_bidirectional_sync (property)
        get_capability()
    """

    # ──────────────────────────────────────────────────────────────
    # Capability declarations (class-level, overridden per adapter)
    # ──────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def supports_execution_sync(self) -> bool:
        """
        Returns True if this provider can receive pushed execution results.

        Must be a class-level constant — do not perform I/O in this property.
        """
        ...

    @property
    @abstractmethod
    def supports_bidirectional_sync(self) -> bool:
        """
        Returns True if this provider can push results back to Veriscope.

        Must be a class-level constant — do not perform I/O in this property.
        """
        ...

    @abstractmethod
    def get_capability(self) -> ProviderCapability:
        """
        Return the full capability descriptor for this provider.

        Returns:
            ProviderCapability with all capability flags set.
        """
        ...

    # ──────────────────────────────────────────────────────────────
    # Sync operations
    # ──────────────────────────────────────────────────────────────

    @abstractmethod
    def validate_connection(self) -> bool:
        """
        Test that the provider connection is reachable and credentials are valid.

        Returns:
            True if the connection is healthy, False otherwise.
        """
        ...

    @abstractmethod
    def push_execution_result(
        self,
        test_case_reference: Dict[str, Any],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Push a manual test execution result to the external provider.

        Args:
            test_case_reference: Provider-specific case reference.
                Must contain at least: external_id, external_key.
            execution: Execution data from Veriscope.
                Must contain at least: outcome, notes, executed_by, executed_at.

        Returns:
            Dict with keys:
                success (bool): Whether the push succeeded.
                status (str): SYNCED | FAILED | NOT_IMPLEMENTED | UNSUPPORTED_PROVIDER_OPERATION
                external_run_id (str | None): Run ID in provider, if created.
                external_execution_id (str | None): Result ID in provider, if created.
                error (str | None): Error message if failed.
        """
        ...

    @abstractmethod
    def retry_execution_result(
        self,
        test_case_reference: Dict[str, Any],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Retry a previously-failed execution result push.

        Default behavior: delegates to push_execution_result().
        Providers may override for provider-specific retry semantics.

        Args:
            test_case_reference: Same as push_execution_result.
            execution: Same as push_execution_result.

        Returns:
            Same shape as push_execution_result.
        """
        ...

    @abstractmethod
    def fetch_execution_status(
        self,
        external_execution_id: str,
    ) -> Dict[str, Any]:
        """
        Fetch the current status of an execution result from the provider.

        Used for bidirectional sync — checking if an externally-managed
        result has changed state.

        Args:
            external_execution_id: The provider's ID for the execution result.

        Returns:
            Dict with keys:
                found (bool): Whether the execution was found.
                status (str | None): Current status in provider.
                raw_payload (dict | None): Raw provider response.
                error (str | None): Error message if fetch failed.
        """
        ...
