"""Pydantic schemas for MappingCandidate evidence model."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class SemanticBestMatchSchema(BaseModel):
    ac_ref: Optional[str] = None
    ac_text: Optional[str] = None
    score: float = 0.0


class FlowEvidenceSchema(BaseModel):
    test_flow: Optional[str] = ""
    declared_ac_flow: Optional[str] = ""
    semantic_match_flow: Optional[str] = ""
    flow_match: bool = False


class DecisionSchema(BaseModel):
    status: str
    confidence: float = 0.0
    reason: str = ""


class MappingCandidateEvidenceJson(BaseModel):
    declared_ref: Optional[str] = None
    declared_ref_exists: bool = False
    declared_ac_text: Optional[str] = None
    test_name: str = ""
    test_title: Optional[str] = ""
    classname: Optional[str] = ""
    semantic_best_match: SemanticBestMatchSchema = Field(default_factory=SemanticBestMatchSchema)
    flow_evidence: FlowEvidenceSchema = Field(default_factory=FlowEvidenceSchema)
    decision: DecisionSchema = Field(..., description="Status, confidence score, and rationale for candidate decision")


class MappingCandidateSchema(BaseModel):
    """Pydantic schema for MappingCandidate evidence model."""
    __test__ = False

    id: str
    repository_id: str
    pull_request_id: Optional[str] = None
    test_case_id: str
    acceptance_criterion_id: Optional[str] = None

    declared_ac_ref: Optional[str] = None
    declared_ac_text_snapshot: Optional[str] = None
    semantic_best_match_ac_id: Optional[str] = None
    semantic_best_match_score: float = 0.0

    candidate_source: str
    confidence_score: float = 0.0
    confidence_label: Optional[str] = None

    review_status: str = Field(
        ...,
        description="VERIFIED | SUGGESTED_STRONG | SUGGESTED_WEAK | CONFLICTED | AMBIGUOUS | UNRESOLVED | USER_CONFIRMED | USER_REJECTED"
    )

    conflict_detected: bool = False
    conflict_type: Optional[str] = None
    conflict_reason: Optional[str] = None

    evidence_json: Dict[str, Any] = Field(default_factory=dict)

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
