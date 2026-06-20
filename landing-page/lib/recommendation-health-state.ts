/**
 * recommendation-health-state.ts
 *
 * Canonical evidence health resolution for the Recommendation Health banner.
 *
 * Single source of truth for mapping backend `decisionSummary.health` → display state.
 * Used by both page.tsx (banner) and recommendation-display-state.ts (display resolver).
 *
 * INVARIANT: `regressionEvidence.decisionSummary.health` is always authoritative.
 * `run.readiness_snapshot.expected_confidence` is stale and must NEVER override a
 * non-READY canonical health value.
 */

// ── Types ─────────────────────────────────────────────────────────────────────

/** Raw health enum values returned by GET /{id}/regression-evidence → decisionSummary.health */
export type BackendEvidenceHealth =
  | "READY"
  | "VALIDATION_PASSED_COVERAGE_INCOMPLETE"
  | "VALIDATION_PASSED_TRACEABILITY_INCOMPLETE"
  | "NEEDS_TRACEABILITY_REVIEW"
  | "BLOCKED_BY_FAILED_TESTS"
  | "BLOCKED_BY_SKIPPED_REQUIRED_TESTS"
  | "BLOCKED_BY_FAILED_OR_SKIPPED_TESTS"
  | "VALIDATION_FAILED"
  | "STALE_INPUTS"
  | "INTERNAL_EVIDENCE_MODEL_INCONSISTENT"
  | "INSUFFICIENT_INPUT"
  | "BLOCKED"
  | "READY_WITH_GAPS"
  | "READY_WITH_TRACEABILITY_ISSUES"
  | string; // forward-compat for future values

/** Display states the banner can render */
export type RecommendationHealthDisplayState =
  | "Ready"
  | "Coverage Incomplete"
  | "Traceability Incomplete"
  | "Needs Review"
  | "Failed"
  | "Stale Inputs"
  | "Limited Evidence";

/** Guardrail inputs — any truthy field blocks "Ready" */
export interface HealthGuardrails {
  /** Number of required items before release (from regressionScope) */
  requiredBeforeReleaseCount?: number;
  /** Release decision status string (e.g. "PENDING_REVIEW") */
  releaseDecisionStatus?: string | null;
  /** Whether any HIGH/CRITICAL evidence gaps are present */
  hasCriticalGaps?: boolean;
  /** Whether regression scope computation failed or was unable to optimize */
  regressionScopeFailed?: boolean;
  /** Whether any blocking consistency warnings exist */
  hasBlockingConsistencyWarnings?: boolean;
}

export interface CanonicalHealthResult {
  /** The resolved display state */
  state: RecommendationHealthDisplayState;
  /** Human-readable subtitle for the banner */
  reason: string;
  /** CTA button label */
  cta: string;
  /** Action the CTA should trigger */
  ctaAction: "create" | "review" | "review_critical" | "regenerate" | "retry";
  /** Whether the canonical source was used (vs stale fallback) */
  isCanonical: boolean;
}

// ── Core mapping ──────────────────────────────────────────────────────────────

/**
 * Map a raw BackendEvidenceHealth value to a user-facing display state.
 * Does NOT apply guardrails — call `applyGuardrails()` afterwards if needed.
 */
