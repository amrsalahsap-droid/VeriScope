import os
import sys
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.test_result import TestCase, TestRun, TestResult
from app.models.flaky_test import FlakyTestProfile
from app.models.recalculation_job import FlakyRecalculationJob
from app.models.observability import SystemEvent
from app.models.recommendation import RecommendationRun, RecommendationTest, RecommendationReasoningEntry
from app.services.flaky_test_service import FlakyTestService
from app.services.recommendation import RecommendationService
from app.schemas.recommendation import RecommendationRunCreate

client = TestClient(app)

def cleanup_database():
    """Cleans up the database of verification records."""
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationTest).delete()
        db.query(RecommendationRun).delete()
        db.query(SystemEvent).delete()
        db.query(FlakyRecalculationJob).delete()
        db.query(FlakyTestProfile).delete()
        db.query(TestResult).delete()
        db.query(TestRun).delete()
        db.query(TestCase).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("Database cleanup successful.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def run_verification():
    print("======================================================================")
    print("STARTING FLAKINESS SYSTEM & RECOMMENDATION DEGRADATION VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # Seeding core organizations and repositories
        org = Organization(id=org_id, name="Calibrated Labs", slug="calibrated-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=987654,
            name="trust-core",
            full_name="calibrated-labs/trust-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()
        print(f"SUCCESS: Seeded Organization {org_id} and Repository {repo_id}")

        service = FlakyTestService(db)

        # --------------------------------------------------------------------
        # 1. Schema & Environment Metadata Persistence Verification
        # --------------------------------------------------------------------
        print("\n--- 1. Testing Schema and Environment Metadata Persistence ---")
        
        tc1 = TestCase(
            id=uuid.uuid4(),
            repository_id=repo_id,
            suite_name="trust_suite",
            test_name="test_auth_flow",
            stable_identity="trust_suite::test_auth_flow",
            canonical_identity_hash="auth_hash_1",
            identity_lineage_root_hash="auth_hash_root_1"
        )
        db.add(tc1)
        db.commit()

        # Seed 5 results with request_origin and framework information
        for i in range(5):
            run = TestRun(
                id=uuid.uuid4(),
                repository_id=repo_id,
                status="SUCCESS",
                file_hash=f"file_hash_auth_{i}",
                normalized_execution_fingerprint=f"fingerprint_auth_{i}",
                request_origin="github_actions",
                parser_version="junit_pytest",
                created_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=10 * i)
            )
            db.add(run)
            db.flush()

            res = TestResult(
                id=uuid.uuid4(),
                test_run_id=run.id,
                test_case_id=tc1.id,
                status="passed" if i % 2 == 0 else "failed",
                failure_message="assertion failed: expected True" if i % 2 != 0 else None,
                created_at=run.created_at
            )
            db.add(res)
        db.commit()

        profile1 = service.calculate_profile(tc1.id)
        assert profile1 is not None
        assert profile1.execution_environment == "github_actions"
        assert profile1.runner_type == "github-hosted"
        assert profile1.ci_provider == "github_actions"
        assert profile1.test_framework == "junit_pytest"
        assert profile1.confidence_level == "LOW"
        print("SUCCESS: Environment execution metadata mapped from TestRun successfully!")

        # --------------------------------------------------------------------
        # 2. Math & Sparse-History Uncertainty Mapping Verification
        # --------------------------------------------------------------------
        print("\n--- 2. Testing Math heuristics and Sparse-History mappings ---")
        
        # tc1 has 5 runs. Alternating P/F/P/F/P.
        # Chronological order (oldest to newest): failed, passed, failed, passed, failed (reverse of i=4,3,2,1,0).
        # i=0: passed (index 0 - newest)
        # i=1: failed (index 1)
        # i=2: passed (index 2)
        # i=3: failed (index 3)
        # i=4: passed (index 4 - oldest)
        # Chronological: passed, failed, passed, failed, passed.
        # Transitions = 4 (passed->failed->passed->failed->passed)
        # total_runs = 5, total_runs - 1 = 4. Instability score = 4 / 4 = 1.0
        # Weight sum: 0.9^0 + 0.9^1 + 0.9^2 + 0.9^3 + 0.9^4 = 1 + 0.9 + 0.81 + 0.729 + 0.6561 = 4.0951
        # Failure weight sum (i=1,3 are failures): 0.9^1 + 0.9^3 = 0.9 + 0.729 = 1.629
        # Recent Failure Rate = 1.629 / 4.0951 = 0.397 (approx 39.7%)
        # Instability score: 1.0, status: unstable.
        assert profile1.status == "unstable"
        assert abs(profile1.instability_score - 1.0) < 0.001
        assert abs(profile1.recent_failure_rate - 0.3977) < 0.01
        assert profile1.confidence_level == "LOW"
        print(f"SUCCESS: Low-history (sample size 5) evaluated: instability={profile1.instability_score:.2f}, failure_rate={profile1.recent_failure_rate:.3f}, confidence={profile1.confidence_level}")

        # Now seed up to 35 runs to achieve HIGH confidence level
        tc2 = TestCase(
            id=uuid.uuid4(),
            repository_id=repo_id,
            suite_name="trust_suite2",
            test_name="test_user_profile",
            stable_identity="trust_suite2::test_user_profile",
            canonical_identity_hash="user_hash_1",
            identity_lineage_root_hash="user_hash_root_1"
        )
        db.add(tc2)
        db.commit()

        for j in range(35):
            run = TestRun(
                id=uuid.uuid4(),
                repository_id=repo_id,
                status="SUCCESS",
                file_hash=f"file_hash_user_{j}",
                normalized_execution_fingerprint=f"fingerprint_user_{j}",
                created_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=10 * j)
            )
            db.add(run)
            db.flush()

            res = TestResult(
                id=uuid.uuid4(),
                test_run_id=run.id,
                test_case_id=tc2.id,
                status="passed" if j % 5 != 0 else "failed", # Fail 7 times out of 35
                failure_message="assertion failed: expected 200" if j % 5 == 0 else None,
                created_at=run.created_at
            )
            db.add(res)
        db.commit()

        profile2 = service.calculate_profile(tc2.id)
        assert profile2 is not None
        assert profile2.confidence_level == "HIGH"
        assert profile2.status == "unstable" # failure rate threshold 0.1, recent failure rate is weighted towards index 0 which is failure (j=0)
        print(f"SUCCESS: High-history (sample size 35) evaluated: instability={profile2.instability_score:.2f}, recent_failure_rate={profile2.recent_failure_rate:.3f}, confidence={profile2.confidence_level}")

        # --------------------------------------------------------------------
        # 3. Failure Mode Distribution Classification Keywords Verification
        # --------------------------------------------------------------------
        print("\n--- 3. Testing Failure Mode Keywords Classification ---")
        
        tc3 = TestCase(
            id=uuid.uuid4(),
            repository_id=repo_id,
            suite_name="trust_suite3",
            test_name="test_api_throttling",
            stable_identity="trust_suite3::test_api_throttling",
            canonical_identity_hash="throttling_hash_1",
            identity_lineage_root_hash="throttling_hash_root_1"
        )
        db.add(tc3)
        db.commit()

        # Seed failure modes: 2 timeouts, 1 infra connection error, 2 assertion failures, 1 unknown
        failure_messages = [
            "timeout waiting for socket response",
            "operation timed out",
            "infra_error: connection refused",
            "assertion failed: expected True",
            "assert 500 == 200",
            "generic database error"
        ]

        for k, msg in enumerate(failure_messages):
            run = TestRun(
                id=uuid.uuid4(),
                repository_id=repo_id,
                status="SUCCESS",
                file_hash=f"file_hash_fail_{k}",
                normalized_execution_fingerprint=f"fingerprint_fail_{k}",
                created_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=10 * k)
            )
            db.add(run)
            db.flush()

            res = TestResult(
                id=uuid.uuid4(),
                test_run_id=run.id,
                test_case_id=tc3.id,
                status="failed",
                failure_message=msg,
                created_at=run.created_at
            )
            db.add(res)
        db.commit()

        profile3 = service.calculate_profile(tc3.id)
        assert profile3 is not None
        dist = profile3.failure_mode_distribution
        assert dist["timeout"] == 2
        assert dist["infra_error"] == 1
        assert dist["assertion_failure"] == 2
        assert dist["unknown"] == 1
        print(f"SUCCESS: Failure mode distribution classified perfectly: timeout={dist['timeout']}, infra={dist['infra_error']}, assertion={dist['assertion_failure']}, unknown={dist['unknown']}")

        # --------------------------------------------------------------------
        # 4. Quarantine Lock Safety Verification
        # --------------------------------------------------------------------
        print("\n--- 4. Testing Quarantine Safety Preservation ---")
        
        # Place tc3 into quarantine manually
        profile3.status = "quarantined"
        profile3.quarantined_at = datetime.datetime.utcnow()
        profile3.quarantine_reason = "Manual quarantine due to ongoing infra investigation."
        profile3.quarantined_by = "lead_sre"
        profile3.rationale = "Preserve this quarantine state!"
        db.commit()

        # Trigger recalculate profile
        recalculated_profile3 = service.calculate_profile(tc3.id)
        assert recalculated_profile3.status == "quarantined"
        assert recalculated_profile3.quarantine_reason == "Manual quarantine due to ongoing infra investigation."
        assert recalculated_profile3.quarantined_by == "lead_sre"
        assert recalculated_profile3.rationale == "Preserve this quarantine state!"
        print("SUCCESS: Quarantined profile status and metadata were protected from recalculation overwrites!")

        # --------------------------------------------------------------------
        # 5. Decay Recovery Heuristics & Staleness Expiration Verification
        # --------------------------------------------------------------------
        print("\n--- 5. Testing Stability Recovery and Staleness Expiration ---")
        
        # Seed 10 consecutive passing runs to an unstable test (tc1)
        for i in range(10):
            run = TestRun(
                id=uuid.uuid4(),
                repository_id=repo_id,
                status="SUCCESS",
                file_hash=f"file_hash_rec_{i}",
                normalized_execution_fingerprint=f"fingerprint_rec_{i}",
                created_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=10 * i) # chronological order newest
            )
            db.add(run)
            db.flush()

            res = TestResult(
                id=uuid.uuid4(),
                test_run_id=run.id,
                test_case_id=tc1.id,
                status="passed",
                created_at=run.created_at
            )
            db.add(res)
        db.commit()

        recovered_profile1 = service.calculate_profile(tc1.id)
        assert recovered_profile1.status == "stable"
        assert recovered_profile1.stability_recovered_at is not None
        assert recovered_profile1.instability_score == 0.0
        assert recovered_profile1.recent_failure_rate == 0.0
        assert "Recovered stability:" in recovered_profile1.rationale
        print("SUCCESS: Test recovered to stable after 10 consecutive passing runs!")

        # Test staleness expiration
        profile2.last_recalculated_at = datetime.datetime.utcnow() - datetime.timedelta(days=15)
        db.commit()
        # Fetching flaky profiles trigger staleness check
        unstable_profiles = service.get_flaky_profiles(repo_id)
        matching_profile2 = next((p for p in unstable_profiles if p.test_case_id == tc2.id), None)
        assert matching_profile2 is not None
        assert matching_profile2.stale_profile is True
        print("SUCCESS: Profile successfully flagged as stale after 15 days of recalculation neglect!")

        # --------------------------------------------------------------------
        # 6. Recalculation Storm Shield Verification
        # --------------------------------------------------------------------
        print("\n--- 6. Testing Recalculation Storm deduplication shield ---")
        
        # Trigger first recalculation job
        res_job1 = service.trigger_recalculation_job(repo_id)
        assert res_job1["status"] == "RUNNING"
        assert res_job1["newly_created"] is True
        job1_id = res_job1["job_id"]

        # Trigger duplicate recalculation job while first is RUNNING
        res_job2 = service.trigger_recalculation_job(repo_id)
        assert res_job2["status"] == "RUNNING"
        assert res_job2["newly_created"] is False
        assert res_job2["job_id"] == job1_id

        # Verify duplicate trigger SystemEvent was emitted
        events = db.query(SystemEvent).filter(SystemEvent.event_type == "flaky_recalculation_deduplicated").all()
        assert len(events) == 1
        assert events[0].entity_id == str(repo_id)
        print(f"SUCCESS: Storm shield blocked redundant recalculations and logged event '{events[0].event_type}'!")

        # Complete the running job
        service.run_recalculation(job1_id, repo_id)
        db.refresh(db.query(FlakyRecalculationJob).filter(FlakyRecalculationJob.id == job1_id).first())
        job_final = db.query(FlakyRecalculationJob).filter(FlakyRecalculationJob.id == job1_id).first()
        assert job_final.status == "COMPLETED"
        assert job_final.completed_at is not None
        print("SUCCESS: Concluded async recalculation worker task updates completed cleanly!")

        # --------------------------------------------------------------------
        # 7. Recommendation Confidence Degradation & Reasoning warnings
        # --------------------------------------------------------------------
        print("\n--- 7. Testing Recommendation Degradation & Explainability warnings ---")
        
        # We have tc2 which is 'unstable' with HIGH confidence.
        # Let's perform a recommendation run triggering tc2.
        # Recommendation run input:
        # Changed files triggers direct file mapping for 'test_user_profile' which matches tc2.
        rec_service = RecommendationService(db)
        
        run_in = RecommendationRunCreate(
            repository_id=repo_id,
            pr_id="pr_101",
            triggered_by="github-webhook",
            changed_files=["app/services/user_profile.py"] # Triggers test_user_profile
        )

        rec_run = rec_service.create_recommendation_run(run_in)
        
        # Asserts:
        # 1. test_user_profile is recommended (not excluded!)
        recommended_tc_ids = [t.test_case_id for t in rec_run.tests]
        assert any("test_user_profile" in tc_id for tc_id in recommended_tc_ids)

        # 2. evidence_quality is degraded from HIGH to MODERATE because tc2 is HIGH confidence unstable
        # Wait, what was the evidence quality without flaky?
        # Latest coverage does not exist, so base evidence quality would be LOW (due to missing coverage).
        # If it was LOW, degrading by one tier makes it LOW. Let's seed a HIGH coverage report so base is HIGH.
        # This will prove the degradation step perfectly!
        # Let's clean up and run this specific check with HIGH base coverage to prove tier drop.
        
        print("SUCCESS: Unstable test remained recommended (not silently excluded) in recommended suite!")

        # Seed HIGH coverage report to test clean HIGH -> MODERATE tier drop
        from app.models.coverage import CoverageReport
        cov = CoverageReport(
            id=uuid.uuid4(),
            repository_id=repo_id,
            commit_sha="pr_101",
            confidence_score="HIGH",
            overall_coverage_pct=95.0,
            file_hash="dummy_file_hash",
            created_at=datetime.datetime.utcnow()
        )
        db.add(cov)
        db.commit()

        # Re-run recommendation with HIGH coverage report seeded
        rec_run2 = rec_service.create_recommendation_run(run_in)
        
        # Base would be HIGH. Flaky test tc2 has HIGH confidence.
        # High confidence flaky test degrades evidence quality from HIGH to MODERATE!
        assert rec_run2.evidence_quality == "MODERATE", f"Expected degraded evidence quality MODERATE, got {rec_run2.evidence_quality}"
        print(f"SUCCESS: Non-linear degradation drop asserted cleanly: base HIGH was degraded to {rec_run2.evidence_quality}")

        # Check Reasoning Entry warnings
        reason_warnings = [e for e in rec_run2.reasoning_entries if e.reason_type == "flaky_test_warning"]
        assert len(reason_warnings) == 1
        warn = reason_warnings[0]
        assert "test_user_profile" in warn.source_entity
        assert warn.source_reference == str(profile2.id)
        assert warn.confidence_level == "HIGH"
        assert warn.evidence_priority == "IMPORTANT"
        assert len(warn.human_readable_reason) <= 500
        assert "Marked unstable:" in warn.human_readable_reason
        assert "instability:" in warn.human_readable_reason
        assert "recent failure rate:" in warn.human_readable_reason
        print("SUCCESS: Persistent explainability reasoning warnings matched specifications:")
        print(f"  - source_entity: {warn.source_entity}")
        print(f"  - source_reference: {warn.source_reference}")
        print(f"  - reason_type: {warn.reason_type}")
        print(f"  - priority: {warn.evidence_priority}")
        print(f"  - warning message: {warn.human_readable_reason}")

        # --------------------------------------------------------------------
        # 8. Paginated API diagnostics check
        # --------------------------------------------------------------------
        print("\n--- 8. Testing Paginated GET /internal/flaky-tests/{repo_id} Route ---")
        
        response = client.get(f"/internal/flaky-tests/{repo_id}")
        assert response.status_code == 200
        data = response.json()
        
        # Flaky profiles (unstable and quarantined) should be tc2 and tc3 (tc1 is stable)
        assert data["total"] == 2
        profiles_list = data["profiles"]
        assert len(profiles_list) == 2
        
        names = [p["test_name"] for p in profiles_list]
        assert "test_user_profile" in names
        assert "test_api_throttling" in names
        
        # Pagination limit check
        response_pag = client.get(f"/internal/flaky-tests/{repo_id}?limit=1")
        assert response_pag.status_code == 200
        data_pag = response_pag.json()
        assert data_pag["total"] == 2
        assert len(data_pag["profiles"]) == 1
        print("SUCCESS: Paginated diagnostics list endpoint operates successfully!")

    finally:
        db.close()

    print("\n=======================================================")
    print("ALL FLAKINESS & DEGRADATION INTEGRATION TESTS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
