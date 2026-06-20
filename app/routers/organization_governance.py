"""
Workspace CI/CD Governance Router

Provides endpoints for organization-level CI/CD governance management including compliance dashboard, bulk operations, policy exceptions, and governance reviews.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import Workspace
from app.models.repository import Repository
from app.models.repository_ci_cd_policy import RepositoryCICDPolicy
from app.models.ci_cd_policy_exception import CICDPolicyException
from app.models.ci_cd_governance_review_snapshot import CICDGovernanceReviewSnapshot
from app.models.workspace_ci_cd_policy_default import WorkspaceCICDPolicyDefault
from app.models.governance_role_assignment import GovernanceRoleAssignment, GovernanceRole, ScopeType
from app.models.workspace_governance_audit_event import WorkspaceGovernanceAuditEvent
from app.services.ci_cd_policy_bulk_operation_service import CICDPolicyBulkOperationService
from app.services.ci_cd_policy_preset_service import CICDPolicyPresetService
from app.services.ci_cd_policy_service import CICDPolicyService
from app.services.workspace_governance_audit_service import WorkspaceGovernanceAuditService
from app.services.ci_cd_governance_analytics_service import CICDGovernanceAnalyticsService
from app.services.governance_permission_service import GovernancePermissionService
from app.schemas.ci_cd_policy import (
    BulkOperationRequest,
    BulkOperationResult,
    RepositoryCompliance,
    OrganizationComplianceDashboard,
    PolicyExceptionRequest,
    PolicyExceptionResponse,
    PolicyExceptionDecision,
    GovernanceReviewSnapshotResponse,
    GovernanceReportRequest,
    BulkPreviewRequest,
    BulkPreviewResult
)
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.governance_notification_service import GovernanceNotificationService


router = APIRouter(tags=["cicd-governance"])

# Backward compatibility: workspace_id route parameter maps to workspace_id
# Workspace model is deprecated in favor of Workspace


def require_permission(permission: str):
    """Dependency to check if user has required permission."""
    def check(
        workspace_id: uuid.UUID,
        repository_id: uuid.UUID = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        result = GovernancePermissionService.require_permission(
            db=db,
            user_id=current_user.id,
            permission=permission,
            workspace_id=workspace_id,
            repository_id=repository_id,
            actor_id=current_user.id
        )
        if not result["allowed"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "You do not have permission to perform this governance action.",
                    "permission_required": permission,
                    "scope_checked": result.get("scope_checked"),
                    "reason": result.get("reason"),
                    "how_to_request_access": result.get("how_to_request_access")
                }
            )
        return current_user
    return check


@router.get("/compliance", response_model=OrganizationComplianceDashboard)
def get_organization_compliance_dashboard(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> OrganizationComplianceDashboard:
    """Get organization compliance dashboard."""
    # Verify workspace exists
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get all repositories for workspace
    repositories = db.query(Repository).filter(
        Repository.workspace_id == workspace_id
    ).all()
    
    total_repositories = len(repositories)
    
    # Calculate compliance metrics
    repositories_with_policy = 0
    repositories_inheriting_org_default = 0
    repositories_with_overrides = 0
    repositories_with_drift = 0
    repositories_with_high_risk_drift = 0
    repositories_with_critical_risk_drift = 0
    repositories_using_each_preset = {"PERMISSIVE": 0, "STANDARD": 0, "STRICT": 0, "REGULATED": 0, "CUSTOM": 0}
    repositories_missing_required_artifact_policy = 0
    repositories_allowing_manual_override = 0
    repositories_not_ready_for_branch_protection = 0
    
    bulk_service = CICDPolicyBulkOperationService()
    preset_service = CICDPolicyPresetService()
    
    overall_compliance_score = 0
    
    for repo in repositories:
        compliance = bulk_service.calculate_repository_compliance(db, repo.id, workspace_id)
        overall_compliance_score += compliance["compliance_score"]
        
        # Count repositories with policy
        repo_policy = db.query(RepositoryCICDPolicy).filter(
            RepositoryCICDPolicy.repository_id == repo.id
        ).first()
        
        if repo_policy:
            repositories_with_policy += 1
            repositories_with_overrides += 1
            
            # Count preset usage
            if compliance["current_preset"]:
                preset_name = compliance["current_preset"]
                if preset_name in repositories_using_each_preset:
                    repositories_using_each_preset[preset_name] += 1
                else:
                    repositories_using_each_preset[preset_name] = 1
            
            # Count missing artifact requirement
            if not repo_policy.require_artifact:
                repositories_missing_required_artifact_policy += 1
            
            # Count manual override
            if repo_policy.allow_manual_override:
                repositories_allowing_manual_override += 1
            
            # Count branch protection readiness
            if not repo_policy.enabled:
                repositories_not_ready_for_branch_protection += 1
        else:
            repositories_inheriting_org_default += 1
            repositories_not_ready_for_branch_protection += 1
        
        # Count drift
        if compliance["drift_detected"]:
            repositories_with_drift += 1
            if compliance["drift_risk_level"] == "HIGH":
                repositories_with_high_risk_drift += 1
            elif compliance["drift_risk_level"] == "CRITICAL":
                repositories_with_critical_risk_drift += 1
    
    # Calculate overall compliance score
    if total_repositories > 0:
        overall_compliance_score = overall_compliance_score // total_repositories
    
    return OrganizationComplianceDashboard(
        total_repositories=total_repositories,
        repositories_with_policy=repositories_with_policy,
        repositories_inheriting_org_default=repositories_inheriting_org_default,
        repositories_with_overrides=repositories_with_overrides,
        repositories_with_drift=repositories_with_drift,
        repositories_with_high_risk_drift=repositories_with_high_risk_drift,
        repositories_with_critical_risk_drift=repositories_with_critical_risk_drift,
        repositories_using_each_preset=repositories_using_each_preset,
        repositories_missing_required_artifact_policy=repositories_missing_required_artifact_policy,
        repositories_allowing_manual_override=repositories_allowing_manual_override,
        repositories_not_ready_for_branch_protection=repositories_not_ready_for_branch_protection,
        overall_compliance_score=overall_compliance_score
    )


@router.get("/repositories", response_model=List[RepositoryCompliance])
def list_repositories_compliance(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> List[RepositoryCompliance]:
    """Get compliance status and scores for all repositories in the workspace."""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    repositories = db.query(Repository).filter(
        Repository.workspace_id == workspace_id,
        Repository.is_active == True
    ).all()
    
    bulk_service = CICDPolicyBulkOperationService()
    results = []
    for repo in repositories:
        compliance = bulk_service.calculate_repository_compliance(db, repo.id, workspace_id)
        results.append(RepositoryCompliance(**compliance))
        
    return results


@router.get("/repositories/{repository_id}/compliance", response_model=RepositoryCompliance)
def get_repository_compliance(
    workspace_id: uuid.UUID,
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> RepositoryCompliance:
    """Get compliance score for a specific repository."""
    # Verify organization exists
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Verify repository belongs to organization
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace_id
    ).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found in organization")
    
    bulk_service = CICDPolicyBulkOperationService()
    compliance = bulk_service.calculate_repository_compliance(db, repository_id)
    
    return RepositoryCompliance(**compliance)


@router.post("/bulk-operations", response_model=BulkOperationResult)
def execute_bulk_operation(
    workspace_id: uuid.UUID,
    payload: BulkOperationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.bulk_apply"))
) -> BulkOperationResult:
    """Execute bulk policy operation on repositories."""
    # Verify organization exists
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    bulk_service = CICDPolicyBulkOperationService()
    
    result = None
    if payload.operation == "APPLY_PRESET":
        if not payload.preset_name:
            raise HTTPException(status_code=400, detail="preset_name required for APPLY_PRESET operation")
        result = bulk_service.bulk_apply_preset(
            db,
            payload.repository_ids,
            payload.preset_name,
            current_user.id,
            workspace_id,
            payload.reason
        )
    elif payload.operation == "RESTORE_ORG_DEFAULT":
        result = bulk_service.bulk_restore_org_default(
            db,
            payload.repository_ids,
            current_user.id,
            workspace_id,
            payload.reason
        )
    elif payload.operation == "ACKNOWLEDGE_DRIFT":
        result = bulk_service.bulk_acknowledge_drift(
            db,
            payload.repository_ids,
            current_user.id,
            workspace_id,
            payload.reason
        )
    elif payload.operation == "EXPORT_POLICIES":
        result = bulk_service.bulk_export_policies(
            db,
            payload.repository_ids,
            current_user.id,
            workspace_id
        )
    elif payload.operation == "SCAN_COMPLIANCE":
        result = bulk_service.bulk_scan_compliance(
            db,
            payload.repository_ids,
            current_user.id,
            workspace_id
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown operation: {payload.operation}")
    
    # Notify about bulk operation result
    if result:
        GovernanceNotificationService.notify_bulk_operation_result(
            db=db,
            workspace_id=workspace_id,
            actor_id=current_user.id,
            operation_type=payload.operation,
            success_count=result.success_count,
            failure_count=result.failure_count
        )
    
    return result


@router.post("/bulk-preview", response_model=BulkPreviewResult)
def preview_bulk_operation(
    workspace_id: uuid.UUID,
    payload: BulkPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.bulk_preview"))
) -> BulkPreviewResult:
    """Preview bulk operation without applying changes."""
    # Verify organization exists
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Log preview audit event
    import uuid
    operation_id = uuid.uuid4()
    WorkspaceGovernanceAuditService.log_bulk_operation(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        event_type="CI_CD_BULK_POLICY_PREVIEWED",
        operation_id=operation_id,
        requested_count=len(payload.repository_ids),
        succeeded_count=0,
        failed_count=0,
        skipped_count=0,
        reason="Bulk preview"
    )
    
    repositories_affected = []
    repositories_skipped = []
    warnings = []
    
    preset_service = CICDPolicyPresetService()
    policy_service = CICDPolicyService()
    
    for repo_id in payload.repository_ids:
        repository = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repository:
            repositories_skipped.append({
                "repositoryId": str(repo_id),
                "reason": "Repository not found"
            })
            continue
        
        # Get current effective policy
        effective = policy_service.get_effective_policy(db, repo_id)
        current_preset = effective["source_preset"]
        
        if payload.operation == "APPLY_PRESET":
            target_preset = payload.preset_name
            # Get preset definition
            preset_def = preset_service.get_preset(target_preset)
            fields_that_will_change = list(preset_def["settings"].keys())
            
            risk_reduction = None
            if current_preset == "PERMISSIVE" and target_preset in ["STANDARD", "STRICT", "REGULATED"]:
                risk_reduction = "HIGH"
            elif current_preset == "STANDARD" and target_preset in ["STRICT", "REGULATED"]:
                risk_reduction = "MEDIUM"
            
            repositories_affected.append({
                "repositoryId": str(repo_id),
                "repositoryName": repository.full_name,
                "currentPreset": current_preset,
                "targetPreset": target_preset,
                "fieldsThatWillChange": fields_that_will_change
            })
            
        elif payload.operation == "RESTORE_ORG_DEFAULT":
            target_preset = effective["workspace_default_preset"] or "STANDARD"
            repositories_affected.append({
                "repositoryId": str(repo_id),
                "repositoryName": repository.full_name,
                "currentPreset": current_preset,
                "targetPreset": target_preset,
                "fieldsThatWillChange": ["all"]
            })
    
    return BulkPreviewResult(
        repositories_affected=repositories_affected,
        repositories_skipped=repositories_skipped,
        current_preset=None,
        target_preset=payload.preset_name if payload.operation == "APPLY_PRESET" else None,
        fields_that_will_change=[],
        risk_reduction=None,
        warnings=warnings
    )


@router.get("/exceptions", response_model=List[PolicyExceptionResponse])
def list_policy_exceptions(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> List[PolicyExceptionResponse]:
    """List policy exceptions for organization."""
    # Verify organization exists
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    exceptions = db.query(CICDPolicyException).filter(
        CICDPolicyException.workspace_id == workspace_id
    ).order_by(CICDPolicyException.created_at.desc()).all()
    
    return [
        PolicyExceptionResponse(
            id=exc.id,
            workspace_id=exc.workspace_id,
            repository_id=exc.repository_id,
            requested_by=exc.requested_by,
            approved_by=exc.approved_by,
            status=exc.status,
            reason=exc.reason,
            exception_fields=exc.exception_fields,
            expires_at=exc.expires_at,
            created_at=exc.created_at,
            updated_at=exc.updated_at,
            decision_reason=exc.decision_reason
        )
        for exc in exceptions
    ]


@router.post("/exceptions", response_model=PolicyExceptionResponse)
def request_policy_exception(
    workspace_id: uuid.UUID,
    payload: PolicyExceptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.exception.request"))
) -> PolicyExceptionResponse:
    """Request a policy exception for a repository."""
    # Verify organization exists
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Verify repository exists and belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == payload.repository_id
    ).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Check for existing pending exception
    existing = db.query(CICDPolicyException).filter(
        CICDPolicyException.repository_id == payload.repository_id,
        CICDPolicyException.status == "PENDING"
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Pending exception already exists for this repository")
    
    exception = CICDPolicyException(
        workspace_id=workspace_id,
        repository_id=payload.repository_id,
        requested_by=current_user.id,
        status="PENDING",
        reason=payload.reason,
        exception_fields=payload.exception_fields,
        expires_at=payload.expires_at
    )
    
    db.add(exception)
    db.commit()
    db.refresh(exception)
    
    # Notify approvers
    GovernanceNotificationService.notify_exception_requested(
        db=db,
        workspace_id=workspace_id,
        exception_id=exception.id,
        repository_id=payload.repository_id,
        requester_user_id=current_user.id
    )
    
    return PolicyExceptionResponse(
        id=exception.id,
        workspace_id=exception.workspace_id,
        repository_id=exception.repository_id,
        requested_by=exception.requested_by,
        approved_by=exception.approved_by,
        status=exception.status,
        reason=exception.reason,
        exception_fields=exception.exception_fields,
        expires_at=exception.expires_at,
        created_at=exception.created_at,
        updated_at=exception.updated_at,
        decision_reason=exception.decision_reason
    )


@router.post("/exceptions/{exception_id}/approve", response_model=PolicyExceptionResponse)
def approve_policy_exception(
    workspace_id: uuid.UUID,
    exception_id: uuid.UUID,
    payload: PolicyExceptionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.exception.approve"))
) -> PolicyExceptionResponse:
    """Approve a policy exception."""
    # Verify organization exists
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    exception = db.query(CICDPolicyException).filter(
        CICDPolicyException.id == exception_id,
        CICDPolicyException.workspace_id == workspace_id
    ).first()
    
    if not exception:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    if exception.status != "PENDING":
        raise HTTPException(status_code=400, detail="Exception is not in PENDING status")
    
    # Segregation of duties: block self-approval
    if exception.requested_by == current_user.id:
        if not GovernancePermissionService.can_approve_own_exception(db, workspace_id):
            WorkspaceGovernanceAuditService.log_self_approval_blocked(
                db=db,
                workspace_id=workspace_id,
                actor_id=current_user.id,
                exception_id=exception_id,
                reason="Requester cannot approve their own exception."
            )
            raise HTTPException(
                status_code=403,
                detail="Requester cannot approve their own exception."
            )
    
    exception.status = "APPROVED"
    exception.approved_by = current_user.id
    exception.decision_reason = payload.decision_reason
    exception.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(exception)
    
    # Notify requester and owner
    GovernanceNotificationService.notify_exception_status_changed(
        db=db,
        workspace_id=workspace_id,
        exception_id=exception.id,
        repository_id=exception.repository_id,
        requester_user_id=exception.requested_by,
        status="APPROVED"
    )
    
    return PolicyExceptionResponse(
        id=exception.id,
        workspace_id=exception.workspace_id,
        repository_id=exception.repository_id,
        requested_by=exception.requested_by,
        approved_by=exception.approved_by,
        status=exception.status,
        reason=exception.reason,
        exception_fields=exception.exception_fields,
        expires_at=exception.expires_at,
        created_at=exception.created_at,
        updated_at=exception.updated_at,
        decision_reason=exception.decision_reason
    )


@router.post("/exceptions/{exception_id}/reject", response_model=PolicyExceptionResponse)
def reject_policy_exception(
    workspace_id: uuid.UUID,
    exception_id: uuid.UUID,
    payload: PolicyExceptionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.exception.reject"))
) -> PolicyExceptionResponse:
    """Reject a policy exception."""
    # Verify organization exists
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    exception = db.query(CICDPolicyException).filter(
        CICDPolicyException.id == exception_id,
        CICDPolicyException.workspace_id == workspace_id
    ).first()
    
    if not exception:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    if exception.status != "PENDING":
        raise HTTPException(status_code=400, detail="Exception is not in PENDING status")
    
    exception.status = "REJECTED"
    exception.approved_by = current_user.id
    exception.decision_reason = payload.decision_reason
    exception.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(exception)
    
    # Notify requester and owner
    GovernanceNotificationService.notify_exception_status_changed(
        db=db,
        workspace_id=workspace_id,
        exception_id=exception.id,
        repository_id=exception.repository_id,
        requester_user_id=exception.requested_by,
        status="REJECTED"
    )
    
    return PolicyExceptionResponse(
        id=exception.id,
        workspace_id=exception.workspace_id,
        repository_id=exception.repository_id,
        requested_by=exception.requested_by,
        approved_by=exception.approved_by,
        status=exception.status,
        reason=exception.reason,
        exception_fields=exception.exception_fields,
        expires_at=exception.expires_at,
        created_at=exception.created_at,
        updated_at=exception.updated_at,
        decision_reason=exception.decision_reason
    )


@router.post("/exceptions/{exception_id}/revoke", response_model=PolicyExceptionResponse)
def revoke_policy_exception(
    workspace_id: uuid.UUID,
    exception_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.exception.revoke"))
) -> PolicyExceptionResponse:
    """Revoke an approved policy exception."""
    # Verify organization exists
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    exception = db.query(CICDPolicyException).filter(
        CICDPolicyException.id == exception_id,
        CICDPolicyException.workspace_id == workspace_id
    ).first()
    
    if not exception:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    if exception.status != "APPROVED":
        raise HTTPException(status_code=400, detail="Exception is not in APPROVED status")
    
    exception.status = "REVOKED"
    exception.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(exception)
    
    # Notify requester and owner
    GovernanceNotificationService.notify_exception_status_changed(
        db=db,
        workspace_id=workspace_id,
        exception_id=exception.id,
        repository_id=exception.repository_id,
        requester_user_id=exception.requested_by,
        status="REVOKED"
    )
    
    return PolicyExceptionResponse(
        id=exception.id,
        workspace_id=exception.workspace_id,
        repository_id=exception.repository_id,
        requested_by=exception.requested_by,
        approved_by=exception.approved_by,
        status=exception.status,
        reason=exception.reason,
        exception_fields=exception.exception_fields,
        expires_at=exception.expires_at,
        created_at=exception.created_at,
        updated_at=exception.updated_at,
        decision_reason=exception.decision_reason
    )


@router.post("/review-snapshots", response_model=GovernanceReviewSnapshotResponse)
def create_governance_review_snapshot(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> GovernanceReviewSnapshotResponse:
    """Create a governance review snapshot."""
    # Verify organization exists
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get compliance dashboard
    from app.routers.organization_governance import get_organization_compliance_dashboard
    compliance = get_organization_compliance_dashboard(workspace_id, db, current_user)
    
    # Count repositories by status
    repositories = db.query(Repository).filter(
        Repository.workspace_id == workspace_id
    ).all()
    
    bulk_service = CICDPolicyBulkOperationService()
    critical_count = 0
    high_risk_count = 0
    drifted_count = 0
    compliant_count = 0
    
    for repo in repositories:
        repo_compliance = bulk_service.calculate_repository_compliance(db, repo.id)
        if repo_compliance["compliance_status"] == "CRITICAL":
            critical_count += 1
        elif repo_compliance["compliance_status"] == "HIGH_RISK":
            high_risk_count += 1
        elif repo_compliance["compliance_status"] == "DRIFTED":
            drifted_count += 1
        elif repo_compliance["compliance_status"] == "COMPLIANT":
            compliant_count += 1
    
    snapshot = CICDGovernanceReviewSnapshot(
        workspace_id=workspace_id,
        created_by=current_user.id,
        total_repositories=compliance.total_repositories,
        compliance_score=compliance.overall_compliance_score,
        critical_count=critical_count,
        high_risk_count=high_risk_count,
        drifted_count=drifted_count,
        compliant_count=compliant_count,
        snapshot_json=compliance.dict()
    )
    
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    
    # Notify about governance review creation
    GovernanceNotificationService.notify_governance_review_created(
        db=db,
        workspace_id=workspace_id,
        review_id=snapshot.id
    )
    
    # Log governance review audit event
    WorkspaceGovernanceAuditService.log_governance_review(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        review_id=snapshot.id,
        reason="Manual governance review snapshot"
    )
    
    return GovernanceReviewSnapshotResponse(
        id=snapshot.id,
        workspace_id=snapshot.workspace_id,
        created_at=snapshot.created_at,
        created_by=snapshot.created_by,
        total_repositories=snapshot.total_repositories,
        compliance_score=snapshot.compliance_score,
        critical_count=snapshot.critical_count,
        high_risk_count=snapshot.high_risk_count,
        drifted_count=snapshot.drifted_count,
        compliant_count=snapshot.compliant_count
    )


@router.get("/review-snapshots", response_model=List[GovernanceReviewSnapshotResponse])
def list_governance_review_snapshots(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.view"))
) -> List[GovernanceReviewSnapshotResponse]:
    """List governance review snapshots for organization."""
    # Verify organization exists
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    snapshots = db.query(CICDGovernanceReviewSnapshot).filter(
        CICDGovernanceReviewSnapshot.workspace_id == workspace_id
    ).order_by(CICDGovernanceReviewSnapshot.created_at.desc()).limit(20).all()
    
    return [
        GovernanceReviewSnapshotResponse(
            id=snap.id,
            workspace_id=snap.workspace_id,
            created_at=snap.created_at,
            created_by=snap.created_by,
            total_repositories=snap.total_repositories,
            compliance_score=snap.compliance_score,
            critical_count=snap.critical_count,
            high_risk_count=snap.high_risk_count,
            drifted_count=snap.drifted_count,
            compliant_count=snap.compliant_count
        )
        for snap in snapshots
    ]


@router.get("/report")
def export_governance_report(
    workspace_id: uuid.UUID,
    format: str = "JSON",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.policy.export"))
):
    """Export governance report in specified format."""
    # Verify organization exists
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Log report export audit event
    WorkspaceGovernanceAuditService.log_report_export(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        format=format,
        reason="Manual governance report export"
    )
    
    # Get compliance dashboard
    from app.routers.organization_governance import get_organization_compliance_dashboard
    compliance = get_organization_compliance_dashboard(workspace_id, db, current_user)
    
    # Get repositories with compliance
    repositories = db.query(Repository).filter(
        Repository.workspace_id == workspace_id
    ).all()
    
    bulk_service = CICDPolicyBulkOperationService()
    repository_compliance_list = []
    
    for repo in repositories:
        repo_compliance = bulk_service.calculate_repository_compliance(db, repo.id)
        repository_compliance_list.append(repo_compliance)
    
    # Get exceptions
    exceptions = db.query(CICDPolicyException).filter(
        CICDPolicyException.workspace_id == workspace_id
    ).all()
    
    report = {
        "workspace_id": str(workspace_id),
        "generated_at": datetime.utcnow().isoformat(),
        "compliance_summary": compliance.dict(),
        "repository_compliance": repository_compliance_list,
        "active_exceptions": [
            {
                "id": str(exc.id),
                "repository_id": str(exc.repository_id),
                "status": exc.status,
                "exception_fields": exc.exception_fields,
                "expires_at": exc.expires_at.isoformat() if exc.expires_at else None
            }
            for exc in exceptions if exc.status == "APPROVED"
        ],
        "expired_exceptions": [
            {
                "id": str(exc.id),
                "repository_id": str(exc.repository_id),
                "status": exc.status,
                "exception_fields": exc.exception_fields
            }
            for exc in exceptions if exc.status == "EXPIRED"
        ]
    }
    
    if format.upper() == "JSON":
        return report
    elif format.upper() == "CSV":
        # Simple CSV conversion
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write compliance summary
        writer.writerow(["Compliance Summary"])
        writer.writerow(["Total Repositories", compliance.total_repositories])
        writer.writerow(["Overall Compliance Score", compliance.overall_compliance_score])
        writer.writerow([])
        
        # Write repository compliance
        writer.writerow(["Repository Compliance"])
        writer.writerow(["Repository", "Policy Source", "Current Preset", "Drift Detected", "Risk Level", "Compliance Score", "Status"])
        for rc in repository_compliance_list:
            writer.writerow([
                rc["repository_name"],
                rc["policy_source"],
                rc["current_preset"] or "N/A",
                rc["drift_detected"],
                rc["drift_risk_level"],
                rc["compliance_score"],
                rc["compliance_status"]
            ])
        
        return {"csv": output.getvalue()}
    elif format.upper() == "MARKDOWN":
        markdown = f"""# Governance Report for Workspace {workspace_id}

