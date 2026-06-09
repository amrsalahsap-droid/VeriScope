"""
Release API Schemas

Pydantic schemas for Release model API requests and responses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID


class ReleaseType:
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    PATCH = "PATCH"
    HOTFIX = "HOTFIX"
    CUSTOM = "CUSTOM"


class ReleaseStatus:
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    READY_FOR_SIGNOFF = "READY_FOR_SIGNOFF"
    RELEASED = "RELEASED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class ReleaseBase(BaseModel):
    """Base schema for Release."""
    version: str = Field(..., description="Release version (e.g., v1.2.0)")
    release_type: str = Field(default=ReleaseType.MINOR, description="Type of release")
    status: str = Field(default=ReleaseStatus.PLANNED, description="Release status")
    planned_date: Optional[datetime] = Field(None, description="Planned release date")
    actual_date: Optional[datetime] = Field(None, description="Actual release date")
    release_notes: Optional[str] = Field(None, description="Release notes")


class ReleaseCreate(ReleaseBase):
    """Schema for creating a Release."""
    repository_id: UUID = Field(..., description="Repository ID")
    created_by: Optional[str] = Field(None, description="User who created the release")


class ReleaseUpdate(BaseModel):
    """Schema for updating a Release."""
    version: Optional[str] = Field(None, description="Release version")
    release_type: Optional[str] = Field(None, description="Type of release")
    status: Optional[str] = Field(None, description="Release status")
    planned_date: Optional[datetime] = Field(None, description="Planned release date")
    actual_date: Optional[datetime] = Field(None, description="Actual release date")
    release_notes: Optional[str] = Field(None, description="Release notes")


class ReleaseResponse(ReleaseBase):
    """Schema for Release response."""
    id: UUID
    repository_id: UUID
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
