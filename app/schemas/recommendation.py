from datetime import datetime
from uuid import UUID
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, model_validator

class SkippedSummary(BaseModel):
    skipped_count: int
    skipped_reason_summary: str
    top_skipped_examples: List[str]

    class Config:
        from_attributes = True

class RecommendationRunCreate(BaseModel):
    repository_id: UUID
    pr_id: str = Field(..., min_length=1)
    changed_files: List[str] = Field(default_factory=list)
    triggered_by: str = Field(..., min_length=1)
    engine_version: Optional[str] = "v3.0.0"
    readiness_acknowledged: Optional[bool] = False
    readiness_snapshot: Optional[Dict[str, Any]] = None
    generated_from_repository_id: Optional[UUID] = None
    generated_from_pull_request_id: Optional[UUID] = None
    generation_mode: Optional[str] = Field(default="confident", description="'draft' or 'confident'")

# Request model for the generate endpoint
class RecommendationGenerateRequest(BaseModel):
    repository_id: UUID
    pull_request_id: str = Field(..., min_length=1)
    pr_id: str = Field(default="", description="Alias for pull_request_id for backward compatibility")
    triggered_by: str = Field(..., min_length=1)
    changed_files: List[str] = Field(default_factory=list)
    engine_version: Optional[str] = "v3.0.0"
    readiness_acknowledged: Optional[bool] = False
    mode: Optional[str] = Field(default="confident", description="Generation mode: 'draft' or 'confident'")

    @model_validator(mode="before")
    @classmethod
    def resolve_pr_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            pr_val = data.get("pull_request_id") or data.get("pr_id")
            if pr_val:
                data["pull_request_id"] = pr_val
                data["pr_id"] = pr_val
        return data

    @model_validator(mode="after")
    def sync_pr_id(self) -> "RecommendationGenerateRequest":
        """Ensure pr_id is set from pull_request_id after validation."""
        if not self.pr_id and self.pull_request_id:
            # Use object.__setattr__ to avoid validation issues
            object.__setattr__(self, "pr_id", self.pull_request_id)
        return self

# Optional body payload for pull-request recommendation generation
class RecommendationGeneratePayload(BaseModel):
    readiness_acknowledged: Optional[bool] = False
    mode: Optional[str] = Field(default=None, description="Generation mode: 'draft' or 'confident'. Defaults to 'confident'.")

class RecommendationTestResponse(BaseModel):
    id: UUID
    recommendation_run_id: UUID
    test_case_id: str
    reason_type: str
    reason_details: Dict[str, Any]
    priority_score: float

    class Config:
        from_attributes = True

class BehaviorScenarioCoverageMatrix(BaseModel):
    scenario_id: str
    scenario_title: str
    behavior_id: str
    behavior_name: str
    journey_id: Optional[str] = None
    journey_name: Optional[str] = None
    impact_level: str  # CRITICAL, HIGH, MEDIUM, LOW
    impact_type: str = "INDIRECT"  # DIRECT, INDIRECT
    priority: str  # BLOCKER, MUST, SHOULD, OPTIONAL
    coverage_status: str  # VERIFIED_ON_CURRENT_PR, COVERED_BY_EXISTING_TEST, PARTIALLY_COVERED, MISSING_AUTOMATED_COVERAGE, MANUAL_VALIDATION_RECOMMENDED
    coverage_confidence: str  # HIGH, MODERATE, LOW
    sufficiency: str  # SUFFICIENT, PARTIAL, INSUFFICIENT, UNKNOWN
    existing_tests: List[str] = []
    current_pr_execution_status: str  # EXECUTED, NOT_EXECUTED, UNKNOWN
    recommended_actions: List[str] = []
    reasons: List[str] = []
    related_changed_files: List[str] = []
    evidence_summary: Optional[List[Dict[str, Any]]] = None
    behavior_confidence: Optional[str] = None
    behavior_risk_level: Optional[str] = None

    class Config:
        from_attributes = True


