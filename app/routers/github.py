import hmac
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Header, Request, status, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.github_installation import GitHubInstallation
from app.models.repository import Repository
from app.models.repository_sync_job import RepositorySyncJob
from app.models.webhook_event import WebhookEvent
from app.models.artifact import RawArtifact
from app.models.observability import SystemEvent
from app.models.pull_request import PullRequest, PullRequestCommit, PullRequestChangedFile, PullRequestSyncJob
from app.models.test_result import TestRun, TestResult
from app.models.coverage import CoverageReport
from app.models.recommendation import RecommendationRun
from app.services.repository_readiness import RepositoryReadinessService
from app.services.test_ingestion import TestIngestionService
from app.services.junit_parser import XMLParsingError, OversizedXMLException
from app.services.coverage_ingestion import CoverageIngestionService, CoverageIngestionError
from sqlalchemy import func, distinct
from app.models.user import Workspace, User
from app.schemas.debugging import PRDebugResponse
from app.services.github_app import GitHubAppService
from app.dependencies.auth import get_current_workspace, require_workspace_member, get_current_user
from pydantic import BaseModel

logger = logging.getLogger("veriscope.github_router")

router = APIRouter(prefix="/github", tags=["GitHub Integration"])
security = HTTPBearer(auto_error=False)

async def optional_workspace(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[Workspace]:
    """Optional workspace authentication for development."""
    if not credentials:
        return None
    try:
        from app.dependencies.auth import get_current_user, get_current_workspace
        user = get_current_user(credentials, db)
        return get_current_workspace(user, db)
    except Exception as e:
        logger.warning(f"Failed to resolve optional workspace: {e}")
        return None


# Pydantic models for callback
class InstallationCallbackRequest(BaseModel):
    installation_id: int
    setup_action: str = "install"


class RepositorySelectionRequest(BaseModel):
    repository_ids: list[str]

# Custom Helper to check webhook signature
def verify_signature(secret: str, raw_body: bytes, signature_header: str) -> bool:
    """Validate HMAC-SHA256 signature for incoming GitHub webhook payloads."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_sig = signature_header.split("=")[1]
    
    computed_sig = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_sig, expected_sig)


def _update_repository_webhook_timestamp(db: Session, github_repo_id: int) -> None:
    """Update repository.last_webhook_at to now when webhook received.
    
    This is a fire-and-forget update - failures are logged but don't block
    webhook processing. Workspace scoping is inherent via github_repo_id uniqueness.
    """
    try:
        repo = db.query(Repository).filter(Repository.github_repo_id == github_repo_id).first()
        if repo:
            repo.last_webhook_at = datetime.utcnow()
            db.commit()
            logger.debug(f"Updated last_webhook_at for repository {repo.full_name}")
    except Exception as e:
        logger.warning(f"Failed to update last_webhook_at for github_repo_id {github_repo_id}: {e}")
        db.rollback()


def _get_webhook_status(last_webhook_at: datetime | None) -> str:
    """Calculate webhook status based on last_webhook_at timestamp.
    
    ACTIVE: webhook received within last 24 hours
    INACTIVE: no webhook in last 24 hours (but had one before)
    UNKNOWN: no webhook ever received
    """
    if not last_webhook_at:
        return "UNKNOWN"
    
    cutoff = datetime.utcnow() - timedelta(hours=24)
    if last_webhook_at >= cutoff:
        return "ACTIVE"
    return "INACTIVE"


def _utc_iso(dt: datetime | None) -> str | None:
    """Serialize a UTC-naive datetime to an ISO-8601 string with explicit 'Z' suffix.

    All datetimes in this codebase are stored as UTC-naive (datetime.utcnow()).
    Without the 'Z' suffix, JavaScript's Date constructor interprets the string
    as *local* time, causing timestamps to appear offset by the user's timezone.
    Appending 'Z' tells JavaScript the value is UTC, producing correct relative
    times regardless of the viewer's locale.
    """
    if dt is None:
        return None
    return dt.isoformat() + "Z"


# ----------------------------------------------------
# 1. Installation Link (Frontend Integration)
# ----------------------------------------------------
@router.post("/installation/link")
def handle_installation_link(
    request: InstallationCallbackRequest,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Handle GitHub App installation link from frontend callback.
    
    This endpoint is called after user completes GitHub App installation.
    It links the installation to the user's workspace and triggers repository sync.
    """
    from app.models.user import WorkspaceMember
    
    # Get user's workspace
    member = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a workspace"
        )
    
    workspace_id = member.workspace_id
    
    # Check if this installation_id already exists anywhere (unique constraint)
    any_installation = db.query(GitHubInstallation).filter(
        GitHubInstallation.github_installation_id == request.installation_id
    ).first()

    if any_installation:
        # Reassign to current workspace and mark active (handles cross-workspace duplicates)
        any_installation.workspace_id = workspace_id
        any_installation.installation_id = request.installation_id
        any_installation.status = "ACTIVE"
        any_installation.updated_at = datetime.utcnow()
        db.commit()
        result_status = "updated"
    else:
        # Check if workspace already has a different installation
        existing_installation = db.query(GitHubInstallation).filter(
            GitHubInstallation.workspace_id == workspace_id
        ).first()

        if existing_installation:
            existing_installation.installation_id = request.installation_id
            existing_installation.github_installation_id = request.installation_id
            existing_installation.status = "ACTIVE"
            existing_installation.updated_at = datetime.utcnow()
            db.commit()
            result_status = "updated"
        else:
            installation = GitHubInstallation(
                workspace_id=workspace_id,
                installation_id=request.installation_id,
                github_installation_id=request.installation_id,
                github_account_login=user.name or user.email or "unknown",
                github_account_type="User",
                repository_selection="all",
                status="ACTIVE",
                installed_by=user.name or user.email,
                installed_at=datetime.utcnow()
            )
            db.add(installation)
            db.commit()
            db.refresh(installation)
            result_status = "created"
    
    # Run inline repository sync (no Redis required)
    sync_result = {"created": 0, "updated": 0}
    try:
        service = GitHubAppService(db)
        sync_result = service.inline_sync_repositories(
            workspace_id=workspace_id,
            github_installation_id=request.installation_id
        )
        logger.info(f"Inline sync completed: {sync_result}")
    except Exception as e:
        logger.warning(f"Inline sync failed (will retry later): {e}")

    # Count repos now in DB
    try:
        repo_count = db.query(Repository).filter(Repository.workspace_id == workspace_id).count()
    except Exception:
        db.rollback()
        repo_count = 0

    return {
        "status": result_status,
        "connected": True,
        "installation_id": request.installation_id,
        "repositories_count": repo_count,
        "sync": sync_result
    }


# ----------------------------------------------------
# 2. Installation Callback (Legacy - for workspace-scoped calls)
# ----------------------------------------------------
@router.post("/installation/callback")
def handle_installation_callback(
    request: InstallationCallbackRequest,
    user = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Handle GitHub App installation callback from frontend (workspace-scoped)."""
    # Check if installation already exists for this workspace
    existing_installation = db.query(GitHubInstallation).filter(
        GitHubInstallation.workspace_id == workspace.id
    ).first()
    
    if existing_installation:
        # Update existing installation (idempotent)
        existing_installation.installation_id = request.installation_id
        existing_installation.github_installation_id = request.installation_id
        existing_installation.status = "ACTIVE"
        existing_installation.updated_at = datetime.utcnow()
        db.commit()
        
        result_status = "updated"
    else:
        # Create new installation
        installation = GitHubInstallation(
            workspace_id=workspace.id,
            installation_id=request.installation_id,
            github_installation_id=request.installation_id,
            github_account_login=user.name or user.email or "unknown",
            github_account_type="User",
            repository_selection="all",
            status="ACTIVE",
            installed_by=user.name or user.email,
            installed_at=datetime.utcnow()
        )
        db.add(installation)
        db.commit()
        db.refresh(installation)
        
        result_status = "created"
    
    # Run inline repository sync (no Redis required)
    sync_result = {"created": 0, "updated": 0}
    try:
        service = GitHubAppService(db)
        sync_result = service.inline_sync_repositories(
            workspace_id=workspace.id,
            github_installation_id=request.installation_id
        )
    except Exception as e:
        logger.warning(f"Inline sync failed: {e}")

    repo_count = db.query(Repository).filter(Repository.workspace_id == workspace.id).count()

    return {
        "status": result_status,
        "connected": True,
        "installation_id": request.installation_id,
        "repositories_count": repo_count,
        "sync": sync_result
    }


# ----------------------------------------------------
# 2. Workspace GitHub Installation Status & Repositories
# ----------------------------------------------------
@router.get("/installation/status")
def get_installation_status(
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get GitHub App installation status for the current workspace."""
    try:
        installation = db.query(GitHubInstallation).filter(
            GitHubInstallation.workspace_id == workspace.id
        ).first()

        if not installation:
            return {
                "connected": False,
                "status": "NOT_INSTALLED",
                "installation_id": None,
                "account_login": None,
                "github_installation_id": None,
                "repositories_count": 0
            }

        # Count repositories for this workspace
        repo_count = db.query(Repository).filter(
            Repository.workspace_id == workspace.id
        ).count()

        return {
            "connected": installation.status == "ACTIVE",
            "status": installation.status,
            "installation_id": installation.github_installation_id,
            "account_login": installation.github_account_login,
            "github_installation_id": installation.github_installation_id,
            "installed_by": installation.installed_by,
            "repositories_count": repo_count,
            "created_at": _utc_iso(installation.created_at),
            "last_sync_completed_at": _utc_iso(installation.last_sync_completed_at),
        }
    except Exception as e:
        logger.error(f"Error fetching installation status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch installation status"
        )


@router.get("/repositories")
def get_workspace_repositories(
    selected_only: bool = False,
    workspace: Optional[Workspace] = Depends(optional_workspace),
    db: Session = Depends(get_db)
):
    """Get repositories for a workspace.

    Returns all active, non-seed repositories for the authenticated workspace.
    Workspace-scoped if workspace provided; returns all active repos in dev mode.

    Safety guarantees:
    - Never crashes on NULL installation_id, NULL source, or missing readiness data.
    - Returns 200 with empty list instead of 500 for empty workspace.
    - installation_id filter includes repos with NULL installation_id (pre-sync repos).
    """
    is_demo_mode = (settings.APP_ENV in ("demo", "test", "development"))

    if workspace:
        # Resolve active GitHub App installation for this workspace
        installation = db.query(GitHubInstallation).filter(
            GitHubInstallation.workspace_id == workspace.id,
            GitHubInstallation.status == "ACTIVE"
        ).first()

        query = db.query(Repository).filter(
            Repository.workspace_id == workspace.id,
            Repository.is_active == True
        )

        # Only filter by installation_id when we have one AND the repo has one.
        # Repos synced before the installation record was created may have NULL
        # installation_id — we must NOT exclude them.
        if installation and installation.github_installation_id:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    Repository.installation_id == installation.github_installation_id,
                    Repository.installation_id == None  # noqa: E711  (SQLAlchemy idiom)
                )
            )
    else:
        # No auth / dev fallback: return all active repositories
        query = db.query(Repository).filter(Repository.is_active == True)

    # Exclude seed/test repos in non-demo environments.
    # Use notin_ so NULL source rows are NOT excluded (NULL != 'TEST' is NULL in SQL).
    if not is_demo_mode:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                Repository.source == None,  # noqa: E711
                ~Repository.source.in_(["TEST", "SEED", "DEMO"])
            )
        )

    if selected_only:
        query = query.filter(Repository.selected_for_analysis == True)

    try:
        repositories = query.order_by(Repository.full_name).all()
    except Exception as e:
        logger.error(f"Repository list query failed: {e}", exc_info=True)
        return {
            "repositories": [],
            "summary": {
                "connected_repositories": 0,
                "selected_repositories": 0,
                "ready_repositories": 0,
                "needs_test_history": 0,
                "sync_issues": 0,
            },
            "message": f"Query error: {str(e)[:200]}",
        }

    # Empty workspace — return 200 with empty list, never 500
    if not repositories:
        return {
            "repositories": [],
            "summary": {
                "connected_repositories": 0,
                "selected_repositories": 0,
                "ready_repositories": 0,
                "needs_test_history": 0,
                "sync_issues": 0,
            },
            "message": "No connected repositories found.",
        }

    # ── Bulk counts (all safe against empty repo_ids) ─────────────────────
    repo_ids = [repo.id for repo in repositories]

    test_runs_counts = dict(
        db.query(TestRun.repository_id, func.count(TestRun.id))
        .filter(TestRun.repository_id.in_(repo_ids))
        .group_by(TestRun.repository_id)
        .all()
    )
    coverage_counts = dict(
        db.query(CoverageReport.repository_id, func.count(CoverageReport.id))
        .filter(CoverageReport.repository_id.in_(repo_ids))
        .group_by(CoverageReport.repository_id)
        .all()
    )
    recommendation_counts = dict(
        db.query(RecommendationRun.repository_id, func.count(RecommendationRun.id))
        .filter(RecommendationRun.repository_id.in_(repo_ids))
        .group_by(RecommendationRun.repository_id)
        .all()
    )
    active_pr_counts = dict(
        db.query(PullRequest.repository_id, func.count(PullRequest.id))
        .filter(PullRequest.repository_id.in_(repo_ids), PullRequest.state == "open")
        .group_by(PullRequest.repository_id)
        .all()
    )
    prs_analyzed_counts = dict(
        db.query(PullRequest.repository_id, func.count(PullRequest.id))
        .filter(PullRequest.repository_id.in_(repo_ids), PullRequest.sync_integrity_status == "FULL_SUCCESS")
        .group_by(PullRequest.repository_id)
        .all()
    )

    # ── Readiness (protected — never crashes the list) ────────────────────
    readiness_service = RepositoryReadinessService(db)
    readiness_results = {}
    if workspace:
        try:
            readiness_results = readiness_service.calculate_readiness_bulk(repositories, workspace.id)
        except Exception as e:
            logger.warning(f"Readiness bulk calculation failed (non-fatal): {e}")

    # ── Summary strip ─────────────────────────────────────────────────────
    summary = {
        "connected_repositories": 0,
        "selected_repositories": 0,
        "ready_repositories": 0,
        "needs_test_history": 0,
        "sync_issues": 0,
    }

    if workspace:
        try:
            summary_query = db.query(Repository).filter(
                Repository.workspace_id == workspace.id,
                Repository.is_active == True
            )
            if not is_demo_mode:
                from sqlalchemy import or_
                summary_query = summary_query.filter(
                    or_(
                        Repository.source == None,  # noqa: E711
                        ~Repository.source.in_(["TEST", "SEED", "DEMO"])
                    )
                )
            all_workspace_repos = summary_query.all()
            summary["connected_repositories"] = len(all_workspace_repos)
            summary["selected_repositories"] = sum(
                1 for r in all_workspace_repos if r.selected_for_analysis
            )

            try:
                summary_readiness = readiness_service.calculate_readiness_bulk(
                    all_workspace_repos, workspace.id
                )
                for r in all_workspace_repos:
                    r_state = "UNKNOWN"
                    if r.id in summary_readiness:
                        r_state = summary_readiness[r.id].readiness_state
                    if r_state in ("READY", "EVIDENCE_READY"):
                        summary["ready_repositories"] += 1
                    elif r_state == "NEEDS_TEST_HISTORY":
                        summary["needs_test_history"] += 1
                    if r.latest_sync_status == "FAILED" or r.sync_error:
                        summary["sync_issues"] += 1
            except Exception as e:
                logger.warning(f"Summary readiness calculation failed (non-fatal): {e}")
                # Fall back: count sync issues without readiness states
                for r in all_workspace_repos:
                    if r.latest_sync_status == "FAILED" or r.sync_error:
                        summary["sync_issues"] += 1

        except Exception as e:
            logger.warning(f"Summary calculation failed (non-fatal): {e}")

    # ── Build payload ─────────────────────────────────────────────────────
    repositories_payload = []
    for repo in repositories:
        readiness_state = "UNKNOWN"
        readiness_reasons = []
        next_action = None
        if repo.id in readiness_results:
            res = readiness_results[repo.id]
            readiness_state = res.readiness_state
            readiness_reasons = res.readiness_reasons
            next_action = res.next_action

        unknown_status_reason = None
        if readiness_state == "UNKNOWN" and readiness_reasons:
            unknown_status_reason = readiness_reasons[0]

        repositories_payload.append({
            "id": str(repo.id),
            "workspace_id": str(repo.workspace_id),
            "github_repo_id": repo.github_repo_id,
            "installation_id": repo.installation_id,
            "owner": repo.owner,
            "name": repo.name,
            "full_name": repo.full_name,
            "default_branch": repo.default_branch or "main",
            "visibility": repo.visibility or "UNKNOWN",
            "is_active": repo.is_active,
            "selected_for_analysis": repo.selected_for_analysis,
            "last_synced_at": _utc_iso(repo.last_synced_at),
            "last_webhook_at": _utc_iso(repo.last_webhook_at),
            "latest_pr_synced_at": _utc_iso(repo.latest_pr_synced_at),
            "latest_sync_status": repo.latest_sync_status or "UNKNOWN",
            "sync_error": repo.sync_error,
            "active_pr_count": active_pr_counts.get(repo.id, 0),
            "prs_analyzed_count": prs_analyzed_counts.get(repo.id, 0),
            "test_runs_count": test_runs_counts.get(repo.id, 0),
            "coverage_reports_count": coverage_counts.get(repo.id, 0),
            "recommendations_count": recommendation_counts.get(repo.id, 0),
            "readiness_state": readiness_state,
            "readiness_reasons": readiness_reasons,
            "next_action": next_action,
            "unknown_status_reason": unknown_status_reason,
        })

    return {
        "repositories": repositories_payload,
        "summary": summary,
    }


