import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { 
  CheckCircle2, 
  Circle, 
  AlertTriangle, 
  Sparkles,
  BarChart2,
  GitPullRequest,
  FileText,
  Link2,
  Users,
  Play,
  RefreshCw,
  ExternalLink
} from "lucide-react";

interface AvailableSignal {
  key: string;
  label: string;
  status: "AVAILABLE" | "MISSING";
  impact: string;
  confidence_contribution: number;
  explanation?: string;
}

interface MissingSignal {
  key: string;
  label: string;
  severity: "REQUIRED" | "RECOMMENDED" | "OPTIONAL";
  impact: string;
  estimated_confidence_gain: number;
  actions: string[];
  explanation?: string;
}

interface RecommendedAction {
  action: string;
  label: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  estimated_confidence_gain: number;
}

interface ReadinessData {
  readiness_level: string;
  expected_confidence: string;
  readiness_score: number;
  can_generate: boolean;
  available_inputs: AvailableSignal[];
  missing_inputs: MissingSignal[];
  next_best_actions?: RecommendedAction[];
  intelligence_completeness_score?: number;
  release_confidence_ceiling?: string;
  primary_message?: string;
  secondary_message?: string;
  confidence_reason?: string;
  confidence_ceiling?: string;
  confidence_blockers?: string[];
  confidence_limiters?: AvailableSignal[];
}

interface RecommendationReadinessPanelProps {
  repositoryId: string;
  repositoryName: string;
  repositoryStatus: string;
  pullRequestId?: string; // Optional: if provided, fetch PR-level readiness
  refreshTrigger?: number; // Increment this to trigger refresh
  onReadinessDataChange?: (data: ReadinessData | null) => void; // Callback to pass readiness data to parent
}

