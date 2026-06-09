from datetime import datetime
from uuid import UUID
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class FragilityPatternListItem(BaseModel):
    pattern_id: UUID
    pattern_type: str
    normalized_pattern_key: str
    title: str
    explanation: str
    risk_level: str
    evidence_count: int
    incident_count: int
    last_seen_at: datetime

    class Config:
        from_attributes = True

class EvidenceLinkDetail(BaseModel):
    id: UUID
    evidence_type: str
    evidence_summary: str
    source_test_run_id: Optional[UUID] = None
    source_test_result_id: Optional[UUID] = None
    source_incident_id: Optional[str] = None
    source_recommendation_run_id: Optional[UUID] = None
    source_pull_request_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

class FragilityPatternDetailResponse(BaseModel):
    id: UUID
    repository_id: UUID
    pattern_type: str
    normalized_pattern_key: str
    title: str
    explanation: str
    fragility_score: float
    risk_level: str
    status: str
    confidence_level: str
    pattern_hash: str
    score_components: Dict[str, Any]
    replayable_evidence_snapshot: Dict[str, Any]
    invalidated_reason: Optional[str] = None
    invalidated_at: Optional[datetime] = None
    invalidated_by: Optional[str] = None
    fragility_generation_version: str
    scoring_formula_version: str
    evidence_count: int
    incident_count: int
    related_failure_count: int
    context: Optional[Dict[str, Any]] = None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
    
    evidence_links: List[EvidenceLinkDetail] = []
    linked_failures: List[Dict[str, Any]] = []
    linked_incidents: List[Dict[str, Any]] = []
    linked_recommendations: List[Dict[str, Any]] = []

    class Config:
        from_attributes = True

class FragilityRecalculateRequest(BaseModel):
    repository_id: UUID
    history_window_days: Optional[int] = Field(default=90, ge=1)
