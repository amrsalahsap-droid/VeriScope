/**
 * recommendation-page-health.ts
 *
 * Health resolution function for the recommendation page banner.
 * Extracted from page.tsx for testability.
 */

import { resolveCanonicalHealth, type CanonicalHealthResult } from "./recommendation-health-state";

/**
 * Get recommendation health state for the banner.
 * 
 * Uses canonical live evidence health (decisionSummary.health) as the authoritative source.
 * The stale readiness_snapshot.expected_confidence is only used as a last-resort fallback
 * when regression evidence data is unavailable (network error, loading state).
 */
export function getRecommendationHealth(
  run: any,
  evidenceGaps: any[],
  regressionEvidence: any
): CanonicalHealthResult {
  // Hard failure states that pre-empt all evidence checks
  if (run.status === "FAILED" || run.status === "ERROR") {
    return {
      state: "Failed",
      reason: "Recommendation generation did not complete.",
      cta: "Retry Generation",
      ctaAction: "retry",
      isCanonical: false,
    };
  }

  // Derive guardrail values from available data
  const releaseDecision = (regressionEvidence as any)?.__releaseDecision;
  const requiredBeforeReleaseCount: number =
    regressionEvidence?.scopeRecommendation?.requiredItems?.length ||
    regressionEvidence?.decisionSummary?.missingAutomatedCoverage ||
    0;

  const scopeStatus: string =
    regressionEvidence?.scopeRecommendation?.status || "";
  const regressionScopeFailed =
    scopeStatus === "FAILED" || scopeStatus === "UNABLE_TO_OPTIMIZE";

  return resolveCanonicalHealth({
    regressionEvidence,
    isStale: !!run.input_stale,
    staleFallbackConfidence: run.readiness_snapshot?.expected_confidence || null,
    evidenceGaps,
    guardrails: {
      requiredBeforeReleaseCount,
      releaseDecisionStatus: releaseDecision?.decisionStatus || null,
      hasCriticalGaps: evidenceGaps.some(
        (g: any) => g.severity === "HIGH" || g.severity === "CRITICAL"
      ),
      regressionScopeFailed,
    },
  });
}
