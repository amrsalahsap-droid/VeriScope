"use client";

import React, { useState } from "react";
import type { ScenarioCoverageMatrix } from "@/lib/scenario-coverage-matrix";
import { AlertTriangle, ChevronDown, ChevronRight, MapPin, Zap, Info } from "lucide-react";

interface MissingCoverageItem {
  domain: string;
  feature: string;
  reason: string;
}

interface ImprovedMissingCoverageProps {
  missingCoverage: MissingCoverageItem[];
  scenarioMatrix: ScenarioCoverageMatrix[];
}

interface GroupedCoverage {
  area: string;
  items: MissingCoverageItem[];
  relatedScenarios: ScenarioCoverageMatrix[];
}

export function ImprovedMissingCoverage({ missingCoverage, scenarioMatrix }: ImprovedMissingCoverageProps) {
  const [expandedArea, setExpandedArea] = useState<string | null>(null);

  if (!missingCoverage || missingCoverage.length === 0) {
    return (
      <div className="text-center py-8 text-zinc-500 text-sm">
        No missing coverage detected
      </div>
    );
  }

  // Group missing coverage by domain/area
  const groupedCoverage = missingCoverage.reduce((acc, item) => {
    const area = item.domain || "General";
    if (!acc[area]) {
      acc[area] = [];
    }
    acc[area].push(item);
    return acc;
  }, {} as Record<string, MissingCoverageItem[]>);

  // Convert to array and find related scenarios for each area
  const coverageGroups: GroupedCoverage[] = Object.entries(groupedCoverage).map(([area, items]) => {
    // Find scenarios that match this area
    const relatedScenarios = scenarioMatrix.filter(s => 
      s.status === "suggested" && 
      (s.impactedArea.toLowerCase().includes(area.toLowerCase()) ||
       s.testingType.toLowerCase().includes(area.toLowerCase()))
    );

    return {
      area,
      items,
      relatedScenarios
    };
  });

  const toggleArea = (area: string) => {
    setExpandedArea(expandedArea === area ? null : area);
  };

  return (
    <div className="space-y-4">
      {coverageGroups.map((group) => {
        const isExpanded = expandedArea === group.area;
        const scenarioCount = group.relatedScenarios.length;

        return (
          <div key={group.area} className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl overflow-hidden">
            {/* Header */}
            <div
              className="p-4 cursor-pointer hover:bg-zinc-900/60 transition-colors"
              onClick={() => toggleArea(group.area)}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-rose-950/30 text-rose-400 border border-rose-500/20 text-[10px] font-semibold">
                      <AlertTriangle className="w-3 h-3" />
                      {group.area}
                    </span>
                    {scenarioCount > 0 && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-950/30 text-emerald-400 border border-emerald-500/20 text-[10px] font-semibold">
                        <Zap className="w-3 h-3" />
                        {scenarioCount} scenario{scenarioCount !== 1 ? 's' : ''} suggested
                      </span>
                    )}
                  </div>
                  
                  {/* Missing capabilities */}
                  <div className="space-y-2">
                    {group.items.map((item, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <MapPin className="w-3 h-3 text-zinc-500 shrink-0 mt-0.5" />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-zinc-200">{item.feature}</p>
                          <p className="text-[10px] text-zinc-400 mt-0.5">{item.reason}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {scenarioCount > 0 && (
                    <button
                      className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium rounded border border-zinc-700 transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleArea(group.area);
                      }}
                    >
                      View scenarios
                    </button>
                  )}
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-zinc-500" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-zinc-500" />
                  )}
                </div>
              </div>
            </div>

            {/* Expanded Scenarios */}
            {isExpanded && scenarioCount > 0 && (
              <div className="border-t border-zinc-800/50 p-4 bg-zinc-950/30">
                <div className="flex items-center gap-2 mb-3">
                  <Info className="w-4 h-4 text-zinc-500" />
                  <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
                    Suggested Scenarios for {group.area}
                  </span>
                </div>
                <div className="space-y-2">
                  {group.relatedScenarios.map((scenario, idx) => (
                    <div key={idx} className="bg-zinc-900/50 rounded-lg p-3 border border-zinc-800/40">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-semibold text-zinc-200">{scenario.requiredScenario}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className={`text-[9px] px-1.5 py-0.5 rounded ${
                              scenario.priority === "MUST" ? "bg-rose-950/30 text-rose-400 border border-rose-500/20" :
                              scenario.priority === "SHOULD" ? "bg-amber-950/30 text-amber-400 border border-amber-500/20" :
                              "bg-zinc-800 text-zinc-400 border border-zinc-700"
                            }`}>
                              {scenario.priority}
                            </span>
                            <span className={`text-[9px] px-1.5 py-0.5 rounded ${
                              scenario.scenarioType === "positive" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                              scenario.scenarioType === "negative" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" :
                              "bg-zinc-500/10 text-zinc-400 border border-zinc-500/20"
                            }`}>
                              {scenario.scenarioType}
                            </span>
                          </div>
                        </div>
                        {scenario.automationCandidate && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-950/30 text-emerald-400 border border-emerald-500/20 text-[9px] font-semibold">
                            <Zap className="w-3 h-3" />
                            Auto
                          </span>
                        )}
                      </div>
                      {scenario.testData && (
                        <div className="mt-2">
                          <span className="text-[9px] text-zinc-500 block mb-1">Test Data</span>
                          <p className="text-[10px] text-zinc-400 bg-zinc-800/50 rounded px-2 py-1">{scenario.testData}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
