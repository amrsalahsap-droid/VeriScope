/**
 * Traceability Rows Builder
 *
 * Builds normalized per-AC traceability rows from the server-side evidence graph
 * (regressionEvidence.buckets), replacing the legacy client-side mapACTraceability
 * which recalculated AC status from stale recommendation snapshot data.
 *
 * Source of truth: GET /api/recommendations/{id}/regression-evidence → buckets
 * Each bucket contains serialized parent requirements with:
 *   - requirementId, readableId, title, classification
 *   - manualValidation (status, mappedManualTestsCount, etc.)
 *   - manualTraceabilitySignals
 *
 * The evidence graph classifies each parent requirement into one of:
 *   - VERIFIED_BY_CURRENT_PR_EXECUTION → TRUSTED / PASSED / COVERED
 *   - PARTIALLY_COVERED → PARTIAL / PASSED / PARTIAL
 *   - MISSING_AUTOMATED_COVERAGE → NOT_MAPPED / NOT_RUN / MISSING
 *   - NOT_MAPPED_TRACEABILITY_RISK → NOT_MAPPED / NOT_RUN / NOT_MAPPED
 *   - FAILED_IN_CURRENT_PR_EXECUTION → TRUSTED / FAILED / COVERED
 *   - SKIPPED_IN_CURRENT_PR_EXECUTION → TRUSTED / SKIPPED / COVERED
 *   - EXISTING_TEST_NOT_RUN_IN_CURRENT_PR → TRUSTED / NOT_RUN / COVERED
 */

export type MappingStatus = "TRUSTED" | "PARTIAL" | "NOT_MAPPED";
export type ExecutionStatus = "PASSED" | "FAILED" | "SKIPPED" | "NOT_RUN";
export type CoverageStatus = "COVERED" | "PARTIAL" | "MISSING" | "NOT_MAPPED";
export type RecommendationStatus = "NO_RERUN_NEEDED" | "REVIEW_RECOMMENDED" | "ADD_TESTS" | "RERUN_RECOMMENDED";

export interface TraceabilityRow {
  ac_ref: string;
  title: string;
  mapping_status: MappingStatus;
  execution_status: ExecutionStatus;
  coverage_status: CoverageStatus;
  recommendation_status: RecommendationStatus;
  source: "evidence_graph";
  requirement_id: string;
  manual_validation?: {
    status: string;
    mapped_manual_tests_count: number;
    latest_outcome: string | null;
    latest_executed_at: string | null;
    latest_executed_by_name: string | null;
    evidence_urls: string[];
    manual_tests: any[];
  };
}

interface EvidenceBucketItem {
  requirementId: string;
  readableId: string;
  title: string;
  classification: string;
  riskLevel?: string;
  manualValidation?: {
    status: string;
    supportStatus?: string;
    mappedManualTestsCount: number;
    executedManualTestsCount?: number;
    passedManualTestsCount?: number;
    failedManualTestsCount?: number;
    latestOutcome?: string | null;
    latestExecutedAt?: string | null;
    latestExecutedByName?: string | null;
    evidenceUrls?: string[];
    manualTests?: any[];
  };
  manualTraceabilitySignals?: {
    mappedManualTestsCount: number;
    latestManualExecutionOutcome?: string | null;
    latestManualExecutionAt?: string | null;
    latestManualTestTitle?: string | null;
  };
}

interface RegressionEvidenceBuckets {
  coveredByPassedPrTests?: EvidenceBucketItem[];
  partiallySupported?: EvidenceBucketItem[];
  missingAutomatedCoverage?: EvidenceBucketItem[];
  traceabilityReviewNeeded?: EvidenceBucketItem[];
}

interface RegressionEvidence {
  buckets?: RegressionEvidenceBuckets;
  scopeRecommendation?: {
    excludedAlreadyVerifiedItems?: Array<{
      requirementId: string;
      readableId: string;
      title: string;
    }>;
    excludedAlreadyVerifiedRequirements?: Array<{
      requirementId: string;
      readableId: string;
      title: string;
    }>;
  };
}

const CLASSIFICATION_MAP: Record<
  string,
  {
    mapping: MappingStatus;
    execution: ExecutionStatus;
    coverage: CoverageStatus;
    recommendation: RecommendationStatus;
  }
> = {
  VERIFIED_BY_CURRENT_PR_EXECUTION: {
    mapping: "TRUSTED",
    execution: "PASSED",
    coverage: "COVERED",
    recommendation: "NO_RERUN_NEEDED",
  },
  PARTIALLY_COVERED: {
    mapping: "PARTIAL",
    execution: "PASSED",
    coverage: "PARTIAL",
    recommendation: "REVIEW_RECOMMENDED",
  },
  MISSING_AUTOMATED_COVERAGE: {
    mapping: "NOT_MAPPED",
    execution: "NOT_RUN",
    coverage: "MISSING",
    recommendation: "ADD_TESTS",
  },
  NOT_MAPPED_TRACEABILITY_RISK: {
    mapping: "NOT_MAPPED",
    execution: "NOT_RUN",
    coverage: "NOT_MAPPED",
    recommendation: "REVIEW_RECOMMENDED",
  },
  FAILED_IN_CURRENT_PR_EXECUTION: {
    mapping: "TRUSTED",
    execution: "FAILED",
    coverage: "COVERED",
    recommendation: "RERUN_RECOMMENDED",
  },
  SKIPPED_IN_CURRENT_PR_EXECUTION: {
    mapping: "TRUSTED",
    execution: "SKIPPED",
    coverage: "COVERED",
    recommendation: "RERUN_RECOMMENDED",
  },
  EXISTING_TEST_NOT_RUN_IN_CURRENT_PR: {
    mapping: "TRUSTED",
    execution: "NOT_RUN",
    coverage: "COVERED",
    recommendation: "RERUN_RECOMMENDED",
  },
};

