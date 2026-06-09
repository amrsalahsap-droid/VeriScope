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
from app.services.pilot_engineer_feedback_aggregator import PilotEngineerFeedbackAggregator

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
    print("STARTING VERISCOPE PHASE 7: PILOT ENGINEER FEEDBACK AGGREGATOR VERIFICATION")
    print("======================================================================\n")

    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # 1. Seed base organization and repository
        org = Organization(id=org_id, name="Feedback Labs", slug="feedback-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=303030,
            name="auth-core",
            full_name="feedback-labs/auth-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # Seed PullRequest
        pr_id = uuid.uuid4()
        db.add(PullRequest(
            id=pr_id, repository_id=repo_id, github_pr_id=1, number=1,
            title="PR 1", author="engineer-y", source_branch="y", target_branch="main",
            state="merged", head_commit_sha="sha_y",
            github_created_at=datetime.datetime.utcnow(), github_updated_at=datetime.datetime.utcnow()
        ))
        db.commit()

        # 2. Seed 6 recommendation runs & outcomes
        run_ids = [uuid.uuid4() for _ in range(6)]
        outcome_ids = [uuid.uuid4() for _ in range(6)]

        for i in range(6):
            db.add(RecommendationRun(
                id=run_ids[i], repository_id=repo_id, pull_request_id=pr_id, pr_id="sha_y",
                triggered_by="github-webhook", engine_version="v1.2.0", ruleset_version="rules-v1",
                degradation_policy_version="policy-v1", recommendation_reasoning_summary=f"Run {i}",
                evidence_quality="HIGH", estimated_runtime_seconds=100.0, full_suite_runtime_seconds=300.0,
                created_at=datetime.datetime.utcnow() - datetime.timedelta(days=7 - i)
            ))
            db.add(RecommendationOutcome(
                id=outcome_ids[i], recommendation_run_id=run_ids[i], repository_id=repo_id,
                pull_request_id=pr_id, outcome_status="FOLLOWED", executed_tests=[]
            ))
        db.commit()

        # 3. Seed engineer feedback (combining valid, abusive, shouting, and excess quotes)
        # Feedback 1: USEFUL - Valid quote
        db.add(RecommendationEngineerFeedback(
            id=uuid.uuid4(), recommendation_outcome_id=outcome_ids[0],
            feedback_type="USEFUL", feedback_text="This was a great recommendation.",
            created_by="engineer-a", created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=5)
        ))
        # Feedback 2: MISSING_TESTS - Valid quote
        db.add(RecommendationEngineerFeedback(
            id=uuid.uuid4(), recommendation_outcome_id=outcome_ids[1],
            feedback_type="MISSING_TESTS", feedback_text="Missed payment unit tests.",
            created_by="engineer-b", created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=4)
        ))
        # Feedback 3: UNCLEAR_REASONING - Valid quote
        db.add(RecommendationEngineerFeedback(
            id=uuid.uuid4(), recommendation_outcome_id=outcome_ids[2],
            feedback_type="UNCLEAR_REASONING", feedback_text="Reasoning explanation was too abstract.",
            created_by="engineer-c", created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=3)
        ))
        # Feedback 4: TOO_MANY_TESTS - Abusive / Vulgar language (MUST be excluded from representative quotes, raw count preserved)
        db.add(RecommendationEngineerFeedback(
            id=uuid.uuid4(), recommendation_outcome_id=outcome_ids[3],
            feedback_type="TOO_MANY_TESTS", feedback_text="This run is absolute shit!",
            created_by="engineer-d", created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        ))
        # Feedback 5: USEFUL - Shouting shout (MUST be excluded from representative quotes as noise, raw count preserved)
        db.add(RecommendationEngineerFeedback(
            id=uuid.uuid4(), recommendation_outcome_id=outcome_ids[4],
            feedback_type="USEFUL", feedback_text="VERY GOOD RECOMMENDATION!!!",
            created_by="engineer-e", created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        ))
        # Feedback 6: USEFUL - Valid quote but exceeds max-3 limit (MUST NOT be in quotes list)
        db.add(RecommendationEngineerFeedback(
            id=uuid.uuid4(), recommendation_outcome_id=outcome_ids[5],
            feedback_type="USEFUL", feedback_text="Perfect alignment.",
            created_by="engineer-f", created_at=datetime.datetime.utcnow()
        ))
        db.commit()

        # 4. Perform deterministic aggregation
        print("--- TEST 1: Aggregating Feedback ---")
        start_date = datetime.datetime.utcnow() - datetime.timedelta(days=10)
        end_date = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        
        aggregated = PilotEngineerFeedbackAggregator.aggregate_feedback(
            db=db,
            repository_ids=[repo_id],
            start_date=start_date,
            end_date=end_date
        )

        assert aggregated is not None
        print("[PASSED] Deterministic aggregation ran successfully.\n")

        # 5. Assert counts
        print("--- TEST 2: Validating Raw Feedback Counts ---")
        assert aggregated["total_feedback_count"] == 6
        assert aggregated["useful_feedback_count"] == 3
        assert aggregated["missing_tests_feedback_count"] == 1
        assert aggregated["unclear_reasoning_feedback_count"] == 1
        assert aggregated["too_many_tests_feedback_count"] == 1
        assert aggregated["not_useful_feedback_count"] == 0
        print("[PASSED] All raw, append-only feedback counts preserved correctly.\n")

        # 6. Assert quote safety exclusions & limits
        print("--- TEST 3: Validating Safe Anonymized Representative Quotes ---")
        quotes = aggregated["representative_quotes"]
        print("Representative Quotes (Max 3):")
        for q in quotes:
            print(f"  - \"{q}\"")

        # Must limit representative quotes to max 3
        assert len(quotes) == 3, f"Quotes count must be capped at 3, got: {len(quotes)}"
        
        # Abusive text must be excluded safely
        assert "This run is absolute shit!" not in quotes, "Abusive feedback was not filtered out."
        # Shouting text must be excluded safely
        assert "VERY GOOD RECOMMENDATION!!!" not in quotes, "Shouting noisy feedback was not filtered out."
        
        # Checked excluded noise count (abusive quote + shout quote)
        assert aggregated["excluded_noise_count"] == 2
        
        # Safe quotes must be present in order of timestamp
        assert quotes[0] == "This was a great recommendation."
        assert quotes[1] == "Missed payment unit tests."
        assert quotes[2] == "Reasoning explanation was too abstract."
        print("[PASSED] Representative quotes limited to 3, and abusive/noisy elements safely excluded.\n")

    finally:
        db.close()

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 ENGINEER FEEDBACK AGGREGATOR TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
