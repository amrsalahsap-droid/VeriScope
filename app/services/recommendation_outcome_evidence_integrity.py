import uuid
import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationOutcomeEvidence,
    RecommendationEngineerFeedback,
    RecommendationReasoningEntry
)
from app.services.recommendation_outcome_classifier import RecommendationOutcomeClassifier

logger = logging.getLogger(__name__)

class RecommendationOutcomeEvidenceIntegrity:
    """
    RecommendationOutcomeEvidenceIntegrity
    ======================================
    Guarantees replay-safe recommendation outcome lineage and prevents historical drift
    by saving append-only data snapshots and executing deterministic replays.
    """

    @classmethod
    def record_evidence(
        cls,
        db: Session,
        outcome_id: uuid.UUID,
        evidence_type: str,
        source_reference_id: str,
        payload: Dict[str, Any]
    ) -> RecommendationOutcomeEvidence:
        """
        Record a new piece of append-only evidence with its fingerprint hash.
        
        Args:
            db: SQLAlchemy Session.
            outcome_id: UUID of the target RecommendationOutcome.
            evidence_type: String classification of the evidence (TEST_RUN, INCIDENT, etc.).
            source_reference_id: Unique string reference of the source entity.
            payload: Snapshot dictionary of the source data.
            
        Returns:
            The created and persisted RecommendationOutcomeEvidence record.
        """
        # Ensure the outcome exists
        outcome = db.query(RecommendationOutcome).filter(RecommendationOutcome.id == outcome_id).first()
        if not outcome:
            raise ValueError(f"RecommendationOutcome with ID {outcome_id} not found.")

        # Serialize datetime and UUID objects inside payload to prevent JSON serialization errors
        serialized_payload = {}
        for k, v in payload.items():
            if isinstance(v, datetime):
                serialized_payload[k] = v.isoformat()
            elif isinstance(v, uuid.UUID):
                serialized_payload[k] = str(v)
            elif isinstance(v, dict):
                serialized_payload[k] = cls._serialize_dict(v)
            elif isinstance(v, list):
                serialized_payload[k] = cls._serialize_list(v)
            else:
                serialized_payload[k] = v

        # Compute stable sha256 fingerprint hash to detect drift
        payload_str = json.dumps(serialized_payload, sort_keys=True)
        raw_fingerprint = f"{evidence_type.upper()}:{source_reference_id}:{payload_str}"
        evidence_fingerprint = hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()

        # Check for duplicate evidence to enforce idempotency
        existing = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome_id,
            RecommendationOutcomeEvidence.evidence_type == evidence_type.upper(),
            RecommendationOutcomeEvidence.source_reference_id == source_reference_id,
            RecommendationOutcomeEvidence.evidence_fingerprint == evidence_fingerprint
        ).first()

        if existing:
            logger.info(
                f"Evidence of type {evidence_type} and reference {source_reference_id} "
                f"already exists for outcome {outcome_id}. Skipping duplicate capture."
            )
            return existing

        evidence = RecommendationOutcomeEvidence(
            id=uuid.uuid4(),
            recommendation_outcome_id=outcome_id,
            evidence_type=evidence_type.upper(),
            source_reference_id=source_reference_id,
            evidence_payload=serialized_payload,
            evidence_fingerprint=evidence_fingerprint,
            created_at=datetime.utcnow()
        )

        db.add(evidence)
        db.commit()
        db.refresh(evidence)

        logger.info(
            f"Successfully recorded append-only evidence {evidence.id} of type {evidence_type} "
            f"for outcome {outcome_id}."
        )

        return evidence

    @classmethod
    def replay_and_verify(cls, db: Session, outcome_id: uuid.UUID) -> Dict[str, Any]:
        """
        Reconstruct outcome lineage chronologically from append-only evidence payloads
        and assert that the replayed outcome classification matches the stored DB state.
        
        Args:
            db: SQLAlchemy Session.
            outcome_id: UUID of the target RecommendationOutcome.
            
        Returns:
            Dict detailing the replay audit results.
            
        Raises:
            ValueError: If the outcome does not exist, or if drift is detected.
        """
        outcome = db.query(RecommendationOutcome).filter(RecommendationOutcome.id == outcome_id).first()
        if not outcome:
            raise ValueError(f"RecommendationOutcome with ID {outcome_id} not found.")

        # Fetch all evidence in chronological order
        evidences = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome_id
        ).order_by(RecommendationOutcomeEvidence.created_at.asc()).all()

        # Reconstructed state variables
        executed_tests = set()
        manually_added_tests = set()
        manually_removed_tests = set()
        was_followed_legacy = None
        override_reason = None
        rollback_occurred = False
        escaped_defect_detected = False
        feedbacks = []

        # Chronological replay
        for ev in evidences:
            payload = ev.evidence_payload
            etype = ev.evidence_type

            if etype == "TEST_RUN":
                # Snapshot of a test run execution
                exec_tests = payload.get("executed_tests", [])
                added_tests = payload.get("manually_added_tests", [])
                removed_tests = payload.get("manually_removed_tests", [])

                executed_tests.update(exec_tests)
                manually_added_tests.update(added_tests)
                manually_removed_tests.update(removed_tests)

                if "was_followed" in payload:
                    was_followed_legacy = payload["was_followed"]
                if "override_reason" in payload:
                    override_reason = payload["override_reason"]

            elif etype == "INCIDENT":
                # Incident escaped defect linkage
                escaped_defect_detected = True
                
                # Check for nested rollbacks or deployments linked during incident tracking
                rollback_record = payload.get("rollback_linkage")
                if rollback_record or payload.get("rollback_occurred") or payload.get("rollback_record"):
                    rollback_occurred = True

            elif etype == "ROLLBACK":
                # Rollback outcome tracking
                rollback_occurred = True

            elif etype == "FEEDBACK":
                # Engineer feedback captured
                feedbacks.append({
                    "feedback_type": payload.get("feedback_type"),
                    "feedback_text": payload.get("feedback_text")
                })

            elif etype == "OVERRIDE":
                # Direct outcome manual overrides
                if "was_followed" in payload:
                    was_followed_legacy = payload["was_followed"]
                if "override_reason" in payload:
                    override_reason = payload["override_reason"]
                if "executed_tests" in payload:
                    executed_tests.update(payload["executed_tests"])
                if "manually_added_tests" in payload:
                    manually_added_tests.update(payload["manually_added_tests"])
                if "manually_removed_tests" in payload:
                    manually_removed_tests.update(payload["manually_removed_tests"])

        # Create transient mock outcome for re-running classifier
        replayed_outcome = RecommendationOutcome(
            recommendation_run_id=outcome.recommendation_run_id,
            repository_id=outcome.repository_id,
            pull_request_id=outcome.pull_request_id,
            recommendation_snapshot_hash=outcome.recommendation_snapshot_hash,
            fragility_snapshot_hash=outcome.fragility_snapshot_hash,
            outcome_status="PENDING",
            rollback_occurred=rollback_occurred,
            escaped_defect_detected=escaped_defect_detected,
            was_followed_legacy=was_followed_legacy,
            override_reason_legacy=override_reason
        )

        replayed_outcome.executed_tests_legacy = list(executed_tests)
        replayed_outcome.manually_added_tests_legacy = list(manually_added_tests)
        replayed_outcome.manually_removed_tests_legacy = list(manually_removed_tests)

        replayed_outcome.feedbacks = [
            RecommendationEngineerFeedback(
                feedback_type=fb["feedback_type"],
                feedback_text=fb.get("feedback_text")
            )
            for fb in feedbacks
        ]

        # Execute classifier classification on the replayed transient outcome
        res = RecommendationOutcomeClassifier.classify(replayed_outcome, db=db)
        replayed_status = res["classification_label"]

        # Check for historical drift between the replayed classification and stored status
        drift_detected = (replayed_status != outcome.outcome_status)

        report = {
            "outcome_id": str(outcome_id),
            "stored_outcome_status": outcome.outcome_status,
            "replayed_outcome_status": replayed_status,
            "drift_detected": drift_detected,
            "evidence_count": len(evidences),
            "reconstructed_executed_tests_count": len(executed_tests),
            "reconstructed_manually_added_count": len(manually_added_tests),
            "reconstructed_manually_removed_count": len(manually_removed_tests),
            "reconstructed_rollback_occurred": rollback_occurred,
            "reconstructed_escaped_defect_detected": escaped_defect_detected,
            "overlap_ratio": res["overlap_ratio"],
            "override_ratio": res["override_ratio"]
        }

        if drift_detected:
            msg = (
                f"Historical Drift Detected for outcome {outcome_id}! "
                f"Stored classification: '{outcome.outcome_status}', "
                f"but chronological evidence replay computed: '{replayed_status}'."
            )
            logger.error(msg)
            # Raise ValueError as per requirements to prevent silent degradation of auditing lineage
            raise ValueError(msg)

        logger.info(f"Deterministic replay completed successfully for outcome {outcome_id} (No drift detected).")
        return report

    @classmethod
    def _serialize_dict(cls, d: Dict[str, Any]) -> Dict[str, Any]:
        res = {}
        for k, v in d.items():
            if isinstance(v, datetime):
                res[k] = v.isoformat()
            elif isinstance(v, uuid.UUID):
                res[k] = str(v)
            elif isinstance(v, dict):
                res[k] = cls._serialize_dict(v)
            elif isinstance(v, list):
                res[k] = cls._serialize_list(v)
            else:
                res[k] = v
        return res

    @classmethod
    def _serialize_list(cls, l: List[Any]) -> List[Any]:
        res = []
        for v in l:
            if isinstance(v, datetime):
                res.append(v.isoformat())
            elif isinstance(v, uuid.UUID):
                res.append(str(v))
            elif isinstance(v, dict):
                res.append(cls._serialize_dict(v))
            elif isinstance(v, list):
                res.append(cls._serialize_list(v))
            else:
                res.append(v)
        return res

