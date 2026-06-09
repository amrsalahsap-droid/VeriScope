"""Detailed Readiness Assessment Schemas for Frontend API."""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.schemas.readiness import ReadinessSignal, NextBestAction, ReadinessAssessmentResponse

# Re-use or define aliases for backwards compatibility
class SignalStatus(str):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"

class SignalSeverity(str):
    REQUIRED = "REQUIRED"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"

class ActionPriority(str):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class AvailableSignal(BaseModel):
    key: str
    label: str
    status: str
    impact: str
    confidence_contribution: int

class MissingSignal(BaseModel):
    key: str
    label: str
    severity: str
    impact: str
    estimated_confidence_gain: int
    actions: List[str]

class RecommendedAction(BaseModel):
    action: str
    label: str
    priority: str
    estimated_confidence_gain: int

# Update DetailedReadinessResponse to have the exact Phase 1B response shape
class DetailedReadinessResponse(ReadinessAssessmentResponse):
    available_signals: List[AvailableSignal] = []
    missing_signals: List[MissingSignal] = []
    recommended_actions: List[RecommendedAction] = []
