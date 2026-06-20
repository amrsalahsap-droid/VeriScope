"use client";

import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { RegressionScopeV2Display } from "./regression-scope/RegressionScopeV2Display";
import { legacyRegressionScopeToV2 } from "../lib/adapters/legacyRegressionScopeToV2";

export interface TargetedScopeModalProps {
  isOpen?: boolean;
  open?: boolean;
  onClose?: () => void;
  onOpenChange?: (open: boolean) => void;
  scope?: any;
  onOpenHistory?: (item: any) => void;
  auditMode?: boolean;
}

export function TargetedScopeModal({
  isOpen,
  open,
  onClose,
  onOpenChange,
  scope,
  onOpenHistory,
  auditMode = false
}: TargetedScopeModalProps) {
  const [showSafeToSkip, setShowSafeToSkip] = useState(false);
  const [showExclusions, setShowExclusions] = useState(false);

  const activeOpen = open !== undefined ? open : (isOpen !== undefined ? isOpen : false);
  
  const handleOpenChange = (val: boolean) => {
    if (onOpenChange) onOpenChange(val);
    if (!val && onClose) onClose();
  };

  if (!scope) return null;

  // Detect if scope is modern V2 (contains groups, executionPlan, or execution_plan)
  const isV2 = !!(scope.groups || scope.executionPlan || scope.execution_plan);
  const scopeV2 = isV2 ? scope : legacyRegressionScopeToV2(scope);

  return (
    <Dialog open={activeOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-zinc-900 border-zinc-800 text-zinc-100 font-sans">
        <DialogHeader className="border-b border-zinc-800/60 pb-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <DialogTitle className="text-xl font-bold text-white font-sans">Targeted Regression Scope</DialogTitle>
            
            {/* Modal Local Toggles */}
            <div className="flex items-center gap-4 flex-wrap">
              <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showSafeToSkip}
                  onChange={(e) => setShowSafeToSkip(e.target.checked)}
                  className="rounded border-zinc-750 bg-zinc-950 text-purple-600 focus:ring-purple-600/30 w-3.5 h-3.5"
                />
                Show Safe To Skip
              </label>
              <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showExclusions}
                  onChange={(e) => setShowExclusions(e.target.checked)}
                  className="rounded border-zinc-750 bg-zinc-950 text-purple-600 focus:ring-purple-600/30 w-3.5 h-3.5"
                />
                Show Exclusions
              </label>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-6 mt-4">
          {/* Main Scope display */}
          <RegressionScopeV2Display
            scope={scopeV2}
            mode="targeted"
            compact
            showSafeToSkip={showSafeToSkip}
            showExclusions={showExclusions}
            auditMode={auditMode}
            onOpenHistory={onOpenHistory}
          />

          {/* Close Button */}
          <div className="flex justify-end pt-4 border-t border-zinc-800/40">
            <Button onClick={() => handleOpenChange(false)} className="bg-zinc-700 hover:bg-zinc-600 text-white font-semibold text-xs py-1.5 px-3 rounded-lg">
              Close
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
export default TargetedScopeModal;
