"""Detailed Readiness API Endpoints for Frontend."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.models.user import Workspace
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.services.detailed_readiness_service import DetailedReadinessService
from app.schemas.readiness_detailed import DetailedReadinessResponse
from app.dependencies.auth import get_current_workspace

router = APIRouter(prefix="/api", tags=["readiness-detailed"])

@router.get("/repositories/{repository_id}/readiness", response_model=DetailedReadinessResponse)
def get_repository_readiness_detailed(
    repository_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get detailed readiness assessment for a repository."""
    # Verify repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Get detailed readiness assessment
    service = DetailedReadinessService(db)
    readiness = service.get_detailed_readiness(repository_id=repository_id)
    
    return readiness

@router.get("/repositories/{repository_id}/pull-requests/{pull_request_id}/readiness", response_model=DetailedReadinessResponse)
def get_pull_request_readiness_detailed(
    repository_id: str,
    pull_request_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get detailed readiness assessment for a specific pull request."""
    # Verify repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Verify pull request exists and belongs to repository
    pull_request = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    
    if not pull_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pull request not found"
        )
    
    # Get detailed readiness assessment
    service = DetailedReadinessService(db)
    readiness = service.get_detailed_readiness(
        repository_id=repository_id,
        pull_request_id=pull_request_id
    )
    
    return readiness
