"use client";

import React, { useState, useEffect } from "react";
import { Layers, AlertTriangle, CheckCircle, XCircle } from "lucide-react";

interface BusinessRequirementsBannerProps {
  repositoryId: string;
  pullRequestId?: string;
}

export default function BusinessRequirementsBanner({ 
  repositoryId, 
  pullRequestId 
}: BusinessRequirementsBannerProps) {
  const [hierarchyData, setHierarchyData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

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
      console.error("Failed to fetch requirements:", err);
    } finally {
      setLoading(false);
    }
  };

  if (!pullRequestId || loading) {
    return null;
  }

  if (!hierarchyData || !hierarchyData.exists) {
    return (
      <div className="bg-rose-950/20 border border-rose-800/40 rounded-lg p-4 mb-4">
        <div className="flex items-center gap-2">
          <XCircle className="w-4 h-4 text-rose-400" />
          <div>
            <div className="font-medium text-sm text-rose-200">Business requirements are missing</div>
            <div className="text-xs text-rose-300 mt-1">
              Only a draft recommendation can be generated.
            </div>
          </div>
        </div>
      </div>
    );
  }

  const { hierarchy_status, total_ac_count, requirement_groups } = hierarchyData;
  const isReady = hierarchy_status.requirement_package === "EXISTS" && 
                  hierarchy_status.requirement_groups === "EXISTS" &&
                  hierarchy_status.acceptance_criteria === "EXISTS" &&
                  hierarchy_status.required_fixes.length === 0;

  if (!isReady) {
    return (
      <div className="bg-amber-950/20 border border-amber-800/40 rounded-lg p-4 mb-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <div>
            <div className="font-medium text-sm text-amber-200">Business requirements need review</div>
            <div className="text-xs text-amber-300 mt-1">
              {hierarchy_status.required_fixes.join(", ")}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-emerald-950/20 border border-emerald-800/40 rounded-lg p-4 mb-4">
      <div className="flex items-center gap-2">
        <Layers className="w-4 h-4 text-emerald-400" />
        <div className="flex-1">
          <div className="font-medium text-sm text-emerald-200">Business Requirements</div>
          <div className="text-xs text-emerald-300 mt-1">
            {requirement_groups.length} requirement groups • {total_ac_count} acceptance criteria • Stable IDs: {hierarchy_status.parent_child_mapping === "PRESERVED" ? "Preserved" : "Partial"}
          </div>
        </div>
        <CheckCircle className="w-4 h-4 text-emerald-400" />
      </div>
    </div>
  );
}
