"""
Outcome Learning API Router

Enforces workspace and repository isolation, expired/inactive role checks, and audit logging.
"""

import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.recommendation import RecommendationRun
from app.models.repository import Repository
from app.models.outcome_event import OutcomeEvent
from app.models.outcome_label import OutcomeLabel
from app.models.recommendation_outcome_summary import RecommendationOutcomeSummary
from app.services.outcome_learning_service import OutcomeLearningService
from app.services.governance_permission_service import GovernancePermissionService
from app.services.workspace_governance_audit_service import WorkspaceGovernanceAuditService
from app.schemas.outcome_learning import (
    OutcomeEventCreate, OutcomeEventResponse,
    OutcomeLabelCreate, OutcomeLabelResponse,
    RecommendationOutcomeSummaryResponse, WorkspaceOutcomeAnalyticsResponse
)


router = APIRouter(tags=["Outcome Learning"])


def verify_run_permission(db: Session, user_id: UUID, run_id: UUID, permission: str) -> RecommendationRun:
    """Helper to verify recommendation run exists and user has permission to access it."""
    run = db.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation run not found."
        )

    # Perform RBAC and isolation check
    permission_result = GovernancePermissionService.require_permission(
        db=db,
        user_id=user_id,
        permission=permission,
        workspace_id=run.workspace_id,
        repository_id=run.repository_id,
        actor_id=user_id
    )

    if not permission_result["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "You do not have permission to perform this governance action.",
                "permission_required": permission,
                "scope_checked": permission_result.get("scope_checked"),
                "reason": permission_result.get("reason"),
                "how_to_request_access": permission_result.get("how_to_request_access")
            }
        )

    return run


@router.post(
    "/api/recommendations/{recommendation_run_id}/outcomes/events",
    response_model=OutcomeEventResponse,
    status_code=status.HTTP_201_CREATED
)
def create_outcome_event(
    recommendation_run_id: UUID,
    event_in: OutcomeEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> OutcomeEventResponse:
    """Ingest outcome event linked to recommendation run. Enforces isolation and bulk_apply permissions."""
    run = verify_run_permission(db, current_user.id, recommendation_run_id, "governance.policy.bulk_apply")

    # Link the event manually to recommendation_run_id to satisfy URL parameter contract
    event_in.recommendation_run_id = recommendation_run_id
    event_in.pull_request_id = run.pull_request_id
    event_in.commit_sha = run.recommendation_snapshot_hash

    event = OutcomeLearningService.ingest_event(
        db=db,
        workspace_id=run.workspace_id,
        repository_id=run.repository_id,
        event_in=event_in,
        actor_user_id=current_user.id
    )

    return event


@router.get(
    "/api/recommendations/{recommendation_run_id}/outcomes",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK
)
def get_recommendation_outcomes(
    recommendation_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Retrieve all outcome events, labels, and the summary for a run. Enforces view permissions."""
    run = verify_run_permission(db, current_user.id, recommendation_run_id, "governance.policy.view")

    events = db.query(OutcomeEvent).filter(OutcomeEvent.recommendation_run_id == recommendation_run_id).all()
    labels = db.query(OutcomeLabel).filter(OutcomeLabel.recommendation_run_id == recommendation_run_id).all()
    summary = db.query(RecommendationOutcomeSummary).filter(
        RecommendationOutcomeSummary.recommendation_run_id == recommendation_run_id
    ).first()

    return {
        "events": [OutcomeEventResponse.model_validate(e) for e in events],
        "labels": [OutcomeLabelResponse.model_validate(l) for l in labels],
        "summary": RecommendationOutcomeSummaryResponse.model_validate(summary) if summary else None
    }


@router.post(
    "/api/recommendations/{recommendation_run_id}/outcomes/labels",
    response_model=OutcomeLabelResponse,
    status_code=status.HTTP_201_CREATED
)
def create_outcome_label(
    recommendation_run_id: UUID,
    label_in: OutcomeLabelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> OutcomeLabelResponse:
    """Create or update a manual outcome label. Enforces bulk_apply permissions."""
    run = verify_run_permission(db, current_user.id, recommendation_run_id, "governance.policy.bulk_apply")

    label = OutcomeLearningService.create_label(
        db=db,
        workspace_id=run.workspace_id,
        repository_id=run.repository_id,
        recommendation_run_id=recommendation_run_id,
        label_in=label_in,
        creator_id=current_user.id
    )

    return label


@router.get(
    "/api/repositories/{repository_id}/outcomes/summary",
    response_model=List[RecommendationOutcomeSummaryResponse],
    status_code=status.HTTP_200_OK
)
def get_repository_outcomes_summary(
    repository_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[RecommendationOutcomeSummaryResponse]:
    """List all recommendation outcome summaries for a repository. Enforces view permissions and repository isolation."""
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found."
        )

    # Perform RBAC and isolation check
    permission_result = GovernancePermissionService.require_permission(
        db=db,
        user_id=current_user.id,
        permission="governance.policy.view",
        workspace_id=repo.workspace_id,
        repository_id=repo.id,
        actor_id=current_user.id
    )

    if not permission_result["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "You do not have permission to perform this governance action.",
                "permission_required": "governance.policy.view",
                "scope_checked": permission_result.get("scope_checked"),
                "reason": permission_result.get("reason"),
                "how_to_request_access": permission_result.get("how_to_request_access")
            }
        )

    summaries = db.query(RecommendationOutcomeSummary).filter(
        RecommendationOutcomeSummary.repository_id == repository_id
    ).order_by(RecommendationOutcomeSummary.created_at.desc()).all()

    return summaries


@router.get(
    "/api/workspaces/{workspace_id}/outcomes/analytics",
    response_model=WorkspaceOutcomeAnalyticsResponse,
    status_code=status.HTTP_200_OK
)
def get_workspace_outcome_analytics(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> WorkspaceOutcomeAnalyticsResponse:
    """Calculate and return aggregate analytics metrics for the workspace. Enforces bulk_apply and owner/admin check."""
    # Check permissions and workspace isolation
    permission_result = GovernancePermissionService.require_permission(
        db=db,
        user_id=current_user.id,
        permission="governance.policy.bulk_apply",  # Only POLICY_ADMIN/GOVERNANCE_OWNER has this
        workspace_id=workspace_id,
        actor_id=current_user.id
    )

    if not permission_result["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "You do not have permission to perform this governance action.",
                "permission_required": "governance.policy.bulk_apply",
                "scope_checked": permission_result.get("scope_checked"),
                "reason": permission_result.get("reason"),
                "how_to_request_access": permission_result.get("how_to_request_access")
            }
        )

    # Log analytics viewed audit event
    WorkspaceGovernanceAuditService.log_outcome_learning_event(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        event_type="OUTCOME_ANALYTICS_VIEWED",
        reason="Workspace outcome analytics viewed successfully"
    )

    metrics = OutcomeLearningService.get_analytics(db, workspace_id)
    return WorkspaceOutcomeAnalyticsResponse(**metrics)
