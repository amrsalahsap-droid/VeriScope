"""Schemas for Manual Test ↔ Acceptance Criteria Mapping."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class ManualTestMappingCreate(BaseModel):
    """Schema for creating a manual test to AC mapping."""
    acceptanceCriterionId: str = Field(..., description="ID, source number (e.g. AC-12), or label of the Acceptance Criterion to map")


class ManualTestMappingResponse(BaseModel):
    """Schema for manual test mapping response."""
    id: UUID
    testCaseId: UUID
    acceptanceCriterionId: UUID
    readableRequirementId: str
    requirementText: str
    mappingSource: str
    createdAt: datetime
