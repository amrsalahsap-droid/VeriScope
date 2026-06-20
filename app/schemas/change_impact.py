"""
Change Impact Schemas for Phase 3.1

Pydantic schemas for change impact analysis API responses and requests.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ChangeImpactResponse(BaseModel):
    """Change impact response for a requirement or test."""
    level: str = Field(..., description="Impact level: DIRECT, RELATED, INDIRECT, NONE")
    matchedFiles: List[str] = Field(default_factory=list, description="List of matched files")
    matchedPatterns: List[str] = Field(default_factory=list, description="List of matched patterns")
    explanation: str = Field(..., description="Human-readable explanation of impact")


class RequirementChangeImpactRequest(BaseModel):
    """Request to analyze change impact for requirements."""
    changedFiles: List[str] = Field(..., description="List of changed file paths")
    requirements: List[Dict[str, Any]] = Field(..., description="List of requirements with id, title, and optional linked_files")


class TestChangeImpactRequest(BaseModel):
    """Request to analyze change impact for tests."""
    changedFiles: List[str] = Field(..., description="List of changed file paths")
    tests: List[Dict[str, Any]] = Field(..., description="List of tests with id, name, and optional linked_files")


class ChangeImpactAnalysisResponse(BaseModel):
    """Response for change impact analysis."""
    results: Dict[str, ChangeImpactResponse] = Field(..., description="Dict mapping IDs to impact results")
    summary: Dict[str, int] = Field(..., description="Summary counts for each impact level")


class ImpactSummaryResponse(BaseModel):
    """Response with impact level summary."""
    direct: int = Field(..., description="Count of DIRECT impacts")
    related: int = Field(..., description="Count of RELATED impacts")
    indirect: int = Field(..., description="Count of INDIRECT impacts")
    none: int = Field(..., description="Count of NONE impacts")
