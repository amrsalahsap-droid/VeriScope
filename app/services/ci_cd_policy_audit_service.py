"""
CI/CD Policy Audit Service

Manages audit events for CI/CD policy changes and manual overrides.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.ci_cd_policy_audit import CICDPolicyAuditEvent


class CICDPolicyAuditService:
    """Service for managing CI/CD policy audit events."""
    
    @staticmethod
    def log_policy_created(
        db: Session,
        repository_id: UUID,
        policy: Dict[str, Any],
        actor_id: Optional[UUID] = None,
        actor_type: str = "USER"
    ):
        """Log policy creation event."""
        event = CICDPolicyAuditEvent(
            repository_id=repository_id,
            event_type="CREATED",
            actor_id=actor_id,
            actor_type=actor_type,
            before_policy=None,
            after_policy=policy,
            changed_fields=list(policy.keys()),
            timestamp=datetime.utcnow()
        )
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_policy_updated(
        db: Session,
        repository_id: UUID,
        before_policy: Dict[str, Any],
        after_policy: Dict[str, Any],
        changed_fields: List[str],
        actor_id: Optional[UUID] = None,
        actor_type: str = "USER"
    ):
        """Log policy update event."""
        event = CICDPolicyAuditEvent(
            repository_id=repository_id,
            event_type="UPDATED",
            actor_id=actor_id,
            actor_type=actor_type,
            before_policy=before_policy,
            after_policy=after_policy,
            changed_fields=changed_fields,
            timestamp=datetime.utcnow()
        )
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_policy_previewed(
        db: Session,
        repository_id: UUID,
        scenario: Dict[str, Any],
        result: Dict[str, Any],
        actor_id: Optional[UUID] = None,
        actor_type: str = "USER"
    ):
        """Log policy preview event."""
        event = CICDPolicyAuditEvent(
            repository_id=repository_id,
            event_type="PREVIEWED",
            actor_id=actor_id,
            actor_type=actor_type,
            before_policy=scenario,
            after_policy=result,
            changed_fields=["preview"],
            timestamp=datetime.utcnow()
        )
        db.add(event)
        db.commit()
    
    @staticmethod
    def log_manual_override(
        db: Session,
        repository_id: UUID,
        original_quality_gate: str,
        override_decision: str,
        reason: str,
        actor_id: Optional[UUID] = None,
        actor_type: str = "USER"
    ):
        """Log manual override event."""
        event = CICDPolicyAuditEvent(
            repository_id=repository_id,
            event_type="MANUAL_OVERRIDE",
            actor_id=actor_id,
            actor_type=actor_type,
            original_quality_gate=original_quality_gate,
            override_decision=override_decision,
            override_reason=reason,
            timestamp=datetime.utcnow()
        )
        db.add(event)
        db.commit()
    
    @staticmethod
    def get_audit_history(
        db: Session,
        repository_id: UUID,
        limit: int = 100
    ) -> List[CICDPolicyAuditEvent]:
        """Get audit history for a repository."""
        return db.query(CICDPolicyAuditEvent).filter(
            CICDPolicyAuditEvent.repository_id == repository_id
        ).order_by(CICDPolicyAuditEvent.timestamp.desc()).limit(limit).all()
