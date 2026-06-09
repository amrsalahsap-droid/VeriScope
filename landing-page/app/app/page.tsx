"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Activity,
  ShieldAlert,
  Gauge,
  Zap,
  BarChart3,
  Target,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  FolderGit2,
  ChevronRight,
  RefreshCw,
  Sliders,
  FileCode2,
  HelpCircle,
  Info,
  PlaySquare,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

interface Repository {
  id: string;
  name: string;
  full_name: string;
  selected_for_analysis: boolean;
}

interface RiskDomain {
  domain: string;
  risk_level: string;
  occurrence_count: number;
}

interface FragileModule {
  file_path: string;
  fragility_score: number;
  failure_count: number;
  recommendation: string;
}

interface ValuableTest {
  stable_identity: string;
  display_name: string;
  priority_score: number;
  run_count: number;
}

interface AddedTest {
  test_case_id: string;
  display_name: string;
  manual_addition_count: number;
}

interface DashboardData {
  top_risk_domains: RiskDomain[];
  most_fragile_modules: FragileModule[];
  most_valuable_tests: ValuableTest[];
  most_added_tests: AddedTest[];
  recommendation_accuracy: {
    score: number;
    score_raw: number;
    rationale: string;
    total_recommendations: number;
    override_rate: number;
  };
  escaped_defects: {
    rate: number;
    count: number;
    rollback_rate: number;
    rollback_count: number;
    total_outcomes: number;
  };
  runtime_saved: {
    total_seconds: number;
    formatted: string;
    run_count: number;
  };
  coverage_health: Array<{
    quality: string;
    count: number;
    percentage: number;
  }>;
  total_runs_analyzed: number;
  lookback_days: number;
}

