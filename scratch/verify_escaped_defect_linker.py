import os
import sys
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationReasoningEntry
)
from app.services.escaped_defect_linker import EscapedDefectLinker

def cleanup_database():
    """Clean up DB before and after testing."""
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationRun).delete()
        db.query(PullRequest).delete()
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
    print("STARTING ESCAPED DEFECT LINKER FORENSIC AUDIT VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # 1. Seeding basic structures
        org = Organization(id=org_id, name="Forensic Labs Inc", slug="forensic-labs-inc")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=989898,
            name="forensic-core",
            full_name="forensic-labs-inc/forensic-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=500000,
            number=500,
            title="PR 500 - Vulnerable Patch",
            author="engineer-leak",
            source_branch="leak-patch",
            target_branch="main",
            state="open",
            additions=12,
            deletions=3,
            changed_files_count=1,
            head_commit_sha="pr_500",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.commit()

        # Seed RecommendationRun
        run = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_500",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Linker test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Baseline check: no outcome initially, but EscapedDefectLinker should instantiate one or find existing placeholder
        print("--- TEST 1: Linking P0 Incident (Direct Confidence) ---")
        incident_data = {
            "id": "INC-P0-101",
            "severity": "P0",
            "timing": datetime.datetime.utcnow(),
            "affected_modules": ["auth/jwt.py", "core/encryption.py"]
        }
        root_cause_linkage = {
            "pull_request_id": pr_id,
            "confidence": "DIRECT"
        }
        rollback_record = {
            "id": "RLB-101",
            "rolled_back_at": datetime.datetime.utcnow()
        }
        deployment_outcome = {
            "id": "DEP-101",
            "deployed_at": datetime.datetime.utcnow() - datetime.timedelta(hours=1),
            "status": "SUCCESS"
        }

        outcome = EscapedDefectLinker.link_incident(
            db=db,
            incident_data=incident_data,
            root_cause_linkage=root_cause_linkage,
            rollback_record=rollback_record,
            deployment_outcome=deployment_outcome
        )

        assert outcome is not None
        assert outcome.outcome_status == "ESCAPED_DEFECT_LINKED"
        assert outcome.escaped_defect_detected is True
        assert outcome.rollback_occurred is True
        assert "INC-P0-101" in outcome.engineer_feedback
        assert "auth/jwt.py" in outcome.engineer_feedback

        # Verify the persisted forensic reasoning entry
        reasoning = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id,
            RecommendationReasoningEntry.reason_type == "escaped_defect_linkage"
        ).first()

        assert reasoning is not None
        assert reasoning.confidence_level == "DIRECT"
        assert reasoning.source_entity == "INC-P0-101"
        assert reasoning.reasoning_metadata["incident_severity"] == "P0"
        assert reasoning.reasoning_metadata["linkage_confidence"] == "DIRECT"
        # Rule 3: Never auto-claim causality
        assert reasoning.reasoning_metadata["causality_asserted"] is False
        assert "causality NOT auto-claimed" in reasoning.human_readable_reason

        print("[PASSED] Direct linkage asserted successfully.\n")

        print("--- TEST 2: Linking P1 Incident (Inferred Confidence) ---")
        # Reuse existing run and update outcome to a P1 inferred defect
        incident_data_p1 = {
            "id": "INC-P1-202",
            "severity": "P1",
            "timing": datetime.datetime.utcnow(),
            "affected_modules": ["auth/jwt.py"]
        }
        root_cause_linkage_p1 = {
            "github_pr_number": 500,
            "confidence": "INFERRED"
        }

        outcome_p1 = EscapedDefectLinker.link_incident(
            db=db,
            incident_data=incident_data_p1,
            root_cause_linkage=root_cause_linkage_p1
        )

        assert outcome_p1 is not None
        assert outcome_p1.outcome_status == "ESCAPED_DEFECT_LINKED"
        assert outcome_p1.escaped_defect_detected is True
        assert "INC-P1-202" in outcome_p1.engineer_feedback

        reasonings = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id,
            RecommendationReasoningEntry.reason_type == "escaped_defect_linkage"
        ).all()
        # Should have 2 entries now
        assert len(reasonings) == 2
        inferred_reasoning = next(r for r in reasonings if r.source_entity == "INC-P1-202")
        assert inferred_reasoning.confidence_level == "INFERRED"
        assert inferred_reasoning.reasoning_metadata["causality_asserted"] is False

        print("[PASSED] Inferred linkage asserted successfully.\n")

        print("--- TEST 3: Deterministic Lineage Verification Exception ---")
        # Try linking with non-existent PR ID or PR number to check exception raising
        root_cause_linkage_invalid = {
            "github_pr_number": 99999, # invalid PR number
            "confidence": "DIRECT"
        }
        try:
            EscapedDefectLinker.link_incident(
                db=db,
                incident_data=incident_data,
                root_cause_linkage=root_cause_linkage_invalid
            )
            assert False, "Should have thrown ValueError for missing PR deterministic lineage!"
        except ValueError as e:
            assert "Lineage resolution failed" in str(e)
            print("[PASSED] Deterministic lineage resolution correctly raised ValueError as expected.")

    finally:
        db.close()

    print("\n=======================================================")
    print("ALL ESCAPED DEFECT LINKER VERIFICATION CHECKS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
