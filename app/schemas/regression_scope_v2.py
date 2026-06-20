"""Regression Scope V2 Schemas for Phase 4

Unified scope model for regression testing that consolidates all scope concepts
into a single, consistent contract.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ScopeGroup(str, Enum):
    """Scope group categories."""
    REQUIRED = "REQUIRED"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"
    SAFE_TO_SKIP = "SAFE_TO_SKIP"
    EXCLUDED_ALREADY_VERIFIED = "EXCLUDED_ALREADY_VERIFIED"
    EXCLUDED_ALREADY_PASSED_TESTS = "EXCLUDED_ALREADY_PASSED_TESTS"


class ScopeItemType(str, Enum):
    """Scope item types."""
    REQUIREMENT = "REQUIREMENT"
    TEST = "TEST"
    SCENARIO = "SCENARIO"
    MANUAL_TEST = "MANUAL_TEST"


class EvidenceClassification(str, Enum):
    """Evidence classification."""
    COVERED = "COVERED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    TRACEABILITY = "TRACEABILITY"


class RiskBand(str, Enum):
    """Risk bands."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ChangeImpactLevel(str, Enum):
    """Change impact levels."""
    DIRECT = "DIRECT"
    RELATED = "RELATED"
    INDIRECT = "INDIRECT"
    NONE = "NONE"


