import sys
import os
import uuid
from datetime import datetime

# Adjust path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.architecture_node import ArchitectureNode
from app.services.recommendation_readiness_gate import RecommendationReadinessGate
from tests.test_readiness_gate_api import setup_test_infrastructure, create_repo_pr, clear_gate_api_signals

def main():
    db = SessionLocal()
    try:
        workspace_id = setup_test_infrastructure(db)
        repo, pr = create_repo_pr(db, workspace_id)
        clear_gate_api_signals(db, repo.id, pr.id)

        # Seed minimal architecture node to allow MINIMUM_READY
        node = ArchitectureNode(
            id=uuid.uuid4(),
            repository_id=repo.id,
            node_type="MODULE",
            name="API",
            path="app/api.py",
            normalized_path="app/api.py",
            layer="DOMAIN"
        )
        db.add(node)
        db.commit()
        
        print(f"Seeded Repository: {repo.full_name} (ID: {repo.id})")
        print(f"Seeded PR: #{pr.number} (ID: {pr.id}, changed_files_count: {pr.changed_files_count})")

        repo_q = db.query(Repository).filter(Repository.id == repo.id).first()
        print(f"Repo query UUID: {repo_q} (is_active: {repo_q.is_active if repo_q else None}, selected_for_analysis: {repo_q.selected_for_analysis if repo_q else None})")
        repo_q_str = db.query(Repository).filter(Repository.id == str(repo.id)).first()
        print(f"Repo query str: {repo_q_str}")

        gate = RecommendationReadinessGate()
        result = gate.assess(db, str(repo.id), str(pr.id))
        
        print("\n=== ASSESS GATE RESULT ===")
        print(f"can_generate: {result.can_generate}")
        print(f"readiness_level: {result.readiness_level}")
        print(f"expected_confidence: {result.expected_confidence}")
        print(f"user_message: {result.user_message}")
        print(f"technical_reason: {result.technical_reason}")
        print("\nAvailable inputs:")
        for inp in result.available_inputs:
            print(f" - {inp.key}: status={inp.status}, score={inp.confidence_contribution}")
        print("\nMissing inputs:")
        for inp in result.missing_inputs:
            print(f" - {inp.key}: severity={inp.severity}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == '__main__':
    main()
