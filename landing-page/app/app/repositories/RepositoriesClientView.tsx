"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Github,
  Plus,
  AlertTriangle,
  GitBranch,
  ExternalLink,
  CheckCircle2,
  GitPullRequest,
  FlaskConical,
  BarChart2,
  Sparkles,
  Lock,
  Globe,
  RefreshCw,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

// ── Types ──────────────────────────────────────────────────────────────────

interface Repo {
  id: string;
  workspace_id: string;
  github_repo_id: number;
  installation_id: number | null;
  owner: string | null;
  name: string;
  full_name: string;
  default_branch: string | null;
  visibility: string;
  is_active: boolean;
  selected_for_analysis: boolean;
  last_synced_at: string | null;
  last_webhook_at: string | null;
  latest_pr_synced_at: string | null;
  latest_sync_status: string;
  sync_error: string | null;
  active_pr_count: number;
  prs_analyzed_count: number;
  test_runs_count: number;
  coverage_reports_count: number;
  recommendations_count: number;
  readiness_state: string;
  readiness_reasons: string[];
  next_action: string | null;
}

interface Summary {
  connected_repositories: number;
  selected_repositories: number;
  ready_repositories: number;
  needs_test_history: number;
  sync_issues: number;
}

interface InstallationStatus {
  connected: boolean;
  status: string;
  installation_id: number | null;
  account_login: string | null;
  repositories_count: number;
}

type ViewState =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "error"; message: string; endpoint?: string; statusCode?: number }
  | { kind: "loaded"; repositories: Repo[]; summary: Summary };

// ── Readiness badge map ────────────────────────────────────────────────────

const READINESS_BADGE: Record<string, { label: string; className: string }> = {
  READY:               { label: "Ready",              className: "bg-emerald-500/[0.08] text-emerald-400/90 border-emerald-500/15" },
  EVIDENCE_READY:      { label: "Evidence Ready",     className: "bg-emerald-500/[0.06] text-emerald-300/80 border-emerald-500/10" },
  CONNECTED:           { label: "Connected",          className: "bg-blue-500/[0.08] text-blue-400/90 border-blue-500/15" },
  NEEDS_SYNC:          { label: "Needs Sync",         className: "bg-amber-500/[0.06] text-amber-300/80 border-amber-500/10" },
  NEEDS_TEST_HISTORY:  { label: "Needs Tests",        className: "bg-amber-500/[0.06] text-amber-300/70 border-amber-500/10" },
  NEEDS_COVERAGE:      { label: "Needs Coverage",     className: "bg-sky-500/[0.06] text-sky-300/80 border-sky-500/10" },
  SYNC_FAILED:         { label: "Sync Failed",        className: "bg-rose-500/[0.08] text-rose-400/80 border-rose-500/15" },
  DISCONNECTED:        { label: "Disconnected",       className: "bg-zinc-800/50 text-zinc-500 border-zinc-700/50" },
  NOT_SELECTED:        { label: "Not Enabled",        className: "bg-zinc-800/30 text-zinc-400 border-zinc-700/30" },
  REMOVED_OR_INACTIVE: { label: "Removed",            className: "bg-zinc-800/50 text-zinc-500 border-zinc-700/50" },
  UNKNOWN:             { label: "Unknown",            className: "bg-zinc-800/30 text-zinc-400 border-zinc-700/30" },
  INACTIVE:            { label: "Inactive",           className: "bg-zinc-800/50 text-zinc-500 border-zinc-700/50" },
};

// ── Skeleton ───────────────────────────────────────────────────────────────

