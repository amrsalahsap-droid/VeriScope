"""
Optimization Metrics Tests for Phase 3.4

Tests for regression optimization metrics and reporting.
"""

import pytest
from app.services.optimization_metrics_service import OptimizationMetricsService


class TestOptimizationMetrics:
    """Test suite for optimization metrics calculation."""

    def test_calculate_optimization_metrics_basic(self):
        """Verify basic optimization metrics calculation."""
        current_test_count = 18
        regression_recommendations = {
            "requiredItems": [{"requirement_id": "AC-01"}],
            "recommendedItems": [{"requirement_id": "AC-02"}],
            "optionalItems": [{"requirement_id": "AC-03"}],
            "safeToSkipItems": [{"requirement_id": "AC-04"}]
        }

        result = OptimizationMetricsService.calculate_optimization_metrics(
            current_test_count,
            regression_recommendations
        )

        assert result["currentTests"] == 18
        assert result["optimizedTests"]["required"] == 1
        assert result["optimizedTests"]["recommended"] == 1
        assert result["optimizedTests"]["optional"] == 1
        assert result["optimizedTests"]["safeToSkip"] == 1
        assert result["optimizedTests"]["totalOptimized"] == 2
        assert result["optimizationPercentage"] == round(((18 - 2) / 18) * 100, 2)
        assert result["executionReduction"] == result["optimizationPercentage"]

    def test_calculate_optimization_metrics_empty_recommendations(self):
        """Verify optimization metrics with empty recommendations."""
        current_test_count = 18
        regression_recommendations = {
            "requiredItems": [],
            "recommendedItems": [],
            "optionalItems": [],
            "safeToSkipItems": []
        }

        result = OptimizationMetricsService.calculate_optimization_metrics(
            current_test_count,
            regression_recommendations
        )

        assert result["currentTests"] == 18
        assert result["optimizedTests"]["totalOptimized"] == 0
        assert result["optimizationPercentage"] == 100.0
        assert result["coverageConfidence"] == 0.0

    def test_calculate_optimization_metrics_all_required(self):
        """Verify optimization metrics when all items are required."""
        current_test_count = 18
        regression_recommendations = {
            "requiredItems": [{"requirement_id": "AC-01"}, {"requirement_id": "AC-02"}],
            "recommendedItems": [],
            "optionalItems": [],
            "safeToSkipItems": []
        }

        result = OptimizationMetricsService.calculate_optimization_metrics(
            current_test_count,
            regression_recommendations
        )

        assert result["optimizedTests"]["totalOptimized"] == 2
        assert result["coverageConfidence"] == 100.0

    def test_calculate_risk_distribution(self):
        """Verify risk distribution calculation."""
        requirements = [
            {"risk_band": "CRITICAL"},
            {"risk_band": "HIGH"},
            {"risk_band": "MEDIUM"},
            {"risk_band": "LOW"},
            {"risk_band": "CRITICAL"}
        ]

        result = OptimizationMetricsService.calculate_risk_distribution(requirements)

        assert result["CRITICAL"]["count"] == 2
        assert result["CRITICAL"]["percentage"] == 40.0
        assert result["HIGH"]["count"] == 1
        assert result["HIGH"]["percentage"] == 20.0
        assert result["MEDIUM"]["count"] == 1
        assert result["MEDIUM"]["percentage"] == 20.0
        assert result["LOW"]["count"] == 1
        assert result["LOW"]["percentage"] == 20.0

    def test_calculate_risk_distribution_empty(self):
        """Verify risk distribution with empty requirements."""
        requirements = []

        result = OptimizationMetricsService.calculate_risk_distribution(requirements)

        assert result["CRITICAL"]["count"] == 0
        assert result["CRITICAL"]["percentage"] == 0.0
        assert result["HIGH"]["count"] == 0
        assert result["HIGH"]["percentage"] == 0.0

    def test_calculate_coverage_distribution(self):
        """Verify coverage distribution calculation."""
        requirements = [
            {"coverage_bucket": "COVERED"},
            {"coverage_bucket": "PARTIAL"},
            {"coverage_bucket": "MISSING"},
            {"coverage_bucket": "TRACEABILITY"},
            {"coverage_bucket": "COVERED"}
        ]

        result = OptimizationMetricsService.calculate_coverage_distribution(requirements)

        assert result["COVERED"]["count"] == 2
        assert result["COVERED"]["percentage"] == 40.0
        assert result["PARTIAL"]["count"] == 1
        assert result["PARTIAL"]["percentage"] == 20.0
        assert result["MISSING"]["count"] == 1
        assert result["MISSING"]["percentage"] == 20.0
        assert result["TRACEABILITY"]["count"] == 1
        assert result["TRACEABILITY"]["percentage"] == 20.0

    def test_calculate_coverage_distribution_empty(self):
        """Verify coverage distribution with empty requirements."""
        requirements = []

        result = OptimizationMetricsService.calculate_coverage_distribution(requirements)

        assert result["COVERED"]["count"] == 0
        assert result["COVERED"]["percentage"] == 0.0

    def test_generate_execution_plan(self):
        """Verify execution plan generation."""
        regression_recommendations = {
            "requiredItems": [{"requirement_id": "AC-01"}, {"requirement_id": "AC-02"}],
            "recommendedItems": [{"requirement_id": "AC-03"}],
            "optionalItems": [{"requirement_id": "AC-04"}],
            "safeToSkipItems": []
        }

        result = OptimizationMetricsService.generate_execution_plan(regression_recommendations)

        assert len(result["phases"]) == 3
        assert result["phases"][0]["phase"] == 1
        assert result["phases"][0]["priority"] == "MUST_RUN"
        assert result["phases"][0]["testCount"] == 2
        assert result["phases"][1]["phase"] == 2
        assert result["phases"][1]["priority"] == "SHOULD_RUN"
        assert result["phases"][1]["testCount"] == 1
        assert result["phases"][2]["phase"] == 3
        assert result["phases"][2]["priority"] == "CAN_RUN"
        assert result["phases"][2]["testCount"] == 1
        assert result["minimumExecution"] == 2
        assert result["recommendedExecution"] == 3
        assert result["comprehensiveExecution"] == 4

    def test_generate_advisory_notice(self):
        """Verify advisory notice generation."""
        optimization_metrics = {
            "optimizationPercentage": 17.0,
            "coverageConfidence": 50.0
        }
        coverage_distribution = {
            "MISSING": {"count": 2},
            "PARTIAL": {"count": 1}
        }

        result = OptimizationMetricsService.generate_advisory_notice(
            optimization_metrics,
            coverage_distribution
        )

        assert "message" in result
        assert "recommendations" in result
        assert result["isAdvisory"] == True
        assert result["doesNotModifyEvidence"] == True
        assert len(result["recommendations"]) > 0

    def test_generate_regression_optimization_summary(self):
        """Verify complete regression optimization summary generation."""
        requirements = [
            {"requirement_id": "AC-01", "risk_band": "CRITICAL", "coverage_bucket": "MISSING"},
            {"requirement_id": "AC-02", "risk_band": "HIGH", "coverage_bucket": "PARTIAL"},
            {"requirement_id": "AC-03", "risk_band": "LOW", "coverage_bucket": "COVERED"}
        ]
        regression_recommendations = {
            "requiredItems": [{"requirement_id": "AC-01"}],
            "recommendedItems": [{"requirement_id": "AC-02"}],
            "optionalItems": [],
            "safeToSkipItems": [{"requirement_id": "AC-03"}]
        }
        current_test_count = 18

        result = OptimizationMetricsService.generate_regression_optimization_summary(
            requirements,
            regression_recommendations,
            current_test_count
        )

        assert "optimizationMetrics" in result
        assert "riskDistribution" in result
        assert "coverageDistribution" in result
        assert "recommendedExecutionPlan" in result
        assert "advisoryNotice" in result

    def test_verify_evidence_truth_preservation(self):
        """Verify evidence truth preservation check."""
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

        assert result["countsMatch"] == True
        assert result["totalMatch"] == True
        assert result["evidenceTruthPreserved"] == True

    def test_verify_evidence_truth_preservation_mismatch(self):
        """Verify evidence truth preservation check detects mismatches."""
        original_requirements = [
            {"coverage_bucket": "COVERED"},
            {"coverage_bucket": "PARTIAL"},
            {"coverage_bucket": "MISSING"}
        ]
        optimized_requirements = [
            {"coverage_bucket": "COVERED"},
            {"coverage_bucket": "COVERED"},  # Changed from PARTIAL
            {"coverage_bucket": "MISSING"}
        ]

        result = OptimizationMetricsService.verify_evidence_truth_preservation(
            original_requirements,
            optimized_requirements
        )

        assert result["countsMatch"] == False
        assert result["totalMatch"] == True
        assert result["evidenceTruthPreserved"] == False

    def test_optimization_metrics_structure(self):
        """Verify optimization metrics output structure."""
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

        assert "currentTests" in result
        assert "optimizedTests" in result
        assert "optimizationPercentage" in result
        assert "executionReduction" in result
        assert "coverageConfidence" in result
        assert "distribution" in result

    def test_optimization_percentage_calculation(self):
        """Verify optimization percentage calculation accuracy."""
        current_test_count = 100
        regression_recommendations = {
            "requiredItems": [{"requirement_id": str(i)} for i in range(50)],
            "recommendedItems": [],
            "optionalItems": [],
            "safeToSkipItems": []
        }

        result = OptimizationMetricsService.calculate_optimization_metrics(
            current_test_count,
            regression_recommendations
        )

        # 50% reduction (100 -> 50)
        assert result["optimizationPercentage"] == 50.0
        assert result["executionReduction"] == 50.0

    def test_coverage_confidence_calculation(self):
        """Verify coverage confidence calculation."""
        regression_recommendations = {
            "requiredItems": [{"requirement_id": str(i)} for i in range(3)],
            "recommendedItems": [{"requirement_id": str(i)} for i in range(3, 6)],
            "optionalItems": [{"requirement_id": str(i)} for i in range(6, 9)],
            "safeToSkipItems": []
        }

        result = OptimizationMetricsService.calculate_optimization_metrics(
            18,
            regression_recommendations
        )

        # 3 required out of 9 total = 33.33%
        assert result["coverageConfidence"] == round((3 / 9) * 100, 2)

    def test_execution_plan_phases_order(self):
        """Verify execution plan phases are in correct order."""
        regression_recommendations = {
            "requiredItems": [{"requirement_id": "AC-01"}],
            "recommendedItems": [{"requirement_id": "AC-02"}],
            "optionalItems": [{"requirement_id": "AC-03"}],
            "safeToSkipItems": []
        }

        result = OptimizationMetricsService.generate_execution_plan(regression_recommendations)

        assert result["phases"][0]["phase"] == 1
        assert result["phases"][1]["phase"] == 2
        assert result["phases"][2]["phase"] == 3

    def test_advisory_notice_contains_recommendations(self):
        """Verify advisory notice contains actionable recommendations."""
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

        assert len(result["recommendations"]) > 0
        assert isinstance(result["recommendations"], list)
        assert all(isinstance(rec, str) for rec in result["recommendations"])

    def test_deterministic_optimization_metrics(self):
        """Verify optimization metrics are deterministic."""
        current_test_count = 18
        regression_recommendations = {
            "requiredItems": [{"requirement_id": "AC-01"}],
            "recommendedItems": [{"requirement_id": "AC-02"}],
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

        assert result1["optimizationPercentage"] == result2["optimizationPercentage"]
        assert result1["coverageConfidence"] == result2["coverageConfidence"]
