"""
CI/CD Observability Service

Provides metrics, health checks, and operational visibility for CI/CD integration.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.pipeline_execution_job import PipelineExecutionJob, PipelineJobStatus
from app.models.pipeline_run import PipelineRun, PipelineRunStatus, QualityGateStatus
from app.models.repository import Repository
from app.models.ci_token import CIToken
from app.models.ci_token_audit import CITokenAuditEvent


class CICDObservabilityService:
    """Service for CI/CD observability metrics and health checks."""
    
    # SLO Thresholds (in seconds)
    SLO_PIPELINE_TRIGGER_P95 = 2.0  # seconds
    SLO_PIPELINE_JOB_PROCESSING_P95 = 120.0  # seconds (2 minutes)
    SLO_GITHUB_PUBLISHING_SUCCESS_RATE = 0.99  # 99%
    SLO_PR_COMMENT_SUCCESS_RATE = 0.99  # 99%
    SLO_ARTIFACT_GENERATION_SUCCESS_RATE = 0.99  # 99%
    SLO_DEAD_LETTER_RESOLUTION_HOURS = 24.0  # hours
    SLO_WEBHOOK_PROCESSING_P95 = 30.0  # seconds
    
    # Health thresholds
    HEALTH_BACKLOG_THRESHOLD = 100  # jobs
    HEALTH_DEAD_LETTER_THRESHOLD = 5  # jobs
    HEALTH_FAILURE_RATE_THRESHOLD = 0.05  # 5%
    
    def get_repository_metrics(self, db: Session, repository_id: uuid.UUID) -> Dict[str, Any]:
        """
        Get comprehensive CI/CD metrics for a repository.
        
        Returns pipeline runs, jobs, performance, GitHub publishing,
        artifacts, and CI token metrics.
        """
        # Pipeline run metrics
        pipeline_runs = self._get_pipeline_run_metrics(db, repository_id)
        
        # Job metrics
        jobs = self._get_job_metrics(db, repository_id)
        
        # Performance metrics
        performance = self._get_performance_metrics(db, repository_id)
        
        # GitHub publishing metrics (simulated from pipeline runs)
        github_publishing = self._get_github_publishing_metrics(db, repository_id)
        
        # Artifact metrics (simulated from CI token usage)
        artifacts = self._get_artifact_metrics(db, repository_id)
        
        # CI token metrics
        ci_tokens = self._get_ci_token_metrics(db, repository_id)
        
        return {
            "pipelineRuns": pipeline_runs,
            "jobs": jobs,
            "performance": performance,
            "githubPublishing": github_publishing,
            "artifacts": artifacts,
            "ciTokens": ci_tokens,
        }
    
    def _get_pipeline_run_metrics(self, db: Session, repository_id: uuid.UUID) -> Dict[str, int]:
        """Get pipeline run counts by status."""
        total = db.query(PipelineRun).filter(
            PipelineRun.repository_id == repository_id
        ).count()
        
        running = db.query(PipelineRun).filter(
            and_(
                PipelineRun.repository_id == repository_id,
                PipelineRun.status == PipelineRunStatus.RUNNING
            )
        ).count()
        
        completed = db.query(PipelineRun).filter(
            and_(
                PipelineRun.repository_id == repository_id,
                PipelineRun.status == PipelineRunStatus.COMPLETED
            )
        ).count()
        
        failed = db.query(PipelineRun).filter(
            and_(
                PipelineRun.repository_id == repository_id,
                PipelineRun.status == PipelineRunStatus.FAILED
            )
        ).count()
        
        blocked = db.query(PipelineRun).filter(
            and_(
                PipelineRun.repository_id == repository_id,
                PipelineRun.quality_gate == QualityGateStatus.BLOCKED
            )
        ).count()
        
        return {
            "total": total,
            "running": running,
            "completed": completed,
            "failed": failed,
            "blocked": blocked,
        }
    
    def _get_job_metrics(self, db: Session, repository_id: uuid.UUID) -> Dict[str, int]:
        """Get job counts by status."""
        pending = db.query(PipelineExecutionJob).filter(
            and_(
                PipelineExecutionJob.repository_id == repository_id,
                PipelineExecutionJob.status == PipelineJobStatus.PENDING
            )
        ).count()
        
        in_progress = db.query(PipelineExecutionJob).filter(
            and_(
                PipelineExecutionJob.repository_id == repository_id,
                PipelineExecutionJob.status == PipelineJobStatus.IN_PROGRESS
            )
        ).count()
        
        retry_pending = db.query(PipelineExecutionJob).filter(
            and_(
                PipelineExecutionJob.repository_id == repository_id,
                PipelineExecutionJob.status == PipelineJobStatus.RETRY_PENDING
            )
        ).count()
        
        dead_letter = db.query(PipelineExecutionJob).filter(
            and_(
                PipelineExecutionJob.repository_id == repository_id,
                PipelineExecutionJob.status == PipelineJobStatus.DEAD_LETTER
            )
        ).count()
        
        return {
            "pending": pending,
            "inProgress": in_progress,
            "retryPending": retry_pending,
            "deadLetter": dead_letter,
        }
    
    def _get_performance_metrics(self, db: Session, repository_id: uuid.UUID) -> Dict[str, float]:
        """Get performance metrics (queue time, processing time)."""
        # Average queue time (created_at to started_at)
        queue_times = db.query(
            func.julianday(PipelineExecutionJob.started_at) - func.julianday(PipelineExecutionJob.created_at)
        ).filter(
            and_(
                PipelineExecutionJob.repository_id == repository_id,
                PipelineExecutionJob.started_at.isnot(None)
            )
        ).all()
        
        if queue_times:
            avg_queue_seconds = sum([t[0] * 86400 for t in queue_times]) / len(queue_times)
        else:
            avg_queue_seconds = 0.0
        
        # Average processing time (started_at to completed_at)
        processing_times = db.query(
            func.julianday(PipelineExecutionJob.completed_at) - func.julianday(PipelineExecutionJob.started_at)
        ).filter(
            and_(
                PipelineExecutionJob.repository_id == repository_id,
                PipelineExecutionJob.started_at.isnot(None),
                PipelineExecutionJob.completed_at.isnot(None)
            )
        ).all()
        
        if processing_times:
            avg_processing_seconds = sum([t[0] * 86400 for t in processing_times]) / len(processing_times)
            # Estimate p95 as 2.5x average (simplified)
            p95_processing_seconds = avg_processing_seconds * 2.5
        else:
            avg_processing_seconds = 0.0
            p95_processing_seconds = 0.0
        
        return {
            "averageQueueSeconds": round(avg_queue_seconds, 2),
            "averageProcessingSeconds": round(avg_processing_seconds, 2),
            "p95ProcessingSeconds": round(p95_processing_seconds, 2),
        }
    
    def _get_github_publishing_metrics(self, db: Session, repository_id: uuid.UUID) -> Dict[str, int]:
        """
        Get GitHub publishing metrics.
        Simulated from pipeline run quality gate results.
        """
        # Count completed pipeline runs as proxy for status publishing
        total_completed = db.query(PipelineRun).filter(
            and_(
                PipelineRun.repository_id == repository_id,
                PipelineRun.status == PipelineRunStatus.COMPLETED
            )
        ).count()
        
        # Count failed as proxy for publishing failures
        total_failed = db.query(PipelineRun).filter(
            and_(
                PipelineRun.repository_id == repository_id,
                PipelineRun.status == PipelineRunStatus.FAILED
            )
        ).count()
        
        # Estimate comment success (simplified - same as status for now)
        comment_success = total_completed
        comment_failed = total_failed
        
        return {
            "statusSuccess": total_completed,
            "statusFailed": total_failed,
            "commentSuccess": comment_success,
            "commentFailed": comment_failed,
        }
    
    def _get_artifact_metrics(self, db: Session, repository_id: uuid.UUID) -> Dict[str, int]:
        """
        Get artifact access metrics.
        Simulated from CI token audit events.
        """
        # Count successful token uses as proxy for artifact downloads
        downloads = db.query(CITokenAuditEvent).filter(
            and_(
                CITokenAuditEvent.repository_id == repository_id,
                CITokenAuditEvent.event_type == "TOKEN_USED"
            )
        ).count()
        
        # Count token rejections as proxy for artifact failures
        failures = db.query(CITokenAuditEvent).filter(
            and_(
                CITokenAuditEvent.repository_id == repository_id,
                CITokenAuditEvent.event_type == "TOKEN_REJECTED"
            )
        ).count()
        
        return {
            "downloads": downloads,
            "failures": failures,
        }
    
    def _get_ci_token_metrics(self, db: Session, repository_id: uuid.UUID) -> Dict[str, int]:
        """Get CI token usage metrics."""
        # Count active tokens
        active_tokens = db.query(CIToken).filter(
            and_(
                CIToken.repository_id == repository_id,
                CIToken.revoked_at.is_(None)
            )
        ).count()
        
        # Count token uses
        used = db.query(CITokenAuditEvent).filter(
            and_(
                CITokenAuditEvent.repository_id == repository_id,
                CITokenAuditEvent.event_type == "TOKEN_USED"
            )
        ).count()
        
        # Count token rejections
        rejected = db.query(CITokenAuditEvent).filter(
            and_(
                CITokenAuditEvent.repository_id == repository_id,
                CITokenAuditEvent.event_type == "TOKEN_REJECTED"
            )
        ).count()
        
        return {
            "active": active_tokens,
            "used": used,
            "rejected": rejected,
        }
    
    def get_health_summary(self, db: Session, repository_id: uuid.UUID) -> Dict[str, Any]:
        """
        Get health summary for a repository's CI/CD integration.
        
        Returns overall status (HEALTHY, DEGRADED, CRITICAL, UNKNOWN)
        and individual health checks.
        """
        checks = []
        
        # Check 1: Async worker activity
        worker_check = self._check_worker_activity(db, repository_id)
        checks.append(worker_check)
        
        # Check 2: Pending backlog
        backlog_check = self._check_backlog(db, repository_id)
        checks.append(backlog_check)
        
        # Check 3: Dead-letter jobs
        dead_letter_check = self._check_dead_letter(db, repository_id)
        checks.append(dead_letter_check)
        
        # Check 4: GitHub publishing success rate
        publishing_check = self._check_github_publishing(db, repository_id)
        checks.append(publishing_check)
        
        # Check 5: Artifact failures
        artifact_check = self._check_artifact_failures(db, repository_id)
        checks.append(artifact_check)
        
        # Check 6: CI token rejection spike
        token_check = self._check_ci_token_rejections(db, repository_id)
        checks.append(token_check)
        
        # Check 7: Latest successful pipeline run
        pipeline_check = self._check_latest_pipeline(db, repository_id)
        checks.append(pipeline_check)
        
        # Determine overall status
        overall_status = self._determine_overall_status(checks)
        
        return {
            "status": overall_status,
            "checks": checks,
        }
    
    def _check_worker_activity(self, db: Session, repository_id: uuid.UUID) -> Dict[str, Any]:
        """Check if worker has processed jobs recently."""
        # Check for jobs completed in the last 5 minutes
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        recent_completions = db.query(PipelineExecutionJob).filter(
            and_(
                PipelineExecutionJob.repository_id == repository_id,
                PipelineExecutionJob.status == PipelineJobStatus.COMPLETED,
                PipelineExecutionJob.completed_at >= five_minutes_ago
            )
        ).count()
        
        if recent_completions > 0:
            return {
                "name": "Async worker",
                "status": "HEALTHY",
                "message": f"Worker processed {recent_completions} job(s) in the last 5 minutes.",
            }
        else:
            return {
                "name": "Async worker",
                "status": "UNKNOWN",
                "message": "No jobs completed in the last 5 minutes. Worker may be idle or stalled.",
            }
    
    def _check_backlog(self, db: Session, repository_id: uuid.UUID) -> Dict[str, Any]:
        """Check if pending backlog is too high."""
        pending_count = db.query(PipelineExecutionJob).filter(
            and_(
                PipelineExecutionJob.repository_id == repository_id,
                PipelineExecutionJob.status == PipelineJobStatus.PENDING
            )
        ).count()
        
        if pending_count > self.HEALTH_BACKLOG_THRESHOLD:
            return {
                "name": "Pending backlog",
                "status": "DEGRADED",
                "message": f"{pending_count} pending jobs exceed threshold of {self.HEALTH_BACKLOG_THRESHOLD}.",
            }
        else:
            return {
                "name": "Pending backlog",
                "status": "HEALTHY",
                "message": f"{pending_count} pending jobs within acceptable threshold.",
            }
    
    def _check_dead_letter(self, db: Session, repository_id: uuid.UUID) -> Dict[str, Any]:
        """Check for dead-letter jobs requiring operator action."""
        dead_letter_count = db.query(PipelineExecutionJob).filter(
            and_(
                PipelineExecutionJob.repository_id == repository_id,
                PipelineExecutionJob.status == PipelineJobStatus.DEAD_LETTER
            )
        ).count()
        
        if dead_letter_count > 0:
            return {
                "name": "Dead-letter jobs",
                "status": "CRITICAL",
                "message": f"{dead_letter_count} job(s) require operator action.",
            }
        else:
            return {
                "name": "Dead-letter jobs",
                "status": "HEALTHY",
                "message": "No dead-letter jobs.",
            }
    
    def _check_github_publishing(self, db: Session, repository_id: uuid.UUID) -> Dict[str, Any]:
        """Check GitHub publishing success rate."""
        total_completed = db.query(PipelineRun).filter(
            and_(
                PipelineRun.repository_id == repository_id,
                PipelineRun.status == PipelineRunStatus.COMPLETED
            )
        ).count()
        
        total_failed = db.query(PipelineRun).filter(
            and_(
                PipelineRun.repository_id == repository_id,
                PipelineRun.status == PipelineRunStatus.FAILED
            )
        ).count()
        
        total = total_completed + total_failed
        
        if total > 0:
            success_rate = total_completed / total
            if success_rate < self.SLO_GITHUB_PUBLISHING_SUCCESS_RATE:
                return {
                    "name": "GitHub publishing",
                    "status": "DEGRADED",
                    "message": f"Success rate {success_rate:.1%} below SLO of {self.SLO_GITHUB_PUBLISHING_SUCCESS_RATE:.1%}.",
                }
            else:
                return {
                    "name": "GitHub publishing",
                    "status": "HEALTHY",
                    "message": f"Success rate {success_rate:.1%} meets SLO.",
                }
        else:
            return {
                "name": "GitHub publishing",
                "status": "UNKNOWN",
                "message": "No publishing history available.",
            }
    
    def _check_artifact_failures(self, db: Session, repository_id: uuid.UUID) -> Dict[str, Any]:
        """Check for artifact access failures."""
        failures = db.query(CITokenAuditEvent).filter(
            and_(
                CITokenAuditEvent.repository_id == repository_id,
                CITokenAuditEvent.event_type == "TOKEN_REJECTED"
            )
        ).count()
        
        if failures > 10:  # Threshold for artifact failures
            return {
                "name": "Artifact access",
                "status": "DEGRADED",
                "message": f"{failures} artifact access failures detected.",
            }
        else:
            return {
                "name": "Artifact access",
                "status": "HEALTHY",
                "message": f"{failures} artifact access failures within acceptable range.",
            }
    
    def _check_ci_token_rejections(self, db: Session, repository_id: uuid.UUID) -> Dict[str, Any]:
        """Check for CI token rejection spike."""
        # Check rejections in the last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_rejections = db.query(CITokenAuditEvent).filter(
            and_(
                CITokenAuditEvent.repository_id == repository_id,
                CITokenAuditEvent.event_type == "TOKEN_REJECTED",
                CITokenAuditEvent.created_at >= one_hour_ago
            )
        ).count()
        
        if recent_rejections > 5:  # Spike threshold
            return {
                "name": "CI token rejections",
                "status": "CRITICAL",
                "message": f"{recent_rejections} token rejections in the last hour - possible security incident.",
            }
        else:
            return {
                "name": "CI token rejections",
                "status": "HEALTHY",
                "message": f"{recent_rejections} token rejections in the last hour.",
            }
    
    def _check_latest_pipeline(self, db: Session, repository_id: uuid.UUID) -> Dict[str, Any]:
        """Check for recent successful pipeline run."""
        latest_completed = db.query(PipelineRun).filter(
            and_(
                PipelineRun.repository_id == repository_id,
                PipelineRun.status == PipelineRunStatus.COMPLETED
            )
        ).order_by(PipelineRun.completed_at.desc()).first()
        
        if latest_completed and latest_completed.completed_at:
            hours_since = (datetime.utcnow() - latest_completed.completed_at).total_seconds() / 3600
            if hours_since < 24:
                return {
                    "name": "Latest pipeline run",
                    "status": "HEALTHY",
                    "message": f"Last successful run {hours_since:.1f} hours ago.",
                }
            else:
                return {
                    "name": "Latest pipeline run",
                    "status": "DEGRADED",
                    "message": f"Last successful run {hours_since:.1f} hours ago - may indicate stale integration.",
                }
        else:
            return {
                "name": "Latest pipeline run",
                "status": "UNKNOWN",
                "message": "No successful pipeline runs found.",
            }
    
    def _determine_overall_status(self, checks: List[Dict[str, Any]]) -> str:
        """Determine overall health status from individual checks."""
        has_critical = any(check["status"] == "CRITICAL" for check in checks)
        has_degraded = any(check["status"] == "DEGRADED" for check in checks)
        has_healthy = any(check["status"] == "HEALTHY" for check in checks)
        
        if has_critical:
            return "CRITICAL"
        elif has_degraded:
            return "DEGRADED"
        elif has_healthy:
            return "HEALTHY"
        else:
            return "UNKNOWN"
