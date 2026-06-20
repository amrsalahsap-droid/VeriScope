"""
Zephyr Sync Connector (Phase 7.3B)

Implements execution result sync for Zephyr (Jira test management).
Supports Zephyr Scale, Squad, and Enterprise modes.

Zephyr sync requires:
- testCycleKey: The Jira issue key for the test cycle (e.g., "CYCLE-123")
- testCaseKey: The Jira issue key for the test case (from ExternalTestCase.external_key)
- status: Mapped from Veriscope outcome to Zephyr status
- comment: Optional notes from ManualTestExecution.notes
- evidence: Optional evidence URL from ManualTestExecution.evidence_url

supports_execution_sync = True  (Phase 7.3B)
supports_bidirectional_sync = False  (Phase 7.3B)
"""

import logging
from typing import Any, Dict

from app.services.provider_sync.provider_sync_connector import (
    ProviderCapability,
    ProviderSyncConnector,
)

logger = logging.getLogger("veriscope.zephyr_sync_connector")

# Default status mapping (Veriscope -> Zephyr)
_DEFAULT_STATUS_MAPPING = {
    "PASSED": "Pass",
    "FAILED": "Fail",
    "BLOCKED": "Blocked",
    "SKIPPED": "Not Executed",
}

# Error codes
_ERROR_TEST_CYCLE_KEY_REQUIRED = "ZEPHYR_TEST_CYCLE_KEY_REQUIRED"
_ERROR_TEST_CASE_KEY_REQUIRED = "ZEPHYR_TEST_CASE_KEY_REQUIRED"
_ERROR_INVALID_STATUS = "ZEPHYR_INVALID_STATUS"


