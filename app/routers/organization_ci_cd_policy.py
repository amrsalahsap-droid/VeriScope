"""
Workspace CI/CD Policy Router

Provides endpoints for managing workspace-level CI/CD policy defaults.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.workspace_ci_cd_policy_default import WorkspaceCICDPolicyDefault
from app.services.governance_permission_service import GovernancePermissionService
from app.schemas.ci_cd_policy import (
    OrganizationDefaultPolicyResponse,
    OrganizationDefaultPolicyUpdate
)
from app.dependencies.auth import get_current_user
from app.models.user import User, Workspace

router = APIRouter(tags=["cicd-policy-organization"])


def require_permission(permission: str):
    """Dependency to require a specific governance permission."""
    def dependency(
        workspace_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> User:
        # Check permission
        has_perm = GovernancePermissionService.has_permission(
            db, current_user.id, permission, workspace_id
        )
        
        if not has_perm:
            explanation = GovernancePermissionService.explain_access_decision(
                db, current_user.id, permission, workspace_id
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


@router.get("", response_model=OrganizationDefaultPolicyResponse)
def get_organization_default_policy(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.org_default.view"))
) -> OrganizationDefaultPolicyResponse:
    """Get workspace default CI/CD policy."""
    # Verify workspace exists
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get or create default policy
    org_default = db.query(WorkspaceCICDPolicyDefault).filter(
        WorkspaceCICDPolicyDefault.workspace_id == workspace_id
    ).first()
    
    if not org_default:
        # Create default policy
        org_default = WorkspaceCICDPolicyDefault(
            workspace_id=workspace_id,
            preset_name="STANDARD",
            auto_apply_to_new_repositories=True,
            allow_repository_override=True,
            require_override_reason=True
        )
        db.add(org_default)
        db.commit()
        db.refresh(org_default)
    
    return OrganizationDefaultPolicyResponse(
        id=org_default.id,
        organization_id=org_default.workspace_id,
        default_preset=org_default.preset_name,
        default_policy_json=org_default.default_policy_json,
        auto_apply_to_new_repositories=org_default.auto_apply_to_new_repositories,
        allow_repository_override=org_default.allow_repository_override,
        require_override_reason=org_default.require_override_reason,
        created_at=org_default.created_at,
        updated_at=org_default.updated_at,
        updated_by=org_default.updated_by
    )


@router.put("", response_model=OrganizationDefaultPolicyResponse)
def update_organization_default_policy(
    workspace_id: uuid.UUID,
    payload: OrganizationDefaultPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.org_default.update"))
) -> OrganizationDefaultPolicyResponse:
    """Update workspace default CI/CD policy."""
    # Verify workspace exists
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Get or create default policy
    org_default = db.query(WorkspaceCICDPolicyDefault).filter(
        WorkspaceCICDPolicyDefault.workspace_id == workspace_id
    ).first()
    
    if not org_default:
        org_default = WorkspaceCICDPolicyDefault(
            workspace_id=workspace_id,
            preset_name="STANDARD",
            auto_apply_to_new_repositories=True,
            allow_repository_override=True,
            require_override_reason=True
        )
        db.add(org_default)
    
    # Update fields from payload
    if payload.default_preset is not None:
        org_default.preset_name = payload.default_preset
    if payload.default_policy_json is not None:
        org_default.default_policy_json = payload.default_policy_json
    if payload.auto_apply_to_new_repositories is not None:
        org_default.auto_apply_to_new_repositories = payload.auto_apply_to_new_repositories
    if payload.allow_repository_override is not None:
        org_default.allow_repository_override = payload.allow_repository_override
    if payload.require_override_reason is not None:
        org_default.require_override_reason = payload.require_override_reason
    
    org_default.updated_at = datetime.utcnow()
    org_default.updated_by = current_user.id
    
    db.commit()
    db.refresh(org_default)
    
    # Log audit event
    from app.services.ci_cd_policy_audit_service import CICDPolicyAuditService
    CICDPolicyAuditService.log_policy_updated(
        db=db,
        repository_id=None,
        before_policy={},
        after_policy=payload.dict(exclude_none=True),
        changed_fields=list(payload.dict(exclude_none=True).keys()),
        actor_id=current_user.id,
        actor_type="USER"
    )
    
    return OrganizationDefaultPolicyResponse(
        id=org_default.id,
        organization_id=org_default.workspace_id,
        default_preset=org_default.preset_name,
        default_policy_json=org_default.default_policy_json,
        auto_apply_to_new_repositories=org_default.auto_apply_to_new_repositories,
        allow_repository_override=org_default.allow_repository_override,
        require_override_reason=org_default.require_override_reason,
        created_at=org_default.created_at,
        updated_at=org_default.updated_at,
        updated_by=org_default.updated_by
    )
