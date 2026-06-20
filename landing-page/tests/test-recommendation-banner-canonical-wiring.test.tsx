/**
 * test-recommendation-banner-canonical-wiring.test.tsx
 *
 * Wiring test for recommendation banner health resolution.
 * Tests that the banner uses canonical evidence (regressionEvidence.decisionSummary.health)
 * and NOT stale confidence (run.readiness_snapshot.expected_confidence).
 *
 * This test verifies the real call path through getRecommendationHealth.
 */

import { getRecommendationHealth } from "@/lib/recommendation-page-health";
import type { CanonicalHealthResult } from "@/lib/recommendation-health-state";

describe("Recommendation Banner Canonical Health Wiring", () => {
  it("uses canonical health from regressionEvidence, not stale confidence", () => {
    // Scenario: Stale snapshot says HIGH confidence, but canonical health says Coverage Incomplete
    const run = {
      status: "COMPLETED",
      input_stale: false,
      readiness_snapshot: {
        expected_confidence: "HIGH", // Stale - should be ignored
      },
    };

    const evidenceGaps: any[] = [];

    const regressionEvidence = {
      decisionSummary: {
        health: "VALIDATION_PASSED_COVERAGE_INCOMPLETE", // Canonical - should be used
      },
      scopeRecommendation: {
        requiredItems: [],
        status: "COMPLETED",
      },
      __releaseDecision: null,
    };

    const result = getRecommendationHealth(run, evidenceGaps, regressionEvidence);

    // Banner must show Coverage Incomplete (from canonical health)
    expect(result.state).toBe("Coverage Incomplete");
    
    // Banner must NOT show Ready (despite stale HIGH confidence)
    expect(result.state).not.toBe("Ready");
    
    // Must indicate canonical source was used
    expect(result.isCanonical).toBe(true);
  });

  it("shows Needs Review when canonical health is NEEDS_TRACEABILITY_REVIEW", () => {
    const run = {
      status: "COMPLETED",
      input_stale: false,
      readiness_snapshot: {
        expected_confidence: "HIGH", // Stale
      },
    };

    const evidenceGaps: any[] = [];

    const regressionEvidence = {
      decisionSummary: {
        health: "NEEDS_TRACEABILITY_REVIEW", // Canonical
      },
      scopeRecommendation: {
        requiredItems: [],
        status: "COMPLETED",
      },
      __releaseDecision: null,
    };

    const result = getRecommendationHealth(run, evidenceGaps, regressionEvidence);

    expect(result.state).toBe("Needs Review");
    expect(result.state).not.toBe("Ready");
    expect(result.isCanonical).toBe(true);
  });

  it("shows Failed when canonical health is BLOCKED_BY_FAILED_TESTS", () => {
    const run = {
      status: "COMPLETED",
      input_stale: false,
      readiness_snapshot: {
        expected_confidence: "HIGH", // Stale
      },
    };

    const evidenceGaps: any[] = [];

    const regressionEvidence = {
      decisionSummary: {
        health: "BLOCKED_BY_FAILED_TESTS", // Canonical
      },
      scopeRecommendation: {
        requiredItems: [],
        status: "COMPLETED",
      },
      __releaseDecision: null,
    };

    const result = getRecommendationHealth(run, evidenceGaps, regressionEvidence);

    expect(result.state).toBe("Failed");
    expect(result.state).not.toBe("Ready");
    expect(result.isCanonical).toBe(true);
  });

  it("falls back to stale confidence when canonical health is unavailable", () => {
    const run = {
      status: "COMPLETED",
      input_stale: false,
      readiness_snapshot: {
        expected_confidence: "HIGH",
      },
    };

    const evidenceGaps: any[] = [];

    const regressionEvidence = null; // No canonical health available

    const result = getRecommendationHealth(run, evidenceGaps, regressionEvidence);

    expect(result.state).toBe("Ready");
    expect(result.isCanonical).toBe(false);
  });

  it("applies guardrail: requiredBeforeReleaseCount blocks Ready", () => {
    const run = {
      status: "COMPLETED",
      input_stale: false,
      readiness_snapshot: {
        expected_confidence: "HIGH",
      },
    };

    const evidenceGaps: any[] = [];

    const regressionEvidence = {
      decisionSummary: {
        health: "READY", // Canonical says Ready
      },
      scopeRecommendation: {
        requiredItems: [{ id: "req1" }, { id: "req2" }], // But required items exist
        status: "COMPLETED",
      },
      __releaseDecision: null,
    };

    const result = getRecommendationHealth(run, evidenceGaps, regressionEvidence);

    // Guardrail should block Ready
    expect(result.state).toBe("Coverage Incomplete");
    expect(result.state).not.toBe("Ready");
  });

  it("applies guardrail: PENDING release decision blocks Ready", () => {
    const run = {
      status: "COMPLETED",
      input_stale: false,
      readiness_snapshot: {
        expected_confidence: "HIGH",
      },
    };

    const evidenceGaps: any[] = [];

    const regressionEvidence = {
      decisionSummary: {
        health: "READY", // Canonical says Ready
      },
      scopeRecommendation: {
        requiredItems: [],
        status: "COMPLETED",
      },
      __releaseDecision: {
        decisionStatus: "PENDING_REVIEW", // But release decision is pending
      },
    };

    const result = getRecommendationHealth(run, evidenceGaps, regressionEvidence);

    // Guardrail should block Ready
    expect(result.state).toBe("Needs Review");
    expect(result.state).not.toBe("Ready");
  });

  it("applies guardrail: critical gaps block Ready", () => {
    const run = {
      status: "COMPLETED",
      input_stale: false,
      readiness_snapshot: {
        expected_confidence: "HIGH",
      },
    };

    const evidenceGaps = [
      { severity: "HIGH", description: "Critical gap" },
    ];

    const regressionEvidence = {
      decisionSummary: {
        health: "READY", // Canonical says Ready
      },
      scopeRecommendation: {
        requiredItems: [],
        status: "COMPLETED",
      },
      __releaseDecision: null,
    };

    const result = getRecommendationHealth(run, evidenceGaps, regressionEvidence);

    // Guardrail should block Ready
    expect(result.state).toBe("Needs Review");
    expect(result.state).not.toBe("Ready");
  });

  it("applies guardrail: UNABLE_TO_OPTIMIZE regression scope blocks Ready", () => {
    const run = {
      status: "COMPLETED",
      input_stale: false,
      readiness_snapshot: {
        expected_confidence: "HIGH",
      },
    };

    const evidenceGaps: any[] = [];

    const regressionEvidence = {
      decisionSummary: {
        health: "READY", // Canonical says Ready
      },
      scopeRecommendation: {
        requiredItems: [],
        status: "UNABLE_TO_OPTIMIZE", // But scope failed
      },
      __releaseDecision: null,
    };

    const result = getRecommendationHealth(run, evidenceGaps, regressionEvidence);

    // Guardrail should block Ready
    expect(result.state).toBe("Needs Review");
    expect(result.state).not.toBe("Ready");
  });

  it("grammar: Unable to optimize (not optimized)", () => {
    const run = {
      status: "COMPLETED",
      input_stale: false,
      readiness_snapshot: {
        expected_confidence: "HIGH",
      },
    };

    const evidenceGaps: any[] = [];

    const regressionEvidence = {
      decisionSummary: {
        health: "READY",
      },
      scopeRecommendation: {
        requiredItems: [],
        status: "UNABLE_TO_OPTIMIZE",
      },
      __releaseDecision: null,
    };

    const result = getRecommendationHealth(run, evidenceGaps, regressionEvidence);

    // Check grammar in reason message
    expect(result.reason).toContain("Unable to optimize");
    expect(result.reason).not.toContain("optimized");
  });
});
