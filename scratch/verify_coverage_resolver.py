import os
import sys
import uuid
import datetime
import hashlib
from pathlib import Path
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.user import Workspace
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.test_result import TestCase
from app.models.coverage import CoverageReport, FileTestLink
from app.services.coverage_evidence_resolver import CoverageEvidenceResolver


def cleanup_database():
    """Clean up seeded data safely."""
    db = SessionLocal()
    try:
        db.query(FileTestLink).delete()
        db.query(TestCase).delete()
        db.query(CoverageReport).delete()
        db.query(PullRequest).delete()
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
    print("STARTING COVERAGE EVIDENCE RESOLVER INTEGRATION VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()

    ws_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # Seed Workspace and Repository
        ws = Workspace(id=ws_id, name="Coverage Corp", slug=f"coverage-corp-{uuid.uuid4().hex[:6]}")
        db.add(ws)
        repo = Repository(
            id=repo_id,
            workspace_id=ws_id,
            github_repo_id=111222,
            installation_id=123456,
            name="coverage-core",
            full_name="coverage-corp/coverage-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # Seed test cases
        tc1_id = uuid.uuid4()
        tc1 = TestCase(
            id=tc1_id,
            repository_id=repo_id,
            suite_name="auth_suite",
            test_name="test_login",
            stable_identity="auth_suite::test_login",
            canonical_identity_hash=hashlib.sha256(b"auth_suite::test_login").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"auth_suite::test_login").hexdigest()
        )
        tc2_id = uuid.uuid4()
        tc2 = TestCase(
            id=tc2_id,
            repository_id=repo_id,
            suite_name="billing_suite",
            test_name="test_invoice",
            stable_identity="billing_suite::test_invoice",
            canonical_identity_hash=hashlib.sha256(b"billing_suite::test_invoice").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"billing_suite::test_invoice").hexdigest()
        )
        db.add(tc1)
        db.add(tc2)
        db.commit()

        # ----------------------------------------------------
        # TEST 1: Exact Commit Match preferred over newer repository reports
        # ----------------------------------------------------
        print("\n--- TEST 1: Exact Commit Coverage Matching Preference ---")
        commit_exact = "sha_exact_11111111111111111111"
        commit_newer = "sha_newer_22222222222222222222"

        # Report for exact commit
        report_exact = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            workspace_id=ws_id,
            format="LCOV",
            source="MANUAL_UPLOAD",
            commit_sha=commit_exact,
            overall_coverage_pct=0.90,
            line_coverage_ratio=0.90,
            confidence_score="HIGH",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            file_hash="hash-exact-1",
            files_total=1,
            covered_lines_total=90,
            uncovered_lines_total=10,
            total_lines=100,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )
        # Report for newer commit (simulating a newer report being generated for another branch/run)
        report_newer = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            workspace_id=ws_id,
            format="LCOV",
            source="MANUAL_UPLOAD",
            commit_sha=commit_newer,
            overall_coverage_pct=0.95,
            line_coverage_ratio=0.95,
            confidence_score="HIGH",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            file_hash="hash-newer-2",
            files_total=1,
            covered_lines_total=95,
            uncovered_lines_total=5,
            total_lines=100,
            created_at=datetime.datetime.utcnow()
        )
        db.add(report_exact)
        db.add(report_newer)
        db.commit()

        # Seed Direct Test link for exact report
        link_exact = FileTestLink(
            coverage_report_id=report_exact.id,
            file_path="src/auth.py",
            test_case_id=tc1_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link_exact)
        db.commit()

        # Call resolver
        bundle = CoverageEvidenceResolver.resolve_coverage(
            db=db,
            repository_id=repo_id,
            pull_request_id=None,
            head_commit_sha=commit_exact,
            changed_files=["src/auth.py", "src/uncovered.py"]
        )

        assert bundle.coverage_report_id == report_exact.id
        assert bundle.coverage_confidence == "HIGH"
        assert bundle.coverage_is_missing is False
        assert bundle.coverage_is_stale is False
        assert "exact commit match" in bundle.reasons[0].lower()

        # Verify mapping trust & group by file
        assert "src/auth.py" in bundle.coverage_links_by_file
        auth_links = bundle.coverage_links_by_file["src/auth.py"]
        assert len(auth_links) == 1
        assert auth_links[0].stable_identity == "auth_suite::test_login"
        assert auth_links[0].confidence_score == "HIGH"  # DIRECT -> HIGH

        # Verify uncovered changed file
        assert "src/uncovered.py" in bundle.uncovered_changed_files
        print("  - Exact commit report selected over newer repository reports.")
        print("  - Direct mapping trust (HIGH) and uncovered list verified.")

        # ----------------------------------------------------
        # TEST 2: Fallback to latest repository report (Rule 3)
        # ----------------------------------------------------
        print("\n--- TEST 2: Safe Fallback to Latest Repository Report ---")
        commit_no_exact = "sha_no_exact_333333333333333333"

        # Link newer report file so we get a link when falling back
        link_newer = FileTestLink(
            coverage_report_id=report_newer.id,
            file_path="src/auth.py",
            test_case_id=tc2_id,
            mapping_type="HEURISTIC_NAMING",
            confidence_score="HIGH"
        )
        db.add(link_newer)
        db.commit()

        # Call resolver for a commit with no exact coverage report.
        # Should fallback to `report_newer` since it's the latest report for this repository
        bundle_fallback = CoverageEvidenceResolver.resolve_coverage(
            db=db,
            repository_id=repo_id,
            pull_request_id=None,
            head_commit_sha=commit_no_exact,
            changed_files=["src/auth.py"]
        )

        assert bundle_fallback.coverage_report_id == report_newer.id
        assert bundle_fallback.coverage_confidence == "HIGH"
        assert bundle_fallback.coverage_is_missing is False
        assert "latest repository coverage report" in bundle_fallback.reasons[0].lower()

        # Verify heuristic naming mapping trust (MODERATE)
        auth_fallback_links = bundle_fallback.coverage_links_by_file["src/auth.py"]
        assert len(auth_fallback_links) == 1
        assert auth_fallback_links[0].stable_identity == "billing_suite::test_invoice"
        assert auth_fallback_links[0].confidence_score == "MODERATE"  # HEURISTIC_NAMING -> MODERATE
        print("  - Successfully fell back to latest repository report.")
        print("  - Heuristic naming trust classified as MODERATE.")

        # ----------------------------------------------------
        # TEST 3: Stale repository report rejected (Rule 3)
        # ----------------------------------------------------
        print("\n--- TEST 3: Rejecting Stale Repository Fallback Report ---")
        # Delete reports and seed only a stale report (> 14 days)
        db.query(FileTestLink).delete()
        db.query(CoverageReport).delete()
        db.commit()

        stale_date = datetime.datetime.utcnow() - datetime.timedelta(days=15)
        report_stale = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            workspace_id=ws_id,
            format="LCOV",
            source="MANUAL_UPLOAD",
            commit_sha="sha_stale_999",
            overall_coverage_pct=0.90,
            line_coverage_ratio=0.90,
            confidence_score="HIGH",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            file_hash="hash-stale-999",
            files_total=1,
            covered_lines_total=90,
            uncovered_lines_total=10,
            total_lines=100,
            created_at=stale_date
        )
        db.add(report_stale)
        db.commit()

        # Fallback to stale repo report should be REJECTED!
        bundle_stale_rejected = CoverageEvidenceResolver.resolve_coverage(
            db=db,
            repository_id=repo_id,
            pull_request_id=None,
            head_commit_sha="sha_some_pr_commit",
            changed_files=["src/auth.py"]
        )

        assert bundle_stale_rejected.coverage_is_missing is True
        assert bundle_stale_rejected.coverage_confidence == "UNKNOWN"
        assert "no valid coverage report available" in bundle_stale_rejected.reasons[0].lower()
        print("  - Stale fallback repository report successfully rejected.")

        # ----------------------------------------------------
        # TEST 4: Low Confidence Repository report rejected (Rule 3)
        # ----------------------------------------------------
        print("\n--- TEST 4: Rejecting Low Confidence Fallback Report ---")
        db.query(CoverageReport).delete()
        db.commit()

        report_low_conf = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            workspace_id=ws_id,
            format="LCOV",
            source="MANUAL_UPLOAD",
            commit_sha="sha_low_conf_999",
            overall_coverage_pct=0.70,
            line_coverage_ratio=0.70,
            confidence_score="LOW",
            coverage_confidence="LOW",
            evidence_health_status="HEALTHY",
            file_hash="hash-low-999",
            files_total=1,
            covered_lines_total=70,
            uncovered_lines_total=30,
            total_lines=100,
            created_at=datetime.datetime.utcnow()
        )
        db.add(report_low_conf)
        db.commit()

        bundle_low_conf_rejected = CoverageEvidenceResolver.resolve_coverage(
            db=db,
            repository_id=repo_id,
            pull_request_id=None,
            head_commit_sha="sha_some_pr_commit_2",
            changed_files=["src/auth.py"]
        )

        assert bundle_low_conf_rejected.coverage_is_missing is True
        assert bundle_low_conf_rejected.coverage_confidence == "UNKNOWN"
        assert "no valid coverage report available" in bundle_low_conf_rejected.reasons[0].lower()
        print("  - Low confidence fallback repository report successfully rejected.")

        # ----------------------------------------------------
        # TEST 5: Stale Exact Match report degrades confidence (Rule 3)
        # ----------------------------------------------------
        print("\n--- TEST 5: Stale Exact Match Report Confidence Degradation ---")
        db.query(CoverageReport).delete()
        db.commit()

        commit_stale_exact = "sha_stale_exact_999"
        report_stale_exact = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            workspace_id=ws_id,
            format="LCOV",
            source="MANUAL_UPLOAD",
            commit_sha=commit_stale_exact,
            overall_coverage_pct=0.90,
            line_coverage_ratio=0.90,
            confidence_score="HIGH",
            coverage_confidence="HIGH",
            evidence_health_status="HEALTHY",
            file_hash="hash-stale-exact-999",
            files_total=1,
            covered_lines_total=90,
            uncovered_lines_total=10,
            total_lines=100,
            created_at=stale_date
        )
        db.add(report_stale_exact)
        db.commit()

        bundle_stale_exact = CoverageEvidenceResolver.resolve_coverage(
            db=db,
            repository_id=repo_id,
            pull_request_id=None,
            head_commit_sha=commit_stale_exact,
            changed_files=["src/auth.py"]
        )

        # Exact match is allowed even if stale, but its confidence must degrade:
        # HIGH -> MODERATE
        assert bundle_stale_exact.coverage_report_id == report_stale_exact.id
        assert bundle_stale_exact.coverage_is_stale is True
        assert bundle_stale_exact.coverage_confidence == "MODERATE"
        assert any("stale" in r.lower() for r in bundle_stale_exact.reasons)
        print("  - Stale exact match report allowed, and confidence degraded from HIGH to MODERATE.")

        # ----------------------------------------------------
        # TEST 6: Rule 6 Heuristic Path trust (LOW) and mapping sorting
        # ----------------------------------------------------
        print("\n--- TEST 6: Heuristic Path mapping and deterministic sorting ---")
        # Add multiple links out of order to verify sorting and trust mapping
        link_path_1 = FileTestLink(
            coverage_report_id=report_stale_exact.id,
            file_path="src/auth.py",
            test_case_id=tc2_id,  # billing_suite::test_invoice
            mapping_type="HEURISTIC_PATH",
            confidence_score="LOW"
        )
        link_path_2 = FileTestLink(
            coverage_report_id=report_stale_exact.id,
            file_path="src/auth.py",
            test_case_id=tc1_id,  # auth_suite::test_login
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link_path_1)
        db.add(link_path_2)
        db.commit()

        bundle_sort = CoverageEvidenceResolver.resolve_coverage(
            db=db,
            repository_id=repo_id,
            pull_request_id=None,
            head_commit_sha=commit_stale_exact,
            changed_files=["src/auth.py"]
        )

        auth_sort_links = bundle_sort.coverage_links_by_file["src/auth.py"]
        assert len(auth_sort_links) == 2
        # Deterministically sorted alphabetically by stable_identity:
        # auth_suite::test_login should come before billing_suite::test_invoice
        assert auth_sort_links[0].stable_identity == "auth_suite::test_login"
        assert auth_sort_links[0].confidence_score == "HIGH"
        assert auth_sort_links[1].stable_identity == "billing_suite::test_invoice"
        assert auth_sort_links[1].confidence_score == "LOW"  # HEURISTIC_PATH -> LOW

        # Verify direct and heuristic test list categorization
        assert "auth_suite::test_login" in bundle_sort.direct_test_mappings
        assert "billing_suite::test_invoice" in bundle_sort.heuristic_test_mappings
        print("  - Links sorted deterministically.")
        print("  - Direct and Heuristic test lists correctly populated.")

    finally:
        db.close()

    print("\n======================================================================")
    print("ALL COVERAGE EVIDENCE RESOLVER INTEGRATION VERIFICATIONS PASSED SUCCESSFULLY!")
    print("======================================================================")


if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
