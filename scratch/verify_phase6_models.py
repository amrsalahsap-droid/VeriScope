import os
import sys
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.test_result import TestCase
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationOutcome,
    RecommendationTestOutcome,
    RecommendationEngineerFeedback,
    RecommendationReasoningEntry,
)

def cleanup_database():
    """Clean up DB before and after testing."""
    db = SessionLocal()
    try:
        db.query(RecommendationEngineerFeedback).delete()
        db.query(RecommendationTestOutcome).delete()
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationRun).delete()
        db.query(PullRequest).delete()
        db.query(TestCase).delete()
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
    print("STARTING PHASE 6 MODELS & COMPATIBILITY LAYER VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # 1. Seeding basic structures
        org = Organization(id=org_id, name="Phase 6 Lab", slug="phase-6-lab")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=654321,
            name="phase6-models",
            full_name="phase-6-lab/phase6-models",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=400000,
            number=400,
            title="PR 400 - Models Check",
            author="engineer-models",
            source_branch="models-patch",
            target_branch="main",
            state="open",
            additions=12,
            deletions=3,
            changed_files_count=1,
            head_commit_sha="pr_400",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.commit()

        # Seed TestCase
        import hashlib
        tc_id = uuid.uuid4()
        tc = TestCase(
            id=tc_id,
            repository_id=repo_id,
            suite_name="models_suite",
            test_name="test_models_flow",
            stable_identity="test_models_flow",
            canonical_identity_hash=hashlib.sha256(b"test_models_flow").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"test_models_flow").hexdigest()
        )
        db.add(tc)
        db.commit()
        
        # 2. Seed RecommendationRun
        run = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_400",
            triggered_by="engineer-manual",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Models check run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Seed RecommendationTest for the run
        rec_test = RecommendationTest(
            recommendation_run_id=run.id,
            test_case_id="test_models_flow",
            reason_type="direct_file_coverage",
            reason_details={},
            priority_score=0.9
        )
        db.add(rec_test)
        db.commit()

        # 3. Create RecommendationOutcome using new Phase 6 columns
        print("--- 1. Testing New Phase 6 RecommendationOutcome Schema ---")
        outcome = RecommendationOutcome(
            recommendation_run_id=run.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="hash_run_123",
            fragility_snapshot_hash="hash_frag_123",
            outcome_status="PENDING",
            recommendation_presented_at=datetime.datetime.utcnow(),
            rollback_occurred=False,
            escaped_defect_detected=False
        )
        db.add(outcome)
        db.commit()
        db.refresh(outcome)

        assert outcome.outcome_status == "PENDING"
        assert outcome.recommendation_snapshot_hash == "hash_run_123"
        assert outcome.repository_id == repo_id
        assert outcome.pull_request_id == pr_id
        print("SUCCESS: Phase 6 RecommendationOutcome successfully saved and verified!")

        # 4. Create granular RecommendationTestOutcome records
        print("\n--- 2. Testing RecommendationTestOutcome Relations ---")
        test_outcome = RecommendationTestOutcome(
            recommendation_outcome_id=outcome.id,
            test_case_id=tc_id,
            recommendation_reason="Direct dependency change detected",
            recommended_by_veriscope=True,
            actually_executed=True,
            manually_added=False,
            manually_removed=False,
            execution_result="PASSED",
            execution_duration_seconds=1.24,
            flaky_influence=False
        )
        db.add(test_outcome)
        db.commit()
        db.refresh(test_outcome)

        assert test_outcome.execution_result == "PASSED"
        assert test_outcome.execution_duration_seconds == 1.24
        assert test_outcome.recommended_by_veriscope is True
        print("SUCCESS: Granular RecommendationTestOutcome successfully saved and verified!")

        # 5. Create RecommendationEngineerFeedback record
        print("\n--- 3. Testing RecommendationEngineerFeedback Relations ---")
        feedback = RecommendationEngineerFeedback(
            recommendation_outcome_id=outcome.id,
            feedback_type="USEFUL",
            feedback_text="Veriscope successfully targeted the auth tenant boundaries.",
            created_by="engineer-bob"
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        assert feedback.feedback_type == "USEFUL"
        assert feedback.created_by == "engineer-bob"
        print("SUCCESS: Normalized RecommendationEngineerFeedback successfully saved and verified!")

        # 6. Testing Legacy Backward-Compatibility Properties
        print("\n--- 4. Testing Legacy Backward-Compatibility Property Bridging ---")
        db.refresh(outcome)
        
        # Test backward-compatible executed_tests mapping
        assert "test_models_flow" in outcome.executed_tests
        
        # Test backward-compatible was_followed mapping
        assert outcome.was_followed is True
        
        # Test backward-compatible feedback_state mapping
        assert outcome.feedback_state == "USEFUL"
        
        # Test backward-compatible classification mapping
        assert outcome.classification == "trusted"
        print("SUCCESS: All legacy property getters/setters map beautifully to Phase 6 models!")

    finally:
        db.close()

    print("\n=======================================================")
    print("ALL PHASE 6 DATABASE MODELS VERIFICATIONS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
