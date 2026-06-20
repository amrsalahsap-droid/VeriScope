import { 
  RegressionScopeV2, 
  ScopeGroup, 
  ScopeItem, 
  ScopeItemType, 
  EvidenceClassification, 
  RiskBand, 
  ChangeImpactLevel, 
  BusinessRiskLevel,
  ScopeSource
} from "../../types/regression-scope-v2";

export function mapLegacyItem(item: any, group: ScopeGroup): ScopeItem {
  // Map item_type
  let typeVal = ScopeItemType.REQUIREMENT;
  if (item.item_type === "TEST" || item.item_type === "EXCLUDED_ALREADY_PASSED" || item.test_id || item.class_name) {
    typeVal = ScopeItemType.TEST;
  }

  // Map risk level
  const hasReview = item.businessRiskReview && item.businessRiskReview.reviewStatus && item.businessRiskReview.reviewStatus !== 'UNREVIEWED';
  const rawRisk = hasReview
    ? (item.businessRiskReview.effectiveRiskLevel || item.businessRiskReview.originalRiskLevel)
    : (item.businessContext?.riskLevel);
  
  let riskBandVal = RiskBand.LOW;
  if (rawRisk === "CRITICAL") riskBandVal = RiskBand.CRITICAL;
  else if (rawRisk === "HIGH") riskBandVal = RiskBand.HIGH;
  else if (rawRisk === "MEDIUM") riskBandVal = RiskBand.MEDIUM;

  let bizRisk = BusinessRiskLevel.UNKNOWN;
  if (item.businessContext?.riskLevel === "CRITICAL" || item.businessRiskReview?.originalRiskLevel === "CRITICAL") bizRisk = BusinessRiskLevel.CRITICAL;
  else if (item.businessContext?.riskLevel === "HIGH" || item.businessRiskReview?.originalRiskLevel === "HIGH") bizRisk = BusinessRiskLevel.HIGH;
  else if (item.businessContext?.riskLevel === "MEDIUM" || item.businessRiskReview?.originalRiskLevel === "MEDIUM") bizRisk = BusinessRiskLevel.MEDIUM;
  else if (item.businessContext?.riskLevel === "LOW" || item.businessRiskReview?.originalRiskLevel === "LOW") bizRisk = BusinessRiskLevel.LOW;

  let effRisk = BusinessRiskLevel.UNKNOWN;
  if (item.businessRiskReview?.effectiveRiskLevel === "CRITICAL") effRisk = BusinessRiskLevel.CRITICAL;
  else if (item.businessRiskReview?.effectiveRiskLevel === "HIGH") effRisk = BusinessRiskLevel.HIGH;
  else if (item.businessRiskReview?.effectiveRiskLevel === "MEDIUM") effRisk = BusinessRiskLevel.MEDIUM;
  else if (item.businessRiskReview?.effectiveRiskLevel === "LOW") effRisk = BusinessRiskLevel.LOW;
  else if (item.businessRiskReview?.reviewStatus !== 'UNREVIEWED' && item.businessRiskReview?.reviewStatus) {
    effRisk = bizRisk;
  } else {
    effRisk = bizRisk;
  }

  // Evidence classification
  let evClass = EvidenceClassification.MISSING;
  if (group === ScopeGroup.EXCLUDED_ALREADY_VERIFIED || group === ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS) {
    evClass = EvidenceClassification.COVERED;
  } else if (group === ScopeGroup.RECOMMENDED) {
    evClass = EvidenceClassification.PARTIAL;
  }

  return {
    id: item.id || `item-${Math.random().toString(36).substring(2, 9)}`,
    readable_id: item.readable_id || item.id || "",
    title: item.title || item.suggested_test_title || item.id || "Untitled",
    item_type: typeVal,
    group: group,
    evidence_classification: evClass,
    risk_score: parseFloat(item.businessContext?.priority || "0") || (riskBandVal === RiskBand.CRITICAL ? 9.0 : riskBandVal === RiskBand.HIGH ? 7.5 : riskBandVal === RiskBand.MEDIUM ? 5.0 : 2.5),
    risk_band: riskBandVal,
    change_impact_level: item.risk_if_skipped === "HIGH" ? ChangeImpactLevel.DIRECT : item.risk_if_skipped === "MEDIUM" ? ChangeImpactLevel.RELATED : ChangeImpactLevel.NONE,
    business_risk_level: bizRisk,
    effective_risk_level: effRisk,
    suggested_action: item.suggested_action || "",
    reason: item.reason_excluded || item.classification || "",
    evidence_references: item.businessContext?.evidenceReferences || [],
    test_references: item.test_id ? [item.test_id] : [],
    can_auto_execute: true,
    is_required_for_release: group === ScopeGroup.REQUIRED,
    is_manual_only: false,
    diagnostics: {
      internal_requirement_id: item.id,
      internal_test_id: item.test_id,
      generation_rule: item.flow
    },
    // Preserve legacy fields
    businessContext: item.businessContext,
    businessRiskReview: item.businessRiskReview
  };
}

