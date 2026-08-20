/**
 * PR Package Adapter
 * 
 * Normalizes PR package data from various API sources into a consistent view model.
 * Handles missing data gracefully and provides deterministic status classification.
 */

export type PRPackageStatus = "READY" | "PARTIAL" | "BLOCKED" | "OUTDATED" | "UNKNOWN";
export type SnapshotStatus = "CURRENT" | "OUTDATED" | "MISSING" | "UNKNOWN";

export interface ChangedFileViewModel {
  file_path: string;
  status: "added" | "modified" | "deleted" | "renamed";
  additions: number;
  deletions: number;
  previous_filename?: string;
  patch_summary?: string;
  patch_missing?: boolean;
  layer?: string;
  component?: string;
  flow?: string;
  type?: "source" | "test" | "config" | "migration" | "unknown";
}

export interface RecommendationAuditViewModel {
  status: "NO_RECOMMENDATION_YET" | "AUDITABLE" | "OUTDATED" | "LEGACY_NO_SNAPSHOT" | "UNKNOWN";
  headCommitShaAtGeneration?: string;
  changedFilesCountAtGeneration?: number;
  recommendedAt?: string;
  recommendationRunId?: string;
}

export interface PRPackageViewModel {
  status: PRPackageStatus;
  prNumber?: number;
  title?: string;
  sourceBranch?: string;
  targetBranch?: string;
  headSha?: string;
  headShaShort?: string;
  baseSha?: string;
  mergeSha?: string;
  changedFilesCount: number;
  changedFiles: ChangedFileViewModel[];
  changedFilePathsAvailable: boolean;
  changedFilesSource?: "github_api" | "cached_pr_package" | "repository_snapshot";
  evidenceSuccessful: boolean;
  evidenceError?: string;
  snapshotStatus: SnapshotStatus;
  blockers: string[];
  warnings: string[];
  canGenerateDraftPlan: boolean;
  canGenerateConfidentPlan: boolean;
  recommendationAudit?: RecommendationAuditViewModel;
}

interface PullRequestData {
  id: string;
  number?: number;
  title?: string;
  source_branch?: string;
  target_branch?: string;
  head_commit_sha?: string | null;
  base_commit_sha?: string | null;
  merge_commit_sha?: string | null;
  changed_files_count?: number;
  changed_files?: any[];
  state?: string;
}

interface ReadinessData {
  pr_package?: {
    head_commit_sha?: string | null;
    changed_files_count?: number;
    changed_file_paths_available?: boolean;
    changed_files?: any[];
    changed_files_source?: "github_api" | "cached_pr_package" | "repository_snapshot";
    evidence_successful?: boolean;
    evidence_error?: string | null;
    readiness?: {
      status?: string;
      blockers?: string[];
      warnings?: string[];
    };
    snapshot?: {
      is_stale?: boolean;
      head_commit_sha_at_generation?: string | null;
    };
  };
  recommendation_audit?: {
    status?: string | null;
    head_commit_sha_at_generation?: string | null;
    changed_files_count_at_generation?: number | null;
    recommended_at?: string | null;
    recommendation_run_id?: string | null;
  };
  available_signals?: Array<{ key: string; status: string }>;
  inputs?: Array<{ input_id: string; details?: Record<string, any> }>;
}

/**
 * Normalize PR package data from multiple possible sources.
 * 
 * Priority order:
 * 1. readinessData.pr_package (from readiness API)
 * 2. pullRequestData (from PR list API)
 * 3. Fallback to empty/unknown state
 */
