"""
Change Impact Schemas for Phase 5 - Change Impact Engine v1

Pydantic schemas for change impact analysis, regression candidate selection,
and release action scope.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class ImpactType(str, Enum):
    """Impact type classification."""
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    CROSS_LAYER = "CROSS_LAYER"
    SECURITY_SENSITIVE = "SECURITY_SENSITIVE"
    UNCHANGED = "UNCHANGED"
    UNKNOWN = "UNKNOWN"


class FinalBucket(str, Enum):
    """Final bucket classification after evidence overlay."""
    REQUIRED = "REQUIRED"
    REVIEW_NEEDED = "REVIEW_NEEDED"
    ALREADY_VERIFIED = "ALREADY_VERIFIED"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"
    SAFE_TO_SKIP = "SAFE_TO_SKIP"
    DEFERRED_COVERAGE_DEBT = "DEFERRED_COVERAGE_DEBT"


class ReleaseAction(str, Enum):
    """Release action for each bucket."""
    NONE = "NONE"
    FIX_OR_RERUN = "FIX_OR_RERUN"
    RE_RUN = "RE_RUN"
    RUN_OR_CREATE_TEST = "RUN_OR_CREATE_TEST"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    VERIFY_FRESHNESS = "VERIFY_FRESHNESS"
    RUN_IF_TIME = "RUN_IF_TIME"


class ChangeInventory(BaseModel):
    """Change inventory from PR data."""
    changed_files: List[str] = Field(default_factory=list, description="List of changed file paths")
    changed_components: List[str] = Field(default_factory=list, description="Extracted component names")
    changed_layers: List[str] = Field(default_factory=list, description="Layer classifications (backend, api, ui, etc.)")
    changed_domains: List[str] = Field(default_factory=list, description="Domain classifications (auth, user, payment, etc.)")
    changed_flows: List[str] = Field(default_factory=list, description="Business flows affected")
    security_sensitive: bool = Field(default=False, description="Whether changes affect security-sensitive areas")
    change_keywords: List[str] = Field(default_factory=list, description="Keywords extracted from changes")
    risk_tags: List[str] = Field(default_factory=list, description="Risk tags for changes")


class ImpactedBehavior(BaseModel):
    """Single impacted behavior."""
    flow: str = Field(..., description="Business flow name")
    impact_type: ImpactType = Field(..., description="Type of impact")
    impact_confidence: float = Field(..., description="Confidence score 0.0-1.0")
    impact_reason: str = Field(..., description="Reason for impact classification")
    changed_files: List[str] = Field(default_factory=list, description="Changed files causing this impact")
    security_sensitive: bool = Field(default=False, description="Whether this is security-sensitive")


class ACImpactMatrix(BaseModel):
    """Impact matrix for a single acceptance criterion."""
    ac_id: str = Field(..., description="AC ID")
    title: str = Field(..., description="AC title")
    business_flow: str = Field(..., description="Primary business flow")
    impact_type: ImpactType = Field(..., description="Type of impact")
    impact_confidence: float = Field(..., description="Confidence score 0.0-1.0")
    impact_reason: str = Field(..., description="Reason for impact classification")
    changed_files_related: List[str] = Field(default_factory=list, description="Changed files related to this AC")
    security_sensitive: bool = Field(default=False, description="Whether this is security-sensitive")
    expected_regression_priority: str = Field(..., description="Expected priority before evidence overlay")


class RegressionCandidate(BaseModel):
    """Regression candidate before evidence overlay."""
    id: str = Field(..., description="Candidate ID")
    title: str = Field(..., description="Candidate title")
    source_ac_id: Optional[str] = Field(None, description="Source AC ID if applicable")
    source_test_id: Optional[str] = Field(None, description="Source test ID if applicable")
    business_flow: str = Field(..., description="Business flow")
    impact_type: ImpactType = Field(..., description="Type of impact")
    impact_reason: str = Field(..., description="Reason for impact classification")
    changed_files: List[str] = Field(default_factory=list, description="Changed files causing impact")
    changed_components: List[str] = Field(default_factory=list, description="Changed components")
    changed_routes: List[str] = Field(default_factory=list, description="Changed routes")
    mapped_tests: List[str] = Field(default_factory=list, description="Mapped test IDs")
    risk_level: str = Field(..., description="Risk level (CRITICAL, HIGH, MEDIUM, LOW)")
    selected_by_mode: str = Field(..., description="Mode that selected this candidate")
    candidate_reason: str = Field(..., description="Reason for candidate selection")


class ReleaseActionScope(BaseModel):
    """Final release action scope after evidence overlay."""
    id: str = Field(..., description="Item ID")
    title: str = Field(..., description="Item title")
    source_ac_id: Optional[str] = Field(None, description="Source AC ID")
    source_test_id: Optional[str] = Field(None, description="Source test ID")
    business_flow: str = Field(..., description="Business flow")
    impact_type: ImpactType = Field(..., description="Type of impact")
    impact_reason: str = Field(..., description="Reason for impact classification")
    changed_files: List[str] = Field(default_factory=list, description="Changed files")
    changed_components: List[str] = Field(default_factory=list, description="Changed components")
    changed_routes: List[str] = Field(default_factory=list, description="Changed routes")
    mapped_tests: List[str] = Field(default_factory=list, description="Mapped test IDs")
    execution_status: str = Field(..., description="Execution status (PASSED, FAILED, NOT_RUN, etc.)")
    freshness_status: str = Field(..., description="Freshness status (FRESH, STALE, UNKNOWN)")
    risk_level: str = Field(..., description="Risk level")
    selected_by_mode: str = Field(..., description="Mode that selected this")
    candidate_reason: str = Field(..., description="Reason for candidate selection")
    final_bucket: FinalBucket = Field(..., description="Final bucket after evidence overlay")
    release_action: ReleaseAction = Field(..., description="Release action")
    evidence_reason: str = Field(..., description="Reason for evidence-based classification")
    selected_by_impact: bool = Field(..., description="Whether this was selected by impact analysis")
    reason_code: Optional[str] = Field(None, description="Reason code for assignment")


from app.models.change_summary import ChangeSummary

class ChangeImpactModel(BaseModel):
    """Complete change impact model."""
    change_inventory: ChangeInventory = Field(..., description="Change inventory")
    directly_impacted_flows: List[ImpactedBehavior] = Field(default_factory=list, description="Directly impacted flows")
    indirectly_impacted_flows: List[ImpactedBehavior] = Field(default_factory=list, description="Indirectly impacted flows")
    cross_layer_impacts: List[ImpactedBehavior] = Field(default_factory=list, description="Cross-layer impacts")
    security_sensitive_impacts: List[ImpactedBehavior] = Field(default_factory=list, description="Security-sensitive impacts")
    unknown_impacts: List[ImpactedBehavior] = Field(default_factory=list, description="Unknown impacts")
    ac_impact_matrix: List[ACImpactMatrix] = Field(default_factory=list, description="AC impact matrix")
    regression_candidates: List[RegressionCandidate] = Field(default_factory=list, description="Regression candidates")
    release_action_scope: List[ReleaseActionScope] = Field(default_factory=list, description="Final release action scope")
    change_summaries: Optional[Dict[str, ChangeSummary]] = Field(default=None, description="Semantic change summaries per file")


class ScopeMode(str, Enum):
    """Scope generation mode."""
    TARGETED = "targeted"
    RISK_BASED = "risk_based"
    FULL_SUITE = "full_suite"


class ChangeImpactDiagnostics(BaseModel):
    """Diagnostics for change impact engine."""
    change_inventory: ChangeInventory = Field(..., description="Change inventory")
    impacted_flows: Dict[str, List[ImpactedBehavior]] = Field(default_factory=dict, description="Impacted flows by type")
    ac_impact_matrix: List[ACImpactMatrix] = Field(default_factory=list, description="AC impact matrix")
    candidate_selection: Dict[str, Any] = Field(default_factory=dict, description="Candidate selection details")
    evidence_overlay: Dict[str, Any] = Field(default_factory=dict, description="Evidence overlay details")
    mode_strategy: str = Field(..., description="Mode strategy used")
    release_action_counts: Dict[str, int] = Field(default_factory=dict, description="Counts by release action")


# Legacy schemas for backward compatibility
class ChangeImpactResponse(BaseModel):
    """Change impact response for a requirement or test (legacy)."""
    level: str = Field(..., description="Impact level: DIRECT, RELATED, INDIRECT, NONE")
    matchedFiles: List[str] = Field(default_factory=list, description="List of matched files")
    matchedPatterns: List[str] = Field(default_factory=list, description="List of matched patterns")
    explanation: str = Field(..., description="Human-readable explanation of impact")


class RequirementChangeImpactRequest(BaseModel):
    """Request to analyze change impact for requirements (legacy)."""
    changedFiles: List[str] = Field(..., description="List of changed file paths")
    requirements: List[Dict[str, Any]] = Field(..., description="List of requirements with id, title, and optional linked_files")


class TestChangeImpactRequest(BaseModel):
    """Request to analyze change impact for tests (legacy)."""
    changedFiles: List[str] = Field(..., description="List of changed file paths")
    tests: List[Dict[str, Any]] = Field(..., description="List of tests with id, name, and optional linked_files")


class ChangeImpactAnalysisResponse(BaseModel):
    """Response for change impact analysis (legacy)."""
    results: Dict[str, ChangeImpactResponse] = Field(..., description="Dict mapping IDs to impact results")
    summary: Dict[str, int] = Field(..., description="Summary counts for each impact level")


class ImpactSummaryResponse(BaseModel):
    """Response with impact level summary (legacy)."""
    direct: int = Field(..., description="Count of DIRECT impacts")
    related: int = Field(..., description="Count of RELATED impacts")
    indirect: int = Field(..., description="Count of INDIRECT impacts")
    none: int = Field(..., description="Count of NONE impacts")
