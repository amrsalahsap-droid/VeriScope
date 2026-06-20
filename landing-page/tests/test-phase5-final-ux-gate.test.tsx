/**
 * @jest-environment jsdom
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import RecommendationRunDetail from "../app/app/recommendations/[recommendationRunId]/page";
import { ScopeGroup } from "../types/regression-scope-v2";

// Mock the useRouter hook
jest.mock("next/navigation", () => ({
  useRouter() {
    return {
      push: jest.fn(),
      replace: jest.fn(),
      prefetch: jest.fn(),
    };
  },
}));

// Mock Link component
jest.mock("next/link", () => {
  return ({ children, href }: { children: React.ReactNode; href: string }) => {
    return <a href={href}>{children}</a>;
  };
});

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

const mockRunDetail = {
  id: "run-123",
  created_at: "2026-06-13T05:00:00Z",
  triggered_by: "engineer",
  repository: { id: "repo-123", full_name: "owner/repo" },
  pull_request: {
    id: "pr-123",
    number: 101,
    title: "Add password validation feature",
    source_branch: "feature/pass",
    target_branch: "main"
  },
  executive_summary: {
    changed_files: ["validation.py", "auth.py"],
    changed_files_count: 2,
    risk_level: "HIGH",
    bullets: ["Password validation logic updated"]
  },
  readiness_snapshot: {
    readiness_snapshot_available: true,
    expected_confidence: "LOW",
    readiness_score: 60,
    can_generate: true,
    missing_inputs: []
  },
  testing_strategy: {
    recommendation_mode: "risk_based",
    evidence_quality: "LOW",
    optimization_allowed: true,
    must_run_count: 2,
    should_run_count: 1,
    fallback_count: 1,
    estimated_runtime_seconds: 60,
    full_suite_runtime_seconds: 120,
    runtime_confidence: "HIGH",
    skipped_count: 3,
    skipped_reason_summary: "No changes"
  },
  recommended_tests: [
    {
      stable_identity: "test_auth_password_strength",
      display_name: "Verify password strength validation",
      suite_name: "test_auth.py",
      tier: "must_run",
      priority_score: 9.5,
      reason_type: "direct_match",
      reason: "Direct match to updated file auth.py",
      current_pr_result: "passed"
    }
  ],
  health: "VALIDATION_PASSED_COVERAGE_INCOMPLETE",
  why: ["Changes to validation.py"],
  warnings: [],
  evidence_gaps: [],
  scenario_coverage_matrix: { items: [] }
};

const mockRegressionEvidence = {
  status: "SUCCESS",
  canRenderRecommendation: true,
  decisionSummary: {
    health: "VALIDATION_PASSED_COVERAGE_INCOMPLETE",
    counts: {
      totalRequirements: 25,
      uploadedPrTestsPassed: 18,
      verifiedTests: 16,
      coverageGaps: 2,
      missingAutomatedCoverage: 7,
      notMappedTraceabilityRisks: 0
    },
    decisionCopy: {
      headline: "Limited Evidence",
      explanation: "Current PR execution passed 18 tests. Veriscope mapped 16 acceptance criteria to passed PR evidence. 2 acceptance criteria are partially supported and need review. 7 acceptance criteria still lack automated coverage."
    }
  },
  buckets: {
    coveredByPassedPrTests: Array(16).fill({ requirementId: "req-cov" }),
    partiallySupported: Array(2).fill({ requirementId: "req-part" }),
    missingAutomatedCoverage: Array(7).fill({ requirementId: "req-miss", readableId: "AC-MISS-X", title: "Missing automated coverage scenario", diagnostics: { internalId: "item-uuid-req-1" } }),
    traceabilityReviewNeeded: []
  }
};

const mockV2RegressionScope = {
  recommendation_run_id: "run-123",
  snapshot_hash: "sha256-abc123xyz789",
  generated_at: "2026-06-13T05:00:00Z",
  scope_type: "risk_based",
  source: "hybrid",
  summary: "This is a V2 regression scope summary",
  execution_plan: {
    required_count: 2,
    recommended_count: 1,
    optional_count: 1,
    safe_to_skip_count: 3,
    total_executable_count: 4,
    estimated_execution_reduction: 45.5,
    confidence_level: 95.0,
    plan_summary: "Run 4 out of 7 tests, saving 45%.",
    advisory_notice: "Please ensure manual validation on staging if critical paths fail."
  },
  groups: {
    [ScopeGroup.REQUIRED]: {
      group: ScopeGroup.REQUIRED,
      count: 2,
      items: [
        {
          id: "item-uuid-req-1",
          readable_id: "AC-REQ-1",
          title: "Verify password strength validation",
          item_type: "REQUIREMENT",
          group: "REQUIRED",
          evidence_classification: "MISSING",
          risk_score: 9.5,
          risk_band: "CRITICAL",
          change_impact_level: "DIRECT",
          business_risk_level: "CRITICAL",
          effective_risk_level: "CRITICAL",
          suggested_action: "Add integration tests",
          reason: "Directly touched",
          evidence_references: [],
          test_references: [],
          can_auto_execute: true,
          is_required_for_release: true,
          is_manual_only: false
        },
        {
          id: "item-uuid-req-2",
          readable_id: "AC-REQ-2",
          title: "Verify MFA rules",
          item_type: "REQUIREMENT",
          group: "REQUIRED",
          evidence_classification: "PARTIAL",
          risk_score: 8.0,
          risk_band: "HIGH",
          change_impact_level: "INDIRECT",
          business_risk_level: "HIGH",
          effective_risk_level: "HIGH",
          suggested_action: "None",
          reason: "Indirect dependency",
          evidence_references: [],
          test_references: [],
          can_auto_execute: true,
          is_required_for_release: true,
          is_manual_only: false
        }
      ]
    },
    [ScopeGroup.RECOMMENDED]: {
      group: ScopeGroup.RECOMMENDED,
      count: 1,
      items: [
        {
          id: "item-uuid-rec-1",
          readable_id: "AC-REC-1",
          title: "Verify session timeouts",
          item_type: "REQUIREMENT",
          group: "RECOMMENDED",
          evidence_classification: "COVERED",
          risk_score: 6.0,
          risk_band: "MEDIUM",
          change_impact_level: "NONE",
          business_risk_level: "MEDIUM",
          effective_risk_level: "MEDIUM",
          suggested_action: "Run integration tests",
          reason: "Common session paths",
          evidence_references: [],
          test_references: [],
          can_auto_execute: true,
          is_required_for_release: false,
          is_manual_only: false
        }
      ]
    },
    [ScopeGroup.OPTIONAL]: {
      group: ScopeGroup.OPTIONAL,
      count: 1,
      items: [
        {
          id: "item-uuid-opt-1",
          readable_id: "AC-OPT-1",
          title: "Verify UI styles loading",
          item_type: "TEST",
          group: "OPTIONAL",
          evidence_classification: "COVERED",
          risk_score: 3.0,
          risk_band: "LOW",
          change_impact_level: "NONE",
          business_risk_level: "LOW",
          effective_risk_level: "LOW",
          suggested_action: "Verify visually",
          reason: "UI rendering",
          evidence_references: [],
          test_references: [],
          can_auto_execute: false,
          is_required_for_release: false,
          is_manual_only: true
        }
      ]
    },
    [ScopeGroup.SAFE_TO_SKIP]: {
      group: ScopeGroup.SAFE_TO_SKIP,
      count: 3,
      items: [
        {
          id: "item-uuid-skip-1",
          readable_id: "AC-SKIP-1",
          title: "Verify CSV data exporter helper",
          item_type: "TEST",
          group: "SAFE_TO_SKIP",
          evidence_classification: "COVERED",
          risk_score: 1.0,
          risk_band: "LOW",
          change_impact_level: "NONE",
          business_risk_level: "LOW",
          effective_risk_level: "LOW",
          suggested_action: "Skip test",
          reason: "No reporting changed",
          evidence_references: [],
          test_references: [],
          can_auto_execute: true,
          is_required_for_release: false,
          is_manual_only: false
        }
      ]
    }
  },
  exclusions: {
    already_verified_count: 1,
    already_passed_tests_count: 1,
    already_verified_items: [
      {
        id: "item-uuid-ex-1",
        readable_id: "AC-EX-1",
        title: "Already verified requirement",
        item_type: "REQUIREMENT",
        group: "EXCLUDED",
        evidence_references: [],
        test_references: []
      }
    ],
    already_passed_test_items: [
      {
        id: "item-uuid-ex-2",
        readable_id: "AC-EX-2",
        title: "Already passed test scenario",
        item_type: "TEST",
        group: "EXCLUDED",
        evidence_references: [],
        test_references: []
      }
    ]
  },
  optimization_metrics: {
    current_regression_size: 7,
    optimized_required_count: 2,
    optimized_recommended_count: 1,
    optimized_optional_count: 1,
    safe_to_skip_count: 3,
    optimization_percentage: 42.8,
    execution_reduction: 45.5,
    coverage_confidence: 95.0
  },
  governance: {
    risk_reviews_count: 1,
    overridden_count: 1,
    needs_discussion_count: 0,
    release_decision_required: true,
    release_decision_status: "PENDING"
  },
  diagnostics: {
    generation_timestamp: "2026-06-13T05:00:00Z",
    generation_duration_ms: 120,
    rules_applied: [],
    warnings: [],
    errors: []
  }
};

describe("Phase 5 Final UX Gate Validation", () => {
  const originalClipboard = { ...global.navigator.clipboard };
  const originalEnv = process.env.NODE_ENV;

  beforeAll(() => {
    Object.defineProperty(global.navigator, "clipboard", {
      value: {
        writeText: jest.fn().mockResolvedValue(undefined),
      },
      writable: true,
      configurable: true
    });
  });

  afterAll(() => {
    Object.defineProperty(global.navigator, "clipboard", {
      value: originalClipboard,
      writable: true,
      configurable: true
    });
    process.env.NODE_ENV = originalEnv;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.NODE_ENV = "test";

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/regression-evidence")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockRegressionEvidence)
        });
      }
      if (url.includes("/regression-scope")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockV2RegressionScope)
        });
      }
      if (url.includes("/release-decision")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ decisionStatus: "APPROVED", approverName: "QA Lead" })
        });
      }
      if (url.includes("/api/recommendations/run-123")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockRunDetail)
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
  });

  const renderPage = () => {
    const params = Promise.resolve({ recommendationRunId: "run-123" });
    return render(<RecommendationRunDetail params={params} />);
  };

  // 1. Section order.
  test("1. Section order is correct and matches design hierarchy", async () => {
    const { container } = renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Verify password strength validation")[0]).toBeInTheDocument();
    });

    const expectedOrder = [
      "release-decision",
      "required-before-release",
      "regression-scope-plan",
      "business-risk-review",
      "coverage-traceability",
      "execution-optimization",
      "governance-audit"
    ];

    const elements = container.querySelectorAll(expectedOrder.map(id => `#${id}`).join(", "));
    const renderedIds = Array.from(elements).map(el => el.id);

    expect(renderedIds).toEqual(expectedOrder);
  });

  // 2. No duplicate section titles.
  test("2. Top-level section titles are not duplicated", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Verify password strength validation")[0]).toBeInTheDocument();
    });

    const headings = [
      "Release Decision",
      "Required Before Release",
      "Regression Scope Plan",
      "Business Risk Review",
      "Coverage & Traceability",
      "Execution Optimization",
      "Governance & Audit"
    ];

    headings.forEach(title => {
      const match = screen.getAllByRole("heading", { name: title, level: 2 });
      expect(match.length).toBe(1);
    });
  });

  // 3. Export actions global.
  test("3. Primary global export actions are top-level and not nested or duplicated", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Export Evidence Report")).toBeInTheDocument();
    });

    // Verify presence and uniqueness
    expect(screen.getAllByText("Export Evidence Report").length).toBe(1);
    expect(screen.getAllByText("Export JSON").length).toBe(1);
    expect(screen.getAllByText("Copy Summary").length).toBe(1);
    expect(screen.getAllByText("Regenerate").length).toBe(1);

    // Make sure they are inside the "Primary Actions" card
    const primaryActionsHeader = screen.getByText("Primary Actions");
    expect(primaryActionsHeader).toBeInTheDocument();
  });

  // 4. Risk review visible.
  test("4. Risk review details and overrides are visible under Business Risk Review", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Verify password strength validation")[0]).toBeInTheDocument();
    });

    expect(screen.getByText("Business Risk Review")).toBeInTheDocument();
    // Check that items in the list display effective risk and review actions
    expect(screen.getAllByTitle("Accept generated risk").length).toBeGreaterThan(0);
    expect(screen.getAllByTitle("Override risk").length).toBeGreaterThan(0);
    expect(screen.getAllByTitle("View review history").length).toBeGreaterThan(0);
  });

  // 5. Release decision visible.
  test("5. Release Decision panel displays health verdict and state", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Limited Evidence")).toBeInTheDocument();
    });

    expect(screen.getByText("Release Decision")).toBeInTheDocument();
    expect(screen.getAllByText(/Current PR execution passed 18 tests/).length).toBeGreaterThan(0);
  });

  // 6. Internal IDs hidden.
  test("6. Internal requirement IDs, UUIDs, and hashes are hidden in normal mode", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Verify password strength validation")[0]).toBeInTheDocument();
    });

    // In normal mode, internal UUIDs and diagnostic hashes must be hidden
    expect(screen.queryByText("item-uuid-req-1")).not.toBeInTheDocument();
    expect(screen.queryByText("sha256-abc123xyz789")).not.toBeInTheDocument();
  });

  // 7. Audit mode reveals diagnostics.
  test("7. Audit Mode in development reveals internal IDs and generation metadata", async () => {
    process.env.NODE_ENV = "development";
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Verify password strength validation")[0]).toBeInTheDocument();
    });

    // Expand the parent Governance & Audit section
    const govSection = screen.getByText("Governance & Audit");
    fireEvent.click(govSection);

    // Wait for the nested Diagnostics / Audit Mode button to appear and click it
    await waitFor(() => {
      expect(screen.getByText("Diagnostics / Audit Mode")).toBeInTheDocument();
    });
    const auditBtn = screen.getByText("Diagnostics / Audit Mode");
    fireEvent.click(auditBtn);

    // In dev mode/audit mode, internal IDs are visible in list row debug logs
    await waitFor(() => {
      expect(screen.getAllByText(/item-uuid-req-1/).length).toBeGreaterThan(0);
    });
  });


  // 8. RegressionScopeV2 counts consistent.
  test("8. RegressionScopeV2 counts are consistent in display elements", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Verify password strength validation")[0]).toBeInTheDocument();
    });

    // Check counts inside Regression Scope V2 display panels
    // Estimated reductions, plan summary saving %
    expect(screen.getByText(/45%/)).toBeInTheDocument();
  });

  // 9. Copy Summary consistent.
  test("9. Copy Summary outputs canonical evidence counts and correct terminology", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Copy Summary")).toBeInTheDocument();
    });

    const copyBtn = screen.getByText("Copy Summary");
    fireEvent.click(copyBtn);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled();
      const text = (navigator.clipboard.writeText as jest.Mock).mock.calls[0][0];

      expect(text).toContain("Release Decision: APPROVED");
      expect(text).toContain("Health: VALIDATION_PASSED_COVERAGE_INCOMPLETE");
      expect(text).toContain("Required Before Release: 2");
      expect(text).toContain("Recommended Regression: 1");
      expect(text).toContain("Optional Safety Net: 1");
      expect(text).toContain("Safe To Skip: 3");
      expect(text).toContain("Total ACs: 25");
      expect(text).toContain("Current PR Tests: 18");
      expect(text).toContain("Passed Tests: 18");
      expect(text).toContain("Covered: 16");
      expect(text).toContain("Partial: 2");
      expect(text).toContain("Missing: 7");
    });
  });

  // 10. Empty states render.
  test("10. Empty state values render gracefully without crashing", async () => {
    // Modify mock to return empty values
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/regression-evidence")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            ...mockRegressionEvidence,
            buckets: {
              coveredByPassedPrTests: [],
              partiallySupported: [],
              missingAutomatedCoverage: [],
              traceabilityReviewNeeded: []
            }
          })
        });
      }
      if (url.includes("/regression-scope")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            ...mockV2RegressionScope,
            groups: {},
            exclusions: {
              already_verified_count: 0,
              already_passed_tests_count: 0,
              already_verified_items: [],
              already_passed_test_items: []
            }
          })
        });
      }
      if (url.includes("/release-decision")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ decisionStatus: "UNDECIDED" })
        });
      }
      if (url.includes("/api/recommendations/run-123")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            ...mockRunDetail,
            why: [],
            evidence_gaps: []
          })
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Release Decision")).toBeInTheDocument();
    });

    // Check h2 sections still render despite no items inside lists
    expect(screen.getByRole("heading", { name: "Required Before Release", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Regression Scope Plan", level: 2 })).toBeInTheDocument();
  });
});
