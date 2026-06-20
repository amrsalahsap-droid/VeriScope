"""
Sync Queue Worker Service

Processes durable sync queue for manual test execution synchronization.
Provides crash recovery, retry logic, and worker coordination.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.manual_execution_sync_event import ManualExecutionSyncEvent
from app.models.manual_test_execution import ManualTestExecution
from app.models.integration_provider_cooldown import IntegrationProviderCooldown
from app.services.integration_sync_service import IntegrationSyncService
from app.services.sync_retry_policy_service import SyncRetryPolicyService, ErrorType

logger = logging.getLogger("veriscope.sync_queue_worker")


class SyncQueueWorker:
    """
    Worker for processing durable sync queue.
    
    Responsibilities:
    - Poll for PENDING / RETRY_PENDING events
    - Claim jobs with DB-level locking
    - Process sync events
    - Handle retries with backoff
    - Mark DEAD_LETTER after max attempts
    - Recover stale IN_PROGRESS jobs
    """
    
    # Configuration
    SYNC_JOB_LOCK_TIMEOUT_SECONDS = 300  # 5 minutes
    MAX_ATTEMPTS = 5  # Increased from 3 to 5 for better retry coverage
    WORKER_ID = f"worker-{uuid.uuid4()}"
    
    def __init__(self, db: Session, enable_jitter: bool = True):
        """
        Initialize the worker with database session.
        
        Args:
            db: Database session
            enable_jitter: Whether to enable jitter in retry calculations (set False for tests)
        """
        self.db = db
        self.retry_policy = SyncRetryPolicyService(enable_jitter=enable_jitter)
    
    def recover_stale_jobs(self) -> int:
        """
        Recover stale IN_PROGRESS jobs that exceeded lock timeout.
        
        Returns:
            Number of jobs recovered
        """
        timeout_threshold = datetime.utcnow() - timedelta(
            seconds=self.SYNC_JOB_LOCK_TIMEOUT_SECONDS
        )
        
        stale_jobs = self.db.query(ManualExecutionSyncEvent).filter(
            ManualExecutionSyncEvent.status == "IN_PROGRESS",
            ManualExecutionSyncEvent.locked_at < timeout_threshold
        ).all()
        
        count = 0
        for job in stale_jobs:
            logger.warning(
                f"Recovering stale IN_PROGRESS job {job.id} "
                f"(locked at {job.locked_at} by {job.locked_by})"
            )
            job.status = "RETRY_PENDING"
            job.locked_at = None
            job.locked_by = None
            job.next_attempt_at = datetime.utcnow()
            job.last_error = "Job recovered after lock timeout"
            count += 1
        
        if count > 0:
            self.db.commit()
            logger.info(f"Recovered {count} stale IN_PROGRESS jobs")
        
        return count
    
    def _check_provider_cooldown(self, provider: str, repository_id: str) -> Optional[IntegrationProviderCooldown]:
        """
        Check if a provider is under cooldown.
        
        Args:
            provider: Provider name (TESTRAIL, XRAY, ZEPHYR)
            repository_id: Repository ID
            
        Returns:
            Active cooldown or None
        """
        cooldown = self.db.query(IntegrationProviderCooldown).filter(
            IntegrationProviderCooldown.provider == provider,
            IntegrationProviderCooldown.repository_id == repository_id,
            IntegrationProviderCooldown.cooldown_until > datetime.utcnow()
        ).first()
        
        if cooldown:
            logger.info(
                f"Provider {provider} for repository {repository_id} is under cooldown "
                f"until {cooldown.cooldown_until} (reason: {cooldown.reason})"
            )
        
        return cooldown
    
    def _set_provider_cooldown(
        self,
        provider: str,
        repository_id: str,
        cooldown_until: datetime,
        reason: str
    ):
        """
        Set a provider cooldown.
        
        Args:
            provider: Provider name
            repository_id: Repository ID
            cooldown_until: When cooldown expires
            reason: Reason for cooldown
        """
        # Delete existing cooldown for this provider/repository
        self.db.query(IntegrationProviderCooldown).filter(
            IntegrationProviderCooldown.provider == provider,
            IntegrationProviderCooldown.repository_id == repository_id
        ).delete()
        
        # Create new cooldown
        cooldown = IntegrationProviderCooldown(
            repository_id=repository_id,
            provider=provider,
            cooldown_until=cooldown_until,
            reason=reason
        )
        self.db.add(cooldown)
        self.db.commit()
        
        logger.info(
            f"Set cooldown for provider {provider} (repository {repository_id}) "
            f"until {cooldown_until} (reason: {reason})"
        )
    
    def claim_job(self) -> Optional[ManualExecutionSyncEvent]:
        """
        Claim a PENDING or RETRY_PENDING job using DB-level atomic update.
        
        Returns:
            Claimed job or None if no jobs available
        """
        now = datetime.utcnow()
        
        # Find a job to claim
        job = self.db.query(ManualExecutionSyncEvent).filter(
            or_(
                and_(
                    ManualExecutionSyncEvent.status == "PENDING",
                    ManualExecutionSyncEvent.next_attempt_at.is_(None)
                ),
                and_(
                    ManualExecutionSyncEvent.status == "RETRY_PENDING",
                    ManualExecutionSyncEvent.next_attempt_at <= now
                )
            )
        ).order_by(ManualExecutionSyncEvent.created_at).first()
        
        if not job:
            return None
        
        # Get repository_id from execution for cooldown check
        execution = self.db.query(ManualTestExecution).filter(
            ManualTestExecution.id == job.execution_id
        ).first()
        
        # Check provider cooldown before claiming (if execution exists)
        if execution:
            cooldown = self._check_provider_cooldown(job.provider, str(execution.repository_id))
            if cooldown:
                # Provider is under cooldown, skip this job
                # Update next_attempt_at to cooldown expiry
                job.next_attempt_at = cooldown.cooldown_until
                job.last_error = f"Provider under cooldown until {cooldown.cooldown_until}"
                self.db.commit()
                logger.info(f"Skipping job {job.id} due to provider cooldown")
                return None
        else:
            logger.warning(f"Execution {job.execution_id} not found for job {job.id}, skipping cooldown check")
        
        # Atomic claim using UPDATE with WHERE clause
        result = self.db.query(ManualExecutionSyncEvent).filter(
            ManualExecutionSyncEvent.id == job.id,
            ManualExecutionSyncEvent.status.in_(["PENDING", "RETRY_PENDING"])
        ).update(
            {
                "status": "IN_PROGRESS",
                "locked_at": now,
                "locked_by": self.WORKER_ID
            },
            synchronize_session=False
        )
        
        if result == 0:
            # Job was claimed by another worker
            return None
        
        self.db.commit()
        self.db.refresh(job)
        
        logger.info(f"Claimed job {job.id} for execution {job.execution_id}")
        return job
    
    def process_job(self, job: ManualExecutionSyncEvent) -> bool:
        """
        Process a claimed sync job.
        
        Args:
            job: The sync event to process
            
        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            logger.info(f"Processing job {job.id} (attempt {job.attempt_count + 1}/{job.max_attempts})")
            
            # Get the execution
            execution = self.db.query(ManualTestExecution).filter(
                ManualTestExecution.id == job.execution_id
            ).first()
            
            if not execution:
                logger.error(f"Execution {job.execution_id} not found for job {job.id}")
                self._mark_failed(job, "Execution not found")
                return False
            
            # Process the sync
            sync_service = IntegrationSyncService(self.db)
            sync_service.process_sync_event(job.id)
            
            # Refresh job to check status
            self.db.refresh(job)
            
            if job.status == "SYNCED":
                logger.info(f"Job {job.id} completed successfully")
                return True
            else:
                logger.warning(f"Job {job.id} failed: {job.last_error}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing job {job.id}: {e}", exc_info=True)
            self._mark_failed(job, str(e))
            return False
    
    def _mark_failed(
        self,
        job: ManualExecutionSyncEvent,
        error: str,
        http_status: Optional[int] = None,
        retry_after_seconds: Optional[int] = None
    ):
        """
        Mark a job as failed and schedule retry if attempts remain.
        
        Uses retry policy to determine backoff and error classification.
        
        Args:
            job: The sync event to mark failed
            error: Error message
            http_status: HTTP status code if available
            retry_after_seconds: Retry-After header value if available
        """
        job.attempt_count += 1
        job.last_error = error
        job.locked_at = None
        job.locked_by = None
        
        # Classify the error
        error_type = self.retry_policy.classify_error(error, http_status)
        
        # Check if error is retryable
        if not self.retry_policy.is_retryable(error_type):
            # Non-retryable error, go straight to DEAD_LETTER
            job.status = "DEAD_LETTER"
            job.completed_at = datetime.utcnow()
            job.last_error = f"{error} (Non-retryable: {error_type.value})"
            logger.error(
                f"Job {job.id} marked as DEAD_LETTER due to non-retryable error: {error_type.value}"
            )
            self.db.commit()
            return
        
        # Check if max attempts reached
        if self.retry_policy.should_dead_letter(job.attempt_count, job.max_attempts):
            job.status = "DEAD_LETTER"
            job.completed_at = datetime.utcnow()
            logger.error(
                f"Job {job.id} marked as DEAD_LETTER after {job.attempt_count} attempts"
            )
        else:
            # Schedule retry with backoff using retry policy
            next_attempt_at, _ = self.retry_policy.calculate_next_retry(
                job.attempt_count,
                job.provider,
                error_type,
                retry_after_seconds
            )
            job.status = "RETRY_PENDING"
            job.next_attempt_at = next_attempt_at
            
            # Set provider cooldown on rate limit
            if error_type == ErrorType.RATE_LIMITED:
                cooldown_duration = timedelta(minutes=15)  # 15 minute cooldown on rate limit
                cooldown_until = datetime.utcnow() + cooldown_duration
                self._set_provider_cooldown(
                    job.provider,
                    job.repository_id,
                    cooldown_until,
                    "RATE_LIMITED"
                )
            
            logger.info(
                f"Job {job.id} scheduled for retry at {next_attempt_at} "
                f"(attempt {job.attempt_count}/{job.max_attempts}, error_type: {error_type.value})"
            )
        
        self.db.commit()
    
    def run_single_cycle(self) -> int:
        """
        Run a single worker cycle: recover stale jobs, claim and process one job.
        
        Returns:
            Number of jobs processed
        """
        # Recover stale jobs
        self.recover_stale_jobs()
        
        # Claim and process a job
        job = self.claim_job()
        if job:
            self.process_job(job)
            return 1
        
        return 0
    
    def run_continuous(self, poll_interval_seconds: int = 5):
        """
        Run the worker continuously, polling for jobs.
        
        Args:
            poll_interval_seconds: Seconds to wait between polls
        """
        logger.info(f"Starting continuous sync queue worker (ID: {self.WORKER_ID})")
        
        import time
        while True:
            try:
                processed = self.run_single_cycle()
                if processed == 0:
                    # No jobs to process, wait
                    time.sleep(poll_interval_seconds)
            except Exception as e:
                logger.error(f"Worker cycle error: {e}", exc_info=True)
                time.sleep(poll_interval_seconds)


def run_worker_cycle(db: Session) -> int:
    """
    Convenience function to run a single worker cycle.
    
    Args:
        db: Database session
        
    Returns:
        Number of jobs processed
    """
    worker = SyncQueueWorker(db)
    return worker.run_single_cycle()
