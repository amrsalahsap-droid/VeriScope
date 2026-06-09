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
    RecommendationTest,
    RecommendationReasoningEntry,
    RecommendationOutcomeEvidence,
    RecommendationEngineerFeedback
)
from app.services.recommendation_engineer_feedback_capture import RecommendationEngineerFeedbackCapture
from app.services.escaped_defect_linker import EscapedDefectLinker
from app.services.rollback_outcome_tracker import RollbackOutcomeTracker
from app.services.recommendation_outcome_evidence_integrity import RecommendationOutcomeEvidenceIntegrity

def cleanup_database():
    """Clean up DB before and after testing."""
    from app.db.base import Base
    from app.db.session import engine
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
        
    db = SessionLocal()
    try:
        try:
            db.query(RecommendationOutcomeEvidence).delete()
        except Exception:
            db.rollback()
        db.query(RecommendationEngineerFeedback).delete()
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationTest).delete()
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
    print("STARTING RECOMMENDATION OUTCOME EVIDENCE INTEGRITY AUDIT VERIFICATION")
    print("======================================================================\n")

    from app.db.base import Base
    from app.db.session import engine
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()

    try:
        # 1. Seeding basic structures
        org = Organization(id=org_id, name="Integrity Lab Systems", slug="integrity-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=989898,
            name="integrity-core",
            full_name="integrity-labs/integrity-core",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=900000,
            number=900,
            title="PR 900 - Integrity Verification",
            author="integrity-auditor",
            source_branch="integrity-dev",
            target_branch="main",
            state="open",
            additions=50,
            deletions=10,
            changed_files_count=1,
            head_commit_sha="pr_900_head",
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
            pr_id="pr_900_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Integrity audit test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Seed some recommended tests
        for i in range(5):
            rec_test = RecommendationTest(
                recommendation_run_id=run.id,
                test_case_id=f"test_integrity_{i}",
                reason_type="historical_fragility",
                reason_details={},
                priority_score=0.8
            )
            db.add(rec_test)
        db.commit()

        # Create basic outcome
        outcome = RecommendationOutcome(
            recommendation_run_id=run.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=str(run.id),
            outcome_status="PENDING",
            was_followed_legacy=True
        )
        db.add(outcome)
        db.commit()
        db.refresh(outcome)

        print("--- TEST 1: RecommendationReasoningEntry Append-Only Immutability ---")
        reasoning = RecommendationReasoningEntry(
            id=uuid.uuid4(),
            recommendation_run_id=run.id,
            reason_type="outcome_classification",
            source_entity=str(outcome.id),
            source_reference="PENDING",
            human_readable_reason="Initial state.",
            confidence_level="HIGH",
            evidence_priority="CRITICAL",
            created_at=datetime.datetime.utcnow()
        )
        db.add(reasoning)
        db.commit()
        
        # Try mutating the reasoning entry
        reasoning.human_readable_reason = "Mutated state."
        try:
            db.commit()
            assert False, "Mutation should have raised a RuntimeError!"
        except Exception as e:
            db.rollback()
            assert "Forensic Immutability Violation" in str(e)
            print("[PASSED] Mutation block raised RuntimeError successfully.")

        # Try deleting the reasoning entry
        try:
            db.delete(reasoning)
            db.commit()
            assert False, "Deletion should have raised a RuntimeError!"
        except Exception as e:
            db.rollback()
            assert "Forensic Immutability Violation" in str(e)
            print("[PASSED] Deletion block raised RuntimeError successfully.\n")

        print("--- TEST 2: RecommendationOutcomeEvidence Append-Only Immutability ---")
        evidence = RecommendationOutcomeEvidence(
            id=uuid.uuid4(),
            recommendation_outcome_id=outcome.id,
            evidence_type="TEST_RUN",
            source_reference_id="test_run_123",
            evidence_payload={"foo": "bar"},
            evidence_fingerprint="some_fingerprint",
            created_at=datetime.datetime.utcnow()
        )
        db.add(evidence)
        db.commit()

        # Try mutating the evidence record
        evidence.evidence_payload = {"foo": "mutated"}
        try:
            db.commit()
            assert False, "Evidence mutation should have raised a RuntimeError!"
        except Exception as e:
            db.rollback()
            assert "Forensic Immutability Violation" in str(e)
            print("[PASSED] Evidence mutation block raised RuntimeError successfully.")

        # Try deleting the evidence record
        try:
            db.delete(evidence)
            db.commit()
            assert False, "Evidence deletion should have raised a RuntimeError!"
        except Exception as e:
            db.rollback()
            assert "Forensic Immutability Violation" in str(e)
            print("[PASSED] Evidence deletion block raised RuntimeError successfully.\n")

        print("--- TEST 3: Automated Pipeline Hook and Evidence Logging ---")
        # 1. Trigger Feedback Capture and check if FEEDBACK evidence is logged
        db.expire_all()
        feedback_rec = RecommendationEngineerFeedbackCapture.capture_feedback(
            db=db,
            recommendation_run_id=run.id,
            feedback_type="MISSING_TESTS",
            feedback_text="Uncovered new branch",
            created_by="auditor-1"
        )
        
        db.expire_all()
        # Verify FEEDBACK evidence exists
        ev_feedback = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome.id,
            RecommendationOutcomeEvidence.evidence_type == "FEEDBACK"
        ).first()
        
        assert ev_feedback is not None
        assert ev_feedback.evidence_payload["feedback_type"] == "MISSING_TESTS"
        assert ev_feedback.evidence_payload["feedback_text"] == "Uncovered new branch"
        assert ev_feedback.evidence_payload["created_by"] == "auditor-1"
        assert ev_feedback.source_reference_id == str(feedback_rec.id)
        print("[PASSED] Feedback capture service evidence auto-logged successfully.")

        # 2. Trigger Escaped Defect Linker and check if INCIDENT evidence is logged
        db.expire_all()
        incident_data = {
            "id": "inc_900_escaped",
            "severity": "P1",
            "timing": datetime.datetime.utcnow(),
            "affected_modules": ["auth/middleware.py"]
        }
        root_cause = {
            "pull_request_id": pr_id,
            "confidence": "DIRECT"
        }
        
        outcome = EscapedDefectLinker.link_incident(
            db=db,
            incident_data=incident_data,
            root_cause_linkage=root_cause
        )
        
        db.expire_all()
        ev_incident = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome.id,
            RecommendationOutcomeEvidence.evidence_type == "INCIDENT"
        ).first()
        
        assert ev_incident is not None
        assert ev_incident.evidence_payload["incident_data"]["severity"] == "P1"
        assert ev_incident.source_reference_id == "inc_900_escaped"
        print("[PASSED] Escaped defect linker evidence auto-logged successfully.")

        # 3. Trigger Rollback Outcome Tracker and check if ROLLBACK evidence is logged
        db.expire_all()
        rollback_data = {
            "id": "roll_900",
            "trigger_reason": "High error rate",
            "confidence": "DIRECT",
            "timing": datetime.datetime.utcnow()
        }
        outcome = RollbackOutcomeTracker.track_rollback(
            db=db,
            rollback_data=rollback_data,
            pull_request_id=pr_id
        )
        
        db.expire_all()
        ev_rollback = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome.id,
            RecommendationOutcomeEvidence.evidence_type == "ROLLBACK"
        ).first()
        
        assert ev_rollback is not None
        assert ev_rollback.evidence_payload["rollback_data"]["trigger_reason"] == "High error rate"
        assert ev_rollback.source_reference_id == "roll_900"
        print("[PASSED] Rollback outcome tracker evidence auto-logged successfully.\n")

        print("--- TEST 4: Deterministic Chronological Replay ---")
        # Now we run replay_and_verify on the outcome
        db.expire_all()
        
        # Clean up any leftover manual test evidence to have pure pipeline replay
        db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome.id,
            RecommendationOutcomeEvidence.source_reference_id == "test_run_123"
        ).delete()
        db.commit()
        
        report = RecommendationOutcomeEvidenceIntegrity.replay_and_verify(db, outcome.id)
        assert report["drift_detected"] is False
        assert report["reconstructed_rollback_occurred"] is True
        assert report["reconstructed_escaped_defect_detected"] is True
        assert report["replayed_outcome_status"] == "ROLLBACK_LINKED"
        print("[PASSED] Chronological evidence replay verified deterministic and correct.\n")

        print("--- TEST 5: Active Historical Drift Detection ---")
        # Simulate unauthorized update to database status directly (drift!)
        outcome = db.query(RecommendationOutcome).filter(RecommendationOutcome.id == outcome.id).first()
        # Direct session edit to bypass normal checks
        db.execute(
            RecommendationOutcome.__table__.update()
            .where(RecommendationOutcome.id == outcome.id)
            .values(outcome_status="PARTIALLY_FOLLOWED")
        )
        db.commit()
        db.expire_all()
        
        outcome_edited = db.query(RecommendationOutcome).filter(RecommendationOutcome.id == outcome.id).first()
        assert outcome_edited.outcome_status == "PARTIALLY_FOLLOWED"
        
        # Re-run verification: it MUST raise a ValueError detecting the drift!
        try:
            RecommendationOutcomeEvidenceIntegrity.replay_and_verify(db, outcome.id)
            assert False, "Verification should have failed due to drift!"
        except ValueError as e:
            assert "Historical Drift Detected" in str(e)
            print("[PASSED] Historical drift successfully detected and exception raised.")

    finally:
        db.close()

    print("\n==================================================================")
    print("ALL RECOMMENDATION OUTCOME EVIDENCE INTEGRITY AUDITS PASSED!")
    print("==================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_verification()
    finally:
        cleanup_database()
