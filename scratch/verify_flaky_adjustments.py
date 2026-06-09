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
from app.models.test_result import TestCase, TestResult, TestRun
from app.models.coverage import CoverageReport, FileTestLink
from app.models.flaky_test import FlakyTestProfile
from app.schemas.recommendation import CandidateTestInput
from app.services.flaky_adjustment_service import FlakyAdjustmentService


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
    print("STARTING FLAKY TEST ADJUSTMENT SERVICE INTEGRATION VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()

    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # 1. Seed Organization and Repository
        org = Organization(id=org_id, name="Flaky Corp", slug="flaky-corp")
        db.add(org)
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=777888,
            name="flaky-core",
            full_name="flaky-corp/flaky-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # 2. Seed Test Cases
        # tc1: Stable
        tc_stable_id = uuid.uuid4()
        tc_stable = TestCase(
            id=tc_stable_id,
            repository_id=repo_id,
            suite_name="auth_suite",
            test_name="test_login",
            stable_identity="auth_suite::test_login",
            canonical_identity_hash=hashlib.sha256(b"auth_suite::test_login").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"auth_suite::test_login").hexdigest()
        )

        # tc2: Unstable with stable alternatives
        tc_unstable_id = uuid.uuid4()
        tc_unstable = TestCase(
            id=tc_unstable_id,
            repository_id=repo_id,
            suite_name="billing_suite",
            test_name="test_charge",
            stable_identity="billing_suite::test_charge",
            canonical_identity_hash=hashlib.sha256(b"billing_suite::test_charge").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"billing_suite::test_charge").hexdigest()
        )

        # tc3: Unstable with NO stable alternatives
        tc_unstable_no_alt_id = uuid.uuid4()
        tc_unstable_no_alt = TestCase(
            id=tc_unstable_no_alt_id,
            repository_id=repo_id,
            suite_name="isolated_suite",
            test_name="test_isolated",
            stable_identity="isolated_suite::test_isolated",
            canonical_identity_hash=hashlib.sha256(b"isolated_suite::test_isolated").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"isolated_suite::test_isolated").hexdigest()
        )

        # tc4: Quarantined
        tc_quarantined_id = uuid.uuid4()
        tc_quarantined = TestCase(
            id=tc_quarantined_id,
            repository_id=repo_id,
            suite_name="billing_suite",
            test_name="test_invoice",
            stable_identity="billing_suite::test_invoice",
            canonical_identity_hash=hashlib.sha256(b"billing_suite::test_invoice").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"billing_suite::test_invoice").hexdigest()
        )

        # Stable alternative test cases (Pool of alternatives)
        # alt1: Same suite (+100), same file mapping (+50), same directory (+20), overlapping (+10) = 180 pts
        tc_alt1_id = uuid.uuid4()
        tc_alt1 = TestCase(
            id=tc_alt1_id,
            repository_id=repo_id,
            suite_name="billing_suite",
            test_name="test_billing_alt1",
            stable_identity="billing_suite::test_billing_alt1",
            canonical_identity_hash=hashlib.sha256(b"billing_suite::test_billing_alt1").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"billing_suite::test_billing_alt1").hexdigest()
        )

        # alt2: Same file mapping (+50), same directory (+20), overlapping (+10) = 80 pts
        tc_alt2_id = uuid.uuid4()
        tc_alt2 = TestCase(
            id=tc_alt2_id,
            repository_id=repo_id,
            suite_name="payment_suite",
            test_name="test_payment_alt2",
            stable_identity="payment_suite::test_payment_alt2",
            canonical_identity_hash=hashlib.sha256(b"payment_suite::test_payment_alt2").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"payment_suite::test_payment_alt2").hexdigest()
        )

        # alt3: Same directory only (+20) = 20 pts
        tc_alt3_id = uuid.uuid4()
        tc_alt3 = TestCase(
            id=tc_alt3_id,
            repository_id=repo_id,
            suite_name="billing_controllers_suite",
            test_name="test_payment_alt3",
            stable_identity="billing_controllers_suite::test_payment_alt3",
            canonical_identity_hash=hashlib.sha256(b"billing_controllers_suite::test_payment_alt3").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"billing_controllers_suite::test_payment_alt3").hexdigest()
        )

        # alt4: Same directory only (+20) = 20 pts (lexicographically after alt3)
        tc_alt4_id = uuid.uuid4()
        tc_alt4 = TestCase(
            id=tc_alt4_id,
            repository_id=repo_id,
            suite_name="billing_processors_suite",
            test_name="test_payment_alt4",
            stable_identity="billing_processors_suite::test_payment_alt4",
            canonical_identity_hash=hashlib.sha256(b"billing_processors_suite::test_payment_alt4").hexdigest(),
            identity_lineage_root_hash=hashlib.sha256(b"billing_processors_suite::test_payment_alt4").hexdigest()
        )

        db.add(tc_stable)
        db.add(tc_unstable)
        db.add(tc_unstable_no_alt)
        db.add(tc_quarantined)
        db.add(tc_alt1)
        db.add(tc_alt2)
        db.add(tc_alt3)
        db.add(tc_alt4)
        db.commit()

        # 3. Seed Coverage Report and File Test Links
        cov = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha="dummy-sha",
            file_hash="dummy-hash",
            confidence_score="HIGH"
        )
        db.add(cov)
        db.commit()

        # link direct coverages
        # quarantined covers billing/invoice.py
        link_quar = FileTestLink(
            coverage_report_id=cov.id,
            file_path="billing/invoice.py",
            test_case_id=tc_quarantined_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        # alt1 covers billing/invoice.py
        link_alt1 = FileTestLink(
            coverage_report_id=cov.id,
            file_path="billing/invoice.py",
            test_case_id=tc_alt1_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        # alt2 covers billing/invoice.py
        link_alt2 = FileTestLink(
            coverage_report_id=cov.id,
            file_path="billing/invoice.py",
            test_case_id=tc_alt2_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        # alt3 covers billing/receipt.py (same billing directory)
        link_alt3 = FileTestLink(
            coverage_report_id=cov.id,
            file_path="billing/receipt.py",
            test_case_id=tc_alt3_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        # alt4 covers billing/tax.py (same billing directory)
        link_alt4 = FileTestLink(
            coverage_report_id=cov.id,
            file_path="billing/tax.py",
            test_case_id=tc_alt4_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        # unstable covers billing/invoice.py (so alt1 is stable alternative for unstable)
        link_unstable = FileTestLink(
            coverage_report_id=cov.id,
            file_path="billing/invoice.py",
            test_case_id=tc_unstable_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )
        # unstable_no_alt covers isolated_dir/file.py (no alternative matches)
        link_unstable_no_alt = FileTestLink(
            coverage_report_id=cov.id,
            file_path="isolated_dir/file.py",
            test_case_id=tc_unstable_no_alt_id,
            mapping_type="DIRECT",
            confidence_score="HIGH"
        )

        db.add(link_quar)
        db.add(link_alt1)
        db.add(link_alt2)
        db.add(link_alt3)
        db.add(link_alt4)
        db.add(link_unstable)
        db.add(link_unstable_no_alt)
        db.commit()

        # 4. Seed FlakyTestProfile entries
        # Unstable test (HIGH confidence flakiness -> ONE_TIER_DEGRADATION)
        prof_unstable = FlakyTestProfile(
            repository_id=repo_id,
            test_case_id=tc_unstable_id,
            status="unstable",
            failure_rate=0.45,
            recent_failure_rate=0.45,
            confidence_level="HIGH"
        )
        # Unstable test with no alt (LOW confidence flakiness -> WARNING only)
        prof_unstable_no_alt = FlakyTestProfile(
            repository_id=repo_id,
            test_case_id=tc_unstable_no_alt_id,
            status="unstable",
            failure_rate=0.15,
            recent_failure_rate=0.15,
            confidence_level="LOW"
        )
        # Quarantined test
        prof_quar = FlakyTestProfile(
            repository_id=repo_id,
            test_case_id=tc_quarantined_id,
            status="quarantined",
            failure_rate=0.85,
            recent_failure_rate=0.85,
            confidence_level="HIGH"
        )

        db.add(prof_unstable)
        db.add(prof_unstable_no_alt)
        db.add(prof_quar)
        db.commit()

        print("Seeded Organization, Repository, TestCases, CoverageReport, FileTestLinks, and FlakyTestProfiles.\n")

        # 5. Call apply_flaky_adjustments
        candidate_tests = [
            CandidateTestInput(
                test_case_id=tc_stable_id,
                current_priority_score=0.95,
                reasons=["Direct file coverage"]
            ),
            CandidateTestInput(
                test_case_id=tc_unstable_id,
                current_priority_score=0.80,
                reasons=["Dependency expansion"]
            ),
            CandidateTestInput(
                test_case_id=tc_unstable_no_alt_id,
                current_priority_score=0.90,
                reasons=["Direct file coverage"]
            ),
            CandidateTestInput(
                test_case_id=tc_quarantined_id,
                current_priority_score=0.85,
                reasons=["Historical failure"]
            )
        ]

        bundle = FlakyAdjustmentService.apply_flaky_adjustments(db, repo_id, candidate_tests)

        # 6. Assetions & Verifications
        print("Checking output bundle structure and rules...")

        adjusted_map = {str(c.test_case_id): c for c in bundle.adjusted_candidates}
        
        # Rule 1: Stable tests have no penalty
        stable_adj = adjusted_map.get(str(tc_stable_id))
        assert stable_adj is not None, "Stable test case must be in output candidates"
        assert stable_adj.priority_score == 0.95, f"Expected stable test priority to remain 0.95, got {stable_adj.priority_score}"
        assert not stable_adj.is_excluded, "Stable test must not be excluded"
        assert not stable_adj.is_flaky, "Stable test must not be marked flaky"
        assert stable_adj.status == "stable"
        print("[PASSED] Rule 1: Stable tests remain unaffected.")

        # Rule 2: Unstable tests remain, flagged, degraded, priority reduced slightly if stable alts exist
        unstable_adj = adjusted_map.get(str(tc_unstable_id))
        assert unstable_adj is not None, "Unstable test case must be in output candidates"
        assert not unstable_adj.is_excluded, "Unstable test must NOT be excluded"
        assert unstable_adj.is_flaky, "Unstable test must be marked flaky"
        assert unstable_adj.status == "unstable"
        assert "Warning: Test is unstable and flaky." in unstable_adj.warnings
        # Since tc_unstable has stable alternatives (tc_alt1, tc_alt2, etc.), its priority must be reduced from 0.80 to 0.70
        assert unstable_adj.priority_score == 0.70, f"Expected priority reduced to 0.70, got {unstable_adj.priority_score}"
        print("[PASSED] Rule 2: Unstable tests flagged, and priority reduced slightly if alternatives exist.")

        # Unstable test with no alternative should keep original priority
        unstable_no_alt_adj = adjusted_map.get(str(tc_unstable_no_alt_id))
        assert unstable_no_alt_adj is not None
        assert unstable_no_alt_adj.priority_score == 0.90, f"Expected priority to remain 0.90, got {unstable_no_alt_adj.priority_score}"
        print("[PASSED] Rule 2 (isolated): Unstable test retains original priority when no stable alternatives exist.")

        # Rule 2 evidence degradation: worst case of HIGH confidence is ONE_TIER_DEGRADATION
        assert bundle.evidence_quality_impact == "ONE_TIER_DEGRADATION", f"Expected ONE_TIER_DEGRADATION, got {bundle.evidence_quality_impact}"
        print("[PASSED] Rule 2 (evidence quality): Bundle correctly flagged with worst-case ONE_TIER_DEGRADATION.")

        # Rule 3: Quarantined tests excluded by default, warning added, preserve as warned/excluded
        quar_adj = adjusted_map.get(str(tc_quarantined_id))
        assert quar_adj is not None, "Quarantined test must be preserved in output"
        assert quar_adj.is_excluded, "Quarantined test must be excluded"
        assert quar_adj.is_flaky, "Quarantined test must be marked flaky"
        assert quar_adj.status == "quarantined"
        assert "Warning: Test is quarantined due to high flakiness/instability." in quar_adj.warnings
        print("[PASSED] Rule 3: Quarantined tests are excluded but preserved with warning logs.")

        # Rule 3/4/7: Stable alternatives are recommended (up to 3, ranked by score)
        # Quarantined test has 4 stable alternatives in repo: tc_alt1 (180), tc_alt2 (80), tc_alt3 (20), tc_alt4 (20)
        # Up to 3 should be selected. Top 3 are: tc_alt1, tc_alt2, and tc_alt3 (tie-break lexicographical order)
        quar_alts = quar_adj.quarantined_alternatives
        assert len(quar_alts) == 3, f"Expected 3 stable alternatives, got {len(quar_alts)}"
        assert tc_alt1_id in quar_alts, "tc_alt1 must be selected"
        assert tc_alt2_id in quar_alts, "tc_alt2 must be selected"
        assert tc_alt3_id in quar_alts, "tc_alt3 must be selected (won tie break over tc_alt4)"
        assert tc_alt4_id not in quar_alts, "tc_alt4 must NOT be selected because cap is 3"
        print("[PASSED] Rule 4 & 7: Stable alternatives correctly ranked, tie-broken, and capped at 3.")

        # Ensure that the stable alternatives are recommended and added to adjusted_candidates
        alt1_adj = adjusted_map.get(str(tc_alt1_id))
        alt2_adj = adjusted_map.get(str(tc_alt2_id))
        alt3_adj = adjusted_map.get(str(tc_alt3_id))
        alt4_adj = adjusted_map.get(str(tc_alt4_id))

        assert alt1_adj is not None, "Selected alternative 1 must be recommended"
        assert alt2_adj is not None, "Selected alternative 2 must be recommended"
        assert alt3_adj is not None, "Selected alternative 3 must be recommended"
        assert alt4_adj is None, "Non-selected alternative 4 must NOT be recommended"

        # Check alternative inherits quarantined priority score
        assert alt1_adj.priority_score == 0.85, f"Expected alternative to inherit quarantined score 0.85, got {alt1_adj.priority_score}"
        assert alt1_adj.alternative_to_quarantined == tc_quarantined_id, "Must link back to quarantined test"
        print("[PASSED] Rule 3/4: Stable alternative tests successfully injected and populated.")

        # Rule 6: Explainability entries in reasoning_entries
        reasoning = bundle.reasoning_entries
        assert len(reasoning) > 0, "Reasoning entries must be generated"
        
        # Check quarantined reasoning entry
        quar_reason = next((r for r in reasoning if r["test_case_id"] == str(tc_quarantined_id)), None)
        assert quar_reason is not None, "Quarantined test must have reasoning entry"
        assert quar_reason["reason_type"] == "flaky_adjustment"
        assert quar_reason["evidence_priority"] == "CRITICAL"
        assert quar_reason["metadata"]["status"] == "quarantined"
        assert quar_reason["metadata"]["is_excluded"] is True
        print("[PASSED] Rule 6: Quarantined handling correctly creates CRITICAL explainability audit entry.")

        # Check unstable reasoning entry
        unstable_reason = next((r for r in reasoning if r["test_case_id"] == str(tc_unstable_id)), None)
        assert unstable_reason is not None, "Unstable test must have reasoning entry"
        assert unstable_reason["evidence_priority"] == "IMPORTANT"
        assert unstable_reason["metadata"]["status"] == "unstable"
        print("[PASSED] Rule 6: Unstable adjustment correctly creates IMPORTANT explainability audit entry.")

        # Check alternative reasoning entry
        alt_reason = next((r for r in reasoning if r["test_case_id"] == str(tc_alt1_id)), None)
        assert alt_reason is not None, "Stable alternative must have reasoning entry"
        assert alt_reason["metadata"]["status"] == "stable_alternative"
        assert alt_reason["metadata"]["alternative_to_quarantined"] == str(tc_quarantined_id)
        print("[PASSED] Rule 6: Stable alternative injection correctly creates explainability audit entry.")

        print("\nALL FLAKY TEST ADJUSTMENT RESOLVER INTEGRATION CHECKS PASSED SUCCESSFULLY!\n")

    finally:
        db.close()
        cleanup_database()


if __name__ == "__main__":
    run_verification()
