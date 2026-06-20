"""
CI/CD Policy Schemas

Request and response schemas for CI/CD policy management.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class CICDPolicyCreate(BaseModel):
    """Request to create a CI/CD policy."""
    enabled: bool = Field(default=True, description="Whether the policy is enabled")
    required_check_name: str = Field(default="Veriscope Quality Gate", description="Required GitHub check name")
    ci_fail_on_partial: bool = Field(default=False, description="Fail CI on PARTIAL quality gate")
    fail_on_unknown_gate: bool = Field(default=True, description="Fail CI on UNKNOWN quality gate")
    fail_on_missing_recommendation: bool = Field(default=True, description="Fail CI when recommendation is missing")
    require_artifact: bool = Field(default=True, description="Require artifact for completion")
    require_pr_comment: bool = Field(default=True, description="Require PR comment for completion")
    allow_manual_override: bool = Field(default=False, description="Allow manual override")
    manual_override_requires_reason: bool = Field(default=True, description="Require reason for manual override")
    strict_mode: bool = Field(default=False, description="Strict mode (fails PARTIAL and UNKNOWN)")


class CICDPolicyUpdate(BaseModel):
    """Request to update a CI/CD policy."""
    enabled: Optional[bool] = Field(None, description="Whether the policy is enabled")
    required_check_name: Optional[str] = Field(None, description="Required GitHub check name")
    ci_fail_on_partial: Optional[bool] = Field(None, description="Fail CI on PARTIAL quality gate")
    fail_on_unknown_gate: Optional[bool] = Field(None, description="Fail CI on UNKNOWN quality gate")
    fail_on_missing_recommendation: Optional[bool] = Field(None, description="Fail CI when recommendation is missing")
    require_artifact: Optional[bool] = Field(None, description="Require artifact for completion")
    require_pr_comment: Optional[bool] = Field(None, description="Require PR comment for completion")
    allow_manual_override: Optional[bool] = Field(None, description="Allow manual override")
    manual_override_requires_reason: Optional[bool] = Field(None, description="Require reason for manual override")
    strict_mode: Optional[bool] = Field(None, description="Strict mode (fails PARTIAL and UNKNOWN)")


class CICDPolicyResponse(BaseModel):
    """Response for CI/CD policy."""
    id: UUID
    repository_id: UUID
    enabled: bool
    required_check_name: str
    ci_fail_on_partial: bool
    fail_on_unknown_gate: bool
    fail_on_missing_recommendation: bool
    require_artifact: bool
    require_pr_comment: bool
    allow_manual_override: bool
    manual_override_requires_reason: bool
    strict_mode: bool
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[UUID] = None


class PolicyPreviewRequest(BaseModel):
    """Request to preview policy outcome."""
    releaseDecision: Optional[str] = Field(None, description="Release decision value")
    recommendationHealth: Optional[str] = Field(None, description="Recommendation health status")
    qualityGate: Optional[str] = Field(None, description="Quality gate value")
    hasRecommendationRun: bool = Field(default=True, description="Whether recommendation run exists")
    hasArtifact: bool = Field(default=True, description="Whether artifact exists")
    hasPrComment: bool = Field(default=True, description="Whether PR comment exists")


class PolicyPreviewResponse(BaseModel):
    """Response for policy preview."""
    githubConclusion: str = Field(..., description="GitHub conclusion (success, failure, neutral)")
    wouldBlockPr: bool = Field(..., description="Whether PR would be blocked")
    qualityGate: str = Field(..., description="Quality gate value")
    reason: str = Field(..., description="Reason for the decision")
    rulesApplied: List[str] = Field(..., description="Rules applied to reach the decision")


class PolicyAuditEvent(BaseModel):
    """Policy audit event."""
    id: UUID
    repository_id: UUID
    event_type: str = Field(..., description="Event type (CREATED, UPDATED, PREVIEWED, MANUAL_OVERRIDE)")
    actor_id: Optional[UUID] = Field(None, description="User who triggered the event")
    before_policy: Optional[Dict[str, Any]] = Field(None, description="Policy state before change")
    after_policy: Optional[Dict[str, Any]] = Field(None, description="Policy state after change")
    changed_fields: Optional[List[str]] = Field(None, description="Fields that changed")
    reason: Optional[str] = Field(None, description="Reason for the change")
    timestamp: datetime = Field(..., description="Event timestamp")


class BranchProtectionReadiness(BaseModel):
    """Branch protection readiness response."""
    repository_id: UUID
    required_check_name: str
    github_app_installed: bool
    checks_write_permission: bool
    statuses_write_permission: bool
    pr_comment_permission: bool
    workflow_configured: bool
    latest_successful_pipeline_run: Optional[datetime] = Field(None, description="Latest successful pipeline run timestamp")
    latest_github_status_result: Optional[str] = Field(None, description="Latest GitHub status result")
    latest_artifact_available: bool = Field(default=False, description="Whether latest artifact is available")
    policy_strictness: str = Field(..., description="Policy strictness (strict, moderate, permissive)")
    recommended_branch_protection: str = Field(..., description="Recommended branch protection setting")
    is_ready: bool = Field(..., description="Whether repository is ready for branch protection")
    readiness_issues: List[str] = Field(default_factory=list, description="Issues preventing readiness")


# Governance schemas

class PresetDefinition(BaseModel):
    """Preset definition."""
    name: str
    description: str
    risk_level: str
    recommended_use_case: str
    settings: Dict[str, Any]
    impact: Dict[str, str]


class PresetListResponse(BaseModel):
    """Response for preset list."""
    presets: List[PresetDefinition]


class ApplyPresetRequest(BaseModel):
    """Request to apply a preset."""
    preset_name: str
    reason: Optional[str] = Field(None, description="Reason for applying the preset")


class EffectivePolicyResponse(BaseModel):
    """Response for effective policy."""
    effective_policy: Dict[str, Any]
    source: str = Field(..., description="Source of policy (REPOSITORY_OVERRIDE, WORKSPACE_DEFAULT, SYSTEM_DEFAULT)")
    source_preset: Optional[str] = Field(None, description="Preset name if applicable")
    workspace_default_preset: Optional[str] = Field(None, description="Workspace default preset")
    repository_override_exists: bool
    drift_from_default: bool
    drift_fields: List[str]


class PolicyDriftResponse(BaseModel):
    """Response for policy drift detection."""
    drift_detected: bool
    drift_fields: List[str]
    default_values: Dict[str, Any]
    repository_values: Dict[str, Any]
    risk_level: str
    recommended_action: str


class PresetRecommendationResponse(BaseModel):
    """Response for preset recommendation."""
    recommended_preset: str
    confidence: str
    reasons: List[str]
    risk_signals: List[str]
    tradeoffs: List[str]


class PolicyExportResponse(BaseModel):
    """Response for policy export."""
    version: str
    type: str
    preset: str
    policy: Dict[str, Any]


class PolicyImportRequest(BaseModel):
    """Request for policy import."""
    version: str
    type: str
    preset: Optional[str] = None
    policy: Dict[str, Any]


class ClonePolicyRequest(BaseModel):
    """Request to clone policy."""
    source_repository_id: UUID


class OrganizationDefaultPolicyResponse(BaseModel):
    """Response for organization default policy."""
    id: UUID
    organization_id: UUID
    default_preset: str
    default_policy_json: Optional[Dict[str, Any]] = None
    auto_apply_to_new_repositories: bool
    allow_repository_override: bool
    require_override_reason: bool
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[UUID] = None


class OrganizationDefaultPolicyUpdate(BaseModel):
    """Request to update organization default policy."""
    default_preset: Optional[str] = None
    default_policy_json: Optional[Dict[str, Any]] = None
    auto_apply_to_new_repositories: Optional[bool] = None
    allow_repository_override: Optional[bool] = None
    require_override_reason: Optional[bool] = None


# Phase 8.9 Governance Rollout schemas

class BulkOperationRequest(BaseModel):
    """Request for bulk policy operation."""
    repository_ids: List[UUID]
    operation: str = Field(..., description="Operation type: APPLY_PRESET, RESTORE_ORG_DEFAULT, ACKNOWLEDGE_DRIFT, EXPORT_POLICIES, SCAN_COMPLIANCE")
    preset_name: Optional[str] = Field(None, description="Preset name for APPLY_PRESET operation")
    reason: Optional[str] = Field(None, description="Reason for the operation")


class BulkOperationResult(BaseModel):
    """Result of bulk policy operation."""
    operationId: str
    operation: str
    requestedCount: int
    succeededCount: int
    failedCount: int
    skippedCount: int
    results: List[Dict[str, Any]]


class RepositoryCompliance(BaseModel):
    """Repository compliance score."""
    repository_id: str
    repository_name: str
    policy_source: str
    current_preset: Optional[str]
    workspace_default_preset: Optional[str]
    drift_detected: bool
    drift_risk_level: str
    branch_protection_ready: bool
    manual_override_enabled: bool
    artifact_required: bool
    pr_comment_required: bool
    unknown_gate_fails: bool
    partial_gate_fails: bool
    compliance_score: int
    compliance_status: str
    recommended_action: str


class OrganizationComplianceDashboard(BaseModel):
    """Organization compliance dashboard response."""
    total_repositories: int
    repositories_with_policy: int
    repositories_inheriting_org_default: int
    repositories_with_overrides: int
    repositories_with_drift: int
    repositories_with_high_risk_drift: int
    repositories_with_critical_risk_drift: int
    repositories_using_each_preset: Dict[str, int]
    repositories_missing_required_artifact_policy: int
    repositories_allowing_manual_override: int
    repositories_not_ready_for_branch_protection: int
    overall_compliance_score: int


class PolicyExceptionRequest(BaseModel):
    """Request to create policy exception."""
    repository_id: UUID
    reason: str
    exception_fields: List[str]
    expires_at: Optional[datetime] = None


class PolicyExceptionResponse(BaseModel):
    """Policy exception response."""
    id: UUID
    organization_id: UUID
    repository_id: UUID
    requested_by: UUID
    approved_by: Optional[UUID]
    status: str
    reason: str
    exception_fields: List[str]
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    decision_reason: Optional[str]


class PolicyExceptionDecision(BaseModel):
    """Request to approve/reject policy exception."""
    decision_reason: str


class GovernanceReviewSnapshotResponse(BaseModel):
    """Governance review snapshot response."""
    id: UUID
    organization_id: UUID
    created_at: datetime
    created_by: UUID
    total_repositories: int
    compliance_score: int
    critical_count: int
    high_risk_count: int
    drifted_count: int
    compliant_count: int


class GovernanceReportRequest(BaseModel):
    """Request for governance report export."""
    format: str = Field(..., description="Export format: JSON, CSV, Markdown")


class BulkPreviewRequest(BaseModel):
    """Request for bulk operation preview."""
    repository_ids: List[UUID]
    operation: str = Field(..., description="Operation type: APPLY_PRESET, RESTORE_ORG_DEFAULT")
    preset_name: Optional[str] = Field(None, description="Preset name for APPLY_PRESET operation")


class BulkPreviewResult(BaseModel):
    """Result of bulk operation preview."""
    repositories_affected: List[Dict[str, Any]]
    repositories_skipped: List[Dict[str, Any]]
    current_preset: Optional[str]
    target_preset: Optional[str]
    fields_that_will_change: List[str]
    risk_reduction: Optional[str]
    warnings: List[str]
