"""Regression Scope V2 Schemas for Phase 4

Unified scope model for regression testing that consolidates all scope concepts
into a single, consistent contract.
"""

import re

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ScopeGroup(str, Enum):
    """Scope group categories."""
    REQUIRED = "REQUIRED"
    REVIEW_NEEDED = "REVIEW_NEEDED"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"
    SAFE_TO_SKIP = "SAFE_TO_SKIP"
    EXCLUDED_ALREADY_VERIFIED = "EXCLUDED_ALREADY_VERIFIED"
    EXCLUDED_ALREADY_PASSED_TESTS = "EXCLUDED_ALREADY_PASSED_TESTS"
    DEFERRED_COVERAGE_DEBT = "DEFERRED_COVERAGE_DEBT"


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
    FULL_SUITE = "full_suite"


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
    execution_status: Optional[str] = Field(None, description="Current execution status (PASSED, FAILED, NOT_RUN, SKIPPED)")
    estimated_effort: Optional[str] = Field(None, description="Estimated effort display label (e.g. '10 min')")
    estimated_effort_minutes: Optional[int] = Field(None, description="Estimated effort in minutes (machine-readable)")
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
    # Release action classification fields
    release_action: Optional[str] = Field(None, description="Action required before release (NONE, RE_RUN, FIX_OR_RERUN, RUN_OR_CREATE_TEST, MANUAL_REVIEW, NOT_RELEASE_BLOCKING)")
    freshness_status: Optional[str] = Field(None, description="Evidence freshness status (FRESH, STALE, UNKNOWN)")
    mapping_status: Optional[str] = Field(None, description="Mapping confidence status (VERIFIED, UNVERIFIED, LOW_CONFIDENCE)")
    # Safe to Skip evidence
    skip_evidence: Optional[Dict[str, Any]] = Field(None, description="Evidence explaining why this item is safe to skip")
    # Mapping confidence fields
    mapping_type: Optional[str] = Field(None, description="Mapping type (e.g. DIRECT_VERIFIED, FUZZY_MATCHED, MULTI_AC_SINGLE_TEST, NO_EXECUTABLE_TEST, REVIEW_NEEDED, UNMAPPED)")
    mapping_confidence: Optional[float] = Field(None, description="Mapping confidence score (0-1.0)")
    mapping_reason: Optional[str] = Field(None, description="Explanation for mapping assignment")
    linked_test_count: Optional[int] = Field(None, description="Number of linked tests")
    linked_tests: Optional[List[str]] = Field(None, description="List of linked tests")
    test_run_commit_sha: Optional[str] = Field(None, description="Test run commit SHA for freshness proof")
    pull_request_head_sha: Optional[str] = Field(None, description="Pull request head commit SHA for freshness proof")
    reason_code: Optional[str] = Field(None, description="Reason code explaining bucket assignment")

    @field_validator("estimated_effort", mode="before")
    @classmethod
    def _coerce_effort_to_label(cls, v):
        """Coerce numeric effort values (e.g. 10) to a display label ('10 min')."""
        if v is None:
            return v
        if isinstance(v, bool):
            return str(v)
        if isinstance(v, (int, float)):
            minutes = int(v)
            return f"{minutes} min"
        return v

    @model_validator(mode="after")
    def _sync_effort_minutes(self):
        """Keep estimated_effort and estimated_effort_minutes consistent."""
        if self.estimated_effort_minutes is None and self.estimated_effort:
            match = re.search(r"(\d+)", self.estimated_effort)
            if match:
                self.estimated_effort_minutes = int(match.group(1))
        elif self.estimated_effort_minutes is not None and not self.estimated_effort:
            self.estimated_effort = f"{self.estimated_effort_minutes} min"
        return self


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
    review_needed_count: int = Field(default=0, description="Number of review-needed items")
    deferred_coverage_debt_count: int = Field(default=0, description="Number of deferred coverage debt items")
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


class ScopeIntegrityReport(BaseModel):
    """Scope integrity validation report."""
    integrity_status: str = Field(..., description="PASS or FAIL")
    integrity_errors: List[str] = Field(default_factory=list, description="Errors list")
    integrity_warnings: List[str] = Field(default_factory=list, description="Warnings list")
    total_unique_logical_items: int = Field(..., description="Total unique logical items")
    bucket_sum: int = Field(..., description="Sum of all bucket items counts")
    duplicate_identities: List[str] = Field(default_factory=list, description="List of duplicate identities")


class TraceabilitySummary(BaseModel):
    """Summary of requirement traceability from the evidence graph."""
    total_requirements: int = Field(..., description="Total number of requirements in the domain")
    covered: int = Field(..., description="Number of requirements with fresh passing tests (ALREADY_VERIFIED)")
    missing: int = Field(..., description="Number of requirements without evidence (REQUIRED)")
    not_mapped: int = Field(..., description="Number of requirements without database_ac_id (no traceability link)")
    review_required: int = Field(0, description="Number of requirements requiring manual review")
    unknown_statuses: List[str] = Field(default_factory=list, description="Unrecognized coverage statuses encountered during summarization")


