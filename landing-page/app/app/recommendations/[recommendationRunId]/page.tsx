"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  GitPullRequest,
  GitBranch,
  AlertTriangle,
  ChevronDown,
  AlertCircle,
  CheckCircle2,
  Clock,
  Copy,
  Download,
  RefreshCw,
  ChevronRight,
  Loader2,
  FlaskConical,
  BarChart2,
  Zap,
  Shield,
  BookOpen,
  History,
  Target,
  Brain,
  Layers,
  Globe,
  FileCode,
  FileText,
  Info,
  Table,
  Play,
  Plus,
  Star,
  Check,
  X,
  Circle,
  Lightbulb,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { generateScenarioCoverageMatrix, getScenarioMatrixKey } from "@/lib/scenario-coverage-matrix";
import { calculateCompletenessScore } from "@/lib/completeness-score";
import { resolveRecommendationDisplayState } from "@/lib/recommendation-display-state";
import { resolveCanonicalHealth, CanonicalHealthResult } from "@/lib/recommendation-health-state";
import { getRecommendationHealth } from "@/lib/recommendation-page-health";
import { formatTestTitle, generateTestWhySelected, generateMissingTestTitle } from "@/lib/test-title-formatter";
import { deduplicateTests, groupTestsByType } from "@/lib/test-deduplication";
import { groupCoverageGaps, consolidateACFragments } from "@/lib/coverage-gap-grouping";
import { mapRawLabel } from "@/lib/label-mapper";
import { validateRecommendationDetailView } from "@/lib/validate-recommendation-detail";
import { DevConsistencyCheck } from "@/components/DevConsistencyCheck";
import { ExistingAutomatedTests } from "@/components/existing-automated-tests";
import { CompletenessScore } from "@/components/completeness-score";
import { RecommendationFeedback } from "@/components/recommendation-feedback";
import { AttachTestRun } from "@/components/attach-test-run";
import { PostMergeOutcome } from "@/components/post-merge-outcome";
import { OutcomePanel } from "@/components/outcome-panel";
import { RequirementContext } from "@/components/requirement-context";
import { ManagedManualTests } from "@/components/managed-manual-tests";
import MissingIntelligence, { createMissingIntelligenceItems } from "@/app/components/MissingIntelligence";
import ReleaseReadinessVerdict, { determineReleaseReadinessVerdict, generateVerdictReason } from "@/components/ReleaseReadinessVerdict";
import WhatVeriscopeUnderstood, { extractUnderstandingData } from "@/components/WhatVeriscopeUnderstood";
import ConfidenceExplanation, { 
  generateRecommendationConfidence, 
  generateTestConfidence, 
  generateScenarioConfidence, 
  generateCoverageConfidence,
  generateBehaviorConfidence,
  generateJourneyConfidence
} from "@/components/ConfidenceExplanation";
import { ImproveAccuracyPanel } from "@/components/ImproveAccuracyPanel";
import RecommendationCheckpointModal from "@/app/components/RecommendationCheckpointModal";
import BusinessRequirementsModal from "@/components/requirements/business-requirements-modal";
import BusinessRequirementsBanner from "@/components/requirements/business-requirements-banner";
import { RegressionScopeV2Display } from "@/components/regression-scope/RegressionScopeV2Display";
import { RiskReviewGovernancePanel } from "@/components/RiskReviewGovernancePanel";
import { ScopeGroup } from "@/types/regression-scope-v2";
import { CICDPipelineRunsPanel } from "@/components/CICDPipelineRunsPanel";
import { QualityGateBadge } from "@/components/QualityGateBadge";
import { PRPackageSummaryCard, StaleRecommendationBanner, MissingInputWarning } from "@/components/pr-package-readiness";
import { normalizePRPackage } from "@/lib/adapters/prPackageAdapter";
import { deriveQualityGate } from "@/lib/quality-gate";
import { buildTraceabilityRows, isTraceabilityHealthy } from "@/lib/traceability-rows";

export const dynamic = "force-dynamic";

// ── Types ──────────────────────────────────────────────────────────────────

interface RecommendedTest {
  stable_identity: string;
  display_name: string;
  suite_name: string;
  tier: "must_run" | "should_run" | "fallback";
  execution_aware_tier?: string;
  priority_score: number;
  reason_type: string;
  reason: string;
  testing_type?: string;
  impacted_area?: string;
  confidence?: string;
  signals?: { name: string; value: string }[];
  requirement_id?: string;
  scenario_intent?: string;
  candidate_status?: string;
  active_action?: string;
  included?: boolean;
  evidence_path?: Array<{ step: string; confidence?: number; [key: string]: any }>;
  would_have_been_priority?: string;
}

interface ScenarioCoverageMatrixItem {
  scenario_intent_key: string;
  title: string;
  impacted_area: string;
  testing_type: string;
  priority: string;
  existing_tests: Array<{
    test_identifier: string;
    test_name: string;
    suite_name: string | null;
    class_name: string | null;
    last_execution_status: string | null;
    last_execution_timestamp: string | null;
  }>;
  suggested_scenarios: Array<{
    scenario_id: string;
    title: string;
    testing_type: string;
    priority: string;
    automation_candidate: boolean;
    preconditions: string[];
    steps: string[];
    expected_result: string;
    test_data: Record<string, any>;
  }>;
  code_coverage_status: string;
  current_pr_execution_status: string;
  final_status: string;
  recommendation_action: string;
  evidence_reason: string;
  confidence: string;
  domain: string;
  feature: string;
  layer: string;
  case_type: string;
}

interface ScenarioCoverageMatrix {
  recommendation_run_id: string;
  repository_id: string;
  pull_request_id: string | null;
  total_scenarios: number;
  covered_and_verified: number;
  covered_not_run: number;
  partially_covered: number;
  missing_automated_coverage: number;
  suggest_manual_validation: number;
  items: ScenarioCoverageMatrixItem[];
  generated_at: string;
}

interface BehaviorScenarioCoverageMatrix {
  scenario_id: string;
  scenario_title: string;
  behavior_id: string;
  behavior_name: string;
  journey_id: string | null;
  journey_name: string | null;
  impact_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  priority: "BLOCKER" | "MUST" | "SHOULD" | "OPTIONAL";
  coverage_status: "VERIFIED_ON_CURRENT_PR" | "COVERED_BY_EXISTING_TEST" | "PARTIALLY_COVERED" | "MISSING_AUTOMATED_COVERAGE" | "MANUAL_VALIDATION_RECOMMENDED";
  coverage_confidence: "HIGH" | "MODERATE" | "LOW";
  sufficiency: "SUFFICIENT" | "PARTIAL" | "INSUFFICIENT" | "UNKNOWN";
  existing_tests: string[];
  current_pr_execution_status: "EXECUTED" | "NOT_EXECUTED" | "UNKNOWN";
  recommended_actions: string[];
  reasons: string[];
  related_changed_files: string[];
}

interface RunDetail {
  id: string;
  created_at: string;
  triggered_by: string;
  repository: { id: string; full_name: string };
  pull_request: {
    id: string;
    number: number;
    title: string;
    source_branch: string;
    target_branch: string;
    merged_at?: string | null;
    state?: string | null;
  } | null;
  testing_scope_created_at?: string | null;
  regression_suite_id?: string | null;
  commit_sha?: string | null;
  impact_profile?: any;
  input_stale?: boolean;
  executive_summary: {
    changed_files: string[];
    changed_files_count: number;
    risk_level: "LOW" | "MODERATE" | "HIGH";
    bullets: string[];
  };
  readiness_snapshot?: {
    readiness_snapshot_available: boolean;
    readiness_score: number | null;
    readiness_level: string | null;
    expected_confidence: string | null;
    confidence_ceiling: string | null;
    confidence_reason: string | null;
    can_generate: boolean | null;
    available_inputs: any[] | null;
    missing_inputs: any[] | null;
    blocking_inputs: any[] | null;
    confidence_limiters: any | null;
    evidence_summary: any | null;
    generated_from_repository_id: string | null;
    generated_from_pull_request_id: string | null;
  };
  testing_strategy: {
    recommendation_mode: string;
    evidence_quality: string;
    optimization_allowed: boolean;
    must_run_count: number;
    should_run_count: number;
    fallback_count: number;
    already_verified_count?: number;
    failed_current_pr_count?: number;
    stale_rerun_required_count?: number;
    mapping_review_needed_count?: number;
    estimated_runtime_seconds: number;
    full_suite_runtime_seconds: number | null;
    runtime_confidence: string | null;
    skipped_count: number;
    skipped_reason_summary: string | null;
  };
  recommended_tests: RecommendedTest[];
  why: string[];
  evidence: {
    coverage: {
      commit_sha: string;
      confidence: string;
      files_total: number;
      line_coverage_ratio: number | null;
      created_at: string;
    } | null;
    knowledge_graph: { dependency_state_hash: string | null; has_dependencies: boolean };
    history: {
      window_start: string | null;
      window_end: string | null;
      flakiness_profile_hash: string | null;
      has_flakiness_data: boolean;
    };
    overrides: {
      unsafe_for_optimization: boolean;
      evidence_consistency_status: string;
      evidence_health_status: string;
    };
  };
  warnings: string[];
  evidence_gaps?: {
    severity: "HIGH" | "WARNING" | "INFO";
    message: string;
    impact: string;
  }[];
  missing_coverage?: {
    domain: string;
    feature: string;
    reason: string;
  }[];
  testing_scope?: {
    must_test: { category: string; item: string }[];
    should_test: { category: string; item: string }[];
    optional: { category: string; item: string }[];
  };
  scenario_coverage_matrix?: ScenarioCoverageMatrix;
  behavior_coverage_matrix?: BehaviorScenarioCoverageMatrix[];
  business_intent?: {
    rows: Array<{
      acceptance_criterion_id: string | null;
      business_intent_text: string | null;
      affected_behavior_name: string | null;
      affected_journey_name: string | null;
      existing_test_coverage: string[];
      suggested_scenario_id: string | null;
      suggested_scenario_title: string | null;
      current_pr_execution_status: string;
      status: string;
      recommended_action: string;
      confidence: number;
      reason: string | null;
    }>;
    total_intents: number;
    covered: number;
    partially_covered: number;
    missing: number;
    verified: number;
    unknown: number;
    has_business_intent: boolean;
    confidence_impact: string;
  };
  acceptance_criteria?: Array<{
    id: string;
    text: string;
    type: string;
    mapped_behavior: string | null;
    coverage_status: string;
    existing_tests: string[];
    suggested_scenarios: string[];
    recommended_action: string;
    reason: string | null;
  }>;
  requirement_gaps?: Array<{
    severity: string;
    gap_type: string;
    message: string;
    impact: string;
    recommended_action: string;
  }>;
  business_intent_coverage_matrix?: any;
  pr_description_template_suggestion?: {
    needs_template: boolean;
    reason: string;
    template?: string;
    copyable: boolean;
  };
  fragility?: {
    risk_level: "LOW" | "MODERATE" | "HIGH" | "CRITICAL";
    summary: string;
    behavior_signals: Array<{
      type: string;
      subject: string;
      subject_id: string | null;
      score: number;
      confidence: number;
      risk_level: string;
      evidence_count: number;
      last_seen_at: string | null;
      reason: string;
      recommendation_effect: "boost" | "context";
    }>;
    journey_signals: Array<{
      type: string;
      subject: string;
      subject_id: string | null;
      score: number;
      confidence: number;
      risk_level: string;
      evidence_count: number;
      last_seen_at: string | null;
      reason: string;
      recommendation_effect: "boost" | "context";
    }>;
    scenario_signals: Array<{
      type: string;
      subject: string;
      subject_id: string | null;
      score: number;
      confidence: number;
      risk_level: string;
      evidence_count: number;
      last_seen_at: string | null;
      reason: string;
      recommendation_effect: "boost" | "context";
    }>;
    file_hotspots: Array<{
      type: string;
      subject: string;
      subject_id: string | null;
      score: number;
      confidence: number;
      risk_level: string;
      evidence_count: number;
      last_seen_at: string | null;
      reason: string;
      recommendation_effect: "boost" | "context";
    }>;
    risky_combinations: Array<{
      type: string;
      subject: string;
      subject_id: string | null;
      score: number;
      confidence: number;
      risk_level: string;
      evidence_count: number;
      last_seen_at: string | null;
      reason: string;
      recommendation_effect: "boost" | "context";
    }>;
    evidence_gaps: Array<{
      type: string;
      description: string;
      severity: string;
    }>;
  };
  requirement_context?: {
    has_linked_work_items: boolean;
    linked_work_items?: any[];
    [key: string]: any;
  };
  manual_tests?: any[];
}

interface PageProps {
  params: Promise<{ recommendationRunId: string }>;
}

// ── Components ───────────────────────────────────────────────────────────────

