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
    RecommendationTest,
    RecommendationReasoningEntry
)
from app.services.recommendation_outcome_classifier import RecommendationOutcomeClassifier

def cleanup_database():
    """Clean up DB before and after testing."""
    db = SessionLocal()
    try:
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
    print("STARTING RECOMMENDATION OUTCOME CLASSIFIER Forensics AUDIT VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # 1. Seeding basic structures
        org = Organization(id=org_id, name="Classifier Analytics Labs", slug="classifier-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=545454,
            name="classifier-core",
            full_name="classifier-labs/classifier-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        # Seed PRs
        pr_id = uuid.uuid4()
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=800000,
            number=800,
            title="PR 800 - Classification Target",
            author="engineer-classifier",
            source_branch="classifier-dev",
            target_branch="main",
            state="open",
            additions=30,
            deletions=5,
            changed_files_count=1,
            head_commit_sha="pr_800_head",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.commit()

        # Seed standard recommendation run (6 recommended tests)
        run = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_800_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Classification standard run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Seed 6 recommended tests for standard run
        for i in range(6):
            rec_test = RecommendationTest(
                recommendation_run_id=run.id,
                test_case_id=f"test_tc{i}",
                reason_type="historical_fragility",
                reason_details={},
                priority_score=0.8
            )
            db.add(rec_test)
        db.commit()

        print("--- TEST 1: Rollback Priority (ROLLBACK_LINKED) ---")
        # An outcome with rollback, escaped defect, overrides, and ignore.
        # ROLLBACK_LINKED must take absolute precedence.
        outcome_1 = RecommendationOutcome(
            recommendation_run_id=run.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run.id),
            outcome_status="PENDING",
            executed_tests=[],  # ignored overlap
            manually_added_tests=["test_tc10"], # overrides
            manually_removed_tests=["test_tc0"],
            was_followed=False,
            override_reason="LOW_TRUST",
            rollback_occurred=True,  # Rollback
            escaped_defect=True      # Escaped defect
        )
        
        res_1 = RecommendationOutcomeClassifier.classify(outcome_1, db=db)
        assert res_1["classification_label"] == "ROLLBACK_LINKED"
        assert res_1["overlap_ratio"] == 0.0
        assert res_1["override_metrics"]["total_manually_added"] == 1
        assert res_1["evidence"]["rollback_occurred"] is True
        assert res_1["confidence_calibration"]["auto_upgrade_allowed"] is False
        assert res_1["confidence_calibration"]["action"] == "DOWNGRADE"
        print("[PASSED] Rollback precedence and metrics preservation verified successfully.\n")

        print("--- TEST 2: Escaped Defect Priority (ESCAPED_DEFECT_LINKED) ---")
        # Outcome with escaped defect and overrides, no rollback.
        outcome_2 = RecommendationOutcome(
            recommendation_run_id=run.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run.id),
            outcome_status="PENDING",
            executed_tests=["test_tc1"],
            manually_added_tests=["test_tc10"],
            was_followed=False,
            override_reason="LOW_TRUST",
            rollback_occurred=False,
            escaped_defect=True
        )
        res_2 = RecommendationOutcomeClassifier.classify(outcome_2, db=db)
        assert res_2["classification_label"] == "ESCAPED_DEFECT_LINKED"
        assert res_2["evidence"]["escaped_defect_detected"] is True
        print("[PASSED] Escaped defect precedence verified successfully.\n")

        print("--- TEST 3: Overridden Priority (OVERRIDDEN) ---")
        # Outcome with overrides, no failures/defects.
        outcome_3 = RecommendationOutcome(
            recommendation_run_id=run.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run.id),
            outcome_status="PENDING",
            executed_tests=["test_tc0", "test_tc1", "test_tc2"],
            manually_added_tests=["test_tc10"],
            was_followed=True,
            override_reason="KNOWN_RISKY_AREA",
            rollback_occurred=False,
            escaped_defect=False
        )
        res_3 = RecommendationOutcomeClassifier.classify(outcome_3, db=db)
        assert res_3["classification_label"] == "OVERRIDDEN"
        assert res_3["evidence"]["has_manual_overrides"] is True
        print("[PASSED] Overridden status verified successfully.\n")

        print("--- TEST 4: Ignored Priority (IGNORED) ---")
        # Outcome with zero recommended tests executed, no overrides.
        outcome_4 = RecommendationOutcome(
            recommendation_run_id=run.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run.id),
            outcome_status="PENDING",
            executed_tests=[],
            manually_added_tests=[],
            was_followed=True,
            rollback_occurred=False,
            escaped_defect=False
        )
        res_4 = RecommendationOutcomeClassifier.classify(outcome_4, db=db)
        assert res_4["classification_label"] == "IGNORED"
        assert res_4["evidence"]["is_ignored"] is True
        print("[PASSED] Ignored status verified successfully.\n")

        print("--- TEST 5: Partially Followed Target (PARTIALLY_FOLLOWED) ---")
        # Strict non-empty subset of recommended tests executed (overlap >= 40%).
        outcome_5 = RecommendationOutcome(
            recommendation_run_id=run.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run.id),
            outcome_status="PENDING",
            executed_tests=["test_tc0", "test_tc1", "test_tc2"],
            manually_added_tests=[],
            was_followed=True,
            rollback_occurred=False,
            escaped_defect=False
        )
        res_5 = RecommendationOutcomeClassifier.classify(outcome_5, db=db)
        assert res_5["classification_label"] == "PARTIALLY_FOLLOWED"
        assert res_5["overlap_ratio"] == 3 / 6
        print("[PASSED] Partially Followed status verified successfully.\n")

        print("--- TEST 6: Fully Followed Target (FOLLOWED) ---")
        # Executed tests match recommended tests exactly.
        outcome_6 = RecommendationOutcome(
            recommendation_run_id=run.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run.id),
            outcome_status="PENDING",
            executed_tests=["test_tc0", "test_tc1", "test_tc2", "test_tc3", "test_tc4", "test_tc5"],
            manually_added_tests=[],
            was_followed=True,
            rollback_occurred=False,
            escaped_defect=False
        )
        res_6 = RecommendationOutcomeClassifier.classify(outcome_6, db=db)
        assert res_6["classification_label"] == "FOLLOWED"
        assert res_6["overlap_ratio"] == 1.0
        print("[PASSED] Fully Followed status verified successfully.\n")

        print("--- TEST 7: Tiny Recommended Suite Overfitting Prevention ---")
        # Seed a tiny recommendation run (3 recommended tests)
        run_tiny_id = uuid.uuid4()
        run_tiny = RecommendationRun(
            id=run_tiny_id,
            repository_id=repo_id,
            pr_id="pr_800_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Classification tiny run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_tiny)
        db.commit()
        
        # 3 tests
        for i in range(3):
            rec_test = RecommendationTest(
                recommendation_run_id=run_tiny_id,
                test_case_id=f"test_tiny_tc{i}",
                reason_type="historical_fragility",
                reason_details={},
                priority_score=0.8
            )
            db.add(rec_test)
        db.commit()
        db.refresh(run_tiny)

        # Tiny suite outcome with exactly 1 test removed
        outcome_tiny = RecommendationOutcome(
            recommendation_run_id=run_tiny_id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run_tiny_id),
            outcome_status="PENDING",
            executed_tests=["test_tiny_tc0", "test_tiny_tc1"],
            manually_added_tests=[],
            manually_removed_tests=["test_tiny_tc2"],
            was_followed=True,
            rollback_occurred=False,
            escaped_defect=False
        )
        res_tiny = RecommendationOutcomeClassifier.classify(outcome_tiny, db=db)
        # Provenance safety: classified as PARTIALLY_FOLLOWED instead of OVERRIDDEN
        assert res_tiny["classification_label"] == "PARTIALLY_FOLLOWED"
        assert res_tiny["tiny_repo_overfitting_prevented"] is True
        print("[PASSED] Tiny suite overfitting prevention verified successfully.\n")

        print("--- TEST 8: Full classify_and_update Database Integration ---")
        # Save outcome to DB and verify classification + Reasoning timeline entry persistence
        outcome_db = RecommendationOutcome(
            recommendation_run_id=run.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run.id),
            outcome_status="PENDING",
            executed_tests=["test_tc0", "test_tc1", "test_tc2", "test_tc3", "test_tc4", "test_tc5"],
            manually_added_tests=[],
            was_followed=True,
            rollback_occurred=False,
            escaped_defect=False
        )
        db.add(outcome_db)
        db.commit()
        
        res_update = RecommendationOutcomeClassifier.classify_and_update(db, outcome_db)
        assert outcome_db.outcome_status == "FOLLOWED"
        
        # Verify Reasoning entry was correctly registered
        reasoning = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id,
            RecommendationReasoningEntry.reason_type == "outcome_classification"
        ).first()
        
        assert reasoning is not None
        assert reasoning.source_reference == "FOLLOWED"
        assert reasoning.reasoning_metadata["classification_label"] == "FOLLOWED"
        assert reasoning.reasoning_metadata["overlap_ratio"] == 1.0
        
        print("[PASSED] Database integration and replayable audit reasoning persistence verified successfully.")

    finally:
        db.close()

    print("\n=======================================================")
    print("ALL RECOMMENDATION OUTCOME CLASSIFIER Forensics PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
