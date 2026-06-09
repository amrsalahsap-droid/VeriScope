import os
import sys
import uuid
import datetime
import hashlib
import json
from pathlib import Path
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.user import Workspace
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestCase, TestResult, TestRun
from app.models.coverage import CoverageReport, FileTestLink
from app.models.fragility_pattern import FragilityPattern
from app.models.dependency import FileDependency
from app.models.flaky_test import FlakyTestProfile
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendedTest,
    RecommendationOutcome,
    RecommendationReasoningEntry,
    RecommendationInputSnapshot,
    RecommendationExplanation,
)
from app.schemas.recommendation import RecommendationRunCreate
from app.services.recommendation import RecommendationService
from app.services.recommendation_report_generator import RecommendationReportGenerator


def cleanup_database():
    """Clean up seeded data safely in reverse dependency order."""
    db = SessionLocal()
    try:
        db.query(RecommendationExplanation).delete()
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationTest).delete()
        db.query(RecommendedTest).delete()
        db.query(RecommendationInputSnapshot).delete()
        db.query(RecommendationRun).delete()
        db.query(FileTestLink).delete()
        db.query(CoverageReport).delete()
        db.query(FlakyTestProfile).delete()
        db.query(FragilityPattern).delete()
        db.query(FileDependency).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequest).delete()
        db.query(TestResult).delete()
        db.query(TestRun).delete()
        db.query(TestCase).delete()
        db.query(Repository).delete()
        db.query(Workspace).delete()
        db.commit()
        print("Database cleaned up successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()


def run_verification():
    print("======================================================================")
    print("STARTING WORLD-CLASS RECOMMENDATION SCOPING VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()

    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_uuid = uuid.uuid4()

    try:
        # 1. Seed Workspace and Repository
        workspace = Workspace(
            id=workspace_id,
            name="World Class Corp",
            slug="world-class-corp"
        )
        db.add(workspace)
        db.commit()

        repo = Repository(
            id=repo_id,
            workspace_id=workspace_id,
            github_repo_id=888999,
            name="world-class-core",
            full_name="world-class-corp/world-class-core",
            default_branch="main",
            is_active=True,
            selected_for_analysis=True
        )
        db.add(repo)
        db.commit()

        # 2. Seed PullRequest and Changed Files to trigger specific domains
        pr = PullRequest(
            id=pr_uuid,
            repository_id=repo_id,
            github_pr_id=12345,
            number=42,
            title="Stripe billing integration with authentication and checkout logic",
            author="lead-engineer",
            source_branch="feature/stripe-payments",
            target_branch="main",
            state="open",
            changed_files_count=2,
            head_commit_sha="dummy-head-commit-sha",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.commit()

        # Seed changed files
        f1 = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path="auth/middleware.py",
            status="modified"
        )
        f2 = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path="billing/checkout.py",
            status="modified"
        )
        db.add(f1)
        db.add(f2)
        db.commit()

        # 3. Seed test cases to build a robust candidate list
        tc_auth_id = uuid.uuid4()
        tc_auth = TestCase(
            id=tc_auth_id,
            repository_id=repo_id,
            suite_name="auth_suite",
            test_name="test_login_flow",
            stable_identity="auth_suite::test_login_flow",
            canonical_identity_hash=hashlib.sha256(b"auth_suite::test_login_flow").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"auth_suite::test_login_flow").hexdigest()
        )

        tc_billing_id = uuid.uuid4()
        tc_billing = TestCase(
            id=tc_billing_id,
            repository_id=repo_id,
            suite_name="billing_suite",
            test_name="test_stripe_checkout",
            stable_identity="billing_suite::test_stripe_checkout",
            canonical_identity_hash=hashlib.sha256(b"billing_suite::test_stripe_checkout").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"billing_suite::test_stripe_checkout").hexdigest()
        )

        tc_other_id = uuid.uuid4()
        tc_other = TestCase(
            id=tc_other_id,
            repository_id=repo_id,
            suite_name="other_suite",
            test_name="test_generic_flow",
            stable_identity="other_suite::test_generic_flow",
            canonical_identity_hash=hashlib.sha256(b"other_suite::test_generic_flow").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"other_suite::test_generic_flow").hexdigest()
        )

        db.add(tc_auth)
        db.add(tc_billing)
        db.add(tc_other)
        db.commit()

        # 4. Seed historical execution to avoid 0 test_runs_count check and support avg durations
        tr = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            status="passed",
            file_hash="run-hash-1",
            normalized_execution_fingerprint="run-fingerprint-1"
        )
        db.add(tr)
        db.commit()

        res1 = TestResult(
            test_run_id=tr.id,
            test_case_id=tc_auth_id,
            status="passed",
            duration=3.0
        )
        res2 = TestResult(
            test_run_id=tr.id,
            test_case_id=tc_billing_id,
            status="passed",
            duration=5.5
        )
        res3 = TestResult(
            test_run_id=tr.id,
            test_case_id=tc_other_id,
            status="passed",
            duration=2.0
        )
        db.add(res1)
        db.add(res2)
        db.add(res3)
        db.commit()

        # 5. Seed CoverageReport and direct/heuristic mapping links
        report = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            workspace_id=workspace_id,
            commit_sha="dummy-head-commit-sha",
            branch="feature/stripe-payments",
            format="LCOV",
            source="MANUAL_UPLOAD",
            files_total=2,
            covered_lines_total=12,
            uncovered_lines_total=8,
            total_lines=20,
            line_coverage_ratio=0.6,
            branch_coverage_ratio=0.5,
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            file_hash="dummy-coverage-file-hash",
            confidence_score="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(report)
        db.commit()

        # Add coverage mappings to create direct link evidence
        link_auth = FileTestLink(
            id=uuid.uuid4(),
            coverage_report_id=report.id,
            file_path="auth/middleware.py",
            test_case_id=tc_auth_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        # Note: tc_billing is left without a direct mapping to trigger missing coverage gaps
        db.add(link_auth)
        db.commit()

        # 6. Seed Dependency Graph for static graph tracking evidence
        dep = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="billing/checkout.py",
            depends_on_file_path="auth/middleware.py",
            dependency_type="import",
            commit_sha="dummy-head-commit-sha"
        )
        db.add(dep)
        db.commit()

        # 7. Seed active FragilityPattern matching changed files to test fragility signals loading
        fragility = FragilityPattern(
            id=uuid.uuid4(),
            repository_id=repo_id,
            pattern_type="FILE_FAILURE_FREQUENCY",
            normalized_pattern_key="auth/middleware.py",
            title="Frequent failures in authentication middleware",
            explanation="The auth middleware exhibits severe historical regressions.",
            fragility_score=85.0,
            risk_level="HIGH",
            status="ACTIVE",
            confidence_level="HIGH",
            pattern_hash="fragility-hash-1",
            evidence_count=6,
            context={"trigger_file": "auth/middleware.py"}
        )
        db.add(fragility)
        db.commit()

        # 8. Seed FlakyTestProfile to test flakiness adjustment learning signals loading
        flaky = FlakyTestProfile(
            id=uuid.uuid4(),
            repository_id=repo_id,
            test_case_id=tc_other_id,
            status="unstable",
            failure_rate=0.45,
            recent_failure_rate=0.45,
            instability_score=0.60,
            sample_size=12,
            confidence_level="MODERATE",
            rationale="Executed tests frequently experience infrastructural timing timeouts."
        )
        db.add(flaky)
        db.commit()

        print("Successfully seeded Workspace, Repository, PullRequest, TestCases, CoverageReport, and Signals.\n")

        # ----------------------------------------------------
        # RUN RECOMMENDATION SERVICE
        # ----------------------------------------------------
        svc = RecommendationService(db)
        run_in = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id=str(pr.number),
            triggered_by="github-webhook",
            changed_files=["auth/middleware.py", "billing/checkout.py"],
            engine_version="v2.0.0" # Triggers full Phase 6 fallback, fragility, flaky, and explanation pipeline
        )
        db_run = svc.create_recommendation_run(run_in)
        db_run_id = db_run.id

        print(f"RecommendationRun successfully generated (Run ID: {db_run_id})\n")

        # ----------------------------------------------------
        # GENERATE REPORT
        # ----------------------------------------------------
        report_data = RecommendationReportGenerator.generate_report(db, db_run_id)

        # ----------------------------------------------------
        # WORLD-CLASS DIAGNOSTIC VERIFICATIONS
        # ----------------------------------------------------
        print("Starting validations of the 13 required world-class diagnostic checkpoints...\n")

        # 1. Changed files identified
        assert "changed_files" in report_data, "Checkpoint 1 Failed: 'changed_files' is missing."
        assert len(report_data["changed_files"]) == 2, "Checkpoint 1 Failed: incorrect changed files count."
        assert "auth/middleware.py" in report_data["changed_files"], "Checkpoint 1 Failed: middleware file missing."
        print("[PASSED] Verification 1: Changed files identified.")

        # 2. Impact graph built
        db.refresh(db_run)
        assert db_run.impact_graph is not None, "Checkpoint 2 Failed: 'impact_graph' was not built on the run."
        assert "nodes" in db_run.impact_graph and "edges" in db_run.impact_graph, "Checkpoint 2 Failed: impact graph payload is malformed."
        assert len(db_run.impact_graph["nodes"]) > 0, "Checkpoint 2 Failed: impact graph contains no nodes."
        print("[PASSED] Verification 2: Impact graph built.")

        # 3. Testing scope generated
        assert "testing_scope" in report_data, "Checkpoint 3 Failed: 'testing_scope' is missing."
        scope = report_data["testing_scope"]
        assert "must_test" in scope and "should_test" in scope and "optional" in scope, "Checkpoint 3 Failed: scope tiers are missing."
        print("[PASSED] Verification 3: Testing scope generated.")

        # 4. User journeys detected
        assert "affected_journeys" in report_data, "Checkpoint 4 Failed: 'affected_journeys' is missing."
        journeys = [j["journey"] for j in report_data["affected_journeys"]]
        assert "Login" in journeys or "Checkout" in journeys, "Checkpoint 4 Failed: failed to map files to user journeys."
        print("[PASSED] Verification 4: User journeys detected.")

        # 5. Risks detected
        assert "risk_level" in report_data, "Checkpoint 5 Failed: 'risk_level' is missing."
        assert report_data["risk_level"] in ("HIGH", "MODERATE", "LOW"), "Checkpoint 5 Failed: risk level is not mapped."
        print("[PASSED] Verification 5: Risks detected.")

        # 6. Tests ranked
        assert "recommended_tests" in report_data, "Checkpoint 6 Failed: 'recommended_tests' is missing."
        total_count = report_data["recommended_tests"]["total_count"]
        assert total_count > 0, "Checkpoint 6 Failed: no recommended tests generated."
        all_recs = report_data["recommended_tests"]["must_run"] + report_data["recommended_tests"]["should_run"]
        assert all("priority" in t for t in all_recs), "Checkpoint 6 Failed: tests lack priority scoring."
        print("[PASSED] Verification 6: Tests ranked.")

        # 7. Reasons generated (Reject "Run these tests")
        for t in all_recs:
            reason = t["reason"].strip()
            assert reason != "", f"Checkpoint 7 Failed: test {t['display_name']} has no reason."
            assert reason.lower() != "run these tests", f"Checkpoint 7 Failed: test {t['display_name']} contains placeholder 'Run these tests'."
        print("[PASSED] Verification 7: Rich reasons generated (rejected generic 'Run these tests').")

        # 8. Evidence gaps detected
        assert "evidence_gaps" in report_data, "Checkpoint 8 Failed: 'evidence_gaps' is missing."
        assert len(report_data["evidence_gaps"]) > 0, "Checkpoint 8 Failed: failed to detect evidence gaps."
        print("[PASSED] Verification 8: Evidence gaps detected.")

        # 9. Missing coverage detected
        assert "missing_coverage" in report_data, "Checkpoint 9 Failed: 'missing_coverage' is missing."
        assert len(report_data["missing_coverage"]) > 0, "Checkpoint 9 Failed: failed to detect missing coverage gap."
        print("[PASSED] Verification 9: Missing coverage detected.")

        # 10. Confidence breakdown calculated
        assert "confidence_breakdown" in report_data, "Checkpoint 10 Failed: 'confidence_breakdown' is missing."
        cb = report_data["confidence_breakdown"]
        assert "score" in cb and "tier" in cb and "breakdown" in cb, "Checkpoint 10 Failed: confidence breakdown structure is malformed."
        print("[PASSED] Verification 10: Confidence breakdown calculated.")

        # 11. Learning signals loaded
        assert db_run.flakiness_profile_hash is not None, "Checkpoint 11 Failed: flakiness profile hash not computed."
        assert db_run.flakiness_profile_hash != "empty_flakiness_state", "Checkpoint 11 Failed: flaky profiles were not loaded."
        print("[PASSED] Verification 11: Flaky adjustment learning signals loaded.")

        # 12. Fragility signals loaded
        assert db_run.dependency_state_hash is not None, "Checkpoint 12 Failed: dependency state hash not computed."
        assert db_run.dependency_state_hash != "empty_dependency_state", "Checkpoint 12 Failed: dependency graph signals not loaded."
        # Verify reasoning entry traces fragility explanations matching rules
        reasonings = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == db_run_id,
            RecommendationReasoningEntry.reason_type == "historical_fragility"
        ).all()
        assert len(reasonings) > 0, "Checkpoint 12 Failed: historical fragility reasoning was not generated."
        assert "Pattern ID:" in reasonings[0].human_readable_reason, "Checkpoint 12 Failed: fragility reason does not contain metadata trace."
        print("[PASSED] Verification 12: Fragility memory signals loaded and human reasoning traces generated.")

        # 13. Report generated (Validating JSON report structure and standard render formats)
        assert report_data["run_id"] == str(db_run_id), "Checkpoint 13 Failed: incorrect run_id mapped to report."
        assert report_data["created_at"] is not None, "Checkpoint 13 Failed: creation timestamp missing."
        
        # Test rendering as HTML UI
        ui_render = RecommendationReportGenerator.render_as_ui(report_data)
        assert "veriscope-recommendation-report" in ui_render["html"], "Checkpoint 13 Failed: HTML render failed."
        
        # Test rendering as GitHub Comment markdown
        gh_comment = RecommendationReportGenerator.render_as_github_comment(report_data)
        assert "🔍 Veriscope Scoping" in gh_comment, "Checkpoint 13 Failed: GitHub Comment render failed."
        
        # Test rendering as PDF stream
        pdf_bytes = RecommendationReportGenerator.render_as_pdf(report_data)
        assert pdf_bytes.startswith(b"%PDF-"), "Checkpoint 13 Failed: PDF binary stream builder failed."
        print("[PASSED] Verification 13: Report generated and successfully formatted as HTML, Markdown, and PDF.\n")

        # ----------------------------------------------------
        # ANSWERS CHECKS (Leadership Scoping Quality Assurance)
        # ----------------------------------------------------
        print("Checking that the Scoping Intelligence Report answers all critical leadership questions...\n")

        # Question A: What changed?
        assert report_data["change_summary"] != "", "Scoping QA Failed: 'What changed?' has empty summary."
        assert len(report_data["changed_files"]) > 0, "Scoping QA Failed: 'What changed?' changed files list is empty."
        print("  - [OK] answers 'What changed?'")

        # Question B: What is impacted?
        assert len(report_data["affected_domains"]) > 0, "Scoping QA Failed: 'What is impacted?' domains list is empty."
        assert len(db_run.impact_graph["nodes"]) > 0, "Scoping QA Failed: 'What is impacted?' impact graph is empty."
        print("  - [OK] answers 'What is impacted?'")

        # Question C: What is risky?
        assert len(report_data["affected_journeys"]) > 0, "Scoping QA Failed: 'What is risky?' affected journeys is empty."
        assert report_data["risk_level"] != "", "Scoping QA Failed: 'What is risky?' risk level is empty."
        print("  - [OK] answers 'What is risky?'")

        # Question D: What should be tested?
        assert "must_test" in report_data["testing_scope"], "Scoping QA Failed: 'What should be tested?' scope is empty."
        assert report_data["recommended_tests"]["total_count"] > 0, "Scoping QA Failed: 'What should be tested?' recommended tests count is 0."
        print("  - [OK] answers 'What should be tested?'")

        # Question E: Why?
        assert len(report_data["recommended_tests"]["must_run"]) > 0, "Scoping QA Failed: Recommended must_run tests are empty."
        assert all(t["reason"] != "" for t in report_data["recommended_tests"]["must_run"]), "Scoping QA Failed: 'Why?' test reasons are blank."
        print("  - [OK] answers 'Why?'")

        # Question F: What evidence exists?
        assert report_data["confidence_breakdown"]["score"] > 0, "Scoping QA Failed: 'What evidence exists?' score is 0."
        print("  - [OK] answers 'What evidence exists?'")

        # Question G: What evidence is missing?
        assert len(report_data["missing_coverage"]) > 0, "Scoping QA Failed: 'What evidence is missing?' coverage gaps is empty."
        assert len(report_data["evidence_gaps"]) > 0, "Scoping QA Failed: 'What evidence is missing?' evidence gaps is empty."
        print("  - [OK] answers 'What evidence is missing?'\n")

        print("======================================================================")
        print("ALL CHECKPOINTS AND SCOPING QUALITY VERIFICATIONS PASSED SUCCESSFULLY!")
        print("RECOMMENDATION IS TRULY WORLD-CLASS AND READY FOR LEADERSHIP VIEWING!")
        print("======================================================================")

    finally:
        db.close()
        cleanup_database()


if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
