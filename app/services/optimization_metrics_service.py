"""Optimization Metrics Service - Regression optimization reporting and metrics."""
from typing import Dict, Any, List, Optional


class OptimizationMetricsService:
    """Service for calculating and reporting regression optimization metrics."""

    @staticmethod
    def calculate_optimization_metrics(
        current_test_count: int,
        regression_recommendations: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Calculate optimization metrics from regression recommendations.

        Args:
            current_test_count: Current number of regression tests
            regression_recommendations: Dict with requiredItems, recommendedItems, optionalItems, safeToSkipItems

        Returns:
            Dict with optimization metrics including currentTests, optimizedTests, optimizationPercentage,
            executionReduction, coverageConfidence, and distribution
        """
        required_count = len(regression_recommendations.get("requiredItems", []))
        recommended_count = len(regression_recommendations.get("recommendedItems", []))
        optional_count = len(regression_recommendations.get("optionalItems", []))
        safe_to_skip_count = len(regression_recommendations.get("safeToSkipItems", []))

        # Calculate optimized test count (required + recommended)
        optimized_test_count = required_count + recommended_count

        # Calculate optimization percentage
        if current_test_count > 0:
            optimization_percentage = ((current_test_count - optimized_test_count) / current_test_count) * 100
        else:
            optimization_percentage = 0.0

        # Calculate execution reduction
        execution_reduction = optimization_percentage

        # Calculate coverage confidence based on required items
        total_items = required_count + recommended_count + optional_count + safe_to_skip_count
        if total_items > 0:
            coverage_confidence = (required_count / total_items) * 100
        else:
            coverage_confidence = 0.0

        return {
            "currentTests": current_test_count,
            "optimizedTests": {
                "required": required_count,
                "recommended": recommended_count,
                "optional": optional_count,
                "safeToSkip": safe_to_skip_count,
                "totalOptimized": optimized_test_count
            },
            "optimizationPercentage": round(optimization_percentage, 2),
            "executionReduction": round(execution_reduction, 2),
            "coverageConfidence": round(coverage_confidence, 2),
            "distribution": {
                "required": required_count,
                "recommended": recommended_count,
                "optional": optional_count,
                "safeToSkip": safe_to_skip_count
            }
        }

    @staticmethod
    def calculate_risk_distribution(
        requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate risk distribution from requirements.

        Args:
            requirements: List of requirements with risk_band

        Returns:
            Dict with risk distribution counts and percentages
        """
        risk_counts = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0
        }

        for req in requirements:
            risk_band = req.get("risk_band", "LOW")
            if risk_band in risk_counts:
                risk_counts[risk_band] += 1

        total = sum(risk_counts.values())

        risk_distribution = {}
        for risk, count in risk_counts.items():
            if total > 0:
                percentage = (count / total) * 100
            else:
                percentage = 0.0
            risk_distribution[risk] = {
                "count": count,
                "percentage": round(percentage, 2)
            }

        return risk_distribution

    @staticmethod
    def calculate_coverage_distribution(
        requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate coverage distribution from requirements.

        Args:
            requirements: List of requirements with coverage_bucket

        Returns:
            Dict with coverage distribution counts and percentages
        """
        coverage_counts = {
            "COVERED": 0,
            "PARTIAL": 0,
            "MISSING": 0,
            "TRACEABILITY": 0
        }

        for req in requirements:
            coverage_bucket = req.get("coverage_bucket", "COVERED")
            if coverage_bucket in coverage_counts:
                coverage_counts[coverage_bucket] += 1

        total = sum(coverage_counts.values())

        coverage_distribution = {}
        for coverage, count in coverage_counts.items():
            if total > 0:
                percentage = (count / total) * 100
            else:
                percentage = 0.0
            coverage_distribution[coverage] = {
                "count": count,
                "percentage": round(percentage, 2)
            }

        return coverage_distribution

    @staticmethod
    def generate_regression_optimization_summary(
        requirements: List[Dict[str, Any]],
        regression_recommendations: Dict[str, List[Dict[str, Any]]],
        current_test_count: int
    ) -> Dict[str, Any]:
        """Generate comprehensive regression optimization summary.

        Args:
            requirements: List of requirements with risk and coverage data
            regression_recommendations: Dict with regression category items
            current_test_count: Current number of regression tests

        Returns:
            Dict with complete optimization summary including risk distribution,
            optimization distribution, recommended execution plan, and advisory notice
        """
        # Calculate metrics
        optimization_metrics = OptimizationMetricsService.calculate_optimization_metrics(
            current_test_count,
            regression_recommendations
        )

        # Calculate risk distribution
        risk_distribution = OptimizationMetricsService.calculate_risk_distribution(requirements)

        # Calculate coverage distribution
        coverage_distribution = OptimizationMetricsService.calculate_coverage_distribution(requirements)

        # Generate recommended execution plan
        execution_plan = OptimizationMetricsService.generate_execution_plan(regression_recommendations)

        # Generate advisory notice
        advisory_notice = OptimizationMetricsService.generate_advisory_notice(
            optimization_metrics,
            coverage_distribution
        )

        return {
            "optimizationMetrics": optimization_metrics,
            "riskDistribution": risk_distribution,
            "coverageDistribution": coverage_distribution,
            "recommendedExecutionPlan": execution_plan,
            "advisoryNotice": advisory_notice
        }

    @staticmethod
    def generate_execution_plan(
        regression_recommendations: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Generate recommended execution plan from regression recommendations.

        Args:
            regression_recommendations: Dict with regression category items

        Returns:
            Dict with execution plan including phases and priority
        """
        required_items = regression_recommendations.get("requiredItems", [])
        recommended_items = regression_recommendations.get("recommendedItems", [])
        optional_items = regression_recommendations.get("optionalItems", [])

        # Phase 1: Required tests (must run)
        phase1 = {
            "phase": 1,
            "name": "Critical Regression",
            "priority": "MUST_RUN",
            "testCount": len(required_items),
            "items": [item.get("requirement_id", "") for item in required_items]
        }

        # Phase 2: Recommended tests (should run if time permits)
        phase2 = {
            "phase": 2,
            "name": "High-Priority Regression",
            "priority": "SHOULD_RUN",
            "testCount": len(recommended_items),
            "items": [item.get("requirement_id", "") for item in recommended_items]
        }

        # Phase 3: Optional tests (run if resources available)
        phase3 = {
            "phase": 3,
            "name": "Comprehensive Regression",
            "priority": "CAN_RUN",
            "testCount": len(optional_items),
            "items": [item.get("requirement_id", "") for item in optional_items]
        }

        return {
            "phases": [phase1, phase2, phase3],
            "totalPhases": 3,
            "minimumExecution": len(required_items),
            "recommendedExecution": len(required_items) + len(recommended_items),
            "comprehensiveExecution": len(required_items) + len(recommended_items) + len(optional_items)
        }

    @staticmethod
    def generate_advisory_notice(
        optimization_metrics: Dict[str, Any],
        coverage_distribution: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate advisory notice for optimization summary.

        Args:
            optimization_metrics: Calculated optimization metrics
            coverage_distribution: Coverage distribution data

        Returns:
            Dict with advisory notice including message and recommendations
        """
        messages = []
        recommendations = []

        # Add optimization message
        optimization_pct = optimization_metrics.get("optimizationPercentage", 0)
        if optimization_pct > 20:
            messages.append(f"Significant optimization opportunity: {optimization_pct}% reduction in test execution")
        elif optimization_pct > 10:
            messages.append(f"Moderate optimization opportunity: {optimization_pct}% reduction in test execution")
        else:
            messages.append(f"Limited optimization opportunity: {optimization_pct}% reduction in test execution")

        # Add coverage confidence message
        coverage_confidence = optimization_metrics.get("coverageConfidence", 0)
        if coverage_confidence > 80:
            messages.append(f"High coverage confidence: {coverage_confidence}% of tests are required")
        elif coverage_confidence > 50:
            messages.append(f"Moderate coverage confidence: {coverage_confidence}% of tests are required")
        else:
            messages.append(f"Low coverage confidence: {coverage_confidence}% of tests are required")

        # Add coverage gap message
        missing_count = coverage_distribution.get("MISSING", {}).get("count", 0)
        if missing_count > 0:
            messages.append(f"Coverage gap: {missing_count} requirements are missing evidence")
            recommendations.append("Address missing coverage before release")
        else:
            messages.append("No coverage gaps detected")

        # Add partial coverage message
        partial_count = coverage_distribution.get("PARTIAL", {}).get("count", 0)
        if partial_count > 0:
            messages.append(f"Partial coverage: {partial_count} requirements have partial evidence")
            recommendations.append("Review partial coverage for completeness")

        # Add general recommendation
        recommendations.append("Use optimized regression scope to reduce execution time while maintaining quality")
        recommendations.append("Review recommended execution plan for phased testing approach")

        return {
            "message": " | ".join(messages),
            "recommendations": recommendations,
            "isAdvisory": True,
            "doesNotModifyEvidence": True
        }

    @staticmethod
    def verify_evidence_truth_preservation(
        original_requirements: List[Dict[str, Any]],
        optimized_requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify that evidence truth is preserved after optimization.

        Args:
            original_requirements: Original requirements before optimization
            optimized_requirements: Requirements after optimization

        Returns:
            Dict with verification results
        """
        # Count original coverage buckets
        original_coverage = {}
        for req in original_requirements:
            coverage = req.get("coverage_bucket", "COVERED")
            original_coverage[coverage] = original_coverage.get(coverage, 0) + 1

        # Count optimized coverage buckets
        optimized_coverage = {}
        for req in optimized_requirements:
            coverage = req.get("coverage_bucket", "COVERED")
            optimized_coverage[coverage] = optimized_coverage.get(coverage, 0) + 1

        # Verify counts match
        counts_match = original_coverage == optimized_coverage

        # Verify total count matches
        total_match = len(original_requirements) == len(optimized_requirements)

        return {
            "countsMatch": counts_match,
            "totalMatch": total_match,
            "originalCoverage": original_coverage,
            "optimizedCoverage": optimized_coverage,
            "evidenceTruthPreserved": counts_match and total_match
        }
