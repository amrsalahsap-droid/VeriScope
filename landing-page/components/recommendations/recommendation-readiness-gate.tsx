"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { 
  CheckCircle2, 
  Circle, 
  AlertTriangle, 
  X,
  FileText,
  Link2,
  Users,
  Play,
  Upload,
  GitPullRequest,
  BarChart2,
  Sparkles,
  ArrowRight,
  ChevronRight,
  ShieldAlert,
  History,
  Activity,
  Plus,
  Loader2
} from "lucide-react";
import PasteAcceptanceCriteriaModal from "./paste-acceptance-criteria-modal";
import { resolveRecommendationAction, getReadinessSummary, getOptionalGapLabel } from "@/lib/readiness-cta-resolver";

interface AvailableInputSignal {
  key: string;
  label: string;
  status: string;
  source: string;
  confidence_contribution: number;
  description: string;
  evidence_count: number;
  linked_to_current_pr: boolean;
}

interface MissingInputSignal {
  key: string;
  label: string;
  severity: "REQUIRED" | "RECOMMENDED" | "OPTIONAL";
  impact: string;
  estimated_confidence_gain: number;
  actions: string[];
}

interface RecommendedAction {
  action: string;
  label: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  estimated_confidence_gain: number;
}

interface ReadinessData {
  readiness_level: string;
  expected_confidence: string;
  readiness_score: number;
  can_generate: boolean;
  available_inputs: AvailableInputSignal[];
  missing_inputs: MissingInputSignal[];
  next_best_actions: RecommendedAction[];
  intelligence_completeness_score?: number;
  release_confidence_ceiling?: string;
  primary_message?: string;
  secondary_message?: string;
  confidence_blockers?: string[];
  confidence_limiters?: any[];
}

interface RecommendationReadinessGateProps {
  isOpen: boolean;
  onClose: () => void;
  onContinue: () => void;
  repositoryId: string;
  pullRequestId?: string;
  action: "generate" | "rerun" | "view";
  recommendationRunId?: string;
  generationStatus?: "idle" | "generating" | "redirecting" | "failed";
}

// Map signal keys to display metadata
const ALL_SIGNALS_MAP: Record<string, { label: string; impact: string; icon: any; unit: string }> = {
  source_code: {
    label: "Source Code",
    impact: "Analyzes language-specific patterns and component syntax",
    icon: FileText,
    unit: "files"
  },
  pull_request_diff: {
    label: "PR Diff",
    impact: "Triggers targeted change impact analysis",
    icon: GitPullRequest,
    unit: "changes"
  },
  architecture_graph: {
    label: "Architecture Graph",
    impact: "Maps component dependencies and system boundaries",
    icon: Sparkles,
    unit: "nodes"
  },
  behavior_catalog: {
    label: "Behavior Catalog",
    impact: "Maps code modifications to system behaviors",
    icon: Activity,
    unit: "behaviors"
  },
  journey_catalog: {
    label: "Journey Catalog",
    impact: "Triggers cross-component user flow validation",
    icon: Users,
    unit: "journeys"
  },
  junit_test_history: {
    label: "Test History",
    impact: "Validates historical test suite execution status",
    icon: History,
    unit: "test runs"
  },
  coverage_report: {
    label: "Coverage Report",
    impact: "Maps code pathways to existing automated tests",
    icon: BarChart2,
    unit: "reports"
  }
};

// Signal group types
type SignalGroup = "USER_INPUTS" | "SYSTEM_INTELLIGENCE" | "OPTIONAL_LEARNING";

// Centralized missing input action resolver
interface MissingInputAction {
  label: string;
  actionType: string;
  enabled: boolean;
  disabledReason?: string;
  icon: any;
  group: SignalGroup;
}

const MISSING_INPUT_ACTION_MAP: Record<string, MissingInputAction> = {
  // User Inputs Needed
  acceptance_criteria: {
    label: "Paste Acceptance Criteria",
    actionType: "PASTE_ACCEPTANCE_CRITERIA",
    enabled: true,
    icon: FileText,
    group: "USER_INPUTS"
  },
  business_intent: {
    label: "Add Business Intent",
    actionType: "PASTE_ACCEPTANCE_CRITERIA",
    enabled: true,
    icon: FileText,
    group: "USER_INPUTS"
  },
  test_history: {
    label: "Upload Test Results",
    actionType: "UPLOAD_TEST_RESULTS",
    enabled: true,
    icon: Upload,
    group: "USER_INPUTS"
  },
  current_pr_execution: {
    label: "Attach Test Results",
    actionType: "ATTACH_TEST_RUN",
    enabled: true,
    icon: Play,
    group: "USER_INPUTS"
  },
  coverage_report: {
    label: "Upload Coverage",
    actionType: "UPLOAD_COVERAGE",
    enabled: true,
    icon: BarChart2,
    group: "USER_INPUTS"
  },
  current_pr_coverage: {
    label: "Attach Coverage Report",
    actionType: "ATTACH_COVERAGE",
    enabled: true,
    icon: BarChart2,
    group: "USER_INPUTS"
  },
  manual_test_cases: {
    label: "Coming soon",
    actionType: "UPLOAD_MANUAL_TESTS",
    enabled: false,
    disabledReason: "Manual test import is not available yet",
    icon: Upload,
    group: "USER_INPUTS"
  },

  // System Intelligence Missing
  architecture_graph: {
    label: "Run Repository Analysis",
    actionType: "RUN_REPOSITORY_INTELLIGENCE",
    enabled: true,
    icon: Sparkles,
    group: "SYSTEM_INTELLIGENCE"
  },
  behavior_catalog: {
    label: "Refresh Behavior Catalog",
    actionType: "RUN_REPOSITORY_INTELLIGENCE",
    enabled: true,
    icon: Activity,
    group: "SYSTEM_INTELLIGENCE"
  },
  journey_catalog: {
    label: "Refresh Journey Catalog",
    actionType: "RUN_REPOSITORY_INTELLIGENCE",
    enabled: true,
    icon: Users,
    group: "SYSTEM_INTELLIGENCE"
  },

  // Optional Learning Signals
  linked_work_item: {
    label: "Coming soon",
    actionType: "LINK_WORK_ITEM",
    enabled: false,
    disabledReason: "Work item integration is not available yet",
    icon: Link2,
    group: "OPTIONAL_LEARNING"
  },
  historical_outcomes: {
    label: "Skip for Now",
    actionType: "SKIP_OPTIONAL",
    enabled: true,
    icon: Circle,
    group: "OPTIONAL_LEARNING"
  },
  fragility_memory: {
    label: "Skip for Now",
    actionType: "SKIP_OPTIONAL",
    enabled: true,
    icon: Circle,
    group: "OPTIONAL_LEARNING"
  }
};

