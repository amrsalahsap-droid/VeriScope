import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.user import Workspace
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestCase, TestRun
from app.models.pattern_memory import PatternMemory
from app.services.recommendation_logic_v3 import RecommendationLogicV3
from app.services.learning_engine_v2 import LearningEngineV2
from app.models.recommendation import RecommendationOutcome, RecommendationRun
from app.services.evidence_gap_detector import EvidenceGapDetector

def verify():
    print("=======================================================================")
    print("STARTING RECOMMENDATION PATTERN MEMORY SAFETY & CONTRACT VERIFICATION")
    print("=======================================================================\n")

    db = SessionLocal()
    try:
        # Find a repository with a PR
        repo = db.query(Repository).join(PullRequest).first()
        if not repo:
            print("No repository with a PR found in the database. Creating dummy context...")
            # Create a dummy workspace and repository
            ws = Workspace(id=uuid.uuid4(), name="Test WS")
            db.add(ws)
            db.commit()
            
            repo = Repository(
                id=uuid.uuid4(),
                workspace_id=ws.id,
                full_name="test-owner/test-repo",
                visibility="PRIVATE",
                selected_for_analysis=True
            )
            db.add(repo)
            db.commit()

        print(f"Using Repository: {repo.full_name} (ID: {repo.id})")
        workspace = db.query(Workspace).filter(Workspace.id == repo.workspace_id).first()
        
        pr = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).first()
        if not pr:
            pr = PullRequest(
                id=uuid.uuid4(),
                repository_id=repo.id,
                number=1,
                title="Test PR",
                head_commit_sha="abcd123"
            )
            db.add(pr)
            db.commit()
        print(f"Using Pull Request #{pr.number} (ID: {pr.id})")

        # Make sure there is at least one test case
        tc = db.query(TestCase).filter(TestCase.repository_id == repo.id).first()
        if not tc:
            tc = TestCase(
                id=uuid.uuid4(),
                repository_id=repo.id,
                stable_identity="app/tests/test_auth.py::TestAuth::test_login",
                test_name="test_login",
                suite_name="app/tests/test_auth.py"
            )
            db.add(tc)
            db.commit()

        # Make sure there is at least one changed file
        cf = db.query(PullRequestChangedFile).filter(PullRequestChangedFile.pull_request_id == pr.id).first()
        if not cf:
            cf = PullRequestChangedFile(
                id=uuid.uuid4(),
                pull_request_id=pr.id,
                file_path="app/services/auth.py",
                status="modified"
            )
            db.add(cf)
            db.commit()

        # Make sure test runs count > 0
        tr_count = db.query(TestRun).filter(TestRun.repository_id == repo.id).count()
        if tr_count == 0:
            tr = TestRun(
                id=uuid.uuid4(),
                repository_id=repo.id,
                commit_sha="abcd123",
                total_tests=1,
                passed_tests=1,
                failed_tests=0,
                skipped_tests=0,
                duration=1.0,
                evidence_source="CI"
            )
            db.add(tr)
            db.commit()

        # Clean existing pattern memories for this repo
        db.query(PatternMemory).filter(PatternMemory.repository_id == repo.id).delete()
        db.commit()

        # ----------------------------------------------------
        # 1. Verify recommendation runs when pattern_memories is empty
        # ----------------------------------------------------
        print("\n--- Test 1: Generate recommendations with empty pattern_memories ---")
        recs = RecommendationLogicV3.generate_recommendations(
            db=db,
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace
        )
        print(f"[PASSED] Successfully generated {len(recs)} recommendations!")

        # ----------------------------------------------------
        # 2. Verify recommendation runs and applies PatternMemory boost
        # ----------------------------------------------------
        print("\n--- Test 2: Generate recommendations with matching pattern_memories ---")
        pm = PatternMemory(
            workspace_id=workspace.id,
            repository_id=repo.id,
            pattern_key=f"file_change:{cf.file_path}",
            changed_file_pattern=cf.file_path,
            recommended_test=tc.stable_identity,
            test_identifier=tc.stable_identity,
            confidence=0.85,
            usage_count=5
        )
        db.add(pm)
        db.commit()

        recs_with_pm = RecommendationLogicV3.generate_recommendations(
            db=db,
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace
        )
        
        found_boost = False
        for r in recs_with_pm:
            if r["test_identifier"] == tc.stable_identity:
                found_boost = True
                pm_val = r["reason_details"].get("pattern_memory", 0)
                print(f"Pattern Memory boost for {tc.stable_identity}: {pm_val}")
                assert pm_val == 85, f"Expected boost score of 85, got {pm_val}"
        assert found_boost, "Test case from pattern memory was not found in recommendations!"
        print("[PASSED] PatternMemory boost successfully loaded and applied!")

        # ----------------------------------------------------
        # 3. Verify recommendation runs when PatternMemory returns no matches
        # ----------------------------------------------------
        print("\n--- Test 3: Generate recommendations with non-matching pattern_memories ---")
        db.query(PatternMemory).filter(PatternMemory.repository_id == repo.id).delete()
        db.commit()
        pm_nomatch = PatternMemory(
            workspace_id=workspace.id,
            repository_id=repo.id,
            pattern_key="file_change:some/other/file.py",
            changed_file_pattern="some/other/file.py",
            recommended_test=tc.stable_identity,
            test_identifier=tc.stable_identity,
            confidence=0.90,
            usage_count=3
        )
        db.add(pm_nomatch)
        db.commit()

        recs_nomatch = RecommendationLogicV3.generate_recommendations(
            db=db,
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace
        )
        for r in recs_nomatch:
            if r["test_identifier"] == tc.stable_identity:
                pm_val = r["reason_details"].get("pattern_memory", 0)
                assert pm_val == 0, f"Expected non-matching boost score to be 0, got {pm_val}"
        print("[PASSED] Verified non-matching patterns yield 0 boost!")

        # 4. Verify learning v2 execution does not crash and updates PatternMemory correctly
        print("\n--- Test 4: LearningEngineV2 learn execution ---")
        db.query(RecommendationOutcome).filter(
            RecommendationOutcome.repository_id == repo.id
        ).delete()
        db.commit()

        run_for_outcome = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pr_id=str(pr.id),
            pull_request_id=pr.id,
            triggered_by="TEST",
            evidence_quality="HIGH",
            engine_version="v3.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Test reasoning"
        )
        db.add(run_for_outcome)
        db.commit()

        outcome = RecommendationOutcome(
            id=uuid.uuid4(),
            recommendation_run_id=run_for_outcome.id,
            repository_id=repo.id,
            pull_request_id=pr.id,
            recommendation_snapshot_hash="some_hash",
            outcome_status="COMPLETED",
            executed_tests=[tc.stable_identity],
            manually_added_tests=[tc.stable_identity],
            manually_removed_tests=[]
        )
        db.add(outcome)
        db.commit()

        db.query(PatternMemory).filter(
            PatternMemory.repository_id == repo.id
        ).delete()
        db.commit()

        learn_result = LearningEngineV2.learn(
            db=db,
            outcome=outcome,
            workspace_id=workspace.id
        )
        db.commit()
        print(f"Learning V2 Diagnostic Result: success={learn_result.success}, signals_processed={learn_result.signals_processed}, patterns_upserted={learn_result.patterns_upserted}, errors={learn_result.errors}")
        assert learn_result.success, f"Expected successful learning, got errors: {learn_result.errors}"
        assert learn_result.patterns_upserted > 0, "Expected at least one pattern upserted!"
        
        all_inserted = db.query(PatternMemory).filter(PatternMemory.repository_id == repo.id).all()
        print(f"All inserted pattern memory rows for repo {repo.id}:")
        for x in all_inserted:
            print(f"  - id={x.id}, pattern_key={x.pattern_key}, changed_file_pattern={x.changed_file_pattern}, recommended_test={x.recommended_test}, test_identifier={x.test_identifier}, workspace_id={x.workspace_id}")
        
        inserted_pm = db.query(PatternMemory).filter(
            PatternMemory.repository_id == repo.id,
            PatternMemory.test_identifier == tc.stable_identity
        ).first()
        assert inserted_pm is not None, "PatternMemory record was not inserted!"
        assert inserted_pm.workspace_id == workspace.id, f"Expected workspace_id to match, got {inserted_pm.workspace_id}"
        print("[PASSED] LearningEngineV2 successfully inserted valid schema-compliant PatternMemory records!")

        # ----------------------------------------------------
        # 5. Verify recommendation handles missing learning memory safely
        # ----------------------------------------------------
        print("\n--- Test 5: Verify missing/unavailable PatternMemory safety ---")
        from sqlalchemy.exc import ProgrammingError
        
        original_query = db.query
        def mock_query(*args, **kwargs):
            if args and args[0] is PatternMemory:
                raise ProgrammingError("select", {}, Exception("psycopg2.errors.UndefinedTable: relation \"pattern_memories\" does not exist"))
            return original_query(*args, **kwargs)

        with patch.object(db, "query", side_effect=mock_query):
            recs_missing = RecommendationLogicV3.generate_recommendations(
                db=db,
                repository_id=repo.id,
                pull_request_id=pr.id,
                workspace=workspace
            )
            assert len(recs_missing) > 0, "Expected recommendations to yield fallback/other signals instead of crashing!"
            
        print("[PASSED] Recommendation engine handles missing table gracefully without crashing!")

        # ----------------------------------------------------
        # 6. Verify evidence gaps contains warning when learning memory is missing/empty
        # ----------------------------------------------------
        print("\n--- Test 6: Verify evidence gaps contains warning ---")
        db.query(PatternMemory).filter(PatternMemory.repository_id == repo.id).delete()
        db.commit()

        run = RecommendationRun(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pr_id=str(pr.id),
            pull_request_id=pr.id,
            triggered_by="TEST",
            evidence_quality="HIGH",
            engine_version="v3.0.0",
            ruleset_version="rules-v1",
            degradation_policy_version="policy-v1",
            recommendation_reasoning_summary="Test reasoning"
        )
        db.add(run)
        db.commit()

        gaps = EvidenceGapDetector.detect_gaps(db, run, [])
        found_gap = False
        for g in gaps:
            if g["message"] == "No learning memory available yet.":
                found_gap = True
                assert g["severity"] == "WARNING", f"Expected severity to be WARNING, got {g['severity']}"
        assert found_gap, "Evidence gap 'No learning memory available yet.' not found!"
        print("[PASSED] EvidenceGapDetector successfully logs warning for empty pattern memory!")

        # ----------------------------------------------------
        # Clean up created entries
        # ----------------------------------------------------
        db.query(PatternMemory).filter(PatternMemory.repository_id == repo.id).delete()
        db.commit()

        print("\n=======================================================================")
        print("ALL RECOMMENDATION PATTERN MEMORY SAFETY UNIT TESTS PASSED SUCCESSFULLY!")
        print("=======================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    verify()
