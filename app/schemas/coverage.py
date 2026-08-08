"""
Schemas for coverage evidence ingestion and querying.

This module defines the schemas for coverage reports, file entries, and test links,
supporting different coverage levels (RUN_LEVEL, TEST_FILE_LEVEL, TEST_CASE_LEVEL).
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

from app.constants.evidence import CoverageLevel, EvidenceSource, EvidenceArtifactType, EvidenceHealthStatus


class CoverageReportCreate(BaseModel):
    """Schema for creating a coverage report."""
    repository_id: UUID
    workspace_id: UUID
    commit_sha: Optional[str] = None
    pull_request_id: Optional[UUID] = None
    raw_artifact_id: Optional[UUID] = None
    format: str = Field(..., description="Coverage format: LCOV, COBERTURA")
    source: str = Field(..., description="Source: MANUAL_UPLOAD, GITHUB_ACTIONS, CI_ARTIFACT")
    branch: Optional[str] = None
    coverage_level: CoverageLevel = Field(default=CoverageLevel.RUN_LEVEL, description="Coverage granularity level")
    files_total: int = 0
    covered_lines_total: int = 0
    uncovered_lines_total: int = 0
    total_lines: int = 0
    line_coverage_ratio: Optional[float] = None
    branch_coverage_ratio: Optional[float] = None
    coverage_confidence: str = "MODERATE"
    evidence_health_status: EvidenceHealthStatus = EvidenceHealthStatus.HEALTHY
    parser_version: str = "1.0.0"
    normalization_schema_version: str = "1.0.0"
    file_hash: str = Field(..., description="SHA-256 hash of payload")


class CoverageReportResponse(BaseModel):
    """Schema for coverage report response."""
    id: UUID
    repository_id: UUID
    workspace_id: UUID
    commit_sha: Optional[str]
    pull_request_id: Optional[UUID]
    raw_artifact_id: Optional[UUID]
    format: str
    source: str
    branch: Optional[str]
    coverage_level: CoverageLevel
    files_total: int
    covered_lines_total: int
    uncovered_lines_total: int
    total_lines: int
    line_coverage_ratio: Optional[float]
    branch_coverage_ratio: Optional[float]
    coverage_confidence: str
    evidence_health_status: EvidenceHealthStatus
    parser_version: str
    normalization_schema_version: str
    file_hash: str
    created_at: datetime

    class Config:
        from_attributes = True


class CoverageFileEntryCreate(BaseModel):
    """Schema for creating a coverage file entry."""
    coverage_report_id: UUID
    repository_id: UUID
    file_path: str
    covered_lines: List[int] = Field(default_factory=list)
    uncovered_lines: List[int] = Field(default_factory=list)
    total_lines: int = 0
    line_coverage_ratio: Optional[float] = None
    branch_coverage_ratio: Optional[float] = None
    functions_covered: Optional[int] = None
    functions_total: Optional[int] = None


class CoverageFileEntryResponse(BaseModel):
    """Schema for coverage file entry response."""
    id: UUID
    coverage_report_id: UUID
    repository_id: UUID
    file_path: str
    covered_lines: List[int]
    uncovered_lines: List[int]
    total_lines: int
    line_coverage_ratio: Optional[float]
    branch_coverage_ratio: Optional[float]
    functions_covered: Optional[int]
    functions_total: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class FileTestLinkCreate(BaseModel):
    """Schema for creating a file-test link."""
    coverage_report_id: UUID
    file_path: str
    test_case_id: Optional[UUID] = None
    stable_test_id: Optional[str] = None
    test_file_id: Optional[UUID] = None
    covered_lines: Optional[List[int]] = Field(default_factory=list)
    line_ranges: Optional[List[List[int]]] = Field(default_factory=list)
    mapping_type: str = Field(..., description="DIRECT, HEURISTIC_NAMING, HEURISTIC_PATH")
    confidence_score: str = Field(..., description="HIGH, MODERATE, LOW")
    source: Optional[str] = None


class FileTestLinkResponse(BaseModel):
    """Schema for file-test link response."""
    id: UUID
    coverage_report_id: UUID
    file_path: str
    test_case_id: Optional[UUID]
    stable_test_id: Optional[str]
    test_file_id: Optional[UUID]
    covered_lines: Optional[List[int]]
    line_ranges: Optional[List[List[int]]]
    mapping_type: str
    confidence_score: str
    source: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CoverageQueryRequest(BaseModel):
    """Schema for querying coverage for changed files."""
    repository_id: UUID
    commit_sha: Optional[str] = None
    pull_request_id: Optional[UUID] = None
    changed_files: List[str] = Field(..., description="List of changed file paths")
    require_test_level: bool = Field(default=False, description="Only return results if test-level coverage exists")


class CoverageQueryResponse(BaseModel):
    """Schema for coverage query response."""
    coverage_report_id: Optional[UUID]
    coverage_level: Optional[CoverageLevel]
    commit_sha: Optional[str]
    is_current: bool = Field(..., description="True if coverage matches current commit SHA")
    covered_files: List[str] = Field(default_factory=list, description="Files with any coverage")
    uncovered_files: List[str] = Field(default_factory=list, description="Files with no coverage")
    file_coverage_details: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Per-file coverage details")
    test_candidates: List[Dict[str, Any]] = Field(default_factory=list, description="Test candidates if test-level coverage exists")
    coverage_confidence: str = "LOW"
    evidence_health_status: EvidenceHealthStatus = EvidenceHealthStatus.HEALTHY


class CoverageIngestionResult(BaseModel):
    """Schema for coverage ingestion result."""
    success: bool
    coverage_report_id: Optional[UUID]
    coverage_level: CoverageLevel
    files_processed: int
    test_links_created: int
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
