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
  BarChart3,
  TrendingUp,
  Database
} from "lucide-react";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

interface BehaviorDiagnosticsSummary {
  total_behaviors: number;
  high_confidence: number;
  medium_confidence: number;
  low_confidence: number;
  evidence_sources: Record<string, number>;
  discovery_coverage: number;
  last_updated: string;
}

interface BehaviorDiagnosticsDetail {
  behavior_id: string;
  behavior_name: string;
  confidence: string;
  evidence_count: number;
  discovery_sources: string[];
  confidence_breakdown: any;
  journey: string | null;
  risk_level: string | null;
}

interface BehaviorDiagnosticsResponse {
  repository_id: string;
  summary: BehaviorDiagnosticsSummary;
  behaviors: BehaviorDiagnosticsDetail[];
}

interface PageProps {
  params: Promise<{ repositoryId: string }>;
}

function getConfidenceBadge(confidence: string) {
  const configs: Record<string, { bg: string; text: string; icon: any }> = {
    HIGH: { bg: "bg-emerald-950/20", text: "text-emerald-400/80", icon: CheckCircle },
    MODERATE: { bg: "bg-amber-950/20", text: "text-amber-400/80", icon: AlertCircle },
    LOW: { bg: "bg-rose-950/20", text: "text-rose-400/80", icon: ShieldAlert },
  };
  const config = configs[confidence] || { bg: "bg-zinc-800", text: "text-zinc-400", icon: AlertCircle };
  const Icon = config.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}>
      <Icon className="w-3 h-3" />
      {confidence}
    </span>
  );
}

