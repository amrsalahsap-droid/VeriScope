import json
import hashlib
import uuid
import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.pilot import PilotReportSnapshot

logger = logging.getLogger("veriscope.pilot_roi_snapshot_generator")


class PilotROISnapshotGenerator:
    """
    PilotROISnapshotGenerator
    =========================
    Persists immutable, cryptographically verifiable, and replayable pilot snapshots.
    Generates deterministic SHA-256 hashes of sub-components using sorted-key
    JSON serialization to prevent tampering and ensure forensic replay safety.

    Rules enforced:
      1. Same evidence always produces the same snapshot hash.
      2. Deterministic serialization via json.dumps(..., sort_keys=True, separators=(",", ":")).
      3. Excluded data warnings, aggregation limitations, and confidence caveats
         are preserved inside the sub-payloads and therefore in the sub-hashes.
    """

    @classmethod
    def calculate_deterministic_hash(cls, data: Dict[str, Any]) -> str:
        """
        Convert any dictionary payload into a sorted, deterministic JSON string
        and compute its SHA-256 hash.
        """
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def _build_deterministic_hash_input(
        cls,
        metrics: Dict[str, Any],
        savings: Dict[str, Any],
        fragility: Dict[str, Any],
        trust: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        generation_version: int
    ) -> Dict[str, Any]:
        """
        Build the strictly deterministic payload that feeds the outer snapshot hash.

        `generated_at` is intentionally excluded so that re-running with identical
        evidence yields an identical hash (Rule 1).
        """
        aggregation_hash = cls.calculate_deterministic_hash(metrics)
        roi_hash = cls.calculate_deterministic_hash(savings)
        fragility_hash = cls.calculate_deterministic_hash(fragility)
        outcome_hash = cls.calculate_deterministic_hash(trust)

        return {
            "aggregation_snapshot_hash": aggregation_hash,
            "roi_snapshot_hash": roi_hash,
            "fragility_snapshot_hash": fragility_hash,
            "outcome_snapshot_hash": outcome_hash,
            "reporting_window": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "generation_version": generation_version
        }

    @classmethod
    def generate_snapshot_payload(
        cls,
        metrics: Dict[str, Any],
        savings: Dict[str, Any],
        fragility: Dict[str, Any],
        trust: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        generation_version: int = 1
    ) -> Dict[str, Any]:
        """
        Assemble the complete snapshot payload, preserving all excluded data
        warnings, aggregation limitations, confidence caveats, and cryptographically
        hashing sub-components.
        """
        deterministic_input = cls._build_deterministic_hash_input(
            metrics=metrics,
            savings=savings,
            fragility=fragility,
            trust=trust,
            start_date=start_date,
            end_date=end_date,
            generation_version=generation_version
        )

        generated_at_str = datetime.utcnow().isoformat()

        payload = {
            **deterministic_input,
            "generated_at": generated_at_str,
            "sub_payloads": {
                "metrics_aggregator": metrics,
                "savings_calculator": savings,
                "fragility_summary": fragility,
                "trust_metrics": trust
            }
        }
        return payload

    @classmethod
    def persist_snapshot(
        cls,
        db: Session,
        pilot_profile_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime,
        metrics: Dict[str, Any],
        savings: Dict[str, Any],
        fragility: Dict[str, Any],
        trust: Dict[str, Any],
        generation_version: int = 1
    ) -> PilotReportSnapshot:
        """
        Build, deterministically hash, and save the immutable snapshot record to the database.
        """
        # Compute the deterministic hash from evidence only (Rule 1)
        deterministic_input = cls._build_deterministic_hash_input(
            metrics=metrics,
            savings=savings,
            fragility=fragility,
            trust=trust,
            start_date=start_date,
            end_date=end_date,
            generation_version=generation_version
        )
        report_hash = cls.calculate_deterministic_hash(deterministic_input)

        # Build the full payload for storage (includes generated_at)
        generated_at = datetime.utcnow()
        full_payload = {
            **deterministic_input,
            "generated_at": generated_at.isoformat(),
            "sub_payloads": {
                "metrics_aggregator": metrics,
                "savings_calculator": savings,
                "fragility_summary": fragility,
                "trust_metrics": trust
            }
        }

        snapshot = PilotReportSnapshot(
            id=uuid.uuid4(),
            pilot_profile_id=pilot_profile_id,
            report_snapshot_hash=report_hash,
            report_version=generation_version,
            reporting_window_start=start_date,
            reporting_window_end=end_date,
            generated_at=generated_at,
            report_payload=full_payload
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        logger.info(
            f"Successfully persisted immutable report snapshot for pilot profile {pilot_profile_id} "
            f"(Snapshot ID: {snapshot.id}, Hash: {report_hash})."
        )
        return snapshot

    @classmethod
    def verify_snapshot_integrity(cls, db: Session, snapshot_id: uuid.UUID) -> Dict[str, Any]:
        """
        Replay and audit a finalized snapshot record to confirm its cryptographic hash matches.

        Returns a detailed audit dict rather than a bare bool so that downstream
        forensics can inspect exactly which sub-hash (if any) drifted.
        """
        snapshot = db.query(PilotReportSnapshot).filter(PilotReportSnapshot.id == snapshot_id).first()
        if not snapshot:
            raise ValueError(f"No PilotReportSnapshot exists with ID: {snapshot_id}.")

        payload = snapshot.report_payload

        # Rebuild deterministic hash input by stripping generated_at (same path as creation)
        deterministic_input = {k: v for k, v in payload.items() if k != "generated_at" and k != "sub_payloads"}
        calculated_hash = cls.calculate_deterministic_hash(deterministic_input)
        stored_hash = snapshot.report_snapshot_hash
        is_valid = calculated_hash == stored_hash

        # Audit sub-hashes if sub_payloads are present
        sub_hashes = {}
        sub_payloads = payload.get("sub_payloads", {})
        if sub_payloads:
            sub_hashes = {
                "aggregation": cls.calculate_deterministic_hash(sub_payloads.get("metrics_aggregator", {})),
                "roi": cls.calculate_deterministic_hash(sub_payloads.get("savings_calculator", {})),
                "fragility": cls.calculate_deterministic_hash(sub_payloads.get("fragility_summary", {})),
                "outcome": cls.calculate_deterministic_hash(sub_payloads.get("trust_metrics", {}))
            }

        stored_sub_hashes = {
            "aggregation": payload.get("aggregation_snapshot_hash"),
            "roi": payload.get("roi_snapshot_hash"),
            "fragility": payload.get("fragility_snapshot_hash"),
            "outcome": payload.get("outcome_snapshot_hash")
        }

        audit = {
            "snapshot_id": str(snapshot_id),
            "snapshot_recorded": True,
            "stored_snapshot_hash": stored_hash,
            "computed_snapshot_hash": calculated_hash,
            "integrity_verified": is_valid,
            "drift_detected": not is_valid,
            "sub_hashes_matched": {
                k: sub_hashes.get(k) == stored_sub_hashes.get(k)
                for k in ("aggregation", "roi", "fragility", "outcome")
            }
        }

        if is_valid:
            logger.info(f"Snapshot {snapshot_id} integrity verified. Forensic hash matches perfectly.")
        else:
            logger.error(
                f"Snapshot {snapshot_id} integrity violation! "
                f"Stored: '{stored_hash}', Computed: '{calculated_hash}'."
            )

        return audit
