import {
  buildInputReadinessViewModel,
  type RawInputReadinessV2Response,
} from "../lib/readiness/inputReadinessAdapter";

function makeResponse(overrides: Partial<RawInputReadinessV2Response> = {}): RawInputReadinessV2Response {
  const inputs = [
    { input_id: "INPUT_1", label: "PR Change Package", status: "READY", weight: 10, earned_score: 10, max_score: 10, is_hard_blocker: true, summary: "Ready", details: {}, actions: [] },
    { input_id: "INPUT_2", label: "Business Requirements", status: "READY", weight: 20, earned_score: 20, max_score: 20, is_hard_blocker: true, summary: "Ready", details: {}, actions: [] },
    { input_id: "INPUT_3", label: "Product Behavior Map", status: "READY", weight: 10, earned_score: 10, max_score: 10, is_hard_blocker: false, summary: "Ready", details: {}, actions: [] },
    { input_id: "INPUT_4", label: "Test Case Inventory", status: "READY", weight: 12, earned_score: 12, max_score: 12, is_hard_blocker: true, summary: "Ready", details: {}, actions: [] },
    { input_id: "INPUT_5", label: "AC → Test Mapping", status: "MISSING", weight: 15, earned_score: 0, max_score: 15, is_hard_blocker: true, summary: "Missing", details: {}, actions: [] },
    { input_id: "INPUT_6", label: "Current PR Test Results", status: "READY", weight: 15, earned_score: 15, max_score: 15, is_hard_blocker: true, summary: "Ready", details: {}, actions: [] },
    { input_id: "INPUT_7", label: "Test Coverage Mapping", status: "READY", weight: 8, earned_score: 8, max_score: 8, is_hard_blocker: false, summary: "Ready", details: {}, actions: [] },
    { input_id: "INPUT_8", label: "Release Context", status: "MISSING", weight: 3, earned_score: 0, max_score: 3, is_hard_blocker: false, summary: "Missing", details: {}, actions: [] },
    { input_id: "INPUT_9", label: "Environment Support Matrix", status: "MISSING", weight: 3, earned_score: 0, max_score: 3, is_hard_blocker: false, summary: "Missing", details: {}, actions: [] },
    { input_id: "INPUT_10", label: "Quality Gate Profile", status: "MISSING", weight: 2, earned_score: 0, max_score: 2, is_hard_blocker: false, summary: "Missing", details: {}, actions: [] },
    { input_id: "INPUT_11", label: "Known Defects / Accepted Risks", status: "MISSING", weight: 1, earned_score: 0, max_score: 1, is_hard_blocker: false, summary: "Missing", details: {}, actions: [] },
    { input_id: "INPUT_12", label: "Out-of-Scope Declaration", status: "MISSING", weight: 1, earned_score: 0, max_score: 1, is_hard_blocker: false, summary: "Missing", details: {}, actions: [] },
  ];

  return {
    generation_status: "DRAFT_ONLY",
    can_generate: "DRAFT_ONLY",
    confident_generation: false,
    confidence_score: 75,
    confidence_level: "HIGH",
    confidence_ceiling: "LOW",
    primary_message: "Test evidence is incomplete. Only a draft plan can be generated.",
    blockers: [{ input_id: "INPUT_5", code: "AC_TEST_MAPPING_MISSING", message: "Map acceptance criteria to test cases to enable confident generation." }],
    warnings: [
      { input_id: "INPUT_8", code: "RELEASE_CONTEXT_MISSING", message: "Release context is missing. Risk tolerance cannot be assessed." },
      { input_id: "INPUT_9", code: "ENVIRONMENT_MATRIX_MISSING", message: "Environment support matrix is missing. Cross-environment gaps cannot be detected." },
      { input_id: "INPUT_10", code: "QUALITY_GATE_MISSING", message: "Quality gate profile is missing. Pass/fail thresholds cannot be enforced." },
      { input_id: "INPUT_11", code: "KNOWN_DEFECTS_MISSING", message: "Known defects and accepted risks are not captured." },
      { input_id: "INPUT_12", code: "OUT_OF_SCOPE_MISSING", message: "Out-of-scope declaration is missing. Scope boundaries are undefined." },
    ],
    inputs,
    next_best_actions: [
      { priority: 1, input_id: "INPUT_5", label: "Map ACs to Tests", reason: "Required for confident generation" },
      { priority: 2, input_id: "INPUT_8", label: "Add Release Context", reason: "Improves risk assessment" },
      { priority: 3, input_id: "INPUT_9", label: "Define Environment Matrix", reason: "Improves cross-environment coverage" },
      { priority: 4, input_id: "INPUT_10", label: "Configure Quality Gates", reason: "Improves pass/fail enforcement" },
      { priority: 5, input_id: "INPUT_11", label: "Capture Known Defects", reason: "Improves risk awareness" },
      { priority: 6, input_id: "INPUT_12", label: "Declare Out-of-Scope", reason: "Clarifies scope boundaries" },
    ],
    ...overrides,
  };
}