// Priority order for recommended next action
const ACTION_PRIORITY: string[] = [
  "pull_request_diff",
  "acceptance_criteria",
  "current_pr_execution",
  "coverage_report",
  "test_history",
  "current_pr_coverage",
  "business_intent",
  "manual_test_cases",
  "architecture_graph",
  "behavior_catalog",
  "journey_catalog"
];

// Map raw keys to readable text for confidence reasons
const KEY_TO_READABLE: Record<string, string> = {
  acceptance_criteria: "acceptance criteria",
  current_pr_execution: "current PR test results",
  coverage_report: "coverage report",
  test_history: "test history",
  current_pr_coverage: "current PR coverage",
  business_intent: "business intent",
  manual_test_cases: "manual test cases",
  pull_request_diff: "PR diff",
  source_code: "source code",
  architecture_graph: "architecture graph",
  behavior_catalog: "behavior catalog",
  journey_catalog: "journey catalog"
};

// Fallback label mapping for any missing input keys not in the action map
const FALLBACK_LABEL_MAP: Record<string, string> = {
  junit_test_history: "Test History",
  managed_manual_tests: "Manual Test Cases"
};

const getMissingInputAction = (key: string): MissingInputAction => {
  return MISSING_INPUT_ACTION_MAP[key] || {
    label: "Not required now",
    actionType: "NONE",
    enabled: false,
    disabledReason: "This input is not required at this time",
    icon: Circle,
    group: "OPTIONAL_LEARNING"
  };
};

const getMissingInputLabel = (key: string, apiLabel?: string): string => {
  if (apiLabel) return apiLabel;
  return FALLBACK_LABEL_MAP[key] || key.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
};

const getMissingInputBadge = (severity: string, group: SignalGroup): string => {
  if (group === "SYSTEM_INTELLIGENCE") {
    return "System intelligence";
  }
  if (group === "OPTIONAL_LEARNING") {
    return "Optional";
  }
  switch (severity) {
    case "REQUIRED":
      return "Required";
    case "RECOMMENDED":
      return "Recommended";
    case "OPTIONAL":
      return "Optional";
    default:
      return severity;
  }
};

const getMissingInputImpact = (key: string, apiImpact?: string): string => {
  if (apiImpact) return apiImpact;
  
  const impactMap: Record<string, string> = {
    acceptance_criteria: "Requirement coverage cannot be proven without acceptance criteria.",
    business_intent: "Veriscope has limited understanding of the business change.",
    current_pr_execution: "Existing tests are known, but Veriscope cannot confirm they passed on this PR.",
    current_pr_coverage: "Current PR coverage data is not available for this change.",
    test_history: "Veriscope cannot identify existing automated regression tests.",
    coverage_report: "Veriscope cannot estimate code-level protection.",
    manual_test_cases: "Manual validation coverage cannot be included in the regression scope.",
    architecture_graph: "Repository architecture has not been analyzed. Run repository intelligence to generate the architecture graph.",
    behavior_catalog: "System behavior catalog has not been discovered. Run repository intelligence to map code to behaviors.",
    journey_catalog: "User journey catalog has not been discovered. Run repository intelligence to map cross-component flows.",
    linked_work_item: "Business context is limited to PR title and description.",
    historical_outcomes: "Veriscope cannot learn from previous recommendation outcomes.",
    fragility_memory: "No previous defect or rollback patterns are available for this repository."
  };
  
  return impactMap[key] || "This input is missing and may affect recommendation quality.";
};

const getConfidenceGain = (key: string, apiGain?: number): number => {
  if (apiGain !== undefined) return apiGain;
  
  const gainMap: Record<string, number> = {
    acceptance_criteria: 10,
    business_intent: 5,
    current_pr_execution: 10,
    current_pr_coverage: 5,
    test_history: 10,
    coverage_report: 10,
    manual_test_cases: 5,
    architecture_graph: 5,
    behavior_catalog: 5,
    journey_catalog: 5,
    linked_work_item: 5,
    historical_outcomes: 5,
    fragility_memory: 5
  };
  
  return gainMap[key] || 5;
};

// Group missing inputs by their group type
const groupMissingInputs = (inputs: MissingInputSignal[]): Record<SignalGroup, MissingInputSignal[]> => {
  const groups: Record<SignalGroup, MissingInputSignal[]> = {
    USER_INPUTS: [],
    SYSTEM_INTELLIGENCE: [],
    OPTIONAL_LEARNING: []
  };
  
  inputs.forEach(input => {
    const action = getMissingInputAction(input.key);
    groups[action.group].push(input);
  });
  
  return groups;
};

// Sort missing inputs within each group: required/recommended first, then optional
const sortMissingInputs = (inputs: MissingInputSignal[]): MissingInputSignal[] => {
  const priorityOrder = { "REQUIRED": 0, "RECOMMENDED": 1, "OPTIONAL": 2 };
  return [...inputs].sort((a, b) => {
    const priorityA = priorityOrder[a.severity] ?? 2;
    const priorityB = priorityOrder[b.severity] ?? 2;
    if (priorityA !== priorityB) return priorityA - priorityB;
    return 0;
  });
};

// Check if multiple system intelligence signals are missing for grouped CTA
const shouldShowGroupedSystemIntelligenceCTA = (inputs: MissingInputSignal[]): boolean => {
  const systemIntelligenceSignals = ["architecture_graph", "behavior_catalog", "journey_catalog"];
  const missingCount = inputs.filter(i => systemIntelligenceSignals.includes(i.key)).length;
  return missingCount > 1;
};

// Get the highest priority missing input for recommended next action
const getRecommendedNextAction = (inputs: MissingInputSignal[]): MissingInputSignal | null => {
  if (!inputs || inputs.length === 0) return null;

  // Sort by priority order
  const sortedInputs = [...inputs].sort((a, b) => {
    const priorityA = ACTION_PRIORITY.indexOf(a.key);
    const priorityB = ACTION_PRIORITY.indexOf(b.key);
    if (priorityA === -1 && priorityB === -1) return 0;
    if (priorityA === -1) return 1;
    if (priorityB === -1) return -1;
    return priorityA - priorityB;
  });

  return sortedInputs[0];
};

