import os
import sys
import uuid
import datetime
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
    RecommendationReasoningEntry
)
from app.services.rollback_outcome_tracker import RollbackOutcomeTracker

def cleanup_database():
    """Clean up DB before and after testing."""
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
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
    print("STARTING ROLLBACK OUTCOME TRACKER FORENSIC AUDIT VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # 1. Seeding basic structures
        org = Organization(id=org_id, name="Rollback Operations Corp", slug="rollback-ops-corp")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=777777,
            name="rollback-core",
            full_name="rollback-ops-corp/rollback-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=700000,
            number=700,
            title="PR 700 - Critical Rollback Target",
            author="engineer-defect",
            source_branch="defect-patch",
            target_branch="main",
            state="open",
            additions=45,
            deletions=12,
            changed_files_count=3,
            head_commit_sha="pr_700_head",
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
            pr_id="pr_700_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Rollback tracker test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Baseline check: no outcome initially, RollbackOutcomeTracker should instantiate one or link existing
        print("--- TEST 1: Linking Direct Confidence Rollback Event ---")
        rollback_data = {
            "id": "RLB-DIRECT-101",
            "timing": datetime.datetime.utcnow() - datetime.timedelta(minutes=15),
            "trigger_reason": "High error rate on gateway middleware",
            "confidence": "DIRECT"
        }
        deployment_data = {
            "id": "DEP-700",
            "deployed_at": datetime.datetime.utcnow() - datetime.timedelta(hours=1),
            "status": "SUCCESS"
        }

        outcome = RollbackOutcomeTracker.track_rollback(
            db=db,
            rollback_data=rollback_data,
            pull_request_id=pr_id,
            deployment_data=deployment_data
        )

        assert outcome is not None
        assert outcome.outcome_status == "ROLLBACK_LINKED"
        assert outcome.rollback_occurred is True
        assert "RLB-DIRECT-101" in outcome.engineer_feedback
        assert "gateway middleware" in outcome.engineer_feedback

        # Verify the persisted forensic reasoning entry
        reasoning = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id,
            RecommendationReasoningEntry.reason_type == "rollback_linkage"
        ).first()

        assert reasoning is not None
        assert reasoning.confidence_level == "DIRECT"
        assert reasoning.source_entity == "RLB-DIRECT-101"
        assert reasoning.reasoning_metadata["rollback_trigger_reason"] == "High error rate on gateway middleware"
        assert reasoning.reasoning_metadata["linkage_confidence"] == "DIRECT"
        assert reasoning.reasoning_metadata["rollback_occurred"] is True
        
        # Verify JSON datetime string serialization
        assert isinstance(reasoning.reasoning_metadata["rolled_back_at"], str)
        assert isinstance(reasoning.reasoning_metadata["deployment_outcome"]["deployed_at"], str)

        print("[PASSED] Direct rollback linkage tracking asserted successfully.\n")

        print("--- TEST 2: Linking Suspected Confidence Rollback Event ---")
        # Track suspected rollback on the same Pull Request (by SHA)
        rollback_data_suspected = {
            "id": "RLB-SUSPECTED-202",
            "timing": datetime.datetime.utcnow(),
            "trigger_reason": "General performance spike in auth microservice",
            "confidence": "SUSPECTED"
        }

        outcome_suspected = RollbackOutcomeTracker.track_rollback(
            db=db,
            rollback_data=rollback_data_suspected,
            commit_sha="pr_700_head"
        )

        assert outcome_suspected is not None
        assert outcome_suspected.outcome_status == "ROLLBACK_LINKED"
        assert outcome_suspected.rollback_occurred is True
        assert "RLB-SUSPECTED-202" in outcome_suspected.engineer_feedback

        reasonings = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id,
            RecommendationReasoningEntry.reason_type == "rollback_linkage"
        ).all()
        
        assert len(reasonings) == 2
        suspected_reasoning = next(r for r in reasonings if r.source_entity == "RLB-SUSPECTED-202")
        assert suspected_reasoning.confidence_level == "SUSPECTED"

        print("[PASSED] Suspected rollback linkage tracking asserted successfully.\n")

        print("--- TEST 3: Deterministic Lineage Exception for Unknown PR ---")
        try:
            RollbackOutcomeTracker.track_rollback(
                db=db,
                rollback_data={"id": "RLB-ERR-303", "confidence": "DIRECT"},
                github_pr_number=99999
            )
            assert False, "Should have thrown ValueError for non-existent PR!"
        except ValueError as e:
            assert "Lineage resolution failed" in str(e)
            print("[PASSED] Deterministic lineage correctly raised ValueError for unknown PR.")

        print("--- TEST 4: Deterministic Lineage Exception for PR without Run ---")
        # Create a PR without any recommendation run
        pr_no_run_id = uuid.uuid4()
        pr_no_run = PullRequest(
            id=pr_no_run_id,
            repository_id=repo_id,
            github_pr_id=700001,
            number=701,
            title="PR 701 - No Recommendation Run",
            author="engineer-dev",
            source_branch="no-run-patch",
            target_branch="main",
            state="open",
            additions=1,
            deletions=1,
            changed_files_count=1,
            head_commit_sha="pr_701_head",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr_no_run)
        db.commit()

        try:
            RollbackOutcomeTracker.track_rollback(
                db=db,
                rollback_data={"id": "RLB-ERR-404", "confidence": "DIRECT"},
                pull_request_id=pr_no_run_id
            )
            assert False, "Should have thrown ValueError for PR without RecommendationRun!"
        except ValueError as e:
            assert "No RecommendationRun exists" in str(e)
            print("[PASSED] Deterministic lineage correctly raised ValueError for missing run.")

        print("--- TEST 5: Invalid Confidence Validation Exception ---")
        try:
            RollbackOutcomeTracker.track_rollback(
                db=db,
                rollback_data={"id": "RLB-ERR-505", "confidence": "HIGH_CONFIDENCE"},
                pull_request_id=pr_id
            )
            assert False, "Should have thrown ValueError for invalid confidence!"
        except ValueError as e:
            assert "Invalid rollback confidence" in str(e)
            print("[PASSED] Confidence validator correctly raised ValueError for invalid confidence.")

    finally:
        db.close()

    print("\n=======================================================")
    print("ALL ROLLBACK OUTCOME TRACKER FORENSIC CHECKS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