Generated: {datetime.utcnow().isoformat()}

## Compliance Summary

- Total Repositories: {compliance.total_repositories}
- Overall Compliance Score: {compliance.overall_compliance_score}%
- Repositories with Policy: {compliance.repositories_with_policy}
- Repositories with Drift: {compliance.repositories_with_drift}
- High-Risk Repositories: {compliance.repositories_with_high_risk_drift}
- Critical-Risk Repositories: {compliance.repositories_with_critical_risk_drift}

## Repository Compliance

| Repository | Policy Source | Current Preset | Drift | Risk Level | Score | Status |
|------------|---------------|----------------|-------|------------|-------|--------|
"""
        for rc in repository_compliance_list:
            markdown += f"| {rc['repository_name']} | {rc['policy_source']} | {rc['current_preset'] or 'N/A'} | {rc['drift_detected']} | {rc['drift_risk_level']} | {rc['compliance_score']} | {rc['compliance_status']} |\n"
        
        return {"markdown": markdown}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


# Analytics Endpoints

@router.get("/analytics")
def get_governance_analytics(
    workspace_id: uuid.UUID,
    window_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.analytics.view"))
) -> Dict[str, Any]:
    """Get comprehensive governance analytics."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return CICDGovernanceAnalyticsService.get_governance_analytics(db, workspace_id, window_days)


