/**
 * Centralized CTA resolver for recommendation readiness states.
 * Ensures consistent CTA labels and actions across PR rows, modal footers, and recommended action cards.
 */

export interface ReadinessState {
  readiness_level: string;
  expected_confidence: string;
  readiness_score: number;
  can_generate: boolean;
  blocking_inputs: Array<{ key: string; label: string }>;
  missing_inputs: Array<{ key: string; label: string; severity: string }>;
  optional_inputs: Array<{ key: string; label: string }>;
  latest_recommendation?: {
    exists: boolean;
    input_stale: boolean;
  };
  // Part 6: PR package readiness for Input 1
  pr_package?: {
    readiness_status: "READY" | "PARTIAL" | "BLOCKED" | "OUTDATED";
    can_generate_confident_regression_plan?: boolean;
    blockers?: string[];
    warnings?: string[];
    snapshot_is_stale?: boolean;
  };
  recommendation_audit?: {
    status: "NO_RECOMMENDATION_YET" | "AUDITABLE" | "OUTDATED" | "LEGACY_NO_SNAPSHOT" | "UNKNOWN";
    recommendation_run_id?: string;
  };
}

export interface CTAAction {
  primaryLabel: string;
  secondaryLabel?: string;
  modalPrimaryLabel: string;
  modalSecondaryLabel?: string;
  actionType: "generate" | "improve" | "resolve" | "view" | "regenerate" | "continue_anyway" | "cancel";
  tone: "positive" | "caution" | "warning" | "neutral";
  reason: string;
  showContinueAnyway: boolean;
  showReviewMissingInputs: boolean;
  generationMode?: "draft" | "confident";
}

