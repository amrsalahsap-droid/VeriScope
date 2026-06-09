"use client";

import { useState } from "react";
import type { ConsistencyCheckResult } from "@/lib/validate-recommendation-detail";

interface DevConsistencyCheckProps {
  result: ConsistencyCheckResult;
}

export function DevConsistencyCheck({ result }: DevConsistencyCheckProps) {
  const [expanded, setExpanded] = useState(false);

  // Only show in development with explicit dev diagnostics flag
  if (process.env.NODE_ENV !== "development") return null;
  if (typeof window !== "undefined" && !new URLSearchParams(window.location.search).has("devDiagnostics")) return null;
  
  // Only show if there are errors (warnings are for dev investigation only)
  if (!result.hasErrors) return null;

  const errorCount = result.errors.length;
  const warnCount = result.warnings.length;

  return (
    <div className="border border-amber-700/50 bg-amber-950/20 rounded-lg text-xs font-mono overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-amber-950/30 transition-colors"
      >
        <span className="text-amber-400 font-semibold">
          🛠 Dev Consistency:{" "}
          {errorCount > 0 && (
            <span className="text-rose-400">{errorCount} error{errorCount !== 1 ? "s" : ""}</span>
          )}
          {errorCount > 0 && warnCount > 0 && <span className="text-amber-600">, </span>}
          {warnCount > 0 && (
            <span className="text-amber-400">{warnCount} warning{warnCount !== 1 ? "s" : ""}</span>
          )}
        </span>
        <span className="text-zinc-500 text-[10px]">{expanded ? "▲ hide" : "▼ show"}</span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-1 border-t border-amber-700/30 pt-2">
          {result.errors.map((e) => (
            <div key={e.code} className="flex items-start gap-1.5 text-rose-400">
              <span className="shrink-0">❌</span>
              <span>
                <span className="font-bold">[{e.code}]</span> {e.message}
              </span>
            </div>
          ))}
          {result.warnings.map((w) => (
            <div key={w.code} className="flex items-start gap-1.5 text-amber-400">
              <span className="shrink-0">⚠</span>
              <span>
                <span className="font-bold">[{w.code}]</span> {w.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