class BusinessRiskLevel(str, Enum):
    """Business risk levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class ScopeMode(str, Enum):
    """Scope generation modes."""
    TARGETED = "targeted"
    RISK_BASED = "risk_based"
    FULL = "full"


class ScopeSource(str, Enum):
    """Scope generation sources."""
    EVIDENCE_BASED = "evidence_based"
    RISK_BASED = "risk_based"
    MANUAL = "manual"
    HYBRID = "hybrid"


class ScopeItemDiagnostics(BaseModel):
    """Diagnostic information for scope items."""
    internal_requirement_id: Optional[str] = None
    internal_test_id: Optional[str] = None
    generation_rule: Optional[str] = None
    confidence_score: Optional[float] = None
    last_updated: Optional[datetime] = None


class ScopeItem(BaseModel):
    """Individual scope item with complete metadata."""
    id: str = Field(..., description="Unique identifier for the scope item")
    readable_id: str = Field(..., description="Human-readable identifier")
    source_ac_number: Optional[int] = Field(None, description="Source AC number if applicable")
    title: str = Field(..., description="Item title")
    item_type: ScopeItemType = Field(..., description="Type of scope item")
    group: ScopeGroup = Field(..., description="Scope group this item belongs to")
    evidence_classification: EvidenceClassification = Field(..., description="Evidence classification")
    risk_score: float = Field(..., description="Risk score (0-100)")
    risk_band: RiskBand = Field(..., description="Risk band")
    change_impact_level: ChangeImpactLevel = Field(..., description="Change impact level")
    business_risk_level: BusinessRiskLevel = Field(..., description="Business risk level")
    effective_risk_level: BusinessRiskLevel = Field(..., description="Effective risk level after reviews")
    suggested_action: str = Field(..., description="Suggested action for this item")
    reason: str = Field(..., description="Reason for this item's classification")
    evidence_references: List[str] = Field(default_factory=list, description="References to evidence")
    test_references: List[str] = Field(default_factory=list, description="References to tests")
    can_auto_execute: bool = Field(..., description="Whether this item can be auto-executed")
    execution_status: Optional[str] = Field(None, description="Current execution status")
    estimated_effort: Optional[str] = Field(None, description="Estimated effort for manual items")
    is_required_for_release: bool = Field(..., description="Whether this item is required for release")
    is_manual_only: bool = Field(..., description="Whether this item is manual-only")
    provider: Optional[str] = Field(None, description="Provider/source for manual tests (e.g. MANUAL_CSV, TESTRAIL)")
    external_id: Optional[str] = Field(None, description="External identifier for manual tests (e.g. MT-123)")
    diagnostics: Optional[ScopeItemDiagnostics] = Field(None, description="Diagnostic information")
    # Phase 6.4: Manual evidence risk adjustment fields
    manual_contribution_status: Optional[str] = Field(None, description="Manual evidence execution status (PASSED, FAILED, BLOCKED, SKIPPED, NOT_EXECUTED)")
    generated_risk_band: Optional[str] = Field(None, description="Risk band generated from automated evidence")
    residual_risk_band: Optional[str] = Field(None, description="Risk band after manual evidence adjustment")
    risk_adjustment_reason: Optional[str] = Field(None, description="Human-readable explanation of risk adjustment")
    risk_adjustment_delta: Optional[int] = Field(None, description="Number of risk bands adjusted (-1, 0, or +1)")


class ScopeGroupSummary(BaseModel):
    """Summary of items in a scope group."""
    group: ScopeGroup = Field(..., description="Scope group")
    count: int = Field(..., description="Number of items in this group")
    items: List[ScopeItem] = Field(..., description="Items in this group")


class ExecutionPlan(BaseModel):
    """Execution plan for regression scope."""
    required_count: int = Field(..., description="Number of required items")
    recommended_count: int = Field(..., description="Number of recommended items")
    optional_count: int = Field(..., description="Number of optional items")
    safe_to_skip_count: int = Field(..., description="Number of safe-to-skip items")
    total_executable_count: int = Field(..., description="Total executable items")
    estimated_execution_reduction: float = Field(..., description="Estimated execution reduction percentage")
    confidence_level: float = Field(..., description="Confidence level (0-100)")
    plan_summary: str = Field(..., description="Summary of the execution plan")
    advisory_notice: str = Field(..., description="Advisory notice for the execution plan")
    # Phase 6.3: manual/automated split metrics (optional, defaulted for backward compatibility)
    manual_required_count: int = Field(default=0, description="Number of required manual test items")
    manual_recommended_count: int = Field(default=0, description="Number of recommended manual test items")
    manual_optional_count: int = Field(default=0, description="Number of optional manual test items")
    manual_safe_to_skip_count: int = Field(default=0, description="Number of safe-to-skip manual test items")
    automated_required_count: int = Field(default=0, description="Number of required automated items")
    automated_recommended_count: int = Field(default=0, description="Number of recommended automated items")
    manual_estimated_minutes: int = Field(default=0, description="Total estimated minutes for manual items")
    automated_estimated_minutes: int = Field(default=0, description="Total estimated minutes for automated items")


class ScopeExclusions(BaseModel):
    """Excluded items from scope."""
    already_verified_count: int = Field(..., description="Count of already verified requirements")
    already_passed_tests_count: int = Field(..., description="Count of already passed tests")
    already_verified_items: List[ScopeItem] = Field(default_factory=list, description="Already verified items")
    already_passed_test_items: List[ScopeItem] = Field(default_factory=list, description="Already passed test items")


class ScopeOptimizationMetrics(BaseModel):
    """Optimization metrics for the scope."""
    current_regression_size: int = Field(..., description="Current regression test count")
    optimized_required_count: int = Field(..., description="Optimized required count")
    optimized_recommended_count: int = Field(..., description="Optimized recommended count")
    optimized_optional_count: int = Field(..., description="Optimized optional count")
    safe_to_skip_count: int = Field(..., description="Safe to skip count")
    optimization_percentage: float = Field(..., description="Optimization percentage")
    execution_reduction: float = Field(..., description="Execution reduction percentage")
    coverage_confidence: float = Field(..., description="Coverage confidence (0-100)")


class ScopeGovernance(BaseModel):
    """Governance information for the scope."""
    risk_reviews_count: int = Field(..., description="Number of risk reviews")
    overridden_count: int = Field(..., description="Number of overridden items")
    needs_discussion_count: int = Field(..., description="Number of items needing discussion")
    release_decision_required: bool = Field(..., description="Whether release decision is required")
    release_decision_status: Optional[str] = Field(None, description="Release decision status")


class ScopeDiagnostics(BaseModel):
    """Diagnostic information for the scope."""
    generation_timestamp: datetime = Field(..., description="When the scope was generated")
    generation_duration_ms: Optional[int] = Field(None, description="Generation duration in milliseconds")
    rules_applied: List[str] = Field(default_factory=list, description="Rules applied during generation")
    warnings: List[str] = Field(default_factory=list, description="Warnings during generation")
    errors: List[str] = Field(default_factory=list, description="Errors during generation")


class RegressionScopeV2(BaseModel):
    """Unified regression scope model V2."""
    recommendation_run_id: str = Field(..., description="Recommendation run ID")
    snapshot_hash: str = Field(..., description="Evidence graph snapshot hash")
    generated_at: datetime = Field(..., description="When the scope was generated")
    scope_type: str = Field(..., description="Type of scope")
    source: ScopeSource = Field(..., description="Source of the scope")
    summary: str = Field(..., description="Summary of the scope")
    execution_plan: ExecutionPlan = Field(..., description="Execution plan")
    groups: Dict[str, ScopeGroupSummary] = Field(..., description="Scope groups")
    exclusions: ScopeExclusions = Field(..., description="Excluded items")
    optimization_metrics: ScopeOptimizationMetrics = Field(..., description="Optimization metrics")
    governance: ScopeGovernance = Field(..., description="Governance information")
    diagnostics: ScopeDiagnostics = Field(..., description="Diagnostic information")


class RegressionScopeV2Request(BaseModel):
    """Request for regression scope V2."""
    mode: ScopeMode = Field(default=ScopeMode.TARGETED, description="Scope generation mode")
    include_safe_to_skip: bool = Field(default=False, description="Include safe-to-skip items")
    include_diagnostics: bool = Field(default=False, description="Include diagnostic information")
    audit: bool = Field(default=False, description="Include audit information")


class RegressionScopeV2Response(BaseModel):
    """Response for regression scope V2 endpoint."""
    status: str = Field(..., description="Response status")
    scope: Optional[RegressionScopeV2] = Field(None, description="Regression scope V2")
    error_code: Optional[str] = Field(None, description="Error code if failed")
    message: Optional[str] = Field(None, description="Error message if failed")
