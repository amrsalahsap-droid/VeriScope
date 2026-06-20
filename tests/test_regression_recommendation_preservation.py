"""
Regression Recommendation Evidence Preservation Tests for Phase 3.2

Tests to verify that the regression recommendation engine does not modify evidence truth.
The engine operates strictly as a derived layer and preserves existing coverage buckets.
"""

import pytest
import random
from app.services.regression_recommendation_engine import RegressionRecommendationEngine


class TestRegressionRecommendationEvidencePreservation:
    """Test suite to verify regression recommendations don't modify evidence truth."""

    def test_regression_recommendation_service_read_only(self):
        """Verify regression recommendation service has no database write operations."""
        import inspect
        from app.services.regression_recommendation_engine import RegressionRecommendationEngine

        # Get all methods in RegressionRecommendationEngine
        methods = inspect.getmembers(RegressionRecommendationEngine, predicate=inspect.isfunction)

        # Verify no methods perform database writes
        for name, method in methods:
            # Skip private methods
            if name.startswith('_'):
                continue

            # Check method signature - should not have db parameter for writes
            sig = inspect.signature(method)
            params = list(sig.parameters.keys())

            # Regression recommendation methods should not accept db sessions for writes
            # They only calculate categories from input data
            assert 'db' not in params, f"Method {name} should not accept db parameter for writes"

    def test_regression_recommendation_pure_function(self):
        """Verify regression recommendation is a pure function (same input = same output)."""
        test_cases = [
            {
                "coverage_bucket": "MISSING",
                "risk_score": 85,
                "risk_band": "CRITICAL",
                "change_impact_level": "DIRECT",
                "is_verified": False
            },
            {
                "coverage_bucket": "COVERED",
                "risk_score": 15,
                "risk_band": "LOW",
                "change_impact_level": "NONE",
                "is_verified": True
            }
        ]

        for test_input in test_cases:
            result1 = RegressionRecommendationEngine.calculate_regression_category(**test_input)
            result2 = RegressionRecommendationEngine.calculate_regression_category(**test_input)

            assert result1["category"] == result2["category"]

    def test_regression_recommendation_no_state_mutation(self):
        """Verify regression recommendation doesn't maintain or mutate state."""
        # RegressionRecommendationEngine uses only static methods and constants
        import inspect
        from app.services.regression_recommendation_engine import RegressionRecommendationEngine

        # Check that all public methods are static
        methods = inspect.getmembers(RegressionRecommendationEngine, predicate=inspect.isfunction)
        for name, method in methods:
            if not name.startswith('_'):
                assert isinstance(inspect.getattr_static(RegressionRecommendationEngine, name), staticmethod), \
                    f"Method {name} should be static"

    def test_regression_recommendation_no_llm_usage(self):
        """Verify regression recommendation doesn't use LLM or external APIs."""
        import inspect
        from app.services.regression_recommendation_engine import RegressionRecommendationEngine

        # Get source code
        source = inspect.getsource(RegressionRecommendationEngine)

        # Verify no LLM-related imports or calls
        llm_keywords = ['openai', 'anthropic', 'llm', 'gpt', 'claude', 'completion', 'chat']
        for keyword in llm_keywords:
            assert keyword.lower() not in source.lower(), \
                f"Regression recommendation should not use LLM (found: {keyword})"

    def test_regression_recommendation_deterministic(self):
        """Verify regression recommendation is deterministic across multiple calls."""
        import random

        # Test with random inputs multiple times
        for _ in range(10):
            coverage = random.choice(["COVERED", "PARTIAL", "MISSING", "TRACEABILITY"])
            risk_score = random.randint(0, 100)
            risk_band = random.choice(["CRITICAL", "HIGH", "MEDIUM", "LOW"])
            impact = random.choice(["DIRECT", "RELATED", "INDIRECT", "NONE"])
            verified = random.choice([True, False])

            input_data = {
                "coverage_bucket": coverage,
                "risk_score": risk_score,
                "risk_band": risk_band,
                "change_impact_level": impact,
                "is_verified": verified
            }

            result1 = RegressionRecommendationEngine.calculate_regression_category(**input_data)
            result2 = RegressionRecommendationEngine.calculate_regression_category(**input_data)

            assert result1["category"] == result2["category"], f"Non-deterministic result for {input_data}"

    def test_regression_recommendation_output_structure(self):
        """Verify regression recommendation output structure is consistent."""
        result = RegressionRecommendationEngine.calculate_regression_category(
            coverage_bucket="MISSING",
            risk_score=75,
            risk_band="HIGH",
            change_impact_level="DIRECT",
            is_verified=False
        )

        # Verify output structure
        assert "category" in result
        assert "reason" in result
        assert "factors" in result

        # Verify types
        assert isinstance(result["category"], str)
        assert isinstance(result["reason"], str)
        assert isinstance(result["factors"], list)

        # Verify valid categories
        assert result["category"] in ["REQUIRED", "RECOMMENDED", "OPTIONAL", "SAFE_TO_SKIP"]

    def test_regression_recommendation_no_database_dependencies(self):
        """Verify regression recommendation doesn't depend on database state."""
        import inspect
        from app.services.regression_recommendation_engine import RegressionRecommendationEngine

        # Get source code
        source = inspect.getsource(RegressionRecommendationEngine)

        # Verify no SQLAlchemy imports
        assert 'sqlalchemy' not in source.lower(), "Regression recommendation should not import SQLAlchemy"
        assert 'from sqlalchemy' not in source, "Regression recommendation should not import from SQLAlchemy"
        assert 'import sqlalchemy' not in source, "Regression recommendation should not import SQLAlchemy"

    def test_regression_recommendation_derived_layer_only(self):
        """Verify regression recommendation operates as derived layer only."""
        # Regression recommendation should only transform input data to output categories
        # It should not modify any underlying data structures

        input_data = {
            "coverage_bucket": "MISSING",
            "risk_score": 75,
            "risk_band": "HIGH",
            "change_impact_level": "DIRECT",
            "is_verified": False
        }

        # Make a copy of input
        import copy
        input_copy = copy.deepcopy(input_data)

        # Calculate category
        result = RegressionRecommendationEngine.calculate_regression_category(**input_data)

        # Verify input is unchanged
        assert input_data == input_copy

        # Verify result is new data, not reference to input
        assert result is not input_data
        assert result is not input_copy

    def test_coverage_buckets_unchanged(self):
        """Verify original coverage buckets are never modified."""
        # Regression recommendation should preserve original coverage buckets
        # It should only add a new regression category

        requirements = [
            {
                "requirement_id": "AC-01",
                "coverage_bucket": "MISSING",
                "risk_score": 75,
                "risk_band": "HIGH",
                "change_impact_level": "DIRECT",
                "is_verified": False
            },
            {
                "requirement_id": "AC-02",
                "coverage_bucket": "COVERED",
                "risk_score": 15,
                "risk_band": "LOW",
                "change_impact_level": "NONE",
                "is_verified": True
            }
        ]

        # Make a copy of original coverage buckets
        original_buckets = {req["requirement_id"]: req["coverage_bucket"] for req in requirements}

        # Generate recommendations
        recommendations = RegressionRecommendationEngine.generate_regression_recommendations(requirements)

        # Verify original coverage buckets are preserved in all items
        for category_items in recommendations.values():
            for item in category_items:
                req_id = item["requirement_id"]
                assert item["coverage_bucket"] == original_buckets[req_id], \
                    f"Coverage bucket for {req_id} was modified"

    def test_no_coverage_bucket_modification_in_batch(self):
        """Verify coverage buckets are never modified in batch processing."""
        requirements = [
            {
                "requirement_id": f"AC-{i:02d}",
                "coverage_bucket": random.choice(["COVERED", "PARTIAL", "MISSING", "TRACEABILITY"]),
                "risk_score": random.randint(0, 100),
                "risk_band": random.choice(["CRITICAL", "HIGH", "MEDIUM", "LOW"]),
                "change_impact_level": random.choice(["DIRECT", "RELATED", "INDIRECT", "NONE"]),
                "is_verified": random.choice([True, False])
            }
            for i in range(1, 21)
        ]

        # Make a copy of original coverage buckets
        original_buckets = {req["requirement_id"]: req["coverage_bucket"] for req in requirements}

        # Generate recommendations
        recommendations = RegressionRecommendationEngine.generate_regression_recommendations(requirements)

        # Verify all original coverage buckets are preserved
        for category_items in recommendations.values():
            for item in category_items:
                req_id = item["requirement_id"]
                assert item["coverage_bucket"] == original_buckets[req_id], \
                    f"Coverage bucket for {req_id} was modified in batch processing"

    def test_optimization_does_not_modify_original_scope(self):
        """Verify scope optimization doesn't modify original scope."""
        import copy

        current_scope = [
            {"requirement_id": "AC-01", "title": "Requirement 1"},
            {"requirement_id": "AC-02", "title": "Requirement 2"}
        ]

        recommendations = {
            "requiredItems": [{"requirement_id": "AC-01", "title": "Requirement 1"}],
            "recommendedItems": [{"requirement_id": "AC-03", "title": "Requirement 3"}],
            "optionalItems": [],
            "safeToSkipItems": [{"requirement_id": "AC-02", "title": "Requirement 2"}]
        }

        # Make a copy of original scope
        original_scope = copy.deepcopy(current_scope)

        # Optimize scope
        optimization = RegressionRecommendationEngine.optimize_regression_scope(
            current_scope=current_scope,
            recommendations=recommendations
        )

        # Verify original scope is unchanged
        assert current_scope == original_scope

        # Verify optimized scope is a new list
        assert optimization["optimizedScope"] is not current_scope
