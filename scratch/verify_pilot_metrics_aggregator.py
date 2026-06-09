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
    RecommendationTestOutcome
)
from app.services.pilot_metrics_aggregator import PilotMetricsAggregator

def cleanup_database():
    """Clean up the test DB records cleanly."""
    db = SessionLocal()
    try:
        db.query(RecommendationTestOutcome).delete()
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
    print("STARTING VERISCOPE PHASE 7: PILOT METRICS AGGREGATOR VERIFICATION")
    print("======================================================================\n")

    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr1_id = uuid.uuid4()
    pr2_id = uuid.uuid4()

    try:
        # 1. Seed base organization, repository, and pull requests
        org = Organization(id=org_id, name="Metrics Aggregator Labs", slug="metrics-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=989898,
            name="metrics-core",
            full_name="metrics-labs/metrics-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr1 = PullRequest(
            id=pr1_id,
            repository_id=repo_id,
            github_pr_id=71000,
            number=710,
            title="PR 710",
            author="engineer-a",
            source_branch="feat-a",
            target_branch="main",
            state="open",
            additions=10,
            deletions=2,
            changed_files_count=1,
            head_commit_sha="sha_710_head",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow()
        )
        db.add(pr1)

        pr2 = PullRequest(
            id=pr2_id,
            repository_id=repo_id,
            github_pr_id=72000,
            number=720,
            title="PR 720",
            author="engineer-b",
            source_branch="feat-b",
            target_branch="main",
            state="open",
            additions=20,
            deletions=5,
            changed_files_count=2,
            head_commit_sha="sha_720_head",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow()
        )
        db.add(pr2)
        db.commit()

        # 2. Seed 4 runs representing diverse lineage and missing data scenarios
        
        # Run 1: Complete followed data (PR 1, full_suite=1000s, recommended=300s)
        run1 = RecommendationRun(
            repository_id=repo_id,
            pull_request_id=pr1_id,
            pr_id="sha_710_head",
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Run 1",
            evidence_quality="HIGH",
            estimated_runtime_seconds=300.0,
            full_suite_runtime_seconds=1000.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=2)
        )
        db.add(run1)

        # Run 2: Overridden data (PR 1, full_suite=2000s, recommended=400s)
        run2 = RecommendationRun(
            repository_id=repo_id,
            pull_request_id=pr1_id,
            pr_id="sha_710_head",
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Run 2",
            evidence_quality="HIGH",
            estimated_runtime_seconds=400.0,
            full_suite_runtime_seconds=2000.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )
        db.add(run2)

        # Run 3: Ignored, missing full suite runtime (PR 2, full_suite=None, recommended=200s)
        run3 = RecommendationRun(
            repository_id=repo_id,
            pull_request_id=pr2_id,
            pr_id="sha_720_head",
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Run 3",
            evidence_quality="HIGH",
            estimated_runtime_seconds=200.0,
            full_suite_runtime_seconds=None, # Missing full suite
            created_at=datetime.datetime.utcnow()
        )
        db.add(run3)

        # Run 4: Complete data but missing PR link and missing outcome (full_suite=1500s, recommended=500s)
        run4 = RecommendationRun(
            repository_id=repo_id,
            pull_request_id=None,  # Missing PR FK
            pr_id="",              # Empty string sentinel
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Run 4",
            evidence_quality="HIGH",
            estimated_runtime_seconds=500.0,
            full_suite_runtime_seconds=1500.0,
            created_at=datetime.datetime.utcnow()
        )
        db.add(run4)
        db.commit()
        db.refresh(run1)
        db.refresh(run2)
        db.refresh(run3)
        db.refresh(run4)

        # Seed recommended tests
        # Run 1: 3 tests
        for i in range(3):
            db.add(RecommendationTest(recommendation_run_id=run1.id, test_case_id=f"test_{i}", reason_type="mapping", reason_details={}, priority_score=0.9))
        # Run 2: 4 tests
        for i in range(4):
            db.add(RecommendationTest(recommendation_run_id=run2.id, test_case_id=f"test_{i}", reason_type="mapping", reason_details={}, priority_score=0.9))
        # Run 3: 2 tests
        for i in range(2):
            db.add(RecommendationTest(recommendation_run_id=run3.id, test_case_id=f"test_{i}", reason_type="mapping", reason_details={}, priority_score=0.9))
        # Run 4: 5 tests
        for i in range(5):
            db.add(RecommendationTest(recommendation_run_id=run4.id, test_case_id=f"test_{i}", reason_type="mapping", reason_details={}, priority_score=0.9))
        db.commit()

        # Seed outcomes
        # Run 1 outcome: Followed (2 executed tests)
        outcome1 = RecommendationOutcome(
            recommendation_run_id=run1.id,
            repository_id=repo_id,
            pull_request_id=pr1_id,
            outcome_status="FOLLOWED",
            executed_tests=["test_0", "test_1"]
        )
        db.add(outcome1)

        # Run 2 outcome: Overridden (1 manual addition)
        outcome2 = RecommendationOutcome(
            recommendation_run_id=run2.id,
            repository_id=repo_id,
            pull_request_id=pr1_id,
            outcome_status="FOLLOWED",
            executed_tests=["test_0"],
            manually_added_tests=["test_manual_x"]
        )
        db.add(outcome2)

        # Run 3 outcome: Ignored
        outcome3 = RecommendationOutcome(
            recommendation_run_id=run3.id,
            repository_id=repo_id,
            pull_request_id=pr2_id,
            outcome_status="IGNORED",
            executed_tests=[]
        )
        db.add(outcome3)
        # Note: Run 4 outcome is intentionally missing!
        db.commit()

        # 3. Execute aggregation
        print("--- TEST 1: Executing Operational Pilot Metrics Aggregation ---")
        start_date = datetime.datetime.utcnow() - datetime.timedelta(days=5)
        end_date = datetime.datetime.utcnow() + datetime.timedelta(days=1)

        res = PilotMetricsAggregator.aggregate_metrics(db, [repo_id], start_date, end_date)
        assert res is not None
        print("[PASSED] Aggregator output is not None.\n")

        # 4. Assert Operational Metrics
        print("--- TEST 2: Validating Core Aggregated Operational Metrics ---")
        assert res["total_recommendation_runs"] == 4
        # PRs analyzed: PR 1 (runs 1, 2) and PR 2 (run 3). Run 4 lacks PR link.
        assert res["total_prs_analyzed"] == 2
        
        # Recommended tests: 3 (run1) + 4 (run2) + 2 (run3) + 5 (run4) = 14
        assert res["total_recommended_tests"] == 14
        # Executed tests: 2 (outcome1) + 1 (outcome2) + 0 (outcome3) = 3
        assert res["total_executed_tests"] == 3

        # Runtime savings duration (non-null full-suite values only)
        # Sum = Run 1 (1000s) + Run 2 (2000s) + Run 4 (1500s) = 4500s. Run 3 is None (excluded).
        assert res["total_full_suite_runtime_seconds"] == 4500.0
        # Sum = Run 1 (300s) + Run 2 (400s) + Run 3 (200s) + Run 4 (500s) = 1400s
        assert res["total_recommended_runtime_seconds"] == 1400.0

        # Ratios (based on total outcomes = 3: outcomes 1, 2, 3)
        # Override count = 1 (outcome 2 has manually_added_tests) -> 1 / 3 = 0.333
        assert res["override_frequency"] == 0.333
        # Ignored count = 1 (outcome 3 status IGNORED) -> 1 / 3 = 0.333
        assert res["ignored_recommendation_rate"] == 0.333
        print("[PASSED] Deterministic operational metrics calculated accurately!\n")

        # 5. Assert Missing Data Exclusions (Never Estimate Silently)
        print("--- TEST 3: Validating Missing Data Lineage Exclusions ---")
        exclusions = res["excluded_data_counts"]
        # Run 3 has null full suite runtime
        assert exclusions["missing_full_suite_runtime"] == 1
        # Run 4 has missing pull request info
        assert exclusions["missing_pull_request"] == 1
        # Run 4 has missing outcome
        assert exclusions["missing_outcome"] == 1
        # No runs have missing estimated runtime
        assert exclusions["missing_recommended_runtime"] == 0
        print("[PASSED] Data exclusions are transparently recorded and never silently estimated!\n")

        # 6. Assert Tiny Dataset Warning
        print("--- TEST 4: Validating Small Dataset Statistical Confidence Warning ---")
        warning = res["confidence_warning"]
        assert warning is not None
        assert "Tiny dataset" in warning
        assert "runs = 4" in warning
        assert "outcomes = 3" in warning
        print(f"[PASSED] Small dataset warning successfully emitted:\n{warning}\n")

    finally:
        db.close()

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 PILOT OPERATIONAL METRICS AGGREGATOR TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