class RecommendationRunResponse(BaseModel):
    id: UUID
    repository_id: UUID
    pr_id: str
    triggered_by: str
    evidence_quality: str
    engine_version: str
    ruleset_version: str
    degradation_policy_version: str
    recommendation_reasoning_summary: str
    created_at: datetime
    
    # New safety, lineage, and runtime fields
    coverage_report_id: Optional[UUID] = None
    dependency_state_hash: Optional[str] = None
    test_history_window_start: Optional[datetime] = None
    test_history_window_end: Optional[datetime] = None
    flakiness_profile_hash: Optional[str] = None
    recommendation_mode: Optional[str] = None
    optimization_allowed: bool = True
    unsafe_for_optimization: bool = False
    evidence_quality_reasons: Optional[List[str]] = None
    estimated_runtime_seconds: Optional[float] = 0.0
    runtime_confidence: Optional[str] = "LOW"
    runtime_source: Optional[str] = "fallback_default"
    skipped_reason_summary: Optional[str] = None
    skipped_count: int = 0
    top_skipped_examples: Optional[List[str]] = None
    correlation_id: Optional[str] = None
    impact_profile: Optional[Dict[str, Any]] = None
    behavior_coverage_matrix: Optional[List[BehaviorScenarioCoverageMatrix]] = None
    business_intent_coverage_matrix: Optional[Dict[str, Any]] = None
    requirement_gap_report: Optional[Dict[str, Any]] = None
    business_intent: Optional[Dict[str, Any]] = Field(None, description="Business intent summary and analysis")
    acceptance_criteria: Optional[List[Dict[str, Any]]] = Field(None, description="Acceptance criteria with coverage status")
    requirement_gaps: Optional[List[Dict[str, Any]]] = Field(None, description="Requirement gaps detected")
    completeness_assessment: Optional[Dict[str, Any]] = Field(None, description="Completeness score and dimension breakdown")

    # Generation gate fields
    is_draft: bool = False
    generation_mode: Optional[str] = None
    generation_blocked_reason: Optional[str] = None

    # Readiness and acknowledgement fields
    readiness_acknowledged: Optional[bool] = False
    readiness_acknowledged_at: Optional[datetime] = None
    readiness_acknowledged_missing_inputs: Optional[List[str]] = None
    readiness_decision: Optional[str] = None

    # Staleness fields
    input_stale: bool = False
    stale_reason: Optional[str] = None
    stale_since: Optional[datetime] = None
    stale_input_types: Optional[List[str]] = None

    # Input 1 snapshot fields
    head_commit_sha_at_generation: Optional[str] = None
    base_commit_sha_at_generation: Optional[str] = None
    merge_commit_sha_at_generation: Optional[str] = None
    changed_files_snapshot_json: Optional[List[Dict[str, Any]]] = None
    pr_package_ready_at_generation: Optional[bool] = None
    pr_snapshot_id: Optional[UUID] = None

    # Input 2 snapshot fields
    requirement_package_id_at_generation: Optional[UUID] = None
    requirement_package_snapshot_json: Optional[Dict[str, Any]] = None
    requirement_groups_snapshot_json: Optional[List[Dict[str, Any]]] = None
    acceptance_criteria_snapshot_json: Optional[List[Dict[str, Any]]] = None
    stable_ac_keys_snapshot_json: Optional[List[str]] = None
    requirement_package_ready_at_generation: Optional[bool] = None

    tests: List[RecommendationTestResponse] = []
    suggested_scenarios: List[SuggestedTestScenarioResponse] = []
    outcome: Optional["OutcomeSummary"] = None

    class Config:
        from_attributes = True


class OutcomeTestSummary(BaseModel):
    """Summary of test outcomes."""
    recommended_count: int = 0
    kept_count: int = 0
    removed_count: int = 0
    executed_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    not_run_count: int = 0


class OutcomeScenarioSummary(BaseModel):
    """Summary of scenario outcomes."""
    suggested_count: int = 0
    accepted_count: int = 0
    dismissed_count: int = 0
    executed_count: int = 0
    important_count: int = 0


class OutcomeOverrideSummary(BaseModel):
    """Summary of override outcomes."""
    added_tests_count: int = 0
    removed_tests_count: int = 0


class OutcomeSummary(BaseModel):
    """Summary of recommendation outcomes including tests, scenarios, overrides, and post-merge outcomes."""
    status: str = "NOT_CAPTURED"
    feedback: Optional[str] = None
    tests: OutcomeTestSummary = Field(default_factory=OutcomeTestSummary)
    scenarios: OutcomeScenarioSummary = Field(default_factory=OutcomeScenarioSummary)
    overrides: OutcomeOverrideSummary = Field(default_factory=OutcomeOverrideSummary)
    defect_escaped: bool = False
    rollback_occurred: bool = False

