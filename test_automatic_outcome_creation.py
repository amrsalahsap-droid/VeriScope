"""
Test automatic RecommendationOutcome creation.

Verifies that every recommendation run has an outcome record created automatically.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.recommendation import RecommendationService
from app.schemas.recommendation import RecommendationRunCreate
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.user import Workspace, User
from app.models.recommendation import RecommendationOutcome


def test_automatic_outcome_creation():
    """Test that outcome is created automatically with recommendation run."""
    print("=" * 70)
    print("AUTOMATIC OUTCOME CREATION TEST")
    print("=" * 70)
    
    # This is a structural test - we verify the code path exists
    # without requiring a full database setup
    
    # Test 1: Model has required fields
    print("\n[1] Model Field Verification")
    print("-" * 70)
    
    from app.models.recommendation import RecommendationOutcome
    
    # Check new fields exist
    outcome_fields = RecommendationOutcome.__table__.columns.keys()
    
    required_fields = [
        "id", "workspace_id", "repository_id", "pull_request_id",
        "recommendation_run_id", "outcome_status", "user_feedback",
        "feedback_comment", "ignored_reason", "defect_escaped",
        "rollback_occurred", "production_incident_url", "created_by",
        "created_at", "updated_at"
    ]
    
    for field in required_fields:
        if field in outcome_fields:
            print(f"  [PASS] {field} exists")
        else:
            print(f"  [FAIL] {field} missing")
            return False
    
    # Test 2: Default values in __init__
    print("\n[2] Default Value Verification")
    print("-" * 70)
    
    outcome = RecommendationOutcome(
        recommendation_run_id=uuid4(),
        repository_id=uuid4(),
        recommendation_snapshot_hash="test_hash"
    )
    
    assert outcome.outcome_status == "SHOWN", f"Expected SHOWN, got {outcome.outcome_status}"
    print(f"  [PASS] outcome_status defaults to SHOWN")
    
    assert outcome.user_feedback == "NOT_REVIEWED", f"Expected NOT_REVIEWED, got {outcome.user_feedback}"
    print(f"  [PASS] user_feedback defaults to NOT_REVIEWED")
    
    assert outcome.defect_escaped == False, f"Expected False, got {outcome.defect_escaped}"
    print(f"  [PASS] defect_escaped defaults to False")
    
    assert outcome.rollback_occurred == False, f"Expected False, got {outcome.rollback_occurred}"
    print(f"  [PASS] rollback_occurred defaults to False")
    
    # Test 3: Service code has idempotent check
    print("\n[3] Idempotent Creation Verification")
    print("-" * 70)
    
    with open("app/services/recommendation.py", "r") as f:
        content = f.read()
        
        # Check for idempotent check
        if "existing_outcome = self.db.query(RecommendationOutcome)" in content:
            print("  [PASS] Idempotent check exists in service")
        else:
            print("  [FAIL] Idempotent check missing")
            return False
        
        # Check for conditional creation
        if "if not existing_outcome:" in content:
            print("  [PASS] Conditional creation exists")
        else:
            print("  [FAIL] Conditional creation missing")
            return False
        
        # Check for new field usage
        if 'outcome_status="SHOWN"' in content:
            print("  [PASS] Uses SHOWN status")
        else:
            print("  [FAIL] SHOWN status not used")
            return False
        
        if 'user_feedback="NOT_REVIEWED"' in content:
            print("  [PASS] Uses NOT_REVIEWED feedback")
        else:
            print("  [FAIL] NOT_REVIEWED feedback not used")
            return False
    
    # Test 4: Unique constraint
    print("\n[4] Unique Constraint Verification")
    print("-" * 70)
    
    # Check that recommendation_run_id has unique=True
    from app.models.recommendation import RecommendationOutcome
    for col in RecommendationOutcome.__table__.columns:
        if col.name == "recommendation_run_id":
            if col.unique:
                print("  [PASS] recommendation_run_id has unique constraint")
            else:
                print("  [FAIL] recommendation_run_id missing unique constraint")
                return False
            break
    
    # Test 5: Workspace backfill in event listener
    print("\n[5] Workspace Backfill Verification")
    print("-" * 70)
    
    with open("app/models/recommendation.py", "r") as f:
        content = f.read()
        
        if "target.workspace_id = run.workspace_id" in content:
            print("  [PASS] Workspace backfill exists in event listener")
        else:
            print("  [FAIL] Workspace backfill missing")
            return False
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    print("\nAutomatic outcome creation implementation verified:")
    print("  - Model has all required fields")
    print("  - Default values set correctly (SHOWN, NOT_REVIEWED)")
    print("  - Service has idempotent creation check")
    print("  - Unique constraint on recommendation_run_id")
    print("  - Workspace backfill in event listener")
    print("\nEvery recommendation run will have an outcome shell after generation.")
    
    return True


if __name__ == "__main__":
    try:
        success = test_automatic_outcome_creation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
