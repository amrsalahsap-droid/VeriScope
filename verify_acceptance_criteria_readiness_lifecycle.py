"""
Diagnostic script to verify Acceptance Criteria readiness lifecycle.

This script traces the complete flow using backend services directly:
1. Fetch readiness before AC
2. Submit AC through backend service
3. Query DB directly to verify persistence
4. Fetch readiness after AC save
5. Simulate page refresh with new readiness call
6. Verify AC moved from missing to available
7. Verify score increased
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db.session import SessionLocal
from app.services.recommendation_readiness_service import RecommendationReadinessService
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.business_intent import BusinessIntentOverride
from app.models.pull_request_work_item_link import PullRequestWorkItemLink
from app.models.external_work_item import ExternalWorkItem
from pydantic import BaseModel
from typing import Optional

# Test data - Use the test PR created by create_test_pr.py
REPOSITORY_ID = "72e9a692-9a3f-4f0e-ba54-4e1837f91d26"
PULL_REQUEST_ID = "5ec9686b-87cc-4109-badf-e99e1149f641"

# Sample AC data
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


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def fetch_readiness(repository_id, pull_request_id):
    """Fetch readiness data using backend service."""
    db = SessionLocal()
    try:
        service = RecommendationReadinessService(db)
        assessment = service.assess_readiness(
            repository_id=repository_id,
            pull_request_id=pull_request_id
        )
        
        # Convert to dict for easier inspection
        return {
            "readiness_level": assessment.readiness_level,
            "expected_confidence": assessment.expected_confidence,
            "readiness_score": assessment.readiness_score,
            "can_generate": assessment.can_generate,
            "available_inputs": [
                {
                    "key": s.get("key"),
                    "label": s.get("key"),
                    "status": s.get("status"),
                    "evidence_count": s.get("evidence_count", 0)
                }
                for s in assessment.available_inputs
            ],
            "missing_inputs": [
                {
                    "key": s.get("key"),
                    "label": s.get("key"),
                    "status": s.get("status"),
                    "impact": s.get("impact", "")
                }
                for s in assessment.missing_inputs
            ]
        }
    finally:
        db.close()


def submit_acceptance_criteria(repository_id, pull_request_id, ac_data):
    """Submit acceptance criteria using backend service directly."""
    from app.routers.repository import add_pr_acceptance_criteria_manual
    from app.models.repository import Repository
    from app.models.pull_request import PullRequest
    from pydantic import BaseModel
    
    class ManualAcceptanceCriteriaSubmit(BaseModel):
        business_change: str
        affected_users: Optional[str] = None
        acceptance_criteria: str
        risk_notes: Optional[str] = None
        testing_notes: Optional[str] = None
    
    db = SessionLocal()
    try:
        # Get repository and PR
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        pr = db.query(PullRequest).filter(
            PullRequest.id == pull_request_id,
            PullRequest.repository_id == repository_id
        ).first()
        
        if not repo or not pr:
            print(f"ERROR: Repository or PR not found")
            return None
        
        # Get workspace from repository
        workspace = repo.workspace
        
        # Create payload
        payload = ManualAcceptanceCriteriaSubmit(**ac_data)
        
        # Call the endpoint function directly
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


def query_db_for_ac(repository_id, pull_request_id):
    """Query database directly for AC records."""
    db = SessionLocal()
    
    results = {
        "acceptance_criteria": [],
        "business_intent_overrides": [],
        "external_work_items": []
    }
    
    try:
        # Query AcceptanceCriterion
        ac_results = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id,
            AcceptanceCriterion.pull_request_id == pull_request_id
        ).all()
        for ac in ac_results:
            results["acceptance_criteria"].append({
                "id": str(ac.id),
                "repository_id": str(ac.repository_id),
                "pull_request_id": str(ac.pull_request_id),
                "source": ac.source,
                "normalized_key": ac.normalized_key,
                "text": ac.text[:100] if ac.text else None,
                "created_at": str(ac.created_at)
            })
        
        # Query BusinessIntentOverride
        bio_results = db.query(BusinessIntentOverride).filter(
            BusinessIntentOverride.repository_id == repository_id,
            BusinessIntentOverride.pull_request_id == pull_request_id
        ).all()
        for bio in bio_results:
            results["business_intent_overrides"].append({
                "id": str(bio.id),
                "repository_id": str(bio.repository_id),
                "pull_request_id": str(bio.pull_request_id),
                "source": bio.source,
                "is_active": bio.is_active,
                "acceptance_criteria": bio.acceptance_criteria[:100] if bio.acceptance_criteria else None,
                "created_at": str(bio.created_at)
            })
        
        # Query ExternalWorkItem via PullRequestWorkItemLink
        wi_results = db.query(ExternalWorkItem).join(
            PullRequestWorkItemLink, PullRequestWorkItemLink.external_work_item_id == ExternalWorkItem.id
        ).filter(
            PullRequestWorkItemLink.pull_request_id == pull_request_id
        ).all()
        for wi in wi_results:
            results["external_work_items"].append({
                "id": str(wi.id),
                "acceptance_criteria": str(wi.acceptance_criteria)[:100] if wi.acceptance_criteria else None,
                "pull_request_id": pull_request_id
            })
        
    except Exception as e:
        print(f"ERROR querying database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
    
    return results


def print_readiness_summary(readiness, label):
    """Print a summary of readiness data."""
    if not readiness:
        print(f"{label}: No readiness data")
        return
    
    available_keys = [s.get("key") for s in readiness.get("available_inputs", [])]
    missing_keys = [s.get("key") for s in readiness.get("missing_inputs", [])]
    score = readiness.get("readiness_score", 0)
    
    print(f"{label}:")
    print(f"  Score: {score}")
    print(f"  Available inputs ({len(available_keys)}): {sorted(available_keys)}")
    print(f"  Missing inputs ({len(missing_keys)}): {sorted(missing_keys)}")
    
    # Check for AC specifically
    ac_available = "acceptance_criteria" in available_keys
    ac_missing = "acceptance_criteria" in missing_keys
    print(f"  Acceptance Criteria: AVAILABLE={ac_available}, MISSING={ac_missing}")
    
    if ac_available:
        ac_signal = next((s for s in readiness.get("available_inputs", []) if s.get("key") == "acceptance_criteria"), None)
        if ac_signal:
            print(f"    Evidence count: {ac_signal.get('evidence_count', 0)}")
            print(f"    Status: {ac_signal.get('status', 'N/A')}")


def main():
    print_section("Acceptance Criteria Readiness Lifecycle Verification")
    print(f"Repository ID: {REPOSITORY_ID}")
    print(f"Pull Request ID: {PULL_REQUEST_ID}")
    
    # Step 1: Fetch readiness before AC
    print_section("Step 1: Fetch Readiness Before AC")
    readiness_before = fetch_readiness(REPOSITORY_ID, PULL_REQUEST_ID)
    print_readiness_summary(readiness_before, "Before AC")
    
    # Step 2: Submit AC (skip if no PR)
    if not PULL_REQUEST_ID:
        print_section("Step 2: Skip AC Submission")
        print("No PR available - skipping AC submission test")
        print("Will only test readiness service logic")
        submit_response = None
    else:
        print_section("Step 2: Submit Acceptance Criteria")
        print(f"Using backend service: add_pr_acceptance_criteria_manual")
        print(f"Payload: {json.dumps(TEST_AC_DATA, indent=2)}")
        
        submit_response = submit_acceptance_criteria(REPOSITORY_ID, PULL_REQUEST_ID, TEST_AC_DATA)
        if not submit_response:
            print("FAILED: Could not submit AC")
            return False
        
        print(f"Response Status: Success")
        print(f"Saved: {submit_response.saved}")
        print(f"Criteria count: {submit_response.criteria_count}")
        print(f"Recommendation stale: {submit_response.recommendation_stale}")
    
    # Step 3: Query DB directly
    print_section("Step 3: Query Database Directly")
    db_results = query_db_for_ac(REPOSITORY_ID, PULL_REQUEST_ID)
    
    print(f"AcceptanceCriteria rows: {len(db_results['acceptance_criteria'])}")
    for row in db_results['acceptance_criteria'][:3]:  # Show first 3
        print(f"  - {row}")
    
    print(f"\nBusinessIntentOverride rows: {len(db_results['business_intent_overrides'])}")
    for row in db_results['business_intent_overrides'][:3]:
        print(f"  - {row}")
    
    print(f"\nExternalWorkItem rows: {len(db_results['external_work_items'])}")
    for row in db_results['external_work_items'][:3]:
        print(f"  - {row}")
    
    # Step 4: Fetch readiness after AC save
    print_section("Step 4: Fetch Readiness After AC Save")
    readiness_after_save = fetch_readiness(REPOSITORY_ID, PULL_REQUEST_ID)
    print_readiness_summary(readiness_after_save, "After AC Save")
    
    # Step 5: Simulate page refresh (new readiness call)
    print_section("Step 5: Simulate Page Refresh (New Readiness Call)")
    readiness_after_refresh = fetch_readiness(REPOSITORY_ID, PULL_REQUEST_ID)
    print_readiness_summary(readiness_after_refresh, "After Refresh")
    
    # Step 6: Verification
    print_section("Step 6: Verification Results")
    
    score_before = int(readiness_before.get("readiness_score", 0) * 100) if readiness_before else 0
    score_after = int(readiness_after_save.get("readiness_score", 0) * 100) if readiness_after_save else 0
    score_after_refresh = int(readiness_after_refresh.get("readiness_score", 0) * 100) if readiness_after_refresh else 0
    
    available_before = [s.get("key") for s in readiness_before.get("available_inputs", [])] if readiness_before else []
    missing_before = [s.get("key") for s in readiness_before.get("missing_inputs", [])] if readiness_before else []
    available_after = [s.get("key") for s in readiness_after_save.get("available_inputs", [])] if readiness_after_save else []
    missing_after = [s.get("key") for s in readiness_after_save.get("missing_inputs", [])] if readiness_after_save else []
    available_refresh = [s.get("key") for s in readiness_after_refresh.get("available_inputs", [])] if readiness_after_refresh else []
    missing_refresh = [s.get("key") for s in readiness_after_refresh.get("missing_inputs", [])] if readiness_after_refresh else []
    
    total_ac_rows = (len(db_results['acceptance_criteria']) + 
                     len(db_results['business_intent_overrides']) + 
                     len(db_results['external_work_items']))
    
    checks = {
        "AC DB count > 0": total_ac_rows > 0,
        "AC in available_inputs after save": "acceptance_criteria" in available_after,
        "AC NOT in missing_inputs after save": "acceptance_criteria" not in missing_after,
        "AC in available_inputs after refresh": "acceptance_criteria" in available_refresh,
        "AC NOT in missing_inputs after refresh": "acceptance_criteria" not in missing_refresh,
        "Score increased by >= 10 (unless capped)": score_after >= score_before + 10 or score_after == 100,
        "After-save matches after-refresh": json.dumps(available_after, sort_keys=True) == json.dumps(available_refresh, sort_keys=True),
        "No duplicate signal keys": len(set(available_after) & set(missing_after)) == 0
    }
    
    all_passed = True
    for check, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check}")
        if not passed:
            all_passed = False
    
    print(f"\nScore before: {score_before}")
    print(f"Score after save: {score_after}")
    print(f"Score after refresh: {score_after_refresh}")
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
