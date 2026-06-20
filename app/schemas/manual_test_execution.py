"""Manual Test Execution Schemas."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class ManualTestExecutionCreate(BaseModel):
    """Request schema for creating a manual test execution."""
    outcome: str = Field(..., description="Outcome of the manual execution. Must be one of: PASSED, FAILED, SKIPPED, BLOCKED")
    notes: Optional[str] = Field(None, description="Optional notes detailing the execution outcome")
    evidenceUrl: Optional[str] = Field(None, description="Optional URL pointing to execution evidence (e.g. Jira link, cloud screenshot)")
    attachmentPath: Optional[str] = Field(None, description="Optional file path to screenshot/evidence attachment")
    recommendationRunId: Optional[str] = Field(None, description="Optional recommendation run ID associated with the execution")
    pullRequestId: Optional[str] = Field(None, description="Optional pull request ID associated with the execution")

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, v: str) -> str:
        valid_outcomes = {"PASSED", "FAILED", "SKIPPED", "BLOCKED"}
        v_upper = v.upper().strip()
        if v_upper not in valid_outcomes:
            raise ValueError(f"Invalid outcome: '{v}'. Must be one of: {', '.join(valid_outcomes)}")
        return v_upper


class ManualTestExecutionDetail(BaseModel):
    """Schema for individual manual test execution response data."""
    id: str
    testId: str
    outcome: str
    executedByName: Optional[str] = None
    executedAt: str
    notes: Optional[str] = None
    evidenceUrl: Optional[str] = None


class ManualTestExecutionResponse(BaseModel):
    """Wrapper response schema for execution POST success."""
    status: str = "SUCCESS"
    execution: ManualTestExecutionDetail
