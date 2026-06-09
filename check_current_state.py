"""
Check current state of the PR the user is on.
Repository ID: 6d3a3376-01d1-4208-8cd6-9db713afc2ed
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import SessionLocal
from app.services.recommendation_readiness_service import RecommendationReadinessService
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.business_intent import BusinessIntentOverride
from app.models.repository import Repository
from app.models.pull_request import PullRequest

REPOSITORY_ID = "6d3a3376-01d1-4208-8cd6-9db713afc2ed"

def main():
    print(f"Checking current state for repository: {REPOSITORY_ID}")
    print()
    
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == REPOSITORY_ID).first()
        if not repo:
            print("Repository not found")
            return
        
        print(f"Repository: {repo.name}")
        print()
        
        # Get all PRs for this repository
        prs = db.query(PullRequest).filter(PullRequest.repository_id == REPOSITORY_ID).all()
        
        print(f"Found {len(prs)} PR(s)")
        print()
        
        for pr in prs:
            print("="*80)
            print(f"PR: {pr.number} - {pr.title}")
            print(f"PR ID: {pr.id}")
            print()
            
            # Check AC in DB
            ac_count = db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.repository_id == REPOSITORY_ID,
                AcceptanceCriterion.pull_request_id == str(pr.id)
            ).count()
            
            bio_count = db.query(BusinessIntentOverride).filter(
                BusinessIntentOverride.repository_id == REPOSITORY_ID,
                BusinessIntentOverride.pull_request_id == str(pr.id)
            ).count()
            
            print(f"AC count: {ac_count}")
            print(f"BusinessIntent count: {bio_count}")
            
            # Check readiness
            service = RecommendationReadinessService(db)
            assessment = service.assess_readiness(
                repository_id=REPOSITORY_ID,
                pull_request_id=str(pr.id)
            )
            
            available_keys = [s.get("key") for s in assessment.available_inputs]
            missing_keys = [s.get("key") for s in assessment.missing_inputs]
            
            ac_available = "acceptance_criteria" in available_keys
            ac_missing = "acceptance_criteria" in missing_keys
            
            print(f"Readiness score: {assessment.readiness_score}")
            print(f"AC available: {ac_available}")
            print(f"AC missing: {ac_missing}")
            print(f"Available keys: {sorted(available_keys)}")
            print(f"Missing keys: {sorted(missing_keys)}")
            print()
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
