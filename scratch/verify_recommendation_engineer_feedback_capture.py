import os
import sys
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationEngineerFeedback
)
from app.services.recommendation_engineer_feedback_capture import RecommendationEngineerFeedbackCapture

client = TestClient(app)

def cleanup_database():
    """Clean up DB before and after testing."""
    db = SessionLocal()
    try:
        db.query(RecommendationEngineerFeedback).delete()
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
    print("STARTING RECOMMENDATION ENGINEER FEEDBACK CAPTURE AUDIT VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # 1. Seeding basic structures
        org = Organization(id=org_id, name="Feedback Analytics Corp", slug="feedback-analytics-corp")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=656565,
            name="feedback-core",
            full_name="feedback-analytics-corp/feedback-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=600000,
            number=600,
            title="PR 600 - Dynamic Feedback Testbed",
            author="engineer-reviewer",
            source_branch="feedback-dev",
            target_branch="main",
            state="open",
            additions=15,
            deletions=2,
            changed_files_count=1,
            head_commit_sha="pr_600_head",
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
            pr_id="pr_600_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Feedback capture test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Baseline check: no outcome or feedback initially
        print("--- TEST 1: Manual Internal POST Endpoint (Append-Only verification) ---")
        # First feedback submission (creates outcome + registers feedback)
        fb_in_1 = {
            "feedback_state": "useful",
            "details": "Great direct mapping on changed file"
        }
        response_1 = client.post(f"/recommendations/{run.id}/feedback", json=fb_in_1)
        assert response_1.status_code == 200
        
        # Second feedback submission (appends to existing outcome, no mutable overwrite!)
        fb_in_2 = {
            "feedback_state": "missing_tests",
            "details": "Missing edge case database transaction tests"
        }
        response_2 = client.post(f"/recommendations/{run.id}/feedback", json=fb_in_2)
        assert response_2.status_code == 200

        # Verify outcome exists and has been synced with latest feedback summary
        db.expire_all()
        outcome = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == run.id
        ).first()
        
        assert outcome is not None
        assert outcome.outcome_status == "ACKNOWLEDGED"
        # Summary matches latest feedback
        assert "MISSING_TESTS: Missing edge case database transaction tests" in outcome.engineer_feedback

        # Verify granular append-only feedbacks table records
        feedbacks = db.query(RecommendationEngineerFeedback).filter(
            RecommendationEngineerFeedback.recommendation_outcome_id == outcome.id
        ).order_by(RecommendationEngineerFeedback.created_at.asc()).all()

        assert len(feedbacks) == 2
        # First feedback is preserved
        assert feedbacks[0].feedback_type == "USEFUL"
        assert feedbacks[0].feedback_text == "Great direct mapping on changed file"
        assert isinstance(feedbacks[0].created_at, datetime.datetime)

        # Second feedback is appended in chronological order
        assert feedbacks[1].feedback_type == "MISSING_TESTS"
        assert feedbacks[1].feedback_text == "Missing edge case database transaction tests"

        print("[PASSED] Lightweight append-only feedback via POST endpoint verified successfully.\n")

        print("--- TEST 2: GitHub Comment Landing Links Endpoint (GET route) ---")
        # Click third feedback link from comments (e.g. Unclear reasoning with actor john-doe)
        response_3 = client.get(
            f"/recommendations/{run.id}/feedback/github?state=unclear_reasoning&details=Why%20was%20auth_utils%20suggested?&actor=john-doe"
        )
        assert response_3.status_code == 200
        assert response_3.json()["status"] == "success"

        # Check third appended record in DB
        db.expire_all()
        feedbacks_updated = db.query(RecommendationEngineerFeedback).filter(
            RecommendationEngineerFeedback.recommendation_outcome_id == outcome.id
        ).order_by(RecommendationEngineerFeedback.created_at.asc()).all()

        assert len(feedbacks_updated) == 3
        fb_github = feedbacks_updated[2]
        assert fb_github.feedback_type == "UNCLEAR_REASONING"
        assert fb_github.feedback_text == "Why was auth_utils suggested?"
        assert fb_github.created_by == "john-doe"

        print("[PASSED] GitHub comment feedback links and actor/notes preservation verified successfully.\n")

        print("--- TEST 3: Admin/Debug Diagnostics GET Endpoints ---")
        # Call admin diagnostic endpoint to fetch full lineage of feedbacks
        response_diag = client.get(f"/internal/recommendations/{run.id}/feedback")
        assert response_diag.status_code == 200
        diag_data = response_diag.json()

        assert len(diag_data) == 3
        assert diag_data[0]["feedback_type"] == "USEFUL"
        assert diag_data[1]["feedback_type"] == "MISSING_TESTS"
        assert diag_data[2]["feedback_type"] == "UNCLEAR_REASONING"
        assert diag_data[2]["created_by"] == "john-doe"
        assert "created_at" in diag_data[0]

        print("[PASSED] Admin diagnostics timeline retrieval verified successfully.\n")

        print("--- TEST 4: Invalid Feedback Type Validation Exception ---")
        # Try invalid feedback state on manual endpoint
        fb_invalid = {
            "feedback_state": "perfect_recommendation", # unsupported state
            "details": "This should fail"
        }
        response_err = client.post(f"/recommendations/{run.id}/feedback", json=fb_invalid)
        assert response_err.status_code == 400
        assert "Invalid feedback type" in response_err.json()["detail"]

        # Try invalid feedback state on github comment endpoint
        response_err_git = client.get(f"/recommendations/{run.id}/feedback/github?state=awesome_state")
        assert response_err_git.status_code == 400
        assert "Invalid feedback type" in response_err_git.json()["detail"]

        print("[PASSED] Strict feedback type validation checks verified successfully.")

    finally:
        db.close()

    print("\n=======================================================")
    print("ALL RECOMMENDATION ENGINEER FEEDBACK CAPTURE CHECKS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
