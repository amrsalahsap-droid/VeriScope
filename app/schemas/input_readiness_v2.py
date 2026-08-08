"""Input Readiness V2 Schemas - 12-Input Contract for Recommendation Readiness."""
from typing import List, Dict, Any
from pydantic import BaseModel, Field


INPUT_WEIGHTS = {
    "INPUT_1":  10.0,
    "INPUT_2":  20.0,
    "INPUT_3":  10.0,
    "INPUT_4":  12.0,
    "INPUT_5":  15.0,
    "INPUT_6":  15.0,
    "INPUT_7":   8.0,
    "INPUT_8":   3.0,
    "INPUT_9":   3.0,
    "INPUT_10":  2.0,
    "INPUT_11":  1.0,
    "INPUT_12":  1.0,
}

HARD_BLOCKER_INPUTS = {"INPUT_1", "INPUT_2", "INPUT_4", "INPUT_5", "INPUT_6"}

INPUT_LABELS = {
    "INPUT_1":  "PR Change Package",
    "INPUT_2":  "Business Requirements",
    "INPUT_3":  "Product Behavior Map",
    "INPUT_4":  "Test Case Inventory",
    "INPUT_5":  "AC → Test Mapping",
    "INPUT_6":  "Current PR Test Results",
    "INPUT_7":  "Test Coverage Mapping",
    "INPUT_8":  "Release Context",
    "INPUT_9":  "Environment Support Matrix",
    "INPUT_10": "Quality Gate Profile",
    "INPUT_11": "Known Defects / Accepted Risks",
    "INPUT_12": "Out-of-Scope Declaration",
}


class InputReadinessAction(BaseModel):
    label: str
    action: str


class InputReadinessBlocker(BaseModel):
    input_id: str
    code: str
    message: str


class InputReadinessWarning(BaseModel):
    input_id: str
    code: str
    message: str


class InputReadinessItem(BaseModel):
    input_id: str
    label: str
    status: str
    weight: float
    earned_score: float
    max_score: float
    is_hard_blocker: bool
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    actions: List[InputReadinessAction] = Field(default_factory=list)
    # Confidence contract: separate numeric score and text label
    confidence_score: float | None = Field(default=None, description="Numeric confidence score (0-1)")
    confidence_label: str | None = Field(default=None, description="Text confidence label (HIGH, MODERATE, LOW, NONE)")


class NextBestAction(BaseModel):
    priority: int
    input_id: str
    label: str
    reason: str


class InputReadinessV2Response(BaseModel):
    generation_status: str
    can_generate: str
    confident_generation: bool
    confidence_score: float
    confidence_level: str
    confidence_ceiling: str
    primary_message: str
    blockers: List[InputReadinessBlocker] = Field(default_factory=list)
    warnings: List[InputReadinessWarning] = Field(default_factory=list)
    inputs: List[InputReadinessItem] = Field(default_factory=list)
    next_best_actions: List[NextBestAction] = Field(default_factory=list)

    # Strict 12-input response fields
    can_generate_draft: bool = True
    can_generate_confident: bool = False
    blocking_inputs: List[str] = Field(default_factory=list)
    partial_inputs: List[str] = Field(default_factory=list)
    review_needed_inputs: List[str] = Field(default_factory=list)
    missing_confidence_boosters: List[str] = Field(default_factory=list)
    primary_reason: str = ""

    # Separate confidence concepts
    evidence_completeness: float = Field(description="Numeric completeness/progress signal (0-100)")
    release_confidence: str = Field(description="Whether the recommendation can be trusted for release decisions")
    confidence_ceiling_reason: str = Field(description="Reason for confidence ceiling limitation")

