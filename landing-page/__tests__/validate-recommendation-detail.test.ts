import {
  validateRecommendationDetailView,
  type ReadinessSnapshotInput,
  type RenderedSectionsData,
} from "../lib/validate-recommendation-detail";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeSnap(overrides: Partial<ReadinessSnapshotInput> = {}): ReadinessSnapshotInput {
  return {
    readiness_snapshot_available: true,
    expected_confidence: "HIGH",
    readiness_score: 0.87,
    can_generate: true,
    blocking_inputs: [],
    missing_inputs: [],
    ...overrides,
  };
}

function makeRendered(overrides: Partial<RenderedSectionsData> = {}): RenderedSectionsData {
  return {
    hasPRTestResults: false,
    showAttachTestRun: false,
    renderedTestIds: ["test-a", "test-b"],
    renderedScenarioIds: ["scen-1"],
    createRegressionScopeButtonCount: 1,
    showNeedsMoreEvidence: false,
    displayedConfidenceLabel: "HIGH",
    displayedScore: 0.87,
    completenessScoreValue: 0.8,
    renderedACCount: 2,
    renderedCoverageItemCount: 3,
    showStaleBanner: false,
    snapshotACCount: 2,
    snapshotCoverageItemCount: 3,
    visibleLabels: [],
    visiblePercentages: [87, 80],
    evidenceSufficient: true,
    showNeedsReview: false,
    criticalGapCount: 0,
    unnamedTestCount: 0,
    requirementNotAvailableCount: 0,
    executiveGapCount: 5,
    sectionGapCount: 5,
    testCardMissingWhySelectedCount: 0,
    missingTestWithoutActionCount: 0,
    optionalGapAsBlockerCount: 0,
    ...overrides,
  };
}

