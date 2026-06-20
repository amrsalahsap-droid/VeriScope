"""
Azure DevOps Sync Connector (Phase 7.2 — Unsupported)

Azure DevOps is a work-item tracker (Azure Boards). Execution sync
is architecturally unsupported — same rationale as Jira.

All sync methods return UNSUPPORTED_PROVIDER_OPERATION.

supports_execution_sync = False  (permanent for Azure DevOps)
supports_bidirectional_sync = False  (permanent for Azure DevOps)
"""

import logging
from typing import Any, Dict

from app.services.provider_sync.provider_sync_connector import (
    ProviderCapability,
    ProviderSyncConnector,
)

logger = logging.getLogger("veriscope.azure_sync_connector")

_UNSUPPORTED_MSG = (
    "Azure DevOps does not support execution sync. "
    "Azure Boards is a work-item tracker — use TestRail, Xray, or Zephyr for test execution sync."
)


class AzureDevOpsSyncConnector(ProviderSyncConnector):
    """
    Azure DevOps sync adapter — execution sync permanently unsupported.

    Azure DevOps integration is used for work item import only (Azure Boards).
    Azure Test Plans sync may be considered in a separate future phase.
    """
    __test__ = False  # Prevent pytest from collecting this as a test class

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    # ── Capabilities ──────────────────────────────────────────────

    @property
    def supports_execution_sync(self) -> bool:
        return False

    @property
    def supports_bidirectional_sync(self) -> bool:
        return False

    def get_capability(self) -> ProviderCapability:
        return ProviderCapability(
            provider="AZURE_DEVOPS",
            supports_execution_sync=False,
            supports_bidirectional_sync=False,
            supports_test_import=False,
            supports_work_item_import=True,   # Azure Boards supports work item import
            supports_webhooks=False,
        )

    # ── Sync operations ───────────────────────────────────────────

    def validate_connection(self) -> bool:
        logger.info("AzureDevOpsSyncConnector: execution sync unsupported — skipping connection validation")
        return False

    def push_execution_result(
        self,
        test_case_reference: Dict[str, Any],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        logger.warning("AzureDevOpsSyncConnector.push_execution_result called — unsupported provider operation")
        return {
            "success": False,
            "status": "UNSUPPORTED_PROVIDER_OPERATION",
            "external_run_id": None,
            "external_execution_id": None,
            "error": _UNSUPPORTED_MSG,
        }

    def retry_execution_result(
        self,
        test_case_reference: Dict[str, Any],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        logger.warning("AzureDevOpsSyncConnector.retry_execution_result called — unsupported provider operation")
        return {
            "success": False,
            "status": "UNSUPPORTED_PROVIDER_OPERATION",
            "external_run_id": None,
            "external_execution_id": None,
            "error": _UNSUPPORTED_MSG,
        }

    def fetch_execution_status(self, external_execution_id: str) -> Dict[str, Any]:
        logger.warning("AzureDevOpsSyncConnector.fetch_execution_status called — unsupported provider operation")
        return {
            "found": False,
            "status": None,
            "raw_payload": None,
            "error": _UNSUPPORTED_MSG,
        }
