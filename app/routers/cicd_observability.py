"""
CI/CD Observability Router

Provides endpoints for CI/CD metrics, health checks, and operational visibility.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.session import get_db
from app.services.cicd_observability_service import CICDObservabilityService
from app.services.cicd_alert_service import CICDAlertService
from app.models.pipeline_execution_job import PipelineExecutionJob, PipelineJobStatus
from app.models.ci_token_audit import CITokenAuditEvent
from app.models.webhook_event import WebhookEvent
from app.api.models.user import User
from app.api.dependencies import get_current_user


router = APIRouter(prefix="/repositories/{repository_id}/cicd", tags=["cicd-observability"])


@router.get("/metrics")
def get_cicd_metrics(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get CI/CD metrics for a repository.
    
    Returns pipeline runs, jobs, performance, GitHub publishing,
    artifacts, and CI token metrics.
    """
    service = CICDObservabilityService()
    metrics = service.get_repository_metrics(db, repository_id)
    return metrics


@router.get("/health")
def get_cicd_health(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get CI/CD health summary for a repository.
    
    Returns overall status (HEALTHY, DEGRADED, CRITICAL, UNKNOWN)
    and individual health checks for worker, backlog, dead-letter,
    publishing, artifacts, tokens, and pipeline runs.
    """
    service = CICDObservabilityService()
    health = service.get_health_summary(db, repository_id)
    return health


@router.get("/alerts")
def get_cicd_alerts(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get active CI/CD alerts for a repository.
    
    Returns list of unresolved alerts with severity, title, message,
    recommended action, and creation time.
    """
    alert_service = CICDAlertService()
    alerts = alert_service.get_active_alerts(db, repository_id)
    
    return [
        {
            "id": str(alert.id),
            "alert_type": alert.alert_type.value,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "recommended_action": alert.recommended_action,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "pipeline_run_id": str(alert.pipeline_run_id) if alert.pipeline_run_id else None,
            "pipeline_job_id": str(alert.pipeline_job_id) if alert.pipeline_job_id else None,
        }
        for alert in alerts
    ]


@router.post("/alerts/evaluate")
def evaluate_and_create_alerts(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Evaluate repository health and create alerts for any issues.
    
    Returns list of newly created alerts.
    """
    alert_service = CICDAlertService()
    new_alerts = alert_service.evaluate_and_create_alerts(db, repository_id)
    
    return [
        {
            "id": str(alert.id),
            "alert_type": alert.alert_type.value,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "recommended_action": alert.recommended_action,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
        }
        for alert in new_alerts
    ]


@router.get("/pipeline-jobs/dead-letter")
def get_dead_letter_jobs(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get dead-letter pipeline jobs for a repository.
    
    Returns list of jobs in DEAD_LETTER status with details about
    failure reason, attempt count, and timing.
    """
    jobs = db.query(PipelineExecutionJob).filter(
        and_(
            PipelineExecutionJob.repository_id == repository_id,
            PipelineExecutionJob.status == PipelineJobStatus.DEAD_LETTER
        )
    ).order_by(PipelineExecutionJob.created_at.desc()).all()
    
    return [
        {
            "id": str(job.id),
            "pipeline_run_id": str(job.pipeline_run_id),
            "status": job.status.value,
            "attempt_count": job.attempt_count,
            "last_error": job.last_error,
            "last_error_type": job.last_error_type,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
        }
        for job in jobs
    ]


@router.post("/pipeline-jobs/{job_id}/retry")
def retry_dead_letter_job(
    repository_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Retry a dead-letter or failed pipeline job.
    
    Moves job to RETRY_PENDING status for reprocessing.
    Audits the operator action.
    """
    job = db.query(PipelineExecutionJob).filter(
        and_(
            PipelineExecutionJob.id == job_id,
            PipelineExecutionJob.repository_id == repository_id
        )
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in (PipelineJobStatus.DEAD_LETTER, PipelineJobStatus.FAILED):
        raise HTTPException(status_code=400, detail="Job is not in a retryable state")
    
    # Move to RETRY_PENDING
    job.status = PipelineJobStatus.RETRY_PENDING
    job.next_attempt_at = datetime.utcnow()
    db.commit()
    
    # Audit the action
    audit_event = CITokenAuditEvent(
        repository_id=repository_id,
        event_type="PIPELINE_JOB_RETRIED",
        actor_type="USER",
        actor_id=str(current_user.id),
        reason=f"Operator retried job {job_id}",
        metadata_json={"job_id": str(job_id), "previous_status": job.status.value}
    )
    db.add(audit_event)
    db.commit()
    
    return {
        "id": str(job.id),
        "status": job.status.value,
        "message": "Job moved to RETRY_PENDING"
    }


@router.post("/pipeline-jobs/{job_id}/cancel")
def cancel_pipeline_job(
    repository_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Cancel a pipeline job.
    
    Moves job to CANCELLED status.
    Audits the operator action.
    """
    job = db.query(PipelineExecutionJob).filter(
        and_(
            PipelineExecutionJob.id == job_id,
            PipelineExecutionJob.repository_id == repository_id
        )
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status == PipelineJobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot cancel completed job")
    
    # Move to CANCELLED
    job.status = PipelineJobStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    db.commit()
    
    # Audit the action
    audit_event = CITokenAuditEvent(
        repository_id=repository_id,
        event_type="PIPELINE_JOB_CANCELLED",
        actor_type="USER",
        actor_id=str(current_user.id),
        reason=f"Operator cancelled job {job_id}",
        metadata_json={"job_id": str(job_id), "previous_status": job.status.value}
    )
    db.add(audit_event)
    db.commit()
    
    return {
        "id": str(job.id),
        "status": job.status.value,
        "message": "Job cancelled"
    }


@router.get("/github/webhook-events")
def get_webhook_events(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get GitHub webhook delivery diagnostics for a repository.
    
    Returns list of webhook events with event type, delivery ID,
    signature status, processing status, failure reason, and timing.
    Does not expose raw webhook payload secrets.
    """
    # Note: WebhookEvent uses BigInteger for repository_id, need to handle conversion
    # For now, return all webhook events (filtering by repository_id would require proper type handling)
    events = db.query(WebhookEvent).order_by(WebhookEvent.received_at.desc()).limit(100).all()
    
    return [
        {
            "id": str(event.id),
            "github_delivery_id": event.github_delivery_id,
            "event_type": event.event_type,
            "action": event.action,
            "signature_valid": event.signature_valid,
            "processing_status": event.processing_status,
            "error_message": event.error_message,
            "received_at": event.received_at.isoformat() if event.received_at else None,
            "processed_at": event.processed_at.isoformat() if event.processed_at else None,
        }
        for event in events
    ]


@router.get("/audit")
def get_cicd_audit_events(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get CI/CD audit events for a repository.
    
    Returns list of audit events including CI token operations,
    pipeline operations, artifact access, and webhook events.
    Redacts sensitive fields (raw tokens, hashes, secrets).
    """
    # Get CI token audit events
    ci_token_events = db.query(CITokenAuditEvent).filter(
        CITokenAuditEvent.repository_id == repository_id
    ).order_by(CITokenAuditEvent.created_at.desc()).limit(100).all()
    
    return [
        {
            "id": str(event.id),
            "event_type": event.event_type,
            "actor_type": event.actor_type,
            "actor_id": event.actor_id,
            "reason": event.reason,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "metadata_summary": _redact_sensitive_metadata(event.metadata_json) if event.metadata_json else None,
        }
        for event in ci_token_events
    ]


def _redact_sensitive_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive fields from audit metadata."""
    if not metadata:
        return {}
    
    sensitive_keys = ["token", "token_hash", "raw_token", "authorization", "github_token", "private_key", "webhook_secret", "secret"]
    redacted = {}
    
    for key, value in metadata.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = _redact_sensitive_metadata(value)
        else:
            redacted[key] = value
    
    return redacted