function getRiskBadge(riskLevel: string | null) {
  if (!riskLevel) return null;
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

export default function BehaviorDiagnosticsPage({ params }: PageProps) {
  const router = useRouter();
  const [repositoryId, setRepositoryId] = useState<string>("");
  const [diagnostics, setDiagnostics] = useState<BehaviorDiagnosticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedBehavior, setExpandedBehavior] = useState<string | null>(null);

  useEffect(() => {
    params.then((resolvedParams) => {
      setRepositoryId(resolvedParams.repositoryId);
      fetchDiagnostics(resolvedParams.repositoryId);
    });
  }, [params]);

  const fetchDiagnostics = useCallback(async (repoId: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/repositories/${repoId}/behaviors/diagnostics`);
      if (!response.ok) {
        throw new Error("Failed to fetch diagnostics");
      }
      const data = await response.json();
      setDiagnostics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  }, []);

  const toggleExpand = (behaviorId: string) => {
    setExpandedBehavior(expandedBehavior === behaviorId ? null : behaviorId);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-zinc-950">
        <Loader2 className="w-8 h-8 text-zinc-400 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-zinc-950">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-rose-400 mx-auto mb-4" />
          <p className="text-zinc-400">{error}</p>
          <Button onClick={() => fetchDiagnostics(repositoryId)} className="mt-4">
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (!diagnostics) {
    return null;
  }

  const { summary, behaviors } = diagnostics;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <div className="border-b border-zinc-800 bg-zinc-900/50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href={`/app/repositories/${repositoryId}`}>
                <Button variant="ghost" size="sm">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>
              </Link>
              <div>
                <h1 className="text-xl font-semibold text-zinc-100">Behavior Discovery Diagnostics</h1>
                <p className="text-sm text-zinc-400">Inspection of discovery quality</p>
              </div>
            </div>
            <Link href={`/app/repositories/${repositoryId}/behaviors`}>
              <Button variant="outline" size="sm">
                <FileText className="w-4 h-4 mr-2" />
                View Behaviors
              </Button>
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <BarChart3 className="w-5 h-5 text-zinc-400" />
              <span className="text-sm text-zinc-400">Total Behaviors</span>
            </div>
            <div className="text-2xl font-semibold text-zinc-100">{summary.total_behaviors}</div>
          </div>

          <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <CheckCircle className="w-5 h-5 text-emerald-400" />
              <span className="text-sm text-zinc-400">High Confidence</span>
            </div>
            <div className="text-2xl font-semibold text-emerald-400">{summary.high_confidence}</div>
          </div>

          <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <AlertCircle className="w-5 h-5 text-amber-400" />
              <span className="text-sm text-zinc-400">Medium Confidence</span>
            </div>
            <div className="text-2xl font-semibold text-amber-400">{summary.medium_confidence}</div>
          </div>

          <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <ShieldAlert className="w-5 h-5 text-rose-400" />
              <span className="text-sm text-zinc-400">Low Confidence</span>
            </div>
            <div className="text-2xl font-semibold text-rose-400">{summary.low_confidence}</div>
          </div>
        </div>

        {/* Discovery Coverage */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <TrendingUp className="w-5 h-5 text-zinc-400" />
              <h2 className="text-lg font-semibold text-zinc-100">Discovery Coverage</h2>
            </div>
            <div className="text-2xl font-semibold text-zinc-100">{summary.discovery_coverage.toFixed(1)}%</div>
          </div>
          <div className="w-full bg-zinc-800 rounded-full h-2">
            <div 
              className="bg-blue-500 h-2 rounded-full transition-all"
              style={{ width: `${summary.discovery_coverage}%` }}
            />
          </div>
          <p className="text-sm text-zinc-400 mt-2">
            Last updated: {new Date(summary.last_updated).toLocaleString()}
          </p>
        </div>

        {/* Evidence Sources */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-6 mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Database className="w-5 h-5 text-zinc-400" />
            <h2 className="text-lg font-semibold text-zinc-100">Evidence Sources</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(summary.evidence_sources).map(([source, count]) => (
              <div key={source} className="bg-zinc-800/50 rounded p-3">
                <div className="text-sm text-zinc-400 mb-1">{source}</div>
                <div className="text-xl font-semibold text-zinc-100">{count}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Behavior Details */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg">
          <div className="p-6 border-b border-zinc-800">
            <h2 className="text-lg font-semibold text-zinc-100">Behavior Details</h2>
            <p className="text-sm text-zinc-400 mt-1">Per-beavior confidence and discovery sources</p>
          </div>
          
          <div className="divide-y divide-zinc-800">
            {behaviors.map((behavior) => (
              <div key={behavior.behavior_id} className="p-4">
                <div 
                  className="flex items-center justify-between cursor-pointer hover:bg-zinc-800/50 rounded p-2 -mx-2"
                  onClick={() => toggleExpand(behavior.behavior_id)}
                >
                  <div className="flex items-center gap-4 flex-1">
                    <ChevronRight 
                      className={`w-4 h-4 text-zinc-400 transition-transform ${
                        expandedBehavior === behavior.behavior_id ? 'rotate-90' : ''
                      }`}
                    />
                    <div className="flex-1">
                      <div className="font-medium text-zinc-100">{behavior.behavior_name}</div>
                      <div className="flex items-center gap-2 mt-1">
                        {getConfidenceBadge(behavior.confidence)}
                        {getRiskBadge(behavior.risk_level)}
                        {behavior.journey && (
                          <span className="text-xs text-zinc-400">{behavior.journey}</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="text-sm text-zinc-400">
                    {behavior.evidence_count} evidence(s)
                  </div>
                </div>

                {expandedBehavior === behavior.behavior_id && (
                  <div className="mt-4 pl-8 pr-4 pb-2">
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div>
                        <div className="text-xs text-zinc-400 mb-1">Discovery Sources</div>
                        <div className="flex flex-wrap gap-1">
                          {behavior.discovery_sources.map((source) => (
                            <span key={source} className="text-xs bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded">
                              {source}
                            </span>
                          ))}
                        </div>
                      </div>
                      {behavior.confidence_breakdown && (
                        <div>
                          <div className="text-xs text-zinc-400 mb-1">Confidence Breakdown</div>
                          <div className="text-xs text-zinc-300">
                            High: {behavior.confidence_breakdown.high_confidence_evidence} | 
                            Medium: {behavior.confidence_breakdown.medium_confidence_evidence} | 
                            Low: {behavior.confidence_breakdown.low_confidence_evidence}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
