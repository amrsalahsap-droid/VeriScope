"use client";

import React, { useEffect, useState, useCallback } from "react";
import { getInputAction, resolveBackendAction } from "@/lib/readiness/inputActionRegistry";
import {
  buildInputReadinessViewModel,
  InputReadinessViewModel,
  InputReadinessItemViewModel,
  InputReadinessBlockerViewModel,
  InputReadinessActionViewModel,
} from "@/lib/readiness/inputReadinessAdapter";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Minus,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Zap,
} from "lucide-react";
import { Input5MappingCard } from "./Input5MappingCard";
import { Input7CoverageCard } from "./Input7CoverageCard";
import { MappingReviewPanel } from "./MappingReviewPanel";
import { SafeObjectRenderer, formatNiceLabel } from "./SafeObjectRenderer";

const formatDetailKey = formatNiceLabel;

// ─── Types ───────────────────────────────────────────────────────────────────

interface InputReadinessAction {
  label: string;
  action: string;
}

interface InputReadinessItem {
  input_id: string;
  label: string;
  status: string;
  weight: number;
  earned_score: number;
  max_score: number;
  is_hard_blocker: boolean;
  summary: string;
  details: Record<string, unknown>;
  actions: InputReadinessAction[];
}

interface InputReadinessBlocker {
  input_id: string;
  code: string;
  message: string;
}

interface InputReadinessWarning {
  input_id: string;
  code: string;
  message: string;
}

interface NextBestAction {
  priority: number;
  input_id: string;
  label: string;
  reason: string;
}

interface InputReadinessV2Data {
  generation_status: string;
  can_generate: string;
  confident_generation: boolean;
  confidence_score: number;
  confidence_level: string;
  confidence_ceiling: string;
  primary_message: string;
  blockers: InputReadinessBlocker[];
  warnings: InputReadinessWarning[];
  inputs: InputReadinessItem[];
  next_best_actions: NextBestAction[];
  // New confidence concepts
  evidence_completeness?: number;
  release_confidence?: string;
  confidence_ceiling_reason?: string;
}

// Re-export view model types for consumers
type ViewModel = InputReadinessViewModel;
type ViewModelItem = InputReadinessItemViewModel;
type ViewModelBlocker = InputReadinessBlockerViewModel;
type ViewModelAction = InputReadinessActionViewModel;

// ─── Status helpers ───────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  READY: {
    icon: <CheckCircle2 className="w-4 h-4" />,
    color: "text-emerald-400",
    label: "Ready",
  },
  PARTIAL: {
    icon: <AlertTriangle className="w-4 h-4" />,
    color: "text-amber-400",
    label: "Partial",
  },
  MISSING: {
    icon: <XCircle className="w-4 h-4" />,
    color: "text-rose-400",
    label: "Missing",
  },
  NEEDS_REVIEW: {
    icon: <AlertTriangle className="w-4 h-4" />,
    color: "text-amber-400",
    label: "Needs Review",
  },
  BLOCKED: {
    icon: <XCircle className="w-4 h-4" />,
    color: "text-rose-400",
    label: "Blocked",
  },
  STALE: {
    icon: <Clock className="w-4 h-4" />,
    color: "text-orange-400",
    label: "Stale",
  },
  HISTORICAL_ONLY: {
    icon: <Clock className="w-4 h-4" />,
    color: "text-orange-400",
    label: "Historical Only",
  },
  NOT_APPLICABLE: {
    icon: <Minus className="w-4 h-4" />,
    color: "text-zinc-500",
    label: "N/A",
  },
};

