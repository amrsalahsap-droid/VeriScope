"""
Manual Evidence Governance Service

Provides governance and trust controls for manual evidence executions.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from enum import Enum

from app.models.manual_evidence_review import ManualEvidenceReview
from app.models.manual_test_execution import ManualTestExecution
from app.models.repository import Repository


class GovernanceStatus(str, Enum):
    """Governance status for manual evidence."""
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHALLENGED = "CHALLENGED"
    EXPIRED = "EXPIRED"


class ManualEvidenceGovernanceService:
    """Service for managing manual evidence governance."""
    
    # Configuration
    MANUAL_EVIDENCE_EXPIRY_DAYS = 30
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_governance_status(
        self,
        execution_id: str,
        repository_id: str
    ) -> Dict[str, Any]:
        """
        Get the governance status of a manual evidence execution.
        
        Returns computed governance state including expiration check.
        """
        execution = self.db.query(ManualTestExecution).filter(
            ManualTestExecution.id == execution_id
        ).first()
        
        if not execution:
            return {
                "executionId": execution_id,
                "governanceStatus": GovernanceStatus.PENDING_REVIEW.value,
                "reviewerName": None,
                "reviewedAt": None,
                "reviewNote": None,
                "expiresAt": None,
                "isExpired": False,
                "error": "Execution not found"
            }
        
        # Get active review
        active_review = self.db.query(ManualEvidenceReview).filter(
            ManualEvidenceReview.manual_test_execution_id == execution_id,
            ManualEvidenceReview.repository_id == repository_id,
            ManualEvidenceReview.is_active == True
        ).first()
        
        # Compute expiration
        is_expired = self._is_expired(execution)
        expires_at = self._compute_expiry_date(execution)
        
        # Determine governance status
        if is_expired:
            governance_status = GovernanceStatus.EXPIRED
        elif active_review:
            governance_status = GovernanceStatus(active_review.review_status)
        else:
            governance_status = GovernanceStatus.PENDING_REVIEW
        
        return {
            "executionId": execution_id,
            "governanceStatus": governance_status.value,
            "reviewerName": active_review.reviewed_by_name if active_review else None,
            "reviewedAt": active_review.reviewed_at.isoformat() if active_review and active_review.reviewed_at else None,
            "reviewNote": active_review.review_note if active_review else None,
            "expiresAt": expires_at.isoformat() if expires_at else None,
            "isExpired": is_expired
        }
    
    def approve_execution(
        self,
        execution_id: str,
        repository_id: str,
        reviewer_id: str,
        reviewer_name: str,
        review_note: Optional[str] = None
    ) -> ManualEvidenceReview:
        """
        Approve a manual evidence execution.
        
        Creates a new governance review and deactivates any existing active review.
        """
        return self._create_review(
            execution_id=execution_id,
            repository_id=repository_id,
            status=GovernanceStatus.APPROVED,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            review_note=review_note
        )
    
    def reject_execution(
        self,
        execution_id: str,
        repository_id: str,
        reviewer_id: str,
        reviewer_name: str,
        review_note: str  # Required for rejection
    ) -> ManualEvidenceReview:
        """
        Reject a manual evidence execution.
        
        Requires a review note explaining the rejection.
        Creates a new governance review and deactivates any existing active review.
        """
        if not review_note or not review_note.strip():
            raise ValueError("Review note is required for rejection")
        
        return self._create_review(
            execution_id=execution_id,
            repository_id=repository_id,
            status=GovernanceStatus.REJECTED,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            review_note=review_note
        )
    
    def challenge_execution(
        self,
        execution_id: str,
        repository_id: str,
        reviewer_id: str,
        reviewer_name: str,
        review_note: str  # Required for challenge
    ) -> ManualEvidenceReview:
        """
        Challenge a manual evidence execution.
        
        Requires a review note explaining the challenge.
        Creates a new governance review and deactivates any existing active review.
        """
        if not review_note or not review_note.strip():
            raise ValueError("Review note is required for challenge")
        
        return self._create_review(
            execution_id=execution_id,
            repository_id=repository_id,
            status=GovernanceStatus.CHALLENGED,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            review_note=review_note
        )
    
    def get_repository_governance_summary(
        self,
        repository_id: str
    ) -> Dict[str, Any]:
        """
        Get a summary of governance states for all manual evidence in a repository.
        """
        all_reviews = self.db.query(ManualEvidenceReview).filter(
            ManualEvidenceReview.repository_id == repository_id,
            ManualEvidenceReview.is_active == True
        ).all()
        
        summary = {
            "total": len(all_reviews),
            "pending_review": 0,
            "approved": 0,
            "rejected": 0,
            "challenged": 0,
            "expired": 0
        }
        
        for review in all_reviews:
            execution = self.db.query(ManualTestExecution).filter(
                ManualTestExecution.id == review.manual_test_execution_id
            ).first()
            
            if execution and self._is_expired(execution):
                summary["expired"] += 1
            else:
                status = review.review_status
                if status == GovernanceStatus.PENDING_REVIEW.value:
                    summary["pending_review"] += 1
                elif status == GovernanceStatus.APPROVED.value:
                    summary["approved"] += 1
                elif status == GovernanceStatus.REJECTED.value:
                    summary["rejected"] += 1
                elif status == GovernanceStatus.CHALLENGED.value:
                    summary["challenged"] += 1
        
        return summary
    
    def _create_review(
        self,
        execution_id: str,
        repository_id: str,
        status: GovernanceStatus,
        reviewer_id: str,
        reviewer_name: str,
        review_note: Optional[str] = None
    ) -> ManualEvidenceReview:
        """
        Create a new governance review and deactivate any existing active review.
        """
        # Deactivate existing active review
        existing_active = self.db.query(ManualEvidenceReview).filter(
            ManualEvidenceReview.manual_test_execution_id == execution_id,
            ManualEvidenceReview.repository_id == repository_id,
            ManualEvidenceReview.is_active == True
        ).first()
        
        if existing_active:
            existing_active.is_active = False
            existing_active.updated_at = datetime.utcnow()
        
        # Create new review
        new_review = ManualEvidenceReview(
            manual_test_execution_id=execution_id,
            repository_id=repository_id,
            review_status=status.value,
            review_note=review_note,
            reviewed_by_id=reviewer_id,
            reviewed_by_name=reviewer_name,
            reviewed_at=datetime.utcnow(),
            is_active=True
        )
        
        self.db.add(new_review)
        self.db.commit()
        self.db.refresh(new_review)
        
        return new_review
    
    def _is_expired(self, execution: ManualTestExecution) -> bool:
        """
        Check if an execution is expired.
        
        An execution is expired if:
        - It is older than MANUAL_EVIDENCE_EXPIRY_DAYS
        - AND no newer execution exists for the same test case
        """
        if not execution.executed_at:
            return False
        
        expiry_date = execution.executed_at + timedelta(days=self.MANUAL_EVIDENCE_EXPIRY_DAYS)
        
        # Check if there's a newer execution for the same test case
        newer_execution = self.db.query(ManualTestExecution).filter(
            ManualTestExecution.external_test_case_id == execution.external_test_case_id,
            ManualTestExecution.executed_at > execution.executed_at
        ).first()
        
        # Expired if past expiry date AND no newer execution exists
        is_expired = datetime.utcnow() > expiry_date and newer_execution is None
        
        return is_expired
    
    def _compute_expiry_date(self, execution: ManualTestExecution) -> Optional[datetime]:
        """
        Compute the expiry date for an execution.
        """
        if not execution.executed_at:
            return None
        
        return execution.executed_at + timedelta(days=self.MANUAL_EVIDENCE_EXPIRY_DAYS)
    
    def is_trusted_for_risk_adjustment(
        self,
        execution_id: str,
        repository_id: str
    ) -> bool:
        """
        Check if manual evidence is trusted for risk adjustment.
        
        Only APPROVED and non-expired evidence is trusted.
        """
        governance_status = self.get_governance_status(execution_id, repository_id)
        return governance_status["governanceStatus"] == GovernanceStatus.APPROVED.value and not governance_status["isExpired"]
