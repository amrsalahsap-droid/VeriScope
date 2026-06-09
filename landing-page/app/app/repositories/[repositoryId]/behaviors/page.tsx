"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { 
  ArrowLeft, 
  ChevronDown, 
  ChevronRight,
  ShieldAlert,
  FileText,
  CheckCircle,
  AlertCircle,
  Loader2,
  BarChart3
} from "lucide-react";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

interface Behavior {
  id: string;
  repository_id: string;
  journey_id: string | null;
  name: string;
  slug: string;
  description: string | null;
  journey_name: string | null;
  risk_level: string;
  risk_reason: string | null;
  risk_evidence: string | null;
  status: string;
  confidence: string | null;
  discovery_source: string;
  created_at: string;
  updated_at: string;
}

interface BehaviorEvidence {
  id: string;
  evidence_type: string;
  source_path: string | null;
  source_name: string | null;
  excerpt: string | null;
  confidence: string;
  created_at: string;
}

interface BehaviorScenario {
  id: string;
  title: string;
  description: string | null;
  priority: string;
  scenario_type: string;
  status: string;
  created_at: string;
  updated_at: string;
}

interface BehaviorDetail extends Behavior {
  journey: { id: string; name: string; slug: string } | null;
  risk: {
    risk_level: string;
    risk_reason: string | null;
    risk_evidence: string | null;
  };
  evidences: BehaviorEvidence[];
  scenarios: BehaviorScenario[];
}

interface PaginatedResponse {
  items: Behavior[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface PageProps {
  params: Promise<{ repositoryId: string }>;
}

function getRiskBadge(riskLevel: string) {
  const configs: Record<string, { bg: string; text: string; icon: any }> = {
    CRITICAL: { bg: "bg-rose-950/20", text: "text-rose-400/80", icon: ShieldAlert },
    HIGH: { bg: "bg-orange-950/20", text: "text-orange-400/80", icon: AlertCircle },
    MEDIUM: { bg: "bg-amber-950/20", text: "text-amber-400/80", icon: AlertCircle },
    LOW: { bg: "bg-emerald-950/20", text: "text-emerald-400/80", icon: CheckCircle },
  };
  const config = configs[riskLevel] || { bg: "bg-zinc-800", text: "text-zinc-400", icon: AlertCircle };
  const Icon = config.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}>
      <Icon className="w-3 h-3" />
      {riskLevel}
    </span>
  );
}

function getConfidenceBadge(confidence: string | null) {
  if (!confidence) return null;
  const configs: Record<string, { bg: string; text: string }> = {
    HIGH: { bg: "bg-emerald-950/20", text: "text-emerald-400/80" },
    MODERATE: { bg: "bg-amber-950/20", text: "text-amber-400/80" },
    LOW: { bg: "bg-zinc-800", text: "text-zinc-400" },
  };
  const config = configs[confidence] || { bg: "bg-zinc-800", text: "text-zinc-400" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}>
      {confidence}
    </span>
  );
}

