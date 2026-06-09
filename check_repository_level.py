"""
Check repository-level readiness (not PR-level).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import SessionLocal
from app.services.recommendation_readiness_service import RecommendationReadinessService
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.business_intent import BusinessIntentOverride
from app.models.repository import Repository

REPOSITORY_ID = "6d3a3376-01d1-4208-8cd6-9db713afc2ed"

def main():
    print(f"Checking repository-level readiness for: {REPOSITORY_ID}")
    print()
    
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == REPOSITORY_ID).first()
        if not repo:
            print("Repository not found")
            return
        
        print(f"Repository: {repo.name}")
        print()
        
        # Check AC at repository level (no pull_request_id)
        ac_count_repo = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == REPOSITORY_ID,
            AcceptanceCriterion.pull_request_id == None
        ).count()
        
        bio_count_repo = db.query(BusinessIntentOverride).filter(
            BusinessIntentOverride.repository_id == REPOSITORY_ID,
            BusinessIntentOverride.pull_request_id == None
        ).count()
        
        print(f"Repository-level AC count (no PR): {ac_count_repo}")
        print(f"Repository-level BusinessIntent count (no PR): {bio_count_repo}")
        print()
        
        # Check repository-level readiness
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(
            repository_id=REPOSITORY_ID,
            pull_request_id=None
        )
        
        available_keys = [s.get("key") for s in assessment.available_inputs]
        missing_keys = [s.get("key") for s in assessment.missing_inputs]
        
        ac_available = "acceptance_criteria" in available_keys
        ac_missing = "acceptance_criteria" in missing_keys
        
        print(f"Repository-level readiness score: {assessment.readiness_score}")
        print(f"AC available: {ac_available}")
        print(f"AC missing: {ac_missing}")
        print(f"Available keys: {sorted(available_keys)}")
        print(f"Missing keys: {sorted(missing_keys)}")
        print()
        
        print("="*80)
        print("NOTE: Repository-level readiness does NOT include PR-specific AC.")
        print("AC submitted to a PR is only counted for that PR's readiness.")
        print("If you're seeing score 13 and AC missing, you're likely on the")
        print("repository page, not the PR page.")
        print("="*80)
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
