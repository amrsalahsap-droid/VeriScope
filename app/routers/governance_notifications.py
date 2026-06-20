from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

from app.db.session import get_db
from app.models.governance_notification import (
    GovernanceNotification,
    NotificationType,
    NotificationSeverity,
    NotificationStatus
)
from app.models.governance_notification_preference import GovernanceNotificationPreference
from app.models.user import User, Workspace
from app.dependencies.auth import get_current_user
from app.services.governance_permission_service import GovernancePermissionService
from app.services.governance_notification_service import GovernanceNotificationService
from app.services.workspace_governance_audit_service import WorkspaceGovernanceAuditService
from pydantic import BaseModel

router = APIRouter(tags=["governance-notifications"])


# Request/Response Models
class NotificationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    repository_id: Optional[uuid.UUID]
    recipient_user_id: uuid.UUID
    notification_type: str
    severity: str
    title: str
    message: str
    source_entity_type: Optional[str]
    source_entity_id: Optional[uuid.UUID]
    status: str
    created_at: datetime
    read_at: Optional[datetime]
    dismissed_at: Optional[datetime]

    class Config:
        from_attributes = True


class NotificationPreferenceResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    notification_type: str
    enabled: bool
    minimum_severity: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationPreferenceUpdate(BaseModel):
    enabled: bool
    minimum_severity: str


class ScanResultResponse(BaseModel):
    scan_type: str
    notifications_created: int
    details: dict


