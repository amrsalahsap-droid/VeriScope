import os
import sys
import uuid
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestRun, TestCase, TestResult
from app.models.recommendation import RecommendationRun, RecommendationOutcome

from app.services.failure_evidence_aggregator import FailureEvidenceAggregator
from app.schemas.failure_evidence import (
    FailureEvidenceTestResult,
    FailureEvidenceTestRun,
    FailureEvidencePullRequest,
    FailureEvidenceChangedFile,
    FailureEvidenceRecommendationRun,
    FailureEvidenceRecommendationOutcome,
    FailureEvidenceBundle,
)

def cleanup_database():
    """Safely clean up all tables before and after execution."""
    db = SessionLocal()
    try:
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationRun).delete()
        db.query(PullRequestChangedFile).delete()
        db.query(PullRequest).delete()
        db.query(TestResult).delete()
        db.query(TestRun).delete()
        db.query(TestCase).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("SUCCESS: Database cleaned up successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def run_failure_evidence_verification():
    print("======================================================================")
    print("STARTING PHASE 4: FAILURE EVIDENCE AGGREGATOR INTEGRATION TESTS")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_active_id = uuid.uuid4()
    repo_stale_id = uuid.uuid4()
    
    try:
        # Seed Base Org and Repos
        org = Organization(id=org_id, name="Failure Evidence Org", slug="failure-evidence-org")
        db.add(org)
        
        repo_active = Repository(
            id=repo_active_id,
            organization_id=org_id,
            github_repo_id=111111,
            name="active-repo",
            full_name="failure-evidence-org/active-repo",
            default_branch="main",
            is_active=True
        )
        db.add(repo_active)
        
        repo_stale = Repository(
            id=repo_stale_id,
            organization_id=org_id,
            github_repo_id=222222,
            name="stale-repo",
            full_name="failure-evidence-org/stale-repo",
            default_branch="main",
            is_active=False,
            deactivation_reason="stale repository deactivation"
        )
        db.add(repo_stale)
        db.commit()

        # Seed Stable Test Cases
        tc1_id = uuid.uuid4()
        tc1 = TestCase(
            id=tc1_id,
            repository_id=repo_active_id,
            suite_name="engine_suite",
            test_name="test_normalization",
            stable_identity="engine_suite::test_normalization",
            canonical_identity_hash="hash1",
            identity_lineage_root_hash="hash1"
        )
        db.add(tc1)
        db.commit()

        aggregator = FailureEvidenceAggregator(db)

        # ====================================================================
        # Test 1. Repository Stale Override Behavior
        # ====================================================================
        print("--- 1. Testing Repository Stale/Inactive Overrides ---")
        
        # Stale repo without include_inactive must raise ValueError
        try:
            aggregator.collect_failure_evidence(repo_stale_id, include_inactive=False)
            raise AssertionError("Should have raised ValueError for stale repository.")
        except ValueError as e:
            assert "is inactive/stale" in str(e)
            print("[OK] Default include_inactive=False correctly rejects stale repositories.")

        # Stale repo with include_inactive=True must succeed
        bundle_stale = aggregator.collect_failure_evidence(repo_stale_id, include_inactive=True)
        assert bundle_stale.repository_status == "STALE"
        print("[OK] include_inactive=True successfully allows stale repo audit with STALE status.")

        # ====================================================================
        # Test 2. Exclude Weak Test Evidence & Quality Metadata
        # ====================================================================
        print("\n--- 2. Testing Exclude Weak Evidence & Quality Metadata ---")
        
        # Seed test runs representing active/degraded/insufficient/broken/drift quality
        pr_id = uuid.uuid4()
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_active_id,
            github_pr_id=88001,
            number=801,
            title="Core feature upgrade",
            author="alice",
            source_branch="upgrade-branch",
            target_branch="main",
            state="open",
            head_commit_sha="sha_head_commit_123",
            github_created_at=datetime.utcnow(),
            github_updated_at=datetime.utcnow()
        )
        db.add(pr)
        db.commit()

        # Run 1: Valid failed run
        run_valid = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_active_id,
            commit_sha="sha_head_commit_123",
            pull_request_id=pr_id,
            status="failed",
            failed_tests=1,
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            parser_support_status="ACTIVE",
            replay_drift_detected=False,
            file_hash="hash_v",
            normalized_execution_fingerprint="fingerprint_v",
            created_at=datetime.utcnow()
        )
        db.add(run_valid)

        # Run 2: Excluded due to UNSUPPORTED parser
        run_unsupported = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_active_id,
            commit_sha="sha_head_commit_123",
            pull_request_id=pr_id,
            status="failed",
            failed_tests=1,
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            parser_support_status="UNSUPPORTED",
            replay_drift_detected=False,
            file_hash="hash_u",
            normalized_execution_fingerprint="fingerprint_u",
            created_at=datetime.utcnow()
        )
        db.add(run_unsupported)

        # Run 3: Excluded due to INSUFFICIENT evidence health
        run_insufficient = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_active_id,
            commit_sha="sha_head_commit_123",
            pull_request_id=pr_id,
            status="failed",
            failed_tests=1,
            evidence_health_status="INSUFFICIENT",
            consistency_status="CONSISTENT",
            parser_support_status="ACTIVE",
            replay_drift_detected=False,
            file_hash="hash_i",
            normalized_execution_fingerprint="fingerprint_i",
            created_at=datetime.utcnow()
        )
        db.add(run_insufficient)

        # Run 4: Excluded due to BROKEN consistency
        run_broken = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_active_id,
            commit_sha="sha_head_commit_123",
            pull_request_id=pr_id,
            status="failed",
            failed_tests=1,
            evidence_health_status="HEALTHY",
            consistency_status="BROKEN",
            parser_support_status="ACTIVE",
            replay_drift_detected=False,
            file_hash="hash_b",
            normalized_execution_fingerprint="fingerprint_b",
            created_at=datetime.utcnow()
        )
        db.add(run_broken)

        # Run 5: Excluded due to replay_drift_detected = True
        run_drift = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_active_id,
            commit_sha="sha_head_commit_123",
            pull_request_id=pr_id,
            status="failed",
            failed_tests=1,
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            parser_support_status="ACTIVE",
            replay_drift_detected=True,
            file_hash="hash_d",
            normalized_execution_fingerprint="fingerprint_d",
            created_at=datetime.utcnow()
        )
        db.add(run_drift)

        # Run 6: Backward Compatibility Check - Null drift is INCLUDED
        run_null_drift = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_active_id,
            commit_sha="sha_head_commit_123",
            pull_request_id=pr_id,
            status="failed",
            failed_tests=1,
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            parser_support_status="ACTIVE",
            replay_drift_detected=None, # Null
            file_hash="hash_nd",
            normalized_execution_fingerprint="fingerprint_nd",
            created_at=datetime.utcnow()
        )
        db.add(run_null_drift)

        # Results representing failures
        tres_valid = TestResult(
            id=uuid.uuid4(),
            test_run_id=run_valid.id,
            test_case_id=tc1_id,
            status="failed",
            duration=0.5,
            created_at=datetime.utcnow()
        )
        db.add(tres_valid)

        tres_nd = TestResult(
            id=uuid.uuid4(),
            test_run_id=run_null_drift.id,
            test_case_id=tc1_id,
            status="failed",
            duration=0.6,
            created_at=datetime.utcnow()
        )
        db.add(tres_nd)

        db.commit()

        # Execute aggregator evidence collection
        bundle = aggregator.collect_failure_evidence(repo_active_id)
        
        # Verify active failed runs list only includes: run_valid and run_null_drift
        run_ids = {str(r.test_run_id) for r in bundle.related_test_runs}
        assert len(run_ids) == 2
        assert str(run_valid.id) in run_ids
        assert str(run_null_drift.id) in run_ids
        print("[OK] Weak/corrupted test evidence correctly filtered out.")
        print("[OK] Null replay_drift_detected backward compatibility included successfully.")

        # Verify excluded evidence summaries
        assert bundle.excluded_evidence_summary["unsupported_runs"] == 1
        assert bundle.excluded_evidence_summary["insufficient_runs"] == 1
        assert bundle.excluded_evidence_summary["broken_runs"] == 1
        assert bundle.excluded_evidence_summary["replay_drift_runs"] == 1
        print("[OK] Excluded evidence diagnostics counts logged perfectly.")

        # Verify quality metadata present
        first_run = bundle.related_test_runs[0]
        assert first_run.evidence_health_status == "HEALTHY"
        assert first_run.consistency_status == "CONSISTENT"
        assert first_run.parser_version == "junit_parser.v1"
        assert first_run.normalization_schema_version == "junit_result.v1"
        print("[OK] Quality metadata fields populated successfully on TestRun dto.")

        # ====================================================================
        # Test 3. Denominator Metrics
        # ====================================================================
        print("\n--- 3. Testing Denominator Metrics ---")
        
        # Add a successful run to assert it increments total runs but NOT failed runs
        run_success = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_active_id,
            commit_sha="sha_head_commit_123",
            pull_request_id=pr_id,
            status="passed",
            failed_tests=0,
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            parser_support_status="ACTIVE",
            replay_drift_detected=False,
            file_hash="hash_s",
            normalized_execution_fingerprint="fingerprint_s",
            created_at=datetime.utcnow()
        )
        db.add(run_success)
        
        tres_success = TestResult(
            id=uuid.uuid4(),
            test_run_id=run_success.id,
            test_case_id=tc1_id,
            status="passed",
            duration=0.2,
            created_at=datetime.utcnow()
        )
        db.add(tres_success)
        db.commit()

        bundle_den = aggregator.collect_failure_evidence(repo_active_id)
        # Total runs in window: 6 failed seeded + 1 success = 7 runs
        print(f"DEBUG: total_runs_in_window = {bundle_den.total_runs_in_window}")
        assert bundle_den.total_runs_in_window == 7
        # Verify failed runs count remains 2 (valid runs)
        assert bundle_den.total_failed_runs == 2
        print("[OK] Denominator metrics (total runs and test results) calculated accurately.")

        # ====================================================================
        # Test 4. Deterministic Truncation & Limits
        # ====================================================================
        print("\n--- 4. Testing Deterministic Truncation Replayability ---")
        
        # Temporarily patch MAX_FAILED_RUNS_LIMIT to 1
        FailureEvidenceAggregator.MAX_FAILED_RUNS_LIMIT = 1
        
        bundle_trunc = aggregator.collect_failure_evidence(repo_active_id)
        assert bundle_trunc.truncated is True
        assert "Max limit of 1 failed runs applied" in bundle_trunc.truncation_reason
        assert len(bundle_trunc.related_test_runs) == 1
        print("[OK] Deterministic truncation limit and metadata applied successfully.")

        # Restore default limit
        FailureEvidenceAggregator.MAX_FAILED_RUNS_LIMIT = 1000

        # ====================================================================
        # Test 5. Robust Changed File Sorting
        # ====================================================================
        print("\n--- 5. Testing Stable Changed-File Sorting ---")
        
        # Seed changed files out of order
        file_z = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr_id,
            file_path="src/z_auth.py",
            status="modified",
            additions=5,
            deletions=1,
            previous_filename="src/old_z.py",
            created_at=datetime.utcnow()
        )
        db.add(file_z)

        file_a = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr_id,
            file_path="src/a_auth.py",
            status="modified",
            additions=3,
            deletions=2,
            previous_filename="src/old_a.py",
            created_at=datetime.utcnow()
        )
        db.add(file_a)
        db.commit()

        bundle_sort = aggregator.collect_failure_evidence(repo_active_id)
        # Sorting order must be by: previous_filename or "", file_path, id
        # previous_filename: src/old_a.py comes before src/old_z.py
        file_paths = [f.file_path for f in bundle_sort.related_changed_files]
        assert file_paths == ["src/a_auth.py", "src/z_auth.py"]
        print("[OK] Changed files sorted stably by (previous_filename, file_path, id).")

        # ====================================================================
        # Test 6. Frozen Replay bounds & Recommendation following
        # ====================================================================
        print("\n--- 6. Verifying Replay Window bounds & Recommendations Lineage ---")
        
        # Seed recommendation runs and outcomes
        rec_run = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repo_active_id,
            pr_id="801",
            triggered_by="manual",
            evidence_quality="HIGH",
            recommendation_mode="NORMAL",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Replay tracking",
            pull_request_id=pr_id,
            created_at=datetime.utcnow()
        )
        db.add(rec_run)

        outcome = RecommendationOutcome(
            id=uuid.uuid4(),
            recommendation_run_id=rec_run.id,
            executed_tests=["auth_suite::test_scope"],
            manually_added_tests=["added_test_1"],
            manually_removed_tests=["removed_test_1"],
            was_followed=False,
            override_reason="LOW_TRUST",
            rollback_occurred=True,
            escaped_defect=False,
            created_at=datetime.utcnow()
        )
        db.add(outcome)
        db.commit()

        # Freeze current upper bound
        frozen_time = datetime.utcnow()
        bundle_f1 = aggregator.collect_failure_evidence(repo_active_id, evidence_window_end=frozen_time)
        
        # Assert outcome fields mapped
        assert len(bundle_f1.linked_incidents) == 1
        linked_outcome = bundle_f1.linked_incidents[0]
        assert linked_outcome.was_followed is False
        assert linked_outcome.manually_added_tests == ["added_test_1"]
        assert linked_outcome.manually_removed_tests == ["removed_test_1"]
        assert linked_outcome.override_reason == "LOW_TRUST"
        assert linked_outcome.rollback_occurred is True
        print("[OK] Recommendation outcome following lineage preserved successfully.")

        # Seed more items after frozen time
        run_late = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_active_id,
            commit_sha="sha_head_commit_123",
            pull_request_id=pr_id,
            status="failed",
            failed_tests=1,
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            parser_support_status="ACTIVE",
            replay_drift_detected=False,
            file_hash="hash_l",
            normalized_execution_fingerprint="fingerprint_l",
            created_at=frozen_time + timedelta(seconds=10)
        )
        db.add(run_late)
        db.commit()

        # Collect with same frozen time upper bound
        bundle_f2 = aggregator.collect_failure_evidence(repo_active_id, evidence_window_end=frozen_time)
        # Should not include run_late
        run_ids_f2 = {str(r.test_run_id) for r in bundle_f2.related_test_runs}
        assert str(run_late.id) not in run_ids_f2
        print("[OK] Upper bound evidence_window_end remains strictly frozen and immutable.")

    finally:
        db.close()

    print("\n======================================================================")
    print("ALL FailureEvidenceAggregator RECALCULATION & TRUST CALIBRATIONS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_failure_evidence_verification()
    finally:
        cleanup_database()
