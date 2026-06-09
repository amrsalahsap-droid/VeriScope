"""
Evidence source and type constants for Veriscope evidence ingestion.

This module defines the standardized constants for evidence sources,
artifact types, and health statuses used across the ingestion pipeline.
"""

from enum import Enum
from typing import Literal


class EvidenceSource(str, Enum):
    """Source of evidence ingestion."""
    MANUAL_UPLOAD = "MANUAL_UPLOAD"
    GITHUB_ACTIONS = "GITHUB_ACTIONS"
    CI_ARTIFACT = "CI_ARTIFACT"
    TEST_MANAGEMENT_IMPORT = "TEST_MANAGEMENT_IMPORT"


class EvidenceArtifactType(str, Enum):
    """Type of evidence artifact."""
    JUNIT_XML = "JUNIT_XML"
    LCOV = "LCOV"
    COBERTURA = "COBERTURA"
    UNKNOWN = "UNKNOWN"


class EvidenceHealthStatus(str, Enum):
    """Health status of ingested evidence."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"
    UNSUPPORTED = "UNSUPPORTED"


class TestManagementProvider(str, Enum):
    """Test management system providers for metadata import."""
    TESTRAIL = "TESTRAIL"
    XRAY = "XRAY"
    ZEPHYR = "ZEPHYR"
    JIRA = "JIRA"
    MANUAL = "MANUAL"


# Type aliases for use in function signatures
EvidenceSourceLiteral = Literal["MANUAL_UPLOAD", "GITHUB_ACTIONS", "CI_ARTIFACT", "TEST_MANAGEMENT_IMPORT"]
EvidenceArtifactTypeLiteral = Literal["JUNIT_XML", "LCOV", "COBERTURA", "UNKNOWN"]
EvidenceHealthStatusLiteral = Literal["HEALTHY", "DEGRADED", "INVALID", "UNSUPPORTED"]
TestManagementProviderLiteral = Literal["TESTRAIL", "XRAY", "ZEPHYR", "JIRA", "MANUAL"]
