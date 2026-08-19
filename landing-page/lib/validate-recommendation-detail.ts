// ── Recommendation Detail View Consistency Checker ───────────────────────────
// Validates that what is rendered on the recommendation page is internally
// consistent with the readiness snapshot and recommendation run data.
// Errors = contradictions that should never be visible to users.
// Warnings = quality issues that should be investigated.

export interface RenderedSectionsData {
  showAttachTestRun?: boolean;
  hasPRTestResults?: boolean;
  renderedTestIds?: string[];
  renderedScenarioIds?: string[];
  createRegressionScopeButtonCount?: number;
  visibleLabels?: string[];
  visiblePercentages?: (number | null | undefined)[];
  showNeedsMoreEvidence?: boolean;
  displayedConfidenceLabel?: string | null;
  displayedScore?: number | null;
  completenessScoreValue?: number | null;
  renderedACCount?: number;
  renderedCoverageItemCount?: number;
  showStaleBanner?: boolean;
  snapshotACCount?: number;
  snapshotCoverageItemCount?: number;
  evidenceSufficient?: boolean;
  showNeedsReview?: boolean;
  criticalGapCount?: number;
  unnamedTestCount?: number;
  requirementNotAvailableCount?: number;
  executiveGapCount?: number;
  sectionGapCount?: number;
  testCardMissingWhySelectedCount?: number;
  missingTestWithoutActionCount?: number;
  optionalGapAsBlockerCount?: number;
}

export interface ReadinessSnapshotInput {
  expected_confidence?: string | null;
  readiness_score?: number | null;
  can_generate?: boolean | null;
  readiness_snapshot_available?: boolean;
  blocking_inputs?: any[] | null;
  missing_inputs?: any[] | null;
}

export interface ConsistencyIssue {
  code: string;
  severity: "error" | "warning";
  message: string;
}

export interface ConsistencyCheckResult {
  errors: ConsistencyIssue[];
  warnings: ConsistencyIssue[];
  hasErrors: boolean;
  hasWarnings: boolean;
}

const SNAKE_CASE_RE = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+){2,}\b/;

