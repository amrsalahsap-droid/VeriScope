"""
CI/CD Alert Service

Manages operational alerts for CI/CD integration health and failures.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.cicd_alert import CICDAlert, AlertSeverity, AlertType
from app.models.pipeline_execution_job import PipelineExecutionJob, PipelineJobStatus
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.ci_token_audit import CITokenAuditEvent
from app.services.cicd_observability_service import CICDObservabilityService


class CICDAlertService:
    """Service for managing CI/CD operational alerts."""
    
    def __init__(self):
        self.observability_service = CICDObservabilityService()
    
    def create_alert(
        self,
        db: Session,
        repository_id: uuid.UUID,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        recommended_action: Optional[str] = None,
        pipeline_run_id: Optional[uuid.UUID] = None,
        pipeline_job_id: Optional[uuid.UUID] = None,
        metadata_json: Optional[Dict[str, Any]] = None
    ) -> CICDAlert:
        """Create a new CI/CD alert."""
        alert = CICDAlert(
            repository_id=repository_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            recommended_action=recommended_action,
            pipeline_run_id=pipeline_run_id,
            pipeline_job_id=pipeline_job_id,
            metadata_json=metadata_json,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert
    
    def get_active_alerts(self, db: Session, repository_id: uuid.UUID) -> List[CICDAlert]:
        """Get all active (unresolved) alerts for a repository."""
        return db.query(CICDAlert).filter(
            and_(
                CICDAlert.repository_id == repository_id,
                CICDAlert.resolved_at.is_(None)
            )
        ).order_by(CICDAlert.created_at.desc()).all()
    
    def resolve_alert(self, db: Session, alert_id: uuid.UUID) -> Optional[CICDAlert]:
        """Resolve an alert."""
        alert = db.query(CICDAlert).filter(CICDAlert.id == alert_id).first()
        if alert:
            alert.resolve()
            db.commit()
            db.refresh(alert)
        return alert
    
    def evaluate_and_create_alerts(self, db: Session, repository_id: uuid.UUID) -> List[CICDAlert]:
        """
        Evaluate repository health and create alerts for any issues.
        
        Returns list of newly created alerts.
        """
        health = self.observability_service.get_health_summary(db, repository_id)
        new_alerts = []
        
        for check in health["checks"]:
            if check["status"] in ("CRITICAL", "DEGRADED"):
                # Check if similar alert already exists and is unresolved
                existing_alert = self._find_similar_alert(db, repository_id, check["name"])
                if not existing_alert:
                    severity = AlertSeverity.CRITICAL if check["status"] == "CRITICAL" else AlertSeverity.WARNING
                    alert_type = self._map_check_name_to_alert_type(check["name"])
                    
                    alert = self.create_alert(
                        db=db,
                        repository_id=repository_id,
                        alert_type=alert_type,
                        severity=severity,
                        title=f"{check['name']} - {check['status']}",
                        message=check["message"],
                        recommended_action=self._get_recommended_action(check["name"]),
                    )
                    new_alerts.append(alert)
        
        return new_alerts
    
    def _find_similar_alert(self, db: Session, repository_id: uuid.UUID, check_name: str) -> Optional[CICDAlert]:
        """Find an existing unresolved alert for the same check."""
        alert_type = self._map_check_name_to_alert_type(check_name)
        return db.query(CICDAlert).filter(
            and_(
                CICDAlert.repository_id == repository_id,
                CICDAlert.alert_type == alert_type,
                CICDAlert.resolved_at.is_(None)
            )
        ).first()
    
    def _map_check_name_to_alert_type(self, check_name: str) -> AlertType:
        """Map health check name to alert type."""
        mapping = {
            "Async worker": AlertType.WORKER_STALE_OR_INACTIVE,
            "Pending backlog": AlertType.PIPELINE_BACKLOG_HIGH,
            "Dead-letter jobs": AlertType.PIPELINE_DEAD_LETTER_PRESENT,
            "GitHub publishing": AlertType.GITHUB_PUBLISHING_FAILURE_SPIKE,
            "Artifact access": AlertType.ARTIFACT_FAILURE_SPIKE,
            "CI token rejections": AlertType.CI_TOKEN_REJECTION_SPIKE,
            "Latest pipeline run": AlertType.NO_RECENT_SUCCESSFUL_PIPELINE,
        }
        return mapping.get(check_name, AlertType.PIPELINE_BACKLOG_HIGH)
    
    def _get_recommended_action(self, check_name: str) -> str:
        """Get recommended action for a health check."""
        actions = {
            "Async worker": "Check worker process status and logs. Restart worker if necessary.",
            "Pending backlog": "Scale up worker capacity or investigate slow processing.",
            "Dead-letter jobs": "Review dead-letter jobs and retry or cancel as appropriate.",
            "GitHub publishing": "Check GitHub API rate limits and authentication credentials.",
            "Artifact access": "Review CI token configuration and artifact permissions.",
            "CI token rejections": "Investigate potential security incident or token configuration issues.",
            "Latest pipeline run": "Verify GitHub webhook delivery and trigger a test pipeline run.",
        }
        return actions.get(check_name, "Review system logs and investigate the issue.")
