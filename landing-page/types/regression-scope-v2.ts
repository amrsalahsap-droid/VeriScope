export enum ScopeGroup {
  REQUIRED = "REQUIRED",
  RECOMMENDED = "RECOMMENDED",
  OPTIONAL = "OPTIONAL",
  SAFE_TO_SKIP = "SAFE_TO_SKIP",
  EXCLUDED_ALREADY_VERIFIED = "EXCLUDED_ALREADY_VERIFIED",
  EXCLUDED_ALREADY_PASSED_TESTS = "EXCLUDED_ALREADY_PASSED_TESTS"
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

export interface ScopeDiagnostics {
  generation_timestamp: string;
  generation_duration_ms?: number;
  rules_applied: string[];
  warnings: string[];
  errors: string[];
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
}