function RepositorySkeleton() {
  return (
    <div className="bg-zinc-900/[0.25] border border-zinc-800/40 rounded-xl p-5 flex flex-col gap-3.5 animate-pulse">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-4 h-4 rounded bg-zinc-800/60 shrink-0" />
          <div className="h-4 w-40 rounded bg-zinc-800/60" />
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="h-3 w-14 rounded bg-zinc-800/60" />
          <div className="h-5 w-16 rounded-full bg-zinc-800/60" />
        </div>
      </div>

      {/* Metadata Row */}
      <div className="flex items-center gap-3">
        <div className="h-3 w-20 rounded bg-zinc-900/60" />
        <div className="h-3 w-16 rounded bg-zinc-900/60" />
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-1.5">
        {[0, 1, 2].map((i) => (
          <div key={i} className="bg-zinc-950/30 rounded-lg py-2 px-1 flex flex-col items-center gap-1 border border-zinc-800/20">
            <div className="w-3.5 h-3.5 rounded bg-zinc-800/60" />
            <div className="h-4 w-5 rounded bg-zinc-800/60" />
            <div className="h-2.5 w-10 rounded bg-zinc-900/60" />
          </div>
        ))}
      </div>

      {/* Evidence Health */}
      <div className="space-y-1.5">
        <div className="h-2.5 w-14 rounded bg-zinc-900/60" />
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-1.5">
              <div className="w-1 h-1 rounded-full bg-zinc-800/60" />
              <div className="h-2.5 w-8 rounded bg-zinc-900/60" />
              <div className="h-2.5 w-12 rounded bg-zinc-800/60" />
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-zinc-800/30 pt-3 flex items-center justify-between mt-auto">
        <div className="h-2.5 w-28 rounded bg-zinc-900/60" />
        <div className="h-5 w-16 rounded bg-zinc-800/60" />
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-8 max-w-5xl">
      {/* Header skeleton */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 animate-pulse">
        <div className="space-y-2">
          <div className="h-7 w-56 rounded-lg bg-zinc-800" />
          <div className="h-4 w-80 rounded bg-zinc-900" />
        </div>
        <div className="h-9 w-36 rounded-lg bg-zinc-800" />
      </div>
      {/* Summary strip skeleton */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 animate-pulse">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl px-4 py-3.5 flex items-center gap-3.5">
            <div className="w-9 h-9 rounded-lg bg-zinc-800/50 shrink-0" />
            <div className="space-y-2">
              <div className="h-5 w-8 rounded bg-zinc-800" />
              <div className="h-2.5 w-20 rounded bg-zinc-900" />
            </div>
          </div>
        ))}
      </div>
      {/* Card skeletons */}
      <div className="grid sm:grid-cols-2 gap-5">
        {[0, 1, 2, 3].map((i) => (
          <RepositorySkeleton key={i} />
        ))}
      </div>
    </div>
  );
}

// ── Summary Strip ───────────────────────────────────────────────────────────

