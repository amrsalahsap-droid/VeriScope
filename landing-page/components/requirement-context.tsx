"use client";

import { useState, useEffect } from "react";
import { 
  BookOpen, 
  ExternalLink, 
  ChevronDown, 
  ChevronRight,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface WorkItem {
  id: string;
  external_key: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  work_item_type: string;
  provider: string;
  url: string | null;
  acceptance_criteria: Array<{
    id: string;
    title: string;
    description: string;
  }>;
}

interface AcceptanceCriteriaCoverage {
  acceptance_criterion_id: string;
  title: string;
  coverage_status: "AUTOMATED_COVERAGE" | "MANUAL_TEST_COVERAGE" | "PARTIAL_COVERAGE" | "MISSING_COVERAGE" | "VERIFIED_ON_CURRENT_PR" | "UNKNOWN";
  confidence: number;
  recommended_action: string;
  automated_tests: string[];
  external_test_cases: string[];
  suggested_scenarios: string[];
}

interface RequirementContextProps {
  repositoryId: string;
  pullRequestId: string;
}

export function RequirementContext({ repositoryId, pullRequestId }: RequirementContextProps) {
  const [loading, setLoading] = useState(true);
  const [workItems, setWorkItems] = useState<WorkItem[]>([]);
  const [acCoverage, setAcCoverage] = useState<Record<string, AcceptanceCriteriaCoverage>>({});
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({});
  const [expandedAC, setExpandedAC] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadWorkItemContext();
  }, [repositoryId, pullRequestId]);

  const loadWorkItemContext = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/repositories/${repositoryId}/pull-requests/${pullRequestId}/work-item-context`);
      if (response.ok) {
        const data = await response.json();
        setWorkItems(data.work_items || []);
        setAcCoverage(data.ac_coverage || {});
      }
    } catch (error) {
      console.error("Failed to load work item context:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleItem = (itemId: string) => {
    setExpandedItems(prev => ({ ...prev, [itemId]: !prev[itemId] }));
  };

  const toggleAC = (acId: string) => {
    setExpandedAC(prev => ({ ...prev, [acId]: !prev[acId] }));
  };

  const coverageBadge = (status: string) => {
    const map: Record<string, { bg: string; text: string; icon: any }> = {
      AUTOMATED_COVERAGE: { bg: "bg-green-500/10", text: "text-green-400", icon: CheckCircle },
      MANUAL_TEST_COVERAGE: { bg: "bg-blue-500/10", text: "text-blue-400", icon: CheckCircle },
      PARTIAL_COVERAGE: { bg: "bg-amber-500/10", text: "text-amber-400", icon: AlertCircle },
      MISSING_COVERAGE: { bg: "bg-red-500/10", text: "text-red-400", icon: XCircle },
      VERIFIED_ON_CURRENT_PR: { bg: "bg-emerald-500/10", text: "text-emerald-400", icon: CheckCircle },
      UNKNOWN: { bg: "bg-zinc-500/10", text: "text-zinc-400", icon: AlertCircle },
    };
    const s = map[status] || map.UNKNOWN;
    const Icon = s.icon;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${s.bg} ${s.text}`}>
        <Icon className="w-3 h-3" />
        {status.replace(/_/g, " ")}
      </span>
    );
  };

  const truncateText = (text: string, maxLength: number = 200) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + "...";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 animate-spin text-zinc-400" />
      </div>
    );
  }

  if (workItems.length === 0) {
    return (
      <div className="text-center py-8">
        <AlertCircle className="w-8 h-8 text-zinc-500 mx-auto mb-2" />
        <p className="text-sm text-zinc-400">No linked work items found</p>
        <p className="text-xs text-zinc-500 mt-1">
          Link Jira issues or Azure work items to see requirement context
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {workItems.map((workItem) => (
        <div
          key={workItem.id}
          className="border border-zinc-800/40 rounded-lg overflow-hidden"
        >
          <button
            onClick={() => toggleItem(workItem.id)}
            className="w-full flex items-center justify-between px-4 py-3 bg-zinc-900/40 hover:bg-zinc-900/60 transition-colors"
          >
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm font-semibold text-zinc-200 truncate">
                  {workItem.title}
                </span>
                <span className="text-xs text-zinc-500 whitespace-nowrap">
                  {workItem.external_key}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                  workItem.priority === "BLOCKER" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                  workItem.priority === "HIGH" ? "bg-orange-500/10 text-orange-400 border-orange-500/20" :
                  workItem.priority === "MEDIUM" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                  "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                }`}>
                  {workItem.priority}
                </span>
                <span className="text-[10px] text-zinc-500">{workItem.provider}</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-zinc-500">{workItem.status}</span>
              {expandedItems[workItem.id] ? (
                <ChevronDown className="w-4 h-4 text-zinc-600" />
              ) : (
                <ChevronRight className="w-4 h-4 text-zinc-600" />
              )}
            </div>
          </button>

          {expandedItems[workItem.id] && (
            <div className="px-4 py-3 bg-zinc-950/20 space-y-4">
              {/* Description */}
              {workItem.description && (
                <div>
                  <p className="text-xs text-zinc-400 mb-1">Description</p>
                  <p className="text-sm text-zinc-300">{truncateText(workItem.description, 300)}</p>
                </div>
              )}

              {/* External Link */}
              {workItem.url && (
                <div>
                  <a
                    href={workItem.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                  >
                    <ExternalLink className="w-3 h-3" />
                    View in {workItem.provider}
                  </a>
                </div>
              )}

              {/* Acceptance Criteria */}
              {workItem.acceptance_criteria && workItem.acceptance_criteria.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-zinc-400">Acceptance Criteria</p>
                  {workItem.acceptance_criteria.map((ac) => {
                    const coverage = acCoverage[ac.id];
                    return (
                      <div
                        key={ac.id}
                        className="border border-zinc-800/30 rounded overflow-hidden"
                      >
                        <button
                          onClick={() => toggleAC(ac.id)}
                          className="w-full flex items-center justify-between px-3 py-2 bg-zinc-900/30 hover:bg-zinc-900/50 transition-colors"
                        >
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            <span className="text-xs font-medium text-zinc-300 truncate">
                              {ac.title}
                            </span>
                            {coverage && coverageBadge(coverage.coverage_status)}
                          </div>
                          {expandedAC[ac.id] ? (
                            <ChevronDown className="w-3.5 h-3.5 text-zinc-600" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />
                          )}
                        </button>

                        {expandedAC[ac.id] && (
                          <div className="px-3 py-2 bg-zinc-950/30 space-y-3">
                            {ac.description && (
                              <div>
                                <p className="text-xs text-zinc-400 mb-1">Description</p>
                                <p className="text-xs text-zinc-300">{truncateText(ac.description, 200)}</p>
                              </div>
                            )}

                            {coverage && (
                              <div className="space-y-2">
                                <p className="text-xs font-semibold text-zinc-400">Coverage</p>
                                <div className="grid grid-cols-2 gap-2 text-xs">
                                  <div>
                                    <span className="text-zinc-500">Status:</span>
                                    <span className="ml-1 text-zinc-300">{coverage.coverage_status.replace(/_/g, " ")}</span>
                                  </div>
                                  <div>
                                    <span className="text-zinc-500">Confidence:</span>
                                    <span className="ml-1 text-zinc-300">{(coverage.confidence * 100).toFixed(0)}%</span>
                                  </div>
                                </div>

                                {coverage.automated_tests.length > 0 && (
                                  <div>
                                    <p className="text-zinc-500 mb-1">Automated Tests:</p>
                                    <div className="space-y-1">
                                      {coverage.automated_tests.slice(0, 3).map((test, idx) => (
                                        <p key={idx} className="text-xs text-zinc-300 truncate">{test}</p>
                                      ))}
                                      {coverage.automated_tests.length > 3 && (
                                        <p className="text-xs text-zinc-500">
                                          +{coverage.automated_tests.length - 3} more
                                        </p>
                                      )}
                                    </div>
                                  </div>
                                )}

                                {coverage.external_test_cases.length > 0 && (
                                  <div>
                                    <p className="text-zinc-500 mb-1">Manual Tests:</p>
                                    <div className="space-y-1">
                                      {coverage.external_test_cases.slice(0, 3).map((test, idx) => (
                                        <p key={idx} className="text-xs text-zinc-300 truncate">{test}</p>
                                      ))}
                                      {coverage.external_test_cases.length > 3 && (
                                        <p className="text-xs text-zinc-500">
                                          +{coverage.external_test_cases.length - 3} more
                                        </p>
                                      )}
                                    </div>
                                  </div>
                                )}

                                {coverage.suggested_scenarios.length > 0 && (
                                  <div>
                                    <p className="text-zinc-500 mb-1">Suggested Scenarios:</p>
                                    <div className="space-y-1">
                                      {coverage.suggested_scenarios.slice(0, 2).map((scenario, idx) => (
                                        <p key={idx} className="text-xs text-zinc-300 truncate">{scenario}</p>
                                      ))}
                                      {coverage.suggested_scenarios.length > 2 && (
                                        <p className="text-xs text-zinc-500">
                                          +{coverage.suggested_scenarios.length - 2} more
                                        </p>
                                      )}
                                    </div>
                                  </div>
                                )}

                                {coverage.recommended_action && (
                                  <div className="bg-amber-500/10 border border-amber-500/20 rounded px-2 py-1.5">
                                    <p className="text-xs text-amber-300">{coverage.recommended_action}</p>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
