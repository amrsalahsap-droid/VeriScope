"use client";

import { useState, useCallback, useEffect } from "react";
import { redirect, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { 
  ArrowLeft, 
  Github, 
  GitBranch, 
  Lock, 
  Globe, 
  RefreshCw, 
  ExternalLink,
  GitPullRequest,
  FlaskConical,
  BarChart2,
  Sparkles,
  AlertTriangle,
  Play,
  Loader2,
  Clock,
  CheckCircle2,
  XCircle,
  FileText,
  Eye,
  Settings
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import RecommendationReadinessPanel from "@/app/components/RecommendationReadinessPanel";
import RecommendationCheckpointModal from "@/app/components/RecommendationCheckpointModal";
import BusinessRequirementsModal from "@/components/requirements/business-requirements-modal";
import { ImproveInputReadinessDrawer } from "@/components/readiness/ImproveInputReadinessDrawer";
import { resolveRecommendationAction, getOptionalGapLabel } from "@/lib/readiness-cta-resolver";
import { executeInputAction } from "@/lib/readiness/executeInputAction";
import { PRPackageSummaryCard, InputReadinessBanner, MissingInputWarning } from "@/components/pr-package-readiness";
import BusinessRequirementsReadinessCard from "@/components/requirements/business-requirements-readiness-card";
import { normalizePRPackage, getBlockerMessage, getWarningMessage } from "@/lib/adapters/prPackageAdapter";

export const dynamic = "force-dynamic";

interface Repository {
  id: string;
  full_name: string;
  owner: string;
  name: string;
  visibility: string;
  default_branch: string | null;
  is_active: boolean;
  selected_for_analysis: boolean;
  last_synced_at: string | null;
  last_webhook_at: string | null;
  latest_pr_synced_at: string | null;
  latest_sync_status: string;
  sync_error: string | null;
  pr_sync_status: string;  // NEVER_SYNCED, SYNCED, FAILED
  readiness_state: string;
  readiness_reasons: string[];
  next_action: string | null;
  evidence: {
    pull_requests_count: number;
    active_pull_requests_count: number;
    test_runs_count: number;
    test_results_count: number;
    coverage_reports_count: number;
    recommendations_count: number;
    fragility_patterns_count: number;
  };
  health: {
    github_connection: string;
    webhook_status: string;
    test_history_status: string;
    coverage_status: string;
    recommendation_status: string;
    fragility_memory_status: string;
  };
}

interface PullRequest {
  id: string;
  number: number;
  title: string;
  author: string;
  source_branch: string;
  target_branch: string;
  state: string;
  head_commit_sha?: string | null;
  base_commit_sha?: string | null;
  merge_commit_sha?: string | null;
  changed_files_count: number;
  last_synced_at: string | null;
  sync_status: string;
  recommendation_status: string;
  latest_recommendation_run_id?: string | null;
  latest_recommendation_at?: string | null;
}

interface RecommendationResult {
  recommendation_run_id: string;
  pull_request_id: string;
  repository_id: string;
  recommended_tests_count: number;
  skipped_tests_count: number;
  estimated_runtime_seconds: number;
  full_suite_runtime_seconds: number | null;
  coverage_confidence: string;
  recommendation_mode: string;
  recommendation_readiness_state: string;
  risk_level: string;
  optimization_allowed: boolean;
  unsafe_for_optimization: boolean;
  runtime_confidence: string | null;
  reasons: string[];
  per_test_explanations: Record<string, string>;
  skipped_reason_summary: string | null;
  next_action: string;
  created_at: string;
}

interface PageProps {
  params: Promise<{ repositoryId: string }>;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "Not synced yet";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "Not synced yet";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "Not synced yet";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "Not synced yet";
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
}

// Helper function to calculate PR readiness information using centralized CTA resolver
function calculatePRReadiness(pr: any, result: any) {
  const missingSignals = [];
  let readinessLevel = "Ready";
  let expectedConfidence = "HIGH";
  let readinessScore = 1.0; // Default to 100%
  
  // Check for missing signals
  if (!pr.business_intent || !pr.business_intent.has_business_intent) {
    missingSignals.push("Acceptance Criteria");
  }
  
  if (!pr.current_pr_execution) {
    missingSignals.push("Current PR Execution");
  }
  
  if (!pr.coverage_report) {
    missingSignals.push("Coverage Report");
  }
  
  if (!pr.test_history) {
    missingSignals.push("Test History");
  }
  
  // Determine readiness level and confidence
  if (missingSignals.length === 0) {
    readinessLevel = "Ready";
    expectedConfidence = "HIGH";
    readinessScore = 0.86; // 86% for high confidence
  } else if (missingSignals.length <= 2) {
    readinessLevel = "Partial";
    expectedConfidence = "MEDIUM";
    readinessScore = 0.65; // 65% for medium confidence
  } else {
    readinessLevel = "Limited";
    expectedConfidence = "LOW";
    readinessScore = 0.40; // 40% for low confidence
  }
  
  // Check if recommendation is stale (older than 2 hours)
  const isStale = pr.latest_recommendation_at ? 
    new Date().getTime() - new Date(pr.latest_recommendation_at).getTime() > 2 * 60 * 60 * 1000 : 
    false;
  
  // Use centralized CTA resolver
  const ctaAction = resolveRecommendationAction({
    readiness_level: readinessLevel,
    expected_confidence: expectedConfidence,
    readiness_score: readinessScore,
    can_generate: true, // Assume can generate if not blocked
    blocking_inputs: [],
    missing_inputs: missingSignals.map(s => ({ key: s, label: s, severity: "REQUIRED" })),
    optional_inputs: [],
    latest_recommendation: {
      exists: pr.recommendation_status === "GENERATED",
      input_stale: isStale
    },
    recommendation_audit: {
      status: pr.recommendation_status === "GENERATED" ? (isStale ? "OUTDATED" : "AUDITABLE") : "NO_RECOMMENDATION_YET"
    }
  });
  
  return {
    readinessLevel,
    expectedConfidence,
    missingSignals,
    nextBestAction: ctaAction.primaryLabel,
    isStale,
    latestRecommendationTime: pr.latest_recommendation_at ? formatRelativeTime(pr.latest_recommendation_at) : null,
    ctaAction
  };
}

// Helper function to get readiness level styling
function getReadinessStyling(level: string) {
  switch (level) {
    case "Ready":
      return {
        bgColor: "bg-emerald-950/20",
        textColor: "text-emerald-400",
        borderColor: "border-emerald-800/40",
        icon: CheckCircle2
      };
    case "Partial":
      return {
        bgColor: "bg-amber-950/20",
        textColor: "text-amber-400",
        borderColor: "border-amber-800/40",
        icon: AlertTriangle
      };
    case "Limited":
      return {
        bgColor: "bg-rose-950/20",
        textColor: "text-rose-400",
        borderColor: "border-rose-800/40",
        icon: XCircle
      };
    default:
      return {
        bgColor: "bg-zinc-950/20",
        textColor: "text-zinc-400",
        borderColor: "border-zinc-800/40",
        icon: Clock
      };
  }
}

// Helper function to get confidence level styling
function getConfidenceStyling(level: string) {
  switch (level) {
    case "HIGH":
      return {
        bgColor: "bg-emerald-950/30",
        textColor: "text-emerald-400",
        borderColor: "border-emerald-800/50"
      };
    case "MEDIUM":
      return {
        bgColor: "bg-amber-950/30",
        textColor: "text-amber-400",
        borderColor: "border-amber-800/50"
      };
    case "LOW":
      return {
        bgColor: "bg-rose-950/30",
        textColor: "text-rose-400",
        borderColor: "border-rose-800/50"
      };
    default:
      return {
        bgColor: "bg-zinc-950/30",
        textColor: "text-zinc-400",
        borderColor: "border-zinc-800/50"
      };
  }
}

export default function RepositoryDetailPage({ params }: PageProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: session } = useSession();
  const [repositoryId, setRepositoryId] = useState<string | null>(null);
  const [repo, setRepo] = useState<Repository | null>(null);
  const [loading, setLoading] = useState(true);
  const [pullRequests, setPullRequests] = useState<PullRequest[]>([]);
  const [selectedPullRequestId, setSelectedPullRequestId] = useState<string | undefined>(() => {
    // Persist selected PR ID across page refreshes
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(`selectedPullRequestId_${repositoryId}`);
      return saved || undefined;
    }
    return undefined;
  });
  const [prsLoading, setPrsLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<{ synced_pull_requests: number; synced_changed_files: number } | null>(null);
  const [recommendationResults, setRecommendationResults] = useState<Map<string, RecommendationResult>>(new Map());
  const [runningRecommendation, setRunningRecommendation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [readinessRefreshTrigger, setReadinessRefreshTrigger] = useState(0);
  const [checkpointModal, setCheckpointModal] = useState<{
    isOpen: boolean;
    pullRequestId?: string;
    action: "generate" | "rerun" | "view";
    recommendationRunId?: string;
  }>({ isOpen: false, action: "generate" });

  // Generation status state for loading states
  const [generationStatus, setGenerationStatus] = useState<"idle" | "generating" | "redirecting" | "failed">("idle");
  const [redirectRecommendationId, setRedirectRecommendationId] = useState<string | null>(null);

  const [pageError, setPageError] = useState<{
    message: string;
    endpoint?: string;
    statusCode?: number;
  } | null>(null);

  // Store readiness data from the panel for use in PR rows and evidence summary.
  // Single source of truth: InputReadinessV2Panel emits the raw V2 response.
  const [selectedPRReadinessData, setSelectedPRReadinessData] = useState<any>(null);

  // Modal states for input readiness CTAs
  const [isBusinessReqModalOpen, setIsBusinessReqModalOpen] = useState(false);
  const [isReadinessDrawerOpen, setIsReadinessDrawerOpen] = useState(false);

  // Intelligence refresh progress state
  const [refreshState, setRefreshState] = useState<"idle" | "running" | "success" | "partial" | "failed">("idle");
  const [refreshStartedAt, setRefreshStartedAt] = useState<Date | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [refreshResult, setRefreshResult] = useState<any>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  // Run Repository Intelligence mutation (Input 3)
  const runRepositoryIntelligence = useCallback(async () => {
    if (!repositoryId || refreshState === "running") return;
    const selectedPR = pullRequests.find((p) => p.id === selectedPullRequestId);
    const headCommitSha = selectedPR ? selectedPR.head_commit_sha : null;
    
    setRefreshState("running");
    setRefreshStartedAt(new Date());
    setElapsedSeconds(0);
    setRefreshResult(null);
    setRefreshError(null);
    
    try {
      const res = await fetch(`/api/repositories/${repositoryId}/intelligence/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          include_architecture: true,
          include_behaviors: true,
          include_journeys: true,
          pull_request_id: selectedPullRequestId || null,
          head_commit_sha: headCommitSha || null,
        }),
      });
      const result = await res.json().catch(() => ({}));
      setRefreshResult(result);

      if (!res.ok) {
        setRefreshState("failed");
        setRefreshError(result?.error || result?.message || "Unknown error");
        toast.error("Intelligence refresh failed", {
          description: result?.error || result?.message || "Unknown error",
        });
        return;
      }

      const runStatus: string = result?.status ?? "SUCCESS";
      const score: number | null = result?.score ?? null;
      const maxScore: number | null = result?.max_score ?? null;
      const partialErrors: Array<{ code: string; message: string }> = result?.partial_errors ?? [];
      const failedSteps: string[] = result?.failed_steps ?? [];
      const specificBehaviors: number = result?.specific_behaviors_created ?? 0;
      const bbmCount: number = result?.business_behavior_mappings_created ?? 0;

      if (runStatus === "SUCCESS" && score === maxScore) {
        setRefreshState("success");
        const scoreLabel = score !== null && maxScore !== null ? ` (${score}/${maxScore})` : "";
        toast.success("Repository Intelligence refreshed" + scoreLabel, {
          description:
            specificBehaviors > 0
              ? `${specificBehaviors} specific behavior${specificBehaviors !== 1 ? "s" : ""} mapped, ${bbmCount} requirement link${bbmCount !== 1 ? "s" : ""} created.`
              : result?.message || "Intelligence refresh completed successfully.",
        });
      } else if (runStatus === "PARTIAL" || partialErrors.length > 0) {
        setRefreshState("partial");
        const topError = partialErrors[0];
        toast.warning("Intelligence refresh completed with warnings", {
          description:
            topError?.message ||
            (failedSteps.length > 0 ? `Steps with issues: ${failedSteps.join(", ")}` : result?.message),
        });
      } else {
        setRefreshState("failed");
        toast.error("Intelligence refresh failed", {
          description: result?.message || "Refresh did not complete.",
        });
      }
    } catch (err: any) {
      setRefreshState("failed");
      setRefreshError(err?.message || "Network error");
      toast.error("Intelligence refresh error", {
        description: err?.message || "Network error",
      });
    } finally {
      setReadinessRefreshTrigger((n) => n + 1);
    }
  }, [repositoryId, selectedPullRequestId, pullRequests, refreshState]);

  // Central CTA dispatcher — used by InputReadinessV2Panel, NBA section, PR row, banners
  const handleInputAction = useCallback((actionOrInputId: string, _inputId?: string) => {
    if (!repositoryId) return;
    executeInputAction(actionOrInputId, {
      repositoryId,
      pullRequestId: selectedPullRequestId,
      router,
      openBusinessRequirementsModal: () => setIsBusinessReqModalOpen(true),
      runRepositoryIntelligence,
      toast: (title, opts) => toast(title, { description: opts?.description }),
    });
  }, [repositoryId, selectedPullRequestId, router, runRepositoryIntelligence]);

  // PR sync state
  const [isSyncingPullRequests, setIsSyncingPullRequests] = useState(false);
  const [hasAttemptedInitialPrSync, setHasAttemptedInitialPrSync] = useState(false);
  const [prSyncError, setPrSyncError] = useState<string | null>(null);

  // Fetch repository data
  const fetchRepository = useCallback(async () => {
    if (!repositoryId) return;

    try {
      const headers: HeadersInit = {};
      if (session?.backendToken) {
        headers["Authorization"] = `Bearer ${session.backendToken}`;
      }
      const res = await fetch(
        `/api/repositories/${repositoryId}`,
        { headers, cache: "no-store" }
      );
      if (res.status === 401) {
        setPageError({
          message: "Your session has expired. Please sign in again.",
          endpoint: `/api/repositories/${repositoryId}`,
          statusCode: 401
        });
        return;
      }
      if (!res.ok) {
        setPageError({
          message: `Failed to load repository data (${res.statusText || res.status})`,
          endpoint: `/api/repositories/${repositoryId}`,
          statusCode: res.status
        });
        return;
      }
      const data = await res.json();
      setRepo(data);
      setPageError(null);
    } catch (err: any) {
      setPageError({
        message: err?.message || "Failed to contact backend server.",
        endpoint: `/api/repositories/${repositoryId}`
      });
    } finally {
      setLoading(false);
    }
  }, [repositoryId, session?.backendToken]);

  // Fetch pull requests
  const fetchPullRequests = useCallback(async () => {
    if (!repositoryId) return;

    setPrsLoading(true);
    try {
      const headers: HeadersInit = {};
      if (session?.backendToken) {
        headers["Authorization"] = `Bearer ${session.backendToken}`;
      }
      const res = await fetch(
        `/api/repositories/${repositoryId}/pull-requests`,
        { headers, cache: "no-store" }
      );
      if (res.status === 401) {
        setPageError({
          message: "Your session has expired. Please sign in again.",
          endpoint: `/api/repositories/${repositoryId}/pull-requests`,
          statusCode: 401
        });
        return;
      }
      if (!res.ok) {
        setError("Failed to fetch pull requests");
        return;
      }
      const data = await res.json();
      setPullRequests(data.pull_requests || []);
      setError(null);
    } catch (err: any) {
      setError(err?.message || "Failed to fetch pull requests");
    } finally {
      setPrsLoading(false);
    }
  }, [repositoryId, session?.backendToken]);

  // Check if PR sync is stale (older than 5 minutes)
  const isPrSyncStale = useCallback((): boolean => {
    if (!repo?.latest_pr_synced_at) return true;  // Never synced
    const syncTime = new Date(repo.latest_pr_synced_at);
    const now = new Date();
    const diffMs = now.getTime() - syncTime.getTime();
    const diffMins = diffMs / 60000;
    return diffMins > 5;  // Stale if older than 5 minutes
  }, [repo]);



  // Auto-sync pull requests if needed
  const autoSyncPullRequests = useCallback(async () => {
    if (!repositoryId || isSyncingPullRequests || hasAttemptedInitialPrSync) return;

    // Auto-sync if: never synced, sync failed, or sync is stale
    const shouldAutoSync = !repo?.latest_pr_synced_at ||
                           repo?.pr_sync_status === "FAILED" ||
                           isPrSyncStale();

    if (!shouldAutoSync) return;

    setIsSyncingPullRequests(true);
    setPrSyncError(null);
    try {
      const headers: HeadersInit = {};
      if (session?.backendToken) {
        headers["Authorization"] = `Bearer ${session.backendToken}`;
      }
      const res = await fetch(
        `/api/repositories/${repositoryId}/pull-requests/sync`,
        { method: "POST", headers, cache: "no-store" }
      );
      if (res.status === 401) {
        setPageError({
          message: "Your session has expired. Please sign in again.",
          endpoint: `/api/repositories/${repositoryId}/pull-requests/sync`,
          statusCode: 401
        });
        return;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setPrSyncError(data?.error || `Sync failed (${res.status})`);
        return;
      }
      // Refetch both PR list and repo detail so all stats update immediately
      await Promise.all([fetchPullRequests(), fetchRepository()]);
      // Trigger readiness panel refresh
      setReadinessRefreshTrigger(prev => prev + 1);
    } catch (err: any) {
      setPrSyncError(err?.message || "Sync failed. Check backend connectivity.");
    } finally {
      setIsSyncingPullRequests(false);
      setHasAttemptedInitialPrSync(true);
    }
  }, [repositoryId, repo, isSyncingPullRequests, hasAttemptedInitialPrSync, isPrSyncStale, fetchPullRequests, fetchRepository, session?.backendToken]);

  // Manually sync pull requests from GitHub
  const syncPullRequests = useCallback(async () => {
    if (!repositoryId) return;
    setSyncing(true);
    setSyncResult(null);
    setError(null);
    setPrSyncError(null);
    try {
      const headers: HeadersInit = {};
      if (session?.backendToken) {
        headers["Authorization"] = `Bearer ${session.backendToken}`;
      }
      const res = await fetch(
        `/api/repositories/${repositoryId}/pull-requests/sync`,
        { method: "POST", headers, cache: "no-store" }
      );
      if (res.status === 401) {
        setPageError({
          message: "Your session has expired. Please sign in again.",
          endpoint: `/api/repositories/${repositoryId}/pull-requests/sync`,
          statusCode: 401
        });
        return;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const errorMessage = data?.message || data?.error || `Sync failed (${res.status})`;
        const errorAction = data?.action ? ` ${data.action}` : "";
        toast.error("Could not sync pull requests", {
          description: `${errorMessage}${errorAction}`,
        });
        setPrSyncError(errorMessage);
        return;
      }
      setSyncResult({ synced_pull_requests: data.synced_pull_requests, synced_changed_files: data.synced_changed_files });
      toast.success("Pull requests synced", {
        description: `${data.synced_pull_requests} PR${data.synced_pull_requests !== 1 ? "s" : ""} · ${data.synced_changed_files} changed file${data.synced_changed_files !== 1 ? "s" : ""}`,
      });
      // Refetch both PR list and repo detail so all stats update immediately
      await Promise.all([fetchPullRequests(), fetchRepository()]);
      // Trigger readiness panel refresh
      setReadinessRefreshTrigger(prev => prev + 1);
    } catch (err: any) {
      toast.error("Could not sync pull requests", {
        description: err?.message || "Sync failed. Check backend connectivity.",
      });
      setPrSyncError(err?.message || "Sync failed. Check backend connectivity.");
    } finally {
      setSyncing(false);
      setHasAttemptedInitialPrSync(true);
    }
  }, [repositoryId, fetchPullRequests, fetchRepository, session?.backendToken]);

  // Show checkpoint modal before generating recommendation
  const showCheckpointModal = useCallback((prId: string, action: "generate" | "rerun") => {
    setCheckpointModal({
      isOpen: true,
      pullRequestId: prId,
      action: action
    });
  }, []);

  // Trigger recommendation for a PR (after checkpoint confirmation)
  const triggerRecommendation = useCallback(async (prId: string, generationMode?: string) => {
    if (!repositoryId) return;

    // Prevent double-submit
    if (generationStatus !== "idle") return;

    setGenerationStatus("generating");
    setRunningRecommendation(prId);
    try {
      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };
      if (session?.backendToken) {
        headers["Authorization"] = `Bearer ${session.backendToken}`;
      }
      const res = await fetch(
        `/api/repositories/${repositoryId}/pull-requests/${prId}/recommendation`,
        {
          method: "POST",
          cache: "no-store",
          headers,
          body: JSON.stringify({
            repository_id: repositoryId,
            pull_request_id: prId,
            triggered_by: "engineer-manual",
            readiness_acknowledged: true,
            mode: generationMode || "confident"
          })
        }
      );
      if (res.status === 401) {
        setPageError({
          message: "Your session has expired. Please sign in again.",
          endpoint: `/api/repositories/${repositoryId}/pull-requests/${prId}/recommendation`,
          statusCode: 401
        });
        setGenerationStatus("failed");
        return;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        let description = data?.detail || data?.message || data?.error || `Engine error (${res.status})`;

        // If backend provided a detailed error, use it
        if (data?.error_code) {
          description = `${data.error_code}: ${description}`;
        }

        // Log for debugging without triggering DevOverlay
        console.warn("Recommendation generation failed:", res.status, data);

        toast.error("Recommendation failed", {
          description,
        });
        setGenerationStatus("failed");
        return;
      }

      // Check for success flag and extract redirect info
      const isSuccess = data?.success === true;
      const redirectUrl = data?.redirect_url;
      const runId = data?.recommendation_run_id;

      if (!isSuccess) {
        toast.error("Recommendation generation failed", {
          description: "Backend did not confirm successful generation.",
        });
        setGenerationStatus("failed");
        return;
      }

      // Determine redirect URL
      let finalRedirectUrl = redirectUrl;
      if (!finalRedirectUrl && runId) {
        finalRedirectUrl = `/app/recommendations/${runId}`;
      }

      if (!finalRedirectUrl) {
        toast.error("Recommendation generated but no ID returned", {
          description: "Recommendation was generated but no recommendation ID was returned.",
          action: {
            label: "Open latest recommendation",
            onClick: () => router.push("/app/recommendations"),
          },
        });
        setGenerationStatus("failed");
        return;
      }

      // Store the recommendation ID for fallback
      setRedirectRecommendationId(runId);

      // Update status to redirecting
      setGenerationStatus("redirecting");

      toast.success("Recommendation complete", {
        description: `${data.recommended_tests_count} test${data.recommended_tests_count !== 1 ? "s" : ""} recommended · mode: ${data.recommendation_mode}`,
      });

      // Refetch PR list to update recommendation status badge
      await fetchPullRequests();

      // Close readiness modal if open (for generate action)
      if (checkpointModal.isOpen && checkpointModal.action === "generate") {
        setCheckpointModal({ isOpen: false, pullRequestId: undefined, action: "generate" });
      }

      // Route to the recommendation result page
      try {
        await router.push(finalRedirectUrl);
      } catch (redirectErr) {
        console.error("Redirect failed:", redirectErr);
        setGenerationStatus("failed");
        toast.error("Redirect failed", {
          description: "Recommendation generated, but we could not open it automatically.",
          action: {
            label: "Open Recommendation",
            onClick: () => {
              if (runId) router.push(`/app/recommendations/${runId}`);
            },
          },
        });
      }
    } catch (err: any) {
      toast.error("Recommendation failed", {
        description: err?.message || "Could not reach backend.",
      });
      setGenerationStatus("failed");
    } finally {
      setRunningRecommendation(null);
      // Reset status after a delay (redirect will navigate away anyway)
      setTimeout(() => setGenerationStatus("idle"), 500);
    }
  }, [repositoryId, router, fetchPullRequests, session?.backendToken, checkpointModal]);

  const handleViewRecommendation = useCallback(async (runId: string, prId: string) => {
    // Prevent double-submit
    if (generationStatus !== "idle") return;

    setGenerationStatus("redirecting");
    setRedirectRecommendationId(runId);
    try {
      const headers: HeadersInit = {};
      if (session?.backendToken) {
        headers["Authorization"] = `Bearer ${session.backendToken}`;
      }
      const response = await fetch(`/api/recommendations/${runId}`, { headers });
      if (response.status === 401) {
        setPageError({
          message: "Your session has expired. Please sign in again.",
          endpoint: `/api/recommendations/${runId}`,
          statusCode: 401
        });
        setGenerationStatus("failed");
        return;
      }
      if (!response.ok) {
        throw new Error("Failed to fetch recommendation run details");
      }
      const run = await response.json();

      const hasMissingInputs = run.completeness_assessment?.missing_recommended_inputs?.length > 0 || false;
      const isLowConfidence = run.evidence_quality === "LOW" || run.runtime_confidence === "LOW";

      if (run.readiness_acknowledged || (!isLowConfidence && !hasMissingInputs)) {
        try {
          await router.push(`/app/recommendations/${runId}`);
        } catch (redirectErr) {
          console.error("Redirect failed:", redirectErr);
          setGenerationStatus("failed");
          toast.error("Redirect failed", {
            description: "Could not open the recommendation automatically.",
            action: {
              label: "Open Recommendation",
              onClick: () => router.push(`/app/recommendations/${runId}`),
            },
          });
        }
      } else {
        setGenerationStatus("idle");
        setCheckpointModal({
          isOpen: true,
          pullRequestId: prId,
          action: "view",
          recommendationRunId: runId
        });
      }
    } catch (err: any) {
      console.error("Error checking recommendation readiness:", err);
      setGenerationStatus("failed");
      toast.error("Failed to load recommendation", {
        description: err?.message || "Could not reach backend.",
      });
    }
  }, [router, repositoryId, session?.backendToken, generationStatus]);

  // Handle checkpoint modal continue action
  const handleCheckpointContinue = useCallback((generationMode?: string) => {
    if (checkpointModal.action === "view" && checkpointModal.recommendationRunId) {
      router.push(`/app/recommendations/${checkpointModal.recommendationRunId}`);
    } else if (checkpointModal.pullRequestId) {
      triggerRecommendation(checkpointModal.pullRequestId, generationMode);
    }
  }, [checkpointModal.action, checkpointModal.pullRequestId, checkpointModal.recommendationRunId, triggerRecommendation, router]);

  // Initialize repositoryId from params
  useEffect(() => {
    params.then(p => setRepositoryId(p.repositoryId));
  }, [params]);

  // Fetch repository when repositoryId is set
  useEffect(() => {
    if (repositoryId) fetchRepository();
  }, [repositoryId, fetchRepository]);

  // Fetch PRs when repositoryId is set
  useEffect(() => {
    if (repositoryId) fetchPullRequests();
  }, [repositoryId, fetchPullRequests]);

  // Default selectedPullRequestId to first PR when PRs are loaded
  useEffect(() => {
    if (pullRequests.length > 0 && !selectedPullRequestId) {
      // Default to the first PR
      setSelectedPullRequestId(pullRequests[0].id);
    }
  }, [pullRequests, selectedPullRequestId]);

  // Persist selected PR ID to localStorage
  useEffect(() => {
    if (repositoryId && selectedPullRequestId) {
      localStorage.setItem(`selectedPullRequestId_${repositoryId}`, selectedPullRequestId);
    } else if (repositoryId && selectedPullRequestId === undefined) {
      localStorage.removeItem(`selectedPullRequestId_${repositoryId}`);
    }
  }, [repositoryId, selectedPullRequestId]);

  // selectedPRReadinessData is updated by InputReadinessV2Panel via onReadinessDataChange.
  // This single source of truth is used for the evidence summary, PR row, and drawer.

  // Auto-open readiness modal if openReadiness query param is set
  useEffect(() => {
    const openReadiness = searchParams.get("openReadiness");
    const urlPullRequestId = searchParams.get("pullRequestId");

    if (openReadiness === "true" && urlPullRequestId) {
      // Set the selected PR ID
      setSelectedPullRequestId(urlPullRequestId);
      
      // Open the checkpoint modal (readiness gate modal)
      setCheckpointModal({
        isOpen: true,
        pullRequestId: urlPullRequestId,
        action: "generate"
      });

      // Clear the query params from the URL using window.history.replaceState
      const url = new URL(window.location.href);
      url.searchParams.delete("openReadiness");
      url.searchParams.delete("pullRequestId");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
  }, [searchParams]);

  // Auto-sync PRs when repository is loaded and sync is needed
  useEffect(() => {
    if (repo && repositoryId) {
      autoSyncPullRequests();
    }
  }, [repo, repositoryId, autoSyncPullRequests]);

  // Elapsed timer for intelligence refresh
  useEffect(() => {
    if (refreshState !== "running" || !refreshStartedAt) return;

    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - refreshStartedAt.getTime()) / 1000));
    }, 1000);

    return () => clearInterval(interval);
  }, [refreshState, refreshStartedAt]);

  // Format elapsed time as mm:ss
  const formatElapsed = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Get progress message based on elapsed time
  const getProgressMessage = (): string => {
    if (elapsedSeconds < 30) {
      return "Repository intelligence is running. This can take up to 2 minutes.";
    } else if (elapsedSeconds < 90) {
      return "Still working… Large repositories can take 1–2 minutes. Do not close this page.";
    } else {
      return "Almost there… Finalizing behavior mappings and readiness.";
    }
  };

  // Intelligence refresh progress panel component
  const IntelligenceRefreshProgressPanel = () => {
    if (refreshState === "idle") return null;

    if (refreshState === "running") {
      return (
        <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-zinc-400 animate-spin" />
            <div>
              <h3 className="text-sm font-semibold text-zinc-200">Refreshing Product Behavior Map…</h3>
              <p className="text-xs text-zinc-500 mt-0.5">Elapsed: {formatElapsed(elapsedSeconds)}</p>
            </div>
          </div>
          <div className="bg-zinc-950/50 border border-zinc-800/40 rounded-lg p-4">
            <p className="text-xs text-zinc-400">Status:</p>
            <p className="text-sm text-zinc-300 mt-1">{getProgressMessage()}</p>
          </div>
        </div>
      );
    }

    if (refreshState === "success" && refreshResult) {
      return (
        <div className="bg-emerald-950/20 border border-emerald-800/40 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            <div>
              <h3 className="text-sm font-semibold text-emerald-300">Product Behavior Map Ready</h3>
              <p className="text-xs text-zinc-500 mt-0.5">
                Score: {refreshResult.score}/{refreshResult.max_score}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="bg-zinc-950/50 border border-zinc-800/40 rounded-lg p-3">
              <p className="text-zinc-500">Specific behaviors created</p>
              <p className="text-emerald-300 font-semibold mt-1">{refreshResult.specific_behaviors_created || 0}</p>
            </div>
            <div className="bg-zinc-950/50 border border-zinc-800/40 rounded-lg p-3">
              <p className="text-zinc-500">Requirement mappings created</p>
              <p className="text-emerald-300 font-semibold mt-1">{refreshResult.business_behavior_mappings_created || 0}</p>
            </div>
          </div>
          {refreshResult.completed_steps && refreshResult.completed_steps.length > 0 && (
            <div className="bg-zinc-950/50 border border-zinc-800/40 rounded-lg p-3">
              <p className="text-xs text-zinc-500 mb-2">Completed steps:</p>
              <div className="space-y-1">
                {refreshResult.completed_steps.map((step: string) => (
                  <div key={step} className="flex items-center gap-2 text-xs text-zinc-300">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    <span>{step.replace(/_/g, " ")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    }

    if (refreshState === "partial" && refreshResult) {
      return (
        <div className="bg-amber-950/20 border border-amber-800/40 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            <div>
              <h3 className="text-sm font-semibold text-amber-300">Product Behavior Map Partial</h3>
              <p className="text-xs text-zinc-500 mt-0.5">
                Score: {refreshResult.score}/{refreshResult.max_score}
              </p>
            </div>
          </div>
          {refreshResult.partial_errors && refreshResult.partial_errors.length > 0 && (
            <div className="bg-zinc-950/50 border border-zinc-800/40 rounded-lg p-3">
              <p className="text-xs text-zinc-500 mb-2">Reason:</p>
              {refreshResult.partial_errors.map((error: any, idx: number) => (
                <div key={idx} className="mb-2 last:mb-0">
                  <p className="text-xs text-amber-300 font-medium">{error.code}</p>
                  <p className="text-xs text-zinc-300 mt-0.5">{error.message}</p>
                  {error.next_action && (
                    <p className="text-xs text-zinc-400 mt-1">Next action: {error.next_action}</p>
                  )}
                </div>
              ))}
            </div>
          )}
          {refreshResult.failed_steps && refreshResult.failed_steps.length > 0 && (
            <div className="bg-zinc-950/50 border border-zinc-800/40 rounded-lg p-3">
              <p className="text-xs text-zinc-500 mb-2">Failed steps:</p>
              {refreshResult.failed_steps.map((step: string) => (
                <div key={step} className="flex items-center gap-2 text-xs text-rose-300">
                  <XCircle className="w-3 h-3" />
                  <span>{step.replace(/_/g, " ")}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    if (refreshState === "failed") {
      return (
        <div className="bg-rose-950/20 border border-rose-800/40 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-3">
            <XCircle className="w-5 h-5 text-rose-400" />
            <div>
              <h3 className="text-sm font-semibold text-rose-300">Product Behavior Map Refresh Failed</h3>
            </div>
          </div>
          {refreshError && (
            <div className="bg-zinc-950/50 border border-zinc-800/40 rounded-lg p-3">
              <p className="text-xs text-zinc-500 mb-2">Error:</p>
              <p className="text-xs text-rose-300">{refreshError}</p>
            </div>
          )}
          {refreshResult?.failed_steps && refreshResult.failed_steps.length > 0 && (
            <div className="bg-zinc-950/50 border border-zinc-800/40 rounded-lg p-3">
              <p className="text-xs text-zinc-500 mb-2">Failed step:</p>
              {refreshResult.failed_steps.map((step: string) => (
                <div key={step} className="flex items-center gap-2 text-xs text-rose-300">
                  <XCircle className="w-3 h-3" />
                  <span>{step.replace(/_/g, " ")}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    return null;
  };

  function getReadinessBadge(state: string | null | undefined) {
    const safeState = state || "UNKNOWN";
    const configs: Record<string, { bg: string; text: string; icon: any }> = {
      READY: { bg: "bg-emerald-950/20", text: "text-emerald-400/80", icon: Sparkles },
      NEEDS_TEST_HISTORY: { bg: "bg-amber-950/20", text: "text-amber-400/70", icon: FlaskConical },
      NEEDS_COVERAGE: { bg: "bg-amber-950/20", text: "text-amber-400/70", icon: BarChart2 },
      SYNC_FAILED: { bg: "bg-rose-950/20", text: "text-rose-400/70", icon: AlertTriangle },
      NOT_SELECTED: { bg: "bg-zinc-800", text: "text-zinc-400", icon: AlertTriangle },
      REMOVED_OR_INACTIVE: { bg: "bg-zinc-800", text: "text-zinc-500", icon: AlertTriangle },
      UNKNOWN: { bg: "bg-zinc-800", text: "text-zinc-400", icon: AlertTriangle },
    };
    const config = configs[safeState] || configs.UNKNOWN;
    const Icon = config.icon;
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
        <Icon className="w-3.5 h-3.5" />
        {safeState.replace(/_/g, " ")}
      </span>
    );
  }

  if (loading) {
    return (
      <div className="space-y-6 max-w-5xl">
        {/* Header skeleton */}
        <div className="flex items-center gap-4 animate-pulse">
          <div className="h-8 w-8 bg-zinc-800 rounded-lg" />
          <div className="h-6 w-48 bg-zinc-800 rounded-lg" />
        </div>
        {/* Metadata grid skeleton */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 animate-pulse">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-4">
              <div className="h-4 w-24 bg-zinc-800 rounded mb-2" />
              <div className="h-5 w-16 bg-zinc-800 rounded" />
            </div>
          ))}
        </div>
        {/* Readiness panel skeleton */}
        <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 animate-pulse">
          <div className="h-4 w-32 bg-zinc-800 rounded mb-4" />
          <div className="h-4 w-48 bg-zinc-800 rounded mb-2" />
          <div className="h-4 w-64 bg-zinc-800 rounded" />
        </div>
        {/* Evidence health skeleton */}
        <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 animate-pulse">
          <div className="h-4 w-32 bg-zinc-800 rounded mb-4" />
          <div className="space-y-3">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="h-4 w-full bg-zinc-800 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (pageError) {
    return (
      <div className="space-y-6 max-w-5xl animate-fade-in">
        <div className="flex items-center gap-4">
          <Link href="/app/repositories">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white">Could not load repository details</h1>
            <p className="text-sm text-zinc-500">Veriscope could not load this repository.</p>
          </div>
        </div>

        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-12 text-center max-w-2xl mx-auto space-y-6">
          <div className="w-16 h-16 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto shadow-lg shadow-white/5">
            <AlertTriangle className="w-8 h-8 text-rose-500" />
          </div>
          
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-white">Could not load repository details</h2>
            <p className="text-sm text-zinc-400 max-w-md mx-auto leading-relaxed">
              Veriscope could not load this repository.
            </p>
          </div>

          {/* Technical Details (Short message always, details in dev) */}
          <div className="bg-zinc-950/60 border border-zinc-900 rounded-xl p-4 font-mono text-xs text-left max-w-md mx-auto space-y-2 text-zinc-400">
            <p>
              <span className="text-zinc-500 font-bold">Repository ID:</span> {repositoryId || "unknown"}
            </p>
            {pageError.endpoint && (
              <p className="truncate" title={pageError.endpoint}>
                <span className="text-zinc-550 font-bold">Endpoint:</span> {pageError.endpoint}
              </p>
            )}
            {pageError.statusCode && (
              <p>
                <span className="text-zinc-550 font-bold">Status Code:</span> {pageError.statusCode}
              </p>
            )}
            <p className="text-rose-400/80">
              <span className="text-zinc-550 font-bold">Error:</span> {pageError.message}
            </p>
          </div>

          <div className="flex justify-center gap-3">
            <Button
              onClick={() => {
                setPageError(null);
                setLoading(true);
                fetchRepository();
                fetchPullRequests();
              }}
              className="bg-white text-zinc-950 hover:bg-zinc-100 font-semibold"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Retry
            </Button>
            <Link href="/app/repositories">
              <Button variant="outline" className="border-zinc-800 bg-transparent text-zinc-350 hover:bg-zinc-900 hover:text-white">
                Back to Repositories
              </Button>
            </Link>
            {repositoryId && (
              <Button
                variant="outline"
                onClick={async () => {
                  toast.promise(
                    (async () => {
                      const headers: HeadersInit = {};
                      if (session?.backendToken) {
                        headers["Authorization"] = `Bearer ${session.backendToken}`;
                      }
                      const res = await fetch(`/api/repositories/${repositoryId}/sync`, {
                        method: "POST",
                        headers
                      });
                      if (!res.ok) throw new Error("Sync failed");
                      setPageError(null);
                      setLoading(true);
                      await Promise.all([fetchRepository(), fetchPullRequests()]);
                    })(),
                    {
                      loading: "Syncing repository metadata...",
                      success: "Repository synced successfully",
                      error: "Failed to sync repository"
                    }
                  );
                }}
                className="border-zinc-800 bg-transparent text-zinc-350 hover:bg-zinc-900 hover:text-white"
              >
                Sync Repository
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // 404 if repo not found or doesn't belong to workspace
  if (!repo) {
    return (
      <div className="space-y-6 max-w-5xl">
        <div className="flex items-center gap-4">
          <Link href="/app/repositories">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white">Repository Not Found</h1>
            <p className="text-sm text-zinc-500">The repository does not exist or you don't have access</p>
          </div>
        </div>
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-zinc-800 flex items-center justify-center mx-auto mb-4">
            <Github className="w-8 h-8 text-zinc-500" />
          </div>
          <h2 className="text-lg font-semibold text-white mb-2">Repository Not Found</h2>
          <p className="text-sm text-zinc-400 max-w-md mx-auto mb-6">
            This repository may have been removed, or you may not have permission to view it.
          </p>
          <Link href="/app/repositories">
            <Button className="bg-white text-zinc-950 hover:bg-zinc-100">
              Back to Repositories
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link href="/app/repositories">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-xl font-bold text-white truncate" title={repo.full_name}>
                {repo.full_name}
              </h1>
              {repo.visibility === "PRIVATE" ? (
                <Lock className="w-4 h-4 text-zinc-500" />
              ) : (
                <Globe className="w-4 h-4 text-zinc-500" />
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <span className={repo.health.github_connection === "CONNECTED" ? "text-emerald-400" : "text-rose-400"}>
                {repo.health.github_connection === "CONNECTED" ? "Connected" : "Disconnected"}
              </span>
              <span>·</span>
              <span>Repo synced {formatRelativeTime(repo.last_synced_at)}</span>
              <span>·</span>
              <span>PR sync {formatRelativeTime(repo.latest_pr_synced_at)}</span>
              <span>·</span>
              <span>{repo.evidence.active_pull_requests_count || 0} active PR</span>
            </div>
          </div>
        </div>
        <a
          href={`https://github.com/${repo.full_name}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-white">
            <Github className="w-4 h-4 mr-1" />
            GitHub
            <ExternalLink className="w-3 h-3 ml-1" />
          </Button>
        </a>
      </div>


      {/* Part 5: Selected PR Change Package Card - Using normalized PR package adapter */}
      {selectedPullRequestId && selectedPRReadinessData && (() => {
        const selectedPR = pullRequests.find(pr => pr.id === selectedPullRequestId);
        const normalizedPRPackage = normalizePRPackage(selectedPR, selectedPRReadinessData);
        return <PRPackageSummaryCard prPackage={normalizedPRPackage} />;
      })()}

      {/* Business Requirements Readiness Card */}
      {selectedPullRequestId && (
        <BusinessRequirementsReadinessCard
          repositoryId={repo.id}
          pullRequestId={selectedPullRequestId}
        />
      )}

      {/* Intelligence Refresh Progress Panel */}
      <IntelligenceRefreshProgressPanel />

      {/* Recommendation Readiness Panel */}
      <RecommendationReadinessPanel
        repositoryId={repo.id}
        repositoryName={repo.full_name}
        repositoryStatus={repo.health.github_connection === "CONNECTED" ? "CONNECTED" : "DISCONNECTED"}
        pullRequestId={selectedPullRequestId}
        refreshTrigger={readinessRefreshTrigger}
        onReadinessDataChange={setSelectedPRReadinessData}
        onAction={handleInputAction}
        runRepositoryIntelligence={runRepositoryIntelligence}
        refreshState={refreshState}
      />

      {/* Part 7: Selected PR Evidence Summary — V2 readiness model */}
      {selectedPullRequestId && selectedPRReadinessData ? (
        <div className="flex items-center gap-3 text-xs text-zinc-500 px-3 py-2 bg-zinc-900/20 border border-zinc-800/40 rounded-lg flex-wrap">
          <span className="font-medium text-zinc-400">Selected PR Evidence</span>
          <span>·</span>
          {(() => {
            const v2 = selectedPRReadinessData;
            const getInputStatus = (id: string) =>
              v2.inputs?.find((i: any) => i.input_id === id)?.status ?? "MISSING";

            const i1Status = getInputStatus("INPUT_1");
            const i2Status = getInputStatus("INPUT_2");
            const i4Status = getInputStatus("INPUT_4");
            const i4Input = v2.inputs?.find((i: any) => i.input_id === "INPUT_4");
            const i4Details = i4Input?.details as any;
            const i4BasicStatus = i4Details?.basic_inventory_status ?? "UNKNOWN";
            const i4IntelligenceStatus = i4Details?.overall_intelligence_status ?? "UNKNOWN";
            const i5Status = getInputStatus("INPUT_5");
            const i6Status = getInputStatus("INPUT_6");
            const i7Status = getInputStatus("INPUT_7");

            const statusColor = (s: string) =>
              s === "READY" ? "text-emerald-400"
              : s === "PARTIAL" ? "text-amber-400"
              : s === "STALE" ? "text-orange-400"
              : s === "NEEDS_REVIEW" ? "text-amber-400"
              : "text-rose-400";

            const genStatusLabel: Record<string, string> = {
              BLOCKED: "Blocked",
              DRAFT_ONLY: "Draft Only",
              MINIMUM_READY: "Min. Ready",
              CONFIDENT_READY: "Confident",
              HIGH_CONFIDENCE_READY: "High Confidence",
            };
            const genStatusColor: Record<string, string> = {
              BLOCKED: "text-rose-400",
              DRAFT_ONLY: "text-amber-400",
              MINIMUM_READY: "text-zinc-300",
              CONFIDENT_READY: "text-emerald-400",
              HIGH_CONFIDENCE_READY: "text-emerald-300",
            };

            return (
              <>
                <span className={`font-semibold ${genStatusColor[v2.generation_status] ?? "text-zinc-400"}`}>
                  {genStatusLabel[v2.generation_status] ?? v2.generation_status}
                </span>
                <span>·</span>
                <span className={statusColor(i1Status)}>PR Package: {i1Status === "READY" ? "Ready" : i1Status === "PARTIAL" ? "Partial" : "Missing"}</span>
                <span>·</span>
                <span className={statusColor(i2Status)}>Requirements: {i2Status === "READY" ? "Ready" : i2Status === "PARTIAL" ? "Partial" : i2Status === "NEEDS_REVIEW" ? "Needs Review" : "Missing"}</span>
                <span>·</span>
                <span className={statusColor(i4BasicStatus)}>Test Inventory: {i4BasicStatus === "READY" ? "Ready" : i4BasicStatus === "PARTIAL" ? "Partial" : "Missing"}</span>
                <span>·</span>
                <span className={statusColor(i4IntelligenceStatus)}>Test Intelligence: {i4IntelligenceStatus === "READY" ? "Ready" : i4IntelligenceStatus === "PARTIAL" ? "Partial" : "Missing"}</span>
                <span>·</span>
                <span className={statusColor(i5Status)}>AC/Test Mapping: {i5Status === "READY" ? "Ready" : i5Status === "PARTIAL" ? "Partial" : i5Status === "NEEDS_REVIEW" ? "Review Needed" : "Missing"}</span>
                <span>·</span>
                <span className={statusColor(i6Status)}>PR Execution: {i6Status === "READY" ? "Ready" : i6Status === "STALE" ? "Stale" : "Missing"}</span>
                <span>·</span>
                <span className={statusColor(i7Status)}>Coverage: {i7Status === "READY" ? "Ready" : i7Status === "HISTORICAL_ONLY" ? "Historical Only" : i7Status === "STALE" ? "Stale" : i7Status === "PARTIAL" ? "Partial" : "Missing"}</span>
                <span>·</span>
                <span className="font-mono">{Math.round(v2.evidence_completeness ?? 0)}% evidence completeness</span>
                <span>·</span>
                <span className={statusColor(v2.release_confidence ?? "LOW")}>Release Confidence: {v2.release_confidence?.toLowerCase() ?? "low"}</span>
                <span>·</span>
                <span className={statusColor(v2.confidence_ceiling ?? "LOW")}>Ceiling: {v2.confidence_ceiling?.toLowerCase() ?? "low"}</span>
              </>
            );
          })()}
        </div>
      ) : (
        <div className="flex items-center gap-4 text-xs text-zinc-500 px-3 py-2 bg-zinc-900/20 border border-zinc-800/40 rounded-lg">
          <span className="font-medium text-zinc-400">Repository Evidence</span>
          <span>·</span>
          <span>PRs: {repo.evidence.pull_requests_count || 0}</span>
          <span>·</span>
          <span>Test runs: {repo.evidence.test_runs_count || 0}</span>
          <span>·</span>
          <span>Coverage reports: {repo.evidence.coverage_reports_count || 0}</span>
          <span>·</span>
          <span>Recommendations: {repo.evidence.recommendations_count || 0}</span>
        </div>
      )}

      {/* Pull Requests Section */}
      <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">Pull Requests</h3>
            <p className="text-xs text-zinc-500 mt-0.5">
              Synced from GitHub App installation
              {repo.latest_pr_synced_at && (
                <span className="ml-1 text-zinc-600">· last synced {formatRelativeTime(repo.latest_pr_synced_at)}</span>
              )}
            </p>
          </div>
          <Button
            onClick={syncPullRequests}
            disabled={syncing}
            variant="outline"
            className="shrink-0 border-zinc-700 bg-zinc-800/60 text-zinc-300 hover:bg-zinc-700 hover:text-white hover:border-zinc-600 transition-all px-4 h-9 text-sm font-medium"
          >
            {syncing ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Syncing…
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4 mr-2" />
                Sync Pull Requests
              </>
            )}
          </Button>
        </div>

        {syncResult && (
          <div className="mb-4 px-3 py-2 rounded-lg bg-emerald-950/20 border border-emerald-800/40 text-xs text-emerald-400">
            Synced {syncResult.synced_pull_requests} pull request{syncResult.synced_pull_requests !== 1 ? "s" : ""} · {syncResult.synced_changed_files} changed file{syncResult.synced_changed_files !== 1 ? "s" : ""}.
          </div>
        )}
        
        {prsLoading || isSyncingPullRequests ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 text-zinc-500 animate-spin" />
            <span className="ml-2 text-sm text-zinc-500">
              {isSyncingPullRequests ? "Syncing pull requests from GitHub..." : "Loading pull requests..."}
            </span>
          </div>
        ) : prSyncError ? (
          <div className="text-center py-8">
            <div className="w-12 h-12 rounded-lg bg-rose-950/20 flex items-center justify-center mx-auto mb-3">
              <AlertTriangle className="w-6 h-6 text-rose-400" />
            </div>
            <h4 className="text-sm font-medium text-zinc-200 mb-1">Could not sync pull requests</h4>
            <p className="text-xs text-zinc-500 max-w-sm mx-auto mb-3">
              {prSyncError}
            </p>
            <Button
              onClick={syncPullRequests}
              disabled={syncing}
              variant="outline"
              size="sm"
              className="shrink-0 border-zinc-700 bg-zinc-800/60 text-zinc-300 hover:bg-zinc-700 hover:text-white hover:border-zinc-600 transition-all"
            >
              {syncing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Retrying...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Retry Sync
                </>
              )}
            </Button>
          </div>
        ) : pullRequests.length === 0 && hasAttemptedInitialPrSync ? (
          <div className="text-center py-8">
            <div className="w-12 h-12 rounded-lg bg-zinc-800 flex items-center justify-center mx-auto mb-3">
              <GitPullRequest className="w-6 h-6 text-zinc-500" />
            </div>
            <h4 className="text-sm font-medium text-zinc-200 mb-1">No active pull requests found</h4>
            <p className="text-xs text-zinc-500 max-w-sm mx-auto">
              No open pull requests found in GitHub after syncing.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {pullRequests.map((pr) => {
              const result = recommendationResults.get(pr.id);
              const isRunning = runningRecommendation === pr.id;
              
              // Normalize PR package data
              const normalizedPRPackage = normalizePRPackage(
                pr, 
                pr.id === selectedPullRequestId ? selectedPRReadinessData : undefined
              );
              
              // Use V2 readiness data for selected PR, fall back for others
              let readiness;
              if (pr.id === selectedPullRequestId && selectedPRReadinessData) {
                const v2 = selectedPRReadinessData;
                const genStatus: Record<string, string> = {
                  BLOCKED: "Blocked",
                  DRAFT_ONLY: "Draft Only",
                  MINIMUM_READY: "Minimum Ready",
                  CONFIDENT_READY: "Ready",
                  HIGH_CONFIDENCE_READY: "Ready",
                };
                const genConfidence: Record<string, string> = {
                  BLOCKED: "LOW",
                  DRAFT_ONLY: "LOW",
                  MINIMUM_READY: "MEDIUM",
                  CONFIDENT_READY: "HIGH",
                  HIGH_CONFIDENCE_READY: "HIGH",
                };
                readiness = {
                  readinessLevel: genStatus[v2.generation_status] ?? v2.generation_status?.replace(/_/g, " ") ?? "Unknown",
                  expectedConfidence: genConfidence[v2.generation_status] ?? v2.confidence_level ?? "LOW",
                  releaseConfidence: v2.release_confidence ?? null,
                  evidenceCompleteness: v2.evidence_completeness ?? null,
                  confidenceCeilingReason: v2.confidence_ceiling_reason ?? null,
                  missingSignals: v2.blockers?.map((b: any) => b.input_id) ?? [],
                  isStale: normalizedPRPackage.snapshotStatus === "OUTDATED",
                  latestRecommendationTime: null,
                  ctaAction: resolveRecommendationAction({
                    readiness_level: v2.generation_status === "BLOCKED" ? "BLOCKED"
                      : v2.generation_status === "DRAFT_ONLY" ? "MINIMUM_READY"
                      : "HIGH_CONFIDENCE_READY",
                    expected_confidence: genConfidence[v2.generation_status] ?? "LOW",
                    readiness_score: v2.confidence_score ?? 0,
                    can_generate: v2.can_generate === "YES",
                    blocking_inputs: v2.blockers?.map((b: any) => ({ key: b.input_id, label: b.input_id })) ?? [],
                    missing_inputs: v2.inputs?.filter((i: any) => i.status === "MISSING").map((i: any) => ({ key: i.input_id, label: i.label, severity: i.is_hard_blocker ? "REQUIRED" : "RECOMMENDED" })) ?? [],
                    optional_inputs: v2.inputs?.filter((i: any) => i.status === "MISSING" && !i.is_hard_blocker).map((i: any) => ({ key: i.input_id, label: i.label })) ?? [],
                    latest_recommendation: {
                      exists: pr.recommendation_status === "GENERATED",
                      input_stale: normalizedPRPackage.snapshotStatus === "OUTDATED",
                    },
                    pr_package: {
                      readiness_status: normalizedPRPackage.status as any,
                      blockers: normalizedPRPackage.blockers,
                      warnings: normalizedPRPackage.warnings,
                      snapshot_is_stale: normalizedPRPackage.snapshotStatus === "OUTDATED",
                    },
                    recommendation_audit: undefined,
                  }),
                };
              } else {
                readiness = calculatePRReadiness(pr, result);
              }
              
              const readinessStyling = getReadinessStyling(readiness.readinessLevel);
              const confidenceStyling = getConfidenceStyling(readiness.expectedConfidence);
              const ReadinessIcon = readinessStyling.icon;
              
              // PR package status styling
              const getPRPackageStatusColor = (status: string) => {
                switch (status) {
                  case "READY": return "text-emerald-400";
                  case "BLOCKED": return "text-rose-400";
                  case "OUTDATED": return "text-orange-400";
                  case "PARTIAL": return "text-amber-400";
                  default: return "text-zinc-400";
                }
              };
              
              return (
                <div 
                  key={pr.id}
                  className={`bg-zinc-800/40 border rounded-lg p-4 cursor-pointer transition-colors ${selectedPullRequestId === pr.id ? 'border-emerald-600/50 bg-zinc-800/60' : 'border-zinc-700/50 hover:border-zinc-600/50'}`}
                  onClick={() => setSelectedPullRequestId(pr.id)}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm font-medium text-zinc-200">#{pr.number}</span>
                        <span className="text-sm text-zinc-300 truncate">{pr.title}</span>
                      </div>

                      {/* Single status line: generation status · release confidence · evidence completeness · PR package */}
                      <div className="flex items-center gap-2 mb-2 text-xs">
                        <span className={`${readinessStyling.textColor} font-medium`}>
                          {readiness.readinessLevel}
                        </span>
                        {(readiness as any).releaseConfidence && (
                          <>
                            <span className="text-zinc-600">·</span>
                            <span className={`${confidenceStyling.textColor} font-medium`}>
                              Release Confidence: {(readiness as any).releaseConfidence.toLowerCase()}
                            </span>
                          </>
                        )}
                        {(readiness as any).evidenceCompleteness != null && (
                          <>
                            <span className="text-zinc-600">·</span>
                            <span className="text-zinc-400">
                              {Math.round((readiness as any).evidenceCompleteness)}% complete
                            </span>
                          </>
                        )}
                        <span className="text-zinc-600">·</span>
                        <span className={`${getPRPackageStatusColor(normalizedPRPackage.status)} font-medium`}>
                          PR Package: {normalizedPRPackage.status}
                        </span>
                        {normalizedPRPackage.headShaShort && (
                          <>
                            <span className="text-zinc-600">·</span>
                            <span className="text-zinc-400">head {normalizedPRPackage.headShaShort}</span>
                          </>
                        )}
                        {readiness.isStale && (
                          <>
                            <span className="text-zinc-600">·</span>
                            <span className="text-amber-400">Needs regeneration</span>
                          </>
                        )}
                      </div>

                      {/* Only show reason for actual blockers, not optional gaps */}
                      {readiness.ctaAction?.actionType === "resolve" && readiness.ctaAction.reason && (
                        <div className="text-xs text-zinc-500 mb-2">
                          Reason: {readiness.ctaAction.reason}
                        </div>
                      )}

                      {/* PR Details */}
                      <div className="flex items-center gap-4 text-xs text-zinc-500">
                        <span className="flex items-center gap-1">
                          <GitBranch className="w-3 h-3" />
                          {pr.source_branch} → {pr.target_branch}
                        </span>
                        <span>{pr.changed_files_count} files changed</span>
                        <span>Synced {formatRelativeTime(pr.last_synced_at)}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {(() => {
                        const ctaAction = readiness.ctaAction;

                        if (ctaAction.actionType === "view") {
                          const isViewRedirecting = generationStatus === "redirecting" && redirectRecommendationId === pr.latest_recommendation_run_id;
                          return (
                            <Button
                              size="sm"
                              onClick={(e) => { e.stopPropagation(); handleViewRecommendation(pr.latest_recommendation_run_id || "", pr.id); }}
                              disabled={isViewRedirecting}
                              className="bg-emerald-600 hover:bg-emerald-500 text-white"
                              aria-label={isViewRedirecting ? "Opening..." : ctaAction.primaryLabel}
                            >
                              {isViewRedirecting ? (
                                <>
                                  <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                  Opening...
                                </>
                              ) : (
                                <>
                                  <Eye className="w-3 h-3 mr-1" />
                                  {ctaAction.primaryLabel}
                                </>
                              )}
                            </Button>
                          );
                        }

                        if (ctaAction.actionType === "regenerate") {
                          return (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={(e) => { e.stopPropagation(); showCheckpointModal(pr.id, "rerun"); }}
                              disabled={runningRecommendation !== null}
                              className="bg-amber-700 hover:bg-amber-600 text-amber-100 border-amber-600"
                              aria-label={ctaAction.primaryLabel}
                            >
                              <RefreshCw className="w-3 h-3 mr-1" />
                              {ctaAction.primaryLabel}
                            </Button>
                          );
                        }

                        if (ctaAction.actionType === "resolve") {
                          return (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedPullRequestId(pr.id);
                                setIsReadinessDrawerOpen(true);
                              }}
                              className="border-rose-600 bg-rose-700 hover:bg-rose-600 text-rose-100"
                              aria-label={ctaAction.primaryLabel}
                            >
                              <AlertTriangle className="w-3 h-3 mr-1" />
                              {ctaAction.primaryLabel}
                            </Button>
                          );
                        }

                        // Default: Generate / Improve
                        const isRunning = runningRecommendation === pr.id;
                        const isGenerating = generationStatus === "generating";
                        const isRedirecting = generationStatus === "redirecting";
                        const isDisabled = isRunning || isGenerating || isRedirecting;
                        const buttonText = isRedirecting ? "Opening..." : isGenerating ? "Generating..." : ctaAction.primaryLabel;
                        return (
                          <Button
                            size="sm"
                            onClick={(e) => { e.stopPropagation(); showCheckpointModal(pr.id, "generate"); }}
                            disabled={isDisabled}
                            className={ctaAction.tone === "positive"
                              ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                              : ctaAction.tone === "caution"
                              ? "bg-amber-600 hover:bg-amber-500 text-white"
                              : "border-zinc-600 text-zinc-300 hover:bg-zinc-700 hover:text-white"
                            }
                            aria-label={buttonText}
                          >
                            {(isGenerating || isRedirecting) ? (
                              <>
                                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                {buttonText}
                              </>
                            ) : (
                              <>
                                <Play className="w-3 h-3 mr-1" />
                                {ctaAction.primaryLabel}
                              </>
                            )}
                          </Button>
                        );
                      })()}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {error && (
        <div className="bg-rose-950/20 border border-rose-800/60 rounded-xl p-4">
          <p className="text-sm text-rose-400">{error}</p>
        </div>
      )}

      {/* Checkpoint Modal */}
      <RecommendationCheckpointModal
        isOpen={checkpointModal.isOpen}
        onClose={() => setCheckpointModal({ ...checkpointModal, isOpen: false })}
        onContinue={handleCheckpointContinue}
        repositoryId={repositoryId || ""}
        pullRequestId={checkpointModal.pullRequestId}
        action={checkpointModal.action}
        recommendationRunId={checkpointModal.recommendationRunId}
        generationStatus={generationStatus}
        runRepositoryIntelligence={runRepositoryIntelligence}
        refreshState={refreshState}
      />

      {/* Business Requirements Modal — Input 2 CTA target */}
      <BusinessRequirementsModal
        isOpen={isBusinessReqModalOpen}
        onClose={() => setIsBusinessReqModalOpen(false)}
        onSuccess={() => {
          setIsBusinessReqModalOpen(false);
          setReadinessRefreshTrigger((n) => n + 1);
        }}
        repositoryId={repositoryId || ""}
        pullRequestId={selectedPullRequestId}
      />

      {/* Improve Input Readiness Drawer — replaces old Resolve Blocking Inputs modal */}
      <ImproveInputReadinessDrawer
        isOpen={isReadinessDrawerOpen}
        onClose={() => setIsReadinessDrawerOpen(false)}
        readinessData={selectedPRReadinessData}
        onAction={handleInputAction}
        onGenerate={() => {
          if (selectedPullRequestId) {
            showCheckpointModal(selectedPullRequestId, "generate");
          }
        }}
      />
    </div>
  );
}
