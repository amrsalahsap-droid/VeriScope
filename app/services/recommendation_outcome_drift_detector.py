import uuid
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationOutcomeSnapshot,
    RecommendationOutcomeEvidence,
    RecommendationTestOutcome,
    RecommendationReasoningEntry
)
from app.models.test_result import TestCase
from app.services.recommendation_outcome_snapshot import RecommendationOutcomeSnapshotService
from app.services.recommendation_outcome_evidence_integrity import RecommendationOutcomeEvidenceIntegrity

logger = logging.getLogger("veriscope.recommendation_outcome_drift_detector")

class RecommendationOutcomeDriftDetector:
    """
    RecommendationOutcomeDriftDetector
    ==================================
    Detects semantic, integrity, reference, and replay drift within the 
    recommendation outcome lineage subsystem.
    """

    @classmethod
    def detect_outcome_drift(cls, db: Session, outcome_id: uuid.UUID) -> Dict[str, Any]:
        """
        Evaluate a single RecommendationOutcome for any signs of historical drift.
        """
        outcome = db.query(RecommendationOutcome).filter(RecommendationOutcome.id == outcome_id).first()
        if not outcome:
            raise ValueError(f"RecommendationOutcome with ID {outcome_id} not found.")

        drift_detected = False
        drift_types = []

        # 1. Snapshot Mismatch check
        snapshot_mismatch = {"drift_detected": False, "mismatches": []}
        snapshot = db.query(RecommendationOutcomeSnapshot).filter(
            RecommendationOutcomeSnapshot.recommendation_outcome_id == outcome_id
        ).first()

        if snapshot:
            try:
                # Recalculate live hashes from DB state
                current_hashes = RecommendationOutcomeSnapshotService.calculate_sub_hashes(outcome)
                
                if snapshot.outcome_snapshot_hash != current_hashes["outcome_snapshot_hash"]:
                    snapshot_mismatch["drift_detected"] = True
                    if snapshot.recommendation_snapshot_hash != current_hashes["recommendation_snapshot_hash"]:
                        snapshot_mismatch["mismatches"].append("recommendation_snapshot_hash_mismatch")
                    if snapshot.fragility_snapshot_hash != current_hashes["fragility_snapshot_hash"]:
                        snapshot_mismatch["mismatches"].append("fragility_snapshot_hash_mismatch")
                    if snapshot.executed_test_snapshot_hash != current_hashes["executed_test_snapshot_hash"]:
                        snapshot_mismatch["mismatches"].append("executed_test_snapshot_hash_mismatch")
                    if snapshot.incident_snapshot_hash != current_hashes["incident_snapshot_hash"]:
                        snapshot_mismatch["mismatches"].append("incident_snapshot_hash_mismatch")
                    if snapshot.rollback_snapshot_hash != current_hashes["rollback_snapshot_hash"]:
                        snapshot_mismatch["mismatches"].append("rollback_snapshot_hash_mismatch")
                    if snapshot.classification_snapshot_hash != current_hashes["classification_snapshot_hash"]:
                        snapshot_mismatch["mismatches"].append("classification_snapshot_hash_mismatch")
                    
                    if not snapshot_mismatch["mismatches"]:
                        snapshot_mismatch["mismatches"].append("full_outcome_snapshot_hash_mismatch")
            except Exception as e:
                snapshot_mismatch["drift_detected"] = True
                snapshot_mismatch["mismatches"].append(f"hash_calculation_failure: {str(e)}")
        
        if snapshot_mismatch["drift_detected"]:
            drift_detected = True
            drift_types.append("snapshot_mismatch")

        # 2. Missing Lineage check
        missing_lineage = {"drift_detected": False, "details": []}
        
        # Scenario A: Outcome is classified but has no snapshot
        if outcome.outcome_status != "PENDING" and not snapshot:
            missing_lineage["drift_detected"] = True
            missing_lineage["details"].append("classified_outcome_missing_snapshot")

        # Scenario B: Reasoning links indicate linked incidents or rollbacks but no matching evidence payload
        reasoning_links = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == outcome.recommendation_run_id,
            RecommendationReasoningEntry.reason_type.in_(["escaped_defect_linkage", "rollback_linkage"])
        ).all()

        for link in reasoning_links:
            etype = "INCIDENT" if link.reason_type == "escaped_defect_linkage" else "ROLLBACK"
            has_evidence = db.query(RecommendationOutcomeEvidence).filter(
                RecommendationOutcomeEvidence.recommendation_outcome_id == outcome_id,
                RecommendationOutcomeEvidence.evidence_type == etype,
                RecommendationOutcomeEvidence.source_reference_id == str(link.source_entity)
            ).first() is not None
            
            if not has_evidence:
                missing_lineage["drift_detected"] = True
                missing_lineage["details"].append(f"reasoning_link_missing_evidence_for_{etype.lower()}_{link.source_entity}")

        if missing_lineage["drift_detected"]:
            drift_detected = True
            drift_types.append("missing_lineage")

        # 3. Stale References check
        stale_references = {"drift_detected": False, "details": []}
        
        # Check pull request, repository, or recommendation run existence
        if outcome.repository_id:
            from app.models.repository import Repository
            repo_exists = db.query(Repository).filter(Repository.id == outcome.repository_id).first() is not None
            if not repo_exists:
                stale_references["drift_detected"] = True
                stale_references["details"].append("stale_repository_reference")
        
        if outcome.pull_request_id:
            from app.models.pull_request import PullRequest
            pr_exists = db.query(PullRequest).filter(PullRequest.id == outcome.pull_request_id).first() is not None
            if not pr_exists:
                stale_references["drift_detected"] = True
                stale_references["details"].append("stale_pull_request_reference")

        run_exists = db.query(RecommendationRun).filter(RecommendationRun.id == outcome.recommendation_run_id).first() is not None
        if not run_exists:
            stale_references["drift_detected"] = True
            stale_references["details"].append("stale_recommendation_run_reference")

        # Check for test outcomes referencing non-existent test cases
        test_outcomes = db.query(RecommendationTestOutcome).filter(
            RecommendationTestOutcome.recommendation_outcome_id == outcome_id
        ).all()
        for to in test_outcomes:
            tc_exists = db.query(TestCase).filter(TestCase.id == to.test_case_id).first() is not None
            if not tc_exists:
                stale_references["drift_detected"] = True
                stale_references["details"].append(f"stale_test_case_reference_for_id_{to.test_case_id}")

        if stale_references["drift_detected"]:
            drift_detected = True
            drift_types.append("stale_references")

        # 4. Replay Inconsistency check
        replay_inconsistency = {"drift_detected": False, "stored_status": outcome.outcome_status, "replayed_status": None, "details": None}
        
        # Only verify if we have append-only evidence to replay
        has_evidence = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome_id
        ).first() is not None

        if has_evidence:
            try:
                # Trigger replay and verify
                report = RecommendationOutcomeEvidenceIntegrity.replay_and_verify(db, outcome_id)
                replay_inconsistency["replayed_status"] = report["replayed_outcome_status"]
                if report["drift_detected"]:
                    replay_inconsistency["drift_detected"] = True
                    replay_inconsistency["details"] = "Replayed classification status does not match stored database outcome status."
            except Exception as e:
                replay_inconsistency["drift_detected"] = True
                replay_inconsistency["details"] = f"Replay execution failed: {str(e)}"
        
        if replay_inconsistency["drift_detected"]:
            drift_detected = True
            drift_types.append("replay_inconsistency")

        return {
            "outcome_id": str(outcome_id),
            "drift_detected": drift_detected,
            "drift_types": drift_types,
            "details": {
                "snapshot_mismatch": snapshot_mismatch,
                "missing_lineage": missing_lineage,
                "stale_references": stale_references,
                "replay_inconsistency": replay_inconsistency
            }
        }

    @classmethod
    def detect_repository_drift(cls, db: Session, repository_id: uuid.UUID) -> Dict[str, Any]:
        """
        Scan all recommendation outcomes in a repository to detect and catalog historical drift.
        Also detects missing lineage for runs that do not have outcome records.
        """
        # Scan outcomes
        outcomes = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.repository_id == repository_id
        ).all()

        drift_reports = []
        total_drifted = 0

        for outcome in outcomes:
            report = cls.detect_outcome_drift(db, outcome.id)
            if report["drift_detected"]:
                total_drifted += 1
                drift_reports.append(report)

        # Scan for runs missing outcomes
        runs_missing_outcomes = []
        runs_without_outcomes = db.query(RecommendationRun).outerjoin(RecommendationOutcome).filter(
            RecommendationRun.repository_id == repository_id,
            RecommendationOutcome.id == None
        ).all()

        for run in runs_without_outcomes:
            runs_missing_outcomes.append(str(run.id))

        total_runs_missing = len(runs_missing_outcomes)

        return {
            "repository_id": str(repository_id),
            "total_outcomes_scanned": len(outcomes),
            "total_outcomes_drifted": total_drifted,
            "total_runs_missing_outcomes": total_runs_missing,
            "drift_reports": drift_reports,
            "runs_missing_outcomes": runs_missing_outcomes,
            "drift_detected": (total_drifted > 0 or total_runs_missing > 0)
        }