function SummaryStrip({ summary }: { summary: Summary }) {
  const items = [
    {
      label: "Connected Repos",
      value: summary.connected_repositories ?? 0,
      icon: CheckCircle2,
      iconBg: "bg-zinc-800/50",
      iconColor: "text-zinc-400",
    },
    {
      label: "Selected",
      value: summary.selected_repositories ?? 0,
      icon: Sparkles,
      iconBg: "bg-blue-950/30",
      iconColor: "text-blue-400/80",
    },
    {
      label: "Ready",
      value: summary.ready_repositories ?? 0,
      icon: Sparkles,
      iconBg: "bg-emerald-950/30",
      iconColor: "text-emerald-400/80",
    },
    {
      label: "Needs Test History",
      value: summary.needs_test_history ?? 0,
      icon: FlaskConical,
      iconBg: "bg-amber-950/20",
      iconColor: "text-amber-400/70",
    },
    {
      label: "Sync Issues",
      value: summary.sync_issues ?? 0,
      icon: AlertTriangle,
      iconBg: "bg-rose-950/20",
      iconColor: "text-rose-400/70",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
      {items.map(({ label, value, icon: Icon, iconBg, iconColor }) => (
        <div
          key={label}
          className="group bg-zinc-900/30 border border-zinc-800/40 hover:border-zinc-700/50 rounded-xl px-4 py-3 flex items-center gap-3 transition-all duration-150"
        >
          <div className={`w-8 h-8 rounded-lg ${iconBg} flex items-center justify-center shrink-0`}>
            <Icon className={`w-3.5 h-3.5 ${iconColor}`} />
          </div>
          <div className="min-w-0">
            <p className="text-lg font-semibold text-zinc-200 leading-none tracking-tight">
              {value}
            </p>
            <p className="text-[11px] text-zinc-500 mt-1 leading-none truncate">
              {label}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Repository Card ───────────────────────────────────────────────────────

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "Not synced yet";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "Not synced yet";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "—";
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function getVisibilityBadge(visibility: string) {
  if (visibility === "PRIVATE") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-zinc-500">
        <Lock className="w-3 h-3" />
        Private
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-zinc-500">
      <Globe className="w-3 h-3" />
      Public
    </span>
  );
}

function getReadinessBadge(state: string | null | undefined, repo: Repo) {
  let safeState = state || "UNKNOWN";
  
  // Client-side fallback if status is UNKNOWN or missing but evidence exists
  if (safeState === "UNKNOWN") {
    if (!repo.last_synced_at) {
      safeState = "NEEDS_SYNC";
    } else if (repo.test_runs_count === 0) {
      safeState = "NEEDS_TEST_HISTORY";
    } else if (repo.coverage_reports_count === 0) {
      safeState = "NEEDS_COVERAGE";
    } else if (repo.test_runs_count > 0 && repo.coverage_reports_count > 0) {
      safeState = "EVIDENCE_READY";
    } else {
      safeState = "CONNECTED";
    }
  }

  const badges: Record<string, { bg: string; text: string; dot: string }> = {
    READY:               { bg: "bg-emerald-500/[0.08]", text: "text-emerald-400/80",  dot: "bg-emerald-400" },
    EVIDENCE_READY:      { bg: "bg-emerald-500/[0.06]", text: "text-emerald-300/80",  dot: "bg-emerald-400" },
    CONNECTED:           { bg: "bg-blue-500/[0.08]",    text: "text-blue-400/90",     dot: "bg-blue-400" },
    NEEDS_SYNC:          { bg: "bg-amber-500/[0.06]",   text: "text-amber-300/80",    dot: "bg-amber-300" },
    NEEDS_TEST_HISTORY:  { bg: "bg-amber-500/[0.06]",   text: "text-amber-300/70",    dot: "bg-amber-300" },
    NEEDS_COVERAGE:      { bg: "bg-sky-500/[0.06]",     text: "text-sky-300/70",      dot: "bg-sky-300" },
    SYNC_FAILED:         { bg: "bg-rose-500/[0.08]",    text: "text-rose-400/70",     dot: "bg-rose-400" },
    DISCONNECTED:        { bg: "bg-zinc-800/50",        text: "text-zinc-500",        dot: "bg-zinc-600" },
    NOT_SELECTED:        { bg: "bg-zinc-800/30",        text: "text-zinc-400",        dot: "bg-zinc-500" },
    REMOVED_OR_INACTIVE: { bg: "bg-zinc-800/50",        text: "text-zinc-500",        dot: "bg-zinc-600" },
    UNKNOWN:             { bg: "bg-zinc-800/30",        text: "text-zinc-400",        dot: "bg-zinc-500" },
    INACTIVE:            { bg: "bg-zinc-800/50",        text: "text-zinc-500",        dot: "bg-zinc-600" },
  };
  const b = badges[safeState] ?? badges.UNKNOWN;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-[3px] rounded-full text-[11px] font-medium border ${b.bg} ${b.text} border-current/10`}>
      <span className={`w-1 h-1 rounded-full ${b.dot}`} />
      {safeState.replace(/_/g, " ")}
    </span>
  );
}

interface EvidenceIndicator {
  label: string;
  healthy: boolean;
  text: string;
}

function EvidenceIndicator({ label, healthy, text }: EvidenceIndicator) {
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      <span className={`w-1 h-1 rounded-full shrink-0 ${healthy ? "bg-emerald-400" : "bg-zinc-700"}`} />
      <span className="text-[10px] text-zinc-500 shrink-0">{label}</span>
      <span className="text-[10px] text-zinc-400 truncate">{text}</span>
    </div>
  );
}

function getPrimaryActionStyle(action: string | null): { bg: string; text: string } {
  if (!action) return { bg: "bg-zinc-800", text: "text-zinc-400" };
  if (action.includes("Upload")) return { bg: "bg-amber-950/30", text: "text-amber-400/80" };
  if (action.includes("Retry") || action.includes("Check")) return { bg: "bg-rose-950/20", text: "text-rose-400/70" };
  if (action.includes("Enable")) return { bg: "bg-blue-950/20", text: "text-blue-400/70" };
  if (action.includes("Open")) return { bg: "bg-emerald-950/20", text: "text-emerald-400/80" };
  return { bg: "bg-zinc-800", text: "text-zinc-400" };
}

function getActionRoute(action: string | null, repoId: string): { href: string; isApi: boolean } | null {
  if (!action) return null;
  if (action.includes("Upload Test")) return { href: `/app/repositories/${repoId}/test-history?from=repositories`, isApi: false };
  if (action.includes("Upload Coverage")) return { href: `/app/repositories/${repoId}/coverage?from=repositories`, isApi: false };
  if (action.includes("Check Webhook")) return { href: `/app/repositories/${repoId}/webhooks?from=repositories`, isApi: false };
  if (action.includes("Check GitHub Installation")) return { href: "/onboarding/github?from=repositories", isApi: false };
  if (action.includes("Retry Sync")) return { href: `/api/repositories/${repoId}/sync`, isApi: true };
  if (action.includes("Enable")) return { href: `/api/repositories/${repoId}/enable`, isApi: true };
  if (action.includes("Disable")) return { href: `/api/repositories/${repoId}/disable`, isApi: true };
  // Open Intelligence and Inspect Setup route to repo detail
  return { href: `/app/repositories/${repoId}`, isApi: false };
}

interface ActionButtonProps {
  action: string | null;
  repoId: string;
  onActionComplete?: () => void;
}

function ActionButton({ action, repoId, onActionComplete }: ActionButtonProps) {
  const [loading, setLoading] = useState(false);
  const route = getActionRoute(action, repoId);
  const style = getPrimaryActionStyle(action);

  if (!route || !action) return null;

  const handleClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!route || !action) return;

    if (!route.isApi) {
      // Navigation action - let Link handle it
      window.location.href = route.href;
      return;
    }

    // API action
    setLoading(true);
    try {
      const res = await fetch(route.href, { method: "POST", cache: "no-store" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        toast.error("Could not enable repository", {
          description: body.error || `Action failed (${res.status}). Please retry or check your workspace permissions.`,
        });
      } else {
        // Show success message for enable action
        if (action.includes("Enable")) {
          toast.success("Repository enabled", {
            description: `${action.includes("Repository") ? "" : "Repository is now active for regression intelligence. Next step: upload test history."}`,
          });
        }
        onActionComplete?.();
      }
    } catch (err: any) {
      toast.error("Could not enable repository", {
        description: err?.message || "Veriscope could not activate this repository. Please retry or check your workspace permissions.",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className={`shrink-0 px-2.5 py-[5px] rounded-md text-[10px] font-medium transition-all flex items-center gap-1.5 ${style.bg} ${style.text} ${loading ? "opacity-50 cursor-wait" : "hover:opacity-80 active:scale-[0.97]"}`}
    >
      {loading ? (
        <>
          <Loader2 className="w-3 h-3 animate-spin" />
          {action.includes("Enable") ? "Enabling..." : "Processing..."}
        </>
      ) : (
        action
      )}
    </button>
  );
}

function RepoCard({ repo, onActionComplete }: { repo: Repo; onActionComplete?: () => void }) {
  // Derive fallback status for mapping description/badge accurately
  const displayState = repo.readiness_state || "UNKNOWN";
  const finalState = displayState === "UNKNOWN" 
    ? (!repo.last_synced_at ? "NEEDS_SYNC" : (repo.test_runs_count === 0 ? "NEEDS_TEST_HISTORY" : (repo.coverage_reports_count === 0 ? "NEEDS_COVERAGE" : "READY")))
    : displayState;
  
  const statusDescription = repo.readiness_reasons?.[0] ?? 
    (finalState === "READY" || finalState === "EVIDENCE_READY" ? "Repository ready" : "Setup in progress");

  const evidenceIndicators: EvidenceIndicator[] = [
    {
      label: "PRs",
      healthy: repo.active_pr_count > 0,
      text: !repo.latest_pr_synced_at 
        ? "PRs not synced yet" 
        : (repo.active_pr_count > 0 ? `${repo.active_pr_count} open` : "No active PRs"),
    },
    {
      label: "PR sync",
      healthy: !!repo.latest_pr_synced_at,
      text: repo.latest_pr_synced_at ? formatRelativeTime(repo.latest_pr_synced_at) : "Not synced yet",
    },
    {
      label: "Tests",
      healthy: repo.test_runs_count > 0,
      text: repo.test_runs_count > 0 ? `${repo.test_runs_count} runs` : "None",
    },
    {
      label: "Coverage",
      healthy: repo.coverage_reports_count > 0,
      text: repo.coverage_reports_count > 0 ? `${repo.coverage_reports_count} reports` : "None",
    },
    {
      label: "AI",
      healthy: repo.recommendations_count > 0,
      text: repo.recommendations_count > 0 ? `${repo.recommendations_count} generated` : "None",
    },
  ];

  const handleCardClick = () => {
    window.location.href = `/app/repositories/${repo.id}`;
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleCardClick();
    }
  };

  return (
    <div
      onClick={handleCardClick}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="button"
      aria-label={`View details for ${repo.full_name}`}
      className="group bg-zinc-900/[0.25] border border-zinc-800/40 hover:border-zinc-700/50 hover:bg-zinc-900/40 rounded-xl p-5 transition-all duration-150 flex flex-col gap-3.5 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <Github className="w-4 h-4 text-zinc-500 shrink-0" />
          <span className="text-[13px] font-semibold text-zinc-200 truncate" title={repo.full_name}>
            {repo.full_name}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {getVisibilityBadge(repo.visibility)}
          {getReadinessBadge(repo.readiness_state, repo)}
        </div>
      </div>

      {/* Metadata Row */}
      <div className="flex items-center gap-3 text-[11px] text-zinc-500 flex-wrap">
        <span className="inline-flex items-center gap-1">
          <GitBranch className="w-3 h-3 text-zinc-600" />
          {repo.default_branch ?? "main"}
        </span>
        <span className="inline-flex items-center gap-1" title={repo.last_synced_at ?? "Not synced"}>
          <RefreshCw className="w-3 h-3 text-zinc-600" />
          Repo: {formatDate(repo.last_synced_at)}
        </span>
        {repo.latest_pr_synced_at ? (
          <span className="inline-flex items-center gap-1" title={repo.latest_pr_synced_at}>
            <GitPullRequest className="w-3 h-3 text-zinc-600" />
            PRs: {formatRelativeTime(repo.latest_pr_synced_at)}
          </span>
        ) : repo.active_pr_count > 0 ? (
          <span className="inline-flex items-center gap-1">
            <GitPullRequest className="w-3 h-3 text-zinc-600" />
            {repo.active_pr_count} open
          </span>
        ) : null}
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-1.5">
        {[
          { icon: FlaskConical, label: "Tests", value: repo.test_runs_count },
          { icon: BarChart2, label: "Coverage", value: repo.coverage_reports_count },
          { icon: Sparkles, label: "AI", value: repo.recommendations_count },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="bg-zinc-950/30 rounded-lg py-2 px-1 text-center border border-zinc-800/20">
            <Icon className="w-3.5 h-3.5 text-zinc-600 mx-auto mb-1" />
            <p className="text-sm font-semibold text-zinc-300 leading-tight">{value}</p>
            <p className="text-[10px] text-zinc-600 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Evidence Health Section */}
      <div className="space-y-1.5">
        <p className="text-[10px] font-medium text-zinc-600 uppercase tracking-wider">Evidence</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {evidenceIndicators.map((ind) => (
            <EvidenceIndicator key={ind.label} {...ind} />
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-zinc-800/30 pt-3 flex items-center justify-between gap-3 mt-auto">
        <p className="text-[11px] text-zinc-500 truncate flex-1 max-w-[180px] sm:max-w-[220px]" title={statusDescription}>
          {statusDescription}
        </p>
        <div className="flex items-center gap-2">
          {repo.selected_for_analysis && (
            <button
              onClick={async (e) => {
                e.preventDefault();
                e.stopPropagation();
                try {
                  const res = await fetch(`/api/repositories/${repo.id}/disable`, { method: "POST" });
                  if (!res.ok) {
                    const body = await res.json().catch(() => ({}));
                    toast.error("Could not disable repository", {
                      description: body.error || `Disable failed (${res.status}). Please retry.`,
                    });
                  } else {
                    toast.success("Repository disabled", {
                      description: "Repository is no longer active for regression intelligence.",
                    });
                    onActionComplete?.();
                  }
                } catch (err: any) {
                  toast.error("Could not disable repository", {
                    description: err?.message || "Disable failed. Please retry.",
                  });
                }
              }}
              className="shrink-0 px-2 py-[5px] rounded-md text-[10px] font-medium border border-zinc-700/50 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600 transition-all"
            >
              Disable
            </button>
          )}
          <ActionButton action={repo.next_action} repoId={repo.id} onActionComplete={onActionComplete} />
        </div>
      </div>
    </div>
  );
}

// ── Main client view ───────────────────────────────────────────────────────

export default function RepositoriesClientView() {
  const [state, setState] = useState<ViewState>({ kind: "loading" });
  const [installationStatus, setInstallationStatus] = useState<InstallationStatus | null>(null);

  const fetchData = useCallback(async () => {
    setState({ kind: "loading" });
    const REPOS_ENDPOINT = "/api/repositories";
    try {
      const [reposRes, installRes] = await Promise.all([
        fetch(REPOS_ENDPOINT, { cache: "no-store" }),
        fetch("/api/github/installation/status", {
          cache: "no-store",
        }).catch(() => null),
      ]);

      if (!reposRes.ok) {
        let message = `Request failed (${reposRes.status})`;
        let endpoint: string | undefined = REPOS_ENDPOINT;
        let statusCode: number | undefined = reposRes.status;
        try {
          const body = await reposRes.json();
          if (body?.error) message = body.error;
          if (body?.endpoint) endpoint = body.endpoint;
          if (body?.status) statusCode = body.status;
        } catch {}
        if (process.env.NODE_ENV === "development") {
          console.error(`[RepositoriesClientView] Fetch error`, {
            endpoint,
            statusCode,
            message,
          });
        }
        setState({ kind: "error", message, endpoint, statusCode });
        return;
      }

      const data = await reposRes.json();
      const repositories: Repo[] = data.repositories ?? [];
      const summary: Summary = data.summary ?? {
        connected_repositories: 0,
        selected_repositories: 0,
        ready_repositories: 0,
        needs_test_history: 0,
        sync_issues: 0,
      };

      // Set installation status if available
      if (installRes && installRes.ok) {
        const installData = await installRes.json();
        setInstallationStatus(installData);
      }

      if (repositories.length === 0) {
        setState({ kind: "empty" });
      } else {
        setState({ kind: "loaded", repositories, summary });
      }
    } catch (err: any) {
      const message = err?.message ?? "Failed to reach backend";
      if (process.env.NODE_ENV === "development") {
        console.error(`[RepositoriesClientView] Network error fetching ${REPOS_ENDPOINT}:`, err);
      }
      setState({
        kind: "error",
        message,
        endpoint: REPOS_ENDPOINT,
      });
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── Loading ──────────────────────────────────────────────────────────────

  if (state.kind === "loading") {
    return <LoadingState />;
  }

  // ── Error ────────────────────────────────────────────────────────────────

  if (state.kind === "error") {
    return (
      <div className="space-y-8 max-w-5xl">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Connected Repositories</h1>
            <p className="text-sm text-zinc-400 mt-1">
              Repositories synced from your GitHub App installation
            </p>
          </div>
        </div>

        <div className="flex flex-col items-center justify-center rounded-xl border border-rose-900/30 bg-rose-950/10 py-16 px-6 text-center">
          <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-rose-900/40 flex items-center justify-center mb-4">
            <AlertTriangle className="w-5 h-5 text-rose-400/70" />
          </div>
          <h3 className="text-sm font-semibold text-zinc-300 mb-1.5">
            Could not load repositories
          </h3>
          <p className="text-xs text-zinc-500 max-w-sm mb-2">
            Veriscope could not fetch repository status from the backend.
          </p>
          {/* Error detail */}
          <div className="flex flex-col items-center gap-1 mb-5">
            <p className="text-[11px] text-rose-400/60 font-mono max-w-sm truncate" title={state.message}>
              {state.statusCode ? (
                <span className="text-rose-400/80 font-semibold mr-1">{state.statusCode}</span>
              ) : null}
              {state.message}
            </p>
            {state.endpoint && (
              <p className="text-[10px] text-zinc-600 font-mono max-w-md truncate" title={state.endpoint}>
                {state.endpoint}
              </p>
            )}
          </div>
          <Button
            onClick={fetchData}
            variant="outline"
            className="flex items-center gap-1.5 border-zinc-700 bg-transparent text-zinc-300 hover:bg-zinc-800 hover:text-white h-8 px-4 text-xs"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  // ── Empty ────────────────────────────────────────────────────────────────

  if (state.kind === "empty") {
    return (
      <div className="space-y-8 max-w-5xl">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Connected Repositories</h1>
            <p className="text-sm text-zinc-400 mt-1">
              Repositories synced from your GitHub App installation
            </p>
          </div>
          <Link href="/onboarding/github">
            <Button className="flex items-center gap-2 bg-white text-zinc-950 hover:bg-zinc-100 font-semibold h-9 text-xs">
              <Plus className="w-4 h-4" />
              Connect GitHub
            </Button>
          </Link>
        </div>

        <div className="flex flex-col items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/20 py-16 px-6 text-center">
          <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mb-4">
            <Github className="w-5 h-5 text-zinc-500" />
          </div>
          <h3 className="text-sm font-semibold text-zinc-300 mb-1.5">
            No repositories connected yet
          </h3>
          <p className="text-xs text-zinc-500 max-w-sm mb-5">
            Install the Veriscope GitHub App to connect repositories and start building regression intelligence.
          </p>
          <div className="flex items-center gap-3">
            <Link href="/onboarding/github">
              <Button className="bg-white text-zinc-950 hover:bg-zinc-100 font-medium text-xs h-8 px-4">
                Connect GitHub
              </Button>
            </Link>
            <a
              href="https://docs.github.com/en/apps/using-github-apps/installing-a-github-app-from-a-third-party"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Read setup guide
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </div>
    );
  }

  // ── Loaded ───────────────────────────────────────────────────────────────

  const { repositories, summary } = state;
  return (
    <div className="space-y-8 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Connected Repositories</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Repositories synced from your GitHub App installation
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={fetchData}
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60"
            title="Sync Repositories"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
          <Link href="/onboarding/github">
            <Button className="flex items-center gap-1.5 bg-white text-zinc-950 hover:bg-zinc-100 font-medium h-8 text-[11px] px-3">
              {installationStatus?.connected ? (
                <>
                  <Github className="w-3.5 h-3.5" />
                  Manage GitHub App
                </>
              ) : (
                <>
                  <Plus className="w-3.5 h-3.5" />
                  Connect GitHub
                </>
              )}
            </Button>
          </Link>
        </div>
      </div>

      {/* Premium Summary Strip */}
      <SummaryStrip summary={summary} />

      {/* Repository grid */}
      <div className="grid sm:grid-cols-2 gap-4">
        {repositories.map((repo) => (
          <RepoCard key={repo.id} repo={repo} onActionComplete={fetchData} />
        ))}
      </div>
    </div>
  );
}
