export enum ScopeGroup {
  REQUIRED = "REQUIRED",
  REVIEW_NEEDED = "REVIEW_NEEDED",
  RECOMMENDED = "RECOMMENDED",
  OPTIONAL = "OPTIONAL",
  SAFE_TO_SKIP = "SAFE_TO_SKIP",
  EXCLUDED_ALREADY_VERIFIED = "EXCLUDED_ALREADY_VERIFIED",
  EXCLUDED_ALREADY_PASSED_TESTS = "EXCLUDED_ALREADY_PASSED_TESTS",
  DEFERRED_COVERAGE_DEBT = "DEFERRED_COVERAGE_DEBT"
}

export enum ScopeItemType {
  REQUIREMENT = "REQUIREMENT",
  TEST = "TEST",
  SCENARIO = "SCENARIO",
  MANUAL_TEST = "MANUAL_TEST"
}

export enum EvidenceClassification {
  COVERED = "COVERED",
  PARTIAL = "PARTIAL",
  MISSING = "MISSING",
  TRACEABILITY = "TRACEABILITY"
}

export enum RiskBand {
  CRITICAL = "CRITICAL",
  HIGH = "HIGH",
  MEDIUM = "MEDIUM",
  LOW = "LOW"
}

export enum ChangeImpactLevel {
  DIRECT = "DIRECT",
  RELATED = "RELATED",
  INDIRECT = "INDIRECT",
  NONE = "NONE"
}

export enum BusinessRiskLevel {
  CRITICAL = "CRITICAL",
  HIGH = "HIGH",
  MEDIUM = "MEDIUM",
  LOW = "LOW",
  UNKNOWN = "UNKNOWN"
}

export enum ScopeMode {
  TARGETED = "targeted",
  RISK_BASED = "risk_based",
  FULL = "full"
}

export enum ScopeSource {
  EVIDENCE_BASED = "evidence_based",
  RISK_BASED = "risk_based",
  MANUAL = "manual",
  HYBRID = "hybrid"
}

export interface ScopeItemDiagnostics {
  internal_requirement_id?: string;
  internal_test_id?: string;
  generation_rule?: string;
  confidence_score?: number;
  last_updated?: string;
}

export interface ScopeItem {
  id: string;
  readable_id: string;
  source_ac_number?: number;
  title: string;
  item_type: ScopeItemType;
  group: ScopeGroup;
  evidence_classification: EvidenceClassification;
  risk_score: number;
  risk_band: RiskBand;
  change_impact_level: ChangeImpactLevel;
  business_risk_level: BusinessRiskLevel;
  effective_risk_level: BusinessRiskLevel;
  suggested_action: string;
  reason: string;
  evidence_references: string[];
  test_references: string[];
  can_auto_execute: boolean;
  execution_status?: string;
  estimated_effort?: string;
  estimated_effort_minutes?: number;
  is_required_for_release: boolean;
  is_manual_only: boolean;
  provider?: string;
  external_id?: string;
  diagnostics?: ScopeItemDiagnostics;
  // Phase 6.4: Manual evidence risk adjustment fields
  manual_contribution_status?: string;
  generated_risk_band?: string;
  residual_risk_band?: string;
  risk_adjustment_reason?: string;
  risk_adjustment_delta?: number;
  // Phase 6.5B: Manual evidence governance status
  governanceStatus?: "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "CHALLENGED" | "EXPIRED";
  // Release action classification fields
  release_action?: string;
  freshness_status?: string;
  freshness_reason?: string;
  mapping_status?: string;
  // Safe to Skip evidence
  skip_evidence?: {
    covered_files: string[];
    changed_files_overlap: string[];
    last_run_timestamp?: string;
    last_run_commit_sha?: string;
    last_run_status: string;
    not_in_changed_files: boolean;
    skip_confidence_pct: number;
    skip_confidence_factors: string[];
  };
  governanceReviewer?: string;
  governanceReviewedAt?: string;
  governanceReviewNote?: string;
  businessContext?: {
    riskLevel?: string;
    priority?: string;
    businessImpact?: string;
    userImpact?: string;
    riskReasons?: string[];
    evidenceReferences?: string[];
    whatWouldMakeReleaseSafe?: string;
  };
  businessRiskReview?: {
    reviewStatus?: string;
    originalRiskLevel?: string;
    originalPriority?: string;
    reviewedRiskLevel?: string;
    reviewedPriority?: string;
    effectiveRiskLevel?: string;
    effectivePriority?: string;
    reviewerName?: string;
    reviewNote?: string;
    updatedAt?: string;
  };
  // Mapping confidence fields
  mapping_type?: string;
  mapping_confidence?: number;
  mapping_reason?: string;
  linked_test_count?: number;
  linked_tests?: string[];
  test_run_commit_sha?: string;
  pull_request_head_sha?: string;
}

export interface ScopeGroupSummary {
  group: ScopeGroup;
  count: number;
  items: ScopeItem[];
}

export interface ExecutionPlan {
  required_count: number;
  recommended_count: number;
  optional_count: number;
  safe_to_skip_count: number;
  review_needed_count?: number;
  deferred_coverage_debt_count?: number;
  total_executable_count: number;
  estimated_execution_reduction: number;
  confidence_level: number;
  plan_summary: string;
  advisory_notice: string;
  manual_required_count?: number;
  manual_recommended_count?: number;
  manual_optional_count?: number;
  manual_safe_to_skip_count?: number;
  automated_required_count?: number;
  automated_recommended_count?: number;
  manual_estimated_minutes?: number;
  automated_estimated_minutes?: number;
}