// Format confidence limiters to readable text
const formatConfidenceLimiters = (limiters: any[]): string => {
  if (!limiters || limiters.length === 0) return "";

  const readableLimiters = limiters.slice(0, 2).map(l => {
    const key = l.key || l.label;
    return KEY_TO_READABLE[key] || key;
  });

  if (readableLimiters.length === 1) {
    return readableLimiters[0];
  }

  if (readableLimiters.length === 2) {
    return `${readableLimiters[0]} and ${readableLimiters[1]}`;
  }

  return readableLimiters.join(", ");
};

const normalizePercent = (value: number | undefined | null): number => {
  if (value === undefined || value === null) return 0;
  if (value <= 1 && value > 0) {
    return Math.min(Math.round(value * 100), 100);
  }
  return Math.min(Math.round(value), 100);
};

export default function RecommendationReadinessGate({
  isOpen,
  onClose,
  onContinue,
  repositoryId,
  pullRequestId,
  action,
  recommendationRunId,
  generationStatus = "idle"
}: RecommendationReadinessGateProps) {
  const router = useRouter();
  const [readinessData, setReadinessData] = useState<ReadinessData | null>(null);
  const [loading, setLoading] = useState(true);
  const [readinessError, setReadinessError] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshErrorCode, setRefreshErrorCode] = useState<string | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [isAvailableInputsCollapsed, setIsAvailableInputsCollapsed] = useState(true);
  const [isOptionalLearningCollapsed, setIsOptionalLearningCollapsed] = useState(true);

  const fetchReadinessData = useCallback(async () => {
    try {
      setLoading(true);
      setReadinessError(null);
      
      const url = pullRequestId 
        ? `/api/repositories/${repositoryId}/pull-requests/${pullRequestId}/readiness`
        : `/api/repositories/${repositoryId}/readiness`;
      
      const response = await fetch(url);
      
      if (!response.ok) {
        if (response.status === 401) {
          return;
        }
        throw new Error(`Failed to fetch readiness data: ${response.status}`);
      }
      
      const data = await response.json();
      setReadinessData(data);
    } catch (err) {
      console.error('[ReadinessGate] Error fetching readiness:', err);
      setReadinessError(err instanceof Error ? err.message : "Failed to load readiness data");
    } finally {
      setLoading(false);
    }
  }, [repositoryId, pullRequestId]);

  useEffect(() => {
    if (isOpen) {
      setRefreshError(null);
      setRefreshErrorCode(null);
      fetchReadinessData();
    }
  }, [isOpen, fetchReadinessData]);



  const handleContinue = async () => {
    if (action === "view" && recommendationRunId) {
      try {
        setLoading(true);
        const missingSignalsList = readinessData?.missing_inputs.map(s => s.key) || [];
        const response = await fetch(`/api/recommendations/${recommendationRunId}/acknowledge-readiness`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            acknowledged_missing_inputs: missingSignalsList,
            decision: "CONTINUE_ANYWAY"
          }),
        });
        if (!response.ok) {
          throw new Error("Failed to acknowledge readiness");
        }
      } catch (err: any) {
        console.error("Error acknowledging readiness:", err);
        setRefreshError(err.message || "Failed to acknowledge readiness");
        setLoading(false);
        return;
      } finally {
        setLoading(false);
      }
      // For "view" action, close modal after acknowledging
      onContinue();
      onClose();
    } else {
      // For "generate" action, let the parent handle the modal close after generation completes
      onContinue();
    }
  };

  const handleActionButtonClick = async (key: string) => {
    const action = getMissingInputAction(key);

    if (!action.enabled) {
      // Disabled actions show their disabled reason, no fallback
      return;
    }

    setActionInProgress(key);

    switch (action.actionType) {
      case "PASTE_ACCEPTANCE_CRITERIA":
        setIsFormOpen(true);
        setActionInProgress(null);
        break;
      case "ATTACH_TEST_RUN":
      case "UPLOAD_TEST_RESULTS": {
        // Validate repositoryId
        if (!repositoryId) {
          setRefreshError("Repository context missing. Cannot navigate to upload page.");
          setActionInProgress(null);
          return;
        }

        // Build URL synchronously
        const queryParams = new URLSearchParams();
        if (pullRequestId) queryParams.append("pullRequestId", pullRequestId);
        queryParams.append("returnTo", "readiness");
        queryParams.append("source", "missing_input_gate");
        queryParams.append("inputType", "test-history");
        const uploadUrl = `/app/repositories/${repositoryId}/test-history?${queryParams.toString()}`;

        // Navigate immediately without waiting for any API calls
        try {
          router.push(uploadUrl);
        } catch (err) {
          console.error("Navigation failed:", err);
          setRefreshError("Failed to navigate to upload page. Please try again.");
          setActionInProgress(null);
        }
        // Note: We don't clear actionInProgress on success because navigation will unmount this component
        break;
      }
      case "ATTACH_COVERAGE":
      case "UPLOAD_COVERAGE": {
        // Validate repositoryId
        if (!repositoryId) {
          setRefreshError("Repository context missing. Cannot navigate to upload page.");
          setActionInProgress(null);
          return;
        }

        // Build URL synchronously
        const queryParams = new URLSearchParams();
        if (pullRequestId) queryParams.append("pullRequestId", pullRequestId);
        queryParams.append("returnTo", "readiness");
        queryParams.append("source", "missing_input_gate");
        queryParams.append("inputType", "coverage");
        const uploadUrl = `/app/repositories/${repositoryId}/coverage?${queryParams.toString()}`;

        // Navigate immediately without waiting for any API calls
        try {
          router.push(uploadUrl);
        } catch (err) {
          console.error("Navigation failed:", err);
          setRefreshError("Failed to navigate to upload page. Please try again.");
          setActionInProgress(null);
        }
        break;
      }
      case "UPLOAD_MANUAL_TESTS":
        router.push(`/app/repositories/${repositoryId}/integrations`);
        setActionInProgress(null);
        break;
      case "LINK_WORK_ITEM":
        router.push(`/app/repositories/${repositoryId}/integrations`);
        setActionInProgress(null);
        break;
      case "RUN_REPOSITORY_INTELLIGENCE":
        try {
          setRefreshError(null);
          setRefreshErrorCode(null);
          const response = await fetch(`/api/repositories/${repositoryId}/intelligence/refresh`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              include_architecture: true,
              include_behaviors: true,
              include_journeys: true,
            }),
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error("Failed to refresh repository intelligence:", errorData.error || response.statusText);
            setRefreshError(errorData.error || response.statusText || "Failed to refresh repository intelligence.");
            setRefreshErrorCode(errorData.error_code || null);
          } else {
            setRefreshError(null);
            setRefreshErrorCode(null);
            // Refresh readiness data after successful intelligence refresh
            await fetchReadinessData();
          }
        } catch (err) {
          console.error("Error refreshing repository intelligence:", err);
          setRefreshError(err instanceof Error ? err.message : "Failed to refresh repository intelligence. Please try again.");
          setRefreshErrorCode(null);
        } finally {
          setActionInProgress(null);
        }
        break;
      case "SKIP_OPTIONAL":
        // No action needed for optional skip
        setActionInProgress(null);
        break;
      case "NONE":
        // No action for not required inputs
        setActionInProgress(null);
        break;
      default:
        console.warn(`Unknown action type: ${action.actionType}`);
        setActionInProgress(null);
    }
  };

  const handleRetryRefresh = async () => {
    if (refreshErrorCode === "SOURCE_NOT_SYNCED") {
      try {
        setActionInProgress("sync");
        setRefreshError(null);
        
        const syncResponse = await fetch(`/api/repositories/${repositoryId}/sync`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        });
        
        if (!syncResponse.ok) {
          const errorData = await syncResponse.json().catch(() => ({}));
          throw new Error(errorData.error || syncResponse.statusText || "Sync failed");
        }
        
        // Success syncing. Now trigger intelligence refresh
        setActionInProgress("architecture_graph");
        const refreshResponse = await fetch(`/api/repositories/${repositoryId}/intelligence/refresh`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            include_architecture: true,
            include_behaviors: true,
            include_journeys: true,
          }),
        });
        
        if (!refreshResponse.ok) {
          const errorData = await refreshResponse.json().catch(() => ({}));
          setRefreshError(errorData.error || refreshResponse.statusText || "Failed to refresh repository intelligence.");
          setRefreshErrorCode(errorData.error_code || null);
        } else {
          setRefreshError(null);
          setRefreshErrorCode(null);
          await fetchReadinessData();
        }
      } catch (err: any) {
        console.error("Error syncing and refreshing:", err);
        setRefreshError(err.message || "Sync and refresh failed.");
        setRefreshErrorCode("SOURCE_NOT_SYNCED"); // Keep code so they can retry
      } finally {
        setActionInProgress(null);
      }
    } else {
      // Just retry the intelligence refresh
      await handleActionButtonClick("architecture_graph");
    }
  };

  const handleActionSuccess = async (_updatedResponse: any, _recommendationStale: boolean = false) => {
    // Do NOT set readiness state from the modal's return value — it may be a partial/wrapped object.
    // Always re-fetch the authoritative, complete state from the backend API.
    await fetchReadinessData();
    // The parent component will handle recommendation staleness via onReadinessUpdated callbacks.
  };

  const getConfidenceColor = (conf: string) => {
    switch (conf?.toUpperCase()) {
      case "HIGH":
        return "text-emerald-400 bg-emerald-950/30 border-emerald-500/20";
      case "MEDIUM":
      case "MODERATE":
        return "text-amber-400 bg-amber-950/30 border-amber-500/20";
      case "LOW":
        return "text-zinc-400 bg-zinc-800/40 border-zinc-700/50";
      default:
        return "text-zinc-400 bg-zinc-800/40 border-zinc-700/50";
    }
  };

  const getReadinessBadge = (level: string) => {
    const formatted = level?.replace(/_/g, " ");
    switch (level?.toUpperCase()) {
      case "HIGH_CONFIDENCE_READY":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full border border-emerald-500/30 bg-emerald-950/20 text-emerald-400">High Confidence Ready</span>;
      case "REGRESSION_READY":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full border border-sky-500/30 bg-sky-950/20 text-sky-400">Regression Ready</span>;
      case "MINIMUM_READY":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full border border-amber-500/30 bg-amber-950/20 text-amber-400">Minimum Ready</span>;
      case "BLOCKED":
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full border border-rose-500/30 bg-rose-950/20 text-rose-400">Blocked</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full border border-zinc-700 bg-zinc-800/40 text-zinc-400">{formatted}</span>;
    }
  };

  const isACMissing = readinessData?.missing_inputs.some(s => s.key === "acceptance_criteria") || false;
  const groupedMissingInputs = readinessData?.missing_inputs ? groupMissingInputs(readinessData.missing_inputs) : { USER_INPUTS: [], SYSTEM_INTELLIGENCE: [], OPTIONAL_LEARNING: [] };
  const showGroupedSystemIntelligenceCTA = readinessData?.missing_inputs ? shouldShowGroupedSystemIntelligenceCTA(readinessData.missing_inputs) : false;
  
  // Use centralized CTA resolver
  const ctaAction = readinessData ? resolveRecommendationAction({
    readiness_level: readinessData.readiness_level,
    expected_confidence: readinessData.expected_confidence,
    readiness_score: readinessData.readiness_score,
    can_generate: readinessData.can_generate,
    blocking_inputs: readinessData.confidence_blockers?.map(b => ({ key: b, label: b })) || [],
    missing_inputs: readinessData.missing_inputs || [],
    optional_inputs: readinessData.missing_inputs?.filter(s => s.severity === "OPTIONAL") || [],
    latest_recommendation: {
      exists: action === "view",
      input_stale: false
    }
  }) : null;
  
  const readinessSummary = readinessData ? getReadinessSummary({
    readiness_level: readinessData.readiness_level,
    expected_confidence: readinessData.expected_confidence,
    readiness_score: readinessData.readiness_score,
    can_generate: readinessData.can_generate,
    blocking_inputs: readinessData.confidence_blockers?.map(b => ({ key: b, label: b })) || [],
    missing_inputs: readinessData.missing_inputs || [],
    optional_inputs: readinessData.missing_inputs?.filter(s => s.severity === "OPTIONAL") || [],
    latest_recommendation: {
      exists: action === "view",
      input_stale: false
    }
  }) : null;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          />

          {/* Modal Container */}
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
            <motion.div 
              initial={{ scale: 0.96, y: 15, opacity: 0 }}
              animate={{ scale: 1, y: 0, opacity: 1 }}
              exit={{ scale: 0.96, y: 15, opacity: 0 }}
              transition={{ type: "spring", duration: 0.4 }}
              className="bg-zinc-950 border border-zinc-800/80 rounded-2xl max-w-2xl w-full max-h-[92vh] flex flex-col overflow-hidden pointer-events-auto shadow-2xl"
            >
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-zinc-900 bg-zinc-950">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-indigo-400" />
                  <h2 className="text-xl font-bold text-white tracking-tight">{readinessSummary?.title || "Recommendation Readiness"}</h2>
                </div>
                <Button variant="ghost" size="icon" onClick={onClose} className="text-zinc-400 hover:text-white rounded-lg">
                  <X className="w-5 h-5" />
                </Button>
              </div>

              {/* Scrollable Content */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {loading ? (
                  <div className="text-center py-16">
                    <div className="animate-spin w-9 h-9 border-2 border-zinc-700 border-t-indigo-500 rounded-full mx-auto mb-4"></div>
                    <p className="text-sm text-zinc-400 font-medium">Evaluating current evidence & signal health...</p>
                  </div>
                ) : readinessError ? (
                  <div className="text-center py-12 bg-rose-950/10 border border-rose-900/20 rounded-xl">
                    <AlertTriangle className="w-10 h-10 text-rose-500 mx-auto mb-4" />
                    <p className="text-sm text-rose-200 mb-2 font-semibold">Readiness assessment failed. Retry assessment before continuing.</p>
                    <p className="text-xs text-rose-300/80 mb-4">{readinessError}</p>
                    <Button onClick={fetchReadinessData} variant="outline" className="border-zinc-800 text-zinc-300">Retry Assessment</Button>
                  </div>
                ) : readinessData ? (
                  <>
                    {/* Compact Summary Block */}
                    <div className="bg-zinc-900/20 border border-zinc-900/60 rounded-xl p-4 space-y-2">
                      <p className="text-zinc-300 text-sm leading-relaxed">
                        Veriscope can {action === "view" ? "show" : "generate"} this recommendation with{' '}
                        <span className="font-semibold text-white">{readinessData.expected_confidence.toLowerCase()}</span> confidence based on current evidence.
                      </p>
                      {(() => {
                        // Determine the second line based on state
                        if (readinessData.readiness_level === "BLOCKED") {
                          const blockers = readinessData.confidence_blockers || [];
                          const blockerText = blockers.length > 0
                            ? KEY_TO_READABLE[blockers[0]] || blockers[0]
                            : 'missing required signals';
                          return (
                            <p className="text-zinc-400 text-xs leading-relaxed">
                              Generation is blocked because <span className="text-rose-400 font-medium">{blockerText}</span> is missing.
                            </p>
                          );
                        }

                        const limiters = readinessData.confidence_limiters || [];
                        if (limiters.length > 0 && readinessData.release_confidence_ceiling !== "HIGH") {
                          const formattedLimiters = formatConfidenceLimiters(limiters);
                          return (
                            <p className="text-zinc-400 text-xs leading-relaxed">
                              Confidence is capped because <span className="text-amber-400 font-medium">{formattedLimiters}</span> are missing.
                            </p>
                          );
                        }

                        return (
                          <p className="text-zinc-400 text-xs leading-relaxed">
                            Evidence is sufficient to generate a recommendation.
                          </p>
                        );
                      })()}
                    </div>

                    {refreshError && (
                      <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-rose-950/10 border border-rose-500/20 text-rose-200 rounded-xl p-4 text-xs leading-relaxed flex gap-3 items-start"
                      >
                        <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <p className="font-semibold text-rose-100">Repository intelligence refresh failed</p>
                          <p className="mt-0.5">
                            {refreshError}
                          </p>
                          <p className="mt-1.5 text-rose-300/80">
                            You can continue with current evidence, but architecture/behavior/journey signals may be missing.
                          </p>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={handleRetryRefresh}
                          disabled={actionInProgress !== null}
                          className="border-rose-800/40 bg-rose-950/20 hover:bg-rose-950/30 text-rose-200 hover:text-rose-100 rounded-lg text-xs shrink-0 self-center"
                        >
                          {actionInProgress ? (
                            <span className="flex items-center gap-1.5">
                              <Loader2 className="w-3 h-3 animate-spin" />
                              Processing...
                            </span>
                          ) : (
                            refreshErrorCode === "SOURCE_NOT_SYNCED" ? "Sync Repository First" : "Retry Refresh"
                          )}
                        </Button>
                      </motion.div>
                    )}

                    {/* Recommended Next Action Card */}
                    {ctaAction && ctaAction.actionType === "generate" && (
                      <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-indigo-950/10 border border-indigo-500/20 text-indigo-300/90 rounded-xl p-4 text-xs leading-relaxed flex gap-3 items-start"
                      >
                        <Sparkles className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <p className="font-semibold text-indigo-200">Recommended next action</p>
                          <p className="mt-0.5">{ctaAction.primaryLabel}</p>
                          <p className="mt-0.5 text-zinc-400">{readinessSummary?.summary}</p>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={handleContinue}
                          disabled={loading}
                          className="border-indigo-600/30 bg-indigo-950/20 hover:bg-indigo-950/30 text-indigo-300 hover:text-indigo-200 rounded-lg text-xs shrink-0"
                        >
                          {ctaAction.primaryLabel}
                        </Button>
                      </motion.div>
                    )}

                    {/* Available Inputs Section */}
                    <div className="space-y-3">
                      <button
                        onClick={() => setIsAvailableInputsCollapsed(!isAvailableInputsCollapsed)}
                        className="flex items-center gap-2 text-xs font-bold text-zinc-400 uppercase tracking-wider hover:text-zinc-300 transition-colors"
                      >
                        <ChevronRight className={`w-4 h-4 transition-transform ${isAvailableInputsCollapsed ? '' : 'rotate-90'}`} />
                        Available Inputs
                      </button>
                      {!isAvailableInputsCollapsed && (
                        <div className="border border-zinc-900 rounded-xl divide-y divide-zinc-900 bg-zinc-900/10 overflow-hidden">
                          {Object.entries(ALL_SIGNALS_MAP).map(([key, info]) => {
                            const matchingSignal = readinessData.available_inputs.find(s => s.key === key);
                            const isAvailable = !!matchingSignal;
                            const evidenceCount = matchingSignal?.evidence_count ?? 0;
                            const SignalIcon = info.icon;

                            return (
                              <div key={key} className="flex items-center justify-between p-3.5 gap-4">
                                <div className="flex items-start gap-3 min-w-0">
                                  <div className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 mt-0.5 ${
                                    isAvailable ? "border-emerald-500/10 bg-emerald-950/10 text-emerald-400" : "border-zinc-800 bg-zinc-900/30 text-zinc-500"
                                  }`}>
                                    <SignalIcon className="w-4 h-4" />
                                  </div>
                                  <div className="min-w-0">
                                    <div className="flex items-center gap-2">
                                      <span className={`text-sm font-semibold ${isAvailable ? "text-zinc-200" : "text-zinc-500"}`}>
                                        {info.label}
                                      </span>
                                      {isAvailable && evidenceCount > 0 && (
                                        <span className="text-[10px] bg-zinc-900 border border-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded font-mono font-medium">
                                          {evidenceCount} {info.unit}
                                        </span>
                                      )}
                                    </div>
                                    <p className="text-xs text-zinc-500 truncate mt-0.5">
                                      {info.impact}
                                    </p>
                                  </div>
                                </div>
                                <div className="shrink-0">
                                  {isAvailable ? (
                                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                                  ) : (
                                    <Circle className="w-4 h-4 text-zinc-800" />
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* Missing Inputs Section */}
                    {(groupedMissingInputs.USER_INPUTS.length > 0 || groupedMissingInputs.SYSTEM_INTELLIGENCE.length > 0 || groupedMissingInputs.OPTIONAL_LEARNING.length > 0) && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
                            {groupedMissingInputs.USER_INPUTS.length === 0 && groupedMissingInputs.SYSTEM_INTELLIGENCE.length === 0 
                              ? "Optional improvements" 
                              : "Missing Inputs"}
                          </h3>
                          <p className="text-xs text-zinc-500">
                            {groupedMissingInputs.USER_INPUTS.length === 0 && groupedMissingInputs.SYSTEM_INTELLIGENCE.length === 0
                              ? "These are not required to generate this recommendation."
                              : "Improve these inputs before generating:"}
                          </p>
                        </div>

                        {/* User Inputs Needed */}
                        {groupedMissingInputs.USER_INPUTS.length > 0 && (
                          <div className="space-y-2">
                            <h4 className="text-xs font-semibold text-zinc-300">User Inputs Needed</h4>
                            <div className="grid grid-cols-1 gap-2">
                              {sortMissingInputs(groupedMissingInputs.USER_INPUTS)
                                .filter(signal => signal.key !== getRecommendedNextAction(readinessData.missing_inputs)?.key)
                                .map((signal) => {
                                const action = getMissingInputAction(signal.key);
                                const SignalIcon = action.icon;
                                const label = getMissingInputLabel(signal.key, signal.label);
                                const badge = getMissingInputBadge(signal.severity, action.group);
                                const impact = getMissingInputImpact(signal.key, signal.impact);
                                const confidenceGain = getConfidenceGain(signal.key, signal.estimated_confidence_gain);

                                return (
                                  <motion.div
                                    key={signal.key}
                                    whileHover={{ scale: 1.01, borderColor: "rgba(63, 63, 70, 0.8)" }}
                                    className="bg-zinc-900/10 border border-zinc-900 p-3 rounded-xl flex flex-col md:flex-row md:items-center md:justify-between gap-3 transition-colors"
                                  >
                                    <div className="flex items-start gap-3 min-w-0 flex-1">
                                      <div className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 mt-0.5 ${
                                        action.enabled
                                          ? "border-zinc-700 bg-zinc-900/60 text-zinc-300"
                                          : "border-zinc-800 bg-zinc-900/30 text-zinc-500"
                                      }`}>
                                        <SignalIcon className="w-4 h-4" />
                                      </div>
                                      <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2 flex-wrap">
                                          <span className="text-sm font-semibold text-zinc-200">
                                            {label}
                                          </span>
                                          <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wide border ${
                                            signal.severity === "REQUIRED"
                                              ? "text-rose-400 bg-rose-950/20 border-rose-900/30"
                                              : signal.severity === "RECOMMENDED"
                                              ? "text-amber-400 bg-amber-950/20 border-amber-900/30"
                                              : "text-zinc-400 bg-zinc-800/40 border-zinc-700/50"
                                          }`}>
                                            {badge}
                                          </span>
                                          {confidenceGain > 0 && (
                                            <span className="text-[10px] text-indigo-400 font-medium font-mono">
                                              +{confidenceGain}% confidence
                                            </span>
                                          )}
                                        </div>
                                        <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                                          {impact}
                                        </p>
                                        {!action.enabled && action.disabledReason && (
                                          <p className="text-[10px] text-zinc-500 mt-1 italic">
                                            {action.disabledReason}
                                          </p>
                                        )}
                                      </div>
                                    </div>
                                    <div className="shrink-0 self-start md:self-center">
                                      {action.enabled ? (
                                        <Button
                                          variant="outline"
                                          size="sm"
                                          onClick={() => handleActionButtonClick(signal.key)}
                                          disabled={actionInProgress === signal.key}
                                          className="border-zinc-700 hover:border-zinc-600 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-lg text-xs"
                                        >
                                          {actionInProgress === signal.key ? (
                                            <span className="flex items-center gap-1.5">
                                              <Loader2 className="w-3 h-3 animate-spin" />
                                              {action.actionType === "UPLOAD_TEST_RESULTS" ||
                                               action.actionType === "ATTACH_TEST_RUN" ||
                                               action.actionType === "UPLOAD_COVERAGE" ||
                                               action.actionType === "ATTACH_COVERAGE"
                                                ? "Opening upload..."
                                                : "Processing..."}
                                            </span>
                                          ) : (
                                            action.label
                                          )}
                                        </Button>
                                      ) : null}
                                    </div>
                                  </motion.div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* System Intelligence Missing */}
                        {groupedMissingInputs.SYSTEM_INTELLIGENCE.length > 0 && (
                          <div className="space-y-2">
                            <h4 className="text-xs font-semibold text-zinc-300">System Intelligence Missing</h4>
                            {showGroupedSystemIntelligenceCTA ? (
                              <motion.div
                                whileHover={{ scale: 1.01, borderColor: "rgba(63, 63, 70, 0.8)" }}
                                className="bg-zinc-900/10 border border-zinc-900 p-3 rounded-xl flex flex-col md:flex-row md:items-center md:justify-between gap-3 transition-colors"
                              >
                                <div className="flex items-start gap-3 min-w-0 flex-1">
                                  <div className="w-8 h-8 rounded-lg border border-zinc-700 bg-zinc-900/60 text-zinc-300 flex items-center justify-center shrink-0 mt-0.5">
                                    <Sparkles className="w-4 h-4" />
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-2 flex-wrap">
                                      <span className="text-sm font-semibold text-zinc-200">
                                        Multiple system intelligence signals missing
                                      </span>
                                      <span className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wide border text-indigo-400 bg-indigo-950/20 border-indigo-900/30">
                                        System intelligence
                                      </span>
                                    </div>
                                    <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                                      Architecture graph, behavior catalog, and/or journey catalog are missing. Run repository intelligence to generate these.
                                    </p>
                                  </div>
                                </div>
                                <div className="shrink-0 self-start md:self-center">
                                  <Button 
                                    variant="outline" 
                                    size="sm"
                                    onClick={() => handleActionButtonClick("architecture_graph")}
                                    disabled={actionInProgress === "architecture_graph"}
                                    className="border-zinc-700 hover:border-zinc-600 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-lg text-xs"
                                  >
                                    {actionInProgress === "architecture_graph" ? (
                                      <span className="flex items-center gap-1.5">
                                        <Loader2 className="w-3 h-3 animate-spin" />
                                        Processing...
                                      </span>
                                    ) : (
                                      "Run Repository Intelligence"
                                    )}
                                  </Button>
                                </div>
                              </motion.div>
                            ) : (
                              <div className="grid grid-cols-1 gap-2">
                                {sortMissingInputs(groupedMissingInputs.SYSTEM_INTELLIGENCE).map((signal) => {
                                  const action = getMissingInputAction(signal.key);
                                  const SignalIcon = action.icon;
                                  const label = getMissingInputLabel(signal.key, signal.label);
                                  const badge = getMissingInputBadge(signal.severity, action.group);
                                  const impact = getMissingInputImpact(signal.key, signal.impact);
                                  const confidenceGain = getConfidenceGain(signal.key, signal.estimated_confidence_gain);
                                  
                                  return (
                                    <motion.div 
                                      key={signal.key}
                                      whileHover={{ scale: 1.01, borderColor: "rgba(63, 63, 70, 0.8)" }}
                                      className="bg-zinc-900/10 border border-zinc-900 p-3 rounded-xl flex flex-col md:flex-row md:items-center md:justify-between gap-3 transition-colors"
                                    >
                                      <div className="flex items-start gap-3 min-w-0 flex-1">
                                        <div className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 mt-0.5 ${
                                          action.enabled 
                                            ? "border-zinc-700 bg-zinc-900/60 text-zinc-300" 
                                            : "border-zinc-800 bg-zinc-900/30 text-zinc-500"
                                        }`}>
                                          <SignalIcon className="w-4 h-4" />
                                        </div>
                                        <div className="min-w-0 flex-1">
                                          <div className="flex items-center gap-2 flex-wrap">
                                            <span className="text-sm font-semibold text-zinc-200">
                                              {label}
                                            </span>
                                            <span className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wide border text-indigo-400 bg-indigo-950/20 border-indigo-900/30">
                                              {badge}
                                            </span>
                                            {confidenceGain > 0 && (
                                              <span className="text-[10px] text-indigo-400 font-medium font-mono">
                                                +{confidenceGain}% confidence
                                              </span>
                                            )}
                                          </div>
                                          <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                                            {impact}
                                          </p>
                                        </div>
                                      </div>
                                      <div className="shrink-0 self-start md:self-center">
                                        {action.enabled && (
                                          <Button 
                                            variant="outline" 
                                            size="sm"
                                            onClick={() => handleActionButtonClick(signal.key)}
                                            disabled={actionInProgress === signal.key}
                                            className="border-zinc-700 hover:border-zinc-600 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-lg text-xs"
                                          >
                                            {actionInProgress === signal.key ? (
                                              <span className="flex items-center gap-1.5">
                                                <Loader2 className="w-3 h-3 animate-spin" />
                                                Processing...
                                              </span>
                                            ) : (
                                              action.label
                                            )}
                                          </Button>
                                        )}
                                      </div>
                                    </motion.div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Optional Learning Signals */}
                        {groupedMissingInputs.OPTIONAL_LEARNING.length > 0 && (
                          <div className="space-y-3">
                            <button
                              onClick={() => setIsOptionalLearningCollapsed(!isOptionalLearningCollapsed)}
                              className="flex items-center gap-2 text-xs font-semibold text-zinc-300 hover:text-zinc-200 transition-colors"
                            >
                              <ChevronRight className={`w-4 h-4 transition-transform ${isOptionalLearningCollapsed ? '' : 'rotate-90'}`} />
                              Optional improvements
                            </button>
                            {!isOptionalLearningCollapsed && (
                              <div className="grid grid-cols-1 gap-3">
                                {sortMissingInputs(groupedMissingInputs.OPTIONAL_LEARNING).map((signal) => {
                                  const action = getMissingInputAction(signal.key);
                                const SignalIcon = action.icon;
                                const label = getOptionalGapLabel(signal.key, signal.label);
                                const badge = getMissingInputBadge(signal.severity, action.group);
                                const impact = getMissingInputImpact(signal.key, signal.impact);
                                const confidenceGain = getConfidenceGain(signal.key, signal.estimated_confidence_gain);

                                // Special handling for linked_work_item to show alternative CTA
                                const isLinkedWorkItem = signal.key === "linked_work_item";
                                const showAlternativeCTA = isLinkedWorkItem && !action.enabled;

                                return (
                                  <motion.div
                                    key={signal.key}
                                    whileHover={{ scale: 1.01, borderColor: "rgba(63, 63, 70, 0.8)" }}
                                    className="bg-zinc-900/10 border border-zinc-900 p-3 rounded-xl flex flex-col md:flex-row md:items-center md:justify-between gap-3 transition-colors"
                                  >
                                    <div className="flex items-start gap-3 min-w-0 flex-1">
                                      <div className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 mt-0.5 ${
                                        action.enabled
                                          ? "border-zinc-700 bg-zinc-900/60 text-zinc-300"
                                          : "border-zinc-800 bg-zinc-900/30 text-zinc-500"
                                      }`}>
                                        <SignalIcon className="w-4 h-4" />
                                      </div>
                                      <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2 flex-wrap">
                                          <span className="text-sm font-semibold text-zinc-200">
                                            {label}
                                          </span>
                                          <span className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wide border text-zinc-400 bg-zinc-800/40 border-zinc-700/50">
                                            {badge}
                                          </span>
                                          {confidenceGain > 0 && (
                                            <span className="text-[10px] text-indigo-400 font-medium font-mono">
                                              +{confidenceGain}% confidence
                                            </span>
                                          )}
                                        </div>
                                        <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                                          {impact}
                                        </p>
                                        {!action.enabled && action.disabledReason && (
                                          <p className="text-[10px] text-zinc-500 mt-1 italic">
                                            {action.disabledReason}
                                          </p>
                                        )}
                                      </div>
                                    </div>
                                    <div className="shrink-0 self-start md:self-center">
                                      {action.enabled ? (
                                        <Button
                                          variant="outline"
                                          size="sm"
                                          onClick={() => handleActionButtonClick(signal.key)}
                                          disabled={actionInProgress === signal.key}
                                          className="border-zinc-700 hover:border-zinc-600 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-lg text-xs"
                                        >
                                          {actionInProgress === signal.key ? (
                                            <span className="flex items-center gap-1.5">
                                              <Loader2 className="w-3 h-3 animate-spin" />
                                              {action.actionType === "UPLOAD_TEST_RESULTS" ||
                                               action.actionType === "ATTACH_TEST_RUN" ||
                                               action.actionType === "UPLOAD_COVERAGE" ||
                                               action.actionType === "ATTACH_COVERAGE"
                                                ? "Opening upload..."
                                                : "Processing..."}
                                            </span>
                                          ) : (
                                            action.label
                                          )}
                                        </Button>
                                      ) : showAlternativeCTA ? (
                                        <Button
                                          variant="outline"
                                          size="sm"
                                          onClick={() => handleActionButtonClick("acceptance_criteria")}
                                          disabled={actionInProgress === "acceptance_criteria"}
                                          className="border-zinc-700 hover:border-zinc-600 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-lg text-xs"
                                        >
                                          {actionInProgress === "acceptance_criteria" ? (
                                            <span className="flex items-center gap-1.5">
                                              <Loader2 className="w-3 h-3 animate-spin" />
                                              Processing...
                                            </span>
                                          ) : (
                                            "Paste Acceptance Criteria"
                                          )}
                                        </Button>
                                      ) : (
                                        <span className="text-[10px] text-zinc-500 px-2 py-1 rounded bg-zinc-800/40 border border-zinc-700/50">
                                          Coming soon
                                        </span>
                                      )}
                                    </div>
                                  </motion.div>
                                );
                              })}
                            </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : null}
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between p-6 border-t border-zinc-900 bg-zinc-950">
                <div className="text-xs text-zinc-500 font-mono font-medium">
                  {readinessData && (
                    <span>Completeness: {normalizePercent(readinessData.intelligence_completeness_score ?? readinessData.readiness_score)}%</span>
                  )}
                </div>
                <div className="flex gap-3">
                  <Button 
                    variant="ghost" 
                    onClick={onClose}
                    className="text-zinc-400 hover:text-white rounded-lg"
                  >
                    Cancel
                  </Button>
                  {ctaAction?.showContinueAnyway ? (
                    <>
                      <Button
                        variant="outline"
                        onClick={handleContinue}
                        disabled={loading || generationStatus !== "idle"}
                        className="rounded-lg font-semibold tracking-tight transition-all border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                      >
                        {ctaAction.secondaryLabel || "Continue Anyway"}
                      </Button>
                      <Button
                        onClick={handleContinue}
                        disabled={loading || generationStatus !== "idle"}
                        className="rounded-lg font-semibold tracking-tight transition-all bg-white text-zinc-950 hover:bg-zinc-100 shadow-md shadow-white/5 active:scale-[0.98]"
                      >
                        {generationStatus === "generating" ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Generating...
                          </>
                        ) : generationStatus === "redirecting" ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Opening...
                          </>
                        ) : (
                          ctaAction.primaryLabel
                        )}
                      </Button>
                    </>
                  ) : (
                    <Button
                      onClick={handleContinue}
                      disabled={loading || !readinessData?.can_generate || generationStatus !== "idle"}
                      className={`rounded-lg font-semibold tracking-tight transition-all ${
                        ctaAction?.tone === "positive"
                          ? "bg-emerald-600 text-white hover:bg-emerald-500 shadow-md shadow-emerald-500/10 active:scale-[0.98]"
                          : ctaAction?.tone === "caution"
                          ? "bg-amber-600 text-white hover:bg-amber-500 shadow-md shadow-amber-500/10 active:scale-[0.98]"
                          : ctaAction?.tone === "warning"
                          ? "bg-rose-600 text-white hover:bg-rose-500 shadow-md shadow-rose-500/10 active:scale-[0.98]"
                          : "bg-white text-zinc-950 hover:bg-zinc-100 shadow-md shadow-white/5 active:scale-[0.98]"
                      }`}
                    >
                      {generationStatus === "generating" ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Generating...
                        </>
                      ) : generationStatus === "redirecting" ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Opening...
                        </>
                      ) : (
                        ctaAction?.primaryLabel || "Continue"
                      )}
                    </Button>
                  )}
                </div>
              </div>
            </motion.div>
          </div>

          {/* Submodal for Acceptance Criteria Submission */}
          <PasteAcceptanceCriteriaModal
            isOpen={isFormOpen}
            onClose={() => setIsFormOpen(false)}
            onSuccess={handleActionSuccess}
            repositoryId={repositoryId}
            pullRequestId={pullRequestId}
          />
        </>
      )}
    </AnimatePresence>
  );
}