export function normalizePRPackage(
  pullRequestData?: PullRequestData | null,
  readinessData?: ReadinessData | null
): PRPackageViewModel {
  const result: PRPackageViewModel = {
    status: "UNKNOWN",
    changedFilesCount: 0,
    changedFiles: [],
    changedFilePathsAvailable: false,
    evidenceSuccessful: false,
    snapshotStatus: "UNKNOWN",
    blockers: [],
    warnings: [],
    canGenerateDraftPlan: false,
    canGenerateConfidentPlan: false,
  };

  // Extract data from readiness API (preferred source)
  const prPackage = readinessData?.pr_package;
  const readinessStatus = prPackage?.readiness?.status;
  const readinessBlockers = prPackage?.readiness?.blockers || [];
  const readinessWarnings = prPackage?.readiness?.warnings || [];
  const snapshot = prPackage?.snapshot;
  const input1Details = readinessData?.inputs?.find((input: any) => input.input_id === "INPUT_1")?.details;

  // Extract data from PR API (fallback source)
  const prHeadSha = pullRequestData?.head_commit_sha;
  const prBaseSha = pullRequestData?.base_commit_sha;
  const prMergeSha = pullRequestData?.merge_commit_sha;
  const prChangedFilesCount = pullRequestData?.changed_files_count || 0;
  const prChangedFiles = pullRequestData?.changed_files || [];

  // Use readiness data if available, otherwise fall back to PR data
  const headSha = prPackage?.head_commit_sha || prHeadSha;
  const baseSha = prBaseSha; // Only available from PR data
  const mergeSha = prMergeSha; // Only available from PR data
  const changedFilesCount = prPackage?.changed_files_count ?? input1Details?.changed_files_count ?? prChangedFilesCount;
  const changedFiles = prPackage?.changed_files ?? input1Details?.changed_files ?? prChangedFiles;
  const changedFilePathsAvailable = prPackage?.changed_file_paths_available
    ?? input1Details?.changed_file_paths_available
    ?? normalizeChangedFiles(changedFiles).length > 0;
  const evidenceSuccessful = prPackage?.evidence_successful
    ?? input1Details?.evidence_successful
    ?? changedFilePathsAvailable;
  const changedFilesSource = prPackage?.changed_files_source ?? input1Details?.changed_files_source;
  const evidenceError = prPackage?.evidence_error ?? input1Details?.evidence_error;

  // Populate basic PR info
  result.prNumber = pullRequestData?.number;
  result.title = pullRequestData?.title;
  result.sourceBranch = pullRequestData?.source_branch;
  result.targetBranch = pullRequestData?.target_branch;
  result.headSha = headSha || undefined;
  result.headShaShort = headSha ? headSha.substring(0, 7) : undefined;
  result.baseSha = baseSha || undefined;
  result.mergeSha = mergeSha || undefined;
  result.changedFilesCount = changedFilesCount;
  result.changedFiles = normalizeChangedFiles(changedFiles);
  result.changedFilePathsAvailable = changedFilePathsAvailable;
  result.evidenceSuccessful = evidenceSuccessful;
  result.changedFilesSource = changedFilesSource;
  result.evidenceError = evidenceError || undefined;

  // Determine snapshot status
  if (snapshot?.is_stale === true) {
    result.snapshotStatus = "OUTDATED";
  } else if (snapshot?.head_commit_sha_at_generation) {
    result.snapshotStatus = "CURRENT";
  } else {
    result.snapshotStatus = "MISSING";
  }

  // Determine blockers
  const blockers = new Set<string>();
  for (const b of readinessBlockers) {
    if (b !== "SNAPSHOT_MISSING") {
      blockers.add(b);
    }
  }
  
  // Auto-detect blockers from available data
  if (!headSha) {
    blockers.add("HEAD_SHA_MISSING");
  }
  if (changedFilesCount === 0) {
    blockers.add("CHANGED_FILES_MISSING");
  }
  if (changedFilesCount > 0 && (!changedFilePathsAvailable || !evidenceSuccessful)) {
    result.warnings.push("CHANGED_FILE_PATHS_UNAVAILABLE");
  }

  result.blockers = Array.from(blockers);
  result.warnings = Array.from(new Set([
    ...readinessWarnings.filter(w => w !== "SNAPSHOT_MISSING"),
    ...(changedFilesCount > 0 && (!changedFilePathsAvailable || !evidenceSuccessful)
      ? ["CHANGED_FILE_PATHS_UNAVAILABLE"]
      : []),
    ...(changedFilesSource === "cached_pr_package" ? ["CHANGED_FILES_FROM_CACHE"] : []),
  ]));

  // Determine status based on blockers
  if (blockers.has("HEAD_SHA_MISSING") || blockers.has("CHANGED_FILES_MISSING")) {
    result.status = "BLOCKED";
  } else if (changedFilesCount > 0 && (!changedFilePathsAvailable || !evidenceSuccessful)) {
    result.status = "PARTIAL";
  } else if (readinessStatus === "READY" && blockers.size === 0) {
    result.status = "READY";
  } else if (readinessStatus === "PARTIAL" && blockers.size === 0) {
    result.status = "PARTIAL";
  } else if (blockers.size > 0) {
    result.status = "BLOCKED";
  } else if (!headSha && !changedFilesCount) {
    result.status = "UNKNOWN";
    result.warnings.push("PR_PACKAGE_DATA_MISSING");
  } else {
    result.status = "READY";
  }

  // Parse and set recommendation audit
  const recAudit = readinessData?.recommendation_audit;
  if (recAudit) {
    result.recommendationAudit = {
      status: (recAudit.status || "UNKNOWN") as any,
      headCommitShaAtGeneration: recAudit.head_commit_sha_at_generation || undefined,
      changedFilesCountAtGeneration: recAudit.changed_files_count_at_generation ?? undefined,
      recommendedAt: recAudit.recommended_at || undefined,
      recommendationRunId: recAudit.recommendation_run_id || undefined,
    };
  } else {
    let auditStatus: "NO_RECOMMENDATION_YET" | "AUDITABLE" | "OUTDATED" | "LEGACY_NO_SNAPSHOT" = "NO_RECOMMENDATION_YET";
    if (snapshot?.head_commit_sha_at_generation) {
      if (snapshot.is_stale === true) {
        auditStatus = "OUTDATED";
      } else {
        auditStatus = "AUDITABLE";
      }
    } else if (snapshot) {
      auditStatus = "LEGACY_NO_SNAPSHOT";
    }
    result.recommendationAudit = {
      status: auditStatus,
      headCommitShaAtGeneration: snapshot?.head_commit_sha_at_generation || undefined,
    };
  }

  // Determine generation capabilities
  result.canGenerateDraftPlan = result.status !== "BLOCKED" && result.status !== "UNKNOWN";
  result.canGenerateConfidentPlan = result.status === "READY" && result.snapshotStatus === "CURRENT";

  // Debug output in development
  if (process.env.NODE_ENV === "development") {
    console.debug("[PR_PACKAGE_ADAPTER_DEBUG]", {
      rawPrPackage: prPackage,
      rawPullRequest: pullRequestData,
      normalized: result,
      blockers: result.blockers,
      status: result.status,
    });
  }

  return result;
}

