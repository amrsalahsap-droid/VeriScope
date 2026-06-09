from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime


class BehaviorDiagnosticsSummary(BaseModel):
    """Summary of behavior discovery diagnostics."""
    total_behaviors: int
    high_confidence: int
    medium_confidence: int
    low_confidence: int
    evidence_sources: Dict[str, int]
    discovery_coverage: float  # Percentage of repository covered
    last_updated: datetime


class BehaviorDiagnosticsDetail(BaseModel):
    """Detailed diagnostics for a single behavior."""
    behavior_id: str
    behavior_name: str
    confidence: str
    evidence_count: int
    discovery_sources: List[str]
    confidence_breakdown: Optional[Dict[str, Any]] = None
    journey: Optional[str] = None
    risk_level: Optional[str] = None


class BehaviorDiagnosticsResponse(BaseModel):
    """Complete diagnostics response."""
    repository_id: str
    summary: BehaviorDiagnosticsSummary
    behaviors: List[BehaviorDiagnosticsDetail]