@router.get("/trends/compliance")
def get_compliance_trend(
    workspace_id: uuid.UUID,
    window_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.analytics.view"))
) -> Dict[str, Any]:
    """Get compliance trend analytics."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return CICDGovernanceAnalyticsService.get_compliance_trend(db, workspace_id, window_days)


@router.get("/trends/policy-adoption")
def get_policy_adoption_trend(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.analytics.view"))
) -> Dict[str, Any]:
    """Get policy adoption analytics."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return CICDGovernanceAnalyticsService.get_policy_adoption_trend(db, workspace_id)


@router.get("/trends/drift")
def get_drift_trend(
    workspace_id: uuid.UUID,
    window_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.analytics.view"))
) -> Dict[str, Any]:
    """Get drift trend analytics."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return CICDGovernanceAnalyticsService.get_drift_trend(db, workspace_id, window_days)


@router.get("/analytics/exceptions")
def get_exception_analytics(
    workspace_id: uuid.UUID,
    window_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.analytics.view"))
) -> Dict[str, Any]:
    """Get exception analytics."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return CICDGovernanceAnalyticsService.get_exception_analytics(db, workspace_id, window_days)


@router.get("/risk-heatmap")
def get_repository_risk_heatmap(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.analytics.view"))
) -> List[Dict[str, Any]]:
    """Get repository risk heatmap."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return CICDGovernanceAnalyticsService.get_repository_risk_heatmap(db, workspace_id)


@router.get("/maturity-score")
def get_governance_maturity_score(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.analytics.view"))
) -> Dict[str, Any]:
    """Get governance maturity score."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return CICDGovernanceAnalyticsService.get_governance_maturity_score(db, workspace_id)


