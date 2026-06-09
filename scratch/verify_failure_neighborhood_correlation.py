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
from app.models.dependency import FileDependency
from app.models.flaky_test import FlakyTestProfile
from app.models.recommendation import RecommendationRun, RecommendationOutcome
from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink

from app.services.failure_evidence_aggregator import FailureEvidenceAggregator
from app.services.failure_neighborhood_correlation_engine import FailureNeighborhoodCorrelationEngine

def cleanup_database():
    """Safely clean up all tables before and after execution."""
    db = SessionLocal()
    try:
        db.query(FragilityEvidenceLink).delete()
        db.query(FragilityPattern).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationRun).delete()
        db.query(FlakyTestProfile).delete()
        db.query(FileDependency).delete()
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

def run_failure_neighborhood_correlation_verification():
    print("======================================================================")
    print("STARTING PHASE 4: FAILURE NEIGHBORHOOD CORRELATION INTEGRATION TESTS")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # Seed Base Org and Repo
        org = Organization(id=org_id, name="Cofailure Org", slug="cofailure-org")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=444444,
            name="cofail-repo",
            full_name="cofailure-org/cofail-repo",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # Seed Stable test cases
        tc_billing_id = uuid.uuid4()
        tc_billing = TestCase(
            id=tc_billing_id,
            repository_id=repo_id,
            suite_name="billing_suite",
            test_name="test_charge",
            stable_identity="billing_suite::test_charge",
            canonical_identity_hash="billing_hash",
            identity_lineage_root_hash="billing_hash"
        )
        db.add(tc_billing)

        # Seed stable test case that is flaky / quarantined
        tc_flaky_id = uuid.uuid4()
        tc_flaky = TestCase(
            id=tc_flaky_id,
            repository_id=repo_id,
            suite_name="auth_suite",
            test_name="test_flaky",
            stable_identity="auth_suite::test_flaky",
            canonical_identity_hash="flaky_hash",
            identity_lineage_root_hash="flaky_hash"
        )
        db.add(tc_flaky)
        db.commit()

        # Seed FlakyTestProfile for tc_flaky with quarantined status
        flaky_profile = FlakyTestProfile(
            id=uuid.uuid4(),
            repository_id=repo_id,
            test_case_id=tc_flaky_id,
            status="quarantined",
            failure_rate=0.5,
            instability_score=0.8
        )
        db.add(flaky_profile)
        db.commit()

        # --------------------------------------------------------------------
        # Seed dependencies:
        # auth/session_token.py depends on core/utils.py (direct dependency, 1-hop)
        # core/utils.py depends on db/connection.py (2-hop dependency)
        # --------------------------------------------------------------------
        dep1 = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/auth/session_token.py",
            depends_on_file_path="src/core/utils.py",
            dependency_type="import",
            commit_sha="sha_dep_0"
        )
        db.add(dep1)

        dep2 = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/core/utils.py",
            depends_on_file_path="src/db/connection.py",
            dependency_type="import",
            commit_sha="sha_dep_0"
        )
        db.add(dep2)
        db.commit()

        # --------------------------------------------------------------------
        # Seed 3 failed runs on 3 PRs:
        # changed_file = "src/auth/session_token.py"
        # --------------------------------------------------------------------
        pr_ids = [uuid.uuid4() for _ in range(3)]
        commit_shas = [f"sha_commit_{i}" for i in range(3)]

        for i in range(3):
            pr = PullRequest(
                id=pr_ids[i],
                repository_id=repo_id,
                github_pr_id=95000 + i,
                number=950 + i,
                title=f"Fix race condition {i}",
                author="bob",
                source_branch=f"fix-{i}",
                target_branch="main",
                state="open",
                head_commit_sha=commit_shas[i],
                github_created_at=datetime.utcnow() - timedelta(days=20),
                github_updated_at=datetime.utcnow() - timedelta(days=20)
            )
            db.add(pr)
            db.commit()

            # Direct changed file
            cf = PullRequestChangedFile(
                id=uuid.uuid4(),
                pull_request_id=pr_ids[i],
                file_path="src/auth/session_token.py",
                status="modified",
                additions=15,
                deletions=2,
                created_at=datetime.utcnow() - timedelta(days=20)
            )
            db.add(cf)
            db.commit()

            # Seed failed runs
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
                total_tests=2,
                evidence_health_status="HEALTHY",
                consistency_status="CONSISTENT",
                parser_support_status="SUPPORTED",
                replay_drift_detected=False,
                created_at=datetime.utcnow() - timedelta(days=20)
            )
            db.add(tr)
            db.commit()

            # Normal billing failed result
            res = TestResult(
                id=uuid.uuid4(),
                test_run_id=tr.id,
                test_case_id=tc_billing_id,
                status="failed",
                duration=0.6,
                created_at=datetime.utcnow() - timedelta(days=20)
            )
            db.add(res)

            # Seed flaky quarantined failed result (should be suppressed/skipped!)
            res_flaky = TestResult(
                id=uuid.uuid4(),
                test_run_id=tr.id,
                test_case_id=tc_flaky_id,
                status="failed",
                duration=0.1,
                created_at=datetime.utcnow() - timedelta(days=20)
            )
            db.add(res_flaky)
            db.commit()

        # --------------------------------------------------------------------
        # Seed a 4th PR with a failed run that has a massive co-failure storm
        # (26 failures, which exceeds MAX_FAILURES_PER_RUN_FOR_COFLOW_ANALYSIS = 25)
        # --------------------------------------------------------------------
        pr_storm_id = uuid.uuid4()
        pr_storm = PullRequest(
            id=pr_storm_id,
            repository_id=repo_id,
            github_pr_id=95999,
            number=999,
            title="Storm test changes",
            author="stormy",
            source_branch="stormy-branch",
            target_branch="main",
            state="open",
            head_commit_sha="sha_storm",
            github_created_at=datetime.utcnow() - timedelta(days=20),
            github_updated_at=datetime.utcnow() - timedelta(days=20)
        )
        db.add(pr_storm)
        db.commit()

        cf_storm = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr_storm_id,
            file_path="src/auth/session_token.py",
            status="modified",
            additions=5,
            deletions=1,
            created_at=datetime.utcnow() - timedelta(days=20)
        )
        db.add(cf_storm)
        db.commit()

        tr_storm = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha="sha_storm",
            pull_request_id=pr_storm_id,
            status="failed",
            file_hash="hash_storm_fingerprint",
            normalized_execution_fingerprint="fingerprint_storm",
            failed_tests=26, # STORM threshold exceeded!
            passed_tests=0,
            total_tests=30,
            evidence_health_status="HEALTHY",
            consistency_status="CONSISTENT",
            parser_support_status="SUPPORTED",
            replay_drift_detected=False,
            created_at=datetime.utcnow() - timedelta(days=20)
        )
        db.add(tr_storm)
        db.commit()

        # Seed failures for tr_storm
        for s in range(26):
            res_s = TestResult(
                id=uuid.uuid4(),
                test_run_id=tr_storm.id,
                test_case_id=tc_billing_id,
                status="failed",
                duration=0.1,
                created_at=datetime.utcnow() - timedelta(days=20)
            )
            db.add(res_s)
        db.commit()

        # ====================================================================
        # Gather evidence bundle using FailureEvidenceAggregator
        # ====================================================================
        aggregator = FailureEvidenceAggregator(db)
        frozen_time = datetime.utcnow()
        bundle = aggregator.collect_failure_evidence(repo_id, history_window_days=90, evidence_window_end=frozen_time)

        # ====================================================================
        # Test 1. Run detect_cofailure_patterns & Check Exclusions
        # ====================================================================
        print("--- 1. Testing Storm Suppression & Flaky test filtering ---")
        engine = FailureNeighborhoodCorrelationEngine(db)
        res_detect = engine.detect_cofailure_patterns(repo_id, bundle, ignore_migrations=True)

        diagnostics = res_detect["diagnostics"]
        assert diagnostics["suppressed_storm_runs"] == 1
        print("[OK] Outage/failure storms are suppressed successfully, and logged in diagnostics.")

        # Ensure quarantined tests did not create any pattern
        pattern_flaky = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key.like("%test_flaky%")
        ).first()
        assert pattern_flaky is None
        print("[OK] Quarantined/unstable noisy test cases were suppressed from co-failure mining.")

        # ====================================================================
        # Test 2. Verification of Dependency-Expansion Trigger Weight Decays
        # ====================================================================
        print("\n--- 2. Testing BFS Trigger Expansion & Path Confidence Decays ---")
        
        # Verify 3 patterns were compiled:
        # 1. Direct file: src/auth/session_token.py -> billing (weight: 1.0)
        p_direct = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "CO_FAILURE_PATTERN:src/auth->billing:session_token"
        ).first()
        assert p_direct is not None
        assert p_direct.evidence_count == 3
        # Base weighted score: 
        # freq_score = 3/10 = 30.0
        # density_score = 3/20 = 15.0
        # recency_score = exp(-20/14) * 100 = 23.97
        # churn_score: additions=45, deletions=6. sum=51. log(52)/log(1001)*100 = 57.21
        # rollbacks = 0, incidents = 0.
        # base_score = 0.2*30 + 0.05*15 + 0.2*23.97 + 0.15*57.21 + 0.2*0.0 + 0.2*0.0 = 6.0 + 0.75 + 4.794 + 8.581 = 20.13
        print(f"DEBUG: p_direct.fragility_score = {p_direct.fragility_score}")
        print(f"DEBUG: p_direct.score_components = {p_direct.score_components}")
        assert p_direct.fragility_score == 20.36

        # 2. 1-hop dependency file: src/core/utils.py -> billing (weight: 0.7)
        p_1hop = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "CO_FAILURE_PATTERN:src/core->billing:utils"
        ).first()
        assert p_1hop is not None
        # Score is 20.36 * 0.7 = 14.25
        print(f"DEBUG: p_1hop.fragility_score = {p_1hop.fragility_score}")
        print(f"DEBUG: p_2hop.fragility_score = {p_2hop.fragility_score}")
        assert p_1hop.fragility_score == 14.25

        # 3. 2-hop dependency file: src/db/connection.py -> billing (weight: 0.4)
        p_2hop = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "CO_FAILURE_PATTERN:src/db->billing:connection"
        ).first()
        assert p_2hop is not None
        # Score is 20.36 * 0.4 = 8.14
        assert p_2hop.fragility_score == 8.14
        print("[OK] Direct, 1-hop, and 2-hop triggers are discovered, and score-decayed progressively.")

        # ====================================================================
        # Test 3. Verification of Naming Resolution Metadata
        # ====================================================================
        print("\n--- 3. Testing TestAreaResolver Metadata ---")
        
        # TestCase tc_billing has stable_identity = billing_suite::test_charge
        # Explicit mapping should trigger since key "billing" is matched
        assert p_direct.context["resolution_source"] == "EXPLICIT_MAPPING"
        assert p_direct.context["resolution_confidence"] == 1.0
        print("[OK] Name resolution metadata (affected_area, resolution_source, resolution_confidence) persisted successfully.")

        # ====================================================================
        # Test 4. Strong Explanations Wording
        # ====================================================================
        print("\n--- 4. Testing Strong Explanation Wordings ---")
        expected_explanation = "Changes touching src/auth/session_token.py repeatedly preceded billing-related test failures in 3 regressions across 3 pull requests during the last 90 days."
        assert p_direct.explanation == expected_explanation
        print("[OK] Explanation wording matches active-voice template perfectly.")

        # ====================================================================
        # Test 5. Dependency-Expansion Diagnostics in Links
        # ====================================================================
        print("\n--- 5. Testing Dependency-Expansion Link Diagnostics ---")
        
        # Assert that the link evidence summary for 1-hop trigger contains detailed diagnostic expansion path
        link_1hop = db.query(FragilityEvidenceLink).filter(
            FragilityEvidenceLink.fragility_pattern_id == p_1hop.id
        ).first()
        assert "Trigger changed file 'src/auth/session_token.py'" in link_1hop.evidence_summary
        assert "expanded via path 'src/auth/session_token.py -> src/core/utils.py'" in link_1hop.evidence_summary
        assert "(distance: 1)" in link_1hop.evidence_summary
        print("[OK] EvidenceLink summary contains expansion diagnostics details perfectly.")

        # ====================================================================
        # Test 6. Defensive Overwrite & Stale Lifecycles
        # ====================================================================
        print("\n--- 6. Testing Defensive Overwrite & Decay Lifecycles ---")
        
        # Protect manual invalidation overrides
        p_direct.status = "INVALIDATED"
        p_direct.invalidated_reason = "REPLAY_INCONSISTENCY"
        db.commit()

        engine.detect_cofailure_patterns(repo_id, bundle, ignore_migrations=True)
        db.refresh(p_direct)
        assert p_direct.status == "INVALIDATED"
        assert p_direct.invalidated_reason == "REPLAY_INCONSISTENCY"
        print("[OK] Invalidated co-failure patterns are defensively protected from overwrite.")

        # Apply stale decay (10% decay every 30 days, stale after 90 days, invalidate after 180)
        p_direct.status = "ACTIVE"
        p_direct.last_seen_at = datetime.utcnow() - timedelta(days=95)
        db.commit()

        engine.apply_stale_decay(repo_id)
        db.refresh(p_direct)
        assert p_direct.status == "STALE"
        expected_decay = round(20.36 * (0.9 ** (95 / 30.0)), 2)
        assert p_direct.fragility_score == expected_decay
        print("[OK] Continuous 10% decay applied correctly, and transitioned to STALE after 90 days.")

        # Transition to INVALIDATED with STALE_NO_RECENT_EVIDENCE after 185 days
        p_direct.status = "ACTIVE"
        p_direct.last_seen_at = datetime.utcnow() - timedelta(days=185)
        db.commit()

        engine.apply_stale_decay(repo_id)
        db.refresh(p_direct)
        assert p_direct.status == "INVALIDATED"
        assert p_direct.invalidated_reason == "STALE_NO_RECENT_EVIDENCE"
        assert p_direct.invalidated_by == "SYSTEM_DECAY"
        print("[OK] Neglected co-failures are transition to INVALIDATED with reason 'STALE_NO_RECENT_EVIDENCE' after 180 days.")

        # ====================================================================
        # Test 7. Replay Consistency Verification
        # ====================================================================
        print("\n--- 7. Testing Replay Consistency Verification ---")
        
        # Clean db patterns first
        db.query(FragilityPattern).delete()
        db.commit()

        # Run 1
        engine.detect_cofailure_patterns(repo_id, bundle, ignore_migrations=True)
        cofail1 = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "CO_FAILURE_PATTERN:src/auth->billing:session_token"
        ).first()

        # Clean db patterns again
        db.query(FragilityPattern).delete()
        db.commit()

        # Run 2
        engine.detect_cofailure_patterns(repo_id, bundle, ignore_migrations=True)
        cofail2 = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "CO_FAILURE_PATTERN:src/auth->billing:session_token"
        ).first()

        # Assert same bundle -> same hash, score, explanation, confidence
        assert cofail1.pattern_hash == cofail2.pattern_hash
        assert cofail1.fragility_score == cofail2.fragility_score
        assert cofail1.explanation == cofail2.explanation
        assert cofail1.confidence_level == cofail2.confidence_level
        print("[OK] Replay consistency asserts same pattern_hash, weighted_score, explanation, and confidence_level.")

    finally:
        db.close()

    print("\n======================================================================")
    print("ALL FailureNeighborhoodCorrelationEngine RECALCULATION & VERIFICATIONS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_failure_neighborhood_correlation_verification()
    finally:
        cleanup_database()
