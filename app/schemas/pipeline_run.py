"""
Pipeline Run Schemas

Request and response schemas for CI/CD pipeline run integration.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class PipelineRunTriggerRequest(BaseModel):
    """Request to trigger or link a pipeline run."""
    provider: str = Field(..., description="CI provider, e.g., GITHUB_ACTIONS, GITLAB_CI")
    external_run_id: str = Field(..., description="External CI run ID")
    pull_request_number: Optional[int] = Field(None, description="PR number if triggered by PR")
    commit_sha: str = Field(..., description="Git commit SHA")
    branch: Optional[str] = Field(None, description="Git branch")
    trigger_source: str = Field(default="pull_request", description="Source that triggered the pipeline")


class RegressionScopeSummary(BaseModel):
    """Summary of regression scope for CI response."""
    required: int = Field(default=0)
    recommended: int = Field(default=0)
    optional: int = Field(default=0)
    safe_to_skip: int = Field(default=0)
    total_executable: int = Field(default=0)


class PipelineRunResponse(BaseModel):
    """Response from pipeline trigger endpoint."""
    pipeline_run_id: UUID
    recommendation_run_id: Optional[UUID]
    quality_gate: str
    release_decision: Optional[str]
    recommendation_health: Optional[str]
    required_before_release: int = Field(default=0)
    regression_scope: RegressionScopeSummary
    changed_files: int = Field(default=0)
    summary: str
    status: str
    created_at: datetime


class PipelineRunArtifact(BaseModel):
    """CI-safe artifact export."""
    recommendation_run_id: UUID
    pipeline_run_id: UUID
    pull_request_number: Optional[int]
    commit_sha: str
    changed_files: int
    recommendation_health: Optional[str]
    release_decision: Optional[str]
    required_before_release: int
    regression_scope: RegressionScopeSummary
    quality_gate: str
    timestamp: datetime