@router.get("/executive-summary")
def get_executive_summary(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.executive_report.view"))
) -> Dict[str, Any]:
    """Get executive governance summary."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    analytics = CICDGovernanceAnalyticsService.get_governance_analytics(db, workspace_id)
    maturity = CICDGovernanceAnalyticsService.get_governance_maturity_score(db, workspace_id)
    heatmap = CICDGovernanceAnalyticsService.get_repository_risk_heatmap(db, workspace_id)
    
    # Generate top risks and recommendations
    critical_repos = [r for r in heatmap if r["risk_band"] == "CRITICAL"][:5]
    high_risk_repos = [r for r in heatmap if r["risk_band"] == "HIGH"][:5]
    
    top_risks = []
    for repo in critical_repos:
        top_risks.append({
            "repository": repo["repository_name"],
            "risk_band": repo["risk_band"],
            "risk_score": repo["risk_score"],
            "reasons": repo["risk_reasons"]
        })
    
    for repo in high_risk_repos:
        top_risks.append({
            "repository": repo["repository_name"],
            "risk_band": repo["risk_band"],
            "risk_score": repo["risk_score"],
            "reasons": repo["risk_reasons"]
        })
    
    return {
        "overall_compliance_score": analytics["compliance_trend"]["current_compliance_score"],
        "maturity_score": maturity["score"],
        "maturity_level": maturity["level"],
        "trend_direction": analytics["compliance_trend"]["trend_direction"],
        "total_repositories": len(heatmap),
        "critical_repositories": len(critical_repos),
        "high_risk_repositories": len(high_risk_repos),
        "repositories_with_drift": analytics["drift_trend"]["current_drifted_repositories"],
        "active_exceptions": analytics["exception_analytics"]["active_exceptions"],
        "pending_exceptions": analytics["exception_analytics"]["pending_exceptions"],
        "expired_exceptions": analytics["exception_analytics"]["expired_exceptions"],
        "branch_protection_ready_percentage": round(
            sum(1 for r in heatmap if r["branch_protection_ready"]) / len(heatmap) * 100, 1
        ) if heatmap else 0,
        "top_risks": top_risks,
        "top_recommendations": maturity["recommended_next_actions"],
        "generated_at": datetime.utcnow().isoformat()
    }


@router.post("/snapshots/compare")
def compare_governance_snapshots(
    workspace_id: uuid.UUID,
    from_snapshot_id: uuid.UUID,
    to_snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.analytics.view"))
) -> Dict[str, Any]:
    """Compare two governance review snapshots."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return CICDGovernanceAnalyticsService.compare_governance_snapshots(
        db, workspace_id, from_snapshot_id, to_snapshot_id
    )


