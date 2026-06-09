"""
Automated tests for Acceptance Criteria lifecycle.

Tests:
1. Raw manual AC only: Expected AC available.
2. Structured AC only: Expected AC available.
3. AC with wrong pull_request_id: Expected AC still missing for current PR.
4. AC with repository_id only and no PR: Expected not counted for PR readiness.
5. AC save then fresh readiness request: Expected AC available and score increased.
6. Duplicate AC paste: Expected no duplicate score.
7. available_inputs/missing_inputs exclusivity: Expected no signal key exists in both.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from app.db.session import SessionLocal
from app.services.recommendation_readiness_service import RecommendationReadinessService
from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.business_intent import BusinessIntentOverride
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.routers.repository import add_pr_acceptance_criteria_manual
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

class ManualAcceptanceCriteriaSubmit(BaseModel):
    business_change: str
    affected_users: Optional[str] = None
    acceptance_criteria: str
    risk_notes: Optional[str] = None
    testing_notes: Optional[str] = None

TEST_AC_DATA = {
    "business_change": "Test business change",
    "affected_users": "Test users",
    "acceptance_criteria": """1. First criterion
2. Second criterion
3. Third criterion""",
    "risk_notes": "Test risk",
    "testing_notes": "Test notes"
}

def cleanup_test_data(db, repository_id, pull_request_id):
    """Clean up test data."""
    db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.repository_id == repository_id,
        AcceptanceCriterion.pull_request_id == pull_request_id
    ).delete()
    
    db.query(BusinessIntentOverride).filter(
        BusinessIntentOverride.repository_id == repository_id,
        BusinessIntentOverride.pull_request_id == pull_request_id
    ).delete()
    
    db.commit()

def fetch_readiness(db, repository_id, pull_request_id):
    """Fetch readiness data."""
    service = RecommendationReadinessService(db)
    assessment = service.assess_readiness(
        repository_id=repository_id,
        pull_request_id=pull_request_id
    )
    
    return {
        "readiness_score": assessment.readiness_score,
        "available_inputs": [s.get("key") for s in assessment.available_inputs],
        "missing_inputs": [s.get("key") for s in assessment.missing_inputs]
    }

def submit_ac(db, repository_id, pull_request_id, ac_data):
    """Submit acceptance criteria."""
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    pr = db.query(PullRequest).filter(
        PullRequest.id == pull_request_id,
        PullRequest.repository_id == repository_id
    ).first()
    
    if not repo or not pr:
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

def test_raw_manual_ac_only():
    """Test 1: Raw manual AC only - Expected AC available."""
    db = SessionLocal()
    try:
        # Get test repository and PR
        repo = db.query(Repository).first()
        if not repo:
            pytest.skip("No repository found")
        
        pr = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).first()
        if not pr:
            pytest.skip("No pull request found")
        
        repository_id = str(repo.id)
        pull_request_id = str(pr.id)
        
        # Clean up first
        cleanup_test_data(db, repository_id, pull_request_id)
        
        # Submit AC
        result = submit_ac(db, repository_id, pull_request_id, TEST_AC_DATA)
        assert result is not None, "AC submission failed"
        assert result.saved is True, "AC not saved"
        
        # Verify AC is available
        readiness = fetch_readiness(db, repository_id, pull_request_id)
        assert "acceptance_criteria" in readiness["available_inputs"], "AC not in available_inputs"
        assert "acceptance_criteria" not in readiness["missing_inputs"], "AC in missing_inputs"
        
        # Verify DB has records
        ac_count = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id,
            AcceptanceCriterion.pull_request_id == pull_request_id
        ).count()
        assert ac_count > 0, "No AC records in DB"
        
        # Clean up
        cleanup_test_data(db, repository_id, pull_request_id)
        
    finally:
        db.close()

def test_structured_ac_only():
    """Test 2: Structured AC only - Expected AC available."""
    db = SessionLocal()
    try:
        repo = db.query(Repository).first()
        if not repo:
            pytest.skip("No repository found")
        
        pr = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).first()
        if not pr:
            pytest.skip("No pull request found")
        
        repository_id = str(repo.id)
        pull_request_id = str(pr.id)
        
        # Clean up first
        cleanup_test_data(db, repository_id, pull_request_id)
        
        # Submit AC (this creates both raw and structured)
        result = submit_ac(db, repository_id, pull_request_id, TEST_AC_DATA)
        assert result is not None
        
        # Verify structured AC exists
        ac_records = db.query(AcceptanceCriterion).filter(
            AcceptanceCriterion.repository_id == repository_id,
            AcceptanceCriterion.pull_request_id == pull_request_id
        ).all()
        
        assert len(ac_records) > 0, "No structured AC records"
        
        # Verify each has correct fields
        for ac in ac_records:
            assert ac.repository_id == repo.id, "Wrong repository_id"
            assert ac.pull_request_id == pr.id, "Wrong pull_request_id"
            assert ac.source == "MANUAL_USER_INPUT", "Wrong source"
            assert ac.normalized_key is not None, "No normalized_key"
            assert ac.text is not None, "No text"
        
        # Verify AC is available
        readiness = fetch_readiness(db, repository_id, pull_request_id)
        assert "acceptance_criteria" in readiness["available_inputs"]
        
        # Clean up
        cleanup_test_data(db, repository_id, pull_request_id)
        
    finally:
        db.close()

def test_ac_with_wrong_pr_id():
    """Test 3: AC with wrong pull_request_id - Expected AC still missing for current PR."""
    db = SessionLocal()
    try:
        repo = db.query(Repository).first()
        if not repo:
            pytest.skip("No repository found")
        
        # Get first PR
        pr1 = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).first()
        if not pr1:
            pytest.skip("No pull request found")
        
        # Try to get second PR, or create a fake one
        pr2 = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).offset(1).first()
        
        if not pr2:
            pytest.skip("Need two PRs for this test")
        
        repository_id = str(repo.id)
        pull_request_id_1 = str(pr1.id)
        pull_request_id_2 = str(pr2.id)
        
        # Clean up both
        cleanup_test_data(db, repository_id, pull_request_id_1)
        cleanup_test_data(db, repository_id, pull_request_id_2)
        
        # Submit AC for PR2
        result = submit_ac(db, repository_id, pull_request_id_2, TEST_AC_DATA)
        assert result is not None
        
        # Check PR1 readiness - AC should be missing
        readiness = fetch_readiness(db, repository_id, pull_request_id_1)
        assert "acceptance_criteria" not in readiness["available_inputs"], "AC should not be available for PR1"
        assert "acceptance_criteria" in readiness["missing_inputs"], "AC should be missing for PR1"
        
        # Check PR2 readiness - AC should be available
        readiness_2 = fetch_readiness(db, repository_id, pull_request_id_2)
        assert "acceptance_criteria" in readiness_2["available_inputs"], "AC should be available for PR2"
        
        # Clean up
        cleanup_test_data(db, repository_id, pull_request_id_1)
        cleanup_test_data(db, repository_id, pull_request_id_2)
        
    finally:
        db.close()

def test_repository_level_ac_not_counted():
    """Test 4: AC with repository_id only and no PR - Expected not counted for PR readiness."""
    db = SessionLocal()
    try:
        repo = db.query(Repository).first()
        if not repo:
            pytest.skip("No repository found")
        
        pr = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).first()
        if not pr:
            pytest.skip("No pull request found")
        
        repository_id = str(repo.id)
        pull_request_id = str(pr.id)
        
        # Clean up
        cleanup_test_data(db, repository_id, pull_request_id)
        
        # Create AC with null pull_request_id (repository-level)
        ac = AcceptanceCriterion(
            id=uuid.uuid4(),
            repository_id=repo.id,
            pull_request_id=None,  # Repository-level
            source="MANUAL_USER_INPUT",
            normalized_key="test_criterion",
            text="Test criterion",
            created_at=datetime.utcnow()
        )
        db.add(ac)
        db.commit()
        
        # Check PR readiness - repository-level AC should not count
        readiness = fetch_readiness(db, repository_id, pull_request_id)
        assert "acceptance_criteria" not in readiness["available_inputs"], "Repository-level AC should not count for PR"
        
        # Clean up
        db.query(AcceptanceCriterion).filter(AcceptanceCriterion.id == ac.id).delete()
        db.commit()
        
    finally:
        db.close()

def test_ac_save_then_fresh_readiness():
    """Test 5: AC save then fresh readiness request - Expected AC available and score increased."""
    db = SessionLocal()
    try:
        repo = db.query(Repository).first()
        if not repo:
            pytest.skip("No repository found")
        
        pr = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).first()
        if not pr:
            pytest.skip("No pull request found")
        
        repository_id = str(repo.id)
        pull_request_id = str(pr.id)
        
        # Clean up
        cleanup_test_data(db, repository_id, pull_request_id)
        
        # Get readiness before
        readiness_before = fetch_readiness(db, repository_id, pull_request_id)
        score_before = int(readiness_before["readiness_score"] * 100)
        
        # Submit AC
        result = submit_ac(db, repository_id, pull_request_id, TEST_AC_DATA)
        assert result is not None
        
        # Get readiness after with new session
        db.close()
        db = SessionLocal()
        readiness_after = fetch_readiness(db, repository_id, pull_request_id)
        score_after = int(readiness_after["readiness_score"] * 100)
        
        # Verify AC available
        assert "acceptance_criteria" in readiness_after["available_inputs"]
        
        # Verify score increased (unless already at 100)
        if score_before < 100:
            assert score_after >= score_before + 10, f"Score should increase by at least 10: {score_before} -> {score_after}"
        
        # Clean up
        cleanup_test_data(db, repository_id, pull_request_id)
        
    finally:
        db.close()

def test_duplicate_ac_paste():
    """Test 6: Duplicate AC paste - Expected no duplicate score."""
    db = SessionLocal()
    try:
        repo = db.query(Repository).first()
        if not repo:
            pytest.skip("No repository found")
        
        pr = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).first()
        if not pr:
            pytest.skip("No pull request found")
        
        repository_id = str(repo.id)
        pull_request_id = str(pr.id)
        
        # Clean up
        cleanup_test_data(db, repository_id, pull_request_id)
        
        # Submit AC first time
        result1 = submit_ac(db, repository_id, pull_request_id, TEST_AC_DATA)
        assert result1 is not None
        
        # Get readiness after first submit
        readiness_1 = fetch_readiness(db, repository_id, pull_request_id)
        score_1 = int(readiness_1["readiness_score"] * 100)
        
        # Submit AC second time (duplicate)
        result2 = submit_ac(db, repository_id, pull_request_id, TEST_AC_DATA)
        assert result2 is not None
        
        # Get readiness after second submit
        db.close()
        db = SessionLocal()
        readiness_2 = fetch_readiness(db, repository_id, pull_request_id)
        score_2 = int(readiness_2["readiness_score"] * 100)
        
        # Score should not increase on duplicate
        assert score_2 == score_1, f"Score should not increase on duplicate: {score_1} -> {score_2}"
        
        # Clean up
        cleanup_test_data(db, repository_id, pull_request_id)
        
    finally:
        db.close()

def test_available_missing_exclusivity():
    """Test 7: available_inputs/missing_inputs exclusivity - Expected no signal key exists in both."""
    db = SessionLocal()
    try:
        repo = db.query(Repository).first()
        if not repo:
            pytest.skip("No repository found")
        
        pr = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).first()
        if not pr:
            pytest.skip("No pull request found")
        
        repository_id = str(repo.id)
        pull_request_id = str(pr.id)
        
        # Get readiness
        readiness = fetch_readiness(db, repository_id, pull_request_id)
        
        available = set(readiness["available_inputs"])
        missing = set(readiness["missing_inputs"])
        
        # No overlap
        overlap = available & missing
        assert len(overlap) == 0, f"Signal keys in both available and missing: {overlap}"
        
    finally:
        db.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
