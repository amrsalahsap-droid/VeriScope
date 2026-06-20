"""
Optimization Metrics Evidence Preservation Tests for Phase 3.4

Tests to verify that optimization metrics and reporting do not modify evidence truth.
The optimization operates strictly as a derived layer and preserves existing AC counts.
"""

import pytest
import copy
from app.services.optimization_metrics_service import OptimizationMetricsService


class TestOptimizationMetricsEvidencePreservation:
    """Test suite to verify optimization metrics don't modify evidence truth."""

    def test_optimization_metrics_read_only(self):
        """Verify optimization metrics don't modify input data."""
        current_test_count = 18
        regression_recommendations = {
            "requiredItems": [{"requirement_id": "AC-01"}],
            "recommendedItems": [{"requirement_id": "AC-02"}],
            "optionalItems": [],
            "safeToSkipItems": []
        }

        # Make a copy of original recommendations
        recommendations_copy = copy.deepcopy(regression_recommendations)

        # Calculate metrics
        result = OptimizationMetricsService.calculate_optimization_metrics(
            current_test_count,
            regression_recommendations
        )

        # Verify original recommendations are unchanged
        assert regression_recommendations == recommendations_copy

        # Verify result is new data, not reference to input
        assert result is not regression_recommendations
        assert result is not recommendations_copy

    def test_optimization_metrics_pure_function(self):
        """Verify optimization metrics are pure functions."""
        current_test_count = 18
        regression_recommendations = {
            "requiredItems": [{"requirement_id": "AC-01"}],
            "recommendedItems": [],
            "optionalItems": [],
            "safeToSkipItems": []
        }

        result1 = OptimizationMetricsService.calculate_optimization_metrics(
            current_test_count,
            regression_recommendations
        )
        result2 = OptimizationMetricsService.calculate_optimization_metrics(
            current_test_count,
            regression_recommendations
        )

        # All results should be identical
        assert result1["optimizationPercentage"] == result2["optimizationPercentage"]
        assert result1["coverageConfidence"] == result2["coverageConfidence"]

    def test_optimization_metrics_no_database_writes(self):
        """Verify optimization metrics don't perform database writes."""
        import inspect
        from app.services.optimization_metrics_service import OptimizationMetricsService

        # Get all methods in OptimizationMetricsService
        methods = inspect.getmembers(OptimizationMetricsService, predicate=inspect.isfunction)

        # Check that methods don't accept db parameter for writes
        for name, method in methods:
            if name.startswith('_'):
                continue

            sig = inspect.signature(method)
            params = list(sig.parameters.keys())

            # Optimization metrics methods should not accept db sessions for writes
            # They only calculate metrics from input data
            assert 'db' not in params, f"Method {name} should not accept db parameter for writes"

    def test_optimization_metrics_no_llm_usage(self):
        """Verify optimization metrics don't use LLM or external APIs."""
        import inspect
        from app.services.optimization_metrics_service import OptimizationMetricsService

        # Get source code
        source = inspect.getsource(OptimizationMetricsService)

        # Verify no LLM-related imports or calls
        llm_keywords = ['openai', 'anthropic', 'llm', 'gpt', 'claude', 'completion', 'chat']
        for keyword in llm_keywords:
            assert keyword.lower() not in source.lower(), \
                f"Optimization metrics should not use LLM (found: {keyword})"

    def test_optimization_metrics_deterministic(self):
        """Verify optimization metrics are deterministic."""
        import random

        # Test with random inputs multiple times
        for _ in range(10):
            current_test_count = random.randint(10, 100)
            regression_recommendations = {
                "requiredItems": [{"requirement_id": f"AC-{i}"} for i in range(random.randint(0, 5))],
                "recommendedItems": [{"requirement_id": f"AC-{i}"} for i in range(random.randint(0, 5))],
                "optionalItems": [{"requirement_id": f"AC-{i}"} for i in range(random.randint(0, 5))],
                "safeToSkipItems": [{"requirement_id": f"AC-{i}"} for i in range(random.randint(0, 5))]
            }

            result1 = OptimizationMetricsService.calculate_optimization_metrics(
                current_test_count,
                regression_recommendations
            )
            result2 = OptimizationMetricsService.calculate_optimization_metrics(
                current_test_count,
                regression_recommendations
            )

            assert result1["optimizationPercentage"] == result2["optimizationPercentage"]

    def test_optimization_metrics_output_structure(self):
        """Verify optimization metrics output structure is consistent."""
        current_test_count = 18
        regression_recommendations = {
            "requiredItems": [{"requirement_id": "AC-01"}],
            "recommendedItems": [],
            "optionalItems": [],
            "safeToSkipItems": []
        }

        result = OptimizationMetricsService.calculate_optimization_metrics(
            current_test_count,
            regression_recommendations
        )

        # Verify output structure
        assert "currentTests" in result
        assert "optimizedTests" in result
        assert "optimizationPercentage" in result
        assert "executionReduction" in result
        assert "coverageConfidence" in result
        assert "distribution" in result

        # Verify types
        assert isinstance(result["currentTests"], int)
        assert isinstance(result["optimizationPercentage"], float)
        assert isinstance(result["executionReduction"], float)
        assert isinstance(result["coverageConfidence"], float)

    def test_optimization_metrics_advisory_only(self):
        """Verify optimization metrics are advisory only, not actual changes."""
        current_test_count = 18
        regression_recommendations = {
            "requiredItems": [{"requirement_id": "AC-01"}],
            "recommendedItems": [],
            "optionalItems": [],
            "safeToSkipItems": []
        }

        result = OptimizationMetricsService.calculate_optimization_metrics(
            current_test_count,
            regression_recommendations
        )

        # Verify it's advisory metadata only
        assert "currentTests" in result
        assert "optimizedTests" in result

        # Verify it doesn't modify actual test counts
        # This is advisory metadata only
        assert result["currentTests"] == current_test_count

    def test_optimization_metrics_no_coverage_modification(self):
        """Verify optimization metrics don't modify coverage buckets."""
        requirements = [
            {"requirement_id": "AC-01", "risk_band": "CRITICAL", "coverage_bucket": "MISSING"},
            {"requirement_id": "AC-02", "risk_band": "HIGH", "coverage_bucket": "PARTIAL"},
            {"requirement_id": "AC-03", "risk_band": "LOW", "coverage_bucket": "COVERED"}
        ]

        original_coverage = [req["coverage_bucket"] for req in requirements]

        # Calculate distribution
        result = OptimizationMetricsService.calculate_coverage_distribution(requirements)

        # Verify coverage buckets are unchanged
        assert [req["coverage_bucket"] for req in requirements] == original_coverage

        # Verify result doesn't modify coverage buckets
        # It only provides distribution statistics
        assert "coverage_bucket" not in result

    def test_optimization_metrics_no_state_mutation(self):
        """Verify optimization metrics don't maintain or mutate state."""
        import inspect
        from app.services.optimization_metrics_service import OptimizationMetricsService

        # Check that all public methods are static
        methods = inspect.getmembers(OptimizationMetricsService, predicate=inspect.isfunction)
        for name, method in methods:
            if not name.startswith('_'):
                assert isinstance(inspect.getattr_static(OptimizationMetricsService, name), staticmethod), \
                    f"Method {name} should be static"

    def test_optimization_summary_preserves_original_counts(self):
        """Verify optimization summary preserves original AC counts."""
        requirements = [
            {"requirement_id": "AC-01", "risk_band": "CRITICAL", "coverage_bucket": "MISSING"},
            {"requirement_id": "AC-02", "risk_band": "HIGH", "coverage_bucket": "PARTIAL"},
            {"requirement_id": "AC-03", "risk_band": "LOW", "coverage_bucket": "COVERED"}
        ]

        original_counts = {
            "CRITICAL": 1,
            "HIGH": 1,
            "LOW": 1,
            "COVERED": 1,
            "PARTIAL": 1,
            "MISSING": 1
        }

        regression_recommendations = {
            "requiredItems": [{"requirement_id": "AC-01"}],
            "recommendedItems": [{"requirement_id": "AC-02"}],
            "optionalItems": [],
            "safeToSkipItems": [{"requirement_id": "AC-03"}]
        }

        # Generate optimization summary
        result = OptimizationMetricsService.generate_regression_optimization_summary(
            requirements,
            regression_recommendations,
            18
        )

        # Verify original counts are preserved in distribution
        assert result["riskDistribution"]["CRITICAL"]["count"] == original_counts["CRITICAL"]
        assert result["riskDistribution"]["HIGH"]["count"] == original_counts["HIGH"]
        assert result["riskDistribution"]["LOW"]["count"] == original_counts["LOW"]
        assert result["coverageDistribution"]["COVERED"]["count"] == original_counts["COVERED"]
        assert result["coverageDistribution"]["PARTIAL"]["count"] == original_counts["PARTIAL"]
        assert result["coverageDistribution"]["MISSING"]["count"] == original_counts["MISSING"]

    def test_optimization_metrics_no_external_dependencies(self):
        """Verify optimization metrics don't depend on external state."""
        import inspect
        from app.services.optimization_metrics_service import OptimizationMetricsService

        # Get source code
        source = inspect.getsource(OptimizationMetricsService)

        # Verify no database imports
        assert 'sqlalchemy' not in source.lower(), "Optimization metrics should not import SQLAlchemy"
        assert 'from sqlalchemy' not in source, "Optimization metrics should not import from SQLAlchemy"
        assert 'import sqlalchemy' not in source, "Optimization metrics should not import SQLAlchemy"

    def test_advisory_notice_is_advisory(self):
        """Verify advisory notice is marked as advisory."""
        optimization_metrics = {
            "optimizationPercentage": 25.0,
            "coverageConfidence": 60.0
        }
        coverage_distribution = {
            "MISSING": {"count": 3},
            "PARTIAL": {"count": 2}
        }

        result = OptimizationMetricsService.generate_advisory_notice(
            optimization_metrics,
            coverage_distribution
        )

        # Verify advisory flags
        assert result["isAdvisory"] == True
        assert result["doesNotModifyEvidence"] == True

    def test_evidence_truth_verification_correct(self):
        """Verify evidence truth verification works correctly."""
        original_requirements = [
            {"coverage_bucket": "COVERED"},
            {"coverage_bucket": "PARTIAL"},
            {"coverage_bucket": "MISSING"}
        ]
        optimized_requirements = [
            {"coverage_bucket": "COVERED"},
            {"coverage_bucket": "PARTIAL"},
            {"coverage_bucket": "MISSING"}
        ]

        result = OptimizationMetricsService.verify_evidence_truth_preservation(
            original_requirements,
            optimized_requirements
        )

        assert result["evidenceTruthPreserved"] == True
        assert result["countsMatch"] == True
        assert result["totalMatch"] == True

    def test_evidence_truth_verification_detects_changes(self):
        """Verify evidence truth verification detects changes."""
        original_requirements = [
            {"coverage_bucket": "COVERED"},
            {"coverage_bucket": "PARTIAL"},
            {"coverage_bucket": "MISSING"}
        ]
        # Simulate a change in coverage
        optimized_requirements = [
            {"coverage_bucket": "COVERED"},
            {"coverage_bucket": "COVERED"},  # Changed from PARTIAL
            {"coverage_bucket": "MISSING"}
        ]

        result = OptimizationMetricsService.verify_evidence_truth_preservation(
            original_requirements,
            optimized_requirements
        )

        assert result["evidenceTruthPreserved"] == False
        assert result["countsMatch"] == False
