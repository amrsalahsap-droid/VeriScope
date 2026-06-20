"""
Regression Recommendation Schemas for Phase 3.2

Pydantic schemas for regression recommendation API responses and requests.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class RegressionCategoryResponse(BaseModel):
    """Regression category response for a requirement."""
    category: str = Field(..., description="Regression category: REQUIRED, RECOMMENDED, OPTIONAL, SAFE_TO_SKIP")
    reason: str = Field(..., description="Human-readable explanation of category")
    factors: List[str] = Field(default_factory=list, description="List of factors contributing to category")


class RegressionRequirementRequest(BaseModel):
    """Request to calculate regression category for a requirement."""
    requirement_id: str = Field(..., description="Requirement ID")
    coverage_bucket: str = Field(..., description="Original coverage bucket: COVERED, PARTIAL, MISSING, TRACEABILITY")
    risk_score: int = Field(..., description="Risk score from Phase 3.0 (0-100)")
    risk_band: str = Field(..., description="Risk band from Phase 3.0: CRITICAL, HIGH, MEDIUM, LOW")
    change_impact_level: str = Field(..., description="Change impact level from Phase 3.1: DIRECT, RELATED, INDIRECT, NONE")
    is_verified: bool = Field(default=False, description="Whether the requirement is verified by current PR execution")


class RegressionRecommendationRequest(BaseModel):
    """Request to generate regression recommendations."""
    requirements: List[RegressionRequirementRequest] = Field(..., description="List of requirements to categorize")


class RegressionRecommendationResponse(BaseModel):
    """Response for regression recommendations."""
    requiredItems: List[Dict[str, Any]] = Field(default_factory=list, description="Items in REQUIRED category")
    recommendedItems: List[Dict[str, Any]] = Field(default_factory=list, description="Items in RECOMMENDED category")
    optionalItems: List[Dict[str, Any]] = Field(default_factory=list, description="Items in OPTIONAL category")
    safeToSkipItems: List[Dict[str, Any]] = Field(default_factory=list, description="Items in SAFE_TO_SKIP category")


class RegressionSummaryResponse(BaseModel):
    """Response with regression recommendation summary."""
    required: int = Field(..., description="Count of REQUIRED items")
    recommended: int = Field(..., description="Count of RECOMMENDED items")
    optional: int = Field(..., description="Count of OPTIONAL items")
    safeToSkip: int = Field(..., description="Count of SAFE_TO_SKIP items")
    total: int = Field(..., description="Total count of all items")


class RegressionOptimizationRequest(BaseModel):
    """Request to optimize regression scope."""
    currentScope: List[Dict[str, Any]] = Field(..., description="Current regression scope items")
    recommendations: RegressionRecommendationResponse = Field(..., description="Generated regression recommendations")


class RegressionOptimizationResponse(BaseModel):
    """Response for regression scope optimization."""
    optimizedScope: List[Dict[str, Any]] = Field(..., description="Optimized regression scope")
    additions: List[Dict[str, Any]] = Field(..., description="Items to add to scope")
    removals: List[Dict[str, Any]] = Field(..., description="Items to remove from scope")
    optimizationSummary: Dict[str, int] = Field(..., description="Summary of optimization changes")