class ZephyrSyncConnector(ProviderSyncConnector):
    """
    Zephyr execution sync connector for Phase 7.3B.

    Supports pushing execution results to Zephyr test cycles.
    Configurable status mapping allows customization of outcome translations.
    """
    __test__ = False  # Prevent pytest from collecting this as a test class

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Zephyr sync connector.

        Args:
            config: Configuration dict with optional:
                - zephyrMode: "scale", "squad", or "enterprise" (default: "scale")
                - testCycleKey: Default test cycle key (can be overridden per sync)
                - statusMapping: Custom status mapping dict
        """
        self._config = config or {}
        self._zephyr_mode = self._config.get("zephyrMode", "scale")
        self._default_test_cycle_key = self._config.get("testCycleKey")
        self._status_mapping = self._config.get("statusMapping", _DEFAULT_STATUS_MAPPING)

    # ── Capabilities ──────────────────────────────────────────────

    @property
    def supports_execution_sync(self) -> bool:
        return True

    @property
    def supports_bidirectional_sync(self) -> bool:
        return False

    def get_capability(self) -> ProviderCapability:
        return ProviderCapability(
            provider="ZEPHYR",
            supports_execution_sync=True,
            supports_bidirectional_sync=False,
            supports_test_import=False,  # Not yet implemented
            supports_work_item_import=False,  # Not yet implemented
            supports_webhooks=False,
        )

    # ── Sync operations ───────────────────────────────────────────

    def validate_connection(self) -> bool:
        """
        Validate connection configuration.

        Returns:
            True if required config is present, False otherwise
        """
        # Phase 7.3B: Basic validation - check for base_url in config
        # Full API validation to be implemented when Zephyr API contract is confirmed
        base_url = self._config.get("base_url")
        return bool(base_url)

    def _map_status(self, veriscope_status: str) -> str:
        """
        Map Veriscope outcome to Zephyr status.

        Args:
            veriscope_status: Veriscope outcome (PASSED, FAILED, BLOCKED, SKIPPED)

        Returns:
            Zephyr status string
        """
        return self._status_mapping.get(veriscope_status, "Not Executed")

    def push_execution_result(
        self,
        test_case_reference: Dict[str, Any],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Push execution result to Zephyr test cycle.

        Args:
            test_case_reference: Dict with test case info including:
                - external_key: Zephyr test case key (e.g., "TEST-123")
            execution: Dict with execution info including:
                - outcome: Veriscope outcome (PASSED, FAILED, BLOCKED, SKIPPED)
                - notes: Optional execution notes
                - evidence_url: Optional evidence URL
                - provider_metadata: Optional provider-specific metadata (testCycleKey)

        Returns:
            Dict with sync result:
                - success: bool
                - provider: "ZEPHYR"
                - externalRunId: test cycle key
                - externalExecutionId: test execution ID (same as runId for Zephyr)
                - rawResponse: raw API response (if any)
            Or failure response with error code
        """
        # Extract test case key
        test_case_key = test_case_reference.get("external_key")
        if not test_case_key:
            logger.error("ZephyrSyncConnector: test_case_key required from test_case_reference.external_key")
            return {
                "success": False,
                "status": "FAILED",
                "error": _ERROR_TEST_CASE_KEY_REQUIRED,
                "error_message": "Zephyr test case key (external_key) is required",
                "httpStatus": None,
                "retryAfterSeconds": None,
                "errorType": "CONFIGURATION_ERROR"
            }

        # Extract test cycle key from provider metadata or default
        provider_metadata = execution.get("provider_metadata", {})
        test_cycle_key = provider_metadata.get("testCycleKey") or self._default_test_cycle_key

        if not test_cycle_key:
            logger.error("ZephyrSyncConnector: testCycleKey required")
            return {
                "success": False,
                "status": "FAILED",
                "error": _ERROR_TEST_CYCLE_KEY_REQUIRED,
                "error_message": "Zephyr test cycle key is required in provider_metadata or config",
                "httpStatus": None,
                "retryAfterSeconds": None,
                "errorType": "CONFIGURATION_ERROR"
            }

        # Map status
        veriscope_outcome = execution.get("outcome")
        if not veriscope_outcome:
            logger.error("ZephyrSyncConnector: outcome required from execution")
            return {
                "success": False,
                "status": "FAILED",
                "error": "OUTCOME_REQUIRED",
                "error_message": "Execution outcome is required",
                "httpStatus": None,
                "retryAfterSeconds": None,
                "errorType": "CONFIGURATION_ERROR"
            }

        zephyr_status = self._map_status(veriscope_outcome)

        # Build Zephyr execution payload
        payload = {
            "testCycleKey": test_cycle_key,
            "tests": [
                {
                    "testCaseKey": test_case_key,
                    "status": zephyr_status,
                    "comment": execution.get("notes", ""),
                }
            ],
        }

        # Add evidence if available
        evidence_url = execution.get("evidence_url")
        if evidence_url:
            payload["tests"][0]["evidence"] = [{"url": evidence_url}]

        # Phase 7.3B: Mock API call - return success with metadata
        # Full API implementation to be added when Zephyr API contract is confirmed
        logger.info(
            f"ZephyrSyncConnector: Would push execution to test cycle {test_cycle_key}, "
            f"test case {test_case_key}, status {zephyr_status}"
        )

        # Return normalized success response with Phase 7.5C error fields
        return {
            "success": True,
            "provider": "ZEPHYR",
            "externalRunId": test_cycle_key,
            "externalExecutionId": f"{test_cycle_key}-{test_case_key}",  # Composite ID
            "rawResponse": payload,
            "status": "SYNCED",
            "error": None,
            "httpStatus": None,
            "retryAfterSeconds": None,
            "errorType": None
        }

    def retry_execution_result(
        self,
        test_case_reference: Dict[str, Any],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Retry execution result sync (delegates to push_execution_result).

        Args:
            test_case_reference: Dict with test case info
            execution: Dict with execution info

        Returns:
            Dict with sync result
        """
        logger.info("ZephyrSyncConnector: retry_execution_result - delegating to push_execution_result")
        return self.push_execution_result(test_case_reference, execution)

    def fetch_execution_status(self, external_execution_id: str) -> Dict[str, Any]:
        """
        Fetch execution status from Zephyr.

        Phase 7.3B: Not implemented - bidirectional sync not supported.

        Args:
            external_execution_id: External execution ID

        Returns:
            Dict with status info or error
        """
        logger.warning("ZephyrSyncConnector.fetch_execution_status: not implemented in Phase 7.3B")
        return {
            "found": False,
            "status": None,
            "raw_payload": None,
            "error": "NOT_IMPLEMENTED",
            "error_message": "Bidirectional sync not supported in Phase 7.3B",
        }
