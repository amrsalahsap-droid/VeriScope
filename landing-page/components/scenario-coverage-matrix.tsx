"use client";

import React, { useState } from "react";
import type { ScenarioCoverageMatrix } from "@/lib/scenario-coverage-matrix";
import { CheckCircle2, XCircle, AlertTriangle, FileText, Layers, ChevronDown, ChevronRight, Star } from "lucide-react";

interface ScenarioCoverageMatrixProps {
  matrix: ScenarioCoverageMatrix[];
}

export function ScenarioCoverageMatrix({ matrix }: ScenarioCoverageMatrixProps) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  if (!matrix || matrix.length === 0) {
    return (
      <div className="text-center py-8 text-zinc-500 text-sm">
        No scenario coverage data available
      </div>
    );
  }

  const coveredCount = matrix.filter(m => m.status === "covered").length;
  const suggestedCount = matrix.filter(m => m.status === "suggested").length;
  const totalCount = matrix.length;
  const coveragePercent = Math.round((coveredCount / totalCount) * 100);

  const toggleRow = (key: string) => {
    setExpandedRow(expandedRow === key ? null : key);
  };

  return (
    <div className="space-y-4">
      {/* Summary Stats */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="text-zinc-400">Covered: {coveredCount}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-amber-400" />
          <span className="text-zinc-400">Suggested: {suggestedCount}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-zinc-500">Coverage: {coveragePercent}%</span>
        </div>
      </div>

      {/* Matrix Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800">
              <th className="text-left py-2 px-3 text-zinc-500 font-medium w-8"></th>
              <th className="text-left py-2 px-3 text-zinc-500 font-medium">Priority</th>
              <th className="text-left py-2 px-3 text-zinc-500 font-medium">Impacted Area</th>
              <th className="text-left py-2 px-3 text-zinc-500 font-medium">Testing Type</th>
              <th className="text-left py-2 px-3 text-zinc-500 font-medium">Required Scenario</th>
              <th className="text-left py-2 px-3 text-zinc-500 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, idx) => {
              const rowKey = `${idx}-${row.requiredScenario}`;
              const isExpanded = expandedRow === rowKey;
              
              return (
                <React.Fragment key={idx}>
                  <tr className="border-b border-zinc-800/50 hover:bg-zinc-900/20 cursor-pointer" onClick={() => toggleRow(rowKey)}>
                    <td className="py-2 px-3">
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-zinc-500" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-zinc-500" />
                      )}
                    </td>
                    <td className="py-2 px-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                        row.priority === "MUST" ? "bg-rose-950/30 text-rose-400 border border-rose-500/20" :
                        row.priority === "SHOULD" ? "bg-amber-950/30 text-amber-400 border border-amber-500/20" :
                        "bg-zinc-800 text-zinc-400 border border-zinc-700"
                      }`}>
                        {row.priority === "MUST" && <Star className="w-3 h-3" />}
                        {row.priority}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-zinc-300">{row.impactedArea}</td>
                    <td className="py-2 px-3">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
                        <Layers className="w-3 h-3" />
                        {row.testingType}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-zinc-200 max-w-xs truncate" title={row.requiredScenario}>
                      {row.requiredScenario}
                    </td>
                    <td className="py-2 px-3">
                      {row.status === "covered" ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/30 text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="w-3 h-3" />
                          Covered
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-950/30 text-amber-400 border border-amber-500/20">
                          <AlertTriangle className="w-3 h-3" />
                          Suggested
                        </span>
                      )}
                    </td>
                  </tr>
                  
                  {/* Expanded Details */}
                  {isExpanded && (
                    <tr className="bg-zinc-950/40">
                      <td colSpan={6} className="py-4 px-3">
                        <div className="space-y-3 pl-2">
                          {/* Test Data */}
                          {row.testData && (
                            <div>
                              <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block mb-1">Test Data</span>
                              <p className="text-xs text-zinc-300 bg-zinc-900/50 rounded px-3 py-2 border border-zinc-800">{row.testData}</p>
                            </div>
                          )}
                          
                          {/* Steps */}
                          {row.steps && row.steps.length > 0 && (
                            <div>
                              <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block mb-1">Test Steps</span>
                              <ol className="text-xs text-zinc-300 space-y-1 list-decimal list-inside">
                                {row.steps.map((step, stepIdx) => (
                                  <li key={stepIdx} className="pl-1">{step}</li>
                                ))}
                              </ol>
                            </div>
                          )}
                          
                          {/* Expected Result */}
                          {row.expectedResult && (
                            <div>
                              <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block mb-1">Expected Result</span>
                              <p className="text-xs text-zinc-300 bg-zinc-900/50 rounded px-3 py-2 border border-zinc-800">{row.expectedResult}</p>
                            </div>
                          )}
                          
                          {/* Existing Test Info */}
                          {row.existingTest && (
                            <div>
                              <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block mb-1">Existing Test</span>
                              <div className="inline-flex items-center gap-1 text-emerald-400">
                                <CheckCircle2 className="w-3 h-3" />
                                <span className="font-mono text-xs">{row.existingTest}</span>
                              </div>
                            </div>
                          )}
                          
                          {/* Scenario Type */}
                          {row.scenarioType && (
                            <div>
                              <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block mb-1">Scenario Type</span>
                              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] ${
                                row.scenarioType === "positive" ? "bg-emerald-950/20 text-emerald-400" :
                                row.scenarioType === "negative" ? "bg-rose-950/20 text-rose-400" :
                                row.scenarioType === "edge" ? "bg-purple-950/20 text-purple-400" :
                                "bg-zinc-800 text-zinc-400"
                              }`}>
                                {row.scenarioType}
                              </span>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-[10px] text-zinc-500 pt-2 border-t border-zinc-800/50 flex-wrap">
        <div className="flex items-center gap-1">
          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
          <span>Covered: Test exists</span>
        </div>
        <div className="flex items-center gap-1">
          <AlertTriangle className="w-3 h-3 text-amber-400" />
          <span>Suggested: Test missing</span>
        </div>
        <div className="flex items-center gap-1">
          <Star className="w-3 h-3 text-rose-400" />
          <span>MUST: Critical scenarios</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-zinc-400">Click row to expand details</span>
        </div>
      </div>
    </div>
  );
}
