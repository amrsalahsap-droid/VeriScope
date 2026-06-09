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
    RecommendationOverrideRecord,
    RecommendationEngineerFeedback
)
from app.services.recommendation_calibration_signal_generator import RecommendationCalibrationSignalGenerator

def cleanup_database():
    """Clean up DB before and after testing."""
    db = SessionLocal()
    try:
        db.query(RecommendationEngineerFeedback).delete()
        db.query(RecommendationOverrideRecord).delete()
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
    print("STARTING RECOMMENDATION CALIBRATION SIGNAL GENERATOR AUDIT VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    
    # Bootstrap DB schema if needed
    from app.db.base import Base
    from app.db.session import engine
    Base.metadata.create_all(bind=engine)

    org_id = uuid.uuid4()
    repo_large_id = uuid.uuid4()
    repo_tiny_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # 1. Seeding basic structures
        org = Organization(id=org_id, name="Calibration Labs", slug="calibration-labs")
        db.add(org)
        
        repo_large = Repository(
            id=repo_large_id,
            organization_id=org_id,
            github_repo_id=717171,
            name="calibration-large",
            full_name="calibration-labs/calibration-large",
            default_branch="main",
            is_active=True
        )
        db.add(repo_large)

        repo_tiny = Repository(
            id=repo_tiny_id,
            organization_id=org_id,
            github_repo_id=727272,
            name="calibration-tiny",
            full_name="calibration-labs/calibration-tiny",
            default_branch="main",
            is_active=True
        )
        db.add(repo_tiny)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_large_id,
            github_pr_id=700000,
            number=700,
            title="PR 700 - Calibration Testbed",
            author="calibration-reviewer",
            source_branch="calibration-dev",
            target_branch="main",
            state="open",
            additions=40,
            deletions=8,
            changed_files_count=1,
            head_commit_sha="pr_700_head",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.commit()

        # Seed RecommendationRuns and Outcomes for Large Repo (10 outcomes to exceed tiny repo threshold)
        print("--- TEST 1: Seeding Large Dataset & Verifying Standard Mathematical Precision ---")
        for i in range(10):
            run = RecommendationRun(
                repository_id=repo_large_id,
                pr_id="pr_700_head",
                pull_request_id=pr_id,
                triggered_by="github-webhook",
                engine_version="v1",
                ruleset_version="rules-v1",
                degradation_policy_version="policy-v1",
                recommendation_reasoning_summary=f"Run {i}",
                evidence_quality="HIGH",
                created_at=datetime.datetime.utcnow() - datetime.timedelta(days=i)
            )
            db.add(run)
            db.commit()
            db.refresh(run)

            # Distribute signals:
            # - followed: 6 out of 10 (60%)
            # - overrides (widening/narrowing): 3 out of 10 (30%)
            # - defects: 1 out of 10 (10%)
            # - rollbacks: 1 out of 10 (10%)
            was_followed = (i < 6) if (i != 9) else None
            has_overrides = (6 <= i < 9)
            has_defect = (i == 9)
            has_rollback = (i == 9)

            outcome_status = "FOLLOWED"
            if has_rollback:
                outcome_status = "ROLLBACK_LINKED"
            elif has_defect:
                outcome_status = "ESCAPED_DEFECT_LINKED"
            elif has_overrides:
                outcome_status = "OVERRIDDEN"

            outcome = RecommendationOutcome(
                recommendation_run_id=run.id,
                repository_id=repo_large_id,
                pull_request_id=pr_id,
                recommendation_snapshot_hash=str(run.id),
                outcome_status=outcome_status,
                was_followed_legacy=was_followed,
                rollback_occurred=has_rollback,
                escaped_defect_detected=has_defect,
                manually_added_tests=["test_add"] if has_overrides else [],
                manually_removed_tests=["test_remove"] if has_overrides else []
            )
            db.add(outcome)
            db.commit()
            db.refresh(outcome)

            # Associate some overrides records
            if has_overrides:
                override_rec = RecommendationOverrideRecord(
                    recommendation_outcome_id=outcome.id,
                    recommendation_run_id=run.id,
                    repository_id=repo_large_id,
                    detected_at=datetime.datetime.utcnow(),
                    total_manually_added=1,
                    total_manually_removed=1,
                    widening_detected=True,
                    narrowing_detected=True,
                    flaky_tests_manually_restored=0
                )
                db.add(override_rec)
                db.commit()

            # Associate usefulness feedback: 5 out of 10 (50%)
            if i < 5:
                feedback = RecommendationEngineerFeedback(
                    recommendation_outcome_id=outcome.id,
                    feedback_type="USEFUL",
                    feedback_text="Very nice recommendation logic"
                )
                db.add(feedback)
                db.commit()

        # Generate signals for Large Repo
        db.expire_all()
        signals_large = RecommendationCalibrationSignalGenerator.generate_signals(
            db=db,
            repository_id=repo_large_id,
            window_days=30
        )

        assert signals_large["total_outcomes_analyzed"] == 10
        assert signals_large["is_tiny_repository_normalization_applied"] is False
        
        # Verify rate precision (raw rate should match standard ratios)
        assert signals_large["signals"]["recommendation_follow_rate"]["raw_rate"] == 0.6
        assert signals_large["signals"]["override_rate"]["raw_rate"] == 0.3
        assert signals_large["signals"]["escaped_defect_rate"]["raw_rate"] == 0.1
        assert signals_large["signals"]["rollback_rate"]["raw_rate"] == 0.1
        assert signals_large["signals"]["recommendation_usefulness_feedback"]["raw_rate"] == 0.5
        print("[PASSED] Standard mathematical precision and aggregations verified successfully.\n")

        print("--- TEST 2: Wilson Score Confidence Intervals ---")
        # Assert Wilson score confidence interval bounds are correct
        for name, data in signals_large["signals"].items():
            wilson = data["confidence_interval"]
            assert 0.0 <= wilson["lower"] <= wilson["estimate"] <= wilson["upper"] <= 1.0
            print(f"[PASSED] Wilson interval for {name}: {wilson}")
        print("[PASSED] 95% Wilson Score confidence intervals verified mathematically valid.\n")

        print("--- TEST 3: Tiny Repository Conservative Normalization (Bayesian Smoothing) ---")
        # Seed a tiny repository (1 outcome: followed=True, feedback=USEFUL)
        run_tiny = RecommendationRun(
            repository_id=repo_tiny_id,
            pr_id="pr_700_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Tiny Run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_tiny)
        db.commit()
        db.refresh(run_tiny)

        outcome_tiny = RecommendationOutcome(
            recommendation_run_id=run_tiny.id,
            repository_id=repo_tiny_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run_tiny.id),
            outcome_status="FOLLOWED",
            was_followed_legacy=True
        )
        db.add(outcome_tiny)
        db.commit()
        db.refresh(outcome_tiny)

        feedback_tiny = RecommendationEngineerFeedback(
            recommendation_outcome_id=outcome_tiny.id,
            feedback_type="USEFUL",
            feedback_text="Tiny feedback"
        )
        db.add(feedback_tiny)
        db.commit()

        # Generate signals for Tiny Repo
        db.expire_all()
        signals_tiny = RecommendationCalibrationSignalGenerator.generate_signals(
            db=db,
            repository_id=repo_tiny_id,
            min_recommendations=5
        )

        assert signals_tiny["total_outcomes_analyzed"] == 1
        assert signals_tiny["is_tiny_repository_normalization_applied"] is True

        # Verify Bayesian Smoothing (Beta prior alpha=2, beta=2)
        # successes=1, total=1. Smoothed rate = (1 + 2) / (1 + 2 + 2) = 3/5 = 0.6
        follow_data = signals_tiny["signals"]["recommendation_follow_rate"]
        assert follow_data["raw_rate"] == 1.0
        assert follow_data["smoothed_rate"] == 0.6
        assert follow_data["final_calibrated_estimate"] == 0.6  # Smooth estimate is used for tiny repos!
        print("[PASSED] Tiny repository Bayesian smoothing verified successfully (100% smoothed to 60% standard estimate).\n")

        print("--- TEST 4: Informational Isolation (No Auto-Learning Loops) ---")
        # Verify that generating signals is strictly informational and has no side effects
        # 1. Store run reasoning summary before signal generation
        orig_summary = run_tiny.recommendation_reasoning_summary
        
        # 2. Generate signals
        _ = RecommendationCalibrationSignalGenerator.generate_signals(db=db, repository_id=repo_tiny_id)
        
        # 3. Assert original recommendation is completely unmodified
        db.refresh(run_tiny)
        assert run_tiny.recommendation_reasoning_summary == orig_summary
        print("[PASSED] Informational isolation successfully verified (No auto-learning feedback loop).\n")

        # Run generator again with same DB snapshot and assert identical output
        signals_replay = RecommendationCalibrationSignalGenerator.generate_signals(
            db=db,
            repository_id=repo_large_id,
            window_days=30
        )
        signals_large.pop("generated_at", None)
        signals_replay.pop("generated_at", None)
        assert signals_replay == signals_large
        print("[PASSED] Deterministic replay verified successfully.")

    finally:
        db.close()

    print("\n==================================================================")
    print("ALL RECOMMENDATION CALIBRATION SIGNAL GENERATOR CHECKS PASSED!")
    print("==================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
