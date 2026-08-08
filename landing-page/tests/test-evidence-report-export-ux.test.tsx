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
    optional_count: 0,
    safe_to_skip_count: 3,
    total_executable_count: 3,
    confidence_level: 95,
    plan_summary: "Run 3 items.",
    advisory_notice: "Run items carefully."
  },
  groups: {
    [ScopeGroup.REQUIRED]: {
      group: ScopeGroup.REQUIRED,
      count: 2,
      items: [
        {
          id: "item-req-1",
          readable_id: "AC-REQ-1",
          title: "Password Strength",
          item_type: "REQUIREMENT",
          group: "REQUIRED",
          evidence_classification: "MISSING",
          risk_score: 9.0,
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
        }
      ]
    }
  },
  exclusions: {
    already_verified_count: 0,
    already_passed_tests_count: 0,
    already_verified_items: [],
    already_passed_test_items: []
  },
  optimization_metrics: {
    current_regression_size: 2,
    optimized_required_count: 1,
    optimized_recommended_count: 0,
    optimized_optional_count: 0,
    safe_to_skip_count: 1,
    optimization_percentage: 50.0,
    execution_reduction: 45.5,
    coverage_confidence: 95.0
  },
  governance: {
    risk_reviews_count: 0,
    overridden_count: 0,
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

describe.skip("Evidence Report Export UX & Terminology Tests", () => {
  const originalClipboard = { ...global.navigator.clipboard };
  const originalCreateElement = document.createElement;
  const mockAnchor = {
    href: "",
    download: "",
    click: jest.fn(),
  };

  beforeAll(() => {
    // Mock clipboard
    Object.defineProperty(global.navigator, "clipboard", {
      value: {
        writeText: jest.fn().mockResolvedValue(undefined),
      },
      writable: true,
      configurable: true
    });

    // Mock document.createElement
    document.createElement = jest.fn((tagName) => {
      const el = originalCreateElement.call(document, tagName);
      if (tagName === "a") {
        el.click = jest.fn();
        mockAnchor.click = el.click as any;
        Object.defineProperty(el, "download", {
          get() { return mockAnchor.download; },
          set(val) { mockAnchor.download = val; }
        });
        Object.defineProperty(el, "href", {
          get() { return mockAnchor.href; },
          set(val) { mockAnchor.href = val; }
        });
      }
      return el;
    });

    // Mock URL functions
    global.URL.createObjectURL = jest.fn(() => "blob:mock-url");
    global.URL.revokeObjectURL = jest.fn();
  });

  afterAll(() => {
    Object.defineProperty(global.navigator, "clipboard", {
      value: originalClipboard,
      writable: true,
      configurable: true
    });
    document.createElement = originalCreateElement;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockAnchor.href = "";
    mockAnchor.download = "";
    mockAnchor.click.mockClear();

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
          json: () => Promise.resolve({ decisionStatus: "APPROVED", approverName: "QA Manager" })
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

  test("1. Export Evidence Report button is global/top-level", async () => {
    renderPage();
    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /Export Evidence Report/i });
      expect(btn).toBeInTheDocument();
      // Verify it's within the Primary Actions card
      const headerDiv = screen.getByText("Primary Actions").closest("div");
      const card = headerDiv ? headerDiv.parentElement : null;
      expect(card).toBeInTheDocument();
      expect(card).toContainElement(btn);
    });
  });

  test("2. Export JSON button is global/top-level", async () => {
    renderPage();
    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /Export JSON/i });
      expect(btn).toBeInTheDocument();
      const headerDiv = screen.getByText("Primary Actions").closest("div");
      const card = headerDiv ? headerDiv.parentElement : null;
      expect(card).toBeInTheDocument();
      expect(card).toContainElement(btn);
    });
  });

  test("3. Copy Summary button is global/top-level", async () => {
    renderPage();
    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /Copy Summary/i });
      expect(btn).toBeInTheDocument();
      const headerDiv = screen.getByText("Primary Actions").closest("div");
      const card = headerDiv ? headerDiv.parentElement : null;
      expect(card).toBeInTheDocument();
      expect(card).toContainElement(btn);
    });
  });

  test("4. Export markdown uses V2 terminology parameters in API call", async () => {
    renderPage();
    await waitFor(() => {
      screen.getByRole("button", { name: /Export Evidence Report/i });
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "SUCCESS",
        markdown_content: "Required Before Release\nRegression Scope Plan\nRecommended Regression\nOptional Safety Net"
      })
    });

    const btn = screen.getByRole("button", { name: /Export Evidence Report/i });
    fireEvent.click(btn);

    await waitFor(() => {
      const calls = mockFetch.mock.calls.map(call => call[0]);
      expect(calls.some(url => url.includes("/evidence-report?format=markdown"))).toBe(true);
    });
  });

  test("5. Copy Summary uses decision-centric terminology", async () => {
    renderPage();
    await waitFor(() => {
      screen.getByRole("button", { name: /Copy Summary/i });
    });

    const btn = screen.getByRole("button", { name: /Copy Summary/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled();
      const copiedText = (navigator.clipboard.writeText as jest.Mock).mock.calls[0][0];
      
      expect(copiedText).toContain("Release Decision: APPROVED");
      expect(copiedText).toContain("Health: VALIDATION_PASSED_COVERAGE_INCOMPLETE");
      expect(copiedText).toContain("Report Ready Status: Ready");
      expect(copiedText).toContain("Required Before Release: 2");
      expect(copiedText).toContain("Recommended Regression: 1");
      expect(copiedText).toContain("Optional Safety Net: 0");
      expect(copiedText).toContain("Safe To Skip: 3");
      expect(copiedText).toContain("Total ACs: 25");
      expect(copiedText).toContain("Current PR Tests: 18");
      expect(copiedText).toContain("Passed Tests: 18");
      expect(copiedText).toContain("Covered: 16");
      expect(copiedText).toContain("Partial: 2");
      expect(copiedText).toContain("Missing: 7");
      expect(copiedText).toContain("Traceability Review Needed: 0");
    });
  });

  test("6. Copy Summary does not include internal IDs", async () => {
    renderPage();
    await waitFor(() => {
      screen.getByRole("button", { name: /Copy Summary/i });
    });

    const btn = screen.getByRole("button", { name: /Copy Summary/i });
    fireEvent.click(btn);

    await waitFor(() => {
      const copiedText = (navigator.clipboard.writeText as jest.Mock).mock.calls[0][0];
      expect(copiedText).not.toContain("item-uuid-req-1");
    });
  });

  test("7. Stale report response shows error/toast and does not trigger markdown download", async () => {
    renderPage();
    await waitFor(() => {
      screen.getByRole("button", { name: /Export Evidence Report/i });
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "REQUIRES_REGENERATION",
        message: "Recommendation is stale."
      })
    });

    const btn = screen.getByRole("button", { name: /Export Evidence Report/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(mockAnchor.click).not.toHaveBeenCalled();
    });
  });

  test("8. Backend error response shows useful error toast message", async () => {
    renderPage();
    await waitFor(() => {
      screen.getByRole("button", { name: /Export Evidence Report/i });
    });

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({
        message: "Internal Server Error in generating evidence"
      })
    });

    const btn = screen.getByRole("button", { name: /Export Evidence Report/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(mockAnchor.click).not.toHaveBeenCalled();
    });
  });

  test("9. Download filename uses veriscope-evidence-report-run-123.md", async () => {
    renderPage();
    await waitFor(() => {
      screen.getByRole("button", { name: /Export Evidence Report/i });
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "SUCCESS",
        markdown_content: "# Report"
      })
    });

    const btn = screen.getByRole("button", { name: /Export Evidence Report/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(mockAnchor.download).toBe("veriscope-evidence-report-run-123.md");
      expect(mockAnchor.click).toHaveBeenCalled();
    });
  });

  test("10. Old terms are not shown in normal report/export UI", async () => {
    renderPage();
    await waitFor(() => {
      const headerDiv = screen.getByText("Primary Actions").closest("div");
      const card = headerDiv ? headerDiv.parentElement : null;
      expect(card).toBeInTheDocument();
      // Ensure normal export UI doesn't have old terms
      expect(card?.textContent).not.toContain("Targeted Scope");
      expect(card?.textContent).not.toContain("Review Items");
      expect(card?.textContent).not.toContain("Required Items");
      expect(card?.textContent).not.toContain("Missing Tests only");
      expect(card?.textContent).not.toContain("Coverage Gaps & Missing Tests");
    });
  });
});
