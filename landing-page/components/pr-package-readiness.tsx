"use client";

import React, { useState } from "react";
import { PRPackageViewModel, ChangedFileViewModel, getBlockerMessage, getWarningMessage } from "@/lib/adapters/prPackageAdapter";
import { ChevronDown, ChevronUp, AlertTriangle, CheckCircle, XCircle, RefreshCw } from "lucide-react";

// Part 7: Readiness Warning Components

interface PRPackageSummaryCardProps {
  prPackage: PRPackageViewModel;
  compact?: boolean;
}

export function PRPackageSummaryCard({ prPackage, compact = false }: PRPackageSummaryCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const getStatusColor = (status: "READY" | "PARTIAL" | "BLOCKED" | "OUTDATED" | "UNKNOWN") => {
    switch (status) {
      case "READY":
        return "text-emerald-400 bg-emerald-950/20 border-emerald-800/40";
      case "PARTIAL":
        return "text-amber-400 bg-amber-950/20 border-amber-800/40";
      case "BLOCKED":
        return "text-rose-400 bg-rose-950/20 border-rose-800/40";
      case "OUTDATED":
        return "text-orange-400 bg-orange-950/20 border-orange-800/40";
      default:
        return "text-zinc-400 bg-zinc-950/20 border-zinc-800/40";
    }
  };

  const getStatusIcon = (status: "READY" | "PARTIAL" | "BLOCKED" | "OUTDATED" | "UNKNOWN") => {
    switch (status) {
      case "READY":
        return <CheckCircle className="w-4 h-4" />;
      case "PARTIAL":
        return <AlertTriangle className="w-4 h-4" />;
      case "BLOCKED":
        return <XCircle className="w-4 h-4" />;
      case "OUTDATED":
        return <RefreshCw className="w-4 h-4" />;
      default:
        return null;
    }
  };

  const formatSha = (sha?: string | null | undefined) => {
    if (!sha) return "N/A";
    return sha.length > 7 ? `${sha.substring(0, 7)}` : sha;
  };

  if (compact) {
    return (
      <div className={`p-4 rounded-lg border ${getStatusColor(prPackage.status)}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {getStatusIcon(prPackage.status)}
            <span className="font-medium">PR Package: {prPackage.status}</span>
          </div>
          <div className="text-sm">
            {prPackage.prNumber && (
              <span className="font-medium">PR #{prPackage.prNumber}</span>
            )}
            {prPackage.headShaShort && (
              <span className="ml-2 text-zinc-400">SHA: {prPackage.headShaShort}</span>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`p-6 rounded-lg border ${getStatusColor(prPackage.status)}`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            {getStatusIcon(prPackage.status)}
            <h3 className="text-lg font-semibold">Selected PR Change Package</h3>
          </div>
          {prPackage.title && (
            <p className="text-sm text-zinc-300 mb-1">
              PR #{prPackage.prNumber} — {prPackage.title}
            </p>
          )}
          <div className="text-sm text-zinc-400">
            {prPackage.sourceBranch && prPackage.targetBranch && (
              <span className="mr-4">
                {prPackage.sourceBranch} → {prPackage.targetBranch}
              </span>
            )}
            {prPackage.headShaShort && (
              <span className="mr-4">Head SHA: {prPackage.headShaShort}</span>
            )}
            {prPackage.baseSha && (
              <span className="mr-4">Base SHA: {formatSha(prPackage.baseSha)}</span>
            )}
            <span>Changed Files: {prPackage.changedFilesCount}</span>
          </div>
        </div>
        <div className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(prPackage.status)}`}>
          {prPackage.status}
        </div>
      </div>

      {prPackage.blockers.length > 0 && (
        <div className="mb-4 p-3 bg-rose-950/20 border border-rose-800/40 rounded-md">
          <div className="flex items-center gap-2 text-rose-400 mb-2">
            <XCircle className="w-4 h-4" />
            <span className="font-medium">Blocked</span>
          </div>
          <ul className="text-sm text-rose-300 space-y-1">
            {prPackage.blockers.map((blocker, idx) => (
              <li key={idx}>• {getBlockerMessage(blocker)}</li>
            ))}
          </ul>
        </div>
      )}

      {prPackage.warnings.length > 0 && (
        <div className="mb-4 p-3 bg-amber-950/20 border border-amber-800/40 rounded-md">
          <div className="flex items-center gap-2 text-amber-400 mb-2">
            <AlertTriangle className="w-4 h-4" />
            <span className="font-medium">Warnings</span>
          </div>
          <ul className="text-sm text-amber-300 space-y-1">
            {prPackage.warnings.map((warning, idx) => (
              <li key={idx}>• {getWarningMessage(warning)}</li>
            ))}
          </ul>
        </div>
      )}

      {!prPackage.changedFilePathsAvailable && prPackage.changedFilesCount > 0 && (
        <div className="mb-4 p-3 bg-amber-950/20 border border-amber-800/40 rounded-md text-sm text-amber-300">
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="w-4 h-4" />
            Changed file details unavailable. PR impact analysis may be incomplete.
          </div>
          {prPackage.evidenceError && <p className="mt-1 text-xs text-amber-400">{prPackage.evidenceError}</p>}
        </div>
      )}

      {prPackage.changedFilesSource === "cached_pr_package" && (
        <p className="mb-4 text-xs text-amber-400">Changed files loaded from cached PR package.</p>
      )}

      {(() => {
        const auditStatus = prPackage.recommendationAudit?.status;
        if (!auditStatus || auditStatus === "NO_RECOMMENDATION_YET" || auditStatus === "UNKNOWN") return null;
        
        const getAuditColor = (status: string) => {
          switch (status) {
            case "AUDITABLE":
              return "text-emerald-400 bg-emerald-950/20 border-emerald-800/40";
            case "OUTDATED":
              return "text-orange-400 bg-orange-950/20 border-orange-800/40";
            case "LEGACY_NO_SNAPSHOT":
              return "text-amber-400 bg-amber-950/20 border-amber-800/40";
            default:
              return "text-zinc-400 bg-zinc-950/20 border-zinc-800/40";
          }
        };

        return (
          <div className={`mb-4 p-3 rounded-md border text-sm ${getAuditColor(auditStatus)}`}>
            <div className="flex items-center gap-2 mb-1">
              {auditStatus === "AUDITABLE" ? (
                <CheckCircle className="w-4 h-4 text-emerald-400" />
              ) : auditStatus === "OUTDATED" ? (
                <RefreshCw className="w-4 h-4 text-orange-400" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-400" />
              )}
              <span className="font-medium">
                Recommendation Snapshot: {
                  auditStatus === "AUDITABLE" ? "Auditable" :
                  auditStatus === "OUTDATED" ? "Outdated Snapshot" :
                  "Legacy (No Snapshot)"
                }
              </span>
            </div>
            <p className="opacity-90">
              {auditStatus === "AUDITABLE" && (
                `This recommendation has a matching PR snapshot generated at commit ${formatSha(prPackage.recommendationAudit?.headCommitShaAtGeneration)}.`
              )}
              {auditStatus === "OUTDATED" && (
                `The PR head commit has changed since generation (generated at ${formatSha(prPackage.recommendationAudit?.headCommitShaAtGeneration)} but current is ${formatSha(prPackage.headSha)}). Regenerate before release signoff.`
              )}
              {auditStatus === "LEGACY_NO_SNAPSHOT" && (
                "Warning: This recommendation does not have an auditable PR snapshot."
              )}
            </p>
          </div>
        );
      })()}

      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm font-medium text-zinc-400 hover:text-zinc-300"
      >
        {isExpanded ? (
          <>
            <ChevronUp className="w-4 h-4" />
            Hide Changed Files
          </>
        ) : (
          <>
            <ChevronDown className="w-4 h-4" />
            Show Changed Files ({prPackage.changedFilesCount})
          </>
        )}
      </button>

      {isExpanded && (
        <ChangedFilesList
          changedFiles={prPackage.changedFiles}
          changedFilesCount={prPackage.changedFilesCount}
          evidenceError={prPackage.evidenceError}
        />
      )}
    </div>
  );
}

interface ChangedFilesListProps {
  changedFiles: ChangedFileViewModel[];
  changedFilesCount?: number;
  evidenceError?: string;
}

export function ChangedFilesList({ changedFiles, changedFilesCount = 0, evidenceError }: ChangedFilesListProps) {
  const getStatusColor = (status: ChangedFileViewModel["status"]) => {
    switch (status) {
      case "added":
        return "text-emerald-400 bg-emerald-950/20";
      case "modified":
        return "text-blue-400 bg-blue-950/20";
      case "deleted":
        return "text-rose-400 bg-rose-950/20";
      case "renamed":
        return "text-purple-400 bg-purple-950/20";
      default:
        return "text-zinc-400 bg-zinc-950/20";
    }
  };

  const getFileTypeIcon = (fileType: ChangedFileViewModel["type"]) => {
    switch (fileType) {
      case "test":
        return <span className="text-xs px-2 py-0.5 rounded bg-purple-950/30 text-purple-400">test</span>;
      case "config":
        return <span className="text-xs px-2 py-0.5 rounded bg-zinc-950/30 text-zinc-400">config</span>;
      case "migration":
        return <span className="text-xs px-2 py-0.5 rounded bg-orange-950/30 text-orange-400">migration</span>;
      case "source":
        return <span className="text-xs px-2 py-0.5 rounded bg-blue-950/30 text-blue-400">source</span>;
      default:
        return null;
    }
  };

  if (!changedFiles || changedFiles.length === 0) {
    return (
      <div className="mt-4 p-4 bg-zinc-950/20 border border-zinc-800/40 rounded-md">
        <p className="text-sm text-amber-300">Changed file details unavailable. PR impact analysis may be incomplete.</p>
        {changedFilesCount > 0 && <p className="mt-1 text-xs text-zinc-500">Provider reported {changedFilesCount} changed file(s), but usable paths were not stored.</p>}
        {evidenceError && <p className="mt-1 text-xs text-zinc-500">{evidenceError}</p>}
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-2">
      {changedFiles.map((file, idx) => (
        <div key={idx} className="p-3 bg-zinc-950/20 border border-zinc-800/40 rounded-md">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs px-2 py-0.5 rounded ${getStatusColor(file.status)}`}>
              {file.status}
            </span>
            {getFileTypeIcon(file.type)}
            <span className="text-sm text-zinc-300 font-mono truncate">{file.file_path}</span>
          </div>
          <div className="flex items-center gap-4 text-xs text-zinc-500">
            <span className="text-emerald-400">+{file.additions}</span>
            <span className="text-rose-400">-{file.deletions}</span>
            {file.previous_filename && (
              <span className="text-zinc-400">from: {file.previous_filename}</span>
            )}
            {file.patch_missing && (
              <span className="text-amber-400">patch missing</span>
            )}
          </div>
          {file.layer && (
            <div className="mt-1 text-xs text-zinc-500">
              Layer: {file.layer}
              {file.component && ` • Component: ${file.component}`}
              {file.flow && ` • Flow: ${file.flow}`}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

interface InputReadinessBannerProps {
  prPackage: PRPackageViewModel;
  className?: string;
}

export function InputReadinessBanner({ prPackage, className = "" }: InputReadinessBannerProps) {
  const getBannerColor = (status: "READY" | "PARTIAL" | "BLOCKED" | "OUTDATED" | "UNKNOWN") => {
    switch (status) {
      case "READY":
        return "bg-emerald-950/20 border-emerald-800/40 text-emerald-400";
      case "PARTIAL":
        return "bg-amber-950/20 border-amber-800/40 text-amber-400";
      case "BLOCKED":
        return "bg-rose-950/20 border-rose-800/40 text-rose-400";
      case "OUTDATED":
        return "bg-orange-950/20 border-orange-800/40 text-orange-400";
      default:
        return "bg-zinc-950/20 border-zinc-800/40 text-zinc-400";
    }
  };

  return (
    <div className={`p-4 rounded-lg border ${getBannerColor(prPackage.status)} ${className}`}>
      <div className="flex items-center gap-3">
        {prPackage.status === "READY" && <CheckCircle className="w-5 h-5" />}
        {prPackage.status === "PARTIAL" && <AlertTriangle className="w-5 h-5" />}
        {prPackage.status === "BLOCKED" && <XCircle className="w-5 h-5" />}
        {prPackage.status === "OUTDATED" && <RefreshCw className="w-5 h-5" />}
        
        <div className="flex-1">
          <p className="font-medium">
            {prPackage.status === "READY" && "PR Package Ready"}
            {prPackage.status === "PARTIAL" && "PR Package Partial"}
            {prPackage.status === "BLOCKED" && "PR Package Blocked"}
            {prPackage.status === "OUTDATED" && "PR Package Outdated"}
            {prPackage.status === "UNKNOWN" && "PR Package Unknown"}
          </p>
          {prPackage.blockers.length > 0 && (
            <p className="text-sm mt-1">
              Blocked: {prPackage.blockers.map(getBlockerMessage).join(", ")}
            </p>
          )}
          {prPackage.warnings.length > 0 && (
            <p className="text-sm mt-1">
              Warnings: {prPackage.warnings.map(getWarningMessage).join(", ")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

interface StaleRecommendationBannerProps {
  prPackage: PRPackageViewModel;
  onRegenerate?: () => void;
}

export function StaleRecommendationBanner({ prPackage, onRegenerate }: StaleRecommendationBannerProps) {
  if (prPackage.snapshotStatus !== "OUTDATED") return null;

  const formatSha = (sha?: string | null | undefined) => {
    if (!sha) return "N/A";
    return sha.length > 7 ? `${sha.substring(0, 7)}` : sha;
  };

  return (
    <div className="p-4 bg-orange-950/20 border border-orange-800/40 rounded-lg">
      <div className="flex items-start gap-3">
        <RefreshCw className="w-5 h-5 text-orange-400 mt-0.5" />
        <div className="flex-1">
          <p className="font-medium text-orange-400">Recommendation Outdated</p>
          <p className="text-sm text-orange-300 mt-1">
            This recommendation is outdated because the PR has new commits. Regenerate before release signoff.
          </p>
          {onRegenerate && (
            <button
              onClick={onRegenerate}
              className="mt-3 px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 transition-colors"
            >
              Regenerate Recommendation
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

interface MissingInputWarningProps {
  type: "HEAD_SHA_MISSING" | "CHANGED_FILES_MISSING" | "SNAPSHOT_MISSING" | "PR_UPDATED_AFTER_RECOMMENDATION" | "PATCH_MISSING" | "LARGE_DIFF_TRUNCATED";
  className?: string;
}

export function MissingInputWarning({ type, className = "" }: MissingInputWarningProps) {
  const warnings: Record<string, { title: string; message: string; color: string }> = {
    HEAD_SHA_MISSING: {
      title: "PR head commit SHA is missing",
      message: "Test freshness cannot be calculated without the head commit SHA.",
      color: "bg-rose-950/20 border-rose-800/40 text-rose-400"
    },
    CHANGED_FILES_MISSING: {
      title: "Changed files are missing",
      message: "Targeted and risk-based regression plans are blocked without changed files.",
      color: "bg-rose-950/20 border-rose-800/40 text-rose-400"
    },
    SNAPSHOT_MISSING: {
      title: "PR snapshot is missing",
      message: "Recommendation snapshot was not created during generation.",
      color: "bg-rose-950/20 border-rose-800/40 text-rose-400"
    },
    PR_UPDATED_AFTER_RECOMMENDATION: {
      title: "PR has been updated",
      message: "This recommendation is outdated because the PR has new commits.",
      color: "bg-orange-950/20 border-orange-800/40 text-orange-400"
    },
    PATCH_MISSING: {
      title: "Patch details unavailable",
      message: "Changed files were found, but patch details are unavailable. Impact analysis may be less precise.",
      color: "bg-amber-950/20 border-amber-800/40 text-amber-400"
    },
    LARGE_DIFF_TRUNCATED: {
      title: "Large diff truncated",
      message: "The PR has too many files. Some changed files were truncated for performance.",
      color: "bg-amber-950/20 border-amber-800/40 text-amber-400"
    }
  };

  const warning = warnings[type];
  if (!warning) return null;

  return (
    <div className={`p-4 rounded-lg border ${warning.color} ${className}`}>
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 mt-0.5" />
        <div>
          <p className="font-medium">{warning.title}</p>
          <p className="text-sm mt-1">{warning.message}</p>
        </div>
      </div>
    </div>
  );
}
