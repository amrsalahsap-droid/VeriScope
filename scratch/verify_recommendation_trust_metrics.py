import os
import sys
import uuid
import datetime
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal, engine
from app.db.base import Base
import app.models
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationTest,
    RecommendationEngineerFeedback
)
from app.services.recommendation_trust_metrics_builder import RecommendationTrustMetricsBuilder

def cleanup_database():
    """Clean up the test DB records cleanly."""
    db = SessionLocal()
    try:
        db.query(RecommendationEngineerFeedback).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationTest).delete()
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
    print("STARTING VERISCOPE PHASE 7: RECOMMENDATION TRUST METRICS VERIFICATION")
    print("======================================================================\n")

    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # 1. Seed base organization and repository
        org = Organization(id=org_id, name="Adoption Corp", slug="adoption-corp")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=202020,
            name="payment-gateway",
            full_name="adoption-corp/payment-gateway",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # Seed 4 PullRequests for different authors to track adoption transitions
        pr_a_id = uuid.uuid4()
        pr_b_id = uuid.uuid4()
        pr_c_id = uuid.uuid4()
        pr_d_id = uuid.uuid4()

        db.add(PullRequest(
            id=pr_a_id, repository_id=repo_id, github_pr_id=1, number=1,
            title="PR 1", author="engineer-a", source_branch="a", target_branch="main",
            state="merged", head_commit_sha="sha_a",
            github_created_at=datetime.datetime.utcnow(), github_updated_at=datetime.datetime.utcnow()
        ))
        db.add(PullRequest(
            id=pr_b_id, repository_id=repo_id, github_pr_id=2, number=2,
            title="PR 2", author="engineer-b", source_branch="b", target_branch="main",
            state="merged", head_commit_sha="sha_b",
            github_created_at=datetime.datetime.utcnow(), github_updated_at=datetime.datetime.utcnow()
        ))
        db.add(PullRequest(
            id=pr_c_id, repository_id=repo_id, github_pr_id=3, number=3,
            title="PR 3", author="engineer-c", source_branch="c", target_branch="main",
            state="merged", head_commit_sha="sha_c",
            github_created_at=datetime.datetime.utcnow(), github_updated_at=datetime.datetime.utcnow()
        ))
        db.add(PullRequest(
            id=pr_d_id, repository_id=repo_id, github_pr_id=4, number=4,
            title="PR 4", author="engineer-d", source_branch="d", target_branch="main",
            state="merged", head_commit_sha="sha_d",
            github_created_at=datetime.datetime.utcnow(), github_updated_at=datetime.datetime.utcnow()
        ))
        db.commit()

        # 2. Seed 6 recommendation runs
        run_ids = [uuid.uuid4() for _ in range(6)]
        
        # Run 1 (engineer-a): followed
        db.add(RecommendationRun(
            id=run_ids[0], repository_id=repo_id, pull_request_id=pr_a_id, pr_id="sha_a",
            triggered_by="github-webhook", engine_version="v1.2.0", ruleset_version="rules-v1",
            degradation_policy_version="policy-v1", recommendation_reasoning_summary="Run 1",
            evidence_quality="HIGH", estimated_runtime_seconds=100.0, full_suite_runtime_seconds=300.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=5)
        ))
        # Run 2 (engineer-a): followed (engineer-a becomes repeat adopter)
        db.add(RecommendationRun(
            id=run_ids[1], repository_id=repo_id, pull_request_id=pr_a_id, pr_id="sha_a",
            triggered_by="github-webhook", engine_version="v1.2.0", ruleset_version="rules-v1",
            degradation_policy_version="policy-v1", recommendation_reasoning_summary="Run 2",
            evidence_quality="HIGH", estimated_runtime_seconds=100.0, full_suite_runtime_seconds=300.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=4)
        ))
        # Run 3 (engineer-b): followed with manual additions (overridden and widened!)
        db.add(RecommendationRun(
            id=run_ids[2], repository_id=repo_id, pull_request_id=pr_b_id, pr_id="sha_b",
            triggered_by="github-webhook", engine_version="v1.2.0", ruleset_version="rules-v1",
            degradation_policy_version="policy-v1", recommendation_reasoning_summary="Run 3",
            evidence_quality="HIGH", estimated_runtime_seconds=100.0, full_suite_runtime_seconds=300.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=3)
        ))
        # Run 4 (engineer-c): ignored
        db.add(RecommendationRun(
            id=run_ids[3], repository_id=repo_id, pull_request_id=pr_c_id, pr_id="sha_c",
            triggered_by="github-webhook", engine_version="v1.2.0", ruleset_version="rules-v1",
            degradation_policy_version="policy-v1", recommendation_reasoning_summary="Run 4",
            evidence_quality="HIGH", estimated_runtime_seconds=100.0, full_suite_runtime_seconds=300.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=2)
        ))
        # Run 5 (engineer-d): followed
        db.add(RecommendationRun(
            id=run_ids[4], repository_id=repo_id, pull_request_id=pr_d_id, pr_id="sha_d",
            triggered_by="github-webhook", engine_version="v1.2.0", ruleset_version="rules-v1",
            degradation_policy_version="policy-v1", recommendation_reasoning_summary="Run 5",
            evidence_quality="HIGH", estimated_runtime_seconds=100.0, full_suite_runtime_seconds=300.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        ))
        # Run 6 (engineer-d): followed with overrides (manually_removed_tests)
        db.add(RecommendationRun(
            id=run_ids[5], repository_id=repo_id, pull_request_id=pr_d_id, pr_id="sha_d",
            triggered_by="github-webhook", engine_version="v1.2.0", ruleset_version="rules-v1",
            degradation_policy_version="policy-v1", recommendation_reasoning_summary="Run 6",
            evidence_quality="HIGH", estimated_runtime_seconds=100.0, full_suite_runtime_seconds=300.0,
            created_at=datetime.datetime.utcnow()
        ))
        db.commit()

        # Seed outcomes corresponding to the 6 runs
        outcome_ids = [uuid.uuid4() for _ in range(6)]
        
        # Outcome 1: followed
        db.add(RecommendationOutcome(
            id=outcome_ids[0], recommendation_run_id=run_ids[0], repository_id=repo_id,
            pull_request_id=pr_a_id, outcome_status="FOLLOWED", executed_tests=[]
        ))
        # Outcome 2: followed
        db.add(RecommendationOutcome(
            id=outcome_ids[1], recommendation_run_id=run_ids[1], repository_id=repo_id,
            pull_request_id=pr_a_id, outcome_status="FOLLOWED", executed_tests=[]
        ))
        # Outcome 3: overridden & widened
        db.add(RecommendationOutcome(
            id=outcome_ids[2], recommendation_run_id=run_ids[2], repository_id=repo_id,
            pull_request_id=pr_b_id, outcome_status="FOLLOWED", executed_tests=[],
            manually_added_tests=["test_new"]
        ))
        # Outcome 4: ignored
        db.add(RecommendationOutcome(
            id=outcome_ids[3], recommendation_run_id=run_ids[3], repository_id=repo_id,
            pull_request_id=pr_c_id, outcome_status="IGNORED", executed_tests=[]
        ))
        # Outcome 5: followed
        db.add(RecommendationOutcome(
            id=outcome_ids[4], recommendation_run_id=run_ids[4], repository_id=repo_id,
            pull_request_id=pr_d_id, outcome_status="FOLLOWED", executed_tests=[]
        ))
        # Outcome 6: overridden
        db.add(RecommendationOutcome(
            id=outcome_ids[5], recommendation_run_id=run_ids[5], repository_id=repo_id,
            pull_request_id=pr_d_id, outcome_status="FOLLOWED", executed_tests=[],
            manually_removed_tests=["test_removed"]
        ))
        db.commit()

        # 3. Seed engineer feedback to check usefulness rating summaries
        # Feedback 1 on Outcome 1: USEFUL
        db.add(RecommendationEngineerFeedback(
            id=uuid.uuid4(), recommendation_outcome_id=outcome_ids[0],
            feedback_type="USEFUL", feedback_text="Accurate recommended tests.",
            created_by="engineer-a", created_at=datetime.datetime.utcnow()
        ))
        # Feedback 2 on Outcome 2: USEFUL
        db.add(RecommendationEngineerFeedback(
            id=uuid.uuid4(), recommendation_outcome_id=outcome_ids[1],
            feedback_type="USEFUL", feedback_text="Spot on.",
            created_by="engineer-a", created_at=datetime.datetime.utcnow()
        ))
        # Feedback 3 on Outcome 3: MISSING_TESTS
        db.add(RecommendationEngineerFeedback(
            id=uuid.uuid4(), recommendation_outcome_id=outcome_ids[2],
            feedback_type="MISSING_TESTS", feedback_text="Added database checks.",
            created_by="engineer-b", created_at=datetime.datetime.utcnow()
        ))
        # Feedback 4 on Outcome 4: NOT_USEFUL
        db.add(RecommendationEngineerFeedback(
            id=uuid.uuid4(), recommendation_outcome_id=outcome_ids[3],
            feedback_type="NOT_USEFUL", feedback_text="Skipped necessary unit tests.",
            created_by="engineer-c", created_at=datetime.datetime.utcnow()
        ))
        db.commit()

        # 4. Generate trust metrics via Builder
        print("--- TEST 1: Building trust metrics across repository scope ---")
        start_date = datetime.datetime.utcnow() - datetime.timedelta(days=10)
        end_date = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        
        metrics = RecommendationTrustMetricsBuilder.build_metrics(
            db=db,
            repository_ids=[repo_id],
            start_date=start_date,
            end_date=end_date
        )

        assert metrics is not None
        print("[PASSED] Trust metrics package successfully generated.\n")

        # 5. Assert Core Metrics Values
        print("--- TEST 2: Validating Core Trust Rates ---")
        # outcomes: followed=3 (1, 2, 5), overridden=2 (3, 6), ignored=1 (4)
        assert metrics["total_runs"] == 6
        assert metrics["total_outcomes"] == 6
        assert metrics["follow_rate"] == 0.50
        assert metrics["override_frequency"] == 0.3333
        assert metrics["widening_frequency"] == 0.1667
        assert metrics["ignored_recommendation_rate"] == 0.1667
        assert metrics["trust_confidence_bounds"][0] > 0.0
        assert metrics["trust_confidence_bounds"][1] < 1.0
        print("[PASSED] Follow, override, widening, and ignored rates are 100% correct.\n")

        # 6. Assert Granular Usefulness Feedback Distribution
        print("--- TEST 3: Validating Engineer Usefulness Feedback ---")
        fb = metrics["feedback_summary"]
        assert fb["total_feedbacks"] == 4
        # Ratings: positive (USEFUL) = 2, negative (NOT_USEFUL) = 1. Missing tests = 1 (informational).
        # Positive feedback rate = 2 / (2 + 1) = 0.6667
        assert fb["positive_feedback_rate"] == 0.6667
        assert fb["distribution"]["USEFUL"] == 2
        assert fb["distribution"]["NOT_USEFUL"] == 1
        assert fb["distribution"]["MISSING_TESTS"] == 1
        assert fb["distribution"]["TOO_MANY_TESTS"] == 0
        print("[PASSED] Usefulness feedback counts and positive score match DB context perfectly.\n")

        # 7. Assert Recurring Recommendation Adoption
        print("--- TEST 4: Validating Recurring Developer Adoption ---")
        ra = metrics["recurring_adoption"]
        # Authors: engineer-a (2 followed), engineer-b (0 followed), engineer-c (0 followed), engineer-d (1 followed)
        # Unique adopters = 2 (engineer-a, engineer-d)
        # Unique repeat adopters = 1 (engineer-a has >= 2 followed)
        # Recurring adoption rate = 1 / 2 = 50% (0.50)
        assert ra["unique_authors_count"] == 4
        assert ra["unique_adopters_count"] == 2
        assert ra["unique_repeat_adopters_count"] == 1
        assert ra["recurring_adoption_rate"] == 0.50
        print("[PASSED] Recurring multi-run adoption rate resolved perfectly without theatrical overclaiming.\n")

        # 8. Assert Repository Segmentation & Confidence warnings
        print("--- TEST 5: Validating Segmentation & Statistical Warnings ---")
        assert str(repo_id) in metrics["repository_segmentation"]
        assert metrics["repository_segmentation"][str(repo_id)]["total_runs"] == 6
        assert metrics["repository_segmentation"][str(repo_id)]["followed_runs"] == 3
        # Since sample size >= 5, there should be no confidence warning
        assert metrics["confidence_warning"] is None
        print("[PASSED] Repository segmentation mapped accurately and no false tiny-dataset warnings emitted.\n")

        # 9. Test Low Sample Confidence Warnings
        print("--- TEST 6: Testing Low Sample (Tiny Dataset) Warnings ---")
        tiny_metrics = RecommendationTrustMetricsBuilder.build_metrics(
            db=db,
            repository_ids=[repo_id],
            start_date=datetime.datetime.utcnow() - datetime.timedelta(seconds=1), # very narrow window
            end_date=datetime.datetime.utcnow() + datetime.timedelta(days=1)
        )
        assert tiny_metrics["confidence_warning"] is not None
        assert "Tiny outcome dataset" in tiny_metrics["confidence_warning"]
        print("[PASSED] Correctly handled tiny dataset with statistical confidence warning.\n")

    finally:
        db.close()

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 TRUST METRICS VERIFICATION TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