export function legacyRegressionScopeToV2(legacyScope: any): RegressionScopeV2 {
  if (!legacyScope) {
    throw new Error("No legacy scope provided");
  }

  const requiredLegacy = legacyScope.required_items || [];
  const reviewLegacy = legacyScope.review_items || [];
  const optionalLegacy = legacyScope.optional_safety_net_items || [];
  const excludedVerifiedLegacy = legacyScope.excluded_already_verified_requirements || [];
  const excludedPassedTestsLegacy = legacyScope.excluded_already_passed_tests || [];

  const required = requiredLegacy.map((item: any) => mapLegacyItem(item, ScopeGroup.REQUIRED));
  const recommended = reviewLegacy.map((item: any) => mapLegacyItem(item, ScopeGroup.RECOMMENDED));
  const optional = optionalLegacy.map((item: any) => mapLegacyItem(item, ScopeGroup.OPTIONAL));
  const verified = excludedVerifiedLegacy.map((item: any) => mapLegacyItem(item, ScopeGroup.EXCLUDED_ALREADY_VERIFIED));
  const passed = excludedPassedTestsLegacy.map((item: any) => mapLegacyItem(item, ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS));

  const requiredCount = required.length;
  const recommendedCount = recommended.length;
  const optionalCount = optional.length;
  const safeToSkipCount = 0;
  const totalExecutableCount = requiredCount + recommendedCount + optionalCount;

  const executionPlan = {
    required_count: requiredCount,
    recommended_count: recommendedCount,
    optional_count: optionalCount,
    safe_to_skip_count: safeToSkipCount,
    total_executable_count: totalExecutableCount,
    estimated_execution_reduction: 0.0,
    confidence_level: 100.0,
    plan_summary: `Run ${totalExecutableCount} items.`,
    advisory_notice: "Generated from legacy regression scope."
  };

  const groups: Record<string, any> = {
    [ScopeGroup.REQUIRED]: {
      group: ScopeGroup.REQUIRED,
      count: requiredCount,
      items: required
    },
    [ScopeGroup.RECOMMENDED]: {
      group: ScopeGroup.RECOMMENDED,
      count: recommendedCount,
      items: recommended
    },
    [ScopeGroup.OPTIONAL]: {
      group: ScopeGroup.OPTIONAL,
      count: optionalCount,
      items: optional
    },
    [ScopeGroup.EXCLUDED_ALREADY_VERIFIED]: {
      group: ScopeGroup.EXCLUDED_ALREADY_VERIFIED,
      count: verified.length,
      items: verified
    },
    [ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS]: {
      group: ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS,
      count: passed.length,
      items: passed
    }
  };

  const exclusions = {
    already_verified_count: verified.length,
    already_passed_tests_count: passed.length,
    already_verified_items: verified,
    already_passed_test_items: passed
  };

  const optimization_metrics = {
    current_regression_size: totalExecutableCount,
    optimized_required_count: requiredCount,
    optimized_recommended_count: recommendedCount,
    optimized_optional_count: optionalCount,
    safe_to_skip_count: safeToSkipCount,
    optimization_percentage: 0.0,
    execution_reduction: 0.0,
    coverage_confidence: 100.0
  };

  const riskReviewsCount = [...required, ...recommended].filter(
    item => item.businessRiskReview && item.businessRiskReview.reviewStatus !== "UNREVIEWED"
  ).length;

  const overriddenCount = [...required, ...recommended].filter(
    item => item.businessRiskReview && item.businessRiskReview.reviewStatus === "OVERRIDDEN"
  ).length;

  const needsDiscussionCount = [...required, ...recommended].filter(
    item => item.businessRiskReview && item.businessRiskReview.reviewStatus === "NEEDS_DISCUSSION"
  ).length;

  const governance = {
    risk_reviews_count: riskReviewsCount,
    overridden_count: overriddenCount,
    needs_discussion_count: needsDiscussionCount,
    release_decision_required: true,
    release_decision_status: legacyScope.health_at_creation || "PENDING"
  };

  const diagnostics = {
    generation_timestamp: legacyScope.created_at || new Date().toISOString(),
    generation_duration_ms: 0,
    rules_applied: legacyScope.generation_rules_applied || [],
    warnings: [],
    errors: legacyScope.diagnostics || []
  };

  return {
    recommendation_run_id: legacyScope.recommendation_run_id || "",
    snapshot_hash: legacyScope.source_evidence_graph_snapshot?.snapshot_hash || "",
    generated_at: legacyScope.created_at || new Date().toISOString(),
    scope_type: legacyScope.scope_type || "targeted",
    source: ScopeSource.HYBRID,
    summary: legacyScope.summary || "",
    execution_plan: executionPlan,
    groups: groups,
    exclusions: exclusions,
    optimization_metrics: optimization_metrics,
    governance: governance,
    diagnostics: diagnostics
  };
}