class OutcomeCreate(BaseModel):
    executed_tests: List[str] = Field(default_factory=list)
    manually_added_tests: List[str] = Field(default_factory=list)
    manually_removed_tests: List[str] = Field(default_factory=list)
    was_followed: bool
    override_reason: Optional[str] = None # LOW_TRUST, MISSING_COVERAGE, KNOWN_RISKY_AREA, etc.
    feedback: Optional[str] = None
    rollback_occurred: bool = False
    escaped_defect: bool = False

class OutcomeResponse(BaseModel):
    id: UUID
    recommendation_run_id: UUID
    executed_tests: List[str]
    manually_added_tests: List[str]
    manually_removed_tests: List[str]
    was_followed: bool
    override_reason: Optional[str]
    feedback: Optional[str]
    rollback_occurred: bool
    escaped_defect: bool
    created_at: datetime

    class Config:
        from_attributes = True

class FeedbackCreate(BaseModel):
    feedback_state: str = Field(..., description="Must be one of: useful, not_useful, missing_tests")
    details: Optional[str] = None


# Outcome Update Schemas
class OutcomeUpdate(BaseModel):
    outcome_status: Optional[str] = Field(None, description="SHOWN, ACCEPTED, PARTIALLY_ACCEPTED, IGNORED, SUPERSEDED, UNKNOWN")
    user_feedback: Optional[str] = Field(None, description="USEFUL, NOT_USEFUL, MISSING_TESTS, TOO_BROAD, TOO_NARROW, NOT_REVIEWED")
    feedback_comment: Optional[str] = None
    ignored_reason: Optional[str] = None
    defect_escaped: Optional[bool] = None
    rollback_occurred: Optional[bool] = None
    production_incident_url: Optional[str] = None


class TestOutcomeUpdate(BaseModel):
    recommendation_action: Optional[str] = Field(None, description="RUN_EXISTING_TEST, SKIP, OPTIONAL_MONITOR")
    execution_status: Optional[str] = Field(None, description="NOT_RUN, PASSED, FAILED, SKIPPED, UNKNOWN")
    engineer_decision: Optional[str] = Field(None, description="KEPT, REMOVED, NOT_DECIDED")
    actual_test_result_id: Optional[UUID] = None
    actual_test_run_id: Optional[UUID] = None
    duration_seconds: Optional[float] = None
    failure_message: Optional[str] = None



class LearnedPattern(BaseModel):
    """A learned pattern from outcome learning."""
    pattern_key: str
    signal_type: str
    strength: float
    confidence: float
    usage_count: int


class BehaviorLearningSignal(BaseModel):
    """Learning signals for a behavior."""
    behavior_id: str
    behavior_name: str
    signal_count: int
    last_seen_at: datetime


class LearningSummary(BaseModel):
    """Repository-level learning summary."""
    total_outcomes: int = 0
    useful_feedback_count: int = 0
    missing_tests_feedback_count: int = 0
    manually_added_tests_count: int = 0
    removed_tests_count: int = 0
    accepted_scenarios_count: int = 0
    escaped_defects_count: int = 0
    rollback_count: int = 0
    top_learned_patterns: List[LearnedPattern] = Field(default_factory=list)
    behaviors_with_most_signals: List[BehaviorLearningSignal] = Field(default_factory=list)


class ScenarioOutcomeUpdate(BaseModel):
    engineer_decision: Optional[str] = Field(None, description="ACCEPTED, DISMISSED, MARKED_IMPORTANT, NOT_DECIDED")
    execution_status: Optional[str] = Field(None, description="NOT_EXECUTED, PASSED, FAILED, BLOCKED, UNKNOWN")
    converted_to_test: Optional[bool] = None
    linked_test_identifier: Optional[str] = None
    comment: Optional[str] = None


class OverrideCreate(BaseModel):
    override_type: str = Field(..., description="TEST_ADDED, TEST_REMOVED, SCENARIO_ADDED, SCENARIO_REMOVED, PRIORITY_CHANGED")
    test_identifier: Optional[str] = None
    scenario_intent_key: Optional[str] = None
    reason: Optional[str] = None
    source: str = Field(default="MANUAL_UI", description="MANUAL_UI, CI_DIFF, API, IMPORTED")


