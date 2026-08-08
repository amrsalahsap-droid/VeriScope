"use client";
import React, { useCallback } from "react";
import { InputReadinessV2Panel } from "@/components/readiness/InputReadinessV2Panel";

interface RecommendationReadinessPanelProps {
  repositoryId: string;
  repositoryName: string;
  repositoryStatus: string;
  pullRequestId?: string;
  refreshTrigger?: number;
  onReadinessDataChange?: (data: unknown) => void;
  onAction?: (action: string, inputId: string) => void;
  runRepositoryIntelligence?: () => Promise<void>;
  refreshState?: "idle" | "running" | "success" | "partial" | "failed";
}

export default function RecommendationReadinessPanel({
  repositoryId,
  pullRequestId,
  refreshTrigger,
  onReadinessDataChange,
  onAction,
  runRepositoryIntelligence,
  refreshState,
}: RecommendationReadinessPanelProps) {
  const handleAction = useCallback((action: string, inputId: string) => {
    onAction?.(action, inputId);
  }, [onAction]);

  const handleReadinessDataChange = useCallback((data: unknown) => {
    onReadinessDataChange?.(data);
  }, [onReadinessDataChange]);

  if (!pullRequestId) {
    return (
      <div className="border border-zinc-800/50 rounded-xl p-4 bg-zinc-900/20 text-center">
        <p className="text-xs text-zinc-500">Select a pull request to view input readiness.</p>
      </div>
    );
  }

  return (
    <InputReadinessV2Panel
      repositoryId={repositoryId}
      pullRequestId={pullRequestId}
      onAction={handleAction}
      refreshTrigger={refreshTrigger}
      onReadinessDataChange={handleReadinessDataChange}
      runRepositoryIntelligence={runRepositoryIntelligence}
      refreshState={refreshState}
    />
  );
}
