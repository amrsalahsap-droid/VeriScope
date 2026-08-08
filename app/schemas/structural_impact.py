"""
Schemas for Structural Impact Selection.

This module defines schemas for structural impact selection, which is the
core candidate discovery layer based on changed files and dependency expansion.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from uuid import UUID

from app.constants.evidence import CoverageLevel


class StructuralImpactSelectionRequest(BaseModel):
    """Request for structural impact selection."""
    repository_id: UUID
    pull_request_id: Optional[UUID] = None
    head_commit_sha: str
    changed_files: List[str] = Field(..., description="List of changed file paths")
    max_expansion_depth: Optional[int] = Field(default=1, description="Max dependency expansion depth")
    max_expansion_nodes: Optional[int] = Field(default=500, description="Max nodes to visit during expansion")
    require_test_level: bool = Field(default=False, description="Require test-level coverage for test selection")


class StructuralImpactSelectionResult(BaseModel):
    """Result of structural impact selection."""
    repository_id: UUID
    pull_request_id: Optional[UUID]
    head_commit_sha: str
    
    # File impact
    changed_files: List[str] = Field(default_factory=list, description="Original changed files")
    expanded_files: List[str] = Field(default_factory=list, description="Files added by dependency expansion")
    impacted_files: List[str] = Field(default_factory=list, description="All impacted files (changed + expanded)")
    
    # Test selection based on coverage
    structurally_impacted_tests: List[Dict[str, Any]] = Field(default_factory=list, description="Tests selected based on structural impact")
    coverage_level: Optional[CoverageLevel] = Field(default=None, description="Coverage level used for test selection")
    
    # Gaps and unmapped files
    unmapped_impacted_files: List[str] = Field(default_factory=list, description="Impacted files with no coverage/test mapping")
    coverage_gaps: List[Dict[str, Any]] = Field(default_factory=list, description="Coverage gaps for impacted files")
    
    # Evidence paths
    evidence_paths: Dict[str, List[str]] = Field(default_factory=dict, description="Evidence paths for each selected test")
    
    # Metadata
    dependency_expansion_used: bool = Field(default=False, description="Whether dependency expansion was used")
    expansion_depth_reached: int = Field(default=0, description="Depth reached during expansion")
    expansion_limit_exceeded: bool = Field(default=False, description="Whether expansion hit limits")
    dependency_state_hash: Optional[str] = Field(default=None, description="Hash of dependency graph state")
    
    # Confidence
    selection_confidence: str = Field(default="MODERATE", description="Confidence in structural selection")
    selection_reasons: List[str] = Field(default_factory=list, description="Reasons for selection decisions")


class StructuralTestCandidate(BaseModel):
    """A test candidate selected by structural impact."""
    test_case_id: Optional[UUID] = None
    stable_test_id: Optional[str] = None
    test_file_id: Optional[UUID] = None
    file_path: str = Field(..., description="Source file covered by this test")
    covered_lines: Optional[List[int]] = Field(default_factory=list)
    line_ranges: Optional[List[List[int]]] = Field(default_factory=list)
    mapping_type: str = Field(..., description="DIRECT, HEURISTIC_NAMING, HEURISTIC_PATH")
    confidence_score: str = Field(..., description="HIGH, MODERATE, LOW")
    source: Optional[str] = Field(default=None, description="Source of mapping (e.g., LCOV_PER_TEST)")
    
    # Structural impact metadata
    impact_reason: str = Field(..., description="Why this test was selected structurally")
    impact_depth: int = Field(default=0, description="Depth of file impact chain")
    evidence_path: List[str] = Field(default_factory=list, description="Chain of evidence from changed file to test")