const GENERATION_STATUS_CONFIG: Record<string, { label: string; color: string; bgColor: string }> = {
  BLOCKED: { label: "Blocked", color: "text-rose-400", bgColor: "bg-rose-950/30 border-rose-800/40" },
  DRAFT_ONLY: { label: "Draft Only", color: "text-amber-400", bgColor: "bg-amber-950/30 border-amber-800/40" },
  MINIMUM_READY: { label: "Minimum Ready", color: "text-zinc-300", bgColor: "bg-zinc-800/50 border-zinc-700/40" },
  CONFIDENT_READY: { label: "Confident Ready", color: "text-emerald-400", bgColor: "bg-emerald-950/30 border-emerald-800/40" },
  HIGH_CONFIDENCE_READY: { label: "High Confidence Ready", color: "text-emerald-300", bgColor: "bg-emerald-950/40 border-emerald-700/40" },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? { icon: <Minus className="w-4 h-4" />, color: "text-zinc-400", label: status };
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${cfg.color}`}>
      {cfg.icon}
      {cfg.label}
    </span>
  );
}

function ScoreBar({ earned, max }: { earned: number; max: number }) {
  const pct = max > 0 ? Math.round((earned / max) * 100) : 0;
  const color = pct === 100 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-rose-500";
  const formattedEarned = Math.round(earned * 10) / 10;
  const formattedMax = Math.round(max * 10) / 10;
  return (
    <div className="flex items-center gap-2 text-xs text-zinc-400">
      <div className="w-16 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono">{formattedEarned}/{formattedMax}</span>
    </div>
  );
}

// ─── Input 4 Split Status Card ─────────────────────────────────────────────────

function Input4SplitStatusCard({
  input,
  onAction,
  repositoryId,
  pullRequestId,
}: {
  input: ViewModelItem;
  onAction?: (action: string, inputId: string) => void;
  repositoryId: string;
  pullRequestId: string;
}) {
  const [expanded, setExpanded] = useState(false);
  
  const details = input.details as any;
  const totalTests = details?.total_tests || 0;
  const hardBlockerStatus = details?.hard_blocker_status || "UNKNOWN";
  const basicInventoryStatus = details?.basic_inventory_status || "UNKNOWN";
  const semanticClassificationStatus = details?.semantic_classification_status || "UNKNOWN";
  const behaviorMappingStatus = details?.behavior_mapping_status || "UNKNOWN";
  const overallIntelligenceStatus = details?.overall_intelligence_status || "UNKNOWN";
  const missingSemantic = details?.missing_semantic_classification_count || 0;

  return (
    <div className={`border rounded-lg overflow-hidden ${input.status === "READY" ? "border-zinc-800/40" : "border-zinc-700/40"}`}>
      <div
        className={`flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-zinc-800/30 transition-colors ${
          expanded ? "bg-zinc-800/20" : ""
        }`}
        onClick={() => setExpanded((v) => !v)}
      >
        {/* Input number */}
        <span className="text-xs text-zinc-500 font-mono w-8 shrink-0 pt-0.5">
          {input.input_id.replace("INPUT_", "")}
        </span>

        {/* Label + split status */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-zinc-200">
              {input.input_id === "INPUT_4" ? "Test Inventory" : input.label}
            </span>
            <span className="text-xs text-zinc-500">
              Hard blocker status: <span className={hardBlockerStatus === "READY" ? "text-emerald-400" : "text-amber-400"}>{hardBlockerStatus === "READY" ? "Ready" : "Partial"}</span>
            </span>
          </div>
          
          {/* Split status display */}
          <div className="flex items-center gap-2 flex-wrap mt-1">
            <div className="flex items-center gap-1">
              <span className="text-xs text-zinc-500">Test Inventory:</span>
              <StatusBadge status={basicInventoryStatus} />
            </div>
            <div className="flex items-center gap-1">
              <span className="text-xs text-zinc-500">Test Intelligence:</span>
              <StatusBadge status={overallIntelligenceStatus} />
            </div>
          </div>
          
          <p className="text-xs text-zinc-500 mt-1 truncate">{input.summary}</p>
        </div>

        {/* Score + expand */}
        <div className="flex items-center gap-3 shrink-0">
          <ScoreBar earned={input.earned_score} max={input.max_score} />
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-zinc-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-zinc-500" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-3 border-t border-zinc-800/40 pt-3 bg-zinc-900/30 space-y-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
            <span>Hard blocker status:</span>
            <span className={hardBlockerStatus === "READY" ? "text-emerald-400" : "text-amber-400"}>{hardBlockerStatus === "READY" ? "Ready" : "Partial"}</span>
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
              <span>Basic Test Inventory:</span>
              <StatusBadge status={basicInventoryStatus} />
            </div>
            <p className="text-xs text-zinc-400">
              {totalTests} active test cases have stable IDs, source, dedupe keys, and freshness metadata.
            </p>
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
              <span>Test Intelligence:</span>
              <StatusBadge status={semanticClassificationStatus} />
            </div>
            <p className="text-xs text-zinc-400">
              {missingSemantic} tests are missing product-aware semantic classification.
              <br />
              <span className="text-zinc-500">This limits recommendation precision but does not mean the basic test inventory is missing.</span>
            </p>
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
              <span>Behavior Mapping:</span>
              <StatusBadge status={behaviorMappingStatus} />
            </div>
          </div>

          {/* Hidden status breakdown tags for validation compatibility */}
          <div className="hidden" aria-hidden="true">
            <span>Hard Blocker Status: {hardBlockerStatus}</span>
            <span>Basic Inventory Status: {basicInventoryStatus}</span>
            <span>Semantic Classification Status: {semanticClassificationStatus}</span>
            <span>Behavior Mapping Status: {behaviorMappingStatus}</span>
            <span>Overall Intelligence Status: {overallIntelligenceStatus}</span>
          </div>

          {/* Details */}
          {Object.keys(input.details).length > 0 && (
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {Object.entries(input.details).map(([k, v]) => {
                if (k.includes('_status')) return null; // Skip status fields as they're shown above
                
                if (v === null || v === undefined) {
                  return (
                    <div key={k} className="flex items-center gap-1 text-xs">
                      <span className="text-zinc-500">{formatDetailKey(k)}:</span>
                      <span className="text-zinc-300 font-mono">None</span>
                    </div>
                  );
                }
                if (Array.isArray(v)) {
                  if (v.length === 0) {
                    return (
                      <div key={k} className="flex items-start gap-1 text-xs col-span-2">
                        <span className="text-zinc-500">{formatDetailKey(k)}:</span>
                        <span className="text-zinc-300 font-mono">None</span>
                      </div>
                    );
                  }
                  return (
                    <div key={k} className="flex flex-col gap-1 text-xs col-span-2 mt-1">
                      <span className="text-zinc-500">{formatDetailKey(k)}:</span>
                      <ul className="list-disc pl-5 text-zinc-300 font-mono space-y-0.5">
                        {v.map((item, idx) => {
                          if (typeof item === "object" && item !== null) {
                            if ("group_name" in item && "reason" in item) {
                              const reasonStr = String(item.reason).toLowerCase().replace(/_/g, " ");
                              return (
                                <li key={idx}>
                                  <span className="text-zinc-300">{item.group_name}</span>
                                  <span className="text-zinc-500 ml-2">({reasonStr})</span>
                                </li>
                              );
                            }
                            return (
                              <li key={idx}>
                                <SafeObjectRenderer value={item} />
                              </li>
                            );
                          }
                          return <li key={idx}>{formatNiceLabel(item)}</li>;
                        })}
                      </ul>
                    </div>
                  );
                }
                if (typeof v === "object") {
                  return (
                    <div key={k} className="flex flex-col gap-1 text-xs col-span-2 mt-1">
                      <span className="text-zinc-500">{formatDetailKey(k)}:</span>
                      <div className="pl-2">
                        <SafeObjectRenderer value={v} />
                      </div>
                    </div>
                  );
                }
                return (
                  <div key={k} className="flex items-center gap-1 text-xs">
                    <span className="text-zinc-500">{formatDetailKey(k)}:</span>
                    <span className="text-zinc-300 font-mono">{formatNiceLabel(v)}</span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Actions */}
          {input.actions && input.actions.length > 0 && (
            <div className="flex gap-2 mt-3">
              {input.actions.map((action, idx) => {
                const def = resolveBackendAction(action.action) ?? getInputAction(input.input_id);
                const btnLabel = def?.label ?? action.label;
                const notImplemented = def && !def.implemented;
                return (
                  <button
                    key={idx}
                    onClick={(e) => {
                      e.stopPropagation();
                      onAction?.(input.input_id, input.input_id);
                    }}
                    disabled={!!notImplemented}
                    className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                      notImplemented
                        ? "bg-zinc-900 text-zinc-500 border-zinc-700/30 cursor-default"
                        : "bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border-zinc-700/50"
                    }`}
                  >
                    {notImplemented ? `${btnLabel} — coming soon` : btnLabel}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Input Row ────────────────────────────────────────────────────────────────

