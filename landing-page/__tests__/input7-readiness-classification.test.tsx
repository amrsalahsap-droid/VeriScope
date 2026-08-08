/**
 * Test Input 7 readiness status and confidence classification in the UI.
 *
 * Tests verify:
 * - PARTIAL_READY status display for partial changed file coverage
 * - MISSING status only when no coverage exists
 * - PARTIAL confidence display for partial changed file coverage
 * - Overall coverage percent consistency between top and bottom
 * - Status reason mentions changed file coverage details
 */

import { render, screen } from "@testing-library/react";
import { Input7CoverageCard } from "@/components/readiness/Input7CoverageCard";
import { InputReadinessItemViewModel } from "@/lib/readiness/inputReadinessAdapter";

describe("Input7CoverageCard - Readiness Classification", () => {
  const mockRepositoryId = "test-repo-id";
  const mockPullRequestId = "test-pr-id";

  const createMockInput = (overrides: Partial<InputReadinessItemViewModel> = {}): InputReadinessItemViewModel => ({
    input_id: "INPUT_7",
    label: "Test Coverage Mapping",
    status: "MISSING",
    weight: 1,
    earned_score: 0,
    max_score: 1,
    is_hard_blocker: false,
    summary: "No code coverage mapping available.",
    details: {},
    actions: [],
    ...overrides,
  });

  describe("PARTIAL_READY status display", () => {
    it("should show PARTIAL_READY for 4 of 6 changed files covered", () => {
      const mockInput = createMockInput({
        status: "PARTIAL_READY",
        summary: "Coverage is current and linked to the active PR. 4 of 6 changed files have coverage; 2 changed files still need review.",
        details: {
          coverage_commit_sha: "abc123def456",
          current_pr_head_sha: "abc123def456",
          commit_sha_source: "AUTO_FROM_SELECTED_PR",
          sha_mismatch: false,
          is_current: true,
          files_total: 7,
          covered_file_count: 7,
          changed_files_total: 6,
          changed_files_with_coverage: 4,
          changed_files_without_coverage: 2,
          file_to_test_link_count: 4,
          current_pr_coverage_confidence: "PARTIAL",
          overall_coverage_pct: 0.96,
          coverage_level: "TEST_CASE_LEVEL",
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Status badge should show PARTIAL (display name for PARTIAL_READY)
      expect(screen.getByText("PARTIAL")).toBeInTheDocument();

      // Summary should mention 4 of 6 changed files
      expect(screen.getByText(/4 of 6 changed files have coverage/)).toBeInTheDocument();

      // Confidence should be PARTIAL
      expect(screen.getByText("PARTIAL")).toBeInTheDocument();
    });

    it("should not show MISSING when current coverage exists", () => {
      const mockInput = createMockInput({
        status: "PARTIAL_READY",
        summary: "Coverage is current and linked to the active PR. 4 of 6 changed files have coverage; 2 changed files still need review.",
        details: {
          coverage_commit_sha: "abc123def456",
          current_pr_head_sha: "abc123def456",
          is_current: true,
          files_total: 7,
          covered_file_count: 7,
          changed_files_total: 6,
          changed_files_with_coverage: 4,
          current_pr_coverage_confidence: "PARTIAL",
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Should not show MISSING status
      expect(screen.queryByText("MISSING")).not.toBeInTheDocument();
    });
  });

  describe("Confidence display", () => {
    it("should show PARTIAL confidence for partial changed file coverage", () => {
      const mockInput = createMockInput({
        status: "PARTIAL_READY",
        summary: "Coverage is current and linked to the active PR. 4 of 6 changed files have coverage; 2 changed files still need review.",
        details: {
          current_pr_coverage_confidence: "PARTIAL",
          changed_files_total: 6,
          changed_files_with_coverage: 4,
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Confidence should be PARTIAL, not NONE
      const confidenceElement = screen.getByText(/PARTIAL/);
      expect(confidenceElement).toBeInTheDocument();

      // Should not show NONE
      expect(screen.queryByText("NONE")).not.toBeInTheDocument();
    });

    it("should show NONE confidence only when no current coverage", () => {
      const mockInput = createMockInput({
        status: "MISSING",
        summary: "No code coverage mapping available.",
        details: {
          current_pr_coverage_confidence: "NONE",
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Should show NONE confidence
      expect(screen.getByText("NONE")).toBeInTheDocument();
    });
  });

  describe("Overall coverage percent display", () => {
    it("should show consistent overall coverage percent in summary and details", () => {
      const mockInput = createMockInput({
        status: "TEST_LEVEL_READY",
        summary: "Per-test coverage available (96.0% overall). Relevant to current PR.",
        details: {
          overall_coverage_pct: 0.96,
          coverage_level: "TEST_CASE_LEVEL",
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Summary should show 96.0%
      expect(screen.getByText(/96.0% overall/)).toBeInTheDocument();

      // Expand details to check bottom display
      const showDetailsButton = screen.getByText("Show details");
      showDetailsButton.click();

      // Bottom should also show 96.0% (multiplied by 100)
      expect(screen.getByText(/96.0%/)).toBeInTheDocument();
    });

    it("should not show 1.0% when actual coverage is 100%", () => {
      const mockInput = createMockInput({
        status: "READY",
        summary: "Current coverage available (100.0% overall, RUN_LEVEL).",
        details: {
          overall_coverage_pct: 1.0,
          coverage_level: "RUN_LEVEL",
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Should show 100.0%, not 1.0%
      expect(screen.getByText(/100.0% overall/)).toBeInTheDocument();
      expect(screen.queryByText(/1.0% overall/)).not.toBeInTheDocument();
    });
  });

  describe("Status reason and details", () => {
    it("should mention 4 of 6 changed files in status reason", () => {
      const mockInput = createMockInput({
        status: "PARTIAL_READY",
        summary: "Coverage is current and linked to the active PR. 4 of 6 changed files have coverage; 2 changed files still need review.",
        details: {
          status_reason: "Coverage is current but only partially covers changed files (4/6).",
          changed_files_total: 6,
          changed_files_with_coverage: 4,
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Summary should mention 4 of 6
      expect(screen.getByText(/4 of 6 changed files have coverage/)).toBeInTheDocument();

      // Expand details to check status reason
      const showDetailsButton = screen.getByText("Show details");
      showDetailsButton.click();

      // Status reason should mention 4/6
      expect(screen.getByText(/4\/6/)).toBeInTheDocument();
    });

    it("should show changed files covered count correctly", () => {
      const mockInput = createMockInput({
        status: "PARTIAL_READY",
        summary: "Coverage is current and linked to the active PR. 4 of 6 changed files have coverage; 2 changed files still need review.",
        details: {
          changed_files_total: 6,
          changed_files_with_coverage: 4,
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Expand details
      const showDetailsButton = screen.getByText("Show details");
      showDetailsButton.click();

      // Should show "4 / 6" for changed files covered
      expect(screen.getByText(/4 \/ 6/)).toBeInTheDocument();
    });
  });

  describe("NO_CHANGED_FILE_COVERAGE status", () => {
    it("should show NO_CHANGED_FILE_COVERAGE when no changed files are covered", () => {
      const mockInput = createMockInput({
        status: "NO_CHANGED_FILE_COVERAGE",
        summary: "Coverage is current but does not overlap with any changed files. (96.0% overall).",
        details: {
          changed_files_total: 6,
          changed_files_with_coverage: 0,
          changed_files_without_coverage: 6,
          current_pr_coverage_confidence: "LOW",
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Status badge should show NO_CHANGED_FILE_COVERAGE
      expect(screen.getByText("NO_CHANGED_FILE_COVERAGE")).toBeInTheDocument();

      // Summary should mention no overlap
      expect(screen.getByText(/does not overlap with any changed files/)).toBeInTheDocument();
    });
  });

  describe("READY status with full changed file coverage", () => {
    it("should show READY when all changed files are covered", () => {
      const mockInput = createMockInput({
        status: "READY",
        summary: "Current coverage available (96.0% overall, RUN_LEVEL). Relevant to current PR.",
        details: {
          changed_files_total: 6,
          changed_files_with_coverage: 6,
          changed_files_without_coverage: 0,
          current_pr_coverage_confidence: "HIGH",
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Status badge should show READY
      expect(screen.getByText("READY")).toBeInTheDocument();

      // Confidence should be HIGH
      expect(screen.getByText("HIGH")).toBeInTheDocument();
    });

    it("should show changed source files covered 4 of 4", () => {
      const mockInput = createMockInput({
        status: "READY",
        summary: "Current coverage available (96.0% overall, RUN_LEVEL). All 4 coverable source files covered. 2 test files changed.",
        details: {
          coverable_changed_files_total: 4,
          coverable_changed_files_covered: 4,
          changed_test_files_total: 2,
          non_coverable_changed_files_total: 0,
          current_pr_coverage_confidence: "HIGH",
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Expand details
      const showDetailsButton = screen.getByText("Show details");
      showDetailsButton.click();

      // Should show "4 / 4" for changed source files
      expect(screen.getByText(/4 \/ 4/)).toBeInTheDocument();

      // Should show changed test files count
      expect(screen.getByText(/Changed test files:/)).toBeInTheDocument();
      expect(screen.getByText(/2/)).toBeInTheDocument();
    });
  });

  describe("Changed file classification display", () => {
    it("should show changed source files covered 4 of 4", () => {
      const mockInput = createMockInput({
        status: "READY",
        summary: "Current coverage available (96.0% overall, RUN_LEVEL). All 4 coverable source files covered.",
        details: {
          coverable_changed_files_total: 4,
          coverable_changed_files_covered: 4,
          changed_test_files_total: 2,
          non_coverable_changed_files_total: 0,
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Expand details
      const showDetailsButton = screen.getByText("Show details");
      showDetailsButton.click();

      // Should show changed source files covered
      expect(screen.getByText("Changed source files covered:")).toBeInTheDocument();
      expect(screen.getByText("4 / 4")).toBeInTheDocument();
    });

    it("should show changed test files 2", () => {
      const mockInput = createMockInput({
        status: "READY",
        summary: "Current coverage available (96.0% overall, RUN_LEVEL). All 4 coverable source files covered. 2 test files changed.",
        details: {
          coverable_changed_files_total: 4,
          coverable_changed_files_covered: 4,
          changed_test_files_total: 2,
          non_coverable_changed_files_total: 0,
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Expand details
      const showDetailsButton = screen.getByText("Show details");
      showDetailsButton.click();

      // Should show changed test files
      expect(screen.getByText("Changed test files:")).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
    });

    it("should show non-coverable changed files when present", () => {
      const mockInput = createMockInput({
        status: "READY",
        summary: "Current coverage available (96.0% overall, RUN_LEVEL). All 4 coverable source files covered.",
        details: {
          coverable_changed_files_total: 4,
          coverable_changed_files_covered: 4,
          changed_test_files_total: 2,
          non_coverable_changed_files_total: 1,
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Expand details
      const showDetailsButton = screen.getByText("Show details");
      showDetailsButton.click();

      // Should show non-coverable changed files
      expect(screen.getByText("Non-coverable changed files:")).toBeInTheDocument();
      expect(screen.getByText("1")).toBeInTheDocument();
    });

    it("should list uncovered source files when any", () => {
      const mockInput = createMockInput({
        status: "PARTIAL_READY",
        summary: "Coverage is current and linked to the active PR. 3 of 4 coverable source files covered; 1 source files still need review.",
        details: {
          coverable_changed_files_total: 4,
          coverable_changed_files_covered: 3,
          uncovered_coverable_changed_files: ["app/uncovered_module.py"],
        },
      });

      render(
        <Input7CoverageCard
          input={mockInput}
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
        />
      );

      // Expand details
      const showDetailsButton = screen.getByText("Show details");
      showDetailsButton.click();

      // Should show uncovered source files section
      expect(screen.getByText("Uncovered changed source files:")).toBeInTheDocument();
      expect(screen.getByText(/app\/uncovered_module\.py/)).toBeInTheDocument();
    });
  });
});
