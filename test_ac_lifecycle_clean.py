"""
Clean test of AC lifecycle - delete existing AC first to test score increase.
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import SessionLocal
from app.services.recommendation_readiness_service import RecommendationReadinessService
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.business_intent import BusinessIntentOverride
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.routers.repository import add_pr_acceptance_criteria_manual
from pydantic import BaseModel
from typing import Optional

# Test data
REPOSITORY_ID = "72e9a692-9a3f-4f0e-ba54-4e1837f91d26"
PULL_REQUEST_ID = "5ec9686b-87cc-4109-badf-e99e1149f641"

TEST_AC_DATA = {
    "business_change": "Add password validation to user registration",
    "affected_users": "New users registering accounts",
    "acceptance_criteria": """1. User must enter a password with at least 8 characters
2. Password must contain at least one uppercase letter
3. Password must contain at least one lowercase letter
4. Password must contain at least one number
5. Password must contain at least one special character
6. Password cannot contain common dictionary words
7. Password confirmation must match password
8. User receives clear error message if password requirements are not met""",
    "risk_notes": "Security risk if weak passwords are allowed",
    "testing_notes": "Test with various password combinations including edge cases"
}

class ManualAcceptanceCriteriaSubmit(BaseModel):
    business_change: str
    affected_users: Optional[str] = None
    acceptance_criteria: str
    risk_notes: Optional[str] = None
    testing_notes: Optional[str] = None

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def fetch_readiness(repository_id, pull_request_id):
    db = SessionLocal()
    try:
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(
            repository_id=repository_id,
            pull_request_id=pull_request_id
        )
        
        return {
            "readiness_level": assessment.readiness_level,
            "expected_confidence": assessment.expected_confidence,
            "readiness_score": assessment.readiness_score,
            "can_generate": assessment.can_generate,
            "available_inputs": [
                {
                    "key": s.get("key"),
                    "status": s.get("status"),
                    "evidence_count": s.get("evidence_count", 0)
                }
                for s in assessment.available_inputs
            ],
            "missing_inputs": [
                {
                    "key": s.get("key"),
                    "status": s.get("status")
                }
                for s in assessment.missing_inputs
            ]
        }
    finally:
        db.close()

def delete_existing_ac(repository_id, pull_request_id):
    db = SessionLocal()
    try:
        # Delete existing AcceptanceCriteria
        db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id,
            AcceptanceCriterion.pull_request_id == pull_request_id
        ).delete()
        
        # Delete existing BusinessIntentOverride
        db.query(BusinessIntentOverride).filter(
            BusinessIntentOverride.repository_id == repository_id,
            BusinessIntentOverride.pull_request_id == pull_request_id
        ).delete()
        
        db.commit()
        print("Deleted existing AC records")
    except Exception as e:
        db.rollback()
        print(f"ERROR deleting AC: {e}")
    finally:
        db.close()

def submit_acceptance_criteria(repository_id, pull_request_id, ac_data):
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        pr = db.query(PullRequest).filter(
            PullRequest.id == pull_request_id,
            PullRequest.repository_id == repository_id
        ).first()
        
        if not repo or not pr:
            print(f"ERROR: Repository or PR not found")
            return None
        
        workspace = repo.workspace
        payload = ManualAcceptanceCriteriaSubmit(**ac_data)
        
        result = add_pr_acceptance_criteria_manual(
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            payload=payload,
            workspace=workspace,
            db=db
        )
        
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        print(f"ERROR submitting AC: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()

def main():
    print_section("Clean AC Lifecycle Test")
    print(f"Repository ID: {REPOSITORY_ID}")
    print(f"Pull Request ID: {PULL_REQUEST_ID}")
    
    # Step 1: Delete existing AC
    print_section("Step 1: Delete Existing AC")
    delete_existing_ac(REPOSITORY_ID, PULL_REQUEST_ID)
    
    # Step 2: Fetch readiness before AC
    print_section("Step 2: Fetch Readiness Before AC")
    readiness_before = fetch_readiness(REPOSITORY_ID, PULL_REQUEST_ID)
    
    available_before = [s.get("key") for s in readiness_before.get("available_inputs", [])]
    missing_before = [s.get("key") for s in readiness_before.get("missing_inputs", [])]
    score_before = int(readiness_before.get("readiness_score", 0) * 100)
    
    print(f"Score: {score_before}")
    print(f"Available: {sorted(available_before)}")
    print(f"Missing: {sorted(missing_before)}")
    print(f"AC Available: {'acceptance_criteria' in available_before}")
    print(f"AC Missing: {'acceptance_criteria' in missing_before}")
    
    # Step 3: Submit AC
    print_section("Step 3: Submit AC")
    submit_response = submit_acceptance_criteria(REPOSITORY_ID, PULL_REQUEST_ID, TEST_AC_DATA)
    if not submit_response:
        print("FAILED: Could not submit AC")
        return False
    
    print(f"Saved: {submit_response.saved}")
    print(f"Criteria count: {submit_response.criteria_count}")
    print(f"Recommendation stale: {submit_response.recommendation_stale}")
    
    # Step 4: Fetch readiness after AC
    print_section("Step 4: Fetch Readiness After AC")
    readiness_after = fetch_readiness(REPOSITORY_ID, PULL_REQUEST_ID)
    
    available_after = [s.get("key") for s in readiness_after.get("available_inputs", [])]
    missing_after = [s.get("key") for s in readiness_after.get("missing_inputs", [])]
    score_after = int(readiness_after.get("readiness_score", 0) * 100)
    
    print(f"Score: {score_after}")
    print(f"Available: {sorted(available_after)}")
    print(f"Missing: {sorted(missing_after)}")
    print(f"AC Available: {'acceptance_criteria' in available_after}")
    print(f"AC Missing: {'acceptance_criteria' in missing_after}")
    
    # Step 5: Verification
    print_section("Step 5: Verification")
    
    checks = {
        "AC in available after": "acceptance_criteria" in available_after,
        "AC NOT in missing after": "acceptance_criteria" not in missing_after,
        "Score increased by >= 10": score_after >= score_before + 10 or score_after == 100,
        "No duplicate keys": len(set(available_after) & set(missing_after)) == 0
    }
    
    all_passed = True
    for check, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check}")
        if not passed:
            all_passed = False
    
    print(f"\nScore before: {score_before}")
    print(f"Score after: {score_after}")
    print(f"Score delta: {score_after - score_before}")
    
    print_section("Final Result")
    if all_passed:
        print("ALL CHECKS PASSED")
        return True
    else:
        print("SOME CHECKS FAILED")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
