"use client";

import { useState } from "react";
import type { RecommendedTest } from "@/lib/scenario-coverage-matrix";
import { Play, Clock, Target, Layers, FileText, CheckCircle2, AlertTriangle, Check, X, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface ExistingTestsProps {
  tests: RecommendedTest[];
  changedFiles: string[];
  recommendationRunId: string;
}

interface TestOutcome {
  engineer_decision: "KEPT" | "REMOVED" | "NOT_DECIDED";
  execution_status: "NOT_RUN" | "PASSED" | "FAILED" | "SKIPPED" | "UNKNOWN";
}

export function ExistingAutomatedTests({ tests, changedFiles, recommendationRunId }: ExistingTestsProps) {
  const [testOutcomes, setTestOutcomes] = useState<Record<string, TestOutcome>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  const updateTestDecision = async (testIdentifier: string, decision: "KEPT" | "REMOVED" | "NOT_DECIDED") => {
    setLoading(prev => ({ ...prev, [testIdentifier]: true }));
    try {
      const response = await fetch(`/api/recommendations/${recommendationRunId}/tests/${testIdentifier}/outcome`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ engineer_decision: decision }),
      });

      if (!response.ok) throw new Error("Failed to update decision");

      setTestOutcomes(prev => ({
        ...prev,
        [testIdentifier]: { ...prev[testIdentifier], engineer_decision: decision }
      }));

      const decisionLabel = decision === "KEPT" ? "kept" : decision === "REMOVED" ? "removed" : "reset";
      toast.success("Test decision updated", { description: `Test marked as ${decisionLabel}` });
    } catch (error) {
      toast.error("Failed to update decision", { description: "Please try again later." });
    } finally {
      setLoading(prev => ({ ...prev, [testIdentifier]: false }));
    }
  };

  if (!tests || tests.length === 0) {
    return (
      <div className="text-center py-8 text-zinc-500 text-sm">
        No existing automated tests found
      </div>
    );
  }

  const tierGroups = {
    must_run: tests.filter(t => t.tier === "must_run"),
    should_run: tests.filter(t => t.tier === "should_run"),
    fallback: tests.filter(t => t.tier === "fallback")
  };

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <Play className="w-3 h-3 text-emerald-400" />
          <span className="text-zinc-400">Runnable Tests: {tests.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-zinc-500">Must Run: {tierGroups.must_run.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-zinc-500">Should Run: {tierGroups.should_run.length}</span>
        </div>
      </div>

      {/* Must Run Tests */}
      {tierGroups.must_run.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider">Must Run</span>
            <span className="text-[10px] text-zinc-500">({tierGroups.must_run.length})</span>
          </div>
          <div className="space-y-2">
            {tierGroups.must_run.map((test) => (
              <TestCard 
                key={test.stable_identity} 
                test={test} 
                changedFiles={changedFiles}
                recommendationRunId={recommendationRunId}
                testOutcomes={testOutcomes}
                loading={loading}
                updateTestDecision={updateTestDecision}
              />
            ))}
          </div>
        </div>
      )}

      {/* Should Run Tests */}
      {tierGroups.should_run.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">Should Run</span>
            <span className="text-[10px] text-zinc-500">({tierGroups.should_run.length})</span>
          </div>
          <div className="space-y-2">
            {tierGroups.should_run.map((test) => (
              <TestCard 
                key={test.stable_identity} 
                test={test} 
                changedFiles={changedFiles}
                recommendationRunId={recommendationRunId}
                testOutcomes={testOutcomes}
                loading={loading}
                updateTestDecision={updateTestDecision}
              />
            ))}
          </div>
        </div>
      )}

      {/* Fallback Tests */}
      {tierGroups.fallback.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Fallback</span>
            <span className="text-[10px] text-zinc-500">({tierGroups.fallback.length})</span>
          </div>
          <div className="space-y-2">
            {tierGroups.fallback.map((test) => (
              <TestCard 
                key={test.stable_identity} 
                test={test} 
                changedFiles={changedFiles}
                recommendationRunId={recommendationRunId}
                testOutcomes={testOutcomes}
                loading={loading}
                updateTestDecision={updateTestDecision}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TestCard({ test, changedFiles, recommendationRunId, testOutcomes, loading, updateTestDecision }: { 
  test: RecommendedTest; 
  changedFiles: string[];
  recommendationRunId: string;
  testOutcomes: Record<string, TestOutcome>;
  loading: Record<string, boolean>;
  updateTestDecision: (id: string, decision: "KEPT" | "REMOVED" | "NOT_DECIDED") => void;
}) {
  const confidence = test.confidence || "LOW";
  const confidenceColor = 
    confidence === "HIGH" ? "text-emerald-400 bg-emerald-950/20 border-emerald-500/20" :
    confidence === "MEDIUM" ? "text-amber-400 bg-amber-950/20 border-amber-500/20" :
    "text-zinc-400 bg-zinc-800 border-zinc-700";

  const outcome = testOutcomes[test.stable_identity] || { engineer_decision: "NOT_DECIDED", execution_status: "NOT_RUN" };
  const isLoading = loading[test.stable_identity];

  const executionStatusColor = 
    outcome.execution_status === "PASSED" ? "text-emerald-400" :
    outcome.execution_status === "FAILED" ? "text-rose-400" :
    outcome.execution_status === "SKIPPED" ? "text-amber-400" :
    "text-zinc-500";

  return (
    <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-lg p-4 hover:bg-zinc-900/60 transition-colors">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-semibold text-zinc-100 truncate" title={test.display_name}>
              {test.display_name}
            </h3>
            <span className={`text-[9px] px-1.5 py-0.5 rounded border ${confidenceColor}`}>
              {confidence}
            </span>
            {/* Execution Status Badge */}
            {outcome.execution_status !== "NOT_RUN" && (
              <span className={`text-[9px] px-1.5 py-0.5 rounded bg-zinc-800 border-zinc-700 ${executionStatusColor}`}>
                {outcome.execution_status}
              </span>
            )}
          </div>
          <p className="text-[10px] text-zinc-500 font-mono truncate" title={test.stable_identity}>
            {test.stable_identity}
          </p>
        </div>
        
        {/* Decision Controls */}
        <div className="flex items-center gap-1.5 shrink-0">
          <Button
            variant={outcome.engineer_decision === "KEPT" ? "default" : "outline"}
            size="sm"
            onClick={() => updateTestDecision(test.stable_identity, "KEPT")}
            disabled={isLoading}
            className={
              outcome.engineer_decision === "KEPT"
                ? "bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-600"
                : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700"
            }
            title="Keep this test"
          >
            <Check className="w-3 h-3" />
          </Button>
          <Button
            variant={outcome.engineer_decision === "REMOVED" ? "default" : "outline"}
            size="sm"
            onClick={() => updateTestDecision(test.stable_identity, "REMOVED")}
            disabled={isLoading}
            className={
              outcome.engineer_decision === "REMOVED"
                ? "bg-rose-600 hover:bg-rose-700 text-white border-rose-600"
                : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700"
            }
            title="Remove this test"
          >
            <X className="w-3 h-3" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => updateTestDecision(test.stable_identity, "KEPT")}
            disabled={isLoading}
            className="bg-zinc-800 hover:bg-zinc-700 text-amber-400 border-zinc-700"
            title="Mark as important"
          >
            <Star className="w-3 h-3" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="space-y-1">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Impacted Area</span>
          <div className="flex items-center gap-1.5 text-zinc-300">
            <Target className="w-3 h-3 text-zinc-500" />
            <span className="truncate">{test.impacted_area || "General"}</span>
          </div>
        </div>
        <div className="space-y-1">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Testing Type</span>
          <div className="flex items-center gap-1.5 text-zinc-300">
            <Layers className="w-3 h-3 text-zinc-500" />
            <span className="truncate">{test.testing_type || "Regression"}</span>
          </div>
        </div>
      </div>

      {test.reason && (
        <div className="mt-3 pt-3 border-t border-zinc-800/50">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Reason</span>
          <p className="text-xs text-zinc-400 leading-snug">{test.reason}</p>
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-zinc-800/50 flex items-center justify-between text-[10px] text-zinc-500">
        <div className="flex items-center gap-1.5">
          <FileText className="w-3 h-3" />
          <span>{changedFiles.length} changed files</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Clock className="w-3 h-3" />
          <span>Est. duration: ~30s</span>
        </div>
      </div>
    </div>
  );
}
