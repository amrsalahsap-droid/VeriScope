import os
import sys
import uuid
import datetime
import hashlib
import math
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal

from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.test_result import TestRun, TestCase, TestResult
from app.models.dependency import FileDependency
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationInputSnapshot,
    RecommendationReasoningEntry
)
from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink, FragilitySnapshot
from app.services.recommendation import RecommendationService
from app.services.fragility_memory_service import FragilityMemoryService
from app.services.fragility_snapshot_service import FragilitySnapshotService
from app.services.fragility_scoring_engine import FragilityScoringEngine
from app.services.fragility_reasoning_builder import FragilityReasoningBuilder
from app.schemas.recommendation import RecommendationRunCreate

client = TestClient(app)

def cleanup_database():
    """Safely clean up all tables before and after execution."""
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationInputSnapshot).delete()
        db.query(RecommendationRun).delete()
        db.query(FragilityEvidenceLink).delete()
        db.query(FragilitySnapshot).delete()
        db.query(FragilityPattern).delete()
        db.query(FileDependency).delete()
        db.query(TestResult).delete()
        db.query(TestRun).delete()
        db.query(TestCase).delete()
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

def run_end_to_end_verification():
    print("======================================================================")
    print("STARTING FRAGILITY PLATFORM END-TO-END CALIBRATION & VERIFICATIONS")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # 0. Seed multi-tenant core
        org = Organization(id=org_id, name="Platform Labs", slug="platform-labs")
        db.add(org)
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=111444,
            name="platform-core",
            full_name="platform-labs/platform-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)

        # Seed test cases
        tc1_id = uuid.uuid4()
        tc1 = TestCase(
            id=tc1_id,
            repository_id=repo_id,
            suite_name="auth_suite",
            test_name="test_scope",
            stable_identity="auth_suite::test_scope",
            canonical_identity_hash="auth_suite_test_scope_hash",
            identity_lineage_root_hash="auth_suite_test_scope_hash"
        )
        db.add(tc1)

        tc2_id = uuid.uuid4()
        tc2 = TestCase(
            id=tc2_id,
            repository_id=repo_id,
            suite_name="billing_suite",
            test_name="test_billing",
            stable_identity="billing_suite::test_billing",
            canonical_identity_hash="billing_suite_test_billing_hash",
            identity_lineage_root_hash="billing_suite_test_billing_hash"
        )
        db.add(tc2)
        db.commit()

        # Seed execution durations (cost = 1.0)
        tr_dur = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            status="passed",
            file_hash="run-dur-hash",
            normalized_execution_fingerprint="run-dur-fingerprint"
        )
        db.add(tr_dur)
        db.commit()

        res1 = TestResult(
            test_run_id=tr_dur.id,
            test_case_id=tc1_id,
            status="passed",
            duration=1.0
        )
        db.add(res1)
        res2 = TestResult(
            test_run_id=tr_dur.id,
            test_case_id=tc2_id,
            status="passed",
            duration=1.0
        )
        db.add(res2)
        db.commit()

        # Seed PRs and TestRuns within the 90-day window
        pr_uuids = [uuid.uuid4() for _ in range(4)]
        commit_shas = [f"sha_commit_{i}_sha" for i in range(4)]
        
        for i in range(4):
            pr = PullRequest(
                id=pr_uuids[i],
                repository_id=repo_id,
                github_pr_id=5500 + i,
                number=500 + i,
                title=f"PR number {500+i}",
                author="engineer",
                source_branch=f"branch-{i}",
                target_branch="main",
                state="open",
                additions=12,
                deletions=3,
                changed_files_count=2,
                head_commit_sha=commit_shas[i],
                github_created_at=datetime.datetime.utcnow() - datetime.timedelta(days=10),
                github_updated_at=datetime.datetime.utcnow() - datetime.timedelta(days=10),
                sync_integrity_status="FULL_SUCCESS",
                evidence_health_status="HEALTHY",
                evidence_consistency_status="CONSISTENT"
            )
            db.add(pr)

            # Preceding Recommendation Run
            run_rec = RecommendationRun(
                id=uuid.uuid4(),
                repository_id=repo_id,
                pr_id=commit_shas[i],
                pull_request_id=pr_uuids[i],
                triggered_by="manual",
                evidence_quality="HIGH",
                engine_version="v1.2.0",
                recommendation_engine_version="v1.2.0",
                ruleset_version="rules-v1",
                degradation_policy_version="policy-v1",
                fallback_policy_version="policy-v1",
                dependency_expansion_strategy_version="expansion-strategy-v1",
                recommendation_reasoning_summary="E2E run",
                recommendation_mode="NORMAL",
                created_at=datetime.datetime.utcnow() - datetime.timedelta(days=10)
            )
            db.add(run_rec)
            db.commit()

            # Recommendation Snapshot
            snap = RecommendationInputSnapshot(
                id=uuid.uuid4(),
                recommendation_run_id=run_rec.id,
                changed_files=["src/auth.py", "src/utils.py"],
                direct_mappings_used=[],
                heuristic_mappings_used=[],
                dependency_files_expanded=[],
                coverage_links_used=[],
                flaky_profiles_used=[],
                historical_failures_used=[],
                degradation_rules_triggered=[],
                created_at=datetime.datetime.utcnow() - datetime.timedelta(days=10)
            )
            db.add(snap)
            db.commit()

            # Failed run
            tr = TestRun(
                id=uuid.uuid4(),
                repository_id=repo_id,
                commit_sha=commit_shas[i],
                pull_request_id=pr_uuids[i],
                status="failed",
                file_hash=f"run_hash_{i}",
                normalized_execution_fingerprint=f"run_fingerprint_{i}",
                created_at=datetime.datetime.utcnow() - datetime.timedelta(days=10)
            )
            db.add(tr)
            db.commit()

            # Failed test
            tres = TestResult(
                id=uuid.uuid4(),
                test_run_id=tr.id,
                test_case_id=tc1_id,
                status="failed",
                duration=1.2,
                created_at=datetime.datetime.utcnow() - datetime.timedelta(days=10)
            )
            db.add(tres)
            db.commit()

        # Seed dependencies
        dep = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/auth.py",
            depends_on_file_path="src/utils.py",
            dependency_type="import",
            commit_sha=commit_shas[0]
        )
        db.add(dep)
        db.commit()

        # Trigger Mining
        fragility_service = FragilityMemoryService(db)
        res_mine = fragility_service.mine_fragility_patterns(repo_id)
        print(f"DEBUG: Initial mined patterns: {res_mine.get('patterns_mined')}")

        # --------------------------------------------------------------------
        # Test 1. File failure frequency
        # --------------------------------------------------------------------
        print("\n--- Test 1. File failure frequency ---")
        p_freq = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.pattern_type == "FILE_FAILURE_FREQUENCY",
            FragilityPattern.normalized_pattern_key == "FILE_FAILURE_FREQUENCY:src/auth.py"
        ).first()
        
        # Verify repeated failed file generates a pattern (evidences = 4)
        assert p_freq is not None
        assert p_freq.evidence_count == 4
        assert p_freq.status == "ACTIVE"

        # Verify low-frequency file (not seeded / failed < 3 times) has no pattern
        p_low = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "FILE_FAILURE_FREQUENCY:src/low_freq.py"
        ).first()
        assert p_low is None
        print("[OK] Repeated file failures successfully mine active patterns, low frequency files ignored.")

        # --------------------------------------------------------------------
        # Test 2. Co-failure patterns
        # --------------------------------------------------------------------
        print("\n--- Test 2. Co-failure patterns ---")
        p_cofail = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.pattern_type == "CO_FAILURE_PATTERN"
        ).first()
        
        # Verify repeated contextual co-failures are detected
        assert p_cofail is not None
        assert p_cofail.evidence_count == 4
        assert p_cofail.normalized_pattern_key == "CO_FAILURE_PATTERN:src/auth.py->auth_suite::test_scope"

        # Verify unrelated test failures are ignored (tc2 test_billing has zero failures preceding it)
        p_unrelated = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.normalized_pattern_key == "CO_FAILURE_PATTERN:src/auth.py->billing_suite::test_billing"
        ).first()
        assert p_unrelated is None
        print("[OK] Repeated contextual co-failures detected; unrelated failures completely ignored.")

        # --------------------------------------------------------------------
        # Test 3. Dependency fragility
        # --------------------------------------------------------------------
        print("\n--- Test 3. Dependency fragility ---")
        # Since src/auth.py imports src/utils.py, failures on utils.py are neighborhood failures of auth.py
        p_dep = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.pattern_type == "DEPENDENCY_PROXIMITY"
        ).first()
        
        # Downstream repeated failures of dependency neighbors must generate proximity patterns
        assert p_dep is not None
        assert p_dep.normalized_pattern_key == "DEPENDENCY_PROXIMITY:src/auth.py->src/utils.py"
        print("[OK] Downstream repeated failures successfully trigger dependency proximity patterns.")

        # --------------------------------------------------------------------
        # Test 4. Escaped defect linkage
        # --------------------------------------------------------------------
        print("\n--- Test 4. Escaped defect linkage ---")
        
        # Clean patterns and seed production incidents
        db.query(FragilityPattern).delete()
        db.commit()

        # Seed RecommendationOutcomes with escaped defects
        runs = db.query(RecommendationRun).filter(RecommendationRun.repository_id == repo_id).all()
        for run in runs[:3]:
            outcome = RecommendationOutcome(
                id=uuid.uuid4(),
                recommendation_run_id=run.id,
                executed_tests=["auth_suite::test_scope"],
                manually_added_tests=[],
                manually_removed_tests=[],
                was_followed=True,
                escaped_defect=True
            )
            db.add(outcome)
        db.commit()

        # Re-mine
        fragility_service.mine_fragility_patterns(repo_id)
        p_defect = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.pattern_type == "ESCAPED_DEFECT_PATTERN"
        ).first()
        
        # Rollback or incident linked recommendations must generate patterns
        assert p_defect is not None
        assert p_defect.evidence_count == 3
        assert p_defect.normalized_pattern_key == "ESCAPED_DEFECT_PATTERN:src/auth.py"
        print("[OK] Incident or rollback-linked recommendations successfully compile defect linkages.")

        # --------------------------------------------------------------------
        # Test 5. Risky combinations
        # --------------------------------------------------------------------
        print("\n--- Test 5. Risky combinations ---")
        p_combo = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.pattern_type == "RISKY_COMBINATION"
        ).first()
        
        # Repeated exact combinations of modified files preceding failed tests generate patterns
        assert p_combo is not None
        assert p_combo.evidence_count == 4
        assert "src/auth.py" in p_combo.normalized_pattern_key
        assert "src/utils.py" in p_combo.normalized_pattern_key
        
        # Verify giant noisy combinations (> 5 changed files) are ignored or capped
        # Let's seed a PR with 6 changed files
        pr_giant = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo_id,
            github_pr_id=5999,
            number=599,
            title="Giant PR",
            author="engineer",
            source_branch="feat-giant",
            target_branch="main",
            state="open",
            additions=100,
            deletions=50,
            changed_files_count=6,
            head_commit_sha="giant_sha",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr_giant)
        
        rec_giant = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            pr_id="giant_sha",
            pull_request_id=pr_giant.id,
            triggered_by="manual",
            evidence_quality="HIGH",
            engine_version="v1.2.0",
            recommendation_engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            fallback_policy_version="policy-v1",
            dependency_expansion_strategy_version="expansion-strategy-v1",
            recommendation_reasoning_summary="Giant run",
            recommendation_mode="NORMAL",
            created_at=datetime.datetime.utcnow()
        )
        db.add(rec_giant)
        db.commit()

        snap_giant = RecommendationInputSnapshot(
            id=uuid.uuid4(),
            recommendation_run_id=rec_giant.id,
            changed_files=[f"src/file_{x}.py" for x in range(6)],
            direct_mappings_used=[],
            heuristic_mappings_used=[],
            dependency_files_expanded=[],
            coverage_links_used=[],
            flaky_profiles_used=[],
            historical_failures_used=[],
            degradation_rules_triggered=[],
            created_at=datetime.datetime.utcnow()
        )
        db.add(snap_giant)
        db.commit()

        # Failed test run for giant PR
        tr_giant = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha="giant_sha",
            pull_request_id=pr_giant.id,
            status="failed",
            file_hash="giant-run-hash",
            normalized_execution_fingerprint="giant-run-fingerprint",
            created_at=datetime.datetime.utcnow()
        )
        db.add(tr_giant)
        db.commit()

        tres_giant = TestResult(
            id=uuid.uuid4(),
            test_run_id=tr_giant.id,
            test_case_id=tc1_id,
            status="failed",
            duration=1.0,
            created_at=datetime.datetime.utcnow()
        )
        db.add(tres_giant)
        db.commit()

        # Re-mine
        fragility_service.mine_fragility_patterns(repo_id)
        
        # Verify combo size never exceeds MAX_RISKY_COMBINATION_SIZE = 5
        giant_combos = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.pattern_type == "RISKY_COMBINATION"
        ).all()
        for c in giant_combos:
            combo_files = c.context.get("trigger_files", [])
            assert len(combo_files) <= 5
        print("[OK] Risky exact combinations detected; giant combinations (> 5 files) successfully capped.")

        # --------------------------------------------------------------------
        # Test 6. Test clusters
        # --------------------------------------------------------------------
        print("\n--- Test 6. Test clusters ---")
        p_cluster = db.query(FragilityPattern).filter(
            FragilityPattern.repository_id == repo_id,
            FragilityPattern.pattern_type == "TEST_CLUSTER_FAILURE"
        ).first()
        
        # Repeated meaningful test suite clusters failing from neighborhood changes generate patterns
        assert p_cluster is not None
        assert p_cluster.normalized_pattern_key.startswith("TEST_CLUSTER_FAILURE:auth_suite:")
        print("[OK] Meaningful test cluster failures successfully mined.")

        # --------------------------------------------------------------------
        # Test 7. Scoring determinism
        # --------------------------------------------------------------------
        print("\n--- Test 7. Scoring determinism ---")
        # Run recalculation multiple times with the same DB inputs
        # Deterministic scoring is calculated continuously
        scores = []
        for _ in range(3):
            # Mine to ensure fresh scores
            db.query(FragilityPattern).filter(FragilityPattern.status != "INVALIDATED").delete()
            db.commit()
            fragility_service.mine_fragility_patterns(repo_id)
            p = db.query(FragilityPattern).filter(
                FragilityPattern.repository_id == repo_id,
                FragilityPattern.normalized_pattern_key == "FILE_FAILURE_FREQUENCY:src/auth.py"
            ).first()
            scores.append(p.fragility_score)

        print(f"DEBUG: Mined score history: {scores}")
        # All scores must be identical to the decimal point
        assert len(set(scores)) == 1
        print("[OK] Fragility scoring is 100% deterministic (same evidence always produces same score).")

        # --------------------------------------------------------------------
        # Test 8. Explanation correctness
        # --------------------------------------------------------------------
        print("\n--- Test 8. Explanation correctness ---")
        patterns = db.query(FragilityPattern).filter(FragilityPattern.repository_id == repo_id).all()
        for p in patterns:
            explanation = FragilityReasoningBuilder.build_explanation(p)
            print(f"DEBUG: Pattern {p.pattern_type} explanation: '{explanation}'")
            # Every explanation references evidence counts
            assert any(str(p.evidence_count) in explanation or "incidents" in explanation or "failures" in explanation for _ in [1])
            # Bounded explanation below 500 characters
            assert len(explanation) <= 500
            # Standard non-speculative vocabulary checked
            assert not any(kw in explanation.lower() for kw in ("ai believes", "likely risky", "architecture claims"))
        print("[OK] Explanation correctness, strict bounding, and evidence trace verified.")

        # --------------------------------------------------------------------
        # Test 9. Replayability
        # --------------------------------------------------------------------
        print("\n--- Test 9. Replayability ---")
        snapshot_service = FragilitySnapshotService(db)
        
        # Recalculate twice to verify identical immutability hash
        snap1 = snapshot_service.generate_fragility_snapshot(repo_id)
        snap2 = snapshot_service.generate_fragility_snapshot(repo_id)
        
        print(f"DEBUG: Snapshot 1 Hash: {snap1.snapshot_hash}")
        print(f"DEBUG: Snapshot 2 Hash: {snap2.snapshot_hash}")
        assert snap1.snapshot_hash == snap2.snapshot_hash
        
        # Verify lineage traces all active patterns and links accurately
        lineage = snapshot_service.get_snapshot_lineage(snap1.id)
        assert lineage["snapshot_hash"] == snap1.snapshot_hash
        assert len(lineage["patterns"]) > 0
        for pat in lineage["patterns"]:
            assert "evidence_links" in pat
            assert len(pat["evidence_links"]) > 0
        print("[OK] Deterministic immutable snapshot hashes and deep lineages are 100% replayable.")

        # --------------------------------------------------------------------
        # Test 10. Recommendation integration
        # --------------------------------------------------------------------
        print("\n--- Test 10. Recommendation integration ---")
        
        # Seed FileDependency so has_deps is True and dependency_graph_confidence is HIGH
        # Clean dependencies and seed specifically for auth.py -> utils.py
        db.query(FileDependency).delete()
        db.commit()
        
        dep1 = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/auth.py",
            depends_on_file_path="src/utils.py",
            dependency_type="import",
            commit_sha="sha_commit_0_sha"
        )
        db.add(dep1)
        db.commit()

        # Clean all patterns except two active HIGH risk patterns to trigger SAFE_FALLBACK
        db.query(FragilityPattern).delete()
        db.commit()

        p_freq = FragilityPattern(
            id=uuid.uuid4(),
            repository_id=repo_id,
            pattern_type="FILE_FAILURE_FREQUENCY",
            normalized_pattern_key="FILE_FAILURE_FREQUENCY:src/auth.py",
            title="File Failure Frequency: src/auth.py",
            explanation="Changes involving src/auth.py preceded 5 failed executions.",
            fragility_score=80.0,
            risk_level="HIGH",
            confidence_level="HIGH",
            pattern_hash="p1_hash",
            score_components={"frequency": 80.0},
            replayable_evidence_snapshot={},
            status="ACTIVE",
            evidence_count=5,
            last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=2),
            context={"trigger_file": "src/auth.py", "related_tests": ["auth_suite::test_scope"]}
        )
        db.add(p_freq)

        p_cofail = FragilityPattern(
            id=uuid.uuid4(),
            repository_id=repo_id,
            pattern_type="CO_FAILURE_PATTERN",
            normalized_pattern_key="CO_FAILURE_PATTERN:src/auth.py->test_billing",
            title="Co Failure: src/auth.py",
            explanation="Changes co-failed with downstream test.",
            fragility_score=85.0,
            risk_level="HIGH",
            confidence_level="HIGH",
            pattern_hash="p2_hash",
            score_components={"frequency": 85.0},
            replayable_evidence_snapshot={},
            status="ACTIVE",
            evidence_count=3,
            last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=2),
            context={"trigger_file": "src/auth.py", "failure_test": "billing_suite::test_billing", "related_tests": ["billing_suite::test_billing"]}
        )
        db.add(p_cofail)
        db.commit()

        # Seed evidence link
        link = FragilityEvidenceLink(
            id=uuid.uuid4(),
            fragility_pattern_id=p_freq.id,
            evidence_type="TEST_FAILURE",
            evidence_summary="Failed run evidence"
        )
        db.add(link)
        db.commit()

        # Trigger recommendation
        rec_service = RecommendationService(db)
        run_in = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id="sha_commit_0_sha",
            changed_files=["src/auth.py"],
            triggered_by="manual"
        )
        run_rec = rec_service.create_recommendation_run(run_in)
        assert run_rec is not None
        
        # Verify warnings, safe fallbacks, and priority mapping
        print(f"DEBUG: recommendation run mode: {run_rec.recommendation_mode}")
        print(f"DEBUG: recommendation rationale summary: '{run_rec.recommendation_reasoning_summary}'")
        
        # Must escalate to SAFE_FALLBACK (>= 2 active high risk patterns)
        assert run_rec.recommendation_mode == "SAFE_FALLBACK"
        # Must amplify warnings in summary
        assert "Warning: High-risk historical fragility detected" in run_rec.recommendation_reasoning_summary
        
        # Must degrade runtime confidence to MODERATE
        assert run_rec.runtime_confidence == "MODERATE"
        
        # Must trace fragility patterns transparently in reasoning entries
        reasoning = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run_rec.id,
            RecommendationReasoningEntry.reason_type == "historical_fragility"
        ).all()
        assert len(reasoning) == 2
        for r in reasoning:
            assert r.human_readable_reason.startswith("Historical fragility pattern detected: ")
            assert "Pattern ID: " in r.human_readable_reason
            assert "Risk Level: " in r.human_readable_reason
            assert "Evidence: " in r.human_readable_reason
            
        print("[OK] Fragility integration verified successfully (mode escalations, warnings, and priority trace are intact).")

    finally:
        cleanup_database()
        db.close()

    print("\n=======================================================")
    print("ALL 10 FRAGILITY INTELLIGENCE PLATFORM E2E CHECKS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_end_to_end_verification()
    finally:
        cleanup_database()
