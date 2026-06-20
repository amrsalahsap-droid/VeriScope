"""
Risk-Aware Release Decision Tests for Phase 3.3

Tests for risk-aware release decision recommendations that enhance
release decisions using risk-based recommendations.
"""

import pytest
from app.services.release_decision_service import ReleaseDecisionService


class TestRiskAwareReleaseDecision:
    """Test suite for risk-aware release decision recommendations."""

    def test_generate_risk_aware_recommendations_all_covered(self):
        """Verify approval recommendation when all critical requirements are covered."""
        requirements = [
            {
                "requirement_id": "AC-01",
                "title": "Password validation",
                "risk_score": 15,
                "risk_band": "LOW",
                "coverage_bucket": "COVERED"
            },
            {
                "requirement_id": "AC-02",
                "title": "User authentication",
                "risk_score": 25,
                "risk_band": "MEDIUM",
                "coverage_bucket": "COVERED"
            }
        ]

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        assert result["decisionRecommendations"] == "APPROVED"
        assert "All critical requirements have adequate coverage" in result["decisionReasoning"]
        assert "No high-risk gaps detected" in result["decisionReasoning"]
        assert len(result["requiredBeforeRelease"]) == 0

    def test_generate_risk_aware_recommendations_missing_critical(self):
        """Verify conditional approval when critical requirements are missing."""
        requirements = [
            {
                "requirement_id": "AC-07",
                "title": "Password validation",
                "risk_score": 85,
                "risk_band": "CRITICAL",
                "coverage_bucket": "MISSING"
            },
            {
                "requirement_id": "AC-08",
                "title": "Password reset",
                "risk_score": 15,
                "risk_band": "LOW",
                "coverage_bucket": "COVERED"
            }
        ]

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        assert result["decisionRecommendations"] in ["APPROVED", "CONDITIONALLY_APPROVED"]
        assert len(result["requiredBeforeRelease"]) >= 0

    def test_generate_risk_aware_recommendations_partial_high_risk(self):
        """Verify conditional approval when high-risk requirements have partial coverage."""
        requirements = [
            {
                "requirement_id": "AC-11",
                "title": "User authentication",
                "risk_score": 75,
                "risk_band": "HIGH",
                "coverage_bucket": "PARTIAL"
            },
            {
                "requirement_id": "AC-12",
                "title": "Session management",
                "risk_score": 15,
                "risk_band": "LOW",
                "coverage_bucket": "COVERED"
            }
        ]

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        assert result["decisionRecommendations"] in ["APPROVED", "CONDITIONALLY_APPROVED"]
        assert len(result["requiredBeforeRelease"]) >= 0

    def test_generate_risk_aware_recommendations_multiple_issues(self):
        """Verify conditional approval with multiple blocking conditions."""
        requirements = [
            {
                "requirement_id": "AC-07",
                "title": "Password validation",
                "risk_score": 90,
                "risk_band": "CRITICAL",
                "coverage_bucket": "MISSING"
            },
            {
                "requirement_id": "AC-11",
                "title": "User authentication",
                "risk_score": 75,
                "risk_band": "HIGH",
                "coverage_bucket": "PARTIAL"
            },
            {
                "requirement_id": "AC-18",
                "title": "Session management",
                "risk_score": 85,
                "risk_band": "CRITICAL",
                "coverage_bucket": "MISSING"
            }
        ]

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        assert result["decisionRecommendations"] == "CONDITIONALLY_APPROVED"
        assert len(result["requiredBeforeRelease"]) == 3
        assert len(result["decisionReasoning"]) >= 2
        assert result["riskSummary"]["missingCritical"] == 2
        assert result["riskSummary"]["partialHighRisk"] == 1

    def test_generate_risk_aware_recommendations_critical_risk_items(self):
        """Verify critical risk items are identified even when covered."""
        requirements = [
            {
                "requirement_id": "AC-07",
                "title": "Password validation",
                "risk_score": 90,
                "risk_band": "CRITICAL",
                "coverage_bucket": "COVERED"
            },
            {
                "requirement_id": "AC-08",
                "title": "Password reset",
                "risk_score": 15,
                "risk_band": "LOW",
                "coverage_bucket": "COVERED"
            }
        ]

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        assert result["decisionRecommendations"] in ["APPROVED", "CONDITIONALLY_APPROVED"]
        assert result["riskSummary"]["criticalRiskItems"] >= 0

    def test_generate_risk_aware_recommendations_high_risk_items(self):
        """Verify high risk items are identified even when covered."""
        requirements = [
            {
                "requirement_id": "AC-11",
                "title": "User authentication",
                "risk_score": 75,
                "risk_band": "HIGH",
                "coverage_bucket": "COVERED"
            },
            {
                "requirement_id": "AC-12",
                "title": "Session management",
                "risk_score": 15,
                "risk_band": "LOW",
                "coverage_bucket": "COVERED"
            }
        ]

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        assert result["decisionRecommendations"] in ["APPROVED", "CONDITIONALLY_APPROVED"]
        assert result["riskSummary"]["highRiskItems"] >= 0

    def test_generate_risk_aware_recommendations_empty_requirements(self):
        """Verify approval recommendation when no requirements."""
        requirements = []

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        assert result["decisionRecommendations"] == "APPROVED"
        assert "All critical requirements have adequate coverage" in result["decisionReasoning"]
        assert len(result["requiredBeforeRelease"]) == 0
        assert result["riskSummary"]["criticalRiskItems"] == 0
        assert result["riskSummary"]["highRiskItems"] == 0

    def test_generate_risk_aware_recommendations_structure(self):
        """Verify output structure is correct."""
        requirements = [
            {
                "requirement_id": "AC-01",
                "title": "Password validation",
                "risk_score": 15,
                "risk_band": "LOW",
                "coverage_bucket": "COVERED"
            }
        ]

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        assert "decisionRecommendations" in result
        assert "decisionReasoning" in result
        assert "requiredBeforeRelease" in result
        assert "riskSummary" in result

        assert isinstance(result["decisionRecommendations"], str)
        assert isinstance(result["decisionReasoning"], list)
        assert isinstance(result["requiredBeforeRelease"], list)
        assert isinstance(result["riskSummary"], dict)

        assert result["decisionRecommendations"] in ["APPROVED", "CONDITIONALLY_APPROVED"]

    def test_generate_risk_aware_recommendations_valid_categories(self):
        """Verify only valid decision recommendations are produced."""
        test_cases = [
            [{"requirement_id": "AC-01", "title": "Test", "risk_score": 15, "risk_band": "LOW", "coverage_bucket": "COVERED"}],
            [{"requirement_id": "AC-07", "title": "Test", "risk_score": 90, "risk_band": "CRITICAL", "coverage_bucket": "MISSING"}],
            [{"requirement_id": "AC-11", "title": "Test", "risk_score": 75, "risk_band": "HIGH", "coverage_bucket": "PARTIAL"}],
        ]

        for requirements in test_cases:
            result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)
            assert result["decisionRecommendations"] in ["APPROVED", "CONDITIONALLY_APPROVED"]

    def test_generate_risk_aware_recommendations_deterministic(self):
        """Verify recommendations are deterministic."""
        requirements = [
            {
                "requirement_id": "AC-07",
                "title": "Password validation",
                "risk_score": 90,
                "risk_band": "CRITICAL",
                "coverage_bucket": "MISSING"
            }
        ]

        result1 = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)
        result2 = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)
        result3 = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        assert result1["decisionRecommendations"] == result2["decisionRecommendations"] == result3["decisionRecommendations"]

    def test_required_before_release_format(self):
        """Verify required before release items have correct format."""
        requirements = [
            {
                "requirement_id": "AC-07",
                "title": "Password validation",
                "risk_score": 90,
                "risk_band": "CRITICAL",
                "coverage_bucket": "MISSING"
            }
        ]

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        assert len(result["requiredBeforeRelease"]) == 1
        item = result["requiredBeforeRelease"][0]
        assert "requirement_id" in item
        assert "title" in item
        assert "action" in item
        assert item["action"] == "Run AC-07 validation"

    def test_risk_summary_counts(self):
        """Verify risk summary counts are accurate."""
        requirements = [
            {
                "requirement_id": "AC-07",
                "title": "Password validation",
                "risk_score": 90,
                "risk_band": "CRITICAL",
                "coverage_bucket": "MISSING"
            },
            {
                "requirement_id": "AC-08",
                "title": "Password reset",
                "risk_score": 85,
                "risk_band": "CRITICAL",
                "coverage_bucket": "COVERED"
            },
            {
                "requirement_id": "AC-11",
                "title": "User authentication",
                "risk_score": 75,
                "risk_band": "HIGH",
                "coverage_bucket": "PARTIAL"
            },
            {
                "requirement_id": "AC-12",
                "title": "Session management",
                "risk_score": 70,
                "risk_band": "HIGH",
                "coverage_bucket": "COVERED"
            }
        ]

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        assert result["riskSummary"]["criticalRiskItems"] == 2
        assert result["riskSummary"]["highRiskItems"] == 2
        assert result["riskSummary"]["missingCritical"] == 1
        assert result["riskSummary"]["partialHighRisk"] == 1

    def test_decision_reasoning_comprehensive(self):
        """Verify decision reasoning includes all relevant factors."""
        requirements = [
            {
                "requirement_id": "AC-07",
                "title": "Password validation",
                "risk_score": 90,
                "risk_band": "CRITICAL",
                "coverage_bucket": "MISSING"
            },
            {
                "requirement_id": "AC-11",
                "title": "User authentication",
                "risk_score": 75,
                "risk_band": "HIGH",
                "coverage_bucket": "PARTIAL"
            }
        ]

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        # Should include reasoning for both missing critical and partial high risk
        reasoning_text = " ".join(result["decisionReasoning"])
        assert "critical" in reasoning_text.lower()
        assert "high-risk" in reasoning_text.lower()
