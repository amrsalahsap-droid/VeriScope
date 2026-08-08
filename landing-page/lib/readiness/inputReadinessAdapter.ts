/**
 * Unified Input Readiness V2 View Model Adapter
 *
 * Normalizes the backend 12-input readiness response into a single canonical view model
 * used by every readiness-related UI section. No section should independently infer
 * readiness or missing-input state.
 */

export type InputStatus =
  | "READY"
  | "PARTIAL"
  | "PARTIAL_READY"
  | "NO_CHANGED_FILE_COVERAGE"
  | "TEST_LEVEL_READY"
  | "PARTIAL_EMPTY"
  | "MISSING"
  | "BLOCKED"
  | "NEEDS_REVIEW"
  | "REVIEW_REQUIRED"
  | "STALE"
  | "HISTORICAL_ONLY"
  | "NOT_APPLICABLE";

export type GenerationStatus =
  | "BLOCKED"
  | "DRAFT_ONLY"
  | "MINIMUM_READY"
  | "CONFIDENT_READY"
  | "HIGH_CONFIDENCE_READY";

export type CanGenerate = false | "DRAFT_ONLY" | true;

export interface InputReadinessActionViewModel {
  input_id: string;
  label: string;
  action: string;
  reason: string;
  priority: number;
}

export interface InputReadinessItemViewModel {
  input_id: string;
  label: string;
  status: InputStatus;
  weight: number;
  earned_score: number;
  max_score: number;
  is_hard_blocker: boolean;
  summary: string;
  details: Record<string, unknown>;
  actions: Array<{ label: string; action: string }>;
}

export interface InputReadinessBlockerViewModel {
  input_id: string;
  code: string;
  message: string;
}

export interface InputReadinessViewModel {
  generationStatus: GenerationStatus;
  canGenerate: CanGenerate;
  confidenceScore: number;
  confidenceLevel: "LOW" | "MEDIUM" | "HIGH";
  confidenceCeiling: "LOW" | "MEDIUM" | "HIGH";
  primaryMessage: string;
  inputs: Record<string, InputReadinessItemViewModel>;
  inputsList: InputReadinessItemViewModel[];
  hardBlockers: InputReadinessBlockerViewModel[];
  missingConfidenceBoosters: InputReadinessBlockerViewModel[];
  nextBestActions: InputReadinessActionViewModel[];
  readyCount: number;
  missingCount: number;
  // New confidence concepts
  evidenceCompleteness: number;
  releaseConfidence: string;
  confidenceCeilingReason: string;
}

export interface RawInputReadinessV2Response {
  generation_status: string;
  can_generate: string | boolean;
  confident_generation: boolean;
  confidence_score: number;
  confidence_level: string;
  confidence_ceiling: string;
  primary_message: string;
  blockers?: Array<{ input_id: string; code: string; message: string }>;
  warnings?: Array<{ input_id: string; code: string; message: string }>;
  inputs?: Array<{
    input_id: string;
    label: string;
    status: string;
    weight: number;
    earned_score: number;
    max_score: number;
    is_hard_blocker: boolean;
    summary: string;
    details?: Record<string, unknown>;
    actions?: Array<{ label: string; action: string }>;
  }>;
  next_best_actions?: Array<{
    priority: number;
    input_id: string;
    label: string;
    reason: string;
    action?: string;
  }>;
  // New confidence concepts
  evidence_completeness?: number;
  release_confidence?: string;
  confidence_ceiling_reason?: string;
}

const NON_READY_STATUSES = new Set<InputStatus>([
  "MISSING",
  "BLOCKED",
  "NEEDS_REVIEW",
  "REVIEW_REQUIRED",
  "STALE",
  "HISTORICAL_ONLY",
  "PARTIAL",
]);

function normalizeStatus(status: string): InputStatus {
  const s = (status || "MISSING").toUpperCase();
  if (
    s === "READY" ||
    s === "PARTIAL" ||
    s === "MISSING" ||
    s === "BLOCKED" ||
    s === "NEEDS_REVIEW" ||
    s === "REVIEW_REQUIRED" ||
    s === "STALE" ||
    s === "HISTORICAL_ONLY" ||
    s === "NOT_APPLICABLE"
  ) {
    return s as InputStatus;
  }
  return "MISSING";
}

function normalizeCanGenerate(canGenerate: string | boolean): CanGenerate {
  if (canGenerate === true || canGenerate === "YES") return true;
  if (canGenerate === "DRAFT_ONLY") return "DRAFT_ONLY";
  return false;
}

function normalizeConfidenceLevel(level: string): "LOW" | "MEDIUM" | "HIGH" {
  const l = (level || "").toUpperCase();
  if (l === "LOW" || l === "MEDIUM" || l === "HIGH") return l;
  return "LOW";
}

