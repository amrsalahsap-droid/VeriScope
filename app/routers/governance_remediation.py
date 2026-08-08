"""
Governance Remediation API Router

Provides prefix-free endpoints for managing manual remediation actions, previews, confirmations, and bulk executions.
The router is registered in main.py.
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.dependencies.auth import get_current_user
from app.services.governance_remediation_service import GovernanceRemediationService
from app.services.governance_permission_service import GovernancePermissionService


# Pydantic schemas
class RemediationActionCreateRequest(BaseModel):
    source_type: str = Field(..., description="Source of the finding (e.g. ACCESS_REVIEW_ITEM, MANUAL)")
    action_type: str = Field(..., description="Action type (e.g. REVOKE_ROLE, CHANGE_ROLE_SCOPE, etc.)")
    source_id: Optional[uuid.UUID] = None
    target_user_id: Optional[uuid.UUID] = None
    target_role: Optional[str] = None
    target_assignment_id: Optional[uuid.UUID] = None
    target_exception_id: Optional[uuid.UUID] = None
    target_policy_id: Optional[uuid.UUID] = None
    repository_id: Optional[uuid.UUID] = None
    confirmation_message: Optional[str] = None


class RemediationActionConfirmRequest(BaseModel):
    confirm_text: str = Field(..., description="Must type exactly 'CONFIRM'")


class BulkRemediationPreviewRequest(BaseModel):
    bulk_type: str = Field(..., description="Type of bulk remediation (expired_role_cleanup, expired_exception_cleanup, policy_drift_remediation)")
    reason: Optional[str] = None


class BulkRemediationItem(BaseModel):
    item_id: str
    action_type: str
    target_id: str


class BulkRemediationExecuteRequest(BaseModel):
    items: List[BulkRemediationItem]
    reason: Optional[str] = None


class RemediationActionResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    repository_id: Optional[uuid.UUID] = None
    source_type: str
    source_id: Optional[uuid.UUID] = None
    action_type: str
    status: str
    requested_by: uuid.UUID
    requested_at: datetime
    confirmed_by: Optional[uuid.UUID] = None
    confirmed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    target_user_id: Optional[uuid.UUID] = None
    target_role: Optional[str] = None
    target_assignment_id: Optional[uuid.UUID] = None
    target_exception_id: Optional[uuid.UUID] = None
    target_policy_id: Optional[uuid.UUID] = None
    impact_preview_json: Optional[Dict[str, Any]] = None
    execution_result_json: Optional[Dict[str, Any]] = None
    requires_confirmation: bool
    confirmation_message: Optional[str] = None
    failure_reason: Optional[str] = None


class BulkItemPreviewResponse(BaseModel):
    item_id: str
    action_type: str
    target_id: str
    target_user_id: Optional[str] = None
    details: str


class BulkItemResultResponse(BaseModel):
    item_id: str
    action_type: str
    target_id: str
    status: str
    success: bool
    failure_reason: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None


# Create router (prefix-free)
router = APIRouter(tags=["governance-remediation"])


def map_action_to_response(action) -> RemediationActionResponse:
    """Helper to map a model instance to Pydantic schema."""
    return RemediationActionResponse(
        id=action.id,
        workspace_id=action.workspace_id,
        repository_id=action.repository_id,
        source_type=action.source_type,
        source_id=action.source_id,
        action_type=action.action_type,
        status=action.status,
        requested_by=action.requested_by,
        requested_at=action.requested_at,
        confirmed_by=action.confirmed_by,
        confirmed_at=action.confirmed_at,
        completed_at=action.completed_at,
        cancelled_at=action.cancelled_at,
        target_user_id=action.target_user_id,
        target_role=action.target_role,
        target_assignment_id=action.target_assignment_id,
        target_exception_id=action.target_exception_id,
        target_policy_id=action.target_policy_id,
        impact_preview_json=action.impact_preview_json,
        execution_result_json=action.execution_result_json,
        requires_confirmation=action.requires_confirmation,
        confirmation_message=action.confirmation_message,
        failure_reason=action.failure_reason
    )


# Permission helper
def require_remediation_permission(permission: str):
    """Dependency to check general remediation permissions."""
    def dependency(
        workspace_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> User:
        if not GovernancePermissionService.has_permission(db, current_user.id, permission, workspace_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have the required permission: {permission}"
            )
        return current_user
    return dependency


@router.post("/remediation/actions", response_model=RemediationActionResponse, status_code=status.HTTP_201_CREATED)
def create_remediation_action(
    workspace_id: uuid.UUID,
    request: RemediationActionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RemediationActionResponse:
    """Create a manual remediation action in DRAFT state."""
    try:
        action = GovernanceRemediationService.create_remediation_action(
            db=db,
            workspace_id=workspace_id,
            requested_by=current_user.id,
            source_type=request.source_type,
            action_type=request.action_type,
            source_id=request.source_id,
            target_user_id=request.target_user_id,
            target_role=request.target_role,
            target_assignment_id=request.target_assignment_id,
            target_exception_id=request.target_exception_id,
            target_policy_id=request.target_policy_id,
            repository_id=request.repository_id,
            confirmation_message=request.confirmation_message
        )
        
        # Notify that remediation action is created
        from app.services.governance_notification_service import GovernanceNotificationService
        GovernanceNotificationService.notify_remediation_created(
            db=db,
            workspace_id=workspace_id,
            action_id=action.id,
            target_user_id=action.target_user_id
        )
        
        return map_action_to_response(action)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get("/remediation/actions", response_model=List[RemediationActionResponse])
def list_remediation_actions(
    workspace_id: uuid.UUID,
    status_filter: Optional[str] = None,
    action_type: Optional[str] = None,
    source_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_remediation_permission("governance.remediation.view"))
) -> List[RemediationActionResponse]:
    """List remediation actions in the workspace."""
    actions = GovernanceRemediationService.list_remediation_actions(
        db=db,
        workspace_id=workspace_id,
        status=status_filter,
        action_type=action_type,
        source_type=source_type
    )
    return [map_action_to_response(a) for a in actions]


@router.get("/remediation/summary")
def get_remediation_summary(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_remediation_permission("governance.remediation.view"))
) -> Dict[str, Any]:
    """Get summary metrics of remediation actions."""
    return GovernanceRemediationService.get_remediation_summary(db, workspace_id)


@router.get("/remediation/actions/{action_id}", response_model=RemediationActionResponse)
def get_remediation_action(
    workspace_id: uuid.UUID,
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_remediation_permission("governance.remediation.view"))
) -> RemediationActionResponse:
    """Get details of a specific remediation action."""
    action = GovernanceRemediationService.get_remediation_action(db, workspace_id, action_id)
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remediation action not found.")
    return map_action_to_response(action)


@router.post("/remediation/actions/{action_id}/preview", response_model=RemediationActionResponse)
def preview_remediation_action(
    workspace_id: uuid.UUID,
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RemediationActionResponse:
    """Generate impact preview and transition action to PENDING_CONFIRMATION."""
    # Ensure user has general preview permission
    if not GovernancePermissionService.has_permission(db, current_user.id, "governance.remediation.preview", workspace_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor does not have preview permissions.")
    try:
        action = GovernanceRemediationService.preview_remediation_action(
            db=db,
            workspace_id=workspace_id,
            action_id=action_id,
            actor_id=current_user.id
        )
        return map_action_to_response(action)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/remediation/actions/{action_id}/confirm", response_model=RemediationActionResponse)
def confirm_remediation_action(
    workspace_id: uuid.UUID,
    action_id: uuid.UUID,
    request: RemediationActionConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RemediationActionResponse:
    """Confirm a remediation action by typing CONFIRM."""
    if not GovernancePermissionService.has_permission(db, current_user.id, "governance.remediation.confirm", workspace_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor does not have confirmation permissions.")
    try:
        action = GovernanceRemediationService.confirm_remediation_action(
            db=db,
            workspace_id=workspace_id,
            action_id=action_id,
            confirm_text=request.confirm_text,
            actor_id=current_user.id
        )
        return map_action_to_response(action)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/remediation/actions/{action_id}/execute", response_model=RemediationActionResponse)
def execute_remediation_action(
    workspace_id: uuid.UUID,
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RemediationActionResponse:
    """Execute a confirmed remediation action."""
    if not GovernancePermissionService.has_permission(db, current_user.id, "governance.remediation.execute", workspace_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor does not have execution permissions.")
    try:
        action = GovernanceRemediationService.execute_remediation_action(
            db=db,
            workspace_id=workspace_id,
            action_id=action_id,
            actor_id=current_user.id
        )
        
        from app.services.governance_notification_service import GovernanceNotificationService
        if action.status == "FAILED":
            GovernanceNotificationService.notify_remediation_failed(
                db=db,
                workspace_id=workspace_id,
                action_id=action.id,
                target_user_id=action.target_user_id
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=action.failure_reason)
            
        GovernanceNotificationService.notify_remediation_executed(
            db=db,
            workspace_id=workspace_id,
            action_id=action.id,
            target_user_id=action.target_user_id
        )
        
        return map_action_to_response(action)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/remediation/actions/{action_id}/cancel", response_model=RemediationActionResponse)
def cancel_remediation_action(
    workspace_id: uuid.UUID,
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RemediationActionResponse:
    """Cancel a remediation action in DRAFT, PENDING_CONFIRMATION, or CONFIRMED state."""
    if not GovernancePermissionService.has_permission(db, current_user.id, "governance.remediation.cancel", workspace_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor does not have cancel permissions.")
    try:
        action = GovernanceRemediationService.cancel_remediation_action(
            db=db,
            workspace_id=workspace_id,
            action_id=action_id,
            actor_id=current_user.id
        )
        return map_action_to_response(action)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/remediation/bulk/preview", response_model=List[BulkItemPreviewResponse])
def preview_bulk_remediation(
    workspace_id: uuid.UUID,
    request: BulkRemediationPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[BulkItemPreviewResponse]:
    """Identify potential bulk items and generate previews."""
    if not GovernancePermissionService.has_permission(db, current_user.id, "governance.remediation.preview", workspace_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor does not have preview permissions.")
    try:
        previews = GovernanceRemediationService.preview_bulk_remediation(
            db=db,
            workspace_id=workspace_id,
            bulk_type=request.bulk_type,
            actor_id=current_user.id,
            reason=request.reason
        )
        return [
            BulkItemPreviewResponse(
                item_id=p["item_id"],
                action_type=p["action_type"],
                target_id=p["target_id"],
                target_user_id=p.get("target_user_id"),
                details=p["details"]
            )
            for p in previews
        ]
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/remediation/bulk/execute", response_model=List[BulkItemResultResponse])
def execute_bulk_remediation(
    workspace_id: uuid.UUID,
    request: BulkRemediationExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[BulkItemResultResponse]:
    """Execute multiple remediation actions with isolated per-item results."""
    if not GovernancePermissionService.has_permission(db, current_user.id, "governance.remediation.bulk_execute", workspace_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor does not have bulk execute permissions.")
    
    items_dict = [
        {
            "item_id": item.item_id,
            "action_type": item.action_type,
            "target_id": item.target_id
        }
        for item in request.items
    ]
    
    results = GovernanceRemediationService.execute_bulk_remediation(
        db=db,
        workspace_id=workspace_id,
        items=items_dict,
        actor_id=current_user.id,
        reason=request.reason
    )
    
    return [
        BulkItemResultResponse(
            item_id=r["item_id"],
            action_type=r["action_type"],
            target_id=r["target_id"],
            status=r["status"],
            success=r["success"],
            failure_reason=r.get("failure_reason"),
            execution_result=r.get("execution_result")
        )
        for r in results
    ]