@router.post("/repositories/select", dependencies=[Depends(require_workspace_member())])
def select_repositories(
    request: RepositorySelectionRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Update repository selection for the current workspace.
    
    Sets selected_for_analysis for user-selected repositories.
    is_active is managed by the sync service based on GitHub availability.
    """
    # Mark selected repositories as selected_for_analysis
    selected_ids = []
    for rid in request.repository_ids:
        try:
            selected_ids.append(UUID(rid))
        except ValueError as e:
            logger.error(f"Invalid UUID in repository_ids: {rid} - {e}")
    
    # Update selected repos
    db.query(Repository).filter(
        Repository.workspace_id == workspace.id,
        Repository.id.in_(selected_ids)
    ).update({"selected_for_analysis": True}, synchronize_session=False)
    
    # Update unselected repos
    db.query(Repository).filter(
        Repository.workspace_id == workspace.id,
        ~Repository.id.in_(selected_ids)
    ).update({"selected_for_analysis": False}, synchronize_session=False)
    
    db.commit()
    
    return {"status": "success", "selected_count": len(selected_ids)}


@router.post("/repositories/{repository_id}/sync", dependencies=[Depends(require_workspace_member())])
def sync_repository(
    repository_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Trigger a resync for a specific repository. Workspace-scoped and idempotent.

    Fetches fresh repository metadata from GitHub and updates:
    - default_branch
    - visibility
    - owner, name, full_name
    - latest_sync_status (SUCCESS or FAILED)
    - last_synced_at
    - sync_error (cleared on success, set on failure)
    - is_active (set to True if repo exists on GitHub, False if 404)

    Preserves:
    - selected_for_analysis (never overwritten)
    """
    from app.services.github_api_client import GitHubClientError, GitHubNotFoundError, GitHubAuthPermissionError

    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace")

    # 2. Confirm GitHub installation exists for workspace
    installation = db.query(GitHubInstallation).filter(
        GitHubInstallation.workspace_id == workspace.id
    ).first()

    if not installation:
        repo.latest_sync_status = "FAILED"
        repo.sync_error = "No GitHub installation found for workspace"
        repo.last_synced_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=400, detail="No GitHub installation found for workspace")

    # 3. Parse repository owner/name from full_name
    try:
        owner, repo_name = repo.full_name.split("/", 1)
    except ValueError:
        repo.latest_sync_status = "FAILED"
        repo.sync_error = f"Invalid repository full_name format: {repo.full_name}"
        repo.last_synced_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid repository full_name format")

    # 4. Fetch repository metadata from GitHub
    service = GitHubAppService(db)
    now = datetime.utcnow()

    try:
        github_repo_data = service.client.get_repository(
            installation_id=installation.github_installation_id,
            owner=owner,
            repo=repo_name
        )

        # 5. Extract and normalize fields
        raw_visibility = github_repo_data.get("visibility") or ("private" if github_repo_data.get("private") else "public")
        visibility = raw_visibility.upper() if raw_visibility.upper() in ("PUBLIC", "PRIVATE", "INTERNAL") else "UNKNOWN"
        new_owner = (github_repo_data.get("owner") or {}).get("login") or owner
        new_name = github_repo_data.get("name", repo_name)
        new_full_name = github_repo_data.get("full_name", repo.full_name)
        new_default_branch = github_repo_data.get("default_branch") or "main"

        # 6. Update repository (preserving selected_for_analysis)
        repo.owner = new_owner
        repo.name = new_name
        repo.full_name = new_full_name
        repo.default_branch = new_default_branch
        repo.visibility = visibility
        repo.last_synced_at = now
        repo.latest_sync_status = "SUCCESS"
        repo.sync_error = None
        repo.last_seen_in_github_at = now

        # Keep is_active True if sync succeeded (repository exists on GitHub)
        if not repo.is_active:
            repo.is_active = True
            repo.deactivation_reason = None

        db.commit()

        # Recalculate readiness after successful sync
        readiness_service = RepositoryReadinessService(db)
        readiness_service.calculate_readiness(repo.id, repo.workspace_id)

        logger.info(f"Repository sync succeeded: {repo.full_name} (id={repo.id})")

        return {
            "status": "success",
            "message": "Repository sync completed",
            "repository_id": str(repo.id),
            "full_name": repo.full_name,
            "latest_sync_status": repo.latest_sync_status,
            "last_synced_at": _utc_iso(repo.last_synced_at)
        }

    except GitHubNotFoundError as e:
        error_msg = f"Repository not found on GitHub: {e}"
        logger.warning(f"Sync failed for repo {repo.id}: {error_msg}")
        repo.latest_sync_status = "FAILED"
        repo.sync_error = error_msg[:500]
        repo.last_synced_at = now
        repo.is_active = False  # Repository no longer exists on GitHub
        repo.deactivation_reason = "REMOVED_FROM_GITHUB"
        db.commit()
        
        # Recalculate readiness after failed sync
        readiness_service = RepositoryReadinessService(db)
        readiness_service.calculate_readiness(repo.id, repo.workspace_id)
        
        raise HTTPException(status_code=404, detail=error_msg)

    except GitHubAuthPermissionError as e:
        error_msg = f"GitHub permission denied: {e}"
        logger.error(f"Sync failed for repo {repo.id}: {error_msg}")
        repo.latest_sync_status = "FAILED"
        repo.sync_error = error_msg[:500]
        repo.last_synced_at = now
        db.commit()
        
        # Recalculate readiness after failed sync
        readiness_service = RepositoryReadinessService(db)
        readiness_service.calculate_readiness(repo.id, repo.workspace_id)
        
        raise HTTPException(status_code=403, detail=error_msg)

    except GitHubClientError as e:
        error_msg = f"GitHub API error: {e}"
        logger.error(f"Sync failed for repo {repo.id}: {error_msg}")
        repo.latest_sync_status = "FAILED"
        repo.sync_error = error_msg[:500]
        repo.last_synced_at = now
        db.commit()
        
        # Recalculate readiness after failed sync
        readiness_service = RepositoryReadinessService(db)
        readiness_service.calculate_readiness(repo.id, repo.workspace_id)
        
        raise HTTPException(status_code=502, detail=error_msg)

    except Exception as e:
        error_msg = f"Unexpected sync error: {str(e)}"
        logger.exception(f"Sync failed for repo {repo.id}: {error_msg}")
        repo.latest_sync_status = "FAILED"
        repo.sync_error = error_msg[:500]
        repo.last_synced_at = now
        db.commit()
        
        # Recalculate readiness after failed sync
        readiness_service = RepositoryReadinessService(db)
        readiness_service.calculate_readiness(repo.id, repo.workspace_id)
        
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/repositories/{repository_id}/enable", dependencies=[Depends(require_workspace_member())])
def enable_repository(
    repository_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Enable a repository for analysis. Workspace-scoped and idempotent.
    
    Sets selected_for_analysis=true. is_active is managed by the sync service
    based on GitHub availability and is not modified here.
    """
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace")
    
    # Idempotent: only update if not already enabled
    if not repo.selected_for_analysis:
        repo.selected_for_analysis = True
        repo.updated_at = datetime.utcnow()
        db.commit()
    
    return {"status": "success", "selected_for_analysis": repo.selected_for_analysis}


@router.post("/repositories/{repository_id}/test-history/upload", dependencies=[Depends(require_workspace_member())])
async def upload_test_history(
    repository_id: UUID,
    file: UploadFile = File(...),
    commit_sha: Optional[str] = Form(None),
    branch: Optional[str] = Form(None),
    run_name: Optional[str] = Form(None),
    source: str = Form("MANUAL_UPLOAD"),
    import_mode: Optional[str] = Form("BOTH"),
    pull_request_id: Optional[UUID] = Form(None),
    head_sha: Optional[str] = Form(None),
    source_context: Optional[str] = Form(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Upload JUnit XML test results for a specific repository.
    
    Workspace-scoped. Verifies repository belongs to workspace and is enabled for analysis.
    """
    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace")
    
    # 2. Verify repository is selected for analysis
    if not repo.selected_for_analysis:
        raise HTTPException(
            status_code=400, 
            detail="Repository is not enabled for analysis. Enable the repository before uploading test history."
        )
    
    # 3. Read file bytes
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read upload file: {str(e)}"
        )
    
    # Resolve PR commit / branch details
    resolved_commit_sha = commit_sha or head_sha
    if pull_request_id:
        resolved_pr = db.query(PullRequest).filter(
            PullRequest.id == pull_request_id,
            PullRequest.repository_id == repository_id
        ).first()
        if resolved_pr:
            if not resolved_commit_sha:
                resolved_commit_sha = resolved_pr.head_commit_sha
            if not branch:
                branch = resolved_pr.source_branch

    # 4. Ingest using TestIngestionService
    ingestion_service = TestIngestionService(db)
    
    try:
        test_run, duplicate_coalesced = ingestion_service.ingest_junit_xml(
            file_bytes=file_bytes,
            filename=file.filename or "junit.xml",
            repository_id=repository_id,
            commit_sha=resolved_commit_sha,
            pull_request_id=pull_request_id,
            ingestion_reason="MANUAL_UPLOAD",
            request_origin=source,
            branch=branch,
            run_name=run_name,
            source_context=source_context,
            import_mode=import_mode or "BOTH"
        )
    except OversizedXMLException as e:
        raise HTTPException(
            status_code=413,
            detail=str(e)
        )
    except XMLParsingError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JUnit XML: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"JUnit ingestion failed for repository {repository_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}"
        )
    
    # 5. Recalculate repository readiness after successful upload
    readiness_service = RepositoryReadinessService(db)
    readiness = readiness_service.calculate_readiness(repository_id, workspace.id)
    
    from app.services.input_readiness_v2_service import InputReadinessV2Service
    v2_service = InputReadinessV2Service(db)
    strict_12_readiness = v2_service.assess(
        repository_id=str(repository_id),
        pull_request_id=str(pull_request_id) if pull_request_id else None
    )
    strict_12_dict = strict_12_readiness.model_dump() if hasattr(strict_12_readiness, "model_dump") else (strict_12_readiness.dict() if hasattr(strict_12_readiness, "dict") else strict_12_readiness)
    
    legacy_repo_readiness = {
        "readiness_state": readiness.readiness_state,
        "readiness_reasons": readiness.readiness_reasons,
        "next_action": readiness.next_action
    }
    
    readiness_summary = {
        "repository_id": str(repository_id),
        "pull_request_id": str(pull_request_id) if pull_request_id else None,
        "generation_status": strict_12_dict.get("generation_status"),
        "can_generate_draft": strict_12_dict.get("can_generate_draft"),
        "can_generate_confident": strict_12_dict.get("can_generate_confident"),
        "confidence_score": strict_12_dict.get("confidence_score"),
        "confidence_level": strict_12_dict.get("confidence_level"),
        "confidence_ceiling": strict_12_dict.get("confidence_ceiling"),
        "primary_message": strict_12_dict.get("primary_message"),
        "primary_reason": strict_12_dict.get("primary_reason"),
        "blocking_inputs": strict_12_dict.get("blocking_inputs"),
        "partial_inputs": strict_12_dict.get("partial_inputs"),
        "review_needed_inputs": strict_12_dict.get("review_needed_inputs"),
        "missing_confidence_boosters": strict_12_dict.get("missing_confidence_boosters"),
        "next_best_actions": strict_12_dict.get("next_best_actions"),
        "warnings": strict_12_dict.get("warnings"),
        "blockers": strict_12_dict.get("blockers")
    }

    if import_mode == "INVENTORY_ONLY" or test_run is None:
        return {
            "import_mode": "INVENTORY_ONLY",
            "test_run_id": None,
            "status": "INVENTORY_UPDATED",
            "message": "Test case inventory updated successfully",
            "duplicate_coalesced": duplicate_coalesced,
            "legacy_repository_readiness": legacy_repo_readiness,
            "strict_12_input_readiness": strict_12_dict,
            "readiness_summary": readiness_summary
        }

    return {
        "test_run_id": str(test_run.id),
        "tests_total": test_run.total_tests,
        "tests_passed": test_run.passed_tests,
        "tests_failed": test_run.failed_tests,
        "tests_skipped": test_run.skipped_tests,
        "duration_seconds": test_run.duration,
        "parser_version": test_run.parser_version,
        "normalization_schema_version": test_run.normalization_schema_version,
        "evidence_health_status": test_run.evidence_health_status,
        "duplicate_coalesced": duplicate_coalesced,
        "legacy_repository_readiness": legacy_repo_readiness,
        "strict_12_input_readiness": strict_12_dict,
        "repository_readiness": {
            "readiness_state": strict_12_dict.get("generation_status"),
            "readiness_reasons": [b.get("message") for b in strict_12_dict.get("blockers", [])] + [w.get("message") for w in strict_12_dict.get("warnings", [])],
            "next_action": strict_12_dict.get("next_best_actions")[0].get("label") if strict_12_dict.get("next_best_actions") else "None"
        },
        "readiness_summary": readiness_summary
    }


