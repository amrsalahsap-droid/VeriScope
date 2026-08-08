import React, { useState } from "react";
import { Activity, ShieldAlert } from "lucide-react";
import { RegressionScopeV2, ScopeGroup } from "../../types/regression-scope-v2";
import { ScopeGroupDisplay } from "./ScopeGroupDisplay";
import { ExecutionPlanDisplay } from "./ExecutionPlanDisplay";
import { ScopeModeSelector } from "./ScopeModeSelector";

export interface RegressionScopeV2DisplayProps {
  scope: RegressionScopeV2;
  showSafeToSkip?: boolean;
  showExclusions?: boolean;
  auditMode?: boolean;
  compact?: boolean;
  onModeChange?: (mode: "targeted" | "risk_based" | "full_suite") => void;
  onOpenHistory?: (item: any) => void;
}

export const RegressionScopeV2Display: React.FC<RegressionScopeV2DisplayProps> = ({
  scope,
  showSafeToSkip,
  showExclusions,
  auditMode,
  compact = false,
  onModeChange,
  onOpenHistory,
}) => {
  const [localShowSafeToSkip, setLocalShowSafeToSkip] = useState(false);
  const [localShowExclusions, setLocalShowExclusions] = useState(false);
  const [localAuditMode, setLocalAuditMode] = useState(false);

  const activeShowSafeToSkip = showSafeToSkip !== undefined ? showSafeToSkip : localShowSafeToSkip;
  const activeShowExclusions = showExclusions !== undefined ? showExclusions : localShowExclusions;
  const activeAuditMode = auditMode !== undefined ? auditMode : localAuditMode;

  const rawMode = scope.scope_type?.toLowerCase();
  const currentMode = (rawMode === "full" || rawMode === "full_suite")
    ? "full_suite"
    : (rawMode as "targeted" | "risk_based" | "full_suite") || "targeted";

  const handleModeChange = (mode: "targeted" | "risk_based" | "full_suite") => {
    if (onModeChange) {
      onModeChange(mode);
    }
  };

  React.useEffect(() => {
    if (scope && scope.integrity) {
      console.log("SCOPE_FINAL_INTEGRITY", {
        status: scope.integrity.integrity_status,
        totalUnique: scope.integrity.total_unique_logical_items,
        bucketSum: scope.integrity.bucket_sum,
        errors: scope.integrity.integrity_errors,
        warnings: scope.integrity.integrity_warnings,
        duplicateIdentities: scope.integrity.duplicate_identities
      });
    }
  }, [scope]);

  // Extract items for each group
  const requiredItems = scope.groups?.[ScopeGroup.REQUIRED]?.items || [];
  const reviewNeededItems = scope.groups?.[ScopeGroup.REVIEW_NEEDED]?.items || [];
  const recommendedItems = scope.groups?.[ScopeGroup.RECOMMENDED]?.items || [];
  const optionalItems = scope.groups?.[ScopeGroup.OPTIONAL]?.items || [];
  const safeToSkipItems = scope.groups?.[ScopeGroup.SAFE_TO_SKIP]?.items || [];
  const deferredCoverageDebtItems = scope.groups?.[ScopeGroup.DEFERRED_COVERAGE_DEBT]?.items || [];
  
  const verifiedItems = scope.groups?.[ScopeGroup.EXCLUDED_ALREADY_VERIFIED]?.items 
    || scope.exclusions?.already_verified_items 
    || [];
  const passedItems = scope.groups?.[ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS]?.items 
    || scope.exclusions?.already_passed_test_items 
    || [];

  return (
    <div className={`space-y-6 ${compact ? "p-0" : "max-w-6xl mx-auto p-4"}`}>
      {/* Header Mode Selector & Info */}
      {!compact && (
        <div className="flex flex-col gap-4 bg-zinc-900/10 border border-zinc-800/80 rounded-xl p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                <Activity className="w-5 h-5 text-purple-400 animate-pulse" />
                Regression Scope V2
              </h2>
              {scope.summary && (
                <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed font-sans max-w-3xl">
                  {scope.summary}
                </p>
              )}
            </div>
            {scope.snapshot_hash && (
              <div className="shrink-0 text-right font-mono text-[9px] text-zinc-500 bg-zinc-900/40 px-2 py-1 rounded border border-zinc-850">
                Snapshot: <span className="text-zinc-450">{scope.snapshot_hash.substring(0, 12)}</span>
              </div>
            )}
          </div>

          <div className="pt-4 border-t border-zinc-850">
            <ScopeModeSelector value={currentMode} onChange={handleModeChange} />
          </div>
        </div>
      )}

      {/* Execution Plan & Settings Toolbar */}
      <div className="space-y-4">
        {scope.execution_plan && (
          <ExecutionPlanDisplay executionPlan={scope.execution_plan} compact={compact} verifiedCount={verifiedItems.length} />
        )}

        {/* Toolbar */}
        {!compact && (
          <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-zinc-900/20 border border-zinc-800/80 rounded-xl">
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold text-zinc-300">Consistent Color Palette Settings</span>
              <div className="h-4 w-px bg-zinc-850" />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setLocalShowSafeToSkip(!localShowSafeToSkip)}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-medium border transition-colors ${
                    activeShowSafeToSkip
                      ? "bg-blue-950/30 border-blue-500/50 text-blue-400"
                      : "bg-zinc-900/50 border-zinc-850 text-zinc-400 hover:bg-zinc-800/50"
                  }`}
                >
                  {activeShowSafeToSkip ? "Hide Safe To Skip" : "Show Safe To Skip"}
                </button>
                <button
                  type="button"
                  onClick={() => setLocalShowExclusions(!localShowExclusions)}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-medium border transition-colors ${
                    activeShowExclusions
                      ? "bg-emerald-950/30 border-emerald-500/50 text-emerald-400"
                      : "bg-zinc-900/50 border-zinc-850 text-zinc-400 hover:bg-zinc-800/50"
                  }`}
                >
                  {activeShowExclusions ? "Hide Exclusions" : "Show Exclusions"}
                </button>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setLocalAuditMode(!localAuditMode)}
                className={`px-3 py-1.5 rounded-lg text-[11px] font-medium border transition-colors ${
                  activeAuditMode
                    ? "bg-purple-950/30 border-purple-500/50 text-purple-400"
                    : "bg-zinc-900/50 border-zinc-850 text-zinc-400 hover:bg-zinc-800/50"
                }`}
              >
                Audit Mode: {activeAuditMode ? "On" : "Off"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Scope Groups */}
      <div className="space-y-4">
        {/* REQUIRED */}
        <ScopeGroupDisplay
          title="Required Before Release"
          description="Mandatory validation targets directly impacted by recent changes."
          group={ScopeGroup.REQUIRED}
          items={requiredItems}
          emptyMessage="No required tasks for this release."
          auditMode={activeAuditMode}
          compact={compact}
          onOpenHistory={onOpenHistory}
        />
        
        {/* REVIEW NEEDED */}
        {reviewNeededItems.length > 0 && (
          <ScopeGroupDisplay
            title="Review Needed"
            description="Passed execution with unknown freshness or mapping gaps requiring analysis."
            group={ScopeGroup.REVIEW_NEEDED}
            items={reviewNeededItems}
            emptyMessage="No items require review."
            auditMode={activeAuditMode}
            compact={compact}
            onOpenHistory={onOpenHistory}
          />
        )}

        {/* RECOMMENDED */}
        <ScopeGroupDisplay
          title="Recommended Regression"
          description="High-value safety coverage recommended based on risk propagation."
          group={ScopeGroup.RECOMMENDED}
          items={recommendedItems}
          emptyMessage="No recommended regression tests."
          auditMode={activeAuditMode}
          compact={compact}
          onOpenHistory={onOpenHistory}
        />

        {/* OPTIONAL */}
        <ScopeGroupDisplay
          title="Optional Safety Net"
          description="Low-risk boundary checks for extra defense-in-depth."
          group={ScopeGroup.OPTIONAL}
          items={optionalItems}
          emptyMessage="No optional safety net tests."
          auditMode={activeAuditMode}
          compact={compact}
          onOpenHistory={onOpenHistory}
        />

        {/* DEFERRED COVERAGE DEBT */}
        {deferredCoverageDebtItems.length > 0 && (
          <ScopeGroupDisplay
            title="Deferred Coverage Debt"
            description="Lower-priority unmapped targets deferred to avoid release blocking."
            group={ScopeGroup.DEFERRED_COVERAGE_DEBT}
            items={deferredCoverageDebtItems}
            emptyMessage="No deferred coverage debt."
            auditMode={activeAuditMode}
            compact={compact}
            onOpenHistory={onOpenHistory}
          />
        )}

        {/* SAFE_TO_SKIP - shown when showSafeToSkip is true */}
        {activeShowSafeToSkip && safeToSkipItems.length > 0 && (
          <ScopeGroupDisplay
            title="Safe To Skip"
            description="Skipped test suites with no code coverage gaps or risk triggers."
            group={ScopeGroup.SAFE_TO_SKIP}
            items={safeToSkipItems}
            emptyMessage="No tasks categorized as safe to skip."
            auditMode={activeAuditMode}
            compact={compact}
            onOpenHistory={onOpenHistory}
          />
        )}

        {/* EXCLUSIONS */}
        {/* Already Verified - shown when exclusions or audit mode */}
        {(activeShowExclusions || activeAuditMode) && (
          <ScopeGroupDisplay
            title="Already Verified"
            description="Tests passed on current commit. No action required."
            group={ScopeGroup.EXCLUDED_ALREADY_VERIFIED}
            items={verifiedItems}
            emptyMessage="No already verified items."
            auditMode={activeAuditMode}
            compact={compact}
            onOpenHistory={onOpenHistory}
          />
        )}
        
        {/* Already Passed Tests - shown when exclusions or audit mode */}
        {(activeShowExclusions || activeAuditMode) && (
          <ScopeGroupDisplay
            title="Already Passed Tests"
            description="Exclusions based on identical execution history."
            group={ScopeGroup.EXCLUDED_ALREADY_PASSED_TESTS}
            items={passedItems}
            emptyMessage="No already passed tests."
            auditMode={activeAuditMode}
            compact={compact}
            onOpenHistory={onOpenHistory}
          />
        )}
      </div>

      {/* DIAGNOSTICS */}
      {activeAuditMode && scope.diagnostics && (
        <div className="bg-zinc-950/40 border border-zinc-800/80 rounded-xl p-5 space-y-4 font-mono text-xs">
          <div className="flex items-center gap-2 border-b border-zinc-850 pb-2.5">
            <ShieldAlert className="w-4 h-4 text-purple-400" />
            <h3 className="font-semibold text-zinc-300">Diagnostics Audit</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <div>
                <span className="text-zinc-500 font-semibold">Generated At:</span>{" "}
                <span className="text-zinc-350">{scope.diagnostics.generation_timestamp}</span>
              </div>
              {scope.diagnostics.generation_duration_ms !== undefined && (
                <div>
                  <span className="text-zinc-500 font-semibold">Generation Duration:</span>{" "}
                  <span className="text-zinc-350">{scope.diagnostics.generation_duration_ms} ms</span>
                </div>
              )}
            </div>
            {scope.diagnostics.rules_applied && scope.diagnostics.rules_applied.length > 0 && (
              <div className="space-y-1">
                <span className="text-zinc-500 font-semibold block">Rules Applied:</span>
                <ul className="list-disc pl-4 space-y-0.5 text-zinc-400 text-[11px]">
                  {scope.diagnostics.rules_applied.map((rule, idx) => (
                    <li key={idx}>{rule}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          {(scope.diagnostics.warnings?.length > 0 || scope.diagnostics.errors?.length > 0) && (
            <div className="space-y-3 pt-2">
              {scope.diagnostics.warnings?.length > 0 && (
                <div className="p-3 bg-amber-950/15 border border-amber-900/30 rounded-lg">
                  <span className="text-[10px] uppercase font-bold text-amber-400 tracking-wider block mb-1">Warnings</span>
                  <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-amber-450">
                    {scope.diagnostics.warnings.map((warn, i) => (
                      <li key={i}>{warn}</li>
                    ))}
                  </ul>
                </div>
              )}
              {scope.diagnostics.errors?.length > 0 && (
                <div className="p-3 bg-rose-950/15 border border-rose-900/30 rounded-lg">
                  <span className="text-[10px] uppercase font-bold text-rose-450 tracking-wider block mb-1">Errors</span>
                  <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-rose-400">
                    {scope.diagnostics.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
export default RegressionScopeV2Display;
