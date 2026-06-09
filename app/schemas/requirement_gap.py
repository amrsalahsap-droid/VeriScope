"""Requirement Gap schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class RequirementGap(BaseModel):
    """Represents a gap in business intent or requirements."""
    
    severity: str = Field(..., description="Severity: CRITICAL, HIGH, MEDIUM, LOW")
    gap_type: str = Field(
        ...,
        description="Gap type: MISSING_PR_DESCRIPTION, MISSING_ACCEPTANCE_CRITERIA, VAGUE_REQUIREMENT, UNMAPPED_BUSINESS_BEHAVIOR, UNTESTED_ACCEPTANCE_CRITERION"
    )
    message: str = Field(..., description="Human-readable description of the gap")
    impact: str = Field(..., description="Impact of the gap on recommendation quality")
    recommended_action: str = Field(..., description="Suggested action to resolve the gap")
    
    class Config:
        json_schema_extra = {
            "example": {
                "severity": "HIGH",
                "gap_type": "MISSING_ACCEPTANCE_CRITERIA",
                "message": "PR has no acceptance criteria defined",
                "impact": "Cannot validate business intent, recommendation confidence reduced",
                "recommended_action": "Add acceptance criteria to PR description or link to a story with criteria"
            }
        }


class RequirementGapReport(BaseModel):
    """Complete report of requirement gaps."""
    
    gaps: List[RequirementGap]
    total_gaps: int
    critical_gaps: int
    high_gaps: int
    medium_gaps: int
    low_gaps: int
    has_critical_gaps: bool
    overall_trust_level: str = Field(..., description="Overall trust level: HIGH, MEDIUM, LOW, VERY_LOW")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "gaps": [],
                "total_gaps": 0,
                "critical_gaps": 0,
                "high_gaps": 2,
                "medium_gaps": 1,
                "low_gaps": 0,
                "has_critical_gaps": False,
                "overall_trust_level": "MEDIUM",
                "generated_at": "2024-01-01T00:00:00Z"
            }
        }
