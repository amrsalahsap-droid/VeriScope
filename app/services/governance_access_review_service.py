"""
Governance Access Review Service

Provides access review creation, item generation, decision tracking,
and security posture calculation for workspace governance.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.governance_access_review import GovernanceAccessReview
from app.models.governance_access_review_item import GovernanceAccessReviewItem
from app.models.governance_role_assignment import GovernanceRoleAssignment, GovernanceRole, ScopeType
from app.models.workspace_governance_audit_event import WorkspaceGovernanceAuditEvent
from app.services.workspace_governance_audit_service import WorkspaceGovernanceAuditService


class GovernanceAccessReviewService:
    """Service for managing governance access reviews and security posture."""

    @staticmethod
    def create_access_review(
        db: Session,
        workspace_id: uuid.UUID,
        review_name: str,
        review_type: str,
        creator_id: uuid.UUID,
        period_start: datetime,
        period_end: datetime
    ) -> GovernanceAccessReview:
        """Create a new access review and generate review items."""
        review = GovernanceAccessReview(
            workspace_id=workspace_id,
            review_name=review_name,
            review_type=review_type,
            status="DRAFT",
            created_by=creator_id,
            period_start=period_start,
            period_end=period_end
        )
        db.add(review)
        db.commit()
        db.refresh(review)

        # Log audit event
        WorkspaceGovernanceAuditService.log_access_review_created(
            db=db,
            workspace_id=workspace_id,
            actor_id=creator_id,
            review_id=review.id,
            review_type=review_type
        )

        # Generate review items
        GovernanceAccessReviewService.generate_review_items(db, review)

        return review

    @staticmethod
    def generate_review_items(db: Session, review: GovernanceAccessReview) -> List[GovernanceAccessReviewItem]:
        """Analyze active roles and generate finding items."""
        items = []
        now = datetime.utcnow()

        # Get all active role assignments in the workspace
        assignments = db.query(GovernanceRoleAssignment).filter(
            GovernanceRoleAssignment.workspace_id == review.workspace_id,
            GovernanceRoleAssignment.is_active == True,
            or_(
                GovernanceRoleAssignment.expires_at.is_(None),
                GovernanceRoleAssignment.expires_at > now
            )
        ).all()

        for assignment in assignments:
            # Analyze each assignment for security findings
            findings = GovernanceAccessReviewService._analyze_assignment(db, assignment, review.workspace_id)

            for finding in findings:
                item = GovernanceAccessReviewItem(
                    review_id=review.id,
                    workspace_id=review.workspace_id,
                    user_id=assignment.user_id,
                    role=assignment.role.value,
                    scope_type=assignment.scope_type.value,
                    repository_id=assignment.repository_id,
                    assignment_id=assignment.id,
                    risk_level=finding["risk_level"],
                    finding_type=finding["finding_type"],
                    finding_message=finding["finding_message"],
                    recommendation=finding["recommendation"],
                    review_status="PENDING"
                )
                db.add(item)
                items.append(item)

        db.commit()
        return items

    @staticmethod
    def _analyze_assignment(
        db: Session,
        assignment: GovernanceRoleAssignment,
        workspace_id: uuid.UUID
    ) -> List[Dict[str, str]]:
        """Analyze a single role assignment for security findings."""
        findings = []
        now = datetime.utcnow()

        # Check for privileged roles
        if assignment.role in [
            GovernanceRole.GOVERNANCE_OWNER,
            GovernanceRole.POLICY_ADMIN,
            GovernanceRole.EXCEPTION_APPROVER
        ]:
            findings.append({
                "risk_level": "HIGH",
                "finding_type": "PRIVILEGED_ROLE",
                "finding_message": f"User has privileged role: {assignment.role.value}",
                "recommendation": "Review if this role is still necessary. Consider reducing scope."
            })

        # Check for expired roles
        if assignment.expires_at and assignment.expires_at < now:
            findings.append({
                "risk_level": "CRITICAL",
                "finding_type": "EXPIRED_ROLE",
                "finding_message": f"Role expired on {assignment.expires_at}",
                "recommendation": "Revoke expired role immediately"
            })

        # Check for stale roles (older than 90 days)
        if assignment.created_at < now - timedelta(days=90):
            findings.append({
                "risk_level": "MEDIUM",
                "finding_type": "STALE_ROLE",
                "finding_message": f"Role assigned over 90 days ago: {assignment.created_at}",
                "recommendation": "Review if role is still actively needed"
            })

        # Check for broad workspace access
        if assignment.scope_type == ScopeType.WORKSPACE and assignment.role in [
            GovernanceRole.REPOSITORY_POLICY_MANAGER
        ]:
            findings.append({
                "risk_level": "MEDIUM",
                "finding_type": "BROAD_WORKSPACE_ACCESS",
                "finding_message": "Repository policy manager has workspace scope",
                "recommendation": "Consider scoping to specific repositories"
            })

        # Check for self-approval risk
        if assignment.role == GovernanceRole.EXCEPTION_APPROVER:
            findings.append({
                "risk_level": "HIGH",
                "finding_type": "SELF_APPROVAL_RISK",
                "finding_message": "User can approve exceptions - review self-approval controls",
                "recommendation": "Ensure segregation of duties is enforced"
            })

        return findings

    @staticmethod
    def list_access_reviews(db: Session, workspace_id: uuid.UUID) -> List[GovernanceAccessReview]:
        """List all access reviews for a workspace."""
        return db.query(GovernanceAccessReview).filter(
            GovernanceAccessReview.workspace_id == workspace_id
        ).order_by(GovernanceAccessReview.created_at.desc()).all()

    @staticmethod
    def get_access_review(
        db: Session,
        workspace_id: uuid.UUID,
        review_id: uuid.UUID
    ) -> Optional[GovernanceAccessReview]:
        """Get a specific access review with its items."""
        return db.query(GovernanceAccessReview).filter(
            GovernanceAccessReview.id == review_id,
            GovernanceAccessReview.workspace_id == workspace_id
        ).first()

    @staticmethod
    def update_review_item_decision(
        db: Session,
        workspace_id: uuid.UUID,
        review_id: uuid.UUID,
        item_id: uuid.UUID,
        decision: str,
        reason: str,
        reviewer_id: uuid.UUID
    ) -> Optional[GovernanceAccessReviewItem]:
        """Update decision for a review item. Advisory only - does not revoke roles."""
        item = db.query(GovernanceAccessReviewItem).filter(
            GovernanceAccessReviewItem.id == item_id,
            GovernanceAccessReviewItem.review_id == review_id,
            GovernanceAccessReviewItem.workspace_id == workspace_id
        ).first()

        if not item:
            return None

        item.review_status = decision
        item.reviewed_by = reviewer_id
        item.reviewed_at = datetime.utcnow()
        item.decision_reason = reason

        db.commit()
        db.refresh(item)

        # Log audit event
        WorkspaceGovernanceAuditService.log_access_review_item_decided(
            db=db,
            workspace_id=workspace_id,
            actor_id=reviewer_id,
            review_id=review_id,
            item_id=item_id,
            decision=decision
        )

        return item

    @staticmethod
    def complete_access_review(
        db: Session,
        workspace_id: uuid.UUID,
        review_id: uuid.UUID,
        completer_id: uuid.UUID
    ) -> Optional[GovernanceAccessReview]:
        """Mark an access review as completed and compute summary."""
        review = db.query(GovernanceAccessReview).filter(
            GovernanceAccessReview.id == review_id,
            GovernanceAccessReview.workspace_id == workspace_id
        ).first()

        if not review:
            return None

        review.status = "COMPLETED"
        review.completed_at = datetime.utcnow()

        # Compute summary
        items = db.query(GovernanceAccessReviewItem).filter(
            GovernanceAccessReviewItem.review_id == review_id
        ).all()

        summary = {
            "total_items": len(items),
            "pending": len([i for i in items if i.review_status == "PENDING"]),
            "approved": len([i for i in items if i.review_status == "APPROVED"]),
            "revoke_recommended": len([i for i in items if i.review_status == "REVOKE_RECOMMENDED"]),
            "acknowledged": len([i for i in items if i.review_status == "ACKNOWLEDGED"]),
            "critical_findings": len([i for i in items if i.risk_level == "CRITICAL"]),
            "high_findings": len([i for i in items if i.risk_level == "HIGH"])
        }

        review.summary_json = summary
        db.commit()
        db.refresh(review)

        # Log audit event
        WorkspaceGovernanceAuditService.log_access_review_completed(
            db=db,
            workspace_id=workspace_id,
            actor_id=completer_id,
            review_id=review_id
        )

        return review

    @staticmethod
    def cancel_access_review(
        db: Session,
        workspace_id: uuid.UUID,
        review_id: uuid.UUID,
        canceller_id: uuid.UUID
    ) -> Optional[GovernanceAccessReview]:
        """Cancel an access review."""
        review = db.query(GovernanceAccessReview).filter(
            GovernanceAccessReview.id == review_id,
            GovernanceAccessReview.workspace_id == workspace_id
        ).first()

        if not review:
            return None

        review.status = "CANCELLED"
        db.commit()
        db.refresh(review)

        # Log audit event
        WorkspaceGovernanceAuditService.log_access_review_cancelled(
            db=db,
            workspace_id=workspace_id,
            actor_id=canceller_id,
            review_id=review_id
        )

        return review

    @staticmethod
    def get_governance_security_posture(
        db: Session,
        workspace_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Calculate security posture summary for a workspace. Advisory only."""
        now = datetime.utcnow()

        # Count active roles by type
        active_roles = db.query(GovernanceRoleAssignment).filter(
            GovernanceRoleAssignment.workspace_id == workspace_id,
            GovernanceRoleAssignment.is_active == True,
            or_(
                GovernanceRoleAssignment.expires_at.is_(None),
                GovernanceRoleAssignment.expires_at > now
            )
        ).all()

        privileged_count = len([r for r in active_roles if r.role in [
            GovernanceRole.GOVERNANCE_OWNER,
            GovernanceRole.POLICY_ADMIN,
            GovernanceRole.EXCEPTION_APPROVER
        ]])

        expired_count = db.query(GovernanceRoleAssignment).filter(
            GovernanceRoleAssignment.workspace_id == workspace_id,
            GovernanceRoleAssignment.expires_at < now
        ).count()

        inactive_count = db.query(GovernanceRoleAssignment).filter(
            GovernanceRoleAssignment.workspace_id == workspace_id,
            GovernanceRoleAssignment.is_active == False
        ).count()

        stale_count = len([r for r in active_roles if r.created_at < now - timedelta(days=90)])

        # Open reviews count
        open_reviews = db.query(GovernanceAccessReview).filter(
            GovernanceAccessReview.workspace_id == workspace_id,
            GovernanceAccessReview.status.in_(["DRAFT", "IN_PROGRESS"])
        ).count()

        # Recent permission denials (last 7 days)
        denial_cutoff = now - timedelta(days=7)
        permission_denials = db.query(WorkspaceGovernanceAuditEvent).filter(
            WorkspaceGovernanceAuditEvent.workspace_id == workspace_id,
            WorkspaceGovernanceAuditEvent.event_type == "GOVERNANCE_PERMISSION_DENIED",
            WorkspaceGovernanceAuditEvent.timestamp >= denial_cutoff
        ).count()

        # Self-approval attempts (last 7 days)
        self_approvals = db.query(WorkspaceGovernanceAuditEvent).filter(
            WorkspaceGovernanceAuditEvent.workspace_id == workspace_id,
            WorkspaceGovernanceAuditEvent.event_type == "GOVERNANCE_SELF_APPROVAL_BLOCKED",
            WorkspaceGovernanceAuditEvent.timestamp >= denial_cutoff
        ).count()

        # Calculate security score (0-100)
        score = 100
        score -= (expired_count * 20)  # Each expired role costs 20 points
        score -= (inactive_count * 10)  # Each inactive role costs 10 points
        score -= (stale_count * 5)  # Each stale role costs 5 points
        score -= (permission_denials * 2)  # Each denial costs 2 points
        score = max(0, min(100, score))

        # Map score to grade
        if score >= 90:
            grade = "A"
        elif score >= 80:
            grade = "B"
        elif score >= 70:
            grade = "C"
        elif score >= 60:
            grade = "D"
        else:
            grade = "F"

        return {
            "security_score": score,
            "security_grade": grade,
            "privileged_roles": privileged_count,
            "expired_roles": expired_count,
            "inactive_roles": inactive_count,
            "stale_roles": stale_count,
            "open_reviews": open_reviews,
            "permission_denials_7d": permission_denials,
            "self_approval_attempts_7d": self_approvals,
            "total_active_roles": len(active_roles),
            "calculated_at": now.isoformat()
        }