export default function BehaviorsPage({ params }: PageProps) {
  const router = useRouter();
  const [repositoryId, setRepositoryId] = useState<string | null>(null);
  const [behaviors, setBehaviors] = useState<Behavior[]>([]);
  const [behaviorDetails, setBehaviorDetails] = useState<Map<string, BehaviorDetail>>(new Map());
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [loadingDetails, setLoadingDetails] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const fetchBehaviors = useCallback(async () => {
    if (!repositoryId) return;

    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/repositories/${repositoryId}/behaviors?page=${page}&page_size=50`,
        { cache: "no-store" }
      );
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) {
        setError("Failed to fetch behaviors");
        return;
      }
      const data: PaginatedResponse = await res.json();
      setBehaviors(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err: any) {
      setError(err?.message || "Failed to fetch behaviors");
    } finally {
      setLoading(false);
    }
  }, [repositoryId, page]);

  const fetchBehaviorDetail = useCallback(async (behaviorId: string) => {
    if (!repositoryId) return;

    setLoadingDetails(prev => new Set(prev).add(behaviorId));
    try {
      const res = await fetch(
        `/api/repositories/${repositoryId}/behaviors/${behaviorId}`,
        { cache: "no-store" }
      );
      if (!res.ok) {
        return;
      }
      const data: BehaviorDetail = await res.json();
      setBehaviorDetails(prev => new Map(prev).set(behaviorId, data));
    } catch (err) {
      console.error("Failed to fetch behavior detail:", err);
    } finally {
      setLoadingDetails(prev => {
        const next = new Set(prev);
        next.delete(behaviorId);
        return next;
      });
    }
  }, [repositoryId]);

  const toggleRow = useCallback(async (behaviorId: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(behaviorId)) {
      newExpanded.delete(behaviorId);
    } else {
      newExpanded.add(behaviorId);
      if (!behaviorDetails.has(behaviorId)) {
        await fetchBehaviorDetail(behaviorId);
      }
    }
    setExpandedRows(newExpanded);
  }, [expandedRows, behaviorDetails, fetchBehaviorDetail]);

  useEffect(() => {
    params.then(p => setRepositoryId(p.repositoryId));
  }, [params]);

  useEffect(() => {
    if (repositoryId) fetchBehaviors();
  }, [repositoryId, fetchBehaviors]);

  if (loading) {
    return (
      <div className="space-y-6 max-w-6xl">
        <div className="flex items-center gap-4 animate-pulse">
          <div className="h-8 w-8 bg-zinc-800 rounded-lg" />
          <div className="h-6 w-48 bg-zinc-800 rounded-lg" />
        </div>
        <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 animate-pulse">
          <div className="h-4 w-32 bg-zinc-800 rounded mb-4" />
          <div className="space-y-3">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 w-full bg-zinc-800 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href={`/app/repositories/${repositoryId}`}>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white">Behavior Catalog</h1>
            <p className="text-sm text-zinc-500">Discovered business behaviors for this repository</p>
          </div>
        </div>
        <Link href={`/app/repositories/${repositoryId}/behaviors/diagnostics`}>
          <Button variant="outline" size="sm">
            <BarChart3 className="w-4 h-4 mr-2" />
            Diagnostics
          </Button>
        </Link>
      </div>

      {error && (
        <div className="bg-rose-950/20 border border-rose-800/40 rounded-xl p-4 text-sm text-rose-400">
          {error}
        </div>
      )}

      {/* Behaviors Table */}
      <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl overflow-hidden">
        <div className="p-5 border-b border-zinc-800/60">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-200">
              Behaviors ({total})
            </h3>
          </div>
        </div>

        {behaviors.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-12 h-12 rounded-lg bg-zinc-800 flex items-center justify-center mx-auto mb-3">
              <FileText className="w-6 h-6 text-zinc-500" />
            </div>
            <h4 className="text-sm font-medium text-zinc-200 mb-1">No behaviors discovered</h4>
            <p className="text-xs text-zinc-500 max-w-sm mx-auto">
              Behaviors will be automatically discovered from your repository code.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/60">
            {behaviors.map((behavior) => {
              const isExpanded = expandedRows.has(behavior.id);
              const detail = behaviorDetails.get(behavior.id);
              const isLoadingDetail = loadingDetails.has(behavior.id);

              return (
                <div key={behavior.id}>
                  {/* Row */}
                  <div
                    className="p-4 hover:bg-zinc-800/30 cursor-pointer transition-colors"
                    onClick={() => toggleRow(behavior.id)}
                  >
                    <div className="flex items-center gap-4">
                      <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0">
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-zinc-400" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-zinc-400" />
                        )}
                      </Button>

                      <div className="flex-1 min-w-0 grid grid-cols-12 gap-4 items-center">
                        {/* Journey */}
                        <div className="col-span-2 min-w-0">
                          <p className="text-sm text-zinc-300 truncate" title={behavior.journey_name || "N/A"}>
                            {behavior.journey_name || "N/A"}
                          </p>
                        </div>

                        {/* Behavior */}
                        <div className="col-span-3 min-w-0">
                          <p className="text-sm font-medium text-zinc-200 truncate" title={behavior.name}>
                            {behavior.name}
                          </p>
                        </div>

                        {/* Risk */}
                        <div className="col-span-2">
                          {getRiskBadge(behavior.risk_level)}
                        </div>

                        {/* Confidence */}
                        <div className="col-span-2">
                          {getConfidenceBadge(behavior.confidence)}
                        </div>

                        {/* Evidence Count */}
                        <div className="col-span-1">
                          <p className="text-sm text-zinc-400">
                            {detail?.evidences.length ?? "-"}
                          </p>
                        </div>

                        {/* Scenario Count */}
                        <div className="col-span-1">
                          <p className="text-sm text-zinc-400">
                            {detail?.scenarios.length ?? "-"}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="px-4 pb-4 bg-zinc-800/20 border-t border-zinc-800/60">
                      {isLoadingDetail ? (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="w-5 h-5 text-zinc-500 animate-spin" />
                        </div>
                      ) : detail ? (
                        <div className="space-y-4 pt-4">
                          {/* Description */}
                          {detail.description && (
                            <div>
                              <h4 className="text-xs font-medium text-zinc-400 mb-2">Description</h4>
                              <p className="text-sm text-zinc-300">{detail.description}</p>
                            </div>
                          )}

                          {/* Risk */}
                          <div>
                            <h4 className="text-xs font-medium text-zinc-400 mb-2">Risk Assessment</h4>
                            <div className="bg-zinc-900/50 rounded-lg p-3 space-y-2">
                              <div className="flex items-center gap-2">
                                {getRiskBadge(detail.risk.risk_level)}
                              </div>
                              {detail.risk.risk_reason && (
                                <p className="text-sm text-zinc-300">{detail.risk.risk_reason}</p>
                              )}
                              {detail.risk.risk_evidence && (
                                <div className="text-xs text-zinc-500 whitespace-pre-line">
                                  {detail.risk.risk_evidence}
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Evidence */}
                          {detail.evidences.length > 0 && (
                            <div>
                              <h4 className="text-xs font-medium text-zinc-400 mb-2">
                                Evidence ({detail.evidences.length})
                              </h4>
                              <div className="space-y-2">
                                {detail.evidences.map((evidence) => (
                                  <div
                                    key={evidence.id}
                                    className="bg-zinc-900/50 rounded-lg p-3 text-sm"
                                  >
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-zinc-800 text-zinc-400">
                                        {evidence.evidence_type}
                                      </span>
                                      {getConfidenceBadge(evidence.confidence)}
                                    </div>
                                    {evidence.source_path && (
                                      <p className="text-xs text-zinc-400 font-mono mb-1">
                                        {evidence.source_path}
                                      </p>
                                    )}
                                    {evidence.excerpt && (
                                      <p className="text-xs text-zinc-500 italic">
                                        "{evidence.excerpt}"
                                      </p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Scenarios */}
                          {detail.scenarios.length > 0 && (
                            <div>
                              <h4 className="text-xs font-medium text-zinc-400 mb-2">
                                Scenarios ({detail.scenarios.length})
                              </h4>
                              <div className="space-y-2">
                                {detail.scenarios.map((scenario) => (
                                  <div
                                    key={scenario.id}
                                    className="bg-zinc-900/50 rounded-lg p-3 text-sm"
                                  >
                                    <div className="flex items-center gap-2 mb-1">
                                      <p className="text-sm font-medium text-zinc-200">
                                        {scenario.title}
                                      </p>
                                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-zinc-800 text-zinc-400">
                                        {scenario.priority}
                                      </span>
                                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-zinc-800 text-zinc-400">
                                        {scenario.scenario_type}
                                      </span>
                                    </div>
                                    {scenario.description && (
                                      <p className="text-xs text-zinc-500">{scenario.description}</p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Metadata */}
                          <div className="flex items-center gap-4 text-xs text-zinc-500 pt-2 border-t border-zinc-800/60">
                            <span>Discovery: {detail.discovery_source}</span>
                            <span>Status: {detail.status}</span>
                            <span>Updated: {new Date(detail.updated_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                      ) : (
                        <div className="py-4 text-center text-sm text-zinc-500">
                          Failed to load behavior details
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-zinc-800/60 flex items-center justify-between">
            <p className="text-xs text-zinc-500">
              Page {page} of {totalPages} · {total} total
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="border-zinc-700 bg-zinc-800/60 text-zinc-300 hover:bg-zinc-700 hover:text-white"
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="border-zinc-700 bg-zinc-800/60 text-zinc-300 hover:bg-zinc-700 hover:text-white"
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
