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
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.test_result import TestRun, TestCase, TestResult
from app.models.coverage import CoverageReport, FileTestLink
from app.models.flaky_test import FlakyTestProfile
from app.services.historical_failure_resolver import HistoricalFailureResolver


def cleanup_database():
    """Clean up seeded data safely."""
    db = SessionLocal()
    try:
        db.query(FlakyTestProfile).delete()
        db.query(FileTestLink).delete()
        db.query(CoverageReport).delete()
        db.query(TestResult).delete()
        db.query(TestRun).delete()
        db.query(TestCase).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("Database cleaned up successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()


def run_verification():
    print("======================================================================")
    print("STARTING HISTORICAL FAILURE RESOLVER INTEGRATION VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()

    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # Seed Organization and Repository
        org = Organization(id=org_id, name="Fail Corp", slug="fail-corp")
        db.add(org)
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=444555,
            name="fail-core",
            full_name="fail-corp/fail-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # Seed 4 test cases
        tc_direct_id = uuid.uuid4()
        tc_direct = TestCase(
            id=tc_direct_id,
            repository_id=repo_id,
            suite_name="auth_suite",
            test_name="test_login",
            stable_identity="auth_suite::test_login",
            canonical_identity_hash=hashlib.sha256(b"auth_suite::test_login").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"auth_suite::test_login").hexdigest()
        )
        tc_dep_id = uuid.uuid4()
        tc_dep = TestCase(
            id=tc_dep_id,
            repository_id=repo_id,
            suite_name="utils_suite",
            test_name="test_encryption",
            stable_identity="utils_suite::test_encryption",
            canonical_identity_hash=hashlib.sha256(b"utils_suite::test_encryption").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"utils_suite::test_encryption").hexdigest()
        )
        tc_module_id = uuid.uuid4()
        tc_module = TestCase(
            id=tc_module_id,
            repository_id=repo_id,
            suite_name="auth_controllers_suite",
            test_name="test_tokens",
            stable_identity="auth_controllers_suite::test_tokens",
            canonical_identity_hash=hashlib.sha256(b"auth_controllers_suite::test_tokens").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"auth_controllers_suite::test_tokens").hexdigest()
        )
        tc_unrelated_id = uuid.uuid4()
        tc_unrelated = TestCase(
            id=tc_unrelated_id,
            repository_id=repo_id,
            suite_name="billing_suite",
            test_name="test_invoice",
            stable_identity="billing_suite::test_invoice",
            canonical_identity_hash=hashlib.sha256(b"billing_suite::test_invoice").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"billing_suite::test_invoice").hexdigest()
        )
        db.add(tc_direct)
        db.add(tc_dep)
        db.add(tc_module)
        db.add(tc_unrelated)
        db.commit()

        # Seed TestRun and TestResult failures
        tr = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            status="failed",
            file_hash="hash-1",
            normalized_execution_fingerprint="fingerprint-1",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )
        db.add(tr)
        db.flush()

        res_direct = TestResult(
            test_run_id=tr.id,
            test_case_id=tc_direct_id,
            status="failed",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=10)
        )
        res_dep = TestResult(
            test_run_id=tr.id,
            test_case_id=tc_dep_id,
            status="failed",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=5)
        )
        res_module = TestResult(
            test_run_id=tr.id,
            test_case_id=tc_module_id,
            status="failed",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        )
        res_unrelated = TestResult(
            test_run_id=tr.id,
            test_case_id=tc_unrelated_id,
            status="failed",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        )
        db.add(res_direct)
        db.add(res_dep)
        db.add(res_module)
        db.add(res_unrelated)
        db.commit()

        # Seed CoverageReport and links
        cov = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha="dummy-sha",
            overall_coverage_pct=0.90,
            confidence_score="HIGH",
            file_hash="hash-cov-1"
        )
        db.add(cov)
        db.flush()

        # direct links: tc_direct covers src/auth/login.py directly
        link_direct = FileTestLink(
            coverage_report_id=cov.id,
            file_path="src/auth/login.py",
            test_case_id=tc_direct_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        # dependency links: tc_dep covers src/utils/encrypt.py (dependency file)
        link_dep = FileTestLink(
            coverage_report_id=cov.id,
            file_path="src/utils/encrypt.py",
            test_case_id=tc_dep_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        db.add(link_direct)
        db.add(link_dep)
        db.commit()

        # ----------------------------------------------------
        # TEST 1: Scoped Relevance Boosting (Rule 1 & 3 & 6)
        # ----------------------------------------------------
        print("\n--- TEST 1: Scoped Relevance Boosting Priority Scoring ---")
        bundle = HistoricalFailureResolver.resolve_historical_failures(
            db=db,
            repository_id=repo_id,
            changed_files=["src/auth/login.py"],
            dependency_files=["src/utils/encrypt.py"]
        )

        # Output should ONLY contain DIRECT, DEPENDENCY_NEIGHBORHOOD, and SAME_MODULE candidates
        # tc_unrelated (billing) should be EXCLUDED as it is global noise
        assert len(bundle.historical_failure_tests) == 3
        candidate_identities = {c.stable_identity for c in bundle.historical_failure_tests}
        assert "billing_suite::test_invoice" not in candidate_identities

        # A. DIRECT (tc_direct) covers src/auth/login.py directly (Priority 0.90)
        c_direct = [c for c in bundle.historical_failure_tests if c.stable_identity == "auth_suite::test_login"][0]
        assert c_direct.priority_score == 0.90
        assert c_direct.relevance_type == "DIRECT"

        # B. DEPENDENCY_NEIGHBORHOOD (tc_dep) covers src/utils/encrypt.py (Priority 0.80)
        c_dep = [c for c in bundle.historical_failure_tests if c.stable_identity == "utils_suite::test_encryption"][0]
        assert c_dep.priority_score == 0.80
        assert c_dep.relevance_type == "DEPENDENCY_NEIGHBORHOOD"

        # C. SAME_MODULE (tc_module) matches parent folder "auth" in auth_controllers_suite (Priority 0.70)
        c_module = [c for c in bundle.historical_failure_tests if c.stable_identity == "auth_controllers_suite::test_tokens"][0]
        assert c_module.priority_score == 0.70
        assert c_module.relevance_type == "SAME_MODULE"

        # Deterministic sorting (0.90 direct comes first)
        assert bundle.historical_failure_tests[0].stable_identity == "auth_suite::test_login"
        assert bundle.historical_failure_tests[1].stable_identity == "utils_suite::test_encryption"
        assert bundle.historical_failure_tests[2].stable_identity == "auth_controllers_suite::test_tokens"
        print("  - Correct priorities and classifications assigned.")
        print("  - Global noise excluded completely.")
        print("  - Deterministic sort verified.")

        # ----------------------------------------------------
        # TEST 2: Flaky Test Exclusions & Kept Direct (Rule 4)
        # ----------------------------------------------------
        print("\n--- TEST 2: Flaky Exclusions & Exception for Direct Coverage ---")
        # Seed related flaky profile (unstable) for tc_dep and tc_direct
        flaky_direct = FlakyTestProfile(
            id=uuid.uuid4(),
            repository_id=repo_id,
            test_case_id=tc_direct_id,
            status="unstable",
            failure_rate=0.40,
            sample_size=10,
            confidence_level="HIGH"
        )
        flaky_dep = FlakyTestProfile(
            id=uuid.uuid4(),
            repository_id=repo_id,
            test_case_id=tc_dep_id,
            status="quarantined",
            failure_rate=0.60,
            sample_size=10,
            confidence_level="HIGH"
        )
        db.add(flaky_direct)
        db.add(flaky_dep)
        db.commit()

        # Call resolver again:
        # - tc_direct is flaky but DIRECT -> MUST be KEPT (exception rule).
        # - tc_dep is flaky and DEPENDENCY_NEIGHBORHOOD -> MUST be EXCLUDED.
        bundle_flaky = HistoricalFailureResolver.resolve_historical_failures(
            db=db,
            repository_id=repo_id,
            changed_files=["src/auth/login.py"],
            dependency_files=["src/utils/encrypt.py"]
        )

        flaky_identities = {c.stable_identity for c in bundle_flaky.historical_failure_tests}
        assert "auth_suite::test_login" in flaky_identities
        assert "utils_suite::test_encryption" not in flaky_identities
        print("  - Quarantined dependency failure correctly excluded.")
        print("  - Flaky direct coverages retained successfully with warnings.")

        # ----------------------------------------------------
        # TEST 3: Hard limit boundaries (Rule 5)
        # ----------------------------------------------------
        print("\n--- TEST 3: Capped Safety Limits ---")
        # Seed 30 additional direct failures to exceed the cap of 25
        db.query(FlakyTestProfile).delete()
        db.commit()

        for i in range(30):
            tc_extra = TestCase(
                id=uuid.uuid4(),
                repository_id=repo_id,
                suite_name="auth_suite",
                test_name=f"test_auth_extra_{i}",
                stable_identity=f"auth_suite::test_auth_extra_{i}",
                canonical_identity_hash=hashlib.sha256(f"auth_suite::test_auth_extra_{i}".encode("utf-8")).hexdigest(),
                identity_lineage_root_hash=hashlib.sha256(f"auth_suite::test_auth_extra_{i}".encode("utf-8")).hexdigest()
            )
            db.add(tc_extra)
            db.flush()

            # Link directly to changed file src/auth/login.py
            link_extra = FileTestLink(
                coverage_report_id=cov.id,
                file_path="src/auth/login.py",
                test_case_id=tc_extra.id,
                mapping_type="DIRECT",
                confidence_score="HIGH"
            )
            db.add(link_extra)

            res_extra = TestResult(
                test_run_id=tr.id,
                test_case_id=tc_extra.id,
                status="failed",
                created_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=i)
            )
            db.add(res_extra)
        db.commit()

        bundle_cap = HistoricalFailureResolver.resolve_historical_failures(
            db=db,
            repository_id=repo_id,
            changed_files=["src/auth/login.py"],
            dependency_files=["src/utils/encrypt.py"]
        )

        assert len(bundle_cap.historical_failure_tests) == 25
        print("  - Output capped exactly at MAX_HISTORICAL_FAILURE_TESTS = 25.")

    finally:
        db.close()

    print("\n======================================================================")
    print("ALL HISTORICAL FAILURE RESOLVER INTEGRATION VERIFICATIONS PASSED SUCCESSFULLY!")
    print("======================================================================")


if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
