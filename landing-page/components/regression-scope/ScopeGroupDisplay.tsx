import React, { useState } from "react";
import { ChevronDown, ChevronRight, Table, History, Shield, Clock, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import { ScopeGroup, ScopeItem } from "../../types/regression-scope-v2";
import { SCOPE_GROUP_STYLES } from "./scopeGroupStyles";

export type ScopeGroupDisplayProps = {
  title: string;
  description?: string;
  group: ScopeGroup;
  items: ScopeItem[];
  emptyMessage?: string;
  auditMode?: boolean;
  compact?: boolean;
  onOpenHistory?: (item: any) => void;
};

export const ScopeGroupDisplay: React.FC<ScopeGroupDisplayProps> = ({
  title,
  description,
  group,
  items,
  emptyMessage = "No items found in this category.",
  auditMode = false,
  compact = false,
  onOpenHistory,
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const styles = SCOPE_GROUP_STYLES[group] || SCOPE_GROUP_STYLES[ScopeGroup.OPTIONAL];

  const getRiskColor = (level: string) => {
    switch (level) {
      case "CRITICAL":
        return "bg-rose-500/10 text-rose-450 border-rose-500/20";
      case "HIGH":
        return "bg-orange-500/10 text-orange-400 border-orange-500/20";
      case "MEDIUM":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "LOW":
        return "bg-blue-500/10 text-blue-450 border-blue-500/20";
      default:
        return "bg-zinc-500/10 text-zinc-400 border-zinc-500/20";
    }
  };

  const getImpactColor = (level: string) => {
    switch (level) {
      case "DIRECT":
        return "bg-rose-500/10 text-rose-450 border-rose-500/25";
      case "RELATED":
        return "bg-amber-500/10 text-amber-450 border-amber-500/25";
      case "INDIRECT":
        return "bg-zinc-800 text-zinc-400 border-zinc-700/50";
      default:
        return "bg-zinc-900 text-zinc-500 border-zinc-800";
    }
  };

  return (
    <div className="border border-zinc-800/60 rounded-xl overflow-hidden bg-zinc-950/10">
      {/* Group Header Toggle */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-zinc-900/40 hover:bg-zinc-900/60 transition-colors border-b border-zinc-850"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <span className={`w-2 h-2 rounded-full ${styles.textClass} bg-current`} />
          <h3 className="text-xs font-semibold text-zinc-250 truncate">{title}</h3>
          <span className="text-[10px] font-mono font-bold bg-zinc-900 text-zinc-450 px-1.5 py-0.2 rounded border border-zinc-800">
            {items.length}
          </span>
        </div>
        <div className="flex items-center gap-2 text-zinc-500">
          {description && !compact && <span className="text-[11px] text-zinc-550 italic hidden md:inline">{description}</span>}
          {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </div>
      </button>

      {/* Group Items */}
      {isOpen && (
        <div className="p-4 space-y-3">
          {items.length === 0 ? (
            <div className="text-center py-6 text-xs text-zinc-500 italic bg-zinc-900/10 border border-dashed border-zinc-800/40 rounded-lg">
              {emptyMessage}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {items.map((item) => {
                const isOverridden = item.effective_risk_level && item.effective_risk_level !== item.business_risk_level;
                
                return (
                  <div
                    key={item.id}
                    className={`bg-zinc-900/20 border border-zinc-850 rounded-lg transition-all hover:bg-zinc-900/40 ${
                      compact ? "p-3" : "p-4"
                    }`}
                  >
                    {/* Item Header */}
                    <div className="flex items-start justify-between gap-3 mb-2 flex-wrap sm:flex-nowrap">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[11px] font-mono font-bold text-zinc-400">{item.readable_id}</span>
                        {onOpenHistory && item.businessRiskReview && (
                          <button
                            type="button"
                            className="text-[9px] h-5 w-5 p-0 text-zinc-405 hover:text-zinc-200 inline-flex items-center justify-center rounded hover:bg-zinc-800 transition-colors"
                            onClick={() => onOpenHistory(item)}
                            title="View review history"
                          >
                            <History className="w-3 h-3" />
                          </button>
                        )}
                        {item.businessRiskReview && item.businessRiskReview.reviewStatus && item.businessRiskReview.reviewStatus !== 'UNREVIEWED' && (
                          <span className={`text-[9px] font-medium px-1.5 py-0.2 rounded border ${
                            item.businessRiskReview.reviewStatus === 'ACCEPTED' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                            item.businessRiskReview.reviewStatus === 'OVERRIDDEN' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                            item.businessRiskReview.reviewStatus === 'NEEDS_DISCUSSION' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                            'bg-zinc-500/10 text-zinc-400 border-zinc-500/20'
                          }`}>
                            {item.businessRiskReview.reviewStatus}
                          </span>
                        )}
                        {item.businessRiskReview && item.businessRiskReview.reviewStatus && item.businessRiskReview.reviewStatus !== 'UNREVIEWED' ? (
                          item.businessRiskReview.effectivePriority && (
                            <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-zinc-800/50 text-zinc-350 border border-zinc-700/50">
                              {item.businessRiskReview.effectivePriority}
                            </span>
                          )
                        ) : item.businessContext && item.businessContext.priority && (
                          <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-zinc-800/50 text-zinc-350 border border-zinc-700/50">
                            {item.businessContext.priority}
                          </span>
                        )}
                        {item.item_type === "MANUAL_TEST" ? (
                          <span
                            data-testid="manual-test-badge"
                            className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.2 rounded bg-violet-500/10 text-violet-300 border border-violet-500/30"
                          >
                            Manual Test
                          </span>
                        ) : (
                          <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.2 rounded bg-zinc-800/50 text-zinc-450 border border-zinc-700/50">
                            {item.item_type}
                          </span>
                        )}

                        {item.item_type === "MANUAL_TEST" && item.can_auto_execute === false && (
                          <span
                            data-testid="manual-cannot-autorun"
                            className="text-[9px] font-medium px-1.5 py-0.2 rounded border border-amber-500/25 bg-amber-500/10 text-amber-300"
                          >
                            Manual only - cannot auto-run
                          </span>
                        )}
                        
                        {/* Risk Band / Priority */}
                        <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded border ${getRiskColor(item.risk_band)}`}>
                          {item.risk_band}
                        </span>

                        {/* Phase 6.4: Manual evidence risk adjustment indicator */}
                        {item.manual_contribution_status && item.generated_risk_band && item.residual_risk_band && (
                          <>
                            {item.risk_adjustment_delta && item.risk_adjustment_delta !== 0 && (
                              <span className={`text-[9px] font-medium px-1.5 py-0.2 rounded border ${
                                item.risk_adjustment_delta < 0
                                  ? 'bg-green-500/10 text-green-400 border-green-500/20'
                                  : 'bg-red-500/10 text-red-400 border-red-500/20'
                              }`}>
                                {item.risk_adjustment_delta < 0 ? '↓' : '↑'} {Math.abs(item.risk_adjustment_delta)} band
                              </span>
                            )}
                            <span className="text-[9px] font-medium px-1.5 py-0.2 rounded border border-zinc-700/50 bg-zinc-800/40 text-zinc-400">
                              Manual: {item.manual_contribution_status}
                            </span>

                            {/* Phase 6.5B: Governance status badge */}
                            {item.governanceStatus && (
                              <span className={`text-[9px] font-medium px-1.5 py-0.2 rounded border ${
                                item.governanceStatus === 'APPROVED'
                                  ? 'bg-green-500/10 text-green-400 border-green-500/20'
                                  : item.governanceStatus === 'PENDING_REVIEW'
                                  ? 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20'
                                  : item.governanceStatus === 'REJECTED'
                                  ? 'bg-red-500/10 text-red-400 border-red-500/20'
                                  : item.governanceStatus === 'CHALLENGED'
                                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                                  : 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20'
                              }`}>
                                {item.governanceStatus}
                              </span>
                            )}
                          </>
                        )}

                        {/* Change Impact */}
                        {item.change_impact_level && (
                          <span className={`text-[9px] font-medium px-1.5 py-0.2 rounded border ${getImpactColor(item.change_impact_level)}`}>
                            Impact: {item.change_impact_level}
                          </span>
                        )}

                        {/* Governance status or overridden badge */}
                        {isOverridden && (
                          <span className="text-[9px] font-medium px-1.5 py-0.2 rounded border border-purple-500/20 bg-purple-950/20 text-purple-400">
                            Overridden ({item.business_risk_level} &rarr; {item.effective_risk_level})
                          </span>
                        )}
                      </div>

                      {/* Right aligned status or tags */}
                      {item.execution_status && (
                        <span className="text-[10px] text-zinc-500 italic">{item.execution_status}</span>
                      )}
                    </div>

                    {/* Title */}
                    <h4 className="text-xs font-semibold text-zinc-200 mb-2 leading-relaxed">{item.title}</h4>

                    {/* Manual Test details */}
                    {item.item_type === "MANUAL_TEST" && (
                      <div data-testid="manual-test-meta" className="flex items-center gap-2 flex-wrap mb-2 text-[10px]">
                        {item.execution_status && (
                          <span data-testid="manual-execution-status" className="px-1.5 py-0.2 rounded border border-zinc-700/50 bg-zinc-800/40 text-zinc-300 font-mono">
                            Status: {item.execution_status}
                          </span>
                        )}
                        {item.estimated_effort && (
                          <span data-testid="manual-estimated-effort" className="px-1.5 py-0.2 rounded border border-zinc-700/50 bg-zinc-800/40 text-zinc-300 font-mono">
                            Effort: {item.estimated_effort}
                          </span>
                        )}
                        {item.provider && (
                          <span data-testid="manual-provider" className="px-1.5 py-0.2 rounded border border-zinc-700/50 bg-zinc-800/40 text-zinc-400 font-mono">
                            Provider: {item.provider}
                          </span>
                        )}
                        {item.external_id && (
                          <span data-testid="manual-external-id" className="px-1.5 py-0.2 rounded border border-zinc-700/50 bg-zinc-800/40 text-zinc-400 font-mono">
                            {item.external_id}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Phase 6.5B: Governance warning when manual contribution exists but not approved */}
                    {item.manual_contribution_status && item.governanceStatus && item.governanceStatus !== 'APPROVED' && (
                      <div className="flex items-start gap-2 p-2 bg-amber-500/5 border border-amber-500/10 rounded text-[10px] text-amber-500/80 leading-relaxed mb-2">
                        <Shield className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                        <span>Manual risk adjustment blocked pending governance approval. Current status: {item.governanceStatus}</span>
                      </div>
                    )}

                    {/* Meta Details Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs mb-3">
                      {item.suggested_action && (
                        <div className="space-y-1">
                          <span className="text-[10px] text-zinc-550 uppercase tracking-wider block font-semibold">Suggested Action</span>
                          <p className="text-zinc-300 font-sans leading-snug">{item.suggested_action}</p>
                        </div>
                      )}
                      {item.reason && (
                        <div className="space-y-1">
                          <span className="text-[10px] text-zinc-550 uppercase tracking-wider block font-semibold">Reason</span>
                          <p className="text-zinc-400 font-sans leading-snug">{item.reason}</p>
                        </div>
                      )}
                    </div>

                    {/* References & Evidence */}
                    {(item.evidence_references?.length > 0 || item.test_references?.length > 0) && (
                      <div className="flex flex-col gap-2 mt-2 pt-2.5 border-t border-zinc-800/40">
                        {item.evidence_references?.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-[9px] text-zinc-500 uppercase font-semibold">Evidence:</span>
                            {item.evidence_references.map((ref, i) => (
                              <span
                                key={i}
                                className="font-mono text-[9px] bg-zinc-950/50 text-zinc-450 border border-zinc-850 px-1.5 py-0.2 rounded"
                              >
                                {ref}
                              </span>
                            ))}
                          </div>
                        )}
                        {item.test_references?.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-[9px] text-zinc-500 uppercase font-semibold">Linked Tests:</span>
                            {item.test_references.map((ref, i) => (
                              <span
                                key={i}
                                className="font-mono text-[9px] bg-zinc-950/50 text-zinc-450 border border-zinc-850 px-1.5 py-0.2 rounded"
                              >
                                {ref}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Business Context Explainability */}
                    {item.businessContext && (
                      <div className="mt-2 pt-2 border-t border-zinc-800/40 space-y-1.5 text-[11px]">
                        {item.businessContext.businessImpact && (
                          <div>
                            <span className="text-zinc-500 font-semibold uppercase tracking-wider text-[9px] block font-sans">Why this matters</span>
                            <span className="text-zinc-300">{item.businessContext.businessImpact}</span>
                            {item.businessContext.userImpact && <span className="text-zinc-400 font-sans"> ({item.businessContext.userImpact})</span>}
                          </div>
                        )}
                        {item.businessContext.riskReasons && item.businessContext.riskReasons.length > 0 && (
                          <div>
                            <span className="text-zinc-500 font-semibold uppercase tracking-wider text-[9px] block font-sans">Risk reasons</span>
                            <ul className="list-disc list-inside text-zinc-450 pl-1 space-y-0.5 font-sans">
                              {item.businessContext.riskReasons.map((reason, idx) => (
                                <li key={idx}>{reason}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {item.businessContext.whatWouldMakeReleaseSafe && (
                          <div>
                            <span className="text-zinc-500 font-semibold uppercase tracking-wider text-[9px] block font-sans">What would make this safe</span>
                            <span className="text-emerald-400">{item.businessContext.whatWouldMakeReleaseSafe}</span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Review Note */}
                    {item.businessRiskReview?.reviewNote && (
                      <div className="mt-2 p-2 rounded bg-zinc-950/40 border border-zinc-805 text-[11px] text-zinc-300 font-sans">
                        <strong>Review Note:</strong> {item.businessRiskReview.reviewNote}
                        {item.businessRiskReview.reviewerName && <span className="text-zinc-500 block text-[9px] mt-0.5 font-sans">by {item.businessRiskReview.reviewerName}</span>}
                      </div>
                    )}

                    {/* Audit Mode Information */}
                    {auditMode && (
                      <div className="mt-3 pt-2.5 border-t border-dashed border-zinc-800/50 space-y-1.5 font-mono text-[10px] text-zinc-500">
                        <div>
                          <span className="text-zinc-600 font-semibold">Internal ID:</span> {item.id}
                        </div>
                        {item.diagnostics && (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                            {item.diagnostics.internal_requirement_id && (
                              <div>
                                <span className="text-zinc-600 font-semibold">Req ID:</span> {item.diagnostics.internal_requirement_id}
                              </div>
                            )}
                            {item.diagnostics.internal_test_id && (
                              <div>
                                <span className="text-zinc-600 font-semibold">Test ID:</span> {item.diagnostics.internal_test_id}
                              </div>
                            )}
                            {item.diagnostics.generation_rule && (
                              <div>
                                <span className="text-zinc-600 font-semibold">Rule:</span> {item.diagnostics.generation_rule}
                              </div>
                            )}
                            {item.diagnostics.confidence_score !== undefined && (
                              <div>
                                <span className="text-zinc-600 font-semibold">Confidence:</span> {item.diagnostics.confidence_score.toFixed(2)}
                              </div>
                            )}
                            {item.diagnostics.last_updated && (
                              <div>
                                <span className="text-zinc-600 font-semibold">Updated:</span> {item.diagnostics.last_updated}
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
  );
};
export default ScopeGroupDisplay;