@router.get("/executive-report")
def export_executive_report(
    workspace_id: uuid.UUID,
    format: str = "json",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.executive_report.export"))
):
    """Export executive governance report."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Log report export audit event
    WorkspaceGovernanceAuditService.log_report_export(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        format=format,
        reason="Executive governance report export"
    )
    
    report = CICDGovernanceAnalyticsService.generate_executive_report(db, workspace_id, format)
    
    if format.upper() == "JSON":
        return report
    elif format.upper() == "CSV":
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write executive summary
        writer.writerow(["Executive Summary"])
        for key, value in report["executive_summary"].items():
            writer.writerow([key, value])
        writer.writerow([])
        
        # Write maturity score
        writer.writerow(["Maturity Score"])
        writer.writerow(["Score", report["maturity_score"]["score"]])
        writer.writerow(["Level", report["maturity_score"]["level"]])
        writer.writerow([])
        
        # Write top critical repositories
        writer.writerow(["Top Critical Repositories"])
        writer.writerow(["Repository", "Risk Band", "Risk Score", "Recommended Action"])
        for repo in report["top_critical_repositories"]:
            writer.writerow([
                repo["repository_name"],
                repo["risk_band"],
                repo["risk_score"],
                repo["recommended_action"]
            ])
        writer.writerow([])
        
        # Write recommended actions
        writer.writerow(["Recommended Executive Actions"])
        for action in report["recommended_executive_actions"]:
            writer.writerow([action])
        
        return {"csv": output.getvalue()}
    elif format.upper() == "MARKDOWN":
        markdown = f"""# Executive Governance Report

