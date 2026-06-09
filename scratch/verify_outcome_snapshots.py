import os
import sys
import uuid
import datetime
import hashlib
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationTest,
    RecommendationOutcomeSnapshot,
    RecommendationReasoningEntry,
    RecommendationOutcomeEvidence,
    RecommendationEngineerFeedback
)
from app.services.recommendation_outcome_classifier import RecommendationOutcomeClassifier
from app.services.recommendation_outcome_snapshot import RecommendationOutcomeSnapshotService
from app.services.escaped_defect_linker import EscapedDefectLinker
from app.services.rollback_outcome_tracker import RollbackOutcomeTracker

def cleanup_database():
    """Clean up DB before and after testing."""
    from app.db.base import Base
    from app.db.session import engine
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
        
    db = SessionLocal()
    try:
        try:
            db.query(RecommendationOutcomeSnapshot).delete()
        except Exception:
            db.rollback()
        try:
            db.query(RecommendationOutcomeEvidence).delete()
        except Exception:
            db.rollback()
        db.query(RecommendationEngineerFeedback).delete()
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationTest).delete()
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
    print("STARTING RECOMMENDATION OUTCOME SNAPSHOT FORENSIC AUDIT VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    
    # Bootstrap DB schema if needed
    from app.db.base import Base
    from app.db.session import engine
    Base.metadata.create_all(bind=engine)

    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # 1. Seeding basic structures
        org = Organization(id=org_id, name="Snapshot Labs", slug="snapshot-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=838383,
            name="snapshot-core",
            full_name="snapshot-labs/snapshot-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=820000,
            number=820,
            title="PR 820 - Snapshot Verification",
            author="snapshot-auditor",
            source_branch="snapshot-dev",
            target_branch="main",
            state="open",
            additions=35,
            deletions=12,
            changed_files_count=1,
            head_commit_sha="pr_820_head",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.commit()

        # Seed RecommendationRun
        run = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_820_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Snapshot audit test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Seed recommended tests
        for i in range(4):
            rec_test = RecommendationTest(
                recommendation_run_id=run.id,
                test_case_id=f"test_snapshot_{i}",
                reason_type="historical_fragility",
                reason_details={},
                priority_score=0.8
            )
            db.add(rec_test)
        db.commit()

        # Create baseline outcome
        outcome = RecommendationOutcome(
            recommendation_run_id=run.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="run_snapshot_123",
            fragility_snapshot_hash="frag_snapshot_123",
            outcome_status="PENDING",
            was_followed_legacy=True
        )
        db.add(outcome)
        db.commit()
        db.refresh(outcome)

        print("--- TEST 1: RecommendationOutcomeSnapshot Immutability constraints ---")
        # Explicitly create snapshot
        snapshot = RecommendationOutcomeSnapshotService.create_snapshot(db, outcome.id)
        assert snapshot is not None
        assert snapshot.recommendation_snapshot_hash == "run_snapshot_123"
        assert snapshot.fragility_snapshot_hash == "frag_snapshot_123"
        
        # Try mutating snapshot -> must raise RuntimeError
        snapshot.outcome_snapshot_hash = "mutated_hash"
        try:
            db.commit()
            assert False, "Mutation should have raised a RuntimeError!"
        except Exception as e:
            db.rollback()
            assert "Forensic Immutability Violation" in str(e)
            print("[PASSED] Snapshot mutation block raised RuntimeError successfully.")

        # Try deleting snapshot -> must raise RuntimeError
        try:
            db.delete(snapshot)
            db.commit()
            assert False, "Deletion should have raised a RuntimeError!"
        except Exception as e:
            db.rollback()
            assert "Forensic Immutability Violation" in str(e)
            print("[PASSED] Snapshot deletion block raised RuntimeError successfully.\n")

        print("--- TEST 2: Deterministic Snapshot Hashing (Evidence snapshots correlation) ---")
        db.expire_all()
        orig_snapshot_hash = snapshot.outcome_snapshot_hash
        assert snapshot.incident_snapshot_hash is None
        assert snapshot.rollback_snapshot_hash is None

        # Link an incident to the first outcome
        incident_data = {
            "id": "inc_820_escaled",
            "severity": "P0",
            "timing": datetime.datetime.utcnow(),
            "affected_modules": ["auth/jwt.py"]
        }
        root_cause = {
            "pull_request_id": pr_id,
            "confidence": "DIRECT"
        }
        
        # Link incident
        EscapedDefectLinker.link_incident(db, incident_data, root_cause)
        db.expire_all()
        
        # Let's run verify_snapshot_integrity
        report = RecommendationOutcomeSnapshotService.verify_snapshot_integrity(db, outcome.id)
        assert report["drift_detected"] is True
        assert report["sub_hashes_matched"]["incidents"] is False  # live has incident, stored does not!
        print("[PASSED] Deterministic sub-snapshot hashing and evidence snapshot correlation verified successfully.\n")

        print("--- TEST 3: Classification Hook Integration ---")
        # Create another outcome and let classifier update it. It should automatically generate the snapshot!
        run_2 = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_820_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Classification Hook Run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_2)
        db.commit()
        db.refresh(run_2)

        outcome_2 = RecommendationOutcome(
            recommendation_run_id=run_2.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="run_snapshot_456",
            fragility_snapshot_hash="frag_snapshot_456",
            outcome_status="PENDING",
            was_followed_legacy=True
        )
        db.add(outcome_2)
        db.commit()
        db.refresh(outcome_2)

        # Classify outcome_2
        db.expire_all()
        RecommendationOutcomeClassifier.classify_and_update(db, outcome_2)
        
        db.expire_all()
        # Assert snapshot was automatically generated
        snapshot_2 = db.query(RecommendationOutcomeSnapshot).filter(
            RecommendationOutcomeSnapshot.recommendation_outcome_id == outcome_2.id
        ).first()
        
        assert snapshot_2 is not None
        assert snapshot_2.recommendation_snapshot_hash == "run_snapshot_456"
        assert snapshot_2.snapshot_version == 1
        print("[PASSED] Automatic snapshot generation on final classification Hook verified successfully.\n")

        print("--- TEST 4: Active Drift & Tampering Detection ---")
        # Create a clean outcome, generate its snapshot, and then tamper with database values to detect drift
        run_3 = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_820_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Drift Run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_3)
        db.commit()
        
        outcome_3 = RecommendationOutcome(
            recommendation_run_id=run_3.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="run_snapshot_789",
            fragility_snapshot_hash="frag_snapshot_789",
            outcome_status="FOLLOWED",
            was_followed_legacy=True
        )
        db.add(outcome_3)
        db.commit()
        
        snapshot_3 = RecommendationOutcomeSnapshotService.create_snapshot(db, outcome_3.id)
        assert snapshot_3 is not None
        
        # Verify initial integrity is perfect
        report_init = RecommendationOutcomeSnapshotService.verify_snapshot_integrity(db, outcome_3.id)
        assert report_init["drift_detected"] is False
        
        # Tamper: update classification of outcome_3 directly bypassing standard pipeline
        db.execute(
            RecommendationOutcome.__table__.update()
            .where(RecommendationOutcome.id == outcome_3.id)
            .values(outcome_status="OVERRIDDEN")
        )
        db.commit()
        db.expire_all()
        
        # Check integrity again -> must detect drift!
        report_tampered = RecommendationOutcomeSnapshotService.verify_snapshot_integrity(db, outcome_3.id)
        assert report_tampered["drift_detected"] is True
        assert report_tampered["sub_hashes_matched"]["classification"] is False  # status has drifted!
        print("[PASSED] Active database tampering and drift detection asserted successfully.")

    finally:
        db.close()

    print("\n==================================================================")
    print("ALL RECOMMENDATION OUTCOME SNAPSHOT CHECKS PASSED!")
    print("==================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
