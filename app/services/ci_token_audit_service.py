"""
CI Token Audit Event Service

Logs security audit events for CI token lifecycle and usage.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.ci_token_audit import CITokenAuditEvent, AuditEventType, ActorType
from typing import Optional, Dict, Any


class CITokenAuditService:
    """Service for logging CI token audit events."""
    
    @staticmethod
    def log_event(
        db: Session,
        repository_id: str,
        event_type: AuditEventType,
        actor_type: ActorType,
        token_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CITokenAuditEvent:
        """
        Log a CI token audit event.
        
        Security rules enforced:
        - Never log raw CI token
        - Never log token hash
        - Never log Authorization header
        - Never log GitHub token
        - Never log private key
        - Never log secrets from artifacts
        """
        # Sanitize metadata to ensure no secrets are logged
        sanitized_metadata = CITokenAuditService._sanitize_metadata(metadata or {})
        
        audit_event = CITokenAuditEvent(
            repository_id=repository_id,
            token_id=token_id,
            event_type=event_type,
            actor_type=actor_type,
            source_ip=source_ip,
            user_agent=user_agent,
            created_at=datetime.utcnow(),
            reason=reason,
            metadata_json=sanitized_metadata
        )
        
        db.add(audit_event)
        db.commit()
        db.refresh(audit_event)
        
        return audit_event
    
    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metadata to remove sensitive information.
        
        Removes:
        - token, token_hash, authorization
        - github_token, github_app_token
        - private_key, secret, api_key
        - password, credential
        """
        sensitive_keys = [
            'token', 'token_hash', 'authorization',
            'github_token', 'github_app_token', 'ghp_',
            'private_key', 'secret', 'api_key',
            'password', 'credential', 'bearer'
        ]
        
        sanitized = {}
        for key, value in metadata.items():
            key_lower = key.lower()
            # Check if key contains sensitive patterns
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                # Redact sensitive values
                sanitized[key] = "[REDACTED]"
            else:
                # Recursively sanitize nested dictionaries
                if isinstance(value, dict):
                    sanitized[key] = CITokenAuditService._sanitize_metadata(value)
                else:
                    sanitized[key] = value
        
        return sanitized
    
    @staticmethod
    def log_token_created(
        db: Session,
        repository_id: str,
        token_id: str,
        actor_type: ActorType = ActorType.USER,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> CITokenAuditEvent:
        """Log CI token creation event."""
        return CITokenAuditService.log_event(
            db=db,
            repository_id=repository_id,
            event_type=AuditEventType.CI_TOKEN_CREATED,
            actor_type=actor_type,
            token_id=token_id,
            source_ip=source_ip,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_token_used(
        db: Session,
        repository_id: str,
        token_id: str,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CITokenAuditEvent:
        """Log CI token usage event."""
        return CITokenAuditService.log_event(
            db=db,
            repository_id=repository_id,
            event_type=AuditEventType.CI_TOKEN_USED,
            actor_type=ActorType.CI,
            token_id=token_id,
            source_ip=source_ip,
            user_agent=user_agent,
            metadata=metadata
        )
    
    @staticmethod
    def log_token_revoked(
        db: Session,
        repository_id: str,
        token_id: str,
        actor_type: ActorType = ActorType.USER,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> CITokenAuditEvent:
        """Log CI token revocation event."""
        return CITokenAuditService.log_event(
            db=db,
            repository_id=repository_id,
            event_type=AuditEventType.CI_TOKEN_REVOKED,
            actor_type=actor_type,
            token_id=token_id,
            source_ip=source_ip,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_token_rejected(
        db: Session,
        repository_id: str,
        reason: str,
        token_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> CITokenAuditEvent:
        """Log CI token rejection event."""
        return CITokenAuditService.log_event(
            db=db,
            repository_id=repository_id,
            event_type=AuditEventType.CI_TOKEN_REJECTED,
            actor_type=ActorType.CI,
            token_id=token_id,
            source_ip=source_ip,
            user_agent=user_agent,
            reason=reason
        )
    
    @staticmethod
    def log_pipeline_triggered(
        db: Session,
        repository_id: str,
        token_id: str,
        pipeline_run_id: str,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> CITokenAuditEvent:
        """Log pipeline trigger by CI token event."""
        return CITokenAuditService.log_event(
            db=db,
            repository_id=repository_id,
            event_type=AuditEventType.PIPELINE_TRIGGERED_BY_CI,
            actor_type=ActorType.CI,
            token_id=token_id,
            source_ip=source_ip,
            user_agent=user_agent,
            metadata={"pipeline_run_id": str(pipeline_run_id)}
        )
    
    @staticmethod
    def log_artifact_accessed(
        db: Session,
        repository_id: str,
        token_id: str,
        pipeline_run_id: str,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> CITokenAuditEvent:
        """Log artifact access by CI token event."""
        return CITokenAuditService.log_event(
            db=db,
            repository_id=repository_id,
            event_type=AuditEventType.ARTIFACT_ACCESSED_BY_CI,
            actor_type=ActorType.CI,
            token_id=token_id,
            source_ip=source_ip,
            user_agent=user_agent,
            metadata={"pipeline_run_id": str(pipeline_run_id)}
        )
    
    @staticmethod
    def log_artifact_access_rejected(
        db: Session,
        repository_id: str,
        reason: str,
        token_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> CITokenAuditEvent:
        """Log artifact access rejection event."""
        return CITokenAuditService.log_event(
            db=db,
            repository_id=repository_id,
            event_type=AuditEventType.ARTIFACT_ACCESS_REJECTED,
            actor_type=ActorType.CI,
            token_id=token_id,
            source_ip=source_ip,
            user_agent=user_agent,
            reason=reason
        )
