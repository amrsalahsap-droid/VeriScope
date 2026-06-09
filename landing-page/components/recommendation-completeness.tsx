"use client";

import { AlertCircle, CheckCircle2, AlertTriangle } from "lucide-react";

// Inline Progress component to avoid shadcn dependency
function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <div className={`h-2 w-full bg-zinc-800 rounded-full overflow-hidden ${className}`}>
      <div
        className="h-full bg-zinc-400 transition-all duration-300"
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}

interface CompletenessDimension {
  score: number;
  max: number;
  details: any;
}

interface CompletenessAssessment {
  overall_score: number;
  grade: string;
  dimensions: {
    behavior_coverage: CompletenessDimension;
    journey_coverage: CompletenessDimension;
    scenario_coverage: CompletenessDimension;
    evidence_quality: CompletenessDimension;
    signal_diversity: CompletenessDimension;
  };
  gaps: Array<{
    dimension: string;
    gap: string;
    severity: string;
    suggestion: string;
  }>;
}

interface RecommendationCompletenessProps {
  completeness: CompletenessAssessment | null;
}

export function RecommendationCompleteness({ completeness }: RecommendationCompletenessProps) {
  if (!completeness) {
    return null;
  }

  const { overall_score, grade, dimensions, gaps } = completeness;

  const gradeColors: Record<string, string> = {
    EXCELLENT: "text-emerald-400",
    GOOD: "text-sky-400",
    MODERATE: "text-amber-400",
    WEAK: "text-orange-400",
    INSUFFICIENT: "text-rose-400",
  };

  const gradeIcons: Record<string, any> = {
    EXCELLENT: CheckCircle2,
    GOOD: CheckCircle2,
    MODERATE: AlertTriangle,
    WEAK: AlertTriangle,
    INSUFFICIENT: AlertCircle,
  };

  const GradeIcon = gradeIcons[grade] || AlertCircle;

  return (
    <div className="space-y-6">
      {/* Overall Score */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg bg-zinc-900 border border-zinc-800 ${gradeColors[grade]}`}>
            <GradeIcon className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Completeness Score</h3>
            <p className="text-xs text-zinc-400">Based on behavior, journey, and scenario coverage</p>
          </div>
        </div>
        <div className="text-right">
          <div className={`text-2xl font-bold ${gradeColors[grade]}`}>
            {overall_score.toFixed(1)}
          </div>
          <div className="text-xs text-zinc-500 uppercase tracking-wider">{grade}</div>
        </div>
      </div>

      {/* Dimension Breakdown */}
      <div className="space-y-4">
        {Object.entries(dimensions).map(([key, dim]) => {
          const percentage = (dim.score / dim.max) * 100;
          const label = key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
          
          return (
            <div key={key} className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-300">{label}</span>
                <span className="text-zinc-500">
                  {dim.score.toFixed(1)} / {dim.max}
                </span>
              </div>
              <Progress value={percentage} className="h-2" />
            </div>
          );
        })}
      </div>

      {/* Gaps & Suggestions */}
      {gaps.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Improvement Suggestions
          </h4>
          <div className="space-y-2">
            {gaps.map((gap, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg border ${
                  gap.severity === "HIGH"
                    ? "bg-rose-950/20 border-rose-800/40"
                    : "bg-amber-950/20 border-amber-800/40"
                }`}
              >
                <div className="flex items-start gap-2">
                  <AlertCircle className={`w-4 h-4 mt-0.5 ${
                    gap.severity === "HIGH" ? "text-rose-400" : "text-amber-400"
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-zinc-300">{gap.gap}</p>
                    <p className="text-xs text-zinc-500 mt-1">{gap.suggestion}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
