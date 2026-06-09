from datetime import datetime
from uuid import UUID
from typing import List, Optional, Any, Dict
from pydantic import BaseModel

class ReasoningEntryResponse(BaseModel):
    id: UUID
    recommendation_run_id: UUID
    reason_type: str
    source_entity: str
    source_reference: str
    human_readable_reason: str
    confidence_level: str
    evidence_priority: str
    created_at: datetime

    class Config:
        from_attributes = True

class IngestionJobDebugResponse(BaseModel):
    id: UUID
    job_type: str
    repository_id: UUID
    status: str
    error_message: Optional[str]
    retry_count: int
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

# Standard Debugging Block Schemas

class PRDebugResponse(BaseModel):
    raw_inputs: Dict[str, Any]
    derived_relationships: Dict[str, Any]
    fallback_heuristics_used: List[str]
    warnings: List[str]
    confidence_issues: List[str]
    telemetry: Dict[str, Any]

class TestRunDebugResponse(BaseModel):
    raw_inputs: Dict[str, Any]
    derived_relationships: Dict[str, Any]
    fallback_heuristics_used: List[str]
    warnings: List[str]
    confidence_issues: List[str]
    telemetry: Dict[str, Any]

class CoverageDebugResponse(BaseModel):
    raw_inputs: Dict[str, Any]
    derived_relationships: Dict[str, Any]
    fallback_heuristics_used: List[str]
    warnings: List[str]
    confidence_issues: List[str]
    telemetry: Dict[str, Any]

class DependencyDebugResponse(BaseModel):
    raw_inputs: Dict[str, Any]
    derived_relationships: Dict[str, Any]
    fallback_heuristics_used: List[str]
    warnings: List[str]
    confidence_issues: List[str]
    telemetry: Dict[str, Any]

class FlakyRegistryDebugResponse(BaseModel):
    raw_inputs: Dict[str, Any]
    derived_relationships: Dict[str, Any]
    fallback_heuristics_used: List[str]
    warnings: List[str]
    confidence_issues: List[str]
    telemetry: Dict[str, Any]

class RecommendationDebugResponse(BaseModel):
    run_id: UUID
    evidence_quality: str
    reasoning_entries: List[ReasoningEntryResponse]
    active_risk_amplification_rules: List[str]
    dependency_expansion_path: List[str]
    evidence_quality_logic: str
    associated_ingestion_jobs: List[IngestionJobDebugResponse]
    
    # Traceability auditing blocks
    raw_inputs: Dict[str, Any]
    derived_relationships: Dict[str, Any]
    fallback_heuristics_used: List[str]
    warnings: List[str]
    confidence_issues: List[str]
    telemetry: Dict[str, Any]

    class Config:
        from_attributes = True

from app.schemas.recommendation import RecommendationTestResponse

class RecommendationDetailedDebugResponse(BaseModel):
    id: UUID
    repository_id: UUID
    pr_id: str
    triggered_by: str
    created_at: datetime
    engine_version: str
    ruleset_version: str
    degradation_policy_version: str
    recommendation_reasoning_summary: str

    run_id: UUID
    evidence_quality: str
    recommendation_mode: str
    unsafe_for_optimization: bool
    coverage_report_id: Optional[UUID] = None
    dependency_state_hash: Optional[str] = None
    test_history_window_start: Optional[datetime] = None
    test_history_window_end: Optional[datetime] = None
    test_history_window: Dict[str, Optional[datetime]]
    flakiness_profile_hash: Optional[str] = None
    estimated_runtime_seconds: Optional[float] = 0.0
    runtime_confidence: Optional[str] = "LOW"
    
    skipped_reason_summary: Optional[str] = None
    skipped_count: int = 0
    top_skipped_examples: Optional[List[str]] = None
    skipped_summary: Dict[str, Any]

    active_risk_amplification_rules: List[str] = []
    dependency_expansion_path: List[str] = []
    evidence_quality_logic: str
    associated_ingestion_jobs: List[IngestionJobDebugResponse] = []
    raw_inputs: Dict[str, Any] = {}
    derived_relationships: Dict[str, Any] = {}
    fallback_heuristics_used: List[str] = []
    warnings: List[str] = []
    confidence_issues: List[str] = []
    telemetry: Dict[str, Any] = {}

    input_snapshot: Optional[Dict[str, Any]] = None
    reasoning_entries: Optional[List[ReasoningEntryResponse]] = None
    recommended_tests: Optional[List[RecommendationTestResponse]] = None
    fragility_snapshot: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