class OutcomeDetailResponse(BaseModel):
    id: UUID
    recommendation_run_id: UUID
    workspace_id: UUID
    repository_id: UUID
    pull_request_id: Optional[UUID]
    outcome_status: str
    user_feedback: Optional[str]
    feedback_comment: Optional[str]
    ignored_reason: Optional[str]
    defect_escaped: bool
    rollback_occurred: bool
    production_incident_url: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestOutcomeDetailResponse(BaseModel):
    id: UUID
    recommendation_outcome_id: UUID
    recommendation_run_id: UUID
    recommended_test_id: Optional[UUID]
    test_identifier: str
    recommendation_action: str
    execution_status: str
    engineer_decision: str
    actual_test_result_id: Optional[UUID]
    actual_test_run_id: Optional[UUID]
    duration_seconds: Optional[float]
    failure_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScenarioOutcomeDetailResponse(BaseModel):
    id: UUID
    recommendation_outcome_id: UUID
    recommendation_run_id: UUID
    suggested_scenario_id: Optional[UUID]
    scenario_intent_key: str
    engineer_decision: str
    execution_status: str
    converted_to_test: bool
    linked_test_identifier: Optional[str]
    comment: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChangedFile(BaseModel):
    file_path: str
    status: str
    additions: int
    deletions: int
    previous_filename: Optional[str] = None

    class Config:
        from_attributes = True


class PREvidenceBundle(BaseModel):
    pull_request_id: UUID
    repository_id: UUID
    head_commit_sha: str
    changed_files: List[ChangedFile]
    pr_snapshot_id: Optional[UUID] = None
    sync_integrity_status: str
    evidence_health_status: str
    unsafe_for_optimization: bool
    recommendation_readiness_state: str
    readiness_reasons: List[str]

    class Config:
        from_attributes = True


class CoverageFileMapping(BaseModel):
    test_case_id: UUID
    stable_identity: str
    mapping_type: str
    confidence_score: str

    class Config:
        from_attributes = True


class AttachTestRunRequest(BaseModel):
    test_run_id: UUID


class CoverageEvidenceBundle(BaseModel):
    coverage_report_id: Optional[UUID] = None
    coverage_confidence: str
    coverage_is_stale: bool
    coverage_is_missing: bool
    coverage_links_by_file: Dict[str, List[CoverageFileMapping]]
    direct_test_mappings: List[str]
    heuristic_test_mappings: List[str]
    uncovered_changed_files: List[str]
    reasons: List[str]

    class Config:
        from_attributes = True


class HeuristicTestCandidate(BaseModel):
    source_file_path: str
    test_case_id: UUID
    stable_identity: str
    heuristic_type: str  # SAME_STEM / TEST_PREFIX_SUFFIX / SAME_DIRECTORY / MODULE_NAME_MATCH
    confidence_score: str  # MODERATE / LOW
    reason: str

    class Config:
        from_attributes = True


class HeuristicMappingBundle(BaseModel):
    heuristic_test_candidates: List[HeuristicTestCandidate]
    reasons: List[str]
    unresolved_files: List[str]

    class Config:
        from_attributes = True


class DependencyExpansionBundle(BaseModel):
    expanded_files: List[str]
    expansion_edges: Dict[str, List[str]]
    expansion_depth_reached: int
    limit_exceeded: bool
    dependency_state_hash: Optional[str] = None
    reasons: List[str]
    original_changed_files: List[str] = []
    expanded_dependent_files: List[str] = []
    traversal_edges: List[List[str]] = []
    depth_per_file: Dict[str, int] = {}
    expansion_limited: bool = False

    class Config:
        from_attributes = True


class HistoricalFailureTest(BaseModel):
    test_case_id: UUID
    stable_identity: str
    priority_score: float
    failed_at: datetime
    failure_count: int
    relevance_type: str  # DIRECT / DEPENDENCY_NEIGHBORHOOD / SAME_MODULE
    reason: str

    class Config:
        from_attributes = True


class HistoricalFailureBundle(BaseModel):
    historical_failure_tests: List[HistoricalFailureTest]
    test_history_window_start: datetime
    test_history_window_end: datetime
    reasons: List[str]

    class Config:
        from_attributes = True


class CandidateTestInput(BaseModel):
    test_case_id: UUID
    current_priority_score: float
    reasons: List[str]

    class Config:
        from_attributes = True


