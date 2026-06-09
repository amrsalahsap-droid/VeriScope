import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session, object_session

from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationTest,
    RecommendationReasoningEntry
)
from app.services.recommendation_ignore_detector import RecommendationIgnoreDetector

logger = logging.getLogger(__name__)

class RecommendationOutcomeClassifier:
    """
    RecommendationOutcomeClassifier
    ===============================
    Classifies final recommendation outcomes conservatively using priority ordering,
    overlap ratios, and override metrics, preventing tiny-repo/tiny-suite overfitting.
    """

    @classmethod
    def classify(cls, outcome: RecommendationOutcome, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Determine the final conservative classification status and associated metadata metrics.
        
        Args:
            outcome: RecommendationOutcome database record.
            db: Optional SQLAlchemy Session for fetching recommended tests reliably.
            
        Returns:
            Dict containing:
                - "classification_label": final classified status (ROLLBACK_LINKED, etc.)
                - "overlap_ratio": float
                - "override_ratio": float
                - "override_metrics": dict
                - "evidence": dict
                - "confidence_calibration": dict
                - "tiny_repo_overfitting_prevented": bool
        """
        # Resolve recommended tests reliably via session if relationship is not loaded
        session = db or object_session(outcome)
        rec_tests = set()
        
        if outcome.recommendation_run:
            rec_tests = set(outcome.recommended_tests)
        elif session:
            # Query recommended tests directly from db to ensure absolute accuracy
            tests = session.query(RecommendationTest).filter(
                RecommendationTest.recommendation_run_id == outcome.recommendation_run_id
            ).all()
            rec_tests = {t.test_case_id for t in tests}
        else:
            rec_tests = set(outcome.recommended_tests)

        exec_tests = set(outcome.executed_tests)
        manually_added = set(outcome.manually_added_tests or [])
        manually_removed = set(outcome.manually_removed_tests or [])

        total_recommended = len(rec_tests)
        total_executed = len(exec_tests)

        # 1. Calculate ratios & override metrics
        overlap_ratio = len(rec_tests & exec_tests) / max(total_recommended, 1)
        override_ratio = (len(manually_added) + len(manually_removed)) / max(total_recommended, 1)

        override_metrics = {
            "total_manually_added": len(manually_added),
            "total_manually_removed": len(manually_removed),
            "override_ratio": override_ratio
        }

        # 2. Heuristics for tiny suites (Rule 4: Avoid tiny-repo overfitting)
        is_tiny_suite = total_recommended < 5
        tiny_repo_overfitting_prevented = False

        # Identify overrides
        has_overrides = (
            len(manually_added) > 0 
            or len(manually_removed) > 0 
            or outcome.was_followed_legacy is False
            or outcome.override_reason is not None
        )

        # 3. Determine ignore status via RecommendationIgnoreDetector
        ignore_res = RecommendationIgnoreDetector.detect(rec_tests, exec_tests)
        is_ignored = ignore_res["status"] == "IGNORED"

        # 4. Priority-based Classification Label (Rule 2)
        label = "FOLLOWED"
        reason = "Recommendation followed with perfect developer alignment."

        if outcome.rollback_occurred:
            label = "ROLLBACK_LINKED"
            reason = "Rollback event was verifying linked to this recommendation run."
        elif outcome.escaped_defect or outcome.escaped_defect_detected:
            label = "ESCAPED_DEFECT_LINKED"
            reason = "Production incident or escaped defect linked back to this recommendation."
        elif has_overrides:
            # If tiny suite, check if we can prevent aggressive overfitting
            # We ONLY prevent overfitting if the developer did not explicitly override (was_followed = False)
            if is_tiny_suite and len(manually_added) == 0 and len(manually_removed) <= 1 and outcome.was_followed_legacy is not False:
                tiny_repo_overfitting_prevented = True
                label = "PARTIALLY_FOLLOWED"
                reason = "Tiny suite: Minor manual customization handled conservatively to avoid overfitting trust calibration."
            else:
                label = "OVERRIDDEN"
                reason = "Developer manual interventions (additions or removals) override default recommendation."
        elif is_ignored:
            label = "IGNORED"
            reason = "Recommendation ignored (zero or extremely minimal executed overlap)."
        elif exec_tests != rec_tests or overlap_ratio < 1.0:
            label = "PARTIALLY_FOLLOWED"
            reason = "Recommendation partially followed with partial execution overlap."

        # 5. Prevent aggressive confidence auto-upgrades (Rule 1)
        # We NEVER allow auto-upgrades. Downgrade if failures occurred, else hold.
        calibration_action = "HOLD"
        suggested_confidence = None
        if label in ("ROLLBACK_LINKED", "ESCAPED_DEFECT_LINKED"):
            calibration_action = "DOWNGRADE"
            suggested_confidence = "LOW"

        confidence_calibration = {
            "auto_upgrade_allowed": False,
            "action": calibration_action,
            "suggested_confidence_level": suggested_confidence,
            "disclaimer": "Confidence auto-upgrades strictly disallowed; calibration is subject to conservative bounds."
        }

        evidence = {
            "rollback_occurred": bool(outcome.rollback_occurred),
            "escaped_defect_detected": bool(outcome.escaped_defect or outcome.escaped_defect_detected),
            "has_manual_overrides": has_overrides,
            "is_ignored": is_ignored,
            "is_tiny_suite": is_tiny_suite,
            "reasoning": reason
        }

        return {
            "classification_label": label,
            "overlap_ratio": overlap_ratio,
            "override_ratio": override_ratio,
            "override_metrics": override_metrics,
            "evidence": evidence,
            "confidence_calibration": confidence_calibration,
            "tiny_repo_overfitting_prevented": tiny_repo_overfitting_prevented
        }

    @classmethod
    def classify_and_update(cls, db: Session, outcome: RecommendationOutcome) -> Dict[str, Any]:
        """
        Classifies the outcome and commits the status transition in the database,
        persisting reasoning timeline entries for deterministic replayability.
        
        Args:
            db: SQLAlchemy Session.
            outcome: RecommendationOutcome database record.
            
        Returns:
            The classification result dictionary.
        """
        res = cls.classify(outcome, db=db)
        outcome.outcome_status = res["classification_label"]

        # Persist a reasoning entry to make the classification lineage fully replayable (Rule 3)
        reasoning = RecommendationReasoningEntry(
            id=uuid.uuid4(),
            recommendation_run_id=outcome.recommendation_run_id,
            reason_type="outcome_classification",
            source_entity=str(outcome.id),
            source_reference=res["classification_label"],
            human_readable_reason=(
                f"Conservative classification settled on '{res['classification_label']}'. "
                f"Overlap ratio: {int(res['overlap_ratio'] * 100)}%. "
                f"Reason: {res['evidence']['reasoning']}"
            ),
            confidence_level="HIGH",
            evidence_priority="CRITICAL",
            reasoning_metadata=res,
            created_at=datetime.utcnow()
        )
        db.add(reasoning)
        
        db.commit()
        db.refresh(outcome)

        # Generate the immutable replayable outcome snapshot (Rule 1)
        from app.services.recommendation_outcome_snapshot import RecommendationOutcomeSnapshotService
        RecommendationOutcomeSnapshotService.create_snapshot(db, outcome.id)
        
        logger.info(
            f"Outcome {outcome.id} successfully classified as '{res['classification_label']}' "
            f"(Tiny-repo overfitting prevented: {res['tiny_repo_overfitting_prevented']})."
        )
        
        return res