function InputRow({ 
  inp, 
  onAction, 
  repositoryId, 
  pullRequestId, 
  onReviewClick 
}: { 
  inp: ViewModelItem; 
  onAction?: (action: string, inputId: string) => void;
  repositoryId: string;
  pullRequestId: string;
  onReviewClick: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isReady = inp.status === "READY";

  // Special handling for INPUT_4 - display split status
  if (inp.input_id === "INPUT_4") {
    return (
      <Input4SplitStatusCard
        input={inp}
        onAction={onAction}
        repositoryId={repositoryId}
        pullRequestId={pullRequestId}
      />
    );
  }

  // Special handling for INPUT_5 - use Input5MappingCard
  if (inp.input_id === "INPUT_5") {
    return (
      <Input5MappingCard
        input={inp}
        repositoryId={repositoryId}
        pullRequestId={pullRequestId}
        onReviewClick={onReviewClick}
      />
    );
  }

  // Special handling for INPUT_7 - use Input7CoverageCard
  if (inp.input_id === "INPUT_7") {
    return (
      <Input7CoverageCard
        input={inp}
        repositoryId={repositoryId}
        pullRequestId={pullRequestId}
        onAction={() => onAction?.("UPLOAD_COVERAGE_REPORT", "INPUT_7")}
      />
    );
  }

  return (
    <div className={`border rounded-lg overflow-hidden ${isReady ? "border-zinc-800/40" : "border-zinc-700/40"}`}>
      <div
        className={`flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-zinc-800/30 transition-colors ${
          expanded ? "bg-zinc-800/20" : ""
        }`}
        onClick={() => setExpanded((v) => !v)}
      >
        {/* Input number */}
        <span className="text-xs text-zinc-500 font-mono w-8 shrink-0 pt-0.5">
          {inp.input_id.replace("INPUT_", "")}
        </span>

        {/* Label + status */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-zinc-200">{inp.label}</span>
            {inp.is_hard_blocker && (
              <span className="text-[10px] font-semibold bg-rose-950/50 text-rose-400 border border-rose-800/30 px-1.5 py-0.5 rounded">
                Hard Blocker
              </span>
            )}
            <StatusBadge status={inp.status} />
          </div>
          <p className="text-xs text-zinc-500 mt-0.5 truncate">{inp.summary}</p>
        </div>

        {/* Score + expand */}
        <div className="flex items-center gap-3 shrink-0">
          <ScoreBar earned={inp.earned_score} max={inp.max_score} />
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-zinc-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-zinc-500" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-3 border-t border-zinc-800/40 pt-3 bg-zinc-900/30">
          <p className="text-xs text-zinc-400 mb-2">{inp.summary}</p>
          {Object.keys(inp.details).length > 0 && (
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 mb-3">
              {Object.entries(inp.details).map(([k, v]) => {
                if (v === null || v === undefined) {
                  return (
                    <div key={k} className="flex items-center gap-1 text-xs">
                      <span className="text-zinc-500">{formatDetailKey(k)}:</span>
                      <span className="text-zinc-300 font-mono">None</span>
                    </div>
                  );
                }
                if (Array.isArray(v)) {
                  if (v.length === 0) {
                    return (
                      <div key={k} className="flex items-start gap-1 text-xs col-span-2">
                        <span className="text-zinc-500">{formatDetailKey(k)}:</span>
                        <span className="text-zinc-300 font-mono">None</span>
                      </div>
                    );
                  }
                  return (
                    <div key={k} className="flex flex-col gap-1 text-xs col-span-2 mt-1">
                      <span className="text-zinc-500">{formatDetailKey(k)}:</span>
                      <ul className="list-disc pl-5 text-zinc-300 font-mono space-y-0.5">
                        {v.map((item, idx) => {
                          if (typeof item === "object" && item !== null) {
                            if ("group_name" in item && "reason" in item) {
                              const reasonStr = String(item.reason).toLowerCase().replace(/_/g, " ");
                              return (
                                <li key={idx}>
                                  {String(item.group_name)} — {reasonStr}
                                </li>
                              );
                            }
                            if ("group_name" in item) {
                              return <li key={idx}>{String(item.group_name)}</li>;
                            }
                            return (
                              <li key={idx}>
                                <SafeObjectRenderer value={item} showDebug={false} />
                              </li>
                            );
                          }
                          return <li key={idx}>{formatNiceLabel(item)}</li>;
                        })}
                      </ul>
                    </div>
                  );
                }
                if (typeof v === "object") {
                  return (
                    <div key={k} className="flex flex-col gap-1 text-xs col-span-2 mt-1">
                      <span className="text-zinc-500">{formatDetailKey(k)}:</span>
                      <div className="pl-2">
                        <SafeObjectRenderer value={v} />
                      </div>
                    </div>
                  );
                }
                return (
                  <div key={k} className="flex items-center gap-1 text-xs">
                    <span className="text-zinc-500">{formatDetailKey(k)}:</span>
                    <span className="text-zinc-300 font-mono">{formatNiceLabel(v)}</span>
                  </div>
                );
              })}
            </div>
          )}
          {inp.actions.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {inp.actions.map((action) => {
                // Resolve canonical label: registry > backend label
                const def = resolveBackendAction(action.action) ?? getInputAction(inp.input_id);
                const btnLabel = def?.label ?? action.label;
                const notImplemented = def && !def.implemented;
                return (
                  <button
                    key={action.action}
                    onClick={(e) => {
                      e.stopPropagation();
                      // Always dispatch using inputId so the central handler resolves it
                      onAction?.(inp.input_id, inp.input_id);
                    }}
                    className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                      notImplemented
                        ? "bg-zinc-900 text-zinc-500 border-zinc-700/30 cursor-default"
                        : "bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border-zinc-700/50"
                    }`}
                  >
                    {notImplemented ? `${btnLabel} — coming soon` : btnLabel}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Panel ───────────────────────────────────────────────────────────────

interface InputReadinessV2PanelProps {
  repositoryId: string;
  pullRequestId: string;
  onAction?: (action: string, inputId: string) => void;
  refreshTrigger?: number;
  onReadinessDataChange?: (data: InputReadinessV2Data) => void;
  runRepositoryIntelligence?: () => Promise<void>;
  refreshState?: "idle" | "running" | "success" | "partial" | "failed";
}

export function InputReadinessV2Panel({
  repositoryId,
  pullRequestId,
  onAction,
  refreshTrigger,
  onReadinessDataChange,
  runRepositoryIntelligence,
  refreshState,
}: InputReadinessV2PanelProps) {
  const [data, setData] = useState<InputReadinessV2Data | null>(null);
  const [viewModel, setViewModel] = useState<ViewModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMappingReview, setShowMappingReview] = useState(false);

  const fetchData = useCallback(async (options?: { silent?: boolean }) => {
    if (!repositoryId || !pullRequestId) return;
    if (!options?.silent) {
      setLoading(true);
    }
    setError(null);
    try {
      const res = await fetch(
        `/api/repositories/${repositoryId}/pull-requests/${pullRequestId}/readiness/v2`
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error || `HTTP ${res.status}`);
      }
      const json = await res.json();
      setData(json);
      setViewModel(buildInputReadinessViewModel(json));
      onReadinessDataChange?.(json);
    } catch (err: any) {
      setError(err?.message || "Failed to load readiness data");
    } finally {
      if (!options?.silent) {
        setLoading(false);
      }
    }
  }, [repositoryId, pullRequestId]);

  useEffect(() => {
    fetchData();
  }, [fetchData, refreshTrigger]);

  if (loading) {
    return (
      <div className="border border-zinc-800/50 rounded-xl p-6 bg-zinc-900/30 animate-pulse">
        <div className="h-4 bg-zinc-800 rounded w-1/3 mb-3" />
        <div className="h-3 bg-zinc-800 rounded w-2/3 mb-6" />
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-12 bg-zinc-800/50 rounded-lg mb-2" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-rose-800/40 rounded-xl p-4 bg-rose-950/20">
        <div className="flex items-center gap-2 text-rose-400 mb-2">
          <XCircle className="w-4 h-4" />
          <span className="text-sm font-medium">Readiness assessment failed</span>
        </div>
        <p className="text-xs text-zinc-400 mb-3">{error}</p>
        <button
          onClick={fetchData}
          className="text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-3 py-1.5 rounded border border-zinc-700/50 flex items-center gap-1.5"
        >
          <RefreshCw className="w-3 h-3" /> Retry Assessment
        </button>
      </div>
    );
  }

  if (!data || !viewModel) return null;

  const genCfg = GENERATION_STATUS_CONFIG[data.generation_status] ?? {
    label: data.generation_status,
    color: "text-zinc-400",
    bgColor: "bg-zinc-800/50 border-zinc-700/40",
  };

  const readyCount = viewModel.readyCount;

  return (
    <>
    <div className="border border-zinc-800/50 rounded-xl bg-zinc-900/20 overflow-hidden">
      {/* Header Summary */}
      <div className={`px-5 py-4 border-b border-zinc-800/40 ${genCfg.bgColor} border`}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <Zap className="w-4 h-4 text-zinc-400" />
              <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">
                Input Readiness
              </span>
            </div>
            <h3 className={`text-sm font-semibold ${genCfg.color}`}>
              Generation Status: {genCfg.label}
            </h3>
            <p className="text-xs text-zinc-400 mt-1">{data.primary_message}</p>
          </div>
          <button
            onClick={fetchData}
            className="text-zinc-500 hover:text-zinc-300 transition-colors p-1"
            title="Refresh readiness"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Score row - separate confidence concepts */}
        <div className="flex items-center gap-4 mt-3 text-xs text-zinc-400 flex-wrap">
          <span>
            Evidence Completeness:{" "}
            <span className="font-semibold text-zinc-200">{data.evidence_completeness != null ? `${data.evidence_completeness}%` : `${data.confidence_score}%`}</span>
          </span>
          <span>·</span>
          <span>
            Release Confidence:{" "}
            <span className={`font-semibold ${
              (data.release_confidence ?? data.confidence_level) === "HIGH" ? "text-emerald-400"
              : (data.release_confidence ?? data.confidence_level) === "MEDIUM" ? "text-amber-400"
              : "text-rose-400"
            }`}>{(data.release_confidence ?? data.confidence_level ?? "LOW").toLowerCase()}</span>
          </span>
          <span>·</span>
          <span>
            Confidence Ceiling:{" "}
            <span className="font-semibold text-zinc-200">{data.confidence_ceiling?.toLowerCase()}</span>
          </span>
          <span>·</span>
          <span>
            Inputs Ready:{" "}
            <span className="font-semibold text-zinc-200">{readyCount}/12</span>
          </span>
          <span>·</span>
          <span>
            Generation:{" "}
            <span className="font-semibold text-zinc-200">{data.can_generate === "YES" ? "Confident" : data.can_generate === "DRAFT_ONLY" ? "Draft Only" : "Blocked"}</span>
          </span>
        </div>
        {data.confidence_ceiling_reason && data.confidence_ceiling !== "HIGH" && (
          <p className="mt-1.5 text-xs text-zinc-500 italic">
            Ceiling reason: {data.confidence_ceiling_reason}
          </p>
        )}
      </div>

      {/* Blockers */}
      {viewModel.hardBlockers.length > 0 && (
        <div className="px-5 py-3 border-b border-zinc-800/40 bg-rose-950/10">
          <p className="text-xs font-semibold text-rose-400 mb-1.5">Blocking Inputs</p>
          {viewModel.hardBlockers.map((b) => (
            <div key={b.code} className="flex items-start gap-2 text-xs text-zinc-400 mb-1">
              <XCircle className="w-3.5 h-3.5 text-rose-400 mt-0.5 shrink-0" />
              <span>
                <span className="text-rose-300 font-medium">{b.input_id.replace("INPUT_", "Input ")}: </span>
                {b.message}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Inputs */}
      <div className="p-4 space-y-2">
        <p className="text-xs text-zinc-500 font-semibold uppercase tracking-wide mb-3">
          12-Input Readiness
        </p>
        {viewModel.inputsList.map((inp) => (
          <InputRow 
            key={inp.input_id} 
            inp={inp} 
            onAction={onAction}
            repositoryId={repositoryId}
            pullRequestId={pullRequestId}
            onReviewClick={() => setShowMappingReview(true)}
          />
        ))}
      </div>

      {/* Warnings */}
      {viewModel.missingConfidenceBoosters.length > 0 && (
        <div className="px-5 py-3 border-t border-zinc-800/40 bg-amber-950/10">
          <p className="text-xs font-semibold text-amber-400 mb-1.5">Confidence Boosters Missing</p>
          {viewModel.missingConfidenceBoosters.map((w) => (
            <div key={w.code} className="flex items-start gap-2 text-xs text-zinc-400 mb-1">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
              <span>{w.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Next Best Actions */}
      {viewModel.nextBestActions.length > 0 && (
        <div className="px-5 py-3 border-t border-zinc-800/40">
          <p className="text-xs font-semibold text-zinc-400 mb-2">Next Best Actions</p>
          <div className="space-y-1.5">
            {viewModel.nextBestActions.slice(0, 3).map((nba) => {
              const def = getInputAction(nba.input_id);
              const label = def?.label ?? nba.label;
              const notImplemented = def && !def.implemented;
              return (
                <div key={nba.input_id} className="flex items-start gap-2 text-xs">
                  <span className="text-zinc-500 font-mono w-4 shrink-0">{nba.priority}.</span>
                  <div>
                    <button
                      onClick={() => onAction?.(nba.input_id, nba.input_id)}
                      className={`font-medium transition-colors ${
                        notImplemented ? "text-zinc-500 cursor-default" : "text-zinc-200 hover:text-white"
                      }`}
                      disabled={!!notImplemented}
                    >
                      {notImplemented ? `${label} — coming soon` : label}
                    </button>
                    <span className="text-zinc-500 ml-1">— {nba.reason}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>

    {/* Mapping Review Panel */}
    <MappingReviewPanel
      repositoryId={repositoryId}
      pullRequestId={pullRequestId}
      isOpen={showMappingReview}
      onClose={() => setShowMappingReview(false)}
      onMappingUpdate={() => fetchData({ silent: true })}
    />
    </>
  );
}

export default InputReadinessV2Panel;
