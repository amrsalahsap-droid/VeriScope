"""
CI/CD Policy Router

Provides endpoints for managing repository-level CI/CD quality gate policies.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.ci_cd_policy_service import CICDPolicyService
from app.services.ci_cd_policy_audit_service import CICDPolicyAuditService
from app.services.ci_cd_policy_preset_service import CICDPolicyPresetService
from app.services.governance_permission_service import GovernancePermissionService
from app.schemas.ci_cd_policy import (
    CICDPolicyResponse,
    CICDPolicyUpdate,
    PolicyPreviewRequest,
    PolicyPreviewResponse,
    BranchProtectionReadiness,
    PresetListResponse,
    ApplyPresetRequest,
    EffectivePolicyResponse,
    PolicyDriftResponse,
    PresetRecommendationResponse,
    PolicyExportResponse,
    PolicyImportRequest,
    ClonePolicyRequest,
    OrganizationDefaultPolicyResponse,
    OrganizationDefaultPolicyUpdate
)
from pydantic import BaseModel


class ManualOverrideRequest(BaseModel):
    """Request for manual override."""
    original_quality_gate: str
    override_decision: str
    reason: str


from app.models.repository import Repository
from app.models.github_installation import GitHubInstallation
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.dependencies.auth import get_current_user
from app.models.user import User


router = APIRouter(prefix="/repositories/{repository_id}/cicd/policy", tags=["cicd-policy"])


def require_permission(permission: str):
    """Dependency to require a specific governance permission."""
    def dependency(
        repository_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> User:
        # Get organization from repository
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Check permission
        has_perm = GovernancePermissionService.has_permission(
            db, current_user.id, permission, repository.workspace_id, repository_id
        )
        
        if not has_perm:
            explanation = GovernancePermissionService.explain_access_decision(
                db, current_user.id, permission, repository.workspace_id, repository_id
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Permission denied",
                    "permission_required": permission,
                    "reason": explanation.get("reason"),
                    "how_to_request_access": explanation.get("how_to_request_access")
                }
            )
        
        return current_user
    return dependency


@router.get("", response_model=CICDPolicyResponse)
def get_policy(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> CICDPolicyResponse:
    """
    Get repository CI/CD policy.
    
    If no policy exists, a default policy with safe defaults is returned.
    """
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    service = CICDPolicyService()
    policy = service.get_policy(db, repository_id)
    
    return CICDPolicyResponse(
        id=policy.id,
        repository_id=policy.repository_id,
        enabled=policy.enabled,
        required_check_name=policy.required_check_name,
        ci_fail_on_partial=policy.ci_fail_on_partial,
        fail_on_unknown_gate=policy.fail_on_unknown_gate,
        fail_on_missing_recommendation=policy.fail_on_missing_recommendation,
        require_artifact=policy.require_artifact,
        require_pr_comment=policy.require_pr_comment,
        allow_manual_override=policy.allow_manual_override,
        manual_override_requires_reason=policy.manual_override_requires_reason,
        strict_mode=policy.strict_mode,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        updated_by=policy.updated_by
    )


@router.put("", response_model=CICDPolicyResponse)
def update_policy(
    repository_id: uuid.UUID,
    payload: CICDPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.update"))
) -> CICDPolicyResponse:
    """
    Update repository CI/CD policy.
    """
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    service = CICDPolicyService()
    policy = service.update_policy(db, repository_id, payload.dict(exclude_unset=True), current_user.id)
    
    # Log audit event
    CICDPolicyAuditService.log_policy_updated(
        db=db,
        repository_id=repository_id,
        before_policy={},
        after_policy=payload.dict(exclude_unset=True),
        changed_fields=list(payload.dict(exclude_unset=True).keys()),
        actor_id=current_user.id,
        actor_type="USER"
    )
    
    return CICDPolicyResponse(
        id=policy.id,
        repository_id=policy.repository_id,
        enabled=policy.enabled,
        required_check_name=policy.required_check_name,
        ci_fail_on_partial=policy.ci_fail_on_partial,
        fail_on_unknown_gate=policy.fail_on_unknown_gate,
        fail_on_missing_recommendation=policy.fail_on_missing_recommendation,
        require_artifact=policy.require_artifact,
        require_pr_comment=policy.require_pr_comment,
        allow_manual_override=policy.allow_manual_override,
        manual_override_requires_reason=policy.manual_override_requires_reason,
        strict_mode=policy.strict_mode,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        updated_by=policy.updated_by
    )


@router.post("/preview", response_model=PolicyPreviewResponse)
def preview_policy(
    repository_id: uuid.UUID,
    scenario: PolicyPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> PolicyPreviewResponse:
    """
    Preview policy outcome for a given scenario.
    """
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    service = CICDPolicyService()
    result = service.preview_policy(db, repository_id, scenario.dict())
    
    # Log audit event
    CICDPolicyAuditService.log_policy_previewed(
        db=db,
        repository_id=repository_id,
        scenario=scenario.dict(),
        result=result,
        actor_id=current_user.id,
        actor_type="USER"
    )
    
    return PolicyPreviewResponse(
        githubConclusion=result["github_conclusion"],
        wouldBlockPr=result["would_block_pr"],
        qualityGate=result["quality_gate"],
        reason=result["reason"],
        rulesApplied=result["rules_applied"]
    )


@router.get("/audit")
def get_policy_audit(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.audit.view"))
) -> List[Dict[str, Any]]:
    """
    Get policy audit history.
    """
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    audit_events = CICDPolicyAuditService.get_audit_history(db, repository_id)
    
    return [
        {
            "id": str(event.id),
            "repository_id": str(event.repository_id),
            "event_type": event.event_type,
            "actor_id": str(event.actor_id) if event.actor_id else None,
            "actor_type": event.actor_type,
            "before_policy": event.before_policy,
            "after_policy": event.after_policy,
            "changed_fields": event.changed_fields,
            "original_quality_gate": event.original_quality_gate,
            "override_decision": event.override_decision,
            "override_reason": event.override_reason,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None
        }
        for event in audit_events
    ]


@router.post("/manual-override")
def apply_manual_override(
    repository_id: uuid.UUID,
    payload: ManualOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.update"))
):
    """
    Apply manual override to quality gate decision.
    
    This only overrides the CI gate publication decision and does not mutate evidence,
    recommendation health, release decision, or regression scope.
    """
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    service = CICDPolicyService()
    
    try:
        result = service.apply_manual_override(
            db=db,
            repository_id=repository_id,
            original_quality_gate=payload.original_quality_gate,
            override_decision=payload.override_decision,
            reason=payload.reason,
            actor_id=current_user.id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/branch-protection-readiness", response_model=BranchProtectionReadiness)
def get_branch_protection_readiness(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> BranchProtectionReadiness:
    """
    Get branch protection readiness for the repository.
    
    Explains whether the repository is ready to use Veriscope as a required GitHub check.
    """
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    service = CICDPolicyService()
    policy = service.get_policy(db, repository_id)
    
    # Check GitHub App installation
    installation = db.query(GitHubInstallation).filter(
        GitHubInstallation.github_installation_id == repository.installation_id
    ).first()
    github_app_installed = installation is not None
    
    # Check permissions (simplified - in production, check actual permissions)
    checks_write_permission = True  # TODO: Check actual permissions
    statuses_write_permission = True  # TODO: Check actual permissions
    pr_comment_permission = True  # TODO: Check actual permissions
    
    # Check workflow configuration (simplified)
    workflow_configured = True  # TODO: Check actual workflow
    
    # Check latest successful pipeline run
    latest_pipeline_run = db.query(PipelineRun).filter(
        PipelineRun.repository_id == repository_id,
        PipelineRun.status == PipelineRunStatus.COMPLETED
    ).order_by(PipelineRun.created_at.desc()).first()
    
    latest_successful_pipeline_run = latest_pipeline_run.created_at if latest_pipeline_run else None
    latest_github_status_result = latest_pipeline_run.quality_gate if latest_pipeline_run else None
    
    # Check artifact availability (simplified)
    latest_artifact_available = latest_pipeline_run is not None  # TODO: Check actual artifact
    
    # Determine policy strictness
    if policy.strict_mode:
        policy_strictness = "strict"
    elif policy.ci_fail_on_partial or policy.fail_on_unknown_gate:
        policy_strictness = "moderate"
    else:
        policy_strictness = "permissive"
    
    # Determine readiness issues
    readiness_issues = []
    if not github_app_installed:
        readiness_issues.append("GitHub App not installed")
    if not checks_write_permission:
        readiness_issues.append("Missing checks write permission")
    if not statuses_write_permission:
        readiness_issues.append("Missing statuses write permission")
    if not pr_comment_permission:
        readiness_issues.append("Missing PR comment permission")
    if not workflow_configured:
        readiness_issues.append("Workflow not configured")
    if not latest_successful_pipeline_run:
        readiness_issues.append("No successful pipeline runs")
    
    is_ready = len(readiness_issues) == 0
    
    # Recommended branch protection setting
    recommended_branch_protection = f"Require: {policy.required_check_name}"
    
    return BranchProtectionReadiness(
        repository_id=repository_id,
        required_check_name=policy.required_check_name,
        github_app_installed=github_app_installed,
        checks_write_permission=checks_write_permission,
        statuses_write_permission=statuses_write_permission,
        pr_comment_permission=pr_comment_permission,
        workflow_configured=workflow_configured,
        latest_successful_pipeline_run=latest_successful_pipeline_run,
        latest_github_status_result=latest_github_status_result,
        latest_artifact_available=latest_artifact_available,
        policy_strictness=policy_strictness,
        recommended_branch_protection=recommended_branch_protection,
        is_ready=is_ready,
        readiness_issues=readiness_issues
    )


# Governance endpoints

@router.get("/presets", response_model=PresetListResponse)
def list_presets(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> PresetListResponse:
    """List all available CI/CD policy presets."""
    preset_service = CICDPolicyPresetService()
    presets = preset_service.list_presets()
    return PresetListResponse(presets=presets)


@router.get("/effective", response_model=EffectivePolicyResponse)
def get_effective_policy(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> EffectivePolicyResponse:
    """Get effective policy with inheritance information."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    service = CICDPolicyService()
    effective_policy = service.get_effective_policy(db, repository_id)
    return EffectivePolicyResponse(**effective_policy)


