/**
 * Central Input Action Registry — single source of truth for all 12-input CTAs.
 * Every UI location (input cards, NBA section, PR row, evidence row, banners)
 * must resolve CTAs from here — no local mapping tables.
 */

export type InputId =
  | "INPUT_1"
  | "INPUT_2"
  | "INPUT_3"
  | "INPUT_4"
  | "INPUT_5"
  | "INPUT_6"
  | "INPUT_7"
  | "INPUT_8"
  | "INPUT_9"
  | "INPUT_10"
  | "INPUT_11"
  | "INPUT_12";

export type InputActionType =
  | "OPEN_MODAL"
  | "NAVIGATE"
  | "RUN_MUTATION"
  | "NOT_IMPLEMENTED";

export type InputActionTarget =
  | "PR_CHANGE_PACKAGE_SYNC"
  | "BUSINESS_REQUIREMENTS_MODAL"
  | "PRODUCT_BEHAVIOR_MAP_MUTATION"
  | "TEST_CASE_IMPORT_PAGE"
  | "AC_TEST_MAPPING_PAGE"
  | "TEST_RESULTS_UPLOAD_PAGE"
  | "COVERAGE_UPLOAD_PAGE"
  | "RELEASE_CONTEXT_MODAL"
  | "ENVIRONMENT_MATRIX_MODAL"
  | "QUALITY_GATE_PAGE"
  | "KNOWN_DEFECTS_MODAL"
  | "OUT_OF_SCOPE_MODAL";

export interface InputActionDefinition {
  inputId: InputId;
  /** Button label shown in every CTA location */
  label: string;
  actionType: InputActionType;
  target: InputActionTarget;
  /** One-sentence description shown as tooltip / subtitle */
  description: string;
  /** Lower number = higher priority in NBA list */
  priority: number;
  requiresPullRequest: boolean;
  hardBlockerAction: boolean;
  /** True when the flow is fully implemented and wired */
  implemented: boolean;
}

export const INPUT_ACTIONS: Record<InputId, InputActionDefinition> = {
  INPUT_1: {
    inputId: "INPUT_1",
    label: "Sync PR Changes",
    actionType: "RUN_MUTATION",
    target: "PR_CHANGE_PACKAGE_SYNC",
    description: "Sync changed files and head SHA from the selected PR.",
    priority: 1,
    requiresPullRequest: true,
    hardBlockerAction: true,
    implemented: true,
  },
  INPUT_2: {
    inputId: "INPUT_2",
    label: "Add Requirements",
    actionType: "OPEN_MODAL",
    target: "BUSINESS_REQUIREMENTS_MODAL",
    description: "Add requirement groups and acceptance criteria for this PR.",
    priority: 2,
    requiresPullRequest: true,
    hardBlockerAction: true,
    implemented: true,
  },
  INPUT_3: {
    inputId: "INPUT_3",
    label: "Run Repository Intelligence",
    actionType: "RUN_MUTATION",
    target: "PRODUCT_BEHAVIOR_MAP_MUTATION",
    description: "Analyze repository structure and map product behaviors.",
    priority: 8,
    requiresPullRequest: false,
    hardBlockerAction: false,
    implemented: true,
  },
  INPUT_4: {
    inputId: "INPUT_4",
    label: "Import Test Cases",
    actionType: "NAVIGATE",
    target: "TEST_CASE_IMPORT_PAGE",
    description: "Upload a JUnit XML or connect a test suite.",
    priority: 3,
    requiresPullRequest: false,
    hardBlockerAction: true,
    implemented: true,
  },
  INPUT_5: {
    inputId: "INPUT_5",
    label: "Map ACs to Tests",
    actionType: "NAVIGATE",
    target: "AC_TEST_MAPPING_PAGE",
    description: "Map acceptance criteria to test cases for this PR.",
    priority: 4,
    requiresPullRequest: true,
    hardBlockerAction: true,
    implemented: true,
  },
  INPUT_6: {
    inputId: "INPUT_6",
    label: "Upload Test Results",
    actionType: "NAVIGATE",
    target: "TEST_RESULTS_UPLOAD_PAGE",
    description: "Attach current PR test execution results.",
    priority: 5,
    requiresPullRequest: true,
    hardBlockerAction: true,
    implemented: true,
  },
  INPUT_7: {
    inputId: "INPUT_7",
    label: "Upload Coverage Report",
    actionType: "NAVIGATE",
    target: "COVERAGE_UPLOAD_PAGE",
    description: "Attach coverage evidence for tests and changed files.",
    priority: 9,
    requiresPullRequest: false,
    hardBlockerAction: false,
    implemented: true,
  },
  INPUT_8: {
    inputId: "INPUT_8",
    label: "Define Release Context",
    actionType: "OPEN_MODAL",
    target: "RELEASE_CONTEXT_MODAL",
    description: "Define release type, scope, and risk tolerance.",
    priority: 10,
    requiresPullRequest: true,
    hardBlockerAction: false,
    implemented: false,
  },
  INPUT_9: {
    inputId: "INPUT_9",
    label: "Define Environment Matrix",
    actionType: "OPEN_MODAL",
    target: "ENVIRONMENT_MATRIX_MODAL",
    description: "Define supported environments, browsers, and platforms.",
    priority: 11,
    requiresPullRequest: true,
    hardBlockerAction: false,
    implemented: false,
  },
  INPUT_10: {
    inputId: "INPUT_10",
    label: "Configure Quality Gates",
    actionType: "NAVIGATE",
    target: "QUALITY_GATE_PAGE",
    description: "Configure pass thresholds and blocking quality policies.",
    priority: 12,
    requiresPullRequest: false,
    hardBlockerAction: false,
    implemented: true,
  },
  INPUT_11: {
    inputId: "INPUT_11",
    label: "Add Known Risks",
    actionType: "OPEN_MODAL",
    target: "KNOWN_DEFECTS_MODAL",
    description: "Capture known defects and accepted risks for this release.",
    priority: 13,
    requiresPullRequest: true,
    hardBlockerAction: false,
    implemented: false,
  },
  INPUT_12: {
    inputId: "INPUT_12",
    label: "Declare Out-of-Scope",
    actionType: "OPEN_MODAL",
    target: "OUT_OF_SCOPE_MODAL",
    description: "Declare areas intentionally excluded from this release.",
    priority: 14,
    requiresPullRequest: true,
    hardBlockerAction: false,
    implemented: false,
  },
};

