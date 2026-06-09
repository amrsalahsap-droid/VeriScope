"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  GitPullRequest,
  ChevronRight,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import RecommendationCheckpointModal from "@/app/components/RecommendationCheckpointModal";

export const dynamic = "force-dynamic";

interface RunSummary {
  id: string;
  repository_id: string;
  repository_full_name: string;
  pull_request_number: number | null;
  pull_request_title: string | null;
  recommendation_mode: string;
  evidence_quality: string;
  recommended_tests_count: number;
  estimated_runtime_seconds: number;
  created_at: string;
}

function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  const hrs = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (hrs < 24) return `${hrs}h ago`;
  return `${days}d ago`;
}

function formatSeconds(s: number): string {
  if (!s || s <= 0) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  return `${m}m`;
}

function modeBadge(mode: string) {
  const labels: Record<string, { label: string; cls: string }> = {
    NORMAL:          { label: "Targeted",     cls: "bg-emerald-950/20 text-emerald-400/80 border-emerald-800/30" },
    WIDENED:         { label: "Widened",      cls: "bg-sky-950/20 text-sky-400/80 border-sky-800/30" },
    SAFE_FALLBACK:   { label: "Conservative", cls: "bg-amber-950/20 text-amber-400/80 border-amber-800/30" },
    CRITICAL:        { label: "Critical",     cls: "bg-rose-950/20 text-rose-400/80 border-rose-800/30" },
    FULL_REGRESSION: { label: "Full Suite",   cls: "bg-zinc-800 text-zinc-400 border-zinc-700" },
  };
  const s = labels[mode] ?? { label: mode, cls: "bg-zinc-800 text-zinc-400 border-zinc-700" };
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
}

export default function RecommendationsPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkpointModal, setCheckpointModal] = useState<{
    isOpen: boolean;
    repositoryId: string;
    pullRequestId?: string;
    action: "generate" | "rerun" | "view";
    recommendationRunId?: string;
  }>({ isOpen: false, repositoryId: "", action: "view" });

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/recommendations", { cache: "no-store" });
      if (res.status === 401) { window.location.href = "/login"; return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { setError(data?.error || `Error ${res.status}`); return; }
      setRuns(data.runs || []);
    } catch (e: any) {
      setError(e?.message || "Failed to load recommendations");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleLinkClick = async (e: React.MouseEvent, runId: string, repoId: string) => {
    e.preventDefault();
    try {
      const response = await fetch(`/api/recommendations/${runId}`);
      if (!response.ok) {
        throw new Error("Failed to fetch recommendation run details");
      }
      const run = await response.json();
      
      const hasMissingInputs = run.completeness_assessment?.missing_recommended_inputs?.length > 0 || false;
      const isLowConfidence = run.evidence_quality === "LOW" || run.runtime_confidence === "LOW";
      
      if (run.readiness_acknowledged || (!isLowConfidence && !hasMissingInputs)) {
        router.push(`/app/recommendations/${runId}`);
      } else {
        setCheckpointModal({
          isOpen: true,
          repositoryId: repoId,
          pullRequestId: run.pull_request?.id || undefined,
          action: "view",
          recommendationRunId: runId
        });
      }
    } catch (err: any) {
      console.error("Error checking recommendation readiness:", err);
      router.push(`/app/recommendations/${runId}`);
    }
  };

  const handleCheckpointContinue = () => {
    if (checkpointModal.recommendationRunId) {
      router.push(`/app/recommendations/${checkpointModal.recommendationRunId}`);
    }
  };

  useEffect(() => { fetchRuns(); }, [fetchRuns]);

  return (
    <div className="space-y-8 max-w-5xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Recommendations</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Test recommendations generated for active pull requests
          </p>
        </div>
        <Button
          onClick={fetchRuns}
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-zinc-500 hover:text-zinc-300"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-5 h-5 text-zinc-500 animate-spin" />
        </div>
      ) : error ? (
        <div className="bg-rose-950/20 border border-rose-800/40 rounded-xl p-6 text-center">
          <AlertTriangle className="w-5 h-5 text-rose-400 mx-auto mb-2" />
          <p className="text-sm text-rose-300">{error}</p>
          <Button onClick={fetchRuns} variant="outline" size="sm" className="mt-4 border-zinc-700 text-zinc-300">
            Retry
          </Button>
        </div>
      ) : runs.length === 0 ? (
        <div className="border border-zinc-800 rounded-xl bg-zinc-900/10 p-12 text-center">
          <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-5 h-5 text-zinc-500" />
          </div>
          <h3 className="text-sm font-semibold text-zinc-300 mb-1">No recommendations yet</h3>
          <p className="text-xs text-zinc-500 max-w-sm mx-auto">
            Open a pull request and click Run Recommendation on the repository detail page.
          </p>
        </div>
      ) : (
        <div className="border border-zinc-800/60 rounded-xl bg-zinc-900/10 overflow-hidden divide-y divide-zinc-800/40">
          {runs.map(run => (
            <Link
              key={run.id}
              href={`/app/recommendations/${run.id}`}
              onClick={(e) => handleLinkClick(e, run.id, run.repository_id)}
              className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-5 hover:bg-zinc-900/30 transition-colors group"
            >
              <div className="flex items-start gap-4">
                <div className="w-9 h-9 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center shrink-0 mt-0.5">
                  <GitPullRequest className="w-4 h-4 text-zinc-400" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {run.pull_request_number && (
                      <span className="text-sm font-semibold text-white">
                        #{run.pull_request_number}
                      </span>
                    )}
                    <span className="text-sm text-zinc-300 truncate">
                      {run.pull_request_title || run.repository_full_name}
                    </span>
                    {modeBadge(run.recommendation_mode)}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500 flex-wrap">
                    <span>{run.repository_full_name}</span>
                    <span>{run.recommended_tests_count} tests</span>
                    {run.estimated_runtime_seconds > 0 && (
                      <span>~{formatSeconds(run.estimated_runtime_seconds)}</span>
                    )}
                    <span>{formatRelative(run.created_at)}</span>
                  </div>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 transition-colors hidden sm:block shrink-0" />
            </Link>
          ))}
        </div>
      )}

      <RecommendationCheckpointModal
        isOpen={checkpointModal.isOpen}
        onClose={() => setCheckpointModal({ ...checkpointModal, isOpen: false })}
        onContinue={handleCheckpointContinue}
        repositoryId={checkpointModal.repositoryId}
        pullRequestId={checkpointModal.pullRequestId}
        action={checkpointModal.action}
        recommendationRunId={checkpointModal.recommendationRunId}
      />
    </div>
  );
}
