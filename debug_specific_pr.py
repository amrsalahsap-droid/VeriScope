"""
Debug specific PR that user is having issues with.
Repository ID: 017ba58f-f192-4655-81ea-781f1955de0e
Pull Request ID: f553f0c3-7493-462d-9453-d50f4c15cecc
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

REPOSITORY_ID = "017ba58f-f192-4655-81ea-781f1955de0e"
PULL_REQUEST_ID = "f553f0c3-7493-462d-9453-d50f4c15cecc"

def main():
    print(f"Debugging specific PR")
    print(f"Repository ID: {REPOSITORY_ID}")
    print(f"Pull Request ID: {PULL_REQUEST_ID}")
    print()
    
    db = SessionLocal()
    try:
        # Check if repository and PR exist
        repo = db.query(Repository).filter(Repository.id == REPOSITORY_ID).first()
        pr = db.query(PullRequest).filter(
            PullRequest.id == PULL_REQUEST_ID,
            PullRequest.repository_id == REPOSITORY_ID
        ).first()
        
        print(f"Repository exists: {repo is not None}")
        if repo:
            print(f"Repository name: {repo.name}")
        
        print(f"PR exists: {pr is not None}")
        if pr:
            print(f"PR number: {pr.number}")
            print(f"PR title: {pr.title}")
        print()
        
        # Check AC in DB
        print("="*80)
        print("ACCEPTANCE CRITERIA IN DATABASE")
        print("="*80)
        
        ac_count = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == REPOSITORY_ID,
            AcceptanceCriterion.pull_request_id == PULL_REQUEST_ID
        ).count()
        
        print(f"AcceptanceCriterion count: {ac_count}")
        
        if ac_count > 0:
            ac_records = db.query(AcceptanceCriterion).filter(
                AcceptanceCriterion.repository_id == REPOSITORY_ID,
                AcceptanceCriterion.pull_request_id == PULL_REQUEST_ID
            ).all()
            
            for ac in ac_records[:5]:  # Show first 5
                print(f"  - ID: {ac.id}")
                print(f"    Text: {ac.text[:100]}")
                print(f"    Source: {ac.source}")
                print(f"    Normalized key: {ac.normalized_key}")
                print()
        
        # Check BusinessIntentOverride
        bio_count = db.query(BusinessIntentOverride).filter(
            BusinessIntentOverride.repository_id == REPOSITORY_ID,
            BusinessIntentOverride.pull_request_id == PULL_REQUEST_ID
        ).count()
        
        print(f"BusinessIntentOverride count: {bio_count}")
        
        if bio_count > 0:
            bio_records = db.query(BusinessIntentOverride).filter(
                BusinessIntentOverride.repository_id == REPOSITORY_ID,
                BusinessIntentOverride.pull_request_id == PULL_REQUEST_ID
            ).all()
            
            for bio in bio_records:
                print(f"  - ID: {bio.id}")
                print(f"    Source: {bio.source}")
                print(f"    Is active: {bio.is_active}")
                print(f"    AC text: {bio.acceptance_criteria[:200] if bio.acceptance_criteria else 'None'}")
                print()
        
        # Check readiness
        print("="*80)
        print("READINESS ASSESSMENT")
        print("="*80)
        
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(
            repository_id=REPOSITORY_ID,
            pull_request_id=PULL_REQUEST_ID
        )
        
        print(f"Readiness score: {assessment.readiness_score}")
        print(f"Readiness level: {assessment.readiness_level}")
        print(f"Can generate: {assessment.can_generate}")
        print()
        
        print("Available inputs:")
        for signal in assessment.available_inputs:
            print(f"  - {signal.get('key')}: {signal.get('status')}")
        
        print()
        print("Missing inputs:")
        for signal in assessment.missing_inputs:
            print(f"  - {signal.get('key')}: {signal.get('status')}")
        
        print()
        print("="*80)
        print("VERIFICATION")
        print("="*80)
        
        available_keys = [s.get("key") for s in assessment.available_inputs]
        missing_keys = [s.get("key") for s in assessment.missing_inputs]
        
        ac_available = "acceptance_criteria" in available_keys
        ac_missing = "acceptance_criteria" in missing_keys
        
        print(f"AC in available_inputs: {ac_available}")
        print(f"AC in missing_inputs: {ac_missing}")
        print(f"AC DB count: {ac_count}")
        print(f"BusinessIntent DB count: {bio_count}")
        
        if ac_count > 0 and ac_missing:
            print()
            print("ERROR: AC exists in DB but readiness says it's missing!")
            print("This indicates a bug in the readiness detection logic.")
        
        if ac_count == 0 and ac_missing:
            print()
            print("INFO: AC not in DB and readiness says it's missing.")
            print("This is expected - AC was not persisted.")
        
        if ac_count > 0 and ac_available:
            print()
            print("SUCCESS: AC exists in DB and readiness says it's available.")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
