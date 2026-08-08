"use client";

import React, { useState } from "react";
import { Brain, Target, Globe, Layers, FileCode, GitBranch, ChevronDown, ChevronUp, AlertTriangle, ChevronRight } from "lucide-react";
import { mapRawLabel, generateBusinessImpact, generateImpactedFlows, generateTechnicalAreas, generateWhyItMatters } from "@/lib/label-mapper";

interface WhatVeriscopeUnderstoodProps {
  impactedBehaviors: string[];
  impactedJourneys: string[];
  changedLayers: string[];
  changedComponents: string[];
  changedFiles: string[];
  summary: string;
  fileImpactMap?: Array<{
    filePath: string;
    changeStatus: string;
    affectedAcs: Array<{
      acId: string;
      title: string;
      group: string;
      executionStatus: string;
    }>;
  }>;
  className?: string;
}

export default function WhatVeriscopeUnderstood({
  impactedBehaviors,
  impactedJourneys,
  changedLayers,
  changedComponents,
  changedFiles,
  summary,
  fileImpactMap,
  className = ""
}: WhatVeriscopeUnderstoodProps) {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());

  const businessImpact = generateBusinessImpact(changedFiles);
  const impactedFlows = generateImpactedFlows(changedFiles);
  const technicalAreas = generateTechnicalAreas(changedFiles);
  const whyItMatters = generateWhyItMatters(changedFiles);

  return (
    <div className={`bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-5 ${className}`}>
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 rounded-lg bg-blue-950/20 border border-blue-800/40">
          <Brain className="w-5 h-5 text-blue-400" />
        </div>
        <h2 className="text-lg font-semibold text-white">What Changed</h2>
      </div>

      {/* Business Impact */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-semibold text-zinc-300">Business Impact</h3>
        </div>
        <p className="text-sm text-zinc-400 leading-relaxed">{businessImpact}</p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4 mb-4">
        {/* Impacted Flows */}
        {impactedFlows.length > 0 && (
          <div className="bg-zinc-800/40 rounded-lg p-3 border border-zinc-700/50">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-emerald-400" />
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                Impacted Flows
              </h3>
            </div>
            <div className="space-y-1">
              {impactedFlows.map((flow, index) => (
                <div key={index} className="text-xs text-zinc-300 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full"></span>
                  {flow}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Technical Areas */}
        {technicalAreas.length > 0 && (
          <div className="bg-zinc-800/40 rounded-lg p-3 border border-zinc-700/50">
            <div className="flex items-center gap-2 mb-2">
              <Layers className="w-4 h-4 text-amber-400" />
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                Technical Areas
              </h3>
            </div>
            <div className="flex flex-wrap gap-1">
              {technicalAreas.map((area, index) => (
                <span
                  key={index}
                  className="text-xs px-2 py-1 bg-amber-950/30 text-amber-400 rounded border border-amber-800/40"
                >
                  {area}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Why It Matters */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Target className="w-4 h-4 text-rose-400" />
          <h3 className="text-sm font-semibold text-zinc-300">Why It Matters</h3>
        </div>
        <div className="space-y-1">
          {whyItMatters.map((reason, index) => (
            <div key={index} className="text-xs text-zinc-400 flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-rose-400 rounded-full"></span>
              {reason}
            </div>
          ))}
        </div>
      </div>

      {/* File Impact Map */}
      {fileImpactMap && fileImpactMap.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <FileCode className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-semibold text-zinc-300">File Impact Map</h3>
          </div>
          <div className="space-y-2">
            {fileImpactMap.map((fileImpact, index) => {
              const isExpanded = expandedFiles.has(fileImpact.filePath);
              const displayAcs = isExpanded ? fileImpact.affectedAcs : fileImpact.affectedAcs.slice(0, 5);
              const hasMore = fileImpact.affectedAcs.length > 5;
              
              const getGroupBadgeColor = (group: string) => {
                switch (group) {
                  case "REQUIRED":
                    return "bg-red-950/30 text-red-400 border-red-800/40";
                  case "EXCLUDED_ALREADY_VERIFIED":
                    return "bg-green-950/30 text-green-400 border-green-800/40";
                  case "RECOMMENDED":
                    return "bg-amber-950/30 text-amber-400 border-amber-800/40";
                  case "OPTIONAL":
                    return "bg-zinc-950/30 text-zinc-400 border-zinc-800/40";
                  case "SAFE_TO_SKIP":
                    return "bg-blue-950/30 text-blue-400 border-blue-800/40";
                  default:
                    return "bg-zinc-950/30 text-zinc-400 border-zinc-800/40";
                }
              };

              const getExecutionStatusColor = (status: string) => {
                switch (status) {
                  case "PASSED":
                    return "text-green-400";
                  case "FAILED":
                    return "text-red-400";
                  case "SKIPPED":
                    return "text-amber-400";
                  case "NOT_RUN":
                    return "text-zinc-400";
                  default:
                    return "text-zinc-400";
                }
              };

              return (
                <div key={index} className="bg-zinc-800/40 rounded-lg border border-zinc-700/50 overflow-hidden">
                  <button
                    onClick={() => {
                      const newExpanded = new Set(expandedFiles);
                      if (newExpanded.has(fileImpact.filePath)) {
                        newExpanded.delete(fileImpact.filePath);
                      } else {
                        newExpanded.add(fileImpact.filePath);
                      }
                      setExpandedFiles(newExpanded);
                    }}
                    className="w-full px-3 py-2 flex items-center justify-between hover:bg-zinc-700/30 transition-colors"
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <ChevronRight 
                        className={`w-4 h-4 text-zinc-400 transition-transform ${
                          isExpanded ? 'rotate-90' : ''
                        }`} 
                      />
                      <span className="text-xs font-mono text-zinc-300 truncate">
                        {fileImpact.filePath}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded border ${
                        fileImpact.changeStatus === 'modified' 
                          ? 'bg-amber-950/30 text-amber-400 border-amber-800/40'
                          : fileImpact.changeStatus === 'added'
                          ? 'bg-green-950/30 text-green-400 border-green-800/40'
                          : fileImpact.changeStatus === 'deleted'
                          ? 'bg-red-950/30 text-red-400 border-red-800/40'
                          : 'bg-zinc-950/30 text-zinc-400 border-zinc-800/40'
                      }`}>
                        {fileImpact.changeStatus.toUpperCase()}
                      </span>
                    </div>
                    <span className="text-xs text-zinc-500">
                      {fileImpact.affectedAcs.length} AC{fileImpact.affectedAcs.length !== 1 ? 's' : ''}
                    </span>
                  </button>
                  
                  {isExpanded && (
                    <div className="px-3 pb-2 space-y-1">
                      {displayAcs.map((ac, acIndex) => (
                        <div key={acIndex} className="flex items-center gap-2 text-xs">
                          <span className="font-mono text-zinc-400">{ac.acId}:</span>
                          <span className="text-zinc-300 truncate flex-1">{ac.title}</span>
                          <span className={`px-2 py-0.5 rounded border text-xs ${getGroupBadgeColor(ac.group)}`}>
                            {ac.group.replace('_', ' ')}
                          </span>
                          <span className={`text-xs ${getExecutionStatusColor(ac.executionStatus)}`}>
                            {ac.executionStatus}
                          </span>
                        </div>
                      ))}
                      {hasMore && !isExpanded && (
                        <div className="text-xs text-zinc-500">
                          and {fileImpact.affectedAcs.length - 5} more
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Technical Details (Collapsible) */}
      <div className="border-t border-zinc-800/50 pt-4">
        <button
          onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
          className="flex items-center gap-2 text-xs text-zinc-500 hover:text-zinc-400 transition-colors"
        >
          {showTechnicalDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          <span>Technical Details</span>
        </button>

        {showTechnicalDetails && (
          <div className="mt-3 space-y-3">
            {/* Changed Components */}
            {changedComponents.length > 0 && (
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <div className="flex items-center gap-2 mb-2">
                  <FileCode className="w-4 h-4 text-blue-400" />
                  <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Changed Components
                  </h3>
                </div>
                <div className="space-y-1">
                  {changedComponents.map((component, index) => (
                    <div key={index} className="text-xs text-zinc-500 flex items-center gap-2 font-mono">
                      <GitBranch className="w-3 h-3 text-blue-500" />
                      {component}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Changed Files */}
            {changedFiles.length > 0 && (
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <div className="flex items-center gap-2 mb-2">
                  <FileCode className="w-4 h-4 text-zinc-400" />
                  <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Changed Files
                  </h3>
                </div>
                <div className="space-y-1">
                  {changedFiles.map((file, index) => (
                    <div key={index} className="text-xs text-zinc-500 font-mono truncate" title={file}>
                      {file}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Raw Behaviors */}
            {impactedBehaviors.length > 0 && (
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <div className="flex items-center gap-2 mb-2">
                  <Target className="w-4 h-4 text-zinc-400" />
                  <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Raw Behaviors
                  </h3>
                </div>
                <div className="space-y-1">
                  {impactedBehaviors.map((behavior, index) => (
                    <div key={index} className="text-xs text-zinc-500 truncate" title={behavior}>
                      {mapRawLabel(behavior)}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Helper function to extract understanding data from recommendation run
export function extractUnderstandingData(run: any): {
  impactedBehaviors: string[];
  impactedJourneys: string[];
  changedLayers: string[];
  changedComponents: string[];
  changedFiles: string[];
  summary: string;
} {
  // Extract impacted behaviors from behavior coverage matrix
  const impactedBehaviors: string[] = run.behavior_coverage_matrix
    ? [...new Set(run.behavior_coverage_matrix.map((item: any) => item.behavior_name).filter((name: any): name is string => Boolean(name)))] as string[]
    : [];

  // Extract impacted journeys from behavior coverage matrix
  const impactedJourneys: string[] = run.behavior_coverage_matrix
    ? [...new Set(run.behavior_coverage_matrix.map((item: any) => item.journey_name).filter((name: any): name is string => Boolean(name)))] as string[]
    : [];

  // Extract changed layers from recommended tests
  const changedLayers: string[] = run.recommended_tests
    ? [...new Set(run.recommended_tests.map((test: any) => test.layer).filter((layer: any): layer is string => Boolean(layer)))] as string[]
    : [];

  // Extract changed files
  const changedFiles: string[] = run.executive_summary?.changed_files || run.changed_files || [];

  // Extract key components from changed files or tests
  const topComponents: string[] = changedFiles
    .map((file: string) => {
      // Extract component name from file path
      const parts = file.split('/');
      const fileName = parts[parts.length - 1];
      const componentName = fileName.replace(/\.(ts|js|tsx|jsx|py|java|cs)$/, '');
      return componentName;
    })
    .slice(0, 8); // Top 8 components

  // Generate summary
  const behaviorCount = impactedBehaviors.length;
  const journeyCount = impactedJourneys.length;
  const layerCount = changedLayers.length;
  
  let summary = "";
  if (behaviorCount > 0 && journeyCount > 0) {
    summary = `${behaviorCount} behavior${behaviorCount !== 1 ? 's' : ''} and ${journeyCount} journey${journeyCount !== 1 ? 's' : ''} impacted`;
  } else if (behaviorCount > 0) {
    summary = `${behaviorCount} behavior${behaviorCount !== 1 ? 's' : ''} impacted`;
  } else if (journeyCount > 0) {
    summary = `${journeyCount} journey${journeyCount !== 1 ? 's' : ''} impacted`;
  } else {
    summary = "Code changes analyzed for impact assessment";
  }

  if (layerCount > 0) {
    summary += ` across ${layerCount} layer${layerCount !== 1 ? 's' : ''}`;
  }

  return {
    impactedBehaviors,
    impactedJourneys,
    changedLayers,
    changedComponents: topComponents,
    changedFiles,
    summary
  };
}
