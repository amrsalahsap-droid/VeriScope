import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationReasoningEntry,
    RecommendationInputSnapshot
)

client = TestClient(app)

def cleanup_database():
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationTest).delete()
        db.query(RecommendationInputSnapshot).delete()
        db.query(RecommendationRun).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def run_targeted_debug_tests():
    cleanup_database()
    print("Starting targeted internal debug API verification...")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    run_id = uuid.uuid4()

    try:
        org = Organization(id=org_id, name="Debug Corp", slug="debug-corp")
        db.add(org)

        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=987789,
            name="debug-repo",
            full_name="debug-corp/debug-repo",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # Seed Recommendation Run
        rec_run = RecommendationRun(
            id=run_id,
            repository_id=repo_id,
            pr_id="12",
            triggered_by="manual",
            evidence_quality="HIGH",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Auditing debug queries",
            recommendation_mode="NORMAL",
            unsafe_for_optimization=False,
            skipped_reason_summary="None",
            skipped_count=0,
            top_skipped_examples=[]
        )
        db.add(rec_run)

        # Seed multiple reasoning entries (5 entries)
        for i in range(5):
            entry = RecommendationReasoningEntry(
                id=uuid.uuid4(),
                recommendation_run_id=run_id,
                reason_type=f"reason_{i}",
                source_entity=f"file_{i}.py",
                source_reference="HEAD",
                human_readable_reason=f"Detailed reason number {i}",
                confidence_level="HIGH",
                evidence_priority="CRITICAL",
                created_at=datetime.utcnow()
            )
            db.add(entry)

        # Seed 2 recommended tests
        for i in range(2):
            test = RecommendationTest(
                id=uuid.uuid4(),
                recommendation_run_id=run_id,
                test_case_id=f"test_case_{i}",
                reason_type="direct",
                reason_details={},
                priority_score=0.9
            )
            db.add(test)

        # Seed input snapshot
        snapshot = RecommendationInputSnapshot(
            id=uuid.uuid4(),
            recommendation_run_id=run_id,
            changed_files=["file_0.py"],
            direct_mappings_used=[{"test_case_id": "test_case_0"}],
            heuristic_mappings_used=[],
            dependency_files_expanded=[],
            coverage_links_used=[],
            flaky_profiles_used=[],
            historical_failures_used=[],
            degradation_rules_triggered=[],
            ranking_inputs={"test_case_0": 0.9}
        )
        db.add(snapshot)
        db.commit()
    finally:
        db.close()

    # 1. Default Behavior Check (include_input_snapshot=False, include_reasoning=True, include_tests=True)
    print("Testing default debug queries...")
    res = client.get(f"/internal/recommendations/{run_id}/debug")
    assert res.status_code == 200, f"Failed GET: {res.text}"
    data = res.json()
    assert data["id"] == str(run_id)
    assert data["recommendation_mode"] == "NORMAL"
    assert data["evidence_quality"] == "HIGH"
    
    # Should not include input snapshot by default
    assert data["input_snapshot"] is None
    
    # Should include reasoning and tests by default (for backward compatibility)
    assert len(data["reasoning_entries"]) == 5
    assert len(data["recommended_tests"]) == 2
    print("[OK] Default behavior matches perfectly.")

    # 2. Query Parameter Check (Explicitly requesting snapshot, reasoning, and tests)
    print("Testing explicit include query params...")
    res2 = client.get(f"/internal/recommendations/{run_id}/debug?include_input_snapshot=true&include_reasoning=true&include_tests=true")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["input_snapshot"] is not None
    assert data2["input_snapshot"]["changed_files"] == ["file_0.py"]
    assert len(data2["reasoning_entries"]) == 5
    assert len(data2["recommended_tests"]) == 2
    print("[OK] Query parameters parsed and snapshots populated correctly.")

    # 3. Query Parameter Check (Excluding reasoning and tests explicitly)
    print("Testing explicit exclusion...")
    res3 = client.get(f"/internal/recommendations/{run_id}/debug?include_reasoning=false&include_tests=false")
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["input_snapshot"] is None
    assert data3["reasoning_entries"] is None
    assert data3["recommended_tests"] is None
    print("[OK] Exclusion query params respected correctly (Do not inline huge blobs unless requested).")

    # 4. reasoning_limit Check (bounding query results)
    print("Testing reasoning limit bounds...")
    res4 = client.get(f"/internal/recommendations/{run_id}/debug?include_reasoning=true&reasoning_limit=2")
    assert res4.status_code == 200
    data4 = res4.json()
    assert len(data4["reasoning_entries"]) == 2
    print("[OK] Query limit bounds respected correctly.")

    print("\nALL TARGETED INTERNAL DEBUG ENDPOINT TESTS PASSED SUCCESSFULLY!")
    cleanup_database()

if __name__ == "__main__":
    try:
        run_targeted_debug_tests()
    except Exception as e:
        cleanup_database()
        raise e
