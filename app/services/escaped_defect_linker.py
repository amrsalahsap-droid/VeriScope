import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.pull_request import PullRequest
from app.models.recommendation import RecommendationRun, RecommendationOutcome, RecommendationReasoningEntry

logger = logging.getLogger(__name__)

class EscapedDefectLinker:
    """
    EscapedDefectLinker
    ====================
    Links production incidents and escaped defects back to recommendation outcomes.
    
    Lineage: Incident -> PullRequest -> RecommendationOutcome
    """
    
    @classmethod
    def link_incident(
        cls,
        db: Session,
        incident_data: Dict[str, Any],
        root_cause_linkage: Dict[str, Any],
        rollback_record: Optional[Dict[str, Any]] = None,
        deployment_outcome: Optional[Dict[str, Any]] = None
    ) -> RecommendationOutcome:
        """
        Links an incident and its associated metadata back to a RecommendationOutcome.
        
        Args:
            db: SQLAlchemy Session.
            incident_data: dict containing:
                - "id": str/UUID (Incident record ID)
                - "severity": str (e.g. "P0", "P1", "P2")
                - "timing": datetime (When it occurred)
                - "affected_modules": List[str] (Affected module file paths)
            root_cause_linkage: dict containing:
                - "pull_request_id": Optional[UUID/str]
                - "commit_sha": Optional[str]
                - "github_pr_number": Optional[int]
                - "confidence": str ("DIRECT", "INFERRED", "UNKNOWN")
            rollback_record: Optional dict containing:
                - "id": Optional[str/UUID] (Rollback record ID)
                - "rolled_back_at": Optional[datetime]
            deployment_outcome: Optional dict containing:
                - "id": Optional[str/UUID] (Deployment outcome ID)
                - "deployed_at": Optional[datetime]
                - "status": Optional[str] ("SUCCESS", "FAILED")
                
        Returns:
            The updated RecommendationOutcome record.
            
        Raises:
            ValueError: If linkage fails due to missing PullRequest, run, or outcome,
                        preserving deterministic lineage.
        """
        # Validate confidence level (Rule 2)
        confidence = root_cause_linkage.get("confidence", "UNKNOWN").upper()
        VALID_CONFIDENCES = {"DIRECT", "INFERRED", "UNKNOWN"}
        if confidence not in VALID_CONFIDENCES:
            confidence = "UNKNOWN"
            
        # Resolve target PullRequest (Rule 1)
        pr = None
        pr_id = root_cause_linkage.get("pull_request_id")
        commit_sha = root_cause_linkage.get("commit_sha")
        github_pr_number = root_cause_linkage.get("github_pr_number")
        
        if pr_id:
            try:
                pr_uuid = uuid.UUID(str(pr_id)) if not isinstance(pr_id, uuid.UUID) else pr_id
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
                f"pr_id={pr_id}, commit_sha={commit_sha}, github_pr_number={github_pr_number}."
            )
            
        # Find latest RecommendationRun for this PullRequest (Rule 1)
        run = db.query(RecommendationRun).filter(
            RecommendationRun.pull_request_id == pr.id
        ).order_by(RecommendationRun.created_at.desc()).first()
        
        if not run:
            raise ValueError(
                f"Lineage resolution failed: No RecommendationRun exists for PullRequest #{pr.number} (ID: {pr.id})."
            )
            
        # Retrieve or instantiate RecommendationOutcome (Rule 1 & Rule 5)
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
            
        # Check if this incident has already been linked to this outcome to prevent duplicates (idempotency / duplicate ingestion protection)
        from app.models.recommendation import RecommendationOutcomeEvidence
        existing_evidence = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome.id,
            RecommendationOutcomeEvidence.evidence_type == "INCIDENT",
            RecommendationOutcomeEvidence.source_reference_id == str(incident_data.get("id"))
        ).first()
        if existing_evidence:
            logger.info(f"Incident {incident_data.get('id')} already linked to outcome {outcome.id}. Skipping duplicate capture (idempotency).")
            return outcome
            
        # Transition outcome status to ESCAPED_DEFECT_LINKED (Rule 5)
        outcome.outcome_status = "ESCAPED_DEFECT_LINKED"
        outcome.escaped_defect_detected = True
        
        # Capture and update rollback linkage (Rule 4)
        if rollback_record:
            outcome.rollback_occurred = True
            
        # Set engineer feedback summary (Rule 4)
        feedback_summary = (
            f"Escaped Defect Linked [Confidence: {confidence} | Severity: {incident_data.get('severity', 'UNKNOWN')}]. "
            f"Incident ID: {incident_data.get('id')}. Severity: {incident_data.get('severity')}. "
            f"Affected Modules: {', '.join(incident_data.get('affected_modules', []))}."
        )
        outcome.engineer_feedback = feedback_summary
        
        # Serialize datetime objects inside nested structures to prevent JSON serialization errors
        serialized_rollback = None
        if rollback_record:
            serialized_rollback = {}
            for k, v in rollback_record.items():
                if isinstance(v, datetime):
                    serialized_rollback[k] = v.isoformat()
                else:
                    serialized_rollback[k] = v

        serialized_deployment = None
        if deployment_outcome:
            serialized_deployment = {}
            for k, v in deployment_outcome.items():
                if isinstance(v, datetime):
                    serialized_deployment[k] = v.isoformat()
                else:
                    serialized_deployment[k] = v

        # Persist forensic reasoning entry to preserve full lineage and metadata (Rule 1, Rule 2, Rule 3, Rule 4)
        metadata = {
            "incident_id": incident_data.get("id"),
            "incident_severity": incident_data.get("severity"),
            "escaped_defect_timing": incident_data.get("timing").isoformat() if isinstance(incident_data.get("timing"), datetime) else str(incident_data.get("timing")),
            "affected_modules": incident_data.get("affected_modules", []),
            "linkage_confidence": confidence,
            "rollback_linkage": serialized_rollback,
            "deployment_outcome": serialized_deployment,
            "causality_asserted": False,  # Rule 3: Never auto-claim causality
            "causal_disclaimer": "Forensic lineage link registered for audit and analytical calibration; causal relationship is NOT automatically asserted."
        }
        
        reasoning = RecommendationReasoningEntry(
            id=uuid.uuid4(),
            recommendation_run_id=run.id,
            reason_type="escaped_defect_linkage",
            source_entity=str(incident_data.get("id")),
            source_reference=f"PR #{pr.number}",
            human_readable_reason=(
                f"Incident '{incident_data.get('id')}' ({incident_data.get('severity')}) linked back to PR #{pr.number} "
                f"with {confidence} confidence. Affected files: {', '.join(incident_data.get('affected_modules', []))}. "
                f"Causal assertion: Correlation only, causality NOT auto-claimed."
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
            evidence_type="INCIDENT",
            source_reference_id=str(incident_data.get("id")),
            payload={
                "incident_data": incident_data,
                "root_cause_linkage": root_cause_linkage,
                "rollback_linkage": serialized_rollback,
                "deployment_outcome": serialized_deployment,
                "escaped_defect_detected": True
            }
        )
        
        logger.info(
            f"Successfully linked incident {incident_data.get('id')} to recommendation outcome of run {run.id} "
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
                    "EscapedDefectLinker: workspace_id not available on run %s — "
                    "skipping defect learning hook.",
                    run.id,
                )
        except Exception as _hook_exc:
            logger.error(
                "EscapedDefectLinker: EscapedDefectLearner hook failed (non-fatal) "
                "for outcome %s: %s",
                outcome.id,
                _hook_exc,
            )
        
        return outcome
