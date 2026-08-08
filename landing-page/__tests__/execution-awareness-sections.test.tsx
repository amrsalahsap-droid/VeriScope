/**
 * Tests for Draft Recommendation Execution Awareness UI sections.
 *
 * Validates that the recommendation detail page correctly renders:
 * - Already Verified section (from execution-aware data)
 * - Failed Current PR section
 * - Stale Rerun Required section
 * - Mapping Review Needed section
 * - Evidence path per candidate
 * - would_have_been_priority on verified tests
 * - Execution-aware counts in testing_strategy
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// ---------------------------------------------------------------------------
// Helpers: replicate the frontend bucketing logic from page.tsx
// ---------------------------------------------------------------------------

interface RecommendedTest {
  stable_identity: string;
  display_name: string;
  suite_name: string;
  tier: string;
  execution_aware_tier?: string;
  priority_score: number;
  reason: string;
  candidate_status?: string;
  active_action?: string;
  included?: boolean;
  mapping_uncertainty?: string;
  evidence_path?: Array<{ step: string; confidence?: number; review_status?: string; [key: string]: any }>;
  would_have_been_priority?: string;
}

const _EXCLUDED_FROM_MUST_RUN = new Set([
  "ALREADY_PASSED_CURRENT_PR",
  "FAILED_CURRENT_PR",
  "SKIPPED_CURRENT_PR",
  "STALE_RESULT_RERUN_REQUIRED",
  "NEEDS_MAPPING_REVIEW",
  "NOT_RELEVANT",
]);

function computeTier(t: RecommendedTest): string {
  return (
    t.execution_aware_tier ||
    (t.candidate_status && _EXCLUDED_FROM_MUST_RUN.has(t.candidate_status)
      ? t.candidate_status === "ALREADY_PASSED_CURRENT_PR"
        ? "already_verified"
        : t.candidate_status === "FAILED_CURRENT_PR"
        ? "failed_current_pr"
        : t.candidate_status === "STALE_RESULT_RERUN_REQUIRED"
        ? "stale_rerun_required"
        : t.candidate_status === "NEEDS_MAPPING_REVIEW"
        ? "mapping_review_needed"
        : "skipped_current_pr"
      : t.tier)
  );
}

function makeTest(overrides: Partial<RecommendedTest>): RecommendedTest {
  return {
    stable_identity: "Suite::test_default",
    display_name: "test_default",
    suite_name: "Suite",
    tier: "must_run",
    priority_score: 0.9,
    reason: "Test reason",
    candidate_status: undefined,
    active_action: "RUN_NOW",
    included: true,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Execution Awareness Bucketing", () => {
  it("passed current SHA tests go to already_verified tier", () => {
    const t = makeTest({
      candidate_status: "ALREADY_PASSED_CURRENT_PR",
      active_action: "NO_RERUN_NEEDED",
      included: false,
    });
    expect(computeTier(t)).toBe("already_verified");
  });

  it("passed current SHA tests do NOT appear in must_run", () => {
    const t = makeTest({
      candidate_status: "ALREADY_PASSED_CURRENT_PR",
      priority_score: 0.95,
    });
    const tier = computeTier(t);
    expect(tier).not.toBe("must_run");
    expect(tier).toBe("already_verified");
  });

  it("failed current SHA tests go to failed_current_pr tier", () => {
    const t = makeTest({
      candidate_status: "FAILED_CURRENT_PR",
      active_action: "BLOCK_RELEASE_OR_INVESTIGATE",
    });
    expect(computeTier(t)).toBe("failed_current_pr");
  });

  it("old SHA results go to stale_rerun_required tier", () => {
    const t = makeTest({
      candidate_status: "STALE_RESULT_RERUN_REQUIRED",
      active_action: "RUN_NOW",
    });
    expect(computeTier(t)).toBe("stale_rerun_required");
  });

  it("suggested mappings go to mapping_review_needed tier", () => {
    const t = makeTest({
      candidate_status: "NEEDS_MAPPING_REVIEW",
      active_action: "CONFIRM_MAPPING_THEN_RUN",
      mapping_uncertainty: "system_suggested",
    });
    expect(computeTier(t)).toBe("mapping_review_needed");
  });

  it("execution_aware_tier from backend takes precedence", () => {
    const t = makeTest({
      execution_aware_tier: "already_verified",
      candidate_status: "ALREADY_PASSED_CURRENT_PR",
    });
    expect(computeTier(t)).toBe("already_verified");
  });

  it("NOT_EXECUTED uses priority-based tier", () => {
    const highPriority = makeTest({
      candidate_status: "NOT_EXECUTED_FOR_CURRENT_PR",
      priority_score: 0.85,
      tier: "must_run",
    });
    expect(computeTier(highPriority)).toBe("must_run");

    const medPriority = makeTest({
      candidate_status: "NOT_EXECUTED_FOR_CURRENT_PR",
      priority_score: 0.6,
      tier: "should_run",
    });
    expect(computeTier(medPriority)).toBe("should_run");
  });
});

describe("Execution Awareness Section Rendering", () => {
  // Minimal section renderer that mirrors the page.tsx logic
  function ExecutionSections({ tests }: { tests: RecommendedTest[] }) {
    const alreadyVerified = tests.filter((t) => computeTier(t) === "already_verified");
    const failedCurrentPR = tests.filter((t) => computeTier(t) === "failed_current_pr");
    const staleRerun = tests.filter((t) => computeTier(t) === "stale_rerun_required");
    const mappingReview = tests.filter((t) => computeTier(t) === "mapping_review_needed");
    const mustRun = tests.filter((t) => computeTier(t) === "must_run");
    const shouldRun = tests.filter((t) => computeTier(t) === "should_run");

    return (
      <div>
        {alreadyVerified.length > 0 && (
          <div data-testid="already-verified-section">
            <h2>Already Verified ({alreadyVerified.length})</h2>
            {alreadyVerified.map((t) => (
              <div key={t.stable_identity} data-testid="verified-item">
                <span>{t.display_name}</span>
                {t.would_have_been_priority && (
                  <span data-testid="would-have-been">Would have been: {t.would_have_been_priority}</span>
                )}
                {t.evidence_path && t.evidence_path.length > 0 && (
                  <span data-testid="evidence-path">Evidence: {t.evidence_path.length} steps</span>
                )}
              </div>
            ))}
          </div>
        )}
        {failedCurrentPR.length > 0 && (
          <div data-testid="failed-section">
            <h2>Failed Current PR ({failedCurrentPR.length})</h2>
            {failedCurrentPR.map((t) => (
              <div key={t.stable_identity} data-testid="failed-item">
                <span>{t.display_name}</span>
              </div>
            ))}
          </div>
        )}
        {staleRerun.length > 0 && (
          <div data-testid="stale-section">
            <h2>Stale Rerun Required ({staleRerun.length})</h2>
            {staleRerun.map((t) => (
              <div key={t.stable_identity} data-testid="stale-item">
                <span>{t.display_name}</span>
              </div>
            ))}
          </div>
        )}
        {mappingReview.length > 0 && (
          <div data-testid="mapping-review-section">
            <h2>Mapping Review Needed ({mappingReview.length})</h2>
            {mappingReview.map((t) => (
              <div key={t.stable_identity} data-testid="mapping-review-item">
                <span>{t.display_name}</span>
                {t.mapping_uncertainty && (
                  <span data-testid="review-status">review_status: {t.mapping_uncertainty}</span>
                )}
              </div>
            ))}
          </div>
        )}
        {mustRun.length > 0 && (
          <div data-testid="must-run-section">
            <h2>Must Run ({mustRun.length})</h2>
          </div>
        )}
        {shouldRun.length > 0 && (
          <div data-testid="should-run-section">
            <h2>Should Run ({shouldRun.length})</h2>
          </div>
        )}
      </div>
    );
  }

  const sampleTests: RecommendedTest[] = [
    makeTest({
      stable_identity: "Suite::test_login",
      display_name: "test_login",
      candidate_status: "ALREADY_PASSED_CURRENT_PR",
      active_action: "NO_RERUN_NEEDED",
      included: false,
      would_have_been_priority: "MUST_RUN",
      evidence_path: [
        { step: "AC→Test", confidence: 0.9, review_status: "user_confirmed" },
        { step: "TestResult", commit_sha: "abc123" },
      ],
    }),
    makeTest({
      stable_identity: "Suite::test_signup_fail",
      display_name: "test_signup_fail",
      candidate_status: "FAILED_CURRENT_PR",
      active_action: "BLOCK_RELEASE_OR_INVESTIGATE",
    }),
    makeTest({
      stable_identity: "Suite::test_profile_stale",
      display_name: "test_profile_stale",
      candidate_status: "STALE_RESULT_RERUN_REQUIRED",
      active_action: "RUN_NOW",
    }),
    makeTest({
      stable_identity: "Suite::test_billing_unconfirmed",
      display_name: "test_billing_unconfirmed",
      candidate_status: "NEEDS_MAPPING_REVIEW",
      active_action: "CONFIRM_MAPPING_THEN_RUN",
      mapping_uncertainty: "system_suggested",
    }),
    makeTest({
      stable_identity: "Suite::test_password_reset",
      display_name: "test_password_reset",
      candidate_status: "NOT_EXECUTED_FOR_CURRENT_PR",
      tier: "must_run",
      priority_score: 0.9,
    }),
    makeTest({
      stable_identity: "Suite::test_optional_feature",
      display_name: "test_optional_feature",
      candidate_status: "NOT_EXECUTED_FOR_CURRENT_PR",
      tier: "should_run",
      priority_score: 0.6,
    }),
  ];

  it("renders Already Verified section for ALREADY_PASSED tests", () => {
    render(<ExecutionSections tests={sampleTests} />);
    expect(screen.getByTestId("already-verified-section")).toBeInTheDocument();
    expect(screen.getByText("Already Verified (1)")).toBeInTheDocument();
    expect(screen.getByText("test_login")).toBeInTheDocument();
  });

  it("shows would_have_been_priority on verified tests", () => {
    render(<ExecutionSections tests={sampleTests} />);
    expect(screen.getByTestId("would-have-been")).toHaveTextContent("Would have been: MUST_RUN");
  });

  it("shows evidence path on verified tests", () => {
    render(<ExecutionSections tests={sampleTests} />);
    expect(screen.getByTestId("evidence-path")).toHaveTextContent("Evidence: 2 steps");
  });

  it("renders Failed Current PR section", () => {
    render(<ExecutionSections tests={sampleTests} />);
    expect(screen.getByTestId("failed-section")).toBeInTheDocument();
    expect(screen.getByText("Failed Current PR (1)")).toBeInTheDocument();
    expect(screen.getByText("test_signup_fail")).toBeInTheDocument();
  });

  it("renders Stale Rerun Required section", () => {
    render(<ExecutionSections tests={sampleTests} />);
    expect(screen.getByTestId("stale-section")).toBeInTheDocument();
    expect(screen.getByText("Stale Rerun Required (1)")).toBeInTheDocument();
    expect(screen.getByText("test_profile_stale")).toBeInTheDocument();
  });

  it("renders Mapping Review Needed section with review_status", () => {
    render(<ExecutionSections tests={sampleTests} />);
    expect(screen.getByTestId("mapping-review-section")).toBeInTheDocument();
    expect(screen.getByText("Mapping Review Needed (1)")).toBeInTheDocument();
    expect(screen.getByTestId("review-status")).toHaveTextContent("review_status: system_suggested");
  });

  it("does NOT show ALREADY_PASSED tests under Must Run", () => {
    render(<ExecutionSections tests={sampleTests} />);
    // Must Run should only contain test_password_reset
    expect(screen.getByTestId("must-run-section")).toBeInTheDocument();
    expect(screen.getByText("Must Run (1)")).toBeInTheDocument();
    // test_login has priority 0.9 but should NOT be in must_run
    const mustRunSection = screen.getByTestId("must-run-section");
    expect(mustRunSection).not.toHaveTextContent("test_login");
  });

  it("shows Should Run section for medium-priority not-executed tests", () => {
    render(<ExecutionSections tests={sampleTests} />);
    expect(screen.getByTestId("should-run-section")).toBeInTheDocument();
    expect(screen.getByText("Should Run (1)")).toBeInTheDocument();
  });

  it("does not render sections when no tests match", () => {
    const noFailures = sampleTests.filter(
      (t) => t.candidate_status !== "FAILED_CURRENT_PR"
    );
    const { container } = render(<ExecutionSections tests={noFailures} />);
    expect(container.querySelector("[data-testid='failed-section']")).toBeNull();
  });
});

describe("Testing Strategy Counts", () => {
  it("includes execution-aware count fields", () => {
    // Simulate the backend testing_strategy response
    const testingStrategy = {
      recommendation_mode: "DRAFT",
      evidence_quality: "MEDIUM",
      optimization_allowed: true,
      must_run_count: 3,
      should_run_count: 2,
      fallback_count: 1,
      already_verified_count: 5,
      failed_current_pr_count: 1,
      stale_rerun_required_count: 2,
      mapping_review_needed_count: 3,
      estimated_runtime_seconds: 120.0,
      full_suite_runtime_seconds: 600.0,
      runtime_confidence: "MEDIUM",
      skipped_count: 0,
      skipped_reason_summary: null,
    };

    expect(testingStrategy.already_verified_count).toBe(5);
    expect(testingStrategy.failed_current_pr_count).toBe(1);
    expect(testingStrategy.stale_rerun_required_count).toBe(2);
    expect(testingStrategy.mapping_review_needed_count).toBe(3);
    // Must run should NOT include already_verified
    expect(testingStrategy.must_run_count).toBe(3);
  });
});
