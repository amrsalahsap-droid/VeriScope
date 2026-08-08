"use client";

import React, { useState, useEffect } from "react";
import { Layers, AlertTriangle, CheckCircle, XCircle, ChevronDown, ChevronUp } from "lucide-react";
import RequirementHierarchyDisplay from "./requirement-hierarchy-display";

interface BusinessRequirementsReadinessCardProps {
  repositoryId: string;
  pullRequestId?: string;
  compact?: boolean;
}

export default function BusinessRequirementsReadinessCard({ 
  repositoryId, 
  pullRequestId,
  compact = false 
}: BusinessRequirementsReadinessCardProps) {
  const [hierarchyData, setHierarchyData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    if (pullRequestId) {
      fetchHierarchy();
    }
  }, [repositoryId, pullRequestId]);

  const fetchHierarchy = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `/api/readiness/repositories/${repositoryId}/pull-requests/${pullRequestId}/requirement-package`
      );
      if (!response.ok) {
        throw new Error("Failed to fetch requirement hierarchy");
      }
      const data = await response.json();
      setHierarchyData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  if (!pullRequestId) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
        <div className="flex items-center gap-2 text-zinc-400">
          <Layers className="w-4 h-4" />
          <span className="text-sm">No PR selected</span>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
        <div className="flex items-center gap-2 text-zinc-400">
          <div className="w-4 h-4 border-2 border-zinc-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading requirements...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
        <div className="flex items-center gap-2 text-rose-400">
          <AlertTriangle className="w-4 h-4" />
          <span className="text-sm">Error loading requirements</span>
        </div>
      </div>
    );
  }

  if (!hierarchyData || !hierarchyData.exists) {
    return (
      <div className="bg-rose-950/20 border border-rose-800/40 rounded-lg p-4">
        <div className="flex items-center gap-2 text-rose-400">
          <XCircle className="w-4 h-4" />
          <div>
            <div className="font-medium text-sm">Business Requirements Missing</div>
            <div className="text-xs text-rose-300 mt-1">
              Add requirement groups and acceptance criteria before generating a confident regression plan.
            </div>
          </div>
        </div>
      </div>
    );
  }

  const { hierarchy_status, total_ac_count, total_scenario_count, requirement_groups } = hierarchyData;

  const getStatusColor = (status: string) => {
    switch (status) {
      case "EXISTS":
        return "text-emerald-400";
      case "MISSING":
        return "text-rose-400";
      default:
        return "text-amber-400";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "EXISTS":
        return <CheckCircle className="w-4 h-4" />;
      case "MISSING":
        return <XCircle className="w-4 h-4" />;
      default:
        return <AlertTriangle className="w-4 h-4" />;
    }
  };

  if (compact) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-zinc-400" />
            <span className="text-sm font-medium text-zinc-200">Business Requirements</span>
            {getStatusIcon(hierarchy_status.requirement_package)}
          </div>
          <div className="text-xs text-zinc-400">
            {requirement_groups.length} groups, {total_ac_count} ACs
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-zinc-400" />
          <span className="font-medium text-zinc-200">Business Requirements</span>
          {getStatusIcon(hierarchy_status.requirement_package)}
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs text-zinc-400">
            {requirement_groups.length} groups, {total_ac_count} ACs
          </div>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-zinc-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-zinc-400" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 pt-2 border-t border-zinc-800/50">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-4">
            <div>
              <div className="text-zinc-500">Requirement Groups</div>
              <div className={`font-medium ${getStatusColor(hierarchy_status.requirement_groups)}`}>
                {requirement_groups.length}
              </div>
            </div>
            <div>
              <div className="text-zinc-500">Acceptance Criteria</div>
              <div className={`font-medium ${getStatusColor(hierarchy_status.acceptance_criteria)}`}>
                {total_ac_count}
              </div>
            </div>
            <div>
              <div className="text-zinc-500">Stable IDs</div>
              <div className="font-medium text-zinc-200">
                {hierarchy_status.parent_child_mapping === "PRESERVED" ? "Preserved" : "Partial"}
              </div>
            </div>
            <div>
              <div className="text-zinc-500">Flattening Risk</div>
              <div className={`font-medium ${hierarchy_status.flattening_risk === "LOW" ? "text-emerald-400" : "text-amber-400"}`}>
                {hierarchy_status.flattening_risk}
              </div>
            </div>
          </div>

          {hierarchy_status.required_fixes.length > 0 && hierarchy_status.required_fixes[0] !== "None - hierarchy is healthy" && (
            <div className="bg-amber-950/30 border border-amber-800/50 rounded-lg p-3 mb-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span className="text-sm font-medium text-amber-200">Hierarchy Issues</span>
              </div>
              <ul className="space-y-1 text-xs text-amber-300">
                {hierarchy_status.required_fixes.map((fix: string, idx: number) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-amber-500">•</span>
                    <span>{fix}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!hierarchy_status.multiple_enhancements_supported && requirement_groups.length > 0 && (
            <div className="bg-amber-950/30 border border-amber-800/50 rounded-lg p-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <p className="text-sm text-amber-200">
                  Requirement grouping is missing. VeriScope can use the ACs, but impact analysis may be less precise.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
