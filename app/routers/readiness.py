"""Recommendation Readiness API Endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from app.db.session import get_db
from app.models.user import Workspace, User
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.services.recommendation_readiness_service import RecommendationReadinessService
from app.schemas.readiness import (
    ReadinessAssessmentResponse,
    ReadinessAssessmentCreate,
    ReadinessSummaryResponse
)
from app.dependencies.auth import get_current_workspace, get_current_user

router = APIRouter(prefix="/readiness", tags=["readiness"])
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

async def optional_workspace(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[Workspace]:
    """Optional workspace authentication for development."""
    if not credentials:
        return None
    try:
        from app.dependencies.auth import get_current_workspace
        return await get_current_workspace(credentials, db)
    except:
        return None

async def optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Optional user authentication for development."""
    if not credentials:
        return None
    try:
        from app.dependencies.auth import get_current_user
        return await get_current_user(credentials, db)
    except:
        return None

@router.post("/assess", response_model=ReadinessAssessmentResponse, status_code=status.HTTP_201_CREATED)
def assess_readiness(
    assessment_request: ReadinessAssessmentCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Assess repository/PR readiness for recommendation generation.
    
    This endpoint evaluates the available signals and determines whether
    a useful recommendation can be generated.
    """
    # Verify repository belongs to workspace
    repository = db.query(Repository).filter(
        Repository.id == assessment_request.repository_id,
        Repository.workspace_id == workspace.id
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Verify pull request exists and belongs to repository if provided
    if assessment_request.pull_request_id:
        pull_request = db.query(PullRequest).filter(
            PullRequest.id == assessment_request.pull_request_id,
            PullRequest.repository_id == assessment_request.repository_id
        ).first()
        
        if not pull_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pull request not found"
            )
    
    # Perform readiness assessment
    service = RecommendationReadinessService(db)
    assessment = service.assess_readiness(
        repository_id=assessment_request.repository_id,
        pull_request_id=assessment_request.pull_request_id
    )
    
    return assessment

@router.get("/repositories/{repository_id}", response_model=ReadinessSummaryResponse)
def get_repository_readiness(
    repository_id: str,
    workspace: Optional[Workspace] = Depends(optional_workspace),
    db: Session = Depends(get_db)
):
    """Get current readiness status for a repository."""
    # Verify repository belongs to workspace if workspace is provided
    if workspace:
        repository = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.workspace_id == workspace.id
        ).first()
        
        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )
    else:
        # Development mode: allow without workspace
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )
    
    # Always create a fresh assessment to reflect latest state
    # This ensures readiness updates immediately after input changes
    service = RecommendationReadinessService(db)
    latest_assessment = service.assess_readiness(repository_id=repository_id)

    logger.info(f"Repository readiness assessment: repo_id={repository_id}, pr_id={latest_assessment.pull_request_id}, available_signals={latest_assessment.available_signals}, missing_signals={latest_assessment.missing_signals}")

    return ReadinessSummaryResponse(
        repository_id=str(latest_assessment.repository_id),
        pull_request_id=str(latest_assessment.pull_request_id) if latest_assessment.pull_request_id else None,
        readiness_level=latest_assessment.readiness_level,
        expected_confidence=latest_assessment.expected_confidence,
        readiness_score=latest_assessment.readiness_score,
        can_generate=latest_assessment.can_generate,
        can_generate_reason=latest_assessment.can_generate_reason,
        signal_count=len(latest_assessment.available_signals),
        total_signals=15,  # Total number of possible signals
        intelligence_completeness_score=latest_assessment.intelligence_completeness_score,
        release_confidence_ceiling=latest_assessment.release_confidence_ceiling,
        available_inputs=latest_assessment.available_inputs,
        missing_inputs=latest_assessment.missing_inputs,
        recommended_inputs=latest_assessment.recommended_inputs,
        blocking_inputs=latest_assessment.blocking_inputs,
        next_best_actions=latest_assessment.next_best_actions,
        primary_message=latest_assessment.primary_message,
        secondary_message=latest_assessment.secondary_message,
        confidence_reason=latest_assessment.confidence_reason,
        confidence_ceiling=latest_assessment.confidence_ceiling,
        confidence_blockers=latest_assessment.confidence_blockers,
        confidence_limiters=latest_assessment.confidence_limiters
    )

@router.get("/repositories/{repository_id}/pull-requests/{pull_request_id}", response_model=ReadinessSummaryResponse)
def get_pull_request_readiness(
    repository_id: str,
    pull_request_id: str,
    workspace: Optional[Workspace] = Depends(optional_workspace),
    db: Session = Depends(get_db)
):
    """Get current readiness status for a specific pull request."""
    # Verify repository belongs to workspace if workspace is provided
    if workspace:
        repository = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.workspace_id == workspace.id
        ).first()
        
        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )
    else:
        # Development mode: allow without workspace
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
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
    
    # Always create a fresh assessment to reflect latest state
    # This ensures readiness updates immediately after input changes
    service = RecommendationReadinessService(db)
    latest_assessment = service.assess_readiness(
        repository_id=repository_id,
        pull_request_id=pull_request_id
    )

    logger.info(f"PR readiness assessment: repo_id={repository_id}, pr_id={pull_request_id}, available_signals={latest_assessment.available_signals}, missing_signals={latest_assessment.missing_signals}")

    return ReadinessSummaryResponse(
        repository_id=str(latest_assessment.repository_id),
        pull_request_id=str(latest_assessment.pull_request_id) if latest_assessment.pull_request_id else None,
        readiness_level=latest_assessment.readiness_level,
        expected_confidence=latest_assessment.expected_confidence,
        readiness_score=latest_assessment.readiness_score,
        can_generate=latest_assessment.can_generate,
        can_generate_reason=latest_assessment.can_generate_reason,
        signal_count=len(latest_assessment.available_signals),
        total_signals=15,  # Total number of possible signals
        intelligence_completeness_score=latest_assessment.intelligence_completeness_score,
        release_confidence_ceiling=latest_assessment.release_confidence_ceiling,
        available_inputs=latest_assessment.available_inputs,
        missing_inputs=latest_assessment.missing_inputs,
        recommended_inputs=latest_assessment.recommended_inputs,
        blocking_inputs=latest_assessment.blocking_inputs,
        next_best_actions=latest_assessment.next_best_actions,
        primary_message=latest_assessment.primary_message,
        secondary_message=latest_assessment.secondary_message,
        confidence_reason=latest_assessment.confidence_reason,
        confidence_ceiling=latest_assessment.confidence_ceiling,
        confidence_blockers=latest_assessment.confidence_blockers,
        confidence_limiters=latest_assessment.confidence_limiters
    )

@router.get("/repositories/{repository_id}/assessments", response_model=List[ReadinessAssessmentResponse])
def get_repository_assessments(
    repository_id: str,
    limit: int = 10,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get recent readiness assessments for a repository."""
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
    
    # Get recent assessments
    from app.models.readiness import RecommendationReadinessAssessment
    
    assessments = db.query(RecommendationReadinessAssessment).filter(
        RecommendationReadinessAssessment.repository_id == repository_id
    ).order_by(RecommendationReadinessAssessment.created_at.desc()).limit(limit).all()
    
    service = RecommendationReadinessService(db)
    return [service.populate_assessment_fields(a) for a in assessments]

@router.get("/repositories/{repository_id}/pull-requests/{pull_request_id}/assessments", response_model=List[ReadinessAssessmentResponse])
def get_pull_request_assessments(
    repository_id: str,
    pull_request_id: str,
    limit: int = 5,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get recent readiness assessments for a specific pull request."""
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
    
    # Get recent assessments for PR
    from app.models.readiness import RecommendationReadinessAssessment
    
    assessments = db.query(RecommendationReadinessAssessment).filter(
        RecommendationReadinessAssessment.repository_id == repository_id,
        RecommendationReadinessAssessment.pull_request_id == pull_request_id
    ).order_by(RecommendationReadinessAssessment.created_at.desc()).limit(limit).all()
    
    service = RecommendationReadinessService(db)
    return [service.populate_assessment_fields(a) for a in assessments]
