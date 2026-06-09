"""
Regression Suite API Schemas

Pydantic schemas for RegressionSuite model API requests and responses.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from uuid import UUID


class SuiteType:
    PR_REGRESSION = "PR_REGRESSION"
    RELEASE_REGRESSION = "RELEASE_REGRESSION"
    SMOKE = "SMOKE"
    FULL = "FULL"
    HOTFIX = "HOTFIX"


class SuiteStatus:
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"


class RegressionSuiteBase(BaseModel):
    """Base schema for RegressionSuite."""
    name: str = Field(..., description="Suite name")
    description: Optional[str] = Field(None, description="Suite description")
    suite_type: str = Field(default=SuiteType.PR_REGRESSION, description="Type of suite")
    status: str = Field(default=SuiteStatus.DRAFT, description="Suite status")
    confidence_level: Optional[str] = Field(None, description="Confidence level (HIGH, MODERATE, LOW)")
    scope_score: Optional[float] = Field(None, description="Scope score (0.0 to 1.0)")


class RegressionSuiteCreate(RegressionSuiteBase):
    """Schema for creating a RegressionSuite."""
    repository_id: UUID = Field(..., description="Repository ID")
    release_id: Optional[UUID] = Field(None, description="Release ID (optional)")
    pull_request_id: Optional[UUID] = Field(None, description="Pull Request ID (optional)")
    recommendation_run_id: Optional[UUID] = Field(None, description="Recommendation Run ID (optional)")
    created_by: Optional[str] = Field(None, description="User who created the suite")


class RegressionSuiteUpdate(BaseModel):
    """Schema for updating a RegressionSuite."""
    name: Optional[str] = Field(None, description="Suite name")
    description: Optional[str] = Field(None, description="Suite description")
    suite_type: Optional[str] = Field(None, description="Type of suite")
    status: Optional[str] = Field(None, description="Suite status")
    confidence_level: Optional[str] = Field(None, description="Confidence level")
    scope_score: Optional[float] = Field(None, description="Scope score")
    is_active: Optional[bool] = Field(None, description="Active flag")


class RegressionSuiteResponse(RegressionSuiteBase):
    """Schema for RegressionSuite response."""
    id: UUID
    repository_id: UUID
    release_id: Optional[UUID]
    pull_request_id: Optional[UUID]
    recommendation_run_id: Optional[UUID]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class RegressionSuiteDetailResponse(BaseModel):
    """Detailed response for RegressionSuite with scope item counts."""
    id: UUID
    repository_id: UUID
    release_id: Optional[UUID]
    pull_request_id: Optional[UUID]
    recommendation_run_id: Optional[UUID]
    name: str
    description: Optional[str]
    suite_type: str
    status: str
    confidence_level: Optional[str]
    scope_score: Optional[float]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    scope_items_count: int

    class Config:
        from_attributes = True


class RegressionSuiteSummaryResponse(BaseModel):
    """Summary response for RegressionSuite with tier/type counts."""
    suite_id: str
    name: str
    suite_type: str
    status: str
    total_scope_items: int
    tier_counts: Dict[str, int]
    type_counts: Dict[str, int]
    created_at: Optional[str]


class RegressionScopeItemResponse(BaseModel):
    """Response for a single scope item."""
    id: UUID
    regression_suite_id: UUID
    test_case_id: Optional[UUID]
    external_test_case_id: Optional[UUID]
    suggested_scenario_id: Optional[UUID]
    behavior_id: Optional[UUID]
    journey_id: Optional[UUID]
    acceptance_criterion_id: Optional[UUID]
    item_type: str
    tier: str
    priority: str
    selection_reason: Optional[str]
    evidence_summary: Optional[Dict[str, Any]]
    execution_status: str
    coverage_status: Optional[str]
    is_excluded: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RegressionScopeGroupedResponse(BaseModel):
    """Response for scope items grouped by tier."""
    suite_id: str
    total_items: int
    grouped_by_tier: Dict[str, List[Dict[str, Any]]]
    all_items: List[Dict[str, Any]]


class RegressionScopeUpdateRequest(BaseModel):
    """Request for updating a scope item."""
    tier: Optional[str] = Field(None, description="New tier")
    priority: Optional[str] = Field(None, description="New priority")
    is_excluded: Optional[bool] = Field(None, description="Exclusion flag")
    execution_status: Optional[str] = Field(None, description="Execution status")
    reason: Optional[str] = Field(None, description="Reason for change (required for tier/exclusion)")
