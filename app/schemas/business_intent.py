"""Business Intent Coverage Matrix schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
from uuid import UUID


class BusinessIntentCoverageMatrixRow(BaseModel):
    """Single row in the business intent coverage matrix."""
    
    business_intent_id: Optional[str] = Field(None, description="ID of the business intent (if applicable)")
    acceptance_criterion_id: Optional[str] = Field(None, description="ID of the acceptance criterion")
    business_intent_text: Optional[str] = Field(None, description="Text of the business intent or AC")
    affected_behavior_id: Optional[str] = Field(None, description="ID of the affected behavior")
    affected_behavior_name: Optional[str] = Field(None, description="Name of the affected behavior")
    affected_journey_id: Optional[str] = Field(None, description="ID of the affected journey")
    affected_journey_name: Optional[str] = Field(None, description="Name of the affected journey")
    existing_test_coverage: List[str] = Field(default_factory=list, description="List of existing test IDs covering this intent")
    suggested_scenario_id: Optional[str] = Field(None, description="ID of suggested scenario if coverage missing")
    suggested_scenario_title: Optional[str] = Field(None, description="Title of suggested scenario")
    current_pr_execution_status: str = Field(default="NOT_EXECUTED", description="Execution status on current PR: EXECUTED, NOT_EXECUTED, UNKNOWN")
    status: str = Field(..., description="Overall status: COVERED, PARTIALLY_COVERED, MISSING, VERIFIED, UNKNOWN")
    recommended_action: str = Field(..., description="Recommended action: RUN_EXISTING_TEST, ADD_AUTOMATED_TEST, EXECUTE_MANUAL_VALIDATION, ALREADY_VERIFIED, CLARIFY_REQUIREMENT")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in coverage assessment")
    reason: Optional[str] = Field(None, description="Reason for the status and recommended action")
    
    class Config:
        json_schema_extra = {
            "example": {
                "business_intent_id": None,
                "acceptance_criterion_id": "123e4567-e89b-12d3-a456-426614174000",
                "business_intent_text": "User must be able to reset password",
                "affected_behavior_id": "456e7890-e12b-34d5-a678-426614174111",
                "affected_behavior_name": "Password Reset",
                "affected_journey_id": "789e0123-e34b-56d7-a890-426614174222",
                "affected_journey_name": "Authentication",
                "existing_test_coverage": ["test_1", "test_2"],
                "suggested_scenario_id": None,
                "suggested_scenario_title": None,
                "current_pr_execution_status": "NOT_EXECUTED",
                "status": "COVERED",
                "recommended_action": "RUN_EXISTING_TEST",
                "confidence": 0.8,
                "reason": "Covered by existing tests but not executed on current PR"
            }
        }


class BusinessIntentCoverageMatrix(BaseModel):
    """Complete business intent coverage matrix."""
    
    rows: List[BusinessIntentCoverageMatrixRow]
    total_intents: int
    covered: int
    partially_covered: int
    missing: int
    verified: int
    unknown: int
    has_business_intent: bool = Field(..., description="Whether the PR has business intent or AC")
    confidence_impact: str = Field(default="NONE", description="Impact on recommendation confidence: NONE, REDUCED, SIGNIFICANTLY_REDUCED")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "rows": [],
                "total_intents": 5,
                "covered": 2,
                "partially_covered": 1,
                "missing": 2,
                "verified": 0,
                "unknown": 0,
                "has_business_intent": True,
                "confidence_impact": "NONE",
                "generated_at": "2024-01-01T00:00:00Z"
            }
        }


# Business Intent Override Schemas

class BusinessIntentOverrideCreate(BaseModel):
    """Schema for creating a business intent override."""
    
    repository_id: UUID = Field(..., description="Repository ID")
    pull_request_id: Optional[UUID] = Field(None, description="Pull Request ID (optional)")
    recommendation_run_id: Optional[UUID] = Field(None, description="Recommendation Run ID (optional)")
    
    business_change_summary: str = Field(..., min_length=1, description="Business change summary")
    affected_users_journeys: Optional[str] = Field(None, description="Affected users/journeys (comma-separated)")
    acceptance_criteria: str = Field(..., min_length=1, description="Acceptance criteria text")
    risk_notes: Optional[str] = Field(None, description="Risk notes (optional)")
    testing_notes: Optional[str] = Field(None, description="Testing notes (optional)")
    
    source: str = Field(default="manual_paste", description="Source of the override")
    created_by: Optional[str] = Field(None, description="User who created the override")


class BusinessIntentOverrideResponse(BaseModel):
    """Schema for business intent override response."""
    
    id: UUID
    repository_id: UUID
    pull_request_id: Optional[UUID]
    recommendation_run_id: Optional[UUID]
    
    business_change_summary: str
    affected_users_journeys: Optional[str]
    acceptance_criteria: str
    risk_notes: Optional[str]
    testing_notes: Optional[str]
    
    # Processing results
    extracted_scenarios: Optional[List[Dict[str, Any]]]
    mapped_behaviors: Optional[List[Dict[str, Any]]]
    extraction_confidence: Optional[str]
    
    # Metadata
    source: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    
    # Status
    is_active: bool
    is_processed: bool
    
    class Config:
        from_attributes = True


class AcceptanceCriteriaExtractionResponse(BaseModel):
    """Schema for acceptance criteria extraction results."""
    
    scenarios: List[Dict[str, Any]]
    total_scenarios: int
    high_confidence_scenarios: int
    medium_confidence_scenarios: int
    low_confidence_scenarios: int
    processing_time_ms: Optional[int]


class BusinessBehaviorMappingResponse(BaseModel):
    """Schema for business behavior mapping results."""
    
    behaviors: List[Dict[str, Any]]
    total_behaviors: int
    high_confidence_behaviors: int
    medium_confidence_behaviors: int
    low_confidence_behaviors: int
    processing_time_ms: Optional[int]


class BusinessIntentProcessingResponse(BaseModel):
    """Schema for complete business intent processing response."""
    
    override: BusinessIntentOverrideResponse
    extraction: AcceptanceCriteriaExtractionResponse
    mapping: BusinessBehaviorMappingResponse
    readiness_updated: bool
    new_readiness_score: Optional[int]
    confidence_improvement: Optional[str]
    processing_time_ms: Optional[int]
