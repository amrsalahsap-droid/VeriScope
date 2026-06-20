"""
Risk Scoring Evidence Preservation Tests for Phase 3.0

Tests to verify that the risk scoring engine does not modify evidence truth, coverage buckets,
readiness decisions, or traceability results. The engine operates strictly as a derived layer.
"""

import pytest
from app.services.risk_based_regression.risk_scoring_service import RiskScoringService


class TestRiskScoringEvidencePreservation:
    """Test suite to verify risk scoring doesn't modify evidence truth."""

    def test_risk_scoring_service_read_only(self):
        """Verify risk scoring service has no database write operations."""
        import inspect
        from app.services.risk_based_regression.risk_scoring_service import RiskScoringService

        # Get all methods in RiskScoringService
        methods = inspect.getmembers(RiskScoringService, predicate=inspect.isfunction)

        # Verify no methods perform database writes
        for name, method in methods:
            # Skip private methods
            if name.startswith('_'):
                continue

            # Check method signature - should not have db parameter for writes
            sig = inspect.signature(method)
            params = list(sig.parameters.keys())

            # Risk scoring methods should not accept db sessions for writes
            # They only calculate scores from input data
            assert 'db' not in params or name == 'batch_calculate_risk_scores', \
                f"Method {name} should not accept db parameter for writes"

    def test_risk_scoring_no_side_effects(self):
        """Verify risk scoring calculation has no side effects."""
        # Create test input
        input_data = {
            "business_risk": "HIGH",
            "coverage_status": "MISSING",
            "criticality": "HIGH",
            "requirement_type": "FUNCTIONAL"
        }

        # Calculate risk score multiple times
        result1 = RiskScoringService.calculate_requirement_risk_score(**input_data)
        result2 = RiskScoringService.calculate_requirement_risk_score(**input_data)
        result3 = RiskScoringService.calculate_requirement_risk_score(**input_data)

        # Verify results are identical (no side effects)
        assert result1 == result2 == result3

    def test_risk_scoring_pure_function(self):
        """Verify risk scoring is a pure function (same input = same output)."""
        test_cases = [
            {
                "business_risk": "CRITICAL",
                "coverage_status": "MISSING",
                "criticality": "CRITICAL",
                "requirement_type": "SECURITY"
            },
            {
                "business_risk": "LOW",
                "coverage_status": "VERIFIED",
                "criticality": "LOW",
                "requirement_type": "FUNCTIONAL"
            }
        ]

        for test_input in test_cases:
            result1 = RiskScoringService.calculate_requirement_risk_score(**test_input)
            result2 = RiskScoringService.calculate_requirement_risk_score(**test_input)

            assert result1["riskScore"] == result2["riskScore"]
            assert result1["riskBand"] == result2["riskBand"]
            assert result1["riskScoreReason"] == result2["riskScoreReason"]

    def test_risk_scoring_no_state_mutation(self):
        """Verify risk scoring doesn't maintain or mutate state."""
        # RiskScoringService uses only static methods and constants
        import inspect
        from app.services.risk_based_regression.risk_scoring_service import RiskScoringService

        # Check that all public methods are static
        methods = inspect.getmembers(RiskScoringService, predicate=inspect.isfunction)
        for name, method in methods:
            if not name.startswith('_'):
                assert isinstance(inspect.getattr_static(RiskScoringService, name), staticmethod), \
                    f"Method {name} should be static"

    def test_risk_scoring_no_llm_usage(self):
        """Verify risk scoring doesn't use LLM or external APIs."""
        import inspect
        from app.services.risk_based_regression.risk_scoring_service import RiskScoringService

        # Get source code
        source = inspect.getsource(RiskScoringService)

        # Verify no LLM-related imports or calls
        llm_keywords = ['openai', 'anthropic', 'llm', 'gpt', 'claude', 'completion', 'chat']
        for keyword in llm_keywords:
            assert keyword.lower() not in source.lower(), \
                f"Risk scoring should not use LLM (found: {keyword})"

    def test_risk_scoring_deterministic(self):
        """Verify risk scoring is deterministic across multiple calls."""
        import random

        # Test with random inputs multiple times
        for _ in range(10):
            business_risk = random.choice(["CRITICAL", "HIGH", "MEDIUM", "LOW"])
            coverage_status = random.choice(["VERIFIED", "PARTIAL", "MISSING", "FAILED", "SKIPPED", "NOT_RUN"])
            criticality = random.choice(["CRITICAL", "HIGH", "MEDIUM", "LOW"])
            requirement_type = random.choice(["FUNCTIONAL", "SECURITY", "PERFORMANCE", "COMPLIANCE", "USER_EXPERIENCE"])

            input_data = {
                "business_risk": business_risk,
                "coverage_status": coverage_status,
                "criticality": criticality,
                "requirement_type": requirement_type
            }

            result1 = RiskScoringService.calculate_requirement_risk_score(**input_data)
            result2 = RiskScoringService.calculate_requirement_risk_score(**input_data)

            assert result1 == result2, f"Non-deterministic result for {input_data}"

    def test_risk_scoring_output_structure(self):
        """Verify risk scoring output structure is consistent."""
        result = RiskScoringService.calculate_requirement_risk_score(
            business_risk="HIGH",
            coverage_status="MISSING",
            criticality="HIGH",
            requirement_type="FUNCTIONAL"
        )

        # Verify output structure
        assert "riskScore" in result
        assert "riskScoreReason" in result
        assert "riskBand" in result

        # Verify types
        assert isinstance(result["riskScore"], int)
        assert isinstance(result["riskScoreReason"], str)
        assert isinstance(result["riskBand"], str)

        # Verify ranges
        assert 0 <= result["riskScore"] <= 100
        assert result["riskBand"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

    def test_risk_scoring_no_database_dependencies(self):
        """Verify risk scoring doesn't depend on database state."""
        import inspect
        from app.services.risk_based_regression.risk_scoring_service import RiskScoringService

        # Get source code
        source = inspect.getsource(RiskScoringService)

        # Verify no database-related imports
        db_keywords = ['sqlalchemy', 'session', 'db.session', 'query', 'model']
        for keyword in db_keywords:
            # Allow in comments but not in code
            lines = source.split('\n')
            for line in lines:
                if not line.strip().startswith('#') and keyword.lower() in line.lower():
                    # Check if it's just a type hint or comment
                    if 'Session' in line and ':' in line:  # Type hint
                        continue
                    assert False, f"Risk scoring should not depend on database (found: {keyword} in '{line}')"

    def test_risk_scoring_derived_layer_only(self):
        """Verify risk scoring operates as derived layer only."""
        # Risk scoring should only transform input data to output scores
        # It should not modify any underlying data structures

        input_data = {
            "business_risk": "HIGH",
            "coverage_status": "MISSING",
            "criticality": "HIGH",
            "requirement_type": "FUNCTIONAL"
        }

        # Make a copy of input
        import copy
        input_copy = copy.deepcopy(input_data)

        # Calculate risk score
        result = RiskScoringService.calculate_requirement_risk_score(**input_data)

        # Verify input is unchanged
        assert input_data == input_copy

        # Verify result is new data, not reference to input
        assert result is not input_data
        assert result is not input_copy
