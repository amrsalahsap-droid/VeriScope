"""
Jira Sync Connector (Phase 7.2 — Unsupported)

Jira is a work-item tracker, not a test execution system. Execution sync
to Jira is architecturally unsupported (not a future-planned feature).

All sync methods return UNSUPPORTED_PROVIDER_OPERATION.

supports_execution_sync = False  (permanent for Jira)
supports_bidirectional_sync = False  (permanent for Jira)
"""

import logging
from typing import Any, Dict

from app.services.provider_sync.provider_sync_connector import (
    ProviderCapability,
    ProviderSyncConnector,
)

logger = logging.getLogger("veriscope.jira_sync_connector")

_UNSUPPORTED_MSG = (
    "Jira does not support execution sync. "
    "Jira is a work-item tracker — use TestRail, Xray, or Zephyr for test execution sync."
)


class JiraSyncConnector(ProviderSyncConnector):
    """
    Jira sync adapter — execution sync permanently unsupported.

    Jira integration is used for work item import only. Returning
    UNSUPPORTED_PROVIDER_OPERATION (distinct from NOT_IMPLEMENTED)
    allows the framework to communicate that this is a design boundary,
    not a missing implementation.
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
            provider="JIRA",
            supports_execution_sync=False,
            supports_bidirectional_sync=False,
            supports_test_import=False,
            supports_work_item_import=True,   # Jira supports work item import
            supports_webhooks=False,
        )

    # ── Sync operations ───────────────────────────────────────────

    def validate_connection(self) -> bool:
        logger.info("JiraSyncConnector: execution sync unsupported — skipping connection validation")
        return False

    def push_execution_result(
        self,
        test_case_reference: Dict[str, Any],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        logger.warning("JiraSyncConnector.push_execution_result called — unsupported provider operation")
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
        logger.warning("JiraSyncConnector.retry_execution_result called — unsupported provider operation")
        return {
            "success": False,
            "status": "UNSUPPORTED_PROVIDER_OPERATION",
            "external_run_id": None,
            "external_execution_id": None,
            "error": _UNSUPPORTED_MSG,
        }

    def fetch_execution_status(self, external_execution_id: str) -> Dict[str, Any]:
        logger.warning("JiraSyncConnector.fetch_execution_status called — unsupported provider operation")
        return {
            "found": False,
            "status": None,
            "raw_payload": None,
            "error": _UNSUPPORTED_MSG,
        }
