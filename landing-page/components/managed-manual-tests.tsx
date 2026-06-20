"use client";

import React, { useState, useEffect } from "react";
import { 
  ClipboardCopy, 
  ExternalLink, 
  ChevronDown, 
  ChevronRight,
  CheckCircle,
  Play,
  FileText,
  AlertCircle,
  Loader2,
  X,
  RefreshCw,
  Cloud
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ManualEvidenceGovernancePanel } from "@/components/manual-evidence/ManualEvidenceGovernancePanel";

interface ManualTestCase {
  id: string;
  title: string;
  provider: string;
  external_key: string;
  priority: string;
  url: string | null;
  linked_ac: string[];
  linked_behavior: string[];
  preconditions: string[];
  steps: Array<{
    step: string;
    expected: string;
  }>;
  expected_result: string;
  execution_status: "NOT_EXECUTED" | "PASSED" | "FAILED" | "SKIPPED" | "BLOCKED";
  latestExecutionStatus?: string;
  latestExecutedAt?: string | null;
  latestExecutedByName?: string | null;
  latestExecutionNotes?: string | null;
  latestEvidenceUrl?: string | null;
  executionHistoryCount?: number;
  latestExecutionId?: string | null;
  syncStatus?: string | null;
  externalRunId?: string | null;
  externalExecutionId?: string | null;
  lastSyncedAt?: string | null;
}

interface ManagedManualTestsProps {
  repositoryId: string;
  pullRequestId: string;
  acceptanceCriteria?: Array<{
    id: string;
    readableId?: string;
    title?: string;
    text?: string;
    fullText?: string;
  }>;
}