export function mapBackendHealthToDisplay(
  health: BackendEvidenceHealth
): Pick<CanonicalHealthResult, "state" | "reason" | "cta" | "ctaAction"> {
  switch (health) {
    case "READY":
      return {
        state: "Ready",
        reason: "All required evidence is covered. No remaining gaps.",
        cta: "Create Regression Scope",
        ctaAction: "create",
      };

    case "VALIDATION_PASSED_COVERAGE_INCOMPLETE":
      return {
        state: "Coverage Incomplete",
        reason:
          "Coverage gaps remain before this recommendation can be considered ready.",
        cta: "Review Missing & Partial Coverage",
        ctaAction: "review",
      };

    case "VALIDATION_PASSED_TRACEABILITY_INCOMPLETE":
      return {
        state: "Traceability Incomplete",
        reason:
          "Evidence is incomplete; traceability review required before release.",
        cta: "Review Traceability",
        ctaAction: "review",
      };

    case "NEEDS_TRACEABILITY_REVIEW":
      return {
        state: "Needs Review",
        reason:
          "Requirement mapping is incomplete. Review unmapped requirements before proceeding.",
        cta: "Review Traceability",
        ctaAction: "review",
      };

    case "BLOCKED_BY_FAILED_TESTS":
      return {
        state: "Failed",
        reason:
          "Current PR execution has failing tests. Fix them before proceeding.",
        cta: "Review Failed Tests",
        ctaAction: "review_critical",
      };

    case "BLOCKED_BY_SKIPPED_REQUIRED_TESTS":
    case "BLOCKED_BY_FAILED_OR_SKIPPED_TESTS":
      return {
        state: "Failed",
        reason: "Required tests were skipped. Run them before proceeding.",
        cta: "Review Skipped Tests",
        ctaAction: "review_critical",
      };

    case "VALIDATION_FAILED":
      return {
        state: "Failed",
        reason: "Evidence validation failed. Regenerate to resolve.",
        cta: "Regenerate Recommendation",
        ctaAction: "regenerate",
      };

    case "STALE_INPUTS":
      return {
        state: "Stale Inputs",
        reason:
          "Inputs have changed since generation. Regenerate to include latest evidence.",
        cta: "Regenerate Recommendation",
        ctaAction: "regenerate",
      };

    case "INTERNAL_EVIDENCE_MODEL_INCONSISTENT":
      return {
        state: "Failed",
        reason:
          "Internal evidence model is inconsistent. Regenerate to resolve.",
        cta: "Regenerate Recommendation",
        ctaAction: "regenerate",
      };

    case "INSUFFICIENT_INPUT":
      return {
        state: "Needs Review",
        reason:
          "Insufficient input data. Add acceptance criteria and rerun.",
        cta: "Review Evidence Gaps",
        ctaAction: "review",
      };

    // Legacy states
    case "BLOCKED":
      return {
        state: "Failed",
        reason:
          "Evidence review is blocked. Fix failing or skipped tests before proceeding.",
        cta: "Review Blocked Tests",
        ctaAction: "review_critical",
      };

    case "READY_WITH_GAPS":
    case "READY_WITH_TRACEABILITY_ISSUES":
      return {
        state: "Coverage Incomplete",
        reason: "Validation passed but some requirements have missing automation.",
        cta: "Review Coverage",
        ctaAction: "review",
      };

    default:
      // Unknown or future health values default to Needs Review, not Ready
      return {
        state: "Needs Review",
        reason: "Evidence is incomplete; review required before release.",
        cta: "Review Evidence Gaps",
        ctaAction: "review",
      };
  }
}

// ── Guardrail enforcement ─────────────────────────────────────────────────────

/**
 * Apply guardrail checks to a resolved health state.
 * If the state is "Ready" but any blocking condition is true, downgrade to
 * "Needs Review" or "Coverage Incomplete".
 */
export function applyGuardrails(
  resolved: Pick<CanonicalHealthResult, "state" | "reason" | "cta" | "ctaAction">,
  guardrails: HealthGuardrails
): Pick<CanonicalHealthResult, "state" | "reason" | "cta" | "ctaAction"> {
  if (resolved.state !== "Ready") {
    // Already non-ready — guardrails are moot
    return resolved;
  }

  const {
    requiredBeforeReleaseCount = 0,
    releaseDecisionStatus,
    hasCriticalGaps = false,
    regressionScopeFailed = false,
    hasBlockingConsistencyWarnings = false,
  } = guardrails;

  // Block Ready if required items remain
  if (requiredBeforeReleaseCount > 0) {
    return {
      state: "Coverage Incomplete",
      reason: `${requiredBeforeReleaseCount} required item${requiredBeforeReleaseCount !== 1 ? "s" : ""} must be resolved before release.`,
      cta: "Review Required Items",
      ctaAction: "review",
    };
  }

  // Block Ready if release decision is still pending
  const pendingStatuses = ["PENDING_REVIEW", "PENDING", "PARTIALLY_VERIFIED"];
  if (releaseDecisionStatus && pendingStatuses.includes(releaseDecisionStatus)) {
    return {
      state: "Needs Review",
      reason: "Release decision is pending. Complete the review before marking ready.",
      cta: "Review Release Decision",
      ctaAction: "review",
    };
  }

  // Block Ready if critical evidence gaps exist
  if (hasCriticalGaps) {
    return {
      state: "Needs Review",
      reason: "Critical evidence gaps detected. Review before proceeding.",
      cta: "Review Critical Gaps",
      ctaAction: "review_critical",
    };
  }

  // Block Ready if regression scope failed or could not be optimized
  if (regressionScopeFailed) {
    return {
      state: "Needs Review",
      reason:
        "Unable to optimize regression scope. Review evidence before creating scope.",
      cta: "Review Evidence",
      ctaAction: "review",
    };
  }

  // Block Ready if blocking consistency warnings exist
  if (hasBlockingConsistencyWarnings) {
    return {
      state: "Needs Review",
      reason: "Consistency warnings require review before release.",
      cta: "Review Warnings",
      ctaAction: "review",
    };
  }

  return resolved;
}

