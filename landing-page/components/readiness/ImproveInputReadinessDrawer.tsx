"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { getInputAction } from "@/lib/readiness/inputActionRegistry";
import {
  buildInputReadinessViewModel,
  InputReadinessViewModel,
  InputReadinessItemViewModel,
  InputReadinessActionViewModel,
} from "@/lib/readiness/inputReadinessAdapter";

// Re-export the V2 data type (defined in InputReadinessV2Panel)
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
}

// Re-export view model types for consumers
type ViewModel = InputReadinessViewModel;
type ViewModelItem = InputReadinessItemViewModel;
type ViewModelAction = InputReadinessActionViewModel;

interface ImproveInputReadinessDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  readinessData: InputReadinessV2Data | null;
  onAction: (inputId: string) => void;
  onGenerate?: () => void;
}

export function ImproveInputReadinessDrawer({
  isOpen,
  onClose,
  readinessData,
  onAction,
  onGenerate,
}: ImproveInputReadinessDrawerProps) {
  const [optionalExpanded, setOptionalExpanded] = useState(false);

  if (!readinessData) return null;

  const viewModel = buildInputReadinessViewModel(readinessData);
  if (!viewModel) return null;

  const { generationStatus, confidenceScore, confidenceLevel, canGenerate, hardBlockers, inputs, nextBestActions } = viewModel;

  // Required actions are hard blockers that are not ready, backed by next-best-actions.
  const requiredActions: ViewModelAction[] = nextBestActions
    .filter((nba) => {
      const inp = inputs[nba.input_id];
      return inp?.is_hard_blocker;
    })
    .slice(0, 4);

  // Optional actions are non-ready, non-hard-blocker inputs (confidence boosters).
  const optionalActions: ViewModelItem[] = Object.values(inputs).filter((i) => !i.is_hard_blocker && i.status !== "READY");

  const topAction = requiredActions[0];
  const topActionDef = topAction ? getInputAction(topAction.input_id) : null;

  const genStatusLabel: Record<string, string> = {
    BLOCKED: "Blocked",
    DRAFT_ONLY: "Draft Only",
    MINIMUM_READY: "Minimum Ready",
    CONFIDENT_READY: "Confident",
    HIGH_CONFIDENCE_READY: "High Confidence",
  };

  const genStatusColor: Record<string, string> = {
    BLOCKED: "text-rose-400",
    DRAFT_ONLY: "text-amber-400",
    MINIMUM_READY: "text-zinc-300",
    CONFIDENT_READY: "text-emerald-400",
    HIGH_CONFIDENCE_READY: "text-emerald-300",
  };

  const explanation = (() => {
    if (generationStatus === "BLOCKED") {
      return "Generation is blocked by missing required inputs. Complete the required actions below to enable generation.";
    }
    if (generationStatus === "DRAFT_ONLY") {
      return "A draft regression plan can be generated now. Add required evidence to generate a confident plan.";
    }
    if (generationStatus === "MINIMUM_READY") {
      return "You can generate a regression plan now. Add optional evidence to improve confidence.";
    }
    if (generationStatus === "CONFIDENT_READY" || generationStatus === "HIGH_CONFIDENCE_READY") {
      return "All required inputs are available. Generate a confident regression plan or add optional boosters.";
    }
    return "Review the inputs below to improve readiness.";
  })();

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed inset-y-0 right-0 w-full max-w-md bg-zinc-950 border-l border-zinc-800/60 z-50 flex flex-col shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-zinc-800/60 bg-zinc-950">
              <div>
                <h2 className="text-lg font-semibold text-white">Improve Input Readiness</h2>
                <div className="flex items-center gap-3 mt-2 text-xs text-zinc-400">
                  <span>
                    Status: <span className={`font-medium ${genStatusColor[generationStatus] ?? "text-zinc-300"}`}>
                      {genStatusLabel[generationStatus] ?? generationStatus}
                    </span>
                  </span>
                  <span>·</span>
                  <span>
                    Confidence: <span className="font-medium text-zinc-200">{Math.round(confidenceScore)}% ({confidenceLevel})</span>
                  </span>
                  <span>·</span>
                  <span>
                    Can generate: <span className="font-medium text-zinc-200">
                      {canGenerate === true ? "Yes" : canGenerate === "DRAFT_ONLY" ? "Draft only" : "No"}
                    </span>
                  </span>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose} className="text-zinc-400 hover:text-white">
                <X className="w-5 h-5" />
              </Button>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Explanation */}
              <div className="bg-zinc-900/20 border border-zinc-800/40 rounded-xl p-4">
                <p className="text-sm text-zinc-300 leading-relaxed">{explanation}</p>
              </div>

              {/* Required Actions */}
              {requiredActions.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-rose-400" />
                    Required for confident generation
                  </h3>
                  <div className="space-y-2">
                    {requiredActions.map((item: any, idx: number) => {
                      const def = getInputAction(item.input_id);
                      const notImplemented = def && !def.implemented;
                      return (
                        <div
                          key={item.input_id}
                          className="bg-zinc-900/10 border border-zinc-800/40 rounded-lg p-3 flex items-start gap-3"
                        >
                          <span className="text-zinc-500 font-mono text-xs w-5 shrink-0 pt-0.5">{idx + 1}.</span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-sm font-medium text-zinc-200 truncate">
                                {def?.label ?? item.label}
                              </span>
                              <span className="text-[10px] font-semibold bg-rose-950/50 text-rose-400 border border-rose-800/30 px-1.5 py-0.5 rounded">
                                Required
                              </span>
                            </div>
                            <p className="text-xs text-zinc-400 mb-2">{def?.description ?? item.reason}</p>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => onAction(item.input_id)}
                              disabled={!!notImplemented}
                              className={`text-xs rounded ${
                                notImplemented
                                  ? "bg-zinc-900 text-zinc-500 border-zinc-700/30 cursor-default"
                                  : "bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border-zinc-700/50"
                              }`}
                            >
                              {notImplemented ? `${def?.label} — coming soon` : def?.label ?? item.label}
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Optional Boosters */}
              {optionalActions.length > 0 && (
                <div className="space-y-3">
                  <button
                    onClick={() => setOptionalExpanded(!optionalExpanded)}
                    className="flex items-center gap-2 text-sm font-semibold text-zinc-400 hover:text-zinc-200 transition-colors"
                  >
                    {optionalExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    Optional confidence boosters
                    <span className="text-xs text-zinc-500">({optionalActions.length})</span>
                  </button>
                  {optionalExpanded && (
                    <div className="space-y-2">
                      {optionalActions.map((inp: ViewModelItem) => {
                        const def = getInputAction(inp.input_id);
                        const notImplemented = def && !def.implemented;
                        return (
                          <div
                            key={inp.input_id}
                            className="bg-zinc-900/10 border border-zinc-800/40 rounded-lg p-3 flex items-start gap-3"
                          >
                            <div className="w-8 h-8 rounded-lg border border-zinc-700 bg-zinc-900/60 flex items-center justify-center shrink-0 mt-0.5">
                              <Sparkles className="w-4 h-4 text-zinc-400" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-sm font-medium text-zinc-200 truncate">
                                  {def?.label ?? inp.label}
                                </span>
                              </div>
                              <p className="text-xs text-zinc-400 mb-2">{def?.description ?? inp.summary}</p>
                              {def?.implemented && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => onAction(inp.input_id)}
                                  className="text-xs rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border-zinc-700/50"
                                >
                                  {def.label}
                                </Button>
                              )}
                              {!def?.implemented && (
                                <span className="text-[10px] text-zinc-500">Coming soon</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Done state */}
              {requiredActions.length === 0 && optionalActions.length === 0 && (
                <div className="bg-emerald-950/10 border border-emerald-800/40 rounded-xl p-4 flex items-start gap-3">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold text-emerald-200">All inputs ready</p>
                    <p className="text-xs text-zinc-400 mt-1">
                      {generationStatus === "HIGH_CONFIDENCE_READY"
                        ? "All required and optional inputs are available."
                        : "All required inputs are available. Generate a confident regression plan."}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between p-6 border-t border-zinc-800/60 bg-zinc-950">
              <div className="text-xs text-zinc-500 font-mono">
                Completeness: {Math.round(confidenceScore)}%
              </div>
              <div className="flex gap-3">
                <Button variant="ghost" onClick={onClose} className="text-zinc-400 hover:text-white">
                  Cancel
                </Button>
                {topActionDef && topActionDef.implemented && requiredActions.length > 0 && (
                  <Button
                    onClick={() => {
                      onAction(topAction.input_id);
                      onClose();
                    }}
                    className="bg-emerald-600 text-white hover:bg-emerald-500 rounded-lg font-semibold"
                  >
                    Continue: {topActionDef.label}
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                )}
                {requiredActions.length === 0 && onGenerate && (
                  <Button
                    onClick={() => {
                      onGenerate();
                      onClose();
                    }}
                    className="bg-emerald-600 text-white hover:bg-emerald-500 rounded-lg font-semibold"
                  >
                    Generate Regression Plan
                  </Button>
                )}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
