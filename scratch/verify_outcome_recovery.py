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
    RecommendationReasoningEntry
)
from app.services.recommendation_outcome_recovery import RecommendationOutcomeRecoveryService
from app.services.recommendation_outcome_snapshot import RecommendationOutcomeSnapshotService

def cleanup_database():
    """Clean up DB before and after testing."""
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationOutcomeSnapshot).delete()
        db.query(RecommendationOutcomeEvidence).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationRun).delete()
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
    print("STARTING RECOMMENDATION OUTCOME RECOVERY VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # Seed structures
        org = Organization(id=org_id, name="Recovery Labs", slug="recovery-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=343434,
            name="recovery-core",
            full_name="recovery-labs/recovery-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=620000,
            number=620,
            title="PR 620 - Recovery Target",
            author="engineer-recovery",
            source_branch="recovery-dev",
            target_branch="main",
            state="open",
            additions=15,
            deletions=4,
            changed_files_count=1,
            head_commit_sha="pr_620_head",
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
            pr_id="pr_620_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Recovery test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Baseline: Create outcome in FOLLOWED state
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

        # Generate snapshot
        snapshot = RecommendationOutcomeSnapshotService.create_snapshot(db, outcome.id)
        assert snapshot is not None

        # Add INCIDENT evidence (but stored status is FOLLOWED)
        evidence = RecommendationOutcomeEvidence(
            id=uuid.uuid4(),
            recommendation_outcome_id=outcome.id,
            evidence_type="INCIDENT",
            source_reference_id="INC-RECOV-222",
            evidence_payload={
                "incident_data": {"id": "INC-RECOV-222", "severity": "P0"},
                "root_cause_linkage": {"pull_request_id": str(pr_id), "confidence": "DIRECT"},
                "escaped_defect_detected": True
            },
            evidence_fingerprint="mock_fingerprint",
            created_at=datetime.datetime.utcnow()
        )
        db.add(evidence)
        db.commit()

        print("--- TEST 1: Replay and Repair Outcome Classification ---")
        # Run replay classification with apply_repair=True
        rep_report = RecommendationOutcomeRecoveryService.replay_outcome_classification(db, outcome.id, apply_repair=True)
        assert rep_report["drift_detected"] is True
        assert rep_report["repaired"] is True
        assert rep_report["replayed_status"] == "ESCAPED_DEFECT_LINKED"
        assert rep_report["stored_status"] == "ESCAPED_DEFECT_LINKED"

        # Verify outcome status was repaired in DB
        db.refresh(outcome)
        assert outcome.outcome_status == "ESCAPED_DEFECT_LINKED"
        print("[PASSED] Replay and repair successfully corrected outcome status based on chronological evidence!\n")

        print("--- TEST 2: Rebuild Outcome Snapshot (Force-Rebuild Bypass) ---")
        # Rebuilding snapshot without force should fail due to drift (since outcome status has changed but snapshot hash represents FOLLOWED)
        reb_report = RecommendationOutcomeRecoveryService.rebuild_outcome_snapshot(db, outcome.id, force=False)
        assert reb_report["snapshot_exists"] is True
        assert reb_report["drift_detected"] is True
        assert reb_report["action"] == "NO_ACTION_REQUIRED_FORCE"

        # Rebuilding snapshot with force=True should bypass deletion check, recreate snapshot, and update the hash!
        reb_report_force = RecommendationOutcomeRecoveryService.rebuild_outcome_snapshot(db, outcome.id, force=True)
        assert reb_report_force["snapshot_exists"] is True
        assert reb_report_force["action"] == "FORCE_REBUILT_SNAPSHOT"
        assert reb_report_force["snapshot_hash"] != snapshot.outcome_snapshot_hash
        print("[PASSED] Rebuild outcome snapshot successfully bypassed immutability safety and force-rebuilt the snapshot!\n")

        print("--- TEST 3: Repair Broken Lineage (Backfill References) ---")
        # Simulate broken lineage by nullifying pull_request_id
        outcome.pull_request_id = None
        db.commit()
        db.refresh(outcome)

        assert outcome.pull_request_id is None

        # Repair broken lineage
        rep_lineage_report = RecommendationOutcomeRecoveryService.repair_broken_lineage(db, outcome.id)
        assert "pull_request_id" in rep_lineage_report["repaired_fields"]
        
        # Verify it was backfilled
        db.refresh(outcome)
        assert outcome.pull_request_id == pr_id
        print("[PASSED] Repair broken lineage successfully backfilled stale/missing references!\n")

        print("--- TEST 4: Repair Broken Lineage (Restore Evidence from Reasoning) ---")
        # Create a reasoning entry indicating a linked incident, but delete the evidence record
        reasoning = RecommendationReasoningEntry(
            id=uuid.uuid4(),
            recommendation_run_id=run.id,
            reason_type="escaped_defect_linkage",
            source_entity="INC-RECOV-333",
            source_reference=f"PR #620",
            human_readable_reason="Incident linked back to PR with DIRECT confidence",
            confidence_level="DIRECT",
            evidence_priority="CRITICAL",
            reasoning_metadata={
                "incident_severity": "P0",
                "escaped_defect_timing": datetime.datetime.utcnow().isoformat(),
                "affected_modules": ["auth/jwt.py"]
            },
            created_at=datetime.datetime.utcnow()
        )
        db.add(reasoning)
        db.commit()

        # Delete all INCIDENT evidence
        db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome.id,
            RecommendationOutcomeEvidence.evidence_type == "INCIDENT"
        ).delete()
        db.commit()

        # Verify no INCIDENT evidence exists
        ev_count = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome.id,
            RecommendationOutcomeEvidence.evidence_type == "INCIDENT"
        ).count()
        assert ev_count == 0

        # Repair broken lineage
        rep_ev_report = RecommendationOutcomeRecoveryService.repair_broken_lineage(db, outcome.id)
        assert rep_ev_report["evidence_recreated_count"] == 1
        
        # Verify evidence was restored from reasoning entry metadata!
        restored_ev = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome.id,
            RecommendationOutcomeEvidence.evidence_type == "INCIDENT",
            RecommendationOutcomeEvidence.source_reference_id == "INC-RECOV-333"
        ).first()

        assert restored_ev is not None
        assert restored_ev.evidence_payload["incident_data"]["severity"] == "P0"
        assert restored_ev.evidence_payload["root_cause_linkage"]["confidence"] == "DIRECT"
        print("[PASSED] Repair broken lineage successfully restored missing evidence payloads from reasoning audit logs!\n")

    finally:
        db.close()

    print("======================================================================")
    print("ALL RECOMMENDATION OUTCOME RECOVERY CHECKS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