Workspace ID: {workspace_id}
Generated: {report["generated_at"]}

## Executive Summary

- Overall Compliance Score: {report["executive_summary"]["overall_compliance_score"]}%
- Maturity Score: {report["executive_summary"]["maturity_score"]}/100 ({report["executive_summary"]["maturity_level"]})
- Trend Direction: {report["executive_summary"]["trend_direction"]}
- Total Repositories: {report["executive_summary"]["total_repositories"]}
- Critical Repositories: {report["executive_summary"]["critical_repositories"]}
- High-Risk Repositories: {report["executive_summary"]["high_risk_repositories"]}
- Repositories with Drift: {report["executive_summary"]["repositories_with_drift"]}
- Active Exceptions: {report["executive_summary"]["active_exceptions"]}
- Pending Exceptions: {report["executive_summary"]["pending_exceptions"]}
- Expired Exceptions: {report["executive_summary"]["expired_exceptions"]}
- Branch Protection Ready: {report["executive_summary"]["branch_protection_ready_percentage"]}%

## Maturity Score

- Total Score: {report["maturity_score"]["score"]}/100
- Level: {report["maturity_score"]["level"]}

### Dimension Scores

- Policy Coverage: {report["maturity_score"]["dimension_scores"]["policy_coverage"]}/20
- Policy Consistency: {report["maturity_score"]["dimension_scores"]["policy_consistency"]}/20
- Branch Protection Readiness: {report["maturity_score"]["dimension_scores"]["branch_protection_readiness"]}/20
- Exception Hygiene: {report["maturity_score"]["dimension_scores"]["exception_hygiene"]}/20
- Operational Observability: {report["maturity_score"]["dimension_scores"]["operational_observability"]}/10
- Evidence Preservation: {report["maturity_score"]["dimension_scores"]["evidence_preservation"]}/10

