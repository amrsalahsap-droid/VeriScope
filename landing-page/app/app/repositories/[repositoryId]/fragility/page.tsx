"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  AlertTriangle,
  Shield,
  FileCode,
  GitBranch,
  Clock,
  Filter,
  ChevronDown,
  BarChart2,
  History,
  Zap,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

// ── Types ──────────────────────────────────────────────────────────────────

interface FragilityDashboardData {
  summary: {
    total_memories: number;
    active_memories: number;
    stale_memories: number;
    critical_count: number;
    high_count: number;
    average_score: number;
  };
  top_fragile_behaviors: Array<{
    id: string;
    subject_id: string | null;
    subject_name: string;
    memory_type: string;
    risk_level: string;
    fragility_score: number;
    confidence: number;
    status: string;
    last_seen_at: string | null;
    evidence_count: number;
  }>;
  top_fragile_journeys: Array<{
    id: string;
    subject_id: string | null;
    subject_name: string;
    memory_type: string;
    risk_level: string;
    fragility_score: number;
    confidence: number;
    status: string;
    last_seen_at: string | null;
    evidence_count: number;
  }>;
  repeated_failing_tests: Array<{
    id: string;
    subject_name: string;
    memory_type: string;
    risk_level: string;
    fragility_score: number;
    confidence: number;
    status: string;
    last_seen_at: string | null;
    evidence_count: number;
  }>;
  file_hotspots: Array<{
    id: string;
    subject_name: string;
    memory_type: string;
    risk_level: string;
    fragility_score: number;
    confidence: number;
    status: string;
    last_seen_at: string | null;
    evidence_count: number;
  }>;
  risky_combinations: Array<{
    id: string;
    subject_name: string;
    memory_type: string;
    risk_level: string;
    fragility_score: number;
    confidence: number;
    status: string;
    last_seen_at: string | null;
    evidence_count: number;
  }>;
  missing_coverage_patterns: Array<{
    id: string;
    subject_name: string;
    memory_type: string;
    risk_level: string;
    fragility_score: number;
    confidence: number;
    status: string;
    last_seen_at: string | null;
    evidence_count: number;
  }>;
  escaped_defect_patterns: Array<{
    id: string;
    subject_name: string;
    memory_type: string;
    risk_level: string;
    fragility_score: number;
    confidence: number;
    status: string;
    last_seen_at: string | null;
    evidence_count: number;
  }>;
  stale_patterns: Array<{
    id: string;
    subject_name: string;
    subject_type: string;
    memory_type: string;
    risk_level: string;
    fragility_score: number;
    confidence: number;
    status: string;
    last_seen_at: string | null;
    evidence_count: number;
  }>;
}

// ── Helpers ────────────────────────────────────────────────────────────────

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

function riskBadge(level: string) {
  const map: Record<string, { bg: string; text: string; dot: string }> = {
    CRITICAL: { bg: "bg-rose-950/30", text: "text-rose-400", dot: "bg-rose-400" },
    HIGH:     { bg: "bg-amber-950/30", text: "text-amber-400", dot: "bg-amber-400" },
    MODERATE: { bg: "bg-yellow-950/30", text: "text-yellow-400", dot: "bg-yellow-400" },
    LOW:      { bg: "bg-emerald-950/20", text: "text-emerald-400", dot: "bg-emerald-400" },
  };
  const s = map[level] ?? map.MODERATE;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {level.charAt(0) + level.slice(1).toLowerCase()}
    </span>
  );
}

