import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.user import Workspace
from app.services.recommendation_logic_v1 import RecommendationLogicV1
import uuid

def test_recommendation_logic():
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

        print(f"Verifying RecommendationLogicV1 for Repo: {repo.full_name}, PR: #{pr.number}")

        # 1. Run algorithm with the standard PR details
        recommendations = RecommendationLogicV1.generate_recommendations(
            db=db,
            repository_id=repo.id,
            pull_request_id=pr.id,
            workspace=workspace
        )

        print(f"\nSUCCESS: Generated {len(recommendations)} recommended tests.")
        
        # Verify schema of the output
        if len(recommendations) > 0:
            print("\n--- Sample Recommended Test Output Schema ---")
            import json
            print(json.dumps(recommendations[0], indent=2))
            
            # Assert all required keys are present
            required_keys = {
                "test_identifier", "test_name", "class_name/module", 
                "priority", "estimated_duration_seconds", "reason", 
                "confidence", "source_signal"
            }
            sample_keys = set(recommendations[0].keys())
            if required_keys.issubset(sample_keys):
                print("\nSUCCESS: Output schema fully conforms to required keys.")
            else:
                print(f"\nFAILURE: Missing required output keys: {required_keys - sample_keys}")

            # Verify deterministic ordering (sorting priorities descending)
            priorities = [t["priority"] for t in recommendations]
            is_sorted = all(priorities[i] >= priorities[i+1] for i in range(len(priorities)-1))
            if is_sorted:
                print("SUCCESS: Recommended tests are deterministically ranked by priority descending.")
            else:
                print("FAILURE: Recommended tests are NOT sorted correctly by priority.")

        # 2. Verify MVP Fallback Mode
        # To simulate no changed files (and trigger MVP Fallback), we pass a dummy PR UUID that has no changed files in the DB,
        # but has test history for the repo.
        print("\nVerifying MVP Fallback Mode...")
        dummy_pr_id = uuid.uuid4()
        fallback_recommendations = RecommendationLogicV1.generate_recommendations(
            db=db,
            repository_id=repo.id,
            pull_request_id=dummy_pr_id,
            workspace=workspace
        )

        print(f"Fallback recommendations count: {len(fallback_recommendations)}")
        if len(fallback_recommendations) > 0:
            print("\n--- Fallback Sample Recommended Test ---")
            print(json.dumps(fallback_recommendations[0], indent=2))
            
            # Verify fallback properties
            all_low = all(t["confidence"] == "LOW" for t in fallback_recommendations)
            all_fallback_signal = all("FALLBACK" in t["source_signal"] for t in fallback_recommendations)
            if all_low and all_fallback_signal:
                print("\nSUCCESS: Fallback mode correctly issued LOW confidence recommendations with the fallback signal.")
            else:
                print("\nFAILURE: Fallback properties are incorrect.")
        else:
            print("\nFAILURE: Fallback mode did not return any recommendations.")

    except Exception as e:
        print(f"Error during logic verification: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_recommendation_logic()