function normalizeAcRef(ref: string): string {
  return String(ref || "").trim().toUpperCase();
}

function buildRowFromBucket(
  item: EvidenceBucketItem,
  bucketKey: string,
): TraceabilityRow {
  const classification =
    item.classification ||
    (bucketKey === "coveredByPassedPrTests"
      ? "VERIFIED_BY_CURRENT_PR_EXECUTION"
      : bucketKey === "partiallySupported"
        ? "PARTIALLY_COVERED"
        : bucketKey === "missingAutomatedCoverage"
          ? "MISSING_AUTOMATED_COVERAGE"
          : "NOT_MAPPED_TRACEABILITY_RISK");

  const mapped = CLASSIFICATION_MAP[classification] ?? {
    mapping: "NOT_MAPPED" as MappingStatus,
    execution: "NOT_RUN" as ExecutionStatus,
    coverage: "NOT_MAPPED" as CoverageStatus,
    recommendation: "REVIEW_RECOMMENDED" as RecommendationStatus,
  };

  const mv = item.manualValidation;
  const signals = item.manualTraceabilitySignals;

  return {
    ac_ref: item.readableId || item.requirementId,
    title: item.title || "",
    mapping_status: mapped.mapping,
    execution_status: mapped.execution,
    coverage_status: mapped.coverage,
    recommendation_status: mapped.recommendation,
    source: "evidence_graph",
    requirement_id: item.requirementId,
    manual_validation: mv
      ? {
          status: mv.status || "NOT_MAPPED",
          mapped_manual_tests_count: mv.mappedManualTestsCount || 0,
          latest_outcome: mv.latestOutcome ?? null,
          latest_executed_at: mv.latestExecutedAt ?? null,
          latest_executed_by_name: mv.latestExecutedByName ?? null,
          evidence_urls: mv.evidenceUrls || [],
          manual_tests: mv.manualTests || [],
        }
      : signals
        ? {
            status: signals.latestManualExecutionOutcome || "NOT_EXECUTED",
            mapped_manual_tests_count: signals.mappedManualTestsCount || 0,
            latest_outcome: signals.latestManualExecutionOutcome ?? null,
            latest_executed_at: signals.latestManualExecutionAt ?? null,
            latest_executed_by_name: null,
            evidence_urls: [],
            manual_tests: [],
          }
        : undefined,
  };
}

/**
 * Build normalized, deduplicated traceability rows from the evidence graph.
 *
 * @param regressionEvidence - The response from GET /regression-evidence
 * @returns Deduplicated array of TraceabilityRow, sorted by coverage status (issues first)
 */
export function buildTraceabilityRows(
  regressionEvidence: RegressionEvidence | null | undefined,
): TraceabilityRow[] {
  if (!regressionEvidence?.buckets) {
    return [];
  }

  const buckets = regressionEvidence.buckets;
  const rows: TraceabilityRow[] = [];
  const seen = new Set<string>();

  // Process buckets in priority order: issues first, then verified
  const bucketOrder: Array<[keyof RegressionEvidenceBuckets, string]> = [
    ["missingAutomatedCoverage", "missingAutomatedCoverage"],
    ["traceabilityReviewNeeded", "traceabilityReviewNeeded"],
    ["partiallySupported", "partiallySupported"],
    ["coveredByPassedPrTests", "coveredByPassedPrTests"],
  ];

  for (const [bucketKey, bucketName] of bucketOrder) {
    const items = buckets[bucketKey];
    if (!items || !Array.isArray(items)) continue;

    for (const item of items) {
      const normalizedRef = normalizeAcRef(item.readableId || item.requirementId);
      if (seen.has(normalizedRef)) continue;
      seen.add(normalizedRef);

      rows.push(buildRowFromBucket(item, bucketName));
    }
  }

  // Also include excluded already-verified items from scopeRecommendation
  // (these may not appear in buckets but should be shown as trusted/verified)
  const excludedVerified =
    regressionEvidence.scopeRecommendation?.excludedAlreadyVerifiedItems ||
    regressionEvidence.scopeRecommendation?.excludedAlreadyVerifiedRequirements ||
    [];

  for (const item of excludedVerified) {
    const normalizedRef = normalizeAcRef(item.readableId || item.requirementId);
    if (seen.has(normalizedRef)) continue;
    seen.add(normalizedRef);

    rows.push({
      ac_ref: item.readableId || item.requirementId,
      title: item.title || "",
      mapping_status: "TRUSTED",
      execution_status: "PASSED",
      coverage_status: "COVERED",
      recommendation_status: "NO_RERUN_NEEDED",
      source: "evidence_graph",
      requirement_id: item.requirementId,
    });
  }

  // Sort: issues first, then verified
  const statusOrder: Record<CoverageStatus, number> = {
    MISSING: 0,
    NOT_MAPPED: 1,
    PARTIAL: 2,
    COVERED: 3,
  };

  return rows.sort((a, b) => {
    const diff =
      (statusOrder[a.coverage_status] ?? 99) -
      (statusOrder[b.coverage_status] ?? 99);
    return diff;
  });
}

/**
 * Determine if the traceability section is "healthy" (no issues).
 * Used to decide whether to collapse the section by default.
 */
export function isTraceabilityHealthy(rows: TraceabilityRow[]): boolean {
  return rows.every(
    (r) =>
      r.coverage_status === "COVERED" &&
      r.mapping_status === "TRUSTED" &&
      r.recommendation_status === "NO_RERUN_NEEDED",
  );
}
