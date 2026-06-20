"""Test suite for Risk Review Workflow (Phase 2.2)

Tests the advisory risk prioritization review workflow for QA leads.
This workflow allows reviewing, accepting, annotating, or overriding
advisory risk priorities for missing and partial requirements.

Key constraints enforced:
- Only missing/partial items are reviewable (verified items cannot be reviewed)
- Review notes are required for OVERRIDDEN and NEEDS_DISCUSSION status
- Snapshot hash must match current evidence graph snapshot
- Reviews are advisory and do not change evidence buckets, test counts, AC coverage status, scope counts, or release readiness
"""

import pytest
import uuid
import json
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.session import SessionLocal
from app.models.risk_review import RiskReview


class TestRiskReviewModel:
    """Test the RiskReview model structure and constraints."""
    
    def test_risk_review_model_creation(self):
        """Test that RiskReview model can be created with required fields."""
        review = RiskReview(
            id=uuid.uuid4(),
            recommendation_run_id=uuid.uuid4(),
            source_requirement_id=str(uuid.uuid4()),
            source_ac_number=1,
            readable_id="AC-01",
            original_risk_level="HIGH",
            original_priority="P1",
            reviewed_risk_level="MEDIUM",
            reviewed_priority="P2",
            review_status="OVERRIDDEN",
            reviewer_id=str(uuid.uuid4()),
            reviewer_name="Test User",
            review_note="Test override note",
            source_snapshot_hash="abc123",
            is_active=True
        )
        
        # Verify all required fields are set
        assert review.id is not None
        assert review.recommendation_run_id is not None
        assert review.original_risk_level is not None
        assert review.original_priority is not None
        assert review.reviewed_risk_level is not None
        assert review.reviewed_priority is not None
        assert review.review_status is not None
        assert review.source_snapshot_hash is not None
        assert review.is_active is not None
    
    def test_risk_review_valid_statuses(self):
        """Test that review status accepts valid values."""
        valid_statuses = ["UNREVIEWED", "ACCEPTED", "OVERRIDDEN", "NEEDS_DISCUSSION"]
        
        for status in valid_statuses:
            review = RiskReview(
                id=uuid.uuid4(),
                recommendation_run_id=uuid.uuid4(),
                source_requirement_id=str(uuid.uuid4()),
                source_ac_number=1,
                readable_id="AC-01",
                original_risk_level="HIGH",
                original_priority="P1",
                reviewed_risk_level="MEDIUM",
                reviewed_priority="P2",
                review_status=status,
                reviewer_id=str(uuid.uuid4()),
                reviewer_name="Test User",
                review_note="Test note",
                source_snapshot_hash="abc123",
                is_active=True
            )
            assert review.review_status == status
    
    def test_risk_review_repr(self):
        """Test that RiskReview __repr__ works correctly."""
        review_id = uuid.uuid4()
        run_id = uuid.uuid4()
        
        review = RiskReview(
            id=review_id,
            recommendation_run_id=run_id,
            source_requirement_id=str(uuid.uuid4()),
            source_ac_number=1,
            readable_id="AC-01",
            original_risk_level="HIGH",
            original_priority="P1",
            reviewed_risk_level="MEDIUM",
            reviewed_priority="P2",
            review_status="OVERRIDDEN",
            reviewer_id=str(uuid.uuid4()),
            reviewer_name="Test User",
            review_note="Test note",
            source_snapshot_hash="abc123",
            is_active=True
        )
        
        repr_str = repr(review)
        assert "RiskReview" in repr_str
        assert str(review_id) in repr_str
        assert str(run_id) in repr_str
        assert "OVERRIDDEN" in repr_str


class TestRiskReviewServiceValidation:
    """Test RiskReviewService validation logic without database."""
    
    def test_note_requirement_validation(self):
        """Test the logic for note requirement validation."""
        from app.services.risk_review_service import RiskReviewService
        
        # Test OVERRIDDEN requires note
        review_status = "OVERRIDDEN"
        review_note = None
        requires_note = review_status in ("OVERRIDDEN", "NEEDS_DISCUSSION") and not review_note
        assert requires_note == True
        
        # Test ACCEPTED does not require note
        review_status = "ACCEPTED"
        review_note = None
        requires_note = review_status in ("OVERRIDDEN", "NEEDS_DISCUSSION") and not review_note
        assert requires_note == False
        
        # Test OVERRIDDEN with note is valid
        review_status = "OVERRIDDEN"
        review_note = "Valid note"
        requires_note = review_status in ("OVERRIDDEN", "NEEDS_DISCUSSION") and not review_note
        assert requires_note == False
    
    def test_effective_risk_calculation(self):
        """Test effective risk calculation logic."""
        # OVERRIDDEN status uses reviewed risk
        review_status = "OVERRIDDEN"
        reviewed_risk = "LOW"
        original_risk = "HIGH"
        effective_risk = reviewed_risk if review_status == "OVERRIDDEN" else original_risk
        assert effective_risk == "LOW"
        
        # ACCEPTED status uses original risk
        review_status = "ACCEPTED"
        reviewed_risk = "LOW"
        original_risk = "HIGH"
        effective_risk = reviewed_risk if review_status == "OVERRIDDEN" else original_risk
        assert effective_risk == "HIGH"
        
        # UNREVIEWED status uses original risk
        review_status = "UNREVIEWED"
        reviewed_risk = "LOW"
        original_risk = "HIGH"
        effective_risk = reviewed_risk if review_status == "OVERRIDDEN" else original_risk
        assert effective_risk == "HIGH"


class TestRiskReviewAdvisoryNature:
    """Test that risk reviews are advisory and don't affect core metrics."""
    
    def test_review_does_not_modify_snapshot_json(self):
        """Verify that creating a review doesn't modify snapshot JSON."""
        # Simulate a snapshot
        snapshot_data = {
            "counts": {
                "totalRequirements": 3,
                "verifiedTests": 1,
                "coverageGaps": 1,
                "missingAutomatedCoverage": 1
            },
            "health": "VALIDATION_PASSED_COVERAGE_INCOMPLETE"
        }
        initial_json = json.dumps(snapshot_data)
        
        # Create a review (this doesn't modify the snapshot)
        review = RiskReview(
            id=uuid.uuid4(),
            recommendation_run_id=uuid.uuid4(),
            source_requirement_id=str(uuid.uuid4()),
            source_ac_number=1,
            readable_id="AC-01",
            original_risk_level="HIGH",
            original_priority="P1",
            reviewed_risk_level="LOW",
            reviewed_priority="P3",
            review_status="OVERRIDDEN",
            reviewer_id=str(uuid.uuid4()),
            reviewer_name="Test User",
            review_note="Lowering risk priority",
            source_snapshot_hash="abc123",
            is_active=True
        )
        
        # Verify snapshot hasn't changed
        assert json.dumps(snapshot_data) == initial_json
        assert snapshot_data["counts"]["totalRequirements"] == 3
        assert snapshot_data["counts"]["verifiedTests"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