### Strengths

"""
        for strength in report["maturity_score"]["strengths"]:
            markdown += f"- {strength}\n"
        
        markdown += "\n### Weaknesses\n\n"
        for weakness in report["maturity_score"]["weaknesses"]:
            markdown += f"- {weakness}\n"
        
        markdown += "\n## Top Critical Repositories\n\n"
        markdown += "| Repository | Risk Band | Risk Score | Recommended Action |\n"
        markdown += "|-----------|-----------|------------|-------------------|\n"
        for repo in report["top_critical_repositories"]:
            markdown += f"| {repo['repository_name']} | {repo['risk_band']} | {repo['risk_score']} | {repo['recommended_action']} |\n"
        
        markdown += "\n## Recommended Executive Actions\n\n"
        for action in report["recommended_executive_actions"]:
            markdown += f"- {action}\n"
        
        return {"markdown": markdown}
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")


# Role Assignment Endpoints

@router.get("/roles")
def list_role_assignments(
    workspace_id: uuid.UUID,
    role: str = None,
    scope_type: str = None,
    repository_id: uuid.UUID = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.roles.view"))
) -> List[Dict[str, Any]]:
    """List governance role assignments for organization."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    query = db.query(GovernanceRoleAssignment).filter(
        GovernanceRoleAssignment.workspace_id == workspace_id
    )
    
    if role:
        query = query.filter(GovernanceRoleAssignment.role == GovernanceRole(role))
    
    if scope_type:
        query = query.filter(GovernanceRoleAssignment.scope_type == ScopeType(scope_type))
    
    if repository_id:
        query = query.filter(GovernanceRoleAssignment.repository_id == repository_id)
    
    if active_only:
        query = query.filter(GovernanceRoleAssignment.is_active == True)
    
    assignments = query.order_by(GovernanceRoleAssignment.created_at.desc()).all()
    
    return [
        {
            "id": str(assignment.id),
            "user_id": str(assignment.user_id),
            "role": assignment.role.value,
            "scope_type": assignment.scope_type.value,
            "repository_id": str(assignment.repository_id) if assignment.repository_id else None,
            "assigned_by": str(assignment.assigned_by) if assignment.assigned_by else None,
            "created_at": assignment.created_at.isoformat(),
            "expires_at": assignment.expires_at.isoformat() if assignment.expires_at else None,
            "is_active": assignment.is_active,
        }
        for assignment in assignments
    ]


