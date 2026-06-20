/**
 * test-recommendation-health-canonical-source.test.tsx
 *
 * Unit tests for recommendation-health-state.ts helper.
 * Tests the canonical health resolution logic directly without DOM rendering.
 */

import {
  mapBackendHealthToDisplay,
  applyGuardrails,
  extractCanonicalHealth,
  resolveCanonicalHealth,
  type BackendEvidenceHealth,
  type HealthGuardrails,
  type CanonicalHealthResult,
  type RecommendationHealthDisplayState,
} from "@/lib/recommendation-health-state";

describe("recommendation-health-state.ts", () => {
  describe("mapBackendHealthToDisplay", () => {
    it("maps READY to Ready", () => {
      const result = mapBackendHealthToDisplay("READY");
      expect(result.state).toBe("Ready");
      expect(result.cta).toBe("Create Regression Scope");
      expect(result.ctaAction).toBe("create");
    });

    it("maps VALIDATION_PASSED_COVERAGE_INCOMPLETE to Coverage Incomplete", () => {
      const result = mapBackendHealthToDisplay("VALIDATION_PASSED_COVERAGE_INCOMPLETE");
      expect(result.state).toBe("Coverage Incomplete");
      expect(result.cta).toBe("Review Missing & Partial Coverage");
      expect(result.ctaAction).toBe("review");
    });

    it("maps VALIDATION_PASSED_TRACEABILITY_INCOMPLETE to Traceability Incomplete", () => {
      const result = mapBackendHealthToDisplay("VALIDATION_PASSED_TRACEABILITY_INCOMPLETE");
      expect(result.state).toBe("Traceability Incomplete");
      expect(result.cta).toBe("Review Traceability");
      expect(result.ctaAction).toBe("review");
    });

    it("maps NEEDS_TRACEABILITY_REVIEW to Needs Review", () => {
      const result = mapBackendHealthToDisplay("NEEDS_TRACEABILITY_REVIEW");
      expect(result.state).toBe("Needs Review");
      expect(result.cta).toBe("Review Traceability");
      expect(result.ctaAction).toBe("review");
    });

    it("maps BLOCKED_BY_FAILED_TESTS to Failed", () => {
      const result = mapBackendHealthToDisplay("BLOCKED_BY_FAILED_TESTS");
      expect(result.state).toBe("Failed");
      expect(result.cta).toBe("Review Failed Tests");
      expect(result.ctaAction).toBe("review_critical");
    });

    it("maps BLOCKED_BY_SKIPPED_REQUIRED_TESTS to Failed", () => {
      const result = mapBackendHealthToDisplay("BLOCKED_BY_SKIPPED_REQUIRED_TESTS");
      expect(result.state).toBe("Failed");
      expect(result.cta).toBe("Review Skipped Tests");
      expect(result.ctaAction).toBe("review_critical");
    });

    it("maps VALIDATION_FAILED to Failed", () => {
      const result = mapBackendHealthToDisplay("VALIDATION_FAILED");
      expect(result.state).toBe("Failed");
      expect(result.cta).toBe("Regenerate Recommendation");
      expect(result.ctaAction).toBe("regenerate");
    });

    it("maps STALE_INPUTS to Stale Inputs", () => {
      const result = mapBackendHealthToDisplay("STALE_INPUTS");
      expect(result.state).toBe("Stale Inputs");
      expect(result.cta).toBe("Regenerate Recommendation");
      expect(result.ctaAction).toBe("regenerate");
    });

    it("maps unknown health to Needs Review", () => {
      const result = mapBackendHealthToDisplay("UNKNOWN_HEALTH" as BackendEvidenceHealth);
      expect(result.state).toBe("Needs Review");
      expect(result.cta).toBe("Review Evidence Gaps");
      expect(result.ctaAction).toBe("review");
    });
  });

  describe("applyGuardrails", () => {
    it("does not block Ready when no guardrails are active", () => {
      const resolved: Pick<CanonicalHealthResult, "state" | "reason" | "cta" | "ctaAction"> = {
        state: "Ready" as RecommendationHealthDisplayState,
        reason: "All required evidence is covered.",
        cta: "Create Regression Scope",
        ctaAction: "create" as const,
      };
      const guardrails: HealthGuardrails = {};
      const result = applyGuardrails(resolved, guardrails);
      expect(result.state).toBe("Ready");
    });

    it("blocks Ready when requiredBeforeReleaseCount > 0", () => {
      const resolved: Pick<CanonicalHealthResult, "state" | "reason" | "cta" | "ctaAction"> = {
        state: "Ready" as RecommendationHealthDisplayState,
        reason: "All required evidence is covered.",
        cta: "Create Regression Scope",
        ctaAction: "create" as const,
      };
      const guardrails: HealthGuardrails = {
        requiredBeforeReleaseCount: 3,
      };
      const result = applyGuardrails(resolved, guardrails);
      expect(result.state).toBe("Coverage Incomplete");
      expect(result.reason).toContain("3 required items");
    });

    it("blocks Ready when releaseDecisionStatus is PENDING_REVIEW", () => {
      const resolved: Pick<CanonicalHealthResult, "state" | "reason" | "cta" | "ctaAction"> = {
        state: "Ready" as RecommendationHealthDisplayState,
        reason: "All required evidence is covered.",
        cta: "Create Regression Scope",
        ctaAction: "create" as const,
      };
      const guardrails: HealthGuardrails = {
        releaseDecisionStatus: "PENDING_REVIEW",
      };
      const result = applyGuardrails(resolved, guardrails);
      expect(result.state).toBe("Needs Review");
      expect(result.reason).toContain("Release decision is pending");
    });

    it("blocks Ready when hasCriticalGaps is true", () => {
      const resolved: Pick<CanonicalHealthResult, "state" | "reason" | "cta" | "ctaAction"> = {
        state: "Ready" as RecommendationHealthDisplayState,
        reason: "All required evidence is covered.",
        cta: "Create Regression Scope",
        ctaAction: "create" as const,
      };
      const guardrails: HealthGuardrails = {
        hasCriticalGaps: true,
      };
      const result = applyGuardrails(resolved, guardrails);
      expect(result.state).toBe("Needs Review");
      expect(result.reason).toContain("Critical evidence gaps");
    });

    it("blocks Ready when regressionScopeFailed is true", () => {
      const resolved: Pick<CanonicalHealthResult, "state" | "reason" | "cta" | "ctaAction"> = {
        state: "Ready" as RecommendationHealthDisplayState,
        reason: "All required evidence is covered.",
        cta: "Create Regression Scope",
        ctaAction: "create" as const,
      };
      const guardrails: HealthGuardrails = {
        regressionScopeFailed: true,
      };
      const result = applyGuardrails(resolved, guardrails);
      expect(result.state).toBe("Needs Review");
      expect(result.reason).toContain("Unable to optimize regression scope");
    });

    it("does not apply guardrails to non-Ready states", () => {
      const resolved: Pick<CanonicalHealthResult, "state" | "reason" | "cta" | "ctaAction"> = {
        state: "Coverage Incomplete" as RecommendationHealthDisplayState,
        reason: "Coverage gaps remain.",
        cta: "Review Coverage",
        ctaAction: "review" as const,
      };
      const guardrails: HealthGuardrails = {
        requiredBeforeReleaseCount: 5,
        hasCriticalGaps: true,
      };
      const result = applyGuardrails(resolved, guardrails);
      expect(result.state).toBe("Coverage Incomplete");
    });
  });

  describe("extractCanonicalHealth", () => {
    it("extracts health from decisionSummary.health", () => {
      const regressionEvidence = {
        decisionSummary: {
          health: "VALIDATION_PASSED_COVERAGE_INCOMPLETE",
        },
      };
      const result = extractCanonicalHealth(regressionEvidence);
      expect(result).toBe("VALIDATION_PASSED_COVERAGE_INCOMPLETE");
    });

    it("extracts health from top-level health as fallback", () => {
      const regressionEvidence = {
        health: "READY",
      };
      const result = extractCanonicalHealth(regressionEvidence);
      expect(result).toBe("READY");
    });

    it("returns null when no health is available", () => {
      const regressionEvidence = {};
      const result = extractCanonicalHealth(regressionEvidence);
      expect(result).toBeNull();
    });

    it("returns null when regressionEvidence is null", () => {
      const result = extractCanonicalHealth(null);
      expect(result).toBeNull();
    });
  });

  describe("resolveCanonicalHealth", () => {
    it("returns Stale Inputs when isStale is true", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: { decisionSummary: { health: "READY" } },
        isStale: true,
      });
      expect(result.state).toBe("Stale Inputs");
      expect(result.isCanonical).toBe(false);
    });

    it("uses canonical health when available", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: {
          decisionSummary: { health: "VALIDATION_PASSED_COVERAGE_INCOMPLETE" },
        },
      });
      expect(result.state).toBe("Coverage Incomplete");
      expect(result.isCanonical).toBe(true);
    });

    it("applies guardrails to canonical health", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: {
          decisionSummary: { health: "READY" },
        },
        guardrails: {
          requiredBeforeReleaseCount: 2,
        },
      });
      expect(result.state).toBe("Coverage Incomplete");
      expect(result.isCanonical).toBe(true);
    });

    it("falls back to stale confidence when canonical health is unavailable", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: null,
        staleFallbackConfidence: "HIGH",
      });
      expect(result.state).toBe("Ready");
      expect(result.isCanonical).toBe(false);
    });

    it("falls back to Limited Evidence when stale confidence is not HIGH", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: null,
        staleFallbackConfidence: "MEDIUM",
      });
      expect(result.state).toBe("Limited Evidence");
      expect(result.isCanonical).toBe(false);
    });

    it("HIGH stale confidence does NOT override non-ready canonical health", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: {
          decisionSummary: { health: "VALIDATION_PASSED_COVERAGE_INCOMPLETE" },
        },
        staleFallbackConfidence: "HIGH",
      });
      expect(result.state).toBe("Coverage Incomplete");
      expect(result.isCanonical).toBe(true);
    });

    it("requiredBeforeReleaseCount > 0 prevents Ready", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: {
          decisionSummary: { health: "READY" },
        },
        guardrails: {
          requiredBeforeReleaseCount: 1,
        },
      });
      expect(result.state).toBe("Coverage Incomplete");
    });

    it("releaseDecisionStatus = PENDING prevents Ready", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: {
          decisionSummary: { health: "READY" },
        },
        guardrails: {
          releaseDecisionStatus: "PENDING_REVIEW",
        },
      });
      expect(result.state).toBe("Needs Review");
    });

    it("critical gap prevents Ready", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: {
          decisionSummary: { health: "READY" },
        },
        evidenceGaps: [{ severity: "HIGH" }],
      });
      expect(result.state).toBe("Needs Review");
    });

    it("regressionScope UNABLE_TO_OPTIMIZE prevents Ready", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: {
          decisionSummary: { health: "READY" },
          scopeRecommendation: { status: "UNABLE_TO_OPTIMIZE" },
        },
        guardrails: {
          regressionScopeFailed: true,
        },
      });
      expect(result.state).toBe("Needs Review");
    });

    it("subtitle is correct for non-ready state", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: {
          decisionSummary: { health: "VALIDATION_PASSED_COVERAGE_INCOMPLETE" },
        },
      });
      expect(result.reason).toContain("Coverage gaps remain");
    });

    it("grammar: Unable to optimize (not optimized)", () => {
      const result = resolveCanonicalHealth({
        regressionEvidence: {
          decisionSummary: { health: "READY" },
        },
        guardrails: {
          regressionScopeFailed: true,
        },
      });
      expect(result.reason).toContain("Unable to optimize");
      expect(result.reason).not.toContain("optimized");
    });
  });
});
