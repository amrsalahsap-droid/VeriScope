"""
Xray Sync Connector (Phase 7.3A)

Implements execution result sync for Xray (Jira test management).
Supports both Xray Cloud and Xray Server/Data Center modes.

Xray sync requires:
- testExecutionKey: The Jira issue key for the test execution (e.g., "XRAY-123")
- testKey: The Jira issue key for the test case (from ExternalTestCase.external_key)
- status: Mapped from Veriscope outcome to Xray status
- comment: Optional notes from ManualTestExecution.notes
- evidence: Optional evidence URL from ManualTestExecution.evidence_url

supports_execution_sync = True  (Phase 7.3A)
supports_bidirectional_sync = False  (Phase 7.3A)
"""

import logging
from typing import Any, Dict

from app.services.provider_sync.provider_sync_connector import (
    ProviderCapability,
    ProviderSyncConnector,
)

logger = logging.getLogger("veriscope.xray_sync_connector")

# Default status mapping (Veriscope -> Xray)
_DEFAULT_STATUS_MAPPING = {
    "PASSED": "PASSED",
    "FAILED": "FAILED",
    "BLOCKED": "TODO",
    "SKIPPED": "TODO",
}

# Error codes
_ERROR_TEST_EXECUTION_KEY_REQUIRED = "XRAY_TEST_EXECUTION_KEY_REQUIRED"
_ERROR_TEST_KEY_REQUIRED = "XRAY_TEST_KEY_REQUIRED"
_ERROR_INVALID_STATUS = "XRAY_INVALID_STATUS"


class XraySyncConnector(ProviderSyncConnector):
    """
    Xray execution sync connector for Phase 7.3A.

    Supports pushing execution results to Xray test executions.
    Configurable status mapping allows customization of outcome translations.
    """
    __test__ = False  # Prevent pytest from collecting this as a test class

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Xray sync connector.

        Args:
            config: Configuration dict with optional:
                - xrayMode: "cloud" or "server" (default: "cloud")
                - testExecutionKey: Default test execution key (can be overridden per sync)
                - statusMapping: Custom status mapping dict
        """
        self._config = config or {}
        self._xray_mode = self._config.get("xrayMode", "cloud")
        self._default_test_execution_key = self._config.get("testExecutionKey")
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
            provider="XRAY",
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
        # Phase 7.3A: Basic validation - check for base_url in config
        # Full API validation to be implemented when Xray API contract is confirmed
        base_url = self._config.get("base_url")
        return bool(base_url)

    def _map_status(self, veriscope_status: str) -> str:
        """
        Map Veriscope outcome to Xray status.

        Args:
            veriscope_status: Veriscope outcome (PASSED, FAILED, BLOCKED, SKIPPED)

        Returns:
            Xray status string
        """
        return self._status_mapping.get(veriscope_status, "TODO")

    def push_execution_result(
        self,
        test_case_reference: Dict[str, Any],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Push execution result to Xray test execution.

        Args:
            test_case_reference: Dict with test case info including:
                - external_key: Xray test key (e.g., "TEST-123")
            execution: Dict with execution info including:
                - outcome: Veriscope outcome (PASSED, FAILED, BLOCKED, SKIPPED)
                - notes: Optional execution notes
                - evidence_url: Optional evidence URL
                - provider_metadata: Optional provider-specific metadata (testExecutionKey)

        Returns:
            Dict with sync result:
                - success: bool
                - provider: "XRAY"
                - externalRunId: test execution key
                - externalExecutionId: test execution ID (same as runId for Xray)
                - rawResponse: raw API response (if any)
            Or failure response with error code
        """
        # Extract test key
        test_key = test_case_reference.get("external_key")
        if not test_key:
            logger.error("XraySyncConnector: test_key required from test_case_reference.external_key")
            return {
                "success": False,
                "status": "FAILED",
                "error": _ERROR_TEST_KEY_REQUIRED,
                "error_message": "Xray test key (external_key) is required",
                "httpStatus": None,
                "retryAfterSeconds": None,
                "errorType": "CONFIGURATION_ERROR"
            }

        # Extract test execution key from provider metadata or default
        provider_metadata = execution.get("provider_metadata", {})
        test_execution_key = provider_metadata.get("testExecutionKey") or self._default_test_execution_key

        if not test_execution_key:
            logger.error("XraySyncConnector: testExecutionKey required")
            return {
                "success": False,
                "status": "FAILED",
                "error": _ERROR_TEST_EXECUTION_KEY_REQUIRED,
                "error_message": "Xray test execution key is required in provider_metadata or config",
                "httpStatus": None,
                "retryAfterSeconds": None,
                "errorType": "CONFIGURATION_ERROR"
            }

        # Map status
        veriscope_outcome = execution.get("outcome")
        if not veriscope_outcome:
            logger.error("XraySyncConnector: outcome required from execution")
            return {
                "success": False,
                "status": "FAILED",
                "error": "OUTCOME_REQUIRED",
                "error_message": "Execution outcome is required",
                "httpStatus": None,
                "retryAfterSeconds": None,
                "errorType": "CONFIGURATION_ERROR"
            }

        xray_status = self._map_status(veriscope_outcome)

        # Build Xray execution payload
        payload = {
            "testExecutionKey": test_execution_key,
            "tests": [
                {
                    "testKey": test_key,
                    "status": xray_status,
                    "comment": execution.get("notes", ""),
                }
            ],
        }

        # Add evidence if available
        evidence_url = execution.get("evidence_url")
        if evidence_url:
            payload["tests"][0]["evidence"] = [{"url": evidence_url}]

        # Phase 7.3A: Mock API call - return success with metadata
        # Full API implementation to be added when Xray API contract is confirmed
        logger.info(
            f"XraySyncConnector: Would push execution to test execution {test_execution_key}, "
            f"test {test_key}, status {xray_status}"
        )

        # Return normalized success response with Phase 7.5C error fields
        return {
            "success": True,
            "provider": "XRAY",
            "externalRunId": test_execution_key,
            "externalExecutionId": f"{test_execution_key}-{test_key}",  # Composite ID
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
        logger.info("XraySyncConnector: retry_execution_result - delegating to push_execution_result")
        return self.push_execution_result(test_case_reference, execution)

    def fetch_execution_status(self, external_execution_id: str) -> Dict[str, Any]:
        """
        Fetch execution status from Xray.

        Phase 7.3A: Not implemented - bidirectional sync not supported.

        Args:
            external_execution_id: External execution ID

        Returns:
            Dict with status info or error
        """
        logger.warning("XraySyncConnector.fetch_execution_status: not implemented in Phase 7.3A")
        return {
            "found": False,
            "status": None,
            "raw_payload": None,
            "error": "NOT_IMPLEMENTED",
            "error_message": "Bidirectional sync not supported in Phase 7.3A",
        }
