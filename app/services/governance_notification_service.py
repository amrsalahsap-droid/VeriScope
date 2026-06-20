from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import uuid

from app.models.governance_notification import (
    GovernanceNotification,
    NotificationType,
    NotificationSeverity,
    NotificationStatus
)
from app.models.governance_notification_preference import GovernanceNotificationPreference
from app.models.governance_role_assignment import GovernanceRole, ScopeType
from app.models.ci_cd_policy_exception import CICDPolicyException
from app.models.user import User
from app.services.governance_permission_service import GovernancePermissionService
from app.services.workspace_governance_audit_service import WorkspaceGovernanceAuditService


class GovernanceNotificationService:
    """Service for managing governance notifications."""

    @staticmethod
    def create_notification(
        db: Session,
        workspace_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        notification_type: NotificationType,
        severity: NotificationSeverity,
        title: str,
        message: str,
        source_entity_type: Optional[str] = None,
        source_entity_id: Optional[uuid.UUID] = None,
        repository_id: Optional[uuid.UUID] = None,
        delivery_metadata: Optional[Dict[str, Any]] = None
    ) -> GovernanceNotification:
        """Create a single governance notification."""
        # Check user preferences
        preference = db.query(GovernanceNotificationPreference).filter(
            GovernanceNotificationPreference.workspace_id == workspace_id,
            GovernanceNotificationPreference.user_id == recipient_user_id,
            GovernanceNotificationPreference.notification_type == notification_type
        ).first()
        
        # Check if notification should be sent based on preferences
        if preference:
            if not preference.enabled:
                return None
            if severity.value < preference.minimum_severity.value:
                return None
        
        # Deduplicate: check for existing unread notification for same source
        if source_entity_type and source_entity_id:
            existing = db.query(GovernanceNotification).filter(
                GovernanceNotification.workspace_id == workspace_id,
                GovernanceNotification.recipient_user_id == recipient_user_id,
                GovernanceNotification.notification_type == notification_type,
                GovernanceNotification.source_entity_type == source_entity_type,
                GovernanceNotification.source_entity_id == source_entity_id,
                GovernanceNotification.status == NotificationStatus.UNREAD,
                GovernanceNotification.created_at > datetime.utcnow() - timedelta(hours=24)
            ).first()
            
            if existing:
                return existing  # Return existing notification instead of creating duplicate
        
        # Create notification
        notification = GovernanceNotification(
            workspace_id=workspace_id,
            repository_id=repository_id,
            recipient_user_id=recipient_user_id,
            notification_type=notification_type,
            severity=severity,
            title=title,
            message=message,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            delivery_metadata=delivery_metadata
        )
        
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
        # Log audit event
        WorkspaceGovernanceAuditService.log_notification_created(
            db=db,
            workspace_id=workspace_id,
            actor_id=recipient_user_id,
            recipient_user_id=recipient_user_id,
            notification_type=notification_type.value,
            severity=severity.value,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            repository_id=repository_id
        )
        
        return notification

    @staticmethod
    def create_bulk_notifications(
        db: Session,
        workspace_id: uuid.UUID,
        recipient_user_ids: List[uuid.UUID],
        notification_type: NotificationType,
        severity: NotificationSeverity,
        title: str,
        message: str,
        source_entity_type: Optional[str] = None,
        source_entity_id: Optional[uuid.UUID] = None,
        repository_id: Optional[uuid.UUID] = None,
        delivery_metadata: Optional[Dict[str, Any]] = None
    ) -> List[GovernanceNotification]:
        """Create multiple notifications for different recipients."""
        notifications = []
        for user_id in recipient_user_ids:
            notification = GovernanceNotificationService.create_notification(
                db=db,
                workspace_id=workspace_id,
                recipient_user_id=user_id,
                notification_type=notification_type,
                severity=severity,
                title=title,
                message=message,
                source_entity_type=source_entity_type,
                source_entity_id=source_entity_id,
                repository_id=repository_id,
                delivery_metadata=delivery_metadata
            )
            if notification:
                notifications.append(notification)
        return notifications

    @staticmethod
    def mark_read(
        db: Session,
        notification_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[GovernanceNotification]:
        """Mark a notification as read."""
        notification = db.query(GovernanceNotification).filter(
            GovernanceNotification.id == notification_id,
            GovernanceNotification.recipient_user_id == user_id
        ).first()
        
        if not notification:
            return None
        
        notification.status = NotificationStatus.READ
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
        
        # Log audit event
        WorkspaceGovernanceAuditService.log_notification_read(
            db=db,
            workspace_id=notification.workspace_id,
            actor_id=user_id,
            notification_id=notification_id
        )
        
        return notification

    @staticmethod
    def mark_dismissed(
        db: Session,
        notification_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[GovernanceNotification]:
        """Mark a notification as dismissed."""
        notification = db.query(GovernanceNotification).filter(
            GovernanceNotification.id == notification_id,
            GovernanceNotification.recipient_user_id == user_id
        ).first()
        
        if not notification:
            return None
        
        notification.status = NotificationStatus.DISMISSED
        notification.dismissed_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
        
        # Log audit event
        WorkspaceGovernanceAuditService.log_notification_dismissed(
            db=db,
            workspace_id=notification.workspace_id,
            actor_id=user_id,
            notification_id=notification_id
        )
        
        return notification

    @staticmethod
    def list_user_notifications(
        db: Session,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID,
        status: Optional[NotificationStatus] = None,
        notification_type: Optional[NotificationType] = None,
        severity: Optional[NotificationSeverity] = None,
        repository_id: Optional[uuid.UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[GovernanceNotification]:
        """List notifications for a specific user."""
        query = db.query(GovernanceNotification).filter(
            GovernanceNotification.recipient_user_id == user_id,
            GovernanceNotification.workspace_id == workspace_id
        )
        
        if status:
            query = query.filter(GovernanceNotification.status == status)
        if notification_type:
            query = query.filter(GovernanceNotification.notification_type == notification_type)
        if severity:
            query = query.filter(GovernanceNotification.severity == severity)
        if repository_id:
            query = query.filter(GovernanceNotification.repository_id == repository_id)
        
        return query.order_by(GovernanceNotification.created_at.desc()).limit(limit).offset(offset).all()

    @staticmethod
    def list_organization_notifications(
        db: Session,
        workspace_id: uuid.UUID,
        status: Optional[NotificationStatus] = None,
        notification_type: Optional[NotificationType] = None,
        severity: Optional[NotificationSeverity] = None,
        repository_id: Optional[uuid.UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[GovernanceNotification]:
        """List all notifications for an organization (admin view)."""
        query = db.query(GovernanceNotification).filter(
            GovernanceNotification.workspace_id == workspace_id
        )
        
        if status:
            query = query.filter(GovernanceNotification.status == status)
        if notification_type:
            query = query.filter(GovernanceNotification.notification_type == notification_type)
        if severity:
            query = query.filter(GovernanceNotification.severity == severity)
        if repository_id:
            query = query.filter(GovernanceNotification.repository_id == repository_id)
        
        return query.order_by(GovernanceNotification.created_at.desc()).limit(limit).offset(offset).all()

    @staticmethod
    def notify_exception_requested(
        db: Session,
        workspace_id: uuid.UUID,
        exception_id: uuid.UUID,
        repository_id: uuid.UUID,
        requester_user_id: uuid.UUID
    ) -> List[GovernanceNotification]:
        """Notify approvers when an exception is requested."""
        # Get EXCEPTION_APPROVER and GOVERNANCE_OWNER users
        approvers = GovernanceNotificationService._get_users_with_roles(
            db, workspace_id, repository_id,
            [GovernanceRole.EXCEPTION_APPROVER, GovernanceRole.GOVERNANCE_OWNER]
        )
        
        recipient_ids = [u.id for u in approvers if u.id != requester_user_id]
        
        return GovernanceNotificationService.create_bulk_notifications(
            db=db,
            workspace_id=workspace_id,
            recipient_user_ids=recipient_ids,
            notification_type=NotificationType.EXCEPTION_REQUESTED,
            severity=NotificationSeverity.INFO,
            title="Policy Exception Requested",
            message="A new policy exception has been requested and requires your review.",
            source_entity_type="PolicyException",
            source_entity_id=exception_id,
            repository_id=repository_id
        )

    @staticmethod
    def notify_exception_status_changed(
        db: Session,
        workspace_id: uuid.UUID,
        exception_id: uuid.UUID,
        repository_id: uuid.UUID,
        requester_user_id: uuid.UUID,
        status: str
    ) -> List[GovernanceNotification]:
        """Notify requester when exception status changes."""
        severity = NotificationSeverity.INFO
        if status == "APPROVED":
            title = "Policy Exception Approved"
            message = "Your policy exception request has been approved."
        elif status == "REJECTED":
            title = "Policy Exception Rejected"
            message = "Your policy exception request has been rejected."
            severity = NotificationSeverity.WARNING
        elif status == "REVOKED":
            title = "Policy Exception Revoked"
            message = "Your policy exception has been revoked."
            severity = NotificationSeverity.HIGH
        else:
            return []
        
        # Notify requester and GOVERNANCE_OWNER
        recipients = [requester_user_id]
        owners = GovernanceNotificationService._get_users_with_roles(
            db, workspace_id, repository_id, [GovernanceRole.GOVERNANCE_OWNER]
        )
        recipients.extend([u.id for u in owners if u.id != requester_user_id])
        
        return GovernanceNotificationService.create_bulk_notifications(
            db=db,
            workspace_id=workspace_id,
            recipient_user_ids=recipients,
            notification_type=NotificationType.EXCEPTION_APPROVED if status == "APPROVED" else
                            NotificationType.EXCEPTION_REJECTED if status == "REJECTED" else
                            NotificationType.EXCEPTION_REVOKED,
            severity=severity,
            title=title,
            message=message,
            source_entity_type="PolicyException",
            source_entity_id=exception_id,
            repository_id=repository_id
        )

    @staticmethod
    def notify_drift_detected(
        db: Session,
        workspace_id: uuid.UUID,
        repository_id: uuid.UUID,
        risk_level: str
    ) -> List[GovernanceNotification]:
        """Notify relevant users when policy drift is detected."""
        if risk_level == "CRITICAL":
            notification_type = NotificationType.CRITICAL_RISK_DRIFT_DETECTED
            severity = NotificationSeverity.CRITICAL
            title = "Critical Policy Drift Detected"
            message = "Critical policy drift has been detected. Immediate attention required."
        elif risk_level == "HIGH":
            notification_type = NotificationType.HIGH_RISK_DRIFT_DETECTED
            severity = NotificationSeverity.HIGH
            title = "High-Risk Policy Drift Detected"
            message = "High-risk policy drift has been detected. Review recommended."
        else:
            notification_type = NotificationType.POLICY_DRIFT_DETECTED
            severity = NotificationSeverity.WARNING
            title = "Policy Drift Detected"
            message = "Policy drift has been detected. Review recommended."
        
        # Notify GOVERNANCE_OWNER, POLICY_ADMIN, and REPOSITORY_POLICY_MANAGER
        recipients = GovernanceNotificationService._get_users_with_roles(
            db, workspace_id, repository_id,
            [GovernanceRole.GOVERNANCE_OWNER, GovernanceRole.POLICY_ADMIN, GovernanceRole.REPOSITORY_POLICY_MANAGER]
        )
        
        return GovernanceNotificationService.create_bulk_notifications(
            db=db,
            workspace_id=workspace_id,
            recipient_user_ids=[u.id for u in recipients],
            notification_type=notification_type,
            severity=severity,
            title=title,
            message=message,
            source_entity_type="Repository",
            source_entity_id=repository_id,
            repository_id=repository_id
        )

    @staticmethod
    def notify_role_expiring(
        db: Session,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: GovernanceRole,
        repository_id: Optional[uuid.UUID],
        days_until_expiry: int
    ) -> List[GovernanceNotification]:
        """Notify user and owner when role is expiring."""
        if days_until_expiry <= 0:
            notification_type = NotificationType.ROLE_EXPIRED
            severity = NotificationSeverity.HIGH
            title = "Governance Role Expired"
            message = f"Your {role.value} role has expired."
        else:
            notification_type = NotificationType.ROLE_EXPIRING_SOON
            severity = NotificationSeverity.WARNING
            title = "Governance Role Expiring Soon"
            message = f"Your {role.value} role will expire in {days_until_expiry} days."
        
        # Notify user and GOVERNANCE_OWNER
        recipients = [user_id]
        owners = GovernanceNotificationService._get_users_with_roles(
            db, workspace_id, repository_id, [GovernanceRole.GOVERNANCE_OWNER]
        )
        recipients.extend([u.id for u in owners if u.id != user_id])
        
        return GovernanceNotificationService.create_bulk_notifications(
            db=db,
            workspace_id=workspace_id,
            recipient_user_ids=recipients,
            notification_type=notification_type,
            severity=severity,
            title=title,
            message=message,
            source_entity_type="GovernanceRoleAssignment",
            repository_id=repository_id
        )

    @staticmethod
    def notify_compliance_drop(
        db: Session,
        workspace_id: uuid.UUID,
        repository_id: Optional[uuid.UUID],
        previous_score: float,
        current_score: float
    ) -> List[GovernanceNotification]:
        """Notify when compliance score drops significantly."""
        title = "Compliance Score Dropped"
        message = f"Compliance score dropped from {previous_score} to {current_score}."
        
        # Notify GOVERNANCE_OWNER, POLICY_ADMIN, and EXECUTIVE_VIEWER
        recipients = GovernanceNotificationService._get_users_with_roles(
            db, workspace_id, repository_id,
            [GovernanceRole.GOVERNANCE_OWNER, GovernanceRole.POLICY_ADMIN, GovernanceRole.EXECUTIVE_VIEWER]
        )
        
        return GovernanceNotificationService.create_bulk_notifications(
            db=db,
            workspace_id=workspace_id,
            recipient_user_ids=[u.id for u in recipients],
            notification_type=NotificationType.COMPLIANCE_SCORE_DROPPED,
            severity=NotificationSeverity.WARNING,
            title=title,
            message=message,
            source_entity_type="Organization" if not repository_id else "Repository",
            source_entity_id=repository_id,
            repository_id=repository_id
        )

    @staticmethod
    def notify_bulk_operation_result(
        db: Session,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        operation_type: str,
        success_count: int,
        failure_count: int
    ) -> List[GovernanceNotification]:
        """Notify actor and owner about bulk operation results."""
        if failure_count > 0:
            notification_type = NotificationType.BULK_OPERATION_PARTIAL_FAILURE
            severity = NotificationSeverity.HIGH
            title = "Bulk Operation Partial Failure"
            message = f"Bulk {operation_type} completed with {success_count} successes and {failure_count} failures."
        else:
            notification_type = NotificationType.BULK_OPERATION_COMPLETED
            severity = NotificationSeverity.INFO
            title = "Bulk Operation Completed"
            message = f"Bulk {operation_type} completed successfully with {success_count} operations."
        
        # Notify actor and GOVERNANCE_OWNER
        recipients = [actor_id]
        owners = GovernanceNotificationService._get_users_with_roles(
            db, workspace_id, None, [GovernanceRole.GOVERNANCE_OWNER]
        )
        recipients.extend([u.id for u in owners if u.id != actor_id])
        
        return GovernanceNotificationService.create_bulk_notifications(
            db=db,
            workspace_id=workspace_id,
            recipient_user_ids=recipients,
            notification_type=notification_type,
            severity=severity,
            title=title,
            message=message
        )

    @staticmethod
    def notify_governance_review_created(
        db: Session,
        workspace_id: uuid.UUID,
        review_id: uuid.UUID
    ) -> List[GovernanceNotification]:
        """Notify when governance review is created."""
        # Notify GOVERNANCE_OWNER, EXECUTIVE_VIEWER, and AUDITOR
        recipients = GovernanceNotificationService._get_users_with_roles(
            db, workspace_id, None,
            [GovernanceRole.GOVERNANCE_OWNER, GovernanceRole.EXECUTIVE_VIEWER, GovernanceRole.AUDITOR]
        )
        
        return GovernanceNotificationService.create_bulk_notifications(
            db=db,
            workspace_id=workspace_id,
            recipient_user_ids=[u.id for u in recipients],
            notification_type=NotificationType.GOVERNANCE_REVIEW_CREATED,
            severity=NotificationSeverity.INFO,
            title="Governance Review Created",
            message="A new governance review snapshot has been created.",
            source_entity_type="GovernanceReview",
            source_entity_id=review_id
        )

    @staticmethod
    def _get_users_with_roles(
        db: Session,
        workspace_id: uuid.UUID,
        repository_id: Optional[uuid.UUID],
        roles: List[GovernanceRole]
    ) -> List[User]:
        """Get users with specific roles in the workspace/repository."""
        from app.models.governance_role_assignment import GovernanceRoleAssignment
        
        now = datetime.utcnow()
        
        # Use explicit join to avoid foreign key ambiguity
        query = db.query(User).join(
            GovernanceRoleAssignment,
            User.id == GovernanceRoleAssignment.user_id
        ).filter(
            GovernanceRoleAssignment.workspace_id == workspace_id,
            GovernanceRoleAssignment.role.in_(roles),
            GovernanceRoleAssignment.is_active == True,
            (GovernanceRoleAssignment.expires_at.is_(None)) | (GovernanceRoleAssignment.expires_at > now)
        )
        
        # Filter by repository / scope explicitly
        if repository_id:
            query = query.filter(
                ((GovernanceRoleAssignment.scope_type == ScopeType.WORKSPACE) & (GovernanceRoleAssignment.repository_id.is_(None))) |
                ((GovernanceRoleAssignment.scope_type == ScopeType.REPOSITORY) & (GovernanceRoleAssignment.repository_id == repository_id))
            )
        else:
            query = query.filter(
                (GovernanceRoleAssignment.scope_type == ScopeType.WORKSPACE) &
                (GovernanceRoleAssignment.repository_id.is_(None))
            )
        
        return query.distinct().all()
