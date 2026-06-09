import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.user import Workspace
from app.routers.repository import create_recommendation
import uuid

def test_dry_run():
    db = SessionLocal()
    try:
        # Find a repository and a pull request
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

        print(f"Testing Recommendation Dry Run Endpoint for Repository: {repo.full_name} and PR: #{pr.number}")
        print(f"Repo ID: {repo.id}, PR ID: {pr.id}")

        # Call the endpoint handler function directly
        result = create_recommendation(
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace,
            db=db
        )

        print("\n--- Dry Run Result Response ---")
        import json
        print(json.dumps(result, indent=2))
        
        # Verify persistence of RecommendationRun
        from app.models.recommendation import RecommendationRun
        run_id = uuid.UUID(result["recommendation_run_id"])
        run = db.query(RecommendationRun).filter(RecommendationRun.id == run_id).first()
        if run:
            print(f"\nSUCCESS: RecommendationRun {run_id} successfully persisted in database.")
            print(f"Triggered by: {run.triggered_by}")
            print(f"Mode: {run.recommendation_mode}")
            print(f"Persisted tests count: {len(run.tests)}")
        else:
            print(f"\nFAILURE: RecommendationRun {run_id} was NOT persisted in database.")

    finally:
        db.close()

if __name__ == "__main__":
    test_dry_run()