export type RegressionScopeExecutionPlan = ExecutionPlan;

export interface ScopeExclusions {
  already_verified_count: number;
  already_passed_tests_count: number;
  already_verified_items: ScopeItem[];
  already_passed_test_items: ScopeItem[];
}

export interface ScopeOptimizationMetrics {
  current_regression_size: number;
  optimized_required_count: number;
  optimized_recommended_count: number;
  optimized_optional_count: number;
  safe_to_skip_count: number;
  optimization_percentage: number;
  execution_reduction: number;
  coverage_confidence: number;
}

export interface ScopeGovernance {
  risk_reviews_count: number;
  overridden_count: number;
  needs_discussion_count: number;
  release_decision_required: boolean;
  release_decision_status?: string;
}

export interface TraceabilitySummary {
  total_requirements: number;
  covered: number;
  missing: number;
  not_mapped: number;
  review_required: number;
  unknown_statuses: string[];
}

export interface ReleaseDecision {
  verdict: string;
  reason: string;
  required_count: number;
  recommended_count: number;
  already_verified_count: number;
  source_mode: string;
}

export interface ChangedRule {
  rule_name: string;
  rule_type: string;
  file_path: string;
  line_number?: number;
}

export interface ChangeSummary {
  file_path: string;
  changed_functions: string[];
  changed_rules: ChangedRule[];
  new_conditionals: number;
  changed_constants: string[];
  affected_domain_terms: string[];
}

export interface CoverageGap {
  file_path: string;
  uncovered_branches: string[];
  related_requirement_ids: string[];
  risk: string;
  gap_type: string;
}

export interface DetailedScenario {
  precondition: string;
  test_input: string;
  expected_result: string;
  test_layer: string;
}

export interface EvidenceItem {
  requirement_id: string;
  requirement_title: string;
  verifying_test: string;
  test_status: string;
  test_freshness: string;
  impact_reason: string;
  final_bucket: string;
}

export interface MissingTestRecommendation {
  id: string;
  title: string;
  source: string;
  priority: number;
  risk_rationale: string;
  suggested_test_scenario: string;
  detailed_scenario?: DetailedScenario;
  linked_requirement_id?: string;
  linked_file?: string;
  estimated_effort: string;
}

export interface ScopeDiagnostics {
  generation_timestamp: string;
  generation_duration_ms?: number;
  rules_applied: string[];
  warnings: string[];
  errors: string[];
  change_impact_diagnostics?: any;
}

export interface ScopeIntegrityReport {
  integrity_status: "PASS" | "FAIL";
  integrity_errors: string[];
  integrity_warnings: string[];
  total_unique_logical_items: number;
  bucket_sum: number;
  duplicate_identities: string[];
}

export interface RegressionScopeV2 {
  recommendation_run_id: string;
  snapshot_hash: string;
  generated_at: string;
  scope_type: string;
  source: ScopeSource;
  summary: string;
  execution_plan: ExecutionPlan;
  groups: Record<string, ScopeGroupSummary>;
  exclusions: ScopeExclusions;
  optimization_metrics: ScopeOptimizationMetrics;
  governance: ScopeGovernance;
  diagnostics: ScopeDiagnostics;
  integrity?: ScopeIntegrityReport;
  // Phase 7: Unified view fields
  traceability_summary?: TraceabilitySummary;
  release_decision?: ReleaseDecision;
  // Phase 8: Gap analysis and missing test recommendations
  recommendations: MissingTestRecommendation[];
  evidence_items?: EvidenceItem[];
}

// Part 9: PR Package Types for Input 1 Readiness
export type ChangedFileStatus = "added" | "modified" | "deleted" | "renamed" | string;

export interface ChangedFile {
  file_path: string;
  previous_file_path?: string | null;
  status: ChangedFileStatus;
  additions?: number;
  deletions?: number;
  patch_summary?: string | null;
  file_sha?: string | null;
  patch_hash?: string | null;
  detected_layer?: string | null;
  detected_component?: string | null;
  detected_flow?: string | null;
}

export type PRPackageReadinessStatus = "READY" | "PARTIAL" | "BLOCKED" | "OUTDATED";

export interface PRPackageReadiness {
  status: PRPackageReadinessStatus;
  confidence?: number;
  can_generate_draft_plan?: boolean;
  can_generate_confident_regression_plan?: boolean;
  blockers: string[];
  warnings: string[];
}

export interface PRPackageSnapshot {
  head_commit_sha_at_generation?: string | null;
  base_commit_sha_at_generation?: string | null;
  merge_commit_sha_at_generation?: string | null;
  changed_files_count_at_generation?: number;
  is_stale: boolean;
  stale_reason?: string | null;
  current_head_sha?: string | null;
  snapshot_head_sha?: string | null;
}

export interface PRPackage {
  repository_id: string;
  pull_request_id: string;
  pr_number?: number;
  title?: string;
  source_branch?: string;
  target_branch?: string;
  head_commit_sha?: string;
  base_commit_sha?: string;
  merge_commit_sha?: string | null;
  changed_files_count: number;
  changed_files: ChangedFile[];
  snapshot?: PRPackageSnapshot;
  readiness: PRPackageReadiness;
}
