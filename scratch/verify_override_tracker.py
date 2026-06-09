"""
verify_override_tracker.py
============================
End-to-end verification of RecommendationOverrideTracker.

Covers:
 1. No overrides — trusted execution → widening=False, narrowing=False, ratio=0.0
 2. Widening only — extra tests added → total_manually_added counted
 3. Narrowing only — tests removed → total_manually_removed counted
 4. Both widening and narrowing — mix → override_ratio computed correctly
 5. Critical test removed → critical_tests_removed counted
 6. Flaky test restored → flaky_tests_manually_restored counted
 7. Idempotency — second track() call returns existing record, was_replayed=True
 8. Missing outcome guard — raises ValueError
 9. Missing test outcomes guard — raises ValueError (collector not run)
10. Replayability — same inputs → deterministic OverrideResult
"""

import os
import sys
import uuid
import hashlib
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.artifact import RawArtifact
from app.models.test_result import TestCase, TestRun, TestResult
from app.models.flaky_test import FlakyTestProfile
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationOutcome,
    RecommendationTestOutcome,
    RecommendationOverrideRecord,
    RecommendationReasoningEntry,
)
from app.services.recommendation_override_tracker import (
    RecommendationOverrideTracker,
    OverrideResult,
)

# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _make_org_repo(db, suffix):
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    db.add(Organization(id=org_id, name=f"Override Corp {suffix}", slug=f"override-corp-{suffix}"))
    repo = Repository(
        id=repo_id,
        organization_id=org_id,
        github_repo_id=abs(hash(suffix)) % 500_000,
        name=f"override-repo-{suffix}",
        full_name=f"override-corp-{suffix}/override-repo-{suffix}",
        default_branch="main",
        is_active=True,
    )
    db.add(repo)
    db.flush()
    return org_id, repo_id


def _make_tc(db, repo_id, suite, name):
    stable = f"{suite}::{name}"
    h = hashlib.sha256(stable.encode()).hexdigest()
    tc = TestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name=suite,
        test_name=name,
        stable_identity=stable,
        raw_test_name=name,
        normalized_test_name=name,
        canonical_identity_hash=h,
        identity_lineage_root_hash=h,
        identity_version=1,
        identity_resolution_strategy="EXACT",
    )
    db.add(tc)
    db.flush()
    return tc


def _make_pr(db, repo_id, number):
    pr = PullRequest(
        id=uuid.uuid4(),
        repository_id=repo_id,
        github_pr_id=number,
        number=number,
        title=f"Override PR {number}",
        author="tester",
        source_branch=f"branch-{number}",
        target_branch="main",
        state="open",
        additions=1,
        deletions=0,
        changed_files_count=1,
        head_commit_sha="abc123",
        github_created_at=datetime.datetime.utcnow(),
        github_updated_at=datetime.datetime.utcnow(),
        sync_integrity_status="FULL_SUCCESS",
        evidence_health_status="HEALTHY",
        evidence_consistency_status="CONSISTENT",
    )
    db.add(pr)
    db.flush()
    return pr


def _make_rec_run(db, repo_id, pr_id):
    run = RecommendationRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        pr_id=str(pr_id),
        pull_request_id=pr_id,
        triggered_by="test",
        evidence_quality="HIGH",
        engine_version="v1.0.0",
        ruleset_version="rules-v1",
        degradation_policy_version="policy-v1",
        recommendation_reasoning_summary="override test",
    )
    db.add(run)
    db.flush()
    return run


def _make_outcome(db, run, repo_id, pr_id):
    outcome = RecommendationOutcome(
        id=uuid.uuid4(),
        recommendation_run_id=run.id,
        repository_id=repo_id,
        pull_request_id=pr_id,
        recommendation_snapshot_hash=hashlib.sha256(str(run.id).encode()).hexdigest(),
        outcome_status="PENDING",
    )
    db.add(outcome)
    db.flush()
    return outcome