function normalizeGenerationStatus(status: string): GenerationStatus {
  const s = (status || "BLOCKED").toUpperCase();
  if (
    s === "BLOCKED" ||
    s === "DRAFT_ONLY" ||
    s === "MINIMUM_READY" ||
    s === "CONFIDENT_READY" ||
    s === "HIGH_CONFIDENCE_READY"
  ) {
    return s as GenerationStatus;
  }
  return "BLOCKED";
}

export function buildInputReadinessViewModel(
  raw: RawInputReadinessV2Response | null
): InputReadinessViewModel | null {
  if (!raw) return null;

  const inputsList: InputReadinessItemViewModel[] = (raw.inputs || []).map(
    (inp) => ({
      input_id: inp.input_id,
      label: inp.label,
      status: normalizeStatus(inp.status),
      weight: inp.weight ?? 0,
      earned_score: inp.earned_score ?? 0,
      max_score: inp.max_score ?? 0,
      is_hard_blocker: inp.is_hard_blocker === true,
      summary: inp.summary || "",
      details: inp.details || {},
      actions: inp.actions || [],
    })
  );

  const inputs: Record<string, InputReadinessItemViewModel> = {};
  inputsList.forEach((inp) => {
    inputs[inp.input_id] = inp;
  });

  const readyCount = inputsList.filter((i) => i.status === "READY").length;
  const missingCount = inputsList.filter((i) => NON_READY_STATUSES.has(i.status)).length;

  // Hard blockers: derived from backend blockers, but double-checked against inputs.
  const hardBlockers: InputReadinessBlockerViewModel[] = (raw.blockers || [])
    .map((b) => ({
      input_id: b.input_id,
      code: b.code,
      message: b.message,
    }))
    .filter((b) => {
      const inp = inputs[b.input_id];
      // If the backend says this is a blocker but the input is READY, it is a contradiction.
      // Keep the blocker in the list only if the input is not READY.
      if (inp && inp.status === "READY") {
        if (typeof window !== "undefined") {
          // eslint-disable-next-line no-console
          console.warn(
            `[READINESS_CONTRADICTION] input_id=${b.input_id} status=READY contradictory_blocker=${b.code}`
          );
        }
        return false;
      }
      return true;
    });

  // Missing confidence boosters: warnings from backend, filtered to exclude READY inputs.
  const missingConfidenceBoosters: InputReadinessBlockerViewModel[] = (raw.warnings || [])
    .map((w) => ({
      input_id: w.input_id,
      code: w.code,
      message: w.message,
    }))
    .filter((w) => {
      const inp = inputs[w.input_id];
      if (inp && inp.status === "READY") {
        if (typeof window !== "undefined") {
          // eslint-disable-next-line no-console
          console.warn(
            `[READINESS_CONTRADICTION] input_id=${w.input_id} status=READY contradictory_warning=${w.code}`
          );
        }
        return false;
      }
      return true;
    });

  const nextBestActions: InputReadinessActionViewModel[] = (raw.next_best_actions || [])
    .map((a) => ({
      input_id: a.input_id,
      label: a.label,
      action: a.action || a.input_id,
      reason: a.reason || "",
      priority: a.priority ?? 0,
    }))
    .filter((a) => {
      const inp = inputs[a.input_id];
      // Do not suggest actions for inputs that are already READY.
      if (inp && inp.status === "READY") {
        return false;
      }
      return true;
    });

  return {
    generationStatus: normalizeGenerationStatus(raw.generation_status),
    canGenerate: normalizeCanGenerate(raw.can_generate),
    confidenceScore: raw.confidence_score ?? 0,
    confidenceLevel: normalizeConfidenceLevel(raw.confidence_level),
    confidenceCeiling: normalizeConfidenceLevel(raw.confidence_ceiling),
    primaryMessage: raw.primary_message || "",
    inputs,
    inputsList,
    hardBlockers,
    missingConfidenceBoosters,
    nextBestActions,
    readyCount,
    missingCount,
    // New confidence concepts
    evidenceCompleteness: raw.evidence_completeness ?? 0,
    releaseConfidence: raw.release_confidence ?? "LOW",
    confidenceCeilingReason: raw.confidence_ceiling_reason ?? "Unknown",
  };
}

// Helper to format a readable missing-booster message for the UI if needed.
export function getInputLabel(input_id: string): string {
  const labels: Record<string, string> = {
    INPUT_1: "PR Change Package",
    INPUT_2: "Business Requirements",
    INPUT_3: "Product Behavior Map",
    INPUT_4: "Test Case Inventory",
    INPUT_5: "AC → Test Mapping",
    INPUT_6: "Current PR Test Results",
    INPUT_7: "Test Coverage Mapping",
    INPUT_8: "Release Context",
    INPUT_9: "Environment Support Matrix",
    INPUT_10: "Quality Gate Profile",
    INPUT_11: "Known Defects / Accepted Risks",
    INPUT_12: "Out-of-Scope Declaration",
  };
  return labels[input_id] || input_id;
}