@router.post("/roles")
def assign_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    scope_type: str,
    repository_id: uuid.UUID = None,
    expires_at: datetime = None,
    reason: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.roles.assign"))
) -> Dict[str, Any]:
    """Assign a governance role to a user."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Validate role
    try:
        governance_role = GovernanceRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    
    # Validate scope type
    try:
        governance_scope = ScopeType(scope_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid scope type: {scope_type}")
    
    # If repository-scoped, validate repository exists and belongs to organization
    if governance_scope == ScopeType.REPOSITORY:
        if not repository_id:
            raise HTTPException(status_code=400, detail="repository_id required for REPOSITORY scope")
        repository = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.workspace_id == workspace_id
        ).first()
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found in organization")
    
    # Check for existing active assignment
    existing = db.query(GovernanceRoleAssignment).filter(
        GovernanceRoleAssignment.user_id == user_id,
        GovernanceRoleAssignment.workspace_id == workspace_id,
        GovernanceRoleAssignment.role == governance_role,
        GovernanceRoleAssignment.scope_type == governance_scope,
        GovernanceRoleAssignment.repository_id == repository_id if governance_scope == ScopeType.REPOSITORY else None,
        GovernanceRoleAssignment.is_active == True
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Active role assignment already exists")
    
    # Create role assignment
    assignment = GovernanceRoleAssignment(
        workspace_id=workspace_id,
        repository_id=repository_id if governance_scope == ScopeType.REPOSITORY else None,
        user_id=user_id,
        role=governance_role,
        scope_type=governance_scope,
        assigned_by=current_user.id,
        expires_at=expires_at,
        is_active=True
    )
    
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    
    # Log audit event
    WorkspaceGovernanceAuditService.log_role_assigned(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        target_user_id=user_id,
        role=role,
        scope_type=scope_type,
        repository_id=repository_id,
        reason=reason
    )
    
    # Log delegated admin if repository policy manager
    if governance_role == GovernanceRole.REPOSITORY_POLICY_MANAGER and governance_scope == ScopeType.REPOSITORY:
        WorkspaceGovernanceAuditService.log_delegated_admin_granted(
            db=db,
            workspace_id=workspace_id,
            actor_id=current_user.id,
            target_user_id=user_id,
            repository_id=repository_id,
            reason=reason
        )
    
    return {
        "id": str(assignment.id),
        "user_id": str(assignment.user_id),
        "role": assignment.role.value,
        "scope_type": assignment.scope_type.value,
        "repository_id": str(assignment.repository_id) if assignment.repository_id else None,
        "assigned_by": str(assignment.assigned_by),
        "created_at": assignment.created_at.isoformat(),
        "expires_at": assignment.expires_at.isoformat() if assignment.expires_at else None,
        "is_active": assignment.is_active,
    }


@router.delete("/roles/{assignment_id}")
def revoke_role(
    workspace_id: uuid.UUID,
    assignment_id: uuid.UUID,
    reason: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.roles.assign"))
) -> Dict[str, Any]:
    """Revoke a governance role assignment."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    assignment = db.query(GovernanceRoleAssignment).filter(
        GovernanceRoleAssignment.id == assignment_id,
        GovernanceRoleAssignment.workspace_id == workspace_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Role assignment not found")
    
    # Mark as inactive instead of deleting
    assignment.is_active = False
    
    db.commit()
    
    # Log audit event
    WorkspaceGovernanceAuditService.log_role_revoked(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        target_user_id=assignment.user_id,
        role=assignment.role.value,
        scope_type=assignment.scope_type.value,
        repository_id=assignment.repository_id,
        reason=reason
    )
    
    # Log delegated admin revoked if repository policy manager
    if assignment.role == GovernanceRole.REPOSITORY_POLICY_MANAGER and assignment.scope_type == ScopeType.REPOSITORY:
        WorkspaceGovernanceAuditService.log_delegated_admin_revoked(
            db=db,
            workspace_id=workspace_id,
            actor_id=current_user.id,
            target_user_id=assignment.user_id,
            repository_id=assignment.repository_id,
            reason=reason
        )
    
    return {"message": "Role assignment revoked"}


@router.get("/users/{user_id}/permissions")
def get_user_effective_permissions(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    repository_id: uuid.UUID = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.roles.view"))
) -> Dict[str, Any]:
    """Get effective permissions for a user."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return GovernancePermissionService.list_effective_permissions(
        db=db,
        user_id=user_id,
        workspace_id=workspace_id,
        repository_id=repository_id
    )


@router.get("/repositories/{repository_id}/users/{user_id}/permissions")
def get_user_repository_permissions(
    workspace_id: uuid.UUID,
    repository_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.roles.view"))
) -> Dict[str, Any]:
    """Get effective permissions for a user in a specific repository."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace_id
    ).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found in organization")
    
    return GovernancePermissionService.list_effective_permissions(
        db=db,
        user_id=user_id,
        workspace_id=workspace_id,
        repository_id=repository_id
    )


@router.post("/permissions/check")
def check_permission(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    permission: str,
    repository_id: uuid.UUID = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.roles.view"))
) -> Dict[str, Any]:
    """Check if a user has a specific permission."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    allowed = GovernancePermissionService.has_permission(
        db=db,
        user_id=user_id,
        permission=permission,
        workspace_id=workspace_id,
        repository_id=repository_id
    )
    
    explanation = GovernancePermissionService.explain_access_decision(
        db=db,
        user_id=user_id,
        permission=permission,
        workspace_id=workspace_id,
        repository_id=repository_id
    )
    
    return {
        "allowed": allowed,
        **explanation
    }


@router.get("/audit")
def get_governance_audit(
    workspace_id: uuid.UUID,
    event_type: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.audit.view"))
) -> List[Dict[str, Any]]:
    """Get governance audit events for organization."""
    organization = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    query = db.query(WorkspaceGovernanceAuditEvent).filter(
        WorkspaceGovernanceAuditEvent.workspace_id == workspace_id
    )
    
    if event_type:
        query = query.filter(WorkspaceGovernanceAuditEvent.event_type == event_type)
    
    events = query.order_by(WorkspaceGovernanceAuditEvent.timestamp.desc()).limit(limit).all()
    
    return [
        {
            "id": str(event.id),
            "event_type": event.event_type,
            "actor_id": str(event.actor_id),
            "operation_id": str(event.operation_id) if event.operation_id else None,
            "requested_count": event.requested_count,
            "succeeded_count": event.succeeded_count,
            "failed_count": event.failed_count,
            "skipped_count": event.skipped_count,
            "reason": event.reason,
            "metadata": event.audit_metadata,
            "timestamp": event.timestamp.isoformat(),
        }
        for event in events
    ]
