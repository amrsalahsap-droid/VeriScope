import React from "react";
import { AlertTriangle } from "lucide-react";
import { RegressionScopeExecutionPlan } from "../../types/regression-scope-v2";

export type ExecutionPlanDisplayProps = {
  executionPlan: RegressionScopeExecutionPlan;
  compact?: boolean;
};

export const ExecutionPlanDisplay: React.FC<ExecutionPlanDisplayProps> = ({
  executionPlan,
  compact = false,
}) => {
  const {
    required_count,
    recommended_count,
    optional_count,
    safe_to_skip_count,
    total_executable_count,
    estimated_execution_reduction,
    confidence_level,
    plan_summary,
    advisory_notice,
  } = executionPlan;

  const MetricCard = ({
    label,
    value,
    colorClass,
    bgClass,
    borderClass,
  }: {
    label: string;
    value: number;
    colorClass: string;
    bgClass: string;
    borderClass: string;
  }) => (
    <div className={`p-3 rounded-xl border ${bgClass} ${borderClass} flex flex-col justify-between`}>
      <span className="text-[10px] text-zinc-500 font-medium tracking-wider uppercase">{label}</span>
      <span className={`text-xl font-bold mt-1 ${colorClass}`}>{value}</span>
    </div>
  );

  return (
    <div className={`space-y-4 ${compact ? "p-0" : "bg-zinc-900/10 border border-zinc-800/80 rounded-xl p-5"}`}>
      {/* Summary Headline */}
      {!compact && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-zinc-800/50">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-zinc-200">Execution Plan</h3>
            <p className="text-xs text-zinc-450 leading-snug">{plan_summary}</p>
          </div>
          <div className="shrink-0 flex items-center gap-3">
            <div className="text-right">
              <span className="text-[10px] text-zinc-500 block uppercase tracking-wider">Confidence</span>
              <span className="text-xs font-bold text-emerald-400">{(confidence_level ?? 0).toFixed(0)}%</span>
            </div>
            <div className="text-right border-l border-zinc-800/60 pl-3">
              <span className="text-[10px] text-zinc-500 block uppercase tracking-wider">Time Saved</span>
              <span className="text-xs font-bold text-purple-400">{(estimated_execution_reduction ?? 0).toFixed(0)}%</span>
            </div>
          </div>
        </div>
      )}

      {/* Grid of Counts */}
      <div className={`grid gap-3 ${compact ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-5"}`}>
        <MetricCard
          label="Required"
          value={required_count}
          colorClass="text-rose-450"
          bgClass="bg-rose-950/10"
          borderClass="border-rose-900/30"
        />
        <MetricCard
          label="Recommended"
          value={recommended_count}
          colorClass="text-amber-450"
          bgClass="bg-amber-950/10"
          borderClass="border-amber-900/30"
        />
        <MetricCard
          label="Optional"
          value={optional_count}
          colorClass="text-zinc-300"
          bgClass="bg-zinc-900/10"
          borderClass="border-zinc-800/30"
        />
        <MetricCard
          label="Safe to Skip"
          value={safe_to_skip_count}
          colorClass="text-blue-400"
          bgClass="bg-blue-950/10"
          borderClass="border-blue-900/30"
        />
        <MetricCard
          label="Total Executable"
          value={total_executable_count}
          colorClass="text-purple-400"
          bgClass="bg-purple-950/10"
          borderClass="border-purple-900/30"
        />
      </div>

      {compact && plan_summary && (
        <div className="p-3 bg-zinc-900/40 border border-zinc-800 rounded-lg text-xs text-zinc-400 leading-snug">
          <strong>Summary:</strong> {plan_summary}
        </div>
      )}

      {/* Advisory Notice */}
      {advisory_notice && (
        <div className="p-3 rounded-lg bg-zinc-950/40 border border-zinc-800/60 flex items-start gap-2.5">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
          <div className="text-[11px] text-zinc-450 leading-relaxed font-sans">
            {advisory_notice}
          </div>
        </div>
      )}
    </div>
  );
};
export default ExecutionPlanDisplay;