export function ManagedManualTests({ repositoryId, pullRequestId, acceptanceCriteria = [] }: ManagedManualTestsProps) {
  const [loading, setLoading] = useState(true);
  const [manualTests, setManualTests] = useState<ManualTestCase[]>([]);
  const [expandedTests, setExpandedTests] = useState<Record<string, boolean>>({});
  const [markingExecuted, setMarkingExecuted] = useState<string | null>(null);
  
  // Execution Form States per test ID
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [evidenceUrls, setEvidenceUrls] = useState<Record<string, string>>({});

  // Mapping state hooks
  const [mappings, setMappings] = useState<Record<string, any[]>>({});
  const [selectedAcId, setSelectedAcId] = useState<Record<string, string>>({});
  const [linkingAc, setLinkingAc] = useState<Record<string, boolean>>({});
  
  // Sync status state
  const [syncStatuses, setSyncStatuses] = useState<Record<string, any>>({});
  const [retryingSync, setRetryingSync] = useState<string | null>(null);

  useEffect(() => {
    loadManualTests();
  }, [repositoryId, pullRequestId]);

  const loadManualTests = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/repositories/${repositoryId}/pull-requests/${pullRequestId}/manual-tests`);
      if (response.ok) {
        const data = await response.json();
        setManualTests(data.manual_tests || []);
        
        // Load sync statuses for tests with executions
        for (const test of data.manual_tests || []) {
          if (test.latestExecutionId) {
            loadSyncStatus(test.latestExecutionId);
          }
        }
      }
    } catch (error) {
      console.error("Failed to load manual tests:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadSyncStatus = async (executionId: string) => {
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/manual-executions/${executionId}/sync-status`);
      if (response.ok) {
        const data = await response.json();
        setSyncStatuses(prev => ({ ...prev, [executionId]: data }));
      }
    } catch (error) {
      console.error("Failed to load sync status:", error);
    }
  };

  const retrySync = async (executionId: string) => {
    setRetryingSync(executionId);
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/manual-executions/${executionId}/retry-sync`, {
        method: "POST"
      });
      if (response.ok) {
        const data = await response.json();
        setSyncStatuses(prev => ({ ...prev, [executionId]: data }));
        toast.success("Sync retry initiated");
      } else {
        const error = await response.json();
        toast.error(`Sync retry failed: ${error.error || 'Unknown error'}`);
      }
    } catch (error) {
      toast.error("Failed to retry sync");
    } finally {
      setRetryingSync(null);
    }
  };

  const loadMappingsForTest = async (testId: string) => {
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/manual-tests/${testId}/mappings`);
      if (response.ok) {
        const data = await response.json();
        setMappings(prev => ({ ...prev, [testId]: data }));
      }
    } catch (error) {
      console.error("Failed to load mappings for test:", testId, error);
    }
  };

  const addMapping = async (testId: string) => {
    const acIdInput = selectedAcId[testId]?.trim();
    if (!acIdInput) return;

    setLinkingAc(prev => ({ ...prev, [testId]: true }));
    try {
      let resolvedAcId = acIdInput;
      const matchingAc = acceptanceCriteria.find(
        ac => ac.readableId === acIdInput || 
              (ac.id && ac.id.startsWith("AC-") && ac.id === acIdInput) || 
              ac.id === acIdInput
      );
      if (matchingAc) {
        resolvedAcId = matchingAc.id;
      }

      const response = await fetch(`/api/repositories/${repositoryId}/manual-tests/${testId}/mappings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ acceptanceCriterionId: resolvedAcId })
      });

      if (response.ok) {
        toast.success("Acceptance Criterion linked successfully");
        setSelectedAcId(prev => ({ ...prev, [testId]: "" }));
        loadMappingsForTest(testId);
      } else {
        const err = await response.json();
        toast.error(err.detail || "Failed to link Acceptance Criterion");
      }
    } catch (error) {
      toast.error("Failed to link Acceptance Criterion");
    } finally {
      setLinkingAc(prev => ({ ...prev, [testId]: false }));
    }
  };

  const deleteMapping = async (testId: string, mappingId: string) => {
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/manual-tests/${testId}/mappings/${mappingId}`, {
        method: "DELETE"
      });
      if (response.ok) {
        toast.success("Link removed successfully");
        loadMappingsForTest(testId);
      } else {
        toast.error("Failed to remove link");
      }
    } catch (error) {
      toast.error("Failed to remove link");
    }
  };

  const toggleTest = (testId: string) => {
    const nextExpanded = !expandedTests[testId];
    setExpandedTests(prev => ({ ...prev, [testId]: nextExpanded }));
    if (nextExpanded) {
      loadMappingsForTest(testId);
    }
  };

  const copySteps = (test: ManualTestCase) => {
    const stepsText = test.steps.map((s, i) => 
      `${i + 1}. ${s.step}\n   Expected: ${s.expected}`
    ).join('\n\n');
    
    navigator.clipboard.writeText(stepsText);
    toast.success("Steps copied to clipboard");
  };

  const markAsExecuted = async (testId: string, outcome: "PASSED" | "FAILED" | "SKIPPED" | "BLOCKED") => {
    setMarkingExecuted(testId);
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/manual-tests/${testId}/execution`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          outcome,
          notes: notes[testId] || "",
          evidenceUrl: evidenceUrls[testId] || "",
          pullRequestId
        })
      });

      if (response.ok) {
        toast.success(`Test marked as ${outcome.toLowerCase()}`);
        // Clear notes and evidence URL fields for this test
        setNotes(prev => ({ ...prev, [testId]: "" }));
        setEvidenceUrls(prev => ({ ...prev, [testId]: "" }));
        loadManualTests();
      } else {
        const errorData = await response.json().catch(() => ({}));
        if (response.status === 403 && errorData?.detail === "MANUAL_TEST_WORKSPACE_ACCESS_DENIED") {
          toast.error("403: Workspace access denied for this manual execution.");
        } else {
          toast.error("Failed to mark test as executed");
        }
      }
    } catch (error) {
      toast.error("Failed to mark test as executed");
    } finally {
      setMarkingExecuted(null);
    }
  };

  const priorityBadge = (priority: string) => {
    const map: Record<string, { bg: string; text: string }> = {
      BLOCKER: { bg: "bg-rose-500/10", text: "text-rose-400" },
      MUST: { bg: "bg-orange-500/10", text: "text-orange-400" },
      SHOULD: { bg: "bg-amber-500/10", text: "text-amber-400" },
      OPTIONAL: { bg: "bg-zinc-500/10", text: "text-zinc-400" },
    };
    const s = map[priority] || map.SHOULD;
    return (
      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${s.bg} ${s.text} border-current`}>
        {priority}
      </span>
    );
  };

  const executionStatusBadge = (status: string) => {
    const map: Record<string, { bg: string; text: string; icon: any }> = {
      NOT_EXECUTED: { bg: "bg-zinc-500/10", text: "text-zinc-400", icon: AlertCircle },
      PASSED: { bg: "bg-green-500/10", text: "text-green-400", icon: CheckCircle },
      FAILED: { bg: "bg-red-500/10", text: "text-red-400", icon: AlertCircle },
      SKIPPED: { bg: "bg-zinc-500/10", text: "text-zinc-400", icon: AlertCircle },
      BLOCKED: { bg: "bg-orange-500/10", text: "text-orange-400", icon: AlertCircle },
    };
    const s = map[status] || map.NOT_EXECUTED;
    const Icon = s.icon;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${s.bg} ${s.text}`}>
        <Icon className="w-3 h-3" />
        {status.replace(/_/g, " ")}
      </span>
    );
  };

  const syncStatusBadge = (syncStatus: string | null) => {
    if (!syncStatus || syncStatus === "PENDING") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-zinc-500/10 text-zinc-400">
          <Loader2 className="w-3 h-3 animate-spin" />
          Pending
        </span>
      );
    }
    if (syncStatus === "IN_PROGRESS") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-500/10 text-blue-400">
          <Loader2 className="w-3 h-3 animate-spin" />
          In Progress
        </span>
      );
    }
    if (syncStatus === "SYNCED") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-500/10 text-green-400">
          <CheckCircle className="w-3 h-3" />
          Synced
        </span>
      );
    }
    if (syncStatus === "FAILED") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-500/10 text-red-400">
          <AlertCircle className="w-3 h-3" />
          Failed
        </span>
      );
    }
    if (syncStatus === "RETRY_PENDING") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/10 text-yellow-400">
          <Loader2 className="w-3 h-3 animate-spin" />
          Retry Pending
        </span>
      );
    }
    if (syncStatus === "DEAD_LETTER") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-gray-500/10 text-gray-400">
          <AlertCircle className="w-3 h-3" />
          Dead Letter
        </span>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 animate-spin text-zinc-400" />
      </div>
    );
  }

  if (manualTests.length === 0) {
    return (
      <div className="text-center py-8">
        <FileText className="w-8 h-8 text-zinc-500 mx-auto mb-2" />
        <p className="text-sm text-zinc-400">No manual tests recommended</p>
        <p className="text-xs text-zinc-500 mt-1">
          Connect TestRail or import CSV to see manual test cases
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {manualTests.map((test) => (
        <div
          key={test.id}
          className="border border-zinc-800/40 rounded-lg overflow-hidden"
        >
          <button
            onClick={() => toggleTest(test.id)}
            className="w-full flex items-center justify-between px-4 py-3 bg-zinc-900/40 hover:bg-zinc-900/60 transition-colors"
          >
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm font-semibold text-zinc-200 truncate">
                  {test.title}
                </span>
                {priorityBadge(test.priority)}
                {executionStatusBadge(test.execution_status)}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-zinc-500">{test.provider}</span>
                <span className="text-[10px] text-zinc-500 font-mono">{test.external_key}</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {expandedTests[test.id] ? (
                <ChevronDown className="w-4 h-4 text-zinc-600" />
              ) : (
                <ChevronRight className="w-4 h-4 text-zinc-600" />
              )}
            </div>
          </button>

          {expandedTests[test.id] && (
            <div className="px-4 py-3 bg-zinc-950/20 space-y-4">
              {/* Linked AC/Behavior */}
              {(test.linked_ac.length > 0 || test.linked_behavior.length > 0) && (
                <div className="flex flex-wrap gap-2">
                  {test.linked_ac.map((ac, idx) => (
                    <span key={idx} className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded border border-blue-500/20">
                      AC: {ac}
                    </span>
                  ))}
                  {test.linked_behavior.map((behavior, idx) => (
                    <span key={idx} className="text-[10px] bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded border border-purple-500/20">
                      Behavior: {behavior}
                    </span>
                  ))}
                </div>
              )}

              {/* Preconditions */}
              {test.preconditions.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-zinc-400 mb-2">Preconditions</p>
                  <ul className="space-y-1">
                    {test.preconditions.map((pre, idx) => (
                      <li key={idx} className="text-xs text-zinc-300 flex items-start gap-2">
                        <span className="text-zinc-500">•</span>
                        <span>{pre}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Steps */}
              {test.steps.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-zinc-400 mb-2">Test Steps</p>
                  <div className="space-y-3">
                    {test.steps.map((step, idx) => (
                      <div key={idx} className="space-y-1">
                        <div className="flex items-start gap-2">
                          <span className="text-xs font-mono text-zinc-500">{idx + 1}.</span>
                          <p className="text-xs text-zinc-300">{step.step}</p>
                        </div>
                        {step.expected && (
                          <div className="flex items-start gap-2 pl-4">
                            <span className="text-xs text-zinc-500">→</span>
                            <p className="text-xs text-zinc-400 italic">{step.expected}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Expected Result */}
              {test.expected_result && (
                <div>
                  <p className="text-xs font-semibold text-zinc-400 mb-1">Expected Result</p>
                  <p className="text-xs text-zinc-300">{test.expected_result}</p>
                </div>
              )}

              {/* Mapped Requirements (Traceability) */}
              <div className="space-y-2 pt-2 border-t border-zinc-800/30">
                <p className="text-xs font-semibold text-zinc-400">Mapped Requirements</p>
                
                {/* Active Mappings List */}
                <div className="space-y-1.5">
                  {(Array.isArray(mappings[test.id]) ? mappings[test.id] : []).length === 0 ? (
                    <p className="text-xs text-zinc-500 italic">No mapped requirements.</p>
                  ) : (
                    (Array.isArray(mappings[test.id]) ? mappings[test.id] : []).map((mapping) => (
                      <div key={mapping.id} className="flex items-center justify-between bg-zinc-900/40 border border-zinc-800/40 rounded px-2.5 py-1.5 text-xs text-zinc-300">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="font-mono text-blue-400 font-semibold shrink-0">{mapping.readableRequirementId}</span>
                          <span className="text-zinc-300 truncate" title={mapping.requirementText}>{mapping.requirementText}</span>
                          <span className="text-[9px] text-zinc-500 uppercase px-1 rounded bg-zinc-900 border border-zinc-800 shrink-0">{mapping.mappingSource}</span>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => deleteMapping(test.id, mapping.id)}
                          className="w-5 h-5 text-zinc-500 hover:text-red-400 hover:bg-zinc-850"
                        >
                          <X className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    ))
                  )}
                </div>

                {/* Add Mapping Form */}
                <div className="space-y-1.5 pt-1">
                  <label htmlFor={`ac-input-${test.id}`} className="text-[10px] text-zinc-500 uppercase block">Link Acceptance Criterion</label>
                  <div className="flex gap-2 items-center">
                    <input
                      type="text"
                      id={`ac-input-${test.id}`}
                      placeholder="e.g. AC-12 or select from suggestions..."
                      className="text-xs bg-zinc-900/60 border border-zinc-800 rounded px-2.5 py-1.5 text-zinc-350 focus:outline-none focus:border-zinc-700 flex-1 min-w-0"
                      value={selectedAcId[test.id] || ""}
                      onChange={(e) => setSelectedAcId(prev => ({ ...prev, [test.id]: e.target.value }))}
                      list={`ac-datalist-${test.id}`}
                    />
                    <datalist id={`ac-datalist-${test.id}`}>
                      {acceptanceCriteria.map(ac => {
                        const label = ac.readableId || (ac.id && ac.id.startsWith("AC-") ? ac.id : `AC-${ac.id.substring(0, 8)}`);
                        return (
                          <option key={ac.id} value={label}>
                            {ac.title || ac.text}
                          </option>
                        );
                      })}
                    </datalist>
                    <Button
                      variant="outline"
                      size="sm"
                      id={`btn-link-ac-${test.id}`}
                      onClick={() => addMapping(test.id)}
                      disabled={!selectedAcId[test.id] || linkingAc[test.id]}
                      className="h-8 shrink-0"
                    >
                      {linkingAc[test.id] ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Link"}
                    </Button>
                  </div>
                </div>

                {/* Advisory Message */}
                <p className="text-[10px] text-amber-500/80 flex items-start gap-1.5 mt-2 bg-amber-500/5 border border-amber-500/10 rounded p-2 leading-relaxed">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>Manual mappings provide traceability only and do not mark requirements covered.</span>
                </p>
              </div>

              {/* Latest Execution Metadata */}
              {test.latestExecutedAt && (
                <div className="bg-zinc-900/40 rounded-lg p-3 border border-zinc-800/20 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-zinc-500 uppercase font-semibold">Latest Execution</span>
                    <div className="flex items-center gap-2">
                      {test.latestExecutionId && syncStatuses[test.latestExecutionId]?.supportsExecutionSync && (
                        <>
                          {syncStatusBadge(syncStatuses[test.latestExecutionId]?.syncStatus || null)}
                          {(syncStatuses[test.latestExecutionId]?.syncStatus === "FAILED" || 
                            syncStatuses[test.latestExecutionId]?.syncStatus === "RETRY_PENDING") && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => retrySync(test.latestExecutionId!)}
                              disabled={
                                retryingSync === test.latestExecutionId ||
                                syncStatuses[test.latestExecutionId]?.cooldownUntil
                              }
                              className="h-6 px-2 text-xs text-zinc-400 hover:text-zinc-300 disabled:opacity-50 disabled:cursor-not-allowed"
                              title={
                                syncStatuses[test.latestExecutionId]?.cooldownUntil
                                  ? `Retry disabled: ${syncStatuses[test.latestExecutionId]?.cooldownReason || 'Provider cooldown active'}`
                                  : 'Retry sync'
                              }
                            >
                              {retryingSync === test.latestExecutionId ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <RefreshCw className="w-3 h-3" />
                              )}
                            </Button>
                          )}
                        </>
                      )}
                      <span className="text-[10px] text-zinc-500">History: {test.executionHistoryCount} run(s)</span>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-zinc-500">Outcome:</span>{" "}
                      <span className={test.latestExecutionStatus === "PASSED" ? "text-green-400" : test.latestExecutionStatus === "FAILED" ? "text-red-400" : "text-zinc-400"}>
                        {test.latestExecutionStatus}
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-500">Executed By:</span>{" "}
                      <span className="text-zinc-300">{test.latestExecutedByName || "Unknown"}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500">Date:</span>{" "}
                      <span className="text-zinc-300">{new Date(test.latestExecutedAt).toLocaleString()}</span>
                    </div>
                    {test.latestEvidenceUrl && (
                      <div className="col-span-2">
                        <span className="text-zinc-500">Evidence URL:</span>{" "}
                        <a href={test.latestEvidenceUrl} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline inline-flex items-center gap-0.5">
                          {test.latestEvidenceUrl} <ExternalLink className="w-3 h-3 inline" />
                        </a>
                      </div>
                    )}
                    {test.latestExecutionNotes && (
                      <div className="col-span-2 text-zinc-400 italic mt-1 bg-zinc-950/20 p-2 rounded">
                        "{test.latestExecutionNotes}"
                      </div>
                    )}
                    {/* External Sync References */}
                    {test.latestExecutionId && syncStatuses[test.latestExecutionId]?.supportsExecutionSync && (
                      <div className="col-span-2 mt-2 pt-2 border-t border-zinc-800/30">
                        <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 uppercase font-semibold mb-2">
                          <Cloud className="w-3 h-3" />
                          {test.provider} Sync
                        </div>
                        <div className="space-y-1 text-xs">
                          {syncStatuses[test.latestExecutionId].externalRunId && (
                            <div>
                              <span className="text-zinc-500">Run ID:</span>{" "}
                              <span className="text-zinc-300 font-mono">{syncStatuses[test.latestExecutionId].externalRunId}</span>
                            </div>
                          )}
                          {syncStatuses[test.latestExecutionId].externalExecutionId && (
                            <div>
                              <span className="text-zinc-500">Execution ID:</span>{" "}
                              <span className="text-zinc-300 font-mono">{syncStatuses[test.latestExecutionId].externalExecutionId}</span>
                            </div>
                          )}
                          {syncStatuses[test.latestExecutionId].lastSyncedAt && (
                            <div>
                              <span className="text-zinc-500">Last Synced:</span>{" "}
                              <span className="text-zinc-300">{new Date(syncStatuses[test.latestExecutionId].lastSyncedAt).toLocaleString()}</span>
                            </div>
                          )}
                          {syncStatuses[test.latestExecutionId].lastError && (
                            <div className="text-red-400 italic text-[10px] mt-1">
                              Error: {syncStatuses[test.latestExecutionId].lastError}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Phase 6.5B: Governance Panel */}
                  {test.latestExecutionId && (
                    <div className="pt-2 border-t border-zinc-800/30">
                      <ManualEvidenceGovernancePanel
                        executionId={test.latestExecutionId}
                        repositoryId={repositoryId}
                        onUpdated={() => {
                          // Refresh manual tests to update governance status
                          loadManualTests();
                        }}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Record Execution Form */}
              <div className="space-y-3 pt-2 border-t border-zinc-800/30">
                <p className="text-xs font-semibold text-zinc-400">Record Manual Execution</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] text-zinc-500 uppercase block mb-1">Execution Notes</label>
                    <input
                      type="text"
                      id={`notes-input-${test.id}`}
                      value={notes[test.id] || ""}
                      onChange={(e) => setNotes(prev => ({ ...prev, [test.id]: e.target.value }))}
                      placeholder="e.g. Verified on staging build."
                      className="w-full text-xs bg-zinc-900/60 border border-zinc-800 rounded px-2.5 py-1.5 text-zinc-300 focus:outline-none focus:border-zinc-700"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-zinc-500 uppercase block mb-1">Evidence URL</label>
                    <input
                      type="text"
                      id={`evidence-input-${test.id}`}
                      value={evidenceUrls[test.id] || ""}
                      onChange={(e) => setEvidenceUrls(prev => ({ ...prev, [test.id]: e.target.value }))}
                      placeholder="e.g. https://jira.com/..."
                      className="w-full text-xs bg-zinc-900/60 border border-zinc-800 rounded px-2.5 py-1.5 text-zinc-300 focus:outline-none focus:border-zinc-700"
                    />
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-zinc-800/30">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copySteps(test)}
                  className="flex-1 min-w-[120px]"
                >
                  <ClipboardCopy className="w-3.5 h-3.5 mr-2" />
                  Copy Steps
                </Button>
                
                {test.url && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => test.url && window.open(test.url, '_blank')}
                    className="flex-1 min-w-[120px]"
                  >
                    <ExternalLink className="w-3.5 h-3.5 mr-2" />
                    Open TMS
                  </Button>
                )}

                <div className="w-full flex items-center gap-2 mt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    id={`btn-pass-${test.id}`}
                    onClick={() => markAsExecuted(test.id, "PASSED")}
                    disabled={markingExecuted === test.id}
                    className="flex-1 bg-green-500/10 hover:bg-green-500/20 text-green-400 border-green-500/20"
                  >
                    <CheckCircle className="w-3.5 h-3.5 mr-2" />
                    Pass
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    id={`btn-fail-${test.id}`}
                    onClick={() => markAsExecuted(test.id, "FAILED")}
                    disabled={markingExecuted === test.id}
                    className="flex-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 border-red-500/20"
                  >
                    <AlertCircle className="w-3.5 h-3.5 mr-2" />
                    Fail
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    id={`btn-skip-${test.id}`}
                    onClick={() => markAsExecuted(test.id, "SKIPPED")}
                    disabled={markingExecuted === test.id}
                    className="flex-1 bg-zinc-500/10 hover:bg-zinc-500/20 text-zinc-400 border-zinc-800"
                  >
                    <AlertCircle className="w-3.5 h-3.5 mr-2" />
                    Skip
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    id={`btn-block-${test.id}`}
                    onClick={() => markAsExecuted(test.id, "BLOCKED")}
                    disabled={markingExecuted === test.id}
                    className="flex-1 bg-orange-500/10 hover:bg-orange-500/20 text-orange-400 border-orange-500/20"
                  >
                    <AlertCircle className="w-3.5 h-3.5 mr-2" />
                    Block
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