describe("buildInputReadinessViewModel", () => {
  let warnSpy: jest.SpyInstance;

  beforeEach(() => {
    warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    warnSpy.mockRestore();
  });

  it("returns null for null data", () => {
    expect(buildInputReadinessViewModel(null)).toBeNull();
  });

  it("normalizes all 12 inputs", () => {
    const vm = buildInputReadinessViewModel(makeResponse())!;
    expect(vm.inputsList).toHaveLength(12);
    expect(Object.keys(vm.inputs)).toHaveLength(12);
  });

  it("counts ready and missing inputs correctly", () => {
    const vm = buildInputReadinessViewModel(makeResponse())!;
    expect(vm.readyCount).toBe(6);
    expect(vm.missingCount).toBe(6);
  });

  it("exposes hard blockers from the backend", () => {
    const vm = buildInputReadinessViewModel(makeResponse())!;
    expect(vm.hardBlockers).toHaveLength(1);
    expect(vm.hardBlockers[0].input_id).toBe("INPUT_5");
  });

  it("exposes missing confidence boosters", () => {
    const vm = buildInputReadinessViewModel(makeResponse())!;
    const ids = vm.missingConfidenceBoosters.map((w) => w.input_id);
    expect(ids).toEqual(["INPUT_8", "INPUT_9", "INPUT_10", "INPUT_11", "INPUT_12"]);
  });

  it("filters contradictory warnings for READY inputs", () => {
    const response = makeResponse({
      warnings: [
        { input_id: "INPUT_7", code: "TEST_COVERAGE_MAPPING_MISSING", message: "Test coverage mapping is missing." },
        { input_id: "INPUT_8", code: "RELEASE_CONTEXT_MISSING", message: "Release context is missing." },
      ],
    });
    const vm = buildInputReadinessViewModel(response)!;
    const ids = vm.missingConfidenceBoosters.map((w) => w.input_id);
    expect(ids).not.toContain("INPUT_7");
    expect(ids).toContain("INPUT_8");
  });

  it("filters contradictory hard blockers for READY inputs", () => {
    const response = makeResponse({
      blockers: [
        { input_id: "INPUT_7", code: "TEST_COVERAGE_MAPPING_MISSING", message: "Test coverage mapping is missing." },
        { input_id: "INPUT_5", code: "AC_TEST_MAPPING_MISSING", message: "Map acceptance criteria to test cases." },
      ],
    });
    const vm = buildInputReadinessViewModel(response)!;
    const ids = vm.hardBlockers.map((b) => b.input_id);
    expect(ids).not.toContain("INPUT_7");
    expect(ids).toContain("INPUT_5");
  });

  it("excludes READY inputs from next best actions", () => {
    const response = makeResponse({
      next_best_actions: [
        { priority: 1, input_id: "INPUT_7", label: "Upload Coverage", reason: "Already ready" },
        { priority: 2, input_id: "INPUT_5", label: "Map ACs to Tests", reason: "Required" },
      ],
    });
    const vm = buildInputReadinessViewModel(response)!;
    const ids = vm.nextBestActions.map((a) => a.input_id);
    expect(ids).not.toContain("INPUT_7");
    expect(ids).toContain("INPUT_5");
  });

  it("normalizes generation status and can_generate", () => {
    const vm = buildInputReadinessViewModel(makeResponse())!;
    expect(vm.generationStatus).toBe("DRAFT_ONLY");
    expect(vm.canGenerate).toBe("DRAFT_ONLY");
    expect(vm.confidenceScore).toBe(75);
    expect(vm.confidenceLevel).toBe("HIGH");
  });
});
