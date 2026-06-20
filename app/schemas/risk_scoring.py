"""
Risk Scoring Schemas for Phase 3.0

Pydantic schemas for risk score API responses and requests.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class RiskScoreResponse(BaseModel):
    """Risk score response for a requirement or gap."""
    riskScore: int = Field(..., ge=0, le=100, description="Risk score from 0-100")
    riskScoreReason: str = Field(..., description="Human-readable explanation of risk score")
    riskBand: str = Field(..., description="Risk band: CRITICAL, HIGH, MEDIUM, LOW")


class RequirementRiskRequest(BaseModel):
    """Request to calculate risk score for a requirement."""
    business_risk: str = Field(..., description="Business risk level: CRITICAL, HIGH, MEDIUM, LOW")
    coverage_status: str = Field(..., description="Coverage status: VERIFIED, PARTIAL, MISSING, FAILED, SKIPPED, NOT_RUN")
    criticality: str = Field(..., description="Requirement criticality: CRITICAL, HIGH, MEDIUM, LOW")
    requirement_type: str = Field(..., description="Requirement type: FUNCTIONAL, SECURITY, PERFORMANCE, COMPLIANCE, USER_EXPERIENCE")
    risk_review_adjustment: Optional[int] = Field(None, ge=-20, le=20, description="Manual adjustment from risk review (-20 to +20)")


class BatchRiskScoreRequest(BaseModel):
    """Request to calculate risk scores for multiple requirements."""
    requirements: list[RequirementRiskRequest] = Field(..., description="List of requirements to score")


class BatchRiskScoreResponse(BaseModel):
    """Response for batch risk score calculation."""
    results: list[Dict[str, Any]] = Field(..., description="List of risk score results with requirement IDs")


class RiskExplanationResponse(BaseModel):
    """Response with human-readable risk explanation."""
    explanation: str = Field(..., description="Human-readable explanation of risk score")
