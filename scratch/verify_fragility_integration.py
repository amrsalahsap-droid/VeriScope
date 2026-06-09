import os
import sys
import uuid
import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.test_result import TestCase, TestResult, TestRun
from app.models.recommendation import RecommendationRun, RecommendationReasoningEntry
from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink
from app.services.recommendation import RecommendationService
from app.schemas.recommendation import RecommendationRunCreate

from app.models.pull_request import PullRequest
from app.models.dependency import FileDependency

def cleanup_database():
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationRun).delete()
        db.query(FragilityEvidenceLink).delete()
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

def run_integration_verification():
    print("======================================================================")
    print("STARTING FRAGILITY INTELLIGENCE RECOMMENDATION INTEGRATION ASSERTIONS")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # 1. Seed base Org and Repo
        org = Organization(id=org_id, name="Integrate Labs", slug="integrate-labs")
        db.add(org)
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=121200,
            name="integrate-core",
            full_name="integrate-labs/integrate-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)

        # Seed PR
        pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo_id,
            github_pr_id=121200,
            number=121,
            title="Integrate auth test",
            author="bob",
            source_branch="auth-fix",
            target_branch="main",
            state="open",
            additions=10,
            deletions=2,
            changed_files_count=1,
            head_commit_sha="sha123commit",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)

        # 2. Seed Test Cases
        tc1_id = uuid.uuid4()
        tc1 = TestCase(
            id=tc1_id,
            repository_id=repo_id,
            suite_name="suite_val",
            test_name="test_first",
            stable_identity="suite_val::test_first",
            canonical_identity_hash="suite_val_test_first_hash",
            identity_lineage_root_hash="suite_val_test_first_hash"
        )
        db.add(tc1)

        tc2_id = uuid.uuid4()
        tc2 = TestCase(
            id=tc2_id,
            repository_id=repo_id,
            suite_name="suite_val",
            test_name="test_second",
            stable_identity="suite_val::test_second",
            canonical_identity_hash="suite_val_test_second_hash",
            identity_lineage_root_hash="suite_val_test_second_hash"
        )
        db.add(tc2)
        db.commit()

        # Seed TestRun and TestResults for execution duration history
        tr = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            status="passed",
            file_hash="dummy-run-hash",
            normalized_execution_fingerprint="dummy-run-fingerprint"
        )
        db.add(tr)
        db.commit()

        res_1 = TestResult(
            test_run_id=tr.id,
            test_case_id=tc1_id,
            status="passed",
            duration=1.0
        )
        db.add(res_1)

        res_2 = TestResult(
            test_run_id=tr.id,
            test_case_id=tc2_id,
            status="passed",
            duration=1.0
        )
        db.add(res_2)
        db.commit()

        # 3. Seed active and stale fragility patterns intersecting module.py
        p1_id = uuid.uuid4()
        p1 = FragilityPattern(
            id=p1_id,
            repository_id=repo_id,
            pattern_type="FILE_FAILURE_FREQUENCY",
            normalized_pattern_key="FILE_FAILURE_FREQUENCY:src/module.py",
            title="File Failure Frequency: src/module.py",
            explanation="Changes involving src/module.py preceded 5 failed executions in the last 90 days.",
            fragility_score=80.0,
            risk_level="HIGH",
            confidence_level="HIGH",
            pattern_hash="p1_hash_abc",
            score_components={"frequency": 80.0},
            replayable_evidence_snapshot={
                "summary_statistics": {
                    "total_evidence": 5,
                    "evidence_window_days": 90
                }
            },
            status="ACTIVE",
            evidence_count=5,
            last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=2),
            context={"trigger_file": "src/module.py", "related_tests": ["suite_val::test_first"]}
        )
        db.add(p1)

        p2_id = uuid.uuid4()
        p2 = FragilityPattern(
            id=p2_id,
            repository_id=repo_id,
            pattern_type="CO_FAILURE_PATTERN",
            normalized_pattern_key="CO_FAILURE_PATTERN:src/module.py->test_second",
            title="Co Failure: src/module.py",
            explanation="Changes involving src/module.py co-failed with downstream test suite_val::test_second in 3 regressions in the last 90 days.",
            fragility_score=40.0,
            risk_level="MODERATE",
            confidence_level="MODERATE",
            pattern_hash="p2_hash_def",
            score_components={"frequency": 40.0},
            replayable_evidence_snapshot={
                "summary_statistics": {
                    "total_evidence": 3,
                    "evidence_window_days": 90
                }
            },
            status="STALE",
            evidence_count=3,
            last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=20),
            context={"trigger_file": "src/module.py", "failure_test": "suite_val::test_second", "related_tests": ["suite_val::test_second"]}
        )
        db.add(p2)
        db.commit()

        # Seed evidence links
        link1 = FragilityEvidenceLink(
            id=uuid.uuid4(),
            fragility_pattern_id=p1_id,
            evidence_type="TEST_FAILURE",
            evidence_summary="File module.py failed in run 1."
        )
        db.add(link1)
        
        # Seed FileDependency so has_deps is True and dependency_graph_confidence is HIGH
        dep = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/module.py",
            depends_on_file_path="src/utils.py",
            dependency_type="import",
            commit_sha="sha123commit"
        )
        db.add(dep)
        db.commit()

        # 4. Trigger recommendation run
        rec_service = RecommendationService(db)
        run_in = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id="sha123commit",
            changed_files=["src/module.py"],
            triggered_by="manual"
        )
        run_rec = rec_service.create_recommendation_run(run_in)
        assert run_rec is not None

        # Verify active and stale candidate prioritization
        # "suite_val::test_first" (ACTIVE) -> should receive priority score 0.92 ((0.92 + 0.0) / 1.0)
        # "suite_val::test_second" (STALE) -> should receive lower priority score 0.35 ((0.35 + 0.0) / 1.0)
        tests = db.query(RecommendationRun).filter(RecommendationRun.id == run_rec.id).first().tests
        
        test_scope_rec = next(t for t in tests if t.test_case_id == "suite_val::test_first")
        print(f"DEBUG: Active pattern matched test priority: {test_scope_rec.priority_score}")
        print(f"DEBUG: Active pattern details: type={test_scope_rec.reason_type}, details={test_scope_rec.reason_details}")
        assert test_scope_rec.priority_score == 0.92

        test_isolation_rec = next(t for t in tests if t.test_case_id == "suite_val::test_second")
        print(f"DEBUG: Stale pattern matched test priority: {test_isolation_rec.priority_score}")
        print(f"DEBUG: Stale pattern details: type={test_isolation_rec.reason_type}, details={test_isolation_rec.reason_details}")
        assert test_isolation_rec.priority_score == 0.35
        print("[OK] Priority boosts verified: ACTIVE patterns boost high (0.92), STALE patterns receive lower weighting (0.35).")

        # Verify reasoning entries format (Rule 3 & 4)
        reasoning_entries = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run_rec.id,
            RecommendationReasoningEntry.reason_type == "historical_fragility"
        ).all()
        
        print(f"DEBUG: Reasoning Entries Count: {len(reasoning_entries)}")
        assert len(reasoning_entries) == 2

        for entry in reasoning_entries:
            print(f"DEBUG: Entry Human Reasoning: '{entry.human_readable_reason}'")
            # Must start with Example prefix
            assert entry.human_readable_reason.startswith("Historical fragility pattern detected: ")
            # Must contain ID
            assert "Pattern ID: " in entry.human_readable_reason
            # Must contain Risk Level
            assert "Risk Level: " in entry.human_readable_reason
            # Must contain Evidence/regressions
            assert "regressions" in entry.human_readable_reason or "regression" in entry.human_readable_reason
            
        print("[OK] Recommendation reasoning formats verified to contain all required variables deterministically.")

        # ====================================================================
        # Test 2. Verification of Safe Fallback (and no silent full regression)
        # ====================================================================
        print("\n--- 2. Testing Safe Fallback Escalation Rules ---")
        
        # Clean p2 stale status to ACTIVE and boost risk level to HIGH to trigger SAFE_FALLBACK (>= 2 active high-risk patterns)
        p2.status = "ACTIVE"
        p2.risk_level = "HIGH"
        db.commit()

        run_rec_fallback = rec_service.create_recommendation_run(run_in)
        print(f"DEBUG: Escalation mode: {run_rec_fallback.recommendation_mode}")
        
        # Must escalate to SAFE_FALLBACK
        assert run_rec_fallback.recommendation_mode == "SAFE_FALLBACK"
        # Must NOT silently trigger FULL_REGRESSION
        assert run_rec_fallback.recommendation_mode != "FULL_REGRESSION"
        print("[OK] Escalation rules verified successfully: escalated to SAFE_FALLBACK without silent regressions.")

    finally:
        cleanup_database()
        db.close()

if __name__ == "__main__":
    cleanup_database()
    try:
        run_integration_verification()
    finally:
        cleanup_database()
