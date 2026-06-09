"""
Test Asset API Schemas

Pydantic schemas for TestAsset model API requests and responses.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class TestPriority:
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TestType:
    UNIT = "UNIT"
    API = "API"
    INTEGRATION = "INTEGRATION"
    E2E = "E2E"
    UI = "UI"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    MANUAL = "MANUAL"
    SMOKE = "SMOKE"


class BusinessCriticality:
    MISSION_CRITICAL = "MISSION_CRITICAL"
    IMPORTANT = "IMPORTANT"
    SUPPORTING = "SUPPORTING"


class AutomationStatus:
    AUTOMATED = "AUTOMATED"
    MANUAL = "MANUAL"
    PARTIALLY_AUTOMATED = "PARTIALLY_AUTOMATED"
    UNKNOWN = "UNKNOWN"


class TestAssetBase(BaseModel):
    """Base schema for TestAsset."""
    stable_identity: Optional[str] = Field(None, description="Stable test identity")
    display_name: str = Field(..., description="Display name of the test")
    priority: str = Field(default=TestPriority.MEDIUM, description="Priority level")
    test_type: str = Field(default=TestType.UNIT, description="Type of test")
    business_criticality: str = Field(default=BusinessCriticality.SUPPORTING, description="Business criticality")
    automation_status: str = Field(default=AutomationStatus.UNKNOWN, description="Automation status")
    behavior_ids: Optional[List[str]] = Field(None, description="List of behavior IDs")
    journey_ids: Optional[List[str]] = Field(None, description="List of journey IDs")
    tags: Optional[Dict[str, Any]] = Field(None, description="Custom tags")


class TestAssetCreate(TestAssetBase):
    """Schema for creating a TestAsset."""
    repository_id: UUID = Field(..., description="Repository ID")
    test_case_id: Optional[UUID] = Field(None, description="Test Case ID (for automated tests)")
    external_test_case_id: Optional[UUID] = Field(None, description="External Test Case ID (for manual tests)")


class TestAssetUpdate(BaseModel):
    """Schema for updating a TestAsset."""
    stable_identity: Optional[str] = Field(None, description="Stable test identity")
    display_name: Optional[str] = Field(None, description="Display name of the test")
    priority: Optional[str] = Field(None, description="Priority level")
    test_type: Optional[str] = Field(None, description="Type of test")
    business_criticality: Optional[str] = Field(None, description="Business criticality")
    automation_status: Optional[str] = Field(None, description="Automation status")
    behavior_ids: Optional[List[str]] = Field(None, description="List of behavior IDs")
    journey_ids: Optional[List[str]] = Field(None, description="List of journey IDs")
    tags: Optional[Dict[str, Any]] = Field(None, description="Custom tags")


class TestAssetResponse(TestAssetBase):
    """Schema for TestAsset response."""
    id: UUID
    repository_id: UUID
    test_case_id: Optional[UUID]
    external_test_case_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
