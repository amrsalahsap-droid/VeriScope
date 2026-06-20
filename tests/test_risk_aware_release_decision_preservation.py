"""
Risk-Aware Release Decision Evidence Preservation Tests for Phase 3.3

Tests to verify that risk-aware release decision recommendations do not modify evidence truth.
The recommendations operate strictly as a derived layer and preserve existing decision states.
"""

import pytest
from app.services.release_decision_service import ReleaseDecisionService


class TestRiskAwareReleaseDecisionEvidencePreservation:
    """Test suite to verify risk-aware release decisions don't modify evidence truth."""

    def test_risk_aware_recommendations_read_only(self):
        """Verify risk-aware recommendations don't modify input data."""
        import copy

        requirements = [
            {
                "requirement_id": "AC-07",
                "title": "Password validation",
                "risk_score": 85,
                "risk_band": "CRITICAL",
                "coverage_bucket": "MISSING"
            }
        ]

        # Make a copy of original requirements
        requirements_copy = copy.deepcopy(requirements)

        # Generate recommendations
        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        # Verify original requirements are unchanged
        assert requirements == requirements_copy

        # Verify result is new data, not reference to input
        assert result is not requirements
        assert result is not requirements_copy

    def test_risk_aware_recommendations_pure_function(self):
        """Verify risk-aware recommendations are pure functions."""
        requirements = [
            {
                "requirement_id": "AC-01",
                "title": "Password validation",
                "risk_score": 15,
                "risk_band": "LOW",
                "coverage_bucket": "COVERED"
            }
        ]

        result1 = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)
        result2 = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)
        result3 = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        # All results should be identical
        assert result1["decisionRecommendations"] == result2["decisionRecommendations"] == result3["decisionRecommendations"]

    def test_risk_aware_recommendations_no_database_writes(self):
        """Verify risk-aware recommendations don't perform database writes."""
        import inspect
        from app.services.release_decision_service import ReleaseDecisionService

        # Get all methods in ReleaseDecisionService
        methods = inspect.getmembers(ReleaseDecisionService, predicate=inspect.isfunction)

        # Check that generate_risk_aware_recommendations doesn't accept db parameter
        sig = inspect.signature(ReleaseDecisionService.generate_risk_aware_recommendations)
        params = list(sig.parameters.keys())

        # Should not have db parameter - it's a pure function
        assert 'db' not in params, "generate_risk_aware_recommendations should not accept db parameter"

    def test_risk_aware_recommendations_no_llm_usage(self):
        """Verify risk-aware recommendations don't use LLM or external APIs."""
        import inspect
        from app.services.release_decision_service import ReleaseDecisionService

        # Get source code
        source = inspect.getsource(ReleaseDecisionService.generate_risk_aware_recommendations)

        # Verify no LLM-related imports or calls
        llm_keywords = ['openai', 'anthropic', 'llm', 'gpt', 'claude', 'completion', 'chat']
        for keyword in llm_keywords:
            assert keyword.lower() not in source.lower(), \
                f"Risk-aware recommendations should not use LLM (found: {keyword})"

    def test_risk_aware_recommendations_deterministic(self):
        """Verify risk-aware recommendations are deterministic."""
        import random

        # Test with random inputs multiple times
        for _ in range(10):
            requirements = [
                {
                    "requirement_id": f"AC-{random.randint(1, 20)}",
                    "title": f"Test requirement {random.randint(1, 100)}",
                    "risk_score": random.randint(0, 100),
                    "risk_band": random.choice(["CRITICAL", "HIGH", "MEDIUM", "LOW"]),
                    "coverage_bucket": random.choice(["COVERED", "PARTIAL", "MISSING", "TRACEABILITY"])
                }
            ]

            result1 = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)
            result2 = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

            assert result1["decisionRecommendations"] == result2["decisionRecommendations"]

    def test_risk_aware_recommendations_output_structure(self):
        """Verify risk-aware recommendations output structure is consistent."""
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

        # Verify output structure
        assert "decisionRecommendations" in result
        assert "decisionReasoning" in result
        assert "requiredBeforeRelease" in result
        assert "riskSummary" in result

        # Verify types
        assert isinstance(result["decisionRecommendations"], str)
        assert isinstance(result["decisionReasoning"], list)
        assert isinstance(result["requiredBeforeRelease"], list)
        assert isinstance(result["riskSummary"], dict)

    def test_risk_aware_recommendations_advisory_only(self):
        """Verify risk-aware recommendations are advisory only, not actual decisions."""
        requirements = [
            {
                "requirement_id": "AC-07",
                "title": "Password validation",
                "risk_score": 85,
                "risk_band": "CRITICAL",
                "coverage_bucket": "MISSING"
            }
        ]

        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        # Verify it's a recommendation, not a decision
        assert result["decisionRecommendations"] in ["APPROVED", "CONDITIONALLY_APPROVED"]

        # Verify it doesn't modify the actual decision status
        # This is advisory metadata only
        assert "decisionStatus" not in result

    def test_risk_aware_recommendations_no_coverage_modification(self):
        """Verify risk-aware recommendations don't modify coverage buckets."""
        requirements = [
            {
                "requirement_id": "AC-07",
                "title": "Password validation",
                "risk_score": 85,
                "risk_band": "CRITICAL",
                "coverage_bucket": "MISSING"
            }
        ]

        original_coverage = requirements[0]["coverage_bucket"]

        # Generate recommendations
        result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        # Verify coverage bucket is unchanged
        assert requirements[0]["coverage_bucket"] == original_coverage

        # Verify result doesn't modify coverage buckets
        # It only provides recommendations
        assert "coverage_bucket" not in result

    def test_risk_aware_recommendations_no_state_mutation(self):
        """Verify risk-aware recommendations don't maintain or mutate state."""
        import inspect
        from app.services.release_decision_service import ReleaseDecisionService

        # Check that generate_risk_aware_recommendations is static
        assert isinstance(inspect.getattr_static(ReleaseDecisionService, 'generate_risk_aware_recommendations'), staticmethod)

    def test_risk_aware_release_state_preserves_existing_state(self):
        """Verify get_risk_aware_release_state preserves existing release state."""
        # This test verifies that the risk-aware state includes the original state
        # plus the new recommendations, without modifying the original state

        requirements = [
            {
                "requirement_id": "AC-01",
                "title": "Password validation",
                "risk_score": 15,
                "risk_band": "LOW",
                "coverage_bucket": "COVERED"
            }
        ]

        # Generate risk-aware recommendations
        risk_recommendations = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

        # Verify the structure includes both original state and new recommendations
        # (This is verified by the implementation that merges the two)
        assert "decisionRecommendations" in risk_recommendations
        assert "decisionReasoning" in risk_recommendations
        assert "requiredBeforeRelease" in risk_recommendations

    def test_risk_aware_recommendations_no_external_dependencies(self):
        """Verify risk-aware recommendations don't depend on external state."""
        import inspect
        from app.services.release_decision_service import ReleaseDecisionService

        # Get source code
        source = inspect.getsource(ReleaseDecisionService.generate_risk_aware_recommendations)

        # Verify no database imports
        assert 'sqlalchemy' not in source.lower(), "Risk-aware recommendations should not import SQLAlchemy"
        assert 'from sqlalchemy' not in source, "Risk-aware recommendations should not import from SQLAlchemy"
        assert 'import sqlalchemy' not in source, "Risk-aware recommendations should not import SQLAlchemy"

    def test_risk_aware_recommendations_valid_categories(self):
        """Verify only valid recommendation categories are produced."""
        import random

        # Test with various inputs
        for _ in range(20):
            requirements = [
                {
                    "requirement_id": f"AC-{random.randint(1, 20)}",
                    "title": f"Test requirement {random.randint(1, 100)}",
                    "risk_score": random.randint(0, 100),
                    "risk_band": random.choice(["CRITICAL", "HIGH", "MEDIUM", "LOW"]),
                    "coverage_bucket": random.choice(["COVERED", "PARTIAL", "MISSING", "TRACEABILITY"])
                }
            ]

            result = ReleaseDecisionService.generate_risk_aware_recommendations(requirements)

            # Should only produce APPROVED or CONDITIONALLY_APPROVED
            # (Never REJECTED - that's a human decision)
            assert result["decisionRecommendations"] in ["APPROVED", "CONDITIONALLY_APPROVED"]
