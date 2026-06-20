"""Optimization Metrics Schemas for Phase 3.4"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class OptimizedTests(BaseModel):
    """Optimized test counts by category."""
    required: int = Field(..., description="Number of required tests")
    recommended: int = Field(..., description="Number of recommended tests")
    optional: int = Field(..., description="Number of optional tests")
    safeToSkip: int = Field(..., description="Number of tests safe to skip")
    totalOptimized: int = Field(..., description="Total optimized test count")


class OptimizationMetrics(BaseModel):
    """Optimization metrics for regression testing."""
    currentTests: int = Field(..., description="Current number of regression tests")
    optimizedTests: OptimizedTests = Field(..., description="Optimized test counts by category")
    optimizationPercentage: float = Field(..., description="Percentage of optimization achieved")
    executionReduction: float = Field(..., description="Estimated execution time reduction percentage")
    coverageConfidence: float = Field(..., description="Coverage confidence score (0-100)")
    distribution: Dict[str, int] = Field(..., description="Distribution of tests by category")


class RiskDistributionItem(BaseModel):
    """Risk distribution for a single risk band."""
    count: int = Field(..., description="Number of requirements in this risk band")
    percentage: float = Field(..., description="Percentage of total requirements")


class RiskDistribution(BaseModel):
    """Risk distribution across all requirements."""
    CRITICAL: RiskDistributionItem = Field(..., description="Critical risk distribution")
    HIGH: RiskDistributionItem = Field(..., description="High risk distribution")
    MEDIUM: RiskDistributionItem = Field(..., description="Medium risk distribution")
    LOW: RiskDistributionItem = Field(..., description="Low risk distribution")


class CoverageDistributionItem(BaseModel):
    """Coverage distribution for a single coverage bucket."""
    count: int = Field(..., description="Number of requirements in this coverage bucket")
    percentage: float = Field(..., description="Percentage of total requirements")


class CoverageDistribution(BaseModel):
    """Coverage distribution across all requirements."""
    COVERED: CoverageDistributionItem = Field(..., description="Covered distribution")
    PARTIAL: CoverageDistributionItem = Field(..., description="Partial coverage distribution")
    MISSING: CoverageDistributionItem = Field(..., description="Missing coverage distribution")
    TRACEABILITY: CoverageDistributionItem = Field(..., description="Traceability distribution")


class ExecutionPhase(BaseModel):
    """Single phase of the execution plan."""
    phase: int = Field(..., description="Phase number")
    name: str = Field(..., description="Phase name")
    priority: str = Field(..., description="Priority level (MUST_RUN, SHOULD_RUN, CAN_RUN)")
    testCount: int = Field(..., description="Number of tests in this phase")
    items: List[str] = Field(..., description="List of requirement IDs in this phase")


class ExecutionPlan(BaseModel):
    """Recommended execution plan for regression testing."""
    phases: List[ExecutionPhase] = Field(..., description="Execution phases")
    totalPhases: int = Field(..., description="Total number of phases")
    minimumExecution: int = Field(..., description="Minimum number of tests to execute")
    recommendedExecution: int = Field(..., description="Recommended number of tests to execute")
    comprehensiveExecution: int = Field(..., description="Comprehensive number of tests to execute")


class AdvisoryNotice(BaseModel):
    """Advisory notice for optimization summary."""
    message: str = Field(..., description="Advisory message")
    recommendations: List[str] = Field(..., description="List of recommendations")
    isAdvisory: bool = Field(..., description="Whether this is advisory only")
    doesNotModifyEvidence: bool = Field(..., description="Whether this modifies evidence truth")


class RegressionOptimizationSummary(BaseModel):
    """Complete regression optimization summary."""
    optimizationMetrics: OptimizationMetrics = Field(..., description="Optimization metrics")
    riskDistribution: Dict[str, RiskDistributionItem] = Field(..., description="Risk distribution")
    coverageDistribution: Dict[str, CoverageDistributionItem] = Field(..., description="Coverage distribution")
    recommendedExecutionPlan: ExecutionPlan = Field(..., description="Recommended execution plan")
    advisoryNotice: AdvisoryNotice = Field(..., description="Advisory notice")


class OptimizationMetricsRequest(BaseModel):
    """Request for optimization metrics calculation."""
    currentTestCount: int = Field(..., description="Current number of regression tests")
    regressionRecommendations: Dict[str, List[Dict[str, Any]]] = Field(..., description="Regression recommendations")


class OptimizationSummaryRequest(BaseModel):
    """Request for regression optimization summary."""
    requirements: List[Dict[str, Any]] = Field(..., description="Requirements with risk and coverage data")
    regressionRecommendations: Dict[str, List[Dict[str, Any]]] = Field(..., description="Regression recommendations")
    currentTestCount: int = Field(..., description="Current number of regression tests")


class EvidenceTruthVerification(BaseModel):
    """Verification of evidence truth preservation."""
    countsMatch: bool = Field(..., description="Whether coverage counts match")
    totalMatch: bool = Field(..., description="Whether total counts match")
    originalCoverage: Dict[str, int] = Field(..., description="Original coverage counts")
    optimizedCoverage: Dict[str, int] = Field(..., description="Optimized coverage counts")
    evidenceTruthPreserved: bool = Field(..., description="Whether evidence truth is preserved")
