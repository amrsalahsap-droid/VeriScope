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
from app.models.pull_request import PullRequest
from app.models.recommendation import (
    RecommendationRun,
    RecommendationOutcome,
    RecommendationReasoningEntry,
    RecommendationOutcomeEvidence
)
from app.services.escaped_defect_linker import EscapedDefectLinker
from app.services.rollback_outcome_tracker import RollbackOutcomeTracker

def cleanup_database():
    """Clean up DB before and after testing."""
    db = SessionLocal()
    try:
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationOutcomeEvidence).delete()
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
    print("STARTING RECOMMENDATION OUTCOME IDEMPOTENCY VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # 1. Seeding basic structures
        org = Organization(id=org_id, name="Idempotency Labs", slug="idempotency-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=121212,
            name="idempotency-core",
            full_name="idempotency-labs/idempotency-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=600000,
            number=600,
            title="PR 600 - Idempotency Vulnerable Target",
            author="engineer-idempotency",
            source_branch="idempotency-dev",
            target_branch="main",
            state="open",
            additions=10,
            deletions=2,
            changed_files_count=1,
            head_commit_sha="pr_600_head",
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
            pr_id="pr_600_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1.2.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Idempotency test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        print("--- TEST 1: Double link_incident (Idempotent Incident linkage) ---")
        incident_data = {
            "id": "INC-IDEM-999",
            "severity": "P1",
            "timing": datetime.datetime.utcnow(),
            "affected_modules": ["auth/claims.py"]
        }
        root_cause_linkage = {
            "pull_request_id": pr_id,
            "confidence": "DIRECT"
        }

        # First Linkage
        outcome1 = EscapedDefectLinker.link_incident(
            db=db,
            incident_data=incident_data,
            root_cause_linkage=root_cause_linkage
        )
        assert outcome1 is not None

        # Verify initial reasoning entries and evidence count
        reasoning_count = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id,
            RecommendationReasoningEntry.reason_type == "escaped_defect_linkage"
        ).count()
        assert reasoning_count == 1

        evidence_count = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome1.id,
            RecommendationOutcomeEvidence.evidence_type == "INCIDENT"
        ).count()
        assert evidence_count == 1

        # Second Linkage (Duplicate Ingestion / Webhook retry)
        outcome2 = EscapedDefectLinker.link_incident(
            db=db,
            incident_data=incident_data,
            root_cause_linkage=root_cause_linkage
        )
        assert outcome2.id == outcome1.id

        # Verify reasoning entries and evidence are NOT duplicated!
        reasoning_count_post = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id,
            RecommendationReasoningEntry.reason_type == "escaped_defect_linkage"
        ).count()
        assert reasoning_count_post == 1, f"Expected 1 reasoning entry, found {reasoning_count_post}!"

        evidence_count_post = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome1.id,
            RecommendationOutcomeEvidence.evidence_type == "INCIDENT"
        ).count()
        assert evidence_count_post == 1, f"Expected 1 evidence entry, found {evidence_count_post}!"

        print("[PASSED] Incident double-linkage idempotency guard successfully prevented duplication!\n")

        print("--- TEST 2: Double track_rollback (Idempotent Rollback linkage) ---")
        rollback_data = {
            "id": "RLB-IDEM-888",
            "timing": datetime.datetime.utcnow(),
            "trigger_reason": "Memory leak on token expiration",
            "confidence": "DIRECT"
        }

        # First Linkage
        outcome_r1 = RollbackOutcomeTracker.track_rollback(
            db=db,
            rollback_data=rollback_data,
            pull_request_id=pr_id
        )
        assert outcome_r1 is not None

        # Verify initial reasoning and evidence count
        r_reasoning_count = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id,
            RecommendationReasoningEntry.reason_type == "rollback_linkage"
        ).count()
        assert r_reasoning_count == 1

        r_evidence_count = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome_r1.id,
            RecommendationOutcomeEvidence.evidence_type == "ROLLBACK"
        ).count()
        assert r_evidence_count == 1

        # Second Linkage (Duplicate / Webhook retry)
        outcome_r2 = RollbackOutcomeTracker.track_rollback(
            db=db,
            rollback_data=rollback_data,
            pull_request_id=pr_id
        )
        assert outcome_r2.id == outcome_r1.id

        # Verify reasoning and evidence are NOT duplicated
        r_reasoning_count_post = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id,
            RecommendationReasoningEntry.reason_type == "rollback_linkage"
        ).count()
        assert r_reasoning_count_post == 1, f"Expected 1 reasoning, found {r_reasoning_count_post}!"

        r_evidence_count_post = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome_r1.id,
            RecommendationOutcomeEvidence.evidence_type == "ROLLBACK"
        ).count()
        assert r_evidence_count_post == 1, f"Expected 1 evidence, found {r_evidence_count_post}!"

        print("[PASSED] Rollback double-linkage idempotency guard successfully prevented duplication!\n")

    finally:
        db.close()

    print("=======================================================")
    print("ALL RECOMMENDATION OUTCOME IDEMPOTENCY CHECKS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
