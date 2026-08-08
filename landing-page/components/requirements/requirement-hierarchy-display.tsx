"use client";

import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, CheckCircle, AlertTriangle, XCircle, FileText, Layers } from "lucide-react";

interface TestableScenario {
  id: string;
  scenario_key: string;
  title: string;
  preconditions: string | null;
  steps: string | null;
  expected_result: string | null;
  scenario_type: string;
  status: string;
}

interface AcceptanceCriterion {
  id: string;
  ac_number: number | null;
  stable_ac_key: string | null;
  title: string | null;
  description: string | null;
  raw_text: string | null;
  normalized_text: string | null;
  source_type: string | null;
  source_id: string | null;
  priority: string | null;
  criticality: string | null;
  status: string;
  version: number;
  testable_scenarios: TestableScenario[];
}

interface RequirementGroup {
  id: string;
  group_number: number;
  group_type: string;
  stable_group_key: string;
  title: string;
  description: string | null;
  business_flow: string | null;
  priority: string | null;
  risk_level: string | null;
  source_type: string | null;
  source_id: string | null;
  status: string;
  acceptance_criteria: AcceptanceCriterion[];
  ac_count: number;
}

interface RequirementPackage {
  id: string;
  repository_id: string;
  pull_request_id: string;
  source_type: string;
  source_id: string | null;
  package_version: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

interface HierarchyStatus {
  requirement_package: string;
  requirement_groups: string;
  acceptance_criteria: string;
  testable_scenarios: string;
  parent_child_mapping: string;
  multiple_enhancements_supported: boolean;
  multiple_acs_per_enhancement_supported: boolean;
  flattening_risk: string;
  required_fixes: string[];
}

interface RequirementHierarchyData {
  exists: boolean;
  requirement_package: RequirementPackage | null;
  requirement_groups: RequirementGroup[];
  total_ac_count: number;
  total_scenario_count: number;
  hierarchy_status: HierarchyStatus;
}

interface RequirementHierarchyDisplayProps {
  repositoryId: string;
  pullRequestId: string;
}

export default function RequirementHierarchyDisplay({ repositoryId, pullRequestId }: RequirementHierarchyDisplayProps) {
  const [data, setData] = useState<RequirementHierarchyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [expandedACs, setExpandedACs] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchHierarchy();
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
      const hierarchyData = await response.json();
      setData(hierarchyData);
      
      // Auto-expand first group if exists
      if (hierarchyData.exists && hierarchyData.requirement_groups.length > 0) {
        setExpandedGroups(new Set([hierarchyData.requirement_groups[0].id]));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const toggleGroup = (groupId: string) => {
    setExpandedGroups(prev => {
      const newSet = new Set(prev);
      if (newSet.has(groupId)) {
        newSet.delete(groupId);
      } else {
        newSet.add(groupId);
      }
      return newSet;
    });
  };

  const toggleAC = (acId: string) => {
    setExpandedACs(prev => {
      const newSet = new Set(prev);
      if (newSet.has(acId)) {
        newSet.delete(acId);
      } else {
        newSet.add(acId);
      }
      return newSet;
    });
  };

  const getGroupTypeColor = (type: string) => {
    switch (type) {
      case "ENHANCEMENT": return "text-emerald-400";
      case "BUG_FIX": return "text-rose-400";
      case "TECH_DEBT": return "text-amber-400";
      case "SECURITY": return "text-purple-400";
      case "NON_FUNCTIONAL": return "text-blue-400";
      default: return "text-zinc-400";
    }
  };

  const getGroupTypeLabel = (type: string) => {
    switch (type) {
      case "ENHANCEMENT": return "Enhancement";
      case "BUG_FIX": return "Bug Fix";
      case "TECH_DEBT": return "Tech Debt";
      case "SECURITY": return "Security";
      case "NON_FUNCTIONAL": return "Non-Functional";
      default: return type;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "ACCEPTED": return <CheckCircle className="w-4 h-4 text-emerald-400" />;
      case "NEEDS_REVIEW": return <AlertTriangle className="w-4 h-4 text-amber-400" />;
      case "REJECTED": return <XCircle className="w-4 h-4 text-rose-400" />;
      default: return <FileText className="w-4 h-4 text-zinc-400" />;
   }
  };

  if (loading) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-center gap-3 text-zinc-400">
          <div className="w-4 h-4 border-2 border-zinc-600 border-t-transparent rounded-full animate-spin" />
          <span>Loading requirement hierarchy...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-center gap-3 text-rose-400">
          <AlertTriangle className="w-5 h-5" />
          <span>Error: {error}</span>
        </div>
      </div>
    );
  }

