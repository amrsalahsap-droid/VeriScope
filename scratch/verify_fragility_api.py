import os
import sys
import uuid
import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.test_result import TestCase, TestResult, TestRun
from app.models.recommendation import RecommendationRun, RecommendationReasoningEntry
from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink, FragilitySnapshot
from app.models.dependency import FileDependency
from app.models.pull_request import PullRequest

client = TestClient(app)

def cleanup_database():
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationRun).delete()
        db.query(FragilityEvidenceLink).delete()
        db.query(FragilityPattern).delete()
        db.query(FragilitySnapshot).delete()
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

def run_api_verification():
    print("======================================================================")
    print("STARTING FRAGILITY MEMORY ROUTING & WEB API INTELLIGENCE VERIFICATIONS")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # 1. Seed base multi-tenant architecture
        org = Organization(id=org_id, name="APILabs", slug="api-labs")
        db.add(org)
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=987654,
            name="api-core",
            full_name="api-labs/api-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        # Seed PR
        pr = PullRequest(
            id=uuid.uuid4(),
            repository_id=repo_id,
            github_pr_id=987654,
            number=98,
            title="API update",
            author="engineer-bob",
            source_branch="feat-api",
            target_branch="main",
            state="open",
            additions=15,
            deletions=5,
            changed_files_count=1,
            head_commit_sha="commit_sha_api",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)

        # Seed Test Case
        tc_id = uuid.uuid4()
        tc = TestCase(
            id=tc_id,
            repository_id=repo_id,
            suite_name="api_suite",
            test_name="test_endpoint",
            stable_identity="api_suite::test_endpoint",
            canonical_identity_hash="api_suite_test_endpoint_hash",
            identity_lineage_root_hash="api_suite_test_endpoint_hash"
        )
        db.add(tc)
        db.commit()

        # Seed TestRun and TestResult for cost
        tr = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            status="passed",
            file_hash="api-run-hash",
            normalized_execution_fingerprint="api-run-fingerprint"
        )
        db.add(tr)
        db.commit()

        res = TestResult(
            test_run_id=tr.id,
            test_case_id=tc_id,
            status="passed",
            duration=1.2
        )
        db.add(res)
        db.commit()

        # Seed FileDependency
        dep = FileDependency(
            id=uuid.uuid4(),
            repository_id=repo_id,
            file_path="src/api.py",
            depends_on_file_path="src/utils.py",
            dependency_type="import",
            commit_sha="commit_sha_api"
        )
        db.add(dep)
        db.commit()

        # 2. Seed active and stale fragility patterns for API testing
        p1_id = uuid.uuid4()
        p1 = FragilityPattern(
            id=p1_id,
            repository_id=repo_id,
            pattern_type="FILE_FAILURE_FREQUENCY",
            normalized_pattern_key="FILE_FAILURE_FREQUENCY:src/api.py",
            title="File Failure Frequency: src/api.py",
            explanation="Changes involving src/api.py preceded 5 failed executions.",
            fragility_score=75.0,
            risk_level="HIGH",
            confidence_level="HIGH",
            pattern_hash="hash_p1_api",
            score_components={"frequency": 75.0},
            replayable_evidence_snapshot={"evidence_ids": []},
            status="ACTIVE",
            evidence_count=5,
            incident_count=1,
            last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=1),
            context={"trigger_file": "src/api.py"}
        )
        db.add(p1)

        p2_id = uuid.uuid4()
        p2 = FragilityPattern(
            id=p2_id,
            repository_id=repo_id,
            pattern_type="CO_FAILURE_PATTERN",
            normalized_pattern_key="CO_FAILURE_PATTERN:src/api.py->test_endpoint",
            title="Co Failure: src/api.py",
            explanation="Changes involving src/api.py co-failed with downstream test.",
            fragility_score=35.0,
            risk_level="MODERATE",
            confidence_level="MODERATE",
            pattern_hash="hash_p2_api",
            score_components={"frequency": 35.0},
            replayable_evidence_snapshot={"evidence_ids": []},
            status="STALE",
            evidence_count=3,
            incident_count=0,
            last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=15),
            context={"trigger_file": "src/api.py"}
        )
        db.add(p2)
        db.commit()

        # Seed evidence links
        link1 = FragilityEvidenceLink(
            id=uuid.uuid4(),
            fragility_pattern_id=p1_id,
            evidence_type="TEST_FAILURE",
            source_test_run_id=tr.id,
            source_test_result_id=res.id,
            evidence_summary="File api.py failed on test run."
        )
        db.add(link1)

        link2 = FragilityEvidenceLink(
            id=uuid.uuid4(),
            fragility_pattern_id=p1_id,
            evidence_type="INCIDENT",
            source_incident_id="incident-99",
            evidence_summary="Escaped defect reported on api.py."
        )
        db.add(link2)
        db.commit()

        # --------------------------------------------------------------------
        # Test 1. GET /api/fragility/{repository_id}
        # --------------------------------------------------------------------
        print("--- Test 1. Verifying GET /api/fragility/{repository_id} active patterns list ---")
        response = client.get(f"/api/fragility/{repo_id}")
        assert response.status_code == 200
        data = response.json()
        
        # Must only return ACTIVE patterns (p1 is ACTIVE, p2 is STALE)
        print(f"DEBUG: Active patterns returned count: {len(data)}")
        assert len(data) == 1
        
        active_pattern = data[0]
        assert active_pattern["pattern_id"] == str(p1_id)
        assert active_pattern["risk_level"] == "HIGH"
        assert active_pattern["evidence_count"] == 5
        assert active_pattern["incident_count"] == 1
        assert "last_seen_at" in active_pattern
        print("[OK] GET /api/fragility/{repository_id} returns exact active patterns list and required fields.")

        # Test repository not found triggers 404
        response_404 = client.get(f"/api/fragility/{uuid.uuid4()}")
        assert response_404.status_code == 404
        print("[OK] GET /api/fragility/{repository_id} returned 404 for unknown repository.")

        # --------------------------------------------------------------------
        # Test 2. GET /api/fragility/{repository_id}/{pattern_id}
        # --------------------------------------------------------------------
        print("\n--- Test 2. Verifying GET /api/fragility/{repository_id}/{pattern_id} detail API ---")
        response_detail = client.get(f"/api/fragility/{repo_id}/{p1_id}")
        assert response_detail.status_code == 200
        detail_data = response_detail.json()
        
        assert detail_data["id"] == str(p1_id)
        assert len(detail_data["evidence_links"]) == 2
        assert len(detail_data["linked_failures"]) == 1
        assert len(detail_data["linked_incidents"]) == 1
        assert detail_data["score_components"]["frequency"] == 75.0
        
        # Check linked failures content
        linked_fail = detail_data["linked_failures"][0]
        assert linked_fail["source_test_run_id"] == str(tr.id)
        assert linked_fail["source_test_result_id"] == str(res.id)
        
        # Check linked incidents content
        linked_inc = detail_data["linked_incidents"][0]
        assert linked_inc["source_incident_id"] == "incident-99"
        
        print("[OK] GET /api/fragility/{repository_id}/{pattern_id} successfully returns detailed active and trace indicators.")

        # Test pattern not found triggers 404
        response_detail_404 = client.get(f"/api/fragility/{repo_id}/{uuid.uuid4()}")
        assert response_detail_404.status_code == 404
        print("[OK] GET /api/fragility/{repository_id}/{pattern_id} returned 404 for unknown pattern.")

        # --------------------------------------------------------------------
        # Test 3. POST /internal/fragility/recalculate
        # --------------------------------------------------------------------
        print("\n--- Test 3. Verifying POST /internal/fragility/recalculate Endpoint ---")
        
        # Create a historical test failure inside the 90 days window
        hist_run = TestRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            status="failed",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=5),
            file_hash="hist-run-hash-1",
            normalized_execution_fingerprint="hist-run-fingerprint-1"
        )
        db.add(hist_run)
        db.commit()

        hist_res = TestResult(
            test_run_id=hist_run.id,
            test_case_id=tc_id,
            status="failed",
            duration=1.0
        )
        db.add(hist_res)
        db.commit()

        # Seed snapshot entry so mine_fragility_patterns finds preceding inputs
        # (needs recommendation snapshots mapping commit_sha / PRs to mine co-failures/frequencies)
        from app.models.recommendation import RecommendationInputSnapshot
        from app.models.pull_request import PullRequestSyncJob
        
        run_rec = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repo_id,
            pr_id="commit_sha_api",
            pull_request_id=pr.id,
            triggered_by="webhook",
            evidence_quality="HIGH",
            engine_version="v1.2.0",
            recommendation_engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            fallback_policy_version="policy-v1",
            dependency_expansion_strategy_version="expansion-strategy-v1",
            recommendation_reasoning_summary="API Rec",
            recommendation_mode="NORMAL",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=5)
        )
        db.add(run_rec)
        db.commit()

        snap = RecommendationInputSnapshot(
            id=uuid.uuid4(),
            recommendation_run_id=run_rec.id,
            changed_files=["src/api.py"],
            direct_mappings_used=[],
            heuristic_mappings_used=[],
            dependency_files_expanded=[],
            coverage_links_used=[],
            flaky_profiles_used=[],
            historical_failures_used=[],
            degradation_rules_triggered=[],
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=5)
        )
        db.add(snap)
        db.commit()

        # Seed TestRun preceding this snap
        hist_run.pull_request_id = pr.id
        db.commit()

        # Clean all active/stale patterns so recalculation runs cleanly
        db.query(FragilityEvidenceLink).delete()
        db.query(FragilityPattern).delete()
        db.commit()

        # Trigger POST recalculate
        body = {
            "repository_id": str(repo_id),
            "history_window_days": 90
        }
        
        # Verify recalculate endpoint exists and succeeds
        response_recalc = client.post("/internal/fragility/recalculate", json=body)
        assert response_recalc.status_code == 200
        recalc_data = response_recalc.json()
        
        assert recalc_data["status"] == "success"
        assert recalc_data["repository_id"] == str(repo_id)
        assert recalc_data["history_window_days"] == 90
        assert "patterns_mined" in recalc_data
        assert "snapshot_id" in recalc_data
        assert "snapshot_hash" in recalc_data
        
        # Preserve historical snapshots check (snapshot record created in DB)
        snapshot_in_db = db.query(FragilitySnapshot).filter(
            FragilitySnapshot.id == uuid.UUID(recalc_data["snapshot_id"])
        ).first()
        assert snapshot_in_db is not None
        assert snapshot_in_db.snapshot_hash == recalc_data["snapshot_hash"]
        print("[OK] POST /internal/fragility/recalculate completes successfully, runs mining, and immutably generates a snapshot.")

        # --------------------------------------------------------------------
        # Test 4. Active Recalculation Deduplication
        # --------------------------------------------------------------------
        print("\n--- Test 4. Verifying Active Recalculation Deduplication ---")
        
        # Access the recalculating store inside the router module
        from app.routers.fragility import _recalculating_repos
        
        # Manually lock the repository recalculation
        _recalculating_repos.add(repo_id)
        try:
            response_dedup = client.post("/internal/fragility/recalculate", json=body)
            # Must return 409 Conflict
            assert response_dedup.status_code == 409
            print(f"DEBUG: Deduplicated recalculation response status: {response_dedup.status_code}")
            assert "already in progress" in response_dedup.json()["detail"]
            print("[OK] Simultaneous recalculations are successfully deduplicated with 409 Conflict.")
        finally:
            # Clean manually locked repo
            _recalculating_repos.discard(repo_id)

        # Assert clean run now succeeds
        response_clean = client.post("/internal/fragility/recalculate", json=body)
        assert response_clean.status_code == 200
        print("[OK] Recalculation succeeds once lock is cleanly released.")

    finally:
        cleanup_database()
        db.close()

    print("\n=======================================================")
    print("ALL FRAGILITY INTEL WEB API INTEGRATION CHECKS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_api_verification()
    finally:
        cleanup_database()
