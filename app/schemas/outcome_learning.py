"""
Outcome Learning API Schemas
"""

from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class OutcomeEventCreate(BaseModel):
    event_type: str = Field(..., description="PR_MERGED, PR_CLOSED_UNMERGED, DEPLOYMENT_FAILED, BUG_REPORTED, etc.")
    event_source: str = Field(..., description="github, ci, manual")
    event_status: Optional[str] = None
    severity: Optional[str] = None
    occurred_at: Optional[datetime] = None
    external_event_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    
    # Optional context fields (to assist strict linking rules if explicitly known)
    pull_request_id: Optional[UUID] = None
    pipeline_run_id: Optional[UUID] = None
    github_pr_number: Optional[int] = None
    commit_sha: Optional[str] = None
    recommendation_run_id: Optional[UUID] = None


class OutcomeEventResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    repository_id: UUID
    pull_request_id: Optional[UUID] = None
    pipeline_run_id: Optional[UUID] = None
    recommendation_run_id: Optional[UUID] = None
    github_pr_number: Optional[int] = None
    commit_sha: Optional[str] = None
    event_type: str
    event_source: str
    event_status: Optional[str] = None
    severity: Optional[str] = None
    occurred_at: datetime
    detected_at: datetime
    external_event_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OutcomeLabelCreate(BaseModel):
    label_type: str = Field(..., description="recommendation_correct, regression_scope_too_large, safe_to_skip_incorrect, etc.")
    label_value: str = Field(..., description="true, false, accurate, too_strict, too_lenient, too_large, too_small")
    confidence: Optional[float] = None
    metadata_json: Optional[Dict[str, Any]] = None


class OutcomeLabelResponse(BaseModel):
    id: UUID
    outcome_event_id: Optional[UUID] = None
    workspace_id: UUID
    repository_id: UUID
    recommendation_run_id: UUID
    label_type: str
    label_value: str
    confidence: Optional[float] = None
    source: str
    created_by_user_id: Optional[UUID] = None
    created_at: datetime
    metadata_json: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class RecommendationOutcomeSummaryResponse(BaseModel):
    id: UUID
    recommendation_run_id: UUID
    pipeline_run_id: Optional[UUID] = None
    workspace_id: UUID
    repository_id: UUID
    pull_request_id: Optional[UUID] = None
    github_pr_number: Optional[int] = None
    commit_sha: Optional[str] = None
    merged: bool
    reverted: bool
    deployment_failed: bool
    incident_found: bool
    bug_found: bool
    regression_found: bool
    missed_critical_test: bool
    missed_high_test: bool
    scope_accuracy: Optional[str] = None
    quality_gate_accuracy: Optional[str] = None
    learning_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkspaceOutcomeAnalyticsResponse(BaseModel):
    recommendation_accuracy: float = 0.0
    quality_gate_accuracy: float = 0.0
    regression_scope_accuracy: float = 0.0
    safe_to_skip_accuracy: float = 0.0
    post_merge_failure_rate: float = 0.0
    post_deployment_failure_rate: float = 0.0
    revert_rate: float = 0.0
    incident_linked_rate: float = 0.0