def _make_test_outcome(
    db,
    outcome_id,
    tc_id,
    recommended_by_veriscope,
    actually_executed,
    manually_added,
    manually_removed,
    execution_result=None,
    execution_presence_status=None,
):
    row = RecommendationTestOutcome(
        id=uuid.uuid4(),
        recommendation_outcome_id=outcome_id,
        test_case_id=tc_id,
        recommended_by_veriscope=recommended_by_veriscope,
        actually_executed=actually_executed,
        manually_added=manually_added,
        manually_removed=manually_removed,
        execution_result=execution_result,
        execution_presence_status=execution_presence_status,
    )
    db.add(row)
    db.flush()
    return row


def _make_reasoning_entry(db, run_id, tc_id, evidence_priority, reason_type="historical_fragility"):
    entry = RecommendationReasoningEntry(
        id=uuid.uuid4(),
        recommendation_run_id=run_id,
        test_case_id=tc_id,
        reason_type=reason_type,
        human_readable_reason=f"Test has {evidence_priority} evidence.",
        confidence_level="HIGH",
        evidence_priority=evidence_priority,
    )
    db.add(entry)
    db.flush()
    return entry


def _make_flaky_profile(db, repo_id, tc_id, status="unstable"):
    profile = FlakyTestProfile(
        id=uuid.uuid4(),
        repository_id=repo_id,
        test_case_id=tc_id,
        failure_rate=0.4,
        recent_failure_rate=0.4,
        instability_score=0.5,
        sample_size=20,
        confidence_level="HIGH",
        status=status,
    )
    db.add(profile)
    db.flush()
    return profile


