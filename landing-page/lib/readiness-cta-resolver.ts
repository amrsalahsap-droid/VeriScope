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
    latest_recommendation
  } = state;

  // Check for backend inconsistency
  if (expected_confidence === "HIGH" && !can_generate) {
    console.warn("Backend inconsistency: expected_confidence=HIGH but can_generate=false. Prioritizing can_generate=false.");
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

  // State 4: HIGH confidence
  if (can_generate && expected_confidence === "HIGH" && readiness_score >= 75) {
    return {
      primaryLabel: "Generate Recommendation",
      secondaryLabel: "Review Optional Gaps",
      modalPrimaryLabel: "Generate Recommendation",
      modalSecondaryLabel: "Review Optional Gaps",
      actionType: "generate",
      tone: "positive",
      reason: "Ready to generate with high confidence",
      showContinueAnyway: false,
      showReviewMissingInputs: false
    };
  }

  // State 3: MEDIUM confidence
  if (can_generate && expected_confidence === "MEDIUM") {
    return {
      primaryLabel: "Generate with Limited Confidence",
      secondaryLabel: "Improve Accuracy",
      modalPrimaryLabel: "Generate with Limited Confidence",
      modalSecondaryLabel: "Improve Accuracy",
      actionType: "generate",
      tone: "caution",
      reason: "Can generate with medium confidence",
      showContinueAnyway: false,
      showReviewMissingInputs: false
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
