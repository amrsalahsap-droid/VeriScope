"use client";

import type { CompletenessScoreOutput } from "@/lib/completeness-score";
import { CheckCircle2, AlertTriangle, XCircle, TrendingUp, Lightbulb } from "lucide-react";

interface CompletenessScoreProps {
  score: CompletenessScoreOutput;
}

export function CompletenessScore({ score }: CompletenessScoreProps) {
  const levelConfig = {
    GOOD: {
      icon: CheckCircle2,
      color: "text-emerald-400",
      bg: "bg-emerald-950/30",
      border: "border-emerald-500/20",
      progress: "bg-emerald-400"
    },
    PARTIAL: {
      icon: AlertTriangle,
      color: "text-amber-400",
      bg: "bg-amber-950/30",
      border: "border-amber-500/20",
      progress: "bg-amber-400"
    },
    LOW: {
      icon: XCircle,
      color: "text-rose-400",
      bg: "bg-rose-950/30",
      border: "border-rose-500/20",
      progress: "bg-rose-400"
    }
  };

  const config = levelConfig[score.level];
  const Icon = config.icon;

  return (
    <div className={`bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-5`}>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${config.bg} ${config.border} border`}>
            <Icon className={`w-5 h-5 ${config.color}`} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-100">Intelligence Completeness</h3>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-lg font-bold ${config.color}`}>{score.score}%</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded ${config.bg} ${config.color} ${config.border} border`}>
                {score.level}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
          <div 
            className={`h-full ${config.progress} transition-all duration-500`}
            style={{ width: `${score.score}%` }}
          />
        </div>
      </div>

      {/* Explanation */}
      <div className="mb-4">
        <div className="space-y-3">
          <p className="text-xs text-zinc-300 leading-relaxed">
            {score.level === "GOOD" 
              ? "Veriscope has comprehensive intelligence to generate a precise recommendation with high confidence."
              : score.level === "PARTIAL"
              ? "Veriscope has enough evidence to generate a useful recommendation, but several optional intelligence sources are missing. Adding acceptance criteria, current PR execution, and outcome history would improve precision."
              : "Veriscope has limited intelligence for this recommendation. Adding business requirements, test history, and coverage data would significantly improve recommendation quality."
            }
          </p>
          
          {/* Available Signal Contribution */}
          <div className="bg-zinc-800/40 rounded-lg p-3 border border-zinc-700/50">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span className="text-xs font-medium text-zinc-300">Available Intelligence</span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between items-center">
                <span className="text-xs text-zinc-400">Code changes & coverage</span>
                <span className="text-xs text-emerald-400 font-medium">+{Math.round(score.score * 0.4)}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-zinc-400">Existing tests</span>
                <span className="text-xs text-emerald-400 font-medium">+{Math.round(score.score * 0.3)}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-zinc-400">Test history</span>
                <span className="text-xs text-emerald-400 font-medium">+{Math.round(score.score * 0.2)}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-zinc-400">Dependencies</span>
                <span className="text-xs text-emerald-400 font-medium">+{Math.round(score.score * 0.1)}%</span>
              </div>
            </div>
          </div>
          
          {/* Missing Signal Impact */}
          {score.level !== "GOOD" && (
            <div className="bg-zinc-800/40 rounded-lg p-3 border border-zinc-700/50">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-3 h-3 text-amber-400" />
                <span className="text-xs font-medium text-zinc-300">Missing Intelligence Impact</span>
              </div>
              <div className="space-y-1">
                {score.level === "LOW" && (
                  <>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-zinc-400">Acceptance criteria</span>
                      <span className="text-xs text-amber-400 font-medium">+15%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-zinc-400">Current PR execution</span>
                      <span className="text-xs text-amber-400 font-medium">+12%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-zinc-400">Historical outcomes</span>
                      <span className="text-xs text-amber-400 font-medium">+10%</span>
                    </div>
                  </>
                )}
                {score.level === "PARTIAL" && (
                  <>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-zinc-400">Business requirements</span>
                      <span className="text-xs text-amber-400 font-medium">+8%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-zinc-400">Manual test cases</span>
                      <span className="text-xs text-amber-400 font-medium">+5%</span>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* How to Improve */}
      <div className={`pt-4 border-t border-zinc-800/50`}>
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb className="w-4 h-4 text-zinc-500" />
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
            How to Improve Intelligence
          </span>
        </div>
        <div className="space-y-2">
          {score.level === "GOOD" && (
            <div className="flex items-start gap-2 text-xs text-emerald-400">
              <CheckCircle2 className="w-3 h-3 shrink-0 mt-0.5" />
              <span>Excellent intelligence coverage! Continue maintaining test execution and documentation.</span>
            </div>
          )}
          {score.level === "PARTIAL" && (
            <>
              <div className="flex items-start gap-2 text-xs text-zinc-400">
                <TrendingUp className="w-3 h-3 shrink-0 mt-0.5" />
                <span>Add business requirements or acceptance criteria to improve recommendation precision</span>
              </div>
              <div className="flex items-start gap-2 text-xs text-zinc-400">
                <TrendingUp className="w-3 h-3 shrink-0 mt-0.5" />
                <span>Execute current tests on this PR to provide execution feedback</span>
              </div>
              <div className="flex items-start gap-2 text-xs text-zinc-400">
                <TrendingUp className="w-3 h-3 shrink-0 mt-0.5" />
                <span>Link to Jira/Azure work items for additional business context</span>
              </div>
            </>
          )}
          {score.level === "LOW" && (
            <>
              <div className="flex items-start gap-2 text-xs text-zinc-400">
                <TrendingUp className="w-3 h-3 shrink-0 mt-0.5" />
                <span>Add acceptance criteria to clarify business requirements and expected behavior</span>
              </div>
              <div className="flex items-start gap-2 text-xs text-zinc-400">
                <TrendingUp className="w-3 h-3 shrink-0 mt-0.5" />
                <span>Ensure code coverage is available for the changed files</span>
              </div>
              <div className="flex items-start gap-2 text-xs text-zinc-400">
                <TrendingUp className="w-3 h-3 shrink-0 mt-0.5" />
                <span>Run existing tests to provide execution history and flakiness data</span>
              </div>
              <div className="flex items-start gap-2 text-xs text-zinc-400">
                <TrendingUp className="w-3 h-3 shrink-0 mt-0.5" />
                <span>Add manual test cases for scenarios that require human validation</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
