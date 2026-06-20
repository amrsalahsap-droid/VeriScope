"""
Governance Security Signal Service

Detects and reports security signals from audit logs and governance events.
Provides read-only abuse indicators for security posture monitoring.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.workspace_governance_audit_event import WorkspaceGovernanceAuditEvent
from app.models.ci_cd_policy_exception import CICDPolicyException
from app.models.governance_role_assignment import GovernanceRoleAssignment


class GovernanceSecuritySignalService:
    """Service for detecting governance security signals."""

    @staticmethod
    def detect_security_signals(db: Session, workspace_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        Scan audit logs and exceptions to populate read-only abuse indicators.
        Returns a list of security signals with severity and recommendations.
        """
        signals = []
        now = datetime.utcnow()

        # Signal 1: Repeated permission denials (3+ in 24 hours)
        denial_cutoff = now - timedelta(hours=24)
        denials = db.query(WorkspaceGovernanceAuditEvent).filter(
            WorkspaceGovernanceAuditEvent.workspace_id == workspace_id,
            WorkspaceGovernanceAuditEvent.event_type == "GOVERNANCE_PERMISSION_DENIED",
            WorkspaceGovernanceAuditEvent.timestamp >= denial_cutoff
        ).all()

        # Group by user
        denial_counts = {}
        for denial in denials:
            user_id = str(denial.actor_user_id) if denial.actor_user_id else "unknown"
            denial_counts[user_id] = denial_counts.get(user_id, 0) + 1

        for user_id, count in denial_counts.items():
            if count >= 3:
                signals.append({
                    "signal_type": "REPEATED_PERMISSION_DENIALS",
                    "severity": "HIGH",
                    "description": f"User {user_id} has {count} permission denials in 24 hours",
                    "recommendation": "Review user permissions and role assignments",
                    "affected_user_id": user_id,
                    "count": count,
                    "detected_at": now.isoformat()
                })

        # Signal 2: Attempted self-approvals (blocked approvals)
        self_approval_cutoff = now - timedelta(days=7)
        self_approvals = db.query(WorkspaceGovernanceAuditEvent).filter(
            WorkspaceGovernanceAuditEvent.workspace_id == workspace_id,
            WorkspaceGovernanceAuditEvent.event_type == "GOVERNANCE_SELF_APPROVAL_BLOCKED",
            WorkspaceGovernanceAuditEvent.timestamp >= self_approval_cutoff
        ).all()

        if len(self_approvals) > 0:
            signals.append({
                "signal_type": "SELF_APPROVAL_ATTEMPTS",
                "severity": "MEDIUM",
                "description": f"{len(self_approvals)} self-approval attempts blocked in last 7 days",
                "recommendation": "Review exception approval workflow and segregation of duties",
                "count": len(self_approvals),
                "detected_at": now.isoformat()
            })

        # Signal 3: Frequent role changes (3+ in 7 days)
        role_change_cutoff = now - timedelta(days=7)
        role_assignments = db.query(GovernanceRoleAssignment).filter(
            GovernanceRoleAssignment.workspace_id == workspace_id,
            GovernanceRoleAssignment.created_at >= role_change_cutoff
        ).all()

        # Group by user
        role_change_counts = {}
        for assignment in role_assignments:
            user_id = str(assignment.user_id)
            role_change_counts[user_id] = role_change_counts.get(user_id, 0) + 1

        for user_id, count in role_change_counts.items():
            if count >= 3:
                signals.append({
                    "signal_type": "FREQUENT_ROLE_CHANGES",
                    "severity": "MEDIUM",
                    "description": f"User {user_id} has {count} role changes in 7 days",
                    "recommendation": "Review role assignment stability and authorization workflow",
                    "affected_user_id": user_id,
                    "count": count,
                    "detected_at": now.isoformat()
                })

        # Signal 4: High exception rate
        exception_cutoff = now - timedelta(days=30)
        exceptions = db.query(CICDPolicyException).filter(
            CICDPolicyException.workspace_id == workspace_id,
            CICDPolicyException.created_at >= exception_cutoff
        ).count()

        if exceptions >= 10:
            signals.append({
                "signal_type": "HIGH_EXCEPTION_RATE",
                "severity": "MEDIUM",
                "description": f"{exceptions} policy exceptions created in last 30 days",
                "recommendation": "Review policy configuration and exception approval process",
                "count": exceptions,
                "detected_at": now.isoformat()
            })

        # Signal 5: Bulk operation failures
        bulk_failure_cutoff = now - timedelta(days=7)
        bulk_failures = db.query(WorkspaceGovernanceAuditEvent).filter(
            WorkspaceGovernanceAuditEvent.workspace_id == workspace_id,
            WorkspaceGovernanceAuditEvent.event_type == "CI_CD_BULK_POLICY_PARTIAL_FAILURE",
            WorkspaceGovernanceAuditEvent.timestamp >= bulk_failure_cutoff
        ).count()

        if bulk_failures > 0:
            signals.append({
                "signal_type": "BULK_OPERATION_FAILURES",
                "severity": "HIGH",
                "description": f"{bulk_failures} bulk policy operation failures in last 7 days",
                "recommendation": "Review bulk operation permissions and repository configurations",
                "count": bulk_failures,
                "detected_at": now.isoformat()
            })

        # Signal 6: Repetitive policy drift
        drift_cutoff = now - timedelta(days=30)
        drift_events = db.query(WorkspaceGovernanceAuditEvent).filter(
            WorkspaceGovernanceAuditEvent.workspace_id == workspace_id,
            WorkspaceGovernanceAuditEvent.event_type.like("%DRIFT%"),
            WorkspaceGovernanceAuditEvent.timestamp >= drift_cutoff
        ).count()

        if drift_events >= 5:
            signals.append({
                "signal_type": "REPETITIVE_POLICY_DRIFT",
                "severity": "MEDIUM",
                "description": f"{drift_events} policy drift events in last 30 days",
                "recommendation": "Review policy enforcement and repository compliance",
                "count": drift_events,
                "detected_at": now.isoformat()
            })

        # Sort by severity (HIGH > MEDIUM > LOW)
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        signals.sort(key=lambda x: severity_order.get(x["severity"], 99))

        return signals

    @staticmethod
    def get_security_signal_summary(db: Session, workspace_id: uuid.UUID) -> Dict[str, Any]:
        """Get a summary of security signals for dashboard display."""
        signals = GovernanceSecuritySignalService.detect_security_signals(db, workspace_id)

        high_severity = len([s for s in signals if s["severity"] == "HIGH"])
        medium_severity = len([s for s in signals if s["severity"] == "MEDIUM"])
        low_severity = len([s for s in signals if s["severity"] == "LOW"])

        return {
            "total_signals": len(signals),
            "high_severity": high_severity,
            "medium_severity": medium_severity,
            "low_severity": low_severity,
            "signals": signals,
            "calculated_at": datetime.utcnow().isoformat()
        }