class AdjustedCandidateTest(BaseModel):
    test_case_id: UUID
    stable_identity: str
    priority_score: float
    reasons: List[str]
    is_excluded: bool
    is_flaky: bool
    status: str  # stable / unstable / quarantined
    warnings: List[str]
    alternative_to_quarantined: Optional[UUID] = None
    quarantined_alternatives: Optional[List[UUID]] = None

    class Config:
        from_attributes = True


class FlakyAdjustmentBundle(BaseModel):
    adjusted_candidates: List[AdjustedCandidateTest]
    flaky_profiles_used: List[Dict[str, Any]]
    evidence_quality_impact: str  # NONE / MILD_DEGRADATION / ONE_TIER_DEGRADATION
    reasoning_entries: List[Dict[str, Any]]

    class Config:
        from_attributes = True


class RankingCandidateInput(BaseModel):
    test_case_id: UUID
    reasons: List[str]
    base_priority_score: float
    evidence_sources: List[str]
    mapping_confidence: str
    flaky_status: Optional[str] = None
    historical_failure_score: Optional[float] = None

    class Config:
        from_attributes = True


class RankedCandidateTest(BaseModel):
    test_case_id: UUID
    stable_identity: str
    risk_value: float
    execution_cost: float
    priority_score: float
    reasons: List[str]
    evidence_sources: List[str]
    mapping_confidence: str
    flaky_status: Optional[str] = None
    is_critical: bool
    is_excluded: bool

    class Config:
        from_attributes = True


class RankedRecommendationBundle(BaseModel):
    ranked_candidates: List[RankedCandidateTest]
    total_runtime_seconds: float
    runtime_confidence: str  # HIGH / MODERATE / LOW
    reasons: List[str]

    class Config:
        from_attributes = True


class FallbackEvidenceBundle(BaseModel):
    pr_evidence_health: str  # HEALTHY / DEGRADED / INSUFFICIENT
    coverage_confidence: str  # HIGH / MODERATE / LOW / UNKNOWN / MISSING
    dependency_graph_confidence: str  # HIGH / MODERATE / LOW / UNKNOWN / MISSING
    flaky_profile_health: str  # HEALTHY / DEGRADED / RISKY
    evidence_consistency: str  # CONSISTENT / DEGRADED / INCONSISTENT
    unsafe_for_optimization: bool
    changed_files_availability: bool
    changed_area_risky: bool = False

    class Config:
        from_attributes = True


class FallbackDecision(BaseModel):
    recommendation_mode: str  # NORMAL / WIDENED / SAFE_FALLBACK / CRITICAL / FULL_REGRESSION
    optimization_allowed: bool
    fallback_level: str  # LEVEL_1 / LEVEL_2 / LEVEL_3 / LEVEL_4 / LEVEL_5
    evidence_quality: str  # HIGH / MODERATE / LOW / UNKNOWN
    reasons: List[str]
    expansion_depth: int
    include_historical_failures: bool
    include_critical_tests: bool
    full_regression_required: bool

    class Config:
        from_attributes = True


class ChangedFileSnapshot(BaseModel):
    file_path: str
    status: str
    additions: int
    deletions: int

    class Config:
        from_attributes = True


class TestInventorySnapshotItem(BaseModel):
    stable_identity: str
    canonical_identity_hash: Optional[str] = None
    dedupe_key: Optional[str] = None
    suite_name: str
    test_name: str
    raw_test_name: Optional[str] = None
    normalized_test_name: Optional[str] = None
    framework_name: Optional[str] = None
    framework_version: Optional[str] = None
    test_type: Optional[str] = None
    automation_status: Optional[str] = None
    source: Optional[str] = None
    source_metadata_json: Optional[Dict[str, Any]] = None
    file_path: Optional[str] = None
    module_or_area: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = True
    last_seen_at: Optional[str] = None
    last_seen_commit_sha: Optional[str] = None
    inventory_snapshot_sha: Optional[str] = None
    confidence: Optional[float] = None

    class Config:
        from_attributes = True


class CoverageFileSnapshotItem(BaseModel):
    file_path: str
    total_lines: int
    line_coverage_ratio: Optional[float] = None
    covered_lines: List[int]
    uncovered_lines: List[int]

    class Config:
        from_attributes = True


class FragilityPatternSnapshotItem(BaseModel):
    pattern_id: str
    risk_level: str
    confidence_score: float
    context: Dict[str, Any]

    class Config:
        from_attributes = True


