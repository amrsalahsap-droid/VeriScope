"""
Workspace Governance Audit Service

Logs workspace-level governance audit events for bulk operations and other governance actions.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.workspace_governance_audit_event import WorkspaceGovernanceAuditEvent


class WorkspaceGovernanceAuditService:
    """Service for logging workspace-level governance audit events."""
    
    @staticmethod
    def log_bulk_operation(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        event_type: str,
        operation_id: UUID,
        requested_count: int,
        succeeded_count: int,
        failed_count: int,
        skipped_count: int,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a bulk operation audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            event_type: Event type (CI_CD_BULK_POLICY_PREVIEWED, CI_CD_BULK_POLICY_APPLIED, etc.)
            operation_id: Operation ID
            requested_count: Number of repositories requested
            succeeded_count: Number of successful operations
            failed_count: Number of failed operations
            skipped_count: Number of skipped operations
            reason: Optional reason for the operation
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type=event_type,
            operation_id=operation_id,
            requested_count=requested_count,
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            reason=reason,
            audit_metadata=metadata
        )
        
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_governance_review(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        review_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a governance review snapshot audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            review_id: Review snapshot ID
            reason: Optional reason for the review
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="CI_CD_GOVERNANCE_REVIEW_CREATED",
            operation_id=review_id,
            reason=reason,
            audit_metadata=metadata
        )
        
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_report_export(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        format: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a governance report export audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            format: Export format (JSON, CSV, Markdown)
            reason: Optional reason for the export
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="CI_CD_GOVERNANCE_REPORT_EXPORTED",
            reason=reason,
            audit_metadata={"format": format, **(metadata or {})}
        )
        
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_permission_check(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        permission: str,
        decision: str,
        reason: Optional[str] = None,
        repository_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a permission check audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            target_user_id: Target user ID
            permission: Permission being checked
            decision: Decision (ALLOWED or DENIED)
            reason: Optional reason for the decision
            repository_id: Optional repository ID
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=target_user_id,
            repository_id=repository_id,
            permission=permission,
            decision=decision,
            event_type="GOVERNANCE_PERMISSION_CHECKED",
            reason=reason,
            audit_metadata=metadata or {}
        )
        
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_role_assigned(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        role: str,
        scope_type: str,
        repository_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a role assignment audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            target_user_id: Target user ID
            role: Role being assigned
            scope_type: Scope type (ORGANIZATION or REPOSITORY)
            repository_id: Optional repository ID
            reason: Optional reason for the assignment
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=target_user_id,
            repository_id=repository_id,
            role=role,
            event_type="GOVERNANCE_ROLE_ASSIGNED",
            reason=reason,
            audit_metadata={"scope_type": scope_type, **(metadata or {})}
        )
        
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_role_revoked(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        role: str,
        scope_type: str,
        repository_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a role revocation audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            target_user_id: Target user ID
            role: Role being revoked
            scope_type: Scope type (ORGANIZATION or REPOSITORY)
            repository_id: Optional repository ID
            reason: Optional reason for the revocation
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=target_user_id,
            repository_id=repository_id,
            role=role,
            event_type="GOVERNANCE_ROLE_REVOKED",
            reason=reason,
            audit_metadata={"scope_type": scope_type, **(metadata or {})}
        )
        
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_permission_denied(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        permission: str,
        reason: Optional[str] = None,
        repository_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a permission denied audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            target_user_id: Target user ID
            permission: Permission that was denied
            reason: Optional reason for the denial
            repository_id: Optional repository ID
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=target_user_id,
            repository_id=repository_id,
            permission=permission,
            decision="DENIED",
            event_type="GOVERNANCE_PERMISSION_DENIED",
            reason=reason,
            audit_metadata=metadata or {}
        )
        
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_self_approval_blocked(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        exception_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a self-approval blocked audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            exception_id: Exception ID
            reason: Optional reason for the block
            metadata: Optional additional metadata
        """
        from app.models.ci_cd_policy_exception import CICDPolicyException
        exception = db.query(CICDPolicyException).filter(
            CICDPolicyException.id == exception_id
        ).first()
        target_user_id = exception.requested_by if exception else None
        repository_id = exception.repository_id if exception else None

        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=target_user_id,
            repository_id=repository_id,
            event_type="GOVERNANCE_SELF_APPROVAL_BLOCKED",
            operation_id=exception_id,
            reason=reason,
            decision="BLOCKED",
            audit_metadata=metadata
        )
        
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_delegated_admin_granted(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        repository_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a delegated admin granted audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            target_user_id: Target user ID
            repository_id: Repository ID
            reason: Optional reason for the delegation
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=target_user_id,
            repository_id=repository_id,
            event_type="GOVERNANCE_DELEGATED_ADMIN_GRANTED",
            reason=reason,
            audit_metadata=metadata or {}
        )
        
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_delegated_admin_revoked(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        repository_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a delegated admin revoked audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            target_user_id: Target user ID
            repository_id: Repository ID
            reason: Optional reason for the revocation
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=target_user_id,
            repository_id=repository_id,
            event_type="GOVERNANCE_DELEGATED_ADMIN_REVOKED",
            reason=reason,
            audit_metadata=metadata or {}
        )
        
        db.add(event)
        db.commit()

    @staticmethod
    def log_notification_created(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        recipient_user_id: UUID,
        notification_type: str,
        severity: str,
        source_entity_type: Optional[str] = None,
        source_entity_id: Optional[UUID] = None,
        repository_id: Optional[UUID] = None
    ) -> None:
        """
        Log a notification creation audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            recipient_user_id: Recipient user ID
            notification_type: Notification type
            severity: Notification severity
            source_entity_type: Optional source entity type
            source_entity_id: Optional source entity ID
            repository_id: Optional repository ID
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=recipient_user_id,
            repository_id=repository_id,
            event_type="GOVERNANCE_NOTIFICATION_CREATED",
            reason="Governance notification created",
            audit_metadata={
                "notification_type": notification_type,
                "severity": severity,
                "source_entity_type": source_entity_type,
                "source_entity_id": str(source_entity_id) if source_entity_id else None
            }
        )
        
        db.add(event)
        db.commit()

    @staticmethod
    def log_notification_read(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        notification_id: UUID
    ) -> None:
        """
        Log a notification read audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            notification_id: Notification ID
        """
        from app.models.governance_notification import GovernanceNotification
        notification = db.query(GovernanceNotification).filter(
            GovernanceNotification.id == notification_id
        ).first()
        target_user_id = notification.recipient_user_id if notification else None
        repository_id = notification.repository_id if notification else None

        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=target_user_id,
            repository_id=repository_id,
            event_type="GOVERNANCE_NOTIFICATION_READ",
            reason="Governance notification marked as read",
            audit_metadata={"notification_id": str(notification_id)}
        )
        
        db.add(event)
        db.commit()

    @staticmethod
    def log_notification_dismissed(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        notification_id: UUID
    ) -> None:
        """
        Log a notification dismissed audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            notification_id: Notification ID
        """
        from app.models.governance_notification import GovernanceNotification
        notification = db.query(GovernanceNotification).filter(
            GovernanceNotification.id == notification_id
        ).first()
        target_user_id = notification.recipient_user_id if notification else None
        repository_id = notification.repository_id if notification else None

        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=target_user_id,
            repository_id=repository_id,
            event_type="GOVERNANCE_NOTIFICATION_DISMISSED",
            reason="Governance notification dismissed",
            audit_metadata={"notification_id": str(notification_id)}
        )
        
        db.add(event)
        db.commit()

    @staticmethod
    def log_notification_scan_executed(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        scan_type: str,
        results: Dict[str, Any]
    ) -> None:
        """
        Log a notification scan execution audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            scan_type: Type of scan (exceptions, roles, compliance)
            results: Scan results
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_NOTIFICATION_SCAN_EXECUTED",
            reason=f"Governance notification scan executed: {scan_type}",
            audit_metadata={"scan_type": scan_type, "results": results}
        )
        
        db.add(event)
        db.commit()

    @staticmethod
    def log_notification_preference_updated(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        user_id: UUID,
        notification_type: str,
        enabled: bool,
        minimum_severity: str
    ) -> None:
        """
        Log a notification preference update audit event.
        
        Args:
            db: Database session
            workspace_id: Organization ID
            actor_id: Actor ID
            user_id: User ID
            notification_type: Notification type
            enabled: Whether notification is enabled
            minimum_severity: Minimum severity level
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_user_id=user_id,
            event_type="GOVERNANCE_NOTIFICATION_PREFERENCE_UPDATED",
            reason="Governance notification preference updated",
            audit_metadata={
                "notification_type": notification_type,
                "enabled": enabled,
                "minimum_severity": minimum_severity
            }
        )
        
        db.add(event)
        db.commit()

    @staticmethod
    def log_access_review_created(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        review_id: UUID,
        review_type: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an access review creation audit event.

        Args:
            db: Database session
            workspace_id: Workspace ID
            actor_id: Actor ID
            review_id: Access review ID
            review_type: Type of access review
            reason: Optional reason for the review
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_ACCESS_REVIEW_CREATED",
            operation_id=review_id,
            reason=reason,
            audit_metadata={"review_type": review_type, **(metadata or {})}
        )

        db.add(event)
        db.commit()

    @staticmethod
    def log_access_review_item_decided(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        review_id: UUID,
        item_id: UUID,
        decision: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an access review item decision audit event.

        Args:
            db: Database session
            workspace_id: Workspace ID
            actor_id: Actor ID
            review_id: Access review ID
            item_id: Review item ID
            decision: Decision made (APPROVED, REVOKE_RECOMMENDED, etc.)
            reason: Optional reason for the decision
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_ACCESS_REVIEW_ITEM_DECIDED",
            operation_id=review_id,
            decision=decision,
            reason=reason,
            audit_metadata={"item_id": str(item_id), **(metadata or {})}
        )

        db.add(event)
        db.commit()

    @staticmethod
    def log_access_review_completed(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        review_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an access review completion audit event.

        Args:
            db: Database session
            workspace_id: Workspace ID
            actor_id: Actor ID
            review_id: Access review ID
            reason: Optional reason for completion
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_ACCESS_REVIEW_COMPLETED",
            operation_id=review_id,
            reason=reason,
            audit_metadata=metadata or {}
        )

        db.add(event)
        db.commit()

    @staticmethod
    def log_access_review_cancelled(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        review_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an access review cancellation audit event.

        Args:
            db: Database session
            workspace_id: Workspace ID
            actor_id: Actor ID
            review_id: Access review ID
            reason: Optional reason for cancellation
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_ACCESS_REVIEW_CANCELLED",
            operation_id=review_id,
            reason=reason,
            audit_metadata=metadata or {}
        )

        db.add(event)
        db.commit()

    @staticmethod
    def log_security_posture_viewed(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a security posture view audit event.

        Args:
            db: Database session
            workspace_id: Workspace ID
            actor_id: Actor ID
            reason: Optional reason for viewing
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_SECURITY_POSTURE_VIEWED",
            reason=reason,
            audit_metadata=metadata or {}
        )

        db.add(event)
        db.commit()

    @staticmethod
    def log_security_signals_viewed(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a security signals view audit event.

        Args:
            db: Database session
            workspace_id: Workspace ID
            actor_id: Actor ID
            reason: Optional reason for viewing
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_SECURITY_SIGNALS_VIEWED",
            reason=reason,
            audit_metadata=metadata or {}
        )

        db.add(event)
        db.commit()

    @staticmethod
    def log_evidence_pack_exported(
        db: Session,
        workspace_id: UUID,
        actor_id: UUID,
        pack_type: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an evidence pack export audit event.

        Args:
            db: Database session
            workspace_id: Workspace ID
            actor_id: Actor ID
            pack_type: Type of evidence pack (EXECUTIVE, AUDITOR, FULL)
            reason: Optional reason for export
            metadata: Optional additional metadata
        """
        event = WorkspaceGovernanceAuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            event_type="GOVERNANCE_EVIDENCE_PACK_EXPORTED",
            reason=reason,
            audit_metadata={"pack_type": pack_type, **(metadata or {})}
        )

        db.add(event)
        db.commit()