  if (!data || !data.exists) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-center gap-3 text-zinc-400">
          <FileText className="w-5 h-5" />
          <span>No requirement package found for this pull request.</span>
        </div>
      </div>
    );
  }

  const { requirement_package, requirement_groups, total_ac_count, total_scenario_count, hierarchy_status } = data;

  return (
    <div className="space-y-4">
      {/* Summary Stats */}
      <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <Layers className="w-5 h-5 text-zinc-400" />
          <h3 className="font-semibold text-zinc-200">Business Requirements</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-zinc-500">Requirement Groups</div>
            <div className="text-zinc-200 font-medium">{requirement_groups.length}</div>
          </div>
          <div>
            <div className="text-zinc-500">Acceptance Criteria</div>
            <div className="text-zinc-200 font-medium">{total_ac_count}</div>
          </div>
          <div>
            <div className="text-zinc-500">Testable Scenarios</div>
            <div className="text-zinc-200 font-medium">{total_scenario_count}</div>
          </div>
          <div>
            <div className="text-zinc-500">Flattening Risk</div>
            <div className={`font-medium ${hierarchy_status.flattening_risk === "LOW" ? "text-emerald-400" : "text-amber-400"}`}>
              {hierarchy_status.flattening_risk}
            </div>
          </div>
        </div>
      </div>

      {/* Hierarchy Status */}
      {(hierarchy_status.required_fixes.length > 0 && hierarchy_status.required_fixes[0] !== "None - hierarchy is healthy") && (
        <div className="bg-amber-950/30 border border-amber-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h4 className="font-medium text-amber-200">Hierarchy Issues Detected</h4>
          </div>
          <ul className="space-y-1 text-sm text-amber-300">
            {hierarchy_status.required_fixes.map((fix, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-amber-500">•</span>
                <span>{fix}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Requirement Groups */}
      <div className="space-y-3">
        {requirement_groups.map((group) => (
          <div key={group.id} className="bg-zinc-900/40 border border-zinc-800 rounded-lg overflow-hidden">
            {/* Group Header */}
            <button
              onClick={() => toggleGroup(group.id)}
              className="w-full px-4 py-3 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                {expandedGroups.has(group.id) ? (
                  <ChevronDown className="w-4 h-4 text-zinc-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-zinc-400" />
                )}
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${getGroupTypeColor(group.group_type)} bg-zinc-800/50`}>
                  {getGroupTypeLabel(group.group_type)}
                </span>
                <span className="font-medium text-zinc-200">{group.title}</span>
                <span className="text-zinc-500 text-sm">({group.ac_count} ACs)</span>
              </div>
              <div className="flex items-center gap-2">
                {getStatusIcon(group.status)}
              </div>
            </button>

            {/* Group Content */}
            {expandedGroups.has(group.id) && (
              <div className="px-4 pb-4 pt-2 border-t border-zinc-800/50">
                {group.description && (
                  <p className="text-zinc-400 text-sm mb-3">{group.description}</p>
                )}
                
                {/* Acceptance Criteria */}
                <div className="space-y-2">
                  {group.acceptance_criteria.map((ac) => (
                    <div key={ac.id} className="bg-zinc-800/30 rounded-lg overflow-hidden">
                      {/* AC Header */}
                      <button
                        onClick={() => toggleAC(ac.id)}
                        className="w-full px-3 py-2 flex items-center justify-between hover:bg-zinc-700/50 transition-colors text-left"
                      >
                        <div className="flex items-center gap-2">
                          {expandedACs.has(ac.id) ? (
                            <ChevronDown className="w-3 h-3 text-zinc-400" />
                          ) : (
                            <ChevronRight className="w-3 h-3 text-zinc-400" />
                          )}
                          <span className="text-zinc-500 text-xs">AC-{ac.ac_number || "?"}</span>
                          <span className="text-zinc-300 text-sm">{ac.title || ac.raw_text?.substring(0, 60) || "Untitled"}</span>
                        </div>
                        {getStatusIcon(ac.status)}
                      </button>

                      {/* AC Details */}
                      {expandedACs.has(ac.id) && (
                        <div className="px-3 pb-3 pt-2 border-t border-zinc-700/50 space-y-2">
                          {ac.description && (
                            <p className="text-zinc-400 text-sm">{ac.description}</p>
                          )}
                          {ac.raw_text && (
                            <p className="text-zinc-500 text-xs italic">{ac.raw_text}</p>
                          )}
                          
                          {/* Testable Scenarios */}
                          {ac.testable_scenarios && ac.testable_scenarios.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-zinc-700/50">
                              <div className="text-xs text-zinc-500 mb-1">Testable Scenarios ({ac.testable_scenarios.length})</div>
                              <div className="space-y-1">
                                {ac.testable_scenarios.map((scenario) => (
                                  <div key={scenario.id} className="text-xs text-zinc-400 pl-2">
                                    • {scenario.title}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Flattening Warning */}
      {!hierarchy_status.multiple_enhancements_supported && requirement_groups.length > 0 && (
        <div className="bg-amber-950/30 border border-amber-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <p className="text-sm text-amber-200">
              Requirement grouping is missing. VeriScope can use the ACs, but impact analysis may be less precise.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