def cleanup(db):
    try:
        db.query(RecommendationOverrideRecord).delete()
        db.query(RecommendationReasoningEntry).delete()
        db.query(FlakyTestProfile).delete()
        db.query(RecommendationTestOutcome).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationTest).delete()
        db.query(RecommendationRun).delete()
        db.query(TestResult).delete()
        db.query(TestRun).delete()
        db.query(TestCase).delete()
        db.query(PullRequest).delete()
        db.query(RawArtifact).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("Database cleanup successful.")
    except Exception as e:
        db.rollback()
        print(f"Cleanup error: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def run_verification():
    print("======================================================================")
    print("STARTING RECOMMENDATION OVERRIDE TRACKER VERIFICATION")
    print("======================================================================")

    db = SessionLocal()
    pr_counter = [20000]

    def next_pr():
        pr_counter[0] += 1
        return pr_counter[0]

    try:
        # ----------------------------------------------------------------
        # TEST 1: No overrides — exact trusted execution
        # ----------------------------------------------------------------
        print("\n--- TEST 1: No overrides (trusted execution) ---")
        _, r1 = _make_org_repo(db, "ov1")
        pr1 = _make_pr(db, r1, next_pr())
        tc1_a = _make_tc(db, r1, "suite_a", "test_login")
        run1 = _make_rec_run(db, r1, pr1.id)
        out1 = _make_outcome(db, run1, r1, pr1.id)
        # Both tests recommended and executed (trusted)
        _make_test_outcome(db, out1.id, tc1_a.id,
                           recommended_by_veriscope=True, actually_executed=True,
                           manually_added=False, manually_removed=False,
                           execution_result="PASSED", execution_presence_status="EXECUTED")
        db.commit()

        tracker = RecommendationOverrideTracker(db)
        result = tracker.track(run1.id)

        assert result.widening_detected is False
        assert result.narrowing_detected is False
        assert result.total_manually_added == 0
        assert result.total_manually_removed == 0
        assert result.override_ratio == 0.0
        assert result.critical_tests_removed == 0
        assert result.flaky_tests_manually_restored == 0
        assert result.was_replayed is False

        record = db.query(RecommendationOverrideRecord).filter(
            RecommendationOverrideRecord.recommendation_outcome_id == out1.id
        ).first()
        assert record is not None
        assert record.widening_detected is False
        assert record.narrowing_detected is False
        assert record.manually_added_test_ids == []
        assert record.manually_removed_test_ids == []
        print("  SUCCESS: No overrides — ratio=0.0, widening=False, narrowing=False.")

        # ----------------------------------------------------------------
        # TEST 2: Widening only — extra tests executed
        # ----------------------------------------------------------------
        print("\n--- TEST 2: Widening only ---")
        _, r2 = _make_org_repo(db, "ov2")
        pr2 = _make_pr(db, r2, next_pr())
        tc2_rec = _make_tc(db, r2, "suite_b", "test_a")
        tc2_extra = _make_tc(db, r2, "suite_b", "test_extra")
        run2 = _make_rec_run(db, r2, pr2.id)
        out2 = _make_outcome(db, run2, r2, pr2.id)
        # Recommended test executed
        _make_test_outcome(db, out2.id, tc2_rec.id,
                           recommended_by_veriscope=True, actually_executed=True,
                           manually_added=False, manually_removed=False,
                           execution_result="PASSED", execution_presence_status="EXECUTED")
        # Extra test added (widening)
        _make_test_outcome(db, out2.id, tc2_extra.id,
                           recommended_by_veriscope=False, actually_executed=True,
                           manually_added=True, manually_removed=False,
                           execution_result="PASSED", execution_presence_status="EXECUTED")
        db.commit()

        result2 = RecommendationOverrideTracker(db).track(run2.id)
        assert result2.widening_detected is True
        assert result2.narrowing_detected is False
        assert result2.total_manually_added == 1
        assert result2.total_manually_removed == 0
        # ratio = (1 added + 0 removed) / max(1 recommended, 1) = 1.0
        assert result2.override_ratio == 1.0
        record2 = db.query(RecommendationOverrideRecord).filter(
            RecommendationOverrideRecord.recommendation_outcome_id == out2.id
        ).first()
        assert len(record2.manually_added_test_ids) == 1
        assert str(tc2_extra.id) in record2.manually_added_test_ids
        print(f"  SUCCESS: Widening — 1 added, ratio={result2.override_ratio:.2f}.")

        # ----------------------------------------------------------------
        # TEST 3: Narrowing only — recommended test not run
        # ----------------------------------------------------------------
        print("\n--- TEST 3: Narrowing only ---")
        _, r3 = _make_org_repo(db, "ov3")
        pr3 = _make_pr(db, r3, next_pr())
        tc3_run = _make_tc(db, r3, "suite_c", "test_executed")
        tc3_skip = _make_tc(db, r3, "suite_c", "test_removed")
        run3 = _make_rec_run(db, r3, pr3.id)
        out3 = _make_outcome(db, run3, r3, pr3.id)
        _make_test_outcome(db, out3.id, tc3_run.id,
                           recommended_by_veriscope=True, actually_executed=True,
                           manually_added=False, manually_removed=False,
                           execution_result="PASSED", execution_presence_status="EXECUTED")
        _make_test_outcome(db, out3.id, tc3_skip.id,
                           recommended_by_veriscope=True, actually_executed=False,
                           manually_added=False, manually_removed=True,
                           execution_result=None, execution_presence_status="ABSENT")
        db.commit()

        result3 = RecommendationOverrideTracker(db).track(run3.id)
        assert result3.widening_detected is False
        assert result3.narrowing_detected is True
        assert result3.total_manually_removed == 1
        assert result3.total_manually_added == 0
        # ratio = (0 + 1) / max(2 recommended, 1) = 0.5
        assert abs(result3.override_ratio - 0.5) < 1e-6
        record3 = db.query(RecommendationOverrideRecord).filter(
            RecommendationOverrideRecord.recommendation_outcome_id == out3.id
        ).first()
        assert str(tc3_skip.id) in record3.manually_removed_test_ids
        print(f"  SUCCESS: Narrowing — 1 removed, ratio={result3.override_ratio:.2f}.")

        # ----------------------------------------------------------------
        # TEST 4: Both widening and narrowing
        # ----------------------------------------------------------------
        print("\n--- TEST 4: Widening AND narrowing ---")
        _, r4 = _make_org_repo(db, "ov4")
        pr4 = _make_pr(db, r4, next_pr())
        tc4_run = _make_tc(db, r4, "suite_d", "test_run")
        tc4_skip = _make_tc(db, r4, "suite_d", "test_skipped")
        tc4_extra = _make_tc(db, r4, "suite_d", "test_extra")
        run4 = _make_rec_run(db, r4, pr4.id)
        out4 = _make_outcome(db, run4, r4, pr4.id)
        # 2 recommended: one run, one skipped
        _make_test_outcome(db, out4.id, tc4_run.id, True, True, False, False, "PASSED", "EXECUTED")
        _make_test_outcome(db, out4.id, tc4_skip.id, True, False, False, True, None, "ABSENT")
        # 1 extra: not recommended
        _make_test_outcome(db, out4.id, tc4_extra.id, False, True, True, False, "FAILED", "EXECUTED")
        db.commit()

        result4 = RecommendationOverrideTracker(db).track(run4.id)
        assert result4.widening_detected is True
        assert result4.narrowing_detected is True
        assert result4.total_manually_added == 1
        assert result4.total_manually_removed == 1
        # ratio = (1 + 1) / max(2, 1) = 1.0
        assert result4.override_ratio == 1.0
        print(f"  SUCCESS: Both widening+narrowing — ratio={result4.override_ratio:.2f}.")

        # ----------------------------------------------------------------
        # TEST 5: Critical test removed
        # ----------------------------------------------------------------
        print("\n--- TEST 5: Critical test removed ---")
        _, r5 = _make_org_repo(db, "ov5")
        pr5 = _make_pr(db, r5, next_pr())
        tc5_crit = _make_tc(db, r5, "suite_e", "test_critical")
        tc5_norm = _make_tc(db, r5, "suite_e", "test_normal")
        run5 = _make_rec_run(db, r5, pr5.id)
        out5 = _make_outcome(db, run5, r5, pr5.id)
        # Critical test was recommended but not run (manually removed)
        _make_test_outcome(db, out5.id, tc5_crit.id, True, False, False, True, None, "ABSENT")
        _make_test_outcome(db, out5.id, tc5_norm.id, True, True, False, False, "PASSED", "EXECUTED")
        # Create CRITICAL reasoning entry for tc5_crit
        _make_reasoning_entry(db, run5.id, tc5_crit.id, "CRITICAL")
        # Create SUPPORTING reasoning entry for tc5_norm (should NOT be counted)
        _make_reasoning_entry(db, run5.id, tc5_norm.id, "SUPPORTING")
        db.commit()

        result5 = RecommendationOverrideTracker(db).track(run5.id)
        assert result5.critical_tests_removed == 1
        record5 = db.query(RecommendationOverrideRecord).filter(
            RecommendationOverrideRecord.recommendation_outcome_id == out5.id
        ).first()
        assert str(tc5_crit.id) in record5.critical_removed_test_ids
        assert str(tc5_norm.id) not in record5.critical_removed_test_ids
        print(f"  SUCCESS: Critical test removed — critical_tests_removed={result5.critical_tests_removed}.")

        # ----------------------------------------------------------------
        # TEST 6: Flaky test manually restored
        # ----------------------------------------------------------------
        print("\n--- TEST 6: Flaky test manually restored ---")
        _, r6 = _make_org_repo(db, "ov6")
        pr6 = _make_pr(db, r6, next_pr())
        tc6_flaky = _make_tc(db, r6, "suite_f", "test_flaky")
        tc6_stable = _make_tc(db, r6, "suite_f", "test_stable")
        run6 = _make_rec_run(db, r6, pr6.id)
        out6 = _make_outcome(db, run6, r6, pr6.id)
        # Flaky test added manually (not recommended)
        _make_test_outcome(db, out6.id, tc6_flaky.id, False, True, True, False, "PASSED", "EXECUTED")
        # Stable test also added (should NOT be counted as flaky restored)
        _make_test_outcome(db, out6.id, tc6_stable.id, False, True, True, False, "PASSED", "EXECUTED")
        # Only tc6_flaky has a FlakyTestProfile
        _make_flaky_profile(db, r6, tc6_flaky.id, status="unstable")
        db.commit()

        result6 = RecommendationOverrideTracker(db).track(run6.id)
        assert result6.flaky_tests_manually_restored == 1
        record6 = db.query(RecommendationOverrideRecord).filter(
            RecommendationOverrideRecord.recommendation_outcome_id == out6.id
        ).first()
        assert str(tc6_flaky.id) in record6.flaky_restored_test_ids
        assert str(tc6_stable.id) not in record6.flaky_restored_test_ids
        print(f"  SUCCESS: Flaky test restored — flaky_tests_manually_restored={result6.flaky_tests_manually_restored}.")

        # ----------------------------------------------------------------
        # TEST 7: Idempotency — second track() returns existing record
        # ----------------------------------------------------------------
        print("\n--- TEST 7: Idempotency (second track() is no-op) ---")
        result7a = RecommendationOverrideTracker(db).track(run5.id)  # Re-use TEST 5
        result7b = RecommendationOverrideTracker(db).track(run5.id)  # Second call

        assert result7b.was_replayed is True
        assert result7b.total_manually_removed == result7a.total_manually_removed
        # Exactly one record exists
        count = db.query(RecommendationOverrideRecord).filter(
            RecommendationOverrideRecord.recommendation_outcome_id == out5.id
        ).count()
        assert count == 1
        print("  SUCCESS: Idempotency — second call was_replayed=True, no duplicate record.")

        # ----------------------------------------------------------------
        # TEST 8: Missing outcome guard
        # ----------------------------------------------------------------
        print("\n--- TEST 8: Missing outcome guard raises ValueError ---")
        _, r8 = _make_org_repo(db, "ov8")
        pr8 = _make_pr(db, r8, next_pr())
        run8 = _make_rec_run(db, r8, pr8.id)
        # Intentionally NOT creating a RecommendationOutcome
        db.commit()

        try:
            RecommendationOverrideTracker(db).track(run8.id)
            assert False, "Expected ValueError for missing outcome"
        except ValueError as e:
            assert "outcome" in str(e).lower()
            print(f"  SUCCESS: Missing outcome guard raised ValueError: {e}")

        # ----------------------------------------------------------------
        # TEST 9: Missing test outcomes guard (collector not run)
        # ----------------------------------------------------------------
        print("\n--- TEST 9: Missing test outcomes guard raises ValueError ---")
        _, r9 = _make_org_repo(db, "ov9")
        pr9 = _make_pr(db, r9, next_pr())
        run9 = _make_rec_run(db, r9, pr9.id)
        out9 = _make_outcome(db, run9, r9, pr9.id)
        # No RecommendationTestOutcome rows — collector hasn't run
        db.commit()

        try:
            RecommendationOverrideTracker(db).track(run9.id)
            assert False, "Expected ValueError for missing test outcomes"
        except ValueError as e:
            assert "testoutcome" in str(e).lower() or "collector" in str(e).lower() or "no recommendationtestoutcome" in str(e).lower() or "collect" in str(e).lower()
            print(f"  SUCCESS: Missing test outcomes guard raised ValueError: {e}")

        # ----------------------------------------------------------------
        # TEST 10: Replayability — same inputs, deterministic result
        # ----------------------------------------------------------------
        print("\n--- TEST 10: Replayability (deterministic result) ---")
        # Re-run tests 1, 2 results and verify consistency
        result_replay1 = RecommendationOverrideTracker(db).track(run1.id)
        assert result_replay1.was_replayed is True
        assert result_replay1.total_manually_added == 0
        assert result_replay1.total_manually_removed == 0
        assert result_replay1.widening_detected is False
        assert result_replay1.narrowing_detected is False

        result_replay2 = RecommendationOverrideTracker(db).track(run2.id)
        assert result_replay2.was_replayed is True
        assert result_replay2.total_manually_added == 1
        assert result_replay2.widening_detected is True
        print("  SUCCESS: Replayability — replayed results are deterministic.")

        print("\n======================================================================")
        print("ALL RECOMMENDATION OVERRIDE TRACKER TESTS PASSED!")
        print("======================================================================")

    finally:
        db.close()
    cleanup(SessionLocal())


if __name__ == "__main__":
    cleanup(SessionLocal())
    try:
        run_verification()
    finally:
        cleanup(SessionLocal())