export function validateRecommendationDetailView({
  recommendationRun,
  readinessSnapshot,
  renderedSectionsData: r,
}: {
  recommendationRun: any;
  readinessSnapshot: ReadinessSnapshotInput | null | undefined;
  renderedSectionsData: RenderedSectionsData;
}): ConsistencyCheckResult {
  const errors: ConsistencyIssue[] = [];
  const warnings: ConsistencyIssue[] = [];

  const snap = readinessSnapshot;

  // 1. Snapshot missing but confidence shown as real value
  const snapshotAvailable = snap?.readiness_snapshot_available === true;
  const confidenceIsReal = r.displayedConfidenceLabel &&
    r.displayedConfidenceLabel !== "N/A" &&
    r.displayedConfidenceLabel !== "UNKNOWN" &&
    r.displayedConfidenceLabel !== "LEGACY";
  if (!snapshotAvailable && confidenceIsReal) {
    errors.push({
      code: "SNAPSHOT_MISSING_REAL_CONFIDENCE",
      severity: "error",
      message: `Confidence shown as "${r.displayedConfidenceLabel}" but no readiness snapshot is available. Display N/A or regenerate.`,
    });
  }

  // 2. HIGH confidence + Needs More Evidence
  if (snap?.expected_confidence === "HIGH" && r.showNeedsMoreEvidence) {
    errors.push({
      code: "HIGH_CONFIDENCE_NEEDS_EVIDENCE",
      severity: "error",
      message: "HIGH confidence recommendation must not show 'Needs More Evidence'.",
    });
  }

  // 3. LOW evidence + 100% completeness score
  if (
    snap?.expected_confidence === "LOW" &&
    r.completenessScoreValue != null &&
    r.completenessScoreValue >= 1.0
  ) {
    errors.push({
      code: "LOW_CONFIDENCE_FULL_COMPLETENESS",
      severity: "error",
      message: "LOW confidence with 100% completeness score is contradictory. Score or confidence label is incorrect.",
    });
  }

  // 4. Score label shown but snapshot has no score
  if (
    (snap?.readiness_score == null || snap.readiness_score === 0) &&
    r.displayedScore != null &&
    r.displayedScore > 0
  ) {
    errors.push({
      code: "SCORE_MISSING_LABEL_SHOWN",
      severity: "error",
      message: "A non-zero readiness score is displayed but the snapshot contains no score.",
    });
  }

  // 5. AC in snapshot but none rendered on screen
  if (r.snapshotACCount && r.snapshotACCount > 0 && r.renderedACCount === 0) {
    errors.push({
      code: "AC_IN_SNAPSHOT_MISSING_ON_SCREEN",
      severity: "error",
      message: `Snapshot includes ${r.snapshotACCount} acceptance criteria item(s) but none are shown on screen.`,
    });
  }

  // 6. Coverage items in snapshot but none rendered
  if (
    r.snapshotCoverageItemCount &&
    r.snapshotCoverageItemCount > 0 &&
    r.renderedCoverageItemCount === 0
  ) {
    errors.push({
      code: "COVERAGE_IN_SNAPSHOT_MISSING_ON_SCREEN",
      severity: "error",
      message: `Snapshot includes ${r.snapshotCoverageItemCount} coverage item(s) but none are shown on screen.`,
    });
  }

  // 7. Current PR test results exist but "Attach" CTA is still shown
  if (r.hasPRTestResults && r.showAttachTestRun) {
    errors.push({
      code: "TEST_RESULTS_EXIST_ATTACH_SHOWN",
      severity: "error",
      message: "'Attach Current PR Test Results' is shown but PR test results already exist.",
    });
  }

  // 8. Duplicate "Create Regression Scope" buttons
  if (r.createRegressionScopeButtonCount && r.createRegressionScopeButtonCount > 1) {
    warnings.push({
      code: "DUPLICATE_CREATE_REGRESSION_SCOPE",
      severity: "warning",
      message: `"Create Regression Scope" CTA appears ${r.createRegressionScopeButtonCount} times. Should appear once.`,
    });
  }

  // 9a. Duplicate test IDs
  if (r.renderedTestIds && r.renderedTestIds.length > 0) {
    const counts: Record<string, number> = {};
    for (const id of r.renderedTestIds) {
      counts[id] = (counts[id] || 0) + 1;
    }
    const dups = Object.entries(counts)
      .filter(([, n]) => n > 1)
      .map(([id]) => id);
    if (dups.length > 0) {
      warnings.push({
        code: "DUPLICATE_TEST_IDS",
        severity: "warning",
        message: `${dups.length} test ID(s) rendered more than once: ${dups.slice(0, 3).join(", ")}${dups.length > 3 ? ` (+${dups.length - 3} more)` : ""}.`,
      });
    }
  }

  // 9b. Duplicate scenario IDs
  if (r.renderedScenarioIds && r.renderedScenarioIds.length > 0) {
    const counts: Record<string, number> = {};
    for (const id of r.renderedScenarioIds) {
      if (!id) continue; // skip missing/undefined/empty identities
      counts[id] = (counts[id] || 0) + 1;
    }
    const dups = Object.entries(counts)
      .filter(([, n]) => n > 1)
      .map(([id]) => id);
    if (dups.length > 0) {
      warnings.push({
        code: "DUPLICATE_SCENARIO_IDS",
        severity: "warning",
        message: `${dups.length} scenario ID(s) rendered more than once: ${dups.slice(0, 3).join(", ")}${dups.length > 3 ? ` (+${dups.length - 3} more)` : ""}.`,
      });
    }
  }

  // 10. Raw snake_case labels visible in UI
  if (r.visibleLabels && r.visibleLabels.length > 0) {
    const snakeCaseLabels = r.visibleLabels.filter((l) => SNAKE_CASE_RE.test(l));
    if (snakeCaseLabels.length > 0) {
      warnings.push({
        code: "RAW_SNAKE_CASE_LABEL",
        severity: "warning",
        message: `Raw snake_case label(s) visible: ${snakeCaseLabels.slice(0, 3).join(", ")}`,
      });
    }
  }

  // 11. Infinity / NaN / null percentage values
  if (r.visiblePercentages && r.visiblePercentages.length > 0) {
    const bad = r.visiblePercentages.filter(
      (p) => p == null || !Number.isFinite(p) || Number.isNaN(p)
    );
    if (bad.length > 0) {
      errors.push({
        code: "INVALID_PERCENTAGE_VALUE",
        severity: "error",
        message: `${bad.length} percentage value(s) are Infinity, NaN, or null.`,
      });
    }
  }

  // 12. PR readiness confidence differs from snapshot without stale banner
  const prConfidence = recommendationRun?.pr_readiness?.expected_confidence;
  const snapConf = snap?.expected_confidence;
  if (
    prConfidence &&
    snapConf &&
    prConfidence !== snapConf &&
    !r.showStaleBanner
  ) {
    errors.push({
      code: "SNAPSHOT_MISMATCH_NO_STALE_BANNER",
      severity: "error",
      message: `PR readiness confidence (${prConfidence}) differs from snapshot (${snapConf}) but stale banner is not shown.`,
    });
  }

  // 13. Evidence sufficient + Needs Review without critical gaps
  if (r.evidenceSufficient && r.showNeedsReview && (r.criticalGapCount || 0) === 0) {
    errors.push({
      code: "EVIDENCE_SUFFICIENT_NEEDS_REVIEW_NO_CRITICAL",
      severity: "error",
      message: "Evidence is sufficient but 'Needs Review' is shown without critical gaps. Should show Ready.",
    });
  }

  // 13b. High coverage (>=90%) marked as insufficient
  if (r.visiblePercentages && r.visiblePercentages.length > 0) {
    const hasHighCoverage = r.visiblePercentages.some((p) => p != null && p >= 90);
    if (hasHighCoverage && !r.evidenceSufficient) {
      errors.push({
        code: "EVIDENCE_INSUFFICIENT_HIGH_COVERAGE",
        severity: "error",
        message: "Coverage >=90% is shown but evidence is marked as insufficient. High coverage should be considered sufficient.",
      });
    }
  }

  // 14. Unnamed Test visible
  if (r.unnamedTestCount && r.unnamedTestCount > 0) {
    errors.push({
      code: "UNNAMED_TEST_VISIBLE",
      severity: "error",
      message: `${r.unnamedTestCount} test(s) display as 'Unnamed Test'. All tests must have readable titles.`,
    });
  }

  // 15. Requirement: N/A visible
  if (r.requirementNotAvailableCount && r.requirementNotAvailableCount > 0) {
    errors.push({
      code: "REQUIREMENT_NOT_AVAILABLE_VISIBLE",
      severity: "error",
      message: `${r.requirementNotAvailableCount} test(s) show 'Requirement: N/A' when AC mapping exists.`,
    });
  }

  // 16. Executive gap count != gap section count
  if (
    r.executiveGapCount != null &&
    r.sectionGapCount != null &&
    r.executiveGapCount !== r.sectionGapCount
  ) {
    errors.push({
      code: "GAP_COUNT_MISMATCH",
      severity: "error",
      message: `Executive gap count (${r.executiveGapCount}) does not match section gap count (${r.sectionGapCount}).`,
    });
  }

  // 17. Test card missing why-selected
  if (r.testCardMissingWhySelectedCount && r.testCardMissingWhySelectedCount > 0) {
    errors.push({
      code: "TEST_CARD_MISSING_WHY_SELECTED",
      severity: "error",
      message: `${r.testCardMissingWhySelectedCount} test card(s) missing 'why selected' explanation.`,
    });
  }

  // 18. Missing test has no suggested action
  if (r.missingTestWithoutActionCount && r.missingTestWithoutActionCount > 0) {
    errors.push({
      code: "MISSING_TEST_WITHOUT_ACTION",
      severity: "error",
      message: `${r.missingTestWithoutActionCount} missing test(s) have no suggested action.`,
    });
  }

  // 19. Optional gap shown as blocker
  if (r.optionalGapAsBlockerCount && r.optionalGapAsBlockerCount > 0) {
    errors.push({
      code: "OPTIONAL_GAP_AS_BLOCKER",
      severity: "error",
      message: `${r.optionalGapAsBlockerCount} optional gap(s) displayed as blocker. Optional gaps must be labeled 'Optional improvement'.`,
    });
  }

  return {
    errors,
    warnings,
    hasErrors: errors.length > 0,
    hasWarnings: warnings.length > 0,
  };
}
