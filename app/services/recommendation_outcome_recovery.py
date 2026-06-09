import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationOutcomeSnapshot,
    RecommendationOutcomeEvidence,
    RecommendationReasoningEntry,
    RecommendationEngineerFeedback,
    prevent_snapshot_deletion
)
from app.services.recommendation_outcome_classifier import RecommendationOutcomeClassifier
from app.services.recommendation_outcome_snapshot import RecommendationOutcomeSnapshotService
from app.services.recommendation_outcome_evidence_integrity import RecommendationOutcomeEvidenceIntegrity

logger = logging.getLogger("veriscope.recommendation_outcome_recovery")

class RecommendationOutcomeRecoveryService:
    """
    RecommendationOutcomeRecoveryService
    ====================================
    Provides administrative recovery tools to deterministic replay, rebuild, 
    and repair broken or drifted recommendation outcome lineages.
    """

    @classmethod
    def replay_outcome_classification(cls, db: Session, outcome_id: uuid.UUID, apply_repair: bool = False) -> Dict[str, Any]:
        """
        Chronologically replay evidence to determine the correct outcome status.
        If apply_repair is True, updates the stored DB outcome status to match replayed status.
        """
        outcome = db.query(RecommendationOutcome).filter(RecommendationOutcome.id == outcome_id).first()
        if not outcome:
            raise ValueError(f"RecommendationOutcome with ID {outcome_id} not found.")

        # Chronologically fetch evidence
        evidences = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome_id
        ).order_by(RecommendationOutcomeEvidence.created_at.asc()).all()

        executed_tests = set()
        manually_added_tests = set()
        manually_removed_tests = set()
        was_followed_legacy = None
        override_reason = None
        rollback_occurred = False
        escaped_defect_detected = False
        feedbacks = []

        for ev in evidences:
            payload = ev.evidence_payload
            etype = ev.evidence_type

            if etype == "TEST_RUN":
                executed_tests.update(payload.get("executed_tests", []))
                manually_added_tests.update(payload.get("manually_added_tests", []))
                manually_removed_tests.update(payload.get("manually_removed_tests", []))
                if "was_followed" in payload:
                    was_followed_legacy = payload["was_followed"]
                if "override_reason" in payload:
                    override_reason = payload["override_reason"]

            elif etype == "INCIDENT":
                escaped_defect_detected = True
                if payload.get("rollback_linkage") or payload.get("rollback_occurred"):
                    rollback_occurred = True

            elif etype == "ROLLBACK":
                rollback_occurred = True

            elif etype == "FEEDBACK":
                feedbacks.append({
                    "feedback_type": payload.get("feedback_type"),
                    "feedback_text": payload.get("feedback_text")
                })

            elif etype == "OVERRIDE":
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

        res = RecommendationOutcomeClassifier.classify(replayed_outcome, db=db)
        replayed_status = res["classification_label"]
        drift_detected = (replayed_status != outcome.outcome_status)
        repaired = False

        if drift_detected and apply_repair:
            outcome.outcome_status = replayed_status
            
            # Persist repair timeline entry
            reasoning = RecommendationReasoningEntry(
                id=uuid.uuid4(),
                recommendation_run_id=outcome.recommendation_run_id,
                reason_type="outcome_classification_replay_repair",
                source_entity=str(outcome.id),
                source_reference=replayed_status,
                human_readable_reason=(
                    f"Operational recovery replayed chronological evidence and repaired classification status "
                    f"from '{outcome.outcome_status}' to '{replayed_status}'."
                ),
                confidence_level="HIGH",
                evidence_priority="CRITICAL",
                reasoning_metadata={
                    "replayed_classification": res,
                    "previous_status": outcome.outcome_status,
                    "repaired_at": datetime.utcnow().isoformat()
                },
                created_at=datetime.utcnow()
            )
            db.add(reasoning)
            db.commit()
            db.refresh(outcome)
            repaired = True

            # Register System Observability Event
            from app.models.observability import SystemEvent
            sys_event = SystemEvent(
                id=uuid.uuid4(),
                entity_type="recommendation_outcome",
                entity_id=str(outcome.id),
                event_type="outcome_repair_replayed",
                payload={"outcome_id": str(outcome.id), "previous_status": res.get("previous_status"), "new_status": replayed_status},
                created_at=datetime.utcnow()
            )
            db.add(sys_event)
            db.commit()

        return {
            "outcome_id": str(outcome_id),
            "stored_status": outcome.outcome_status,
            "replayed_status": replayed_status,
            "drift_detected": drift_detected,
            "repaired": repaired,
            "evidence_count": len(evidences)
        }

    @classmethod
    def rebuild_outcome_snapshot(cls, db: Session, outcome_id: uuid.UUID, force: bool = False) -> Dict[str, Any]:
        """
        Builds a missing outcome snapshot or force-rebuilds an existing one
        by temporarily removing SQLAlchemy deletion safety checks.
        """
        outcome = db.query(RecommendationOutcome).filter(RecommendationOutcome.id == outcome_id).first()
        if not outcome:
            raise ValueError(f"RecommendationOutcome with ID {outcome_id} not found.")

        existing_snapshot = db.query(RecommendationOutcomeSnapshot).filter(
            RecommendationOutcomeSnapshot.recommendation_outcome_id == outcome_id
        ).first()

        action = "NO_ACTION"
        if not existing_snapshot:
            # Generate missing snapshot
            RecommendationOutcomeSnapshotService.create_snapshot(db, outcome_id)
            action = "CREATED_MISSING_SNAPSHOT"
        else:
            # Snapshot exists. Check drift.
            current_hashes = RecommendationOutcomeSnapshotService.calculate_sub_hashes(outcome)
            drift_detected = (existing_snapshot.outcome_snapshot_hash != current_hashes["outcome_snapshot_hash"])
            
            if drift_detected:
                if force:
                    # Administrative bypass of Forensic Immutability Constraints
                    event.remove(RecommendationOutcomeSnapshot, "before_delete", prevent_snapshot_deletion)
                    try:
                        db.delete(existing_snapshot)
                        db.commit()
                    finally:
                        # Re-register safety checks
                        event.listen(RecommendationOutcomeSnapshot, "before_delete", prevent_snapshot_deletion)
                    
                    # Create new snapshot
                    RecommendationOutcomeSnapshotService.create_snapshot(db, outcome_id)
                    action = "FORCE_REBUILT_SNAPSHOT"
                else:
                    return {
                        "outcome_id": str(outcome_id),
                        "snapshot_exists": True,
                        "drift_detected": True,
                        "action": "NO_ACTION_REQUIRED_FORCE",
                        "error": "Snapshot integrity drift detected, but force=True is required to bypass immutability guards."
                    }

        new_snapshot = db.query(RecommendationOutcomeSnapshot).filter(
            RecommendationOutcomeSnapshot.recommendation_outcome_id == outcome_id
        ).first()

        return {
            "outcome_id": str(outcome_id),
            "snapshot_id": str(new_snapshot.id) if new_snapshot else None,
            "snapshot_hash": new_snapshot.outcome_snapshot_hash if new_snapshot else None,
            "snapshot_exists": new_snapshot is not None,
            "action": action
        }

    @classmethod
    def repair_broken_lineage(cls, db: Session, outcome_id: uuid.UUID) -> Dict[str, Any]:
        """
        Repairs broken references and captures missing append-only evidence items
        from available Reasoning Entry logs.
        """
        outcome = db.query(RecommendationOutcome).filter(RecommendationOutcome.id == outcome_id).first()
        if not outcome:
            raise ValueError(f"RecommendationOutcome with ID {outcome_id} not found.")

        repaired_fields = []
        evidence_recreated_count = 0

        # 1. Backfill repository_id, pull_request_id from RecommendationRun
        run = db.query(RecommendationRun).filter(RecommendationRun.id == outcome.recommendation_run_id).first()
        if run:
            if not outcome.repository_id:
                outcome.repository_id = run.repository_id
                repaired_fields.append("repository_id")
            if not outcome.pull_request_id:
                outcome.pull_request_id = run.pull_request_id
                repaired_fields.append("pull_request_id")
            if not outcome.recommendation_snapshot_hash or outcome.recommendation_snapshot_hash == "legacy_hash":
                outcome.recommendation_snapshot_hash = run.evidence_fingerprint or str(run.id)
                repaired_fields.append("recommendation_snapshot_hash")

        if repaired_fields:
            db.commit()
            db.refresh(outcome)

        # 2. Check for missing evidence associated with reasoning entry links
        reasoning_links = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == outcome.recommendation_run_id,
            RecommendationReasoningEntry.reason_type.in_(["escaped_defect_linkage", "rollback_linkage"])
        ).all()

        for link in reasoning_links:
            etype = "INCIDENT" if link.reason_type == "escaped_defect_linkage" else "ROLLBACK"
            
            existing_evidence = db.query(RecommendationOutcomeEvidence).filter(
                RecommendationOutcomeEvidence.recommendation_outcome_id == outcome_id,
                RecommendationOutcomeEvidence.evidence_type == etype,
                RecommendationOutcomeEvidence.source_reference_id == str(link.source_entity)
            ).first()

            if not existing_evidence:
                # Reconstruct evidence payload from reasoning entry metadata
                metadata = link.reasoning_metadata or {}
                
                if etype == "INCIDENT":
                    payload = {
                        "incident_data": {
                            "id": link.source_entity,
                            "severity": metadata.get("incident_severity", "UNKNOWN"),
                            "timing": metadata.get("escaped_defect_timing", datetime.utcnow().isoformat()),
                            "affected_modules": metadata.get("affected_modules", [])
                        },
                        "root_cause_linkage": {
                            "pull_request_id": str(outcome.pull_request_id) if outcome.pull_request_id else None,
                            "confidence": link.confidence_level
                        },
                        "rollback_linkage": metadata.get("rollback_linkage"),
                        "deployment_outcome": metadata.get("deployment_outcome"),
                        "escaped_defect_detected": True
                    }
                else:  # ROLLBACK
                    payload = {
                        "rollback_data": {
                            "id": link.source_entity,
                            "rolled_back_at": metadata.get("rolled_back_at", datetime.utcnow().isoformat()),
                            "trigger_reason": metadata.get("rollback_trigger_reason", "UNKNOWN"),
                            "confidence": link.confidence_level
                        },
                        "pull_request_id": str(outcome.pull_request_id) if outcome.pull_request_id else None,
                        "deployment_data": metadata.get("deployment_outcome"),
                        "rollback_occurred": True
                    }

                # Record restored append-only evidence
                RecommendationOutcomeEvidenceIntegrity.record_evidence(
                    db=db,
                    outcome_id=outcome_id,
                    evidence_type=etype,
                    source_reference_id=str(link.source_entity),
                    payload=payload
                )
                evidence_recreated_count += 1

        return {
            "outcome_id": str(outcome_id),
            "repaired_fields": repaired_fields,
            "evidence_recreated_count": evidence_recreated_count,
            "lineage_fully_repaired": True
        }