/** Resolve the canonical action for a given input ID. */
export function getInputAction(inputId: string): InputActionDefinition | null {
  return INPUT_ACTIONS[inputId as InputId] ?? null;
}

/**
 * Map a raw backend action string (e.g. "OPEN_BUSINESS_REQUIREMENTS_MODAL")
 * back to an InputId so the dispatcher can look it up in the registry.
 */
export const BACKEND_ACTION_TO_INPUT_ID: Record<string, InputId> = {
  // Input 1
  SYNC_PR_CHANGES: "INPUT_1",
  // Input 2
  OPEN_BUSINESS_REQUIREMENTS_MODAL: "INPUT_2",
  ADD_REQUIREMENTS: "INPUT_2",
  // Input 3
  RUN_REPOSITORY_INTELLIGENCE: "INPUT_3",
  PRODUCT_BEHAVIOR_MAP_FLOW: "INPUT_3",
  // Input 4
  IMPORT_TEST_CASES: "INPUT_4",
  UPLOAD_JUNIT_XML: "INPUT_4",
  // Input 5
  MAP_ACS_TO_TESTS: "INPUT_5",
  AC_TEST_MAPPING_PAGE: "INPUT_5",
  // Input 6
  UPLOAD_TEST_RESULTS: "INPUT_6",
  ATTACH_TEST_RUN: "INPUT_6",
  // Input 7
  UPLOAD_COVERAGE_REPORT: "INPUT_7",
  ATTACH_COVERAGE: "INPUT_7",
  UPLOAD_COVERAGE: "INPUT_7",
  // Input 8
  LINK_WORK_ITEM: "INPUT_8",
  RELEASE_CONTEXT_MODAL: "INPUT_8",
  // Input 9
  DEFINE_ENVIRONMENT_MATRIX: "INPUT_9",
  ENVIRONMENT_MATRIX_MODAL: "INPUT_9",
  // Input 10
  CONFIGURE_QUALITY_GATES: "INPUT_10",
  QUALITY_GATE_MODAL: "INPUT_10",
  // Input 11
  ADD_KNOWN_RISKS: "INPUT_11",
  KNOWN_DEFECTS_MODAL: "INPUT_11",
  // Input 12
  DECLARE_OUT_OF_SCOPE: "INPUT_12",
  OUT_OF_SCOPE_MODAL: "INPUT_12",
};

/**
 * Resolve a backend action string to its canonical InputActionDefinition.
 * Returns null if the action string is unrecognised.
 */
export function resolveBackendAction(backendAction: string): InputActionDefinition | null {
  const inputId = BACKEND_ACTION_TO_INPUT_ID[backendAction];
  if (!inputId) return null;
  return INPUT_ACTIONS[inputId];
}
