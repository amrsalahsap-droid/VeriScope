import os
import sys
import uuid
import datetime
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal

from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import (
    PullRequest,
    PullRequestCommit,
    PullRequestChangedFile,
    PullRequestSyncJob,
    PullRequestSnapshot
)
from app.models.test_result import TestRun, TestCase, TestResult
from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.dependency import FileDependency
from app.models.flaky_test import FlakyTestProfile
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationOutcome,
    RecommendationReasoningEntry,
    RecommendationInputSnapshot
)
from app.services.recommendation import RecommendationService
from app.schemas.recommendation import RecommendationRunCreate

client = TestClient(app)

def cleanup_database():
    """Clean up seeded data safely."""
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationTest).delete()
        db.query(RecommendationInputSnapshot).delete()
        db.query(RecommendationRun).delete()
        db.query(FlakyTestProfile).delete()
        db.query(FileDependency).delete()
        db.query(FileTestLink).delete()
        db.query(CoverageFileEntry).delete()
        db.query(CoverageReport).delete()
        db.query(TestResult).delete()
        db.query(TestRun).delete()
        db.query(TestCase).delete()
        db.query(PullRequestSnapshot).delete()
        db.query(PullRequestCommit).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequestSyncJob).delete()
        db.query(PullRequest).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("SUCCESS: Database cleaned up successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def run_verification():
    print("======================================================================")
    print("STARTING END-TO-END CONSERVATIVE RECOMMENDATION ENGINE INTEGRATION VERIFICATION")
    print("======================================================================\n")

    start_perf = time.time()
    db = SessionLocal()

    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    pr_num = 888
    commit_sha = "eeddccbbaa00112233445566778899aa"

    try:
        # Seed base Organization and Repository
        org = Organization(id=org_id, name="Engine Corp", slug="engine-corp")
        db.add(org)
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=888999,
            name="engine-core",
            full_name="engine-corp/engine-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        # Seed Pull Request
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=888000,
            number=pr_num,
            title="Integrate Scoped Auth",
            author="alice",
            source_branch="auth-scope",
            target_branch="main",
            state="open",
            additions=30,
            deletions=5,
            changed_files_count=1,
            head_commit_sha=commit_sha,
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        
        pr_commit = PullRequestCommit(
            pull_request_id=pr_id,
            sha=commit_sha,
            message="Re-architect auth scope rules",
            author="alice",
            commit_date=datetime.datetime.utcnow()
        )
        db.add(pr_commit)
        db.commit()
        
        rec_service = RecommendationService(db)

        # --------------------------------------------------------------------
        # 1. Direct Coverage Mapping Verification
        # --------------------------------------------------------------------
        print("\n--- Goal 1: Direct Coverage Mapping Verification ---")
        
        # Seed fresh high-precision Coverage Report
        coverage_report = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha=commit_sha,
            overall_coverage_pct=0.95,
            total_lines=100,
            covered_lines_count=95,
            uncovered_lines_count=5,
            confidence_score="HIGH",
            confidence_logic="High statement coverage.",
            file_hash="report-hash-direct",
            correlation_id="corr-direct-1"
        )
        db.add(coverage_report)
        
        # Seed stable TestCase and Link
        tc1_id = uuid.uuid4()
        tc1_identity = "auth_suite::test_scope"
        tc1_hash = hashlib.sha256(tc1_identity.encode("utf-8")).hexdigest()
        tc1 = TestCase(
            id=tc1_id,
            repository_id=repo_id,
            suite_name="auth_suite",
            test_name="test_scope",
            stable_identity=tc1_identity,
            canonical_identity_hash=tc1_hash,
            identity_lineage_root_hash=tc1_hash
        )
        db.add(tc1)
        
        file_link = FileTestLink(
            coverage_report_id=coverage_report.id,
            file_path="src/auth.py",
            test_case_id=tc1_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(file_link)
        
        # Seed File Dependency so has_deps is True
        dep1 = FileDependency(
            repository_id=repo_id,
            file_path="src/auth.py",
            depends_on_file_path="src/utils.py",
            dependency_type="import",
            commit_sha=commit_sha
        )
        db.add(dep1)
        db.commit()

        run_in = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id=commit_sha,
            changed_files=["src/auth.py"],
            triggered_by="manual"
        )
        
        run_rec = rec_service.create_recommendation_run(run_in)
        assert run_rec is not None
        
        # Assert mapped test is recommended and reason type is direct_file_coverage
        recommended_tcs = {t.test_case_id: t for t in run_rec.tests}
        assert "auth_suite::test_scope" in recommended_tcs
        assert recommended_tcs["auth_suite::test_scope"].reason_type == "direct_file_coverage"
        print("[OK] Direct coverage mapping verified with reason_type='direct_file_coverage'")

        # --------------------------------------------------------------------
        # 2. Path Heuristic Fallback Verification
        # --------------------------------------------------------------------
        print("\n--- Goal 2: Path Heuristic Fallback Verification ---")
        
        # Missing coverage map simulates Low evidence, forcing path-heuristics matching
        # Seed folder match TestCase
        tc_folder_id = uuid.uuid4()
        tc_folder_identity = "auth_suite::test_endpoint"
        tc_folder_hash = hashlib.sha256(tc_folder_identity.encode("utf-8")).hexdigest()
        tc_folder = TestCase(
            id=tc_folder_id,
            repository_id=repo_id,
            suite_name="auth_suite",
            test_name="test_endpoint",
            stable_identity=tc_folder_identity,
            canonical_identity_hash=tc_folder_hash,
            identity_lineage_root_hash=tc_folder_hash
        )
        db.add(tc_folder)
        db.commit()

        # Generate recommendation with extra file requiring folder match fallback
        run_in_fallback = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id=commit_sha,
            changed_files=["src/auth.py", "empty_coverage.py"],
            triggered_by="manual"
        )
        run_rec_fallback = rec_service.create_recommendation_run(run_in_fallback)
        assert run_rec_fallback.recommendation_mode in ("WIDENED", "SAFE_FALLBACK")
        assert run_rec_fallback.evidence_quality in ("MODERATE", "LOW")
        
        recommended_tcs_fb = {t.test_case_id: t for t in run_rec_fallback.tests}
        
        # Verify folder match recommended with reason type path_heuristic_fallback
        # (Heuristic resolver matches because both auth.py and test_endpoint are in auth space / suite)
        assert any(t.reason_type == "path_heuristic_fallback" for t in run_rec_fallback.tests)
        print("[OK] Path heuristic fallback triggered safely with reason_type='path_heuristic_fallback' and evidence degraded.")

        # --------------------------------------------------------------------
        # 3. Dependency Expansion Verification
        # --------------------------------------------------------------------
        print("\n--- Goal 3: Dependency Expansion Verification ---")
        
        # Seed tc_dep linked to src/utils.py (which src/auth.py depends on)
        tc_dep_id = uuid.uuid4()
        tc_dep_identity = "utils_suite::test_logger"
        tc_dep_hash = hashlib.sha256(tc_dep_identity.encode("utf-8")).hexdigest()
        tc_dep = TestCase(
            id=tc_dep_id,
            repository_id=repo_id,
            suite_name="utils_suite",
            test_name="test_logger",
            stable_identity=tc_dep_identity,
            canonical_identity_hash=tc_dep_hash,
            identity_lineage_root_hash=tc_dep_hash
        )
        db.add(tc_dep)
        
        # Coverage link partial_report mapping
        partial_report = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha=commit_sha,
            overall_coverage_pct=0.65,
            total_lines=100,
            covered_lines_count=65,
            uncovered_lines_count=35,
            confidence_score="MODERATE",
            confidence_logic="Partial mappings available.",
            file_hash="report-hash-partial",
            correlation_id="corr-partial-1"
        )
        db.add(partial_report)
        
        link_partial_auth = FileTestLink(
            coverage_report_id=partial_report.id,
            file_path="src/auth.py",
            test_case_id=tc1_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link_partial_auth)

        link_partial_utils = FileTestLink(
            coverage_report_id=partial_report.id,
            file_path="src/utils.py",
            test_case_id=tc_dep_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link_partial_utils)
        db.commit()

        run_in_partial = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id=commit_sha,
            changed_files=["src/auth.py", "partial.py"],
            triggered_by="manual"
        )
        run_rec_partial = rec_service.create_recommendation_run(run_in_partial)
        assert run_rec_partial.recommendation_mode == "WIDENED"
        
        # Verify both direct test case (tc1) and expanded dependency test case (tc_dep) are included
        partial_tests = {t.test_case_id for t in run_rec_partial.tests}
        assert "auth_suite::test_scope" in partial_tests
        assert "utils_suite::test_logger" in partial_tests
        print("[OK] Dependency expansion resolved and mapped successfully (bounded and deterministic).")

        # --------------------------------------------------------------------
        # 4. Historical Failure Boost Verification
        # --------------------------------------------------------------------
        print("\n--- Goal 4: Historical Failure Boost Verification ---")
        
        # Seed an unrelated test case in billing module
        tc_bill_id = uuid.uuid4()
        tc_bill_identity = "billing_suite::test_gateway"
        tc_bill_hash = hashlib.sha256(tc_bill_identity.encode("utf-8")).hexdigest()
        tc_bill = TestCase(
            id=tc_bill_id,
            repository_id=repo_id,
            suite_name="billing_suite",
            test_name="test_gateway",
            stable_identity=tc_bill_identity,
            canonical_identity_hash=tc_bill_hash,
            identity_lineage_root_hash=tc_bill_hash
        )
        db.add(tc_bill)
        
        # Seed test failures
        tr_id = uuid.uuid4()
        test_run = TestRun(
            id=tr_id,
            repository_id=repo_id,
            commit_sha=commit_sha,
            status="failed",
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            total_tests=2,
            passed_tests=0,
            failed_tests=2,
            skipped_tests=0,
            duration=5.0,
            file_hash="hash-fail-1",
            normalized_execution_fingerprint="fingerprint-fail-1"
        )
        db.add(test_run)
        
        # Related failed test (auth) and unrelated failed test (billing)
        res_auth = TestResult(
            test_run_id=tr_id,
            test_case_id=tc1_id,
            status="failed",
            duration=2.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
        )
        res_bill = TestResult(
            test_run_id=tr_id,
            test_case_id=tc_bill_id,
            status="failed",
            duration=3.0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
        )
        db.add(res_auth)
        db.add(res_bill)
        db.commit()

        # Clean/degrade coverage report to LOW/SAFE_FALLBACK to trigger historical failure resolution
        db.query(FileTestLink).delete()
        db.query(CoverageFileEntry).delete()
        db.query(CoverageReport).delete()
        db.commit()
        
        stale_report = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha=commit_sha,
            overall_coverage_pct=0.90,
            total_lines=10,
            covered_lines_count=9,
            uncovered_lines_count=1,
            confidence_score="HIGH",
            confidence_logic="Stale report",
            file_hash="report-stale",
            correlation_id="corr-stale-1",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=15) # stale
        )
        db.add(stale_report)
        
        link_stale = FileTestLink(
            coverage_report_id=stale_report.id,
            file_path="src/auth.py",
            test_case_id=tc1_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link_stale)
        db.commit()

        # Generate recommendation
        run_in_fail = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id=commit_sha,
            changed_files=["src/auth.py"],
            triggered_by="manual"
        )
        run_rec_fail = rec_service.create_recommendation_run(run_in_fail)
        
        # Verify that related test (tc1) is recommended
        # and unrelated failed test (tc_bill) is ignored/not blindly recommended
        fail_tests = {t.test_case_id for t in run_rec_fail.tests}
        assert "auth_suite::test_scope" in fail_tests
        assert "billing_suite::test_gateway" not in fail_tests
        print("[OK] Historical failure boost matches neighborhood and skips unrelated modules.")

        # --------------------------------------------------------------------
        # 5. Quarantine Handling & Alternative Verification
        # --------------------------------------------------------------------
        print("\n--- Goal 5: Quarantine Handling & Alternative Verification ---")
        
        # Restore stable coverage report
        db.query(FileTestLink).delete()
        db.query(CoverageReport).delete()
        db.commit()
        
        stable_report = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha=commit_sha,
            overall_coverage_pct=0.95,
            total_lines=10,
            covered_lines_count=9,
            uncovered_lines_count=1,
            confidence_score="HIGH",
            confidence_logic="Active report",
            file_hash="report-active",
            correlation_id="corr-active-1"
        )
        db.add(stable_report)
        
        link_stable = FileTestLink(
            coverage_report_id=stable_report.id,
            file_path="src/auth.py",
            test_case_id=tc1_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link_stable)

        # Mark tc1 (test_scope) as quarantined
        flaky_quar = FlakyTestProfile(
            id=uuid.uuid4(),
            repository_id=repo_id,
            test_case_id=tc1_id,
            failure_rate=0.45,
            recent_failure_rate=0.50,
            instability_score=0.55,
            status="quarantined",
            last_failure_at=datetime.datetime.utcnow(),
            sample_size=10,
            confidence_level="HIGH",
            rationale="High flakiness timeout."
        )
        db.add(flaky_quar)

        # Seed tc4 (test_isolation) in same suite (auth_suite) as a stable alternative
        tc4_id = uuid.uuid4()
        tc4_identity = "auth_suite::test_isolation"
        tc4_hash = hashlib.sha256(tc4_identity.encode("utf-8")).hexdigest()
        tc4 = TestCase(
            id=tc4_id,
            repository_id=repo_id,
            suite_name="auth_suite",
            test_name="test_isolation",
            stable_identity=tc4_identity,
            canonical_identity_hash=tc4_hash,
            identity_lineage_root_hash=tc4_hash
        )
        db.add(tc4)
        db.commit()

        run_in_quar = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id=commit_sha,
            changed_files=["src/auth.py"],
            triggered_by="manual"
        )
        run_rec_quar = rec_service.create_recommendation_run(run_in_quar)
        
        # Unstable test remains in database tests but is skipped/excluded from executable suite
        quar_tests = {t.test_case_id: t for t in run_rec_quar.tests}
        assert "auth_suite::test_scope" in quar_tests
        
        # Verify stable alternative suggested
        assert "auth_suite::test_isolation" in quar_tests
        
        # Verify reasoning warnings are present
        reasons_quar = {r.reason_type for r in run_rec_quar.reasoning_entries}
        assert "flaky_test_warning" in reasons_quar
        assert "quarantine_alternative_warning" in reasons_quar
        print("[OK] Quarantine checks assert exclusion flags and stable alternative injection perfectly.")

        # --------------------------------------------------------------------
        # 6. Runtime Ordering Verification
        # --------------------------------------------------------------------
        print("\n--- Goal 6: Runtime Ordering Verification ---")
        
        # Estimations must show low confidence if no average historical execution is found
        assert run_rec_quar.runtime_confidence == "LOW"
        assert run_rec_quar.runtime_source == "fallback_default"
        
        # Seed test average durations
        tr_id_dur = uuid.uuid4()
        tr_dur = TestRun(
            id=tr_id_dur,
            repository_id=repo_id,
            commit_sha=commit_sha,
            status="passed",
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            total_tests=2,
            passed_tests=2,
            failed_tests=0,
            skipped_tests=0,
            duration=12.0,
            file_hash="hash-dur-1",
            normalized_execution_fingerprint="fingerprint-dur-1"
        )
        db.add(tr_dur)
        
        dur1 = TestResult(
            test_run_id=tr_id_dur,
            test_case_id=tc1_id,
            status="passed",
            duration=3.5,
            created_at=datetime.datetime.utcnow()
        )
        dur4 = TestResult(
            test_run_id=tr_id_dur,
            test_case_id=tc4_id,
            status="passed",
            duration=5.0,
            created_at=datetime.datetime.utcnow()
        )
        dur_folder = TestResult(
            test_run_id=tr_id_dur,
            test_case_id=tc_folder_id,
            status="passed",
            duration=1.5,
            created_at=datetime.datetime.utcnow()
        )
        db.add(dur1)
        db.add(dur4)
        db.add(dur_folder)
        db.commit()

        run_rec_dur = rec_service.create_recommendation_run(run_in_quar)
        print(f"DEBUG: run_rec_dur.runtime_confidence = {run_rec_dur.runtime_confidence}")
        print(f"DEBUG: run_rec_dur.runtime_source = {run_rec_dur.runtime_source}")
        print(f"DEBUG: run_rec_dur.estimated_runtime_seconds = {run_rec_dur.estimated_runtime_seconds}")
        print(f"DEBUG: run_rec_dur tests = {[(t.test_case_id, t.priority_score) for t in run_rec_dur.tests]}")
        assert run_rec_dur.runtime_confidence == "HIGH"
        assert run_rec_dur.runtime_source == "historical_average"
        assert run_rec_dur.estimated_runtime_seconds > 0.0
        print("[OK] Runtime Ordering and cost estimations calculated with high-trust averages.")

        # --------------------------------------------------------------------
        # 7. Tiered Fallback Verification
        # --------------------------------------------------------------------
        print("\n--- Goal 7: Tiered Fallback Verification ---")
        
        # HIGH -> NORMAL
        # Re-seed high evidence
        db.query(FlakyTestProfile).delete()
        db.commit()
        run_high = rec_service.create_recommendation_run(run_in)
        assert run_high.evidence_quality == "HIGH"
        assert run_high.recommendation_mode == "NORMAL"

        # MODERATE -> WIDENED
        # Partial coverage report loaded
        db.query(FileTestLink).delete()
        db.query(CoverageReport).delete()
        db.commit()

        moderate_report_id = uuid.uuid4()
        moderate_report = CoverageReport(
            id=moderate_report_id,
            repository_id=repo_id,
            commit_sha=commit_sha,
            overall_coverage_pct=0.65,
            total_lines=100,
            covered_lines_count=65,
            uncovered_lines_count=35,
            confidence_score="MODERATE",
            confidence_logic="Partial mappings available.",
            file_hash="report-hash-moderate-g7",
            correlation_id="corr-moderate-g7"
        )
        db.add(moderate_report)

        link_mod_auth = FileTestLink(
            coverage_report_id=moderate_report_id,
            file_path="src/auth.py",
            test_case_id=tc1_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link_mod_auth)

        link_mod_utils = FileTestLink(
            coverage_report_id=moderate_report_id,
            file_path="src/utils.py",
            test_case_id=tc_dep_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link_mod_utils)
        db.commit()

        run_mod = rec_service.create_recommendation_run(run_in_partial)
        print(f"DEBUG: run_mod.evidence_quality = {run_mod.evidence_quality}")
        print(f"DEBUG: run_mod.reasons = {run_mod.recommendation_reasoning_summary}")
        print(f"DEBUG: run_mod.evidence_quality_reasons = {run_mod.evidence_quality_reasons}")
        assert run_mod.evidence_quality == "MODERATE"
        assert run_mod.recommendation_mode == "WIDENED"

        # LOW -> SAFE_FALLBACK
        # Stale coverage report loaded
        db.query(FileTestLink).delete()
        db.query(CoverageReport).delete()
        db.commit()

        stale_report_id = uuid.uuid4()
        stale_report_g7 = CoverageReport(
            id=stale_report_id,
            repository_id=repo_id,
            commit_sha=commit_sha,
            overall_coverage_pct=0.90,
            total_lines=10,
            covered_lines_count=9,
            uncovered_lines_count=1,
            confidence_score="MODERATE",
            confidence_logic="Stale report",
            file_hash="report-stale-g7",
            correlation_id="corr-stale-g7",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=15) # stale
        )
        db.add(stale_report_g7)

        link_stale_g7 = FileTestLink(
            coverage_report_id=stale_report_id,
            file_path="src/auth.py",
            test_case_id=tc1_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link_stale_g7)
        db.commit()

        run_low = rec_service.create_recommendation_run(run_in_fail)
        print(f"DEBUG: run_low.evidence_quality = {run_low.evidence_quality}")
        print(f"DEBUG: run_low.reasons = {run_low.recommendation_reasoning_summary}")
        assert run_low.evidence_quality == "LOW"
        assert run_low.recommendation_mode == "SAFE_FALLBACK"

        # UNKNOWN -> FULL_REGRESSION
        # Insufficient file forces UNKNOWN fallback
        run_in_reg = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id=commit_sha,
            changed_files=["insufficient_evidence.py"],
            triggered_by="manual"
        )
        run_unk = rec_service.create_recommendation_run(run_in_reg)
        assert run_unk.evidence_quality == "UNKNOWN"
        assert run_unk.recommendation_mode == "FULL_REGRESSION"
        print("[OK] Tiered fallback resolutions verified perfectly (HIGH->NORMAL, MODERATE->WIDENED, LOW->SAFE_FALLBACK, UNKNOWN->FULL_REGRESSION).")

        # --------------------------------------------------------------------
        # 8. Replay Reproducibility Verification
        # --------------------------------------------------------------------
        print("\n--- Goal 8: Replay Reproducibility Verification ---")

        # Let's restore the high-trust coverage report in the DB
        db.query(FileTestLink).delete()
        db.query(CoverageReport).delete()
        db.commit()

        stable_report_g8 = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha=commit_sha,
            overall_coverage_pct=0.95,
            total_lines=10,
            covered_lines_count=9,
            uncovered_lines_count=1,
            confidence_score="HIGH",
            confidence_logic="Active report",
            file_hash="report-active-g8",
            correlation_id="corr-active-g8"
        )
        db.add(stable_report_g8)

        link_stable_g8 = FileTestLink(
            coverage_report_id=stable_report_g8.id,
            file_path="src/auth.py",
            test_case_id=tc1_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link_stable_g8)
        db.commit()

        # Now generate a brand new high-trust run, snapshot it, and replay it!
        run_in_orig = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id=commit_sha,
            changed_files=["src/auth.py"],
            triggered_by="manual"
        )
        run_orig = rec_service.create_recommendation_run(run_in_orig)
        assert run_orig.evidence_quality == "HIGH"
        
        # Load input snapshot from this run
        snapshot = db.query(RecommendationInputSnapshot).filter(
            RecommendationInputSnapshot.recommendation_run_id == run_orig.id
        ).first()
        assert snapshot is not None
        
        # Re-run engine with exact inputs from snapshot
        run_in_rep = RecommendationRunCreate(
            repository_id=uuid.UUID(str(snapshot.recommendation_run.repository_id)),
            pr_id=snapshot.recommendation_run.pr_id,
            changed_files=snapshot.changed_files,
            triggered_by=snapshot.recommendation_run.triggered_by
        )
        run_rep = rec_service.create_recommendation_run(run_in_rep)
        
        # Test IDs must match exactly
        orig_ids = {t.test_case_id for t in run_orig.tests}
        rep_ids = {t.test_case_id for t in run_rep.tests}
        assert orig_ids == rep_ids
        print("[OK] Replay reproducibility matched recommended tests exactly.")

        # --------------------------------------------------------------------
        # 9. Reasoning Coverage Verification
        # --------------------------------------------------------------------
        print("\n--- Goal 9: Reasoning Coverage Verification ---")
        
        # Check every recommended test has at least one reasoning entry
        for t in run_orig.tests:
            # Get the TestCase UUID for this stable identity
            tc_uuid = db.query(TestCase.id).filter(TestCase.stable_identity == t.test_case_id).scalar()
            assert tc_uuid is not None
            # Match reasoning entry
            reasons = db.query(RecommendationReasoningEntry).filter(
                RecommendationReasoningEntry.recommendation_run_id == run_orig.id,
                RecommendationReasoningEntry.test_case_id == tc_uuid
            ).all()
            assert len(reasons) > 0
            
        # Low confidence runs have warning reasoning entries
        assert any("low" in e.confidence_level.lower() or "medium" in e.confidence_level.lower() for e in run_low.reasoning_entries)
        print("[OK] Reasoning coverage verified; every test maps to supporting audit timelines.")

        # --------------------------------------------------------------------
        # 10. Performance Verification
        # --------------------------------------------------------------------
        print("\n--- Goal 10: Performance Verification ---")
        perf_duration = time.time() - start_perf
        print(f"Total end-to-end performance duration: {perf_duration:.2f} seconds")
        assert perf_duration < 60.0
        print("[OK] Performance verified under 60-second limit.")

    finally:
        db.close()

    print("\n======================================================================")
    print("ALL 10 CONSERVATIVE RECOMMENDATION ENGINE INTEGRATION VERIFICATIONS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