function run(snap: ReadinessSnapshotInput | null, rendered: RenderedSectionsData) {
  return validateRecommendationDetailView({
    recommendationRun: {},
    readinessSnapshot: snap,
    renderedSectionsData: rendered,
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("validateRecommendationDetailView", () => {
  describe("Happy path — high-confidence snapshot renders correctly", () => {
    it("returns no issues for a clean high-confidence recommendation", () => {
      const result = run(makeSnap(), makeRendered());
      expect(result.hasErrors).toBe(false);
      expect(result.hasWarnings).toBe(false);
    });

    it("shows Ready/Evidence-sufficient: no NEEDS_MORE_EVIDENCE for HIGH confidence", () => {
      const result = run(
        makeSnap({ expected_confidence: "HIGH" }),
        makeRendered({ showNeedsMoreEvidence: false })
      );
      expect(result.errors.some((e) => e.code === "HIGH_CONFIDENCE_NEEDS_EVIDENCE")).toBe(false);
    });
  });

  describe("Legacy run — snapshot absent", () => {
    it("flags SNAPSHOT_MISSING_REAL_CONFIDENCE when no snapshot but confidence displayed", () => {
      const result = run(
        null,
        makeRendered({ displayedConfidenceLabel: "HIGH" })
      );
      expect(result.errors.some((e) => e.code === "SNAPSHOT_MISSING_REAL_CONFIDENCE")).toBe(true);
    });

    it("does NOT flag when snapshot absent and confidence is N/A", () => {
      const result = run(
        null,
        makeRendered({ displayedConfidenceLabel: "N/A" })
      );
      expect(result.errors.some((e) => e.code === "SNAPSHOT_MISSING_REAL_CONFIDENCE")).toBe(false);
    });

    it("does NOT flag when snapshot absent and no confidence displayed", () => {
      const result = run(null, makeRendered({ displayedConfidenceLabel: null }));
      expect(result.errors.some((e) => e.code === "SNAPSHOT_MISSING_REAL_CONFIDENCE")).toBe(false);
    });
  });

  describe("Missing snapshot shows legacy banner only", () => {
    it("passes cleanly when snapshot unavailable and confidence is not shown", () => {
      const result = run(
        makeSnap({ readiness_snapshot_available: false }),
        makeRendered({ displayedConfidenceLabel: "N/A" })
      );
      expect(result.hasErrors).toBe(false);
    });
  });

  describe("HIGH confidence + Needs More Evidence", () => {
    it("errors when HIGH confidence AND showNeedsMoreEvidence is true", () => {
      const result = run(
        makeSnap({ expected_confidence: "HIGH" }),
        makeRendered({ showNeedsMoreEvidence: true })
      );
      expect(result.errors.some((e) => e.code === "HIGH_CONFIDENCE_NEEDS_EVIDENCE")).toBe(true);
    });
  });

  describe("LOW confidence + 100% completeness", () => {
    it("errors on LOW confidence with completeness 1.0", () => {
      const result = run(
        makeSnap({ expected_confidence: "LOW" }),
        makeRendered({ completenessScoreValue: 1.0 })
      );
      expect(result.errors.some((e) => e.code === "LOW_CONFIDENCE_FULL_COMPLETENESS")).toBe(true);
    });

    it("does not error for LOW confidence with completeness < 1.0", () => {
      const result = run(
        makeSnap({ expected_confidence: "LOW" }),
        makeRendered({ completenessScoreValue: 0.75 })
      );
      expect(result.errors.some((e) => e.code === "LOW_CONFIDENCE_FULL_COMPLETENESS")).toBe(false);
    });
  });

  describe("Current PR tests available hides Attach CTA", () => {
    it("errors when hasPRTestResults is true but showAttachTestRun is also true", () => {
      const result = run(
        makeSnap(),
        makeRendered({ hasPRTestResults: true, showAttachTestRun: true })
      );
      expect(result.errors.some((e) => e.code === "TEST_RESULTS_EXIST_ATTACH_SHOWN")).toBe(true);
    });

    it("passes when test results exist and attach CTA is hidden", () => {
      const result = run(
        makeSnap(),
        makeRendered({ hasPRTestResults: true, showAttachTestRun: false })
      );
      expect(result.errors.some((e) => e.code === "TEST_RESULTS_EXIST_ATTACH_SHOWN")).toBe(false);
    });
  });

  describe("Create Regression Scope appears once", () => {
    it("warns when CTA appears more than once", () => {
      const result = run(
        makeSnap(),
        makeRendered({ createRegressionScopeButtonCount: 2 })
      );
      expect(result.warnings.some((w) => w.code === "DUPLICATE_CREATE_REGRESSION_SCOPE")).toBe(true);
    });

    it("does not warn when CTA appears exactly once", () => {
      const result = run(
        makeSnap(),
        makeRendered({ createRegressionScopeButtonCount: 1 })
      );
      expect(result.warnings.some((w) => w.code === "DUPLICATE_CREATE_REGRESSION_SCOPE")).toBe(false);
    });
  });

  describe("Duplicate tests deduplication", () => {
    it("warns when same test ID appears twice", () => {
      const result = run(
        makeSnap(),
        makeRendered({ renderedTestIds: ["test-a", "test-b", "test-a"] })
      );
      expect(result.warnings.some((w) => w.code === "DUPLICATE_TEST_IDS")).toBe(true);
    });

    it("passes when all test IDs are unique", () => {
      const result = run(
        makeSnap(),
        makeRendered({ renderedTestIds: ["test-a", "test-b", "test-c"] })
      );
      expect(result.warnings.some((w) => w.code === "DUPLICATE_TEST_IDS")).toBe(false);
    });
  });

  describe("Coverage gaps do not duplicate missing tests", () => {
    it("warns when same scenario ID appears in both gaps and suggested", () => {
      const result = run(
        makeSnap(),
        makeRendered({ renderedScenarioIds: ["scen-1", "scen-2", "scen-1"] })
      );
      expect(result.warnings.some((w) => w.code === "DUPLICATE_SCENARIO_IDS")).toBe(true);
    });
  });

  describe("No raw snake_case in normal UI", () => {
    it("warns when a visible label contains raw snake_case", () => {
      const result = run(
        makeSnap(),
        makeRendered({ visibleLabels: ["missing_automated_coverage_gap"] })
      );
      expect(result.warnings.some((w) => w.code === "RAW_SNAKE_CASE_LABEL")).toBe(true);
    });

    it("does not warn for normal readable labels", () => {
      const result = run(
        makeSnap(),
        makeRendered({ visibleLabels: ["Missing Coverage", "High Risk", "Run Tests"] })
      );
      expect(result.warnings.some((w) => w.code === "RAW_SNAKE_CASE_LABEL")).toBe(false);
    });
  });

  describe("No Infinity/NaN percentage", () => {
    it("errors when a percentage is Infinity", () => {
      const result = run(
        makeSnap(),
        makeRendered({ visiblePercentages: [87, Infinity] })
      );
      expect(result.errors.some((e) => e.code === "INVALID_PERCENTAGE_VALUE")).toBe(true);
    });

    it("errors when a percentage is NaN", () => {
      const result = run(
        makeSnap(),
        makeRendered({ visiblePercentages: [87, NaN] })
      );
      expect(result.errors.some((e) => e.code === "INVALID_PERCENTAGE_VALUE")).toBe(true);
    });

    it("errors when a percentage is null", () => {
      const result = run(
        makeSnap(),
        makeRendered({ visiblePercentages: [87, null] })
      );
      expect(result.errors.some((e) => e.code === "INVALID_PERCENTAGE_VALUE")).toBe(true);
    });

    it("passes for valid finite percentages", () => {
      const result = run(
        makeSnap(),
        makeRendered({ visiblePercentages: [87, 65, 0, 100] })
      );
      expect(result.errors.some((e) => e.code === "INVALID_PERCENTAGE_VALUE")).toBe(false);
    });
  });

  describe("Post-merge outcome hidden until relevant", () => {
    it("passes when test results do not exist and attach CTA is shown", () => {
      const result = run(
        makeSnap(),
        makeRendered({ hasPRTestResults: false, showAttachTestRun: true })
      );
      expect(result.errors.some((e) => e.code === "TEST_RESULTS_EXIST_ATTACH_SHOWN")).toBe(false);
    });
  });

  describe("Stale inputs show Regenerate (snapshot mismatch)", () => {
    it("errors when PR confidence differs from snapshot but no stale banner", () => {
      const result = validateRecommendationDetailView({
        recommendationRun: { pr_readiness: { expected_confidence: "MODERATE" } },
        readinessSnapshot: makeSnap({ expected_confidence: "HIGH" }),
        renderedSectionsData: makeRendered({ showStaleBanner: false }),
      });
      expect(result.errors.some((e) => e.code === "SNAPSHOT_MISMATCH_NO_STALE_BANNER")).toBe(true);
    });

    it("passes when PR confidence matches snapshot", () => {
      const result = validateRecommendationDetailView({
        recommendationRun: { pr_readiness: { expected_confidence: "HIGH" } },
        readinessSnapshot: makeSnap({ expected_confidence: "HIGH" }),
        renderedSectionsData: makeRendered({ showStaleBanner: false }),
      });
      expect(result.errors.some((e) => e.code === "SNAPSHOT_MISMATCH_NO_STALE_BANNER")).toBe(false);
    });
  });

  describe("Fresh recommendation does not show stale/needs-more-evidence", () => {
    it("passes for fresh HIGH confidence run with no stale indicators", () => {
      const result = run(
        makeSnap({ expected_confidence: "HIGH" }),
        makeRendered({
          showNeedsMoreEvidence: false,
          showStaleBanner: false,
          displayedConfidenceLabel: "HIGH",
        })
      );
      expect(result.hasErrors).toBe(false);
    });
  });

  describe("Evidence sufficient + Needs Review without critical gaps", () => {
    it("errors when evidence sufficient, needs review shown, but no critical gaps", () => {
      const result = run(
        makeSnap(),
        makeRendered({ evidenceSufficient: true, showNeedsReview: true, criticalGapCount: 0 })
      );
      expect(result.errors.some((e) => e.code === "EVIDENCE_SUFFICIENT_NEEDS_REVIEW_NO_CRITICAL")).toBe(true);
    });

    it("passes when evidence sufficient with critical gaps", () => {
      const result = run(
        makeSnap(),
        makeRendered({ evidenceSufficient: true, showNeedsReview: true, criticalGapCount: 2 })
      );
      expect(result.errors.some((e) => e.code === "EVIDENCE_SUFFICIENT_NEEDS_REVIEW_NO_CRITICAL")).toBe(false);
    });
  });

  describe("Unnamed Test visible", () => {
    it("errors when unnamed tests are visible", () => {
      const result = run(
        makeSnap(),
        makeRendered({ unnamedTestCount: 2 })
      );
      expect(result.errors.some((e) => e.code === "UNNAMED_TEST_VISIBLE")).toBe(true);
    });

    it("passes when no unnamed tests", () => {
      const result = run(
        makeSnap(),
        makeRendered({ unnamedTestCount: 0 })
      );
      expect(result.errors.some((e) => e.code === "UNNAMED_TEST_VISIBLE")).toBe(false);
    });
  });

  describe("Requirement: N/A visible", () => {
    it("errors when tests show Requirement: N/A", () => {
      const result = run(
        makeSnap(),
        makeRendered({ requirementNotAvailableCount: 3 })
      );
      expect(result.errors.some((e) => e.code === "REQUIREMENT_NOT_AVAILABLE_VISIBLE")).toBe(true);
    });

    it("passes when all tests have requirements mapped", () => {
      const result = run(
        makeSnap(),
        makeRendered({ requirementNotAvailableCount: 0 })
      );
      expect(result.errors.some((e) => e.code === "REQUIREMENT_NOT_AVAILABLE_VISIBLE")).toBe(false);
    });
  });

  describe("Executive gap count != gap section count", () => {
    it("errors when executive and section gap counts differ", () => {
      const result = run(
        makeSnap(),
        makeRendered({ executiveGapCount: 5, sectionGapCount: 3 })
      );
      expect(result.errors.some((e) => e.code === "GAP_COUNT_MISMATCH")).toBe(true);
    });

    it("passes when gap counts match", () => {
      const result = run(
        makeSnap(),
        makeRendered({ executiveGapCount: 5, sectionGapCount: 5 })
      );
      expect(result.errors.some((e) => e.code === "GAP_COUNT_MISMATCH")).toBe(false);
    });
  });

  describe("Test card missing why-selected", () => {
    it("errors when test cards missing why-selected", () => {
      const result = run(
        makeSnap(),
        makeRendered({ testCardMissingWhySelectedCount: 1 })
      );
      expect(result.errors.some((e) => e.code === "TEST_CARD_MISSING_WHY_SELECTED")).toBe(true);
    });

    it("passes when all test cards have why-selected", () => {
      const result = run(
        makeSnap(),
        makeRendered({ testCardMissingWhySelectedCount: 0 })
      );
      expect(result.errors.some((e) => e.code === "TEST_CARD_MISSING_WHY_SELECTED")).toBe(false);
    });
  });

  describe("Missing test has no suggested action", () => {
    it("errors when missing tests lack suggested actions", () => {
      const result = run(
        makeSnap(),
        makeRendered({ missingTestWithoutActionCount: 2 })
      );
      expect(result.errors.some((e) => e.code === "MISSING_TEST_WITHOUT_ACTION")).toBe(true);
    });

    it("passes when all missing tests have actions", () => {
      const result = run(
        makeSnap(),
        makeRendered({ missingTestWithoutActionCount: 0 })
      );
      expect(result.errors.some((e) => e.code === "MISSING_TEST_WITHOUT_ACTION")).toBe(false);
    });
  });

  describe("Optional gap shown as blocker", () => {
    it("errors when optional gaps displayed as blocker", () => {
      const result = run(
        makeSnap(),
        makeRendered({ optionalGapAsBlockerCount: 1 })
      );
      expect(result.errors.some((e) => e.code === "OPTIONAL_GAP_AS_BLOCKER")).toBe(true);
    });

    it("passes when optional gaps labeled correctly", () => {
      const result = run(
        makeSnap(),
        makeRendered({ optionalGapAsBlockerCount: 0 })
      );
      expect(result.errors.some((e) => e.code === "OPTIONAL_GAP_AS_BLOCKER")).toBe(false);
    });
  });
});
