"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, CheckCircle, XCircle, Clock, AlertTriangle, RotateCcw, Plus, Minus, BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";

interface OutcomeSummary {
  status: string;
  feedback: string | null;
  tests: {
    recommended_count: number;
    kept_count: number;
    removed_count: number;
    executed_count: number;
    passed_count: number;
    failed_count: number;
    skipped_count: number;
    not_run_count: number;
  };
  scenarios: {
    suggested_count: number;
    accepted_count: number;
    dismissed_count: number;
    executed_count: number;
    important_count: number;
  };
  overrides: {
    added_tests_count: number;
    removed_tests_count: number;
  };
  defect_escaped: boolean;
  rollback_occurred: boolean;
}

interface OutcomePanelProps {
  outcomeSummary: OutcomeSummary | null;
}

export function OutcomePanel({ outcomeSummary }: OutcomePanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!outcomeSummary) {
    return (
      <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-4">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-zinc-400" />
          <h3 className="text-sm font-medium text-zinc-200">Outcome Status</h3>
        </div>
        <p className="text-xs text-zinc-500 mt-2">Pending review</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-amber-950/20 border border-amber-800/40 rounded-xl p-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-medium text-zinc-200">Outcome Status</h3>
        </div>
        <p className="text-xs text-amber-300 mt-2">Unable to load outcome data. Learning data may be temporarily unavailable.</p>
      </div>
    );
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "ACCEPTED":
        return { label: "Accepted", icon: CheckCircle, color: "text-emerald-400" };
      case "PARTIALLY_ACCEPTED":
        return { label: "Partially accepted", icon: Clock, color: "text-amber-400" };
      case "IGNORED":
        return { label: "Ignored", icon: XCircle, color: "text-rose-400" };
      case "SHOWN":
        return { label: "Pending review", icon: Clock, color: "text-zinc-400" };
      case "NOT_CAPTURED":
        return { label: "Not captured", icon: Clock, color: "text-zinc-400" };
      default:
        return { label: status, icon: Clock, color: "text-zinc-400" };
    }
  };

  const getFeedbackLabel = (feedback: string | null) => {
    if (!feedback) return null;
    switch (feedback) {
      case "USEFUL":
        return { label: "Useful", color: "text-emerald-400" };
      case "NOT_USEFUL":
        return { label: "Not useful", color: "text-rose-400" };
      case "MISSING_TESTS":
        return { label: "Missing tests", color: "text-amber-400" };
      case "TOO_BROAD":
        return { label: "Too broad", color: "text-amber-400" };
      case "TOO_NARROW":
        return { label: "Too narrow", color: "text-amber-400" };
      case "NOT_REVIEWED":
        return { label: "Not reviewed", color: "text-zinc-400" };
      default:
        return { label: feedback, color: "text-zinc-400" };
    }
  };

  const statusInfo = getStatusLabel(outcomeSummary.status);
  const feedbackInfo = getFeedbackLabel(outcomeSummary.feedback);
  const StatusIcon = statusInfo.icon;

  const hasLearning = outcomeSummary.status !== "NOT_CAPTURED" && outcomeSummary.status !== "SHOWN";
  const hasPostMergeIssues = outcomeSummary.defect_escaped || outcomeSummary.rollback_occurred;

  return (
    <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusIcon className={`w-4 h-4 ${statusInfo.color}`} />
          <h3 className="text-sm font-medium text-zinc-200">Outcome Status</h3>
        </div>
        <div className="flex items-center gap-2">
          {hasLearning && (
            <span className="text-xs text-emerald-400 flex items-center gap-1">
              <CheckCircle className="w-3 h-3" />
              Learning captured
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="h-6 w-6 p-0"
          >
            {isExpanded ? (
              <ChevronUp className="w-4 h-4 text-zinc-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-zinc-400" />
            )}
          </Button>
        </div>
      </div>

      <div className="mt-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className={`text-xs ${statusInfo.color}`}>{statusInfo.label}</span>
          {feedbackInfo && (
            <span className={`text-xs ${feedbackInfo.color}`}>{feedbackInfo.label}</span>
          )}
        </div>

        {isExpanded && (
          <div className="space-y-3 pt-3 border-t border-zinc-800/50">
            {/* Test Execution Status */}
            <div>
              <p className="text-xs text-zinc-400 mb-2">Test Execution</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  <span className="text-zinc-300">Passed: {outcomeSummary.tests.passed_count}</span>
                </div>
                <div className="flex items-center gap-2">
                  <XCircle className="w-3 h-3 text-rose-400" />
                  <span className="text-zinc-300">Failed: {outcomeSummary.tests.failed_count}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="w-3 h-3 text-zinc-400" />
                  <span className="text-zinc-300">Not run: {outcomeSummary.tests.not_run_count}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="w-3 h-3 text-zinc-400" />
                  <span className="text-zinc-300">Skipped: {outcomeSummary.tests.skipped_count}</span>
                </div>
              </div>
            </div>

            {/* Test Decisions */}
            <div>
              <p className="text-xs text-zinc-400 mb-2">Test Decisions</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  <span className="text-zinc-300">Kept: {outcomeSummary.tests.kept_count}</span>
                </div>
                <div className="flex items-center gap-2">
                  <XCircle className="w-3 h-3 text-rose-400" />
                  <span className="text-zinc-300">Removed: {outcomeSummary.tests.removed_count}</span>
                </div>
              </div>
            </div>

            {/* Overrides */}
            {(outcomeSummary.overrides.added_tests_count > 0 || outcomeSummary.overrides.removed_tests_count > 0) && (
              <div>
                <p className="text-xs text-zinc-400 mb-2">Manual Overrides</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {outcomeSummary.overrides.added_tests_count > 0 && (
                    <div className="flex items-center gap-2">
                      <Plus className="w-3 h-3 text-blue-400" />
                      <span className="text-zinc-300">Added: {outcomeSummary.overrides.added_tests_count}</span>
                    </div>
                  )}
                  {outcomeSummary.overrides.removed_tests_count > 0 && (
                    <div className="flex items-center gap-2">
                      <Minus className="w-3 h-3 text-rose-400" />
                      <span className="text-zinc-300">Removed: {outcomeSummary.overrides.removed_tests_count}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Scenario Decisions */}
            {outcomeSummary.scenarios.suggested_count > 0 && (
              <div>
                <p className="text-xs text-zinc-400 mb-2">Scenario Decisions</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-3 h-3 text-emerald-400" />
                    <span className="text-zinc-300">Accepted: {outcomeSummary.scenarios.accepted_count}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <XCircle className="w-3 h-3 text-rose-400" />
                    <span className="text-zinc-300">Dismissed: {outcomeSummary.scenarios.dismissed_count}</span>
                  </div>
                  {outcomeSummary.scenarios.important_count > 0 && (
                    <div className="flex items-center gap-2">
                      <BookOpen className="w-3 h-3 text-amber-400" />
                      <span className="text-zinc-300">Important: {outcomeSummary.scenarios.important_count}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Post-Merge Outcome */}
            {hasPostMergeIssues && (
              <div className="bg-rose-950/30 border border-rose-800/30 rounded-lg p-3">
                <p className="text-xs text-rose-400 mb-2">Post-Merge Issues</p>
                <div className="space-y-1 text-xs">
                  {outcomeSummary.defect_escaped && (
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-3 h-3 text-rose-400" />
                      <span className="text-zinc-300">Defect escaped to production</span>
                    </div>
                  )}
                  {outcomeSummary.rollback_occurred && (
                    <div className="flex items-center gap-2">
                      <RotateCcw className="w-3 h-3 text-amber-400" />
                      <span className="text-zinc-300">Rollback occurred</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
