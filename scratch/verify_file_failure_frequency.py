import os
import sys
import uuid
import math
import json
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
from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink

from app.services.failure_evidence_aggregator import FailureEvidenceAggregator
from app.services.file_failure_frequency_engine import FileFailureFrequencyEngine

def cleanup_database():
    """Safely clean up all tables before and after execution."""
    db = SessionLocal()
    try:
        db.query(FragilityEvidenceLink).delete()
        db.query(FragilityPattern).delete()
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

def run_file_failure_frequency_verification():
    print("======================================================================")
    print("STARTING PHASE 4: FILE FAILURE FREQUENCY ENGINE INTEGRATION TESTS")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # Seed Base Org and Repo
        org = Organization(id=org_id, name="Failure Freq Org", slug="failure-freq-org")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=333333,
            name="freq-repo",
            full_name="failure-freq-org/freq-repo",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # Seed stable test cases
        tc1_id = uuid.uuid4()
        tc1 = TestCase(
            id=tc1_id,
            repository_id=repo_id,
            suite_name="freq_suite",
            test_name="test_freq",
            stable_identity="freq_suite::test_freq",
            canonical_identity_hash="freq_hash",
            identity_lineage_root_hash="freq_hash"
        )
        db.add(tc1)
        db.commit()

        # --------------------------------------------------------------------
        # Seed evidence:
        # We need a file "src/core/session.py" involved in 3 occurrences:
        # - 2 failed runs
        # - 1 rollback outcome recommendation
        # Let's seed 3 PRs:
        # --------------------------------------------------------------------
        pr_ids = [uuid.uuid4() for _ in range(3)]
        commit_shas = [f"sha_commit_{i}" for i in range(3)]

        for i in range(3):
            pr = PullRequest(
                id=pr_ids[i],
                repository_id=repo_id,
                github_pr_id=90000 + i,
                number=900 + i,
                title=f"Resolve bug {i}",
                author="bob",
                source_branch=f"bugfix-{i}",
                target_branch="main",
                state="open",
                head_commit_sha=commit_shas[i],
                github_created_at=datetime.utcnow() - timedelta(days=20),
                github_updated_at=datetime.utcnow() - timedelta(days=20)
            )
            db.add(pr)
            db.commit()

            # Add changed files for "src/core/session.py"
            cf1 = PullRequestChangedFile(
                id=uuid.uuid4(),
                pull_request_id=pr_ids[i],
                file_path="src/core/session.py",
                status="modified",
                additions=10,
                deletions=5,
                created_at=datetime.utcnow() - timedelta(days=20)
            )
            db.add(cf1)

            # Add some non-target files to test exclusions
            # Generated file
            cf_gen = PullRequestChangedFile(
                id=uuid.uuid4(),
                pull_request_id=pr_ids[i],
                file_path=f"src/proto/session_pb2_{i}.py",
                status="modified",
                additions=1000,
                deletions=1000,
                created_at=datetime.utcnow() - timedelta(days=20)
            )
            db.add(cf_gen)

            # Vendor file
            cf_vendor = PullRequestChangedFile(
                id=uuid.uuid4(),
                pull_request_id=pr_ids[i],
                file_path=f"vendor/cache/session_{i}.cache",
                status="modified",
                additions=5,
                deletions=2,
                created_at=datetime.utcnow() - timedelta(days=20)
            )
            db.add(cf_vendor)

            # Migration file
            cf_migration = PullRequestChangedFile(
                id=uuid.uuid4(),
                pull_request_id=pr_ids[i],
                file_path=f"db/migrate/001_session_migration_{i}.py",
                status="modified",
                additions=20,
                deletions=0,
                created_at=datetime.utcnow() - timedelta(days=20)
            )
            db.add(cf_migration)
            db.commit()

            # Seed test run for first 3 PRs (failed runs)
            if i < 3:
                tr = TestRun(
                    id=uuid.uuid4(),
                    repository_id=repo_id,
                    commit_sha=commit_shas[i],
                    pull_request_id=pr_ids[i],
                    status="failed",
                    file_hash=f"hash_{i}_fingerprint",
                    normalized_execution_fingerprint=f"fingerprint_{i}",
                    failed_tests=1,
                    passed_tests=0,
                    total_tests=1,
                    evidence_health_status="HEALTHY",
                    consistency_status="CONSISTENT",
                    parser_support_status="SUPPORTED",
                    replay_drift_detected=False,
                    created_at=datetime.utcnow() - timedelta(days=20)
                )

                db.add(tr)
                db.commit()

                res = TestResult(
                    id=uuid.uuid4(),
                    test_run_id=tr.id,
                    test_case_id=tc1_id,
                    status="failed",
                    duration=0.5,
                    created_at=datetime.utcnow() - timedelta(days=20)
                )
                db.add(res)
                db.commit()


            # Seed rollback outcome recommendation for the 3rd PR
            if i == 2:
                rec_run = RecommendationRun(
                    id=uuid.uuid4(),
                    repository_id=repo_id,
                    pr_id=commit_shas[i],
                    pull_request_id=pr_ids[i],
                    triggered_by="manual",
                    evidence_quality="HIGH",
                    recommendation_mode="NORMAL",
                    engine_version="v1.2.0",
                    recommendation_engine_version="v1.2.0",
                    ruleset_version="rules-v1",
                    degradation_policy_version="policy-v1",
                    fallback_policy_version="policy-v1",
                    dependency_expansion_strategy_version="expansion-strategy-v1",
                    recommendation_reasoning_summary="Base historical run",
                    created_at=datetime.utcnow() - timedelta(days=20)
                )

                db.add(rec_run)
                db.commit()

                outcome = RecommendationOutcome(
                    id=uuid.uuid4(),
                    recommendation_run_id=rec_run.id,
                    executed_tests=["freq_suite::test_freq"],
                    manually_added_tests=[],
                    manually_removed_tests=[],
                    was_followed=True,
                    rollback_occurred=True,
                    created_at=datetime.utcnow() - timedelta(days=20)
                )
                db.add(outcome)
                db.commit()

        # Seed another file F2 that does not meet thresholds (only 1 failed run)
        pr_f2_id = uuid.uuid4()
        pr_f2 = PullRequest(
            id=pr_f2_id,
            repository_id=repo_id,
            github_pr_id=99999,
            number=999,
            title="Non threshold change",
            author="charlie",
            source_branch="non-thresh",
            target_branch="main",
            state="open",
            head_commit_sha="sha_f2",
            github_created_at=datetime.utcnow() - timedelta(days=20),
            github_updated_at=datetime.utcnow() - timedelta(days=20)
        )
        db.add(pr_f2)
        db.commit()

        cf2 = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr_f2_id,
            file_path="src/core/lightweight.py",
            status="modified",
            additions=1,
            deletions=1,
            created_at=datetime.utcnow() - timedelta(days=20)
        )
        db.add(cf2)
        db.commit()

        tr_f2 = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha="sha_f2",
            pull_request_id=pr_f2_id,
            status="failed",
            file_hash="hash_f2_fingerprint",
            normalized_execution_fingerprint="fingerprint_f2",
            failed_tests=1,
            passed_tests=0,
            total_tests=1,
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            parser_support_status="SUPPORTED",
            replay_drift_detected=False,
            created_at=datetime.utcnow() - timedelta(days=20)
        )

        db.add(tr_f2)
        db.commit()

        res_f2 = TestResult(
            id=uuid.uuid4(),
            test_run_id=tr_f2.id,
            test_case_id=tc1_id,
            status="failed",
            duration=0.1,
            created_at=datetime.utcnow() - timedelta(days=20)
        )
        db.add(res_f2)
        db.commit()

        # ====================================================================
        # Gather evidence bundle using FailureEvidenceAggregator
        # ====================================================================
        aggregator = FailureEvidenceAggregator(db)
        # Freeze window bound to exactly 20 days ago to test
        frozen_time = datetime.utcnow()
        bundle = aggregator.collect_failure_evidence(repo_id, history_window_days=90, evidence_window_end=frozen_time)

        # ====================================================================
        # Test 1. Run detect_file_failure_patterns and verify counts/skips
        # ====================================================================
        print("--- 1. Testing File Exclusion & Ignore Diagnostics ---")
        engine = FileFailureFrequencyEngine(db)
        print(f"DEBUG: bundle failed runs: {[r.test_run_id for r in bundle.related_test_runs]}")
        print(f"DEBUG: bundle changed files: {[(f.file_path, f.pull_request_id) for f in bundle.related_changed_files]}")
        print(f"DEBUG: bundle recommendations: {[(r.recommendation_run_id, r.pull_request_id) for r in bundle.linked_recommendations]}")
        print(f"DEBUG: bundle outcomes: {[(o.recommendation_outcome_id, o.recommendation_run_id) for o in bundle.linked_incidents]}")
        
        res_detect = engine.detect_file_failure_patterns(repo_id, bundle, ignore_migrations=True)
        print(f"DEBUG: res_detect result = {res_detect}")

        assert res_detect["patterns_mined"] == 1
        diagnostics = res_detect["diagnostics"]
        assert diagnostics["generated_ignored_count"] == 3
        assert diagnostics["vendor_ignored_count"] == 3
        assert diagnostics["migration_ignored_count"] == 3
        print("[OK] Ignore rules and skipped file diagnostics tracked perfectly.")

        # ====================================================================
        # Test 2. Threshold filtering
        # ====================================================================
        print("\n--- 2. Testing Threshold Filtering & Validation ---")
        
        # Verify src/core/session.py pattern is created (meets threshold: occurrences=4, distinct_runs=4)
        pattern = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "FILE_FAILURE_FREQUENCY:src/core/session.py"
        ).first()
        assert pattern is not None
        assert pattern.evidence_count == 4
        assert pattern.status == "ACTIVE"

        # Verify src/core/lightweight.py pattern is NOT created (below threshold)
        pattern_light = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "FILE_FAILURE_FREQUENCY:src/core/lightweight.py"
        ).first()
        assert pattern_light is None
        print("[OK] Patterns successfully created above threshold, and ignored below threshold.")

        # ====================================================================
        # Test 3. Actuarial Calibration Calculations
        # ====================================================================
        print("\n--- 3. Testing Actuarial Scoring, Density Floor & Log Churn ---")
        
        # Frequency score: 3 failed runs / 10 = 30.0
        # Failure density: 3 failed runs / max(bundle.total_runs_in_window, 20)
        # Total runs in window seeded = 4. max(4, 20) = 20. Density = 3/20 = 15% (15.0 score)
        # Log churn: additions=30, deletions=15. Churn sum = 45. normalized = log(46) = 3.8286. 
        # Churn score = 3.8286 / log(1001) * 100 = 55.42
        # Progressive rollback score: min(1 / 3, 1.0) * 100 = 33.33
        # Recency weighting: last seen = 20 days ago. days_since = 20. exp(-20/14) * 100 = 23.97
        # Incident progressive score: 0.0 (no incidents)
        
        score_comp = pattern.score_components
        assert round(score_comp["frequency"], 1) == 30.0
        assert round(score_comp["density"], 1) == 15.0
        assert round(score_comp["churn"], 1) == 55.4
        assert round(score_comp["rollback"], 1) == 33.3
        assert round(score_comp["incident"], 1) == 0.0
        assert round(score_comp["recency"], 1) == 24.0

        # Weighted score: 0.2*30 + 0.05*15 + 0.2*23.97 + 0.15*55.42 + 0.2*33.33 + 0.2*0.0 = 6.0 + 0.75 + 4.794 + 8.313 + 6.666 = 26.52
        assert pattern.fragility_score == 26.52
        assert pattern.risk_level == "LOW" # score < 30.0
        assert pattern.confidence_level == "MODERATE" # evidence_count=4, distinct_prs=3, days_since=20 (< 90)
        print("[OK] Scoring components, progressive incident weightings, logarithmic churn, and density floors validated perfectly.")

        # ====================================================================
        # Test 4. Explanation format verification
        # ====================================================================
        print("\n--- 4. Testing Strong Explanations ---")
        expected_explanation = "Changes involving src/core/session.py preceded 3 failed runs and 1 rollback-linked recommendations during the last 90 days."
        assert pattern.explanation == expected_explanation
        print("[OK] Deterministic explanation matches active-voice requirements exactly.")


        # ====================================================================
        # Test 5. Overwrite Protection Lifecycle
        # ====================================================================
        print("\n--- 5. Testing Defensive Overwrite Protection ---")
        
        # 1. Manual Invalidation override preservation
        pattern.status = "INVALIDATED"
        pattern.invalidated_reason = "Manual override"
        db.commit()

        # Run detection again. The pattern should remain INVALIDATED and NOT be overwritten
        engine.detect_file_failure_patterns(repo_id, bundle, ignore_migrations=True)
        pattern_check = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "FILE_FAILURE_FREQUENCY:src/core/session.py"
        ).first()
        assert pattern_check.status == "INVALIDATED"
        assert pattern_check.invalidated_reason == "Manual override"
        print("[OK] Manual INVALIDATED overrides are defensively preserved from overwrite.")

        # 2. Overwrite checks on ACTIVE pattern
        pattern_check.status = "ACTIVE"
        db.commit()

        # Try to run with same bundle (no new window/stronger evidence/version)
        engine.detect_file_failure_patterns(repo_id, bundle, ignore_migrations=True)
        pattern_after = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "FILE_FAILURE_FREQUENCY:src/core/session.py"
        ).first()
        # Since it was not overwritten, its ID should be the exact same!
        assert pattern_after.id == pattern_check.id
        print("[OK] Overwrite is skipped when there is no newer window, stronger evidence, or scoring version.")

        # Trigger overwrite by simulating stronger evidence (adding a failed test run)
        tr_extra = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha="sha_extra",
            pull_request_id=pr_ids[0],
            status="failed",
            file_hash="hash_extra_fingerprint",
            normalized_execution_fingerprint="fingerprint_extra",
            failed_tests=1,
            passed_tests=0,
            total_tests=1,
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            parser_support_status="SUPPORTED",
            replay_drift_detected=False,
            created_at=datetime.utcnow() - timedelta(days=20)
        )

        db.add(tr_extra)
        db.commit()

        bundle_stronger = aggregator.collect_failure_evidence(repo_id, history_window_days=90, evidence_window_end=frozen_time)
        engine.detect_file_failure_patterns(repo_id, bundle_stronger, ignore_migrations=True)
        pattern_stronger = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "FILE_FAILURE_FREQUENCY:src/core/session.py"
        ).first()
        
        # ID must be different now (since it deleted and recreated to overwrite!)
        assert pattern_stronger.id != pattern_check.id
        assert pattern_stronger.evidence_count == 5
        print("[OK] Overwrite successfully triggers when incoming evidence count is stronger.")


        # ====================================================================
        # Test 6. Stale Decay Lifecycles
        # ====================================================================
        print("\n--- 6. Testing Stale-Decay Lifecycles & Transition Codes ---")
        
        # Original score
        orig_score = pattern_stronger.fragility_score
        
        # Simulate 95 days of inactivity
        pattern_stronger.last_seen_at = datetime.utcnow() - timedelta(days=95)
        pattern_stronger.status = "ACTIVE"
        db.commit()

        # Apply stale decay
        engine.apply_stale_decay(repo_id)
        db.refresh(pattern_stronger)
        assert pattern_stronger.status == "STALE"
        expected_decay = round(orig_score * (0.9 ** (95 / 30.0)), 2)
        assert pattern_stronger.fragility_score == expected_decay
        print("[OK] Score decays by continuous 10% per 30 days and transitions to STALE after 90 days.")

        # Simulate 190 days of inactivity
        pattern_stronger.last_seen_at = datetime.utcnow() - timedelta(days=190)
        pattern_stronger.status = "ACTIVE"
        db.commit()

        # Apply stale decay again
        engine.apply_stale_decay(repo_id)
        db.refresh(pattern_stronger)
        assert pattern_stronger.status == "INVALIDATED"
        assert pattern_stronger.invalidated_reason == "STALE_NO_RECENT_EVIDENCE"
        assert pattern_stronger.invalidated_by == "SYSTEM_DECAY"
        print("[OK] Neglected patterns successfully transition to INVALIDATED with reason 'STALE_NO_RECENT_EVIDENCE' after 180 days.")

        # ====================================================================
        # Test 7. Replay Consistency Verification
        # ====================================================================
        print("\n--- 7. Testing Replay Consistency Verification ---")
        
        # Clean db patterns first
        db.query(FragilityPattern).delete()
        db.commit()

        # Run 1
        engine.detect_file_failure_patterns(repo_id, bundle_stronger, ignore_migrations=True)
        p1 = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "FILE_FAILURE_FREQUENCY:src/core/session.py"
        ).first()

        # Clean db patterns again
        db.query(FragilityPattern).delete()
        db.commit()

        # Run 2
        engine.detect_file_failure_patterns(repo_id, bundle_stronger, ignore_migrations=True)
        p2 = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "FILE_FAILURE_FREQUENCY:src/core/session.py"
        ).first()

        # Verification asserts: same bundle -> same hash, score, explanation, confidence
        assert p1.pattern_hash == p2.pattern_hash
        assert p1.fragility_score == p2.fragility_score
        assert p1.explanation == p2.explanation
        assert p1.confidence_level == p2.confidence_level
        print("[OK] Replay consistency asserts same pattern_hash, weighted_score, explanation, and confidence_level.")

    finally:
        db.close()

    print("\n======================================================================")
    print("ALL FileFailureFrequencyEngine RECALCULATION & TRUST VERIFICATIONS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_file_failure_frequency_verification()
    finally:
        cleanup_database()
