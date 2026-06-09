import os
import sys
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.test_result import TestCase
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationOutcome,
    RecommendationReasoningEntry
)
from app.services.recommendation import RecommendationService
from app.services.analytics import RecommendationAnalyticsService
from app.schemas.recommendation import RecommendationRunCreate, OutcomeCreate, FeedbackCreate

client = TestClient(app)

def cleanup_database():
    """Clean up DB after testing."""
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationTest).delete()
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

def seed_test_case(db: SessionLocal, repo_id: uuid.UUID, test_name: str) -> TestCase:
    import hashlib
    tc = TestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name="verify_suite",
        test_name=test_name,
        stable_identity=test_name,
        canonical_identity_hash=hashlib.sha256(test_name.encode()).hexdigest(),
        identity_lineage_root_hash=hashlib.sha256(test_name.encode()).hexdigest()
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    return tc

def run_learning_loop_verification():
    print("======================================================================")
    print("STARTING PHASE 6 ORGANIZATIONAL LEARNING LOOP VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    rec_service = RecommendationService(db)
    analytics_service = RecommendationAnalyticsService(db)

    try:
        # Seed org and repository
        org = Organization(id=org_id, name="Learning Loop Labs", slug="learning-loop-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=987654,
            name="learning-loop-core",
            full_name="learning-loop-labs/learning-loop-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        # Seed PR
        pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo_id,
            github_pr_id=300000,
            number=300,
            title="PR 300 - Loop Test",
            author="engineer-loop",
            source_branch="loop-patch",
            target_branch="main",
            state="open",
            additions=10,
            deletions=2,
            changed_files_count=1,
            head_commit_sha="pr_300",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.commit()

        # Seed some candidate TestCase records
        tc_a = seed_test_case(db, repo_id, "test_verify_a")
        tc_b = seed_test_case(db, repo_id, "test_verify_b")
        tc_c = seed_test_case(db, repo_id, "test_verify_c")
        
        print("--- 1. Testing Safe Initial Placeholder Generation ---")
        run_in = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id="pr_300",
            triggered_by="github-webhook",
            changed_files=["app/models/organization.py"]
        )
        run_rec = rec_service.create_recommendation_run(run_in)
        assert run_rec is not None

        # Assert that an initial placeholder RecommendationOutcome record was created automatically
        placeholder = db.query(RecommendationOutcome).filter(
            RecommendationOutcome.recommendation_run_id == run_rec.id
        ).first()
        assert placeholder is not None
        assert placeholder.was_followed is True
        assert placeholder.executed_tests == []
        assert placeholder.manually_added_tests == []
        assert placeholder.manually_removed_tests == []
        assert placeholder.override_reason is None
        assert placeholder.feedback is None
        assert placeholder.rollback_occurred is False
        assert placeholder.escaped_defect is False
        print("SUCCESS: Default placeholder was successfully automatically instantiated upon run creation!")

        # Overwrite the placeholder using record_outcome
        outcome_in = OutcomeCreate(
            executed_tests=["test_verify_a"],
            manually_added_tests=[],
            manually_removed_tests=["test_verify_b"],
            was_followed=False,
            override_reason="LOW_TRUST",
            feedback="low_confidence",
            rollback_occurred=True,
            escaped_defect=True
        )
        outcome_rec = rec_service.record_outcome(run_rec.id, outcome_in)
        assert outcome_rec is not None
        assert outcome_rec.id == placeholder.id  # Verify it updated the existing record
        assert outcome_rec.override_reason == "LOW_TRUST"
        assert outcome_rec.rollback_occurred is True
        assert outcome_rec.escaped_defect is True
        print("SUCCESS: record_outcome successfully updated the placeholder outcome rather than double-inserting!")

        # Verify duplicate attempts on updated outcome are correctly blocked (409 Conflict)
        try:
            rec_service.record_outcome(run_rec.id, outcome_in)
            assert False, "Should have thrown HTTP 409 conflict for double-writing custom outcome!"
        except Exception as e:
            assert "already been recorded" in str(e.detail)
            print("SUCCESS: Duplicate custom outcome record double-writes are correctly prevented (Immutable Lineage)!")

        # --- 2. Testing Mathematical Alignment Taxonomy ---
        print("\n--- 2. Testing Mathematical Alignment Taxonomy Properties ---")
        
        # Helper function to generate a run and return the outcome record directly
        def create_run_with_rec_tests(rec_list: List[str]) -> RecommendationRun:
            run = RecommendationRun(
                repository_id=repo_id,
                pr_id="pr_300",
                triggered_by="github-webhook",
                engine_version="v1",
                ruleset_version="rules-v1",
                degradation_policy_version="policy-v1",
                recommendation_reasoning_summary="Taxonomy test",
                evidence_quality="HIGH",
                created_at=datetime.datetime.utcnow()
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            
            for t_id in rec_list:
                db_t = RecommendationTest(
                    recommendation_run_id=run.id,
                    test_case_id=t_id,
                    reason_type="direct_file_coverage",
                    reason_details={},
                    priority_score=0.9
                )
                db.add(db_t)
            
            db.commit()
            db.refresh(run)
            return run

        # Case A: trusted (exact match)
        run_trusted = create_run_with_rec_tests(["test_verify_a", "test_verify_b"])
        outcome_trusted = RecommendationOutcome(
            recommendation_run_id=run_trusted.id,
            executed_tests=["test_verify_a", "test_verify_b"],
            manually_added_tests=[],
            manually_removed_tests=[],
            was_followed=True
        )
        db.add(outcome_trusted)
        db.commit()
        assert outcome_trusted.classification == "trusted"
        print("  - 'trusted' alignment classified successfully.")

        # Case B: ignored (zero overlap)
        run_ignored = create_run_with_rec_tests(["test_verify_a", "test_verify_b"])
        outcome_ignored = RecommendationOutcome(
            recommendation_run_id=run_ignored.id,
            executed_tests=["test_verify_c"],
            manually_added_tests=["test_verify_c"],
            manually_removed_tests=["test_verify_a", "test_verify_b"],
            was_followed=False
        )
        db.add(outcome_ignored)
        db.commit()
        assert outcome_ignored.classification == "ignored"
        print("  - 'ignored' alignment classified successfully.")

        # Case C: widened (all recommended run plus manual additions)
        run_widened = create_run_with_rec_tests(["test_verify_a"])
        outcome_widened = RecommendationOutcome(
            recommendation_run_id=run_widened.id,
            executed_tests=["test_verify_a", "test_verify_b"],
            manually_added_tests=["test_verify_b"],
            manually_removed_tests=[],
            was_followed=True
        )
        db.add(outcome_widened)
        db.commit()
        assert outcome_widened.classification == "widened"
        print("  - 'widened' alignment classified successfully.")

        # Case D: narrowed (strict subset run, no additions)
        run_narrowed = create_run_with_rec_tests(["test_verify_a", "test_verify_b"])
        outcome_narrowed = RecommendationOutcome(
            recommendation_run_id=run_narrowed.id,
            executed_tests=["test_verify_a"],
            manually_added_tests=[],
            manually_removed_tests=["test_verify_b"],
            was_followed=True
        )
        db.add(outcome_narrowed)
        db.commit()
        assert outcome_narrowed.classification == "narrowed"
        print("  - 'narrowed' alignment classified successfully.")

        # Case E: overridden (mix of both additions and removals)
        run_overridden = create_run_with_rec_tests(["test_verify_a", "test_verify_b"])
        outcome_overridden = RecommendationOutcome(
            recommendation_run_id=run_overridden.id,
            executed_tests=["test_verify_b", "test_verify_c"],
            manually_added_tests=["test_verify_c"],
            manually_removed_tests=["test_verify_a"],
            was_followed=False
        )
        db.add(outcome_overridden)
        db.commit()
        assert outcome_overridden.classification == "overridden"
        print("  - 'overridden' alignment classified successfully.")

        # Case F: Empty recommended test set behavior
        run_empty_rec = create_run_with_rec_tests([])
        outcome_empty_trusted = RecommendationOutcome(
            recommendation_run_id=run_empty_rec.id,
            executed_tests=[],
            manually_added_tests=[],
            manually_removed_tests=[],
            was_followed=True
        )
        db.add(outcome_empty_trusted)
        
        outcome_empty_widened = RecommendationOutcome(
            recommendation_run_id=create_run_with_rec_tests([]).id,
            executed_tests=["test_verify_a"],
            manually_added_tests=["test_verify_a"],
            manually_removed_tests=[],
            was_followed=True
        )
        db.add(outcome_empty_widened)
        db.commit()
        
        assert outcome_empty_trusted.classification == "trusted"
        assert outcome_empty_widened.classification == "widened"
        print("  - Empty recommendation edge-cases classified successfully.")

        # --- 3. Testing Deep Learning Diagnostics & Suite Expansion ---
        print("\n--- 3. Testing Deep Learning Diagnostics & Suite Expansion ---")
        
        # Let's seed outcome history to verify mathematical insights:
        # We will record specific manual additions for test_verify_c to trigger suite expansion
        def record_custom_outcome(run_id: uuid.UUID, adds: List[str], was_followed: bool, defect: bool = False, rollback: bool = False):
            outcome = RecommendationOutcome(
                recommendation_run_id=run_id,
                executed_tests=["test_verify_a"] + adds,
                manually_added_tests=adds,
                manually_removed_tests=[],
                was_followed=was_followed,
                override_reason="MISSING_COVERAGE" if adds else None,
                escaped_defect=defect,
                rollback_occurred=rollback
            )
            db.add(outcome)
            db.commit()

        # Seed custom runs: test_verify_c added manually in 3 separate customized outcomes
        for i in range(3):
            run = create_run_with_rec_tests(["test_verify_a"])
            record_custom_outcome(run.id, ["test_verify_c"], was_followed=False, defect=(i == 0), rollback=(i == 0))

        # Query diagnostics via Python analytics service
        diagnostics = analytics_service.get_learning_diagnostics(repo_id)
        
        print("DIAGNOSTICS OVERRIDE INSIGHTS:", diagnostics["override_insights"])
        print("DIAGNOSTICS TAXONOMY DISTRIBUTION:", diagnostics["taxonomy_distribution"])
        
        assert diagnostics["total_recommendations"] > 0
        assert diagnostics["taxonomy_distribution"]["widened"] > 0
        
        # Assert defect and rollback rates are calculated
        assert "escaped_defect_rate" in diagnostics["failure_signals"]
        assert "rollback_rate" in diagnostics["failure_signals"]
        assert diagnostics["failure_signals"]["escaped_defect_rate"] > 0
        assert diagnostics["failure_signals"]["by_taxonomy"]["widened"]["escaped_defects"] == 1
        print("SUCCESS: Defect/rollback taxonomy correlation mapped successfully.")

        # Assert manual additions details are compiled correctly
        added_tcs = diagnostics["override_insights"]["top_manually_added_tests"]
        assert len(added_tcs) > 0
        assert added_tcs[0]["test_case_id"] == "test_verify_c"
        assert added_tcs[0]["count"] == 5
        print("SUCCESS: Override insights correctly compiled the most frequent additions!")

        # Assert conservative learning loop expansion suggestions are triggered correctly
        recommendations = diagnostics["conservative_learning_recommendations"]
        assert len(recommendations) > 0
        assert recommendations[0]["test_case_id"] == "test_verify_c"
        assert recommendations[0]["manual_addition_count"] == 5
        assert "frequently added manually" in recommendations[0]["reason"]
        print("SUCCESS: Conservative suite expansion recommendation correctly suggested test_verify_c!")

        # --- 4. Expose Public endpoints diagnostics test ---
        print("\n--- 4. Testing Public API GET /api/recommendations/repository/{id}/learning-diagnostics ---")
        response = client.get(f"/api/recommendations/repository/{repo_id}/learning-diagnostics")
        assert response.status_code == 200
        api_data = response.json()
        assert api_data["repository_id"] == str(repo_id)
        assert len(api_data["conservative_learning_recommendations"]) > 0
        assert api_data["conservative_learning_recommendations"][0]["test_case_id"] == "test_verify_c"
        print("SUCCESS: Public diagnostics HTTP route operates and returns valid learning insights payload!")

    finally:
        db.close()

    print("\n=======================================================")
    print("ALL PHASE 6 RECOMMENDATION OUTCOME TESTS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_learning_loop_verification()
    finally:
        cleanup_database()
