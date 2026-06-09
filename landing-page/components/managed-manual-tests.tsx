"use client";

import { useState, useEffect } from "react";
import { 
  ClipboardCopy, 
  ExternalLink, 
  ChevronDown, 
  ChevronRight,
  CheckCircle,
  Play,
  FileText,
  AlertCircle,
  Loader2
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

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
  execution_status: "NOT_EXECUTED" | "PASSED" | "FAILED" | "SKIPPED";
}

interface ManagedManualTestsProps {
  repositoryId: string;
  pullRequestId: string;
}

export function ManagedManualTests({ repositoryId, pullRequestId }: ManagedManualTestsProps) {
  const [loading, setLoading] = useState(true);
  const [manualTests, setManualTests] = useState<ManualTestCase[]>([]);
  const [expandedTests, setExpandedTests] = useState<Record<string, boolean>>({});
  const [markingExecuted, setMarkingExecuted] = useState<string | null>(null);

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
      }
    } catch (error) {
      console.error("Failed to load manual tests:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleTest = (testId: string) => {
    setExpandedTests(prev => ({ ...prev, [testId]: !prev[testId] }));
  };

  const copySteps = (test: ManualTestCase) => {
    const stepsText = test.steps.map((s, i) => 
      `${i + 1}. ${s.step}\n   Expected: ${s.expected}`
    ).join('\n\n');
    
    navigator.clipboard.writeText(stepsText);
    toast.success("Steps copied to clipboard");
  };

  const markAsExecuted = async (testId: string, outcome: "PASSED" | "FAILED") => {
    setMarkingExecuted(testId);
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/manual-tests/${testId}/execution`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome })
      });

      if (response.ok) {
        toast.success(`Test marked as ${outcome.toLowerCase()}`);
        loadManualTests();
      } else {
        toast.error("Failed to mark test as executed");
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

              {/* Actions */}
              <div className="flex items-center gap-2 pt-2 border-t border-zinc-800/30">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copySteps(test)}
                  className="flex-1"
                >
                  <ClipboardCopy className="w-3.5 h-3.5 mr-2" />
                  Copy Steps
                </Button>
                
                {test.url && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => test.url && window.open(test.url, '_blank')}
                    className="flex-1"
                  >
                    <ExternalLink className="w-3.5 h-3.5 mr-2" />
                    Open in {test.provider}
                  </Button>
                )}

                {test.execution_status === "NOT_EXECUTED" && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => markAsExecuted(test.id, "PASSED")}
                      disabled={markingExecuted === test.id}
                      className="flex-1"
                    >
                      {markingExecuted === test.id ? (
                        <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                      ) : (
                        <CheckCircle className="w-3.5 h-3.5 mr-2" />
                      )}
                      Mark Passed
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => markAsExecuted(test.id, "FAILED")}
                      disabled={markingExecuted === test.id}
                      className="flex-1"
                    >
                      {markingExecuted === test.id ? (
                        <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                      ) : (
                        <AlertCircle className="w-3.5 h-3.5 mr-2" />
                      )}
                      Mark Failed
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
