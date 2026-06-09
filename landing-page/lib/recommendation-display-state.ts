// ── Recommendation Display State Resolver ─────────────────────────────────────────────

export interface DisplayStateInput {
  snapshotAvailable: boolean;
  confidenceAtGeneration: string | null;
  scoreAtGeneration: number | null;
  canGenerateAtGeneration: boolean | null;
  blockingInputsAtGeneration: any[] | null;
  confidenceLimitersAtGeneration: any[] | null;
  inputStale: boolean;
  generationStatus: string | null;
  completenessScore: number;
  missingEvidence: string[];
  criticalGaps: boolean;
}

export interface DisplayStateOutput {
  healthState: "Failed" | "Legacy" | "Stale Inputs" | "Ready" | "Ready With Optional Gaps" | "Limited Evidence" | "Needs Review";
  healthLabel: string;
  confidenceLabel: string;
  evidenceStatusLabel: string;
  primaryMessage: string;
  secondaryMessage: string;
  showNeedsMoreEvidence: boolean;
  showImproveAccuracy: boolean;
  showStaleBanner: boolean;
  showCompletenessScore: boolean;
  showHistoricalTestMessage: boolean;
}

export function resolveRecommendationDisplayState(input: DisplayStateInput): DisplayStateOutput {
  const {
    snapshotAvailable,
    confidenceAtGeneration,
    scoreAtGeneration,
    canGenerateAtGeneration,
    blockingInputsAtGeneration,
    confidenceLimitersAtGeneration,
    inputStale,
    generationStatus,
    completenessScore,
    missingEvidence,
    criticalGaps
  } = input;

  // Health state resolution
  let healthState: DisplayStateOutput["healthState"];
  let healthLabel: string;
  let confidenceLabel: string;
  let evidenceStatusLabel: string;
  let primaryMessage: string;
  let secondaryMessage: string;

  // 1. Failed generation
  if (generationStatus === "FAILED") {
    healthState = "Failed";
    healthLabel = "Generation Failed";
    confidenceLabel = "N/A";
    evidenceStatusLabel = "Generation Error";
    primaryMessage = "Recommendation generation failed. Please retry.";
    secondaryMessage = "Check backend logs for error details.";
  }
  // 2. Legacy recommendation (no snapshot)
  else if (!snapshotAvailable) {
    healthState = "Legacy";
    healthLabel = "Legacy Recommendation";
    confidenceLabel = "N/A";
    evidenceStatusLabel = "Snapshot Unavailable";
    primaryMessage = "Legacy recommendation: readiness snapshot was not captured.";
    secondaryMessage = "Regenerate to view accurate evidence and confidence.";
  }
  // 3. Stale inputs
  else if (inputStale) {
    healthState = "Stale Inputs";
    healthLabel = "Stale Inputs";
    confidenceLabel = confidenceAtGeneration || "N/A";
    evidenceStatusLabel = "Inputs Changed";
    primaryMessage = "Inputs have changed since generation.";
    secondaryMessage = "Regenerate to include latest evidence.";
  }
  // 4. Critical gaps exist
  else if (criticalGaps) {
    healthState = "Needs Review";
    healthLabel = "Needs Review";
    confidenceLabel = confidenceAtGeneration || "N/A";
    evidenceStatusLabel = "Critical Gaps";
    primaryMessage = "Critical evidence gaps detected.";
    secondaryMessage = "Review evidence quality before proceeding.";
  }
  // 5. High confidence with optional gaps only
  else if (confidenceAtGeneration === "HIGH" && missingEvidence.length > 0 && !criticalGaps) {
    healthState = "Ready With Optional Gaps";
    healthLabel = "Ready with optional gaps";
    confidenceLabel = "HIGH";
    evidenceStatusLabel = "Sufficient";
    primaryMessage = "Recommendation is ready. Remaining gaps are optional improvements.";
    secondaryMessage = "Generated from high-confidence evidence.";
  }
  // 6. High confidence with no critical gaps
  else if (confidenceAtGeneration === "HIGH") {
    healthState = "Ready";
    healthLabel = "Ready";
    confidenceLabel = "HIGH";
    evidenceStatusLabel = "Sufficient";
    primaryMessage = "Generated from high-confidence evidence.";
    secondaryMessage = "Recommendation is ready for execution.";
  }
  // 7. Medium or Low confidence
  else {
    healthState = "Limited Evidence";
    healthLabel = "Limited Evidence";
    confidenceLabel = confidenceAtGeneration || "LOW";
    evidenceStatusLabel = confidenceAtGeneration === "MEDIUM" ? "Partially Sufficient" : "Insufficient";
    primaryMessage = "Recommendation has limited evidence.";
    secondaryMessage = "Add more evidence to improve confidence.";
  }

  // Banner visibility rules
  const showStaleBanner = inputStale && snapshotAvailable;
  
  // Needs More Evidence: only show when confidence is LOW AND score < 75
  const showNeedsMoreEvidence = snapshotAvailable && confidenceAtGeneration === "LOW" && (scoreAtGeneration || 0) < 75;
  
  // Historical test message: show when current PR execution is missing but historical tests exist
  const hasHistoricalTests = missingEvidence.includes("current_pr_execution") === false && completenessScore > 0;
  const showHistoricalTestMessage = snapshotAvailable && missingEvidence.includes("current_pr_execution") && hasHistoricalTests;
  
  // Improve Accuracy: only show when confidence is not HIGH and snapshot is available
  const showImproveAccuracy = snapshotAvailable && confidenceAtGeneration !== "HIGH" && completenessScore < 100;
  
  // Completeness Score: show for all non-legacy runs
  const showCompletenessScore = snapshotAvailable;

  return {
    healthState,
    healthLabel,
    confidenceLabel,
    evidenceStatusLabel,
    primaryMessage,
    secondaryMessage,
    showNeedsMoreEvidence,
    showImproveAccuracy,
    showStaleBanner,
    showCompletenessScore,
    showHistoricalTestMessage
  };
}
