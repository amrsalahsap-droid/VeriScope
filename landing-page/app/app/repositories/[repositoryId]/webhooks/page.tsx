"use client";

import { useState, useCallback, useEffect } from "react";
import { useSession } from "next-auth/react";
import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ExternalLink, Webhook, CheckCircle2, AlertCircle, Clock, Github, RefreshCw, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ repositoryId: string }>;
}

interface Repository {
  id: string;
  full_name: string;
}

interface WebhookEvent {
  event_type: string;
  action: string;
  received_at: string;
  processing_status: string;
}

interface WebhookStatus {
  webhook_status: "ACTIVE" | "INACTIVE" | "UNKNOWN";
  last_webhook_at: string | null;
  recent_events: WebhookEvent[];
  installation_status?: string;
  github_account?: string;
  permissions_summary?: string;
  publishing_enabled?: boolean;
  pr_comments_enabled?: boolean;
  last_sync_time?: string | null;
  rate_limit_state?: string;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "Never";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "Never";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "Never";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "Never";
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

export default function WebhooksPage({ params }: PageProps) {
  const { data: session } = useSession();
  const [repositoryId, setRepositoryId] = useState<string | null>(null);
  const [repo, setRepo] = useState<Repository | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [webhookStatus, setWebhookStatus] = useState<WebhookStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch repository data
  const fetchRepository = useCallback(async () => {
    if (!repositoryId || !session?.backendToken) return;
    
    if (!session?.user) {
      redirect("/login");
      return;
    }

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/github/repositories/${repositoryId}`,
        { headers: { Authorization: `Bearer ${session.backendToken}` }, cache: "no-store" }
      );
      if (!res.ok) {
        setRepo(null);
        return;
      }
      const data = await res.json();
      setRepo(data);
    } catch {
      setRepo(null);
    } finally {
      setLoading(false);
    }
  }, [repositoryId, session?.backendToken, session?.user]);

  // Fetch webhook status
  const fetchWebhookStatus = useCallback(async () => {
    if (!repositoryId || !session?.backendToken) return;

    try {
      const res = await fetch(
        `/api/repositories/${repositoryId}/webhook-status`,
        { cache: "no-store" }
      );
      if (!res.ok) {
        setError("Failed to fetch webhook status");
        return;
      }
      const data = await res.json();
      setWebhookStatus(data);
      setError(null);
    } catch (err: any) {
      setError(err?.message || "Failed to fetch webhook status");
    }
  }, [repositoryId, session?.backendToken]);

  // Initialize repositoryId from params
  useEffect(() => {
    params.then(p => setRepositoryId(p.repositoryId));
  }, [params]);

  // Fetch repository when repositoryId is set
  useEffect(() => {
    if (repositoryId) fetchRepository();
  }, [repositoryId, fetchRepository]);

  // Fetch webhook status when repositoryId is set
  useEffect(() => {
    if (repositoryId) fetchWebhookStatus();
  }, [repositoryId, fetchWebhookStatus]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchWebhookStatus();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <div className="space-y-6 max-w-5xl">
        {/* Header skeleton */}
        <div className="flex items-center gap-4 animate-pulse">
          <div className="h-8 w-8 bg-zinc-800 rounded-lg" />
          <div className="h-6 w-48 bg-zinc-800 rounded-lg" />
        </div>
        {/* Status overview skeleton */}
        <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 animate-pulse">
          <div className="h-4 w-32 bg-zinc-800 rounded mb-4" />
          <div className="h-4 w-48 bg-zinc-800 rounded" />
        </div>
        {/* Setup guidance skeleton */}
        <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 animate-pulse">
          <div className="h-4 w-32 bg-zinc-800 rounded mb-4" />
          <div className="space-y-4">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-4 w-full bg-zinc-800 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

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
      </div>
    );
  }

  const isWebhookActive = webhookStatus?.webhook_status === "ACTIVE";

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/app/repositories/${repositoryId}`}>
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div className="min-w-0">
          <h1 className="text-xl font-bold text-white truncate">{repo.full_name}</h1>
          <p className="text-sm text-zinc-500">Webhook Setup</p>
        </div>
      </div>

      {/* Status Overview */}
      <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-zinc-300">Webhook Status</h3>
          <div className="flex items-center gap-3">
            {isWebhookActive ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400/80">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Receiving Events
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs text-amber-400/70">
                <AlertCircle className="w-3.5 h-3.5" />
                No Recent Events
              </span>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
        <div className="space-y-2 text-sm text-zinc-400">
          <div className="flex items-center gap-3">
            <Clock className="w-4 h-4 text-zinc-500" />
            <span>Last webhook received: {formatRelativeTime(webhookStatus?.last_webhook_at || null)}</span>
          </div>
          {webhookStatus?.installation_status && (
            <div className="flex items-center gap-3">
              <Github className="w-4 h-4 text-zinc-500" />
              <span>Installation: {webhookStatus.installation_status}</span>
            </div>
          )}
          {webhookStatus?.github_account && (
            <div className="flex items-center gap-3">
              <Github className="w-4 h-4 text-zinc-500" />
              <span>Account: {webhookStatus.github_account}</span>
            </div>
          )}
          {webhookStatus?.rate_limit_state && webhookStatus.rate_limit_state !== "normal" && (
            <div className="flex items-center gap-3">
              <AlertCircle className="w-4 h-4 text-amber-500" />
              <span className="text-amber-400">Rate Limit: {webhookStatus.rate_limit_state}</span>
            </div>
          )}
        </div>
      </div>

      {/* GitHub App Integration Details */}
      <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
        <h3 className="text-sm font-medium text-zinc-300 mb-4">GitHub App Integration</h3>
        <div className="grid sm:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-zinc-500 mb-1">Installation Status</p>
            <p className="text-zinc-200">{webhookStatus?.installation_status || "Not available yet"}</p>
          </div>
          <div>
            <p className="text-zinc-500 mb-1">GitHub Account</p>
            <p className="text-zinc-200">{webhookStatus?.github_account || "Not connected"}</p>
          </div>
          <div>
            <p className="text-zinc-500 mb-1">Permissions</p>
            <p className="text-zinc-200">{webhookStatus?.permissions_summary || "Not available yet"}</p>
          </div>
          <div>
            <p className="text-zinc-500 mb-1">Last Sync</p>
            <p className="text-zinc-200">{formatRelativeTime(webhookStatus?.last_sync_time || null)}</p>
          </div>
          <div>
            <p className="text-zinc-500 mb-1">Publishing Enabled</p>
            <p className="text-zinc-200">{webhookStatus?.publishing_enabled ? "Yes" : "No"}</p>
          </div>
          <div>
            <p className="text-zinc-500 mb-1">PR Comments Enabled</p>
            <p className="text-zinc-200">{webhookStatus?.pr_comments_enabled ? "Yes" : "No"}</p>
          </div>
        </div>
      </div>

      {/* Setup Guidance */}
      <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
        <h3 className="text-sm font-medium text-zinc-300 mb-4">Setup Guidance</h3>
        <div className="space-y-4">
          <div className="flex gap-3">
            <div className="w-6 h-6 rounded-full bg-zinc-800 flex items-center justify-center shrink-0 text-xs font-medium text-zinc-400">
              1
            </div>
            <div>
              <p className="text-sm font-medium text-zinc-200">Open or Update a Pull Request</p>
              <p className="text-xs text-zinc-500 mt-0.5">
                Create a new PR or push a commit to an existing PR to trigger a webhook event.
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="w-6 h-6 rounded-full bg-zinc-800 flex items-center justify-center shrink-0 text-xs font-medium text-zinc-400">
              2
            </div>
            <div>
              <p className="text-sm font-medium text-zinc-200">Wait for Webhook Delivery</p>
              <p className="text-xs text-zinc-500 mt-0.5">
                GitHub will automatically send the webhook to Veriscope. This usually takes a few seconds.
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="w-6 h-6 rounded-full bg-zinc-800 flex items-center justify-center shrink-0 text-xs font-medium text-zinc-400">
              3
            </div>
            <div>
              <p className="text-sm font-medium text-zinc-200">Refresh Status</p>
              <p className="text-xs text-zinc-500 mt-0.5">
                Click the refresh button above to check if the webhook was received successfully.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Events */}
      {webhookStatus?.recent_events && webhookStatus.recent_events.length > 0 && (
        <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
          <h3 className="text-sm font-medium text-zinc-300 mb-4">Recent Events</h3>
          <div className="space-y-3">
            {webhookStatus.recent_events.map((event, index) => (
              <div key={index} className="flex items-center justify-between py-2 border-b border-zinc-800/50 last:border-0">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${
                    event.processing_status === "COMPLETED" ? "bg-emerald-400" :
                    event.processing_status === "FAILED" ? "bg-rose-400" :
                    "bg-amber-400"
                  }`} />
                  <div>
                    <p className="text-sm text-zinc-200">
                      <span className="font-medium">{event.event_type}</span>
                      {event.action && <span className="text-zinc-500"> • {event.action}</span>}
                    </p>
                    <p className="text-xs text-zinc-500">{formatDate(event.received_at)}</p>
                  </div>
                </div>
                <span className={`text-xs ${
                  event.processing_status === "COMPLETED" ? "text-emerald-400/80" :
                  event.processing_status === "FAILED" ? "text-rose-400/80" :
                  "text-amber-400/80"
                }`}>
                  {event.processing_status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Cards */}
      <div className="grid sm:grid-cols-2 gap-4">
        <a
          href="https://github.com/settings/installations"
          target="_blank"
          rel="noopener noreferrer"
          className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 hover:border-zinc-700 transition-colors"
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center">
              <Github className="w-5 h-5 text-zinc-400" />
            </div>
            <div>
              <h3 className="text-sm font-medium text-white">GitHub Settings</h3>
              <p className="text-xs text-zinc-500">Manage app installation</p>
            </div>
          </div>
          <p className="text-sm text-zinc-400 mb-4">
            View and configure the Veriscope GitHub App installation settings.
          </p>
          <Button variant="outline" size="sm" className="text-xs">
            Open GitHub
            <ExternalLink className="w-3 h-3 ml-1" />
          </Button>
        </a>

        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isWebhookActive ? "bg-emerald-950/20" : "bg-amber-950/20"}`}>
              <Webhook className={`w-5 h-5 ${isWebhookActive ? "text-emerald-400/70" : "text-amber-400/70"}`} />
            </div>
            <div>
              <h3 className="text-sm font-medium text-white">Events Status</h3>
              <p className="text-xs text-zinc-500">Webhook activity</p>
            </div>
          </div>
          <p className="text-sm text-zinc-400 mb-4">
            {isWebhookActive 
              ? "Webhooks are being received. New PRs, pushes, and workflow runs will be processed automatically."
              : "No webhooks received yet. Ensure the GitHub App is installed and the repository has recent activity."
            }
          </p>
          {isWebhookActive && (
            <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400/80">
              <CheckCircle2 className="w-3 h-3" />
              Active
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-rose-950/20 border border-rose-900/50 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-rose-200">Status Error</p>
            <p className="text-sm text-rose-300/80 mt-1">{error}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setError(null)}
            className="text-rose-400 hover:text-rose-300 h-6 w-6 p-0"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
