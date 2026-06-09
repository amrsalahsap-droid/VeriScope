import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.pull_request import PullRequest
from app.models.recommendation import RecommendationRun, RecommendationOutcome, RecommendationReasoningEntry

logger = logging.getLogger(__name__)

class RollbackOutcomeTracker:
    """
    RollbackOutcomeTracker
    ======================
    Tracks rollback-linked recommendation outcomes.
    
    Deterministic Lineage Path: Rollback -> Deployment -> PullRequest -> RecommendationOutcome
    """

    @classmethod
    def track_rollback(
        cls,
        db: Session,
        rollback_data: Dict[str, Any],
        pull_request_id: Optional[Any] = None,
        commit_sha: Optional[str] = None,
        github_pr_number: Optional[int] = None,
        deployment_data: Optional[Dict[str, Any]] = None
    ) -> RecommendationOutcome:
        """
        Links a rollback event and optional deployment back to a RecommendationOutcome.
        
        Args:
            db: SQLAlchemy Session.
            rollback_data: dict containing:
                - "id": Optional[str/UUID] (Rollback record ID)
                - "rolled_back_at": Optional[datetime/str] or "timing"
                - "trigger_reason": Optional[str]
                - "confidence": str ("DIRECT", "SUSPECTED", "UNKNOWN")
            pull_request_id: Optional UUID/str
            commit_sha: Optional str
            github_pr_number: Optional int
            deployment_data: Optional dict containing:
                - "id": Optional[str/UUID] (Deployment outcome ID)
                - "deployed_at": Optional[datetime/str]
                - "status": Optional[str]
                
        Returns:
            The updated RecommendationOutcome record.
            
        Raises:
            ValueError: If lineage resolution fails due to missing PullRequest or run,
                        or if confidence level is invalid, preserving deterministic lineage.
        """
        # Validate confidence level (Rule 4)
        confidence = rollback_data.get("confidence")
        if not confidence:
            confidence = "UNKNOWN"
        else:
            confidence = str(confidence).upper().strip()
            
        VALID_CONFIDENCES = {"DIRECT", "SUSPECTED", "UNKNOWN"}
        if confidence not in VALID_CONFIDENCES:
            raise ValueError(
                f"Invalid rollback confidence: '{confidence}'. Must be one of {VALID_CONFIDENCES}."
            )
            
        # Resolve target PullRequest (Rule 1)
        pr = None
        
        if pull_request_id:
            try:
                pr_uuid = uuid.UUID(str(pull_request_id)) if not isinstance(pull_request_id, uuid.UUID) else pull_request_id
                pr = db.query(PullRequest).filter(PullRequest.id == pr_uuid).first()
            except ValueError:
                pass
        
        if not pr and commit_sha:
            pr = db.query(PullRequest).filter(PullRequest.head_commit_sha == commit_sha).first()
            
        if not pr and github_pr_number:
            pr = db.query(PullRequest).filter(PullRequest.number == int(github_pr_number)).first()
            
        if not pr:
            raise ValueError(
                f"Lineage resolution failed: No PullRequest matches the provided linkage identifiers: "
                f"pull_request_id={pull_request_id}, commit_sha={commit_sha}, github_pr_number={github_pr_number}."
            )
            
        # Find latest RecommendationRun for this PullRequest (Rule 1)
        run = db.query(RecommendationRun).filter(
            RecommendationRun.pull_request_id == pr.id
        ).order_by(RecommendationRun.created_at.desc()).first()
        
        if not run:
            raise ValueError(
                f"Lineage resolution failed: No RecommendationRun exists for PullRequest #{pr.number} (ID: {pr.id})."
            )
            
        # Retrieve or instantiate RecommendationOutcome (Rule 1)
        outcome = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == run.id
        ).first()
        
        if not outcome:
            outcome = RecommendationOutcome(
                recommendation_run_id=run.id,
                repository_id=run.repository_id,
                pull_request_id=pr.id,
                recommendation_snapshot_hash=run.evidence_fingerprint or str(run.id),
                outcome_status="PENDING"
            )
            db.add(outcome)
            db.flush()
            
        rollback_id = rollback_data.get("id") or str(uuid.uuid4())

        # Check if this rollback has already been linked to this outcome to prevent duplicates (idempotency / duplicate ingestion protection)
        from app.models.recommendation import RecommendationOutcomeEvidence
        existing_evidence = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome.id,
            RecommendationOutcomeEvidence.evidence_type == "ROLLBACK",
            RecommendationOutcomeEvidence.source_reference_id == str(rollback_id)
        ).first()
        if existing_evidence:
            logger.info(f"Rollback {rollback_id} already linked to outcome {outcome.id}. Skipping duplicate capture (idempotency).")
            return outcome
            
        # Transition outcome status to ROLLBACK_LINKED and set rollback_occurred (Rule 5)
        outcome.outcome_status = "ROLLBACK_LINKED"
        outcome.rollback_occurred = True
        
        # Set engineer feedback summary (Rule 3 & Rule 4)
        trigger_reason = rollback_data.get("trigger_reason") or rollback_data.get("rollback_trigger_reason") or "UNKNOWN"
        rolled_back_at_val = rollback_data.get("rolled_back_at") or rollback_data.get("timing")
        
        feedback_summary = (
            f"Rollback Linked [Confidence: {confidence} | Reason: {trigger_reason}]. "
            f"Rollback ID: {rollback_id}. Triggered at: {rolled_back_at_val}."
        )
        outcome.engineer_feedback = feedback_summary
        
        # JSON Serialization Guard for datetime fields inside dictionary structures (Constraint Guard)
        serialized_rollback = {}
        for k, v in rollback_data.items():
            if isinstance(v, datetime):
                serialized_rollback[k] = v.isoformat()
            else:
                serialized_rollback[k] = v
        # Ensure rollback_id, trigger_reason, and confidence are cleanly defined in serialization
        if "id" not in serialized_rollback:
            serialized_rollback["id"] = rollback_id
        if "trigger_reason" not in serialized_rollback:
            serialized_rollback["trigger_reason"] = trigger_reason
        if "confidence" not in serialized_rollback:
            serialized_rollback["confidence"] = confidence

        serialized_deployment = None
        if deployment_data:
            serialized_deployment = {}
            for k, v in deployment_data.items():
                if isinstance(v, datetime):
                    serialized_deployment[k] = v.isoformat()
                else:
                    serialized_deployment[k] = v

        # Persist forensic reasoning entry to preserve full lineage and metadata (Rule 2 & Rule 3)
        metadata = {
            "rollback_id": rollback_id,
            "rolled_back_at": serialized_rollback.get("rolled_back_at") or serialized_rollback.get("timing"),
            "rollback_trigger_reason": trigger_reason,
            "linkage_confidence": confidence,
            "rollback_linkage": serialized_rollback,
            "deployment_outcome": serialized_deployment,
            "rollback_occurred": True
        }
        
        reasoning = RecommendationReasoningEntry(
            id=uuid.uuid4(),
            recommendation_run_id=run.id,
            reason_type="rollback_linkage",
            source_entity=str(rollback_id),
            source_reference=f"PR #{pr.number}",
            human_readable_reason=(
                f"Rollback '{rollback_id}' ({trigger_reason}) linked back to PR #{pr.number} "
                f"with {confidence} confidence."
            ),
            confidence_level=confidence,
            evidence_priority="CRITICAL",
            reasoning_metadata=metadata,
            created_at=datetime.utcnow()
        )
        db.add(reasoning)
        
        db.commit()
        db.refresh(outcome)

        # Capture append-only snapshot evidence for auditing integrity (Rule 3 & Rule 4)
        from app.services.recommendation_outcome_evidence_integrity import RecommendationOutcomeEvidenceIntegrity
        RecommendationOutcomeEvidenceIntegrity.record_evidence(
            db=db,
            outcome_id=outcome.id,
            evidence_type="ROLLBACK",
            source_reference_id=str(rollback_id),
            payload={
                "rollback_data": rollback_data,
                "pull_request_id": str(pull_request_id) if pull_request_id else None,
                "commit_sha": commit_sha,
                "github_pr_number": github_pr_number,
                "deployment_data": deployment_data,
                "rollback_occurred": True
            }
        )
        
        logger.info(
            f"Successfully linked rollback {rollback_id} to recommendation outcome of run {run.id} "
            f"(PR #{pr.number}) with confidence {confidence}."
        )
        
        # ------------------------------------------------------------------ #
        # Strengthen knowledge-graph edges for the missed-test gap (non-fatal) #
        # ------------------------------------------------------------------ #
        try:
            from app.services.escaped_defect_learner import EscapedDefectLearner
            workspace_id = getattr(run, "workspace_id", None)
            if workspace_id:
                EscapedDefectLearner.learn_from_outcome(
                    db=db,
                    outcome=outcome,
                    workspace_id=workspace_id,
                )
            else:
                logger.warning(
                    "RollbackOutcomeTracker: workspace_id not available on run %s — "
                    "skipping defect learning hook.",
                    run.id,
                )
        except Exception as _hook_exc:
            logger.error(
                "RollbackOutcomeTracker: EscapedDefectLearner hook failed (non-fatal) "
                "for outcome %s: %s",
                outcome.id,
                _hook_exc,
            )
        
        return outcome
