"use client";

import React from "react";
import RecommendationReadinessGate from "@/components/recommendations/recommendation-readiness-gate";

interface RecommendationCheckpointModalProps {
  isOpen: boolean;
  onClose: () => void;
  onContinue: () => void;
  repositoryId: string;
  pullRequestId?: string;
  action: "generate" | "rerun" | "view";
  recommendationRunId?: string;
  generationStatus?: "idle" | "generating" | "redirecting" | "failed";
  runRepositoryIntelligence?: () => Promise<void>;
  refreshState?: "idle" | "running" | "success" | "partial" | "failed";
}

export default function RecommendationCheckpointModal(props: RecommendationCheckpointModalProps) {
  return <RecommendationReadinessGate {...props} />;
}
