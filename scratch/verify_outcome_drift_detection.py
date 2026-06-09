import os
import sys
import uuid
import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationOutcomeSnapshot,
    RecommendationOutcomeEvidence,
    RecommendationReasoningEntry,
    RecommendationTestOutcome
)
from app.models.test_result import TestCase
from app.services.recommendation_outcome_drift_detector import RecommendationOutcomeDriftDetector
from app.services.recommendation_outcome_snapshot import RecommendationOutcomeSnapshotService

def cleanup_database():
    """Clean up DB before and after testing."""
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationOutcomeSnapshot).delete()
        db.query(RecommendationOutcomeEvidence).delete()
        db.query(RecommendationTestOutcome).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationRun).delete()
        db.query(TestCase).delete()
        db.query(PullRequest).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("Database cleanup successful.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def run_verification():
    print("======================================================================")
    print("STARTING RECOMMENDATION OUTCOME DRIFT DETECTION VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # Seed basic structures
        org = Organization(id=org_id, name="Drift Detection Labs", slug="drift-detection-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=232323,
            name="drift-core",
            full_name="drift-detection-labs/drift-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=610000,
            number=610,
            title="PR 610 - Drift Target",
            author="engineer-drift",
            source_branch="drift-dev",
            target_branch="main",
            state="open",
            additions=5,
            deletions=1,
            changed_files_count=1,
            head_commit_sha="pr_610_head",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.commit()

        run = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_610_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Drift test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Baseline: Create clean outcome and snapshot
        outcome = RecommendationOutcome(
            recommendation_run_id=run.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run.id),
            outcome_status="FOLLOWED",
            executed_tests=[],
            manually_added_tests=[],
            was_followed=True
        )
        db.add(outcome)
        db.commit()
        db.refresh(outcome)

        snapshot = RecommendationOutcomeSnapshotService.create_snapshot(db, outcome.id)
        assert snapshot is not None

        # Verify no drift initially
        report_clean = RecommendationOutcomeDriftDetector.detect_outcome_drift(db, outcome.id)
        assert report_clean["drift_detected"] is False
        print("[PASSED] Baseline verified: no initial drift detected in clean outcome and snapshot.\n")

        print("--- TEST 1: Snapshot Mismatch ---")
        # Artificially alter the outcome status in the database to trigger a snapshot mismatch (e.g. bypass ORM check via direct SQL update, or just setting property without snapshot listener being triggered because listen is before_update, but let's just modify the outcome status using DB session updates)
        # Wait, if we change outcome status, it triggers event listener prevent_snapshot_mutation? No, the event listener is on RecommendationOutcomeSnapshot, not RecommendationOutcome. So RecommendationOutcome CAN be modified.
        outcome.outcome_status = "OVERRIDDEN"
        db.commit()
        db.refresh(outcome)

        report_mismatch = RecommendationOutcomeDriftDetector.detect_outcome_drift(db, outcome.id)
        assert report_mismatch["drift_detected"] is True
        assert "snapshot_mismatch" in report_mismatch["drift_types"]
        assert "classification_snapshot_hash_mismatch" in report_mismatch["details"]["snapshot_mismatch"]["mismatches"]
        print("[PASSED] Snapshot mismatch (hash drift) correctly detected and reported!\n")

        # Revert outcome status
        outcome.outcome_status = "FOLLOWED"
        db.commit()
        db.refresh(outcome)

        print("--- TEST 2: Missing Lineage (Classified but missing snapshot) ---")
        # Delete snapshot from DB using event removal for delete
        from sqlalchemy import event
        from app.models.recommendation import prevent_snapshot_deletion
        event.remove(RecommendationOutcomeSnapshot, "before_delete", prevent_snapshot_deletion)
        try:
            db.delete(snapshot)
            db.commit()
        finally:
            event.listen(RecommendationOutcomeSnapshot, "before_delete", prevent_snapshot_deletion)

        report_missing_snap = RecommendationOutcomeDriftDetector.detect_outcome_drift(db, outcome.id)
        assert report_missing_snap["drift_detected"] is True
        assert "missing_lineage" in report_missing_snap["drift_types"]
        assert "classified_outcome_missing_snapshot" in report_missing_snap["details"]["missing_lineage"]["details"]
        print("[PASSED] Missing snapshot lineage correctly detected and reported!\n")

        # Restore snapshot
        snapshot = RecommendationOutcomeSnapshotService.create_snapshot(db, outcome.id)

        print("--- TEST 3: Stale References ---")
        # Temporarily set pull_request_id to a non-existent UUID in session state
        original_pr_id = outcome.pull_request_id
        outcome.pull_request_id = uuid.uuid4()

        report_stale_ref = RecommendationOutcomeDriftDetector.detect_outcome_drift(db, outcome.id)
        assert report_stale_ref["drift_detected"] is True
        assert "stale_references" in report_stale_ref["drift_types"]
        assert "stale_pull_request_reference" in report_stale_ref["details"]["stale_references"]["details"]
        print("[PASSED] Stale reference correctly detected and reported!\n")

        # Restore original pr_id
        outcome.pull_request_id = original_pr_id
        db.commit()

        print("--- TEST 4: Chronological Replay Inconsistency ---")
        # Add a piece of INCIDENT evidence
        evidence = RecommendationOutcomeEvidence(
            id=uuid.uuid4(),
            recommendation_outcome_id=outcome.id,
            evidence_type="INCIDENT",
            source_reference_id="INC-DRIFT-111",
            evidence_payload={
                "incident_data": {"id": "INC-DRIFT-111", "severity": "P0"},
                "root_cause_linkage": {"pull_request_id": str(pr_id), "confidence": "DIRECT"},
                "escaped_defect_detected": True
            },
            evidence_fingerprint="mock_fingerprint",
            created_at=datetime.datetime.utcnow()
        )
        db.add(evidence)
        db.commit()

        # The stored outcome status is "FOLLOWED", but replaying will yield "ESCAPED_DEFECT_LINKED"
        # This is a classic chronological replay inconsistency drift!
        report_replay = RecommendationOutcomeDriftDetector.detect_outcome_drift(db, outcome.id)
        assert report_replay["drift_detected"] is True
        assert "replay_inconsistency" in report_replay["drift_types"]
        assert "ESCAPED_DEFECT_LINKED" in report_replay["details"]["replay_inconsistency"]["details"]
        print("[PASSED] Chronological replay inconsistency correctly detected and reported!\n")

    finally:
        db.close()

    print("======================================================================")
    print("ALL RECOMMENDATION OUTCOME DRIFT DETECTION CHECKS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
