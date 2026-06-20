from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User, Workspace, WorkspaceMember

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me")
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns authenticated user profile and active workspace details.
    Workspace creation is handled by get_current_user dependency.
    """
    # Find active workspace membership
    member = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).first()
    workspace_data = None
    if member:
        workspace = db.query(Workspace).filter(Workspace.id == member.workspace_id).first()
        if workspace:
            workspace_data = {
                "id": str(workspace.id),
                "name": workspace.name,
                "slug": workspace.slug,
                "role": member.role
            }

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "auth_provider": user.auth_provider,
        "workspace": workspace_data
    }


@router.delete("/me")
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Delete the authenticated user and all associated data.

    - Deletes workspace memberships
    - If user is the only member of a workspace they created, deletes the workspace
      (which cascades to delete all repositories, installations, and related data)
    - If workspace has other members, only removes the user's membership
    """
    from app.models.user import WorkspaceMember, Workspace
    from app.models import immutability
    from app.models.business_intent import BusinessIntentOverride
    from sqlalchemy import text

    logger = logging.getLogger(__name__)

    # Enable bypass of forensic immutability guards for Right to Be Forgotten deletion
    immutability.bypass_immutability = True

    try:
        # Temporarily disable PostgreSQL triggers that block evidence ledger mutations
        # This is necessary for account deletion (Right to Be Forgotten)
        # We execute and commit this immediately to ensure triggers are disabled
        # globally across any connection pool / session boundaries during the deletes.
        db.execute(text("ALTER TABLE pull_request_snapshots DISABLE TRIGGER enforce_snapshot_immutability;"))
        db.execute(text("ALTER TABLE raw_artifacts DISABLE TRIGGER enforce_artifact_update_immutability;"))
        db.commit()

        # Get all workspace memberships for this user
        memberships = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).all()

        for membership in memberships:
            workspace_id = membership.workspace_id
            workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()

            if workspace:
                # Check if this user is the only member
                member_count = db.query(WorkspaceMember).filter(
                    WorkspaceMember.workspace_id == workspace_id
                ).count()

                if member_count == 1:
                    # User is the only member - delete the entire workspace
                    # This will cascade delete: repositories, github_installation, and all related data
                    logger.info(f"Deleting workspace {workspace_id} as user is the only member")

                    # Manually delete orphaned BusinessIntentOverride records before workspace deletion
                    # These may have repository_id/pull_request_id set to repositories being deleted
                    from app.models.repository import Repository
                    from app.models.pull_request import PullRequestSnapshot
                    from app.models.artifact import RawArtifact
                    
                    repo_ids = [r.id for r in db.query(Repository).filter(Repository.workspace_id == workspace_id).all()]
                    if repo_ids:
                        # Delete pull request snapshots first to avoid cascade trigger
                        pr_ids = [pr.id for pr in db.query(PullRequestSnapshot).filter(
                            PullRequestSnapshot.repository_id.in_(repo_ids)
                        ).all()]
                        if pr_ids:
                            db.query(PullRequestSnapshot).filter(
                                PullRequestSnapshot.id.in_(pr_ids)
                            ).delete(synchronize_session=False)
                            db.flush()
                        
                        # Delete raw artifacts
                        artifact_ids = [ra.id for ra in db.query(RawArtifact).filter(
                            RawArtifact.repository_id.in_(repo_ids)
                        ).all()]
                        if artifact_ids:
                            db.query(RawArtifact).filter(
                                RawArtifact.id.in_(artifact_ids)
                            ).delete(synchronize_session=False)
                            db.flush()
                        
                        db.query(BusinessIntentOverride).filter(
                            BusinessIntentOverride.repository_id.in_(repo_ids)
                        ).delete(synchronize_session=False)
                        db.flush()

                    db.delete(workspace)
                else:
                    # Workspace has other members - only remove this user's membership
                    logger.info(f"Removing user membership from workspace {workspace_id}")
                    db.delete(membership)

        # Delete the user
        logger.info(f"Deleting user {user.id}")
        db.delete(user)
        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")
    finally:
        # Re-enable triggers after successful deletion or rollback
        try:
            db.execute(text("ALTER TABLE pull_request_snapshots ENABLE TRIGGER enforce_snapshot_immutability;"))
            db.execute(text("ALTER TABLE raw_artifacts ENABLE TRIGGER enforce_artifact_update_immutability;"))
            db.commit()
        except Exception as enable_err:
            logger.error(f"Failed to re-enable triggers in finally block: {enable_err}")
        # Restore guards
        immutability.bypass_immutability = False

    return {"status": "success", "message": "User deleted successfully"}
