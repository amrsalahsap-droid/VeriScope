"""Business context schemas for business understanding annotations."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BusinessContext(BaseModel):
    """Business context annotation for requirements and scope items."""
    capability: Optional[str] = None
    userJourney: Optional[str] = None
    actor: Optional[str] = None
    businessAction: Optional[str] = None
    protectedOutcome: Optional[str] = None
    failureMode: Optional[str] = None
    userImpact: Optional[str] = None
    businessImpact: Optional[str] = None
    riskLevel: Optional[str] = None
    riskReasons: List[str] = Field(default_factory=list)
    priority: Optional[str] = None
    confidence: Optional[str] = None
    evidenceReferences: List[str] = Field(default_factory=list)
    derivedFrom: List[str] = Field(default_factory=list)
    matchedSemanticSignals: List[str] = Field(default_factory=list)
    triggeredRule: Optional[str] = None
    riskOrigin: Optional[str] = None
    isDeterministic: bool = False
    whatWouldLowerRisk: Optional[str] = None
    whatWouldMakeReleaseSafe: Optional[str] = None


class BusinessRiskSummary(BaseModel):
    """Summary of business risks in the current state."""
    critical_gaps: int = 0
    high_gaps: int = 0
    medium_gaps: int = 0
    low_gaps: int = 0
    unknown_gaps: int = 0
    summary_text: Optional[str] = None