class ReleaseDecision(BaseModel):
    """Unified release decision derived from the active mode's ReleaseActionScope."""
    verdict: str = Field(..., description="Release verdict: SAFE_TO_RELEASE, REVIEW_RECOMMENDED, DO_NOT_RELEASE")
    reason: str = Field(..., description="Human-readable explanation of the decision")
    required_count: int = Field(..., description="Number of REQUIRED items")
    recommended_count: int = Field(..., description="Number of RECOMMENDED items")
    already_verified_count: int = Field(..., description="Number of ALREADY_VERIFIED items")
    source_mode: str = Field(..., description="The mode used to generate this decision")


class ChangedRule(BaseModel):
    """Represents a validation rule that was added or modified in the PR."""
    rule_name: str = Field(..., description="Name of the rule (e.g., minLength, uppercase)")
    rule_type: str = Field(..., description="Type of rule (validation, business logic, security)")
    file_path: str = Field(..., description="File where the rule was changed")
    line_number: Optional[int] = Field(None, description="Line number where the rule appears")


class ChangeSummary(BaseModel):
    """Semantic diff summary for a changed file."""
    file_path: str = Field(..., description="Path to the changed file")
    changed_functions: List[str] = Field(default_factory=list, description="Function names that were added/modified")
    changed_rules: List[ChangedRule] = Field(default_factory=list, description="Validation rules added/modified")
    new_conditionals: int = Field(default=0, description="Count of new if/else/switch branches")
    changed_constants: List[str] = Field(default_factory=list, description="New/changed constants (messages, limits)")
    affected_domain_terms: List[str] = Field(default_factory=list, description="Domain terms affected (password, token, etc.)")


class CoverageGap(BaseModel):
    """Represents a coverage gap in changed code."""
    file_path: str = Field(..., description="File with uncovered code")
    uncovered_branches: List[str] = Field(default_factory=list, description="Human-readable descriptions of uncovered branches")
    related_requirement_ids: List[str] = Field(default_factory=list, description="Requirements linked to this gap")
    risk: str = Field(..., description="Risk level: HIGH, MEDIUM, LOW")
    gap_type: str = Field(..., description="Type of gap: NEW_BRANCH, UNCOVERED_FUNCTION, SHALLOW_COVERAGE")


class DetailedScenario(BaseModel):
    precondition: str = Field(..., description="Precondition for the test scenario")
    test_input: str = Field(..., description="Specific test input details")
    expected_result: str = Field(..., description="Expected test result")
    test_layer: str = Field(..., description="Validation layer (e.g. API, UI, E2E)")


class EvidenceItem(BaseModel):
    requirement_id: str = Field(..., description="Requirement ID")
    requirement_title: str = Field(..., description="Requirement title")
    verifying_test: str = Field(..., description="Verifying test name")
    test_status: str = Field(..., description="Test status (e.g., PASSED, FAILED, SKIPPED)")
    test_freshness: str = Field(..., description="Test freshness (e.g., FRESH, STALE)")
    impact_reason: str = Field(..., description="Impact reason")
    final_bucket: str = Field(..., description="Final bucket classification, e.g. ALREADY_VERIFIED")


class MissingTestRecommendation(BaseModel):
    """Represents a recommended missing test."""
    id: str = Field(..., description="Unique identifier for the recommendation")
    title: str = Field(..., description="Human-readable title of the recommended test")
    source: str = Field(..., description="Source: REQUIREMENT_GAP, COVERAGE_GAP, RISK_HEURISTIC")
    priority: int = Field(..., description="Priority: 1 (critical) to 5 (low)")
    risk_rationale: str = Field(..., description="Explanation of why this test is needed")
    suggested_test_scenario: str = Field(..., description="Short description of test steps")
    detailed_scenario: Optional[DetailedScenario] = Field(None, description="Detailed scenario details")
    linked_requirement_id: Optional[str] = Field(None, description="Linked requirement ID if applicable")
    linked_file: Optional[str] = Field(None, description="Linked file if applicable")
    linked_code_change: Optional[str] = Field(None, description="Linked code change description if applicable")
    estimated_effort: str = Field(..., description="Estimated effort: LOW, MEDIUM, HIGH")


class ScopeDiagnostics(BaseModel):
    """Diagnostic information for the scope."""
    generation_timestamp: datetime = Field(..., description="When the scope was generated")
    generation_duration_ms: Optional[int] = Field(None, description="Generation duration in milliseconds")
    rules_applied: List[str] = Field(default_factory=list, description="Rules applied during generation")
    warnings: List[str] = Field(default_factory=list, description="Warnings during generation")
    errors: List[str] = Field(default_factory=list, description="Errors during generation")
    # Phase 5.10: Change impact engine diagnostics
    change_impact_diagnostics: Optional[Any] = Field(None, description="Change impact engine diagnostics")


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
    integrity: Optional[ScopeIntegrityReport] = Field(None, description="Scope integrity validation report")
    # Phase 7: Unified view fields
    traceability_summary: Optional[TraceabilitySummary] = Field(None, description="Traceability summary from evidence graph")
    release_decision: Optional[ReleaseDecision] = Field(None, description="Unified release decision")
    # Phase 8: Gap analysis and missing test recommendations
    recommendations: List[MissingTestRecommendation] = Field(default_factory=list, description="Recommended missing tests for additional safety")
    evidence_items: List[EvidenceItem] = Field(default_factory=list, description="Evidence details for verifying tests")


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
    mode: Optional[ScopeMode] = Field(None, description="The mode used to generate this scope")
    error_code: Optional[str] = Field(None, description="Error code if failed")
    message: Optional[str] = Field(None, description="Error message if failed")
