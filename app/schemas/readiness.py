"""Recommendation Readiness Schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class ReadinessLevelEnum(str, Enum):
    CONNECTED = "CONNECTED"
    EVIDENCE_READY = "EVIDENCE_READY"
    RECOMMENDATION_READY = "RECOMMENDATION_READY"
    HIGH_CONFIDENCE_READY = "HIGH_CONFIDENCE_READY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    MINIMUM_READY = "MINIMUM_READY"
    REGRESSION_READY = "REGRESSION_READY"

class ExpectedConfidenceEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class SignalTypeEnum(str, Enum):
    source_code = "source_code"
    pull_request_diff = "pull_request_diff"
    junit_test_history = "junit_test_history"
    test_history = "test_history"
    coverage_report = "coverage_report"
    architecture_graph = "architecture_graph"
    behavior_catalog = "behavior_catalog"
    journey_catalog = "journey_catalog"
    acceptance_criteria = "acceptance_criteria"
    linked_work_item = "linked_work_item"
    managed_manual_tests = "managed_manual_tests"
    historical_outcomes = "historical_outcomes"
    fragility_memory = "fragility_memory"
    current_pr_execution = "current_pr_execution"
    github_connection = "github_connection"
    webhook_activity = "webhook_activity"
    current_pr_coverage = "current_pr_coverage"
    business_intent = "business_intent"

class ReadinessSignal(BaseModel):
    key: str
    status: str
    evidence_count: int
    linked_to_current_pr: bool
    explanation: str
    estimated_confidence_gain: Optional[float] = 0.0
    impact: Optional[str] = None
    action: Optional[str] = None

class NextBestAction(BaseModel):
    key: str
    impact: str
    action: str

class ReadinessAssessmentResponse(BaseModel):
    """Response model for readiness assessment."""
    id: Optional[str] = None
    repository_id: str
    pull_request_id: Optional[str] = None
    readiness_level: str
    expected_confidence: str
    readiness_score: float = Field(ge=0.0, le=1.0, description="Readiness score from 0.0 to 1.0")
    available_signals: List[str] = []
    missing_signals: List[str] = []
    blocking_gaps: List[str] = []
    optional_gaps: List[str] = []
    recommended_actions: List[str] = []
    confidence_impact_summary: str = ""
    can_generate: bool
    can_generate_reason: str = ""
    created_at: Optional[datetime] = None

    # New fields for Phase 1B
    intelligence_completeness_score: int
    release_confidence_ceiling: str
    available_inputs: List[ReadinessSignal]
    missing_inputs: List[ReadinessSignal]
    recommended_inputs: List[ReadinessSignal]
    blocking_inputs: List[ReadinessSignal]
    next_best_actions: List[NextBestAction]
    primary_message: str
    secondary_message: str

    # Confidence explanation fields
    confidence_reason: str = ""
    confidence_ceiling: str = "HIGH"
    confidence_blockers: List[str] = []
    confidence_limiters: List[ReadinessSignal] = []

    class Config:
        from_attributes = True

class ReadinessAssessmentCreate(BaseModel):
    """Request model for creating readiness assessment."""
    repository_id: str
    pull_request_id: Optional[str] = None

class ReadinessSummaryResponse(BaseModel):
    """Summary response for readiness status."""
    repository_id: str
    pull_request_id: Optional[str] = None
    readiness_level: str
    expected_confidence: str
    readiness_score: float
    can_generate: bool
    can_generate_reason: str = ""
    signal_count: int = Field(description="Number of available signals", default=0)
    total_signals: int = Field(description="Total possible signals", default=15)

    # New fields for Phase 1B
    intelligence_completeness_score: int
    release_confidence_ceiling: str
    available_inputs: List[ReadinessSignal]
    missing_inputs: List[ReadinessSignal]
    recommended_inputs: List[ReadinessSignal]
    blocking_inputs: List[ReadinessSignal]
    next_best_actions: List[NextBestAction]
    primary_message: str
    secondary_message: str

    # Confidence explanation fields
    confidence_reason: str = ""
    confidence_ceiling: str = "HIGH"
    confidence_blockers: List[str] = []
    confidence_limiters: List[ReadinessSignal] = []

    class Config:
        from_attributes = True


class AvailableInputSignal(BaseModel):
    key: str
    label: str
    status: str
    source: str
    confidence_contribution: float
    description: str
    evidence_count: int
    linked_to_current_pr: bool


class MissingInputSignal(BaseModel):
    key: str
    label: str
    severity: str
    impact: str
    estimated_confidence_gain: float
    action_key: str
    action_label: str


class RecommendationReadinessGateResult(BaseModel):
    repository_id: str
    pull_request_id: Optional[str] = None
    recommendation_run_id: Optional[str] = None
    can_generate: bool
    can_view_existing: bool
    readiness_level: str
    expected_confidence: str
    intelligence_completeness_score: int
    release_confidence_ceiling: str
    available_inputs: List[AvailableInputSignal] = []
    missing_inputs: List[MissingInputSignal] = []
    blocking_inputs: List[MissingInputSignal] = []
    recommended_inputs: List[MissingInputSignal] = []
    optional_inputs: List[MissingInputSignal] = []
    next_best_actions: List[NextBestAction] = []
    user_message: str
    technical_reason: str
    created_at: datetime

    # Confidence explanation fields
    confidence_reason: str = ""
    confidence_ceiling: str = "HIGH"
    confidence_blockers: List[str] = []
    confidence_limiters: List[MissingInputSignal] = []

    class Config:
        from_attributes = True


class ReadinessAcknowledgementDecision(str, Enum):
    CONTINUE_ANYWAY = "CONTINUE_ANYWAY"
    IMPROVE_INPUTS_FIRST = "IMPROVE_INPUTS_FIRST"


class ReadinessAcknowledgementCreate(BaseModel):
    acknowledged_missing_inputs: List[str]
    decision: ReadinessAcknowledgementDecision
    note: Optional[str] = None


class RecommendationReadinessGateResponse(BaseModel):
    can_generate: bool
    readiness_level: str
    expected_confidence: str
    intelligence_completeness_score: int
    release_confidence_ceiling: str
    available_inputs: List[AvailableInputSignal] = []
    missing_inputs: List[MissingInputSignal] = []
    next_best_actions: List[NextBestAction] = []
    primary_message: str
    secondary_message: str
    created_at: datetime

    # Confidence explanation fields
    confidence_reason: str = ""
    confidence_ceiling: str = "HIGH"
    confidence_blockers: List[str] = []
    confidence_limiters: List[MissingInputSignal] = []

    class Config:
        from_attributes = True