@router.get("/repositories/{repository_id}/test-history/summary", dependencies=[Depends(require_workspace_member())])
def get_test_history_summary(
    repository_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get test history summary for a specific repository.
    
    Workspace-scoped. Returns persisted test run counts and latest test run details.
    """
    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace")
    
    # 2. Count test runs and results
    test_runs_count = (
        db.query(func.count(TestRun.id))
        .filter(TestRun.repository_id == repository_id)
        .scalar() or 0
    )
    
    test_results_count = (
        db.query(func.count(TestResult.id))
        .join(TestRun, TestResult.test_run_id == TestRun.id)
        .filter(TestRun.repository_id == repository_id)
        .scalar() or 0
    )
    
    # 3. Get latest test run
    latest_test_run = (
        db.query(TestRun)
        .filter(TestRun.repository_id == repository_id)
        .order_by(TestRun.created_at.desc())
        .first()
    )
    
    latest_test_run_at = _utc_iso(latest_test_run.created_at) if latest_test_run else None
    
    latest_test_run_data = None
    if latest_test_run:
        latest_test_run_data = {
            "id": str(latest_test_run.id),
            "run_name": latest_test_run.ingestion_reason,
            "commit_sha": latest_test_run.commit_sha,
            "branch": None,  # Not stored in TestRun model currently
            "tests_total": latest_test_run.total_tests,
            "tests_passed": latest_test_run.passed_tests,
            "tests_failed": latest_test_run.failed_tests,
            "tests_skipped": latest_test_run.skipped_tests,
            "duration_seconds": latest_test_run.duration,
            "evidence_health_status": latest_test_run.evidence_health_status
        }
    
    return {
        "repository_id": str(repository_id),
        "test_runs_count": test_runs_count,
        "test_results_count": test_results_count,
        "latest_test_run_at": latest_test_run_at,
        "latest_test_run": latest_test_run_data
    }


@router.get("/repositories/{repository_id}")
def get_repository_detail(
    repository_id: UUID,
    workspace: Optional[Workspace] = Depends(optional_workspace),
    db: Session = Depends(get_db)
):
    """Get detailed repository information including metadata, readiness, evidence counts, and health status.
    
    Workspace-scoped if workspace provided. Returns 404 if repository not found.
    For development, allows access without workspace.
    """
    from app.services.repository_readiness import RepositoryReadinessService
    
    if workspace:
        repo = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.workspace_id == workspace.id
        ).first()
        
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found in workspace")
    else:
        # Development mode: allow without workspace
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
    
    # Calculate readiness
    from app.services.repository_readiness import RepositoryReadinessService, RepositoryReadinessResult
    readiness_service = RepositoryReadinessService(db)
    if workspace:
        readiness = readiness_service.calculate_readiness(repository_id, workspace.id)
    else:
        # Development mode: skip workspace-scoped readiness
        readiness = RepositoryReadinessResult.make("READY", [])
    
    # Fetch evidence counts
    pull_requests_count = (
        db.query(func.count(PullRequest.id))
        .filter(PullRequest.repository_id == repository_id)
        .scalar() or 0
    )
    active_pull_requests_count = (
        db.query(func.count(PullRequest.id))
        .filter(
            PullRequest.repository_id == repository_id,
            PullRequest.state == "open"
        )
        .scalar() or 0
    )
    test_runs_count = (
        db.query(func.count(TestRun.id))
        .filter(TestRun.repository_id == repository_id)
        .scalar() or 0
    )
    test_results_count = (
        db.query(func.count(TestRun.id))
        .filter(TestRun.repository_id == repository_id)
        .scalar() or 0
    )
    coverage_reports_count = (
        db.query(func.count(CoverageReport.id))
        .filter(CoverageReport.repository_id == repository_id)
        .scalar() or 0
    )
    recommendations_count = (
        db.query(func.count(RecommendationRun.id))
        .filter(RecommendationRun.repository_id == repository_id)
        .scalar() or 0
    )
    fragility_patterns_count = 0  # TODO: implement fragility pattern counting

    # Use repository's latest_pr_synced_at (updated by sync endpoint)
    latest_pr_synced_at = _utc_iso(repo.latest_pr_synced_at)

    # Determine PR sync status
    if repo.latest_pr_synced_at is None:
        pr_sync_status = "NEVER_SYNCED"
    elif repo.sync_error is not None and repo.latest_sync_status == "FAILED":
        pr_sync_status = "FAILED"
    else:
        pr_sync_status = "SYNCED"

    # Calculate health status
    github_connection = "CONNECTED" if repo.installation_id else "DISCONNECTED"
    webhook_status = _get_webhook_status(repo.last_webhook_at)
    test_history_status = "PRESENT" if test_runs_count > 0 else "MISSING"
    coverage_status = "PRESENT" if coverage_reports_count > 0 else "MISSING"
    recommendation_status = "READY" if readiness.readiness_state == "READY" else "NOT_READY"
    
    return {
        "id": str(repo.id),
        "full_name": repo.full_name,
        "owner": repo.owner,
        "name": repo.name,
        "visibility": repo.visibility,
        "default_branch": repo.default_branch,
        "is_active": repo.is_active,
        "selected_for_analysis": repo.selected_for_analysis,
        # Explicit, distinct timestamps — do not conflate these
        "last_synced_at": _utc_iso(repo.last_synced_at),
        "last_webhook_at": _utc_iso(repo.last_webhook_at),
        "latest_pr_synced_at": latest_pr_synced_at,
        "latest_sync_status": repo.latest_sync_status,
        "sync_error": repo.sync_error,
        "pr_sync_status": pr_sync_status,

        "readiness_state": readiness.readiness_state,
        "readiness_reasons": readiness.readiness_reasons,
        "next_action": readiness.next_action,

        "evidence": {
            "pull_requests_count": pull_requests_count,
            "active_pull_requests_count": active_pull_requests_count,
            "test_runs_count": test_runs_count,
            "test_results_count": test_results_count,
            "coverage_reports_count": coverage_reports_count,
            "recommendations_count": recommendations_count,
            "fragility_patterns_count": fragility_patterns_count,
        },

        "health": {
            "github_connection": github_connection,
            "webhook_status": webhook_status,
            "test_history_status": test_history_status,
            "coverage_status": coverage_status,
            "recommendation_status": recommendation_status,
        },
    }


@router.post("/repositories/{repository_id}/disable", dependencies=[Depends(require_workspace_member())])
def disable_repository(
    repository_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Disable a repository from analysis. Workspace-scoped and idempotent.
    
    Sets selected_for_analysis=false only. Historical evidence
    (test runs, coverage, recommendations) is preserved. Repository remains
    installed from GitHub and can be re-enabled later.
    """
    from app.services.repository_readiness import RepositoryReadinessService
    
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace")
    
    # Idempotent: only update if not already disabled
    if repo.selected_for_analysis:
        repo.selected_for_analysis = False
        repo.updated_at = datetime.utcnow()
        db.commit()
    
    # Recalculate readiness for this repository
    readiness_service = RepositoryReadinessService(db)
    readiness = readiness_service.calculate_readiness(repository_id, workspace.id)
    
    # Fetch counts for the response (evidence remains intact)
    active_pr_count = (
        db.query(func.count(PullRequest.id))
        .filter(PullRequest.repository_id == repository_id)
        .scalar() or 0
    )
    prs_analyzed_count = (
        db.query(func.count(PullRequest.id))
        .filter(
            PullRequest.repository_id == repository_id,
            PullRequest.sync_integrity_status == "FULL_SUCCESS"
        )
        .scalar() or 0
    )
    test_runs_count = (
        db.query(func.count(TestRun.id))
        .filter(TestRun.repository_id == repository_id)
        .scalar() or 0
    )
    coverage_reports_count = (
        db.query(func.count(CoverageReport.id))
        .filter(CoverageReport.repository_id == repository_id)
        .scalar() or 0
    )
    recommendations_count = (
        db.query(func.count(RecommendationRun.id))
        .filter(RecommendationRun.repository_id == repository_id)
        .scalar() or 0
    )
    
    # Return full repository response matching GET /github/repositories contract
    return {
        "id": str(repo.id),
        "workspace_id": str(repo.workspace_id),
        "github_repo_id": repo.github_repo_id,
        "installation_id": repo.installation_id,
        "owner": repo.owner,
        "name": repo.name,
        "full_name": repo.full_name,
        "default_branch": repo.default_branch,
        "visibility": repo.visibility,
        "is_active": repo.is_active,
        "selected_for_analysis": repo.selected_for_analysis,
        "last_synced_at": _utc_iso(repo.last_synced_at),
        "last_webhook_at": _utc_iso(repo.last_webhook_at),
        "webhook_status": _get_webhook_status(repo.last_webhook_at),
        "latest_sync_status": repo.latest_sync_status,
        "sync_error": repo.sync_error,
        "created_at": _utc_iso(repo.created_at),
        "updated_at": _utc_iso(repo.updated_at),
        "active_pr_count": active_pr_count,
        "prs_analyzed_count": prs_analyzed_count,
        "test_runs_count": test_runs_count,
        "coverage_reports_count": coverage_reports_count,
        "recommendations_count": recommendations_count,
        "readiness_state": readiness.readiness_state,
        "readiness_reasons": readiness.readiness_reasons,
        "next_action": readiness.next_action,
    }


@router.post("/repositories/{repository_id}/test-history/upload", dependencies=[Depends(require_workspace_member())])
async def upload_test_history(
    repository_id: UUID,
    file: UploadFile = File(...),
    commit_sha: Optional[str] = Form(None),
    branch: Optional[str] = Form(None),
    run_name: Optional[str] = Form(None),
    source: str = Form("MANUAL_UPLOAD"),
    import_mode: Optional[str] = Form("BOTH"),
    pull_request_id: Optional[UUID] = Form(None),
    head_sha: Optional[str] = Form(None),
    source_context: Optional[str] = Form(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Upload JUnit XML test results for a repository. Workspace-scoped.
    
    Requires repository to be selected_for_analysis. Preserves raw artifact,
    runs JUnit ingestion pipeline, and returns ingestion summary.
    """
    # Verify repository belongs to workspace and is enabled
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace")
    
    if not repo.selected_for_analysis:
        raise HTTPException(
            status_code=400, 
            detail="Repository must be enabled for analysis before uploading test results"
        )
    
    # Fast pre-reading size check
    max_bytes = settings.MAX_JUNIT_XML_SIZE_MB * 1024 * 1024
    if file.size and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Payload too large: JUnit XML size exceeding limit of {settings.MAX_JUNIT_XML_SIZE_MB} MB."
        )
    
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read upload file stream: {str(e)}"
        )
    
    # Resolve PR commit / branch details
    resolved_commit_sha = commit_sha or head_sha
    if pull_request_id:
        resolved_pr = db.query(PullRequest).filter(
            PullRequest.id == pull_request_id,
            PullRequest.repository_id == repository_id
        ).first()
        if resolved_pr:
            if not resolved_commit_sha:
                resolved_commit_sha = resolved_pr.head_commit_sha
            if not branch:
                branch = resolved_pr.source_branch

    ingestion_service = TestIngestionService(db)
    
    try:
        test_run, duplicate_coalesced = ingestion_service.ingest_junit_xml(
            file_bytes=file_bytes,
            filename=file.filename or "junit.xml",
            repository_id=repository_id,
            commit_sha=resolved_commit_sha,
            pull_request_id=pull_request_id,
            ingestion_reason="ORIGINAL_UPLOAD",
            request_origin=source,
            branch=branch,
            source_context=source_context,
            import_mode=import_mode or "BOTH"
        )
    except OversizedXMLException as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e)
        )
    except XMLParsingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"JUnit ingestion failed for repository {repository_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion pipeline failure: {str(e)}"
        )
    
    # Recalculate readiness after test upload
    readiness_service = RepositoryReadinessService(db)
    readiness = readiness_service.calculate_readiness(repository_id, workspace.id)

    from app.services.recommendation_readiness_service import RecommendationReadinessService
    rec_readiness_svc = RecommendationReadinessService(db)
    latest_assessment = rec_readiness_svc.assess_readiness(
        repository_id=repository_id,
        pull_request_id=pull_request_id
    )
    readiness_summary = {
        "repository_id": str(latest_assessment.repository_id),
        "pull_request_id": str(latest_assessment.pull_request_id) if latest_assessment.pull_request_id else None,
        "readiness_level": latest_assessment.readiness_level,
        "expected_confidence": latest_assessment.expected_confidence,
        "readiness_score": latest_assessment.readiness_score,
        "can_generate": latest_assessment.can_generate,
        "can_generate_reason": latest_assessment.can_generate_reason,
        "signal_count": len(latest_assessment.available_signals),
        "total_signals": 15,
        "intelligence_completeness_score": latest_assessment.intelligence_completeness_score,
        "release_confidence_ceiling": latest_assessment.release_confidence_ceiling,
        "available_inputs": latest_assessment.available_inputs,
        "missing_inputs": latest_assessment.missing_inputs,
        "recommended_inputs": latest_assessment.recommended_inputs,
        "blocking_inputs": latest_assessment.blocking_inputs,
        "next_best_actions": latest_assessment.next_best_actions,
        "primary_message": latest_assessment.primary_message,
        "secondary_message": latest_assessment.secondary_message,
        "confidence_reason": latest_assessment.confidence_reason,
        "confidence_ceiling": latest_assessment.confidence_ceiling,
        "confidence_blockers": latest_assessment.confidence_blockers,
        "confidence_limiters": latest_assessment.confidence_limiters
    }
    
    # For INVENTORY_ONLY mode, test_run is None; return inventory update status
    if import_mode == "INVENTORY_ONLY" or test_run is None:
        return {
            "import_mode": "INVENTORY_ONLY",
            "test_run_id": None,
            "status": "INVENTORY_UPDATED",
            "message": "Test case inventory updated successfully",
            "duplicate_coalesced": duplicate_coalesced,
            "readiness_summary": readiness_summary
        }

    return {
        "test_run_id": str(test_run.id),
        "tests_total": test_run.total_tests,
        "tests_passed": test_run.passed_tests,
        "tests_failed": test_run.failed_tests,
        "tests_skipped": test_run.skipped_tests,
        "parser_version": test_run.parser_version,
        "normalization_version": test_run.normalization_schema_version,
        "evidence_health_status": test_run.evidence_health_status,
        "duplicate_coalesced": duplicate_coalesced,
        "readiness_summary": readiness_summary
    }


@router.get("/repositories/{repository_id}/webhook-status", dependencies=[Depends(require_workspace_member())])
def get_webhook_status(
    repository_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get webhook status and recent events for a repository. Workspace-scoped."""
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace")
    
    # Determine webhook status
    webhook_status = _get_webhook_status(repo.last_webhook_at)
    
    # Get recent webhook events for this repository
    recent_events = (
        db.query(WebhookEvent)
        .filter(WebhookEvent.repository_id == repo.github_repo_id)
        .order_by(WebhookEvent.received_at.desc())
        .limit(10)
        .all()
    )
    
    events_data = []
    for event in recent_events:
        events_data.append({
            "event_type": event.event_type,
            "action": event.action,
            "received_at": _utc_iso(event.received_at),
            "processing_status": event.processing_status
        })
    
    return {
        "webhook_status": webhook_status,
        "last_webhook_at": _utc_iso(repo.last_webhook_at),
        "recent_events": events_data
    }


@router.get("/repositories/{repository_id}/pull-requests")
def get_pull_requests(
    repository_id: UUID,
    workspace: Optional[Workspace] = Depends(optional_workspace),
    db: Session = Depends(get_db)
):
    """Get pull requests for a repository.
    
    Workspace-scoped if workspace provided. For development, allows access without workspace.
    """
    if workspace:
        repo = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.workspace_id == workspace.id
        ).first()
        
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found in workspace")
    else:
        # Development mode: allow without workspace
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get pull requests for this repository
    pull_requests = (
        db.query(PullRequest)
        .filter(PullRequest.repository_id == repository_id)
        .order_by(PullRequest.github_updated_at.desc())
        .all()
    )
    
    prs_data = []
    for pr in pull_requests:
        # Check if there's a recommendation run for this PR
        recommendation_run = (
            db.query(RecommendationRun)
            .filter(RecommendationRun.pull_request_id == pr.id)
            .order_by(RecommendationRun.created_at.desc())
            .first()
        )
        
        prs_data.append({
            "id": str(pr.id),
            "number": pr.number,
            "title": pr.title,
            "author": pr.author,
            "source_branch": pr.source_branch,
            "target_branch": pr.target_branch,
            "state": pr.state,
            "head_commit_sha": pr.head_commit_sha,
            "base_commit_sha": getattr(pr, "base_commit_sha", None),
            "merge_commit_sha": getattr(pr, "merge_commit_sha", None),
            "changed_files_count": pr.changed_files_count,
            "last_synced_at": _utc_iso(pr.last_sync_completed_at),
            "sync_status": pr.sync_integrity_status,
            "recommendation_status": "GENERATED" if recommendation_run else "NOT_RUN",
            "latest_recommendation_run_id": str(recommendation_run.id) if recommendation_run else None,
            "latest_recommendation_at": _utc_iso(recommendation_run.created_at) if recommendation_run else None
        })
    
    return {
        "pull_requests": prs_data
    }


@router.get("/repositories/{repository_id}/learning-summary", dependencies=[Depends(require_workspace_member())])
def get_learning_summary(
    repository_id: UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get repository-level learning summary. Workspace-scoped."""
    from app.models.recommendation import (
        RecommendationOutcome, RecommendationTestOutcome, SuggestedScenarioOutcome,
        RecommendationOverride
    )
    from app.models.pattern_memory_v2 import PatternMemoryV2
    from app.models.behavior import Behavior
    from app.schemas.recommendation import LearningSummary, LearnedPattern, BehaviorLearningSignal
    from sqlalchemy import func
    
    # Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace")
    
    # Count total outcomes
    total_outcomes = db.query(RecommendationOutcome).filter(
        RecommendationOutcome.repository_id == repository_id
    ).count()
    
    # Count feedback types
    useful_feedback_count = db.query(RecommendationOutcome).filter(
        RecommendationOutcome.repository_id == repository_id,
        RecommendationOutcome.user_feedback == "USEFUL"
    ).count()
    
    missing_tests_feedback_count = db.query(RecommendationOutcome).filter(
        RecommendationOutcome.repository_id == repository_id,
        RecommendationOutcome.user_feedback == "MISSING_TESTS"
    ).count()
    
    # Count manually added tests
    manually_added_tests_count = db.query(RecommendationOverride).filter(
        RecommendationOverride.repository_id == repository_id,
        RecommendationOverride.override_type == "ADDED"
    ).count()
    
    # Count removed tests
    removed_tests_count = db.query(RecommendationTestOutcome).filter(
        RecommendationTestOutcome.repository_id == repository_id,
        RecommendationTestOutcome.engineer_decision == "REMOVED"
    ).count()
    
    # Count accepted scenarios
    accepted_scenarios_count = db.query(SuggestedScenarioOutcome).filter(
        SuggestedScenarioOutcome.repository_id == repository_id,
        SuggestedScenarioOutcome.engineer_decision == "ACCEPTED"
    ).count()
    
    # Count escaped defects
    escaped_defects_count = db.query(RecommendationOutcome).filter(
        RecommendationOutcome.repository_id == repository_id,
        RecommendationOutcome.escaped_defect == True
    ).count()
    
    # Count rollbacks
    rollback_count = db.query(RecommendationOutcome).filter(
        RecommendationOutcome.repository_id == repository_id,
        RecommendationOutcome.rollback_occurred == True
    ).count()
    
    # Get top learned patterns
    top_patterns = db.query(PatternMemoryV2).filter(
        PatternMemoryV2.repository_id == repository_id
    ).order_by(PatternMemoryV2.usage_count.desc()).limit(10).all()
    
    top_learned_patterns = [
        LearnedPattern(
            pattern_key=pm.pattern_key,
            signal_type=pm.signal_type,
            strength=pm.strength,
            confidence=pm.confidence,
            usage_count=pm.usage_count
        )
        for pm in top_patterns
    ]
    
    # Get behaviors with most learning signals
    behavior_signals = db.query(
        PatternMemoryV2.behavior_id,
        func.count(PatternMemoryV2.id).label("signal_count"),
        func.max(PatternMemoryV2.last_seen_at).label("last_seen_at")
    ).filter(
        PatternMemoryV2.repository_id == repository_id,
        PatternMemoryV2.behavior_id.isnot(None)
    ).group_by(PatternMemoryV2.behavior_id).order_by(
        func.count(PatternMemoryV2.id).desc()
    ).limit(10).all()
    
    behaviors_with_most_signals = []
    for behavior_id, signal_count, last_seen_at in behavior_signals:
        behavior = db.query(Behavior).filter(Behavior.id == behavior_id).first()
        if behavior:
            behaviors_with_most_signals.append(
                BehaviorLearningSignal(
                    behavior_id=str(behavior_id),
                    behavior_name=behavior.name,
                    signal_count=signal_count,
                    last_seen_at=last_seen_at
                )
            )
    
    return LearningSummary(
        total_outcomes=total_outcomes,
        useful_feedback_count=useful_feedback_count,
        missing_tests_feedback_count=missing_tests_feedback_count,
        manually_added_tests_count=manually_added_tests_count,
        removed_tests_count=removed_tests_count,
        accepted_scenarios_count=accepted_scenarios_count,
        escaped_defects_count=escaped_defects_count,
        rollback_count=rollback_count,
        top_learned_patterns=top_learned_patterns,
        behaviors_with_most_signals=behaviors_with_most_signals
    )


@router.post("/repositories/{repository_id}/pull-requests/sync")
def sync_pull_requests(
    repository_id: UUID,
    workspace: Optional[Workspace] = Depends(optional_workspace),
    db: Session = Depends(get_db)
):
    """Manually sync open pull requests from GitHub for a repository.

    Fetches all open PRs via the GitHub API, upserts them, and fetches changed
    files for each. Does not depend on webhooks — safe to call at any time.
    Workspace-scoped if workspace provided. For development, allows access without workspace.
    """
    from fastapi.responses import JSONResponse
    from app.services.github_api_client import GitHubNotFoundError, GitHubAuthPermissionError, GitHubRateLimitExceededError

    # 1. Verify repository exists
    if workspace:
        repo = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.workspace_id == workspace.id
        ).first()
        if not repo:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error_code": "REPOSITORY_NOT_FOUND",
                    "message": "Repository not found in your active workspace.",
                    "action": "Select a valid repository"
                }
            )
    else:
        # Development mode: allow without workspace
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error_code": "REPOSITORY_NOT_FOUND",
                    "message": "Repository not found.",
                    "action": "Select a valid repository"
                }
            )

    if not repo.is_active:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error_code": "REPOSITORY_NOT_CONNECTED",
                "message": "Repository is inactive.",
                "action": "Reconnect Repository"
            }
        )

    try:
        owner, repo_name = repo.full_name.split("/", 1)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error_code": "INVALID_REPOSITORY_MAPPING",
                "message": "Invalid repository full_name format.",
                "action": "Fix repository mapping"
            }
        )

    # 2. Resolve GitHub installation
    if workspace:
        installation = db.query(GitHubInstallation).filter(
            GitHubInstallation.workspace_id == workspace.id
        ).first()
    else:
        # Development mode: find any installation
        installation = db.query(GitHubInstallation).first()
    
    if not installation:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error_code": "MISSING_GITHUB_INSTALLATION",
                "message": "GitHub App installation is missing. Reconnect GitHub to sync pull requests.",
                "action": "Reconnect GitHub App"
            }
        )

    github_installation_id = installation.github_installation_id
    service = GitHubAppService(db)

    # Backfill repository.installation_id if missing or mismatching
    if not repo.installation_id or repo.installation_id != github_installation_id:
        try:
            # Verify repo is part of installation
            github_repo_data = service.client.get_repository(
                installation_id=github_installation_id,
                owner=owner,
                repo=repo_name
            )
            # Backfill repository installation_id
            repo.installation_id = github_installation_id
            db.commit()
            db.refresh(repo)
        except GitHubNotFoundError:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error_code": "GITHUB_REPOSITORY_NOT_FOUND",
                    "message": "Repository not found on GitHub or not accessible by installation.",
                    "action": "Check repository visibility or permissions"
                }
            )
        except GitHubAuthPermissionError:
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "error_code": "GITHUB_PERMISSION_DENIED",
                    "message": "GitHub App does not have access to this repository.",
                    "action": "Grant repository access to GitHub App"
                }
            )
        except Exception as e:
            return JSONResponse(
                status_code=502,
                content={
                    "success": False,
                    "error_code": "PR_SYNC_FAILED",
                    "message": f"GitHub API verification failed: {str(e)}",
                    "action": "Retry Sync"
                }
            )

    # 3. Fetch open PRs from GitHub
    try:
        open_prs = service.client.list_pull_requests(
            installation_id=github_installation_id,
            owner=owner,
            repo=repo_name,
            state="open"
        )
    except GitHubNotFoundError:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error_code": "GITHUB_REPOSITORY_NOT_FOUND",
                "message": "Repository not found on GitHub or not accessible by installation.",
                "action": "Check repository visibility or permissions"
            }
        )
    except GitHubAuthPermissionError:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error_code": "GITHUB_PERMISSION_DENIED",
                "message": "GitHub App does not have access to this repository.",
                "action": "Grant repository access to GitHub App"
            }
        )
    except GitHubRateLimitExceededError as e:
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error_code": "GITHUB_API_RATE_LIMITED",
                "message": "GitHub API rate limit exceeded. Please try again later.",
                "action": "Wait for rate limit reset"
            }
        )
    except Exception as e:
        logger.error(f"Failed to fetch PRs from GitHub for {repo.full_name}: {e}")
        return JSONResponse(
            status_code=502,
            content={
                "success": False,
                "error_code": "PR_SYNC_FAILED",
                "message": f"Could not sync pull requests. Retry or check GitHub connection. Details: {str(e)}",
                "action": "Retry Sync"
            }
        )

    synced_prs = []
    synced_files_total = 0

    for pr_data in open_prs:
        github_pr_id = pr_data.get("id")
        number = pr_data.get("number")
        title = pr_data.get("title", "No Title")
        author = (pr_data.get("user") or {}).get("login", "unknown")
        source_branch = (pr_data.get("head") or {}).get("ref", "unknown")
        target_branch = (pr_data.get("base") or {}).get("ref", "unknown")
        head_commit_sha = (pr_data.get("head") or {}).get("sha", "")
        state = pr_data.get("state", "open")
        additions = pr_data.get("additions", 0)
        deletions = pr_data.get("deletions", 0)
        changed_files_count = pr_data.get("changed_files", 0)

        gh_created_at_str = pr_data.get("created_at")
        gh_updated_at_str = pr_data.get("updated_at")
        gh_created_at = datetime.fromisoformat(gh_created_at_str.replace("Z", "+00:00")).replace(tzinfo=None) if gh_created_at_str else datetime.utcnow()
        gh_updated_at = datetime.fromisoformat(gh_updated_at_str.replace("Z", "+00:00")).replace(tzinfo=None) if gh_updated_at_str else datetime.utcnow()

        # Skip drafts
        if pr_data.get("draft"):
            continue

        # Upsert PR stub and execute sync synchronously
        try:
            # 1. Retrieve or create PullRequest stub — must scope by repository_id
            # to prevent cross-repository/cross-workspace collision on the same github_pr_id
            pr_record = db.query(PullRequest).filter(
                PullRequest.github_pr_id == github_pr_id,
                PullRequest.repository_id == repo.id
            ).first()
            if not pr_record:
                pr_record = PullRequest(
                    repository_id=repo.id,
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
                    github_created_at=gh_created_at,
                    github_updated_at=gh_updated_at,
                    last_github_updated_at=gh_updated_at,
                    sync_integrity_status="UNKNOWN",
                    evidence_health_status="HEALTHY",
                    evidence_consistency_status="UNKNOWN"
                )
                db.add(pr_record)
                db.commit()
                db.refresh(pr_record)
            else:
                pr_record.title = title
                pr_record.state = state
                pr_record.additions = additions
                pr_record.deletions = deletions
                pr_record.changed_files_count = changed_files_count
                pr_record.head_commit_sha = head_commit_sha
                pr_record.github_updated_at = gh_updated_at
                pr_record.last_github_updated_at = gh_updated_at
                db.commit()

            # 2. Create PullRequestSyncJob row
            sync_job = PullRequestSyncJob(
                pull_request_id=pr_record.id,
                repository_id=repo.id,
                github_installation_id=github_installation_id,
                status="PENDING",
                sync_reason="MANUAL_SYNC",
                started_at=datetime.utcnow(),
                head_commit_sha=head_commit_sha
            )
            db.add(sync_job)
            db.commit()
            db.refresh(sync_job)

            # 3. Execute sync synchronously
            try:
                service.execute_pull_request_sync_job(pr_record.id, github_installation_id, sync_job.id)
                
                # Refresh db session to get updated details
                db.refresh(pr_record)
            except Exception as sync_error:
                logger.error(f"PR sync execution failed for PR #{number}: {sync_error}")
                # Continue to next PR even if sync fails
                continue
        except Exception as e:
            logger.warning(f"PR sync failed for PR #{number}: {e}")
            continue

        # Count changed files now persisted
        files_count = db.query(func.count(PullRequestChangedFile.id)).filter(
            PullRequestChangedFile.pull_request_id == pr_record.id
        ).scalar() or 0
        synced_files_total += files_count

        # Only count as successfully synced if files were actually persisted
        if files_count > 0 or pr_record.sync_integrity_status == "FULL_SUCCESS":
            synced_prs.append({
                "number": number,
                "title": title,
                "state": state.upper(),
                "changed_files_count": files_count,
            })
        else:
            # PR was fetched but sync failed - log this but don't count as synced
            logger.warning(f"PR #{number} fetched but sync failed or incomplete. Files persisted: {files_count}, Sync status: {pr_record.sync_integrity_status}")

    # Close stale open PRs in DB if they are no longer in open_prs from GitHub
    fetched_gh_ids = {pr_data.get("id") for pr_data in open_prs}
    db_stale_open_prs = db.query(PullRequest).filter(
        PullRequest.repository_id == repo.id,
        PullRequest.state == "open"
    ).all()
    for db_pr in db_stale_open_prs:
        if db_pr.github_pr_id not in fetched_gh_ids:
            db_pr.state = "closed"
            db_pr.updated_at = datetime.utcnow()
    db.commit()

    # Update repository's latest_pr_synced_at
    repo.latest_pr_synced_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "synced_pull_requests": len(synced_prs),
        "synced_changed_files": synced_files_total,
        "synced_count": len(synced_prs),
        "open_pr_count": len(synced_prs),
        "latest_pr_synced_at": datetime.utcnow().isoformat() + "Z",
        "pull_requests": synced_prs,
        "error_message": None,
    }


@router.post("/repositories/{repository_id}/pull-requests/{pull_request_id}/recommendation", dependencies=[Depends(require_workspace_member())])
def create_recommendation(
    repository_id: UUID,
    pull_request_id: UUID,
    payload: Optional[RecommendationGeneratePayload] = None,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Dry-run recommendation for a pull request. Workspace-scoped.

    Runs the full recommendation engine against the PR's changed files,
    test history, and coverage evidence. Persists the run and returns a
    structured summary. Does NOT post a GitHub PR comment.

    Repeated calls create a new versioned run each time (idempotent evidence
    collection, new run record per invocation).
    """
    from app.services.recommendation import RecommendationService
    from app.schemas.recommendation import RecommendationRunCreate, RecommendationGeneratePayload
    from app.services.repository_readiness import RepositoryReadinessService

    # 1. Verify repository belongs to workspace
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace")

    # 2. Verify PR belongs to repository
    pr = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found in repository")

    # 3. Verify repository readiness — must be READY or NEEDS_COVERAGE (low-coverage dry run allowed)
    readiness_svc = RepositoryReadinessService(db)
    readiness = readiness_svc.calculate_readiness(repository_id, workspace.id)
    allowed_states = {"READY", "NEEDS_COVERAGE"}
    if readiness.readiness_state not in allowed_states:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Repository is not ready for recommendations "
                f"(state={readiness.readiness_state}). "
                f"Reasons: {'; '.join(readiness.readiness_reasons)}"
            )
        )

    # 4. Run recommendation engine
    svc = RecommendationService(db)
    readiness_acknowledged = payload.readiness_acknowledged if payload else False
    try:
        run = svc.create_recommendation_run(
            RecommendationRunCreate(
                repository_id=repository_id,
                pr_id=str(pr.id),
                changed_files=[],          # collected from DB by the service
                triggered_by="MANUAL_DRY_RUN",
                readiness_acknowledged=readiness_acknowledged
            )
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Recommendation engine failed for PR {pr.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recommendation engine error: {str(e)}"
        )

    # 5. Build response — use only real persisted fields, no fabricated values
    from app.services.recommendation_reasoning_engine import RecommendationReasoningEngine

    recommended_tests = run.tests or []
    recommended_count = len(recommended_tests)

    # Generate plain-English explanations
    reasoning_engine = RecommendationReasoningEngine(db)
    explanation = reasoning_engine.explain(run)

    # Derive risk level from recommendation mode and evidence quality
    mode = run.recommendation_mode or "NORMAL"
    evidence_quality = run.evidence_quality or "UNKNOWN"
    if mode in ("FULL_REGRESSION", "SAFE_FALLBACK") or evidence_quality in ("LOW", "UNKNOWN"):
        risk_level = "HIGH"
    elif mode == "WIDENED" or evidence_quality == "MODERATE":
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return {
        "recommendation_run_id": str(run.id),
        "repository_id": str(repository_id),
        "pull_request_id": str(pr.id),
        "recommended_tests_count": recommended_count,
        "skipped_tests_count": run.skipped_count or 0,
        "estimated_runtime_seconds": run.estimated_runtime_seconds or 0.0,
        "full_suite_runtime_seconds": run.full_suite_runtime_seconds,
        "coverage_confidence": run.evidence_quality,
        "recommendation_mode": mode,
        "recommendation_readiness_state": run.recommendation_readiness_state,
        "risk_level": risk_level,
        "optimization_allowed": run.optimization_allowed,
        "unsafe_for_optimization": run.unsafe_for_optimization,
        "runtime_confidence": run.runtime_confidence,
        # Plain-English executive summary (≤4 bullets)
        "reasons": explanation["executive_summary"],
        # Per-test explanations keyed by stable_identity
        "per_test_explanations": explanation["per_test_explanations"],
        "skipped_reason_summary": run.skipped_reason_summary,
        "next_action": "Review Recommendation",
        "created_at": _utc_iso(run.created_at),
    }


@router.post("/repositories/{repository_id}/coverage/upload", dependencies=[Depends(require_workspace_member())])
async def upload_coverage(
    repository_id: UUID,
    file: UploadFile = File(...),
    format: str = Form("LCOV"),
    commit_sha: Optional[str] = Form(None),
    branch: Optional[str] = Form(None),
    source: str = Form("MANUAL_UPLOAD"),
    pull_request_id: Optional[UUID] = Form(None),
    head_sha: Optional[str] = Form(None),
    source_context: Optional[str] = Form(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Upload LCOV/Cobertura coverage report for a repository. Workspace-scoped.
    
    Requires repository to be selected_for_analysis. Preserves raw artifact,
    runs coverage ingestion pipeline, and returns summary.
    """
    # Verify repository belongs to workspace and is enabled
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in workspace")
    
    if not repo.selected_for_analysis:
        raise HTTPException(
            status_code=400, 
            detail="Enable this repository before uploading coverage evidence."
        )
    
    # Validate that test history has been uploaded first
    test_runs_count = db.query(func.count(TestRun.id)).filter(TestRun.repository_id == repository_id).scalar() or 0
    if test_runs_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Upload test history before coverage to make this repository recommendation-ready."
        )
    
    # Validate format
    if format.upper() not in ["LCOV", "COBERTURA"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {format}. Supported formats: LCOV, COBERTURA"
        )
    
    # Fast pre-reading size check
    max_bytes = settings.MAX_LCOV_SIZE_MB * 1024 * 1024
    if file.size and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Payload too large: Coverage report size exceeding limit of {settings.MAX_LCOV_SIZE_MB} MB."
        )
    
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read upload file stream: {str(e)}"
        )
    
    # Resolve PR commit / branch details
    resolved_commit_sha = commit_sha or head_sha
    if pull_request_id:
        resolved_pr = db.query(PullRequest).filter(
            PullRequest.id == pull_request_id,
            PullRequest.repository_id == repository_id
        ).first()
        if resolved_pr:
            if not resolved_commit_sha:
                resolved_commit_sha = resolved_pr.head_commit_sha
            if not branch:
                branch = resolved_pr.source_branch

    # Coverage ingestion requires commit_sha
    if not resolved_commit_sha:
        raise HTTPException(
            status_code=400,
            detail="commit_sha is required for coverage upload"
        )
    
    try:
        report = CoverageIngestionService.ingest_coverage(
            db=db,
            repository_id=repository_id,
            commit_sha=resolved_commit_sha,
            payload_bytes=file_bytes,
            file_name=file.filename or "coverage.info",
            pull_request_id=pull_request_id,
            branch=branch,
            correlation_id=None,
            source_context=source_context
        )
        db.commit()
    except CoverageIngestionError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing coverage report: {str(e)}"
        )
    
    # Recalculate readiness after coverage upload
    readiness_service = RepositoryReadinessService(db)
    readiness = readiness_service.calculate_readiness(repository_id, workspace.id)

    from app.services.recommendation_readiness_service import RecommendationReadinessService
    rec_readiness_svc = RecommendationReadinessService(db)
    latest_assessment = rec_readiness_svc.assess_readiness(
        repository_id=repository_id,
        pull_request_id=pull_request_id
    )
    readiness_summary = {
        "repository_id": str(latest_assessment.repository_id),
        "pull_request_id": str(latest_assessment.pull_request_id) if latest_assessment.pull_request_id else None,
        "readiness_level": latest_assessment.readiness_level,
        "expected_confidence": latest_assessment.expected_confidence,
        "readiness_score": latest_assessment.readiness_score,
        "can_generate": latest_assessment.can_generate,
        "can_generate_reason": latest_assessment.can_generate_reason,
        "signal_count": len(latest_assessment.available_signals),
        "total_signals": 15,
        "intelligence_completeness_score": latest_assessment.intelligence_completeness_score,
        "release_confidence_ceiling": latest_assessment.release_confidence_ceiling,
        "available_inputs": latest_assessment.available_inputs,
        "missing_inputs": latest_assessment.missing_inputs,
        "recommended_inputs": latest_assessment.recommended_inputs,
        "blocking_inputs": latest_assessment.blocking_inputs,
        "next_best_actions": latest_assessment.next_best_actions,
        "primary_message": latest_assessment.primary_message,
        "secondary_message": latest_assessment.secondary_message,
        "confidence_reason": latest_assessment.confidence_reason,
        "confidence_ceiling": latest_assessment.confidence_ceiling,
        "confidence_blockers": latest_assessment.confidence_blockers,
        "confidence_limiters": latest_assessment.confidence_limiters
    }
    
    return {
        "coverage_report_id": str(report.id),
        "format": format.upper(),
        "files_total": report.files_total,
        "covered_lines_total": report.covered_lines_total,
        "uncovered_lines_total": report.uncovered_lines_total,
        "total_lines": report.total_lines,
        "line_coverage_ratio": report.line_coverage_ratio,
        "coverage_confidence": report.coverage_confidence,
        "parser_version": "cobertura_parser.v1" if format.upper() == "COBERTURA" else "lcov_parser.v1",
        "normalization_schema_version": "cobertura_result.v1" if format.upper() == "COBERTURA" else "lcoc_result.v1",
        "evidence_health_status": report.evidence_health_status,
        "repository_readiness": {
            "readiness_state": readiness.readiness_state,
            "readiness_reasons": readiness.readiness_reasons,
            "next_action": readiness.next_action
        },
        "readiness_summary": readiness_summary
    }


# ----------------------------------------------------
# 1. Public OAuth Callback Endpoint
# ----------------------------------------------------
@router.get("/install/callback", status_code=status.HTTP_202_ACCEPTED)
def install_callback(
    installation_id: int,
    setup_action: str,
    state: str,
    db: Session = Depends(get_db)
):
    """Secure OAuth callback endpoint to verify setup state and trigger background repository sync."""
    service = GitHubAppService(db)
    
    correlation_id = {
        "github_installation_id": installation_id,
        "setup_action": setup_action,
        "state_token": state[:15] + "..." if state else None
    }
    
    logger.info(f"Received GitHub App installation callback. Details: {correlation_id}")
    
    # Verify State Signature and extract Organization ID
    try:
        org_id = service.verify_state_token(state)
    except Exception as e:
        logger.warning(f"Callback state token verification failed: {e}")
        service.log_system_event(
            entity_type="github_installation",
            entity_id=str(installation_id),
            event_type="webhook_signature_failed",
            payload={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Secure verification failed: {e}"
        )
        
    service.log_system_event(
        entity_type="github_installation",
        entity_id=str(installation_id),
        event_type="github_installation_callback_received",
        payload={**correlation_id, "workspace_id": str(org_id)}
    )

    # Trigger Background Sync Job
    try:
        sync_job_id = service.enqueue_sync_job(
            workspace_id=org_id,
            github_installation_id=installation_id,
            sync_reason="INSTALLATION_CALLBACK"
        )
        
        service.log_system_event(
            entity_type="github_installation",
            entity_id=str(installation_id),
            event_type="github_installation_verified",
            payload={"workspace_id": str(org_id), "sync_job_id": str(sync_job_id)}
        )
        
        return {
            "status": "accepted",
            "message": "GitHub App installation received. Repository synchronization initiated.",
            "workspace_id": org_id,
            "github_installation_id": installation_id,
            "sync_job_id": sync_job_id
        }
    except Exception as e:
        logger.error(f"Failed to initiate background sync job in callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Sync service currently unavailable: {e}"
        )


# ----------------------------------------------------
# 2. Public Webhook Handler Endpoint
# ----------------------------------------------------
@router.post("/webhook", status_code=status.HTTP_200_OK)
async def webhook_handler(
    request: Request,
    x_github_delivery: str = Header(...),
    x_github_event: str = Header(...),
    x_hub_signature_256: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Authenticate, log, and process events with deduplication and replay freshness validation."""
    service = GitHubAppService(db)
    
    # 1. Signature Authentication
    raw_body = await request.body()
    if not settings.GITHUB_WEBHOOK_SECRET:
        logger.error("GITHUB_WEBHOOK_SECRET is not configured.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server integration secret is unconfigured."
        )
        
    sig_valid = verify_signature(settings.GITHUB_WEBHOOK_SECRET, raw_body, x_hub_signature_256)
    if not sig_valid:
        logger.warning(f"Rejected webhook with invalid signature. Delivery ID: {x_github_delivery}")
        service.log_system_event(
            entity_type="webhook",
            entity_id=x_github_delivery,
            event_type="webhook_signature_failed",
            payload={"event_type": x_github_event}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature."
        )

    # Decode JSON payload
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must be valid JSON."
        )

    action = payload.get("action")
    installation_id = payload.get("installation", {}).get("id")
    repository_id = payload.get("repository", {}).get("id")

    # 2. Webhook Replay Freshness Validation
    # Webhooks must be verified within the max age seconds unless in internal testing mode
    is_testing = payload.get("testing_mode", False) or request.query_params.get("testing_mode") == "true"
    
    event_timestamp = None
    # Look for timestamp in standard payload positions
    for ts_key in ["updated_at", "created_at", "timestamp"]:
        if ts_key in payload:
            ts_val = payload[ts_key]
            try:
                # String parsing e.g. "2026-05-22T05:01:51Z"
                if isinstance(ts_val, str):
                    event_timestamp = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                elif isinstance(ts_val, (int, float)):
                    event_timestamp = datetime.fromtimestamp(ts_val, timezone.utc)
            except Exception:
                pass
            
    if event_timestamp:
        # Convert event timestamp to naive UTC datetime matching database
        event_timestamp_naive = event_timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        now_naive = datetime.utcnow()
        age_seconds = (now_naive - event_timestamp_naive).total_seconds()
        
        if age_seconds > settings.GITHUB_WEBHOOK_MAX_AGE_SECONDS and not is_testing:
            logger.warning(f"Rejected stale webhook delivery: {x_github_delivery}. Age: {age_seconds}s (limit: {settings.GITHUB_WEBHOOK_MAX_AGE_SECONDS}s)")
            service.log_system_event(
                entity_type="webhook",
                entity_id=x_github_delivery,
                event_type="webhook_replay_rejected",
                payload={"age_seconds": age_seconds, "limit_seconds": settings.GITHUB_WEBHOOK_MAX_AGE_SECONDS}
            )
            service.log_system_event(
                entity_type="webhook",
                entity_id=x_github_delivery,
                event_type="stale_webhook_detected",
                payload={"event_time": event_timestamp_naive.isoformat()}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Webhook delivery is stale. Rejecting replay request (Age: {age_seconds:.0f}s)."
            )
    else:
        event_timestamp_naive = datetime.utcnow()

    # 3. Deduplication Check
    existing_event = db.query(WebhookEvent).filter(WebhookEvent.github_delivery_id == x_github_delivery).first()
    if existing_event:
        logger.info(f"Ignored duplicate webhook delivery ID: {x_github_delivery}.")
        service.log_system_event(
            entity_type="webhook",
            entity_id=x_github_delivery,
            event_type="webhook_duplicate_ignored",
            payload={"event_type": x_github_event, "action": action}
        )
        return {
            "status": "ignored",
            "detail": f"Duplicate webhook delivery ID: {x_github_delivery} received."
        }

    # 4. Save Raw Payload through RawArtifact and register WebhookEvent
    from sqlalchemy.exc import IntegrityError
    try:
        raw_artifact = RawArtifact(
            artifact_type="github_webhook_payload",
            repository_id=None,
            storage_path=f"webhooks/{x_github_delivery}.json",
            artifact_metadata={"payload": payload},
            created_at=datetime.utcnow()
        )
        db.add(raw_artifact)
        db.flush() # Get raw_artifact.id

        webhook_event = WebhookEvent(
            github_delivery_id=x_github_delivery,
            event_type=x_github_event,
            action=action,
            installation_id=installation_id,
            repository_id=repository_id,
            signature_valid=True,
            processing_status="PROCESSING",
            raw_artifact_id=raw_artifact.id,
            received_at=datetime.utcnow()
        )
        db.add(webhook_event)
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info(f"Integrity check triggered on concurrent duplicate webhook delivery ID: {x_github_delivery}.")
        service.log_system_event(
            entity_type="webhook",
            entity_id=x_github_delivery,
            event_type="webhook_duplicate_ignored",
            payload={"event_type": x_github_event, "action": action, "concurrency_storm": True}
        )
        return {
            "status": "ignored",
            "detail": f"Duplicate webhook delivery ID: {x_github_delivery} received."
        }

    # 5. Load Installation to apply Timestamp Safety Check
    if not installation_id:
        # Some global hooks do not carry installation context
        webhook_event.processing_status = "COMPLETED"
        webhook_event.processed_at = datetime.utcnow()
        db.commit()
        return {"status": "processed", "detail": "Global event skipped."}

    installation: Optional[GitHubInstallation] = db.query(GitHubInstallation).filter(
        GitHubInstallation.github_installation_id == installation_id
    ).first()

    if installation:
        # Check event ordering
        if installation.last_github_event_at and event_timestamp_naive < installation.last_github_event_at:
            # Replay of older webhook event. Skip direct state mutation and schedule full reconciliation instead
            logger.info(f"Received out-of-order webhook event. Event time {event_timestamp_naive} is older than last_event {installation.last_github_event_at}. Scheduling full reconciliation.")
            service.log_system_event(
                entity_type="github_installation",
                entity_id=str(installation_id),
                event_type="stale_sync_detected",
                payload={"event_time": event_timestamp_naive.isoformat(), "last_event_time": installation.last_github_event_at.isoformat()}
            )
            
            # Enqueue full reconciliation resync
            service.enqueue_sync_job(
                workspace_id=installation.workspace_id,
                github_installation_id=installation_id,
                sync_reason="PERIODIC_RECONCILIATION"
            )
            
            webhook_event.processing_status = "COMPLETED"
            webhook_event.processed_at = datetime.utcnow()
            db.commit()
            return {"status": "processed", "detail": "Stale event scheduled reconciliation resync."}
        else:
            installation.last_github_event_at = event_timestamp_naive
            db.commit()

    # 6. Event Action Processing Routing
    try:
        if x_github_event == "installation":
            if action == "created":
                # New installation created - trigger sync job
                if installation:
                    logger.info(f"GitHub App installation created: {installation_id}. Triggering sync.")
                    installation.status = "PENDING_SYNC"
                    db.commit()
                    service.enqueue_sync_job(
                        workspace_id=installation.workspace_id,
                        github_installation_id=installation_id,
                        sync_reason="INSTALLATION_CREATED"
                    )
            elif action == "deleted":
                # Instant hard deactivation of installation mapping and all active repositories
                if installation:
                    logger.warning(f"GitHub App uninstalled for installation: {installation_id}. Set status REMOVED.")
                    installation.status = "REMOVED"
                    installation.evidence_health_status = "INSUFFICIENT"
                    
                    # Hard deactivate all associated repositories
                    repos = db.query(Repository).filter(Repository.workspace_id == installation.workspace_id).all()
                    for r in repos:
                        r.is_active = False
                        r.deactivation_reason = "INSTALLATION_DELETED"
                        service.log_system_event(
                            entity_type="repository",
                            entity_id=str(r.id),
                            event_type="repository_deactivated",
                            payload={"deactivation_reason": "INSTALLATION_DELETED", "github_delivery_id": x_github_delivery}
                        )
                        
                    service.log_system_event(
                        entity_type="github_installation",
                        entity_id=str(installation_id),
                        event_type="evidence_health_degraded",
                        payload={"health": "INSUFFICIENT", "reason": "INSTALLATION_DELETED"}
                    )
                    
                    db.commit()
            elif action in ("suspend", "unsuspend"):
                if installation:
                    status_map = {"suspend": "SUSPENDED", "unsuspend": "ACTIVE"}
                    installation.status = status_map[action]
                    db.commit()
                    
        elif x_github_event == "installation_repositories":
            # Any repository changes (added/removed) triggers a complete authoritative full sync job
            if installation:
                logger.info(f"Received installation_repositories event. Triggering authoritative resync.")
                service.enqueue_sync_job(
                    workspace_id=installation.workspace_id,
                    github_installation_id=installation_id,
                    sync_reason="INSTALLATION_REPOSITORIES_EVENT"
                )

        elif x_github_event == "pull_request":
            if action in ("opened", "synchronize", "reopened"):
                # Get Repository
                gh_repo_id = payload.get("repository", {}).get("id")
                if not gh_repo_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing repository.id in payload")
                
                db_repo = db.query(Repository).filter(Repository.github_repo_id == gh_repo_id).first()
                if not db_repo:
                    logger.warning(f"Repository with GitHub ID {gh_repo_id} not found in database. Skipping PR webhook.")
                    webhook_event.processing_status = "COMPLETED"
                    webhook_event.processed_at = datetime.utcnow()
                    db.commit()
                    return {"status": "ignored", "detail": f"Repository with github_repo_id {gh_repo_id} not found."}
                
                # Update webhook timestamp for this repository
                _update_repository_webhook_timestamp(db, gh_repo_id)
                
                # Recalculate readiness after webhook received
                readiness_service = RepositoryReadinessService(db)
                readiness_service.calculate_readiness(db_repo.id, db_repo.workspace_id)
                
                # Rule 3: Ignore unsupported (inactive) repositories
                if not db_repo.is_active:
                    logger.info(f"Ignoring PR event for deactivated repository {db_repo.full_name}")
                    webhook_event.processing_status = "COMPLETED"
                    webhook_event.processed_at = datetime.utcnow()
                    db.commit()
                    return {"status": "ignored", "detail": f"Repository {db_repo.full_name} is inactive."}
                
                # Fetch PR fields from payload
                pr_payload = payload.get("pull_request", {})
                
                # Rule 1: Ignore draft PRs initially
                if pr_payload.get("draft") is True:
                    logger.info(f"Ignoring draft PR in webhook.")
                    webhook_event.processing_status = "COMPLETED"
                    webhook_event.processed_at = datetime.utcnow()
                    db.commit()
                    return {"status": "ignored", "detail": "Draft PRs are ignored initially."}
                
                # Rule 2: Ignore closed PRs
                pr_state = pr_payload.get("state")
                if pr_state == "closed":
                    logger.info(f"Ignoring closed PR in webhook.")
                    webhook_event.processing_status = "COMPLETED"
                    webhook_event.processed_at = datetime.utcnow()
                    db.commit()
                    return {"status": "ignored", "detail": "Closed PRs are ignored."}

                github_pr_id = pr_payload.get("id")
                number = pr_payload.get("number")
                title = pr_payload.get("title", "No Title")
                author = pr_payload.get("user", {}).get("login", "unknown")
                source_branch = pr_payload.get("head", {}).get("ref")
                target_branch = pr_payload.get("base", {}).get("ref")
                
                # Check for rollback/hotfix PR
                title_lower = title.lower()
                body_lower = pr_payload.get("body", "").lower()
                rollback_keywords = ["revert", "rollback", "hotfix", "fix:"]
                is_rollback = any(kw in title_lower or kw in body_lower for kw in rollback_keywords)
                
                if is_rollback:
                    logger.info(f"Potential rollback PR detected: {title}")
                    # Get changed files in this PR
                    changed_files = []
                    for file in pr_payload.get("changed_files", []):
                        changed_files.append(file.get("filename"))
                    
                    # Find recent merged recommendation runs (last 7 days)
                    from datetime import timedelta
                    from app.models.recommendation import RecommendationRun
                    from app.models.pattern_memory_v2 import PatternMemoryV2
                    from app.models.pull_request import PullRequest
                    from app.models.pull_request import PullRequestChangedFile
                    import uuid
                    
                    seven_days_ago = datetime.utcnow() - timedelta(days=7)
                    recent_runs = db.query(RecommendationRun).filter(
                        RecommendationRun.repository_id == db_repo.id,
                        RecommendationRun.created_at >= seven_days_ago
                    ).all()
                    
                    rollback_detected = False
                    for run in recent_runs:
                        # Get changed files from the original PR
                        pr = db.query(PullRequest).filter(
                            PullRequest.id == run.pr_id
                        ).first()
                        if pr:
                            original_changed_files = db.query(PullRequestChangedFile).filter(
                                PullRequestChangedFile.pull_request_id == pr.id
                            ).all()
                            original_file_paths = [f.file_path for f in original_changed_files]
                            
                            # Check for file overlap
                            file_overlap = set(changed_files) & set(original_file_paths)
                            if file_overlap:
                                rollback_detected = True
                                logger.info(f"Rollback detected for run {run.id} - overlapping files: {file_overlap}")
                                
                                # Create PatternMemoryV2 signals for affected ACs
                                # Load ACs for the repository
                                from app.models.acceptance_criterion import AcceptanceCriterion
                                acs = db.query(AcceptanceCriterion).filter(
                                    AcceptanceCriterion.repository_id == db_repo.id
                                ).all()
                                
                                # For each overlapping file, find linked ACs and create signals
                                for file_path in file_overlap:
                                    # Find ACs that reference this file (simplified - would need proper traceability)
                                    for ac in acs:
                                        # Create signal for the AC
                                        existing = db.query(PatternMemoryV2).filter(
                                            PatternMemoryV2.pattern_key == ac.normalized_key,
                                            PatternMemoryV2.repository_id == db_repo.id
                                        ).first()
                                        
                                        if existing:
                                            existing.usage_count += 1
                                            existing.strength = min(1.0, existing.strength + 0.15)
                                        else:
                                            signal = PatternMemoryV2(
                                                id=uuid.uuid4(),
                                                repository_id=db_repo.id,
                                                workspace_id=db_repo.workspace_id,
                                                pattern_key=ac.normalized_key,
                                                signal_type="ROLLBACK",
                                                strength=0.8,
                                                confidence=0.8,
                                                usage_count=1
                                            )
                                            db.add(signal)
                                
                                db.commit()
                                
                                # Add comment to original PR
                                try:
                                    from app.services.github_service import GitHubService
                                    github_service = GitHubService(db)
                                    github_service.add_pr_comment(
                                        db_repo.github_repo_id,
                                        pr.github_pr_number,
                                        "⚠️ **VeriScope: Potential Rollback Detected**\n\n"
                                        f"A potential rollback was detected for this release. "
                                        f"Outcome learning signals have been updated for the affected areas.\n\n"
                                        f"Overlapping files: {', '.join(file_overlap)}"
                                    )
                                except Exception as e:
                                    logger.warning(f"Failed to add rollback comment: {e}")
                                
                                break  # Only process the first matching run
                    
                    if rollback_detected:
                        logger.info("Rollback detection completed and signals recorded")
                additions = pr_payload.get("additions", 0)
                deletions = pr_payload.get("deletions", 0)
                changed_files_count = pr_payload.get("changed_files", 0)
                head_commit_sha = pr_payload.get("head", {}).get("sha")
                
                # Parse timestamps
                gh_created_at_str = pr_payload.get("created_at")
                gh_updated_at_str = pr_payload.get("updated_at")
                
                gh_created_at = datetime.fromisoformat(gh_created_at_str.replace("Z", "+00:00")).replace(tzinfo=None) if gh_created_at_str else datetime.utcnow()
                gh_updated_at = datetime.fromisoformat(gh_updated_at_str.replace("Z", "+00:00")).replace(tzinfo=None) if gh_updated_at_str else datetime.utcnow()
                
                # Deduplicate based on PR specific ordering — scope by repository_id to prevent cross-workspace collision
                existing_pr = db.query(PullRequest).filter(
                    PullRequest.github_pr_id == github_pr_id,
                    PullRequest.repository_id == db_repo.id
                ).first()
                
                if existing_pr:
                    # Event ordering check: reject or reschedule if incoming update is older than or equal to what we processed
                    if existing_pr.last_github_updated_at and gh_updated_at <= existing_pr.last_github_updated_at:
                        logger.info(f"Received stale pull_request webhook event. Event updated_at {gh_updated_at} is older/equal to last_github_updated_at {existing_pr.last_github_updated_at}. Scheduling reconciliation resync.")
                        service.log_system_event(
                            entity_type="pr",
                            entity_id=str(existing_pr.id),
                            event_type="stale_webhook_detected",
                            payload={
                                "event_time": gh_updated_at.isoformat(),
                                "last_event_time": existing_pr.last_github_updated_at.isoformat(),
                                "webhook_delivery_id": x_github_delivery
                            }
                        )
                        existing_pr.reconciliation_required = True
                        db.commit()
                        
                        webhook_event.processing_status = "COMPLETED"
                        webhook_event.processed_at = datetime.utcnow()
                        db.commit()
                        return {"status": "processed", "detail": "Stale event scheduled reconciliation resync."}
                    else:
                        existing_pr.last_github_updated_at = gh_updated_at
                        existing_pr.last_processed_delivery_id = x_github_delivery
                        db.commit()
                
                sync_reason = f"WEBHOOK_{action.upper()}"
                
                # Enqueue background task
                sync_job_id = service.enqueue_pull_request_sync(
                    repository_id=db_repo.id,
                    github_pr_id=github_pr_id,
                    number=number,
                    title=title,
                    author=author,
                    source_branch=source_branch,
                    target_branch=target_branch,
                    state=pr_state,
                    additions=additions,
                    deletions=deletions,
                    changed_files_count=changed_files_count,
                    head_commit_sha=head_commit_sha,
                    github_created_at=gh_created_at,
                    github_updated_at=gh_updated_at,
                    installation_id=installation_id,
                    sync_reason=sync_reason,
                    webhook_delivery_id=x_github_delivery
                )
                
                webhook_event.processing_status = "COMPLETED"
                webhook_event.processed_at = datetime.utcnow()
                db.commit()
                
                return {
                    "status": "processed",
                    "action": action,
                    "pull_request_id": github_pr_id,
                    "sync_job_id": str(sync_job_id)
                }
            elif action == "closed":
                # Get Repository
                gh_repo_id = payload.get("repository", {}).get("id")
                if not gh_repo_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing repository.id in payload")
                
                db_repo = db.query(Repository).filter(Repository.github_repo_id == gh_repo_id).first()
                if not db_repo:
                    logger.warning(f"Repository with GitHub ID {gh_repo_id} not found in database. Skipping PR webhook.")
                    webhook_event.processing_status = "COMPLETED"
                    webhook_event.processed_at = datetime.utcnow()
                    db.commit()
                    return {"status": "ignored", "detail": f"Repository with github_repo_id {gh_repo_id} not found."}
                
                # Update webhook timestamp for this repository
                _update_repository_webhook_timestamp(db, gh_repo_id)
                
                # Rule 3: Ignore unsupported (inactive) repositories
                if not db_repo.is_active:
                    logger.info(f"Ignoring PR event for deactivated repository {db_repo.full_name}")
                    webhook_event.processing_status = "COMPLETED"
                    webhook_event.processed_at = datetime.utcnow()
                    db.commit()
                    return {"status": "ignored", "detail": f"Repository {db_repo.full_name} is inactive."}
                
                # Fetch PR fields from payload
                pr_payload = payload.get("pull_request", {})
                is_merged = pr_payload.get("merged") is True
                event_type = "PR_MERGED" if is_merged else "PR_CLOSED_UNMERGED"
                
                github_pr_id = pr_payload.get("id")
                db_pr = db.query(PullRequest).filter(
                    PullRequest.github_pr_id == github_pr_id,
                    PullRequest.repository_id == db_repo.id
                ).first()
                
                # Update pull request state in database
                gh_updated_at_str = pr_payload.get("updated_at")
                gh_updated_at = datetime.fromisoformat(gh_updated_at_str.replace("Z", "+00:00")).replace(tzinfo=None) if gh_updated_at_str else datetime.utcnow()
                
                if db_pr:
                    db_pr.state = "closed"
                    db_pr.github_updated_at = gh_updated_at
                    db_pr.last_github_updated_at = gh_updated_at
                    db_pr.last_processed_delivery_id = x_github_delivery
                    db.commit()
                
                # Parse occurred_at (merged_at or closed_at)
                occurred_at_str = pr_payload.get("merged_at") if is_merged else pr_payload.get("closed_at")
                occurred_at = None
                if occurred_at_str:
                    try:
                        occurred_at = datetime.fromisoformat(occurred_at_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        pass
                
                # Prepare OutcomeEventCreate
                from app.services.outcome_learning_service import OutcomeLearningService
                from app.schemas.outcome_learning import OutcomeEventCreate
                
                event_in = OutcomeEventCreate(
                    event_type=event_type,
                    event_source="github",
                    event_status="completed",
                    occurred_at=occurred_at,
                    external_event_id=x_github_delivery,
                    metadata_json=payload,
                    pull_request_id=db_pr.id if db_pr else None,
                    github_pr_number=pr_payload.get("number"),
                    commit_sha=pr_payload.get("head", {}).get("sha")
                )
                
                # Ingest event
                OutcomeLearningService.ingest_event(
                    db=db,
                    workspace_id=db_repo.workspace_id,
                    repository_id=db_repo.id,
                    event_in=event_in
                )
                
                webhook_event.processing_status = "COMPLETED"
                webhook_event.processed_at = datetime.utcnow()
                db.commit()
                return {"status": "processed", "action": action, "event_type": event_type}

        elif x_github_event == "check_suite":
            if action == "completed":
                # Get Repository
                gh_repo_id = payload.get("repository", {}).get("id")
                if not gh_repo_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing repository.id in payload")
                
                db_repo = db.query(Repository).filter(Repository.github_repo_id == gh_repo_id).first()
                if not db_repo:
                    logger.warning(f"Repository with GitHub ID {gh_repo_id} not found in database. Skipping check_suite webhook.")
                    webhook_event.processing_status = "COMPLETED"
                    webhook_event.processed_at = datetime.utcnow()
                    db.commit()
                    return {"status": "ignored", "detail": f"Repository with github_repo_id {gh_repo_id} not found."}
                
                # Update webhook timestamp for this repository
                _update_repository_webhook_timestamp(db, gh_repo_id)
                
                # Rule 3: Ignore unsupported (inactive) repositories
                if not db_repo.is_active:
                    logger.info(f"Ignoring check_suite event for deactivated repository {db_repo.full_name}")
                    webhook_event.processing_status = "COMPLETED"
                    webhook_event.processed_at = datetime.utcnow()
                    db.commit()
                    return {"status": "ignored", "detail": f"Repository {db_repo.full_name} is inactive."}

                check_suite_payload = payload.get("check_suite", {})
                head_sha = check_suite_payload.get("head_sha")
                
                # --- OUTCOME LEARNING INGESTION START ---
                conclusion = check_suite_payload.get("conclusion")
                ci_event_type = None
                if conclusion == "success":
                    ci_event_type = "CI_PASSED_AFTER_RECOMMENDATION"
                elif conclusion in ("failure", "timed_out"):
                    ci_event_type = "CI_FAILED_AFTER_RECOMMENDATION"

                if ci_event_type:
                    occurred_at_str = check_suite_payload.get("updated_at")
                    occurred_at = None
                    if occurred_at_str:
                        try:
                            occurred_at = datetime.fromisoformat(occurred_at_str.replace("Z", "+00:00")).replace(tzinfo=None)
                        except Exception:
                            pass
                    
                    from app.services.outcome_learning_service import OutcomeLearningService
                    from app.schemas.outcome_learning import OutcomeEventCreate
                    
                    # Look up PRs in payload or database to link
                    pr_payloads = check_suite_payload.get("pull_requests", [])
                    pr_numbers = [p.get("number") for p in pr_payloads if p.get("number")]
                    
                    # Fallback to DB PRs matching head_sha
                    if not pr_numbers:
                        db_prs = db.query(PullRequest).filter(
                            PullRequest.repository_id == db_repo.id,
                            PullRequest.head_commit_sha == head_sha
                        ).all()
                        pr_numbers = [db_pr.number for db_pr in db_prs]

                    if pr_numbers:
                        for pr_num in pr_numbers:
                            db_pr = db.query(PullRequest).filter(
                                PullRequest.repository_id == db_repo.id,
                                PullRequest.number == pr_num
                            ).first()
                            
                            event_in = OutcomeEventCreate(
                                event_type=ci_event_type,
                                event_source="github",
                                event_status="completed",
                                occurred_at=occurred_at,
                                external_event_id=f"{x_github_delivery}_{pr_num}",
                                metadata_json=payload,
                                pull_request_id=db_pr.id if db_pr else None,
                                github_pr_number=pr_num,
                                commit_sha=head_sha
                            )
                            try:
                                OutcomeLearningService.ingest_event(
                                    db=db,
                                    workspace_id=db_repo.workspace_id,
                                    repository_id=db_repo.id,
                                    event_in=event_in
                                )
                            except Exception as ol_err:
                                logger.error(f"Failed to ingest outcome event for check_suite, PR {pr_num}: {ol_err}")
                    else:
                        event_in = OutcomeEventCreate(
                            event_type=ci_event_type,
                            event_source="github",
                            event_status="completed",
                            occurred_at=occurred_at,
                            external_event_id=x_github_delivery,
                            metadata_json=payload,
                            commit_sha=head_sha
                        )
                        try:
                            OutcomeLearningService.ingest_event(
                                db=db,
                                workspace_id=db_repo.workspace_id,
                                repository_id=db_repo.id,
                                event_in=event_in
                            )
                        except Exception as ol_err:
                            logger.error(f"Failed to ingest outcome event for check_suite, commit {head_sha}: {ol_err}")
                # --- OUTCOME LEARNING INGESTION END ---
                
                # Fetch PRs from payload and from DB matching head_sha
                prs_to_process = []
                
                # 1. Pull requests listed in payload
                pr_payloads = check_suite_payload.get("pull_requests", [])
                for pr_p in pr_payloads:
                    pr_num = pr_p.get("number")
                    if pr_num and pr_num not in prs_to_process:
                        prs_to_process.append(pr_num)
                        
                # 2. Lookup existing PRs in DB by head_sha
                db_prs = db.query(PullRequest).filter(
                    PullRequest.repository_id == db_repo.id,
                    PullRequest.head_commit_sha == head_sha
                ).all()
                for db_pr in db_prs:
                    if db_pr.number not in prs_to_process:
                        prs_to_process.append(db_pr.number)
                
                # Fetch details for each PR and process if they are supported, active, not draft, and not closed.
                owner, repo_name = db_repo.full_name.split("/")
                prs_processed_count = 0
                
                for pr_num in prs_to_process:
                    try:
                        # Fetch PR details from GitHub using our new get_pull_request method on the client
                        pr_data = service.client.get_pull_request(
                            installation_id=installation_id,
                            owner=owner,
                            repo=repo_name,
                            pull_number=pr_num
                        )
                    except Exception as e:
                        logger.warning(f"Failed to fetch PR {pr_num} details from GitHub: {e}")
                        # Fallback to DB if GitHub API fails
                        db_pr = db.query(PullRequest).filter(
                            PullRequest.repository_id == db_repo.id,
                            PullRequest.number == pr_num
                        ).first()
                        if db_pr:
                            pr_data = {
                                "id": db_pr.github_pr_id,
                                "number": db_pr.number,
                                "title": db_pr.title,
                                "user": {"login": db_pr.author},
                                "head": {"ref": db_pr.source_branch, "sha": db_pr.head_commit_sha},
                                "base": {"ref": db_pr.target_branch},
                                "state": db_pr.state,
                                "draft": False,
                                "additions": db_pr.additions,
                                "deletions": db_pr.deletions,
                                "changed_files": db_pr.changed_files_count
                            }
                        else:
                            continue

                    # Ignore draft PRs
                    if pr_data.get("draft") is True:
                        logger.info(f"Ignoring draft PR {pr_num} in check_suite webhook.")
                        continue
                        
                    # Ignore closed PRs
                    if pr_data.get("state") == "closed":
                        logger.info(f"Ignoring closed PR {pr_num} in check_suite webhook.")
                        continue
                    
                    prs_processed_count += 1
                    
                    # Ensure PR stub / record exists in DB
                    db_pr = db.query(PullRequest).filter(
                        PullRequest.repository_id == db_repo.id,
                        PullRequest.number == pr_num
                    ).first()
                    
                    # Parse timestamps
                    gh_created_at_str = pr_data.get("created_at")
                    gh_updated_at_str = pr_data.get("updated_at")
                    gh_created_at = datetime.fromisoformat(gh_created_at_str.replace("Z", "+00:00")).replace(tzinfo=None) if gh_created_at_str else datetime.utcnow()
                    gh_updated_at = datetime.fromisoformat(gh_updated_at_str.replace("Z", "+00:00")).replace(tzinfo=None) if gh_updated_at_str else datetime.utcnow()

                    if not db_pr:
                        # Create PR stub
                        db_pr = PullRequest(
                            repository_id=db_repo.id,
                            github_pr_id=pr_data.get("id"),
                            number=pr_num,
                            title=pr_data.get("title", "No Title"),
                            author=pr_data.get("user", {}).get("login", "unknown"),
                            source_branch=pr_data.get("head", {}).get("ref", "unknown"),
                            target_branch=pr_data.get("base", {}).get("ref", "unknown"),
                            state=pr_data.get("state", "open"),
                            additions=pr_data.get("additions", 0),
                            deletions=pr_data.get("deletions", 0),
                            changed_files_count=pr_data.get("changed_files", 0),
                            head_commit_sha=pr_data.get("head", {}).get("sha"),
                            github_created_at=gh_created_at,
                            github_updated_at=gh_updated_at,
                            last_github_updated_at=gh_updated_at,
                            last_processed_delivery_id=x_github_delivery,
                            sync_integrity_status="UNKNOWN",
                            evidence_health_status="HEALTHY",
                            evidence_consistency_status="UNKNOWN"
                        )
                        db.add(db_pr)
                        db.commit()
                        db.refresh(db_pr)
                    else:
                        db_pr.head_commit_sha = pr_data.get("head", {}).get("sha")
                        db_pr.github_updated_at = gh_updated_at
                        db_pr.last_github_updated_at = gh_updated_at
                        db_pr.last_processed_delivery_id = x_github_delivery
                        db.commit()
                    
                    # Check if the PR needs synchronization (head_commit_sha doesn't match head_sha or sync_integrity_status is not success)
                    if db_pr.head_commit_sha != head_sha or db_pr.sync_integrity_status != "FULL_SUCCESS":
                        # PR commits/files need sync
                        sync_reason = f"WEBHOOK_CHECK_SUITE_COMPLETED_SYNC"
                        service.enqueue_pull_request_sync(
                            repository_id=db_repo.id,
                            github_pr_id=db_pr.github_pr_id,
                            number=pr_num,
                            title=db_pr.title,
                            author=db_pr.author,
                            source_branch=db_pr.source_branch,
                            target_branch=db_pr.target_branch,
                            state=db_pr.state,
                            additions=db_pr.additions,
                            deletions=db_pr.deletions,
                            changed_files_count=db_pr.changed_files_count,
                            head_commit_sha=head_sha,
                            github_created_at=db_pr.github_created_at,
                            github_updated_at=db_pr.github_updated_at,
                            installation_id=installation_id,
                            sync_reason=sync_reason,
                            webhook_delivery_id=x_github_delivery
                        )
                    else:
                        # PR is already synced for this SHA. Directly enqueue recommendation generation!
                        logger.info(f"PR {pr_num} already synced for SHA {head_sha}. Enqueuing recommendation generation directly.")
                        from app.services.github_app import get_rq_queue, generate_recommendation_task_wrapper
                        queue = get_rq_queue()
                        queue.enqueue(
                            generate_recommendation_task_wrapper,
                            args=(str(db_repo.id), str(pr_num), f"WEBHOOK_CHECK_SUITE_COMPLETED"),
                            job_id=f"generate_recommendation_{db_pr.id}_{head_sha}"
                        )
                
                webhook_event.processing_status = "COMPLETED"
                webhook_event.processed_at = datetime.utcnow()
                db.commit()
                return {"status": "processed", "action": action, "prs_processed": prs_processed_count}

        # Generic repository event handler - updates webhook timestamp for any repository event
        elif repository_id and x_github_event in ("push", "workflow_run", "workflow_job", "create", "delete", "release"):
            # Update webhook timestamp for repository events even if we don't process them specifically
            _update_repository_webhook_timestamp(db, repository_id)
            
            webhook_event.processing_status = "COMPLETED"
            webhook_event.processed_at = datetime.utcnow()
            db.commit()
            return {"status": "processed", "detail": f"{x_github_event} event acknowledged"}

        webhook_event.processing_status = "COMPLETED"
        webhook_event.processed_at = datetime.utcnow()
        db.commit()
        return {"status": "processed"}

    except Exception as e:
        logger.exception(f"Error processing webhook event: {e}")
        webhook_event.processing_status = "FAILED"
        webhook_event.error_message = str(e)
        webhook_event.processed_at = datetime.utcnow()
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing error: {e}"
        )


# ----------------------------------------------------
# 3. Internal / Admin Endpoints
# ----------------------------------------------------
@router.post("/installations/{id}/sync", status_code=status.HTTP_202_ACCEPTED)
def manual_sync_trigger(
    id: UUID,  # This ID refers to the organization ID
    db: Session = Depends(get_db)
):
    """Admin-triggered manual full repository synchronization."""
    service = GitHubAppService(db)
    
    # Load organization's active installation details
    installation = db.query(GitHubInstallation).filter(GitHubInstallation.workspace_id == id).first()
    if not installation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active GitHub Installation found for Organization ID: {id}"
        )
        
    try:
        sync_job_id = service.enqueue_sync_job(
            workspace_id=id,
            github_installation_id=installation.github_installation_id,
            sync_reason="MANUAL_RETRY"
        )
        return {
            "status": "accepted",
            "message": "Manual repository resync queued.",
            "sync_job_id": sync_job_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


@router.get("/installations/{id}/sync-status")
def get_sync_status(
    id: UUID, # Organization ID
    db: Session = Depends(get_db)
):
    """Retrieve detailed execution stats of the latest repository sync runs."""
    installation = db.query(GitHubInstallation).filter(GitHubInstallation.workspace_id == id).first()
    if not installation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installation not found.")
        
    latest_job = db.query(RepositorySyncJob).filter(
        RepositorySyncJob.workspace_id == id
    ).order_by(RepositorySyncJob.started_at.desc()).first()
    
    return {
        "workspace_id": id,
        "github_installation_id": installation.github_installation_id,
        "installation_status": installation.status,
        "evidence_health_status": installation.evidence_health_status,
        "consecutive_failures": installation.consecutive_sync_failures,
        "last_successful_sync_at": installation.last_successful_sync_at,
        "latest_job": {
            "id": latest_job.id if latest_job else None,
            "status": latest_job.status if latest_job else None,
            "sync_reason": latest_job.sync_reason if latest_job else None,
            "integrity_status": latest_job.integrity_status if latest_job else None,
            "error_message": latest_job.error_message if latest_job else None,
            "total_repositories_seen": latest_job.total_repositories_seen if latest_job else 0,
            "repositories_created": latest_job.repositories_created if latest_job else 0,
            "repositories_updated": latest_job.repositories_updated if latest_job else 0,
            "repositories_marked_inactive": latest_job.repositories_marked_inactive if latest_job else 0,
            "pagination_completed": latest_job.pagination_completed if latest_job else False
        } if latest_job else None
    }


@router.get("/webhooks/{delivery_id}")
def get_webhook_event_details(
    delivery_id: str,
    db: Session = Depends(get_db)
):
    """Query persisted webhook event history metadata."""
    event = db.query(WebhookEvent).filter(WebhookEvent.github_delivery_id == delivery_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook event not found.")
        
    raw_payload = db.query(RawArtifact).filter(RawArtifact.id == event.raw_artifact_id).first()
    
    return {
        "delivery_id": event.github_delivery_id,
        "event_type": event.event_type,
        "action": event.action,
        "processing_status": event.processing_status,
        "error_message": event.error_message,
        "received_at": event.received_at,
        "processed_at": event.processed_at,
        "raw_payload": raw_payload.artifact_metadata.get("payload") if raw_payload else None
    }


@router.get("/sync-jobs/{id}")
def get_sync_job_details(
    id: UUID,
    db: Session = Depends(get_db)
):
    """Query specialized sync job detail audit fields."""
    job = db.query(RepositorySyncJob).filter(RepositorySyncJob.id == id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync job not found.")
        
    return {
        "id": job.id,
        "workspace_id": job.workspace_id,
        "github_installation_id": job.github_installation_id,
        "status": job.status,
        "sync_reason": job.sync_reason,
        "evidence_health_status": job.evidence_health_status,
        "integrity_status": job.integrity_status,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error_message": job.error_message,
        "retry_count": job.retry_count,
        "pagination_completed": job.pagination_completed,
        "pages_received": job.pages_received,
        "pages_expected": job.pages_expected,
        "total_repos_seen": job.total_repositories_seen,
        "repos_created": job.repositories_created,
        "repos_updated": job.repositories_updated,
        "repos_marked_inactive": job.repositories_marked_inactive
    }


# ----------------------------------------------------
# 4. Diagnostics & Trust Health Dashboard Endpoint
# ----------------------------------------------------
@router.get("/installations/{id}/trust-health")
def get_trust_health_diagnostics(
    id: UUID,  # Organization ID
    db: Session = Depends(get_db)
):
    """Diagnostics diagnostic dashboard exposing composite sync, webhook, and recommendation safety limits."""
    installation = db.query(GitHubInstallation).filter(GitHubInstallation.workspace_id == id).first()
    if not installation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installation not found.")

    # Calculate active webhook backlog (RECEIVED or PROCESSING states)
    backlog_count = db.query(WebhookEvent).filter(
        WebhookEvent.installation_id == installation.github_installation_id,
        WebhookEvent.processing_status.in_(["RECEIVED", "PROCESSING"])
    ).count()

    # Calculate latest latency (time between receipt and completion) for the last completed webhook
    last_completed = db.query(WebhookEvent).filter(
        WebhookEvent.installation_id == installation.github_installation_id,
        WebhookEvent.processing_status == "COMPLETED",
        WebhookEvent.processed_at.is_(None) == False
    ).order_by(WebhookEvent.received_at.desc()).first()

    processing_latency_seconds = None
    if last_completed and last_completed.processed_at:
        processing_latency_seconds = (last_completed.processed_at - last_completed.received_at).total_seconds()

    # Get latest repository sync job
    latest_job = db.query(RepositorySyncJob).filter(
        RepositorySyncJob.workspace_id == id
    ).order_by(RepositorySyncJob.started_at.desc()).first()

    # Build trust analysis
    degradation_reasons = []
    recommendation_safety_warnings = []
    
    if installation.evidence_health_status == "DEGRADED":
        degradation_reasons.append(f"Intermittent synchronization failure. Consecutive failure count: {installation.consecutive_sync_failures}")
        recommendation_safety_warnings.append("WARNING: Operational evidence is degraded. Widening recommendation scope to parents/neighbors is active.")
        
    elif installation.evidence_health_status == "INSUFFICIENT":
        degradation_reasons.append(f"Repeated installation sync failures ({installation.consecutive_sync_failures} failures) or app was uninstalled.")
        recommendation_safety_warnings.append("CRITICAL: Ingestion mapping is insufficient. Disable all aggressive regression test optimizations. Safe-Fallback run all tests.")
        
    if backlog_count > 5:
        degradation_reasons.append(f"High webhook processing backlog ({backlog_count} events). Event synchronization is delayed.")
        recommendation_safety_warnings.append("WARNING: Webhook latency is high. Recommendations might operate on stale repository branches.")

    # Repository mapping quality (total repos active vs total seen)
    active_repos = db.query(Repository).filter(Repository.workspace_id == id, Repository.is_active == True).count()
    total_repos = db.query(Repository).filter(Repository.workspace_id == id).count()
    mapping_quality = "HIGH" if total_repos == 0 else f"{active_repos}/{total_repos} active"

    return {
        "workspace_id": id,
        "github_installation_id": installation.github_installation_id,
        "installation_health": installation.evidence_health_status,
        "sync_integrity": latest_job.integrity_status if latest_job else "UNKNOWN",
        "webhook_backlog": backlog_count,
        "webhook_processing_latency_seconds": processing_latency_seconds,
        "last_successful_sync": installation.last_successful_sync_at,
        "repository_mapping_quality": mapping_quality,
        "coverage_mapping_health": "VALID" if installation.evidence_health_status == "HEALTHY" else "STALE",
        "evidence_degradation_reasons": degradation_reasons,
        "recommendation_safety_warnings": recommendation_safety_warnings
    }


# ----------------------------------------------------
# 5. Internal PR Debug Diagnostic Endpoint
# ----------------------------------------------------
internal_router = APIRouter(prefix="/internal/prs", tags=["Internal Diagnostics"])

@internal_router.get("/{id}/debug", response_model=PRDebugResponse)
def get_pr_debug(
    id: UUID,
    db: Session = Depends(get_db)
):
    """Retrieve highly comprehensive forensic explainability data for a specific Pull Request."""
    pr = db.query(PullRequest).filter(PullRequest.id == id).first()
    if pr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull Request with ID {id} not found."
        )

    # 1. Raw Inputs
    raw_inputs = {
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
        "last_processed_delivery_id": pr.last_processed_delivery_id
    }

    # 2. Derived Relationships
    derived_relationships = {
        "commits": [
            {
                "sha": c.sha,
                "message": c.message,
                "author": c.author,
                "commit_date": c.commit_date.isoformat() if c.commit_date else None
            }
            for c in pr.commits
        ],
        "changed_files": [
            {
                "file_path": f.file_path,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions
            }
            for f in pr.changed_files
        ]
    }

    # 3. Fallback Heuristics Used
    fallback_heuristics_used = []
    if any(job.status == "SUPERSEDED" for job in pr.sync_jobs):
        fallback_heuristics_used.append("superseded_pending_jobs")
    if pr.reconciliation_required:
        fallback_heuristics_used.append("reconciliation_required_heuristic")
    if pr.last_processed_delivery_id is None:
        fallback_heuristics_used.append("missing_processed_delivery_heuristic")

    # 4. Warnings
    warnings = []
    if pr.evidence_truncated:
        warnings.append(pr.truncation_reason or "evidence_truncated")
    if pr.changed_files_count > 300 or len(pr.commits) > 100:
        warnings.append("Size threshold violations: changed files or commits exceeded safety caps")

    # 5. Confidence Issues
    confidence_issues = []
    confidence_issues.append(f"health:{pr.evidence_health_status}")
    confidence_issues.append(f"consistency:{pr.evidence_consistency_status}")
    if pr.unsafe_for_optimization:
        confidence_issues.append("unsafe_for_optimization")

    # 6. Telemetry (Correlation ID, sync jobs status, retry count)
    sync_jobs_list = [
        {
            "job_id": str(job.id),
            "status": job.status,
            "sync_reason": job.sync_reason,
            "retry_count": job.retry_count,
            "error_message": job.error_message,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None
        }
        for job in pr.sync_jobs
    ]
    total_retries = sum(job.retry_count for job in pr.sync_jobs)
    
    telemetry = {
        "correlation_id": pr.last_processed_delivery_id or str(pr.id),
        "last_sync_started_at": pr.last_sync_started_at.isoformat() if pr.last_sync_started_at else None,
        "last_sync_completed_at": pr.last_sync_completed_at.isoformat() if pr.last_sync_completed_at else None,
        "last_successful_sync_at": pr.last_successful_sync_at.isoformat() if pr.last_successful_sync_at else None,
        "sync_jobs": sync_jobs_list,
        "total_retry_count": total_retries
    }

    return PRDebugResponse(
        raw_inputs=raw_inputs,
        derived_relationships=derived_relationships,
        fallback_heuristics_used=fallback_heuristics_used,
        warnings=warnings,
        confidence_issues=confidence_issues,
        telemetry=telemetry
    )


# ----------------------------------------------------
# 6. Hardened PR Comment Observability & Recovery APIs
# ----------------------------------------------------

@router.get("/comments/metrics", status_code=status.HTTP_200_OK)
def get_comments_metrics(db: Session = Depends(get_db)):
    """Retrieve operational observability metrics for the PR comment delivery subsystem."""
    from app.services.pr_comment_service import PRCommentService
    service = PRCommentService(db)
    return service.get_delivery_metrics()


@router.get("/comments/dead-letter", status_code=status.HTTP_200_OK)
def get_comments_dead_letter(db: Session = Depends(get_db)):
    """Retrieve all comments in the Dead-Letter Queue (permanently failed comment states)."""
    from app.services.pr_comment_service import PRCommentService
    service = PRCommentService(db)
    dead_comments = service.list_dead_letter_comments()
    return [
        {
            "id": str(c.id),
            "repository_id": str(c.repository_id),
            "pull_request_id": str(c.pull_request_id),
            "comment_status": c.comment_status,
            "comment_integrity_status": c.comment_integrity_status,
            "delivery_attempt_count": c.delivery_attempt_count,
            "last_delivery_error": c.last_delivery_error,
            "last_delivery_attempt_at": c.last_delivery_attempt_at.isoformat() if c.last_delivery_attempt_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None
        }
        for c in dead_comments
    ]


@router.post("/comments/{state_id}/replay", status_code=status.HTTP_202_ACCEPTED)
def post_replay_comment_delivery(state_id: UUID, db: Session = Depends(get_db)):
    """Manually trigger replay for a comment state by re-enqueuing its latest recommendation run."""
    from app.services.pr_comment_service import PRCommentService
    service = PRCommentService(db)
    try:
        msg = service.replay_comment_delivery(state_id)
        return {"status": "accepted", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/comments/runs/{run_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
def post_regenerate_comment(run_id: UUID, db: Session = Depends(get_db)):
    """Manually regenerate and enqueue delivery for a specific recommendation run."""
    from app.services.pr_comment_service import PRCommentService
    service = PRCommentService(db)
    try:
        msg = service.regenerate_comment_from_recommendation(run_id)
        return {"status": "accepted", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/comments/prs/{pr_id}/repair", status_code=status.HTTP_200_OK)
def post_repair_comment_state(pr_id: UUID, db: Session = Depends(get_db)):
    """Manually query GitHub to align the database comment ID and reset integrity status."""
    from app.services.pr_comment_service import PRCommentService
    service = PRCommentService(db)
    try:
        msg = service.repair_stale_comment_state(pr_id)
        return {"status": "success", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ----------------------------------------------------
# Internal: Manual Installation Link (Local Dev Only)
# ----------------------------------------------------
@router.post("/internal/installations/manual-link")
def manual_installation_link(
    request: InstallationCallbackRequest,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually link a GitHub installation to the current workspace (local dev only).
    
    This endpoint allows developers to link an installation without going through
    the full GitHub App installation flow. Useful for testing.
    """
    from app.models.user import WorkspaceMember
    
    # Get user's workspace
    member = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a workspace"
        )
    
    workspace_id = member.workspace_id
    
    # Check if installation already exists
    existing_installation = db.query(GitHubInstallation).filter(
        GitHubInstallation.workspace_id == workspace_id
    ).first()
    
    if existing_installation:
        existing_installation.installation_id = request.installation_id
        existing_installation.github_installation_id = request.installation_id
        existing_installation.status = "ACTIVE"
        existing_installation.updated_at = datetime.utcnow()
        db.commit()
        result_status = "updated"
    else:
        installation = GitHubInstallation(
            workspace_id=workspace_id,
            installation_id=request.installation_id,
            github_installation_id=request.installation_id,
            github_account_login=user.name or user.email or "unknown",
            github_account_type="User",
            repository_selection="all",
            status="ACTIVE",
            installed_by=user.name or user.email,
            installed_at=datetime.utcnow()
        )
        db.add(installation)
        db.commit()
        result_status = "created"

    # Run inline repository sync
    sync_result = {"created": 0, "updated": 0}
    try:
        service = GitHubAppService(db)
        sync_result = service.inline_sync_repositories(
            workspace_id=workspace_id,
            github_installation_id=request.installation_id
        )
    except Exception as e:
        logger.warning(f"Inline sync failed for manual-link: {e}")

    repo_count = db.query(Repository).filter(Repository.workspace_id == workspace_id).count()

    return {
        "status": result_status,
        "connected": True,
        "installation_id": request.installation_id,
        "repositories_count": repo_count,
        "sync": sync_result
    }