export function resolveRecommendationAction(state: ReadinessState): CTAAction {
  const {
    readiness_level,
    expected_confidence,
    readiness_score,
    can_generate,
    blocking_inputs,
    missing_inputs,
    optional_inputs,
    latest_recommendation,
    pr_package
  } = state;

  // Helper function to check Input 5 (AC/Test Mapping) status
  const getInput5Status = () => {
    const input5 = missing_inputs.find(input => input.key === 'INPUT_5');
    return input5?.severity || 'READY';
  };

  const input5Status = getInput5Status();
  const confirmedMappingsCount = state.pr_package?.confirmed_mappings_count || 0;

  // Part 6: Check PR package readiness first (Input 1 guardrails)
  if (pr_package?.readiness_status === "BLOCKED") {
    const firstBlocker = pr_package.blockers?.[0] || "PR package incomplete";
    return {
      primaryLabel: "Sync PR Changes First",
      secondaryLabel: undefined,
      modalPrimaryLabel: "Sync PR Changes First",
      modalSecondaryLabel: undefined,
      actionType: "resolve",
      tone: "warning",
      reason: `PR package blocked: ${firstBlocker}. Changed files/head SHA are required for confident targeted regression.`,
      showContinueAnyway: false,
      showReviewMissingInputs: false
    };
  }

  // Part 6: Check for stale PR package
  if (pr_package?.snapshot_is_stale || state.recommendation_audit?.status === "OUTDATED") {
    return {
      primaryLabel: "Regenerate Recommendation",
      secondaryLabel: "View Previous Recommendation",
      modalPrimaryLabel: "Regenerate Recommendation",
      modalSecondaryLabel: "View Previous Recommendation",
      actionType: "regenerate",
      tone: "caution",
      reason: "PR has changed since this recommendation was generated",
      showContinueAnyway: false,
      showReviewMissingInputs: false
    };
  }

  // Input 5 validation: If Input 5 is missing, no confident generation, draft only at most
  if (input5Status === 'MISSING') {
    return {
      primaryLabel: "Generate Draft Recommendation",
      secondaryLabel: "Add AC → Test Mappings",
      modalPrimaryLabel: "Generate Draft Recommendation",
      modalSecondaryLabel: "Add AC → Test Mappings",
      actionType: "generate",
      tone: "caution",
      reason: "AC → Test mappings are missing. Only draft recommendation available.",
      showContinueAnyway: false,
      showReviewMissingInputs: false,
      generationMode: "draft"
    };
  }

  // Input 5 validation: If Input 5 is partial/review-needed, draft only with warning
  if (input5Status === 'PARTIAL' || input5Status === 'REVIEW_NEEDED') {
    return {
      primaryLabel: "Generate Draft After Review",
      secondaryLabel: "Review Mappings First",
      modalPrimaryLabel: "Generate Draft After Review",
      modalSecondaryLabel: "Review Mappings First",
      actionType: "generate",
      tone: "caution",
      reason: "AC → Test mappings are not confirmed. Draft recommendation only.",
      showContinueAnyway: false,
      showReviewMissingInputs: false,
      generationMode: "draft"
    };
  }

  // Input 5 validation: If confirmed AC → Test mappings = 0, no confident generation
  if (confirmedMappingsCount === 0 && input5Status !== 'MISSING') {
    return {
      primaryLabel: "Generate Draft Recommendation",
      secondaryLabel: "Confirm AC → Test Mappings",
      modalPrimaryLabel: "Generate Draft Recommendation",
      modalSecondaryLabel: "Confirm AC → Test Mappings",
      actionType: "generate",
      tone: "caution",
      reason: "No confirmed AC → Test mappings. Only draft recommendation available.",
      showContinueAnyway: false,
      showReviewMissingInputs: false,
      generationMode: "draft"
    };
  }

  // Part 6: PR package ready but other inputs missing (PARTIAL state)
  if (pr_package?.readiness_status === "PARTIAL" && can_generate) {
    return {
      primaryLabel: "Generate Draft Recommendation",
      secondaryLabel: "Improve Inputs",
      modalPrimaryLabel: "Generate Draft Recommendation",
      modalSecondaryLabel: "Improve Inputs",
      actionType: "generate",
      tone: "caution",
      reason: "Draft available. Some evidence inputs are incomplete.",
      showContinueAnyway: false,
      showReviewMissingInputs: false,
      generationMode: "draft"
    };
  }

  // Check for backend inconsistency
  if (expected_confidence === "HIGH" && !can_generate) {
    console.warn("Backend inconsistency: expected_confidence=HIGH but can_generate=false. Prioritizing can_generate=false.");
  }

  // Check for LEGACY_NO_SNAPSHOT (Recommendation exists but lacks snapshot)
  if (state.recommendation_audit?.status === "LEGACY_NO_SNAPSHOT") {
    return {
      primaryLabel: "View Recommendation",
      secondaryLabel: "Regenerate",
      modalPrimaryLabel: "View Recommendation",
      modalSecondaryLabel: "Regenerate",
      actionType: "view",
      tone: "caution",
      reason: "This recommendation was generated without an auditable PR snapshot",
      showContinueAnyway: false,
      showReviewMissingInputs: false
    };
  }

  // State 6: Recommendation exists and not stale
  if (latest_recommendation?.exists && !latest_recommendation.input_stale) {
    return {
      primaryLabel: "View Recommendation",
      secondaryLabel: "Regenerate",
      modalPrimaryLabel: "View Recommendation",
      modalSecondaryLabel: "Regenerate",
      actionType: "view",
      tone: "positive",
      reason: "Recommendation already generated and up to date",
      showContinueAnyway: false,
      showReviewMissingInputs: false
    };
  }

  // State 7: Recommendation exists but stale
  if (latest_recommendation?.exists && latest_recommendation.input_stale) {
    return {
      primaryLabel: "Regenerate Recommendation",
      secondaryLabel: "View Previous Recommendation",
      modalPrimaryLabel: "Regenerate Recommendation",
      modalSecondaryLabel: "View Previous Recommendation",
      actionType: "regenerate",
      tone: "caution",
      reason: "Recommendation is stale due to new inputs",
      showContinueAnyway: false,
      showReviewMissingInputs: false
    };
  }

  // State 1: BLOCKED
  if (!can_generate || blocking_inputs.length > 0) {
    const firstBlocker = blocking_inputs[0]?.label || "blocking inputs";
    return {
      primaryLabel: "Resolve Blocking Inputs",
      secondaryLabel: undefined,
      modalPrimaryLabel: "Resolve Blocking Inputs",
      modalSecondaryLabel: undefined,
      actionType: "resolve",
      tone: "warning",
      reason: `Cannot generate: ${firstBlocker}`,
      showContinueAnyway: false,
      showReviewMissingInputs: false
    };
  }

  // Part 6: Generate Confident Regression Plan (PR package ready + HIGH confidence)
  if (pr_package?.readiness_status === "READY" && pr_package?.can_generate_confident_regression_plan && expected_confidence === "HIGH" && readiness_score >= 75) {
    return {
      primaryLabel: "Generate Confident Regression Plan",
      secondaryLabel: "Review Optional Gaps",
      modalPrimaryLabel: "Generate Confident Regression Plan",
      modalSecondaryLabel: "Review Optional Gaps",
      actionType: "generate",
      tone: "positive",
      reason: "Ready to generate confident regression plan with complete PR package",
      showContinueAnyway: false,
      showReviewMissingInputs: false
    };
  }

  // Check if quality gate profile is missing (Input 10)
  const qualityGateMissing = missing_inputs.some(input => input.key === 'INPUT_10');

  // State 5: CONFIDENT_READY / HIGH_CONFIDENCE_READY
  if (can_generate && expected_confidence === "HIGH" && readiness_score >= 75) {
    if (qualityGateMissing) {
      // Can generate basic recommendation but not high-confidence release-safe
      return {
        primaryLabel: "Generate Recommendation",
        secondaryLabel: "Review Optional Gaps",
        modalPrimaryLabel: "Generate Recommendation",
        modalSecondaryLabel: "Review Optional Gaps",
        actionType: "generate",
        tone: "positive",
        reason: "Ready to generate recommendation (quality gate profile missing for high-confidence release-safe)",
        showContinueAnyway: false,
        showReviewMissingInputs: false,
        generationMode: "confident"
      };
    } else {
      // Full confident recommendation
      return {
        primaryLabel: "Generate Confident Recommendation",
        secondaryLabel: "Review Optional Gaps",
        modalPrimaryLabel: "Generate Confident Recommendation",
        modalSecondaryLabel: "Review Optional Gaps",
        actionType: "generate",
        tone: "positive",
        reason: "Ready to generate confident recommendation with complete evidence",
        showContinueAnyway: false,
        showReviewMissingInputs: false,
        generationMode: "confident"
      };
    }
  }

  // State 4: MINIMUM_READY - Basic recommendation available
  if (can_generate && expected_confidence === "MEDIUM") {
    return {
      primaryLabel: "Generate Recommendation",
      secondaryLabel: "Improve Accuracy",
      modalPrimaryLabel: "Generate Recommendation",
      modalSecondaryLabel: "Improve Accuracy",
      actionType: "generate",
      tone: "caution",
      reason: "Ready to generate basic recommendation",
      showContinueAnyway: false,
      showReviewMissingInputs: false,
      generationMode: "confident"
    };
  }

  // State 2: LOW confidence but can generate
  if (can_generate && expected_confidence === "LOW") {
    return {
      primaryLabel: "Improve Inputs",
      secondaryLabel: "Continue Anyway",
      modalPrimaryLabel: "Improve Inputs",
      modalSecondaryLabel: "Continue Anyway",
      actionType: "improve",
      tone: "caution",
      reason: "Low confidence - improving inputs recommended",
      showContinueAnyway: true,
      showReviewMissingInputs: false
    };
  }

  // Default fallback
  return {
    primaryLabel: "Review Readiness",
    secondaryLabel: undefined,
    modalPrimaryLabel: "Review Readiness",
    modalSecondaryLabel: undefined,
    actionType: "resolve",
    tone: "neutral",
    reason: "Review readiness state",
    showContinueAnyway: false,
    showReviewMissingInputs: true
  };
}

