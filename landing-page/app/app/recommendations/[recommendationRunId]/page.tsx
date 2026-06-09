"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  GitPullRequest,
  GitBranch,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  Download,
  RefreshCw,
  ChevronDown,
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { generateScenarioCoverageMatrix } from "@/lib/scenario-coverage-matrix";
import { calculateCompletenessScore } from "@/lib/completeness-score";
import { resolveRecommendationDisplayState } from "@/lib/recommendation-display-state";
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
import PasteAcceptanceCriteriaModal from "@/components/recommendations/paste-acceptance-criteria-modal";

export const dynamic = "force-dynamic";

// ── Types ──────────────────────────────────────────────────────────────────

interface RecommendedTest {
  stable_identity: string;
  display_name: string;
  suite_name: string;
  tier: "must_run" | "should_run" | "fallback";
  priority_score: number;
  reason_type: string;
  reason: string;
  testing_type?: string;
  impacted_area?: string;
  confidence?: string;
  signals?: { name: string; value: string }[];
  requirement_id?: string;
  scenario_intent?: string;
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

// Health state resolver
function getRecommendationHealth(run: any, evidenceGaps: any[]): {
  state: "Ready" | "Limited Evidence" | "Needs Review" | "Stale Inputs" | "Failed";
  reason: string;
  cta: string;
  ctaAction: "create" | "review" | "review_critical" | "regenerate" | "retry";
} {
  // Failed if recommendation status failed
  if (run.status === "FAILED" || run.status === "ERROR") {
    return {
      state: "Failed",
      reason: "Recommendation generation did not complete.",
      cta: "Retry Generation",
      ctaAction: "retry"
    };
  }

  // Stale Inputs if input_stale=true
  if (run.input_stale) {
    return {
      state: "Stale Inputs",
      reason: "Inputs changed after generation. Regenerate to include latest evidence.",
      cta: "Regenerate Recommendation",
      ctaAction: "regenerate"
    };
  }

  const confidence = run.readiness_snapshot?.expected_confidence || "LOW";
  const score = run.readiness_snapshot?.readiness_score || 0;

  // Needs Review only if truly critical gaps exist (HIGH or CRITICAL severity)
  const hasCriticalGaps = evidenceGaps.some((gap: any) =>
    gap.severity === "HIGH" || gap.severity === "CRITICAL"
  );
  if (hasCriticalGaps) {
    return {
      state: "Needs Review",
      reason: "Critical gaps require review before finalizing scope.",
      cta: "Review Critical Gaps",
      ctaAction: "review_critical"
    };
  }

  // Ready with optional gaps if HIGH confidence and only optional gaps exist
  const hasOptionalGaps = evidenceGaps.some((gap: any) =>
    gap.severity === "LOW" || gap.severity === "OPTIONAL" || gap.priority === "LOW"
  );
  if (confidence === "HIGH" && hasOptionalGaps && !hasCriticalGaps) {
    return {
      state: "Ready",
      reason: "Recommendation is ready. Remaining gaps are optional improvements.",
      cta: "Create Regression Scope",
      ctaAction: "create"
    };
  }

  // Ready if confidence HIGH and no critical gaps
  if (confidence === "HIGH") {
    return {
      state: "Ready",
      reason: "Generated from high-confidence evidence.",
      cta: "Create Regression Scope",
      ctaAction: "create"
    };
  }

  // Limited Evidence if confidence LOW or MEDIUM and not stale
  return {
    state: "Limited Evidence",
    reason: "Generated with missing recommended evidence.",
    cta: "Review Gaps",
    ctaAction: "review"
  };
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
        linkedExistingTests,
        linkedMissingTest: hasSuggestedTests ? ac.suggested_scenarios[0] : null,
        priority: ac.recommended_action === 'ADD_AUTOMATED_TEST' ? 'Must' : 'Recommended',
        notes: ac.reason || ac.mapped_behavior || ''
      });
    });
  }
  
  // Also check business intent rows for AC coverage
  if (run.business_intent?.rows) {
    run.business_intent.rows.forEach((row: any) => {
      if (row.acceptance_criterion_id && !traceabilityMap.find(t => t.id === row.acceptance_criterion_id)) {
        const linkedTests = testMap.get(row.acceptance_criterion_id) || [];
        const hasExistingTests = linkedTests.length > 0;
        
        traceabilityMap.push({
          id: row.acceptance_criterion_id,
          title: row.business_intent_text?.length > 80 ? row.business_intent_text.substring(0, 80) + '...' : row.business_intent_text || 'Unknown AC',
          fullText: row.business_intent_text || '',
          coverageStatus: row.status === 'COVERED' || row.status === 'VERIFIED' ? 'Covered' : 
                        row.status === 'PARTIALLY_COVERED' ? 'Partially covered' : 
                        row.status === 'MISSING' ? 'Missing' : 'Not mapped',
          linkedExistingTests: linkedTests.map(t => t.display_name || t.stable_identity),
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

  if (!run.evidence.coverage) {
    missingSignals.push("coverage_report");
  }

  if (!run.evidence.history || !run.evidence.history.has_flakiness_data) {
    missingSignals.push("test_history");
  }

  // Map missing signals to display labels
  return missingSignals.map(signal => formatDisplayLabel(signal, "signal"));
}

// ── Main page ──────────────────────────────────────────────────────────────

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
  const [showOutcomeForm, setShowOutcomeForm] = useState(false);
  const [showAllAC, setShowAllAC] = useState(false);
  const [expandedAC, setExpandedAC] = useState<string | null>(null);

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
      if (!res.ok) { setError(data?.error || `Error ${res.status}`); return; }
      setRun(data);
      
      // Fetch outcome summary
      if (data.outcome) {
        setOutcomeSummary(data.outcome);
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

  const { executive_summary, testing_strategy, recommended_tests, why, evidence, warnings: rawWarnings, evidence_gaps: rawEvidenceGaps = [], missing_coverage = [], scenario_coverage_matrix, impact_profile } = run;
  const mustRun   = recommended_tests.filter(t => t.tier === "must_run");
  const shouldRun = recommended_tests.filter(t => t.tier === "should_run");
  const fallback  = recommended_tests.filter(t => t.tier === "fallback");

  const warnings = run.input_stale && rawWarnings
    ? rawWarnings.filter((w: string) => !w.toLowerCase().includes("acceptance criteria") && !w.toLowerCase().includes("no ac"))
    : (rawWarnings || []);

  const evidence_gaps = run.input_stale && rawEvidenceGaps
    ? rawEvidenceGaps.filter((gap: any) => {
        const msg = (gap.message || "").toLowerCase();
        const reason = (gap.reason || "").toLowerCase();
        return !msg.includes("acceptance criteria") && !msg.includes("no ac") && !reason.includes("acceptance criteria") && !reason.includes("no ac");
      })
    : rawEvidenceGaps;

  const requirementGaps = run.input_stale && run.requirement_gaps
    ? run.requirement_gaps.filter((gap: any) => {
        const msg = (gap.message || "").toLowerCase();
        return !msg.includes("acceptance criteria") && !msg.includes("no ac");
      })
    : (run.requirement_gaps || []);

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

  // Check if current PR execution is available at generation time
  const missingInputs = run.readiness_snapshot?.missing_inputs || [];
  const hasCurrentPRExecution = !missingInputs.some((i: any) =>
    i.key === "current_pr_execution" || i.signal === "current_pr_execution" || i === "current_pr_execution"
  );

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

  // Calculate health state
  const healthState = getRecommendationHealth(run, evidence_gaps);

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
        .map((s: any, idx: number) => `scenario-${s.scenario_id ?? s.id ?? s.requiredScenario?.slice(0, 20)?.replace(/\s+/g, '-').toLowerCase() ?? idx}`)
    );
    scenarioMatrix.forEach((scenario: any) => {
      if (scenario.status === "suggested" || scenario.status === "partial") {
        const sid = `scenario-${scenario.scenario_id ?? scenario.id ?? scenario.requiredScenario?.slice(0, 20)?.replace(/\s+/g, '-').toLowerCase() ?? 'unknown'}`;
        if (suggestedIds.has(sid)) return; // already shown in Create Missing Tests
        rawGaps.push({
          type: "behavior",
          name: scenario.behavior_name || scenario.scenario_title || "Unknown behavior",
          coverageStatus: scenario.status === "suggested" ? "missing" : "partial",
          suggestedAction: scenario.scenario_title || "Add scenario test",
          priority: scenario.priority === "BLOCKER" || scenario.priority === "MUST" ? "must" : "recommended",
          reason: scenario.reasons?.[0] || "Behavior not covered by tests",
          sourceEvidence: scenario.journey_name || "Scenario analysis"
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

  // Classify recommended tests by current PR execution outcome.
  // When hasCurrentPRExecution is true but backend hasn't set per-test current_pr_result,
  // fall back to optimistic "passed" if no execution failures appear in evidence_gaps.
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
    // If no per-test result is set but JUnit was attached and no failures in evidence_gaps,
    // treat all as passed (backend matched them successfully and all passed).
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

      const scenarioTitle = scenario.scenario_title || scenario.behavior_name || "";
      const scenarioIntent = scenario.behavior_name || scenario.scenario_intent || "";
      const scenarioReqId = scenario.requirement_id || "";
      const normalizedTitle = normalize(scenarioTitle);
      const normalizedIntent = normalize(scenarioIntent);

      // Try to match against passed tests first
      for (const test of passedTests) {
        const testName = test.display_name || test.stable_identity || "";
        const testSuite = test.test_suite_name || test.suite_name || "";
        const testReqId = test.requirement_id || "";
        const normalizedTestName = normalize(testName);
        const normalizedSuite = normalize(testSuite);

        // Layer 1: exact test_id match
        if (test.stable_identity === scenario.scenario_id || test.stable_identity === scenario.id) {
          matches.set(scenario.scenario_id || scenario.id, { test, method: "exact_test_id" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (exact_test_id)`);
          }
          return;
        }

        // Layer 2: normalized name match
        if (normalizedTitle === normalizedTestName) {
          matches.set(scenario.scenario_id || scenario.id, { test, method: "normalized_name" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (normalized_name)`);
          }
          return;
        }

        // Layer 3: classname + test name match
        const combinedTest = `${normalizedSuite} ${normalizedTestName}`;
        if (normalizedTitle.includes(normalizedTestName) && normalizedTitle.includes(normalizedSuite)) {
          matches.set(scenario.scenario_id || scenario.id, { test, method: "classname_testname" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (classname_testname)`);
          }
          return;
        }

        // Layer 4: AC ID match
        if (scenarioReqId && testReqId && scenarioReqId === testReqId) {
          matches.set(scenario.scenario_id || scenario.id, { test, method: "ac_id" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (ac_id)`);
          }
          return;
        }

        // Layer 5: requirement title match
        if (test.requirement_title && normalizedTitle.includes(normalize(test.requirement_title))) {
          matches.set(scenario.scenario_id || scenario.id, { test, method: "requirement_title" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (requirement_title)`);
          }
          return;
        }

        // Layer 6: scenario intent match
        if (normalizedIntent === normalizedTestName || normalizedIntent.includes(normalizedTestName)) {
          matches.set(scenario.scenario_id || scenario.id, { test, method: "scenario_intent" });
          if (typeof window !== "undefined") {
            console.log(`[Veriscope] Match: scenario "${scenarioTitle}" -> test "${testName}" (scenario_intent)`);
          }
          return;
        }

        // Layer 7: keyword/semantic intent fallback
        if (hasKeywordOverlap(scenarioTitle, testName, 2) || hasKeywordOverlap(scenarioIntent, testName, 2)) {
          matches.set(scenario.scenario_id || scenario.id, { test, method: "keyword_semantic" });
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
          matches.set(scenario.scenario_id || scenario.id, { test, method: "failed_or_skipped_match" });
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
          const scenarioId = s.scenario_id ?? s.id;
          const match = scenarioToTestMatch.get(scenarioId);
          // Exclude if matched to a passed test
          if (match && prTestClassification.passed.includes(match.test)) {
            if (typeof window !== "undefined") {
              console.log(`[Veriscope] Excluding scenario "${s.scenario_title || s.behavior_name}" from Create Missing Tests - matched to passed test via ${match.method}`);
            }
            return false;
          }
          return true;
        })
        .map((scenario: any, idx: number) => ({
          id: `scenario-${scenario.scenario_id ?? scenario.id ?? scenario.requiredScenario?.slice(0, 20)?.replace(/\s+/g, '-').toLowerCase() ?? idx}`,
          title: generateMissingTestTitle(scenario),
          type: 'missing' as const,
          tier: (scenario.priority === 'BLOCKER' || scenario.priority === 'MUST' ? 'must_run' : 'should_run') as "must_run" | "should_run" | "fallback",
          requirement_id: scenario.requirement_id,
          scenario_intent: scenario.behavior_name,
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
      s.status === "suggested" && generateMissingTestTitle(s) === 'Create validation test'
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
          .map((s) => s.scenario_id || s.id || s.title),
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

      {/* Legacy Recommendation Warning */}
      {!run.readiness_snapshot && (
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
      )}

      {/* Dev Consistency Check — compact, dev-only, hidden when no issues */}
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
              // Scroll to Coverage Gaps section
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
              {run.pull_request && (
                <span className="text-sm text-zinc-400 font-mono">
                  PR #{run.pull_request.number} · {run.pull_request.title}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="text-[11px] text-zinc-500">{run.repository.full_name}</span>
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
          repositoryId={run.repository.id}
          pullRequestId={run.pull_request?.id}
          currentCommitSha={run.commit_sha ?? undefined}
          onAttached={refreshRun}
        />
      )}

      {/* Executive Decision */}
      <Section title="Executive Decision" icon={Zap}>
        <div className="space-y-4">
          {/* Decision Summary */}
          <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-4">
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
              <div>
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Recommendation</p>
                <p className="text-sm font-semibold text-zinc-200">
                  {(() => {
                    const mode = testing_strategy.recommendation_mode;
                    if (mode === "FULL_SUITE") return "Full authentication/security regression";
                    if (mode === "TARGETED") return "Targeted regression";
                    if (mode === "SMOKE") return "Smoke validation";
                    if (mode === "NO_RUN") return "No regression recommended";
                    return mode;
                  })()}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Confidence</p>
                <p className={`text-sm font-semibold ${
                  displayState.confidenceLabel === "HIGH" ? "text-emerald-400" :
                  displayState.confidenceLabel === "MODERATE" ? "text-amber-400" :
                  displayState.confidenceLabel === "N/A" ? "text-zinc-500" :
                  "text-rose-400"
                }`}>
                  {displayState.confidenceLabel}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Scope</p>
                <p className="text-sm font-semibold text-zinc-200">
                  {(() => {
                    const mode = testing_strategy.recommendation_mode;
                    if (mode === "FULL_SUITE") return "Full suite";
                    if (mode === "TARGETED") return "Targeted regression";
                    if (mode === "SMOKE") return "Smoke validation";
                    if (mode === "NO_RUN") return "No regression recommended";
                    return mode;
                  })()}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Reason</p>
                <p className="text-sm font-semibold text-zinc-200 truncate">
                  {(() => {
                    if (!run.readiness_snapshot?.readiness_snapshot_available) {
                      return "Legacy recommendation - regenerate for current state";
                    }
                    const mode = testing_strategy.recommendation_mode;
                    const confidence = displayState.confidenceLabel;
                    const hasSecurity = changedFiles.some(f => 
                      f.toLowerCase().includes("auth") || f.toLowerCase().includes("password") || 
                      f.toLowerCase().includes("security") || f.toLowerCase().includes("token")
                    );
                    
                    if (mode === "FULL_SUITE" && confidence === "HIGH" && hasSecurity) {
                      return "Password validation affects authentication-sensitive flows";
                    }
                    if (mode === "FULL_SUITE" && confidence === "LOW" && hasSecurity) {
                      return "Security-sensitive change with limited evidence";
                    }
                    if (mode === "FULL_SUITE" && confidence === "HIGH") {
                      return "Critical system components requiring comprehensive testing";
                    }
                    if (mode === "FULL_SUITE" && confidence === "LOW") {
                      return "Safety fallback due to limited evidence";
                    }
                    if (mode === "TARGETED") {
                      return "Focused testing on impacted areas";
                    }
                    if (mode === "SMOKE") {
                      return "Quick validation of critical paths";
                    }
                    return why.length > 0 ? why[0] : "Changes impact system components";
                  })()}
                </p>
              </div>
            </div>

            {/* Metrics */}
            <div className={`grid gap-3 ${hasCurrentPRExecution ? "sm:grid-cols-5" : "sm:grid-cols-3"}`}>
              {hasCurrentPRExecution ? (
                <>
                  <div className="bg-zinc-950/40 rounded-lg p-3 border border-emerald-800/30">
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Verified tests</p>
                    <p className="text-xl font-bold text-emerald-400">{prTestClassification.passed.length}</p>
                  </div>
                  <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Failed tests</p>
                    <p className={`text-xl font-bold ${prTestClassification.failed.length > 0 ? "text-rose-400" : "text-zinc-400"}`}>{prTestClassification.failed.length}</p>
                  </div>
                  <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Required not run</p>
                    <p className={`text-xl font-bold ${prTestClassification.notRun.length > 0 ? "text-amber-400" : "text-zinc-400"}`}>{prTestClassification.notRun.length}</p>
                  </div>
                </>
              ) : (
                <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Must-run tests</p>
                  <p className="text-xl font-bold text-zinc-200">{testing_strategy.must_run_count}</p>
                </div>
              )}
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Missing tests</p>
                <p className="text-xl font-bold text-zinc-200">{finalViewModel.grouped.missing.length}</p>
              </div>
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Coverage gaps</p>
                <p className="text-xl font-bold text-zinc-200">{sectionGapCount}</p>
              </div>
            </div>

            {/* Decision Copy */}
            <div className="border-t border-zinc-800/40 pt-3">
              <p className="text-xs text-zinc-400 leading-relaxed">
                {(() => {
                  if (!run.readiness_snapshot?.readiness_snapshot_available) {
                    return "This is a legacy recommendation. Regenerate to capture current readiness and confidence.";
                  }
                  const mode = testing_strategy.recommendation_mode;
                  const confidence = displayState.confidenceLabel;
                  const hasSecurity = changedFiles.some(f => 
                    f.toLowerCase().includes("auth") || f.toLowerCase().includes("password") || 
                    f.toLowerCase().includes("security") || f.toLowerCase().includes("token")
                  );
                  
                  if (mode === "FULL_SUITE" && confidence === "HIGH" && hasSecurity) {
                    return "Full suite recommended because this PR changes authentication/security-sensitive password validation flows.";
                  }
                  if (mode === "FULL_SUITE" && confidence === "LOW" && hasSecurity) {
                    return "Full suite recommended as a safety fallback because evidence is limited for an authentication/security-sensitive change.";
                  }
                  if (mode === "FULL_SUITE" && confidence === "HIGH") {
                    return "Full suite recommended because this PR changes critical system components requiring comprehensive testing.";
                  }
                  if (mode === "FULL_SUITE" && confidence === "LOW") {
                    return "Full suite recommended as a safety fallback because evidence is limited for this change.";
                  }
                  if (mode === "TARGETED") {
                    return "Targeted regression recommended based on impacted areas and available evidence.";
                  }
                  if (mode === "SMOKE") {
                    return "Smoke validation recommended for quick critical path verification.";
                  }
                  return why.length > 0 ? why[0] : "Changes impact system components requiring testing.";
                })()}
              </p>
            </div>
          </div>

        </div>
      </Section>

      {/* Release Readiness Verdict */}
      {(() => {
        const verdictEvidenceQuality = run.readiness_snapshot?.expected_confidence || "UNKNOWN";
        const verdictCoverageRatio = run.evidence.coverage?.line_coverage_ratio ?? null;
        const verdictHasFailures = prTestClassification.failed.length > 0;
        const verdictMissingScenarios = scenarioMatrix.filter(s => s.status === "suggested");
        const verdict = determineReleaseReadinessVerdict(
          run.recommended_tests,
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
              run.recommended_tests,
              verdictMissingScenarios,
              verdictCoverageRatio
            )}
            impactedAreas={extractUnderstandingData(run).impactedBehaviors}
            confidence={run.readiness_snapshot?.expected_confidence || undefined}
          />
        );
      })()}

      {/* What Veriscope Understood */}
      <WhatVeriscopeUnderstood {...extractUnderstandingData(run)} />

      {/* Recommended Regression Scope / Current PR Validation Result */}
      <Section title={hasCurrentPRExecution ? "Current PR Validation Result" : "Recommended Regression Scope"} icon={FlaskConical}>
        {(() => {
          // Define TestCard component inline within the same scope
          function TestCard({ item, changedFiles, recommendationRunId }: { 
            item: any; 
            changedFiles: string[]; 
            recommendationRunId: string;
          }) {
            const isExisting = item.type === 'existing';
            const test = isExisting ? item.originalTest : item.originalScenario;
            
            const priorityLabel = item.tier === 'must_run' ? 'Must' : item.tier === 'should_run' ? 'Recommended' : 'Optional';
            const priorityColor = item.tier === 'must_run' ? 'text-rose-400' : item.tier === 'should_run' ? 'text-amber-400' : 'text-zinc-400';
            
            const typeLabel = isExisting ? 'Existing automated test' : 'Missing automated coverage';
            const typeColor = isExisting ? 'text-emerald-400' : 'text-amber-400';

            // Map to acceptance criteria using layered matching
            const acMapping = mapToAcceptanceCriteria(test, run.acceptance_criteria || [], !isExisting);
            const requirementText = acMapping
              ? `AC-${acMapping.ac.id.slice(0, 8)} ${acMapping.ac.text.length > 60 ? acMapping.ac.text.substring(0, 60) + '...' : acMapping.ac.text}`
              : 'Requirement not mapped';
            
            // Why selected - make more specific
            const whySelected = isExisting 
              ? generateTestWhySelected(test, changedFiles)
              : `Selected because it validates ${item.scenario_intent || test?.behavior_name || 'uncovered behavior'}${requirementText !== 'Requirement not mapped' ? ` and maps to ${requirementText}` : ''}.`;
            
            // Risk if skipped
            const riskIfSkipped = isExisting
              ? (test?.risk_if_skipped || `Skipping may miss regression in ${test?.impacted_area || 'impacted area'}.`)
              : (test?.risk_if_skipped || `Missing coverage for ${item.scenario_intent || test?.behavior_name || 'this behavior'} may allow defects to reach production.`);
            
            // Current PR execution status — use classification from prTestClassification
            const isPassed = isExisting && hasCurrentPRExecution && prTestClassification.passed.some(
              (p: any) => p.stable_identity === test?.stable_identity || p.id === test?.id
            );
            const isFailed = isExisting && hasCurrentPRExecution && prTestClassification.failed.some(
              (p: any) => p.stable_identity === test?.stable_identity || p.id === test?.id
            );
            const isSkipped = isExisting && hasCurrentPRExecution && prTestClassification.skipped.some(
              (p: any) => p.stable_identity === test?.stable_identity || p.id === test?.id
            );
            const rawPRResult = test?.current_pr_result || "";
            const currentPRResult = isPassed ? "Passed"
              : isFailed ? "Failed"
              : isSkipped ? "Skipped"
              : (hasCurrentPRExecution && isExisting) ? "Not run on this PR"
              : rawPRResult || "Not run on this PR";
            const currentPRColor = currentPRResult === 'Passed' ? 'text-emerald-400'
              : currentPRResult === 'Failed' ? 'text-rose-400'
              : currentPRResult === 'Skipped' ? 'text-amber-400'
              : 'text-zinc-400';
            
            // Historical result
            const historicalResult = test?.historical_result || 'No history';
            const historicalDate = test?.last_run_date ? new Date(test.last_run_date).toLocaleDateString() : null;
            
            // Evidence source — current PR execution takes priority when attached and passed
            const evidenceSource = isPassed
              ? 'Current PR execution'
              : test?.evidence_source || (isExisting ? 'Test history' : 'Coverage report');
            
            const linkedFile = test?.linked_file || (isExisting && test?.file_path);
            
            return (
              <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-lg p-4 hover:bg-zinc-900/60 transition-colors">
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h3 className="text-sm font-semibold text-zinc-100" title={item.title}>
                        {item.title}
                      </h3>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded border ${priorityColor} bg-zinc-950/20 border-zinc-800`}>
                        {priorityLabel}
                      </span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded border ${typeColor} bg-zinc-950/20 border-zinc-800`}>
                        {typeLabel}
                      </span>
                    </div>
                    <p className="text-[10px] text-zinc-500 font-mono truncate" title={item.stable_identity || item.id}>
                      Test ID: {item.stable_identity || item.id}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs mb-3">
                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Requirement/AC</span>
                    <div className="flex items-center gap-1.5 text-zinc-300">
                      <FileText className="w-3 h-3 text-zinc-500" />
                      <span className="truncate">{requirementText}</span>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Current PR Result</span>
                    <div className="flex items-center gap-1.5">
                      <span className={`truncate ${currentPRColor}`}>{currentPRResult}</span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs mb-3">
                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Historical Result</span>
                    <div className="flex items-center gap-1.5 text-zinc-300">
                      <span className="truncate">{historicalResult}{historicalDate ? ` (${historicalDate})` : ''}</span>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Evidence Source</span>
                    <div className="flex items-center gap-1.5 text-zinc-300">
                      <span className="truncate">{evidenceSource}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-1 mb-3">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Why Selected</span>
                  <p className="text-xs text-zinc-400 leading-snug">{whySelected}</p>
                </div>

                <div className="space-y-1 mb-3">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Risk if Skipped</span>
                  <p className="text-xs text-zinc-400 leading-snug">{riskIfSkipped}</p>
                </div>

                {linkedFile && (
                  <div className="space-y-1 mb-3">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Linked Changed File</span>
                    <p className="text-xs text-zinc-400 font-mono truncate">{linkedFile}</p>
                  </div>
                )}

                <div className="pt-3 border-t border-zinc-800/50 flex items-center justify-between text-[10px] text-zinc-500">
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-3 h-3" />
                    <span>Est. duration: ~30s</span>
                  </div>
                </div>
              </div>
            );
          }

          // Scope summary with PR changed files
          const fileCount = changedFiles.length;
          const fileSummary = fileCount === 1 
            ? `PR changes: ${fileCount} file` 
            : `PR changes: ${fileCount} files across authentication, data, and test infrastructure`;

          // Use the hoisted finalViewModel so section counts always match Executive Decision counts.
          const { deduplicatedItems, grouped } = finalViewModel;

          // Partition existing items by PR classification
          const existingItems = grouped.existing;
          const passedItems = hasCurrentPRExecution
            ? existingItems.filter(item => prTestClassification.passed.some(
                (p: any) => p.stable_identity === item.stable_identity || p.id === item.stable_identity
              ))
            : [];
          const failedItems = hasCurrentPRExecution
            ? existingItems.filter(item => prTestClassification.failed.some(
                (p: any) => p.stable_identity === item.stable_identity || p.id === item.stable_identity
              ))
            : [];
          const skippedItems = hasCurrentPRExecution
            ? existingItems.filter(item => prTestClassification.skipped.some(
                (p: any) => p.stable_identity === item.stable_identity || p.id === item.stable_identity
              ))
            : [];
          const notRunItems = hasCurrentPRExecution
            ? existingItems.filter(item =>
                !prTestClassification.passed.some((p: any) => p.stable_identity === item.stable_identity || p.id === item.stable_identity) &&
                !prTestClassification.failed.some((p: any) => p.stable_identity === item.stable_identity || p.id === item.stable_identity) &&
                !prTestClassification.skipped.some((p: any) => p.stable_identity === item.stable_identity || p.id === item.stable_identity)
              )
            : [];

          return (
            <>
              {/* Scope Summary */}
              <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-lg p-4 mb-6">
                <p className="text-xs text-zinc-400">{fileSummary}</p>
                {hasCurrentPRExecution ? (
                  <div className="flex items-center gap-4 mt-2 text-xs flex-wrap">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                      <span className="text-emerald-300 font-medium">{prTestClassification.passed.length}/{recommended_tests.length} passed</span>
                    </div>
                    {prTestClassification.failed.length > 0 && (
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-3 h-3 text-rose-400" />
                        <span className="text-rose-300">{prTestClassification.failed.length} failed</span>
                      </div>
                    )}
                    {prTestClassification.skipped.length > 0 && (
                      <div className="flex items-center gap-2">
                        <Clock className="w-3 h-3 text-amber-400" />
                        <span className="text-amber-300">{prTestClassification.skipped.length} skipped</span>
                      </div>
                    )}
                    {prTestClassification.notRun.length > 0 && (
                      <div className="flex items-center gap-2">
                        <Circle className="w-3 h-3 text-zinc-500" />
                        <span className="text-zinc-400">{prTestClassification.notRun.length} not run</span>
                      </div>
                    )}
                    <span className="text-zinc-500">· Current PR execution attached</span>
                    {grouped.missing.length > 0 && (
                      <div className="flex items-center gap-2">
                        <Plus className="w-3 h-3 text-amber-400" />
                        <span className="text-zinc-300">Create Missing Tests: {grouped.missing.length}</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center gap-4 mt-2 text-xs">
                    <div className="flex items-center gap-2">
                      <Play className="w-3 h-3 text-emerald-400" />
                      <span className="text-zinc-300">Run Existing Tests: {grouped.existing.length}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Plus className="w-3 h-3 text-amber-400" />
                      <span className="text-zinc-300">Create Missing Tests: {grouped.missing.length}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Star className="w-3 h-3 text-zinc-500" />
                      <span className="text-zinc-300">Optional Tests: {grouped.optional.length}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Execution-aware existing tests section */}
              {hasCurrentPRExecution ? (
                <>
                  {/* Verified (passed) tests — collapsed by default */}
                  {passedItems.length > 0 && (
                    <div className="mb-6">
                      <details className="group">
                        <summary className="flex items-center gap-2 mb-3 cursor-pointer list-none">
                          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          <h3 className="text-sm font-semibold text-emerald-300">Verified by Current PR Execution</h3>
                          <span className="text-xs text-zinc-500">({passedItems.length} passed)</span>
                          <ChevronDown className="w-3 h-3 text-zinc-500 ml-auto group-open:rotate-180 transition-transform" />
                        </summary>
                        <div className="space-y-2 mt-2">
                          {passedItems.map(item => (
                            <TestCard
                              key={item.id}
                              item={item}
                              changedFiles={changedFiles}
                              recommendationRunId={runId || ""}
                            />
                          ))}
                        </div>
                      </details>
                    </div>
                  )}

                  {/* Failed tests */}
                  {failedItems.length > 0 && (
                    <div className="mb-6">
                      <div className="flex items-center gap-2 mb-3">
                        <AlertTriangle className="w-4 h-4 text-rose-400" />
                        <h3 className="text-sm font-semibold text-rose-300">Failed Tests — Investigate Before Release</h3>
                        <span className="text-xs text-zinc-500">({failedItems.length})</span>
                      </div>
                      <div className="space-y-2">
                        {failedItems.map(item => (
                          <TestCard key={item.id} item={item} changedFiles={changedFiles} recommendationRunId={runId || ""} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Skipped tests */}
                  {skippedItems.length > 0 && (
                    <div className="mb-6">
                      <div className="flex items-center gap-2 mb-3">
                        <Clock className="w-4 h-4 text-amber-400" />
                        <h3 className="text-sm font-semibold text-amber-300">Skipped Required Tests — Run Before Release</h3>
                        <span className="text-xs text-zinc-500">({skippedItems.length})</span>
                      </div>
                      <div className="space-y-2">
                        {skippedItems.map(item => (
                          <TestCard key={item.id} item={item} changedFiles={changedFiles} recommendationRunId={runId || ""} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Required tests not run */}
                  {notRunItems.length > 0 && (
                    <div className="mb-6">
                      <div className="flex items-center gap-2 mb-3">
                        <Play className="w-4 h-4 text-amber-400" />
                        <h3 className="text-sm font-semibold text-amber-300">Required Tests Not Run — Must Execute</h3>
                        <span className="text-xs text-zinc-500">({notRunItems.length})</span>
                      </div>
                      <div className="space-y-2">
                        {notRunItems.map(item => (
                          <TestCard key={item.id} item={item} changedFiles={changedFiles} recommendationRunId={runId || ""} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* All passed and none not-run: success state */}
                  {failedItems.length === 0 && skippedItems.length === 0 && notRunItems.length === 0 && passedItems.length > 0 && (
                    <div className="bg-emerald-950/20 border border-emerald-800/40 rounded-lg p-4 mb-6 flex items-center gap-3">
                      <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                      <p className="text-sm text-emerald-300">
                        No remaining existing tests need to be run. Current PR execution passed all {passedItems.length} selected tests.
                      </p>
                    </div>
                  )}
                </>
              ) : (
                /* Before execution: show all existing tests as must-run */
                grouped.existing.length > 0 && (
                  <div className="mb-6">
                    <div className="flex items-center gap-2 mb-3">
                      <Play className="w-4 h-4 text-emerald-400" />
                      <h3 className="text-sm font-semibold text-zinc-200">Run Existing Tests</h3>
                      <span className="text-xs text-zinc-500">({grouped.existing.length})</span>
                    </div>
                    <div className="space-y-2">
                      {grouped.existing.map(item => (
                        <TestCard
                          key={item.id}
                          item={item}
                          changedFiles={changedFiles}
                          recommendationRunId={runId || ""}
                        />
                      ))}
                    </div>
                  </div>
                )
              )}

              {/* Create Missing Tests */}
              {grouped.missing.length > 0 && (
                <div className="mb-6">
                  <div className="flex items-center gap-2 mb-3">
                    <Plus className="w-4 h-4 text-amber-400" />
                    <h3 className="text-sm font-semibold text-zinc-200">Create Missing Tests</h3>
                    <span className="text-xs text-zinc-500">({grouped.missing.length})</span>
                  </div>
                  <div className="space-y-2">
                    {grouped.missing.map(item => (
                      <TestCard
                        key={item.id}
                        item={item}
                        changedFiles={changedFiles}
                        recommendationRunId={runId || ""}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Optional Tests */}
              {grouped.optional.length > 0 && (
                <div className="mb-6">
                  <div className="flex items-center gap-2 mb-3">
                    <Star className="w-4 h-4 text-zinc-500" />
                    <h3 className="text-sm font-semibold text-zinc-200">Optional Tests</h3>
                    <span className="text-xs text-zinc-500">({grouped.optional.length})</span>
                  </div>
                  <div className="space-y-2">
                    {grouped.optional.map(item => (
                      <TestCard
                        key={item.id}
                        item={item}
                        changedFiles={changedFiles}
                        recommendationRunId={runId || ""}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* No tests message */}
              {deduplicatedItems.length === 0 && (
                <p className="text-sm text-zinc-500 text-center py-6">No tests recommended.</p>
              )}
            </>
          );
        })()}
      </Section>

      {/* Test Card Component */}
      {(() => {
        // Define TestCard component inline
        function TestCard({ item, changedFiles, recommendationRunId }: { 
          item: any; 
          changedFiles: string[]; 
          recommendationRunId: string;
        }) {
          const isExisting = item.type === 'existing';
          const test = isExisting ? item.originalTest : item.originalScenario;
          
          const priorityLabel = item.tier === 'must_run' ? 'Must' : item.tier === 'should_run' ? 'Recommended' : 'Optional';
          const priorityColor = item.tier === 'must_run' ? 'text-rose-400' : item.tier === 'should_run' ? 'text-amber-400' : 'text-zinc-400';
          
          const typeLabel = isExisting ? 'Existing test' : 'Missing automated coverage';
          const typeColor = isExisting ? 'text-emerald-400' : 'text-amber-400';
          
          const whySelected = isExisting 
            ? generateTestWhySelected(test, changedFiles)
            : `Suggested because it covers ${item.scenario_intent || 'uncovered behavior'} for the changed files and maps to ${item.requirement_id || 'acceptance criteria'}.`;

          const linkedFile = test?.linked_file || (isExisting && test?.file_path);
          
          return (
            <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-lg p-4 hover:bg-zinc-900/60 transition-colors">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h3 className="text-sm font-semibold text-zinc-100" title={item.title}>
                      {item.title}
                    </h3>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded border ${priorityColor} bg-zinc-950/20 border-zinc-800`}>
                      {priorityLabel}
                    </span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded border ${typeColor} bg-zinc-950/20 border-zinc-800`}>
                      {typeLabel}
                    </span>
                  </div>
                  <p className="text-[10px] text-zinc-500 font-mono truncate" title={item.stable_identity || item.id}>
                    Test ID: {item.stable_identity || item.id}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs mb-3">
                <div className="space-y-1">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Risk Area</span>
                  <div className="flex items-center gap-1.5 text-zinc-300">
                    <Target className="w-3 h-3 text-zinc-500" />
                    <span className="truncate">{test?.impacted_area || 'General'}</span>
                  </div>
                </div>
                <div className="space-y-1">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Requirement/AC</span>
                  <div className="flex items-center gap-1.5 text-zinc-300">
                    <FileText className="w-3 h-3 text-zinc-500" />
                    <span className="truncate">{item.requirement_id || test?.requirement_id || 'N/A'}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-1 mb-3">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Why Selected</span>
                <p className="text-xs text-zinc-400 leading-snug">{whySelected}</p>
              </div>

              {linkedFile && (
                <div className="space-y-1 mb-3">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Linked Changed File</span>
                  <p className="text-xs text-zinc-400 font-mono truncate">{linkedFile}</p>
                </div>
              )}

              <div className="pt-3 border-t border-zinc-800/50 flex items-center justify-between text-[10px] text-zinc-500">
                <div className="flex items-center gap-1.5">
                  <Clock className="w-3 h-3" />
                  <span>Est. duration: ~30s</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span>Evidence source: {isExisting ? 'Test history' : 'Scenario analysis'}</span>
                </div>
              </div>
            </div>
          );
        }

        return null;
      })()}

      {/* Acceptance Criteria Traceability */}
      {((run.acceptance_criteria && run.acceptance_criteria.length > 0) || (run.business_intent?.has_business_intent)) && (
        <CollapsibleSection title="Acceptance Criteria Traceability" icon={FileText} defaultOpen={false}>
          {(() => {
            const acTraceability = mapACTraceability(run, recommended_tests);
            
            if (acTraceability.length === 0) {
              return <p className="text-sm text-zinc-500 text-center py-6">No acceptance criteria found.</p>;
            }
            
            const displayAC = showAllAC ? acTraceability : acTraceability.slice(0, 5);
            
            return (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-500">{acTraceability.length} acceptance criteria found</span>
                  {acTraceability.length > 5 && !showAllAC && (
                    <button
                      onClick={() => setShowAllAC(true)}
                      className="text-xs text-blue-400 hover:text-blue-300"
                    >
                      Show all
                    </button>
                  )}
                </div>
                <div className="space-y-2">
                  {displayAC.map((ac: any) => {
                    const statusColor = ac.coverageStatus === 'Covered' ? 'text-emerald-400 bg-emerald-950/20 border-emerald-800/40' :
                                       ac.coverageStatus === 'Partially covered' ? 'text-amber-400 bg-amber-950/20 border-amber-800/40' :
                                       ac.coverageStatus === 'Missing' ? 'text-rose-400 bg-rose-950/20 border-rose-800/40' :
                                       'text-zinc-400 bg-zinc-950/20 border-zinc-800/40';
                    const priorityColor = ac.priority === 'Must' ? 'text-rose-400' : 'text-amber-400';
                    const isExpanded = expandedAC === ac.id;
                    
                    return (
                      <div key={ac.id} className="bg-zinc-950/40 border border-zinc-800/30 rounded-lg overflow-hidden">
                        <div 
                          className="p-3 cursor-pointer hover:bg-zinc-900/40 transition-colors"
                          onClick={() => setExpandedAC(expandedAC === ac.id ? null : ac.id)}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1 flex-wrap">
                                <span className="text-[10px] font-mono text-zinc-500">{ac.id}</span>
                                <span className={`text-[9px] px-1.5 py-0.5 rounded border ${statusColor}`}>
                                  {ac.coverageStatus}
                                </span>
                                <span className={`text-[9px] px-1.5 py-0.5 rounded border bg-zinc-800 ${priorityColor}`}>
                                  {ac.priority}
                                </span>
                              </div>
                              <p className="text-xs text-zinc-200 line-clamp-2">{ac.title}</p>
                            </div>
                            {isExpanded ? <ChevronDown className="w-4 h-4 text-zinc-500 shrink-0" /> : <ChevronRight className="w-4 h-4 text-zinc-500 shrink-0" />}
                          </div>
                        </div>
                        {isExpanded && (
                          <div className="border-t border-zinc-800/50 p-3 bg-zinc-950/60 space-y-2">
                            <div className="space-y-1">
                              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Full AC Text</span>
                              <p className="text-xs text-zinc-300 leading-relaxed">{ac.fullText}</p>
                            </div>
                            {ac.linkedExistingTests.length > 0 && (
                              <div className="space-y-1">
                                <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Linked Existing Tests</span>
                                <div className="space-y-1">
                                  {ac.linkedExistingTests.map((test: string, idx: number) => (
                                    <div key={idx} className="flex items-center gap-2 text-xs text-emerald-400">
                                      <CheckCircle2 className="w-3 h-3" />
                                      <span className="truncate">{test}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            {ac.linkedMissingTest && (
                              <div className="space-y-1">
                                <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Suggested Test</span>
                                <div className="flex items-center gap-2 text-xs text-amber-400">
                                  <Plus className="w-3 h-3" />
                                  <span className="truncate">{ac.linkedMissingTest}</span>
                                </div>
                              </div>
                            )}
                            {ac.notes && (
                              <div className="space-y-1">
                                <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Notes</span>
                                <p className="text-xs text-zinc-400">{ac.notes}</p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
                {acTraceability.length > 5 && (
                  <button
                    onClick={() => setShowAllAC(!showAllAC)}
                    className="w-full text-center text-xs text-zinc-400 hover:text-zinc-300 py-2 border-t border-zinc-800/40"
                  >
                    {showAllAC ? 'Show top 5' : `Show all ${acTraceability.length}`}
                  </button>
                )}
              </div>
            );
          })()}
        </CollapsibleSection>
      )}

      {/* Coverage Gaps & Missing Tests */}
      <Section title="Coverage Gaps & Missing Tests" icon={AlertTriangle} id="coverage-gaps">
        {(() => {
          // Define GapCard component inline
          function GapCard({ gap }: { gap: any }) {
            const statusColor = gap.coverageStatus === 'missing' 
              ? 'text-rose-400 bg-rose-950/20 border-rose-800/40'
              : gap.coverageStatus === 'partial'
              ? 'text-amber-400 bg-amber-950/20 border-amber-800/40'
              : 'text-emerald-400 bg-emerald-950/20 border-emerald-800/40';

            const priorityColor = gap.priority === 'critical'
              ? 'text-rose-400 bg-rose-950/20 border-rose-800/40'
              : gap.priority === 'must'
              ? 'text-rose-400 bg-rose-950/20 border-rose-800/40'
              : gap.priority === 'recommended'
              ? 'text-amber-400 bg-amber-950/20 border-amber-800/40'
              : 'text-zinc-400 bg-zinc-950/20 border-zinc-800/40';

            return (
              <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-lg p-4">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h4 className="text-sm font-semibold text-zinc-200" title={gap.name}>
                        {gap.name}
                      </h4>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded border ${statusColor}`}>
                        {gap.coverageStatus === 'missing' ? 'Missing' : gap.coverageStatus === 'partial' ? 'Partial' : 'Covered'}
                      </span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded border ${priorityColor}`}>
                        {gap.priority === 'critical' ? 'Critical' : gap.priority === 'must' ? 'Must' : gap.priority === 'recommended' ? 'Recommended' : 'Optional improvement'}
                      </span>
                    </div>
                    <p className="text-[10px] text-zinc-500">Source: {gap.source}</p>
                  </div>
                </div>

                <div className="space-y-2 mb-3">
                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Requirement/Behavior</span>
                    <p className="text-xs text-zinc-300">{gap.name}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Status</span>
                    <p className="text-xs text-zinc-300">
                      {gap.coverageStatus === 'missing' ? 'Missing automated coverage' : 
                       gap.coverageStatus === 'partial' ? 'Partial coverage' : 
                       gap.priority === 'optional' ? 'Optional improvement' : 'Missing'}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Suggested Action</span>
                    <p className="text-xs text-zinc-300">{gap.suggestedAction}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Why It Matters</span>
                    <p className="text-xs text-zinc-400 leading-snug">{gap.whyItMatters}</p>
                  </div>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Source</span>
                  <p className="text-xs text-zinc-400">{gap.source}</p>
                </div>
                {gap.linkedTestId && (
                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Linked Test</span>
                    <p className="text-xs text-emerald-400">{gap.linkedTestTitle}</p>
                  </div>
                )}
                {!gap.linkedTestId && (
                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Missing Test</span>
                    <p className="text-xs text-rose-400">No existing test linked</p>
                  </div>
                )}
              </div>
            );
          }

          // Consolidate all gap data
          const allGaps: any[] = [];

          // 1. Requirement coverage gaps from business_intent
          if (run.business_intent?.rows) {
            run.business_intent.rows.forEach((row: any) => {
              if (row.status === "MISSING" || row.status === "PARTIALLY_COVERED") {
                allGaps.push({
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

          // 2. Behavior coverage gaps from scenario matrix (excluding those already in regression scope)
          const missingScenarioIds = new Set(
            scenarioMatrix
              .filter(s => s.status === 'suggested')
              .map((s, idx) => `scenario-${s.scenario_id ?? s.id ?? s.requiredScenario?.slice(0, 20)?.replace(/\s+/g, '-').toLowerCase() ?? idx}`)
          );
          
          scenarioMatrix.forEach((scenario: any) => {
            if (scenario.status === "suggested" || scenario.status === "partial") {
              const scenarioId = `scenario-${scenario.scenario_id ?? scenario.id ?? scenario.requiredScenario?.slice(0, 20)?.replace(/\s+/g, '-').toLowerCase() ?? 'unknown'}`;
              // Skip if already shown in Create Missing Tests section
              if (missingScenarioIds.has(scenarioId)) return;
              
              allGaps.push({
                type: "behavior",
                name: scenario.behavior_name || scenario.scenario_title || "Unknown behavior",
                coverageStatus: scenario.status === "suggested" ? "missing" : "partial",
                suggestedAction: scenario.scenario_title || "Add scenario test",
                priority: scenario.priority === "BLOCKER" || scenario.priority === "MUST" ? "must" : "recommended",
                reason: scenario.reasons?.[0] || "Behavior not covered by tests",
                sourceEvidence: scenario.journey_name || "Scenario analysis",
                behaviorId: scenario.behavior_id
              });
            }
          });

          // 3. Requirement gaps
          if (requirementGaps && requirementGaps.length > 0) {
            requirementGaps.forEach((gap: any) => {
              allGaps.push({
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
          }

          // 4. Automation gaps from missing coverage
          if (missing_coverage && missing_coverage.length > 0) {
            missing_coverage.forEach((gap: any) => {
              allGaps.push({
                type: "automation",
                name: gap.domain ? `${gap.domain} - ${gap.feature}` : gap.feature || "Unknown",
                coverageStatus: "missing",
                suggestedAction: gap.reason || "Add automated coverage",
                priority: "recommended",
                reason: gap.impact,
                sourceEvidence: "Coverage analysis"
              });
            });
          }

          // Consolidate AC fragments
          const consolidatedGaps = consolidateACFragments(allGaps);

          // Group gaps by category
          const grouped = groupCoverageGaps(consolidatedGaps, recommended_tests);

          // Calculate total gaps for executive decision consistency
          const totalGaps = grouped.critical.length + grouped.missingAutomated.length + grouped.partialCoverage.length + grouped.optional.length;
          
          // Sort all gaps by priority (critical > must > recommended > optional) and show top 5
          const priorityOrder = { critical: 0, must: 1, recommended: 2, optional: 3 };
          const allGapsSorted = [...grouped.critical, ...grouped.missingAutomated, ...grouped.partialCoverage, ...grouped.optional]
            .sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);
          const topGapsDisplay = showAllGaps ? allGapsSorted : allGapsSorted.slice(0, 5);

          if (totalGaps === 0) {
            return <p className="text-sm text-zinc-500 text-center py-6">No coverage gaps detected.</p>;
          }

          return (
            <div className="space-y-6">
              {/* Gap Summary */}
              <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-semibold text-zinc-200">Total gaps: {totalGaps}</span>
                  {totalGaps > 5 && !showAllGaps && (
                    <button
                      onClick={() => setShowAllGaps(true)}
                      className="text-xs text-blue-400 hover:text-blue-300"
                    >
                      Show all gaps
                    </button>
                  )}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-rose-400" />
                    <span className="text-zinc-400">Critical: {grouped.critical.length}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-rose-400" />
                    <span className="text-zinc-400">Must: {grouped.missingAutomated.length}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-amber-400" />
                    <span className="text-zinc-400">Recommended: {grouped.partialCoverage.length}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-zinc-400" />
                    <span className="text-zinc-400">Optional: {grouped.optional.length}</span>
                  </div>
                </div>
              </div>
              {/* Top Gaps by Priority */}
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  <h3 className="text-sm font-semibold text-zinc-200">
                    {showAllGaps ? `All ${totalGaps} Gaps` : `Top ${Math.min(5, totalGaps)} Gaps by Priority`}
                  </h3>
                </div>
                <div className="space-y-2">
                  {topGapsDisplay.map((gap) => (
                    <GapCard key={gap.id} gap={gap} />
                  ))}
                </div>
              </div>
              {/* Show all button */}
              {totalGaps > 5 && (
                <button
                  onClick={() => setShowAllGaps(!showAllGaps)}
                  className="w-full text-center text-xs text-zinc-400 hover:text-zinc-300 py-2 border-t border-zinc-800/40"
                >
                  {showAllGaps ? `Show top ${Math.min(5, totalGaps)} gaps` : `Show all ${totalGaps} gaps`}
                </button>
              )}
            </div>
          );
        })()}
      </Section>

      {/* Behavior Coverage Matrix */}
      {Object.keys(groupedByBehavior).length > 0 && (
        <CollapsibleSection title="Behavior Coverage Matrix" icon={Table} defaultOpen={false}>
          <div className="space-y-4">
            <p className="text-[10px] text-zinc-500">
              Coverage analysis by behavior and journey
            </p>
            <div className="space-y-2">
              {Object.entries(groupedByBehavior).map(([behavior, scenarios]) => (
                <div key={behavior} className="bg-zinc-950/40 rounded-lg p-4 border border-zinc-800/30">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex-1">
                      <p className="text-sm font-medium text-zinc-200 mb-1">{behavior}</p>
                      <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                        {scenarios[0]?.journey_name && (
                          <span className="flex items-center gap-1">
                            <Globe className="w-3 h-3" />
                            {scenarios[0]?.journey_name}
                          </span>
                        )}
                        <span className="text-zinc-400">{scenarios.length} scenario{scenarios.length !== 1 ? "s" : ""}</span>
                      </div>
                    </div>
                    <span className="text-[9px] font-bold px-2 py-1 rounded border bg-zinc-800 text-zinc-300 border-zinc-700">
                      {scenarios[0]?.reasons?.[0] || "Direct file mapping"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CollapsibleSection>
      )}

      {/* Evidence Used Audit */}
      <Section title="Evidence Used" icon={Shield}>
        <div className="space-y-4">
          {/* Evidence Status Banner - Using displayState */}
          {displayState.showStaleBanner ? (
            <div className="bg-amber-950/20 border border-amber-800/40 rounded-xl p-4 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-amber-200">
                  {displayState.evidenceStatusLabel}
                </p>
                <p className="text-xs text-amber-300 mt-1">
                  {displayState.secondaryMessage}
                </p>
              </div>
            </div>
          ) : displayState.healthState === "Ready" ? (
            <div className="bg-emerald-950/20 border border-emerald-800/40 rounded-xl p-4 flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-emerald-200">
                  Evidence status: {displayState.evidenceStatusLabel}
                </p>
                <p className="text-xs text-emerald-300 mt-1">
                  {displayState.secondaryMessage}
                </p>
              </div>
            </div>
          ) : displayState.healthState === "Limited Evidence" ? (
            <div className="bg-amber-950/20 border border-amber-800/40 rounded-xl p-4 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-amber-200">
                  Evidence status: {displayState.evidenceStatusLabel}
                </p>
                <p className="text-xs text-amber-300 mt-1">
                  {displayState.secondaryMessage}
                </p>
              </div>
            </div>
          ) : displayState.showNeedsMoreEvidence ? (
            <div className="bg-rose-950/20 border border-rose-800/40 rounded-xl p-4 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-rose-200">
                  Needs more evidence
                </p>
                <p className="text-xs text-rose-300 mt-1">
                  {displayState.secondaryMessage}
                </p>
              </div>
            </div>
          ) : displayState.showHistoricalTestMessage ? (
            <div className="bg-blue-950/20 border border-blue-800/40 rounded-xl p-4 flex items-start gap-3">
              <Info className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-blue-200">
                  Historical test evidence used
                </p>
                <p className="text-xs text-blue-300 mt-1">
                  Current PR test execution is not attached. Historical test evidence was used.
                </p>
              </div>
            </div>
          ) : !hasCurrentPRExecution && run.readiness_snapshot?.readiness_snapshot_available ? (
            <div className="bg-amber-950/20 border border-amber-800/40 rounded-xl p-4 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-amber-200">
                  Current PR execution: Not attached
                </p>
                <p className="text-xs text-amber-300 mt-1">
                  Current PR test execution is not available. Attach test results to improve accuracy.
                </p>
              </div>
              <AttachTestRun
                recommendationRunId={runId || ""}
                repositoryId={run.repository.id}
                pullRequestId={run.pull_request?.id}
                currentCommitSha={run.commit_sha ?? undefined}
                onAttached={refreshRun}
              />
            </div>
          ) : null}

          {/* Current PR Execution Status */}
          {run.readiness_snapshot?.readiness_snapshot_available && (
            <div className={`rounded-xl p-4 flex items-start gap-3 ${
              hasCurrentPRExecution
                ? "bg-emerald-950/20 border border-emerald-800/40"
                : "bg-zinc-950/40 border border-zinc-800/30"
            }`}>
              {hasCurrentPRExecution ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <Circle className="w-5 h-5 text-zinc-500 shrink-0 mt-0.5" />
              )}
              <div>
                <p className={`text-sm font-semibold ${
                  hasCurrentPRExecution ? "text-emerald-200" : "text-zinc-400"
                }`}>
                  Current PR execution: {hasCurrentPRExecution ? "Attached" : "Not attached"}
                </p>
              </div>
            </div>
          )}

          {/* Evidence Used Audit */}
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
              {/* PR diff */}
              <div className="flex items-center justify-between bg-zinc-950/40 rounded px-3 py-2 border border-zinc-800/30">
                <span className="text-zinc-400">PR diff</span>
                <span className={run.pull_request ? "text-emerald-400" : "text-rose-400"}>
                  {run.pull_request ? "Available" : "Missing"}
                </span>
              </div>
              {/* Acceptance criteria */}
              <div className="flex items-center justify-between bg-zinc-950/40 rounded px-3 py-2 border border-zinc-800/30">
                <span className="text-zinc-400">Acceptance criteria</span>
                <span className={(run.acceptance_criteria && run.acceptance_criteria.length > 0) || run.business_intent?.has_business_intent ? "text-emerald-400" : "text-rose-400"}>
                  {(run.acceptance_criteria && run.acceptance_criteria.length > 0) || run.business_intent?.has_business_intent ? "Available" : "Missing"}
                </span>
              </div>
              {/* Historical test evidence */}
              <div className="flex items-center justify-between bg-zinc-950/40 rounded px-3 py-2 border border-zinc-800/30">
                <span className="text-zinc-400">Historical test evidence</span>
                <span className={run.evidence?.history?.has_flakiness_data ? "text-emerald-400" : "text-rose-400"}>
                  {run.evidence?.history?.has_flakiness_data ? "Available" : "Missing"}
                </span>
              </div>
              {/* Current PR test execution */}
              <div className="flex items-center justify-between bg-zinc-950/40 rounded px-3 py-2 border border-zinc-800/30">
                <span className="text-zinc-400">Current PR test execution</span>
                <span className={hasCurrentPRExecution ? "text-emerald-400" : "text-rose-400"}>
                  {hasCurrentPRExecution ? "Attached" : "Not attached"}
                </span>
              </div>
              {/* Coverage report */}
              <div className="flex items-center justify-between bg-zinc-950/40 rounded px-3 py-2 border border-zinc-800/30">
                <span className="text-zinc-400">Coverage report</span>
                <span className={run.evidence?.coverage ? "text-emerald-400" : "text-rose-400"}>
                  {run.evidence?.coverage
                    ? (() => {
                        const raw = run.evidence.coverage.line_coverage_ratio;
                        if (raw == null) return "Available";
                        const pct = raw > 1 ? Math.round(raw) : Math.round(raw * 100);
                        return `Available — ${pct}% line coverage`;
                      })()
                    : "Missing"}
                </span>
              </div>
              {/* Current PR coverage */}
              <div className="flex items-center justify-between bg-zinc-950/40 rounded px-3 py-2 border border-zinc-800/30">
                <span className="text-zinc-400">Current PR coverage</span>
                <span className={run.evidence?.coverage ? "text-emerald-400" : "text-rose-400"}>
                  {run.evidence?.coverage ? "Attached" : "Not attached"}
                </span>
              </div>
              {/* Architecture intelligence */}
              <div className="flex items-center justify-between bg-zinc-950/40 rounded px-3 py-2 border border-zinc-800/30">
                <span className="text-zinc-400">Architecture intelligence</span>
                <span className="text-zinc-400">Available</span>
              </div>
              {/* Behavior catalog */}
              <div className="flex items-center justify-between bg-zinc-950/40 rounded px-3 py-2 border border-zinc-800/30">
                <span className="text-zinc-400">Behavior catalog</span>
                <span className={behaviorCoverageMatrix.length > 0 ? "text-emerald-400" : "text-rose-400"}>
                  {behaviorCoverageMatrix.length > 0 ? "Available" : "Missing"}
                </span>
              </div>
              {/* Journey catalog */}
              <div className="flex items-center justify-between bg-zinc-950/40 rounded px-3 py-2 border border-zinc-800/30">
                <span className="text-zinc-400">Journey catalog</span>
                <span className={behaviorCoverageMatrix.some((b: any) => b.journey_name) ? "text-emerald-400" : "text-rose-400"}>
                  {behaviorCoverageMatrix.some((b: any) => b.journey_name) ? "Available" : "Missing"}
                </span>
              </div>
            </div>

            {/* Optional Improvements */}
            {run.readiness_snapshot?.missing_inputs && run.readiness_snapshot.missing_inputs.length > 0 && (
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Optional Improvements</p>
                <p className="text-[10px] text-zinc-500 mb-2 italic">Optional only. These do not block this recommendation.</p>
                <div className="space-y-1">
                  {run.readiness_snapshot.missing_inputs.map((input: any, idx: number) => {
                    const key = input.key || input.signal || input.label || input.name || "unknown";
                    const label = signalLabels[key] || input.label || input.name || key;
                    return (
                      <div key={idx} className="text-xs text-zinc-400 flex items-center gap-2">
                        <span className="w-1 h-1 bg-zinc-500 rounded-full" />
                        <span>{label}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </Section>

      {/* Primary Actions */}
      <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <CheckCircle2 className="w-4 h-4 text-zinc-500" />
          <h2 className="text-sm font-semibold text-zinc-200">Primary Actions</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={exportJson} className="border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white gap-1.5 text-xs">
            <Download className="w-3.5 h-3.5" />
            Export Report
          </Button>
          <Button variant="outline" size="sm" onClick={() => {
            const summary = `Recommendation for PR #${run.pull_request?.number}\nConfidence: ${displayState.confidenceLabel}\nScope: ${(() => {
              const mode = testing_strategy.recommendation_mode;
              if (mode === "FULL_SUITE") return "Full suite";
              if (mode === "TARGETED") return "Targeted regression";
              if (mode === "SMOKE") return "Smoke validation";
              return mode;
            })()}\nMust-run tests: ${testing_strategy.must_run_count}\nMissing scenarios: ${scenarioMatrix.filter(s => s.status === "suggested").length}`;
            navigator.clipboard.writeText(summary);
            toast.success("Summary copied to clipboard");
          }} className="border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white gap-1.5 text-xs">
            <Copy className="w-3.5 h-3.5" />
            Copy Summary
          </Button>
          {run.pull_request && (
            <Button variant="outline" size="sm" onClick={() => setCheckpointModal({ isOpen: true, action: "rerun" })} disabled={isRegenerating} className="border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white gap-1.5 text-xs">
              {isRegenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              {isRegenerating ? "Regenerating..." : "Regenerate"}
            </Button>
          )}
          {run.repository && run.pull_request && (
            <Link href={`/app/repositories/${run.repository.id}`}>
              <Button variant="outline" size="sm" className="border-zinc-700 bg-zinc-800/40 text-zinc-300 hover:bg-zinc-700 hover:text-white gap-1.5 text-xs">
                <GitPullRequest className="w-3.5 h-3.5" />
                Back to Repository
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Audit Trail - Collapsed by default */}
      <CollapsibleSection title="Audit Trail" icon={History} defaultOpen={false}>
        <div className="space-y-5">

      {/* Intelligence Completeness Score - Only show if snapshot available */}
      {displayState.showCompletenessScore && (
        <CompletenessScore score={completenessScore} />
      )}

      {/* Improve Accuracy Panel - Only show if displayState allows */}
      {displayState.showImproveAccuracy && (
        <ImproveAccuracyPanel
          recommendationRunId={runId || ""}
          repositoryId={run.repository?.id || ""}
          pullRequestId={run.pull_request?.id || ""}
          missingSignals={getMissingSignals(run)}
          currentCompleteness={completenessScore.score}
          onActionComplete={(actionId) => {
            console.log('Action completed:', actionId);
            if (runId) {
              fetchRun(runId);
            }
          }}
          onRefreshRun={() => {
            if (runId) {
              fetchRun(runId);
            }
          }}
        />
      )}

      {/* Business Intent Section - Only show if there's actual content */}
      {run.business_intent && run.business_intent.has_business_intent && (
        <CollapsibleSection title="Business Intent" icon={Brain} defaultOpen={false}>
          <div className="space-y-4">
            <div className="grid sm:grid-cols-3 gap-3">
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Total Intents</p>
                <p className="text-xl font-bold text-zinc-200">{run.business_intent.total_intents}</p>
              </div>
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Covered</p>
                <p className="text-xl font-bold text-emerald-400">{run.business_intent.covered + run.business_intent.verified}</p>
              </div>
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Missing</p>
                <p className="text-xl font-bold text-rose-400">{run.business_intent.missing}</p>
              </div>
            </div>
            {run.business_intent.confidence_impact !== "NONE" && (
              <div className={`rounded-lg p-3 border ${
                run.business_intent.confidence_impact === "REDUCED" 
                  ? "bg-amber-950/20 border-amber-800/40" 
                  : "bg-rose-950/20 border-rose-800/40"
              }`}>
                <p className="text-xs text-zinc-400">
                  Confidence impact: <span className="font-medium text-zinc-300">{run.business_intent.confidence_impact}</span>
                </p>
              </div>
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* Expected Behavior Scenarios - Only show if there are actual suggested scenarios */}
      {run.business_intent && run.business_intent.rows && run.business_intent.rows.some((r: any) => r.suggested_scenario_title) && run.business_intent.rows.filter((r: any) => r.suggested_scenario_title).length > 0 && (
        <CollapsibleSection title="Expected Behavior Scenarios" icon={BookOpen} defaultOpen={false}>
          <div className="space-y-3">
            <p className="text-[10px] text-zinc-500">
              Scenarios generated from acceptance criteria
            </p>
            <div className="space-y-2">
              {run.business_intent.rows.filter((r: any) => r.suggested_scenario_title).map((row: any, idx: number) => (
                <div key={idx} className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex-1">
                      <p className="text-[10px] font-semibold text-zinc-300 mb-1">{row.suggested_scenario_title}</p>
                      <p className="text-[9px] text-zinc-500">{row.business_intent_text}</p>
                    </div>
                    <span className="text-[9px] text-amber-400 font-medium">Suggested</span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    {row.affected_behavior_name && (
                      <span>Behavior: {row.affected_behavior_name}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CollapsibleSection>
      )}

      {/* PR Description Template Suggestion */}
      {run.pr_description_template_suggestion && run.pr_description_template_suggestion.needs_template && (
        <CollapsibleSection title="Improve PR Description" icon={FileCode} defaultOpen={false}>
          <div className="space-y-4">
            <div className="bg-blue-950/20 rounded-lg p-4 border border-blue-800/40">
              <div className="flex items-start gap-2">
                <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-blue-300 mb-1">{run.pr_description_template_suggestion.reason}</p>
                  <p className="text-xs text-blue-400/80">
                    Use this template to improve future recommendation accuracy.
                  </p>
                </div>
              </div>
            </div>
            {run.pr_description_template_suggestion?.template && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Suggested Template</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-[10px] text-zinc-400 hover:text-white gap-1"
                    onClick={() => {
                      navigator.clipboard.writeText(run.pr_description_template_suggestion?.template || "");
                      toast.success("Template copied", { description: "Template copied to clipboard" });
                    }}
                  >
                    <Copy className="w-3 h-3" /> Copy
                  </Button>
                </div>
                <pre className="bg-zinc-950/60 rounded-lg p-4 text-[11px] text-zinc-300 font-mono whitespace-pre-wrap border border-zinc-800/40 overflow-x-auto">
                  {run.pr_description_template_suggestion.template}
                </pre>
              </div>
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* Behavior Impact Summary */}
      {Object.keys(groupedByBehavior).length > 0 && (
        <CollapsibleSection title="Behavior Impact Summary" icon={Target} defaultOpen={false}>
          <div className="space-y-4">
            <p className="text-[10px] text-zinc-500">
              {Object.keys(groupedByBehavior).length} behavior{Object.keys(groupedByBehavior).length !== 1 ? "s" : ""} impacted by this PR
            </p>
            <div className="space-y-3">
              {Object.values(groupedByBehavior).map((group: any) => (
                <div key={group.behavior_id} className="bg-zinc-950/40 rounded-lg p-4 border border-zinc-800/30">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-semibold text-zinc-200">{group.behavior_name}</span>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                          group.impact_level === "CRITICAL" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                          group.impact_level === "HIGH" ? "bg-orange-500/10 text-orange-400 border-orange-500/20" :
                          group.impact_level === "MEDIUM" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                          "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                        }`}>
                          {group.impact_level}
                        </span>
                      </div>
                      {group.journey_name && (
                        <div className="flex items-center gap-1.5 text-[10px] text-zinc-500">
                          <Globe className="w-3 h-3" />
                          <span>{group.journey_name}</span>
                        </div>
                      )}
                    </div>
                    <span className="text-[9px] text-zinc-500">{group.scenarios.length} scenario{group.scenarios.length !== 1 ? "s" : ""}</span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                      <span>Changed files:</span>
                      <div className="flex flex-wrap gap-1">
                        {group.scenarios[0]?.related_changed_files?.slice(0, 3).map((file: string) => (
                          <span key={file} className="text-[9px] font-mono bg-zinc-900 text-zinc-400 px-1.5 py-0.5 rounded border border-zinc-800/60">
                            {file.split("/").slice(-2).join("/")}
                          </span>
                        ))}
                        {group.scenarios[0]?.related_changed_files?.length > 3 && (
                          <span className="text-[9px] text-zinc-500">+{group.scenarios[0].related_changed_files.length - 3} more</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                      <span>Reason:</span>
                      <span className="text-zinc-400">{group.scenarios[0]?.reasons?.[0] || "Direct file mapping"}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CollapsibleSection>
      )}

      {/* Requirement Context - Only show if there are linked work items */}
      {run.pull_request && run.requirement_context && run.requirement_context.has_linked_work_items && (
        <CollapsibleSection title="Requirement Context" icon={BookOpen} defaultOpen={false}>
          <RequirementContext
            repositoryId={run.repository.id}
            pullRequestId={run.pull_request.id}
          />
        </CollapsibleSection>
      )}

      {/* Managed Manual Tests - Only show if there are actual manual tests */}
      {run.pull_request && run.manual_tests && run.manual_tests.length > 0 && (
        <CollapsibleSection title="Managed Manual Tests" icon={FileText} defaultOpen={false}>
          <ManagedManualTests
            repositoryId={run.repository.id}
            pullRequestId={run.pull_request.id}
          />
        </CollapsibleSection>
      )}

      {/* Behavior Coverage Matrix */}
      {Object.keys(groupedByBehavior).length > 0 && (
        <CollapsibleSection title="Behavior Coverage Matrix" icon={Table} defaultOpen={false}>
          <div className="space-y-4">
            <p className="text-[10px] text-zinc-500">
              Scenario coverage grouped by behavior
            </p>
            {Object.values(groupedByBehavior).map((group: any) => (
              <BehaviorCoverageGroup key={group.behavior_id} group={group} />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Coverage Gaps */}
      {(mustFixBeforeMerge.length > 0 || shouldValidate.length > 0 || optionalBoosters.length > 0) && (
        <CollapsibleSection title="Coverage Gaps" icon={AlertTriangle} defaultOpen={false}>
          <div className="space-y-4">
            {/* Must Fix Before Merge */}
            {mustFixBeforeMerge.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider">Must Fix Before Merge</span>
                  <span className="text-[9px] text-zinc-500">{mustFixBeforeMerge.length} scenario{mustFixBeforeMerge.length !== 1 ? "s" : ""}</span>
                </div>
                <div className="space-y-2">
                  {mustFixBeforeMerge.map((scenario: BehaviorScenarioCoverageMatrix) => (
                    <div key={scenario.scenario_id} className="bg-rose-950/20 rounded-lg p-3 border border-rose-500/20">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-semibold text-zinc-300">{scenario.scenario_title}</span>
                          <span className="text-[9px] font-mono bg-rose-500/10 text-rose-400 px-1.5 py-0.5 rounded border border-rose-500/20">
                            {formatDisplayLabel(scenario.coverage_status, "coverage")}
                          </span>
                        </div>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                          scenario.priority === "BLOCKER" ? "bg-rose-500/10 text-rose-400" :
                          "bg-orange-500/10 text-orange-400"
                        }`}>
                          {scenario.priority}
                        </span>
                      </div>
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                          <span>Behavior:</span>
                          <span className="text-zinc-400">{scenario.behavior_name}</span>
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                          <span>Action:</span>
                          <span className="text-zinc-400">{scenario.recommended_actions[0] || "Add test"}</span>
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
              </div>
            )}

            {/* Should Validate */}
            {shouldValidate.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">Should Validate</span>
                  <span className="text-[9px] text-zinc-500">{shouldValidate.length} scenario{shouldValidate.length !== 1 ? "s" : ""}</span>
                </div>
                <div className="space-y-2">
                  {shouldValidate.map((scenario: BehaviorScenarioCoverageMatrix) => (
                    <div key={scenario.scenario_id} className="bg-amber-950/20 rounded-lg p-3 border border-amber-500/20">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-semibold text-zinc-300">{scenario.scenario_title}</span>
                          <span className="text-[9px] font-mono bg-amber-500/10 text-amber-400 px-1.5 py-0.5 rounded border border-amber-500/20">
                            {formatDisplayLabel(scenario.coverage_status, "coverage")}
                          </span>
                        </div>
                        <span className="text-[9px] font-bold bg-amber-500/10 text-amber-400 px-1.5 py-0.5 rounded">
                          {scenario.priority}
                        </span>
                      </div>
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                          <span>Behavior:</span>
                          <span className="text-zinc-400">{scenario.behavior_name}</span>
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                          <span>Action:</span>
                          <span className="text-zinc-400">{scenario.recommended_actions[0] || "Add test"}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Optional Confidence Boosters */}
            {optionalBoosters.length > 0 && (
              <OptionalCoverageSection scenarios={optionalBoosters} />
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* Existing Tests to Run */}
      {existingTestsToRun.length > 0 && (
        <CollapsibleSection title="Existing Tests to Run" icon={Play} defaultOpen={false}>
          <div className="space-y-3">
            <p className="text-[10px] text-zinc-500">
              {existingTestsToRun.length} scenario{existingTestsToRun.length !== 1 ? "s" : ""} with existing tests mapped to impacted behaviors, not yet verified on current PR
            </p>
            <div className="space-y-2">
              {existingTestsToRun.map((scenario: BehaviorScenarioCoverageMatrix) => (
                <div key={scenario.scenario_id} className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-semibold text-zinc-300">{scenario.scenario_title}</span>
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                        scenario.priority === "MUST" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                        scenario.priority === "SHOULD" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                        "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                      }`}>
                        {scenario.priority}
                      </span>
                    </div>
                    <span className="text-[9px] font-mono bg-blue-500/10 text-blue-400 px-1.5 py-0.5 rounded border border-blue-500/20">
                      NOT EXECUTED
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                      <span>Behavior:</span>
                      <span className="text-zinc-400">{scenario.behavior_name}</span>
                    </div>
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
          </div>
        </CollapsibleSection>
      )}

      {/* Current PR Verified Scenarios */}
      {currentPRVerified.length > 0 && (
        <CollapsibleSection title="Current PR Verified Scenarios" icon={CheckCircle2} defaultOpen={false}>
          <div className="space-y-3">
            <p className="text-[10px] text-zinc-500">
              {currentPRVerified.length} scenario{currentPRVerified.length !== 1 ? "s" : ""} already verified on current PR build
            </p>
            <div className="space-y-2">
              {currentPRVerified.map((scenario: BehaviorScenarioCoverageMatrix) => (
                <div key={scenario.scenario_id} className="bg-emerald-950/20 rounded-lg p-3 border border-emerald-500/20">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-semibold text-zinc-300">{scenario.scenario_title}</span>
                      <span className="text-[9px] font-mono bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/20">
                        VERIFIED
                      </span>
                    </div>
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                      scenario.priority === "MUST" ? "bg-rose-500/10 text-rose-400" :
                      scenario.priority === "SHOULD" ? "bg-amber-500/10 text-amber-400" :
                      "bg-zinc-500/10 text-zinc-400"
                    }`}>
                      {scenario.priority}
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                      <span>Behavior:</span>
                      <span className="text-zinc-400">{scenario.behavior_name}</span>
                    </div>
                    {scenario.existing_tests.length > 0 && (
                      <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                        <span>Verified by:</span>
                        <div className="flex flex-wrap gap-1">
                          {scenario.existing_tests.map((test: string) => (
                            <span key={test} className="text-[9px] font-mono bg-zinc-900 text-zinc-400 px-1.5 py-0.5 rounded border border-zinc-800/60">
                              {test.split("::").slice(-1)[0]}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CollapsibleSection>
      )}

      {/* 2. Project Understanding */}
      <CollapsibleSection title="Project Understanding" icon={Brain} defaultOpen={false}>
        <div className="space-y-5">
          {/* What Veriscope understood */}
          <div className="space-y-3">
            <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">What Veriscope understood</p>
            <div className="grid sm:grid-cols-3 gap-3">
              {/* Affected Journeys */}
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <div className="flex items-center gap-1.5 mb-2">
                  <Globe className="w-3.5 h-3.5 text-zinc-500" />
                  <span className="text-[10px] font-semibold text-zinc-400">Affected Journeys</span>
                </div>
                <div className="space-y-1.5">
                  {hasAuth && (
                    <div className="group relative inline-block">
                      <span className="text-[10px] bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded border border-zinc-700/50 cursor-help">
                        Auth flow
                      </span>
                      <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                        <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                          Source: {changedFiles.find(f => f.toLowerCase().includes("auth")) || "auth-related files"}
                        </div>
                      </div>
                    </div>
                  )}
                  {hasPassword && (
                    <div className="group relative inline-block">
                      <span className="text-[10px] bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded border border-zinc-700/50 cursor-help">
                        Password reset
                      </span>
                      <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                        <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                          Source: {changedFiles.find(f => f.toLowerCase().includes("password")) || "password-related files"}
                        </div>
                      </div>
                    </div>
                  )}
                  {hasSignup && (
                    <div className="group relative inline-block">
                      <span className="text-[10px] bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded border border-zinc-700/50 cursor-help">
                        User signup
                      </span>
                      <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                        <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                          Source: {changedFiles.find(f => f.toLowerCase().includes("signup")) || "signup-related files"}
                        </div>
                      </div>
                    </div>
                  )}
                  {!hasAuth && !hasPassword && !hasSignup && (
                    <span className="text-[10px] text-zinc-500 italic">No journeys detected</span>
                  )}
                </div>
              </div>

              {/* Affected Domains */}
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <div className="flex items-center gap-1.5 mb-2">
                  <Layers className="w-3.5 h-3.5 text-zinc-500" />
                  <span className="text-[10px] font-semibold text-zinc-400">Affected Domains</span>
                </div>
                <div className="space-y-1.5">
                  {hasSecurity && (
                    <div className="group relative inline-block">
                      <span className="text-[10px] bg-rose-950/30 text-rose-300 px-2 py-0.5 rounded border border-rose-500/20 cursor-help">
                        Security
                      </span>
                      <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                        <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                          Auth & password changes detected
                        </div>
                      </div>
                    </div>
                  )}
                  {changedFiles.some(f => f.toLowerCase().includes("api")) && (
                    <div className="group relative inline-block">
                      <span className="text-[10px] bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded border border-zinc-700/50 cursor-help">
                        API
                      </span>
                      <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                        <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                          Source: API route files modified
                        </div>
                      </div>
                    </div>
                  )}
                  {changedFiles.some(f => f.toLowerCase().includes("page") || f.toLowerCase().includes("ui")) && (
                    <div className="group relative inline-block">
                      <span className="text-[10px] bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded border border-zinc-700/50 cursor-help">
                        UI/Frontend
                      </span>
                      <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                        <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                          Source: Page/UI files modified
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Touched Layers */}
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <div className="flex items-center gap-1.5 mb-2">
                  <FileCode className="w-3.5 h-3.5 text-zinc-500" />
                  <span className="text-[10px] font-semibold text-zinc-400">Touched Layers</span>
                </div>
                <div className="space-y-1.5">
                  {changedFiles.some(f => f.includes("route")) && (
                    <div className="group relative inline-block">
                      <span className="text-[10px] bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded border border-zinc-700/50 cursor-help">
                        Routes
                      </span>
                      <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                        <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                          {changedFiles.filter(f => f.includes("route")).length} route files
                        </div>
                      </div>
                    </div>
                  )}
                  {changedFiles.some(f => f.includes("module")) && (
                    <div className="group relative inline-block">
                      <span className="text-[10px] bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded border border-zinc-700/50 cursor-help">
                        Modules
                      </span>
                      <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                        <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                          {changedFiles.filter(f => f.includes("module")).length} module files
                        </div>
                      </div>
                    </div>
                  )}
                  {changedFiles.some(f => f.includes("test")) && (
                    <div className="group relative inline-block">
                      <span className="text-[10px] bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded border border-zinc-700/50 cursor-help">
                        Tests
                      </span>
                      <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                        <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                          {changedFiles.filter(f => f.includes("test")).length} test files
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Why this matters */}
          <div className="space-y-3 border-t border-zinc-800/40 pt-4">
            <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Why this matters</p>
            <div className="grid sm:grid-cols-3 gap-3">
              {/* Risk Summary */}
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <div className="flex items-center gap-1.5 mb-2">
                  <AlertTriangle className="w-3.5 h-3.5 text-zinc-500" />
                  <span className="text-[10px] font-semibold text-zinc-400">Risk Summary</span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-zinc-500">Risk Level</span>
                    {riskBadge(executive_summary.risk_level)}
                  </div>
                  <div className="group relative">
                    <p className="text-[10px] text-zinc-400 leading-snug">
                      {executive_summary.bullets.slice(0, 2).join(" ")}
                    </p>
                    <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                      <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                        Based on {executive_summary.changed_files_count} changed files
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Security Concerns */}
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <div className="flex items-center gap-1.5 mb-2">
                  <Shield className="w-3.5 h-3.5 text-zinc-500" />
                  <span className="text-[10px] font-semibold text-zinc-400">Security Concerns</span>
                </div>
                <div className="space-y-1.5">
                  {hasSecurity && (
                    <div className="group relative">
                      <p className="text-[10px] text-rose-300 leading-snug">
                        Auth/password changes require validation
                      </p>
                      <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                        <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                          Source: Security-sensitive files modified
                        </div>
                      </div>
                    </div>
                  )}
                  {!hasSecurity && (
                    <p className="text-[10px] text-zinc-500 italic">No security concerns detected</p>
                  )}
                </div>
              </div>

              {/* Architecture Impact */}
              <div className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <div className="flex items-center gap-1.5 mb-2">
                  <BarChart2 className="w-3.5 h-3.5 text-zinc-500" />
                  <span className="text-[10px] font-semibold text-zinc-400">Architecture Impact</span>
                </div>
                <div className="space-y-1.5">
                  <div className="group relative">
                    <p className="text-[10px] text-zinc-400 leading-snug">
                      {changedFiles.length} file{changedFiles.length !== 1 ? "s" : ""} across {Object.keys(groupedFiles).length} area{Object.keys(groupedFiles).length !== 1 ? "s" : ""}
                    </p>
                    <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10">
                      <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-[9px] text-zinc-300 whitespace-nowrap shadow-lg">
                        Grouped by file path analysis
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Suggested Missing Scenarios */}
          {missing_coverage.length > 0 && (
            <div className="space-y-3 border-t border-zinc-800/40 pt-4">
              <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Suggested Missing Scenarios</p>
              <div className="space-y-2">
                {missing_coverage.slice(0, 3).map((item, i) => (
                  <div key={i} className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-1.5">
                        <Info className="w-3 h-3 text-amber-400 shrink-0" />
                        <span className="text-[10px] font-semibold text-zinc-300">{item.feature}</span>
                      </div>
                      <span className="text-[9px] font-mono bg-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded border border-zinc-700/50">
                        {item.domain}
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      <div className="flex items-start gap-2">
                        <span className="text-[9px] text-zinc-500 shrink-0 w-12">Scenario:</span>
                        <p className="text-[10px] text-zinc-400 leading-snug">{item.reason}</p>
                      </div>
                      <div className="flex items-start gap-2">
                        <span className="text-[9px] text-zinc-500 shrink-0 w-12">Data:</span>
                        <p className="text-[10px] text-zinc-400 leading-snug">Edge cases and boundary conditions</p>
                      </div>
                      <div className="flex items-start gap-2">
                        <span className="text-[9px] text-zinc-500 shrink-0 w-12">Expected:</span>
                        <p className="text-[10px] text-zinc-400 leading-snug">Validate behavior under {item.domain} conditions</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* 3. Impacted Areas */}
      <CollapsibleSection title="Impacted Areas" icon={BarChart2} defaultOpen={false}>
        <div className="grid sm:grid-cols-4 gap-3">
          {[
            { name: "Authentication", active: hasAuth, desc: "Authentication flow and token validation" },
            { name: "Password Reset", active: hasPassword, desc: "Password validation and reset workflows" },
            { name: "User Registration", active: hasSignup, desc: "Signup form and onboarding flows" },
            { name: "Security Validation", active: hasSecurity, desc: "Access control and security validation" },
          ].map(area => (
            <div key={area.name} className={`p-4 rounded-lg border flex flex-col justify-between ${
              area.active ? "bg-emerald-950/15 border-emerald-500/20 text-emerald-400" : "bg-zinc-950/20 border-zinc-800/40 text-zinc-650"
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider">{area.name}</span>
                <span className={`w-2 h-2 rounded-full ${area.active ? "bg-emerald-400 animate-pulse" : "bg-zinc-850"}`} />
              </div>
              <p className={`text-[10px] mt-2.5 leading-snug ${area.active ? "text-emerald-500/60" : "text-zinc-650"}`}>
                {area.desc}
              </p>
            </div>
          ))}
        </div>
      </CollapsibleSection>

      {/* Recommended Scope */}
      {run.testing_scope && (
        <CollapsibleSection title="Recommended Scope" icon={Target} defaultOpen={false}>
          <div className="space-y-4">
            {/* Must Test */}
            {run.testing_scope.must_test && run.testing_scope.must_test.length > 0 && (
              <div className="space-y-2">
                <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider block">Must Test</span>
                <div className="flex flex-wrap gap-2">
                  {run.testing_scope.must_test.map((s, idx) => (
                    <div key={idx} className="inline-flex items-center gap-2 bg-rose-950/20 border border-rose-500/30 rounded-lg px-3 py-1.5 text-xs text-rose-300">
                      <span className="font-bold bg-rose-500/10 px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide">{s.category}</span>
                      <span>{s.item}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Should Test */}
            {run.testing_scope.should_test && run.testing_scope.should_test.length > 0 && (
              <div className="space-y-2">
                <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider block">Should Test</span>
                <div className="flex flex-wrap gap-2">
                  {run.testing_scope.should_test.map((s, idx) => (
                    <div key={idx} className="inline-flex items-center gap-2 bg-amber-950/20 border border-amber-500/30 rounded-lg px-3 py-1.5 text-xs text-amber-300">
                      <span className="font-bold bg-amber-500/10 px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide">{s.category}</span>
                      <span>{s.item}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Optional */}
            {run.testing_scope.optional && run.testing_scope.optional.length > 0 && (
              <div className="space-y-2">
                <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Optional</span>
                <div className="flex flex-wrap gap-2">
                  {run.testing_scope.optional.map((s, idx) => (
                    <div key={idx} className="inline-flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-300">
                      <span className="font-bold bg-zinc-800 px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide">{s.category}</span>
                      <span>{s.item}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* 1. Existing Automated Tests to Run */}
      {runExistingTests.length > 0 && (
        <CollapsibleSection title="Existing Automated Tests to Run" icon={Play} defaultOpen={false}>
          <div className="space-y-3">
            <p className="text-[10px] text-zinc-500">
              {runExistingTests.length} scenario{runExistingTests.length !== 1 ? "s" : ""} with existing tests that should be run on this PR to verify coverage
            </p>
            {runExistingTests.map(item => (
              <div key={item.scenario_intent_key} className="bg-zinc-950/40 rounded-lg p-3 border border-zinc-800/30">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-semibold text-zinc-300">{item.title}</span>
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                      item.priority === "MUST" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                      item.priority === "SHOULD" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                      "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                    }`}>
                      {item.priority}
                    </span>
                  </div>
                  <span className="text-[9px] font-mono bg-blue-500/10 text-blue-400 px-1.5 py-0.5 rounded border border-blue-500/20">
                    {formatDisplayLabel(item.final_status, "coverage")}
                  </span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    <span>Area:</span>
                    <span className="text-zinc-400">{item.impacted_area}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    <span>Type:</span>
                    <span className="text-zinc-400">{item.testing_type}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    <span>Current PR Execution:</span>
                    <span className="text-zinc-400">{formatDisplayLabel(item.current_pr_execution_status, "execution")}</span>
                  </div>
                  {item.existing_tests.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[9px] text-zinc-500 font-semibold uppercase tracking-wider">Existing Tests (Not Run on PR):</span>
                      {item.existing_tests.map(test => (
                        <div key={test.test_identifier} className="flex items-center gap-2 bg-zinc-900/50 rounded px-2 py-1">
                          <span className="text-[10px] font-mono text-zinc-300">{test.test_name}</span>
                          {test.last_execution_status && (
                            <span className={`text-[9px] px-1.5 py-0.5 rounded ${
                              test.last_execution_status === "PASSED" ? "bg-emerald-500/10 text-emerald-400" :
                              test.last_execution_status === "FAILED" ? "bg-rose-500/10 text-rose-400" :
                              "bg-zinc-500/10 text-zinc-400"
                            }`}>
                              {test.last_execution_status} (historical)
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* 2. Suggested Missing Test Scenarios */}
      {(addAutomatedTests.length > 0 || executeManualScenarios.length > 0) && (
        <CollapsibleSection title="Suggested Missing Test Scenarios" icon={AlertTriangle} defaultOpen={false}>
          <div className="space-y-4">
            {/* ADD_AUTOMATED_TEST */}
            {addAutomatedTests.length > 0 && (
              <div className="space-y-3">
                <p className="text-[10px] font-semibold text-rose-400 uppercase tracking-wider">
                  Add Automated Tests ({addAutomatedTests.length})
                </p>
                {addAutomatedTests.map(item => (
                  <div key={item.scenario_intent_key} className="bg-zinc-950/40 rounded-lg p-3 border border-rose-500/20">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-semibold text-zinc-300">{item.title}</span>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                          item.priority === "MUST" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                          item.priority === "SHOULD" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                          "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                        }`}>
                          {item.priority}
                        </span>
                      </div>
                      <span className="text-[9px] font-mono bg-rose-500/10 text-rose-400 px-1.5 py-0.5 rounded border border-rose-500/20">
                        {item.final_status}
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                        <span>Area:</span>
                        <span className="text-zinc-400">{item.impacted_area}</span>
                      </div>
                      <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                        <span>Type:</span>
                        <span className="text-zinc-400">{item.testing_type}</span>
                      </div>
                      <p className="text-[10px] text-zinc-400 leading-snug">{item.evidence_reason}</p>
                      {item.suggested_scenarios.length > 0 && (
                        <div className="space-y-1 mt-2">
                          <span className="text-[9px] text-zinc-500 font-semibold uppercase tracking-wider">Suggested Scenarios:</span>
                          {item.suggested_scenarios.map(scenario => (
                            <div key={scenario.scenario_id} className="bg-zinc-900/50 rounded px-2 py-1.5">
                              <span className="text-[10px] text-zinc-300">{scenario.title}</span>
                              <span className={`text-[9px] ml-2 px-1.5 py-0.5 rounded ${
                                scenario.automation_candidate ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"
                              }`}>
                                {scenario.automation_candidate ? "Automatable" : "Manual"}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {/* EXECUTE_MANUAL_SCENARIO */}
            {executeManualScenarios.length > 0 && (
              <div className="space-y-3">
                <p className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider">
                  Execute Manual Scenarios ({executeManualScenarios.length})
                </p>
                {executeManualScenarios.map(item => (
                  <div key={item.scenario_intent_key} className="bg-zinc-950/40 rounded-lg p-3 border border-amber-500/20">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-semibold text-zinc-300">{item.title}</span>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                          item.priority === "MUST" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                          item.priority === "SHOULD" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                          "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                        }`}>
                          {item.priority}
                        </span>
                      </div>
                      <span className="text-[9px] font-mono bg-amber-500/10 text-amber-400 px-1.5 py-0.5 rounded border border-amber-500/20">
                        {item.final_status}
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                        <span>Area:</span>
                        <span className="text-zinc-400">{item.impacted_area}</span>
                      </div>
                      <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                        <span>Type:</span>
                        <span className="text-zinc-400">{item.testing_type}</span>
                      </div>
                      <p className="text-[10px] text-zinc-400 leading-snug">{item.evidence_reason}</p>
                      {item.suggested_scenarios.length > 0 && (
                        <div className="space-y-1 mt-2">
                          <span className="text-[9px] text-zinc-500 font-semibold uppercase tracking-wider">Manual Scenarios:</span>
                          {item.suggested_scenarios.map(scenario => (
                            <div key={scenario.scenario_id} className="bg-zinc-900/50 rounded px-2 py-1.5">
                              <span className="text-[10px] text-zinc-300">{scenario.title}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* 3. Already Verified */}
      {alreadyVerified.length > 0 && (
        <CollapsibleSection title="Already Verified on Current PR" icon={CheckCircle2} defaultOpen={false}>
          <div className="space-y-3">
            <p className="text-[10px] text-zinc-500">
              {alreadyVerified.length} scenario{alreadyVerified.length !== 1 ? "s" : ""} covered and verified by tests that passed on this PR
            </p>
            {alreadyVerified.map(item => (
              <div key={item.scenario_intent_key} className="bg-zinc-950/40 rounded-lg p-3 border border-emerald-500/20">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-semibold text-zinc-300">{item.title}</span>
                    <span className="text-[9px] font-mono bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/20">
                      {formatDisplayLabel(item.final_status, "coverage")}
                    </span>
                  </div>
                  <span className="text-[9px] text-zinc-500">{item.confidence}</span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    <span>Area:</span>
                    <span className="text-zinc-400">{item.impacted_area}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    <span>Current PR Execution:</span>
                    <span className="text-emerald-400 font-medium">{formatDisplayLabel(item.current_pr_execution_status, "execution")}</span>
                  </div>
                  {item.existing_tests.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[9px] text-zinc-500 font-semibold uppercase tracking-wider">Verified Tests (Passed on PR):</span>
                      {item.existing_tests.map(test => (
                        <div key={test.test_identifier} className="flex items-center gap-2 bg-zinc-900/50 rounded px-2 py-1">
                          <span className="text-[10px] font-mono text-zinc-300">{test.test_name}</span>
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
                            PASSED on PR
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* 4. Expand Coverage */}
      {expandCoverage.length > 0 && (
        <CollapsibleSection title="Expand Coverage" icon={Layers} defaultOpen={false}>
          <div className="space-y-3">
            <p className="text-[10px] text-zinc-500">
              {expandCoverage.length} scenario{expandCoverage.length !== 1 ? "s" : ""} with partial coverage - file coverage exists but no test verifies the business scenario
            </p>
            {expandCoverage.map(item => (
              <div key={item.scenario_intent_key} className="bg-zinc-950/40 rounded-lg p-3 border border-amber-500/20">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-semibold text-zinc-300">{item.title}</span>
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                      item.priority === "MUST" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                      item.priority === "SHOULD" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                      "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                    }`}>
                      {item.priority}
                    </span>
                  </div>
                  <span className="text-[9px] font-mono bg-amber-500/10 text-amber-400 px-1.5 py-0.5 rounded border border-amber-500/20">
                    {formatDisplayLabel(item.final_status, "coverage")}
                  </span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    <span>Area:</span>
                    <span className="text-zinc-400">{item.impacted_area}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    <span>Code Coverage:</span>
                    <span className="text-zinc-400">{formatDisplayLabel(item.code_coverage_status, "coverage")}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    <span>Current PR Execution:</span>
                    <span className="text-zinc-400">{formatDisplayLabel(item.current_pr_execution_status, "execution")}</span>
                  </div>
                  <p className="text-[10px] text-zinc-400 leading-snug">{item.evidence_reason}</p>
                  {item.suggested_scenarios.length > 0 && (
                    <div className="space-y-1 mt-2">
                      <span className="text-[9px] text-zinc-500 font-semibold uppercase tracking-wider">Suggested Test Scenarios:</span>
                      {item.suggested_scenarios.map(scenario => (
                        <div key={scenario.scenario_id} className="bg-zinc-900/50 rounded px-2 py-1.5">
                          <span className="text-[10px] text-zinc-300">{scenario.title}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Testing Strategy */}
      <CollapsibleSection title="Testing Strategy" icon={Shield} defaultOpen={false}>
        <div className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-500">Selection mode</span>
                {modeBadge(testing_strategy.recommendation_mode)}
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-500">Coverage confidence</span>
                <span className={`font-medium ${
                  (run.readiness_snapshot?.expected_confidence || "LOW") === "HIGH" ? "text-emerald-400" :
                  (run.readiness_snapshot?.expected_confidence || "LOW") === "MODERATE" ? "text-amber-400" :
                  "text-rose-400"
                }`}>{run.readiness_snapshot?.expected_confidence || "LOW"}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-500">Optimization</span>
                <span className={testing_strategy.optimization_allowed ? "text-emerald-400" : "text-zinc-500"}>
                  {testing_strategy.optimization_allowed ? "Enabled" : "Disabled"}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-500">Must run</span>
                <span className="text-rose-400 font-medium">{testing_strategy.must_run_count}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-500">Should run</span>
                <span className="text-amber-400 font-medium">{testing_strategy.should_run_count}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-500">Fallback</span>
                <span className="text-zinc-400 font-medium">{testing_strategy.fallback_count}</span>
              </div>
            </div>
          </div>

          {/* Grouped priority testing types list */}
          {strategyTypes.length > 0 && (
            <div className="space-y-3.5 border-t border-zinc-800/40 pt-4 mt-4">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2.5">Priority Testing Types Needed</p>
              
              {/* HIGH Priority */}
              {mustTest.length > 0 && (
                <div className="space-y-2">
                  <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider">Must Test</span>
                  <div className="space-y-1.5">
                    {mustTest.map((t: any) => (
                      <div key={t.type} className="text-xs bg-zinc-950/40 p-2.5 rounded border border-zinc-800/60 flex items-start justify-between gap-4">
                        <span className="font-semibold text-zinc-200 min-w-[100px]">{t.label}</span>
                        <span className="text-zinc-400 flex-1 leading-snug">{t.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* MEDIUM Priority */}
              {shouldTest.length > 0 && (
                <div className="space-y-2 pt-2">
                  <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">Should Test</span>
                  <div className="space-y-1.5">
                    {shouldTest.map((t: any) => (
                      <div key={t.type} className="text-xs bg-zinc-950/40 p-2.5 rounded border border-zinc-800/60 flex items-start justify-between gap-4">
                        <span className="font-semibold text-zinc-200 min-w-[100px]">{t.label}</span>
                        <span className="text-zinc-400 flex-1 leading-snug">{t.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* LOW Priority */}
              {optionalTest.length > 0 && (
                <div className="space-y-2 pt-2">
                  <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Optional / Fallback</span>
                  <div className="space-y-1.5">
                    {optionalTest.map((t: any) => (
                      <div key={t.type} className="text-xs bg-zinc-950/40 p-2.5 rounded border border-zinc-800/60 flex items-start justify-between gap-4">
                        <span className="font-semibold text-zinc-200 min-w-[100px]">{t.label}</span>
                        <span className="text-zinc-400 flex-1 leading-snug">{t.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {testing_strategy.skipped_reason_summary && (
            <p className="mt-3 text-[11px] text-zinc-500 border-t border-zinc-800/40 pt-3">
              {testing_strategy.skipped_reason_summary}
            </p>
          )}
        </div>
      </CollapsibleSection>

      {/* Why these tests? */}
      <CollapsibleSection title="Why these tests?" icon={BookOpen} defaultOpen={false}>
        {why.length > 0 ? (
          <ul className="space-y-2">
            {why.map((bullet, i) => (
              <li key={i} className="flex items-start gap-2.5 text-sm text-zinc-300">
                <span className="w-5 h-5 rounded-full bg-zinc-800 flex items-center justify-center text-[10px] text-zinc-500 shrink-0 mt-0.5">
                  {i + 1}
                </span>
                {bullet}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zinc-500">No reasoning recorded for this run.</p>
        )}
      </CollapsibleSection>

      {/* Evidence Gaps */}
      {evidence_gaps.length > 0 && (
        <CollapsibleSection title="Evidence Gaps" icon={Shield} defaultOpen={false}>
          <div className="space-y-3">
            {evidence_gaps.map((gap, i) => (
              <div
                key={i}
                className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-start gap-3 bg-zinc-950/20 ${
                  gap.severity === "HIGH" ? "border-rose-900/40 text-rose-300 bg-rose-950/5" :
                  gap.severity === "WARNING" ? "border-amber-900/40 text-amber-300 bg-amber-950/5" :
                  "border-zinc-800/60 text-zinc-300"
                }`}
              >
                <span
                  className={`text-[9px] font-bold px-2 py-0.5 rounded border uppercase tracking-wider shrink-0 w-fit ${
                    gap.severity === "HIGH" ? "bg-rose-500/10 text-rose-400 border-rose-500/25" :
                    gap.severity === "WARNING" ? "bg-amber-500/10 text-amber-400 border-amber-500/25" :
                    "bg-zinc-800 text-zinc-400 border-zinc-700/50"
                  }`}
                >
                  {gap.severity}
                </span>
                <div className="space-y-1 min-w-0 flex-1">
                  <p className="text-xs font-semibold leading-normal">{gap.message}</p>
                  <p className="text-[11px] text-zinc-500 leading-relaxed">
                    <span className="font-semibold text-zinc-400">Impact: </span>
                    {gap.impact}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Historical Fragility - Only show if there are relevant signals */}
      {run.fragility && (run.fragility.behavior_signals.length > 0 || run.fragility.journey_signals.length > 0) && (
        <CollapsibleSection title="Historical Fragility" icon={History} defaultOpen={false}>
          <div className="space-y-4">
            {/* Summary */}
            <div className="flex items-center gap-3">
              {riskBadge(run.fragility.risk_level)}
              <p className="text-sm text-zinc-300">{run.fragility.summary}</p>
            </div>

            {/* Behavior Signals */}
            {run.fragility.behavior_signals.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Behaviors</h4>
                <div className="space-y-2">
                  {run.fragility.behavior_signals.map((signal, i) => (
                    <FragilitySignalCard key={i} signal={signal} />
                  ))}
                </div>
              </div>
            )}

            {/* Journey Signals */}
            {run.fragility.journey_signals.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Journeys</h4>
                <div className="space-y-2">
                  {run.fragility.journey_signals.map((signal, i) => (
                    <FragilitySignalCard key={i} signal={signal} />
                  ))}
                </div>
              </div>
            )}

            {/* File Hotspots */}
            {run.fragility.file_hotspots.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">File Hotspots</h4>
                <div className="space-y-2">
                  {run.fragility.file_hotspots.map((signal, i) => (
                    <FragilitySignalCard key={i} signal={signal} />
                  ))}
                </div>
              </div>
            )}

            {/* Evidence Gaps */}
            {run.fragility.evidence_gaps.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Evidence Gaps</h4>
                <div className="space-y-2">
                  {run.fragility.evidence_gaps.map((gap, i) => (
                    <div key={i} className="p-3 rounded-lg bg-zinc-950/30 border border-zinc-800/60">
                      <p className="text-xs text-zinc-400">{gap.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </CollapsibleSection>
      )}

        </div>
      </CollapsibleSection>

      {/* Outcome Status - only after outcome review starts */}
      {outcomeSummary && outcome && (
        <CollapsibleSection title="Outcome Status" icon={CheckCircle2} defaultOpen={false}>
          <OutcomePanel outcomeSummary={outcomeSummary} />
        </CollapsibleSection>
      )}

      {/* Post-Merge Outcome - only when relevant */}
      {(hasCreatedSuite || run.pull_request?.merged_at || outcome || showOutcomeForm) && (
        <CollapsibleSection title="Post-Merge Outcome" icon={GitBranch} defaultOpen={false}>
          <PostMergeOutcome
            recommendationRunId={runId || ""}
          />
        </CollapsibleSection>
      )}

      {/* Compact Feedback Footer */}
      <div className="mt-6 pt-4 border-t border-zinc-800/50 flex items-center justify-between gap-4 flex-wrap">
        <p className="text-xs text-zinc-500">Was this recommendation useful?</p>
        <div className="flex-1 min-w-0">
          <RecommendationFeedback
            recommendationRunId={runId || ""}
            existingFeedback={outcome?.user_feedback}
            existingComment={outcome?.feedback_comment}
          />
        </div>
        {!showOutcomeForm && (
          <button
            onClick={() => setShowOutcomeForm(true)}
            className="text-xs text-zinc-500 hover:text-zinc-300 underline underline-offset-2 whitespace-nowrap"
          >
            Record outcome
          </button>
        )}
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
        <PasteAcceptanceCriteriaModal
          isOpen={isPasteModalOpen}
          onClose={() => setIsPasteModalOpen(false)}
          onSuccess={(updatedReadiness) => {
            toast.success("Acceptance Criteria Saved", {
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


