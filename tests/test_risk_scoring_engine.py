"""
Risk Scoring Engine Tests for Phase 3.0

Tests for the deterministic risk scoring engine that prioritizes requirements, gaps, and
regression scope candidates without modifying evidence truth, coverage buckets, readiness
decisions, or traceability results.
"""

import pytest
from app.services.risk_based_regression.risk_scoring_service import (
    RiskScoringService,
    RiskBand,
    CoverageStatus,
    RequirementCriticality,
    BusinessRisk,
    RequirementType
)


class TestRiskScoringService:
    """Test suite for RiskScoringService."""

    def test_critical_missing_scores_high(self):
        """Verify critical + missing AC scores higher than partial medium AC."""
        result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="CRITICAL",
            coverage_status="MISSING",
            criticality="CRITICAL",
            requirement_type="FUNCTIONAL"
        )

        assert result["riskScore"] >= 95
        assert result["riskBand"] == RiskBand.CRITICAL.value
        assert "CRITICAL" in result["riskScoreReason"]
        assert "MISSING" in result["riskScoreReason"]

    def test_partial_medium_scores_moderate(self):
        """Verify partial + medium AC scores in moderate range."""
        result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="MEDIUM",
            coverage_status="PARTIAL",
            criticality="MEDIUM",
            requirement_type="FUNCTIONAL"
        )

        assert 50 <= result["riskScore"] <= 70
        assert result["riskBand"] in [RiskBand.HIGH.value, RiskBand.MEDIUM.value]
        assert "MEDIUM" in result["riskScoreReason"]
        assert "PARTIAL" in result["riskScoreReason"]

    def test_verified_low_scores_low(self):
        """Verify verified requirements remain low risk."""
        result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="LOW",
            coverage_status="VERIFIED",
            criticality="LOW",
            requirement_type="FUNCTIONAL"
        )

        assert result["riskScore"] <= 20
        assert result["riskBand"] == RiskBand.LOW.value
        assert "LOW" in result["riskScoreReason"]
        assert "VERIFIED" in result["riskScoreReason"]

    def test_security_type_multiplier(self):
        """Verify security requirements have higher risk multiplier."""
        functional_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="HIGH",
            coverage_status="MISSING",
            criticality="HIGH",
            requirement_type="FUNCTIONAL"
        )

        security_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="HIGH",
            coverage_status="MISSING",
            criticality="HIGH",
            requirement_type="SECURITY"
        )

        assert security_result["riskScore"] > functional_result["riskScore"]

    def test_risk_review_adjustment(self):
        """Verify risk reviews adjust effective score."""
        base_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="HIGH",
            coverage_status="MISSING",
            criticality="HIGH",
            requirement_type="FUNCTIONAL",
            risk_review_adjustment=None
        )

        adjusted_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="HIGH",
            coverage_status="MISSING",
            criticality="HIGH",
            requirement_type="FUNCTIONAL",
            risk_review_adjustment=-10
        )

        assert adjusted_result["riskScore"] == base_result["riskScore"] - 10
        assert "Review Adjustment: -10" in adjusted_result["riskScoreReason"]

    def test_score_clamping(self):
        """Verify scores are clamped to 0-100 range."""
        # Test upper bound
        high_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="CRITICAL",
            coverage_status="MISSING",
            criticality="CRITICAL",
            requirement_type="SECURITY",
            risk_review_adjustment=50  # Should push over 100
        )

        assert high_result["riskScore"] <= 100

        # Test lower bound
        low_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="LOW",
            coverage_status="VERIFIED",
            criticality="LOW",
            requirement_type="USER_EXPERIENCE",
            risk_review_adjustment=-50  # Should push below 0
        )

        assert low_result["riskScore"] >= 0

    def test_risk_band_thresholds(self):
        """Verify risk band thresholds are correct."""
        critical_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="CRITICAL",
            coverage_status="MISSING",
            criticality="CRITICAL",
            requirement_type="SECURITY"
        )
        assert critical_result["riskBand"] == RiskBand.CRITICAL.value

        high_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="HIGH",
            coverage_status="MISSING",
            criticality="HIGH",
            requirement_type="FUNCTIONAL"
        )
        assert high_result["riskBand"] in [RiskBand.CRITICAL.value, RiskBand.HIGH.value]

        medium_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="MEDIUM",
            coverage_status="PARTIAL",
            criticality="MEDIUM",
            requirement_type="FUNCTIONAL"
        )
        assert medium_result["riskBand"] in [RiskBand.HIGH.value, RiskBand.MEDIUM.value]

        low_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="LOW",
            coverage_status="VERIFIED",
            criticality="LOW",
            requirement_type="FUNCTIONAL"
        )
        assert low_result["riskBand"] == RiskBand.LOW.value

    def test_invalid_input_defaults_to_low_risk(self):
        """Verify invalid input defaults to low risk."""
        result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="INVALID",
            coverage_status="INVALID",
            criticality="INVALID",
            requirement_type="INVALID"
        )

        assert result["riskScore"] == 0
        assert result["riskBand"] == RiskBand.LOW.value
        assert "Invalid input" in result["riskScoreReason"]

    def test_gap_risk_score(self):
        """Verify gap risk score calculation."""
        result = RiskScoringService.calculate_gap_risk_score(
            business_risk="HIGH",
            criticality="HIGH",
            requirement_type="FUNCTIONAL"
        )

        # Gaps should always use MISSING coverage
        assert "MISSING" in result["riskScoreReason"]
        assert result["riskScore"] > 0

    def test_batch_calculation(self):
        """Verify batch risk score calculation."""
        requirements = [
            {
                "id": "req-1",
                "business_risk": "CRITICAL",
                "coverage_status": "MISSING",
                "criticality": "CRITICAL",
                "requirement_type": "FUNCTIONAL"
            },
            {
                "id": "req-2",
                "business_risk": "LOW",
                "coverage_status": "VERIFIED",
                "criticality": "LOW",
                "requirement_type": "FUNCTIONAL"
            }
        ]

        results = RiskScoringService.batch_calculate_risk_scores(requirements)

        assert len(results) == 2
        assert results[0]["requirement_id"] == "req-1"
        assert results[1]["requirement_id"] == "req-2"
        assert results[0]["riskScore"] > results[1]["riskScore"]

    def test_risk_explanation(self):
        """Verify risk explanation generation."""
        explanation = RiskScoringService.get_risk_explanation(95, "CRITICAL")
        assert "Critical risk" in explanation
        assert "95/100" in explanation
        assert "Immediate attention required" in explanation

        explanation = RiskScoringService.get_risk_explanation(15, "LOW")
        assert "Low risk" in explanation
        assert "15/100" in explanation
        assert "Adequate coverage" in explanation

    def test_deterministic_scoring(self):
        """Verify scoring is deterministic (same inputs = same outputs)."""
        inputs = {
            "business_risk": "HIGH",
            "coverage_status": "MISSING",
            "criticality": "HIGH",
            "requirement_type": "FUNCTIONAL"
        }

        result1 = RiskScoringService.calculate_requirement_risk_score(**inputs)
        result2 = RiskScoringService.calculate_requirement_risk_score(**inputs)

        assert result1["riskScore"] == result2["riskScore"]
        assert result1["riskBand"] == result2["riskBand"]
        assert result1["riskScoreReason"] == result2["riskScoreReason"]

    def test_compliance_type_multiplier(self):
        """Verify compliance requirements have higher risk multiplier."""
        functional_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="HIGH",
            coverage_status="MISSING",
            criticality="HIGH",
            requirement_type="FUNCTIONAL"
        )

        compliance_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="HIGH",
            coverage_status="MISSING",
            criticality="HIGH",
            requirement_type="COMPLIANCE"
        )

        assert compliance_result["riskScore"] > functional_result["riskScore"]

    def test_failed_coverage_penalty(self):
        """Verify failed coverage has penalty."""
        failed_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="HIGH",
            coverage_status="FAILED",
            criticality="HIGH",
            requirement_type="FUNCTIONAL"
        )

        skipped_result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="HIGH",
            coverage_status="SKIPPED",
            criticality="HIGH",
            requirement_type="FUNCTIONAL"
        )

        assert failed_result["riskScore"] > skipped_result["riskScore"]

    def test_not_run_coverage_score(self):
        """Verify not_run coverage has moderate risk."""
        result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="MEDIUM",
            coverage_status="NOT_RUN",
            criticality="MEDIUM",
            requirement_type="FUNCTIONAL"
        )

        assert result["riskScore"] > 0
        assert result["riskScore"] < 50  # Should be moderate
