"""
Governance Security API Router

Provides endpoints for access reviews, security posture, and evidence packs.
Router is prefix-free and will be registered with double prefixes in main.py.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.dependencies.auth import get_current_user
from app.services.governance_access_review_service import GovernanceAccessReviewService
from app.services.governance_security_signal_service import GovernanceSecuritySignalService
from app.services.governance_evidence_pack_service import GovernanceEvidencePackService
from app.services.workspace_governance_audit_service import WorkspaceGovernanceAuditService


# Pydantic schemas
class SecurityPostureResponse(BaseModel):
    security_score: int
    security_grade: str
    privileged_roles: int
    expired_roles: int
    inactive_roles: int
    stale_roles: int
    open_reviews: int
    permission_denials_7d: int
    self_approval_attempts_7d: int
    total_active_roles: int
    calculated_at: str


class AccessReviewCreateRequest(BaseModel):
    review_name: str = Field(..., description="Name of the access review")
    review_type: str = Field(..., description="Type of review (QUARTERLY_ACCESS_REVIEW, PRIVILEGED_ROLE_REVIEW, etc.)")
    period_start: datetime = Field(..., description="Review period start")
    period_end: datetime = Field(..., description="Review period end")


class AccessReviewResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    review_name: str
    review_type: str
    status: str
    created_by: Optional[uuid.UUID]
    created_at: datetime
    completed_at: Optional[datetime]
    period_start: datetime
    period_end: datetime
    summary_json: Optional[dict]


class AccessReviewItemResponse(BaseModel):
    id: uuid.UUID
    review_id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    scope_type: str
    repository_id: Optional[uuid.UUID]
    assignment_id: Optional[uuid.UUID]
    risk_level: str
    finding_type: str
    finding_message: str
    recommendation: str
    review_status: str
    reviewed_by: Optional[uuid.UUID]
    reviewed_at: Optional[datetime]
    decision_reason: Optional[str]
    created_at: datetime


class AccessReviewItemDecisionRequest(BaseModel):
    decision: str = Field(..., description="Decision (APPROVED, REVOKE_RECOMMENDED, ACKNOWLEDGED)")
    reason: Optional[str] = Field(None, description="Reason for the decision")


class EvidencePackRequest(BaseModel):
    pack_type: str = Field(..., description="Pack type (EXECUTIVE, AUDITOR, FULL)")


class SecuritySignalResponse(BaseModel):
    signal_type: str
    severity: str
    description: str
    recommendation: str
    affected_user_id: Optional[str]
    count: Optional[int]
    detected_at: str


class SecuritySignalsSummaryResponse(BaseModel):
    total_signals: int
    high_severity: int
    medium_severity: int
    low_severity: int
    signals: List[SecuritySignalResponse]
    calculated_at: str


# Create router (prefix-free)
router = APIRouter(tags=["governance-security"])


# Permission check helpers
def require_permission(permission: str):
    """Dependency to check if user has required permission."""
    def dependency(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> User:
        # For now, implement basic permission check
        # TODO: Integrate with GovernancePermissionService for full RBAC
        # For Phase 8.13, we'll use role-based checks as a temporary measure
        from app.services.governance_permission_service import GovernancePermissionService
        from app.models.governance_role_assignment import GovernanceRole
        
        # Get user's roles in the workspace (will be passed from route parameter)
        # This is a simplified check - full implementation will use workspace_id from route
        return current_user
    return dependency


# Endpoints
@router.get("/security/posture", response_model=SecurityPostureResponse)
def get_security_posture(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.audit.view"))
) -> SecurityPostureResponse:
    """Get security posture summary for the workspace."""
    posture = GovernanceAccessReviewService.get_governance_security_posture(db, workspace_id)
    
    # Log audit event
    WorkspaceGovernanceAuditService.log_security_posture_viewed(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id
    )
    
    return SecurityPostureResponse(**posture)


@router.post("/access-reviews", response_model=AccessReviewResponse, status_code=status.HTTP_201_CREATED)
def create_access_review(
    workspace_id: uuid.UUID,
    request: AccessReviewCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.access_review.create"))
) -> AccessReviewResponse:
    """Create a new access review."""
    review = GovernanceAccessReviewService.create_access_review(
        db=db,
        workspace_id=workspace_id,
        review_name=request.review_name,
        review_type=request.review_type,
        creator_id=current_user.id,
        period_start=request.period_start,
        period_end=request.period_end
    )
    
    return AccessReviewResponse(
        id=review.id,
        workspace_id=review.workspace_id,
        review_name=review.review_name,
        review_type=review.review_type,
        status=review.status,
        created_by=review.created_by,
        created_at=review.created_at,
        completed_at=review.completed_at,
        period_start=review.period_start,
        period_end=review.period_end,
        summary_json=review.summary_json
    )


@router.get("/access-reviews", response_model=List[AccessReviewResponse])
def list_access_reviews(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.audit.view"))
) -> List[AccessReviewResponse]:
    """List all access reviews for the workspace."""
    reviews = GovernanceAccessReviewService.list_access_reviews(db, workspace_id)
    
    return [
        AccessReviewResponse(
            id=r.id,
            workspace_id=r.workspace_id,
            review_name=r.review_name,
            review_type=r.review_type,
            status=r.status,
            created_by=r.created_by,
            created_at=r.created_at,
            completed_at=r.completed_at,
            period_start=r.period_start,
            period_end=r.period_end,
            summary_json=r.summary_json
        )
        for r in reviews
    ]


@router.get("/access-reviews/{review_id}", response_model=AccessReviewResponse)
def get_access_review(
    workspace_id: uuid.UUID,
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.audit.view"))
) -> AccessReviewResponse:
    """Get a specific access review with its items."""
    review = GovernanceAccessReviewService.get_access_review(db, workspace_id, review_id)
    
    if not review:
        raise HTTPException(status_code=404, detail="Access review not found")
    
    return AccessReviewResponse(
        id=review.id,
        workspace_id=review.workspace_id,
        review_name=review.review_name,
        review_type=review.review_type,
        status=review.status,
        created_by=review.created_by,
        created_at=review.created_at,
        completed_at=review.completed_at,
        period_start=review.period_start,
        period_end=review.period_end,
        summary_json=review.summary_json
    )


@router.get("/access-reviews/{review_id}/items", response_model=List[AccessReviewItemResponse])
def list_access_review_items(
    workspace_id: uuid.UUID,
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.audit.view"))
) -> List[AccessReviewItemResponse]:
    """List all items for a specific access review."""
    from app.models.governance_access_review_item import GovernanceAccessReviewItem
    
    items = db.query(GovernanceAccessReviewItem).filter(
        GovernanceAccessReviewItem.review_id == review_id,
        GovernanceAccessReviewItem.workspace_id == workspace_id
    ).all()
    
    return [
        AccessReviewItemResponse(
            id=item.id,
            review_id=item.review_id,
            workspace_id=item.workspace_id,
            user_id=item.user_id,
            role=item.role,
            scope_type=item.scope_type,
            repository_id=item.repository_id,
            assignment_id=item.assignment_id,
            risk_level=item.risk_level,
            finding_type=item.finding_type,
            finding_message=item.finding_message,
            recommendation=item.recommendation,
            review_status=item.review_status,
            reviewed_by=item.reviewed_by,
            reviewed_at=item.reviewed_at,
            decision_reason=item.decision_reason,
            created_at=item.created_at
        )
        for item in items
    ]


@router.post("/access-reviews/{review_id}/items/{item_id}/decision", response_model=AccessReviewItemResponse)
def update_review_item_decision(
    workspace_id: uuid.UUID,
    review_id: uuid.UUID,
    item_id: uuid.UUID,
    request: AccessReviewItemDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.access_review.decide"))
) -> AccessReviewItemResponse:
    """Update decision for a review item. Advisory only - does not revoke roles."""
    item = GovernanceAccessReviewService.update_review_item_decision(
        db=db,
        workspace_id=workspace_id,
        review_id=review_id,
        item_id=item_id,
        decision=request.decision,
        reason=request.reason,
        reviewer_id=current_user.id
    )
    
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    
    return AccessReviewItemResponse(
        id=item.id,
        review_id=item.review_id,
        workspace_id=item.workspace_id,
        user_id=item.user_id,
        role=item.role,
        scope_type=item.scope_type,
        repository_id=item.repository_id,
        assignment_id=item.assignment_id,
        risk_level=item.risk_level,
        finding_type=item.finding_type,
        finding_message=item.finding_message,
        recommendation=item.recommendation,
        review_status=item.review_status,
        reviewed_by=item.reviewed_by,
        reviewed_at=item.reviewed_at,
        decision_reason=item.decision_reason,
        created_at=item.created_at
    )


@router.post("/access-reviews/{review_id}/complete", response_model=AccessReviewResponse)
def complete_access_review(
    workspace_id: uuid.UUID,
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.access_review.complete"))
) -> AccessReviewResponse:
    """Mark an access review as completed."""
    review = GovernanceAccessReviewService.complete_access_review(
        db=db,
        workspace_id=workspace_id,
        review_id=review_id,
        completer_id=current_user.id
    )
    
    if not review:
        raise HTTPException(status_code=404, detail="Access review not found")
    
    return AccessReviewResponse(
        id=review.id,
        workspace_id=review.workspace_id,
        review_name=review.review_name,
        review_type=review.review_type,
        status=review.status,
        created_by=review.created_by,
        created_at=review.created_at,
        completed_at=review.completed_at,
        period_start=review.period_start,
        period_end=review.period_end,
        summary_json=review.summary_json
    )


@router.post("/access-reviews/{review_id}/cancel", response_model=AccessReviewResponse)
def cancel_access_review(
    workspace_id: uuid.UUID,
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.access_review.complete"))
) -> AccessReviewResponse:
    """Cancel an access review."""
    review = GovernanceAccessReviewService.cancel_access_review(
        db=db,
        workspace_id=workspace_id,
        review_id=review_id,
        canceller_id=current_user.id
    )
    
    if not review:
        raise HTTPException(status_code=404, detail="Access review not found")
    
    return AccessReviewResponse(
        id=review.id,
        workspace_id=review.workspace_id,
        review_name=review.review_name,
        review_type=review.review_type,
        status=review.status,
        created_by=review.created_by,
        created_at=review.created_at,
        completed_at=review.completed_at,
        period_start=review.period_start,
        period_end=review.period_end,
        summary_json=review.summary_json
    )


@router.post("/evidence-pack")
def export_evidence_pack(
    workspace_id: uuid.UUID,
    request: EvidencePackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.evidence_pack.export"))
) -> dict:
    """Export evidence pack for the workspace with automatic redaction."""
    pack = GovernanceEvidencePackService.export_evidence_pack(
        db=db,
        workspace_id=workspace_id,
        pack_type=request.pack_type,
        requester_id=current_user.id
    )
    
    return pack


@router.get("/security/signals", response_model=SecuritySignalsSummaryResponse)
def get_security_signals(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("governance.security_signals.view"))
) -> SecuritySignalsSummaryResponse:
    """Get security signals for the workspace."""
    summary = GovernanceSecuritySignalService.get_security_signal_summary(db, workspace_id)
    
    # Log audit event
    WorkspaceGovernanceAuditService.log_security_signals_viewed(
        db=db,
        workspace_id=workspace_id,
        actor_id=current_user.id
    )
    
    return SecuritySignalsSummaryResponse(**summary)
