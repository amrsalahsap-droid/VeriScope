"""
Governance Evidence Pack Service

Compiles and exports governance evidence packs for auditors and executives.
Automatically redacts credentials, tokens, passwords, and sensitive data recursively.
"""

import uuid
import re
import json
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.workspace_ci_cd_policy_default import WorkspaceCICDPolicyDefault
from app.models.ci_cd_policy_exception import CICDPolicyException
from app.models.governance_role_assignment import GovernanceRoleAssignment
from app.models.governance_notification import GovernanceNotification
from app.models.workspace_governance_audit_event import WorkspaceGovernanceAuditEvent
from app.models.ci_cd_governance_review_snapshot import CICDGovernanceReviewSnapshot
from app.services.workspace_governance_audit_service import WorkspaceGovernanceAuditService


class GovernanceEvidencePackService:
    """Service for exporting governance evidence packs with redaction."""

    # Patterns to redact
    REDACTION_PATTERNS = [
        # Webhook secrets
        r'webhook[_-]?secret["\']?\s*[:=]\s*["\']?[^"\']{20,}["\']?',
        r'secret["\']?\s*[:=]\s*["\']?[^"\']{20,}["\']?',
        # API tokens
        r'token["\']?\s*[:=]\s*["\']?[^"\']{20,}["\']?',
        r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\']{20,}["\']?',
        r'bearer["\']?\s*[:=]\s*["\']?[^"\']{20,}["\']?',
        # Passwords
        r'password["\']?\s*[:=]\s*["\']?[^"\']{8,}["\']?',
        r'passwd["\']?\s*[:=]\s*["\']?[^"\']{8,}["\']?',
        # Connection strings
        r'(postgresql|mysql|mongodb)://[^@]+@[^/]+',
        r'driver=["\']?[^"\']+["\']?;server=["\']?[^"\']+["\']?;database=["\']?[^"\']+["\']?;uid=["\']?[^"\']+["\']?;pwd=["\']?[^"\']+["\']?',
        # Authorization headers
        r'authorization["\']?\s*[:=]\s*["\']?(bearer|basic)\s+[^\s"]+',
        # Private keys (simplified pattern)
        r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----.*?-----END\s+(RSA\s+)?PRIVATE\s+KEY-----',
    ]

    @staticmethod
    def redact_sensitive_data(data: Any) -> Any:
        """
        Recursively redact sensitive data from the input.
        Handles nested dictionaries, lists, and strings.
        """
        if isinstance(data, dict):
            return {key: GovernanceEvidencePackService.redact_sensitive_data(value) 
                    for key, value in data.items()}
        elif isinstance(data, list):
            return [GovernanceEvidencePackService.redact_sensitive_data(item) 
                    for item in data]
        elif isinstance(data, str):
            return GovernanceEvidencePackService._redact_string(data)
        else:
            return data

    @staticmethod
    def _redact_string(text: str) -> str:
        """Apply redaction patterns to a string."""
        redacted = text
        for pattern in GovernanceEvidencePackService.REDACTION_PATTERNS:
            redacted = re.sub(pattern, '[REDACTED]', redacted, flags=re.IGNORECASE | re.DOTALL)
        return redacted

    @staticmethod
    def export_evidence_pack(
        db: Session,
        workspace_id: uuid.UUID,
        pack_type: str,
        requester_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Compile evidence pack for the workspace.
        Pack types: 'EXECUTIVE', 'AUDITOR', 'FULL'
        Automatically redacts sensitive data.
        """
        pack = {
            "workspace_id": str(workspace_id),
            "pack_type": pack_type,
            "exported_at": datetime.utcnow().isoformat(),
            "exported_by": str(requester_id),
            "sections": {}
        }

        # Section 1: Policy Presets and Defaults
        pack["sections"]["policy_defaults"] = GovernanceEvidencePackService._get_policy_defaults(
            db, workspace_id, pack_type
        )

        # Section 2: Policy Exceptions
        pack["sections"]["policy_exceptions"] = GovernanceEvidencePackService._get_policy_exceptions(
            db, workspace_id, pack_type
        )

        # Section 3: Role Assignments
        pack["sections"]["role_assignments"] = GovernanceEvidencePackService._get_role_assignments(
            db, workspace_id, pack_type
        )

        # Section 4: Notifications (only for AUDITOR and FULL)
        if pack_type in ["AUDITOR", "FULL"]:
            pack["sections"]["notifications"] = GovernanceEvidencePackService._get_notifications(
                db, workspace_id, pack_type
            )

        # Section 5: Audit Events (only for FULL)
        if pack_type == "FULL":
            pack["sections"]["audit_events"] = GovernanceEvidencePackService._get_audit_events(
                db, workspace_id, pack_type
            )

        # Section 6: Governance Review Snapshots
        pack["sections"]["governance_reviews"] = GovernanceEvidencePackService._get_governance_reviews(
            db, workspace_id, pack_type
        )

        # Apply recursive redaction
        pack = GovernanceEvidencePackService.redact_sensitive_data(pack)

        # Log audit event
        WorkspaceGovernanceAuditService.log_evidence_pack_exported(
            db=db,
            workspace_id=workspace_id,
            actor_id=requester_id,
            pack_type=pack_type
        )

        return pack

    @staticmethod
    def _get_policy_defaults(
        db: Session,
        workspace_id: uuid.UUID,
        pack_type: str
    ) -> List[Dict[str, Any]]:
        """Get workspace policy defaults."""
        defaults = db.query(WorkspaceCICDPolicyDefault).filter(
            WorkspaceCICDPolicyDefault.workspace_id == workspace_id
        ).all()

        return [
            {
                "id": str(d.id),
                "default_preset": d.default_preset,
                "default_policy_json": d.default_policy_json,
                "inherit_from_system_default": d.inherit_from_system_default,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in defaults
        ]

    @staticmethod
    def _get_policy_exceptions(
        db: Session,
        workspace_id: uuid.UUID,
        pack_type: str
    ) -> List[Dict[str, Any]]:
        """Get policy exceptions."""
        exceptions = db.query(CICDPolicyException).filter(
            CICDPolicyException.workspace_id == workspace_id
        ).all()

        return [
            {
                "id": str(e.id),
                "repository_id": str(e.repository_id) if e.repository_id else None,
                "requested_by": str(e.requested_by) if e.requested_by else None,
                "approved_by": str(e.approved_by) if e.approved_by else None,
                "status": e.status,
                "exception_fields": e.exception_fields,
                "reason": e.reason,
                "decision_reason": e.decision_reason,
                "expires_at": e.expires_at.isoformat() if e.expires_at else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in exceptions
        ]

    @staticmethod
    def _get_role_assignments(
        db: Session,
        workspace_id: uuid.UUID,
        pack_type: str
    ) -> List[Dict[str, Any]]:
        """Get role assignments."""
        assignments = db.query(GovernanceRoleAssignment).filter(
            GovernanceRoleAssignment.workspace_id == workspace_id
        ).all()

        return [
            {
                "id": str(a.id),
                "user_id": str(a.user_id),
                "role": a.role.value if a.role else None,
                "scope_type": a.scope_type.value if a.scope_type else None,
                "repository_id": str(a.repository_id) if a.repository_id else None,
                "assigned_by": str(a.assigned_by) if a.assigned_by else None,
                "is_active": a.is_active,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assignments
        ]

    @staticmethod
    def _get_notifications(
        db: Session,
        workspace_id: uuid.UUID,
        pack_type: str
    ) -> List[Dict[str, Any]]:
        """Get governance notifications."""
        notifications = db.query(GovernanceNotification).filter(
            GovernanceNotification.workspace_id == workspace_id
        ).limit(1000).all()  # Limit to prevent large exports

        return [
            {
                "id": str(n.id),
                "recipient_user_id": str(n.recipient_user_id) if n.recipient_user_id else None,
                "notification_type": n.notification_type.value if n.notification_type else None,
                "severity": n.severity.value if n.severity else None,
                "status": n.status.value if n.status else None,
                "title": n.title,
                "message": n.message,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "read_at": n.read_at.isoformat() if n.read_at else None,
            }
            for n in notifications
        ]

    @staticmethod
    def _get_audit_events(
        db: Session,
        workspace_id: uuid.UUID,
        pack_type: str
    ) -> List[Dict[str, Any]]:
        """Get audit events."""
        events = db.query(WorkspaceGovernanceAuditEvent).filter(
            WorkspaceGovernanceAuditEvent.workspace_id == workspace_id
        ).limit(2000).all()  # Limit to prevent large exports

        return [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
                "target_user_id": str(e.target_user_id) if e.target_user_id else None,
                "repository_id": str(e.repository_id) if e.repository_id else None,
                "permission": e.permission,
                "role": e.role,
                "decision": e.decision,
                "reason": e.reason,
                "audit_metadata": e.audit_metadata,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in events
        ]

    @staticmethod
    def _get_governance_reviews(
        db: Session,
        workspace_id: uuid.UUID,
        pack_type: str
    ) -> List[Dict[str, Any]]:
        """Get governance review snapshots."""
        reviews = db.query(CICDGovernanceReviewSnapshot).filter(
            CICDGovernanceReviewSnapshot.workspace_id == workspace_id
        ).limit(100).all()

        return [
            {
                "id": str(r.id),
                "review_type": r.review_type,
                "triggered_by": str(r.triggered_by) if r.triggered_by else None,
                "summary_json": r.summary_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ]
