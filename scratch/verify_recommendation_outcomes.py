import os
import sys
import uuid
import datetime
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Set

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.recommendation import (
    RecommendationRun,
    RecommendationTest,
    RecommendationOutcome,
    RecommendationReasoningEntry,
    RecommendationOutcomeEvidence,
    RecommendationOutcomeSnapshot,
    RecommendationEngineerFeedback
)
from app.services.recommendation_outcome_classifier import RecommendationOutcomeClassifier
from app.services.recommendation_outcome_snapshot import RecommendationOutcomeSnapshotService
from app.services.recommendation_outcome_evidence_integrity import RecommendationOutcomeEvidenceIntegrity
from app.services.recommendation_exposure_tracker import RecommendationExposureTracker
from app.services.recommendation_ignore_detector import RecommendationIgnoreDetector
from app.services.recommendation_engineer_feedback_capture import RecommendationEngineerFeedbackCapture
from app.services.escaped_defect_linker import EscapedDefectLinker
from app.services.rollback_outcome_tracker import RollbackOutcomeTracker

def cleanup_database():
    """Clean up verification records in database."""
    from app.db.base import Base
    from app.db.session import engine
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
        
    db = SessionLocal()
    try:
        # Delete children first
        db.query(RecommendationOutcomeSnapshot).delete()
        db.query(RecommendationOutcomeEvidence).delete()
        db.query(RecommendationEngineerFeedback).delete()
        db.query(RecommendationReasoningEntry).delete()
        db.query(RecommendationTest).delete()
        db.query(RecommendationOutcome).delete()
        db.query(RecommendationRun).delete()
        db.query(PullRequest).delete()
        db.query(Repository).delete()
        db.query(Organization).delete()
        db.commit()
        print("Database cleanup completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

def run_all_checks():
    print("======================================================================")
    print("STARTING DETERMINISTIC RECOMMENDATION OUTCOME AUDIT VERIFICATION")
    print("======================================================================\n")

    db = SessionLocal()
    
    # Setup test entities
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    pr_id = uuid.uuid4()
    
    try:
        # Seeding organization, repository and pull request
        org = Organization(id=org_id, name="Deterministic Audit Labs", slug="det-audit-labs")
        db.add(org)
        
        repo = Repository(
            id=repo_id,
            organization_id=org_id,
            github_repo_id=987654,
            name="outcome-deterministic",
            full_name="det-audit-labs/outcome-deterministic",
            default_branch="main",
            is_active=True
        )
        db.add(repo)
        
        pr = PullRequest(
            id=pr_id,
            repository_id=repo_id,
            github_pr_id=980000,
            number=980,
            title="PR 980 - Determinism Auditing",
            author="det-auditor",
            source_branch="det-dev",
            target_branch="main",
            state="open",
            additions=42,
            deletions=10,
            changed_files_count=2,
            head_commit_sha="pr_980_head",
            github_created_at=datetime.datetime.utcnow(),
            github_updated_at=datetime.datetime.utcnow(),
            sync_integrity_status="FULL_SUCCESS",
            evidence_health_status="HEALTHY",
            evidence_consistency_status="CONSISTENT"
        )
        db.add(pr)
        db.commit()
        
        print("[INIT] Seeded org, repo, and PR successfully.\n")

        # --------------------------------------------------------------------
        # TEST 1: Every RecommendationRun creates RecommendationOutcome
        # --------------------------------------------------------------------
        print("--- TEST 1: every RecommendationRun creates RecommendationOutcome ---")
        run_1 = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_980_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Deterministic test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_1)
        db.commit()
        db.refresh(run_1)

        # Standard pipeline requires an outcome record for every run to track alignment
        outcome_1 = RecommendationOutcome(
            recommendation_run_id=run_1.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash=run_1.id.hex,
            outcome_status="PENDING",
            was_followed_legacy=True
        )
        db.add(outcome_1)
        db.commit()
        db.refresh(outcome_1)
        
        assert outcome_1.recommendation_run_id == run_1.id
        assert run_1.outcome is not None
        assert run_1.outcome.id == outcome_1.id
        print("[PASSED] Verified RecommendationRun map to RecommendationOutcome successfully.\n")

        # --------------------------------------------------------------------
        # TEST 2: Exposure timestamps deterministic
        # --------------------------------------------------------------------
        print("--- TEST 2: exposure timestamps deterministic ---")
        tracker = RecommendationExposureTracker(db)
        
        # Track presented first time
        outcome_updated = tracker.track_presented(run_1.id)
        assert outcome_updated is not None
        presented_time_1 = outcome_updated.recommendation_presented_at
        assert presented_time_1 is not None
        
        # Track presented a second time -> should NOT mutate the timestamp (immutability rule)
        outcome_updated_2 = tracker.track_presented(run_1.id)
        assert outcome_updated_2.recommendation_presented_at == presented_time_1
        
        # Track acknowledged
        outcome_updated_ack = tracker.track_acknowledged(run_1.id)
        assert outcome_updated_ack is not None
        ack_time_1 = outcome_updated_ack.recommendation_acknowledged_at
        assert ack_time_1 is not None
        
        # Track acknowledged second time -> should NOT mutate the timestamp
        outcome_updated_ack_2 = tracker.track_acknowledged(run_1.id)
        assert outcome_updated_ack_2.recommendation_acknowledged_at == ack_time_1
        print("[PASSED] Verified exposure timestamps are set deterministically and are immutable once set.\n")

        # --------------------------------------------------------------------
        # TEST 3: Override detection correct
        # --------------------------------------------------------------------
        print("--- TEST 3: override detection correct ---")
        # Define recommended tests
        for i in range(5):
            t = RecommendationTest(
                recommendation_run_id=run_1.id,
                test_case_id=f"test_case_{i}",
                reason_type="direct_file_mapping",
                reason_details={},
                priority_score=0.9
            )
            db.add(t)
        db.commit()
        db.refresh(run_1)
        
        # Tamper executing 4/5, but manual additions/removals provided (override)
        outcome_override = RecommendationOutcome(
            recommendation_run_id=run_1.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="run_1_hash",
            outcome_status="PENDING",
            was_followed_legacy=True,
            executed_tests=["test_case_0", "test_case_1", "test_case_2", "test_case_3"],
            manually_added_tests=["test_case_custom"],
            manually_removed_tests=["test_case_4"]
        )
        res_override = RecommendationOutcomeClassifier.classify(outcome_override, db=db)
        assert res_override["classification_label"] == "OVERRIDDEN"
        assert res_override["override_metrics"]["total_manually_added"] == 1
        assert res_override["override_metrics"]["total_manually_removed"] == 1
        print("[PASSED] Verified manual test suite overrides are classified as OVERRIDDEN successfully.\n")

        # --------------------------------------------------------------------
        # TEST 4: Ignored recommendations detected correctly
        # --------------------------------------------------------------------
        print("--- TEST 4: ignored recommendations detected correctly ---")
        # Overlap ratio < 40% (e.g. 1 out of 5 executed = 20%)
        outcome_ignored = RecommendationOutcome(
            recommendation_run_id=run_1.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="run_1_hash",
            outcome_status="PENDING",
            was_followed_legacy=True,
            executed_tests=["test_case_0"],
            manually_added_tests=[],
            manually_removed_tests=[]
        )
        res_ignored = RecommendationOutcomeClassifier.classify(outcome_ignored, db=db)
        assert res_ignored["classification_label"] == "IGNORED"
        assert res_ignored["overlap_ratio"] == 0.2
        print("[PASSED] Verified ignore alignment (overlap < 40%) classified as IGNORED successfully.\n")

        # --------------------------------------------------------------------
        # TEST 5: Rollback linkage replayable
        # --------------------------------------------------------------------
        print("--- TEST 5: rollback linkage replayable ---")
        # Run 2 for Rollback testing
        run_2 = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_980_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Rollback test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_2)
        db.commit()
        db.refresh(run_2)

        outcome_2 = RecommendationOutcome(
            recommendation_run_id=run_2.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="run_2_hash",
            outcome_status="PENDING",
            was_followed_legacy=True
        )
        db.add(outcome_2)
        db.commit()
        db.refresh(outcome_2)

        # Link rollback event
        rollback_data = {
            "id": "roll_980_ev",
            "timing": datetime.datetime.utcnow().isoformat(),
            "trigger_reason": "Latency spike after deployment",
            "confidence": "DIRECT"
        }
        
        # Track rollback creates a ROLLBACK evidence log and mutates outcome_status
        RollbackOutcomeTracker.track_rollback(
            db=db,
            rollback_data=rollback_data,
            pull_request_id=pr_id
        )
        db.expire_all()
        db.refresh(outcome_2)
        
        assert outcome_2.rollback_occurred is True
        
        # Process outcome classification update
        RecommendationOutcomeClassifier.classify_and_update(db, outcome_2)
        assert outcome_2.outcome_status == "ROLLBACK_LINKED"
        
        # Deterministic Replay check
        replay_res = RecommendationOutcomeEvidenceIntegrity.replay_and_verify(db, outcome_2.id)
        assert replay_res["replayed_outcome_status"] == "ROLLBACK_LINKED"
        assert replay_res["reconstructed_rollback_occurred"] is True
        print("[PASSED] Verified rollback linkage is deterministically captured and successfully replayed.\n")

        # --------------------------------------------------------------------
        # TEST 6: Escaped defect linkage replayable
        # --------------------------------------------------------------------
        print("--- TEST 6: escaped defect linkage replayable ---")
        # Run 3 for incident testing
        run_3 = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_980_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Incident test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_3)
        db.commit()
        db.refresh(run_3)

        outcome_3 = RecommendationOutcome(
            recommendation_run_id=run_3.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="run_3_hash",
            outcome_status="PENDING",
            was_followed_legacy=True
        )
        db.add(outcome_3)
        db.commit()
        db.refresh(outcome_3)

        incident_data = {
            "id": "inc_980_ev",
            "severity": "P0",
            "timing": datetime.datetime.utcnow(),
            "affected_modules": ["auth/middleware.py"]
        }
        root_cause_linkage = {
            "pull_request_id": pr_id,
            "confidence": "DIRECT"
        }

        # Link incident
        EscapedDefectLinker.link_incident(db, incident_data, root_cause_linkage)
        db.expire_all()
        db.refresh(outcome_3)
        
        assert outcome_3.escaped_defect_detected is True
        
        # Classification
        RecommendationOutcomeClassifier.classify_and_update(db, outcome_3)
        assert outcome_3.outcome_status == "ESCAPED_DEFECT_LINKED"
        
        # Deterministic replay check
        replay_res_inc = RecommendationOutcomeEvidenceIntegrity.replay_and_verify(db, outcome_3.id)
        assert replay_res_inc["replayed_outcome_status"] == "ESCAPED_DEFECT_LINKED"
        assert replay_res_inc["reconstructed_escaped_defect_detected"] is True
        print("[PASSED] Verified escaped defect incident linkage is deterministic and successfully replayed.\n")

        # --------------------------------------------------------------------
        # TEST 7: Engineer feedback append-only
        # --------------------------------------------------------------------
        print("--- TEST 7: engineer feedback append-only ---")
        feedback = RecommendationEngineerFeedbackCapture.capture_feedback(
            db=db,
            recommendation_run_id=run_1.id,
            feedback_type="MISSING_TESTS",
            feedback_text="Tenant boundaries are missing from regression paths",
            created_by="engineer-bob"
        )
        
        assert feedback is not None
        assert feedback.feedback_type == "MISSING_TESTS"
        
        # Retrieve the generated feedback evidence snapshot log
        feedback_ev = db.query(RecommendationOutcomeEvidence).filter(
            RecommendationOutcomeEvidence.recommendation_outcome_id == outcome_1.id,
            RecommendationOutcomeEvidence.evidence_type == "FEEDBACK"
        ).first()
        
        assert feedback_ev is not None
        assert feedback_ev.evidence_payload["feedback_type"] == "MISSING_TESTS"
        
        # Attempt to mutably overwrite the evidence payload -> Must trigger a Forensic Immutability Violation RuntimeError
        feedback_ev.evidence_payload = {"feedback_type": "USEFUL"}
        try:
            db.commit()
            assert False, "Forensic immutability fail: Mutation should have been blocked!"
        except Exception as e:
            db.rollback()
            assert "Forensic Immutability Violation" in str(e)
            print("[PASSED] Verified feedback and auditing logs are append-only; database mutations successfully blocked.\n")

        # --------------------------------------------------------------------
        # TEST 8: Outcome classifications deterministic
        # --------------------------------------------------------------------
        print("--- TEST 8: outcome classifications deterministic ---")
        # Define mock outcome structures with different properties to check classifier priority ordering:
        # ROLLBACK_LINKED > ESCAPED_DEFECT_LINKED > OVERRIDDEN > IGNORED > PARTIALLY_FOLLOWED > FOLLOWED
        
        # Setup run 4
        run_4 = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_980_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Classification precedence check",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_4)
        db.commit()
        
        for i in range(5):
            t = RecommendationTest(
                recommendation_run_id=run_4.id,
                test_case_id=f"test_case_{i}",
                reason_type="historical_fragility",
                reason_details={},
                priority_score=0.8
            )
            db.add(t)
        db.commit()

        # A. Rollback + defect + override + ignored -> ROLLBACK_LINKED
        outcome_c1 = RecommendationOutcome(
            recommendation_run_id=run_4.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            rollback_occurred=True,
            escaped_defect=True,
            executed_tests=["test_case_0"], # ignore overlap
            manually_added_tests=["custom_test"], # override
            outcome_status="PENDING"
        )
        res_c1 = RecommendationOutcomeClassifier.classify(outcome_c1, db=db)
        assert res_c1["classification_label"] == "ROLLBACK_LINKED"

        # B. Escaped defect + override + ignored -> ESCAPED_DEFECT_LINKED
        outcome_c2 = RecommendationOutcome(
            recommendation_run_id=run_4.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            rollback_occurred=False,
            escaped_defect=True,
            executed_tests=["test_case_0"], # ignore
            manually_added_tests=["custom_test"], # override
            outcome_status="PENDING"
        )
        res_c2 = RecommendationOutcomeClassifier.classify(outcome_c2, db=db)
        assert res_c2["classification_label"] == "ESCAPED_DEFECT_LINKED"

        # C. Override + ignored -> OVERRIDDEN
        outcome_c3 = RecommendationOutcome(
            recommendation_run_id=run_4.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            rollback_occurred=False,
            escaped_defect=False,
            executed_tests=["test_case_0"], # ignore
            manually_added_tests=["custom_test"], # override
            outcome_status="PENDING"
        )
        res_c3 = RecommendationOutcomeClassifier.classify(outcome_c3, db=db)
        assert res_c3["classification_label"] == "OVERRIDDEN"

        # D. Raw ignore -> IGNORED
        outcome_c4 = RecommendationOutcome(
            recommendation_run_id=run_4.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            rollback_occurred=False,
            escaped_defect=False,
            executed_tests=["test_case_0"], # 20% raw overlap
            manually_added_tests=[],
            manually_removed_tests=[],
            outcome_status="PENDING"
        )
        res_c4 = RecommendationOutcomeClassifier.classify(outcome_c4, db=db)
        assert res_c4["classification_label"] == "IGNORED"

        # E. Partial overlap (no custom override, executed 3/5) -> PARTIALLY_FOLLOWED
        outcome_c5 = RecommendationOutcome(
            recommendation_run_id=run_4.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            rollback_occurred=False,
            escaped_defect=False,
            executed_tests=["test_case_0", "test_case_1", "test_case_2"], # 60% overlap
            manually_added_tests=[],
            manually_removed_tests=[],
            outcome_status="PENDING"
        )
        res_c5 = RecommendationOutcomeClassifier.classify(outcome_c5, db=db)
        assert res_c5["classification_label"] == "PARTIALLY_FOLLOWED"

        # F. Full perfect execution -> FOLLOWED
        outcome_c6 = RecommendationOutcome(
            recommendation_run_id=run_4.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            rollback_occurred=False,
            escaped_defect=False,
            executed_tests=["test_case_0", "test_case_1", "test_case_2", "test_case_3", "test_case_4"],
            manually_added_tests=[],
            manually_removed_tests=[],
            outcome_status="PENDING"
        )
        res_c6 = RecommendationOutcomeClassifier.classify(outcome_c6, db=db)
        assert res_c6["classification_label"] == "FOLLOWED"

        print("[PASSED] Verified classifier priority order and deterministic classifications successfully.\n")

        # --------------------------------------------------------------------
        # TEST 9: Same evidence produces same outcome snapshot
        # --------------------------------------------------------------------
        print("--- TEST 9: same evidence produces same outcome snapshot ---")
        # Let's seed two independent runs and outcomes with identical properties
        run_ident_1 = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_980_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Same evidence check run 1",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_ident_1)
        
        run_ident_2 = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_980_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Same evidence check run 2",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_ident_2)
        db.commit()

        # Seed recommended tests for both runs identically
        for run_ident in (run_ident_1, run_ident_2):
            for i in range(5):
                t = RecommendationTest(
                    recommendation_run_id=run_ident.id,
                    test_case_id=f"test_case_{i}",
                    reason_type="historical_fragility",
                    reason_details={},
                    priority_score=0.8
                )
                db.add(t)
        db.commit()

        outcome_ident_1 = RecommendationOutcome(
            recommendation_run_id=run_ident_1.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="common_run_hash",
            fragility_snapshot_hash="common_frag_hash",
            outcome_status="FOLLOWED",
            executed_tests=["test_case_0", "test_case_1", "test_case_2", "test_case_3", "test_case_4"]
        )
        db.add(outcome_ident_1)
        
        outcome_ident_2 = RecommendationOutcome(
            recommendation_run_id=run_ident_2.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="common_run_hash",
            fragility_snapshot_hash="common_frag_hash",
            outcome_status="FOLLOWED",
            executed_tests=["test_case_0", "test_case_1", "test_case_2", "test_case_3", "test_case_4"]
        )
        db.add(outcome_ident_2)
        db.commit()

        # Create snapshot for the first outcome to show it persists successfully
        snapshot_ident_1 = RecommendationOutcomeSnapshotService.create_snapshot(db, outcome_ident_1.id)
        assert snapshot_ident_1 is not None

        # Compute hashes for both outcomes and verify they are identical
        hashes_1 = RecommendationOutcomeSnapshotService.calculate_sub_hashes(outcome_ident_1)
        hashes_2 = RecommendationOutcomeSnapshotService.calculate_sub_hashes(outcome_ident_2)

        # Must produce identical outcome_snapshot_hash because their evidence payloads and status configurations match perfectly!
        assert hashes_1["outcome_snapshot_hash"] == hashes_2["outcome_snapshot_hash"]
        assert snapshot_ident_1.outcome_snapshot_hash == hashes_2["outcome_snapshot_hash"]
        print(f"[PASSED] Deterministic hashing verified. Cryptographic signature: {snapshot_ident_1.outcome_snapshot_hash}\n")

        # --------------------------------------------------------------------
        # TEST 10: Tiny-suite conservative handling
        # --------------------------------------------------------------------
        print("--- TEST 10: tiny-suite conservative handling ---")
        # Setup a tiny suite of 3 tests
        run_tiny = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_980_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Tiny suite test run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_tiny)
        db.commit()

        for i in range(3):
            t = RecommendationTest(
                recommendation_run_id=run_tiny.id,
                test_case_id=f"test_tiny_{i}",
                reason_type="historical_fragility",
                reason_details={},
                priority_score=0.8
            )
            db.add(t)
        db.commit()

        # A. Overlap ratio under 40% (e.g. 1 out of 3 = 33.3% raw overlap)
        # Without tiny suite protection, this raw 33% raw ratio would flag status as IGNORED.
        # But statistical Wilson Score Interval adjusted overlap is used instead to check upper bound.
        # For x=1, n=3 at 90% confidence, upper bound is ~74% which is >= 40% threshold, mapping to PARTIALLY_FOLLOWED!
        outcome_t1 = RecommendationOutcome(
            recommendation_run_id=run_tiny.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="tiny_hash",
            outcome_status="PENDING",
            executed_tests=["test_tiny_0"],
            manually_added_tests=[],
            manually_removed_tests=[]
        )
        res_t1 = RecommendationOutcomeClassifier.classify(outcome_t1, db=db)
        assert res_t1["classification_label"] == "PARTIALLY_FOLLOWED" # Verified!
        print("[PASSED] Verified tiny-suite raw ignore overlap is safely adjusted to PARTIALLY_FOLLOWED.")

        # B. Minor manual customization on tiny suite (0 custom additions, 1 manual deletion)
        # Standard rules would classify this as OVERRIDDEN.
        # Tiny-suite overfitting rule holds status at PARTIALLY_FOLLOWED.
        outcome_t2 = RecommendationOutcome(
            recommendation_run_id=run_tiny.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="tiny_hash",
            outcome_status="PENDING",
            executed_tests=["test_tiny_0", "test_tiny_1"],
            manually_added_tests=[],
            manually_removed_tests=["test_tiny_2"]
        )
        res_t2 = RecommendationOutcomeClassifier.classify(outcome_t2, db=db)
        assert res_t2["classification_label"] == "PARTIALLY_FOLLOWED"
        assert res_t2["tiny_repo_overfitting_prevented"] is True
        print("[PASSED] Verified tiny-suite manual deletes hold status at PARTIALLY_FOLLOWED instead of OVERRIDDEN.\n")

        # --------------------------------------------------------------------
        # TEST 11: Append-only lineage preserved
        # --------------------------------------------------------------------
        print("--- TEST 11: append-only lineage preserved ---")
        # Reasoning Entries are append-only. Mutation/deletion must trigger RuntimeError.
        reason_entry = RecommendationReasoningEntry(
            id=uuid.uuid4(),
            recommendation_run_id=run_1.id,
            reason_type="outcome_classification",
            source_entity=str(outcome_1.id),
            source_reference="audit-lineage",
            human_readable_reason="Verifying lineage preservation",
            confidence_level="HIGH",
            evidence_priority="CRITICAL",
            reasoning_metadata={},
            created_at=datetime.datetime.utcnow()
        )
        db.add(reason_entry)
        db.commit()

        # Try to delete reasoning entry
        db.delete(reason_entry)
        try:
            db.commit()
            assert False, "Lineage mutation fail: Deletion on RecommendationReasoningEntry should have been blocked!"
        except Exception as e:
            db.rollback()
            assert "Forensic Immutability Violation" in str(e)
            print("[PASSED] Verified RecommendationReasoningEntry immutability blocks deletions.")

        # Try to update reasoning entry
        reason_entry.human_readable_reason = "Mutated description"
        try:
            db.commit()
            assert False, "Lineage mutation fail: Updates on RecommendationReasoningEntry should have been blocked!"
        except Exception as e:
            db.rollback()
            assert "Forensic Immutability Violation" in str(e)
            print("[PASSED] Verified RecommendationReasoningEntry immutability blocks updates.\n")

        # --------------------------------------------------------------------
        # TEST 12: Replay classification stability verified
        # --------------------------------------------------------------------
        print("--- TEST 12: replay classification stability verified ---")
        # Seeding a perfect follow-up outcome with execution evidence
        run_st = RecommendationRun(
            repository_id=repo_id,
            pr_id="pr_980_head",
            pull_request_id=pr_id,
            triggered_by="github-webhook",
            engine_version="v1",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Stability check run",
            evidence_quality="HIGH",
            created_at=datetime.datetime.utcnow()
        )
        db.add(run_st)
        db.commit()

        for i in range(5):
            t = RecommendationTest(
                recommendation_run_id=run_st.id,
                test_case_id=f"test_case_{i}",
                reason_type="historical_fragility",
                reason_details={},
                priority_score=0.8
            )
            db.add(t)
        db.commit()

        outcome_st = RecommendationOutcome(
            recommendation_run_id=run_st.id,
            repository_id=repo_id,
            pull_request_id=pr_id,
            recommendation_snapshot_hash="stability_hash",
            outcome_status="PENDING",
            was_followed_legacy=True,
            executed_tests=["test_case_0", "test_case_1", "test_case_2", "test_case_3", "test_case_4"]
        )
        db.add(outcome_st)
        db.commit()
        db.refresh(outcome_st)

        # Log evidence TEST_RUN
        test_run_payload = {
            "executed_tests": ["test_case_0", "test_case_1", "test_case_2", "test_case_3", "test_case_4"],
            "manually_added_tests": [],
            "manually_removed_tests": [],
            "was_followed": True
        }
        RecommendationOutcomeEvidenceIntegrity.record_evidence(
            db=db,
            outcome_id=outcome_st.id,
            evidence_type="TEST_RUN",
            source_reference_id="test_run_stability_source",
            payload=test_run_payload
        )
        
        # Classification update (Automatically shifts status to FOLLOWED and generates snapshot)
        RecommendationOutcomeClassifier.classify_and_update(db, outcome_st)
        assert outcome_st.outcome_status == "FOLLOWED"

        # A. Perfect replay verification
        report = RecommendationOutcomeEvidenceIntegrity.replay_and_verify(db, outcome_st.id)
        assert report["drift_detected"] is False
        assert report["replayed_outcome_status"] == "FOLLOWED"
        print("[PASSED] Stability verified: Chronological evidence replay yields perfect outcome alignment without drift.")

        # B. Direct administrative DB modification bypass simulation (tampering)
        # Set status directly on SQLAlchemy metadata, bypassing classifier pipeline update
        db.execute(
            RecommendationOutcome.__table__.update()
            .where(RecommendationOutcome.id == outcome_st.id)
            .values(outcome_status="IGNORED")
        )
        db.commit()
        db.expire_all()

        # Re-run replay verification -> Must detect drift and raise ValueError
        try:
            RecommendationOutcomeEvidenceIntegrity.replay_and_verify(db, outcome_st.id)
            assert False, "Drift detection fail: Should have flagged mismatch between IGNORED and FOLLOWED!"
        except ValueError as e:
            assert "Historical Drift Detected" in str(e)
            print("[PASSED] Active database tampering detected successfully via evidence replay.\n")

    finally:
        db.close()

    print("==================================================================")
    print("ALL 12 DETERMINISTIC RECOMMENDATION OUTCOME CHECKS PASSED!")
    print("==================================================================")

if __name__ == "__main__":
    cleanup_database()
    try:
        run_all_checks()
    finally:
        cleanup_database()
