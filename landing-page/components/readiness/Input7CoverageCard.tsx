"use client";

import React, { useState } from "react";
import { CheckCircle, AlertTriangle, Clock, XCircle, Upload } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { InputReadinessItemViewModel } from "@/lib/readiness/inputReadinessAdapter";

interface Input7CoverageCardProps {
  input: InputReadinessItemViewModel;
  repositoryId: string;
  pullRequestId: string;
  onAction?: () => void;
}

export function Input7CoverageCard({
  input,
  repositoryId,
  pullRequestId,
  onAction,
}: Input7CoverageCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const details = input.details || {};
  const status = input.status as string;

  const coverageCommitSha = (details.coverage_commit_sha as string | null) ?? null;
  const currentPrHeadSha = (details.current_pr_head_sha as string | null) ?? null;
  const commitShaSource = (details.commit_sha_source as string) ?? "MANUAL";
  const shaMismatch = (details.sha_mismatch as boolean) ?? false;
  const isCurrent = (details.is_current as boolean) ?? false;
  const filesTotal = (details.files_total as number) ?? 0;
  const coveredFileCount = (details.covered_file_count as number) ?? (details.coverage_file_count as number) ?? 0;
  const changedFilesTotal = (details.changed_files_total as number) ?? 0;
  const changedFilesWithCoverage = (details.changed_files_with_coverage as number) ?? 0;
  const fileToTestLinkCount = (details.file_to_test_link_count as number) ?? (details.linked_test_count as number) ?? 0;
  const coverageConfidence = (details.current_pr_coverage_confidence as string | null) ?? "NONE";

  // New classification fields
  const coverableChangedFilesTotal = (details.coverable_changed_files_total as number) ?? 0;
  const coverableChangedFilesCovered = (details.coverable_changed_files_covered as number) ?? 0;
  const changedTestFilesTotal = (details.changed_test_files_total as number) ?? 0;
  const nonCoverableChangedFilesTotal = (details.non_coverable_changed_files_total as number) ?? 0;
  const uncoveredCoverableChangedFiles = (details.uncovered_coverable_changed_files as string[]) ?? [];

  const isHistorical = status === "HISTORICAL_ONLY";
  const isMissing = status === "MISSING";

  const getStatusIcon = (s: string) => {
    switch (s) {
      case "READY":
      case "TEST_LEVEL_READY":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case "PARTIAL_READY":
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case "PARTIAL":
      case "PARTIAL_EMPTY":
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case "NO_CHANGED_FILE_COVERAGE":
        return <AlertTriangle className="w-4 h-4 text-amber-500" />;
      case "HISTORICAL_ONLY":
      case "STALE":
        return <Clock className="w-4 h-4 text-orange-500" />;
      case "MISSING":
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return <AlertTriangle className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusColor = (s: string) => {
    switch (s) {
      case "READY":
      case "TEST_LEVEL_READY":
        return "border-green-500/20 bg-green-500/5";
      case "PARTIAL_READY":
        return "border-yellow-500/20 bg-yellow-500/5";
      case "PARTIAL":
      case "PARTIAL_EMPTY":
        return "border-yellow-500/20 bg-yellow-500/5";
      case "NO_CHANGED_FILE_COVERAGE":
        return "border-amber-500/20 bg-amber-500/5";
      case "HISTORICAL_ONLY":
      case "STALE":
        return "border-orange-500/20 bg-orange-500/5";
      case "MISSING":
        return "border-red-500/20 bg-red-500/5";
      default:
        return "border-gray-500/20 bg-gray-500/5";
    }
  };

  const formatSha = (sha: string | null) => {
    if (!sha) return "—";
    return sha.length > 12 ? `${sha.slice(0, 12)}...` : sha;
  };

  return (
    <div className={`border rounded-lg p-4 ${getStatusColor(status)}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {getStatusIcon(status)}
          <h3 className="font-semibold text-white">{input.label}</h3>
          <span
            className={`px-2 py-1 text-xs rounded ${
              status === "READY" || status === "TEST_LEVEL_READY"
                ? "bg-green-500/20 text-green-300"
                : status === "PARTIAL_READY" || status === "PARTIAL" || status === "PARTIAL_EMPTY"
                ? "bg-yellow-500/20 text-yellow-300"
                : status === "NO_CHANGED_FILE_COVERAGE"
                ? "bg-amber-500/20 text-amber-300"
                : status === "HISTORICAL_ONLY" || status === "STALE"
                ? "bg-orange-500/20 text-orange-300"
                : "bg-red-500/20 text-red-300"
            }`}
          >
            {status === "TEST_LEVEL_READY" ? "READY" : status === "PARTIAL_READY" ? "PARTIAL" : status}
          </span>
        </div>
      </div>

      <p className="text-sm text-gray-300 mb-4">{input.summary}</p>

      {isHistorical && (
        <div className="text-xs text-orange-300 bg-orange-950/20 border border-orange-900/30 rounded-lg p-3 mb-4">
          Historical Only — coverage SHA does not match selected PR head SHA.
        </div>
      )}

      <div className="space-y-1.5 p-3 bg-zinc-900/40 border border-zinc-800/40 rounded-lg text-xs font-mono mb-4">
        <div className="flex justify-between">
          <span className="text-zinc-400">Coverage commit SHA:</span>
          <span className="text-zinc-200" title={coverageCommitSha ?? undefined}>
            {formatSha(coverageCommitSha)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Current PR head SHA:</span>
          <span className="text-zinc-200" title={currentPrHeadSha ?? undefined}>
            {formatSha(currentPrHeadSha)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Commit SHA source:</span>
          <span className={commitShaSource === "AUTO_FROM_SELECTED_PR" ? "text-emerald-400" : "text-zinc-200"}>
            {commitShaSource === "AUTO_FROM_SELECTED_PR" ? "Auto from selected PR" : "Manual"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">SHA mismatch:</span>
          <span className={shaMismatch ? "text-rose-400" : "text-emerald-400"}>{shaMismatch ? "true" : "false"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Is current:</span>
          <span className={isCurrent ? "text-emerald-400" : "text-amber-400"}>{isCurrent ? "true" : "false"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Files total:</span>
          <span className="text-zinc-200">{filesTotal}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Covered file count:</span>
          <span className="text-zinc-200">{coveredFileCount}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Changed source files covered:</span>
          <span className="text-zinc-200">
            {coverableChangedFilesCovered} / {coverableChangedFilesTotal}
          </span>
        </div>
        {changedTestFilesTotal > 0 && (
          <div className="flex justify-between">
            <span className="text-zinc-400">Changed test files:</span>
            <span className="text-zinc-200">{changedTestFilesTotal}</span>
          </div>
        )}
        {nonCoverableChangedFilesTotal > 0 && (
          <div className="flex justify-between">
            <span className="text-zinc-400">Non-coverable changed files:</span>
            <span className="text-zinc-200">{nonCoverableChangedFilesTotal}</span>
          </div>
        )}
        {uncoveredCoverableChangedFiles.length > 0 && (
          <div className="mt-2 pt-2 border-t border-zinc-800/40">
            <div className="text-zinc-400 text-xs mb-1">Uncovered changed source files:</div>
            {uncoveredCoverableChangedFiles.map((file, idx) => (
              <div key={idx} className="text-xs text-rose-400 font-mono ml-2">
                - {file}
              </div>
            ))}
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-zinc-400">File-to-test links:</span>
          <span className="text-zinc-200">{fileToTestLinkCount}</span>
        </div>
        {fileToTestLinkCount === 0 && filesTotal > 0 && (
          <div className="text-xs text-zinc-500 mt-1 italic">
            File-level coverage is available. Per-test file links are not available from this coverage format.
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-zinc-400">Current PR coverage confidence:</span>
          <span
            className={
              coverageConfidence === "HIGH"
                ? "text-emerald-400"
                : coverageConfidence === "MODERATE"
                ? "text-amber-400"
                : coverageConfidence === "LOW" || coverageConfidence === "NONE"
                ? "text-rose-400"
                : "text-zinc-200"
            }
          >
            {coverageConfidence}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {isMissing || isHistorical ? (
          <Link
            href={`/app/repositories/${repositoryId}/coverage?pullRequestId=${pullRequestId}&returnTo=readiness`}
          >
            <Button size="sm" variant="outline" className="text-xs flex items-center gap-1">
              <Upload className="w-3.5 h-3.5" />
              {isHistorical ? "Upload Current Coverage" : "Upload Coverage Report"}
            </Button>
          </Link>
        ) : (
          <Button size="sm" variant="outline" className="text-xs" onClick={onAction}>
            View Coverage Details
          </Button>
        )}

        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="text-xs text-zinc-400 hover:text-white underline underline-offset-4"
        >
          {isExpanded ? "Hide details" : "Show details"}
        </button>
      </div>

      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-zinc-800/40 text-xs text-zinc-400 space-y-1">
          <p>Status reason: {(details.status_reason as string) ?? "—"}</p>
          <p>Coverage level: {(details.coverage_level as string) ?? "—"}</p>
          <p>Overall coverage: {(((details.overall_coverage_pct as number) ?? 0) * 100).toFixed(1)}%</p>
        </div>
      )}
    </div>
  );
}