@router.post("/apply-preset", response_model=CICDPolicyResponse)
def apply_preset(
    repository_id: uuid.UUID,
    payload: ApplyPresetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.apply_preset"))
) -> CICDPolicyResponse:
    """Apply a preset to repository policy."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    preset_service = CICDPolicyPresetService()
    try:
        policy = preset_service.apply_preset(
            db=db,
            repository_id=repository_id,
            preset_name=payload.preset_name,
            actor_id=current_user.id,
            reason=payload.reason
        )
        return CICDPolicyResponse(
            id=policy.id,
            repository_id=policy.repository_id,
            enabled=policy.enabled,
            required_check_name=policy.required_check_name,
            ci_fail_on_partial=policy.ci_fail_on_partial,
            fail_on_unknown_gate=policy.fail_on_unknown_gate,
            fail_on_missing_recommendation=policy.fail_on_missing_recommendation,
            require_artifact=policy.require_artifact,
            require_pr_comment=policy.require_pr_comment,
            allow_manual_override=policy.allow_manual_override,
            manual_override_requires_reason=policy.manual_override_requires_reason,
            strict_mode=policy.strict_mode,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
            updated_by=policy.updated_by
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recommend-preset", response_model=PresetRecommendationResponse)
def recommend_preset(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> PresetRecommendationResponse:
    """Recommend a preset based on repository risk."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    preset_service = CICDPolicyPresetService()
    recommendation = preset_service.recommend_preset(db, repository_id)
    return PresetRecommendationResponse(**recommendation)