/**
 * Normalize changed files array to consistent view model.
 */
function normalizeChangedFiles(rawFiles: any[]): ChangedFileViewModel[] {
  if (!Array.isArray(rawFiles)) {
    return [];
  }

  return rawFiles.map((file) => ({
    file_path: file.file_path || file.filename || file.path || "unknown",
    status: normalizeFileStatus(file.status),
    additions: file.additions || 0,
    deletions: file.deletions || 0,
    previous_filename: file.previous_filename || file.previous_file || undefined,
    patch_summary: file.patch_summary || file.patch || undefined,
    patch_missing: file.patch_missing === true,
    layer: file.layer || undefined,
    component: file.component || undefined,
    flow: file.flow || undefined,
    type: normalizeFileType(file.type, file.file_path),
  }));
}

function normalizeFileStatus(status: string): ChangedFileViewModel["status"] {
  if (!status) return "modified";
  const s = status.toLowerCase();
  if (s === "added") return "added";
  if (s === "deleted" || s === "removed") return "deleted";
  if (s === "renamed") return "renamed";
  return "modified";
}

function normalizeFileType(type: string, filePath: string): ChangedFileViewModel["type"] {
  if (type) {
    const t = type.toLowerCase();
    if (["source", "test", "config", "migration"].includes(t)) {
      return t as ChangedFileViewModel["type"];
    }
  }
  
  if (filePath) {
    const path = filePath.toLowerCase();
    if (path.includes("test") || path.includes("spec")) return "test";
    if (path.includes("config") || path.endsWith(".json") || path.endsWith(".yaml") || path.endsWith(".yml")) return "config";
    if (path.includes("migration") || path.includes("migrate")) return "migration";
  }
  
  return "unknown";
}

/**
 * Get readable warning message for a blocker code.
 */
export function getBlockerMessage(blockerCode: string): string {
  const messages: Record<string, string> = {
    HEAD_SHA_MISSING: "PR head commit SHA is missing. Test freshness cannot be calculated.",
    CHANGED_FILES_MISSING: "Changed files are missing. Targeted and risk-based regression plans are blocked.",
    SNAPSHOT_MISSING: "This recommendation does not have an auditable PR snapshot.",
    PR_UPDATED_AFTER_RECOMMENDATION: "This recommendation is outdated because the PR has new commits.",
    PR_CHANGED_FILES_UPDATED: "Changed files changed after this recommendation was generated.",
    PATCH_MISSING: "Changed files were found, but patch details are unavailable. Impact analysis may be less precise.",
    LARGE_DIFF_TRUNCATED: "Large diff detected. Some patch details may be truncated.",
    PR_PACKAGE_DATA_MISSING: "PR package data is not available in the API response.",
    CHANGED_FILE_PATHS_UNAVAILABLE: "Changed file details unavailable. PR impact analysis may be incomplete.",
    CHANGED_FILES_FROM_CACHE: "Changed files loaded from cached PR package.",
  };
  
  return messages[blockerCode] || `Unknown blocker: ${blockerCode}`;
}

/**
 * Get readable warning message for a warning code.
 */
export function getWarningMessage(warningCode: string): string {
  const messages: Record<string, string> = {
    PATCH_MISSING: "Changed files were found, but patch details are unavailable. Impact analysis may be less precise.",
    LARGE_DIFF_TRUNCATED: "Large diff detected. Some patch details may be truncated.",
    PR_PACKAGE_DATA_MISSING: "PR package data is not available in the API response.",
    CHANGED_FILE_PATHS_UNAVAILABLE: "Changed file details unavailable. PR impact analysis may be incomplete.",
    CHANGED_FILES_FROM_CACHE: "Changed files loaded from cached PR package.",
  };
  
  return messages[warningCode] || `Unknown warning: ${warningCode}`;
}
