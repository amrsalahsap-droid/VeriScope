import os
import sys
import uuid
import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationReasoningEntry,
    RecommendationOutcomeEvidence,
    RecommendationOutcomeSnapshot
)
from app.db.session import engine
from app.db.base import Base
import app.models
from app.models.pilot import PilotReport, PilotSnapshot
from app.services.pilot_service import PilotService

def cleanup_database():
    """Clean up DB before and after testing."""
    db = SessionLocal()
    try:
        db.query(PilotSnapshot).delete()
        db.query(PilotReport).delete()
        db.query(RecommendationOutcomeSnapshot).delete()
        db.query(RecommendationOutcomeEvidence).delete()
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
    print("STARTING VERISCOPE PHASE 7: PILOT CONVERSION VERIFICATION")
    print("======================================================================\n")

    # Dynamically create all registered database tables (including pilot tables)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # Seed structures
        org = Organization(id=org_id, name="Pilot Conversion Labs", slug="pilot-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=454545,
            name="pilot-core",
            full_name="pilot-labs/pilot-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=630000,
            number=630,
            title="PR 630 - Pilot Target",
            author="engineer-pilot",
            source_branch="pilot-dev",
            target_branch="main",
            state="open",
            additions=12,
            deletions=3,
            changed_files_count=1,
            head_commit_sha="pr_630_head",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.commit()

        # Seed 3 runs to get statistical data
        # Run 1: followed (full_suite = 1000s, estimated = 300s -> saved 700s)
        run1 = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_630_head",
            pull_request_id=pr_id,
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
        
        # Run 2: followed (full_suite = 2000s, estimated = 500s -> saved 1500s)
        run2 = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_630_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Run 2",
            evidence_quality="HIGH",
            estimated_runtime_seconds=500.0,
            full_suite_runtime_seconds=2000.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )
        db.add(run2)

        # Run 3: overridden (full_suite = 3000s -> saved 0)
        run3 = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_630_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Run 3",
            evidence_quality="HIGH",
            estimated_runtime_seconds=800.0,
            full_suite_runtime_seconds=3000.0,
            created_at=datetime.datetime.utcnow()
        )
        db.add(run3)
        db.commit()
        db.refresh(run1)
        db.refresh(run2)
        db.refresh(run3)

        # Seed outcomes
        outcome1 = RecommendationOutcome(
            recommendation_run_id=run1.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run1.id),
            outcome_status="FOLLOWED",
            executed_tests=[],
            manually_added_tests=[],
            was_followed=True
        )
        db.add(outcome1)

        outcome2 = RecommendationOutcome(
            recommendation_run_id=run2.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run2.id),
            outcome_status="FOLLOWED",
            executed_tests=[],
            manually_added_tests=[],
            was_followed=True
        )
        db.add(outcome2)

        outcome3 = RecommendationOutcome(
            recommendation_run_id=run3.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run3.id),
            outcome_status="OVERRIDDEN",
            executed_tests=[],
            manually_added_tests=[],
            was_followed=False
        )
        db.add(outcome3)
        db.commit()

        # Let's run PilotService.generate_pilot_report!
        start_date = datetime.datetime.utcnow() - datetime.timedelta(days=5)
        end_date = datetime.datetime.utcnow() + datetime.timedelta(days=1)

        print("--- TEST 1: Generating Pilot Report & Snapshot ---")
        report = PilotService.generate_pilot_report(db, repo_id, start_date, end_date)
        assert report is not None
        assert report.total_runs == 3
        assert report.followed_runs == 2
        assert report.overridden_runs == 1
        assert report.ignored_runs == 0
        
        # Savings: Run 1 (700s) + Run 2 (1500s) = 2200s
        assert report.ci_runtime_saved_seconds == 2200.0
        # Total CI runtime: Run 1 (1000s) + Run 2 (2000s) + Run 3 (3000s) = 6000s
        assert report.ci_runtime_total_seconds == 6000.0

        # Wilson bounds (x=2, n=3)
        assert report.trust_adherence_rate == 2/3
        assert report.trust_lower_bound > 0.0
        assert report.trust_upper_bound < 1.0

        # Verify Snapshot was created
        snapshot = db.query(PilotSnapshot).filter(PilotSnapshot.pilot_report_id == report.id).first()
        assert snapshot is not None
        assert snapshot.payload["total_runs"] == 3
        assert snapshot.payload["ci_runtime_saved_seconds"] == 2200.0
        assert snapshot.payload["repository_name"] == "pilot-labs/pilot-core"
        print("[PASSED] Pilot report and immutable snapshot generated perfectly with accurate savings!\n")

        print("--- TEST 2: Generating Markdown One-Page Pilot Report ---")
        md_report = PilotService.generate_markdown_report(db, report.id)
        assert md_report is not None
        assert "Veriscope Operational Pilot Report" in md_report
        assert "Developer Adherence Rate" in md_report
        assert "66.7%" in md_report
        assert "Aggregated Saved CI Duration" in md_report
        assert "0.61 hours" in md_report
        assert "Audit Snapshot SHA-256 Hash" in md_report
        # Calm operational tone validation: absolutely no emojis and alarmist phrasing
        assert "🔥" not in md_report
        assert "🚀" not in md_report
        assert "saving millions of dollars" not in md_report
        print("[PASSED] Calm, professional markdown operational report generated successfully!\n")

        print("--- TEST 3: Snapshot Immutability (Mutation & Deletion Safety) ---")
        try:
            snapshot.generated_at = datetime.datetime.utcnow()
            db.commit()
            assert False, "Should have thrown RuntimeError for mutating snapshot!"
        except RuntimeError as e:
            assert "Forensic Immutability Violation" in str(e)
            db.rollback()
            print("[PASSED] ORM event listener correctly prevented snapshot mutation.")

        try:
            db.delete(snapshot)
            db.commit()
            assert False, "Should have thrown RuntimeError for deleting snapshot!"
        except RuntimeError as e:
            assert "Forensic Immutability Violation" in str(e)
            db.rollback()
            print("[PASSED] ORM event listener correctly prevented snapshot deletion.\n")

        print("--- TEST 4: Replaying & Auditing Snapshot ---")
        replay_res = PilotService.replay_pilot_snapshot(db, snapshot.id)
        assert replay_res["verification_status"] == "SUCCESS_VERIFIED"
        assert replay_res["snapshot_hash"] == snapshot.snapshot_hash
        assert replay_res["payload"]["total_runs"] == 3
        print("[PASSED] Replaying and auditing finalized snapshot completed successfully!\n")

    finally:
        db.close()

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 PILOT PACKAGING TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    # Ensure all tables exist before executing the cleanup queries
    Base.metadata.create_all(bind=engine)
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
