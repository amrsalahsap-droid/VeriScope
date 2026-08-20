/**
 * Quality Gate derivation logic.
 *
 * Replaces the stale `readiness_snapshot.gate_status` (captured at
 * recommendation generation time) with a live model derived from
 * `regressionScope.release_decision.verdict`.
 */

export type QualityGateProfileStatus = "CONFIGURED" | "MISSING";

export type EvidenceReadiness = "READY" | "READY_WITH_REVIEW" | "BLOCKED";

export type ComputedReleaseVerdict =
  | "SAFE_TO_RELEASE"
  | "REVIEW_RECOMMENDED"
  | "DO_NOT_RELEASE";

export interface QualityGateModel {
  quality_gate_profile_status: QualityGateProfileStatus;
  evidence_readiness: EvidenceReadiness;
  computed_release_verdict: ComputedReleaseVerdict | null;
}

/**
 * Map a regression scope release decision verdict to an evidence readiness
 * status.
 */
const VERDICT_TO_EVIDENCE_READINESS: Record<
  string,
  EvidenceReadiness
> = {
  SAFE_TO_RELEASE: "READY",
  REVIEW_RECOMMENDED: "READY_WITH_REVIEW",
  DO_NOT_RELEASE: "BLOCKED",
};

/**
 * Derive the live quality gate model from the regression scope release
 * decision and the availability of a quality gate profile.
 *
 * @param releaseDecisionVerdict - `regressionScope.release_decision.verdict`
 * @param hasQualityGateProfile  - Whether a CI/CD quality gate profile is
 *                                 configured for the repository.
 */
export function deriveQualityGate(
  releaseDecisionVerdict: string | null | undefined,
  hasQualityGateProfile: boolean,
): QualityGateModel {
  const quality_gate_profile_status: QualityGateProfileStatus =
    hasQualityGateProfile ? "CONFIGURED" : "MISSING";

  const computed_release_verdict: ComputedReleaseVerdict | null =
    (releaseDecisionVerdict as ComputedReleaseVerdict) ?? null;

  const evidence_readiness: EvidenceReadiness =
    computed_release_verdict
      ? VERDICT_TO_EVIDENCE_READINESS[computed_release_verdict] ??
        "READY_WITH_REVIEW"
      : "BLOCKED";

  return {
    quality_gate_profile_status,
    evidence_readiness,
    computed_release_verdict,
  };
}
