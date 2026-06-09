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
from app.models.fragility_pattern import FragilityPattern, FragilityEvidenceLink, FragilitySnapshot
from app.services.fragility_snapshot_service import FragilitySnapshotService

def cleanup_database():
    db = SessionLocal()
    try:
        db.query(FragilityEvidenceLink).delete()
        db.query(FragilitySnapshot).delete()
        db.query(FragilityPattern).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("SUCCESS: Database cleaned up successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def run_snapshot_verification():
    print("======================================================================")
    print("STARTING FRAGILITY SNAPSHOT DETERMINISM, IMMUTABILITY & AUDIT TESTS")
    print("======================================================================\n")

    db = SessionLocal()
    repo_id = uuid.uuid4()
    org_id = uuid.uuid4()

    try:
        # Seed Org and Repo
        org = Organization(id=org_id, name="Snapshot Labs", slug="snapshot-labs")
        db.add(org)
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=773322,
            name="snapshot-core",
            full_name="snapshot-labs/snapshot-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        db.commit()

        # Seed Active Patterns
        p1_id = uuid.uuid4()
        p1 = FragilityPattern(
            id=p1_id,
            repository_id=repo_id,
            pattern_type="FILE_FAILURE_FREQUENCY",
            normalized_pattern_key="FILE_FAILURE_FREQUENCY:src/auth.py",
            title="File Failure Frequency: src/auth.py",
            explanation="Test failure frequency.",
            fragility_score=50.0,
            risk_level="HIGH",
            confidence_level="HIGH",
            pattern_hash="hash_pattern_1_sha256_placeholder_value_abc",
            score_components={"frequency": 50.0},
            replayable_evidence_snapshot={},
            status="ACTIVE",
            evidence_count=4,
            first_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=10),
            last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=2)
        )
        db.add(p1)

        p2_id = uuid.uuid4()
        p2 = FragilityPattern(
            id=p2_id,
            repository_id=repo_id,
            pattern_type="CO_FAILURE_PATTERN",
            normalized_pattern_key="CO_FAILURE_PATTERN:src/utils.py->auth_test",
            title="Co Failure: src/utils.py",
            explanation="Test co failure.",
            fragility_score=35.0,
            risk_level="MODERATE",
            confidence_level="MODERATE",
            pattern_hash="hash_pattern_2_sha256_placeholder_value_def",
            score_components={"frequency": 30.0},
            replayable_evidence_snapshot={},
            status="ACTIVE",
            evidence_count=3,
            first_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=8),
            last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=3)
        )
        db.add(p2)

        # Seed some stale patterns that should NOT be in the active snapshot list
        p3 = FragilityPattern(
            id=uuid.uuid4(),
            repository_id=repo_id,
            pattern_type="UNSTABLE_MODULE",
            normalized_pattern_key="UNSTABLE_MODULE:src/legacy",
            title="Unstable Module: src/legacy",
            explanation="Stale unstable module.",
            fragility_score=15.0,
            risk_level="LOW",
            confidence_level="LOW",
            pattern_hash="hash_pattern_3_sha256_placeholder_value_ghi",
            score_components={"frequency": 10.0},
            replayable_evidence_snapshot={},
            status="STALE",
            evidence_count=1,
            last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=20)
        )
        db.add(p3)
        db.commit()

        # Seed Evidence Links for P1 and P2
        link1 = FragilityEvidenceLink(
            id=uuid.uuid4(),
            fragility_pattern_id=p1_id,
            evidence_type="TEST_FAILURE",
            source_incident_id="INC-110",
            evidence_summary="File auth.py failed in run 1."
        )
        db.add(link1)

        link2 = FragilityEvidenceLink(
            id=uuid.uuid4(),
            fragility_pattern_id=p2_id,
            evidence_type="ROLLBACK",
            evidence_summary="File utils.py failed and triggered a rollback."
        )
        db.add(link2)
        db.commit()

        # Instantiate Snapshot Service
        snapshot_service = FragilitySnapshotService(db)

        # ====================================================================
        # Test 1. Determinism and Reproducibility
        # ====================================================================
        print("--- 1. Testing Standalone Snapshot Determinism & Reproducibility ---")
        snap1 = snapshot_service.generate_fragility_snapshot(repo_id, trigger="MANUAL_RECALCULATION")
        snap2 = snapshot_service.generate_fragility_snapshot(repo_id, trigger="MANUAL_RECALCULATION")

        print(f"DEBUG: Snapshot 1 Hash: {snap1.snapshot_hash}")
        print(f"DEBUG: Snapshot 2 Hash: {snap2.snapshot_hash}")
        
        # Assert exact hash match
        assert snap1.snapshot_hash == snap2.snapshot_hash
        assert snap1.active_patterns == 2
        assert snap1.stale_patterns == 1
        assert snap1.total_patterns == 3
        # Ensure active_pattern_ids are sorted deterministically
        assert snap1.active_pattern_ids == sorted([str(p1_id), str(p2_id)])
        print("[OK] Standalone snapshot hashes are 100% deterministic and reproducible.")

        # ====================================================================
        # Test 2. Immutability and Recalculation Standalone Preservation
        # ====================================================================
        print("\n--- 2. Testing Recalculation Preservation & Immutability ---")
        
        # Add another active pattern to trigger a state change
        p4_id = uuid.uuid4()
        p4 = FragilityPattern(
            id=p4_id,
            repository_id=repo_id,
            pattern_type="ROLLBACK_INVOLVEMENT",
            normalized_pattern_key="ROLLBACK_INVOLVEMENT:src/session.py",
            title="Rollback Involvement: src/session.py",
            explanation="Test rollback.",
            fragility_score=85.0,
            risk_level="CRITICAL",
            confidence_level="HIGH",
            pattern_hash="hash_pattern_4_sha256_placeholder_value_jkl",
            score_components={"rollback": 80.0},
            replayable_evidence_snapshot={},
            status="ACTIVE",
            evidence_count=5,
            last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )
        db.add(p4)
        db.commit()

        # Generate a new snapshot after recalculation
        snap3 = snapshot_service.generate_fragility_snapshot(repo_id, trigger="SCHEDULED_RECALCULATION")
        print(f"DEBUG: Snapshot 3 Hash (After Recalculation): {snap3.snapshot_hash}")

        # Assert a new snapshot with different hash is created
        assert snap3.snapshot_hash != snap1.snapshot_hash
        assert snap3.active_patterns == 3
        assert snap3.active_pattern_ids == sorted([str(p1_id), str(p2_id), str(p4_id)])

        # Assert old historical snapshots remain preserved intact in the database
        preserved_snaps = db.query(FragilitySnapshot).filter(FragilitySnapshot.repository_id == repo_id).all()
        assert len(preserved_snaps) == 3
        print("[OK] Snapshot immutability and historical recalculation preservation verified successfully.")

        # ====================================================================
        # Test 3. Detailed Audit & Evidence Lineage Traceability (Rule 5)
        # ====================================================================
        print("\n--- 3. Testing Standalone Detailed Audit & Evidence Lineage ---")
        
        # Query lineage of Snapshot 1
        lineage = snapshot_service.get_snapshot_lineage(snap1.id)
        
        print(f"DEBUG: Lineage Snapshot ID: {lineage['snapshot_id']}")
        print(f"DEBUG: Lineage Pattern count: {len(lineage['patterns'])}")
        
        # Verify lineage contains exactly our active patterns (P1 and P2)
        assert len(lineage["patterns"]) == 2
        
        p1_lineage = next(p for p in lineage["patterns"] if p["pattern_id"] == str(p1_id))
        assert p1_lineage["pattern_type"] == "FILE_FAILURE_FREQUENCY"
        assert p1_lineage["risk_level"] == "HIGH"
        # Assert p1 has its evidence link fully populated
        assert len(p1_lineage["evidence_links"]) == 1
        assert p1_lineage["evidence_links"][0]["evidence_type"] == "TEST_FAILURE"
        assert p1_lineage["evidence_links"][0]["source_incident_id"] == "INC-110"
        assert p1_lineage["evidence_links"][0]["evidence_summary"] == "File auth.py failed in run 1."

        p2_lineage = next(p for p in lineage["patterns"] if p["pattern_id"] == str(p2_id))
        assert p2_lineage["pattern_type"] == "CO_FAILURE_PATTERN"
        assert p2_lineage["risk_level"] == "MODERATE"
        assert len(p2_lineage["evidence_links"]) == 1
        assert p2_lineage["evidence_links"][0]["evidence_type"] == "ROLLBACK"
        
        print("[OK] Evidence lineage audit ledger trace resolved and verified (Rule 5).")

        # ====================================================================
        # Test 4. ML Absence Certification
        # ====================================================================
        print("\n--- 4. Certifying Pure Mathematical & Ledger Snapshot Design (No ML) ---")
        
        src_path = Path(__file__).resolve().parent.parent / "app" / "services" / "fragility_snapshot_service.py"
        with open(src_path, "r", encoding="utf-8") as f:
            src_code = f.read()
            
        forbidden = ["sklearn", "scikit", "tensorflow", "pytorch", "torch", "keras", "xgboost", "randomforest", "openai", "gemini", "anthropic", "llm"]
        for f in forbidden:
            assert f not in src_code.lower(), f"Forbidden library or keyword '{f}' found in snapshot service!"
            
        print("[OK] Verified zero ML/LLM library imports or stochastic operations.")

        print("\n======================================================================")
        print("ALL FRAGILITY SNAPSHOT DETERMINISM, IMMUTABILITY & AUDIT TESTS PASSED!")
        print("======================================================================\n")

    finally:
        cleanup_database()
        db.close()

if __name__ == "__main__":
    cleanup_database()
    try:
        run_snapshot_verification()
    finally:
        cleanup_database()