export default function RecommendationReadinessPanel({ 
  repositoryId, 
  repositoryName, 
  repositoryStatus,
  pullRequestId,
  refreshTrigger,
  onReadinessDataChange
}: RecommendationReadinessPanelProps) {
  const { data: session } = useSession();
  const [readinessData, setReadinessData] = useState<ReadinessData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandAvailable, setExpandAvailable] = useState(false);
  const [expandMissing, setExpandMissing] = useState(false);

  // Pass readiness data to parent when it changes
  useEffect(() => {
    if (onReadinessDataChange) {
      onReadinessDataChange(readinessData);
    }
  }, [readinessData, onReadinessDataChange]);

  const fallbackLabels: Record<string, string> = {
    source_code: "Source Code",
    pull_request_diff: "PR Diff",
    architecture_graph: "Architecture Graph",
    behavior_catalog: "Behavior Catalog",
    journey_catalog: "Journey Catalog",
    test_history: "Test History",
    junit_test_history: "Test History",
    coverage_report: "Coverage Report",
    current_pr_coverage: "Current PR Coverage",
    acceptance_criteria: "Acceptance Criteria",
    business_intent: "Business Intent",
    linked_work_item: "Linked Work Item",
    historical_outcomes: "Historical Outcomes",
    fragility_memory: "Fragility Memory",
    current_pr_execution: "Current PR Test Results",
  };

  const fallbackDescriptions: Record<string, string> = {
    source_code: "Analyze repository source code structure.",
    pull_request_diff: "Analyze changes introduced in the pull request.",
    architecture_graph: "Map architectural dependencies and boundaries.",
    behavior_catalog: "Track codebase behavior discoveries.",
    journey_catalog: "Validate key user journeys.",
    test_history: "History of automated test runs.",
    junit_test_history: "History of automated test runs.",
    current_pr_execution: "Test results verified on the current PR branch.",
    coverage_report: "Historical code coverage protection.",
    current_pr_coverage: "Code coverage changes on the current PR.",
    acceptance_criteria: "Verify acceptance criteria for requirement coverage.",
    business_intent: "Identify business intents and user stories.",
    linked_work_item: "Associate the PR with a tracking ticket or work item.",
    historical_outcomes: "Learn from historical recommendation outcomes.",
    fragility_memory: "Track areas historically fragile or prone to regression.",
  };

  const groups = [
    {
      name: "Required Analysis",
      keys: ["source_code", "pull_request_diff"],
    },
    {
      name: "Repository Intelligence",
      keys: ["architecture_graph", "behavior_catalog", "journey_catalog"],
    },
    {
      name: "Testing Evidence",
      keys: ["test_history", "current_pr_execution", "coverage_report", "current_pr_coverage"],
    },
    {
      name: "Business Context",
      keys: ["acceptance_criteria", "business_intent", "linked_work_item"],
    },
    {
      name: "Learning Signals",
      keys: ["historical_outcomes", "fragility_memory"],
    }
  ];

  const statusBadgeMap: Record<string, { label: string; styling: string }> = {
    BLOCKED: {
      label: "Blocked",
      styling: "bg-rose-950/20 text-rose-400 border-rose-800/30",
    },
    MINIMUM_READY: {
      label: "Minimum Ready",
      styling: "bg-zinc-800/50 text-zinc-400 border-zinc-700/50",
    },
    LIMITED_EVIDENCE: {
      label: "Limited Evidence",
      styling: "bg-amber-950/20 text-amber-400 border-amber-800/30",
    },
    EVIDENCE_READY: {
      label: "Evidence Ready",
      styling: "bg-amber-950/20 text-amber-400 border-amber-800/30",
    },
    REGRESSION_READY: {
      label: "Regression Ready",
      styling: "bg-emerald-950/20 text-emerald-400 border-emerald-800/30",
    },
    HIGH_CONFIDENCE: {
      label: "High Confidence Ready",
      styling: "bg-emerald-950/20 text-emerald-400 border-emerald-800/30",
    },
    UNKNOWN: {
      label: "Unknown",
      styling: "bg-zinc-850 text-zinc-400 border-zinc-700/50",
    }
  };

  const getMergedStatus = (): string => {
    if (!readinessData) return "UNKNOWN";
    
    const availableKeys = new Set(
      (readinessData.available_inputs || []).map(s => s.key)
    );
    
    const hasSource = availableKeys.has("source_code");
    const hasDiff = availableKeys.has("pull_request_diff");
    const hasArch = availableKeys.has("architecture_graph");
    const hasBehavior = availableKeys.has("behavior_catalog");
    const hasJourney = availableKeys.has("journey_catalog");
    const hasTests = availableKeys.has("test_history") || availableKeys.has("junit_test_history");
    const hasCoverage = availableKeys.has("coverage_report") || availableKeys.has("current_pr_coverage");
    const hasAc = availableKeys.has("acceptance_criteria");
    const hasExecution = availableKeys.has("current_pr_execution");

    if (!hasSource || !hasDiff) {
      return "BLOCKED";
    }

    const isRegressionReady = hasSource && hasDiff && hasArch && hasBehavior && hasJourney && hasTests && hasCoverage;

    if (isRegressionReady && hasAc && hasExecution) {
      return "HIGH_CONFIDENCE";
    }

    if (isRegressionReady) {
      return "REGRESSION_READY";
    }

    if (hasSource && hasDiff && (hasTests || hasCoverage)) {
      return "EVIDENCE_READY";
    }

    const otherSignalsCount = (hasArch ? 1 : 0) + (hasBehavior ? 1 : 0) + (hasJourney ? 1 : 0) + (hasAc ? 1 : 0) + (hasExecution ? 1 : 0);
    if (otherSignalsCount === 0 && !hasTests && !hasCoverage) {
      return "MINIMUM_READY";
    }

    return "LIMITED_EVIDENCE";
  };

  const getSignalInfo = (key: string): { signal: AvailableSignal | MissingSignal | null; isAvailable: boolean } | null => {
    if (!readinessData) return null;

    let signal: AvailableSignal | MissingSignal | null = (readinessData.available_inputs || []).find(
      s => s.key === key || (key === "test_history" && s.key === "junit_test_history")
    ) || null;
    let isAvailable = true;

    if (!signal) {
      signal = (readinessData.missing_inputs || []).find(
        s => s.key === key || (key === "test_history" && s.key === "junit_test_history")
      ) || null;
      isAvailable = false;
    }

    return { signal, isAvailable };
  };


  useEffect(() => {
    fetchReadinessData();
  }, [repositoryId, pullRequestId, refreshTrigger, session?.backendToken]);

  const fetchReadinessData = async () => {
    try {
      setLoading(true);
      setError(null);
      // Use PR-level endpoint if pullRequestId is provided, otherwise use repository-level
      const url = pullRequestId 
        ? `/api/readiness/repositories/${repositoryId}/pull-requests/${pullRequestId}`
        : `/api/readiness/repositories/${repositoryId}`;
      
      const headers: HeadersInit = {};
      if (session?.backendToken) {
        headers["Authorization"] = `Bearer ${session.backendToken}`;
      }

      const response = await fetch(url, { headers, cache: "no-store" });
      
      if (!response.ok) {
        if (response.status === 401) {
          // User not authenticated, don't show error
          return;
        }
        throw new Error(`Failed to fetch readiness data: ${response.status}`);
      }
      
      const data = await response.json();
      setReadinessData(data);
    } catch (err) {
      console.error("Error fetching readiness data:", err);
      setError(err instanceof Error ? err.message : "Failed to load readiness data");
    } finally {
      setLoading(false);
    }
  };

  const getReadinessLevelColor = (level: string) => {
    switch (level) {
      case "HIGH_CONFIDENCE_READY":
      case "RECOMMENDATION_READY":
        return "bg-emerald-950/20 text-emerald-400 border-emerald-800/30";
      case "EVIDENCE_READY":
      case "PARTIAL":
        return "bg-amber-950/20 text-amber-400 border-amber-800/30";
      case "CONNECTED":
        return "bg-zinc-800/50 text-zinc-400 border-zinc-700/50";
      case "BLOCKED":
        return "bg-rose-950/20 text-rose-400 border-rose-800/30";
      default:
        return "bg-zinc-800/50 text-zinc-400 border-zinc-700/50";
    }
  };

  const getConfidenceColor = (confidence: string) => {
    switch (confidence) {
      case "HIGH":
        return "bg-emerald-500/20 text-emerald-400";
      case "MEDIUM":
        return "bg-amber-500/20 text-amber-400";
      case "LOW":
        return "bg-rose-500/20 text-rose-400";
      default:
        return "bg-zinc-500/20 text-zinc-400";
    }
  };

  const formatPercentage = (value: number): string => {
    if (value === undefined || value === null || isNaN(value)) return "0%";
    let percent = value;
    if (value < 1) {
      percent = value * 100;
    }
    percent = Math.min(100, Math.max(0, percent));
    return `${Math.round(percent)}%`;
  };


  const getConciseReason = () => {
    if (!readinessData) return "Loading readiness assessment...";
    
    if (readinessData.readiness_level === "BLOCKED" || !readinessData.can_generate) {
      const requiredMissing = readinessData.missing_inputs?.filter(s => s.severity === "REQUIRED") || [];
      if (requiredMissing.length > 0) {
        return "Required inputs missing for generation.";
      }
      return "Required signals are missing for recommendation generation.";
    }
    
    if (readinessData.readiness_level === "PARTIAL" || readinessData.expected_confidence === "LOW") {
      return "Some recommended signals are missing, affecting confidence.";
    }
    
    return "Repository is ready for recommendation generation.";
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "HIGH":
        return "bg-rose-500/20 text-rose-400 border-rose-800/30";
      case "MEDIUM":
        return "bg-amber-500/20 text-amber-400 border-amber-800/30";
      case "LOW":
        return "bg-zinc-500/20 text-zinc-400 border-zinc-800/30";
      default:
        return "bg-zinc-500/20 text-zinc-400 border-zinc-800/30";
    }
  };

  const getSignalLabel = (key: string, apiLabel?: string): string => {
    if (apiLabel) return apiLabel;
    
    const labelMap: Record<string, string> = {
      source_code: "Source Code",
      pull_request_diff: "PR Diff",
      architecture_graph: "Architecture Graph",
      behavior_catalog: "Behavior Catalog",
      journey_catalog: "Journey Catalog",
      junit_test_history: "Test History",
      test_history: "Test History",
      coverage_report: "Coverage Report",
      current_pr_coverage: "Current PR Coverage",
      acceptance_criteria: "Acceptance Criteria",
      business_intent: "Business Intent",
      manual_test_cases: "Manual Test Cases",
      managed_manual_tests: "Manual Test Cases",
      linked_work_item: "Linked Work Item",
      historical_outcomes: "Historical Outcomes",
      fragility_memory: "Fragility Memory",
      current_pr_execution: "Current PR Test Results",
      github_connection: "GitHub Connection",
      webhook_activity: "Webhook Activity"
    };
    
    return labelMap[key] || key.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
  };

  if (loading) {
    return (
      <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
        <div className="animate-pulse">
          <div className="h-6 w-32 bg-zinc-800 rounded mb-4"></div>
          <div className="space-y-3">
            <div className="h-4 w-48 bg-zinc-800 rounded"></div>
            <div className="h-4 w-40 bg-zinc-800 rounded"></div>
            <div className="h-4 w-36 bg-zinc-800 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
        <div className="text-center">
          <AlertTriangle className="w-8 h-8 text-zinc-500 mx-auto mb-3" />
          <h3 className="text-sm font-medium text-zinc-300 mb-2">Readiness Assessment Unavailable</h3>
          <p className="text-xs text-zinc-500 mb-4">
            {error}
          </p>
          <Button variant="ghost" size="sm" onClick={fetchReadinessData} aria-label="Retry loading readiness data">
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (!readinessData) {
    return (
      <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
        <div className="text-center">
          <AlertTriangle className="w-8 h-8 text-zinc-500 mx-auto mb-3" />
          <h3 className="text-sm font-medium text-zinc-300 mb-2">Readiness data unavailable</h3>
          <p className="text-xs text-zinc-500 mb-4">
            Could not load readiness data from the server.
          </p>
          <Button variant="ghost" size="sm" onClick={fetchReadinessData} aria-label="Retry loading readiness data">
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const mergedStatus = getMergedStatus();
  const badgeInfo = statusBadgeMap[mergedStatus] || statusBadgeMap.UNKNOWN;

  // Get title and subtitle based on context
  const getReadinessTitle = () => {
    if (pullRequestId) {
      return "PR Recommendation Readiness";
    }
    return "Repository Baseline Readiness";
  };

  const getReadinessSubtitle = () => {
    if (pullRequestId) {
      return "Readiness for selected pull request";
    }
    return "Repository-level intelligence used before selecting a pull request";
  };

  // Backend inconsistency handling
  const checkInconsistencies = (): string[] => {
    const warnings: string[] = [];

    if (!readinessData) return warnings;

    // Check 1: BLOCKED status but no blockers
    if (readinessData.readiness_level === "BLOCKED" && (!readinessData.confidence_blockers || readinessData.confidence_blockers.length === 0)) {
      warnings.push("Backend returned blocked status without blockers.");
    }

    // Check 2: Duplicate signals in both available and missing
    const availableKeys = new Set((readinessData.available_inputs || []).map(s => s.key));
    const missingKeys = new Set((readinessData.missing_inputs || []).map(s => s.key));
    const duplicates = [...availableKeys].filter(key => missingKeys.has(key));
    if (duplicates.length > 0) {
      warnings.push(`Duplicate signals in available and missing: ${duplicates.join(", ")}`);
    }

    return warnings;
  };

  const inconsistencies = checkInconsistencies();

  // Log warnings in development
  if (inconsistencies.length > 0 && process.env.NODE_ENV === "development") {
    console.warn("Readiness data inconsistencies:", inconsistencies);
  }

  const getCanGenerateState = (): string => {
    if (!readinessData) return "Unknown";
    if (!readinessData.can_generate) return "No";
    if (readinessData.expected_confidence === "HIGH") return "Yes";
    return "Yes, with reduced confidence";
  };

  return (
    <div className="space-y-4">
      {/* Inconsistency Warning */}
      {inconsistencies.length > 0 && (
        <div className="px-3 py-2 rounded-lg bg-amber-950/20 border border-amber-800/40 text-xs text-amber-400">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <div>
              <div className="font-medium mb-1">Readiness data inconsistent</div>
              <ul className="list-disc list-inside space-y-0.5 text-zinc-400">
                {inconsistencies.map((warning, idx) => (
                  <li key={idx}>{warning}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Regression Intelligence Readiness Panel */}
      <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-medium text-zinc-300">{getReadinessTitle()}</h3>
            <p className="text-xs text-zinc-500 mt-0.5">{getReadinessSubtitle()}</p>
          </div>
          <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${badgeInfo.styling}`}>
            {badgeInfo.label}
          </span>
        </div>

        <div className="grid grid-cols-4 gap-4 mb-4">
          <div>
            <div className="text-xs text-zinc-500 mb-1">Status</div>
            <div className="text-sm font-medium text-white">{badgeInfo.label}</div>
          </div>
          <div>
            <div className="text-xs text-zinc-500 mb-1">Score</div>
            <div className="text-2xl font-bold text-white">{formatPercentage(readinessData.readiness_score)}</div>
          </div>
          <div>
            <div className="text-xs text-zinc-500 mb-1">Confidence</div>
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getConfidenceColor(readinessData.expected_confidence)}`}>
                {readinessData.expected_confidence}
              </span>
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-500 mb-1">Can generate</div>
            <div className="text-sm font-medium text-white">{getCanGenerateState()}</div>
          </div>
        </div>

        {/* Clean summary area */}
        <div className="space-y-3 mb-4 pt-3 border-t border-zinc-800/40">
          {/* Blockers */}
          {readinessData.confidence_blockers && readinessData.confidence_blockers.length > 0 && (
            <div>
              <div className="text-xs font-medium text-rose-400 mb-2">Blocking issue:</div>
              <ul className="space-y-1">
                {readinessData.confidence_blockers.map((blocker, idx) => (
                  <li key={idx} className="text-xs text-zinc-300 flex items-start gap-2">
                    <span className="text-rose-400 mt-0.5">✕</span>
                    <span>{blocker === 'source_code' ? 'Source Code' : blocker === 'pull_request_diff' ? 'PR Diff' : blocker}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Confidence limiters - only show if not blocked */}
          {(!readinessData.confidence_blockers || readinessData.confidence_blockers.length === 0) && (
            <>
              {readinessData.confidence_limiters && readinessData.confidence_limiters.length > 0 ? (
                <div>
                  <div className="text-xs font-medium text-amber-400 mb-2">Confidence is capped because:</div>
                  <ul className="space-y-1">
                    {readinessData.confidence_limiters.map((limiter, idx) => (
                      <li key={idx} className="text-xs text-zinc-300 flex items-start gap-2">
                        <span className="text-amber-400 mt-0.5">○</span>
                        <span>{limiter.label || limiter.key}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="text-xs text-zinc-400">
                  Ready to generate with {readinessData.expected_confidence} confidence.
                </div>
              )}
            </>
          )}

          {/* Confidence will improve with - only show if blocked */}
          {readinessData.confidence_blockers && readinessData.confidence_blockers.length > 0 && (
            <div>
              <div className="text-xs font-medium text-zinc-500 mb-2">Confidence will improve with:</div>
              <ul className="space-y-1">
                {(readinessData.missing_inputs || []).slice(0, 5).map((input, idx) => (
                  <li key={idx} className="text-xs text-zinc-400 flex items-start gap-2">
                    <span className="text-zinc-500 mt-0.5">○</span>
                    <span>{input.label || input.key}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Signal Counts */}
        <div className="flex items-center gap-4 text-xs pt-2 border-t border-zinc-800/40">
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-zinc-400">{readinessData.available_inputs?.length || 0} available</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Circle className="w-3.5 h-3.5 text-zinc-500" />
            <span className="text-zinc-400">{readinessData.missing_inputs?.length || 0} missing</span>
          </div>
        </div>

        {/* Collapsed Signal Groups */}
        <div className="pt-4 border-t border-zinc-800/40">
          {groups.map((group) => {
            const availableCount = group.keys.filter(key => {
              const info = getSignalInfo(key);
              return info && info.isAvailable;
            }).length;
            const totalCount = group.keys.length;

            return (
              <div key={group.name} className="mb-3 last:mb-0">
                <button
                  onClick={() => {
                    // Toggle expansion for this group
                    const key = `group-${group.name}`;
                    const current = (window as any)[key] || false;
                    (window as any)[key] = !current;
                    // Force re-render by updating state
                    setReadinessData({ ...readinessData });
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 bg-zinc-800/30 border border-zinc-700/50 rounded-lg hover:bg-zinc-800/50 transition-colors"
                >
                  <span className="text-xs font-medium text-zinc-300">{group.name}</span>
                  <span className="text-xs text-zinc-500">{availableCount}/{totalCount} ready</span>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Expanded Signal Groups (conditionally rendered) */}
      <div className="space-y-4">
        {groups.map((group) => {
          const key = `group-${group.name}`;
          const isExpanded = (window as any)[key] || false;

          if (!isExpanded) return null;

          return (
            <div key={group.name} className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-4">
              <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-3">
                {group.name}
              </h4>
              <div className="space-y-2">
                {group.keys.map((key) => {
                  const info = getSignalInfo(key);
                  const isAvailable = info ? info.isAvailable : false;
                  const signal = info ? info.signal : null;

                  const label = getSignalLabel(key, signal?.label);
                  if (!label || label.trim() === "") return null; // Never render rows without labels

                  const description = signal?.explanation || signal?.impact || fallbackDescriptions[key] || "";
                  const severity = (!isAvailable && signal && 'severity' in signal) ? (signal as any).severity : undefined;

                  return (
                    <div key={key} className="flex items-start gap-2.5 text-xs text-zinc-300">
                      {isAvailable ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                      ) : (
                        <Circle className="w-4 h-4 text-zinc-500 shrink-0 mt-0.5" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className={`font-semibold ${isAvailable ? 'text-zinc-200' : 'text-zinc-400'}`}>
                            {label}
                          </span>
                          {isAvailable && signal && 'confidence_contribution' in signal && (signal as any).confidence_contribution > 0 && (
                            <span className="text-[10px] text-emerald-400 font-mono font-medium">
                              +{ (signal as any).confidence_contribution }%
                            </span>
                          )}
                          {!isAvailable && severity && typeof severity === 'string' && (
                            <span className={`text-[8px] px-1 rounded border font-bold uppercase tracking-wide shrink-0 ${
                              severity === "REQUIRED"
                                ? "text-rose-400 bg-rose-950/20 border-rose-900/30"
                                : severity === "RECOMMENDED"
                                ? "text-amber-400 bg-amber-950/20 border-amber-900/30"
                                : "text-zinc-500 bg-zinc-800/40 border-zinc-700/50"
                            }`}>
                              {severity.toLowerCase()}
                            </span>
                          )}
                        </div>
                        {description && (
                          <p className="text-[10px] text-zinc-500 mt-0.5 leading-relaxed">
                            {description}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
