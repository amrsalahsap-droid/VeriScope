"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, AlertTriangle, Info, ChevronDown, ChevronUp } from "lucide-react";

interface ConfidenceSignal {
  id: string;
  name: string;
  present: boolean;
  impact: "high" | "medium" | "low";
  description?: string;
}

interface ConfidenceExplanationProps {
  type: "recommendation" | "test" | "scenario" | "coverage" | "behavior" | "journey";
  level: "LOW" | "MEDIUM" | "HIGH";
  signals: ConfidenceSignal[];
  explanation: string;
  compact?: boolean;
  className?: string;
}

export default function ConfidenceExplanation({
  type,
  level,
  signals,
  explanation,
  compact = false,
  className = ""
}: ConfidenceExplanationProps) {
  const [expanded, setExpanded] = useState(false);

  const levelConfig = {
    HIGH: {
      color: "text-emerald-400",
      bgColor: "bg-emerald-950/20",
      borderColor: "border-emerald-800/40",
      icon: CheckCircle2,
      label: "High Confidence"
    },
    MEDIUM: {
      color: "text-amber-400",
      bgColor: "bg-amber-950/20",
      borderColor: "border-amber-800/40",
      icon: AlertTriangle,
      label: "Medium Confidence"
    },
    LOW: {
      color: "text-rose-400",
      bgColor: "bg-rose-950/20",
      borderColor: "border-rose-800/40",
      icon: XCircle,
      label: "Low Confidence"
    }
  };

  const config = levelConfig[level];
  const Icon = config.icon;

  const presentSignals = signals.filter(s => s.present);
  const missingSignals = signals.filter(s => !s.present);
  const criticalMissing = missingSignals.filter(s => s.impact === "high");

  if (compact) {
    return (
      <div className={`inline-flex items-center gap-2 ${className}`}>
        <div className={`p-1 rounded ${config.bgColor} ${config.borderColor} border`}>
          <Icon className={`w-3 h-3 ${config.color}`} />
        </div>
        <span className={`text-xs font-medium ${config.color}`}>{config.label}</span>
        {!expanded && criticalMissing.length > 0 && (
          <button
            onClick={() => setExpanded(true)}
            className="text-xs text-zinc-400 hover:text-zinc-300 underline"
          >
            Why?
          </button>
        )}
        {expanded && (
          <div className="absolute z-10 bg-zinc-900 border border-zinc-700 rounded-lg p-3 mt-8 shadow-xl max-w-xs">
            <div className="space-y-2">
              <div className="text-xs font-medium text-zinc-300">{explanation}</div>
              {criticalMissing.length > 0 && (
                <div className="space-y-1">
                  <div className="text-xs font-medium text-rose-400">Missing Critical:</div>
                  {criticalMissing.map(signal => (
                    <div key={signal.id} className="flex items-center gap-1 text-xs text-zinc-400">
                      <XCircle className="w-3 h-3 text-rose-400" />
                      {signal.name}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-4 ${className}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${config.bgColor} ${config.borderColor} border`}>
            <Icon className={`w-4 h-4 ${config.color}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-white">{config.label}</h3>
              <span className="text-xs text-zinc-500 capitalize">{type}</span>
            </div>
            <p className="text-xs text-zinc-300 mt-1">{explanation}</p>
          </div>
        </div>
        
        {(presentSignals.length > 0 || missingSignals.length > 0) && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-zinc-400 hover:text-white transition-colors"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        )}
      </div>

      {expanded && (presentSignals.length > 0 || missingSignals.length > 0) && (
        <div className="mt-4 space-y-3 pt-3 border-t border-zinc-800/50">
          {presentSignals.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                <span className="text-xs font-medium text-zinc-400">
                  Supporting Signals ({presentSignals.length})
                </span>
              </div>
              <div className="space-y-1">
                {presentSignals.map(signal => (
                  <div key={signal.id} className="flex items-center gap-2 text-xs text-zinc-300">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    <span>{signal.name}</span>
                    {signal.impact === "high" && (
                      <span className="text-xs px-1.5 py-0.5 bg-emerald-950/30 text-emerald-400 rounded border border-emerald-800/40">
                        Critical
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {missingSignals.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <XCircle className="w-3 h-3 text-rose-400" />
                <span className="text-xs font-medium text-zinc-400">
                  Missing Signals ({missingSignals.length})
                </span>
              </div>
              <div className="space-y-1">
                {missingSignals.map(signal => (
                  <div key={signal.id} className="flex items-center gap-2 text-xs text-zinc-300">
                    <XCircle className="w-3 h-3 text-rose-400" />
                    <span>{signal.name}</span>
                    {signal.impact === "high" && (
                      <span className="text-xs px-1.5 py-0.5 bg-rose-950/30 text-rose-400 rounded border border-rose-800/40">
                        Critical
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Helper functions to generate confidence explanations for different types

export function generateRecommendationConfidence(run: any): {
  level: "LOW" | "MEDIUM" | "HIGH";
  signals: any[];
  explanation: string;
} {
  const signals = [
    {
      id: "business_intent",
      name: "Business requirements",
      present: run.business_intent && run.business_intent.has_business_intent,
      impact: "high" as const
    },
    {
      id: "test_history",
      name: "Test execution history",
      present: run.evidence.history?.has_flakiness_data,
      impact: "high" as const
    },
    {
      id: "coverage_report",
      name: "Code coverage report",
      present: !!run.evidence.coverage,
      impact: "medium" as const
    },
    {
      id: "current_execution",
      name: "Current PR test execution",
      present: false, // TODO: Check if current PR has test executions
      impact: "medium" as const
    },
    {
      id: "dependency_analysis",
      name: "Dependency analysis",
      present: run.evidence.knowledge_graph?.has_dependencies,
      impact: "low" as const
    }
  ];

  const presentSignals = signals.filter(s => s.present);
  const criticalPresent = presentSignals.filter(s => s.impact === "high").length;
  const criticalMissing = signals.filter(s => !s.present && s.impact === "high").length;

  let level: "LOW" | "MEDIUM" | "HIGH";
  let explanation: string;

  if (criticalPresent >= 2 && criticalMissing === 0) {
    level = "HIGH";
    explanation = "Strong evidence available with comprehensive business context and test history.";
  } else if (criticalPresent >= 1 && criticalMissing <= 1) {
    level = "MEDIUM";
    explanation = "Good evidence available but missing some key signals for full confidence.";
  } else {
    level = "LOW";
    explanation = "Limited evidence available with missing critical signals for reliable recommendations.";
  }

  return { level, signals, explanation };
}

export function generateTestConfidence(test: any, run: any): {
  level: "LOW" | "MEDIUM" | "HIGH";
  signals: any[];
  explanation: string;
} {
  const signals = [
    {
      id: "behavior_match",
      name: "Behavior match found",
      present: !!test.behavior_name,
      impact: "high" as const
    },
    {
      id: "journey_match",
      name: "Journey match found",
      present: !!test.journey_name,
      impact: "high" as const
    },
    {
      id: "recent_execution",
      name: "Recent test execution",
      present: test.last_execution_status && test.last_execution_timestamp,
      impact: "medium" as const
    },
    {
      id: "stable_identity",
      name: "Stable test identity",
      present: !!test.stable_identity,
      impact: "medium" as const
    },
    {
      id: "coverage_link",
      name: "Coverage data linked",
      present: !!test.coverage_data,
      impact: "low" as const
    }
  ];

  const presentSignals = signals.filter(s => s.present);
  const criticalPresent = presentSignals.filter(s => s.impact === "high").length;

  let level: "LOW" | "MEDIUM" | "HIGH";
  let explanation: string;

  if (criticalPresent === 2) {
    level = "HIGH";
    explanation = "Strong behavioral and journey context with stable test identification.";
  } else if (criticalPresent === 1) {
    level = "MEDIUM";
    explanation = "Partial behavioral context available with some confidence factors.";
  } else {
    level = "LOW";
    explanation = "Limited behavioral context with minimal confidence signals.";
  }

  return { level, signals, explanation };
}

export function generateCoverageConfidence(run: any): {
  level: "LOW" | "MEDIUM" | "HIGH";
  signals: any[];
  explanation: string;
} {
  const coverage = run.evidence.coverage;
  const signals = [
    {
      id: "coverage_report",
      name: "Coverage report available",
      present: !!coverage,
      impact: "high" as const
    },
    {
      id: "line_coverage",
      name: "Line coverage data",
      present: !!coverage?.line_coverage_ratio,
      impact: "high" as const
    },
    {
      id: "recent_commit",
      name: "Recent coverage snapshot",
      present: coverage && Date.now() - new Date(coverage.created_at).getTime() < 24 * 60 * 60 * 1000,
      impact: "medium" as const
    },
    {
      id: "branch_coverage",
      name: "Branch coverage data",
      present: !!coverage?.branch_coverage_ratio,
      impact: "low" as const
    }
  ];

  const presentSignals = signals.filter(s => s.present);
  const coverageRatio = coverage?.line_coverage_ratio || 0;

  let level: "LOW" | "MEDIUM" | "HIGH";
  let explanation: string;

  if (presentSignals.length >= 3 && coverageRatio >= 0.8) {
    level = "HIGH";
    explanation = "Comprehensive coverage data with high coverage ratio.";
  } else if (presentSignals.length >= 2 && coverageRatio >= 0.5) {
    level = "MEDIUM";
    explanation = "Adequate coverage data with moderate coverage ratio.";
  } else {
    level = "LOW";
    explanation = "Limited or outdated coverage information.";
  }

  return { level, signals, explanation };
}

export function generateScenarioConfidence(scenario: any, run: any): {
  level: "LOW" | "MEDIUM" | "HIGH";
  signals: any[];
  explanation: string;
} {
  const signals = [
    {
      id: "business_intent",
      name: "Business intent source",
      present: !!scenario.business_intent_id || !!scenario.acceptance_criterion_id,
      impact: "high" as const
    },
    {
      id: "behavior_mapping",
      name: "Behavior mapping",
      present: !!scenario.affected_behavior_id,
      impact: "high" as const
    },
    {
      id: "journey_mapping",
      name: "Journey mapping",
      present: !!scenario.affected_journey_id,
      impact: "medium" as const
    },
    {
      id: "automation_candidate",
      name: "Automation assessment",
      present: scenario.automation_candidate !== undefined,
      impact: "medium" as const
    },
    {
      id: "test_data",
      name: "Test data defined",
      present: scenario.test_data && Object.keys(scenario.test_data).length > 0,
      impact: "low" as const
    }
  ];

  const presentSignals = signals.filter(s => s.present);
  const criticalPresent = presentSignals.filter(s => s.impact === "high").length;

  let level: "LOW" | "MEDIUM" | "HIGH";
  let explanation: string;

  if (criticalPresent === 2) {
    level = "HIGH";
    explanation = "Strong business context with clear behavioral mapping.";
  } else if (criticalPresent === 1) {
    level = "MEDIUM";
    explanation = "Partial business context with some behavioral mapping.";
  } else {
    level = "LOW";
    explanation = "Limited business context with minimal behavioral mapping.";
  }

  return { level, signals, explanation };
}

export function generateBehaviorConfidence(behavior: any, run: any): {
  level: "LOW" | "MEDIUM" | "HIGH";
  signals: any[];
  explanation: string;
} {
  const signals = [
    {
      id: "direct_file_mapping",
      name: "Direct file mapping",
      present: !!behavior.direct_file_match,
      impact: "high" as const
    },
    {
      id: "scenario_coverage",
      name: "Scenario coverage",
      present: behavior.scenarios && behavior.scenarios.length > 0,
      impact: "high" as const
    },
    {
      id: "journey_context",
      name: "Journey context",
      present: !!behavior.journey_name,
      impact: "medium" as const
    },
    {
      id: "test_execution",
      name: "Test execution data",
      present: behavior.scenarios?.some((s: any) => s.current_pr_execution_status === "EXECUTED"),
      impact: "medium" as const
    },
    {
      id: "historical_data",
      name: "Historical performance",
      present: behavior.scenarios?.some((s: any) => s.last_execution_status),
      impact: "low" as const
    }
  ];

  const presentSignals = signals.filter(s => s.present);
  const criticalPresent = presentSignals.filter(s => s.impact === "high").length;

  let level: "LOW" | "MEDIUM" | "HIGH";
  let explanation: string;

  if (criticalPresent === 2) {
    level = "HIGH";
    explanation = "Strong file mapping and scenario coverage evidence.";
  } else if (criticalPresent === 1) {
    level = "MEDIUM";
    explanation = "Partial mapping evidence with some scenario coverage.";
  } else {
    level = "LOW";
    explanation = "Limited mapping evidence with minimal scenario coverage.";
  }

  return { level, signals, explanation };
}

export function generateJourneyConfidence(journey: any, run: any): {
  level: "LOW" | "MEDIUM" | "HIGH";
  signals: any[];
  explanation: string;
} {
  const signals = [
    {
      id: "behavior_coverage",
      name: "Behavior coverage",
      present: journey.behaviors && journey.behaviors.length > 0,
      impact: "high" as const
    },
    {
      id: "scenario_coverage",
      name: "Scenario coverage",
      present: journey.scenarios && journey.scenarios.length > 0,
      impact: "high" as const
    },
    {
      id: "user_journey_mapping",
      name: "User journey mapping",
      present: !!journey.user_journey_steps,
      impact: "medium" as const
    },
    {
      id: "test_execution",
      name: "Test execution data",
      present: journey.scenarios?.some((s: any) => s.current_pr_execution_status === "EXECUTED"),
      impact: "medium" as const
    },
    {
      id: "business_context",
      name: "Business context",
      present: !!journey.business_goal,
      impact: "low" as const
    }
  ];

  const presentSignals = signals.filter(s => s.present);
  const criticalPresent = presentSignals.filter(s => s.impact === "high").length;

  let level: "LOW" | "MEDIUM" | "HIGH";
  let explanation: string;

  if (criticalPresent === 2) {
    level = "HIGH";
    explanation = "Comprehensive behavior and scenario coverage for journey.";
  } else if (criticalPresent === 1) {
    level = "MEDIUM";
    explanation = "Partial coverage with some behavioral or scenario evidence.";
  } else {
    level = "LOW";
    explanation = "Limited coverage evidence for journey assessment.";
  }

  return { level, signals, explanation };
}
