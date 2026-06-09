"""
Scope Override API Schemas

Pydantic schemas for ScopeOverride model API requests and responses.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class OverrideType:
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    TIER_CHANGED = "TIER_CHANGED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    MARKED_REQUIRED = "MARKED_REQUIRED"
    MARKED_OPTIONAL = "MARKED_OPTIONAL"
    EXCLUDED = "EXCLUDED"
    RESTORED = "RESTORED"


class ScopeOverrideCreate(BaseModel):
    """Schema for creating a ScopeOverride."""
    regression_scope_item_id: UUID = Field(..., description="Regression Scope Item ID")
    regression_suite_id: UUID = Field(..., description="Regression Suite ID")
    override_type: str = Field(..., description="Type of override")
    original_value: Optional[Dict[str, Any]] = Field(None, description="Original value before override")
    new_value: Optional[Dict[str, Any]] = Field(None, description="New value after override")
    reason: str = Field(..., description="Reason for override (required)")
    overridden_by: Optional[str] = Field(None, description="User who made the override")


class ScopeOverrideResponse(BaseModel):
    """Schema for ScopeOverride response."""
    id: UUID
    regression_scope_item_id: UUID
    regression_suite_id: UUID
    override_type: str
    original_value: Optional[Dict[str, Any]]
    new_value: Optional[Dict[str, Any]]
    reason: str
    overridden_by: Optional[str]
    overridden_at: datetime

    class Config:
        from_attributes = True
