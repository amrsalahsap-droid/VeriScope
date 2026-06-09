"""Regression test for Acceptance Criteria persistence across page refresh."""
import pytest
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.business_intent import BusinessIntentOverride
from app.services.recommendation_readiness_service import RecommendationReadinessService


def test_ac_persistence_across_refresh(db: Session):
    """
    Test that Acceptance Criteria persist and are detected correctly after page refresh.
    
    This simulates the flow:
    1. Create repo + PR with 6 changed files
    2. Add AC manually
    3. Fetch readiness (before refresh)
    4. Simulate page refresh by creating a new request/session
    5. Fetch readiness again (after refresh)
    
    Expected both before and after refresh:
    - pull_request_diff available
    - acceptance_criteria available
    - business_intent available if provided
    - readiness score stable
    - readiness_level not downgraded
    - no BLOCKED status
    """
    # 1. Create repository
    repo = Repository(
        id="test-repo-id",
        full_name="test/repo",
        owner="test",
        name="repo",
        visibility="public",
        default_branch="main",
        is_active=True,
        selected_for_analysis=True,
        workspace_id="test-workspace-id"
    )
    db.add(repo)
    db.commit()
    
    # 2. Create PR with 6 changed files
    pr = PullRequest(
        id="test-pr-id",
        repository_id=repo.id,
        number=1,
        title="Test PR",
        author="testuser",
        source_branch="feature/test",
        target_branch="main",
        state="open",
        changed_files_count=6,
        head_commit_sha="abc123"
    )
    db.add(pr)
    db.commit()
    
    # 3. Add AC manually
    ac = AcceptanceCriterion(
        id="test-ac-id",
        repository_id=repo.id,
        pull_request_id=pr.id,
        text="User can login successfully",
        source="MANUAL_USER_INPUT",
        confidence=1.0,
        evidence_excerpt="User can login successfully",
        normalized_key="user_can_login_successfully",
        criterion_type="FUNCTIONAL"
    )
    db.add(ac)
    
    # 4. Add Business Intent
    bio = BusinessIntentOverride(
        id="test-bio-id",
        repository_id=repo.id,
        pull_request_id=pr.id,
        business_change_summary="Add login feature",
        affected_users_journeys="New users",
        acceptance_criteria="User can login successfully",
        source="MANUAL_USER_INPUT",
        is_active=True,
        is_processed=True
    )
    db.add(bio)
    db.commit()
    
    # 5. Fetch readiness before refresh
    service = RecommendationReadinessService(db)
    assessment_before = service.assess_readiness(
        repository_id=str(repo.id),
        pull_request_id=str(pr.id)
    )
    
    # 6. Simulate page refresh - create new service instance
    service_after = RecommendationReadinessService(db)
    assessment_after = service_after.assess_readiness(
        repository_id=str(repo.id),
        pull_request_id=str(pr.id)
    )
    
    # Assertions for before refresh
    assert "pull_request_diff" in assessment_before.available_signals, "PR diff should be available before refresh"
    assert "acceptance_criteria" in assessment_before.available_signals, "AC should be available before refresh"
    assert "business_intent" in assessment_before.available_signals, "Business intent should be available before refresh"
    assert assessment_before.readiness_level != "BLOCKED", "Should not be BLOCKED before refresh"
    assert assessment_before.can_generate == True, "Should be able to generate before refresh"
    
    # Assertions for after refresh
    assert "pull_request_diff" in assessment_after.available_signals, "PR diff should be available after refresh"
    assert "acceptance_criteria" in assessment_after.available_signals, "AC should be available after refresh"
    assert "business_intent" in assessment_after.available_signals, "Business intent should be available after refresh"
    assert assessment_after.readiness_level != "BLOCKED", "Should not be BLOCKED after refresh"
    assert assessment_after.can_generate == True, "Should be able to generate after refresh"
    
    # Score stability check
    score_before = int(assessment_before.readiness_score * 100)
    score_after = int(assessment_after.readiness_score * 100)
    assert score_before == score_after, f"Score should be stable: before={score_before}, after={score_after}"
    
    # Status consistency check
    assert assessment_before.readiness_level == assessment_after.readiness_level, \
        f"Readiness level should be consistent: before={assessment_before.readiness_level}, after={assessment_after.readiness_level}"
    
    # Available signals consistency
    assert set(assessment_before.available_signals) == set(assessment_after.available_signals), \
        "Available signals should be consistent before and after refresh"
    
    # Cleanup
    db.delete(ac)
    db.delete(bio)
    db.delete(pr)
    db.delete(repo)
    db.commit()
    
    print("✓ AC persistence test passed")
    print(f"  - PR diff available: True")
    print(f"  - AC available: True")
    print(f"  - Business intent available: True")
    print(f"  - Score stable: {score_before}%")
    print(f"  - Readiness level: {assessment_before.readiness_level}")


if __name__ == "__main__":
    # Run with pytest
    pytest.main([__file__, "-v"])