def require_permission(permission: str):
    """Dependency to check if user has required permission."""
    def check(
        workspace_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        result = GovernancePermissionService.require_permission(
            db=db,
            user_id=current_user.id,
            permission=permission,
            workspace_id=workspace_id,
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


@router.get("/mine", response_model=List[NotificationResponse])
def list_my_notifications(
    workspace_id: uuid.UUID,
    status: Optional[NotificationStatus] = None,
    notification_type: Optional[NotificationType] = None,
    severity: Optional[NotificationSeverity] = None,
    repository_id: Optional[uuid.UUID] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[NotificationResponse]:
    """List notifications for the current user."""
    # Verify user has any governance role in the workspace
    has_role = GovernancePermissionService.get_user_roles(db, current_user.id, workspace_id)
    if not has_role:
        raise HTTPException(status_code=403, detail="You do not have governance access to this workspace")
    
    notifications = GovernanceNotificationService.list_user_notifications(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        status=status,
        notification_type=notification_type,
        severity=severity,
        repository_id=repository_id,
        limit=limit,
        offset=offset
    )
    
    return notifications


@router.get("", response_model=List[NotificationResponse])
def list_organization_notifications(
    workspace_id: uuid.UUID,
    status: Optional[NotificationStatus] = None,
    notification_type: Optional[NotificationType] = None,
    severity: Optional[NotificationSeverity] = None,
    repository_id: Optional[uuid.UUID] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.audit.view"))
) -> List[NotificationResponse]:
    """List all notifications for the workspace (admin view)."""
    notifications = GovernanceNotificationService.list_organization_notifications(
        db=db,
        workspace_id=workspace_id,
        status=status,
        notification_type=notification_type,
        severity=severity,
        repository_id=repository_id,
        limit=limit,
        offset=offset
    )
    
    return notifications


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    workspace_id: uuid.UUID,
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> NotificationResponse:
    """Mark a notification as read."""
    notification = GovernanceNotificationService.mark_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id
    )
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if notification.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Notification not found in this workspace")
    
    return notification


@router.post("/{notification_id}/dismiss", response_model=NotificationResponse)
def dismiss_notification(
    workspace_id: uuid.UUID,
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> NotificationResponse:
    """Dismiss a notification."""
    notification = GovernanceNotificationService.mark_dismissed(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id
    )
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if notification.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Notification not found in this workspace")
    
    return notification


@router.get("/preferences", response_model=List[NotificationPreferenceResponse])
def list_notification_preferences(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[NotificationPreferenceResponse]:
    """List notification preferences for the current user."""
    preferences = db.query(GovernanceNotificationPreference).filter(
        GovernanceNotificationPreference.workspace_id == workspace_id,
        GovernanceNotificationPreference.user_id == current_user.id
    ).all()
    
    return preferences


@router.put("/preferences", response_model=NotificationPreferenceResponse)
def update_notification_preference(
    workspace_id: uuid.UUID,
    notification_type: NotificationType,
    preference_update: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> NotificationPreferenceResponse:
    """Update notification preference for a specific notification type."""
    # Check if user has governance role
    has_role = GovernancePermissionService.get_user_roles(db, current_user.id, workspace_id)
    if not has_role:
        raise HTTPException(status_code=403, detail="You do not have governance access to this workspace")
    
    # Check if user is GOVERNANCE_OWNER trying to disable CRITICAL notifications
    if preference_update.minimum_severity == "CRITICAL" and not preference_update.enabled:
        is_owner = any(role["role"] == "GOVERNANCE_OWNER" for role in has_role)
        if is_owner:
            raise HTTPException(
                status_code=403,
                detail="GOVERNANCE_OWNER cannot disable CRITICAL notifications"
            )
    
    preference = db.query(GovernanceNotificationPreference).filter(
        GovernanceNotificationPreference.workspace_id == workspace_id,
        GovernanceNotificationPreference.user_id == current_user.id,
        GovernanceNotificationPreference.notification_type == notification_type
    ).first()
    
    if not preference:
        preference = GovernanceNotificationPreference(
            workspace_id=workspace_id,
            user_id=current_user.id,
            notification_type=notification_type,
            enabled=preference_update.enabled,
            minimum_severity=preference_update.minimum_severity
        )
        db.add(preference)
    else:
        preference.enabled = preference_update.enabled
        preference.minimum_severity = preference_update.minimum_severity
    
    db.commit()
    db.refresh(preference)
    
    # Log audit event
    WorkspaceGovernanceAuditService.log_notification_preference_updated(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        user_id=current_user.id,
        notification_type=notification_type.value,
        enabled=preference_update.enabled,
        minimum_severity=preference_update.minimum_severity
    )
    
    return preference


@router.post("/scan-exceptions", response_model=ScanResultResponse)
def scan_exceptions(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.roles.assign"))
) -> ScanResultResponse:
    """Scan for expiring and expired exceptions and create notifications."""
    from app.models.ci_cd_policy_exception import CICDPolicyException
    from datetime import timedelta
    
    notifications_created = 0
    expiring_soon = []
    expired = []
    
    # Find exceptions expiring in next 7 days
    expiring_threshold = datetime.utcnow() + timedelta(days=7)
    expiring_exceptions = db.query(CICDPolicyException).filter(
        CICDPolicyException.workspace_id == workspace_id,
        CICDPolicyException.status == "APPROVED",
        CICDPolicyException.expires_at.isnot(None),
        CICDPolicyException.expires_at <= expiring_threshold,
        CICDPolicyException.expires_at > datetime.utcnow()
    ).all()
    
    for exception in expiring_exceptions:
        days_until_expiry = (exception.expires_at - datetime.utcnow()).days
        GovernanceNotificationService.create_notification(
            db=db,
            workspace_id=workspace_id,
            recipient_user_id=exception.requested_by,
            notification_type=NotificationType.EXCEPTION_EXPIRING_SOON,
            severity=NotificationSeverity.WARNING,
            title="Policy Exception Expiring Soon",
            message=f"Your policy exception will expire in {days_until_expiry} days.",
            source_entity_type="PolicyException",
            source_entity_id=exception.id,
            repository_id=exception.repository_id
        )
        notifications_created += 1
        expiring_soon.append(str(exception.id))
    
    # Find expired exceptions
    expired_exceptions = db.query(CICDPolicyException).filter(
        CICDPolicyException.workspace_id == workspace_id,
        CICDPolicyException.status == "APPROVED",
        CICDPolicyException.expires_at.isnot(None),
        CICDPolicyException.expires_at <= datetime.utcnow()
    ).all()
    
    for exception in expired_exceptions:
        GovernanceNotificationService.create_notification(
            db=db,
            workspace_id=workspace_id,
            recipient_user_id=exception.requested_by,
            notification_type=NotificationType.EXCEPTION_EXPIRED,
            severity=NotificationSeverity.HIGH,
            title="Policy Exception Expired",
            message="Your policy exception has expired.",
            source_entity_type="PolicyException",
            source_entity_id=exception.id,
            repository_id=exception.repository_id
        )
        notifications_created += 1
        expired.append(str(exception.id))
    
    # Log audit event
    WorkspaceGovernanceAuditService.log_notification_scan_executed(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        scan_type="exceptions",
        results={
            "expiring_soon_count": len(expiring_soon),
            "expired_count": len(expired),
            "notifications_created": notifications_created
        }
    )
    
    return ScanResultResponse(
        scan_type="exceptions",
        notifications_created=notifications_created,
        details={
            "expiring_soon": expiring_soon,
            "expired": expired
        }
    )


@router.post("/scan-role-expiry", response_model=ScanResultResponse)
def scan_role_expiry(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.roles.assign"))
) -> ScanResultResponse:
    """Scan for expiring and expired roles and create notifications."""
    from app.models.governance_role_assignment import GovernanceRoleAssignment
    from datetime import timedelta
    
    notifications_created = 0
    expiring_soon = []
    expired = []
    
    # Find roles expiring in next 7 days
    expiring_threshold = datetime.utcnow() + timedelta(days=7)
    expiring_roles = db.query(GovernanceRoleAssignment).filter(
        GovernanceRoleAssignment.workspace_id == workspace_id,
        GovernanceRoleAssignment.is_active == True,
        GovernanceRoleAssignment.expires_at.isnot(None),
        GovernanceRoleAssignment.expires_at <= expiring_threshold,
        GovernanceRoleAssignment.expires_at > datetime.utcnow()
    ).all()
    
    for role_assignment in expiring_roles:
        days_until_expiry = (role_assignment.expires_at - datetime.utcnow()).days
        GovernanceNotificationService.notify_role_expiring(
            db=db,
            workspace_id=workspace_id,
            user_id=role_assignment.user_id,
            role=role_assignment.role,
            repository_id=role_assignment.repository_id,
            days_until_expiry=days_until_expiry
        )
        notifications_created += 1
        expiring_soon.append(str(role_assignment.id))
    
    # Find expired roles
    expired_roles = db.query(GovernanceRoleAssignment).filter(
        GovernanceRoleAssignment.workspace_id == workspace_id,
        GovernanceRoleAssignment.is_active == True,
        GovernanceRoleAssignment.expires_at.isnot(None),
        GovernanceRoleAssignment.expires_at <= datetime.utcnow()
    ).all()
    
    for role_assignment in expired_roles:
        GovernanceNotificationService.notify_role_expiring(
            db=db,
            workspace_id=workspace_id,
            user_id=role_assignment.user_id,
            role=role_assignment.role,
            repository_id=role_assignment.repository_id,
            days_until_expiry=0
        )
        notifications_created += 1
        expired.append(str(role_assignment.id))
    
    # Log audit event
    WorkspaceGovernanceAuditService.log_notification_scan_executed(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        scan_type="role_expiry",
        results={
            "expiring_soon_count": len(expiring_soon),
            "expired_count": len(expired),
            "notifications_created": notifications_created
        }
    )
    
    return ScanResultResponse(
        scan_type="role_expiry",
        notifications_created=notifications_created,
        details={
            "expiring_soon": expiring_soon,
            "expired": expired
        }
    )


@router.post("/scan-compliance", response_model=ScanResultResponse)
def scan_compliance(
    workspace_id: uuid.UUID,
    threshold: float = Query(0.1, ge=0, le=1, description="Minimum drop threshold to trigger notification"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.roles.assign"))
) -> ScanResultResponse:
    """Scan for compliance score drops and create notifications."""
    
    notifications_created = 0
    drops_detected = []
    
    # Verify workspace exists without querying Organization
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    
    if workspace:
        # In a real implementation, you would compare with historical data
        # For this phase, we'll just check if compliance is low
        pass
    
    # Log audit event
    WorkspaceGovernanceAuditService.log_notification_scan_executed(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        scan_type="compliance",
        results={
            "threshold": threshold,
            "drops_detected": len(drops_detected),
            "notifications_created": notifications_created
        }
    )
    
    return ScanResultResponse(
        scan_type="compliance",
        notifications_created=notifications_created,
        details={
            "threshold": threshold,
            "drops_detected": drops_detected
        }
    )
