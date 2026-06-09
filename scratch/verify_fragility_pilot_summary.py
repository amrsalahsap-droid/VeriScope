import os
import sys
import uuid
import datetime
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal, engine
from app.db.base import Base
import app.models
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.fragility_pattern import FragilityPattern
from app.services.fragility_pilot_summary_builder import FragilityPilotSummaryBuilder

def cleanup_database():
    """Clean up DB after testing."""
    db = SessionLocal()
    try:
        db.query(FragilityPattern).delete()
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
    print("STARTING VERISCOPE PHASE 7: FRAGILITY PILOT SUMMARY BUILDER VERIFICATION")
    print("======================================================================\n")

    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    try:
        # Seed base organization and repository
        org = Organization(id=org_id, name="Fragility Summary Labs", slug="fragility-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=656565,
            name="fragility-core",
            full_name="fragility-labs/fragility-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # Seed active patterns representing diverse categories and scores
        
        # 1. UNSTABLE_MODULE (Fragile Modules) - Seed 6 active + 1 invalidated
        # We expect only the top 5 active modules in descending score order (excluding score 60.0 and invalidated ones)
        print("Seeding Fragile Modules patterns...")
        for i, score in enumerate([90.0, 70.0, 85.0, 60.0, 80.0, 75.0]):
            db.add(FragilityPattern(
                repository_id=repo_id,
                pattern_type="UNSTABLE_MODULE",
                normalized_pattern_key=f"UNSTABLE_MODULE:src/module_{i}",
                title=f"Fragile Module {i}",
                explanation=f"Exceeded failure frequency inside module {i}.",
                fragility_score=score,
                risk_level="HIGH" if score > 75.0 else "MODERATE",
                status="ACTIVE"
            ))
        
        db.add(FragilityPattern(
            repository_id=repo_id,
            pattern_type="UNSTABLE_MODULE",
            normalized_pattern_key="UNSTABLE_MODULE:src/invalidated_module",
            title="Invalidated Module",
            explanation="This is an invalidated module.",
            fragility_score=99.0,
            risk_level="CRITICAL",
            status="INVALIDATED" # Pruned
        ))

        # 2. CO_FAILURE_PATTERN (Co-failure Patterns) - Seed 3 active
        print("Seeding Co-failure patterns...")
        db.add(FragilityPattern(
            repository_id=repo_id,
            pattern_type="CO_FAILURE_PATTERN",
            normalized_pattern_key="CO_FAILURE_PATTERN:auth:audit",
            title="permission change + audit logging impact",
            explanation="Changes in auth co-failed with downstream audit tests.",
            fragility_score=85.0,
            risk_level="HIGH",
            status="ACTIVE"
        ))
        db.add(FragilityPattern(
            repository_id=repo_id,
            pattern_type="CO_FAILURE_PATTERN",
            normalized_pattern_key="CO_FAILURE_PATTERN:billing:stripe",
            title="billing route + gateway failure",
            explanation="Billing file edits co-failed with downstream payment gateways.",
            fragility_score=92.0,
            risk_level="CRITICAL",
            status="ACTIVE"
        ))
        db.add(FragilityPattern(
            repository_id=repo_id,
            pattern_type="CO_FAILURE_PATTERN",
            normalized_pattern_key="CO_FAILURE_PATTERN:notification:slack",
            title="notifier + delivery delay",
            explanation="Notifier pipeline edits co-failed with downstream dispatchers.",
            fragility_score=50.0,
            risk_level="LOW",
            status="ACTIVE"
        ))

        # 3. ROLLBACK_INVOLVEMENT (Rollback-linked) - Seed 2 active
        print("Seeding Rollback-linked patterns...")
        db.add(FragilityPattern(
            repository_id=repo_id,
            pattern_type="ROLLBACK_INVOLVEMENT",
            normalized_pattern_key="ROLLBACK_INVOLVEMENT:db/migration",
            title="Database Schema Migration Rollbacks",
            explanation="Database schema changes linked directly to post-deployment rollbacks.",
            fragility_score=80.0,
            risk_level="HIGH",
            status="ACTIVE"
        ))
        db.add(FragilityPattern(
            repository_id=repo_id,
            pattern_type="ROLLBACK_INVOLVEMENT",
            normalized_pattern_key="ROLLBACK_INVOLVEMENT:cache/redis",
            title="Cache Redis Eviction Rollbacks",
            explanation="Cache layer evictions linked to production rollbacks.",
            fragility_score=45.0,
            risk_level="LOW",
            status="ACTIVE"
        ))

        # 4. DEPENDENCY_PROXIMITY (Unstable dependency neighborhoods) - Seed 4 active
        print("Seeding Dependency Neighborhood patterns...")
        for i, score in enumerate([35.0, 75.0, 65.0, 45.0]):
            db.add(FragilityPattern(
                repository_id=repo_id,
                pattern_type="DEPENDENCY_PROXIMITY",
                normalized_pattern_key=f"DEPENDENCY_PROXIMITY:service_{i}",
                title=f"Unstable Neighborhood {i}",
                explanation=f"Unstable transitives near service {i}.",
                fragility_score=score,
                risk_level="MODERATE" if score > 50.0 else "LOW",
                status="ACTIVE"
            ))

        # 5. FILE_FAILURE_FREQUENCY (High Churn Files) - Seed 1 active
        print("Seeding High Churn Files patterns...")
        db.add(FragilityPattern(
            repository_id=repo_id,
            pattern_type="FILE_FAILURE_FREQUENCY",
            normalized_pattern_key="FILE_FAILURE_FREQUENCY:src/legacy/parser.py",
            title="parser.py frequent failures",
            explanation=f"Frequent failed test executions linked to parser.py changes.",
            fragility_score=78.0,
            risk_level="HIGH",
            status="ACTIVE"
        ))

        db.commit()

        # 3. Generate summary
        print("--- TEST 1: Generating Operational Fragility Summary ---")
        summary = FragilityPilotSummaryBuilder.generate_fragility_summary(db, repo_id)
        assert summary is not None
        assert summary["repository_id"] == str(repo_id)
        print("[PASSED] Fragility summary generated successfully.\n")

        # 4. Assert Fragile Modules Truncation & Sorting
        print("--- TEST 2: Validating Top-5 Truncation & Descending Sorting ---")
        modules = summary["most_fragile_modules"]
        # Expected count = 5 (active counts = 6, invalidated = 1, limited to 5)
        assert len(modules) == 5
        
        # Expected order of scores: 90.0, 85.0, 80.0, 75.0, 70.0 (excluding 60.0 and 99.0 invalidated)
        assert modules[0]["fragility_score"] == 90.0
        assert modules[1]["fragility_score"] == 85.0
        assert modules[2]["fragility_score"] == 80.0
        assert modules[3]["fragility_score"] == 75.0
        assert modules[4]["fragility_score"] == 70.0
        
        # Verify that score 60.0 pattern and 99.0 invalidated pattern were excluded
        keys = [m["normalized_pattern_key"] for m in modules]
        assert "UNSTABLE_MODULE:src/invalidated_module" not in keys
        # The index with score 60.0 is module_3 (index 3 in seeding: [90.0, 70.0, 85.0, 60.0, 80.0, 75.0])
        assert "UNSTABLE_MODULE:src/module_3" not in keys
        print("[PASSED] Truncation and sorting executed perfectly.\n")

        # 5. Assert Co-failure patterns
        print("--- TEST 3: Validating Co-failure Patterns ---")
        co_fail = summary["most_repeated_co_failure_patterns"]
        assert len(co_fail) == 3
        # Sorted by score DESC: billing (92.0) -> auth (85.0) -> notification (50.0)
        assert co_fail[0]["title"] == "billing route + gateway failure"
        assert co_fail[0]["fragility_score"] == 92.0
        assert co_fail[1]["title"] == "permission change + audit logging impact"
        assert co_fail[1]["fragility_score"] == 85.0
        assert co_fail[2]["title"] == "notifier + delivery delay"
        assert co_fail[2]["fragility_score"] == 50.0
        print("[PASSED] Co-failure patterns matched expected values and sorted order.\n")

        # 6. Assert Rollback-linked patterns
        print("--- TEST 4: Validating Rollback-linked patterns ---")
        rollbacks = summary["rollback_linked_fragility_patterns"]
        assert len(rollbacks) == 2
        assert rollbacks[0]["title"] == "Database Schema Migration Rollbacks"
        assert rollbacks[0]["fragility_score"] == 80.0
        print("[PASSED] Rollback-linked patterns validated.\n")

        # 7. Assert Neighborhood patterns
        print("--- TEST 5: Validating Dependency Neighborhoods ---")
        neighborhoods = summary["unstable_dependency_neighborhoods"]
        assert len(neighborhoods) == 4
        # Sorted order of scores: 75.0 (service_1) -> 65.0 (service_2) -> 45.0 (service_3) -> 35.0 (service_0)
        assert neighborhoods[0]["normalized_pattern_key"] == "DEPENDENCY_PROXIMITY:service_1"
        assert neighborhoods[0]["fragility_score"] == 75.0
        assert neighborhoods[3]["normalized_pattern_key"] == "DEPENDENCY_PROXIMITY:service_0"
        assert neighborhoods[3]["fragility_score"] == 35.0
        print("[PASSED] Unstable neighborhoods validated.\n")

        # 8. Assert Churn patterns
        print("--- TEST 6: Validating High Churn Modules/Files ---")
        churn = summary["high_churn_modules"]
        assert len(churn) == 1
        assert churn[0]["title"] == "parser.py frequent failures"
        assert churn[0]["fragility_score"] == 78.0
        print("[PASSED] High churn modules/files validated.\n")

    finally:
        db.close()

    print("======================================================================")
    print("ALL VERISCOPE PHASE 7 FRAGILITY PILOT SUMMARY BUILDER TESTS PASSED!")
    print("======================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