@router.get("/drift", response_model=PolicyDriftResponse)
def get_policy_drift(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.drift.view"))
) -> PolicyDriftResponse:
    """Get policy drift from organization default."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    preset_service = CICDPolicyPresetService()
    drift = preset_service.detect_policy_drift(db, repository_id)
    return PolicyDriftResponse(**drift)


@router.get("/export", response_model=PolicyExportResponse)
def export_policy(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.export"))
) -> PolicyExportResponse:
    """Export repository policy as JSON."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    service = CICDPolicyService()
    export_data = service.export_policy(db, repository_id)
    return PolicyExportResponse(**export_data)


@router.post("/import", response_model=CICDPolicyResponse)
def import_policy(
    repository_id: uuid.UUID,
    payload: PolicyImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.import"))
) -> CICDPolicyResponse:
    """Import policy from JSON."""
    # Verify repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    service = CICDPolicyService()
    try:
        policy = service.import_policy(
            db=db,
            repository_id=repository_id,
            import_data=payload.dict(),
            actor_id=current_user.id
        )
        return CICDPolicyResponse(
            id=policy.id,
            repository_id=policy.repository_id,
            enabled=policy.enabled,
            required_check_name=policy.required_check_name,
            ci_fail_on_partial=policy.ci_fail_on_partial,
            fail_on_unknown_gate=policy.fail_on_unknown_gate,
            fail_on_missing_recommendation=policy.fail_on_missing_recommendation,
            require_artifact=policy.require_artifact,
            require_pr_comment=policy.require_pr_comment,
            allow_manual_override=policy.allow_manual_override,
            manual_override_requires_reason=policy.manual_override_requires_reason,
            strict_mode=policy.strict_mode,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
            updated_by=policy.updated_by
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/clone-from", response_model=CICDPolicyResponse)
def clone_policy(
    repository_id: uuid.UUID,
    payload: ClonePolicyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.clone"))
) -> CICDPolicyResponse:
    """Clone policy from another repository."""
    # Verify target repository exists
    target_repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not target_repository:
        raise HTTPException(status_code=404, detail="Target repository not found")
    
    # Verify source repository exists
    source_repository = db.query(Repository).filter(Repository.id == payload.source_repository_id).first()
    if not source_repository:
        raise HTTPException(status_code=404, detail="Source repository not found")
    
    service = CICDPolicyService()
    policy = service.clone_policy(
        db=db,
        source_repository_id=payload.source_repository_id,
        target_repository_id=repository_id,
        actor_id=current_user.id
    )
    return CICDPolicyResponse(
        id=policy.id,
        repository_id=policy.repository_id,
        enabled=policy.enabled,
        required_check_name=policy.required_check_name,
        ci_fail_on_partial=policy.ci_fail_on_partial,
        fail_on_unknown_gate=policy.fail_on_unknown_gate,
        fail_on_missing_recommendation=policy.fail_on_missing_recommendation,
        require_artifact=policy.require_artifact,
        require_pr_comment=policy.require_pr_comment,
        allow_manual_override=policy.allow_manual_override,
        manual_override_requires_reason=policy.manual_override_requires_reason,
        strict_mode=policy.strict_mode,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        updated_by=policy.updated_by
    )
