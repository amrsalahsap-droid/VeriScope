"""
TestRail Sync Connector (Phase 7.2 Adapter)

Wraps the existing TestRailConnector.push_execution_result() to conform to the
ProviderSyncConnector contract. Zero behavior change from Phase 7.1 — all actual
HTTP communication still goes through TestRailConnector.

supports_execution_sync = True
supports_bidirectional_sync = False  (Phase 7.2 scope)
"""

import logging
from typing import Any, Dict

from app.services.provider_sync.provider_sync_connector import (
    ProviderCapability,
    ProviderSyncConnector,
)
from app.services.testrail_connector import TestRailConnector

logger = logging.getLogger("veriscope.testrail_sync_connector")


class TestRailSyncConnector(ProviderSyncConnector):
    """
    Execution sync adapter for TestRail.

    Delegates all HTTP communication to the existing TestRailConnector.
    This adapter adds no logic of its own — it is purely a contract shim.
    """
    __test__ = False  # Prevent pytest from collecting this as a test class

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: IntegrationConnection.config dict.
                    Expected keys: base_url, username, api_key
        """
        self._config = config
        self._connector = TestRailConnector(
            base_url=config.get("base_url", ""),
            username=config.get("username", ""),
            api_key=config.get("api_key", ""),
        )

    # ── Capabilities ──────────────────────────────────────────────

    @property
    def supports_execution_sync(self) -> bool:
        return True

    @property
    def supports_bidirectional_sync(self) -> bool:
        return False

    def get_capability(self) -> ProviderCapability:
        return ProviderCapability(
            provider="TESTRAIL",
            supports_execution_sync=True,
            supports_bidirectional_sync=False,
            supports_test_import=True,
            supports_work_item_import=False,
            supports_webhooks=False,
        )

    # ── Sync operations ───────────────────────────────────────────

    def validate_connection(self) -> bool:
        """Delegate to TestRailConnector credential validation."""
        try:
            return self._connector.validate_credentials(self._config)
        except Exception as e:
            logger.warning(f"TestRail connection validation failed: {e}")
            return False

    def push_execution_result(
        self,
        test_case_reference: Dict[str, Any],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Push execution result to TestRail.

        Delegates directly to TestRailConnector.push_execution_result().
        No transformation or added logic.
        """
        return self._connector.push_execution_result(test_case_reference, execution)

    def retry_execution_result(
        self,
        test_case_reference: Dict[str, Any],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Retry a failed push — TestRail has no dedicated retry endpoint,
        so this is identical to push_execution_result.
        """
        logger.info(
            f"TestRail retry_execution_result: delegating to push "
            f"for case {test_case_reference.get('external_key')}"
        )
        return self.push_execution_result(test_case_reference, execution)

    def fetch_execution_status(self, external_execution_id: str) -> Dict[str, Any]:
        """
        Fetch execution status from TestRail.

        Phase 7.2 scope: bidirectional sync is not yet implemented.
        Returns a not-implemented response until Phase 7.3+.
        """
        return {
            "found": False,
            "status": None,
            "raw_payload": None,
            "error": (
                "TestRail bidirectional sync not implemented in Phase 7.2. "
                "Execution results are pushed only."
            ),
        }