export function getReadinessSummary(state: ReadinessState): {
  title: string;
  summary: string;
  secondaryLine?: string;
} {
  const action = resolveRecommendationAction(state);

  if (action.actionType === "generate" && action.tone === "positive") {
    return {
      title: "Ready to Generate Recommendation",
      summary: "Veriscope can generate this recommendation with high confidence based on current evidence.",
      secondaryLine: "Remaining gaps are optional and can improve future learning."
    };
  }

  if (action.actionType === "generate" && action.tone === "caution") {
    return {
      title: "Generate with Limited Confidence",
      summary: "Veriscope can generate this recommendation, but confidence is limited due to missing signals.",
      secondaryLine: "Improving inputs will increase recommendation accuracy."
    };
  }

  if (action.actionType === "resolve") {
    return {
      title: "Resolve Blocking Inputs",
      summary: "Required signals are missing for recommendation generation.",
      secondaryLine: action.reason
    };
  }

  if (action.actionType === "improve") {
    return {
      title: "Improve Inputs",
      summary: "Current evidence is insufficient for a confident recommendation.",
      secondaryLine: "Adding missing signals will significantly improve accuracy."
    };
  }

  return {
    title: "Review Readiness",
    summary: "Review the current readiness state.",
    secondaryLine: action.reason
  };
}

export function getOptionalGapLabel(key: string, label: string): string {
  const labelMap: Record<string, string> = {
    linked_work_item: "Linked work item not connected",
    historical_outcomes: "No historical outcomes yet",
    fragility_memory: "No fragility history yet",
    managed_manual_tests: "No manual tests yet",
    current_pr_coverage: "No PR coverage yet"
  };

  return labelMap[key] || `${label} not available`;
}
