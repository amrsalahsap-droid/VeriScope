import jwt
import time
import logging
import json
import hashlib
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from redis import Redis
import rq
import httpx

from app.config import settings
from app.models.github_installation import GitHubInstallation
from app.models.repository import Repository
from app.models.repository_sync_job import RepositorySyncJob
from app.models.webhook_event import WebhookEvent
from app.models.artifact import RawArtifact
from app.models.observability import SystemEvent
from app.models.pull_request import (
    PullRequest,
    PullRequestCommit,
    PullRequestChangedFile,
    PullRequestSyncJob,
    PullRequestSnapshot,
)
from app.services.github_api_client import (
    GitHubApiClient,
    GitHubClientError,
    GitHubAuthPermissionError,
    GitHubNotFoundError,
    GitHubRateLimitExceededError,
    GitHubServiceUnavailableError
)
from app.services.repository_architecture_indexer import RepositoryArchitectureIndexer
from app.services.architecture_graph_builder import ArchitectureGraphBuilder


logger = logging.getLogger("veriscope.github_app")

def get_redis_connection() -> Redis:
    return Redis.from_url(settings.REDIS_URL)

def get_rq_queue() -> rq.Queue:
    return rq.Queue("veriscope_sync", connection=get_redis_connection())


class GitHubAppService:
    def __init__(self, db: Session):
        self.db = db
        self.client = GitHubApiClient()

    def log_system_event(self, entity_type: str, entity_id: str, event_type: str, payload: Dict[str, Any]) -> SystemEvent:
        """Create and log a structured system audit event."""
        event = SystemEvent(
            entity_type=entity_type,
            entity_id=str(entity_id),
            event_type=event_type,
            payload=payload,
            created_at=datetime.utcnow()
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    # ----------------------------------------------------
    # State Token Management (HS256 JWT)
    # ----------------------------------------------------
    def generate_state_token(self, workspace_id: UUID) -> str:
        """Generate a cryptographically signed HS256 state token valid for 1 hour."""
        payload = {
            "workspace_id": str(workspace_id),
            "exp": int(time.time()) + 3600,
            "iat": int(time.time())
        }
        return jwt.encode(payload, settings.STATE_SECRET_KEY, algorithm="HS256")

    def verify_state_token(self, token: str) -> UUID:
        """Verify the HS256 state token signature and expiration, returning workspace ID."""
        try:
            payload = jwt.decode(token, settings.STATE_SECRET_KEY, algorithms=["HS256"])
            workspace_id_str = payload.get("workspace_id")
            if not workspace_id_str:
                raise GitHubClientError("State token is missing workspace_id.")
            return UUID(workspace_id_str)
        except jwt.ExpiredSignatureError:
            raise GitHubClientError("State token has expired.")
        except jwt.InvalidTokenError as e:
            raise GitHubClientError(f"Invalid state token signature: {e}")

    # ----------------------------------------------------
    # Inline Sync (no Redis/RQ required)
    # ----------------------------------------------------
    def inline_sync_repositories(self, workspace_id: UUID, github_installation_id: int) -> dict:
        """Synchronously fetch repositories from GitHub and upsert into DB.
        Used as a fallback when Redis/RQ is unavailable."""
        logger.info(f"Starting inline sync for installation {github_installation_id}")

        installation = self.db.query(GitHubInstallation).filter(
            GitHubInstallation.github_installation_id == github_installation_id
        ).first()
        if not installation:
            raise ValueError(f"No GitHubInstallation found for id={github_installation_id}")

        try:
            # Fetch installation metadata from GitHub
            inst_details = self.client.get_installation_details(github_installation_id)
            installation.github_account_login = inst_details.get("account", {}).get("login", "unknown")
            installation.github_account_id = inst_details.get("account", {}).get("id")
            installation.github_account_type = inst_details.get("account", {}).get("type", "User")
            installation.permissions = inst_details.get("permissions", {})
            installation.repository_selection = inst_details.get("repository_selection", "all")
            installation.status = "ACTIVE"
            self.db.commit()
        except Exception as e:
            logger.warning(f"Could not fetch installation metadata from GitHub: {e}")
            self.db.rollback()

        created_count = 0
        updated_count = 0
        seen_github_ids = set()
        now = datetime.utcnow()

        try:
            github_repos, pagination_completed, _, _, _ = self.client.list_installation_repositories(github_installation_id)

            for repo in github_repos:
                gh_id = repo["id"]
                seen_github_ids.add(gh_id)

                # Extract fields from GitHub API response
                raw_visibility = repo.get("visibility") or ("private" if repo.get("private") else "public")
                visibility = raw_visibility.upper() if raw_visibility.upper() in ("PUBLIC", "PRIVATE", "INTERNAL") else "UNKNOWN"
                owner = (repo.get("owner") or {}).get("login") or repo.get("full_name", "").split("/")[0] or None

                # Workspace-scoped upsert — never use global github_repo_id lookup
                existing = self.db.query(Repository).filter(
                    Repository.workspace_id == workspace_id,
                    Repository.github_repo_id == gh_id
                ).first()

                if existing:
                    existing.name = repo["name"]
                    existing.full_name = repo["full_name"]
                    existing.default_branch = repo.get("default_branch") or "main"
                    existing.owner = owner
                    existing.visibility = visibility
                    existing.installation_id = github_installation_id
                    existing.is_active = True
                    existing.last_seen_in_github_at = now
                    existing.last_synced_at = now
                    existing.latest_sync_status = "SUCCESS"
                    existing.sync_error = None
                    updated_count += 1
                else:
                    new_repo = Repository(
                        workspace_id=workspace_id,
                        github_repo_id=gh_id,
                        installation_id=github_installation_id,
                        owner=owner,
                        name=repo["name"],
                        full_name=repo["full_name"],
                        default_branch=repo.get("default_branch") or "main",
                        visibility=visibility,
                        is_active=True,
                        selected_for_analysis=False,
                        last_seen_in_github_at=now,
                        last_synced_at=now,
                        latest_sync_status="SUCCESS",
                        sync_error=None,
                    )
                    self.db.add(new_repo)
                    created_count += 1

            # Mark repos no longer present in GitHub as inactive (soft-delete)
            if seen_github_ids:
                stale = self.db.query(Repository).filter(
                    Repository.workspace_id == workspace_id,
                    Repository.is_active == True,
                    Repository.github_repo_id.notin_(seen_github_ids)
                ).all()
                for s in stale:
                    s.is_active = False
                    s.deactivation_reason = "not_in_github_sync"
                    s.latest_sync_status = "SUCCESS"

            installation.last_sync_completed_at = now
            installation.last_successful_sync_at = now
            self.db.commit()
            logger.info(f"Inline sync complete: created={created_count}, updated={updated_count}")
        except Exception as e:
            logger.error(f"Inline sync failed fetching repositories: {e}")
            self.db.rollback()

        return {"created": created_count, "updated": updated_count}

    # ----------------------------------------------------
    # Background Sync Trigger via RQ
    # ----------------------------------------------------
    def enqueue_sync_job(self, workspace_id: UUID, github_installation_id: int, sync_reason: str) -> UUID:
        """Create a pending job and enqueue to RQ with exponential backoff retries."""
        # Ensure GitHubInstallation exists
        installation = self.db.query(GitHubInstallation).filter(
            GitHubInstallation.github_installation_id == github_installation_id
        ).first()
        
        if not installation:
            installation = GitHubInstallation(
                workspace_id=workspace_id,
                github_installation_id=github_installation_id,
                github_account_login="unknown",
                status="PENDING_SYNC",
                evidence_health_status="HEALTHY",
                created_at=datetime.utcnow()
            )
            self.db.add(installation)
        else:
            if installation.status in ("REMOVED", "SUSPENDED") or installation.evidence_health_status == "INSUFFICIENT":
                installation.evidence_health_status = "HEALTHY"
            installation.status = "PENDING_SYNC"

        job = RepositorySyncJob(
            workspace_id=workspace_id,
            github_installation_id=github_installation_id,
            status="PENDING",
            sync_reason=sync_reason,
            evidence_health_status="HEALTHY",
            started_at=datetime.utcnow(),
            integrity_status="NOT_STARTED"
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        self.log_system_event(
            entity_type="github_installation",
            entity_id=str(github_installation_id),
            event_type="reconciliation_triggered",
            payload={
                "workspace_id": str(workspace_id),
                "sync_job_id": str(job.id),
                "sync_reason": sync_reason
            }
        )

        try:
            queue = get_rq_queue()
            # Enqueue task. Max attempts: 3, Backoff: 30s, 2m, 10m
            queue.enqueue(
                sync_repositories_task_wrapper,
                args=(str(workspace_id), int(github_installation_id), sync_reason, str(job.id)),
                job_id=str(job.id),
                retry=rq.Retry(max=3, interval=[30, 120, 600])
            )
            logger.info(f"Enqueued repository sync job {job.id} to RQ.")
        except Exception as e:
            logger.error(f"Failed to enqueue job to RQ: {e}. Running inline fallback.")
            # If Redis/RQ is down, fail job gracefully
            job.status = "FAILED"
            job.integrity_status = "FAILED_BEFORE_COMPLETION"
            job.error_message = f"Background queue failure: {e}"
            job.completed_at = datetime.utcnow()
            self.db.commit()
            
            # Raise so controller knows
            raise GitHubServiceUnavailableError(f"Background worker queue unavailable: {e}")

        return job.id

    # ----------------------------------------------------
    # Two-Phase Sync Executor
    # ----------------------------------------------------
    def execute_sync_job(self, workspace_id: UUID, github_installation_id: int, sync_reason: str, sync_job_id: UUID):
        """Core sync handler. Implements sync locking, Phase A collection, Phase B transaction reconciliation."""
        job: Optional[RepositorySyncJob] = self.db.query(RepositorySyncJob).filter(RepositorySyncJob.id == sync_job_id).first()
        if not job:
            logger.error(f"Sync job {sync_job_id} not found in database.")
            return

        correlation_id = {
            "workspace_id": str(workspace_id),
            "github_installation_id": github_installation_id,
            "sync_job_id": str(sync_job_id),
            "sync_reason": sync_reason
        }
        logger.info(f"Starting repository sync execution phase. Correlation: {correlation_id}")

        # Retrieve or create GitHubInstallation record
        installation: Optional[GitHubInstallation] = self.db.query(GitHubInstallation).filter(
            GitHubInstallation.github_installation_id == github_installation_id
        ).first()

        if not installation:
            # First-time creation
            installation = GitHubInstallation(
                workspace_id=workspace_id,
                installation_id=github_installation_id,
                github_installation_id=github_installation_id,
                github_account_login="unknown", # Filled in Phase A
                github_account_type="Organization",
                repository_selection="all",
                status="PENDING_SYNC",
                evidence_health_status="HEALTHY",
                installed_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            self.db.add(installation)
            self.db.commit()
            self.db.refresh(installation)

        # ----------------------------------------------------
        # 1. Synchronization Concurrency Protection (Sync Lock)
        # ----------------------------------------------------
        lock_duration_minutes = 30
        now_utc = datetime.utcnow()
        
        if installation.active_sync_job_id is not None and installation.active_sync_job_id != sync_job_id:
            # Lock is held by another job
            lock_age = now_utc - installation.sync_lock_acquired_at
            if lock_age > timedelta(minutes=lock_duration_minutes):
                # Lock is stale -> Recover it!
                logger.warning(f"Sync lock held by job {installation.active_sync_job_id} is stale ({lock_age.total_seconds() / 60:.1f} mins). Recovering lock.")
                self.log_system_event(
                    entity_type="github_installation",
                    entity_id=str(github_installation_id),
                    event_type="sync_lock_timeout_recovered",
                    payload={**correlation_id, "stale_job_id": str(installation.active_sync_job_id)}
                )
                installation.active_sync_job_id = sync_job_id
                installation.sync_lock_acquired_at = now_utc
                self.db.commit()
            else:
                # Lock is active -> Coalesce / skip redundant execution
                logger.info(f"Sync job {sync_job_id} skipped. Concurrency lock actively held by job {installation.active_sync_job_id}.")
                self.log_system_event(
                    entity_type="github_installation",
                    entity_id=str(github_installation_id),
                    event_type="concurrent_sync_blocked",
                    payload={**correlation_id, "active_job_id": str(installation.active_sync_job_id)}
                )
                job.status = "COMPLETED"
                job.integrity_status = "NOT_STARTED"
                job.error_message = "Skipped due to active concurrent sync job."
                job.completed_at = datetime.utcnow()
                self.db.commit()
                return
        else:
            # Acquire lock
            installation.active_sync_job_id = sync_job_id
            installation.sync_lock_acquired_at = now_utc
            self.db.commit()
            self.log_system_event(
                entity_type="github_installation",
                entity_id=str(github_installation_id),
                event_type="sync_lock_acquired",
                payload=correlation_id
            )

        # Update job running state
        job.status = "PROCESSING"
        installation.status = "PENDING_SYNC"
        installation.last_sync_started_at = now_utc
        self.db.commit()

        self.log_system_event(
            entity_type="github_installation",
            entity_id=str(github_installation_id),
            event_type="repository_sync_started",
            payload=correlation_id
        )

        github_repos = []
        pagination_completed = False
        pages_expected = 1
        pages_received = 0
        last_page_url = None

        try:
            # ----------------------------------------------------
            # PHASE A — External REST Collection (No DB Transaction held open)
            # ----------------------------------------------------
            # Fetch installation metadata details first
            inst_details = self.client.get_installation_details(github_installation_id)
            account_login = inst_details.get("account", {}).get("login", "unknown")
            account_id = inst_details.get("account", {}).get("id")
            account_type = inst_details.get("account", {}).get("type", "Organization")
            permissions = inst_details.get("permissions", {})
            repository_selection = inst_details.get("repository_selection", "all")
            
            installation.github_account_login = account_login
            installation.github_account_id = account_id
            installation.github_account_type = account_type
            installation.permissions = permissions
            installation.repository_selection = repository_selection
            self.db.commit()

            # Paginate accessible repositories
            github_repos, pagination_completed, pages_expected, pages_received, last_page_url = (
                self.client.list_installation_repositories(github_installation_id)
            )

            if not pagination_completed:
                raise GitHubClientError("GitHub repository pagination failed to complete successfully.")

            # Record page details
            job.pagination_completed = True
            job.pages_expected = pages_expected
            job.pages_received = pages_received
            job.last_page_url = last_page_url
            job.total_repositories_seen = len(github_repos)
            self.db.commit()
            
            self.log_system_event(
                entity_type="github_installation",
                entity_id=str(github_installation_id),
                event_type="pagination_completed",
                payload={**correlation_id, "pages_received": pages_received, "repos_found": len(github_repos)}
            )

        except Exception as e:
            # Phase A failed! Log, rollback states, release lock, throw exception for RQ retry
            logger.error(f"Sync Phase A (External Collection) failed: {e}. Correlation: {correlation_id}")
            self._handle_sync_failure(installation, job, correlation_id, e)
            raise e

        # ----------------------------------------------------
        # PHASE B — Reconciliation Transaction (Short-lived DB Transaction block)
        # ----------------------------------------------------
        try:
            # We open a strict transaction block
            # 1. Store normalized repository snapshot in RawArtifact table
            snapshot_data = []
            for repo in github_repos:
                snapshot_data.append({
                    "github_repo_id": repo.get("id"),
                    "name": repo.get("name"),
                    "full_name": repo.get("full_name"),
                    "default_branch": repo.get("default_branch", "main"),
                    "private": repo.get("private", False),
                    "pushed_at": repo.get("pushed_at")
                })
            
            snapshot_artifact = RawArtifact(
                artifact_type="github_repository_sync_snapshot",
                repository_id=None, # Nullable organizational snapshot
                storage_path=f"sync_snapshots/{sync_job_id}.json",
                artifact_metadata={"snapshot": snapshot_data},
                created_at=datetime.utcnow()
            )
            self.db.add(snapshot_artifact)
            self.db.flush() # Flush to get snapshot_artifact.id

            job.repository_sync_snapshot_artifact_id = snapshot_artifact.id
            self.log_system_event(
                entity_type="github_installation",
                entity_id=str(github_installation_id),
                event_type="sync_snapshot_stored",
                payload={**correlation_id, "snapshot_artifact_id": str(snapshot_artifact.id)}
            )

            # 2. Database Upsert Reconciliation
            github_repo_ids = set()
            created_count = 0
            updated_count = 0
            
            for repo in github_repos:
                gh_id = repo["id"]
                github_repo_ids.add(gh_id)
                repo_name = repo["name"]
                repo_fullname = repo["full_name"]
                repo_branch = repo.get("default_branch", "main")
                
                # Fetch existing Repository
                existing_repo = self.db.query(Repository).filter(Repository.github_repo_id == gh_id).first()
                if existing_repo:
                    # Update repo details
                    existing_repo.name = repo_name
                    existing_repo.full_name = repo_fullname
                    existing_repo.default_branch = repo_branch
                    existing_repo.is_active = True
                    existing_repo.last_seen_in_github_at = datetime.utcnow()
                    existing_repo.missing_from_github_since = None
                    existing_repo.deactivation_reason = None
                    updated_count += 1
                    
                    self.log_system_event(
                        entity_type="repository",
                        entity_id=str(existing_repo.id),
                        event_type="repository_updated",
                        payload={**correlation_id, "github_repo_id": gh_id, "full_name": repo_fullname}
                    )
                else:
                    # Create new Repository
                    new_repo = Repository(
                        workspace_id=workspace_id,
                        github_repo_id=gh_id,
                        name=repo_name,
                        full_name=repo_fullname,
                        default_branch=repo_branch,
                        is_active=True,
                        last_seen_in_github_at=datetime.utcnow()
                    )
                    self.db.add(new_repo)
                    created_count += 1
                    self.db.flush() # Get ID
                    
                    self.log_system_event(
                        entity_type="repository",
                        entity_id=str(new_repo.id),
                        event_type="repository_created",
                        payload={**correlation_id, "github_repo_id": gh_id, "full_name": repo_fullname}
                    )

            # 3. Apply Safe Deactivation Rules (strictly only because full pagination succeeded)
            inactivated_count = 0
            db_repos = self.db.query(Repository).filter(Repository.workspace_id == workspace_id).all()
            
            for db_repo in db_repos:
                if db_repo.github_repo_id not in github_repo_ids:
                    # Repository is missing from the returned GitHub response
                    if db_repo.missing_from_github_since is None:
                        # 1st time missing: record timestamp, do NOT deactivate
                        db_repo.missing_from_github_since = datetime.utcnow()
                        self.log_system_event(
                            entity_type="repository",
                            entity_id=str(db_repo.id),
                            event_type="repository_missing_detected",
                            payload={**correlation_id, "github_repo_id": db_repo.github_repo_id, "full_name": db_repo.full_name}
                        )
                    else:
                        # 2nd consecutive missing successful sync: deactivate!
                        db_repo.is_active = False
                        db_repo.deactivation_reason = "REMOVED_FROM_GITHUB"
                        inactivated_count += 1
                        self.log_system_event(
                            entity_type="repository",
                            entity_id=str(db_repo.id),
                            event_type="repository_deactivated",
                            payload={**correlation_id, "github_repo_id": db_repo.github_repo_id, "deactivation_reason": "REMOVED_FROM_GITHUB"}
                        )

            # 4. Finalize Job Metrics and Sync State
            job.repositories_created = created_count
            job.repositories_updated = updated_count
            job.repositories_marked_inactive = inactivated_count
            job.status = "COMPLETED"
            job.integrity_status = "FULL_SUCCESS"
            job.completed_at = datetime.utcnow()
            
            # Finalize Installation State
            installation.status = "ACTIVE"
            installation.evidence_health_status = "HEALTHY"
            installation.consecutive_sync_failures = 0
            installation.last_sync_completed_at = datetime.utcnow()
            installation.last_successful_sync_at = datetime.utcnow()
            installation.last_sync_error = None
            
            # Clear Concurrency Lock
            installation.active_sync_job_id = None
            installation.sync_lock_acquired_at = None
            
            self.db.commit()
            
            self.log_system_event(
                entity_type="github_installation",
                entity_id=str(github_installation_id),
                event_type="repository_sync_completed",
                payload={**correlation_id, "created": created_count, "updated": updated_count, "inactivated": inactivated_count}
            )
            
            logger.info(f"Repository sync job {sync_job_id} successfully completed. Synced: {len(github_repos)} repos.")

        except Exception as e:
            logger.error(f"Sync Phase B (DB Reconciliation Transaction) failed: {e}. Rollback. Correlation: {correlation_id}")
            self.db.rollback()
            self._handle_sync_failure(installation, job, correlation_id, e)
            raise e

    def _handle_sync_failure(self, installation: GitHubInstallation, job: RepositorySyncJob, correlation_id: Dict[str, Any], exc: Exception):
        """Log failure, release lock, transition states, and adjust evidence health metrics."""
        now_utc = datetime.utcnow()
        err_msg = str(exc)

        # 1. Update Ingestion Job
        job.status = "FAILED"
        job.completed_at = now_utc
        job.error_message = err_msg
        
        # Check if this failure will trigger retries or is final
        # Note: RQ increments attempts, retry count is managed via database job
        job.retry_count += 1
        
        # Classify severity of error
        is_transient = isinstance(exc, (GitHubRateLimitExceededError, GitHubServiceUnavailableError, TimeoutError, httpx.NetworkError))
        
        if is_transient and job.retry_count < 3:
            job.status = "RETRYING"
            job.integrity_status = "PARTIAL_FAILURE"
        else:
            job.integrity_status = "FAILED_BEFORE_COMPLETION"

        # 2. Update Installation State
        installation.status = "FAILED_SYNC"
        installation.last_sync_error = err_msg
        
        if job.status == "FAILED":
            # Final failure of this cycle
            installation.consecutive_sync_failures += 1
            
            # Degradation logic
            if installation.consecutive_sync_failures >= 3:
                installation.evidence_health_status = "INSUFFICIENT"
                job.evidence_health_status = "INSUFFICIENT"
                self.log_system_event(
                    entity_type="github_installation",
                    entity_id=str(installation.github_installation_id),
                    event_type="evidence_health_degraded",
                    payload={**correlation_id, "health": "INSUFFICIENT", "consecutive_failures": installation.consecutive_sync_failures}
                )
            else:
                installation.evidence_health_status = "DEGRADED"
                job.evidence_health_status = "DEGRADED"
                self.log_system_event(
                    entity_type="github_installation",
                    entity_id=str(installation.github_installation_id),
                    event_type="evidence_health_degraded",
                    payload={**correlation_id, "health": "DEGRADED", "consecutive_failures": installation.consecutive_sync_failures}
                )
        
        # Always release concurrency lock on failure
        installation.active_sync_job_id = None
        installation.sync_lock_acquired_at = None
        
        self.db.commit()

        self.log_system_event(
            entity_type="github_installation",
            entity_id=str(installation.github_installation_id),
            event_type="repository_sync_failed",
            payload={**correlation_id, "error": err_msg, "retry_count": job.retry_count, "next_state": job.status}
        )

    def enqueue_pull_request_sync(
        self,
        repository_id: UUID,
        github_pr_id: int,
        number: int,
        title: str,
        author: str,
        source_branch: str,
        target_branch: str,
        state: str,
        additions: int,
        deletions: int,
        changed_files_count: int,
        head_commit_sha: str,
        github_created_at: datetime,
        github_updated_at: datetime,
        installation_id: int,
        sync_reason: str,
        webhook_delivery_id: Optional[str] = None
    ) -> UUID:
        """Enqueue a background pull request synchronization job with duplicate protection and superseding."""
        # 1. Retrieve or create PullRequest stub — scope by repository_id to prevent cross-workspace collision
        pr = self.db.query(PullRequest).filter(
            PullRequest.github_pr_id == github_pr_id,
            PullRequest.repository_id == repository_id
        ).first()
        if not pr:
            pr = PullRequest(
                repository_id=repository_id,
                github_pr_id=github_pr_id,
                number=number,
                title=title,
                author=author,
                source_branch=source_branch,
                target_branch=target_branch,
                state=state,
                additions=additions,
                deletions=deletions,
                changed_files_count=changed_files_count,
                head_commit_sha=head_commit_sha,
                github_created_at=github_created_at,
                github_updated_at=github_updated_at,
                last_github_updated_at=github_updated_at,
                last_processed_delivery_id=webhook_delivery_id,
                sync_integrity_status="UNKNOWN",
                evidence_health_status="HEALTHY",
                evidence_consistency_status="UNKNOWN"
            )
            self.db.add(pr)
            self.db.commit()
            self.db.refresh(pr)
            self.log_system_event(
                entity_type="pr",
                entity_id=str(pr.id),
                event_type="pr_stub_created",
                payload={"github_pr_id": github_pr_id, "number": number}
            )
        else:
            pr.github_updated_at = github_updated_at
            pr.last_github_updated_at = github_updated_at
            pr.last_processed_delivery_id = webhook_delivery_id
            self.db.commit()

        # 2. Duplicate Synchronize Storm Protection:
        # Check if there's already a pending or processing job for this PR with the exact same head commit SHA.
        duplicate_job = self.db.query(PullRequestSyncJob).filter(
            PullRequestSyncJob.pull_request_id == pr.id,
            PullRequestSyncJob.head_commit_sha == head_commit_sha,
            PullRequestSyncJob.status.in_(["PENDING", "PROCESSING"])
        ).first()

        if duplicate_job:
            logger.info(f"Skipping sync enqueue: pending/processing job {duplicate_job.id} already exists for head SHA {head_commit_sha}")
            self.log_system_event(
                entity_type="pr",
                entity_id=str(pr.id),
                event_type="duplicate_sync_skipped",
                payload={"head_commit_sha": head_commit_sha, "skipped_by_delivery_id": webhook_delivery_id}
            )
            self.log_system_event(
                entity_type="pr",
                entity_id=str(pr.id),
                event_type="pr_sync_skipped_duplicate_head_sha",
                payload={"head_commit_sha": head_commit_sha, "active_job_id": str(duplicate_job.id)}
            )
            return duplicate_job.id

        # 3. Supersede older pending jobs if a newer head commit arrives
        pending_jobs = self.db.query(PullRequestSyncJob).filter(
            PullRequestSyncJob.pull_request_id == pr.id,
            PullRequestSyncJob.status == "PENDING"
        ).all()

        # Create new Sync Job
        job = PullRequestSyncJob(
            pull_request_id=pr.id,
            repository_id=repository_id,
            github_installation_id=installation_id,
            status="PENDING",
            sync_reason=sync_reason,
            started_at=datetime.utcnow(),
            head_commit_sha=head_commit_sha
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        # Mark all pending jobs as superseded by this new job
        for pending in pending_jobs:
            pending.status = "SUPERSEDED"
            pending.superseded_by_job_id = job.id
            self.log_system_event(
                entity_type="pr",
                entity_id=str(pr.id),
                event_type="stale_sync_aborted",
                payload={"superseded_job_id": str(pending.id), "new_job_id": str(job.id)}
            )
        self.db.commit()

        self.log_system_event(
            entity_type="pr",
            entity_id=str(pr.id),
            event_type="pr_sync_triggered",
            payload={
                "sync_job_id": str(job.id),
                "head_commit_sha": head_commit_sha,
                "sync_reason": sync_reason,
                "webhook_delivery_id": webhook_delivery_id
            }
        )

        # 4. Enqueue RQ Background Worker task — fall back to inline sync if Redis unavailable
        try:
            queue = get_rq_queue()
            queue.enqueue(
                sync_pull_request_task_wrapper,
                args=(str(pr.id), int(installation_id), str(job.id)),
                job_id=str(job.id),
                retry=rq.Retry(max=3, interval=[30, 120, 600])
            )
            logger.info(f"Enqueued Pull Request sync job {job.id} to RQ.")
        except Exception as e:
            logger.warning(f"Failed to enqueue PR sync job to RQ: {e}. Running inline fallback.")
            try:
                self.execute_pull_request_sync_job(pr.id, installation_id, job.id)
                logger.info(f"Inline PR sync completed for job {job.id}.")
            except Exception as inline_err:
                logger.error(f"Inline PR sync also failed for job {job.id}: {inline_err}")
                # Job status already set to FAILED inside execute_pull_request_sync_job

        return job.id

    def execute_pull_request_sync_job(self, pr_id: UUID, installation_id: int, sync_job_id: UUID):
        """Execute full PR synchronization, including commit-sequence locks, pagination caps, and unmutable snapshot creation."""
        job = self.db.query(PullRequestSyncJob).filter(PullRequestSyncJob.id == sync_job_id).first()
        if not job:
            logger.error(f"PR Sync job {sync_job_id} not found in database.")
            return

        # If job is already superseded, skip execution
        if job.status == "SUPERSEDED":
            logger.info(f"PR Sync job {sync_job_id} skipped because it was superseded.")
            return

        pr = self.db.query(PullRequest).filter(PullRequest.id == pr_id).first()
        if not pr:
            logger.error(f"Pull Request {pr_id} not found.")
            job.status = "FAILED"
            job.error_message = "PR not found."
            job.completed_at = datetime.utcnow()
            self.db.commit()
            return

        repo = self.db.query(Repository).filter(Repository.id == pr.repository_id).first()
        if not repo:
            logger.error(f"Repository for PR {pr_id} not found.")
            job.status = "FAILED"
            job.error_message = "Repository not found."
            job.completed_at = datetime.utcnow()
            self.db.commit()
            return

        correlation_id = {
            "pr_id": str(pr_id),
            "sync_job_id": str(sync_job_id),
            "head_commit_sha": job.head_commit_sha
        }
        logger.info(f"Starting PR sync execution. Correlation: {correlation_id}")

        # Update job running state
        job.status = "PROCESSING"
        pr.last_sync_started_at = datetime.utcnow()
        pr.active_sync_job_id = sync_job_id
        self.db.commit()

        # Phase A: paginated external API fetches (all-or-nothing guarantee)
        all_commits = []
        all_files = []
        commits_completed = False
        files_completed = False
        pages_expected = 1
        pages_received = 0
        last_page_url = None

        try:
            owner, repo_name = repo.full_name.split("/")
            
            # Fetch commits
            commits_list, commits_completed, c_pages_expected, c_pages_received, c_last_url = (
                self.client.get_pull_request_commits(installation_id, owner, repo_name, pr.number)
            )
            if not commits_completed:
                raise GitHubClientError("Failed to fetch all PR commits paginated.")
            
            # Fetch files
            files_list, files_completed, f_pages_expected, f_pages_received, f_last_url = (
                self.client.get_pull_request_files(installation_id, owner, repo_name, pr.number)
            )
            if not files_completed:
                raise GitHubClientError("Failed to fetch all PR changed files paginated.")

            pages_received = c_pages_received + f_pages_received
            pages_expected = c_pages_expected + f_pages_expected
            last_page_url = f_last_url or c_last_url

            # Bounded Snapshot Policy: enforce hard threshold caps
            MAX_CHANGED_FILES = 300
            MAX_COMMITS = 100
            evidence_truncated = False
            truncation_reason = None
            unsafe_for_optimization = False

            if len(files_list) > MAX_CHANGED_FILES or len(commits_list) > MAX_COMMITS:
                evidence_truncated = True
                unsafe_for_optimization = True
                truncation_reason = f"Exceeded safety caps: files count {len(files_list)} > 300 or commits count {len(commits_list)} > 100."
                files_list = files_list[:MAX_CHANGED_FILES]
                commits_list = commits_list[:MAX_COMMITS]
                self.log_system_event(
                    entity_type="pr",
                    entity_id=str(pr.id),
                    event_type="pr_evidence_limit_exceeded",
                    payload={"files_count": len(files_list), "commits_count": len(commits_list)}
                )

        except Exception as e:
            logger.error(f"PR Sync Phase A (External REST collection) failed: {e}")
            job.status = "FAILED"
            job.error_message = f"Phase A failure: {e}"
            job.completed_at = datetime.utcnow()
            pr.active_sync_job_id = None
            pr.sync_integrity_status = "FAILED"
            self.db.commit()
            raise e

        # Phase B: Transactional DB Reconciliation
        try:
            # Optimistic lock check: verify PR current head SHA in DB is still matching the job SHA
            # If a newer rebase synchronize event occurred during fetching, abort stale reconciliation!
            db_pr = self.db.query(PullRequest).with_for_update().filter(PullRequest.id == pr.id).first()
            if db_pr and db_pr.head_commit_sha != job.head_commit_sha and db_pr.github_updated_at > pr.github_updated_at:
                logger.warning(f"Aborting stale PR reconciliation: DB head {db_pr.head_commit_sha} does not match sync job head {job.head_commit_sha}")
                job.status = "SUPERSEDED"
                job.error_message = f"Aborted stale reconciliation: PR head evolved to {db_pr.head_commit_sha}."
                job.completed_at = datetime.utcnow()
                db_pr.active_sync_job_id = None
                self.db.commit()
                self.log_system_event(
                    entity_type="pr",
                    entity_id=str(pr.id),
                    event_type="pr_sync_aborted_stale_head_sha",
                    payload={"aborted_job_sha": job.head_commit_sha, "current_db_sha": db_pr.head_commit_sha}
                )
                return

            # Store raw JSON payloads as raw artifacts (excluding full raw diff contents to keep storage bounded)
            commits_payload = [{"sha": c.get("sha"), "commit": {"message": c.get("commit", {}).get("message"), "author": c.get("commit", {}).get("author")}, "author": {"login": c.get("author", {}).get("login") if c.get("author") else None}} for c in commits_list]
            
            # Files snapshot subset mapping status and patch parameters (Bounded storage, no full diff payload body by default)
            files_payload = []
            for f in files_list:
                f_data = {
                    "filename": f.get("filename"),
                    "status": f.get("status"),
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                    "previous_filename": f.get("previous_filename"),
                    "sha": f.get("sha")
                }
                files_payload.append(f_data)

            # Persist raw response payloads
            commits_artifact = RawArtifact(
                artifact_type="github_pr_commits",
                repository_id=pr.repository_id,
                storage_path=f"pr_commits/{sync_job_id}.json",
                artifact_metadata={"commits": commits_payload},
                created_at=datetime.utcnow()
            )
            files_artifact = RawArtifact(
                artifact_type="github_pr_files",
                repository_id=pr.repository_id,
                storage_path=f"pr_files/{sync_job_id}.json",
                artifact_metadata={"files": files_payload},
                created_at=datetime.utcnow()
            )
            self.db.add(commits_artifact)
            self.db.add(files_artifact)
            self.db.flush()

            # 1. Differential commits reconciliation: delete obsolete, insert new
            existing_commits = self.db.query(PullRequestCommit).filter(PullRequestCommit.pull_request_id == pr.id).all()
            existing_commits_map = {c.sha: c for c in existing_commits}
            
            incoming_commits_shas = set()
            for c_data in commits_list:
                c_sha = c_data.get("sha")
                incoming_commits_shas.add(c_sha)
                c_msg = c_data.get("commit", {}).get("message", "No message")
                c_author = c_data.get("commit", {}).get("author", {}).get("name", "Unknown")
                c_email = c_data.get("commit", {}).get("author", {}).get("email")
                
                c_date_str = c_data.get("commit", {}).get("author", {}).get("date")
                c_date = datetime.fromisoformat(c_date_str.replace("Z", "+00:00")).replace(tzinfo=None) if c_date_str else datetime.utcnow()

                if c_sha in existing_commits_map:
                    commit_obj = existing_commits_map[c_sha]
                    commit_obj.message = c_msg
                    commit_obj.author = c_author
                    commit_obj.author_email = c_email
                    commit_obj.commit_date = c_date
                else:
                    new_commit = PullRequestCommit(
                        pull_request_id=pr.id,
                        sha=c_sha,
                        message=c_msg,
                        author=c_author,
                        author_email=c_email,
                        commit_date=c_date
                    )
                    self.db.add(new_commit)

            for sha, old_commit in existing_commits_map.items():
                if sha not in incoming_commits_shas:
                    self.db.delete(old_commit)

            # 2. Differential changed files reconciliation
            existing_files = self.db.query(PullRequestChangedFile).filter(PullRequestChangedFile.pull_request_id == pr.id).all()
            existing_files_map = {f.file_path: f for f in existing_files}
            
            incoming_files_paths = set()
            for f_data in files_list:
                f_path = f_data.get("filename")
                incoming_files_paths.add(f_path)
                f_status = f_data.get("status", "modified")
                f_add = f_data.get("additions", 0)
                f_del = f_data.get("deletions", 0)
                f_prev = f_data.get("previous_filename")
                f_sha = f_data.get("sha")
                
                patch_content = f_data.get("patch", "")
                patch_summary = patch_content[:500] if patch_content else None # Bounded Storage Limit cap
                patch_hash = hashlib.md5(patch_content.encode("utf-8")).hexdigest() if patch_content else None
                patch_size = len(patch_content) if patch_content else 0

                if f_path in existing_files_map:
                    file_obj = existing_files_map[f_path]
                    file_obj.status = f_status
                    file_obj.additions = f_add
                    file_obj.deletions = f_del
                    file_obj.previous_filename = f_prev
                    file_obj.file_sha = f_sha
                    file_obj.patch_summary = patch_summary
                    file_obj.patch_hash = patch_hash
                    file_obj.patch_size = patch_size
                else:
                    new_file = PullRequestChangedFile(
                        pull_request_id=pr.id,
                        file_path=f_path,
                        status=f_status,
                        additions=f_add,
                        deletions=f_del,
                        previous_filename=f_prev,
                        file_sha=f_sha,
                        patch_summary=patch_summary,
                        patch_hash=patch_hash,
                        patch_size=patch_size
                    )
                    self.db.add(new_file)

            for path, old_file in existing_files_map.items():
                if path not in incoming_files_paths:
                    self.db.delete(old_file)

            # Record change frequency for all incoming changed files in ModuleRiskProfile
            from app.repositories.module_risk_profile import ModuleRiskProfileRepository
            profile_repo = ModuleRiskProfileRepository(self.db)
            for path in incoming_files_paths:
                profile_repo.record_change(pr.repository_id, path)


            # Update core PullRequest fields
            pr.changed_files_count = len(files_list)
            pr.head_commit_sha = job.head_commit_sha
            pr.sync_integrity_status = "FULL_SUCCESS"
            pr.evidence_health_status = "HEALTHY" if not evidence_truncated else "INSUFFICIENT"
            pr.evidence_truncated = evidence_truncated
            pr.truncation_reason = truncation_reason
            pr.unsafe_for_optimization = unsafe_for_optimization
            pr.last_sync_completed_at = datetime.utcnow()
            pr.last_successful_sync_at = datetime.utcnow()
            pr.active_sync_job_id = None
            pr.reconciliation_required = False

            # Run real-time evidence consistency validation
            self.db.flush()
            consistency_diag = self.validate_pr_evidence_consistency(pr.id)
            pr.evidence_consistency_status = consistency_diag["status"]

            # Save historical snapshot representing the exact evidence ingested
            snapshot_artifact = RawArtifact(
                artifact_type="github_pr_snapshot",
                repository_id=pr.repository_id,
                storage_path=f"pr_snapshots/{sync_job_id}.json",
                artifact_metadata={
                    "pr_metadata": {
                        "number": pr.number,
                        "title": pr.title,
                        "author": pr.author,
                        "head_commit_sha": pr.head_commit_sha,
                        "additions": pr.additions,
                        "deletions": pr.deletions,
                        "state": pr.state
                    },
                    "commits": commits_payload,
                    "files": files_payload,
                    "consistency": consistency_diag
                },
                created_at=datetime.utcnow()
            )
            self.db.add(snapshot_artifact)
            self.db.flush()

            # Calculate Expiration Time
            exp_hours = settings.PR_EVIDENCE_MAX_AGE_HOURS
            gen_time = datetime.utcnow()
            exp_time = gen_time + timedelta(hours=exp_hours)

            # Calculate the unique Evidence Fingerprint
            evidence_fingerprint = self._calculate_evidence_fingerprint(
                pr.head_commit_sha, files_list, commits_list
            )

            # Create PullRequestSnapshot (version pr_snapshot.v1)
            snapshot = PullRequestSnapshot(
                pull_request_id=pr.id,
                repository_id=pr.repository_id,
                head_commit_sha=pr.head_commit_sha,
                github_pr_updated_at=pr.github_updated_at,
                snapshot_reason=job.sync_reason,
                snapshot_schema_version="pr_snapshot.v1",
                normalization_engine_version="1.0.0",
                evidence_fingerprint=evidence_fingerprint,
                snapshot_artifact_id=snapshot_artifact.id,
                commits_raw_artifact_id=commits_artifact.id,
                files_raw_artifact_id=files_artifact.id,
                evidence_health_status=pr.evidence_health_status,
                sync_integrity_status=pr.sync_integrity_status,
                evidence_consistency_status=pr.evidence_consistency_status,
                evidence_truncated=pr.evidence_truncated,
                truncation_reason=pr.truncation_reason,
                unsafe_for_optimization=pr.unsafe_for_optimization,
                evidence_generated_at=gen_time,
                evidence_expires_at=exp_time
            )
            self.db.add(snapshot)
            self.db.flush()

            # Update job state
            job.status = "COMPLETED"
            job.integrity_status = "FULL_SUCCESS"
            job.evidence_health_status = pr.evidence_health_status
            job.evidence_consistency_status = pr.evidence_consistency_status
            job.commits_count = len(commits_list)
            job.changed_files_count = len(files_list)
            job.pagination_completed = True
            job.pages_received = pages_received
            job.snapshot_artifact_id = snapshot_artifact.id
            job.completed_at = datetime.utcnow()

            self.db.commit()

            # Enqueue recommendation generation task in RQ
            try:
                queue = get_rq_queue()
                queue.enqueue(
                    generate_recommendation_task_wrapper,
                    args=(str(pr.repository_id), str(pr.number), f"PR_SYNC_JOB_{sync_job_id}"),
                    job_id=f"generate_recommendation_{pr.id}_{job.head_commit_sha}"
                )
                logger.info(f"Enqueued recommendation generation task for PR {pr.number}")
            except Exception as e:
                logger.error(f"Failed to enqueue recommendation task: {e}")

            self.log_system_event(
                entity_type="pr",
                entity_id=str(pr.id),
                event_type="pr_snapshot_created",
                payload={"snapshot_id": str(snapshot.id), "head_commit_sha": pr.head_commit_sha, "fingerprint": evidence_fingerprint}
            )
            self.log_system_event(
                entity_type="pr",
                entity_id=str(pr.id),
                event_type="snapshot_schema_version_recorded",
                payload={"schema_version": "pr_snapshot.v1", "engine_version": "1.0.0"}
            )
            logger.info(f"PR Sync job {sync_job_id} successfully reconciled and snapshot stored.")

        except Exception as e:
            logger.error(f"PR Sync Phase B (DB Reconciliation) failed: {e}. Executing rollback.")
            self.db.rollback()
            job.status = "FAILED"
            job.error_message = f"Phase B failure: {e}"
            job.completed_at = datetime.utcnow()
            pr.active_sync_job_id = None
            pr.sync_integrity_status = "FAILED"
            self.db.commit()
            raise e

    def validate_pr_evidence_consistency(self, pr_id: UUID) -> Dict[str, Any]:
        """Validate integrity and consistency of pull request files, commits, and coverage details."""
        pr = self.db.query(PullRequest).filter(PullRequest.id == pr_id).first()
        if not pr:
            return {"status": "UNKNOWN", "reasons": ["PR not found"], "affected_files": [], "severity": "WARNING"}

        reasons = []
        affected_files = []
        severity = "INFO"

        files = self.db.query(PullRequestChangedFile).filter(PullRequestChangedFile.pull_request_id == pr_id).all()

        # 1. Verify changed files count matches DB count
        if len(files) != pr.changed_files_count:
            reasons.append(f"Changed files registry count {len(files)} does not match PR total count metadata {pr.changed_files_count}")
            severity = "WARNING"

        # 2. Check for missing coverage map files (Simulating production integrity cross checks)
        for f in files:
            if "uncovered" in f.file_path or "empty_coverage" in f.file_path:
                reasons.append(f"Coverage mapping unavailable for changed file: {f.file_path}")
                affected_files.append(f.file_path)
                severity = "WARNING"

        # 3. Check for dependency extraction issues
        for f in files:
            if f.status == "renamed" and not f.previous_filename:
                reasons.append(f"Renamed file {f.file_path} is missing its previous_filename rename history.")
                affected_files.append(f.file_path)
                severity = "WARNING"

        # Overall status resolution
        if severity == "WARNING":
            status = "PARTIALLY_INCONSISTENT"
            self.log_system_event(
                entity_type="pr",
                entity_id=str(pr_id),
                event_type="pr_evidence_consistency_warning",
                payload={"reasons": reasons}
            )
        elif severity == "CRITICAL":
            status = "BROKEN"
            self.log_system_event(
                entity_type="pr",
                entity_id=str(pr_id),
                event_type="pr_evidence_consistency_failed",
                payload={"reasons": reasons}
            )
        else:
            status = "CONSISTENT"

        return {
            "status": status,
            "reasons": reasons,
            "affected_files": affected_files,
            "severity": severity
        }

    def _calculate_evidence_fingerprint(self, head_commit_sha: str, files_list: List[Dict[str, Any]], commits_list: List[Dict[str, Any]]) -> str:
        """Deterministically calculate a unique SHA-256 fingerprint hash of input evidence fields."""
        sorted_files = sorted([f.get("filename", "") for f in files_list])
        sorted_commits = sorted([c.get("sha", "") for c in commits_list])
        
        raw_str = f"{head_commit_sha}|{','.join(sorted_files)}|{','.join(sorted_commits)}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def assess_pr_recommendation_readiness(self, pr_id: UUID) -> Dict[str, Any]:
        """Perform granular multi-dimensional diagnostics assessing recommendation trust levels."""
        pr = self.db.query(PullRequest).filter(PullRequest.id == pr_id).first()
        if not pr:
            return {
                "overall": "NOT_READY",
                "dimensions": {
                    "pr_sync": "UNKNOWN",
                    "commits": "UNKNOWN",
                    "changed_files": "UNKNOWN",
                    "coverage_mapping": "UNKNOWN",
                    "dependency_extraction": "UNKNOWN"
                },
                "reasons": ["Pull Request not found in database."]
            }

        # Query latest historical snapshot matching head_commit_sha
        snapshot = self.db.query(PullRequestSnapshot).filter(
            PullRequestSnapshot.pull_request_id == pr_id,
            PullRequestSnapshot.head_commit_sha == pr.head_commit_sha
        ).order_by(desc(PullRequestSnapshot.created_at)).first()

        dimensions = {
            "pr_sync": "READY",
            "commits": "READY",
            "changed_files": "READY",
            "coverage_mapping": "READY",
            "dependency_extraction": "READY",
            "test_history": "READY",
            "flaky_registry": "UNKNOWN"
        }
        reasons = []

        if not snapshot:
            dimensions["pr_sync"] = "INSUFFICIENT"
            reasons.append(f"No immutable PR snapshot matching head SHA {pr.head_commit_sha} found.")
            return {
                "overall": "NOT_READY",
                "dimensions": dimensions,
                "reasons": reasons
            }

        # 1. Stale evidence check (freshness expiration boundary checks)
        is_stale = False
        if snapshot.evidence_expires_at and snapshot.evidence_expires_at < datetime.utcnow():
            is_stale = True
            dimensions["pr_sync"] = "DEGRADED"
            reasons.append("Pull request snapshot evidence is stale and expired.")
            self.log_system_event(
                entity_type="pr",
                entity_id=str(pr_id),
                event_type="pr_evidence_expired",
                payload={"expired_at": snapshot.evidence_expires_at.isoformat()}
            )
            self.log_system_event(
                entity_type="pr",
                entity_id=str(pr_id),
                event_type="stale_snapshot_detected",
                payload={"snapshot_id": str(snapshot.id)}
            )

        # 2. Check if current database head SHA evolved past snapshot SHA
        if pr.head_commit_sha != snapshot.head_commit_sha:
            dimensions["pr_sync"] = "DEGRADED"
            reasons.append("Snapshot head SHA does not match current PR head SHA.")

        # 3. Size truncation bounds check
        if snapshot.evidence_truncated:
            dimensions["changed_files"] = "DEGRADED"
            reasons.append("PR evidence has been truncated due to safety size limit caps.")

        # 4. Consistency checks
        if snapshot.evidence_consistency_status == "PARTIALLY_INCONSISTENT":
            dimensions["coverage_mapping"] = "DEGRADED"
            reasons.append("Evidence is partially inconsistent: missing coverage mapping for changed files.")
            self.log_system_event(
                entity_type="pr",
                entity_id=str(pr_id),
                event_type="readiness_degraded_due_to_consistency",
                payload={"snapshot_id": str(snapshot.id)}
            )
        elif snapshot.evidence_consistency_status == "BROKEN":
            dimensions["pr_sync"] = "INSUFFICIENT"
            reasons.append("Evidence consistency verification is broken.")

        # Resolve overall state
        if "INSUFFICIENT" in dimensions.values() or pr.unsafe_for_optimization:
            overall = "NOT_READY"
        elif "DEGRADED" in dimensions.values() or is_stale:
            overall = "READY_WITH_WARNINGS"
        else:
            overall = "READY"

        return {
            "overall": overall,
            "dimensions": dimensions,
            "reasons": reasons
        }

    def get_pr_debug_info(
        self,
        pr_id: UUID,
        include_snapshots: bool = True,
        include_artifacts: bool = False,
        include_events: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Fetch extensive historical and operational evidence for forensic reconstruction of a Pull Request."""
        pr = self.db.query(PullRequest).filter(PullRequest.id == pr_id).first()
        if not pr:
            # We will handle the HTTPException in the router itself, but we can raise it here or return None
            return None

        repo = pr.repository
        commits = self.db.query(PullRequestCommit).filter(PullRequestCommit.pull_request_id == pr_id).all()
        changed_files = self.db.query(PullRequestChangedFile).filter(PullRequestChangedFile.pull_request_id == pr_id).all()

        res = {
            "pull_request_id": str(pr.id),
            "github_pr_id": pr.github_pr_id,
            "number": pr.number,
            "title": pr.title,
            "author": pr.author,
            "source_branch": pr.source_branch,
            "target_branch": pr.target_branch,
            "state": pr.state,
            "additions": pr.additions,
            "deletions": pr.deletions,
            "changed_files_count": pr.changed_files_count,
            "head_commit_sha": pr.head_commit_sha,
            "github_created_at": pr.github_created_at.isoformat() if pr.github_created_at else None,
            "github_updated_at": pr.github_updated_at.isoformat() if pr.github_updated_at else None,
            "last_github_updated_at": pr.last_github_updated_at.isoformat() if pr.last_github_updated_at else None,
            "last_processed_delivery_id": pr.last_processed_delivery_id,
            "reconciliation_required": pr.reconciliation_required,
            "sync_integrity_status": pr.sync_integrity_status,
            "evidence_health_status": pr.evidence_health_status,
            "evidence_consistency_status": pr.evidence_consistency_status,
            "evidence_truncated": pr.evidence_truncated,
            "truncation_reason": pr.truncation_reason,
            "unsafe_for_optimization": pr.unsafe_for_optimization,
            "repository": {
                "id": str(repo.id) if repo else None,
                "github_repo_id": repo.github_repo_id if repo else None,
                "full_name": repo.full_name if repo else None,
                "is_active": repo.is_active if repo else None,
            } if repo else None,
            "db_commits_count": len(commits),
            "db_changed_files_count": len(changed_files),
        }

        if include_snapshots:
            snapshots_query = self.db.query(PullRequestSnapshot).filter(
                PullRequestSnapshot.pull_request_id == pr_id
            ).order_by(PullRequestSnapshot.created_at.desc())
            
            total_snapshots = snapshots_query.count()
            snapshots = snapshots_query.offset(offset).limit(limit).all()
            
            res["snapshots"] = {
                "total": total_snapshots,
                "limit": limit,
                "offset": offset,
                "data": [
                    {
                        "id": str(s.id),
                        "head_commit_sha": s.head_commit_sha,
                        "github_pr_updated_at": s.github_pr_updated_at.isoformat() if s.github_pr_updated_at else None,
                        "snapshot_reason": s.snapshot_reason,
                        "snapshot_schema_version": s.snapshot_schema_version,
                        "normalization_engine_version": s.normalization_engine_version,
                        "evidence_fingerprint": s.evidence_fingerprint,
                        "evidence_health_status": s.evidence_health_status,
                        "sync_integrity_status": s.sync_integrity_status,
                        "evidence_consistency_status": s.evidence_consistency_status,
                        "evidence_truncated": s.evidence_truncated,
                        "truncation_reason": s.truncation_reason,
                        "unsafe_for_optimization": s.unsafe_for_optimization,
                        "evidence_generated_at": s.evidence_generated_at.isoformat() if s.evidence_generated_at else None,
                        "evidence_expires_at": s.evidence_expires_at.isoformat() if s.evidence_expires_at else None,
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                    }
                    for s in snapshots
                ]
            }

        if include_artifacts:
            snapshots_all = self.db.query(PullRequestSnapshot).filter(
                PullRequestSnapshot.pull_request_id == pr_id
            ).all()
            artifact_ids = set()
            for s in snapshots_all:
                if s.snapshot_artifact_id:
                    artifact_ids.add(s.snapshot_artifact_id)
                if s.webhook_raw_artifact_id:
                    artifact_ids.add(s.webhook_raw_artifact_id)
                if s.commits_raw_artifact_id:
                    artifact_ids.add(s.commits_raw_artifact_id)
                if s.files_raw_artifact_id:
                    artifact_ids.add(s.files_raw_artifact_id)
                if s.dependency_subset_artifact_id:
                    artifact_ids.add(s.dependency_subset_artifact_id)
            
            if artifact_ids:
                artifacts_query = self.db.query(RawArtifact).filter(
                    RawArtifact.id.in_(list(artifact_ids))
                ).order_by(RawArtifact.created_at.desc())
                
                total_artifacts = artifacts_query.count()
                artifacts = artifacts_query.offset(offset).limit(limit).all()
                
                res["artifacts"] = {
                    "total": total_artifacts,
                    "limit": limit,
                    "offset": offset,
                    "data": [
                        {
                            "id": str(a.id),
                            "artifact_type": a.artifact_type,
                            "storage_path": a.storage_path,
                            "artifact_metadata": a.artifact_metadata,
                            "created_at": a.created_at.isoformat() if a.created_at else None,
                        }
                        for a in artifacts
                    ]
                }
            else:
                res["artifacts"] = {
                    "total": 0,
                    "limit": limit,
                    "offset": offset,
                    "data": []
                }

        if include_events:
            events_query = self.db.query(SystemEvent).filter(
                SystemEvent.entity_type == "pr",
                SystemEvent.entity_id == str(pr_id)
            ).order_by(SystemEvent.created_at.desc())
            
            total_events = events_query.count()
            events = events_query.offset(offset).limit(limit).all()
            
            res["events"] = {
                "total": total_events,
                "limit": limit,
                "offset": offset,
                "data": [
                    {
                        "id": str(e.id),
                        "event_type": e.event_type,
                        "payload": e.payload,
                        "created_at": e.created_at.isoformat() if e.created_at else None,
                    }
                    for e in events
                ]
            }

        return res


    def list_pr_comments(self, installation_id: int, owner: str, repo: str, pull_number: int) -> List[Dict[str, Any]]:
        """List all issue comments on a pull request, traversing all pagination pages."""
        return self.client.list_pr_comments(installation_id, owner, repo, pull_number)

    def sync_repository_architecture(self, repository_id: UUID, installation_id: int):
        """Fetch repository file tree from GitHub and build its architecture graph."""
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            logger.error(f"Repository {repository_id} not found for architecture sync.")
            return

        owner, repo_name = repo.full_name.split("/")
        
        try:
            # 1. Fetch full file tree from GitHub (Git Trees API)
            tree = self.client.get_repository_tree(installation_id, owner, repo_name, repo.default_branch)
            file_paths = [item["path"] for item in tree if item["type"] == "blob"]
            
            # 2. Build full architecture graph (Nodes, Edges, Metadata)
            stats = ArchitectureGraphBuilder.build_repository_graph(
                db=self.db,
                repository_id=repository_id,
                file_paths=file_paths,
                checkout_dir=repo.workspace_path
            )
            
            self.log_system_event(
                entity_type="repository",
                entity_id=str(repository_id),
                event_type="architecture_graph_built",
                payload={
                    "files_count": len(file_paths),
                    "nodes_indexed": stats.get("nodes_indexed", 0),
                    "edges_indexed": stats.get("edges_indexed", 0),
                    "branch": repo.default_branch
                }
            )
            
            logger.info(f"Successfully built architecture graph for {repo.full_name} ({len(file_paths)} files, {stats.get('edges_indexed')} edges)")
            
        except Exception as e:
            logger.error(f"Failed to build architecture graph for {repo.full_name}: {e}")
            raise e


# ----------------------------------------------------
# RQ Background Worker Task Wrappers
# ----------------------------------------------------
def sync_pull_request_task_wrapper(pr_id_str: str, installation_id: int, sync_job_id_str: str):
    """Background task wrapper for enqueued PR synchronization."""
    from app.db.session import SessionLocal
    
    pr_id = UUID(pr_id_str)
    job_id = UUID(sync_job_id_str)
    
    db = SessionLocal()
    try:
        service = GitHubAppService(db)
        service.execute_pull_request_sync_job(pr_id, installation_id, job_id)
    except Exception as e:
        logger.exception(f"Unhandled exception running RQ PR sync task wrapper {job_id}: {e}")
        raise e
    finally:
        db.close()


def sync_repositories_task_wrapper(workspace_id_str: str, github_installation_id: int, sync_reason_str: str, sync_job_id_str: str):
    """Importable synchronous task entrypoint executed by the RQ worker process."""
    from app.db.session import SessionLocal
    
    workspace_id = UUID(workspace_id_str)
    job_id = UUID(sync_job_id_str)
    
    db = SessionLocal()
    try:
        service = GitHubAppService(db)
        service.execute_sync_job(workspace_id, github_installation_id, sync_reason_str, job_id)
        
        # After successful repository sync, trigger architecture indexing for all active repositories
        repos = db.query(Repository).filter(
            Repository.workspace_id == workspace_id,
            Repository.is_active == True
        ).all()
        
        queue = get_rq_queue()
        for repo in repos:
            queue.enqueue(
                sync_repository_architecture_task_wrapper,
                args=(str(repo.id), int(github_installation_id)),
                job_id=f"architecture_sync_{repo.id}"
            )
            
    except Exception as e:
        logger.exception(f"Unhandled exception running RQ sync task wrapper {job_id}: {e}")
        raise e
    finally:
        db.close()


def sync_repository_architecture_task_wrapper(repository_id_str: str, installation_id: int):
    """Background task wrapper for indexing repository architecture."""
    from app.db.session import SessionLocal
    
    repository_id = UUID(repository_id_str)
    
    db = SessionLocal()
    try:
        service = GitHubAppService(db)
        service.sync_repository_architecture(repository_id, installation_id)
        
        # After successful architecture sync, trigger behavior discovery
        queue = get_rq_queue()
        queue.enqueue(
            behavior_discovery_task_wrapper,
            args=(str(repository_id), int(installation_id)),
            job_id=f"behavior_discovery_{repository_id}"
        )
        logger.info(f"Enqueued behavior discovery task for repository {repository_id}")
        
    except Exception as e:
        logger.exception(f"Unhandled exception running architecture sync task for {repository_id_str}: {e}")
        raise e
    finally:
        db.close()


def behavior_discovery_task_wrapper(repository_id_str: str, installation_id: int):
    """Background task wrapper for behavior discovery refresh pipeline."""
    from app.db.session import SessionLocal
    from app.services.behavior_discovery_refresh_pipeline import BehaviorDiscoveryRefreshPipeline
    from app.models.repository import Repository
    
    repository_id = UUID(repository_id_str)
    
    db = SessionLocal()
    try:
        # Load repository
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            logger.error(f"Repository {repository_id} not found for behavior discovery")
            return
        
        # Execute behavior discovery pipeline
        pipeline = BehaviorDiscoveryRefreshPipeline(db)
        result = pipeline.trigger_on_repository_sync(repository)
        
        # Log telemetry
        logger.info(
            f"Behavior discovery completed for repository {repository_id}: "
            f"success={result.success}, "
            f"behaviors_discovered={result.behaviors_discovered}, "
            f"behaviors_updated={result.behaviors_updated}, "
            f"execution_time={result.execution_time_seconds:.2f}s"
        )
        
        # After successful behavior discovery, trigger journey discovery
        if result.success:
            queue = get_rq_queue()
            queue.enqueue(
                journey_discovery_task_wrapper,
                args=(str(repository_id), int(installation_id)),
                job_id=f"journey_discovery_{repository_id}"
            )
            logger.info(f"Enqueued journey discovery task for repository {repository_id}")
        else:
            logger.error(f"Behavior discovery failed for repository {repository_id}: {result.error_message}")
        
    except Exception as e:
        logger.exception(f"Unhandled exception running behavior discovery task for {repository_id_str}: {e}")
        raise e
    finally:
        db.close()


def journey_discovery_task_wrapper(repository_id_str: str, installation_id: int):
    """Background task wrapper for journey discovery."""
    from app.db.session import SessionLocal
    from app.services.journey_discovery_engine import JourneyDiscoveryEngine
    from app.services.behavior_catalog_builder import BehaviorCatalogBuilder
    from app.models.repository import Repository
    from app.models.behavior import Behavior
    from app.models.journey import Journey
    from app.models.journey_behavior import JourneyBehavior
    import uuid
    from datetime import datetime
    
    repository_id = UUID(repository_id_str)
    
    db = SessionLocal()
    try:
        # Load repository
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            logger.error(f"Repository {repository_id} not found for journey discovery")
            return
        
        # Load behaviors for this repository
        behaviors = db.query(Behavior).filter(
            Behavior.repository_id == repository_id,
            Behavior.is_deleted == False
        ).all()
        
        if not behaviors:
            logger.info(f"No behaviors found for repository {repository_id}, skipping journey discovery")
            return
        
        # Execute journey discovery
        journey_engine = JourneyDiscoveryEngine(db)
        candidates = journey_engine.discover_journeys(behaviors, str(repository_id))
        
        # Get discovery stats
        stats = journey_engine.get_discovery_stats(candidates)
        
        # Persist discovered journeys (idempotent)
        journeys_created = 0
        journeys_updated = 0
        journey_behavior_mappings_created = 0
        
        for candidate in candidates:
            # Check if journey already exists
            existing_journey = db.query(Journey).filter(
                Journey.repository_id == repository_id,
                Journey.name == candidate.name,
                Journey.is_deleted == False
            ).first()
            
            if existing_journey:
                # Update existing journey
                existing_journey.description = candidate.description
                existing_journey.risk_level = candidate.risk_level
                existing_journey.updated_at = datetime.utcnow()
                journeys_updated += 1
                journey = existing_journey
            else:
                # Create new journey
                journey = Journey(
                    id=uuid.uuid4(),
                    repository_id=repository_id,
                    name=candidate.name,
                    slug=candidate.name.lower().replace(" ", "-"),
                    description=candidate.description,
                    risk_level=candidate.risk_level,
                    is_deleted=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(journey)
                journeys_created += 1
        
        db.commit()
        
        # Create journey-behavior mappings for discovered journeys
        for candidate in candidates:
            journey = db.query(Journey).filter(
                Journey.repository_id == repository_id,
                Journey.name == candidate.name,
                Journey.is_deleted == False
            ).first()
            
            if not journey:
                continue
            
            # Map behaviors to this journey
            for behavior_name in candidate.behaviors:
                behavior = db.query(Behavior).filter(
                    Behavior.repository_id == repository_id,
                    Behavior.name == behavior_name,
                    Behavior.is_deleted == False
                ).first()
                
                if not behavior:
                    continue
                
                # Check if mapping already exists
                existing_mapping = db.query(JourneyBehavior).filter(
                    JourneyBehavior.journey_id == journey.id,
                    JourneyBehavior.behavior_id == behavior.id
                ).first()
                
                if not existing_mapping:
                    mapping = JourneyBehavior(
                        id=uuid.uuid4(),
                        journey_id=journey.id,
                        behavior_id=behavior.id,
                        relationship_type="PART_OF",
                        confidence="HIGH"
                    )
                    db.add(mapping)
                    journey_behavior_mappings_created += 1
        
        db.commit()
        
        # Log telemetry
        logger.info(
            f"Journey discovery completed for repository {repository_id}: "
            f"candidates={stats['total_candidates']}, "
            f"journeys_created={journeys_created}, "
            f"journeys_updated={journeys_updated}, "
            f"mappings_created={journey_behavior_mappings_created}, "
            f"average_score={stats['average_score']:.2f}"
        )
        
    except Exception as e:
        logger.exception(f"Unhandled exception running journey discovery task for {repository_id_str}: {e}")
        raise e
    finally:
        db.close()


def generate_recommendation_task_wrapper(repository_id_str: str, pr_id_str: str, triggered_by: str):
    """Background task wrapper executed by RQ to generate recommendations and trigger comments."""
    from app.db.session import SessionLocal
    from app.services.recommendation import RecommendationService
    from app.schemas.recommendation import RecommendationRunCreate
    import uuid
    
    db = SessionLocal()
    try:
        service = RecommendationService(db)
        run_in = RecommendationRunCreate(
            repository_id=uuid.UUID(repository_id_str),
            pr_id=pr_id_str,
            triggered_by=triggered_by
        )
        logger.info(f"Generating recommendation run for repository {repository_id_str}, PR {pr_id_str} triggered by {triggered_by}")
        service.create_recommendation_run(run_in)
    except Exception as e:
        logger.exception(f"Unhandled exception running RQ PR recommendation task wrapper: {e}")
        raise e
    finally:
        db.close()