export default function AppDashboardPage() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string>("all");
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [reposLoading, setReposLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 1. Fetch connected repositories to populate dropdown filter
  const fetchRepositories = useCallback(async () => {
    setReposLoading(true);
    try {
      const res = await fetch("/api/repositories", { cache: "no-store" });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      const json = await res.json().catch(() => ({}));
      if (res.ok) {
        // Filter down to repositories connected and selected for analysis
        setRepos(json.repositories || []);
      }
    } catch (e: any) {
      console.error("Failed to load repositories:", e);
    } finally {
      setReposLoading(false);
    }
  }, []);

  // 2. Fetch Dashboard metrics dynamically based on repo selection
  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let url = "/api/intelligence/dashboard";
      if (selectedRepoId !== "all") {
        url += `?repository_id=${selectedRepoId}`;
      }
      const res = await fetch(url, { cache: "no-store" });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(json?.error || `Backend returned status ${res.status}`);
        return;
      }
      setData(json);
    } catch (e: any) {
      setError(e?.message || "Failed to load dashboard intelligence data");
    } finally {
      setLoading(false);
    }
  }, [selectedRepoId]);

  useEffect(() => {
    fetchRepositories();
  }, [fetchRepositories]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Leadership assessment narrative generator
  const getExecutiveBrief = () => {
    if (!data) return "";
    const accuracy = data.recommendation_accuracy.score;
    const escaped = data.escaped_defects.count;
    const rollbacks = data.escaped_defects.rollback_count;
    const runtime = data.runtime_saved.formatted;
    const runs = data.runtime_saved.run_count;

    if (runs === 0) {
      return "No pipeline runs have been executed within the 30-day lookback window. Connect your repositories and execute test suites to calibrate regression metrics.";
    }

    let brief = `Veriscope has calibrated recommendations across ${runs} pipeline runs. `;
    brief += `Testing recommendation accuracy is at ${accuracy}%, successfully containing `;
    
    if (escaped === 0) {
      brief += "100% of regressions within verified test suites with zero escaped defects. ";
    } else {
      brief += `regression risks, with only ${escaped} defect${escaped > 1 ? "s" : ""} escaping verified scopes. `;
      if (rollbacks > 0) {
        brief += `Additionally, ${rollbacks} rollback${rollbacks > 1 ? "s were" : " was"} resolved via trust calibration. `;
      }
    }
    
    brief += `Total CI pipeline saved execution time is calibrated at ${runtime}. `;
    
    if (data.top_risk_domains.length > 0) {
      const topDomain = data.top_risk_domains[0].domain;
      brief += `The primary focus of testing risk resides within the "${topDomain}" domain.`;
    } else {
      brief += "Overall codebase stability is within normal tolerances.";
    }

    return brief;
  };

  const getSystemHealthLevel = () => {
    if (!data || data.total_runs_analyzed === 0) return "UNKNOWN";
    const escaped = data.escaped_defects.count;
    const accuracy = data.recommendation_accuracy.score;
    
    if (escaped > 3 || accuracy < 85) return "ATTENTION";
    if (escaped > 0 || accuracy < 95) return "STABLE";
    return "OPTIMAL";
  };

  const health = getSystemHealthLevel();

  return (
    <div className="space-y-8 max-w-6xl">
      {/* 1. Dashboard Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-5 border-b border-zinc-900 pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl flex items-center gap-2">
            <BarChart3 className="w-8 h-8 text-white" />
            Intelligence Dashboard
          </h1>
          <p className="text-sm text-zinc-400 mt-1.5">
            Calibrated codebase regression risk, fragile systems, and test execution efficiency
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Repository Dropdown Selector */}
          <div className="flex items-center gap-2 bg-zinc-900/60 border border-zinc-800 rounded-lg px-3 py-1.5 focus-within:border-zinc-700 transition duration-200">
            <FolderGit2 className="w-4 h-4 text-zinc-500" />
            <select
              value={selectedRepoId}
              onChange={(e) => setSelectedRepoId(e.target.value)}
              disabled={reposLoading}
              className="bg-transparent text-xs font-semibold text-zinc-200 focus:outline-none cursor-pointer pr-4"
            >
              <option value="all" className="bg-zinc-950 text-zinc-300">
                All Repositories
              </option>
              {repos.map((repo) => (
                <option key={repo.id} value={repo.id} className="bg-zinc-950 text-zinc-300">
                  {repo.full_name}
                </option>
              ))}
            </select>
          </div>

          <Button
            onClick={() => {
              fetchRepositories();
              fetchDashboardData();
            }}
            variant="ghost"
            size="icon"
            className="h-9 w-9 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900 border border-zinc-900 rounded-lg"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-zinc-300" : ""}`} />
          </Button>
        </div>
      </div>

      {loading ? (
        // 2. Loading State (Skeletons)
        <div className="space-y-6">
          <div className="h-32 w-full bg-zinc-900/30 border border-zinc-900 rounded-2xl animate-pulse" />
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-32 bg-zinc-900/30 border border-zinc-900 rounded-xl animate-pulse" />
            ))}
          </div>
          <div className="grid lg:grid-cols-2 gap-6">
            <div className="h-80 bg-zinc-900/20 border border-zinc-900 rounded-xl animate-pulse" />
            <div className="h-80 bg-zinc-900/20 border border-zinc-900 rounded-xl animate-pulse" />
          </div>
        </div>
      ) : error ? (
        // 3. Error State
        <div className="bg-rose-950/10 border border-rose-900/30 rounded-2xl p-8 text-center max-w-xl mx-auto space-y-4">
          <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto" />
          <h3 className="text-md font-semibold text-rose-300">Dashboard Ingestion Failed</h3>
          <p className="text-xs text-rose-400/80 leading-relaxed">
            {error}. Ensure the PostgreSQL database migrations have been successfully executed and the FastAPI server is running.
          </p>
          <Button
            onClick={fetchDashboardData}
            variant="outline"
            size="sm"
            className="border-rose-900/50 hover:bg-rose-950/20 text-rose-300 rounded-lg text-xs"
          >
            Retry Sync
          </Button>
        </div>
      ) : !data || data.total_runs_analyzed === 0 ? (
        // 4. Empty State
        <div className="border border-zinc-800/80 rounded-2xl bg-zinc-900/10 p-16 text-center max-w-2xl mx-auto space-y-6">
          <div className="w-12 h-12 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto shadow-lg shadow-white/5">
            <Target className="w-6 h-6 text-zinc-500" />
          </div>
          <div className="space-y-2">
            <h3 className="text-md font-semibold text-zinc-300">No Intelligence Insights Available</h3>
            <p className="text-xs text-zinc-500 max-w-md mx-auto leading-relaxed">
              Veriscope requires active pipeline test execution metrics in the database. Ensure GitHub webhook integration is receiving regression payloads, or execute local test suites.
            </p>
          </div>
          <div className="flex justify-center gap-3">
            <a href="/app/repositories">
              <Button size="sm" className="bg-white text-zinc-950 hover:bg-zinc-200 font-semibold text-xs rounded-lg">
                Connect Repository
              </Button>
            </a>
          </div>
        </div>
      ) : (
        // 5. Dashboard Visual Presentation
        <div className="space-y-8 animate-fade-in">
          {/* A. Executive Calibrated Risk Hero widget */}
          <div className="relative overflow-hidden bg-gradient-to-br from-zinc-900/40 via-zinc-900/20 to-transparent border border-zinc-950 rounded-2xl p-6 sm:p-7 shadow-xl shadow-black/40">
            <div className="absolute top-0 right-0 w-80 h-80 bg-zinc-800/5 rounded-full filter blur-3xl pointer-events-none" />
            
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div className="space-y-3 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded">
                    Executive Briefing
                  </span>
                  
                  {health === "OPTIMAL" && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400 px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
                      <CheckCircle2 className="w-3 h-3" /> System Optimal
                    </span>
                  )}
                  {health === "STABLE" && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-400 px-2 py-0.5 bg-amber-500/10 border border-amber-500/20 rounded-full">
                      <Info className="w-3 h-3" /> Calibration Stable
                    </span>
                  )}
                  {health === "ATTENTION" && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-rose-400 px-2 py-0.5 bg-rose-500/10 border border-rose-500/20 rounded-full">
                      <ShieldAlert className="w-3 h-3" /> Action Required
                    </span>
                  )}
                </div>
                
                <h2 className="text-lg font-bold text-white tracking-tight">Calibrated Testing & Regression Brief</h2>
                <p className="text-xs text-zinc-300 leading-relaxed font-medium max-w-4xl">
                  {getExecutiveBrief()}
                </p>
              </div>

              <div className="bg-zinc-950/60 border border-zinc-900 rounded-xl p-4 md:w-56 shrink-0 flex flex-col justify-center space-y-1">
                <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-wider">Calibration Integrity</span>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-3xl font-extrabold text-white">{data.recommendation_accuracy.score}%</span>
                  <span className="text-[10px] font-semibold text-zinc-500">Score</span>
                </div>
                <div className="w-full bg-zinc-900 h-1.5 rounded-full overflow-hidden mt-2 border border-zinc-800">
                  <div 
                    className="bg-gradient-to-r from-emerald-500 to-emerald-400 h-full rounded-full transition-all duration-500" 
                    style={{ width: `${data.recommendation_accuracy.score}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* B. Core Metrics Grid (4 columns) */}
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {/* KPI 1: Accuracy */}
            <div className="bg-zinc-900/25 border border-zinc-900 rounded-xl p-5 hover:border-zinc-800/80 transition-all duration-200 group flex flex-col justify-between space-y-4">
              <div className="flex items-center justify-between text-zinc-500">
                <span className="text-[10px] font-bold uppercase tracking-wider">Calibration Accuracy</span>
                <div className="p-1.5 bg-zinc-950 border border-zinc-900 rounded-lg group-hover:text-emerald-400 transition-colors">
                  <Target className="w-3.5 h-3.5" />
                </div>
              </div>
              <div>
                <p className="text-2xl font-bold text-white tracking-tight">
                  {data.recommendation_accuracy.score}%
                </p>
                <div className="text-[10px] text-zinc-400 mt-1 flex items-center justify-between font-mono">
                  <span>Override Rate:</span>
                  <span className="font-semibold text-zinc-300">{(data.recommendation_accuracy.override_rate * 100).toFixed(1)}%</span>
                </div>
              </div>
            </div>

            {/* KPI 2: Escaped Defects */}
            <div className="bg-zinc-900/25 border border-zinc-900 rounded-xl p-5 hover:border-zinc-800/80 transition-all duration-200 group flex flex-col justify-between space-y-4">
              <div className="flex items-center justify-between text-zinc-500">
                <span className="text-[10px] font-bold uppercase tracking-wider">Defect Slippage</span>
                <div className="p-1.5 bg-zinc-950 border border-zinc-900 rounded-lg group-hover:text-rose-400 transition-colors">
                  <ShieldAlert className="w-3.5 h-3.5" />
                </div>
              </div>
              <div>
                <div className="flex items-baseline gap-1.5">
                  <p className="text-2xl font-bold text-white tracking-tight">
                    {data.escaped_defects.count}
                  </p>
                  {data.escaped_defects.count > 0 && (
                    <span className="text-[10px] font-semibold text-rose-400">Leaked</span>
                  )}
                </div>
                <div className="text-[10px] text-zinc-400 mt-1 flex items-center justify-between font-mono">
                  <span>Rollback Rate:</span>
                  <span className="font-semibold text-zinc-300">{(data.escaped_defects.rollback_rate * 100).toFixed(1)}%</span>
                </div>
              </div>
            </div>

            {/* KPI 3: Runtime Saved */}
            <div className="bg-zinc-900/25 border border-zinc-900 rounded-xl p-5 hover:border-zinc-800/80 transition-all duration-200 group flex flex-col justify-between space-y-4">
              <div className="flex items-center justify-between text-zinc-500">
                <span className="text-[10px] font-bold uppercase tracking-wider">CI Runtime Saved</span>
                <div className="p-1.5 bg-zinc-950 border border-zinc-900 rounded-lg group-hover:text-amber-400 transition-colors">
                  <Zap className="w-3.5 h-3.5" />
                </div>
              </div>
              <div>
                <p className="text-2xl font-bold text-white tracking-tight">
                  {data.runtime_saved.formatted}
                </p>
                <div className="text-[10px] text-zinc-400 mt-1 flex items-center justify-between font-mono">
                  <span>Runs Optimized:</span>
                  <span className="font-semibold text-zinc-300">{data.runtime_saved.run_count} runs</span>
                </div>
              </div>
            </div>

            {/* KPI 4: Coverage Health */}
            <div className="bg-zinc-900/25 border border-zinc-900 rounded-xl p-5 hover:border-zinc-800/80 transition-all duration-200 group flex flex-col justify-between space-y-4">
              <div className="flex items-center justify-between text-zinc-500">
                <span className="text-[10px] font-bold uppercase tracking-wider">Coverage Health</span>
                <div className="p-1.5 bg-zinc-950 border border-zinc-900 rounded-lg group-hover:text-sky-400 transition-colors">
                  <Activity className="w-3.5 h-3.5" />
                </div>
              </div>
              <div className="space-y-2">
                {/* Horizontal Segmented Bar */}
                <div className="flex h-2.5 w-full bg-zinc-950 rounded-full overflow-hidden border border-zinc-900">
                  {data.coverage_health.map((item) => {
                    if (item.count === 0) return null;
                    const colors: Record<string, string> = {
                      HIGH: "bg-emerald-500",
                      MODERATE: "bg-amber-500",
                      LOW: "bg-rose-500",
                      UNKNOWN: "bg-zinc-600",
                    };
                    return (
                      <div
                        key={item.quality}
                        className={colors[item.quality] || "bg-zinc-600"}
                        style={{ width: `${item.percentage}%` }}
                        title={`${item.quality}: ${item.count} (${item.percentage}%)`}
                      />
                    );
                  })}
                </div>
                {/* Mini Legends */}
                <div className="flex justify-between text-[9px] text-zinc-500 font-semibold font-mono">
                  {data.coverage_health.slice(0, 3).map((item) => {
                    const labelColor: Record<string, string> = {
                      HIGH: "text-emerald-500",
                      MODERATE: "text-amber-500",
                      LOW: "text-rose-500",
                    };
                    return (
                      <span key={item.quality} className={labelColor[item.quality]}>
                        {item.percentage}% {item.quality[0]}
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* C. Secondary Detail Grids */}
          <div className="grid lg:grid-cols-2 gap-6">
            {/* Component 1: Top Risk Domains */}
            <div className="bg-zinc-950 border border-zinc-900 rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-zinc-500" />
                  Top Risk Domains
                </h3>
                <span className="text-[10px] text-zinc-500 font-semibold">Active Pulses</span>
              </div>
              
              {data.top_risk_domains.length === 0 ? (
                <div className="py-8 text-center text-xs text-zinc-600 font-medium">
                  No risk domains registered in lookback window.
                </div>
              ) : (
                <div className="divide-y divide-zinc-900">
                  {data.top_risk_domains.map((item) => {
                    const riskCls: Record<string, string> = {
                      HIGH: "bg-rose-500/10 text-rose-400 border-rose-500/20",
                      MODERATE: "bg-amber-500/10 text-amber-400 border-amber-500/20",
                      LOW: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
                    };
                    return (
                      <div key={item.domain} className="flex items-center justify-between py-2.5">
                        <span className="text-xs font-semibold text-zinc-300 truncate max-w-[200px]">
                          {item.domain}
                        </span>
                        <div className="flex items-center gap-3">
                          <span className={`text-[9px] px-2 py-0.5 rounded font-bold border ${riskCls[item.risk_level] || riskCls.LOW}`}>
                            {item.risk_level}
                          </span>
                          <span className="text-xs font-mono font-semibold text-zinc-500 w-16 text-right">
                            {item.occurrence_count} runs
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Component 2: Most Fragile Modules */}
            <div className="bg-zinc-950 border border-zinc-900 rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Activity className="w-4 h-4 text-zinc-500" />
                  Most Fragile Modules
                </h3>
                <span className="text-[10px] text-zinc-500 font-semibold">Calibration Alert</span>
              </div>

              {data.most_fragile_modules.length === 0 ? (
                <div className="py-8 text-center text-xs text-zinc-600 font-medium">
                  No fragile modules detected in lookback window.
                </div>
              ) : (
                <div className="space-y-4">
                  {data.most_fragile_modules.map((item) => (
                    <div key={item.file_path} className="space-y-1.5">
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-semibold text-zinc-300 truncate max-w-[280px]" title={item.file_path}>
                          {item.file_path.split("/").pop()}
                        </span>
                        <span className="font-mono text-zinc-400 font-semibold text-[10px]">
                          Fragility: {(item.fragility_score * 100).toFixed(0)}% ({item.failure_count} failures)
                        </span>
                      </div>
                      
                      {/* Fragility score progress bar */}
                      <div className="w-full bg-zinc-900 h-1.5 rounded-full overflow-hidden border border-zinc-900/50">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${
                            item.fragility_score > 0.6
                              ? "bg-rose-500"
                              : item.fragility_score > 0.3
                              ? "bg-amber-500"
                              : "bg-sky-500"
                          }`}
                          style={{ width: `${item.fragility_score * 100}%` }}
                        />
                      </div>
                      
                      <div className="text-[10px] text-zinc-500 italic truncate font-medium">
                        Rec: {item.recommendation}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Component 3: Most Valuable Tests (Core Stabilizers) */}
            <div className="bg-zinc-950 border border-zinc-900 rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Target className="w-4 h-4 text-zinc-500" />
                  Most Valuable Tests (Core Stabilizers)
                </h3>
                <span className="text-[10px] text-zinc-500 font-semibold">Priority &gt;= 80%</span>
              </div>

              {data.most_valuable_tests.length === 0 ? (
                <div className="py-8 text-center text-xs text-zinc-600 font-medium">
                  No high-priority suite executions recorded in this window.
                </div>
              ) : (
                <div className="divide-y divide-zinc-900 max-h-72 overflow-y-auto pr-1">
                  {data.most_valuable_tests.map((item) => (
                    <div key={item.stable_identity} className="flex items-center justify-between py-2.5">
                      <div className="flex items-center gap-2 min-w-0 pr-4">
                        <FileCode2 className="w-3.5 h-3.5 text-zinc-600 shrink-0" />
                        <span className="text-xs font-semibold text-zinc-300 truncate" title={item.stable_identity}>
                          {item.display_name}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-[10px] font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/10">
                          P: {(item.priority_score * 100).toFixed(0)}%
                        </span>
                        <span className="text-xs font-mono font-semibold text-zinc-500 w-16 text-right">
                          {item.run_count} runs
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Component 4: Developer Calibrators (Manually Overridden/Added Tests) */}
            <div className="bg-zinc-950 border border-zinc-900 rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-zinc-500" />
                  Developer Calibrators (Overrides)
                </h3>
                <span className="text-[10px] text-zinc-500 font-semibold">Top Added back</span>
              </div>

              {data.most_added_tests.length === 0 ? (
                <div className="py-8 text-center text-xs text-zinc-600 font-medium">
                  No developer manual overrides logged in this window.
                </div>
              ) : (
                <div className="divide-y divide-zinc-900 max-h-72 overflow-y-auto pr-1">
                  {data.most_added_tests.map((item) => (
                    <div key={item.test_case_id} className="flex items-center justify-between py-2.5">
                      <div className="flex items-center gap-2 min-w-0 pr-4">
                        <Sliders className="w-3.5 h-3.5 text-zinc-600 shrink-0" />
                        <span className="text-xs font-semibold text-zinc-300 truncate" title={item.test_case_id}>
                          {item.display_name}
                        </span>
                      </div>
                      <span className="text-xs font-mono font-bold text-amber-400 bg-amber-500/10 px-2.5 py-0.5 rounded border border-amber-500/10 shrink-0">
                        {item.manual_addition_count} adds
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