// ── Primary entry point ───────────────────────────────────────────────────────

/**
 * Extract canonical health from the regression evidence API response.
 * Returns the raw backend health string, or null if not available.
 */
export function extractCanonicalHealth(
  regressionEvidence: any
): BackendEvidenceHealth | null {
  if (!regressionEvidence) return null;
  // The endpoint returns { decisionSummary: { health: "..." }, ... }
  const h =
    regressionEvidence?.decisionSummary?.health ??
    regressionEvidence?.health ??
    null;
  return typeof h === "string" && h.length > 0 ? h : null;
}

/**
 * Resolve the canonical recommendation health state.
 *
 * Priority:
 * 1. `regressionEvidence.decisionSummary.health` (live, authoritative)
 * 2. Guardrail checks (block Ready even if live health says Ready)
 * 3. Fallback to stale confidence-based state (lowest priority)
 *
 * The stale confidence path is only used when regression evidence is unavailable
 * (e.g., loading error, network failure).
 */
export function resolveCanonicalHealth(
  options: {
    /** Full regressionEvidence response from GET /{id}/regression-evidence */
    regressionEvidence: any;
    /** True if run.input_stale is set */
    isStale?: boolean;
    /** Stale-based fallback confidence (run.readiness_snapshot.expected_confidence) */
    staleFallbackConfidence?: string | null;
    /** Evidence gaps for critical gap check */
    evidenceGaps?: any[];
    /** Guardrail data */
    guardrails?: HealthGuardrails;
  }
): CanonicalHealthResult {
  const {
    regressionEvidence,
    isStale = false,
    staleFallbackConfidence,
    evidenceGaps = [],
    guardrails = {},
  } = options;

  // Stale inputs always take precedence (not even live evidence can override this)
  if (isStale) {
    return {
      state: "Stale Inputs",
      reason:
        "Inputs changed after generation. Regenerate to include latest evidence.",
      cta: "Regenerate Recommendation",
      ctaAction: "regenerate",
      isCanonical: false,
    };
  }

  // Attempt canonical resolution from live evidence
  const canonicalHealth = extractCanonicalHealth(regressionEvidence);
  if (canonicalHealth) {
    const hasCriticalGaps =
      guardrails.hasCriticalGaps ??
      evidenceGaps.some(
        (g: any) => g.severity === "HIGH" || g.severity === "CRITICAL"
      );

    const mapped = mapBackendHealthToDisplay(canonicalHealth);
    const withGuardrails = applyGuardrails(mapped, {
      ...guardrails,
      hasCriticalGaps,
    });

    return { ...withGuardrails, isCanonical: true };
  }

  // Fallback: stale confidence-based heuristic (lowest priority)
  const hasCriticalGaps = evidenceGaps.some(
    (g: any) => g.severity === "HIGH" || g.severity === "CRITICAL"
  );

  if (hasCriticalGaps) {
    return {
      state: "Needs Review",
      reason: "Critical gaps require review before finalizing scope.",
      cta: "Review Critical Gaps",
      ctaAction: "review_critical",
      isCanonical: false,
    };
  }

  if (staleFallbackConfidence === "HIGH") {
    return {
      state: "Ready",
      reason: "Generated from high-confidence evidence.",
      cta: "Create Regression Scope",
      ctaAction: "create",
      isCanonical: false,
    };
  }

  return {
    state: "Limited Evidence",
    reason: "Generated with missing recommended evidence.",
    cta: "Review Gaps",
    ctaAction: "review",
    isCanonical: false,
  };
}