function statusBadge(status: string) {
  const map: Record<string, { bg: string; text: string }> = {
    ACTIVE: { bg: "bg-emerald-500/10", text: "text-emerald-400" },
    STALE:  { bg: "bg-zinc-500/10", text: "text-zinc-400" },
  };
  const s = map[status] ?? map.ACTIVE;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${s.bg} ${s.text}`}>
      {status}
    </span>
  );
}

// ── Components ─────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, color }: { icon: any, label: string, value: number | string, color: string }) {
  return (
    <div className="p-4 rounded-xl bg-zinc-950/30 border border-zinc-800/60">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon className="w-4 h-4" />
        </div>
        <div>
          <p className="text-xs text-zinc-500">{label}</p>
          <p className="text-lg font-semibold text-zinc-100">{value}</p>
        </div>
      </div>
    </div>
  );
}

function FragilityItem({ item, type }: { item: any, type: string }) {
  const riskColor = item.risk_level === "CRITICAL" ? "text-rose-400" :
                   item.risk_level === "HIGH" ? "text-amber-400" :
                   item.risk_level === "MODERATE" ? "text-yellow-400" : "text-emerald-400";

  return (
    <div className="p-3 rounded-lg bg-zinc-950/30 border border-zinc-800/60 hover:border-zinc-700/60 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-sm font-medium ${riskColor}`}>{item.subject_name}</span>
            {riskBadge(item.risk_level)}
            {statusBadge(item.status)}
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-500">
            <span>Score: {item.fragility_score.toFixed(1)}</span>
            <span>Evidence: {item.evidence_count}</span>
            <span>Confidence: {(item.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
        {item.last_seen_at && (
          <div className="flex items-center gap-1 text-xs text-zinc-500 shrink-0">
            <Clock className="w-3 h-3" />
            {formatRelative(item.last_seen_at)}
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, icon: Icon, children }: { title: string, icon: any, children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-zinc-400" />
        <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
      </div>
      {children}
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function FragilityDashboardPage() {
  const params = useParams();
  const repositoryId = params.repositoryId as string;
  
  const [data, setData] = useState<FragilityDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [timeframeDays, setTimeframeDays] = useState<number | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append("status_filter", statusFilter);
      if (timeframeDays) params.append("timeframe_days", timeframeDays.toString());
      
      const url = `/api/fragility/${repositoryId}/dashboard${params.toString() ? `?${params.toString()}` : ""}`;
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error("Failed to fetch dashboard data");
      }
      
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  }, [repositoryId, statusFilter, timeframeDays]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const clearFilters = () => {
    setStatusFilter("");
    setTimeframeDays(null);
  };

  const hasActiveFilters = statusFilter || timeframeDays;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-500 mx-auto mb-4"></div>
          <p className="text-sm text-zinc-500">Loading fragility dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-rose-400 mx-auto mb-4" />
          <p className="text-sm text-zinc-400 mb-4">{error}</p>
          <Button onClick={fetchDashboard} variant="outline" size="sm">
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <div className="border-b border-zinc-800/60 bg-zinc-950/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href={`/repositories/${repositoryId}`}
                className="p-2 hover:bg-zinc-800/50 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-zinc-400" />
              </Link>
              <div>
                <h1 className="text-lg font-semibold text-zinc-100">Fragility Dashboard</h1>
                <p className="text-xs text-zinc-500">Historical patterns and risk signals</p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              {hasActiveFilters && (
                <Button
                  onClick={clearFilters}
                  variant="ghost"
                  size="sm"
                  className="text-zinc-400 hover:text-zinc-200"
                >
                  <X className="w-4 h-4 mr-1" />
                  Clear filters
                </Button>
              )}
              <Button
                onClick={() => setShowFilters(!showFilters)}
                variant="outline"
                size="sm"
              >
                <Filter className="w-4 h-4 mr-2" />
                Filters
                {hasActiveFilters && <span className="ml-1 px-1.5 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs">Active</span>}
              </Button>
            </div>
          </div>
          
          {/* Filter Panel */}
          {showFilters && (
            <div className="mt-4 p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/60 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-2">Status</label>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800/60 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-zinc-700"
                  >
                    <option value="">All</option>
                    <option value="ACTIVE">Active</option>
                    <option value="STALE">Stale</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-2">Timeframe (days)</label>
                  <select
                    value={timeframeDays || ""}
                    onChange={(e) => setTimeframeDays(e.target.value ? parseInt(e.target.value) : null)}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800/60 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-zinc-700"
                  >
                    <option value="">All time</option>
                    <option value="7">Last 7 days</option>
                    <option value="30">Last 30 days</option>
                    <option value="90">Last 90 days</option>
                    <option value="180">Last 180 days</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Summary Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatCard icon={BarChart2} label="Total Patterns" value={data.summary.total_memories} color="bg-blue-500/10 text-blue-400" />
          <StatCard icon={Zap} label="Active" value={data.summary.active_memories} color="bg-emerald-500/10 text-emerald-400" />
          <StatCard icon={Clock} label="Stale" value={data.summary.stale_memories} color="bg-zinc-500/10 text-zinc-400" />
          <StatCard icon={AlertTriangle} label="Critical" value={data.summary.critical_count} color="bg-rose-500/10 text-rose-400" />
          <StatCard icon={Shield} label="High Risk" value={data.summary.high_count} color="bg-amber-500/10 text-amber-400" />
          <StatCard icon={History} label="Avg Score" value={data.summary.average_score.toFixed(1)} color="bg-purple-500/10 text-purple-400" />
        </div>

        {/* Top Fragile Behaviors */}
        {data.top_fragile_behaviors.length > 0 && (
          <Section title="Top Fragile Behaviors" icon={Zap}>
            <div className="space-y-2">
              {data.top_fragile_behaviors.map((item) => (
                <FragilityItem key={item.id} item={item} type="behavior" />
              ))}
            </div>
          </Section>
        )}

        {/* Top Fragile Journeys */}
        {data.top_fragile_journeys.length > 0 && (
          <Section title="Top Fragile Journeys" icon={GitBranch}>
            <div className="space-y-2">
              {data.top_fragile_journeys.map((item) => (
                <FragilityItem key={item.id} item={item} type="journey" />
              ))}
            </div>
          </Section>
        )}

        {/* Repeated Failing Tests */}
        {data.repeated_failing_tests.length > 0 && (
          <Section title="Repeated Failing Tests" icon={AlertTriangle}>
            <div className="space-y-2">
              {data.repeated_failing_tests.map((item) => (
                <FragilityItem key={item.id} item={item} type="test" />
              ))}
            </div>
          </Section>
        )}

        {/* File Hotspots */}
        {data.file_hotspots.length > 0 && (
          <Section title="File Hotspots" icon={FileCode}>
            <div className="space-y-2">
              {data.file_hotspots.map((item) => (
                <FragilityItem key={item.id} item={item} type="file" />
              ))}
            </div>
          </Section>
        )}

        {/* Risky Combinations */}
        {data.risky_combinations.length > 0 && (
          <Section title="Risky Combinations" icon={Shield}>
            <div className="space-y-2">
              {data.risky_combinations.map((item) => (
                <FragilityItem key={item.id} item={item} type="combination" />
              ))}
            </div>
          </Section>
        )}

        {/* Missing Coverage Patterns */}
        {data.missing_coverage_patterns.length > 0 && (
          <Section title="Missing Coverage Patterns" icon={Zap}>
            <div className="space-y-2">
              {data.missing_coverage_patterns.map((item) => (
                <FragilityItem key={item.id} item={item} type="coverage" />
              ))}
            </div>
          </Section>
        )}

        {/* Escaped Defect Patterns */}
        {data.escaped_defect_patterns.length > 0 && (
          <Section title="Escaped Defect Patterns" icon={AlertTriangle}>
            <div className="space-y-2">
              {data.escaped_defect_patterns.map((item) => (
                <FragilityItem key={item.id} item={item} type="defect" />
              ))}
            </div>
          </Section>
        )}

        {/* Stale Patterns */}
        {data.stale_patterns.length > 0 && (
          <Section title="Stale Patterns" icon={Clock}>
            <div className="space-y-2">
              {data.stale_patterns.map((item) => (
                <FragilityItem key={item.id} item={item} type="stale" />
              ))}
            </div>
          </Section>
        )}

        {/* Empty State */}
        {data.summary.total_memories === 0 && (
          <div className="text-center py-12">
            <Shield className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <p className="text-sm text-zinc-500">No fragility patterns detected yet</p>
            <p className="text-xs text-zinc-600 mt-1">Patterns will appear as the system learns from historical data</p>
          </div>
        )}
      </div>
    </div>
  );
}
