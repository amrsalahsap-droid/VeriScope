import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.user import Workspace
from app.services.recommendation_input_builder import RecommendationInputBuilder
import uuid

def test_input_builder():
    db = SessionLocal()
    try:
        # Find active repository, pull request, and workspace
        repo = db.query(Repository).filter(Repository.selected_for_analysis == True).first()
        if not repo:
            print("No selected repository found.")
            return

        pr = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).first()
        if not pr:
            print(f"No pull request found for repository {repo.full_name}.")
            return

        workspace = db.query(Workspace).filter(Workspace.id == repo.workspace_id).first()
        if not workspace:
            print(f"No workspace found for repository {repo.full_name}.")
            return

        print(f"Verifying RecommendationInputBuilder for Repo: {repo.full_name}, PR: #{pr.number}")

        # 1. Build initial snapshot
        snapshot1 = RecommendationInputBuilder.build_snapshot(
            db=db,
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace
        )

        print("\n--- Built Snapshot 1 ---")
        print(f"Repository ID: {snapshot1.repository_id}")
        print(f"Pull Request ID: {snapshot1.pull_request_id}")
        print(f"Evidence Counts: {snapshot1.evidence_counts}")
        print(f"Coverage Confidence: {snapshot1.coverage_confidence}")
        print(f"Readiness State: {snapshot1.readiness_state}")
        print(f"Generated At: {snapshot1.generated_at}")
        print(f"Input Snapshot Hash: {snapshot1.input_snapshot_hash}")

        # 2. Build second snapshot on identical database state
        snapshot2 = RecommendationInputBuilder.build_snapshot(
            db=db,
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace
        )
        print(f"\nSnapshot 2 Hash: {snapshot2.input_snapshot_hash}")

        # Assert identical hash
        if snapshot1.input_snapshot_hash == snapshot2.input_snapshot_hash:
            print("SUCCESS: Identical database state yields identical snapshot hash.")
        else:
            print("FAILURE: Hash is not deterministic on identical database state.")

        # 3. Simulate database change by adding a temporary PullRequestChangedFile
        print("\nSimulating PR changed files modification (inserting a new file)...")
        temp_file = PullRequestChangedFile(
            id=uuid.uuid4(),
            pull_request_id=pr.id,
            file_path="src/new_temp_file_for_testing.py",
            status="added",
            additions=10,
            deletions=0
        )
        db.add(temp_file)
        db.flush() # Flush to db transaction (not committed)

        snapshot3 = RecommendationInputBuilder.build_snapshot(
            db=db,
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace
        )
        print(f"Snapshot 3 (Modified State) Hash: {snapshot3.input_snapshot_hash}")

        # Assert different hash
        if snapshot1.input_snapshot_hash != snapshot3.input_snapshot_hash:
            print("SUCCESS: Modified database state yields a completely different snapshot hash.")
        else:
            print("FAILURE: Modified database state did NOT change the snapshot hash.")

    except Exception as e:
        print(f"Error during verification: {e}")
    finally:
        print("\nRolling back the temporary database transaction...")
        db.rollback() # Rollback to keep database pure
        db.close()

if __name__ == "__main__":
    test_input_builder()
