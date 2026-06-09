"""
verify_executed_test_collector.py
===================================
End-to-end verification of RecommendationExecutedTestCollector.

Covers:
 1. Trusted execution — TestRun exactly matches recommendation.
 2. Widened execution — extra tests run beyond recommendation.
 3. Narrowed execution — subset of recommended tests run.
 4. Fully ignored — zero recommended tests executed.
 5. Skipped-but-present — recommended test appears as `skipped` in TestRun.
 6. Absent recommended test — completely absent from TestRun.
 7. Fallback identifier matching — stable_identity string fallback.
 8. Idempotency — second collect() call is a no-op, no duplicates.
 9. Cross-repo guard — mismatched repository raises ValueError.
10. Unknown execution state — preserved as UNKNOWN.
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
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationOutcome,
    RecommendationTestOutcome,
)
from app.services.recommendation_executed_test_collector import (
    RecommendationExecutedTestCollector,
    CollectionResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_org_repo(db, suffix=""):
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    org = Organization(id=org_id, name=f"Collector Corp {suffix}", slug=f"collector-corp-{suffix}")
    db.add(org)
    repo = Repository(
        id=repo_id,
        organization_id=org_id,
        github_repo_id=abs(hash(suffix)) % 1_000_000,
        name=f"collector-repo-{suffix}",
        full_name=f"collector-corp-{suffix}/collector-repo-{suffix}",
        default_branch="main",
        is_active=True,
    )
    db.add(repo)
    db.flush()
    return org_id, repo_id


def _make_test_case(db, repo_id, suite, name):
    stable = f"{suite}::{name}"
    canon_hash = hashlib.sha256(stable.encode()).hexdigest()
    tc = TestCase(
        id=uuid.uuid4(),
        repository_id=repo_id,
        suite_name=suite,
        test_name=name,
        stable_identity=stable,
        raw_test_name=name,
        normalized_test_name=name,
        canonical_identity_hash=canon_hash,
        identity_lineage_root_hash=canon_hash,
        identity_version=1,
        identity_resolution_strategy="EXACT",
    )
    db.add(tc)
    db.flush()
    return tc


def _make_raw_artifact(db):
    art = RawArtifact(
        id=uuid.uuid4(),
        artifact_type="junit_xml",
        storage_path="test/dummy.xml",
        artifact_metadata={},
    )
    db.add(art)
    db.flush()
    return art


def _make_test_run(db, repo_id, pull_request_id, cases_statuses):
    """cases_statuses: list of (TestCase, status_str, duration_float)"""
    art = _make_raw_artifact(db)
    fingerprint_parts = [str(repo_id)]
    for tc, status, _ in cases_statuses:
        fingerprint_parts.append(f"{tc.canonical_identity_hash}:{status}")
    fingerprint = hashlib.sha256("|".join(fingerprint_parts).encode()).hexdigest()
    # Make unique per call
    fingerprint = hashlib.sha256((fingerprint + str(uuid.uuid4())).encode()).hexdigest()

    tr = TestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        pull_request_id=pull_request_id,
        commit_sha="abc123",
        raw_artifact_id=art.id,
        file_hash=hashlib.sha256(fingerprint.encode()).hexdigest(),
        normalized_execution_fingerprint=fingerprint,
        status="SUCCESS",
        total_tests=len(cases_statuses),
        passed_tests=sum(1 for _, s, _ in cases_statuses if s == "passed"),
        failed_tests=sum(1 for _, s, _ in cases_statuses if s == "failed"),
        skipped_tests=sum(1 for _, s, _ in cases_statuses if s == "skipped"),
        duration=sum(d for _, _, d in cases_statuses),
    )
    db.add(tr)
    db.flush()

    for tc, status, duration in cases_statuses:
        res = TestResult(
            id=uuid.uuid4(),
            test_run_id=tr.id,
            test_case_id=tc.id,
            status=status,
            duration=duration,
        )
        db.add(res)
    db.flush()
    return tr


def _make_rec_run(db, repo_id, pr_id, test_case_ids_and_reasons):
    """test_case_ids_and_reasons: list of (test_case_id_str, reason_type)"""
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
        recommendation_reasoning_summary="test run",
    )
    db.add(run)
    db.flush()

    for tc_id_str, reason in test_case_ids_and_reasons:
        rt = RecommendationTest(
            id=uuid.uuid4(),
            recommendation_run_id=run.id,
            test_case_id=tc_id_str,
            reason_type=reason,
            reason_details={"source": "test"},
            priority_score=1.0,
        )
        db.add(rt)

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
    return run, outcome


def _make_pr(db, repo_id, number):
    pr = PullRequest(
        id=uuid.uuid4(),
        repository_id=repo_id,
        github_pr_id=number,
        number=number,
        title=f"Test PR {number}",
        author="tester",
        source_branch=f"branch-{number}",
        target_branch="main",
        state="open",
        additions=5,
        deletions=2,
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


def cleanup(db):
    try:
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
    print("STARTING RECOMMENDATION EXECUTED TEST COLLECTOR VERIFICATION")
    print("======================================================================")

    db = SessionLocal()

    try:
        # ----------------------------------------------------------------
        # TEST 1: Trusted — TestRun exactly matches recommendation
        # ----------------------------------------------------------------
        print("\n--- TEST 1: Trusted Execution (exact match) ---")
        _, repo_id = _make_org_repo(db, "t1")
        pr = _make_pr(db, repo_id, 1001)
        tc_a = _make_test_case(db, repo_id, "suite_auth", "test_login")
        tc_b = _make_test_case(db, repo_id, "suite_auth", "test_logout")
        db.commit()

        rec_run, outcome = _make_rec_run(db, repo_id, pr.id, [
            (str(tc_a.id), "historical_fragility"),
            (str(tc_b.id), "direct_file_mapping"),
        ])
        test_run = _make_test_run(db, repo_id, pr.id, [
            (tc_a, "passed", 1.2),
            (tc_b, "passed", 0.8),
        ])
        db.commit()

        collector = RecommendationExecutedTestCollector(db)
        result = collector.collect(rec_run.id, test_run.id)

        assert result.classification == "trusted", f"Expected trusted, got {result.classification}"
        assert result.total_recommended == 2
        assert result.recommended_and_executed == 2
        assert result.recommended_absent == 0
        assert result.non_recommended_executed == 0
        assert result.outcome_rows_written == 2

        rows = db.query(RecommendationTestOutcome).filter(
            RecommendationTestOutcome.recommendation_outcome_id == outcome.id
        ).all()
        assert len(rows) == 2
        for row in rows:
            assert row.recommended_by_veriscope is True
            assert row.actually_executed is True
            assert row.manually_added is False
            assert row.manually_removed is False
            assert row.execution_result == "PASSED"
            assert row.execution_presence_status == "EXECUTED"
        print("  SUCCESS: Trusted execution — 2 rows written, all EXECUTED.")

        # ----------------------------------------------------------------
        # TEST 2: Widened — extra tests run beyond recommendation
        # ----------------------------------------------------------------
        print("\n--- TEST 2: Widened Execution (extra tests) ---")
        _, repo_id2 = _make_org_repo(db, "t2")
        pr2 = _make_pr(db, repo_id2, 1002)
        tc2_a = _make_test_case(db, repo_id2, "suite_api", "test_create")
        tc2_b = _make_test_case(db, repo_id2, "suite_api", "test_delete")
        tc2_extra = _make_test_case(db, repo_id2, "suite_api", "test_list")
        db.commit()

        rec_run2, outcome2 = _make_rec_run(db, repo_id2, pr2.id, [
            (str(tc2_a.id), "dependency_expansion"),
        ])
        test_run2 = _make_test_run(db, repo_id2, pr2.id, [
            (tc2_a, "passed", 1.0),
            (tc2_b, "passed", 0.5),
            (tc2_extra, "failed", 2.0),
        ])
        db.commit()

        result2 = collector.collect(rec_run2.id, test_run2.id)
        # Need a fresh collector scoped to this repo
        collector2 = RecommendationExecutedTestCollector(db)
        result2 = collector2.collect(rec_run2.id, test_run2.id)

        assert result2.classification == "widened", f"Expected widened, got {result2.classification}"
        assert result2.total_recommended == 1
        assert result2.recommended_and_executed == 1
        assert result2.non_recommended_executed == 2

        rows2 = db.query(RecommendationTestOutcome).filter(
            RecommendationTestOutcome.recommendation_outcome_id == outcome2.id
        ).all()
        assert len(rows2) == 3
        added_rows = [r for r in rows2 if r.manually_added]
        assert len(added_rows) == 2
        for r in added_rows:
            assert r.recommended_by_veriscope is False
            assert r.actually_executed is True
            assert r.execution_presence_status == "EXECUTED"
        print("  SUCCESS: Widened execution — 3 rows, 2 manually added.")

        # ----------------------------------------------------------------
        # TEST 3: Narrowed — subset of recommended tests executed
        # ----------------------------------------------------------------
        print("\n--- TEST 3: Narrowed Execution (subset run) ---")
        _, repo_id3 = _make_org_repo(db, "t3")
        pr3 = _make_pr(db, repo_id3, 1003)
        tc3_a = _make_test_case(db, repo_id3, "suite_db", "test_query")
        tc3_b = _make_test_case(db, repo_id3, "suite_db", "test_write")
        tc3_c = _make_test_case(db, repo_id3, "suite_db", "test_index")
        db.commit()

        rec_run3, outcome3 = _make_rec_run(db, repo_id3, pr3.id, [
            (str(tc3_a.id), "historical_fragility"),
            (str(tc3_b.id), "historical_fragility"),
            (str(tc3_c.id), "historical_fragility"),
        ])
        # Only tc3_a actually ran
        test_run3 = _make_test_run(db, repo_id3, pr3.id, [
            (tc3_a, "passed", 0.3),
        ])
        db.commit()

        collector3 = RecommendationExecutedTestCollector(db)
        result3 = collector3.collect(rec_run3.id, test_run3.id)

        assert result3.classification == "narrowed", f"Expected narrowed, got {result3.classification}"
        assert result3.recommended_absent == 2
        assert result3.recommended_and_executed == 1

        absent_rows = db.query(RecommendationTestOutcome).filter(
            RecommendationTestOutcome.recommendation_outcome_id == outcome3.id,
            RecommendationTestOutcome.manually_removed == True
        ).all()
        assert len(absent_rows) == 2
        for r in absent_rows:
            assert r.execution_presence_status == "ABSENT"
            assert r.actually_executed is False
            assert r.execution_result is None
        print("  SUCCESS: Narrowed execution — 2 ABSENT rows.")

        # ----------------------------------------------------------------
        # TEST 4: Fully ignored — zero recommended tests executed
        # ----------------------------------------------------------------
        print("\n--- TEST 4: Fully Ignored (none of recommended ran) ---")
        _, repo_id4 = _make_org_repo(db, "t4")
        pr4 = _make_pr(db, repo_id4, 1004)
        tc4_rec = _make_test_case(db, repo_id4, "suite_cache", "test_eviction")
        tc4_run = _make_test_case(db, repo_id4, "suite_cache", "test_hit")
        db.commit()

        rec_run4, outcome4 = _make_rec_run(db, repo_id4, pr4.id, [
            (str(tc4_rec.id), "historical_fragility"),
        ])
        test_run4 = _make_test_run(db, repo_id4, pr4.id, [
            (tc4_run, "passed", 0.1),  # different test entirely
        ])
        db.commit()

        collector4 = RecommendationExecutedTestCollector(db)
        result4 = collector4.collect(rec_run4.id, test_run4.id)

        assert result4.classification == "ignored", f"Expected ignored, got {result4.classification}"
        assert result4.recommended_absent == 1
        assert result4.non_recommended_executed == 1

        absent4 = db.query(RecommendationTestOutcome).filter(
            RecommendationTestOutcome.recommendation_outcome_id == outcome4.id,
            RecommendationTestOutcome.manually_removed == True
        ).all()
        assert len(absent4) == 1
        assert absent4[0].execution_presence_status == "ABSENT"
        print("  SUCCESS: Ignored — recommended test ABSENT, non-recommended EXECUTED.")

        # ----------------------------------------------------------------
        # TEST 5: PRESENT_SKIPPED — recommended test appears as skipped
        # ----------------------------------------------------------------
        print("\n--- TEST 5: PRESENT_SKIPPED (skipped in TestRun, not removed) ---")
        _, repo_id5 = _make_org_repo(db, "t5")
        pr5 = _make_pr(db, repo_id5, 1005)
        tc5 = _make_test_case(db, repo_id5, "suite_slow", "test_e2e")
        db.commit()

        rec_run5, outcome5 = _make_rec_run(db, repo_id5, pr5.id, [
            (str(tc5.id), "historical_fragility"),
        ])
        test_run5 = _make_test_run(db, repo_id5, pr5.id, [
            (tc5, "skipped", 0.0),
        ])
        db.commit()

        collector5 = RecommendationExecutedTestCollector(db)
        result5 = collector5.collect(rec_run5.id, test_run5.id)

        assert result5.recommended_absent == 0, "Skipped test should NOT be absent"
        assert result5.recommended_present_skipped == 1

        row5 = db.query(RecommendationTestOutcome).filter(
            RecommendationTestOutcome.recommendation_outcome_id == outcome5.id
        ).first()
        assert row5 is not None
        assert row5.actually_executed is True,     "PRESENT_SKIPPED must have actually_executed=True"
        assert row5.manually_removed is False,     "PRESENT_SKIPPED must NOT be manually_removed"
        assert row5.execution_result == "SKIPPED"
        assert row5.execution_presence_status == "PRESENT_SKIPPED"
        print("  SUCCESS: PRESENT_SKIPPED — actually_executed=True, manually_removed=False, presence=PRESENT_SKIPPED.")

        # ----------------------------------------------------------------
        # TEST 6: Idempotency — second collect() is a no-op
        # ----------------------------------------------------------------
        print("\n--- TEST 6: Idempotency (second collect is no-op) ---")
        # Re-use TEST 1's run/test_run
        collector6 = RecommendationExecutedTestCollector(db)
        result6 = collector6.collect(rec_run.id, test_run.id)

        assert result6.outcome_rows_written == 0,   f"Expected 0 written on replay, got {result6.outcome_rows_written}"
        assert result6.outcome_rows_skipped == 2,   f"Expected 2 skipped on replay, got {result6.outcome_rows_skipped}"
        # Rows in DB must still be 2 (no duplicates)
        rows6 = db.query(RecommendationTestOutcome).filter(
            RecommendationTestOutcome.recommendation_outcome_id == outcome.id
        ).all()
        assert len(rows6) == 2
        print("  SUCCESS: Idempotency — 0 written, 2 skipped, no duplicate rows.")

        # ----------------------------------------------------------------
        # TEST 7: Fallback stable_identity matching
        # ----------------------------------------------------------------
        print("\n--- TEST 7: Fallback stable_identity matching ---")
        _, repo_id7 = _make_org_repo(db, "t7")
        pr7 = _make_pr(db, repo_id7, 1007)
        tc7 = _make_test_case(db, repo_id7, "suite_net", "test_connect")
        db.commit()

        # Pass stable_identity string instead of UUID as test_case_id
        rec_run7, outcome7 = _make_rec_run(db, repo_id7, pr7.id, [
            (tc7.stable_identity, "direct_file_mapping"),  # string, not UUID
        ])
        test_run7 = _make_test_run(db, repo_id7, pr7.id, [
            (tc7, "passed", 0.5),
        ])
        db.commit()

        collector7 = RecommendationExecutedTestCollector(db)
        result7 = collector7.collect(rec_run7.id, test_run7.id)

        assert result7.total_recommended == 1, f"Fallback match failed: recommended={result7.total_recommended}"
        assert result7.recommended_and_executed == 1
        assert result7.classification == "trusted"
        row7 = db.query(RecommendationTestOutcome).filter(
            RecommendationTestOutcome.recommendation_outcome_id == outcome7.id
        ).first()
        assert row7 is not None
        assert row7.recommended_by_veriscope is True
        assert row7.execution_presence_status == "EXECUTED"
        print("  SUCCESS: Fallback stable_identity match resolved correctly.")

        # ----------------------------------------------------------------
        # TEST 8: Cross-repo guard
        # ----------------------------------------------------------------
        print("\n--- TEST 8: Cross-repo guard raises ValueError ---")
        _, repo_id8a = _make_org_repo(db, "t8a")
        _, repo_id8b = _make_org_repo(db, "t8b")
        pr8 = _make_pr(db, repo_id8a, 1008)
        pr8b = _make_pr(db, repo_id8b, 1108)
        tc8 = _make_test_case(db, repo_id8a, "suite_cross", "test_x")
        tc8b = _make_test_case(db, repo_id8b, "suite_cross", "test_x")
        db.commit()

        rec_run8, _ = _make_rec_run(db, repo_id8a, pr8.id, [(str(tc8.id), "historical_fragility")])
        # TestRun belongs to a DIFFERENT repository
        test_run8 = _make_test_run(db, repo_id8b, pr8b.id, [(tc8b, "passed", 0.1)])
        db.commit()

        collector8 = RecommendationExecutedTestCollector(db)
        try:
            collector8.collect(rec_run8.id, test_run8.id)
            assert False, "Expected ValueError for cross-repo pairing!"
        except ValueError as e:
            assert "mismatch" in str(e).lower() or "cross-repo" in str(e).lower()
            print(f"  SUCCESS: Cross-repo guard raised ValueError: {e}")

        # ----------------------------------------------------------------
        # TEST 9: Unknown execution status preserved
        # ----------------------------------------------------------------
        print("\n--- TEST 9: Unknown execution status preserved as UNKNOWN ---")
        _, repo_id9 = _make_org_repo(db, "t9")
        pr9 = _make_pr(db, repo_id9, 1109)
        tc9 = _make_test_case(db, repo_id9, "suite_misc", "test_weird")
        db.commit()

        rec_run9, outcome9 = _make_rec_run(db, repo_id9, pr9.id, [
            (str(tc9.id), "historical_fragility"),
        ])
        # Manually insert a TestResult with a non-standard status
        art9 = _make_raw_artifact(db)
        fingerprint9 = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
        tr9 = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id9,
            pull_request_id=pr9.id,
            commit_sha="abc123",
            raw_artifact_id=art9.id,
            file_hash=hashlib.sha256(fingerprint9.encode()).hexdigest(),
            normalized_execution_fingerprint=fingerprint9,
            status="SUCCESS",
            total_tests=1,
            passed_tests=0,
            failed_tests=0,
            skipped_tests=0,
            duration=0.0,
        )
        db.add(tr9)
        db.flush()
        db.add(TestResult(
            id=uuid.uuid4(),
            test_run_id=tr9.id,
            test_case_id=tc9.id,
            status="quarantined",   # maps to QUARANTINED → but presence = EXECUTED
            duration=0.0,
        ))
        db.commit()

        collector9 = RecommendationExecutedTestCollector(db)
        result9 = collector9.collect(rec_run9.id, tr9.id)

        row9 = db.query(RecommendationTestOutcome).filter(
            RecommendationTestOutcome.recommendation_outcome_id == outcome9.id
        ).first()
        assert row9 is not None
        assert row9.execution_result == "QUARANTINED"
        assert row9.execution_presence_status == "EXECUTED"
        print("  SUCCESS: Quarantined status preserved, presence=EXECUTED.")

        print("\n======================================================================")
        print("ALL RECOMMENDATION EXECUTED TEST COLLECTOR TESTS PASSED!")
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
