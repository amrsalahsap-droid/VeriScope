import uuid
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.recommendation import (
    RecommendationOutcome,
    RecommendationOutcomeSnapshot,
    RecommendationOutcomeEvidence
)

logger = logging.getLogger(__name__)

class RecommendationOutcomeSnapshotService:
    """
    RecommendationOutcomeSnapshotService
    ====================================
    Persists and audits immutable, replayable outcome snapshots of recommendation runs,
    enforcing deterministic JSON serialization and anti-tamper verification.
    """

    @classmethod
    def calculate_sub_hashes(cls, outcome: RecommendationOutcome) -> Dict[str, Any]:
        """
        Calculate deterministic SHA-256 hashes of all outcome sub-structures.
        
        Uses strictly deterministic JSON serialization:
        json.dumps(..., sort_keys=True, separators=(",", ":"))
        """
        # 1. Recommendation Snapshot Hash
        recommendation_snapshot_hash = outcome.recommendation_snapshot_hash or "legacy_hash"

        # 2. Fragility Snapshot Hash
        fragility_snapshot_hash = outcome.fragility_snapshot_hash

        # 3. Executed Test Snapshot Hash (Sorted list of stable identities)
        test_payload = {
            "executed_tests": sorted(outcome.executed_tests or []),
            "manually_added_tests": sorted(outcome.manually_added_tests or []),
            "manually_removed_tests": sorted(outcome.manually_removed_tests or [])
        }
        test_str = json.dumps(test_payload, sort_keys=True, separators=(",", ":"))
        executed_test_snapshot_hash = hashlib.sha256(test_str.encode("utf-8")).hexdigest()

        # 4. Incident Snapshot Hash (Sorted by incident ID for determinism)
        incident_evs = [ev.evidence_payload for ev in outcome.evidences if ev.evidence_type == "INCIDENT"]
        if incident_evs:
            sorted_incidents = sorted(incident_evs, key=lambda x: str(x.get("incident_data", {}).get("id", "")))
            inc_str = json.dumps(sorted_incidents, sort_keys=True, separators=(",", ":"))
            incident_snapshot_hash = hashlib.sha256(inc_str.encode("utf-8")).hexdigest()
        else:
            incident_snapshot_hash = None

        # 5. Rollback Snapshot Hash (Sorted by rollback ID for determinism)
        rollback_evs = [ev.evidence_payload for ev in outcome.evidences if ev.evidence_type == "ROLLBACK"]
        if rollback_evs:
            sorted_rollbacks = sorted(rollback_evs, key=lambda x: str(x.get("rollback_data", {}).get("id", "")))
            roll_str = json.dumps(sorted_rollbacks, sort_keys=True, separators=(",", ":"))
            rollback_snapshot_hash = hashlib.sha256(roll_str.encode("utf-8")).hexdigest()
        else:
            rollback_snapshot_hash = None

        # 6. Classification Snapshot Hash
        class_payload = {
            "outcome_status": outcome.outcome_status,
            "was_followed_legacy": outcome.was_followed_legacy,
            "override_reason": outcome.override_reason,
            "feedback": outcome.feedback
        }
        class_str = json.dumps(class_payload, sort_keys=True, separators=(",", ":"))
        classification_snapshot_hash = hashlib.sha256(class_str.encode("utf-8")).hexdigest()

        # 7. Combined Full Outcome Snapshot Hash
        full_payload = {
            "recommendation_snapshot_hash": recommendation_snapshot_hash,
            "fragility_snapshot_hash": fragility_snapshot_hash,
            "executed_test_snapshot_hash": executed_test_snapshot_hash,
            "incident_snapshot_hash": incident_snapshot_hash,
            "rollback_snapshot_hash": rollback_snapshot_hash,
            "classification_snapshot_hash": classification_snapshot_hash,
            "snapshot_version": 1
        }
        full_str = json.dumps(full_payload, sort_keys=True, separators=(",", ":"))
        outcome_snapshot_hash = hashlib.sha256(full_str.encode("utf-8")).hexdigest()

        return {
            "outcome_snapshot_hash": outcome_snapshot_hash,
            "recommendation_snapshot_hash": recommendation_snapshot_hash,
            "fragility_snapshot_hash": fragility_snapshot_hash,
            "executed_test_snapshot_hash": executed_test_snapshot_hash,
            "incident_snapshot_hash": incident_snapshot_hash,
            "rollback_snapshot_hash": rollback_snapshot_hash,
            "classification_snapshot_hash": classification_snapshot_hash
        }

    @classmethod
    def create_snapshot(cls, db: Session, outcome_id: uuid.UUID) -> RecommendationOutcomeSnapshot:
        """
        Build and persist a new immutable RecommendationOutcomeSnapshot.
        
        Args:
            db: SQLAlchemy Session.
            outcome_id: UUID of the target RecommendationOutcome.
            
        Returns:
            The created RecommendationOutcomeSnapshot.
        """
        # Ensure outcome exists
        outcome = db.query(RecommendationOutcome).filter(RecommendationOutcome.id == outcome_id).first()
        if not outcome:
            raise ValueError(f"RecommendationOutcome with ID {outcome_id} not found.")

        # If a snapshot already exists, return it (enforces unique snapshot per outcome)
        existing = db.query(RecommendationOutcomeSnapshot).filter(
            RecommendationOutcomeSnapshot.recommendation_outcome_id == outcome_id
        ).first()
        if existing:
            logger.info(f"Snapshot already exists for outcome {outcome_id}. Returning existing snapshot.")
            return existing

        # Compute deterministic hashes (Rule 2 & Rule 3)
        hashes = cls.calculate_sub_hashes(outcome)

        snapshot = RecommendationOutcomeSnapshot(
            id=uuid.uuid4(),
            recommendation_outcome_id=outcome_id,
            outcome_snapshot_hash=hashes["outcome_snapshot_hash"],
            recommendation_snapshot_hash=hashes["recommendation_snapshot_hash"],
            fragility_snapshot_hash=hashes["fragility_snapshot_hash"],
            executed_test_snapshot_hash=hashes["executed_test_snapshot_hash"],
            incident_snapshot_hash=hashes["incident_snapshot_hash"],
            rollback_snapshot_hash=hashes["rollback_snapshot_hash"],
            classification_snapshot_hash=hashes["classification_snapshot_hash"],
            generated_at=datetime.utcnow(),
            snapshot_version=1
        )

        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        logger.info(f"Successfully generated immutable outcome snapshot {snapshot.id} for outcome {outcome_id}.")
        return snapshot

    @classmethod
    def verify_snapshot_integrity(cls, db: Session, outcome_id: uuid.UUID) -> Dict[str, Any]:
        """
        Verify the integrity of a stored outcome snapshot against live/calculated evidence.
        
        Args:
            db: SQLAlchemy Session.
            outcome_id: UUID of the target RecommendationOutcome.
            
        Returns:
            Dict detailing the integrity audit.
        """
        outcome = db.query(RecommendationOutcome).filter(RecommendationOutcome.id == outcome_id).first()
        if not outcome:
            raise ValueError(f"RecommendationOutcome with ID {outcome_id} not found.")

        snapshot = db.query(RecommendationOutcomeSnapshot).filter(
            RecommendationOutcomeSnapshot.recommendation_outcome_id == outcome_id
        ).first()
        if not snapshot:
            return {
                "outcome_id": str(outcome_id),
                "snapshot_recorded": False,
                "integrity_verified": False,
                "error": "No snapshot exists for this recommendation outcome."
            }

        # Calculate current hashes from database state
        current_hashes = cls.calculate_sub_hashes(outcome)
        stored_hash = snapshot.outcome_snapshot_hash
        computed_hash = current_hashes["outcome_snapshot_hash"]

        drift_detected = (stored_hash != computed_hash)

        report = {
            "outcome_id": str(outcome_id),
            "snapshot_id": str(snapshot.id),
            "snapshot_recorded": True,
            "stored_snapshot_hash": stored_hash,
            "computed_snapshot_hash": computed_hash,
            "drift_detected": drift_detected,
            "sub_hashes_matched": {
                "recommendation": snapshot.recommendation_snapshot_hash == current_hashes["recommendation_snapshot_hash"],
                "fragility": snapshot.fragility_snapshot_hash == current_hashes["fragility_snapshot_hash"],
                "executed_tests": snapshot.executed_test_snapshot_hash == current_hashes["executed_test_snapshot_hash"],
                "incidents": snapshot.incident_snapshot_hash == current_hashes["incident_snapshot_hash"],
                "rollbacks": snapshot.rollback_snapshot_hash == current_hashes["rollback_snapshot_hash"],
                "classification": snapshot.classification_snapshot_hash == current_hashes["classification_snapshot_hash"]
            }
        }

        if drift_detected:
            logger.error(
                f"Outcome Snapshot Integrity Drift Detected for outcome {outcome_id}! "
                f"Stored: '{stored_hash}', Computed: '{computed_hash}'."
            )
        else:
            logger.info(f"Outcome Snapshot Integrity verified successfully for outcome {outcome_id}.")

        return report