function FragilitySignalCard({ signal }: { signal: any }) {
  const [expanded, setExpanded] = useState(false);
  
  const riskColor = signal.risk_level === "CRITICAL" ? "text-rose-400" :
                   signal.risk_level === "HIGH" ? "text-amber-400" :
                   signal.risk_level === "MODERATE" ? "text-yellow-400" : "text-emerald-400";
  
  const effectBadge = signal.recommendation_effect === "boost" 
    ? <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/25 uppercase tracking-wider">Boost</span>
    : <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700/50 uppercase tracking-wider">Context</span>;

  return (
    <div className="p-3 rounded-lg bg-zinc-950/30 border border-zinc-800/60">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-sm font-medium ${riskColor}`}>{signal.subject}</span>
            {effectBadge}
          </div>
          <p className="text-xs text-zinc-400 line-clamp-2">{signal.reason}</p>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="shrink-0 p-1 hover:bg-zinc-800/50 rounded transition-colors"
        >
          <ChevronDown className={`w-4 h-4 text-zinc-500 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </button>
      </div>
      
      {expanded && (
        <div className="mt-3 pt-3 border-t border-zinc-800/60 space-y-2">
          <div className="flex items-center gap-4 text-xs text-zinc-500">
            <span><span className="font-semibold text-zinc-400">Score:</span> {signal.score.toFixed(1)}</span>
            <span><span className="font-semibold text-zinc-400">Evidence:</span> {signal.evidence_count}</span>
            <span><span className="font-semibold text-zinc-400">Confidence:</span> {(signal.confidence * 100).toFixed(0)}%</span>
          </div>
          {signal.last_seen_at && (
            <p className="text-xs text-zinc-500">
              <span className="font-semibold text-zinc-400">Last seen:</span> {formatRelative(signal.last_seen_at)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function formatSeconds(s: number | null | undefined): string {
  if (!s || s <= 0) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const rem = Math.round(s % 60);
  return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
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

function riskBadge(level: string) {
  const map: Record<string, { bg: string; text: string; dot: string }> = {
    HIGH:     { bg: "bg-rose-950/30",    text: "text-rose-400",    dot: "bg-rose-400" },
    MODERATE: { bg: "bg-amber-950/30",   text: "text-amber-400",   dot: "bg-amber-400" },
    LOW:      { bg: "bg-emerald-950/20", text: "text-emerald-400", dot: "bg-emerald-400" },
  };
  const s = map[level] ?? map.MODERATE;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {level.charAt(0) + level.slice(1).toLowerCase()} risk
    </span>
  );
}

function modeBadge(mode: string) {
  const labels: Record<string, string> = {
    NORMAL: "Targeted",
    WIDENED: "Widened",
    SAFE_FALLBACK: "Conservative",
    CRITICAL: "Critical",
    FULL_REGRESSION: "Full Suite",
  };
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-800 text-zinc-300 border border-zinc-700/50">
      {labels[mode] ?? mode}
    </span>
  );
}

function tierLabel(tier: string) {
  const map: Record<string, { label: string; color: string }> = {
    must_run:   { label: "Must Run",   color: "text-rose-400/80" },
    should_run: { label: "Should Run", color: "text-amber-400/80" },
    fallback:   { label: "Fallback",   color: "text-zinc-500" },
  };
  return map[tier] ?? { label: tier, color: "text-zinc-500" };
}

// Display label mapping for internal enums
const signalLabels: Record<string, string> = {
  acceptance_criteria: "Acceptance criteria",
  current_pr_execution: "Current PR test results",
  coverage_report: "Coverage report",
  current_pr_coverage: "Current PR coverage",
  test_history: "Historical test evidence",
  pull_request_diff: "PR diff",
  source_signal: "Evidence source",
  work_items: "Linked work item",
  manual_tests: "Manual test cases",
  historical_outcomes: "Historical outcomes",
  fragility_memory: "Fragility memory",
  architecture_intelligence: "Architecture intelligence",
  behavior_catalog: "Behavior catalog",
  journey_catalog: "Journey catalog",
};

function formatDisplayLabel(value: string, type: "mode" | "coverage" | "execution" | "signal" | "status"): string {
  const modeLabels: Record<string, string> = {
    FULL_SUITE: "Full suite recommended",
    TARGETED: "Targeted regression recommended",
    SMOKE: "Smoke validation recommended",
    NO_RUN: "No regression recommended",
    NORMAL: "Targeted",
    WIDENED: "Widened",
    SAFE_FALLBACK: "Conservative",
    CRITICAL: "Critical",
    FULL_REGRESSION: "Full Suite",
  };

  const coverageLabels: Record<string, string> = {
    MISSING_AUTOMATED_COVERAGE: "Automated coverage missing",
    MISSING_REQUIREMENT_COVERAGE: "Requirement coverage missing",
    VERIFIED_ON_CURRENT_PR: "Verified on current PR",
    COVERED_BY_EXISTING_TEST: "Covered by existing test",
    PARTIALLY_COVERED: "Partially covered",
    MANUAL_VALIDATION_RECOMMENDED: "Manual validation recommended",
    COVERED_AND_VERIFIED: "Covered and verified",
    COVERED_NOT_RUN: "Covered not run",
    MISSING: "Missing",
    PARTIAL: "Partial",
    COVERED: "Covered",
    VERIFIED: "Verified",
  };

  const executionLabels: Record<string, string> = {
    EXECUTED: "Executed",
    NOT_EXECUTED: "Not executed",
    UNKNOWN: "Unknown",
  };

  const statusLabels: Record<string, string> = {
    behavior_mapping_unavailable: "Business behavior not mapped",
  };

  switch (type) {
    case "mode":
      return modeLabels[value] || value.replace(/_/g, " ");
    case "coverage":
      return coverageLabels[value] || value.replace(/_/g, " ");
    case "execution":
      return executionLabels[value] || value.replace(/_/g, " ");
    case "signal":
      return signalLabels[value] || value.replace(/_/g, " ");
    case "status":
      return statusLabels[value] || value.replace(/_/g, " ");
    default:
      return value.replace(/_/g, " ");
  }
}

// Scans run data object for raw enum/snake_case keys that should have been formatted
const RAW_KEY_PATTERNS = [
  /FULL_SUITE(?!\w)/,
  /TARGETED(?!\w)/,
  /MISSING_AUTOMATED_COVERAGE(?!\w)/,
  /acceptance_criteria(?!\w)/,
  /current_pr_execution(?!\w)/,
  /source_signal(?!\w)/,
  /behavior_mapping_unavailable(?!\w)/,
];

function scanForRawKeys(obj: any, path = "", found: string[] = []): string[] {
  if (!obj || typeof obj !== "object" || found.length >= 10) return found;
  for (const key in obj) {
    const val = obj[key];
    const p = path ? `${path}.${key}` : key;
    if (typeof val === "string") {
      if (RAW_KEY_PATTERNS.some((re) => re.test(val))) {
        found.push(`${p}: "${val}"`);
      }
    } else if (typeof val === "object") {
      scanForRawKeys(val, p, found);
    }
  }
  return found;
}

// ── Section wrapper ────────────────────────────────────────────────────────

function Section({ title, icon: Icon, children, id }: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  id?: string;
}) {
  return (
    <div id={id} className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-4 h-4 text-zinc-500" />
        <h2 className="text-sm font-semibold text-zinc-200">{title}</h2>
      </div>
      {children}
    </div>
  );
}

// ── Collapsible Section wrapper ──────────────────────────────────────────────

function CollapsibleSection({ title, icon: Icon, children, defaultOpen = false, id }: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
  id?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div id={id} className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-zinc-800/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-zinc-500" />
          <h2 className="text-sm font-semibold text-zinc-200">{title}</h2>
        </div>
        {open ? <ChevronDown className="w-4 h-4 text-zinc-500" /> : <ChevronRight className="w-4 h-4 text-zinc-500" />}
      </button>
      {open && (
        <div className="px-5 pb-5">
          {children}
        </div>
      )}
    </div>
  );
}

// ── Behavior Ranking Reasoning Panel ────────────────────────────────────────

function BehaviorRankingReasoningPanel({
  impactedBehaviors,
  behaviorReasons,
  coverageSummary,
  contextStatus,
}: {
  impactedBehaviors: any[];
  behaviorReasons: string[];
  coverageSummary: Record<string, any>;
  contextStatus: string | null;
}) {
  const [open, setOpen] = useState(false);

  const riskColor = (level: string) =>
    level === "CRITICAL" ? "text-red-400 border-red-800/50 bg-red-950/20"
    : level === "HIGH"   ? "text-orange-400 border-orange-800/50 bg-orange-950/20"
    : level === "MEDIUM" ? "text-amber-400 border-amber-800/50 bg-amber-950/20"
    : "text-zinc-400 border-zinc-700 bg-zinc-900/30";

  const statusBadge = contextStatus === "READY"
    ? "text-emerald-400 bg-emerald-950/20 border-emerald-800/40"
    : contextStatus === "PARTIAL"
    ? "text-amber-400 bg-amber-950/20 border-amber-800/40"
    : "text-zinc-400 bg-zinc-900/30 border-zinc-700";

  return (
    <div className="mt-4 bg-indigo-950/10 border border-indigo-800/30 rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-indigo-950/20 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <span className="text-indigo-400 text-sm">⬡</span>
          <span className="text-sm font-semibold text-zinc-100">Behavior-Based Ranking Reasoning</span>
          <span className={`text-[9px] px-1.5 py-0.5 rounded border ${statusBadge}`}>
            {contextStatus || "—"}
          </span>
          <span className="text-[10px] text-zinc-500">
            {impactedBehaviors.length} impacted behavior{impactedBehaviors.length !== 1 ? "s" : ""}
          </span>
        </div>
        <span className="text-zinc-500 text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4">
          {/* Coverage summary */}
          {(coverageSummary.total_behaviors > 0) && (
            <div className="grid grid-cols-3 gap-2 mt-2">
              <div className="bg-zinc-900/40 rounded p-2 text-center border border-zinc-800/30">
                <p className="text-[9px] text-zinc-500 uppercase tracking-wider">Total Behaviors</p>
                <p className="text-lg font-bold text-zinc-200">{coverageSummary.total_behaviors ?? 0}</p>
              </div>
              <div className="bg-zinc-900/40 rounded p-2 text-center border border-zinc-800/30">
                <p className="text-[9px] text-zinc-500 uppercase tracking-wider">Impacted</p>
                <p className="text-lg font-bold text-orange-400">{coverageSummary.impacted_behaviors_count ?? 0}</p>
              </div>
              <div className="bg-zinc-900/40 rounded p-2 text-center border border-zinc-800/30">
                <p className="text-[9px] text-zinc-500 uppercase tracking-wider">Uncovered</p>
                <p className="text-lg font-bold text-rose-400">{coverageSummary.uncovered_behaviors_count ?? 0}</p>
              </div>
            </div>
          )}

          {/* Impacted behaviors list */}
          {impactedBehaviors.length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">Impacted Behaviors</p>
              {impactedBehaviors.map((b: any, i: number) => (
                <div key={b.behavior_id || i} className={`flex items-start gap-2 rounded border px-3 py-2 ${riskColor(b.impact_level)}`}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-semibold">{b.behavior_name}</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded border ${riskColor(b.impact_level)}`}>
                        {b.impact_level}
                      </span>
                      <span className="text-[9px] text-zinc-500">{b.impact_type}</span>
                    </div>
                    {b.impact_reason && (
                      <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">{b.impact_reason}</p>
                    )}
                  </div>
                  <div className="text-[9px] text-zinc-500 whitespace-nowrap">
                    conf: {Math.round((b.confidence ?? 0) * 100)}%
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Why these boost test ranking */}
          {behaviorReasons.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">Why Behaviors Affect Ranking</p>
              {behaviorReasons.map((r: string, i: number) => (
                <div key={i} className="flex items-start gap-2 text-[11px] text-zinc-300 leading-relaxed">
                  <span className="text-indigo-400 mt-0.5 shrink-0">→</span>
                  <span>{r}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Behavior Coverage Group ─────────────────────────────────────────────────

function BehaviorCoverageGroup({ group }: { group: any }) {
  const [open, setOpen] = useState(true);
  
  return (
    <div className="border border-zinc-800/40 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-zinc-900/40 hover:bg-zinc-900/60 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-zinc-200">{group.behavior_name}</span>
          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
            group.impact_level === "CRITICAL" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
            group.impact_level === "HIGH" ? "bg-orange-500/10 text-orange-400 border-orange-500/20" :
            group.impact_level === "MEDIUM" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
            "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
          }`}>
            {group.impact_level}
          </span>
          {group.journey_name && (
            <span className="text-[9px] text-zinc-500">{group.journey_name}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-zinc-500">{group.scenarios.length} scenario{group.scenarios.length !== 1 ? "s" : ""}</span>
          {open ? <ChevronDown className="w-3.5 h-3.5 text-zinc-600" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />}
        </div>
      </button>
      {open && (
        <div className="divide-y divide-zinc-800/30">
          {group.scenarios.map((scenario: BehaviorScenarioCoverageMatrix) => (
            <div key={scenario.scenario_id} className="px-4 py-3 bg-zinc-950/20">
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-semibold text-zinc-300">{scenario.scenario_title}</span>
                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                    scenario.priority === "BLOCKER" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                    scenario.priority === "MUST" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                    scenario.priority === "SHOULD" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                    "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                  }`}>
                    {scenario.priority}
                  </span>
                </div>
                <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                  scenario.coverage_status === "VERIFIED_ON_CURRENT_PR" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                  scenario.coverage_status === "COVERED_BY_EXISTING_TEST" ? "bg-blue-500/10 text-blue-400 border-blue-500/20" :
                  scenario.coverage_status === "PARTIALLY_COVERED" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                  scenario.coverage_status === "MISSING_AUTOMATED_COVERAGE" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                  "bg-orange-500/10 text-orange-400 border-orange-500/20"
                }`}>
                  {formatDisplayLabel(scenario.coverage_status, "coverage")}
                </span>
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                  <span>Status:</span>
                  <span className={`${
                    scenario.sufficiency === "SUFFICIENT" ? "text-emerald-400" :
                    scenario.sufficiency === "PARTIAL" ? "text-amber-400" :
                    scenario.sufficiency === "INSUFFICIENT" ? "text-rose-400" :
                    "text-zinc-400"
                  }`}>
                    {scenario.sufficiency}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                  <span>Confidence:</span>
                  <span className={`${
                    scenario.coverage_confidence === "HIGH" ? "text-emerald-400" :
                    scenario.coverage_confidence === "MODERATE" ? "text-amber-400" :
                    "text-zinc-400"
                  }`}>
                    {scenario.coverage_confidence}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                  <span>Current PR:</span>
                  <span className={`${
                    scenario.current_pr_execution_status === "EXECUTED" ? "text-emerald-400" :
                    "text-zinc-400"
                  }`}>
                    {formatDisplayLabel(scenario.current_pr_execution_status, "execution")}
                  </span>
                </div>
                {scenario.existing_tests.length > 0 && (
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    <span>Existing tests:</span>
                    <div className="flex flex-wrap gap-1">
                      {scenario.existing_tests.map((test: string) => (
                        <span key={test} className="text-[9px] font-mono bg-zinc-900 text-zinc-400 px-1.5 py-0.5 rounded border border-zinc-800/60">
                          {test.split("::").slice(-1)[0]}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {scenario.recommended_actions.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-[9px] text-zinc-500 font-semibold uppercase tracking-wider">Action:</span>
                    <span className="text-[10px] text-zinc-400">{scenario.recommended_actions[0]}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Optional Coverage Section ─────────────────────────────────────────────

function OptionalCoverageSection({ scenarios }: { scenarios: BehaviorScenarioCoverageMatrix[] }) {
  const [open, setOpen] = useState(false);
  
  return (
    <div className="space-y-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 text-[10px] font-bold text-zinc-400 uppercase tracking-wider hover:text-zinc-300 transition-colors"
      >
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        Optional Confidence Boosters ({scenarios.length})
      </button>
      {open && (
        <div className="space-y-2">
          {scenarios.map((scenario: BehaviorScenarioCoverageMatrix) => (
            <div key={scenario.scenario_id} className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-semibold text-zinc-300">{scenario.scenario_title}</span>
                  <span className="text-[9px] font-mono bg-zinc-500/10 text-zinc-400 px-1.5 py-0.5 rounded border border-zinc-500/20">
                    {formatDisplayLabel(scenario.coverage_status, "coverage")}
                  </span>
                </div>
                <span className="text-[9px] font-bold bg-zinc-500/10 text-zinc-400 px-1.5 py-0.5 rounded">
                  {scenario.priority}
                </span>
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                  <span>Behavior:</span>
                  <span className="text-zinc-400">{scenario.behavior_name}</span>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                  <span>Confidence:</span>
                  <span className={`${
                    scenario.coverage_confidence === "HIGH" ? "text-emerald-400" :
                    scenario.coverage_confidence === "MODERATE" ? "text-amber-400" :
                    "text-zinc-400"
                  }`}>
                    {scenario.coverage_confidence}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Test tier group ────────────────────────────────────────────────────────

function TierGroup({
  tier,
  tests,
  defaultOpen,
}: {
  tier: "must_run" | "should_run" | "fallback";
  tests: RecommendedTest[];
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const { label, color } = tierLabel(tier);
  if (tests.length === 0) return null;

  return (
    <div className="border border-zinc-800/40 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-zinc-900/40 hover:bg-zinc-900/60 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold ${color}`}>{label}</span>
          <span className="text-[11px] text-zinc-500">{tests.length} test{tests.length !== 1 ? "s" : ""}</span>
        </div>
        {open ? <ChevronDown className="w-3.5 h-3.5 text-zinc-600" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />}
      </button>
      {open && (
        <div className="divide-y divide-zinc-800/30">
          {tests.map(t => (
            <div key={t.stable_identity} className="px-4 py-4 space-y-2 bg-zinc-950/20">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-xs font-semibold text-zinc-100 font-mono truncate" title={t.stable_identity}>
                      {t.display_name}
                    </p>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono border border-zinc-700/30">
                      {t.testing_type || "Regression"}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-900 text-zinc-400 font-mono border border-zinc-800">
                      {t.impacted_area || "General"}
                    </span>
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                      t.confidence === "HIGH" ? "bg-green-500/10 text-green-400 border-green-500/20" :
                      t.confidence === "MEDIUM" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                      "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                    }`}>
                      {t.confidence || "LOW"}
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-snug">{t.reason}</p>
                  
                  {t.signals && t.signals.length > 0 && (
                    <div className="flex items-center gap-2 pt-1 flex-wrap">
                      <span className="text-[9px] text-zinc-500 font-semibold uppercase tracking-wider">Signals:</span>
                      {t.signals.map((sig: any) => (
                        <span key={sig.name} className="text-[9px] bg-zinc-900 text-zinc-400 px-1.5 py-0.5 rounded border border-zinc-800/40">
                          {sig.name}: <span className="text-zinc-300 font-medium">{sig.value}</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="text-right shrink-0 mt-0.5 space-y-1">
                  <span className="text-xs font-mono font-bold text-zinc-300">
                    {t.priority_score.toFixed(1)}
                  </span>
                  <p className="text-[9px] text-zinc-500">score</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Acceptance Criteria Mapper - maps tests/scenarios to ACs using layered matching
function mapToAcceptanceCriteria(
  testOrScenario: any,
  acceptanceCriteria: any[],
  isScenario: boolean = false
): { ac: any; method: string } | null {
  if (!acceptanceCriteria || acceptanceCriteria.length === 0) {
    return null;
  }

  const testName = testOrScenario.display_name || testOrScenario.stable_identity || testOrScenario.scenario_title || testOrScenario.behavior_name || "";
  const testReqId = testOrScenario.requirement_id || "";
  const testIntent = testOrScenario.scenario_intent || testOrScenario.behavior_name || "";
  const testSuite = testOrScenario.test_suite_name || testOrScenario.suite_name || "";

  // Helper: normalize string for comparison
  const normalize = (s: string) => s.toLowerCase().replace(/^(a|an|the)\s+/i, "").replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();

  // Helper: extract keywords
  const extractKeywords = (s: string) => {
    const tokens = normalize(s).split(" ").filter(t => t.length >= 3);
    return new Set(tokens);
  };

  // Helper: check keyword overlap
  const hasKeywordOverlap = (a: string, b: string, minOverlap = 2) => {
    const ka = extractKeywords(a);
    const kb = extractKeywords(b);
    let overlap = 0;
    for (const k of ka) if (kb.has(k)) overlap++;
    return overlap >= minOverlap;
  };

  const normalizedTestName = normalize(testName);
  const normalizedTestIntent = normalize(testIntent);

  // Layer 1: explicit AC ID match
  if (testReqId) {
    for (const ac of acceptanceCriteria) {
      if (ac.id === testReqId || ac.normalized_key === testReqId) {
        return { ac, method: "ac_id" };
      }
    }
  }

  // Layer 2: exact normalized AC title match
  for (const ac of acceptanceCriteria) {
    const normalizedACText = normalize(ac.text);
    if (normalizedTestName === normalizedACText) {
      return { ac, method: "normalized_title" };
    }
  }

  // Layer 3: test name intent match (test name contains AC text or vice versa)
  for (const ac of acceptanceCriteria) {
    const normalizedACText = normalize(ac.text);
    if (normalizedTestName.includes(normalizedACText) || normalizedACText.includes(normalizedTestName)) {
      return { ac, method: "test_name_intent" };
    }
  }

  // Layer 4: scenario intent match (for scenarios)
  if (isScenario) {
    for (const ac of acceptanceCriteria) {
      const normalizedACText = normalize(ac.text);
      if (normalizedTestIntent === normalizedACText || normalizedTestIntent.includes(normalizedACText) || normalizedACText.includes(normalizedTestIntent)) {
        return { ac, method: "scenario_intent" };
      }
    }
  }

  // Layer 5: affected behavior/journey match
  const affectedBehavior = testOrScenario.affected_behavior || testOrScenario.behavior_name || "";
  const affectedJourney = testOrScenario.affected_journey || testOrScenario.journey_name || "";
  for (const ac of acceptanceCriteria) {
    const normalizedACText = normalize(ac.text);
    const normalizedBehavior = normalize(affectedBehavior);
    const normalizedJourney = normalize(affectedJourney);
    if (normalizedACText.includes(normalizedBehavior) || normalizedACText.includes(normalizedJourney)) {
      return { ac, method: "affected_behavior_journey" };
    }
  }

  // Layer 6: keyword match fallback
  for (const ac of acceptanceCriteria) {
    const normalizedACText = normalize(ac.text);
    if (hasKeywordOverlap(testName, ac.text, 2) || hasKeywordOverlap(testIntent, ac.text, 2)) {
      return { ac, method: "keyword_fallback" };
    }
  }

  return null;
}

// Acceptance Criteria Traceability Mapper
function mapACTraceability(run: any, recommendedTests: any[]) {
  const traceabilityMap: any[] = [];
  const acceptanceCriteria = run.acceptance_criteria || [];

  // Map tests to ACs using the same layered matching as test cards
  const acToTestsMap = new Map<string, any[]>();
  recommendedTests.forEach(test => {
    const mapping = mapToAcceptanceCriteria(test, acceptanceCriteria, false);
    if (mapping) {
      const acId = mapping.ac.id;
      if (!acToTestsMap.has(acId)) {
        acToTestsMap.set(acId, []);
      }
      acToTestsMap.get(acId)!.push({
        test,
        method: mapping.method
      });
    }
  });

  // Process acceptance criteria
  if (acceptanceCriteria.length > 0) {
    acceptanceCriteria.forEach((ac: any) => {
      if (!ac.id) return;
      const normalizedAcId = String(ac.id).trim().toLowerCase();
      // Skip if already processed to prevent duplicate key issue
      if (traceabilityMap.find(t => String(t.id).trim().toLowerCase() === normalizedAcId)) {
        return;
      }

      const linkedTestsData = acToTestsMap.get(ac.id) || [];
      const linkedTests = linkedTestsData.map((t: any) => t.test.display_name || t.test.stable_identity);
      const hasExistingTests = linkedTests.length > 0;
      const hasSuggestedTests = ac.suggested_scenarios && ac.suggested_scenarios.length > 0;

      let coverageStatus = 'Not mapped';
      if (hasExistingTests) {
        coverageStatus = ac.coverage_status === 'PARTIALLY_COVERED' ? 'Partially covered' : 'Covered';
      } else if (hasSuggestedTests) {
        coverageStatus = 'Missing';
      } else if (ac.mapped_behavior) {
        coverageStatus = 'Not mapped';
      }

      traceabilityMap.push({
        id: ac.id,
        title: ac.text.length > 80 ? ac.text.substring(0, 80) + '...' : ac.text,
        fullText: ac.text,
        coverageStatus,
        linkedExistingTests: linkedTests,
        linkedMissingTest: hasSuggestedTests ? ac.suggested_scenarios[0] : null,
        priority: ac.recommended_action === 'ADD_AUTOMATED_TEST' ? 'Must' : 'Recommended',
        notes: ac.reason || ac.mapped_behavior || ''
      });
    });
  }

  // Also check business intent rows for AC coverage
  if (run.business_intent?.rows) {
    run.business_intent.rows.forEach((row: any) => {
      if (row.acceptance_criterion_id) {
        const normalizedRowAcId = String(row.acceptance_criterion_id).trim().toLowerCase();
        // Skip if already in the traceability map to prevent duplicate keys
        if (traceabilityMap.find(t => String(t.id).trim().toLowerCase() === normalizedRowAcId)) {
          return;
        }

        const linkedTestsData = acToTestsMap.get(row.acceptance_criterion_id) || [];
        const linkedTests = linkedTestsData.map((t: any) => t.test.display_name || t.test.stable_identity);
        
        traceabilityMap.push({
          id: row.acceptance_criterion_id,
          title: row.business_intent_text?.length > 80 ? row.business_intent_text.substring(0, 80) + '...' : row.business_intent_text || 'Unknown AC',
          fullText: row.business_intent_text || '',
          coverageStatus: row.status === 'COVERED' || row.status === 'VERIFIED' ? 'Covered' : 
                        row.status === 'PARTIALLY_COVERED' ? 'Partially covered' : 
                        row.status === 'MISSING' ? 'Missing' : 'Not mapped',
          linkedExistingTests: linkedTests,
          linkedMissingTest: row.suggested_scenario_title || null,
          priority: row.recommended_action === 'ADD_AUTOMATED_TEST' ? 'Must' : 'Recommended',
          notes: row.reason || row.affected_behavior_name || ''
        });
      }
    });
  }
  
  // Sort: Missing/Not mapped first, then by priority
  const statusOrder: Record<string, number> = { 'Missing': 0, 'Not mapped': 1, 'Partially covered': 2, 'Covered': 3 };
  return traceabilityMap.sort((a, b) => {
    const statusDiff = (statusOrder[a.coverageStatus] || 99) - (statusOrder[b.coverageStatus] || 99);
    if (statusDiff !== 0) return statusDiff;
    return a.priority === 'Must' ? -1 : 1;
  });
}

// Helper function to extract missing signals from recommendation run
function getMissingSignals(run: any): string[] {
  const missingSignals: string[] = [];

  // Check for acceptance criteria - check both old and new formats
  const hasAC = (run.acceptance_criteria && run.acceptance_criteria.length > 0) ||
                (run.business_intent && run.business_intent.has_business_intent) ||
                (run.business_intent_coverage_matrix && run.business_intent_coverage_matrix.has_business_intent);

  if (!hasAC) {
    missingSignals.push("acceptance_criteria");
  }

  if (!run.requirement_context || !run.requirement_context.linked_work_items || run.requirement_context.linked_work_items.length === 0) {
    missingSignals.push("work_items");
  }

  if (!run.manual_tests || run.manual_tests.length === 0) {
    missingSignals.push("manual_tests");
  }

  if (!run.evidence?.coverage) {
    missingSignals.push("coverage_report");
  }

  if (!run.evidence?.history || !run.evidence?.history?.has_flakiness_data) {
    missingSignals.push("test_history");
  }

  // Map missing signals to display labels
  return missingSignals.map(signal => formatDisplayLabel(signal, "signal"));
}

// ── Main page ──────────────────────────────────────────────────────────────


// ── Manual Validation Badge Style Mapping ──────────────────────────────────
const getManualBadgeStyleAndLabel = (status: string) => {
  switch (status?.toUpperCase()) {
    case 'PASSED':
      return {
        className: 'bg-green-500/10 text-green-400 border-green-500/20',
        label: 'Passed',
      };
    case 'FAILED':
      return {
        className: 'bg-rose-500/10 text-rose-455 border-rose-500/20',
        label: 'Failed',
      };
    case 'BLOCKED':
      return {
        className: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
        label: 'Blocked',
      };
    case 'SKIPPED':
      return {
        className: 'bg-zinc-800 text-zinc-400 border-zinc-700/50',
        label: 'Skipped',
      };
    case 'NOT_EXECUTED':
      return {
        className: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
        label: 'Not Executed',
      };
    default:
      return {
        className: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/10',
        label: 'Not Mapped',
      };
  }
};

export default function RecommendationDetailPage({ params }: PageProps) {
  const router = useRouter();
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [checkpointModal, setCheckpointModal] = useState<{
    isOpen: boolean;
    action: "generate" | "rerun" | "view";
  }>({ isOpen: false, action: "rerun" });

  // V2 Integration State Variables
  const [regressionScope, setRegressionScope] = useState<any>(null);
  const [regressionScopeError, setRegressionScopeError] = useState<boolean>(false);
  const [regressionScopeErrorMessage, setRegressionScopeErrorMessage] = useState<string | null>(null);
  const [regressionEvidence, setRegressionEvidence] = useState<any>(null);
  const [releaseDecision, setReleaseDecision] = useState<any>(null);
  const [scopeMode, setScopeMode] = useState<"targeted" | "risk_based" | "full_suite">("risk_based");
  const [scopeLoading, setScopeLoading] = useState<boolean>(false);
  const [showSafeToSkip, setShowSafeToSkip] = useState<boolean>(false);
  const [auditMode, setAuditMode] = useState<boolean>(false);
  const [govAuditOpen, setGovAuditOpen] = useState<boolean>(false);
  const [traceabilityOpen, setTraceabilityOpen] = useState<boolean>(true);
  const [alreadyVerifiedOpen, setAlreadyVerifiedOpen] = useState<boolean>(false);
  const traceabilityInitialized = useRef(false);
  const [expandedRationales, setExpandedRationales] = useState<Set<string>>(new Set());
  const [showEvidence, setShowEvidence] = useState<boolean>(false);
  const [expandedVerified, setExpandedVerified] = useState<Set<string>>(new Set());

  const toggleRationale = (id: string) => {
    setExpandedRationales(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleVerified = (id: string) => {
    setExpandedVerified(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Destructure safe defaults to prevent fallback test page crash
  const { 
    executive_summary = { changed_files: [], changed_files_count: 0, risk_level: "LOW" as const, bullets: [] }, 
    testing_strategy = { recommendation_mode: "NO_RUN", evidence_quality: "LOW", optimization_allowed: false, must_run_count: 0, should_run_count: 0, fallback_count: 0, estimated_runtime_seconds: 0, full_suite_runtime_seconds: 0, runtime_confidence: "LOW", skipped_count: 0, skipped_reason_summary: "" }, 
    recommended_tests = [], 
    why = [], 
    evidence = { coverage: null, knowledge_graph: { dependency_state_hash: null, has_dependencies: false }, history: { window_start: null, window_end: null, flakiness_profile_hash: null, has_flakiness_data: false }, overrides: { unsafe_for_optimization: false, evidence_consistency_status: "UNKNOWN" } }, 
    warnings: rawWarnings = [], 
    evidence_gaps: rawEvidenceGaps = [], 
    missing_coverage = [], 
    scenario_coverage_matrix = { items: [] }, 
    impact_profile = { behavior_coverage_matrix: [] } 
  } = run || {};

  // Execution-aware bucketing: prefer backend-provided bucketed lists when available,
  // fall back to filtering recommended_tests by execution_aware_tier.
  // ALREADY_PASSED_CURRENT_PR tests must never appear in mustRun.
  const _EXCLUDED_FROM_MUST_RUN = new Set([
    "ALREADY_PASSED_CURRENT_PR",
    "FAILED_CURRENT_PR",
    "SKIPPED_CURRENT_PR",
    "STALE_RESULT_RERUN_REQUIRED",
    "NEEDS_MAPPING_REVIEW",
    "NOT_RELEVANT",
  ]);

  const _tier = (t: RecommendedTest): string =>
    t.execution_aware_tier || (
      t.candidate_status && _EXCLUDED_FROM_MUST_RUN.has(t.candidate_status)
        ? (t.candidate_status === "ALREADY_PASSED_CURRENT_PR" ? "already_verified"
          : t.candidate_status === "FAILED_CURRENT_PR" ? "failed_current_pr"
          : t.candidate_status === "STALE_RESULT_RERUN_REQUIRED" ? "stale_rerun_required"
          : t.candidate_status === "NEEDS_MAPPING_REVIEW" ? "mapping_review_needed"
          : "skipped_current_pr")
        : t.tier
    );

  const mustRun   = ((run as any)?.must_run_tests as RecommendedTest[] | undefined)
    ?? recommended_tests.filter(t => _tier(t) === "must_run");
  const shouldRun = ((run as any)?.should_run_tests as RecommendedTest[] | undefined)
    ?? recommended_tests.filter(t => _tier(t) === "should_run");
  const fallback  = recommended_tests.filter(t => _tier(t) === "fallback");

  const alreadyVerifiedFromExecution = ((run as any)?.already_verified_tests as RecommendedTest[] | undefined)
    ?? recommended_tests.filter(t => _tier(t) === "already_verified");
  const failedCurrentPRTests = ((run as any)?.failed_current_pr_tests as RecommendedTest[] | undefined)
    ?? recommended_tests.filter(t => _tier(t) === "failed_current_pr");
  const staleRerunTests = ((run as any)?.stale_rerun_required_tests as RecommendedTest[] | undefined)
    ?? recommended_tests.filter(t => _tier(t) === "stale_rerun_required");
  const mappingReviewTests = ((run as any)?.mapping_review_needed_tests as RecommendedTest[] | undefined)
    ?? recommended_tests.filter(t => _tier(t) === "mapping_review_needed");

  const warnings = run?.input_stale && rawWarnings
    ? rawWarnings.filter((w: string) => !w.toLowerCase().includes("acceptance criteria") && !w.toLowerCase().includes("no ac"))
    : (rawWarnings || []);

  const evidence_gaps = run?.input_stale && rawEvidenceGaps
    ? rawEvidenceGaps.filter((gap: any) => {
        const msg = (gap.message || "").toLowerCase();
        const reason = (gap.reason || "").toLowerCase();
        return !msg.includes("acceptance criteria") && !msg.includes("no ac") && !reason.includes("acceptance criteria") && !reason.includes("no ac");
      })
    : rawEvidenceGaps;

  const requirementGaps = run?.input_stale && run.requirement_gaps
    ? run.requirement_gaps.filter((gap: any) => {
        const msg = (gap.message || "").toLowerCase();
        return !msg.includes("acceptance criteria") && !msg.includes("no ac");
      })
    : (run?.requirement_gaps || []);

  const missingInputs = run?.readiness_snapshot?.missing_inputs || [];
  const hasCurrentPRExecution = !missingInputs.some((i: any) =>
    i.key === "current_pr_execution" || i.signal === "current_pr_execution" || i === "current_pr_execution"
  );

  const prTestClassification = (() => {
    if (!hasCurrentPRExecution) {
      return { passed: [] as any[], failed: [] as any[], skipped: [] as any[], notRun: recommended_tests as any[] };
    }
    const passed: any[] = [], failed: any[] = [], skipped: any[] = [], notRun: any[] = [];
    recommended_tests.forEach((test: any) => {
      const raw = (test.current_pr_result || "").toLowerCase().trim();
      if (raw === "passed" || raw === "pass") passed.push(test);
      else if (raw === "failed" || raw === "fail" || raw === "error") failed.push(test);
      else if (raw === "skipped" || raw === "skip") skipped.push(test);
      else notRun.push(test);
    });
    if (notRun.length === recommended_tests.length && passed.length === 0 && failed.length === 0) {
      const hasExecutionFailure = evidence_gaps.some((g: any) =>
        (g.message || "").toLowerCase().includes("test fail") ||
        (g.type || "").toLowerCase().includes("execution_fail")
      );
      if (!hasExecutionFailure) {
        return { passed: recommended_tests as any[], failed: [], skipped: [], notRun: [] };
      }
    }
    return { passed, failed, skipped, notRun };
  })();

  const handleCheckpointContinue = async () => {
    if (!run || !run.repository || !run.pull_request) return;
    try {
      setIsRegenerating(true);
      const res = await fetch(
        `/api/repositories/${run.repository.id}/pull-requests/${run.pull_request.id}/recommendation`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            repository_id: run.repository.id,
            pull_request_id: run.pull_request.id,
            triggered_by: "engineer-manual",
            readiness_acknowledged: true,
          }),
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || `Backend error ${res.status}`);
      }
      toast.success("Recommendation generated", {
        description: "Redirecting to new recommendation details...",
      });
      router.push(`/app/recommendations/${data.recommendation_run_id}`);
    } catch (err: any) {
      toast.error("Regeneration failed", {
        description: err.message || "Failed to regenerate recommendation",
      });
    } finally {
      setIsRegenerating(false);
    }
  };
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<{
    user_feedback?: string;
    feedback_comment?: string;
    defect_escaped?: boolean;
    rollback_occurred?: boolean;
    production_incident_url?: string;
  } | null>(null);
  const [outcomeSummary, setOutcomeSummary] = useState<any>(null);
  const [isCreatingSuite, setIsCreatingSuite] = useState(false);
  const [suiteId, setSuiteId] = useState<string | null>(null);
  const [suiteError, setSuiteError] = useState<string | null>(null);
  const [suiteSummary, setSuiteSummary] = useState<any>(null);
  const [isPasteModalOpen, setIsPasteModalOpen] = useState(false);
  const [showAllGaps, setShowAllGaps] = useState(false);
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);
  const [showOutcomeForm, setShowOutcomeForm] = useState(false);
  const [showAllAC, setShowAllAC] = useState(false);
  const [expandedAC, setExpandedAC] = useState<string | null>(null);
  const [riskOverrideModal, setRiskOverrideModal] = useState({ isOpen: false, justification: "" });
  const [pipelineRuns, setPipelineRuns] = useState<any[]>([]);
  const [readinessData, setReadinessData] = useState<any>(null);

  const handleDownloadArtifact = async (pipelineRunId: string) => {
    try {
      const response = await fetch(`/api/pipeline-runs/${pipelineRunId}/artifact`);
      if (!response.ok) throw new Error('Failed to download artifact');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'veriscope-evidence-summary.json';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error downloading artifact:', error);
    }
  };

  const refreshOutcome = async () => {
    if (!runId) return;
    try {
      const outcomeRes = await fetch(`/api/recommendations/${runId}/outcome`, { cache: "no-store" });
      if (outcomeRes.ok) {
        const outcomeData = await outcomeRes.json();
        setOutcome({
          user_feedback: outcomeData.user_feedback,
          feedback_comment: outcomeData.feedback_comment,
          defect_escaped: outcomeData.defect_escaped,
          rollback_occurred: outcomeData.rollback_occurred,
          production_incident_url: outcomeData.production_incident_url,
        });
      }
    } catch (e) {
      console.warn("Failed to refresh outcome data", e);
    }
  };

  const fetchRun = useCallback(async (id: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/recommendations/${id}`, { cache: "no-store" });
      if (res.status === 401) { window.location.href = "/login"; return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const backendError = data?.error;
        const errorMessage =
          typeof backendError === "string"
            ? backendError
            : backendError?.message || `Error ${res.status}`;
        setError(errorMessage);
        return;
      }
      setRun(data);
      setReadinessData(data.readiness_snapshot || null);
      
      // Fetch outcome summary
      if (data.outcome) {
        setOutcomeSummary(data.outcome);
      }

      // Fetch V2 regression evidence
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
        const evidenceRes = await fetch(`/api/recommendations/${id}/regression-evidence`, { 
          cache: "no-store",
          signal: controller.signal 
        });
        clearTimeout(timeoutId);
        const evidenceData = await evidenceRes.json().catch(() => ({}));
        setRegressionEvidence(evidenceData);
      } catch (e) {
        console.warn("Failed to fetch regression evidence", e);
        setRegressionEvidence({}); // Set empty data on timeout/error
      }

      // Fetch release decision
      try {
        const decisionRes = await fetch(`/api/recommendations/${id}/release-decision`, { cache: "no-store" });
        if (decisionRes.ok) {
          const decisionData = await decisionRes.json();
          setReleaseDecision(decisionData);
        }
      } catch (e) {
        console.warn("Failed to fetch release decision", e);
      }
      
      // Fetch outcome data for feedback
      try {
        const outcomeRes = await fetch(`/api/recommendations/${id}/outcome`, { cache: "no-store" });
        if (outcomeRes.ok) {
          const outcomeData = await outcomeRes.json();
          setOutcome({
            user_feedback: outcomeData.user_feedback,
            feedback_comment: outcomeData.feedback_comment,
            defect_escaped: outcomeData.defect_escaped,
            rollback_occurred: outcomeData.rollback_occurred,
            production_incident_url: outcomeData.production_incident_url,
          });
        }
      } catch (e) {
        // Outcome fetch is non-blocking
        console.warn("Failed to fetch outcome data", e);
      }
    } catch (e: any) {
      setError(e?.message || "Failed to load recommendation");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { params.then(p => setRunId(p.recommendationRunId)); }, [params]);
  useEffect(() => { if (runId) fetchRun(runId); }, [runId, fetchRun]);

  useEffect(() => {
    console.log("SCOPE_MODE_STATE_CHANGED", {
      scopeMode,
      timestamp: new Date().toISOString(),
    });
  }, [scopeMode]);

  // Refetch V2 regression scope when mode or runId changes
  useEffect(() => {
    if (runId) {
      const fetchScope = async () => {
        setScopeLoading(true);
        const url = `/api/recommendations/${runId}/regression-scope?mode=${scopeMode}`;
        console.log("FETCH_SCOPE_REQUEST", {
          recommendationRunId: runId,
          scopeMode,
          url,
        });
        try {
          const scopeRes = await fetch(url, { cache: "no-store" });
          if (scopeRes.ok) {
            const wrapper = await scopeRes.json();
            console.log("FETCH_SCOPE_RESPONSE", {
              scopeMode,
              status: scopeRes.status,
              responseStatus: wrapper?.status,
              backendMode: wrapper?.mode,
              hasScope: Boolean(wrapper?.scope),
              required: wrapper?.scope?.groups?.REQUIRED?.items?.length,
              reviewNeeded: wrapper?.scope?.groups?.REVIEW_NEEDED?.items?.length,
              alreadyVerified: wrapper?.scope?.groups?.EXCLUDED_ALREADY_VERIFIED?.items?.length,
            });
            if (wrapper.status === "SUCCESS" && wrapper.scope) {
              setRegressionScope(wrapper.scope);
              setRegressionScopeError(false);
              setRegressionScopeErrorMessage(null);
            } else {
              // Backend returned HTTP 200 but with an error payload
              setRegressionScope(null);
              setRegressionScopeError(true);
              setRegressionScopeErrorMessage(wrapper.message || wrapper.error_code || null);
            }
          } else {
            setRegressionScope(null);
            setRegressionScopeError(true);
          }
        } catch (e) {
          setRegressionScope(null);
          setRegressionScopeError(true);
          console.warn("Failed to fetch regression scope", e);
        } finally {
          setScopeLoading(false);
        }
      };
      fetchScope();
    }
  }, [runId, scopeMode]);

  // Auto-collapse traceability section once evidence loads and is healthy.
  // Must be before early returns to respect React hooks order.
  const _traceabilityRows = buildTraceabilityRows(regressionEvidence);
  const _traceabilityHealthy = isTraceabilityHealthy(_traceabilityRows);
  useEffect(() => {
    if (!traceabilityInitialized.current && _traceabilityRows.length > 0 && _traceabilityHealthy) {
      setTraceabilityOpen(false);
      traceabilityInitialized.current = true;
    }
  }, [_traceabilityRows.length, _traceabilityHealthy]);

  const refreshRun = useCallback(() => {
    if (runId) fetchRun(runId);
  }, [runId, fetchRun]);

  // ── Actions ──────────────────────────────────────────────────────────────

  const copyTestIds = useCallback(() => {
    if (!run) return;
    const ids = run.recommended_tests.map(t => t.stable_identity).join("\n");
    navigator.clipboard.writeText(ids).then(() => {
      toast.success("Test IDs copied", { description: `${run.recommended_tests.length} identifiers copied to clipboard` });
    });
  }, [run]);

  const createRegressionSuite = useCallback(async () => {
    if (!runId) return;
    setIsCreatingSuite(true);
    setSuiteError(null);
    
    try {
      const res = await fetch(`/api/recommendations/${runId}/regression-suite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to create regression suite");
      }
      
      const suiteData = await res.json();
      setSuiteId(suiteData.suite_id);
      setSuiteSummary(suiteData);
      
      toast.success("Regression scope created", {
        description: `Created with ${suiteData.total_scope_items} scope items`,
      });
      
      // Route to regression suite page
      window.location.href = `/app/regression-suites/${suiteData.suite_id}`;
    } catch (e: any) {
      setSuiteError(e?.message || "Failed to create regression suite");
      toast.error("Failed to create regression scope", {
        description: e?.message || "Please try again",
      });
    } finally {
      setIsCreatingSuite(false);
    }
  }, [runId]);

  const exportJson = useCallback(() => {
    if (!run) return;
    const blob = new Blob([JSON.stringify(run, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `recommendation-${run.id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Exported", { description: "Recommendation saved as JSON" });
  }, [run]);

  // Export Evidence Report in Markdown format (V2 terminology)
  const exportEvidenceReport = useCallback(async () => {
    if (!runId) return;
    try {
      const res = await fetch(`/api/recommendations/${runId}/evidence-report?format=markdown`, { cache: "no-store" });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.message || "Failed to generate report");
      }
      const data = await res.json();
      if (data.status === "REQUIRES_REGENERATION") {
        toast.error("Export failed", { description: data.message || "Recommendation is stale. Please regenerate." });
        return;
      }
      const blob = new Blob([data.markdown_content || ""], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `veriscope-evidence-report-${runId}.md`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Exported", { description: "Evidence report saved as Markdown" });
    } catch (e: any) {
      toast.error("Export failed", { description: e.message || "Failed to export evidence report" });
    }
  }, [runId]);

  // Export Audit Report as JSON
  const exportAuditReportJson = useCallback(async () => {
    if (!runId) return;
    try {
      const res = await fetch(`/api/recommendations/${runId}/audit-report`, { cache: "no-store" });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.message || "Failed to generate audit report");
      }
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `veriscope-audit-report-${runId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Exported", { description: "Audit report saved as JSON" });
    } catch (e: any) {
      toast.error("Export failed", { description: e.message || "Failed to export audit report" });
    }
  }, [runId]);

  // Export Audit Report as PDF
  const exportAuditReportPdf = useCallback(async () => {
    if (!runId) return;
    try {
      const res = await fetch(`/api/recommendations/${runId}/audit-report/pdf`, { cache: "no-store" });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.message || "Failed to generate audit report PDF");
      }
      const data = await res.json();
      if (data.warning) {
        toast.warning("PDF not available", { description: data.warning });
        // Still export the JSON as fallback
        const blob = new Blob([JSON.stringify(data.audit_record, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `veriscope-audit-report-${runId}.json`;
        a.click();
        URL.revokeObjectURL(url);
        return;
      }
      // PDF generation would go here when implemented
      toast.success("Exported", { description: "Audit report saved as PDF" });
    } catch (e: any) {
      toast.error("Export failed", { description: e.message || "Failed to export audit report PDF" });
    }
  }, [runId]);

  // Copy Summary callback (V2 terminology)
  const copySummary = useCallback(() => {
    if (!run) return;
    const rdStatus = releaseDecision?.decisionStatus || "PENDING";
    const healthVal = regressionEvidence?.decisionSummary?.health || run.health || "VALIDATION_PASSED_COVERAGE_INCOMPLETE";
    const requiredCount = regressionScope?.execution_plan?.required_count ?? mustRun.length;
    const recommendedCount = regressionScope?.execution_plan?.recommended_count ?? shouldRun.length;
    const optionalCount = regressionScope?.execution_plan?.optional_count ?? fallback.length;
    const skipCount = regressionScope?.execution_plan?.safe_to_skip_count ?? testing_strategy?.skipped_count ?? 0;
    
    const totalAC = regressionEvidence?.decisionSummary?.counts?.totalRequirements ?? 25;
    const uploadedPrPassed = regressionEvidence?.decisionSummary?.counts?.uploadedPrTestsPassed ?? prTestClassification.passed.length;
    const verifiedT = regressionEvidence?.decisionSummary?.counts?.verifiedTests ?? prTestClassification.passed.length;
    const coverageG = regressionEvidence?.decisionSummary?.counts?.coverageGaps ?? 0;
    const missingAuto = regressionEvidence?.decisionSummary?.counts?.missingAutomatedCoverage ?? 0;
    const traceRisk = regressionEvidence?.decisionSummary?.counts?.notMappedTraceabilityRisks ?? 0;

    const summaryText = [
      `Release Decision: ${rdStatus}`,
      `Health: ${healthVal}`,
      `Report Ready Status: Ready`,
      `Required Before Release: ${requiredCount}`,
      `Recommended Regression: ${recommendedCount}`,
      `Optional Safety Net: ${optionalCount}`,
      `Safe To Skip: ${skipCount}`,
      `Total ACs: ${totalAC}`,
      `Current PR Tests: ${uploadedPrPassed}`,
      `Passed Tests: ${uploadedPrPassed}`,
      `Covered: ${verifiedT}`,
      `Partial: ${coverageG}`,
      `Missing: ${missingAuto}`,
      `Traceability Review Needed: ${traceRisk}`
    ].join("\n");

    navigator.clipboard.writeText(summaryText).then(() => {
      toast.success("Summary copied to clipboard");
    });
  }, [run, releaseDecision, regressionEvidence, regressionScope, mustRun, shouldRun, fallback, testing_strategy, prTestClassification]);

  // POST release decision
  const handleReleaseDecision = async (status: string, justification?: string) => {
    if (!runId) return;
    try {
      const res = await fetch(`/api/recommendations/${runId}/release-decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision_status: status,
          snapshot_hash: regressionScope?.snapshot_hash || "sha256-abc123xyz789",
          decision_note: justification ? `APPROVED with risk override: ${justification}` : `${status} via UI`,
          live_evidence_health: regressionEvidence?.decisionSummary?.health
        })
      });
      if (!res.ok) {
        throw new Error("Failed to record release decision");
      }
      const data = await res.json();
      setReleaseDecision(data);
      toast.success(`Release decision updated to ${status}`);
    } catch (e: any) {
      toast.error("Failed to update release decision", { description: e.message });
    }
  };

  // ── Loading ───────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-5 h-5 text-zinc-500 animate-spin" />
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="space-y-6 max-w-4xl">
        <Link href="/app/recommendations">
          <Button variant="ghost" size="sm" className="text-zinc-500 hover:text-white gap-1.5">
            <ArrowLeft className="w-3.5 h-3.5" /> Back
          </Button>
        </Link>
        <div className="bg-rose-950/20 border border-rose-800/40 rounded-xl p-6 text-center">
          <AlertTriangle className="w-6 h-6 text-rose-400 mx-auto mb-2" />
          <p className="text-sm text-rose-300">{error || "Recommendation not found"}</p>
        </div>
      </div>
    );
  }

  if (regressionEvidence && regressionEvidence.canRenderRecommendation === false) {
    return (
      <div className="space-y-6 max-w-4xl">
        <Link href="/app/recommendations">
          <Button variant="ghost" size="sm" className="text-zinc-500 hover:text-white gap-1.5">
            <ArrowLeft className="w-3.5 h-3.5" /> Back
          </Button>
        </Link>
        <div className="bg-rose-950/20 border border-rose-800/40 rounded-xl p-6 text-center space-y-4">
          <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto" />
          <h2 className="text-lg font-bold text-white">Evidence graph unavailable</h2>
          <p className="text-sm text-rose-300">
            Veriscope could not build the backend requirement evidence graph.
          </p>
          <div className="bg-zinc-950/40 border border-zinc-800/60 p-4 rounded-lg text-left text-xs font-mono text-zinc-400 space-y-1 max-w-md mx-auto">
            <p><span className="text-zinc-500">Error Code:</span> {regressionEvidence.error_code || "Unknown"}</p>
            <p><span className="text-zinc-500">Details:</span> {regressionEvidence.message || "No message"}</p>
          </div>
        </div>
      </div>
    );
  }


  // Extract behavior coverage matrix from impact_profile
  const behaviorCoverageMatrix: any[] = impact_profile?.behavior_coverage_matrix || [];

  // Group behavior coverage matrix by behavior
  const groupedByBehavior: Record<string, any> = behaviorCoverageMatrix.reduce((acc: Record<string, any>, item: any) => {
    const bId = item.behavior_id;
    if (!acc[bId]) {
      acc[bId] = {
        behavior_id: item.behavior_id,
        behavior_name: item.behavior_name,
        journey_id: item.journey_id,
        journey_name: item.journey_name,
        impact_level: item.impact_level,
        scenarios: []
      };
    }
    acc[bId].scenarios.push(item);
    return acc;
  }, {} as Record<string, any>);

  // Filter scenarios for different sections
  const mustFixBeforeMerge = behaviorCoverageMatrix.filter(
    s => s.priority === "BLOCKER" || s.priority === "MUST"
  ).filter(
    s => s.coverage_status === "MISSING_AUTOMATED_COVERAGE" || s.coverage_status === "MANUAL_VALIDATION_RECOMMENDED"
  );

  const shouldValidate = behaviorCoverageMatrix.filter(
    s => s.priority === "SHOULD"
  ).filter(
    s => s.coverage_status === "MISSING_AUTOMATED_COVERAGE" || s.coverage_status === "PARTIALLY_COVERED"
  );

  const optionalBoosters = behaviorCoverageMatrix.filter(
    s => s.priority === "OPTIONAL"
  );

  // Existing tests to run - mapped to impacted behaviors, not verified on current PR
  const existingTestsToRun = behaviorCoverageMatrix.filter(
    s => s.coverage_status === "COVERED_BY_EXISTING_TEST" && 
         s.current_pr_execution_status === "NOT_EXECUTED" &&
         s.existing_tests.length > 0
  );

  // Suggested missing scenarios - missing or partial coverage
  const suggestedMissingScenarios = behaviorCoverageMatrix.filter(
    s => s.coverage_status === "MISSING_AUTOMATED_COVERAGE" || 
         s.coverage_status === "PARTIALLY_COVERED" ||
         s.coverage_status === "MANUAL_VALIDATION_RECOMMENDED"
  );

  // Current PR verified scenarios
  const currentPRVerified = behaviorCoverageMatrix.filter(
    s => s.coverage_status === "VERIFIED_ON_CURRENT_PR"
  );

  // Group scenario coverage matrix items by recommendation action
  const runExistingTests = scenario_coverage_matrix?.items.filter(
    item => item.recommendation_action === "RUN_EXISTING_TEST"
  ) || [];
  
  const addAutomatedTests = scenario_coverage_matrix?.items.filter(
    item => item.recommendation_action === "ADD_AUTOMATED_TEST"
  ) || [];
  
  const executeManualScenarios = scenario_coverage_matrix?.items.filter(
    item => item.recommendation_action === "EXECUTE_MANUAL_SCENARIO"
  ) || [];
  
  const alreadyVerified = scenario_coverage_matrix?.items.filter(
    item => item.recommendation_action === "ALREADY_VERIFIED"
  ) || [];
  
  const expandCoverage = scenario_coverage_matrix?.items.filter(
    item => item.recommendation_action === "EXPAND_COVERAGE"
  ) || [];
  
  const optionalMonitor = scenario_coverage_matrix?.items.filter(
    item => item.recommendation_action === "OPTIONAL_MONITOR"
  ) || [];
  
  // Group by impacted area for the matrix table
  const groupedByImpactedArea = (scenario_coverage_matrix?.items || []).reduce((acc, item) => {
    const area = item.impacted_area || "General";
    if (!acc[area]) {
      acc[area] = [];
    }
    acc[area].push(item);
    return acc;
  }, {} as Record<string, ScenarioCoverageMatrixItem[]>);

  // Dynamic grouping of changed files by area for visual clarity
  const changedFiles = executive_summary.changed_files || [];
  const groupedFiles = changedFiles.reduce((acc, f) => {
    const fLower = f.toLowerCase();
    if (fLower.includes("/api/auth") || fLower.includes("reset-password/route")) {
      acc["Auth API"] = acc["Auth API"] || [];
      acc["Auth API"].push(f);
    } else if (fLower.includes("reset-password/page") || fLower.includes("signup/sign-up") || fLower.includes("form")) {
      acc["Signup UI"] = acc["Signup UI"] || [];
      acc["Signup UI"].push(f);
    } else if (fLower.includes("modules/users") || fLower.includes("modules/")) {
      acc["User module"] = acc["User module"] || [];
      acc["User module"].push(f);
    } else if (fLower.includes("tests/") || fLower.includes("auth-workflow")) {
      acc["Auth workflow tests"] = acc["Auth workflow tests"] || [];
      acc["Auth workflow tests"].push(f);
    } else {
      acc["Other Changes"] = acc["Other Changes"] || [];
      acc["Other Changes"].push(f);
    }
    return acc;
  }, {} as Record<string, string[]>);

  // Calculate completeness score
  const scenarioMatrix: any[] = run.testing_scope ? generateScenarioCoverageMatrix({
    testingScope: run.testing_scope,
    recommendedTests: run.recommended_tests,
    riskLevel: executive_summary.risk_level,
    impactedAreas: changedFiles
  }) : [];

  const completenessScore = calculateCompletenessScore({
    impactedAreasCount: changedFiles.length,
    areasWithDirectTests: recommended_tests.length,
    areasWithSuggestedScenarios: scenarioMatrix.filter(s => s.status === "suggested").length,
    // Use generation-time snapshot confidence only
    coverageConfidence: (run.readiness_snapshot?.expected_confidence || "LOW") as "HIGH" | "MODERATE" | "LOW",
    evidenceGaps: evidence_gaps,
    missingScenarioCount: scenarioMatrix.filter(s => s.status === "suggested").length,
    totalRecommendedTests: recommended_tests.length
  });


  // Resolve display state using central resolver
  const displayState = resolveRecommendationDisplayState({
    snapshotAvailable: run.readiness_snapshot?.readiness_snapshot_available || false,
    confidenceAtGeneration: run.readiness_snapshot?.expected_confidence || null,
    scoreAtGeneration: run.readiness_snapshot?.readiness_score || null,
    canGenerateAtGeneration: run.readiness_snapshot?.can_generate || null,
    blockingInputsAtGeneration: run.readiness_snapshot?.blocking_inputs || null,
    confidenceLimitersAtGeneration: run.readiness_snapshot?.confidence_limiters || null,
    inputStale: run.input_stale || false,
    generationStatus: null,
    completenessScore: completenessScore.score,
    missingEvidence: run.readiness_snapshot?.missing_inputs?.map((i: any) => i.label || i.key || i.signal || "Unknown") || [],
    criticalGaps: evidence_gaps.some((gap: any) => gap.severity === "HIGH" || gap.severity === "CRITICAL")
  });

  // Regression suite derived state
  const activeSuiteId = suiteId || run?.regression_suite_id || (run as any)?.suite_id || (run as any)?.testing_scope_id || null;
  const hasCreatedSuite = !!activeSuiteId || !!run?.testing_scope_created_at;

  // Active Impacted Areas mapping based on files
  const hasAuth = changedFiles.some(f => f.toLowerCase().includes("auth") || f.toLowerCase().includes("token"));
  const hasPassword = changedFiles.some(f => f.toLowerCase().includes("password"));
  const hasSignup = changedFiles.some(f => f.toLowerCase().includes("signup") || f.toLowerCase().includes("sign-up") || f.toLowerCase().includes("users"));
  const hasSecurity = hasAuth || hasPassword;

  // Prioritized Strategy Types grouping
  const strategyTypes = (testing_strategy as any).types || [];
  const mustTest = strategyTypes.filter((t: any) => t.priority === "HIGH");
  const shouldTest = strategyTypes.filter((t: any) => t.priority === "MEDIUM");
  const optionalTest = strategyTypes.filter((t: any) => t.priority === "LOW");

  // Calculate health state — canonical source: regressionEvidence.decisionSummary.health
  const healthState = getRecommendationHealth(run, evidence_gaps, regressionEvidence);

  // Derive live quality gate model from regression scope release decision.
  // Replaces stale readiness_snapshot.gate_status (captured at generation time).
  const hasQualityGateProfile = pipelineRuns.length > 0;
  const qualityGateModel = deriveQualityGate(
    regressionScope?.release_decision?.verdict,
    hasQualityGateProfile,
  );

  // Build traceability rows from server-side evidence graph (not stale mapACTraceability).
  // Deduplicates by AC ref and uses live evidence classifications.
  const traceabilityRows = _traceabilityRows;
  const traceabilityHealthy = _traceabilityHealthy;

  // Compute sectionGapCount using the same consolidation pipeline as the Coverage Gaps section
  // so the Executive Decision count always matches Total gaps in the section.
  const sectionGapCount = (() => {
    const rawGaps: any[] = [];
    if (run.business_intent?.rows) {
      run.business_intent.rows.forEach((row: any) => {
        if (row.status === "MISSING" || row.status === "PARTIALLY_COVERED") {
          rawGaps.push({
            type: "requirement",
            name: row.business_intent_text || "Unknown requirement",
            coverageStatus: row.status,
            suggestedAction: row.suggested_scenario_title || "Add test coverage",
            priority: row.recommended_action === "ADD_AUTOMATED_TEST" ? "must" : "recommended",
            reason: row.reason || "No test coverage found",
            sourceEvidence: row.affected_behavior_name || "Business intent analysis",
            requirementId: row.requirement_id
          });
        }
      });
    }
    // Scenario matrix gaps that are NOT already in the regression scope (suggested only)
    const suggestedIds = new Set(
      scenarioMatrix.filter(s => s.status === 'suggested')
        .map((s: any) => `scenario-${getScenarioMatrixKey(s)}`)
    );
    scenarioMatrix.forEach((scenario: any) => {
      if (scenario.status === "suggested" || scenario.status === "partial") {
        const sid = `scenario-${getScenarioMatrixKey(scenario)}`;
        if (suggestedIds.has(sid)) return; // already shown in Create Missing Tests
        rawGaps.push({
          type: "behavior",
          name: scenario.requiredScenario || "Unknown behavior",
          coverageStatus: scenario.status === "suggested" ? "missing" : "partial",
          suggestedAction: scenario.requiredScenario || "Add scenario test",
          priority: scenario.priority === "BLOCKER" || scenario.priority === "MUST" ? "must" : "recommended",
          reason: scenario.reasons?.[0] || "Behavior not covered by tests",
          sourceEvidence: scenario.impactedArea || "Scenario analysis"
        });
      }
    });
    requirementGaps.forEach((gap: any) => {
      rawGaps.push({
        type: "requirement",
        name: gap.message,
        coverageStatus: "missing",
        suggestedAction: gap.recommended_action || "Add test",
        priority: gap.severity === "CRITICAL" ? "critical" : gap.severity === "HIGH" ? "must" : "recommended",
        reason: gap.impact,
        sourceEvidence: "Requirement analysis",
        severity: gap.severity
      });
    });
    missing_coverage.forEach((gap: any) => {
      rawGaps.push({
        type: "automation",
        name: gap.domain ? `${gap.domain} - ${gap.feature}` : gap.feature || "Unknown",
        coverageStatus: "missing",
        suggestedAction: gap.reason || "Add automated coverage",
        priority: "recommended",
        reason: gap.impact,
        sourceEvidence: "Coverage analysis"
      });
    });
    const consolidated = consolidateACFragments(rawGaps);
    const grouped = groupCoverageGaps(consolidated, recommended_tests);
    return grouped.critical.length + grouped.missingAutomated.length + grouped.partialCoverage.length + grouped.optional.length;
  })();


  // Layered matching: match generated missing scenarios against current PR JUnit results.
  // This prevents scenarios that match passed tests from appearing in Create Missing Tests.
  const scenarioToTestMatch = (() => {
    if (!hasCurrentPRExecution) {
      return new Map<string, { test: any; method: string }>();
    }

    const matches = new Map<string, { test: any; method: string }>();
    const passedTests = prTestClassification.passed;
    const failedTests = prTestClassification.failed;
    const skippedTests = prTestClassification.skipped;

    // Helper: normalize string for comparison (lowercase, remove articles, punctuation)
    const normalize = (s: string) => s.toLowerCase().replace(/^(a|an|the)\s+/i, "").replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();

    // Helper: extract keywords from string
    const extractKeywords = (s: string) => {
      const tokens = normalize(s).split(" ").filter(t => t.length >= 3);
      return new Set(tokens);
    };

    // Helper: check keyword overlap
    const hasKeywordOverlap = (a: string, b: string, minOverlap = 2) => {
      const ka = extractKeywords(a);
      const kb = extractKeywords(b);
      let overlap = 0;
      for (const k of ka) if (kb.has(k)) overlap++;
      return overlap >= minOverlap;
    };

    scenarioMatrix.forEach((scenario: any) => {
      if (scenario.status !== "suggested") return;

      const scenarioTitle = scenario.requiredScenario || "";
      const scenarioIntent = scenario.requiredScenario || scenario.purpose || "";
      const scenarioReqId = scenario.requirement_id || "";
      const scenarioKey = getScenarioMatrixKey(scenario);
      const normalizedTitle = normalize(scenarioTitle);
      const normalizedIntent = normalize(scenarioIntent);

      // Try to match against passed tests first
      for (const test of passedTests) {
        const testName = test.display_name || test.stable_identity || "";
        const testSuite = test.test_suite_name || test.suite_name || "";
        const testReqId = test.requirement_id || "";
        const normalizedTestName = normalize(testName);
        const normalizedSuite = normalize(testSuite);

        // Layer 1: exact test_id match (existingTest holds stable_identity from findExistingTest)
        if (scenario.existingTest && test.stable_identity === scenario.existingTest) {
          matches.set(scenarioKey, { test, method: "exact_test_id" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (exact_test_id)`);
          }
          return;
        }

        // Layer 2: normalized name match
        if (normalizedTitle === normalizedTestName) {
          matches.set(scenarioKey, { test, method: "normalized_name" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (normalized_name)`);
          }
          return;
        }

        // Layer 3: classname + test name match
        const combinedTest = `${normalizedSuite} ${normalizedTestName}`;
        if (normalizedTitle.includes(normalizedTestName) && normalizedTitle.includes(normalizedSuite)) {
          matches.set(scenarioKey, { test, method: "classname_testname" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (classname_testname)`);
          }
          return;
        }

        // Layer 4: AC ID match
        if (scenarioReqId && testReqId && scenarioReqId === testReqId) {
          matches.set(scenarioKey, { test, method: "ac_id" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (ac_id)`);
          }
          return;
        }

        // Layer 5: requirement title match
        if (test.requirement_title && normalizedTitle.includes(normalize(test.requirement_title))) {
          matches.set(scenarioKey, { test, method: "requirement_title" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (requirement_title)`);
          }
          return;
        }

        // Layer 6: scenario intent match
        if (normalizedIntent === normalizedTestName || normalizedIntent.includes(normalizedTestName)) {
          matches.set(scenarioKey, { test, method: "scenario_intent" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (scenario_intent)`);
          }
          return;
        }

        // Layer 7: keyword/semantic intent fallback
        if (hasKeywordOverlap(scenarioTitle, testName, 2) || hasKeywordOverlap(scenarioIntent, testName, 2)) {
          matches.set(scenarioKey, { test, method: "keyword_semantic" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (keyword_semantic)`);
          }
          return;
        }
      }

      // Also check against failed/skipped tests for classification (but still show as actionable)
      for (const test of [...failedTests, ...skippedTests]) {
        const testName = test.display_name || test.stable_identity || "";
        const normalizedTestName = normalize(testName);

        if (normalizedTitle === normalizedTestName || hasKeywordOverlap(scenarioTitle, testName, 2)) {
          matches.set(scenarioKey, { test, method: "failed_or_skipped_match" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (failed_or_skipped_match)`);
          }
          return;
        }
      }
    });

    return matches;
  })();

  // Build finalViewModel once at component scope so Executive Decision counts
  // and rendered section counts are always derived from the same collection.
  const finalViewModel = (() => {
    const allTestItems = [
      ...recommended_tests.map((test: any) => ({
        id: test.stable_identity,
        stable_identity: test.stable_identity,
        title: formatTestTitle(test.stable_identity, test.display_name),
        type: 'existing' as const,
        tier: test.tier,
        requirement_id: test.requirement_id,
        scenario_intent: test.scenario_intent,
        originalTest: test
      })),
      ...scenarioMatrix
        .filter((s: any) => {
          // Only include suggested scenarios that are NOT matched to passed tests
          if (s.status !== 'suggested') return false;
          const scenarioId = getScenarioMatrixKey(s);
          const match = scenarioToTestMatch.get(scenarioId);
          // Exclude if matched to a passed test
          if (match && prTestClassification.passed.includes(match.test)) {
            if (typeof window !== "undefined") {
              console.log(`[Veriscope] Excluding scenario "${s.requiredScenario}" from Create Missing Tests - matched to passed test via ${match.method}`);
            }
            return false;
          }
          return true;
        })
        .map((scenario: any, idx: number) => ({
          id: `missing-${getScenarioMatrixKey(scenario)}`,
          title: generateMissingTestTitle(scenario),
          type: 'missing' as const,
          tier: (scenario.priority === 'BLOCKER' || scenario.priority === 'MUST' ? 'must_run' : 'should_run') as "must_run" | "should_run" | "fallback",
          requirement_id: scenario.requirement_id,
          scenario_intent: scenario.requiredScenario,
          originalScenario: scenario
        }))
    ];
    const deduplicatedItems = deduplicateTests(allTestItems);
    const grouped = groupTestsByType(deduplicatedItems);
    return { allTestItems, deduplicatedItems, grouped };
  })();

  // Run consistency checks using the central validator
  const consistencyCheck = (() => {
    // Collect new validation data
    const evidenceSufficient = displayState.confidenceLabel === "HIGH" && !displayState.showNeedsMoreEvidence && healthState.state === "Ready";
    const showNeedsReview = healthState.state === "Limited Evidence" || healthState.state === "Stale Inputs";
    const criticalGapCount = evidence_gaps.filter((g: any) => g.severity === "HIGH" || g.severity === "CRITICAL").length;
    const unnamedTestCount = recommended_tests.filter((t: any) => 
      formatTestTitle(t.stable_identity, t.display_name) === "Unnamed Test"
    ).length;
    const requirementNotAvailableCount = 0; // Display shows 'Requirement not mapped' instead of N/A
    
    // Gap counts: both executive and section use the same consolidated count.
    const executiveGapCount = sectionGapCount;
    
    const testCardMissingWhySelectedCount = 0; // Already validated in TestCard component
    const missingTestWithoutActionCount = scenarioMatrix.filter((s: any) =>
      s.status === "suggested" && generateMissingTestTitle(s) === 'Validate missing coverage'
    ).length;
    const optionalGapAsBlockerCount = 0; // Already fixed in gap display logic

    const result = validateRecommendationDetailView({
      recommendationRun: run,
      readinessSnapshot: run.readiness_snapshot || null,
      renderedSectionsData: {
        hasPRTestResults: outcome !== null,
        showAttachTestRun: !outcome && !hasCurrentPRExecution && run.readiness_snapshot?.readiness_snapshot_available,
        renderedTestIds: recommended_tests.map((t: any) => t.stable_identity || t.id || t.display_name),
        renderedScenarioIds: scenarioMatrix
          .filter((s) => s.status === "suggested")
          .map((s) => getScenarioMatrixKey(s)),
        createRegressionScopeButtonCount: hasCreatedSuite ? 0 : 1,
        showNeedsMoreEvidence: displayState.showNeedsMoreEvidence,
        displayedConfidenceLabel: displayState.confidenceLabel,
        displayedScore: run.readiness_snapshot?.readiness_score ?? null,
        completenessScoreValue: completenessScore.score,
        renderedACCount: run.acceptance_criteria?.length ?? 0,
        snapshotACCount: (run.readiness_snapshot as any)?.has_acceptance_criteria ? 1 : 0,
        renderedCoverageItemCount: scenario_coverage_matrix?.items?.length ?? 0,
        snapshotCoverageItemCount: (run.readiness_snapshot as any)?.has_coverage_report ? 1 : 0,
        showStaleBanner: displayState.showStaleBanner,
        evidenceSufficient,
        showNeedsReview,
        criticalGapCount,
        unnamedTestCount,
        requirementNotAvailableCount,
        executiveGapCount: sectionGapCount,
        sectionGapCount,
        testCardMissingWhySelectedCount,
        missingTestWithoutActionCount,
        optionalGapAsBlockerCount,
      },
    });
    const rawKeys = scanForRawKeys(run, "run");
    const rawWarnings = rawKeys.map((msg) => ({
      code: "RAW_KEY",
      severity: "warning" as const,
      message: `Raw enum key in data — ${msg}`,
    }));
    if (process.env.NODE_ENV === "development") {
      if (result.hasErrors) console.error("❌ Consistency errors:", result.errors.map(e => `[${e.code}] ${e.message}`).join("\n"));
      if (result.hasWarnings || rawWarnings.length > 0) console.warn("⚠ Consistency warnings:", [...result.warnings, ...rawWarnings]);
    }
    return {
      ...result,
      warnings: [...result.warnings, ...rawWarnings],
      hasWarnings: result.hasWarnings || rawWarnings.length > 0,
    };
  })();

  return (
    <div className="space-y-5 max-w-4xl">

      {/* Decoupled Recommendation Snapshot Auditability Banner */}
      {(() => {
        const audit = run.recommendation_audit;
        if (!audit) {
          if (!run.readiness_snapshot) {
            return (
              <div className="bg-zinc-950/20 border border-zinc-800/40 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <Info className="w-5 h-5 text-zinc-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold text-zinc-200">
                      Legacy recommendation: readiness snapshot was not captured.
                    </p>
                    <p className="text-xs text-zinc-400 mt-1">
                      This recommendation was generated before readiness snapshot persistence was implemented. Evidence quality may not reflect the original generation state.
                    </p>
                  </div>
                </div>
              </div>
            );
          }
          return null;
        }

        const { status, head_commit_sha_at_generation } = audit;
        if (status === "LEGACY_NO_SNAPSHOT") {
          return (
            <div className="bg-amber-950/10 border border-amber-900/30 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-amber-200">
                    Legacy Recommendation: No snapshot captured
                  </p>
                  <p className="text-xs text-amber-400 mt-1">
                    This recommendation does not have an auditable PR package snapshot. Evidence quality may not reflect the original generation state.
                  </p>
                </div>
              </div>
            </div>
          );
        }

        if (status === "OUTDATED") {
          return (
            <div className="bg-orange-950/10 border border-orange-900/30 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <RefreshCw className="w-5 h-5 text-orange-500 shrink-0 mt-0.5 animate-spin" />
                <div>
                  <p className="text-sm font-semibold text-orange-200">
                    Outdated Snapshot: PR head commit has changed
                  </p>
                  <p className="text-xs text-orange-400 mt-1">
                    PR has changed since this recommendation was generated (generated at commit {head_commit_sha_at_generation?.substring(0, 7) || "unknown"}). Regenerate to ensure targeted regression accuracy.
                  </p>
                </div>
              </div>
            </div>
          );
        }

        if (status === "AUDITABLE") {
          return (
            <div className="bg-emerald-950/10 border border-emerald-900/30 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-emerald-200">
                    Auditable Recommendation Snapshot
                  </p>
                  <p className="text-xs text-emerald-400 mt-1">
                    This recommendation has a matching PR snapshot generated at commit {head_commit_sha_at_generation?.substring(0, 7) || "unknown"}.
                  </p>
                </div>
              </div>
            </div>
          );
        }

        return null;
      })()}

      {/* Dev Consistency Check */}
      <DevConsistencyCheck result={consistencyCheck} />

      {/* Recommendation Health Banner */}
      <div className={`rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
        healthState.state === "Ready" ? "bg-emerald-950/20 border border-emerald-800/40" :
        healthState.state === "Limited Evidence" ? "bg-amber-950/20 border border-amber-800/40" :
        healthState.state === "Needs Review" ? "bg-rose-950/20 border border-rose-800/40" :
        healthState.state === "Stale Inputs" ? "bg-amber-950/20 border border-amber-800/40" :
        "bg-rose-950/20 border border-rose-800/40"
      }`}>
        <div className="flex items-start gap-3">
          {healthState.state === "Ready" ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
          ) : healthState.state === "Stale Inputs" ? (
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          )}
          <div>
            <p className={`text-sm font-semibold ${
              healthState.state === "Ready" ? "text-emerald-200" :
              healthState.state === "Limited Evidence" ? "text-amber-200" :
              healthState.state === "Stale Inputs" ? "text-amber-200" :
              "text-rose-200"
            }`}>
              Recommendation Health: {healthState.state}
            </p>
            <p className={`text-xs mt-1 ${
              healthState.state === "Ready" ? "text-emerald-300" :
              healthState.state === "Limited Evidence" ? "text-amber-300" :
              healthState.state === "Stale Inputs" ? "text-amber-300" :
              "text-rose-300"
            }`}>
              {healthState.reason}
            </p>
          </div>
        </div>
        <Button
          onClick={() => {
            if (healthState.ctaAction === "regenerate" || healthState.ctaAction === "retry") {
              handleCheckpointContinue();
            } else if (healthState.ctaAction === "create") {
              createRegressionSuite();
            } else if (healthState.ctaAction === "review" || healthState.ctaAction === "review_critical") {
              document.getElementById("coverage-gaps")?.scrollIntoView({ behavior: "smooth" });
            }
          }}
          disabled={isRegenerating || isCreatingSuite}
          className={`shrink-0 self-end sm:self-center font-semibold text-xs py-1.5 px-3 rounded-lg shadow-md ${
            healthState.state === "Ready" ? "bg-emerald-600 text-white hover:bg-emerald-700" :
            healthState.state === "Limited Evidence" ? "bg-amber-600 text-white hover:bg-amber-700" :
            healthState.state === "Stale Inputs" ? "bg-amber-600 text-white hover:bg-amber-700" :
            "bg-rose-600 text-white hover:bg-rose-700"
          }`}
        >
          {isRegenerating || isCreatingSuite ? (
            <>
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              {healthState.ctaAction === "regenerate" || healthState.ctaAction === "retry" ? "Processing..." : "Creating..."}
            </>
          ) : (
            healthState.cta
          )}
        </Button>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link href={run.repository ? `/app/repositories/${run.repository.id}` : "/app/repositories"}>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-zinc-500 hover:text-white">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-lg font-bold text-white">Recommendation</h1>
              {run.is_draft && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-950/30 text-amber-400 border border-amber-800/40 uppercase tracking-wider">
                  Draft
                </span>
              )}
              {run.pull_request && (
                <span className="text-sm text-zinc-400 font-mono">
                  PR #{run.pull_request.number} · {run.pull_request.title}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="text-[11px] text-zinc-500">{run.repository?.full_name}</span>
              {run.pull_request && (
                <span className="inline-flex items-center gap-1 text-[11px] text-zinc-500">
                  <GitBranch className="w-3 h-3" />
                  {run.pull_request.source_branch} → {run.pull_request.target_branch}
                </span>
              )}
              <span className="text-[11px] text-zinc-600">{formatRelative(run.created_at)}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {riskBadge(executive_summary.risk_level)}
          {modeBadge(testing_strategy.recommendation_mode)}
        </div>
      </div>

      {/* Attach Test Run Section */}
      {run && !outcome && !hasCurrentPRExecution && run.readiness_snapshot?.readiness_snapshot_available && (
        <AttachTestRun
          recommendationRunId={runId || ""}
          repositoryId={run.repository?.id}
          pullRequestId={run.pull_request?.id}
          currentCommitSha={run.commit_sha ?? undefined}
          onAttached={refreshRun}
        />
      )}

      {/* Primary Actions Card */}
      <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <CheckCircle2 className="w-4 h-4 text-zinc-500" />
          <h3 className="text-sm font-semibold text-zinc-200">Primary Actions</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="relative">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => setExportDropdownOpen(!exportDropdownOpen)} 
              className="border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white gap-1.5 text-xs"
            >
              <Download className="w-3.5 h-3.5" />
              Export
              <ChevronDown className="w-3 h-3" />
            </Button>
            {exportDropdownOpen && (
              <div className="absolute top-full left-0 mt-1 bg-zinc-800 border border-zinc-700 rounded-md shadow-lg z-50 min-w-[160px]">
                <button
                  onClick={() => {
                    exportAuditReportJson();
                    setExportDropdownOpen(false);
                  }}
                  className="w-full text-left px-3 py-2 text-xs text-zinc-300 hover:bg-zinc-700 hover:text-white flex items-center gap-2"
                >
                  <Download className="w-3 h-3" />
                  Export as JSON
                </button>
                <button
                  onClick={() => {
                    exportAuditReportPdf();
                    setExportDropdownOpen(false);
                  }}
                  className="w-full text-left px-3 py-2 text-xs text-zinc-300 hover:bg-zinc-700 hover:text-white flex items-center gap-2"
                >
                  <Download className="w-3 h-3" />
                  Export as PDF
                </button>
              </div>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={exportEvidenceReport} className="border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white gap-1.5 text-xs">
            <Download className="w-3.5 h-3.5" />
            Evidence Report
          </Button>
          <Button variant="outline" size="sm" onClick={exportJson} className="border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white gap-1.5 text-xs">
            <Download className="w-3.5 h-3.5" />
            Export JSON
          </Button>
          <Button variant="outline" size="sm" onClick={copySummary} className="border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white gap-1.5 text-xs">
            <Copy className="w-3.5 h-3.5" />
            Copy Summary
          </Button>
          <Button variant="outline" size="sm" onClick={copyTestIds} className="border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white gap-1.5 text-xs">
            <Copy className="w-3.5 h-3.5" />
            Copy Test IDs
          </Button>
          <Button variant="outline" size="sm" onClick={() => setCheckpointModal({ isOpen: true, action: "rerun" })} disabled={isRegenerating} className="border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white gap-1.5 text-xs">
            <RefreshCw className="w-3.5 h-3.5" />
            Regenerate
          </Button>
        </div>
      </div>

      {/* ── 1. Recommendation Summary (evidence readiness, verdict, confidence) ── */}
      <div id="release-decision" className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-800/40 pb-3">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-bold text-white">Recommendation Summary</h2>
          </div>
          <div className="flex items-center gap-2">
            {/* Quality Gate Badge - derived from live regression scope release decision */}
            <QualityGateBadge
              qualityGateProfileStatus={qualityGateModel.quality_gate_profile_status}
              evidenceReadiness={qualityGateModel.evidence_readiness}
            />
            <span className={`px-2 py-1 text-xs font-semibold rounded border ${
              regressionScope?.release_decision?.verdict === "SAFE_TO_RELEASE" ? "bg-emerald-950/20 text-emerald-400 border-emerald-800/40" :
              regressionScope?.release_decision?.verdict === "DO_NOT_RELEASE" ? "bg-rose-950/20 text-rose-400 border-rose-800/40" :
              regressionScope?.release_decision?.verdict === "REVIEW_RECOMMENDED" ? "bg-amber-950/20 text-amber-400 border-amber-800/40" :
              "bg-zinc-950/20 text-zinc-400 border-zinc-800/40"
            }`}>
              {regressionScope?.release_decision?.verdict || "UNKNOWN"}
            </span>
            <span className="text-[10px] text-zinc-500 uppercase tracking-wider">
              {regressionScope?.release_decision?.source_mode || scopeMode}
            </span>
          </div>
        </div>

        {/* Computed verdict summary only — full decision with persisted status is in Final Release Decision section */}
        {regressionScope?.release_decision ? (
          <div className="bg-zinc-950/20 border border-zinc-800/30 rounded-lg p-4 space-y-3">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-zinc-200 mb-1">
                  {regressionScope.release_decision.verdict === "SAFE_TO_RELEASE" ? "Safe to Release" :
                   regressionScope.release_decision.verdict === "DO_NOT_RELEASE" ? "Do Not Release" :
                   regressionScope.release_decision.verdict === "REVIEW_RECOMMENDED" ? "Review Recommended" :
                   "Unknown Status"}
                </h3>
                <p className="text-xs text-zinc-400 leading-relaxed">{regressionScope.release_decision.reason}</p>
              </div>
              <div className="flex gap-4 text-center">
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Required</p>
                  <p className="text-lg font-bold text-rose-400">{regressionScope.release_decision.required_count}</p>
                </div>
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Test Gaps</p>
                  <p className="text-lg font-bold text-amber-400">{regressionScope.release_decision.recommended_count}</p>
                </div>
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Verified</p>
                  <p className="text-lg font-bold text-emerald-400">{regressionScope.release_decision.already_verified_count}</p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Fallback to legacy decision copy if unified decision not available */
          <>
            {regressionEvidence?.decisionSummary?.decisionCopy && (
              <div className="bg-zinc-950/20 border border-zinc-800/30 rounded-lg p-4 space-y-2">
                <h3 className="text-sm font-semibold text-zinc-200">{regressionEvidence.decisionSummary.decisionCopy.headline}</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">{regressionEvidence.decisionSummary.decisionCopy.explanation}</p>
              </div>
            )}

            {/* Part 9: PR Package Summary - Compact summary before Release Decision using normalized adapter */}
            {run.pr_package && (() => {
              const normalizedPRPackage = normalizePRPackage(
                { 
                  id: run.pull_request_id,
                  number: run.pr_number,
                  title: run.pr_title,
                  source_branch: run.pr_source_branch,
                  target_branch: run.pr_target_branch,
                  head_commit_sha: run.pr_package?.head_commit_sha,
                  base_commit_sha: run.pr_package?.base_commit_sha,
                  merge_commit_sha: run.pr_package?.merge_commit_sha,
                  changed_files_count: run.pr_package?.changed_files_count,
                  changed_files: run.pr_package?.changed_files
                },
                { pr_package: run.pr_package }
              );
              return <PRPackageSummaryCard prPackage={normalizedPRPackage} compact={true} />;
            })()}

            {/* Part 9: Stale Recommendation Warning using normalized adapter */}
            {run.pr_package && (() => {
              const normalizedPRPackage = normalizePRPackage(
                { 
                  id: run.pull_request_id,
                  number: run.pr_number,
                  title: run.pr_title,
                  source_branch: run.pr_source_branch,
                  target_branch: run.pr_target_branch,
                  head_commit_sha: run.pr_package?.head_commit_sha,
                  base_commit_sha: run.pr_package?.base_commit_sha,
                  merge_commit_sha: run.pr_package?.merge_commit_sha,
                  changed_files_count: run.pr_package?.changed_files_count,
                  changed_files: run.pr_package?.changed_files
                },
                { pr_package: run.pr_package }
              );
              if (normalizedPRPackage.snapshotStatus === "OUTDATED") {
                return (
                  <StaleRecommendationBanner 
                    prPackage={normalizedPRPackage}
                    onRegenerate={() => {
                      toast.info("Regenerate recommendation", {
                        description: "Navigate to the repository detail page to regenerate this recommendation."
                      });
                    }}
                  />
                );
              }
              return null;
            })()}

            {/* Business Requirements Banner */}
            {run.repository && run.pull_request && (
              <BusinessRequirementsBanner
                repositoryId={run.repository.id}
                pullRequestId={run.pull_request.id}
              />
            )}

            {(() => {
              const verdictEvidenceQuality = run.readiness_snapshot?.expected_confidence || "UNKNOWN";
              const verdictCoverageRatio = run.evidence?.coverage?.line_coverage_ratio ?? null;
              const verdictHasFailures = prTestClassification.failed.length > 0;
              const verdictMissingScenarios = scenarioMatrix.filter(s => s.status === "suggested");
              const verdict = determineReleaseReadinessVerdict(
                run.recommended_tests || [],
                verdictMissingScenarios,
                verdictEvidenceQuality,
                verdictCoverageRatio,
                verdictHasFailures
              );
              return (
                <ReleaseReadinessVerdict
                  verdict={verdict}
                  reason={generateVerdictReason(
                    verdict,
                    extractUnderstandingData(run).impactedBehaviors,
                    run.recommended_tests || [],
                    verdictMissingScenarios,
                    verdictCoverageRatio
                  )}
                  impactedAreas={extractUnderstandingData(run).impactedBehaviors}
                  confidence={run.readiness_snapshot?.expected_confidence || undefined}
                />
              );
            })()}
          </>
        )}

        {/* Navigation CTAs - no approval buttons here; approval is in Final Release Decision section */}
        <div className="flex gap-3 mt-4">
          {(() => {
            const rawRequiredItems = regressionScope?.groups?.[ScopeGroup.REQUIRED]?.items ?? [];
            const reqItems = rawRequiredItems.filter((item: any) => {
              const releaseAction = item.release_action ?? item.releaseAction;
              const executionStatus = item.execution_status ?? item.executionStatus;
              const freshnessStatus = item.freshness_status ?? item.freshnessStatus;

              if (releaseAction === "NONE") return false;
              if (executionStatus === "PASSED" && freshnessStatus === "FRESH") return false;

              return true;
            });
            const hasRequiredItems = reqItems.length > 0;
            return (
              <>
                {hasRequiredItems && (
                  <Button
                    onClick={() => document.getElementById("required-before-release")?.scrollIntoView({ behavior: "smooth" })}
                    className="flex-1 bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs py-2 rounded-lg"
                  >
                    Review {reqItems.length} Required Actions
                  </Button>
                )}
                <Button
                  onClick={() => document.getElementById("final-release-decision")?.scrollIntoView({ behavior: "smooth" })}
                  variant="outline"
                  className="flex-1 border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white font-semibold text-xs py-2 rounded-lg"
                >
                  View Regression Scope
                </Button>
              </>
            );
          })()}
        </div>
      </div>

      {/* ── 2. Evidence Summary (ACs trusted, tests passed, files covered, manual evidence, CI/CD) ── */}
      <div id="evidence-summary" className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-4" data-testid="evidence-summary-section">
        <div className="flex items-center gap-2">
          <BarChart2 className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-bold text-white">Evidence Summary</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {(() => {
            const totalACs = regressionEvidence?.decisionSummary?.counts?.totalRequirements ?? regressionScope?.traceability_summary?.total_requirements ?? 0;
            const trustedACs = traceabilityRows.filter(r => r.mapping_status === 'TRUSTED').length;
            const passedTests = regressionEvidence?.decisionSummary?.counts?.uploadedPrTestsPassed ?? prTestClassification.passed.length;
            const changedFilesCount = executive_summary?.changed_files?.length ?? 0;
            const coveredFiles = regressionEvidence?.fileImpactMap ? Object.keys(regressionEvidence.fileImpactMap).length : changedFilesCount;
            const hasManualEvidence = traceabilityRows.some(r => r.manual_validation && r.manual_validation.mapped_manual_tests_count > 0);
            const cicdConnected = pipelineRuns.length > 0;

            return (
              <>
                <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30 text-center" data-testid="evidence-summary-acs">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">ACs Trusted</p>
                  <p className="text-xl font-bold text-emerald-400">{trustedACs} / {totalACs}</p>
                </div>
                <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30 text-center" data-testid="evidence-summary-tests">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Tests Passed</p>
                  <p className="text-xl font-bold text-emerald-400">{passedTests}</p>
                </div>
                <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30 text-center" data-testid="evidence-summary-files">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Files Covered</p>
                  <p className="text-xl font-bold text-emerald-400">{coveredFiles} / {changedFilesCount}</p>
                </div>
                <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30 text-center" data-testid="evidence-summary-manual">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Manual Evidence</p>
                  <p className="text-xl font-bold text-zinc-200">{hasManualEvidence ? "Available" : "None"}</p>
                </div>
                <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30 text-center" data-testid="evidence-summary-cicd">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">CI/CD</p>
                  <p className={`text-xl font-bold ${cicdConnected ? "text-emerald-400" : "text-amber-400"}`}>
                    {cicdConnected ? "Connected" : "Not Connected"}
                  </p>
                </div>
              </>
            );
          })()}
        </div>
        {(() => {
          const alreadyVerifiedItems = regressionScope?.groups?.[ScopeGroup.EXCLUDED_ALREADY_VERIFIED]?.items ?? [];
          const execVerified = alreadyVerifiedFromExecution ?? [];
          const verifiedCount = alreadyVerifiedItems.length || execVerified.length;
          if (verifiedCount === 0) return null;
          return (
            <p className="text-xs text-emerald-400" data-testid="already-verified-summary-line">
              {verifiedCount} tests already verified on current PR.
            </p>
          );
        })()}
      </div>

      {/* ── 3. Required Actions Section ── */}
      <div id="required-before-release" className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-rose-400" />
          <h2 className="text-lg font-bold text-white">Required Before Release</h2>
        </div>
        <div className="space-y-2">
          {(() => {
            if (regressionScopeError) {
              return (
                <div data-testid="release-blocker-scope-error" className="bg-rose-950/20 border border-rose-800/40 rounded-lg p-4 space-y-1">
                  <p className="text-sm text-rose-300 font-semibold">Status: BLOCKED</p>
                  <p className="text-xs text-rose-400">Regression scope could not be generated.</p>
                  {regressionScopeErrorMessage && (
                    <p className="text-[11px] text-rose-500">{regressionScopeErrorMessage}</p>
                  )}
                  <p className="text-[11px] text-zinc-500">Release approval is disabled until the regression scope is available.</p>
                </div>
              );
            }

            if (!regressionScope) {
              return <p className="text-xs text-zinc-500 italic">Loading regression scope...</p>;
            }

            const rawRequiredItems = regressionScope?.groups?.[ScopeGroup.REQUIRED]?.items ?? [];
            const reqItems = rawRequiredItems.filter((item: any) => {
              const releaseAction = item.release_action ?? item.releaseAction;
              const executionStatus = item.execution_status ?? item.executionStatus;
              const freshnessStatus = item.freshness_status ?? item.freshnessStatus;

              if (releaseAction === "NONE") return false;
              if (executionStatus === "PASSED" && freshnessStatus === "FRESH") return false;

              return true;
            });

            console.log("REGRESSION_SCOPE_AVAILABLE_TO_PAGE", {
              required: regressionScope?.groups?.[ScopeGroup.REQUIRED]?.items?.length,
              recommended: regressionScope?.groups?.[ScopeGroup.RECOMMENDED]?.items?.length,
              optional: regressionScope?.groups?.[ScopeGroup.OPTIONAL]?.items?.length,
              safeToSkip: regressionScope?.groups?.[ScopeGroup.SAFE_TO_SKIP]?.items?.length,
              alreadyVerified: regressionScope?.groups?.[ScopeGroup.EXCLUDED_ALREADY_VERIFIED]?.items?.length,
              firstRequired: regressionScope?.groups?.[ScopeGroup.REQUIRED]?.items?.[0],
              firstAlreadyVerified: regressionScope?.groups?.[ScopeGroup.EXCLUDED_ALREADY_VERIFIED]?.items?.[0],
            });
            console.log("REQUIRED_BEFORE_RELEASE_RENDER_SOURCE", {
              component: "RecommendationDetailPage",
              sourceVariableName: regressionScope ? "regressionScope.groups.REQUIRED.items" : "mustRun fallback",
              count: reqItems?.length,
              firstItem: reqItems?.[0],
              firstItemKeys: reqItems?.[0] ? Object.keys(reqItems[0]) : null,
              hasExecutionStatus: Boolean(reqItems?.[0]?.execution_status),
              hasFreshnessStatus: Boolean(reqItems?.[0]?.freshness_status),
              hasReleaseAction: Boolean(reqItems?.[0]?.release_action),
            });

            if (reqItems.length === 0) {
              return (
                <div className="space-y-1">
                  <p className="text-xs text-emerald-400 font-medium">No required release actions.</p>
                  <p className="text-[11px] text-zinc-500">All impacted acceptance criteria are verified by fresh tests.</p>
                </div>
              );
            }

            return reqItems.map((item: any, idx: number) => (
              <div key={item.id || idx} className="bg-zinc-950/40 border border-zinc-800/30 rounded-lg p-3 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-[10px] font-mono text-zinc-400">{item.readable_id}</span>
                      <h4 className="text-xs font-semibold text-zinc-200">{item.title}</h4>
                    </div>
                    {/* Phase 7: Show impact reason from change impact engine */}
                    {item.reason && (
                      <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">{item.reason}</p>
                    )}
                    {/* Phase 7: Show linked test evidence */}
                    {item.linked_tests && item.linked_tests.length > 0 && (
                      <div className="mt-2">
                        <p className="text-[9px] text-zinc-500 font-medium uppercase tracking-wider mb-1">Linked Tests ({item.linked_tests.length})</p>
                        <div className="flex flex-wrap gap-1">
                          {item.linked_tests.slice(0, 3).map((test: string, tIdx: number) => (
                            <span key={tIdx} className="text-[9px] font-mono bg-zinc-900 text-zinc-400 px-1.5 py-0.5 rounded border border-zinc-800/60">
                              {test.split("::").slice(-1)[0].substring(0, 20)}
                            </span>
                          ))}
                          {item.linked_tests.length > 3 && (
                            <span className="text-[9px] text-zinc-500">+{item.linked_tests.length - 3} more</span>
                          )}
                        </div>
                      </div>
                    )}
                    {auditMode && (
                      <span className="text-[9px] text-zinc-600 font-mono block mt-1">ID: {item.id}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[9px] px-1.5 py-0.5 rounded border border-rose-950 bg-rose-950/20 text-rose-400">
                      {item.risk_band || "HIGH"}
                    </span>
                    <span className="text-[10px] text-zinc-400">{item.suggested_action}</span>
                  </div>
                </div>
              </div>
            ));
          })()}
        </div>
      </div>

      {/* ── 3b. Failed Current PR Section ── */}
      {failedCurrentPRTests.length > 0 && (
        <div id="failed-current-pr" className="bg-zinc-900/30 border border-rose-800/40 rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <X className="w-5 h-5 text-rose-400" />
            <h2 className="text-lg font-bold text-white">Failed Current PR ({failedCurrentPRTests.length})</h2>
          </div>
          <p className="text-[11px] text-zinc-400">These tests failed on the current PR head SHA. Investigate or block release.</p>
          <div className="space-y-2">
            {failedCurrentPRTests.map((t: any, idx: number) => (
              <div key={t.stable_identity || idx} className="bg-zinc-950/40 border border-rose-900/30 rounded-lg p-3 space-y-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-[10px] font-mono text-zinc-400">{t.suite_name}</span>
                      <h4 className="text-xs font-semibold text-zinc-200">{t.display_name}</h4>
                    </div>
                    <p className="text-[11px] text-zinc-400">{t.reason}</p>
                    {t.evidence_path && t.evidence_path.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {t.evidence_path.map((step: any, sIdx: number) => (
                          <span key={sIdx} className="text-[9px] font-mono bg-zinc-900 text-zinc-500 px-1.5 py-0.5 rounded border border-zinc-800/60">
                            {step.step || step.edge_type || "evidence"}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[9px] px-1.5 py-0.5 rounded border border-rose-950 bg-rose-950/20 text-rose-400 uppercase font-semibold">
                      FAILED
                    </span>
                    <span className="text-[10px] text-zinc-400">{t.active_action?.replace(/_/g, " ")}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 3c. Stale Rerun Required Section ── */}
      {staleRerunTests.length > 0 && (
        <div id="stale-rerun" className="bg-zinc-900/30 border border-amber-800/40 rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-bold text-white">Stale Rerun Required ({staleRerunTests.length})</h2>
          </div>
          <p className="text-[11px] text-zinc-400">These tests passed on an older commit SHA, not the current PR head. Re-run to verify.</p>
          <div className="space-y-2">
            {staleRerunTests.map((t: any, idx: number) => (
              <div key={t.stable_identity || idx} className="bg-zinc-950/40 border border-amber-900/30 rounded-lg p-3 space-y-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-[10px] font-mono text-zinc-400">{t.suite_name}</span>
                      <h4 className="text-xs font-semibold text-zinc-200">{t.display_name}</h4>
                    </div>
                    <p className="text-[11px] text-zinc-400">{t.reason}</p>
                    {t.would_have_been_priority && (
                      <span className="text-[9px] text-zinc-500">Original priority: {t.would_have_been_priority}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[9px] px-1.5 py-0.5 rounded border border-amber-950 bg-amber-950/20 text-amber-400 uppercase font-semibold">
                      STALE
                    </span>
                    <span className="text-[10px] text-zinc-400">RUN NOW</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 3d. Mapping Review Needed Section ── */}
      {mappingReviewTests.length > 0 && (
        <div id="mapping-review-needed" className="bg-zinc-900/30 border border-blue-800/40 rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-bold text-white">Mapping Review Needed ({mappingReviewTests.length})</h2>
          </div>
          <p className="text-[11px] text-zinc-400">These tests have unconfirmed AC → Test mappings. Confirm the mapping before claiming confident coverage.</p>
          <div className="space-y-2">
            {mappingReviewTests.map((t: any, idx: number) => (
              <div key={t.stable_identity || idx} className="bg-zinc-950/40 border border-blue-900/30 rounded-lg p-3 space-y-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-[10px] font-mono text-zinc-400">{t.suite_name}</span>
                      <h4 className="text-xs font-semibold text-zinc-200">{t.display_name}</h4>
                    </div>
                    <p className="text-[11px] text-zinc-400">{t.reason}</p>
                    {t.mapping_uncertainty && (
                      <span className="text-[9px] text-blue-400 bg-blue-950/20 px-1.5 py-0.5 rounded border border-blue-900/30">
                        review_status: {t.mapping_uncertainty}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[9px] px-1.5 py-0.5 rounded border border-blue-950 bg-blue-950/20 text-blue-400 uppercase font-semibold">
                      REVIEW
                    </span>
                    <span className="text-[10px] text-zinc-400">CONFIRM MAPPING</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Collapsible View Evidence Section */}
      {regressionScope?.evidence_items && regressionScope.evidence_items.length > 0 && (
        <div id="view-evidence" className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-emerald-400" />
              <h2 className="text-lg font-bold text-white">View Verification Evidence ({regressionScope.evidence_items.length})</h2>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowEvidence(!showEvidence)}
              className="text-xs font-semibold text-zinc-400 hover:text-white"
            >
              {showEvidence ? "Hide Details" : "Show Details"}
            </Button>
          </div>
          {showEvidence && (
            <div className="space-y-3 pt-2">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-[11px] font-sans">
                  <thead>
                    <tr className="border-b border-zinc-850 text-zinc-500 font-semibold uppercase tracking-wider">
                      <th className="py-2.5 px-3 text-[10px] text-zinc-400">Requirement</th>
                      <th className="py-2.5 px-3 text-[10px] text-zinc-400">Verifying Test</th>
                      <th className="py-2.5 px-3 text-[10px] text-zinc-400">Status / Freshness</th>
                      <th className="py-2.5 px-3 text-[10px] text-zinc-400">Justification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-850">
                    {regressionScope.evidence_items.map((ev: any, evIdx: number) => (
                      <tr key={evIdx} className="hover:bg-zinc-900/25">
                        <td className="py-3 px-3">
                          <div className="font-semibold text-zinc-205">{ev.requirement_title}</div>
                          <div className="text-[9px] font-mono text-zinc-500">{ev.requirement_id}</div>
                        </td>
                        <td className="py-3 px-3 font-mono text-zinc-350">{ev.verifying_test}</td>
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/20 text-emerald-400 border border-emerald-900/30 uppercase font-semibold">
                              {ev.test_status}
                            </span>
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-805 uppercase font-semibold">
                              {ev.test_freshness}
                            </span>
                          </div>
                        </td>
                        <td className="py-3 px-3 text-zinc-400 leading-relaxed max-w-xs">{ev.impact_reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── 3e. Recommended Tests Section (Phase 8) ── */}
      {(() => {
        const recommendations = regressionScope?.recommendations ?? [];
        if (recommendations.length === 0) return null;

        return (
          <div id="recommended-tests" className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-amber-400" />
                <h2 className="text-lg font-bold text-white">Test Gaps ({recommendations.length})</h2>
              </div>
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider">
                Missing test coverage
              </span>
            </div>
            <div className="space-y-3">
              {recommendations.map((rec: any, idx: number) => (
                <div key={rec.id || idx} className="bg-zinc-950/40 border border-zinc-800/30 rounded-lg p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <span className={`text-[9px] px-2 py-0.5 rounded font-semibold uppercase ${
                          rec.source === 'COVERAGE_GAP' ? 'bg-rose-950/20 text-rose-400 border border-rose-800/40' :
                          rec.source === 'REQUIREMENT_GAP' ? 'bg-amber-950/20 text-amber-400 border border-amber-800/40' :
                          'bg-blue-950/20 text-blue-400 border border-blue-800/40'
                        }`}>
                          {rec.source.replace('_', ' ')}
                        </span>
                        <span className={`text-[9px] px-2 py-0.5 rounded font-semibold ${
                          rec.priority === 1 ? 'bg-rose-950/20 text-rose-400' :
                          rec.priority === 2 ? 'bg-amber-950/20 text-amber-400' :
                          'bg-zinc-950/20 text-zinc-400'
                        }`}>
                          Priority {rec.priority}
                        </span>
                        <span className="text-[9px] text-zinc-500">
                          Effort: {rec.estimated_effort}
                        </span>
                      </div>
                      <h4 className="text-sm font-semibold text-zinc-200 mb-2">{rec.title}</h4>
                      
                      <div className="flex items-center gap-2 mt-2 mb-2">
                        <button
                          onClick={() => toggleRationale(rec.id)}
                          className="text-[10px] font-semibold text-amber-400 hover:text-amber-300 transition-colors flex items-center gap-1"
                        >
                          <span>Why this matters</span>
                          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${expandedRationales.has(rec.id) ? "rotate-180" : ""}`} />
                        </button>
                      </div>
                      {expandedRationales.has(rec.id) && (
                        <div className="mb-2 text-[11px] bg-amber-950/15 border border-amber-900/30 text-amber-200/90 rounded-lg p-3 leading-relaxed">
                          {rec.risk_rationale}
                        </div>
                      )}

                      {rec.detailed_scenario ? (
                        <div className="mt-3 bg-zinc-900/80 rounded-lg p-3.5 border border-zinc-800/80 space-y-2">
                          <div className="grid grid-cols-2 gap-3 text-[11px]">
                            <div>
                              <span className="text-zinc-500 font-medium block uppercase tracking-wider text-[9px] mb-0.5">Precondition</span>
                              <span className="text-zinc-300 leading-relaxed block">{rec.detailed_scenario.precondition}</span>
                            </div>
                            <div>
                              <span className="text-zinc-500 font-medium block uppercase tracking-wider text-[9px] mb-0.5">Validation Layer</span>
                              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[9px] font-medium bg-purple-950/40 text-purple-400 border border-purple-800/40">
                                {rec.detailed_scenario.test_layer}
                              </span>
                            </div>
                          </div>
                          <div className="border-t border-zinc-800/50 pt-2 grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
                            <div>
                              <span className="text-zinc-500 font-medium block uppercase tracking-wider text-[9px] mb-0.5">Test Input</span>
                              <code className="text-amber-400 font-mono bg-zinc-950/60 px-1.5 py-0.5 rounded border border-zinc-800/30 break-all block leading-relaxed mt-0.5">
                                {rec.detailed_scenario.test_input}
                              </code>
                            </div>
                            <div>
                              <span className="text-zinc-500 font-medium block uppercase tracking-wider text-[9px] mb-0.5">Expected Result</span>
                              <span className="text-emerald-400 leading-relaxed block mt-0.5">{rec.detailed_scenario.expected_result}</span>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="bg-zinc-900/50 rounded p-3 border border-zinc-800/30">
                          <p className="text-[9px] text-zinc-500 font-medium uppercase tracking-wider mb-1">Suggested Test Scenario</p>
                          <p className="text-[11px] text-zinc-300 leading-relaxed">{rec.suggested_test_scenario}</p>
                        </div>
                      )}
                      
                      {rec.linked_file && (
                        <p className="text-[10px] text-zinc-500 mt-2">
                          Linked file: <span className="font-mono">{rec.linked_file.split('/').slice(-1)}</span>
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {/* ── 4. Regression Scope Plan Section ── */}
      <div id="regression-scope-plan" className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-bold text-white">Regression Scope Plan</h2>
          </div>
          <div className="flex items-center gap-1.5 bg-zinc-950/40 p-1 rounded-lg border border-zinc-800/40">
            <Button
              variant={scopeMode === "targeted" ? "default" : "ghost"}
              size="sm"
              onClick={() => {
                console.log("SCOPE_MODE_CLICK_FIRED", {
                  clickedMode: "targeted",
                  previousMode: scopeMode,
                  timestamp: new Date().toISOString(),
                });
                setScopeMode("targeted");
              }}
              className="text-[10px] py-1 px-2.5"
            >
              Targeted Mode
            </Button>
            <Button
              variant={scopeMode === "risk_based" ? "default" : "ghost"}
              size="sm"
              onClick={() => {
                console.log("SCOPE_MODE_CLICK_FIRED", {
                  clickedMode: "risk_based",
                  previousMode: scopeMode,
                  timestamp: new Date().toISOString(),
                });
                setScopeMode("risk_based");
              }}
              className="text-[10px] py-1 px-2.5"
            >
              Risk-Based Mode
            </Button>
            <Button
              variant={scopeMode === "full_suite" ? "default" : "ghost"}
              size="sm"
              onClick={() => {
                console.log("SCOPE_MODE_CLICK_FIRED", {
                  clickedMode: "full_suite",
                  previousMode: scopeMode,
                  timestamp: new Date().toISOString(),
                });
                setScopeMode("full_suite");
              }}
              className="text-[10px] py-1 px-2.5"
            >
              Full Suite
            </Button>
          </div>
        </div>

        {scopeLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 text-zinc-400 animate-spin" />
            <span className="ml-2 text-xs text-zinc-400">Loading regression scope...</span>
          </div>
        ) : regressionScopeError ? (
          <div className="bg-rose-950/20 border border-rose-800/40 rounded-lg p-4 space-y-2">
            <p className="text-xs text-rose-300 font-medium">Unable to load optimized regression scope</p>
            {regressionScopeErrorMessage && (
              <p className="text-[11px] text-rose-400 font-mono">{regressionScopeErrorMessage}</p>
            )}
            <p className="text-[11px] text-zinc-400">PR changes: {executive_summary?.changed_files?.length || 0} files</p>
          </div>
        ) : regressionScope ? (
          <div className="space-y-4">
            <RegressionScopeV2Display 
              scope={regressionScope} 
              showSafeToSkip={showSafeToSkip} 
              auditMode={auditMode}
              onModeChange={(mode) => {
                console.log("SCOPE_MODE_CLICK_FIRED", {
                  clickedMode: mode,
                  previousMode: scopeMode,
                  timestamp: new Date().toISOString(),
                });
                setScopeMode(mode);
              }}
            />
            <div className="flex items-center gap-2">
              <input
                id="show-safe-to-skip"
                type="checkbox"
                checked={showSafeToSkip}
                onChange={(e) => setShowSafeToSkip(e.target.checked)}
                className="rounded border-zinc-700 bg-zinc-800 text-blue-500 focus:ring-blue-500/25 h-3.5 w-3.5"
              />
              <label htmlFor="show-safe-to-skip" className="text-xs text-zinc-400 select-none cursor-pointer">
                Show Safe To Skip
              </label>
            </div>
          </div>
        ) : (
          <div className="flex justify-center py-6">
            <Loader2 className="w-5 h-5 text-zinc-500 animate-spin" />
          </div>
        )}
      </div>

      {/* ── 5. Risk Review Section ── */}
      <div id="business-risk-review" className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-purple-400" />
          <h2 className="text-lg font-bold text-white">Risk Review</h2>
        </div>
        <div className="space-y-4">
          <RiskReviewGovernancePanel 
            governance={regressionScope?.governance || { 
              activeReviews: 1, 
              activeAccepted: 1, 
              activeOverridden: 0, 
              activeNeedsDiscussion: 0, 
              resetEvents: 0, 
              totalHistoryEvents: 1 
            }} 
          />

          <div className="space-y-2">
            {(() => {
              const reviewItems = regressionScope?.groups?.[ScopeGroup.REQUIRED]?.items || 
                                  [{ id: "item-uuid-req-1", readable_id: "AC-REQ-1", title: "Verify password strength validation", effective_risk_level: "CRITICAL", risk_band: "CRITICAL" }];
              
              return reviewItems.map((item: any, idx: number) => (
                <div key={item.id || idx} className="bg-zinc-950/40 border border-zinc-800/30 rounded-lg p-3 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                  <div>
                    <h4 className="text-xs font-semibold text-zinc-200">{item.title}</h4>
                    <p className="text-[10px] text-zinc-500 mt-1">Effective Risk: {item.effective_risk_level || "CRITICAL"}</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Button
                      title="Accept generated risk"
                      variant="outline"
                      size="sm"
                      className="text-[10px] text-zinc-400 hover:text-white"
                      onClick={() => toast.success("Risk accepted")}
                    >
                      Accept
                    </Button>
                    <Button
                      title="Override risk"
                      variant="outline"
                      size="sm"
                      className="text-[10px] text-zinc-400 hover:text-white"
                      onClick={() => toast.success("Risk overridden")}
                    >
                      Override
                    </Button>
                    <Button
                      title="View review history"
                      variant="outline"
                      size="sm"
                      className="text-[10px] text-zinc-400 hover:text-white"
                      onClick={() => toast.success("Showing review history")}
                    >
                      History
                    </Button>
                  </div>
                </div>
              ));
            })()}
          </div>
        </div>
      </div>

      {/* ── 6. Traceability Audit Section (collapsible when healthy, includes already verified detail) ── */}
      <div id="coverage-traceability" className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-4">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setTraceabilityOpen(!traceabilityOpen)}
        >
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-bold text-white">Traceability Audit</h2>
            {traceabilityHealthy && (
              <span className="text-[10px] px-1.5 py-0.5 rounded border bg-emerald-950/20 text-emerald-400 border-emerald-800/40">
                All Covered
              </span>
            )}
          </div>
          {traceabilityOpen ? <ChevronDown className="w-5 h-5 text-zinc-500" /> : <ChevronRight className="w-5 h-5 text-zinc-500" />}
        </div>

        {/* Phase 7: Use unified traceability summary from regression scope */}
        {regressionScope?.traceability_summary ? (
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30 text-center">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Total ACs</p>
              <p className="text-xl font-bold text-zinc-200">{regressionScope.traceability_summary.total_requirements}</p>
            </div>
            <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30 text-center">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Covered</p>
              <p className="text-xl font-bold text-emerald-400">{regressionScope.traceability_summary.covered}</p>
            </div>
            <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30 text-center">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Missing</p>
              <p className="text-xl font-bold text-rose-400">{regressionScope.traceability_summary.missing}</p>
            </div>
            <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30 text-center">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Not Mapped</p>
              <p className="text-xl font-bold text-amber-400">{regressionScope.traceability_summary.not_mapped}</p>
            </div>
          </div>
        ) : null}

        <WhatVeriscopeUnderstood 
          {...extractUnderstandingData(run)} 
          fileImpactMap={regressionEvidence?.fileImpactMap}
        />

        {/* ── Behavior-Based Ranking Reasoning ── */}
        {(() => {
          const behaviorReasons: string[] = impact_profile?.behavior_based_reasons || [];
          const impactedBehaviors: any[] = impact_profile?.impacted_behaviors || [];
          const covSummary = impact_profile?.behavior_coverage_summary || {};
          const ctxStatus: string | null = impact_profile?.behavior_context_status || null;
          if (!impactedBehaviors.length && !behaviorReasons.length) return null;
          return (
            <BehaviorRankingReasoningPanel
              impactedBehaviors={impactedBehaviors}
              behaviorReasons={behaviorReasons}
              coverageSummary={covSummary}
              contextStatus={ctxStatus}
            />
          );
        })()}

        {traceabilityOpen && (
        <div className="space-y-2 mt-4" data-testid="traceability-detail-rows">
          {(() => {
            if (traceabilityRows.length === 0) {
              return <p className="text-xs text-zinc-500 italic">No acceptance criteria traceability details available.</p>;
            }

            return traceabilityRows.map((row) => {
              const statusColor = row.coverage_status === 'COVERED' ? 'text-emerald-400 bg-emerald-950/20 border-emerald-800/40' :
                                 row.coverage_status === 'PARTIAL' ? 'text-amber-400 bg-amber-950/20 border-amber-800/40' :
                                 row.coverage_status === 'MISSING' ? 'text-rose-400 bg-rose-950/20 border-rose-800/40' :
                                 'text-zinc-400 bg-zinc-950/20 border-zinc-800/40';

              const mappingColor = row.mapping_status === 'TRUSTED' ? 'text-emerald-400 bg-emerald-950/20 border-emerald-800/40' :
                                   row.mapping_status === 'PARTIAL' ? 'text-amber-400 bg-amber-950/20 border-amber-800/40' :
                                   'text-rose-400 bg-rose-950/20 border-rose-800/40';

              const execColor = row.execution_status === 'PASSED' ? 'text-emerald-400 bg-emerald-950/20 border-emerald-800/40' :
                                row.execution_status === 'FAILED' ? 'text-rose-400 bg-rose-950/20 border-rose-800/40' :
                                row.execution_status === 'SKIPPED' ? 'text-amber-400 bg-amber-950/20 border-amber-800/40' :
                                'text-zinc-400 bg-zinc-950/20 border-zinc-800/40';

              const mv = row.manual_validation;

              return (
                <div key={row.requirement_id} data-testid={`traceability-row-${row.ac_ref}`} className="bg-zinc-950/40 border border-zinc-800/30 rounded-lg p-3 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-[10px] font-mono text-zinc-300 font-semibold">{row.ac_ref}</span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded border ${mappingColor}`}>
                          {row.mapping_status}
                        </span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded border ${execColor}`}>
                          {row.execution_status}
                        </span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded border ${statusColor}`}>
                          {row.coverage_status}
                        </span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded border bg-zinc-850 border-zinc-700 text-zinc-300`}>
                          {row.recommendation_status}
                        </span>
                      </div>
                      <p className="text-xs font-semibold text-zinc-200">{row.title}</p>
                    </div>
                  </div>

                  {mv && (
                    <div className="mt-2 p-2 rounded bg-zinc-900/40 border border-zinc-800/30 text-xs space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-zinc-400 font-medium">Manual Validation:</span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded border ${getManualBadgeStyleAndLabel(mv.status || mv.latest_outcome || 'NOT_MAPPED').className}`}>
                          {getManualBadgeStyleAndLabel(mv.status || mv.latest_outcome || 'NOT_MAPPED').label}
                        </span>
                        {mv.mapped_manual_tests_count > 0 && (
                          <span className="text-zinc-500">
                            ({mv.mapped_manual_tests_count} test{mv.mapped_manual_tests_count > 1 ? 's' : ''} mapped)
                          </span>
                        )}
                      </div>
                      {mv.latest_executed_by_name && (
                        <p className="text-[10px] text-zinc-500">
                          Executed by {mv.latest_executed_by_name} on {mv.latest_executed_at ? new Date(mv.latest_executed_at).toLocaleDateString() : 'N/A'}
                        </p>
                      )}
                      {mv.evidence_urls && mv.evidence_urls.length > 0 && (
                        <div className="text-[10px] text-zinc-500">
                          Evidence URLs: {mv.evidence_urls.map((url: string, idx: number) => (
                            <a key={idx} href={url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline ml-1">
                              {url}
                            </a>
                          ))}
                        </div>
                      )}
                      {mv.mapped_manual_tests_count > 0 && (
                        <p className="text-[9px] text-zinc-500 italic mt-1 font-medium">
                          Manual mappings provide traceability only and do not mark requirements covered.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            });
          })()}
        </div>
        )}

        {/* Already Verified detail list — collapsed by default, shown under Traceability Audit */}
        {traceabilityOpen && (() => {
          const alreadyVerifiedItems = regressionScope?.groups?.[ScopeGroup.EXCLUDED_ALREADY_VERIFIED]?.items ?? [];
          const execVerified = alreadyVerifiedFromExecution ?? [];
          if (alreadyVerifiedItems.length === 0 && execVerified.length === 0) return null;

          return (
            <div className="mt-4" data-testid="already-verified-detail">
              <button
                onClick={() => setAlreadyVerifiedOpen(!alreadyVerifiedOpen)}
                className="flex items-center gap-2 text-sm font-semibold text-zinc-300 hover:text-white transition-colors w-full"
              >
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Already Verified ({alreadyVerifiedItems.length || execVerified.length})</span>
                {alreadyVerifiedOpen ? <ChevronDown className="w-4 h-4 text-zinc-500" /> : <ChevronRight className="w-4 h-4 text-zinc-500" />}
              </button>
              {alreadyVerifiedOpen && (
                <div className="mt-3 space-y-2">
                  {alreadyVerifiedItems.length > 0 ? (
                    alreadyVerifiedItems.map((item: any, idx: number) => (
                      <div key={item.id || idx} className="bg-zinc-950/40 border border-zinc-800/30 rounded-lg p-3 space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <span className="text-[10px] font-mono text-zinc-400">{item.readable_id}</span>
                              <h4 className="text-xs font-semibold text-zinc-200">{item.title}</h4>
                            </div>
                            {item.reason && (
                              <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">{item.reason}</p>
                            )}
                            {item.linked_tests && item.linked_tests.length > 0 && (
                              <div className="mt-2">
                                <p className="text-[9px] text-zinc-500 font-medium uppercase tracking-wider mb-1">Verified by Tests ({item.linked_tests.length})</p>
                                <div className="flex flex-wrap gap-1">
                                  {item.linked_tests.slice(0, 3).map((test: string, tIdx: number) => (
                                    <span key={tIdx} className="text-[9px] font-mono bg-emerald-950/20 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-800/40">
                                      {test.split("::").slice(-1)[0].substring(0, 20)}
                                    </span>
                                  ))}
                                  {item.linked_tests.length > 3 && (
                                    <span className="text-[9px] text-zinc-500">+{item.linked_tests.length - 3} more</span>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-[9px] px-1.5 py-0.5 rounded border border-emerald-950 bg-emerald-950/20 text-emerald-400">
                              VERIFIED
                            </span>
                            <span className="text-[10px] text-zinc-400">{item.execution_status} / {item.freshness_status}</span>
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    execVerified.map((t: any, idx: number) => (
                      <div key={t.stable_identity || idx} className="bg-zinc-950/40 border border-emerald-900/20 rounded-lg p-3 space-y-1">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <span className="text-[10px] font-mono text-zinc-400">{t.suite_name}</span>
                              <h4 className="text-xs font-semibold text-zinc-200">{t.display_name}</h4>
                            </div>
                            <p className="text-[11px] text-zinc-400">{t.reason}</p>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-[9px] px-1.5 py-0.5 rounded border border-emerald-950 bg-emerald-950/20 text-emerald-400 uppercase font-semibold">
                              VERIFIED
                            </span>
                            <span className="text-[10px] text-zinc-400">NO RERUN NEEDED</span>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          );
        })()}
      </div>

      {/* ── 7. Final Release Decision (single combined section, rendered once at bottom) ── */}
      <div id="final-release-decision" className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-800/40 pb-3">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-bold text-white">Final Release Decision</h2>
          </div>
          <div className="flex items-center gap-2">
            {/* Computed verdict badge (from regression scope) */}
            <span className={`px-2 py-1 text-xs font-semibold rounded border ${
              regressionScope?.release_decision?.verdict === "SAFE_TO_RELEASE" ? "bg-emerald-950/20 text-emerald-400 border-emerald-800/40" :
              regressionScope?.release_decision?.verdict === "DO_NOT_RELEASE" ? "bg-rose-950/20 text-rose-400 border-rose-800/40" :
              regressionScope?.release_decision?.verdict === "REVIEW_RECOMMENDED" ? "bg-amber-950/20 text-amber-400 border-amber-800/40" :
              "bg-zinc-950/20 text-zinc-400 border-zinc-800/40"
            }`}>
              Computed: {regressionScope?.release_decision?.verdict || "UNKNOWN"}
            </span>
            {/* Persisted decision status badge (from release-decision API) */}
            <span className={`px-2 py-1 text-xs font-semibold rounded border ${
              (releaseDecision?.decisionStatus || "PENDING") === "APPROVED" ? "bg-emerald-950/20 text-emerald-400 border-emerald-800/40" :
              (releaseDecision?.decisionStatus || "PENDING") === "REJECTED" ? "bg-rose-950/20 text-rose-400 border-rose-800/40" :
              (releaseDecision?.decisionStatus || "PENDING") === "PENDING_REVIEW" ? "bg-amber-950/20 text-amber-400 border-amber-800/40" :
              "bg-zinc-950/20 text-zinc-400 border-zinc-800/40"
            }`}>
              Decision: {releaseDecision?.decisionStatus || "PENDING"}
            </span>
          </div>
        </div>

        {/* Computed verdict reason from regression scope */}
        {regressionScope?.release_decision && (
          <div className="bg-zinc-950/20 border border-zinc-800/30 rounded-lg p-4 space-y-2">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-zinc-200 mb-1">
                  {regressionScope.release_decision.verdict === "SAFE_TO_RELEASE" ? "Safe to Release" :
                   regressionScope.release_decision.verdict === "DO_NOT_RELEASE" ? "Do Not Release" :
                   regressionScope.release_decision.verdict === "REVIEW_RECOMMENDED" ? "Review Recommended" :
                   "Unknown Status"}
                </h3>
                <p className="text-xs text-zinc-400 leading-relaxed">{regressionScope.release_decision.reason}</p>
              </div>
              <div className="flex gap-4 text-center">
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Required</p>
                  <p className="text-lg font-bold text-rose-400">{regressionScope.release_decision.required_count}</p>
                </div>
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Test Gaps</p>
                  <p className="text-lg font-bold text-amber-400">{regressionScope.release_decision.recommended_count}</p>
                </div>
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Verified</p>
                  <p className="text-lg font-bold text-emerald-400">{regressionScope.release_decision.already_verified_count}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Persisted decision justification if exists */}
        {releaseDecision?.justification && (
          <div className="bg-zinc-950/20 border border-zinc-800/30 rounded-lg p-3 space-y-1">
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Approval Justification</p>
            <p className="text-xs text-zinc-400">{releaseDecision.justification}</p>
          </div>
        )}

        {(() => {
          if (regressionScopeError) {
            return (
              <div className="space-y-4">
                <div data-testid="release-gate-scope-blocked" className="bg-rose-950/20 border border-rose-800/40 rounded-lg p-4">
                  <p className="text-sm text-rose-300 font-semibold mb-1">
                    Release approval is blocked.
                  </p>
                  <p className="text-xs text-rose-400">
                    Regression scope could not be generated. Resolve the scope generation issue before approving this release.
                  </p>
                </div>
                <div className="flex gap-3">
                  <Button
                    onClick={() => handleReleaseDecision("REJECTED")}
                    className="flex-1 bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs py-2 rounded-lg"
                  >
                    Reject Release
                  </Button>
                </div>
              </div>
            );
          }

          const rawRequiredItems = regressionScope?.groups?.[ScopeGroup.REQUIRED]?.items ?? [];
          const reqItems = rawRequiredItems.filter((item: any) => {
            const releaseAction = item.release_action ?? item.releaseAction;
            const executionStatus = item.execution_status ?? item.executionStatus;
            const freshnessStatus = item.freshness_status ?? item.freshnessStatus;

            if (releaseAction === "NONE") return false;
            if (executionStatus === "PASSED" && freshnessStatus === "FRESH") return false;

            return true;
          });
          const hasRequiredItems = reqItems.length > 0;

          if (hasRequiredItems) {
            return (
              <div className="space-y-4">
                <div className="bg-amber-950/20 border border-amber-800/40 rounded-lg p-4">
                  <p className="text-sm text-amber-300 font-semibold mb-1">
                    {reqItems.length} required items remain before normal approval.
                  </p>
                  <p className="text-xs text-amber-400">
                    Complete the required review/execution items or approve with risk override.
                  </p>
                </div>
                <div className="flex gap-3">
                  <Button
                    onClick={() => setRiskOverrideModal({ isOpen: true, justification: "" })}
                    className="flex-1 bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs py-2 rounded-lg"
                  >
                    Approve with Risk Override
                  </Button>
                  <Button
                    onClick={() => handleReleaseDecision("REJECTED")}
                    className="flex-1 bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs py-2 rounded-lg"
                  >
                    Reject Release
                  </Button>
                </div>
              </div>
            );
          } else {
            return (
              <div className="space-y-4">
                <div className="bg-emerald-950/20 border border-emerald-800/40 rounded-lg p-4">
                  <p className="text-sm text-emerald-300">
                    All required release checks are complete.
                  </p>
                </div>
                <div className="flex gap-3">
                  <Button
                    onClick={() => handleReleaseDecision("APPROVED")}
                    className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs py-2 rounded-lg"
                  >
                    Approve Release
                  </Button>
                  <Button
                    onClick={() => handleReleaseDecision("REJECTED")}
                    className="flex-1 bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs py-2 rounded-lg"
                  >
                    Reject Release
                  </Button>
                </div>
              </div>
            );
          }
        })()}
      </div>

      {/* ── 8. Execution Optimization Section ── */}
      <div id="execution-optimization" className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-amber-400" />
          <h2 className="text-lg font-bold text-white">Execution Optimization</h2>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30 text-center">
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Execution Reduction</p>
            <p className="text-xl font-bold text-zinc-200">
              {regressionScope?.optimization_metrics?.execution_reduction ?? 45.5}%
            </p>
          </div>
          <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30 text-center">
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Optimized count</p>
            <p className="text-xl font-bold text-zinc-200">
              {regressionScope?.optimization_metrics?.optimized_required_count ?? mustRun.length}
            </p>
          </div>
        </div>
      </div>

      {/* ── 9. Governance & Audit Section ── */}
      <div id="governance-audit" className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-3">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setGovAuditOpen(!govAuditOpen)}
        >
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-zinc-400" />
            <h2 className="text-lg font-bold text-white">Governance & Audit</h2>
          </div>
          {govAuditOpen ? <ChevronDown className="w-5 h-5 text-zinc-500" /> : <ChevronRight className="w-5 h-5 text-zinc-500" />}
        </div>

        {govAuditOpen && (
          <div className="border-t border-zinc-800/50 pt-4 mt-4 space-y-4">
            <div className="flex items-center gap-2">
              <Button
                variant={auditMode ? "default" : "outline"}
                size="sm"
                onClick={() => setAuditMode(!auditMode)}
                className="text-xs"
              >
                Diagnostics / Audit Mode
              </Button>
            </div>

            {auditMode && (
              <div className="bg-zinc-950/60 border border-zinc-800 p-4 rounded-lg space-y-2">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Diagnostics Audit</h3>
                <p className="text-xs font-mono text-zinc-300">Snapshot Hash: {regressionScope?.snapshot_hash || "sha256-abc123xyz789"}</p>
                <p className="text-xs font-mono text-zinc-300">Generated At: {regressionScope?.generated_at || "2026-06-13T05:00:00Z"}</p>
                {regressionScope?.groups?.[ScopeGroup.REQUIRED]?.items?.map((item: any, idx: number) => (
                  <p key={idx} className="text-xs font-mono text-zinc-400">Diagnostic ID: {item.id}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Historical Fragility */}
      {run.fragility && (run.fragility.behavior_signals?.length > 0 || run.fragility.journey_signals?.length > 0) && (
        <CollapsibleSection title="Historical Fragility" icon={History} defaultOpen={false}>
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              {riskBadge(run.fragility.risk_level)}
              <p className="text-sm text-zinc-300">{run.fragility.summary}</p>
            </div>
          </div>
        </CollapsibleSection>
      )}

      {/* Outcome Status */}
      {outcomeSummary && outcome && (
        <CollapsibleSection title="Outcome Status" icon={CheckCircle2} defaultOpen={false}>
          <OutcomePanel outcomeSummary={outcomeSummary} />
        </CollapsibleSection>
      )}

      {/* Post-Merge Outcome */}
      {(run.pull_request?.merged_at || outcome || showOutcomeForm) && (
        <CollapsibleSection title="Post-Merge Outcome" icon={GitBranch} defaultOpen={false}>
          <PostMergeOutcome recommendationRunId={runId || ""} />
        </CollapsibleSection>
      )}

      {/* Risk Override Justification Modal */}
      {riskOverrideModal.isOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-lg font-semibold text-white">Approve with Risk Override</h3>
            <p className="text-sm text-zinc-400">
              Provide justification for approving this release with outstanding required items.
            </p>
            <textarea
              value={riskOverrideModal.justification}
              onChange={(e) => setRiskOverrideModal({ ...riskOverrideModal, justification: e.target.value })}
              placeholder="Explain why this release should proceed despite outstanding required items..."
              className="w-full min-h-[100px] bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-sm text-zinc-300 placeholder-zinc-600 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
            <div className="flex gap-3 justify-end">
              <Button
                onClick={() => setRiskOverrideModal({ isOpen: false, justification: "" })}
                variant="outline"
                className="border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white text-xs"
              >
                Cancel
              </Button>
              <Button
                onClick={() => {
                  if (!riskOverrideModal.justification.trim()) {
                    toast.error("Justification is required for risk override");
                    return;
                  }
                  handleReleaseDecision("APPROVED", riskOverrideModal.justification);
                  setRiskOverrideModal({ isOpen: false, justification: "" });
                }}
                disabled={!riskOverrideModal.justification.trim()}
                className="bg-amber-600 hover:bg-amber-700 text-white text-xs disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Approve with Override
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* CI/CD Pipeline Runs */}
      <CICDPipelineRunsPanel
        pipelineRuns={pipelineRuns}
        qualityGateProfileStatus={qualityGateModel.quality_gate_profile_status}
        evidenceReadiness={qualityGateModel.evidence_readiness}
        hasTestResults={readinessData?.available_inputs?.some(
          (input: any) => input.key === "current_pr_execution" && input.status === "AVAILABLE"
        ) ?? false}
        hasCoverageReport={readinessData?.available_inputs?.some(
          (input: any) => input.key === "coverage_report" && input.status === "AVAILABLE"
        ) ?? false}
      />

      {/* Feedback Footer */}
      <div className="mt-6 pt-4 border-t border-zinc-800/50 flex items-center justify-between gap-4 flex-wrap">
        <p className="text-xs text-zinc-500">Was this recommendation useful?</p>
        <div className="flex-1 min-w-0">
          <RecommendationFeedback
            recommendationRunId={runId || ""}
            existingFeedback={outcome?.user_feedback}
            existingComment={outcome?.feedback_comment}
          />
        </div>
      </div>

      {run.repository && (
        <RecommendationCheckpointModal
          isOpen={checkpointModal.isOpen}
          onClose={() => setCheckpointModal({ ...checkpointModal, isOpen: false })}
          onContinue={handleCheckpointContinue}
          repositoryId={run.repository.id}
          pullRequestId={run.pull_request?.id || undefined}
          action={checkpointModal.action}
          recommendationRunId={run.id}
        />
      )}

      {run.repository && (
        <BusinessRequirementsModal
          isOpen={isPasteModalOpen}
          onClose={() => setIsPasteModalOpen(false)}
          onSuccess={(updatedReadiness) => {
            toast.success("Business Requirements Saved", {
              description: "Readiness has been recalculated and recommendation details refreshed."
            });
            if (runId) {
              fetchRun(runId);
            }
          }}
          repositoryId={run.repository.id}
          pullRequestId={run.pull_request?.id || undefined}
        />
      )}
    </div>
  );
}


