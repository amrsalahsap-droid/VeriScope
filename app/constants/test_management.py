"""
Test Management Integration Constants

Constants for external test management system integrations.
"""

from enum import Enum
from typing import Dict


class VeriscopeExecutionOutcome(str, Enum):
    """Veriscope manual test execution outcomes."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class TestRailExecutionStatus(str, Enum):
    """TestRail execution statuses."""
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    RETEST = "retest"


# Outcome mapping: Veriscope -> TestRail
VERISCOPE_TO_TESTRAIL_OUTCOME_MAP: Dict[VeriscopeExecutionOutcome, TestRailExecutionStatus] = {
    VeriscopeExecutionOutcome.PASSED: TestRailExecutionStatus.PASSED,
    VeriscopeExecutionOutcome.FAILED: TestRailExecutionStatus.FAILED,
    VeriscopeExecutionOutcome.BLOCKED: TestRailExecutionStatus.BLOCKED,
    VeriscopeExecutionOutcome.SKIPPED: TestRailExecutionStatus.RETEST,
}


def map_veriscope_to_testrail_outcome(veriscope_outcome: str) -> str:
    """
    Map Veriscope execution outcome to TestRail status.
    
    Args:
        veriscope_outcome: Veriscope execution outcome (PASSED, FAILED, BLOCKED, SKIPPED)
        
    Returns:
        TestRail status string (passed, failed, blocked, retest)
        
    Raises:
        ValueError: If outcome is not recognized
    """
    try:
        veriscope_enum = VeriscopeExecutionOutcome(veriscope_outcome.upper())
        testrail_status = VERISCOPE_TO_TESTRAIL_OUTCOME_MAP[veriscope_enum]
        return testrail_status.value
    except (ValueError, KeyError) as e:
        raise ValueError(f"Unrecognized Veriscope outcome: {veriscope_outcome}") from e


class SyncStatus(str, Enum):
    """Manual execution sync status."""
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
