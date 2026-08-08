"use client";

import React, { useState } from "react";
import { Eye, CheckCircle, AlertTriangle, Clock, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { InputReadinessItemViewModel } from "@/lib/readiness/inputReadinessAdapter";
import { SafeObjectRenderer } from "./SafeObjectRenderer";

interface Input5MappingCardProps {
  input: InputReadinessItemViewModel;
  repositoryId: string;
  pullRequestId: string;
  onReviewClick?: () => void;
}

export function Input5MappingCard({
  input,
  repositoryId,
  pullRequestId,
  onReviewClick
}: Input5MappingCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showDebug, setShowDebug] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);
  const [rawJsonCopied, setRawJsonCopied] = useState(false);
  
  // Extract key metrics from details — use canonical field names from backend.
  // NOTE: this card reads the new AC-level 7-state mapping_summary fields
  // (evidence_verified_aligned_count, metadata_conflict_semantic_match_count,
  // partial_support_count, no_candidate_count, user_confirmed_count,
  // veriscope_key_verified_count) exposed on `details` by
  // InputReadinessV2Service._evaluate_input_5. It intentionally does NOT read
  // legacy candidate-level counters (suggested_mapped_ac_count,
  // pending_review_mapping_count, needs_review_mapping_count,
  // conflicted_mapping_count) or any compatibility_summary — those reflect a
  // different, pre-7-state aggregation and can disagree with the AC-Test
  // Mapping workspace.
  const details = input.details || {};
  const total = (details.total_acs as number) ?? (details.accepted_ac_count as number) ?? (details.total_accepted_acs as number) ?? 0;
  const testCaseCount = (details.test_case_count as number) ?? (details.mapped_tests_count as number) ?? 0;
  const testsWithAcRefs = (details.tests_with_external_ac_refs as number) ?? (details.tests_with_ac_refs as number) ?? 0;
  const mappingAttempts = (details.mapping_attempt_count as number) ?? (details.mapping_attempts as number) ?? testsWithAcRefs;
  const candidateMappingEdges = (details.candidate_edge_count as number) ?? (details.candidate_mapping_edges as number) ?? 0;

  // ── New 7-state AC-level counts (source of truth) ──────────────────────
  const userConfirmedCount = (details.user_confirmed_count as number) ?? 0;
  const veriscopeKeyVerifiedCount = (details.veriscope_key_verified_count as number) ?? 0;
  const evidenceAlignedCount = (details.evidence_verified_aligned_count as number) ?? 0;
  const metadataConflictCount = (details.metadata_conflict_semantic_match_count as number) ?? 0;
  const partialSupportCount = (details.partial_support_count as number) ?? 0;
  const suggestedCount = (details.suggested_count as number) ?? 0;
  const noCandidateCount = (details.no_candidate_count as number) ?? 0;
  const rejectedCount = (details.rejected_count as number) ?? 0;
  const summaryIntegrity = (details.summary_integrity as string) ?? undefined;
  const blockingReasons = Array.isArray(details.blocking_reasons) ? (details.blocking_reasons as string[]) : [];

  // Scoring metrics — use the new trusted-coverage model
  const trustedCoveragePct = (details.trusted_coverage_percent as number) ?? (details.confirmed_coverage_percent as number) ?? (details.coverage_progress_pct as number) ?? 0;
  const autoTrustedCount = (details.auto_trusted_coverage_count as number) ?? (veriscopeKeyVerifiedCount + evidenceAlignedCount);
  const trustedCoverageCount = (details.trusted_coverage_count as number) ?? (autoTrustedCount + userConfirmedCount);
  const reviewRequiredCount = (details.review_required_count as number) ?? (metadataConflictCount + partialSupportCount + suggestedCount + noCandidateCount);
  const confirmedACs = userConfirmedCount + veriscopeKeyVerifiedCount;

  // Discovery score still shown for diagnostics; if coverage is fully trusted,
  // it reflects the full input weight.
  const discoveryScore = (details.mapping_discovery_score as number) ?? input.earned_score ?? 0;
  const discoveryMaxScore = (details.mapping_discovery_max_score as number) ?? input.max_score ?? 15;

  // Review Mappings button visibility
  const hasPendingWork = reviewRequiredCount > 0;
  const actionableReviewCount = reviewRequiredCount;

  const metadataQualityStatus = (details.metadata_quality_status as string) ?? "FAIL";
  const metadataQualityDetail = (details.metadata_quality_detail as string) ?? "";
  
  // Breakdown objects
  const mappingSourceBreakdown = details.mapping_source_breakdown as Record<string, number> | undefined;
  const reviewStatusBreakdown = details.review_status_breakdown as Record<string, number> | undefined;
  const confidenceBreakdown = details.confidence_breakdown as Record<string, number> | undefined;
  const topSuggestedMappings = Array.isArray(details.top_suggested_mappings)
    ? (details.top_suggested_mappings as any[])
    : undefined;

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "READY":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case "PARTIAL":
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case "REVIEW_NEEDED":
      case "REVIEW_REQUIRED":
        return <AlertTriangle className="w-4 h-4 text-orange-500" />;
      case "MISSING":
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "READY":
        return "border-green-500/20 bg-green-500/5";
      case "PARTIAL":
        return "border-yellow-500/20 bg-yellow-500/5";
      case "REVIEW_NEEDED":
      case "REVIEW_REQUIRED":
        return "border-orange-500/20 bg-orange-500/5";
      case "MISSING":
        return "border-red-500/20 bg-red-500/5";
      default:
        return "border-gray-500/20 bg-gray-500/5";
    }
  };

  return (
    <div className={`border rounded-lg p-4 ${getStatusColor(input.status)}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {getStatusIcon(input.status)}
          <h3 className="font-semibold text-white">{input.label}</h3>
          <span className={`px-2 py-1 text-xs rounded ${
            input.status === "READY" ? "bg-green-500/20 text-green-300" :
            input.status === "PARTIAL" ? "bg-yellow-500/20 text-yellow-300" :
            (input.status === "NEEDS_REVIEW" || input.status === "REVIEW_REQUIRED") ? "bg-orange-500/20 text-orange-300" :
            "bg-red-500/20 text-red-300"
          }`}>
            {input.status}
          </span>
        </div>
        <div className="text-right">
          <div className="text-sm font-semibold text-white">
            Trusted coverage: <span className={trustedCoveragePct === 100 ? "text-emerald-400" : trustedCoveragePct === 0 ? "text-rose-400" : "text-amber-400"}>{trustedCoveragePct}%</span>
          </div>
          <div
            className="text-xs text-gray-400"
            title="Mapping discovery score: partial credit earned across all ACs based on evidence strength (confirmed=1.0, evidence-aligned=0.85, strong suggestion=0.6, weak suggestion=0.2, partial support=0.1), averaged and scaled to this input's weight. This is a discovery signal, not confirmed coverage."
          >
            Mapping discovery score: <span className="text-amber-300 font-mono">{discoveryScore} / {discoveryMaxScore}</span>
          </div>
        </div>
      </div>

      {/* Summary */}
      <p className="text-sm text-gray-300 mb-4">{input.summary}</p>

      {/* Conceptual status breakdown list */}
      <div className="space-y-1.5 p-3 bg-zinc-900/40 border border-zinc-800/40 rounded-lg text-xs font-mono mb-4">
        <div className="flex justify-between">
          <span className="text-zinc-400">Accepted ACs:</span>
          <span className="text-zinc-300">{total}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Test cases:</span>
          <span className="text-zinc-300">{testCaseCount}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Tests with AC refs:</span>
          <span className="text-zinc-300">{testsWithAcRefs}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Mapping attempts:</span>
          <span className="text-zinc-300">{mappingAttempts}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Candidate edges:</span>
          <span className="text-zinc-300">{candidateMappingEdges}</span>
        </div>
        <div className="flex justify-between border-t border-zinc-700/50 pt-1.5 mt-1.5">
          <span className="text-zinc-400">Trusted coverage:</span>
          <span className={trustedCoveragePct === 100 ? "text-emerald-400" : trustedCoveragePct === 0 ? "text-rose-400" : "text-amber-400"}>{trustedCoveragePct}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Auto-trusted:</span>
          <span className="text-emerald-300">{autoTrustedCount}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">User-confirmed:</span>
          <span className="text-blue-300">{userConfirmedCount} <span className="text-zinc-500">optional</span></span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Review required:</span>
          <span className={reviewRequiredCount === 0 ? "text-emerald-400" : "text-orange-400"}>{reviewRequiredCount}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Metadata conflicts requiring resolution:</span>
          <span className="text-orange-400">{metadataConflictCount}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Partial support requiring review:</span>
          <span className="text-amber-400">{partialSupportCount}</span>
        </div>
        <div className="flex justify-between border-t border-zinc-800/80 pt-1.5 mt-1">
          <span className="text-zinc-400">ACs with no candidates:</span>
          <span className="text-rose-400">{noCandidateCount}</span>
        </div>
      </div>

      {/* Secondary row: extra metadata */}
      <div className="flex flex-wrap gap-3 text-[10px] text-zinc-500 mb-4 font-mono">
        <span>Confirmed mapped test cases: <span className="text-zinc-300">{Number(details.mapped_tests_count || 0)}</span></span>
        {rejectedCount > 0 && (
          <span>Rejected: <span className="text-zinc-300">{rejectedCount}</span></span>
        )}
        {summaryIntegrity && (
          <span>Summary integrity: <span className={summaryIntegrity === "PASS" ? "text-emerald-400" : "text-rose-400"}>{summaryIntegrity}</span></span>
        )}
        {metadataQualityStatus && (
          <span>
            Metadata quality:{" "}
            <span className={
              metadataQualityStatus === "PASS" ? "text-emerald-400" :
              metadataQualityStatus === "PARTIAL" ? "text-amber-400" : "text-rose-400"
            }>
              {metadataQualityDetail || metadataQualityStatus}
            </span>
          </span>
        )}
      </div>

      {/* Progress Bar — trusted coverage (user-confirmed + auto-trusted) */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>Trusted Coverage</span>
          <span className={trustedCoveragePct === 100 ? "text-emerald-400" : trustedCoveragePct === 0 ? "text-rose-400" : "text-amber-400"}>
            {trustedCoveragePct === 100 ? "Complete" : `${trustedCoveragePct}% (${trustedCoverageCount ?? autoTrustedCount + userConfirmedCount}/${total} ACs)`}
          </span>
        </div>
        <div className="w-full bg-zinc-700 rounded-full h-2">
          <div
            className="bg-emerald-500 h-2 rounded-full transition-all duration-300"
            style={{ width: `${trustedCoveragePct}%` }}
          />
        </div>
        {trustedCoveragePct === 100 && reviewRequiredCount === 0 && (
          <p className="text-xs text-emerald-400 mt-1">
            {autoTrustedCount} AC{autoTrustedCount !== 1 ? "s have" : " has"} evidence-aligned trusted mappings. No review required.
          </p>
        )}
        {reviewRequiredCount === 0 && trustedCoveragePct < 100 && evidenceAlignedCount > 0 && (
          <p className="text-xs text-amber-400 mt-1">
            {evidenceAlignedCount} AC{evidenceAlignedCount !== 1 ? "s have" : " has"} evidence-aligned mappings. User confirmation is optional.
          </p>
        )}
        {metadataConflictCount > 0 && (
          <p className="text-xs text-orange-400 mt-1">
            {metadataConflictCount} metadata conflict{metadataConflictCount !== 1 ? "s require" : " requires"} resolution.
          </p>
        )}
        {partialSupportCount > 0 && (
          <p className="text-xs text-amber-400 mt-1">
            {partialSupportCount} partial support mapping{partialSupportCount !== 1 ? "s require" : " requires"} review.
          </p>
        )}
        {blockingReasons.length > 0 && (
          <ul className="text-xs text-zinc-400 mt-1 list-disc list-inside">
            {blockingReasons.map((reason, idx) => (
              <li key={idx}>{reason}</li>
            ))}
          </ul>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2">
        <Button
          onClick={onReviewClick}
          variant="outline"
          size="sm"
          className={`flex items-center gap-2 ${hasPendingWork ? "border-amber-700/50 text-amber-300 hover:bg-amber-950/30" : "border-zinc-700 text-zinc-300 hover:bg-zinc-800"}`}
        >
          <Eye className="w-4 h-4" />
          {hasPendingWork ? "Review Mappings" : "View Mappings"}
          {actionableReviewCount > 0 && (
            <span className="ml-1 px-1.5 py-0.5 text-[10px] rounded-full bg-amber-800/60">
              {actionableReviewCount}
            </span>
          )}
        </Button>
        
        <Button
          variant="ghost"
          size="sm"
          className="text-gray-400 hover:text-white"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isExpanded ? "Hide Summary" : "Show Summary"}
        </Button>
        
        <Button
          variant="ghost"
          size="sm"
          className="text-gray-400 hover:text-white"
          onClick={() => setShowDebug(!showDebug)}
        >
          {showDebug ? "Hide Debug" : "View Debug Details"}
        </Button>
      </div>

      {/* Expandable Summary */}
      {isExpanded && (
        <div className="mt-4 pt-4 border-t border-gray-700 space-y-4">
          <div className="text-sm text-gray-400 mb-2">Mapping Breakdown:</div>
          
          {/* Mapping Source Breakdown */}
          {mappingSourceBreakdown && (
            <div className="space-y-2">
              <div className="text-xs text-gray-500">Mapping Sources:</div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {Object.entries(mappingSourceBreakdown).map(([source, count]) => (
                  <div key={source} className="flex justify-between">
                    <span className="text-gray-300">{source.replace(/_/g, " ")}:</span>
                    <span className="text-zinc-300 font-mono">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Review Status Breakdown */}
          {reviewStatusBreakdown && (
            <div className="space-y-2">
              <div className="text-xs text-gray-500">Review Status:</div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {Object.entries(reviewStatusBreakdown).map(([status, count]) => (
                  <div key={status} className="flex justify-between">
                    <span className="text-gray-300">{status.replace(/_/g, " ")}:</span>
                    <span className="text-zinc-300 font-mono">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Confidence Breakdown */}
          {confidenceBreakdown && (
            <div className="space-y-2">
              <div className="text-xs text-gray-500">Confidence Levels:</div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {Object.entries(confidenceBreakdown).map(([level, count]) => (
                  <div key={level} className="flex justify-between">
                    <span className="text-gray-300">{level.replace(/_/g, " ")}:</span>
                    <span className="text-zinc-300 font-mono">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Unmapped ACs */}
          {Array.isArray(details.unmapped_ac_list) && (details.unmapped_ac_list as any[]).length > 0 && (
            <div className="space-y-2">
              <div className="text-xs text-gray-500">Unmapped ACs ({(details.unmapped_ac_list as any[]).length}):</div>
              <div className="max-h-32 overflow-y-auto">
                <ul className="text-xs text-gray-300 space-y-1">
                  {(details.unmapped_ac_list as any[]).slice(0, 10).map((ac: any, idx: number) => (
                    <li key={idx}>• {ac.stable_ac_key || ac.ac_title || `AC-${idx + 1}`}</li>
                  ))}
                  {(details.unmapped_ac_list as any[]).length > 10 && (
                    <li className="text-gray-500">... and {(details.unmapped_ac_list as any[]).length - 10} more</li>
                  )}
                </ul>
              </div>
            </div>
          )}

          {/* Top Suggested Mappings */}
          {topSuggestedMappings && topSuggestedMappings.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs text-gray-500">Top Suggested Mappings:</div>
              <div className="space-y-1">
                {topSuggestedMappings.slice(0, 5).map((mapping: any, idx: number) => (
                  <div key={idx} className="text-xs text-gray-300 flex justify-between">
                    <span>{mapping.stable_ac_key || mapping.ac_key} - {mapping.test_name}</span>
                    {mapping.confidence_score !== undefined && mapping.confidence_score !== null ? (
                      <span className="text-zinc-300 font-mono">{Math.round(mapping.confidence_score * 100)}%</span>
                    ) : mapping.confidence_label ? (
                      <span className="text-zinc-300 font-mono">{mapping.confidence_label}</span>
                    ) : null}
                  </div>
                ))}
                {topSuggestedMappings.length > 5 && (
                  <div className="text-xs text-gray-500">... and {topSuggestedMappings.length - 5} more</div>
                )}
              </div>
            </div>
          )}

          {/* Actions */}
          {input.actions && input.actions.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs text-gray-500">Available Actions:</div>
              <div className="flex flex-wrap gap-2">
                {input.actions.map((action: any, index: number) => (
                  <Button
                    key={index}
                    variant="outline"
                    size="sm"
                    className="text-xs"
                  >
                    {action.label}
                  </Button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Debug View */}
      {showDebug && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm text-gray-400">Debug Details:</div>
            <div className="flex gap-2">
              <button
                className="text-[10px] px-2 py-0.5 rounded border border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:border-zinc-500 transition-colors"
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(details, null, 2));
                  setRawJsonCopied(true);
                  setTimeout(() => setRawJsonCopied(false), 2000);
                }}
              >
                {rawJsonCopied ? "Copied!" : "Copy raw JSON"}
              </button>
              <button
                className="text-[10px] px-2 py-0.5 rounded border border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:border-zinc-500 transition-colors"
                onClick={() => setShowRawJson(!showRawJson)}
              >
                {showRawJson ? "Hide raw JSON" : "View raw JSON"}
              </button>
            </div>
          </div>
          {showRawJson ? (
            <pre className="text-xs text-zinc-300 font-mono bg-zinc-800 p-3 rounded overflow-x-auto max-h-96 overflow-y-auto border border-zinc-700">
              {JSON.stringify(details, null, 2)}
            </pre>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {Object.entries(details).map(([key, value]) => (
                <div key={key} className="space-y-1">
                  <div className="text-xs text-zinc-500 font-medium">{key.replace(/_/g, " ")}:</div>
                  <div className="ml-2">
                    <SafeObjectRenderer 
                      value={value} 
                      showDebug={true}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
