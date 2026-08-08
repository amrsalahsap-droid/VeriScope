"""
Pipeline Execution Worker Service

Background worker for processing pipeline runs asynchronously.
Handles job claiming, retry/backoff, stale recovery, and GitHub publishing.
"""

import uuid
import signal
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.pipeline_execution_job import PipelineExecutionJob, PipelineJobStatus
from app.models.pipeline_run import PipelineRun, PipelineRunStatus, QualityGateStatus
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import RecommendationRun
from app.models.release_decision import ReleaseDecision
from app.services.quality_gate_service import QualityGateService
from app.services.github_check_service import GitHubCheckService

logger = logging.getLogger("veriscope.worker")


class PipelineExecutionWorker:
    """Background worker for async pipeline execution."""
    
    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.stale_threshold_minutes = 10
        self.backoff_schedule = [1, 5, 15, 60]  # minutes
        self._shutdown_requested = False
        self._current_job: Optional[PipelineExecutionJob] = None
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
    
    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Worker {self.worker_id} received shutdown signal {signum}")
        self._shutdown_requested = True
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested
    
    def request_shutdown(self):
        """Request graceful shutdown."""
        logger.info(f"Worker {self.worker_id} shutdown requested")
        self._shutdown_requested = True
    
    def release_current_job(self, db: Session):
        """
        Safely release the current job during shutdown.
        
        Resets job to PENDING status so it can be claimed by another worker.
        """
        if self._current_job:
            logger.info(f"Worker {self.worker_id} releasing current job {self._current_job.id}")
            try:
                job = db.query(PipelineExecutionJob).filter(
                    PipelineExecutionJob.id == self._current_job.id
                ).first()
                
                if job and job.status == PipelineJobStatus.IN_PROGRESS and job.locked_by == self.worker_id:
                    job.status = PipelineJobStatus.PENDING
                    job.locked_at = None
                    job.locked_by = None
                    job.started_at = None
                    job.attempt_count = max(0, job.attempt_count - 1)
                    db.commit()
                    logger.info(f"Worker {self.worker_id} released job {job.id} back to PENDING")
            except Exception as e:
                logger.error(f"Worker {self.worker_id} failed to release job: {e}")
                db.rollback()
            finally:
                self._current_job = None
    
    def claim_next_job(self, db: Session) -> Optional[PipelineExecutionJob]:
        """
        Atomically claim the next available job.
        
        Uses SELECT ... FOR UPDATE SKIP LOCKED to avoid race conditions.
        Only claims jobs that are PENDING or RETRY_PENDING with next_attempt_at <= now.
        Returns None if shutdown is requested.
        """
        if self._shutdown_requested:
            logger.info(f"Worker {self.worker_id} shutdown requested, not claiming new jobs")
            return None
        
        now = datetime.utcnow()
        
        # Find claimable job with row-level lock
        job = db.query(PipelineExecutionJob).filter(
            and_(
                PipelineExecutionJob.status.in_([
                    PipelineJobStatus.PENDING,
                    PipelineJobStatus.RETRY_PENDING
                ]),
                or_(
                    PipelineExecutionJob.next_attempt_at.is_(None),
                    PipelineExecutionJob.next_attempt_at <= now
                )
            )
        ).order_by(
            PipelineExecutionJob.created_at.asc()
        ).with_for_update(skip_locked=True).first()
        
        if not job:
            return None
        
        # Atomically update job to IN_PROGRESS
        job.status = PipelineJobStatus.IN_PROGRESS
        job.locked_at = now
        job.locked_by = self.worker_id
        job.attempt_count += 1
        job.started_at = now
        db.commit()
        db.refresh(job)
        
        self._current_job = job
        return job
    
    def process_job(self, db: Session, job: PipelineExecutionJob) -> bool:
        """
        Process a claimed job.
        
        Returns True if successful, False if should retry.
        Raises exception for permanent failures.
        """
        try:
            # Load related entities
            pipeline_run = db.query(PipelineRun).filter(
                PipelineRun.id == job.pipeline_run_id
            ).first()
            
            if not pipeline_run:
                self.mark_dead_letter(db, job, "PipelineRun not found")
                return False
            
            repository = db.query(Repository).filter(
                Repository.id == job.repository_id
            ).first()
            
            if not repository:
                self.mark_dead_letter(db, job, "Repository not found")
                return False
            
            # Load recommendation run if available
            recommendation_run = None
            if job.recommendation_run_id:
                recommendation_run = db.query(RecommendationRun).filter(
                    RecommendationRun.id == job.recommendation_run_id
                ).first()
            
            # Compute quality gate if we have a recommendation
            if recommendation_run:
                self._compute_quality_gate(db, pipeline_run, recommendation_run)
            
            # Publish final GitHub status/check
            if repository.owner and repository.full_name:
                self._publish_github_status(db, repository, pipeline_run, job)
            
            # Create/update PR comment
            pull_request = None
            if job.pull_request_id:
                pull_request = db.query(PullRequest).filter(
                    PullRequest.id == job.pull_request_id
                ).first()
            
            if pull_request and repository.owner and repository.full_name:
                self._publish_pr_comment(db, repository, pipeline_run, pull_request, job)
            
            # Generate and store recommendation report artifact
            self._generate_recommendation_artifact(db, repository, pipeline_run, recommendation_run)
            
            # Mark job as completed
            self.mark_completed(db, job, pipeline_run)
            return True
            
        except Exception as e:
            # Determine if error is retryable
            if self._is_retryable_error(e):
                self.mark_retry_pending(db, job, str(e), type(e).__name__)
                return False
            else:
                self.mark_dead_letter(db, job, str(e), type(e).__name__)
                raise
    
    def mark_completed(self, db: Session, job: PipelineExecutionJob, pipeline_run: PipelineRun):
        """Mark job as completed and update pipeline run."""
        job.status = PipelineJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.locked_at = None
        job.locked_by = None
        
        # Update pipeline run status
        pipeline_run.status = PipelineRunStatus.COMPLETED
        pipeline_run.completed_at = datetime.utcnow()
        
        db.commit()
        self._current_job = None
    
    def mark_retry_pending(self, db: Session, job: PipelineExecutionJob, error: str, error_type: str):
        """Mark job for retry with backoff."""
        job.status = PipelineJobStatus.RETRY_PENDING
        job.last_error = error
        job.last_error_type = error_type
        job.locked_at = None
        job.locked_by = None
        
        # Calculate backoff time
        attempt_index = min(job.attempt_count - 1, len(self.backoff_schedule) - 1)
        backoff_minutes = self.backoff_schedule[attempt_index]
        job.next_attempt_at = datetime.utcnow() + timedelta(minutes=backoff_minutes)
        
        db.commit()
        self._current_job = None
    
    def mark_dead_letter(self, db: Session, job: PipelineExecutionJob, error: str, error_type: str):
        """Mark job as dead letter (permanent failure)."""
        job.status = PipelineJobStatus.DEAD_LETTER
        job.last_error = error
        job.last_error_type = error_type
        job.completed_at = datetime.utcnow()
        job.locked_at = None
        job.locked_by = None
        
        # Update pipeline run to failed
        pipeline_run = db.query(PipelineRun).filter(
            PipelineRun.id == job.pipeline_run_id
        ).first()
        if pipeline_run:
            pipeline_run.status = PipelineRunStatus.FAILED
            pipeline_run.completed_at = datetime.utcnow()
        
        db.commit()
        self._current_job = None
    
    def recover_stale_jobs(self, db: Session) -> int:
        """
        Recover jobs that have been IN_PROGRESS too long.
        
        Returns count of recovered jobs.
        """
        threshold = datetime.utcnow() - timedelta(minutes=self.stale_threshold_minutes)
        
        stale_jobs = db.query(PipelineExecutionJob).filter(
            and_(
                PipelineExecutionJob.status == PipelineJobStatus.IN_PROGRESS,
                PipelineExecutionJob.locked_at < threshold
            )
        ).all()
        
        count = 0
        for job in stale_jobs:
            job.status = PipelineJobStatus.RETRY_PENDING
            job.locked_at = None
            job.locked_by = None
            job.last_error = f"Stale job recovered by {self.worker_id}"
            job.last_error_type = "StaleRecovery"
            
            # Calculate backoff
            attempt_index = min(job.attempt_count, len(self.backoff_schedule) - 1)
            backoff_minutes = self.backoff_schedule[attempt_index]
            job.next_attempt_at = datetime.utcnow() + timedelta(minutes=backoff_minutes)
            
            count += 1
        
        if count > 0:
            db.commit()
        
        return count
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.
        
        Retryable:
        - GitHub rate limit (429)
        - GitHub 5xx errors
        - Network timeouts
        - Transient failures
        
        Not retryable:
        - Invalid CI token
        - PR not found
        - Repository not found
        - Permission errors
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # Non-retryable errors
        non_retryable = [
            'authentication',
            'authorization',
            'permission',
            'not found',
            'invalid token',
            'revoked',
        ]
        
        for keyword in non_retryable:
            if keyword in error_msg:
                return False
        
        # Retryable by default for transient errors
        return True
    
    def get_job_status(self, db: Session, job_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get current status of a job."""
        job = db.query(PipelineExecutionJob).filter(
            PipelineExecutionJob.id == job_id
        ).first()
        
        if not job:
            return None
        
        return {
            "id": str(job.id),
            "status": job.status.value,
            "attempt_count": job.attempt_count,
            "max_attempts": job.max_attempts,
            "next_attempt_at": job.next_attempt_at.isoformat() if job.next_attempt_at else None,
            "last_error": job.last_error,
            "last_error_type": job.last_error_type,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }
    
    def _compute_quality_gate(
        self,
        db: Session,
        pipeline_run: PipelineRun,
        recommendation_run: RecommendationRun
    ):
        """Compute quality gate based on recommendation state."""
        # Get release decision
        release_decision = db.query(ReleaseDecision).filter(
            ReleaseDecision.recommendation_run_id == recommendation_run.id
        ).first()
        
        # Get required before release count from regression scope
        required_count = 0
        if recommendation_run.requirement_evidence_snapshot_json:
            try:
                import json
                snapshot = json.loads(recommendation_run.requirement_evidence_snapshot_json)
                required_count = len(snapshot.get("required_items", []))
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Compute quality gate
        quality_gate = QualityGateService.compute_quality_gate(
            release_decision=release_decision,
            recommendation_health=recommendation_run.evidence_health_status,
            required_before_release_count=required_count,
            has_blocking_failed_tests=False,
            recommendation_generation_failed=False
        )
        
        pipeline_run.quality_gate = quality_gate
        
        # Update status based on quality gate
        if quality_gate in [QualityGateStatus.PASSED, QualityGateStatus.PARTIAL, QualityGateStatus.FAILED]:
            pipeline_run.status = PipelineRunStatus.COMPLETED
            pipeline_run.completed_at = datetime.utcnow()
        elif quality_gate == QualityGateStatus.BLOCKED:
            pipeline_run.status = PipelineRunStatus.FAILED
            pipeline_run.completed_at = datetime.utcnow()
    
    def _publish_github_status(
        self,
        db: Session,
        repository: Repository,
        pipeline_run: PipelineRun,
        job: PipelineExecutionJob
    ):
        """Publish final GitHub status/check."""
        try:
            ci_fail_on_partial = repository.ci_fail_on_partial if hasattr(repository, 'ci_fail_on_partial') else False
            
            # Resolve GitHub installation token dynamically
            github_token = "test"  # Fallback
            if repository.installation_id:
                try:
                    from app.services.github_api_client import GitHubApiClient
                    github_client = GitHubApiClient()
                    github_token = github_client.get_installation_token(repository.installation_id)
                except Exception as e:
                    logger.error(f"Failed to resolve GitHub installation token: {e}")
            
            github_service = GitHubCheckService(
                github_token=github_token,
                ci_fail_on_partial=ci_fail_on_partial
            )
            
            owner, repo = repository.full_name.split('/', 1)
            final_status = github_service.map_quality_gate_to_status(
                QualityGateStatus(pipeline_run.quality_gate)
            )
            
            description = f"Quality Gate: {pipeline_run.quality_gate}"
            if pipeline_run.quality_gate == QualityGateStatus.PARTIAL.value:
                description += " (some requirements pending)"
            elif pipeline_run.quality_gate == QualityGateStatus.PASSED.value:
                description += " (all requirements met)"
            
            github_service.create_commit_status(
                owner=owner,
                repo=repo,
                commit_sha=pipeline_run.commit_sha,
                state=final_status,
                description=description,
                context="veriscope/quality-gate"
            )
        except Exception as e:
            # Log error but don't fail job
            import logging
            logging.getLogger("veriscope.worker").error(f"Failed to publish GitHub status: {e}")
    
    def _publish_pr_comment(
        self,
        db: Session,
        repository: Repository,
        pipeline_run: PipelineRun,
        pull_request: PullRequest,
        job: PipelineExecutionJob
    ):
        """Create or update PR comment with quality gate result."""
        try:
            ci_fail_on_partial = repository.ci_fail_on_partial if hasattr(repository, 'ci_fail_on_partial') else False
            
            # Resolve GitHub installation token dynamically
            github_token = "test"  # Fallback
            if repository.installation_id:
                try:
                    from app.services.github_api_client import GitHubApiClient
                    github_client = GitHubApiClient()
                    github_token = github_client.get_installation_token(repository.installation_id)
                except Exception as e:
                    logger.error(f"Failed to resolve GitHub installation token: {e}")
            
            github_service = GitHubCheckService(
                github_token=github_token,
                ci_fail_on_partial=ci_fail_on_partial
            )
            
            # Build response for comment generation
            from app.services.pipeline_run_service import PipelineRunService
            response = PipelineRunService._build_response(db, pipeline_run)
            
            comment = GitHubCheckService.generate_pr_comment(
                quality_gate=QualityGateStatus(pipeline_run.quality_gate),
                required_count=response.required_before_release,
                regression_scope_summary=response.regression_scope.dict(),
                summary_text=response.summary,
                recommendation_url=f"https://veriscope.app/recommendations/{response.recommendation_run_id}" if response.recommendation_run_id else None,
                artifact_url=f"https://veriscope.app/api/pipeline-runs/{pipeline_run.id}/artifact",
                recommendation_health=response.recommendation_health,
                release_decision=response.release_decision,
                changed_files=response.changed_files
            )
            
            owner, repo = repository.full_name.split('/', 1)
            github_service.post_pr_comment(
                owner=owner,
                repo=repo,
                pull_number=pull_request.number,
                body=comment
            )
        except Exception as e:
            # Log error but don't fail job
            import logging
            logging.getLogger("veriscope.worker").error(f"Failed to publish PR comment: {e}")
    
    def _generate_recommendation_artifact(
        self,
        db: Session,
        repository: Repository,
        pipeline_run: PipelineRun,
        recommendation_run: Optional[RecommendationRun]
    ):
        """Generate and store recommendation report artifact."""
        try:
            if not recommendation_run:
                logger.warning("No recommendation run available, skipping artifact generation")
                return
            
            from app.services.pipeline_run_service import PipelineRunService
            response = PipelineRunService._build_response(db, pipeline_run)
            
            # Build artifact content
            artifact_content = {
                "summary": response.summary,
                "release_decision": response.release_decision,
                "quality_gate": response.quality_gate,
                "required_before_release": response.required_before_release,
                "regression_scope": response.regression_scope.dict(),
                "recommendation_health": response.recommendation_health,
                "changed_files": response.changed_files,
                "recommendation_run_id": str(response.recommendation_run_id) if response.recommendation_run_id else None,
                "pipeline_run_id": str(response.pipeline_run_id),
                "commit_sha": pipeline_run.commit_sha,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Store artifact in database
            from app.models.artifact import RawArtifact
            import json
            
            artifact = RawArtifact(
                id=uuid.uuid4(),
                artifact_type="RECOMMENDATION_REPORT",
                repository_id=repository.id,
                storage_path=f"recommendation_reports/{pipeline_run.id}.json",
                artifact_metadata={
                    "recommendation_run_id": str(recommendation_run.id),
                    "pipeline_run_id": str(pipeline_run.id),
                    "commit_sha": pipeline_run.commit_sha
                },
                created_at=datetime.utcnow()
            )
            
            db.add(artifact)
            db.flush()
            
            logger.info(f"Generated recommendation report artifact: {artifact.id}")
            
        except Exception as e:
            # Log error but don't fail job
            import logging
            logging.getLogger("veriscope.worker").error(f"Failed to generate recommendation artifact: {e}")

