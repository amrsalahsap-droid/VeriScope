import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationEngineerFeedback
)

logger = logging.getLogger(__name__)

class RecommendationEngineerFeedbackCapture:
    """
    RecommendationEngineerFeedbackCapture
    =====================================
    Captures human engineer feedback on recommendation relevance in an append-only,
    immutable timeline table to ensure audit logs, replayability, and lineage are preserved.
    """

    @classmethod
    def capture_feedback(
        cls,
        db: Session,
        recommendation_run_id: Any,
        feedback_type: str,
        feedback_text: Optional[str] = None,
        created_by: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> RecommendationEngineerFeedback:
        """
        Appends a new engineer feedback record for a specific RecommendationRun.
        
        Args:
            db: SQLAlchemy Session.
            recommendation_run_id: UUID or str of target RecommendationRun.
            feedback_type: str (USEFUL, NOT_USEFUL, MISSING_TESTS, TOO_MANY_TESTS, UNCLEAR_REASONING).
            feedback_text: Optional free-text notes.
            created_by: Optional identity/actor (e.g. username, github author).
            created_at: Optional timestamp of feedback creation.
            
        Returns:
            The created RecommendationEngineerFeedback record.
            
        Raises:
            ValueError: If lineage resolution fails due to missing RecommendationRun,
                        or if feedback_type is invalid.
        """
        # 1. Resolve RecommendationRun
        try:
            run_uuid = uuid.UUID(str(recommendation_run_id)) if not isinstance(recommendation_run_id, uuid.UUID) else recommendation_run_id
        except ValueError:
            raise ValueError(f"Lineage resolution failed: Invalid run UUID: '{recommendation_run_id}'.")
            
        run = db.query(RecommendationRun).filter(RecommendationRun.id == run_uuid).first()
        if not run:
            raise ValueError(
                f"Lineage resolution failed: No RecommendationRun exists with ID: '{recommendation_run_id}'."
            )
            
        # 2. Validate feedback_type (case-insensitive conversion)
        fb_type_clean = str(feedback_type).upper().strip().replace(" ", "_")
        
        VALID_FEEDBACK_TYPES = {
            "USEFUL",
            "NOT_USEFUL",
            "MISSING_TESTS",
            "TOO_MANY_TESTS",
            "UNCLEAR_REASONING"
        }
        
        if fb_type_clean not in VALID_FEEDBACK_TYPES:
            raise ValueError(
                f"Invalid feedback type: '{feedback_type}'. Must be one of {VALID_FEEDBACK_TYPES}."
            )
            
        # 3. Retrieve or instantiate parent RecommendationOutcome
        outcome = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == run.id
        ).first()
        
        if not outcome:
            # Instantiate default placeholder outcome record
            recommended_tcs = [t.test_case_id for t in run.tests]
            was_followed = fb_type_clean == "USEFUL"
            
            outcome = RecommendationOutcome(
                recommendation_run_id=run.id,
                repository_id=run.repository_id,
                pull_request_id=run.pull_request_id,
                recommendation_snapshot_hash=run.evidence_fingerprint or str(run.id),
                executed_tests=recommended_tcs,
                manually_added_tests=[],
                manually_removed_tests=[],
                was_followed=was_followed,
                override_reason=None if was_followed else "LOW_TRUST",
            )
            # Explicitly force outcome_status to ACKNOWLEDGED to prevent property setter overrides
            outcome.outcome_status = "ACKNOWLEDGED"
            db.add(outcome)
            db.flush()
        elif outcome.outcome_status == "PENDING":
            outcome.outcome_status = "ACKNOWLEDGED"
            
        # 4. Instantiate a brand new granular append-only feedback record (Rule 1 & Rule 2)
        feedback_record = RecommendationEngineerFeedback(
            id=uuid.uuid4(),
            recommendation_outcome_id=outcome.id,
            feedback_type=fb_type_clean,
            feedback_text=feedback_text,
            created_by=created_by,
            created_at=created_at or datetime.utcnow()
        )
        db.add(feedback_record)
        # Ensure ORM relationship caching remains perfectly consistent!
        outcome.feedbacks.append(feedback_record)
        
        # 5. Update denormalized outcome summary fields for compatibility (Rule 4 & Rule 5)
        # Avoid overriding alignment logic if outcome has custom alignment classification,
        # but preserve summary of the latest appended feedback in lowercase to match legacy lookups.
        summary_text = fb_type_clean.upper()
        if feedback_text:
            summary_text = f"{fb_type_clean.upper()}: {feedback_text}"
            
        summary_text_legacy = fb_type_clean.lower()
        if feedback_text:
            summary_text_legacy = f"{fb_type_clean.lower()}: {feedback_text}"
            
        outcome.engineer_feedback = summary_text
        outcome.feedback_legacy = summary_text_legacy
        
        db.commit()
        db.refresh(feedback_record)

        # Capture append-only snapshot evidence for auditing integrity (Rule 3 & Rule 4)
        from app.services.recommendation_outcome_evidence_integrity import RecommendationOutcomeEvidenceIntegrity
        RecommendationOutcomeEvidenceIntegrity.record_evidence(
            db=db,
            outcome_id=outcome.id,
            evidence_type="FEEDBACK",
            source_reference_id=str(feedback_record.id),
            payload={
                "feedback_type": fb_type_clean,
                "feedback_text": feedback_text,
                "created_by": created_by,
                "created_at": feedback_record.created_at
            }
        )
        
        logger.info(
            f"Successfully appended engineer feedback '{fb_type_clean}' for recommendation run {run.id} "
            f"(Outcome ID: {outcome.id}) by actor: {created_by}."
        )
        
        return feedback_record
