"""
BehaviorFragilitySignal Schema

Output signal for behavior/journey-level fragility mapping.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID


class BehaviorFragilitySignal(BaseModel):
    """
    Signal representing fragility at behavior/journey level.
    
    Maps file/test/incident fragility to Behavior Catalog and Journey Catalog.
    """
    behavior_id: UUID = Field(..., description="ID of the affected behavior")
    journey_id: Optional[UUID] = Field(None, description="ID of the affected journey (if applicable)")
    scenario_id: Optional[UUID] = Field(None, description="ID of the affected scenario (if applicable)")
    
    signal_type: str = Field(..., description="Type of fragility signal")
    # REPEATED_TEST_FAILURE, FILE_FAILURE_HOTSPOT, ESCAPED_DEFECT, ROLLBACK, CO_FAILURE, MISSING_COVERAGE
    
    score: float = Field(..., ge=0.0, le=100.0, description="Fragility score (0-100)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence level (0-1)")
    
    evidence_event_ids: List[UUID] = Field(default_factory=list, description="IDs of supporting evidence events")
    
    reason: str = Field(..., description="Explanation of why this behavior is fragile")
    
    class Config:
        json_schema_extra = {
            "example": {
                "behavior_id": "uuid",
                "journey_id": "uuid",
                "scenario_id": None,
                "signal_type": "ESCAPED_DEFECT",
                "score": 85.0,
                "confidence": 0.9,
                "evidence_event_ids": ["uuid1", "uuid2"],
                "reason": "Previous escaped defect related to password reset behavior"
            }
        }