class BehaviorSnapshotItem(BaseModel):
    behavior_id: str
    name: str
    slug: str
    confidence: Optional[str] = None
    risk_level: Optional[str] = None
    journey_id: Optional[str] = None
    discovery_source: Optional[str] = None

    class Config:
        from_attributes = True


class JourneySnapshotItem(BaseModel):
    journey_id: str
    name: str
    slug: str
    risk_level: Optional[str] = None
    discovery_source: Optional[str] = None

    class Config:
        from_attributes = True


class BehaviorEvidenceSnapshotItem(BaseModel):
    behavior_id: str
    evidence_type: str
    source_path: Optional[str] = None
    confidence: Optional[str] = None
    excerpt: Optional[str] = None

    class Config:
        from_attributes = True


class JourneyMappingSnapshotItem(BaseModel):
    journey_id: str
    behavior_id: str
    relationship_type: Optional[str] = None
    confidence: Optional[str] = None

    class Config:
        from_attributes = True


class RecommendationInputSnapshotResponse(BaseModel):
    repository_id: UUID
    pull_request_id: UUID
    changed_files: List[ChangedFileSnapshot]
    test_inventory: List[TestInventorySnapshotItem]
    coverage_files: List[CoverageFileSnapshotItem]
    evidence_counts: Dict[str, int]
    coverage_confidence: str
    readiness_state: str
    readiness_reasons: List[str]
    readiness_input_summary: Optional[Dict[str, Any]] = None
    fragility_patterns: List[FragilityPatternSnapshotItem]
    behaviors: List[BehaviorSnapshotItem] = []
    journeys: List[JourneySnapshotItem] = []
    behavior_evidences: List[BehaviorEvidenceSnapshotItem] = []
    journey_mappings: List[JourneyMappingSnapshotItem] = []
    behavior_confidence_summary: Dict[str, int] = {}
    journey_summary: Dict[str, Any] = {}
    business_intent_override: Optional[Dict[str, Any]] = None
    requirement_package: Optional[Dict[str, Any]] = None
    requirement_groups: List[Dict[str, Any]] = []
    acceptance_criteria: List[Dict[str, Any]] = []
    stable_ac_keys: List[str] = []
    business_behavior_mappings: List[Dict[str, Any]] = []
    behavior_scenario_coverages: List[Dict[str, Any]] = []
    changed_file_behavior_mappings: List[Dict[str, Any]] = []
    changed_file_paths_available: bool = False
    changed_files_source: Optional[str] = None
    behavior_map_source_commit_sha: Optional[str] = None
    behavior_map_generated_at: Optional[str] = None
    behavior_context_status: Optional[str] = None
    unmapped_product_files: List[str] = []
    unmapped_requirement_groups: List[str] = []
    generated_at: datetime
    input_snapshot_hash: str

    class Config:
        from_attributes = True


class RecommendationExplanationResponse(BaseModel):
    id: UUID
    recommendation_run_id: UUID
    test_id: str
    triggered_files: List[str]
    domains: List[str]
    testing_types: List[str]
    signals: List[str]
    score_breakdown: Dict[str, float]
    reason: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChangeImpactNode(BaseModel):
    id: str
    type: str
    label: str

    class Config:
        from_attributes = True


class ChangeImpactEdge(BaseModel):
    source: str
    target: str

    class Config:
        from_attributes = True


class ChangeImpactChain(BaseModel):
    file: str
    domain: str
    risk: str
    testing_type: str
    test: str

    class Config:
        from_attributes = True


class ChangeImpactGraphResponse(BaseModel):
    nodes: List[ChangeImpactNode]
    edges: List[ChangeImpactEdge]
    chains: List[ChangeImpactChain]

    class Config:
        from_attributes = True


class EvidenceGapResponse(BaseModel):
    severity: str
    message: str
    impact: str

    class Config:
        from_attributes = True


class MissingCoverageResponse(BaseModel):
    domain: str
    feature: str
    reason: str

    class Config:
        from_attributes = True


class SuggestedTestScenarioResponse(BaseModel):
    id: UUID
    recommendation_run_id: UUID
    title: str
    testing_type: str
    impacted_area: str
    priority: str
    preconditions: List[str]
    test_data: Dict[str, Any]
    steps: List[str]
    expected_result: str
    automation_candidate: bool
    related_changed_files: List[str]
    reason: str
    confidence: str
    source_signal: str
    created_at: datetime

    class Config:
        from_attributes = True
