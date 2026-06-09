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
)
from app.models.pilot import (
    PilotOrganizationProfile,
    PilotRepositoryEnrollment,
)
from app.models.fragility_pattern import FragilityPattern
from app.services.pilot_report_generator import PilotReportGenerator

def cleanup_database():
    """Clean up the test DB records cleanly."""
    db = SessionLocal()
    try:
        db.query(PilotRepositoryEnrollment).delete()
        db.query(PilotOrganizationProfile).delete()
        db.query(FragilityPattern).delete()
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
    print("STARTING VERISCOPE PHASE 7: PILOT REPORT GENERATOR VERIFICATION")
    print("======================================================================\n")

    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # 1. Seed base organization and repository
        org = Organization(id=org_id, name="Alpha Pilot Enterprises", slug="alpha-pilot-ent")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=101010,
            name="core-api",
            full_name="alpha-pilot/core-api",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=121000,
            number=121,
            title="PR 121",
            author="engineer-x",
            source_branch="feat-x",
            target_branch="main",
            state="open",
            additions=15,
            deletions=4,
            changed_files_count=1,
            head_commit_sha="sha_121_head",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow()
        )
        db.add(pr)
        db.commit()

        # 2. Seed Pilot Profile and Enrollment
        profile = PilotOrganizationProfile(
            id=profile_id,
            organization_id=org_id,
            pilot_name="Alpha Core Pilot",
            pilot_status="ACTIVE",
            pilot_start_date=datetime.datetime.utcnow() - datetime.timedelta(days=10),
            pilot_end_date=datetime.datetime.utcnow() + datetime.timedelta(days=20),
            pricing_model="FIXED_MONTHLY",
            monthly_price_usd=250.00,
            repo_limit=5
        )
        db.add(profile)

        enrollment = PilotRepositoryEnrollment(
            id=uuid.uuid4(),
            pilot_profile_id=profile_id,
            repository_id=repo_id,
            enrollment_status="ACTIVE"
        )
        db.add(enrollment)
        db.commit()

        # 3. Seed 4 recommendation runs: average full suite = 7800s (2h 10m), veriscope = 2460s (41m)
        
        # Run 1: followed
        run1 = RecommendationRun(
            repository_id=repo_id,
            pull_request_id=pr_id,
            pr_id="sha_121_head",
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Run 1",
            evidence_quality="HIGH",
            estimated_runtime_seconds=2460.0,
            full_suite_runtime_seconds=7800.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=2)
        )
        db.add(run1)

        # Run 2: overridden
        run2 = RecommendationRun(
            repository_id=repo_id,
            pull_request_id=pr_id,
            pr_id="sha_121_head",
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Run 2",
            evidence_quality="HIGH",
            estimated_runtime_seconds=2460.0,
            full_suite_runtime_seconds=7800.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )
        db.add(run2)

        # Run 3: ignored (missing full suite)
        run3 = RecommendationRun(
            repository_id=repo_id,
            pull_request_id=pr_id,
            pr_id="sha_121_head",
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Run 3",
            evidence_quality="HIGH",
            estimated_runtime_seconds=2460.0,
            full_suite_runtime_seconds=None,
            created_at=datetime.datetime.utcnow()
        )
        db.add(run3)

        # Run 4: followed
        run4 = RecommendationRun(
            repository_id=repo_id,
            pull_request_id=pr_id,
            pr_id="sha_121_head",
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Run 4",
            evidence_quality="HIGH",
            estimated_runtime_seconds=2460.0,
            full_suite_runtime_seconds=7800.0,
            created_at=datetime.datetime.utcnow()
        )
        db.add(run4)

        # Run 5: overridden
        run5 = RecommendationRun(
            repository_id=repo_id,
            pull_request_id=pr_id,
            pr_id="sha_121_head",
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Run 5",
            evidence_quality="HIGH",
            estimated_runtime_seconds=2460.0,
            full_suite_runtime_seconds=7800.0,
            created_at=datetime.datetime.utcnow()
        )
        db.add(run5)
        db.commit()
        db.refresh(run1)
        db.refresh(run2)
        db.refresh(run3)
        db.refresh(run4)
        db.refresh(run5)

        # Seed outcomes
        outcome1 = RecommendationOutcome(
            recommendation_run_id=run1.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            outcome_status="FOLLOWED",
            executed_tests=[]
        )
        db.add(outcome1)

        outcome2 = RecommendationOutcome(
            recommendation_run_id=run2.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            outcome_status="FOLLOWED",
            executed_tests=[],
            manually_added_tests=["test_a"] # triggers override
        )
        db.add(outcome2)

        outcome3 = RecommendationOutcome(
            recommendation_run_id=run3.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            outcome_status="IGNORED",
            executed_tests=[]
        )
        db.add(outcome3)

        outcome4 = RecommendationOutcome(
            recommendation_run_id=run4.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            outcome_status="FOLLOWED",
            executed_tests=[],
            escaped_defect_detected=True # triggers EscapedDefectSafety attention
        )
        db.add(outcome4)

        outcome5 = RecommendationOutcome(
            recommendation_run_id=run5.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            outcome_status="FOLLOWED",
            executed_tests=[],
            manually_added_tests=["test_b"] # overridden
        )
        db.add(outcome5)
        db.commit()

        # Seed active fragility patterns
        db.add(FragilityPattern(
            repository_id=repo_id,
            pattern_type="UNSTABLE_MODULE",
            normalized_pattern_key="UNSTABLE_MODULE:auth",
            title="auth",
            explanation="Exceeded failure frequency inside auth.",
            fragility_score=90.0,
            status="ACTIVE"
        ))
        db.add(FragilityPattern(
            repository_id=repo_id,
            pattern_type="CO_FAILURE_PATTERN",
            normalized_pattern_key="CO_FAILURE_PATTERN:auth:audit",
            title="permission change + audit logging impact",
            explanation="Changes in auth co-failed with downstream audit tests.",
            fragility_score=85.0,
            status="ACTIVE"
        ))
        db.add(FragilityPattern(
            repository_id=repo_id,
            pattern_type="ROLLBACK_INVOLVEMENT",
            normalized_pattern_key="ROLLBACK_INVOLVEMENT:billing",
            title="billing",
            explanation="Billing file edits linked directly to rollbacks.",
            fragility_score=88.0,
            status="ACTIVE"
        ))
        db.commit()

        # 4. Generate the Operational Pilot Report
        print("--- TEST 1: Generating Pilot Evaluation Report package ---")
        start_date = datetime.datetime.utcnow() - datetime.timedelta(days=12)
        end_date = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        
        report_pkg = PilotReportGenerator.generate_report(
            db=db,
            pilot_profile_id=profile_id,
            start_date=start_date,
            end_date=end_date,
            is_incident_lineage_complete=True
        )

        assert report_pkg is not None
        assert "json_payload" in report_pkg
        assert "markdown_content" in report_pkg
        assert "pdf_ready_structure" in report_pkg
        print("[PASSED] Pilot Report Orchestration executed successfully.\n")

        # 5. Assert JSON payload metrics
        print("--- TEST 2: Validating JSON Payload Metrics ---")
        payload = report_pkg["json_payload"]
        assert payload["pilot_summary"]["organization_name"] == "Alpha Pilot Enterprises"
        assert payload["pilot_summary"]["pilot_name"] == "Alpha Core Pilot"
        assert payload["pilot_summary"]["enrolled_repositories"] == ["alpha-pilot/core-api"]

        # Savings: average full = 7800 (2h 10m), average veriscope = 2460 (41m).
        # Net saving = 5340s = 89 minutes. Followed count = 2 (outcomes 1 and 4).
        # Hours saved = 5340 * 2 / 3600 = 2.97 hours -> rounds to 3.0 engineering hours
        savings_data = payload["regression_efficiency"]
        assert savings_data["average_full_suite_runtime"] == "2h 10m"
        assert savings_data["average_veriscope_runtime"] == "41m"
        assert savings_data["estimated_runtime_reduction"] == "68.5%"
        assert savings_data["estimated_engineering_hours_saved"] == 3.0

        # Trust signals
        trust = payload["recommendation_trust_signals"]
        assert trust["total_runs"] == 5
        assert trust["followed_runs"] == 2
        assert trust["overridden_runs"] == 2
        assert trust["ignored_runs"] == 1
        assert trust["adherence_rate"] == 0.40  # 2 followed / 5 total outcomes (N=5)

        # Safety Assessment: Escaped defect present -> safety status "ATTENTION", defect rate 20.0%
        safety = payload["escaped_defect_safety"]
        assert safety["safety_status"] == "ATTENTION"
        assert safety["escaped_defect_rate_percent"] == 20.0
        assert "temporal correlation analysis" in safety["safety_assessment"].lower()
        assert "direct causal relationships are not automatically assumed" in safety["safety_assessment"].lower()

        # Dynamic Next Step
        assert "escaped defect safety audit" in payload["recommended_next_step"].lower()
        print("[PASSED] JSON operational metrics matched all calculations perfectly.\n")

        # 6. Assert Markdown Report
        print("--- TEST 3: Validating Markdown Formatting rules ---")
        md = report_pkg["markdown_content"]
        assert "# Veriscope Operational Pilot Report" in md
        assert "## 1. Executive Summary" in md
        assert "## 2. Regression Efficiency & Savings" in md
        assert "## 3. Fragility & Risk Intelligence" in md
        assert "## 4. Trust Signals & Developer Adherence" in md
        assert "## 5. Escaped Defect Safety Assessment" in md
        assert "## 6. Recommended Next Steps" in md
        # Calm tone audit (no emojis)
        assert "🔥" not in md
        assert "🚀" not in md
        assert "prevented" not in md.lower()
        print("[PASSED] Emojiless operational markdown generated perfectly.\n")

        # 7. Assert PDF Ready Structure
        print("--- TEST 4: Validating Future PDF HTML/CSS Template ---")
        pdf = report_pkg["pdf_ready_structure"]
        assert pdf["document_metadata"]["client"] == "Alpha Pilot Enterprises"
        assert "@media print" in pdf["css_styles"]
        assert "page-break-inside: avoid" in pdf["css_styles"]
        assert "<div class='page'>" in pdf["html_template"]
        assert "Veriscope Operational Pilot Report" in pdf["html_template"]
        print("[PASSED] Future PDF-ready semantic HTML structure validated successfully.\n")

    finally:
        db.close()

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 PILOT REPORT GENERATOR TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
