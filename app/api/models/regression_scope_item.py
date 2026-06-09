"""
Regression Scope Item API Schemas

Pydantic schemas for RegressionScopeItem model API requests and responses.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class ScopeItemType:
    AUTOMATED_TEST = "AUTOMATED_TEST"
    MANUAL_TEST = "MANUAL_TEST"
    SUGGESTED_SCENARIO = "SUGGESTED_SCENARIO"
    COVERAGE_GAP = "COVERAGE_GAP"


class ScopeTier:
    MUST_RUN = "MUST_RUN"
    SHOULD_RUN = "SHOULD_RUN"
    OPTIONAL = "OPTIONAL"


class ScopePriority:
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ExecutionStatus:
    NOT_RUN = "NOT_RUN"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    MANUAL_PENDING = "MANUAL_PENDING"
    UNKNOWN = "UNKNOWN"


class RegressionScopeItemBase(BaseModel):
    """Base schema for RegressionScopeItem."""
    item_type: str = Field(..., description="Type of scope item")
    tier: str = Field(default=ScopeTier.SHOULD_RUN, description="Tier of the item")
    priority: str = Field(default=ScopePriority.MEDIUM, description="Priority of the item")
    selection_reason: Optional[str] = Field(None, description="Reason for selection")
    evidence_summary: Optional[Dict[str, Any]] = Field(None, description="Evidence summary")
    execution_status: str = Field(default=ExecutionStatus.NOT_RUN, description="Execution status")
    coverage_status: Optional[str] = Field(None, description="Coverage status")
    is_excluded: bool = Field(default=False, description="Exclusion flag")


class RegressionScopeItemCreate(RegressionScopeItemBase):
    """Schema for creating a RegressionScopeItem."""
    regression_suite_id: UUID = Field(..., description="Regression Suite ID")
    test_case_id: Optional[UUID] = Field(None, description="Test Case ID (for automated tests)")
    external_test_case_id: Optional[UUID] = Field(None, description="External Test Case ID (for manual tests)")
    suggested_scenario_id: Optional[UUID] = Field(None, description="Suggested Scenario ID")
    behavior_id: Optional[UUID] = Field(None, description="Behavior ID")
    journey_id: Optional[UUID] = Field(None, description="Journey ID")
    acceptance_criterion_id: Optional[UUID] = Field(None, description="Acceptance Criterion ID")


class RegressionScopeItemUpdate(BaseModel):
    """Schema for updating a RegressionScopeItem."""
    tier: Optional[str] = Field(None, description="Tier of the item")
    priority: Optional[str] = Field(None, description="Priority of the item")
    selection_reason: Optional[str] = Field(None, description="Reason for selection")
    evidence_summary: Optional[Dict[str, Any]] = Field(None, description="Evidence summary")
    execution_status: Optional[str] = Field(None, description="Execution status")
    coverage_status: Optional[str] = Field(None, description="Coverage status")
    is_excluded: Optional[bool] = Field(None, description="Exclusion flag")


class RegressionScopeItemResponse(RegressionScopeItemBase):
    """Schema for RegressionScopeItem response."""
    id: UUID
    regression_suite_id: UUID
    test_case_id: Optional[UUID]
    external_test_case_id: Optional[UUID]
    suggested_scenario_id: Optional[UUID]
    behavior_id: Optional[UUID]
    journey_id: Optional[UUID]
    acceptance_criterion_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
