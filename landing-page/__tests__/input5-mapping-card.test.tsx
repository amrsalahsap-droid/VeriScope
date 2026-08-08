import React from "react";
import { render, screen } from "@testing-library/react";
import { Input5MappingCard } from "@/components/readiness/Input5MappingCard";
import type { InputReadinessItemViewModel, InputStatus } from "@/lib/readiness/inputReadinessAdapter";

function makeInput5(overrides: Record<string, unknown> = {}): InputReadinessItemViewModel {
  return {
    input_id: "INPUT_5",
    label: "AC → Test Mapping",
    status: (overrides.status as InputStatus) ?? "READY",
    weight: 15,
    earned_score: (overrides.earned_score as number) ?? 15,
    max_score: 15,
    is_hard_blocker: true,
    summary: (overrides.summary as string) ?? "Trusted coverage: 100%. Auto-trusted: 25. User-confirmed: 0. Review required: 0.",
    details: {
      input: "AC_TEST_MAPPING",
      status: (overrides.status as InputStatus) ?? "READY",
      total_acs: 25,
      accepted_ac_count: 25,
      trusted_coverage_percent: 100,
      confirmed_coverage_percent: 100,
      coverage_progress_pct: 100,
      user_confirmed_count: 0,
      veriscope_key_verified_count: 0,
      auto_trusted_coverage_count: 25,
      auto_trusted_evidence_aligned_count: 25,
      auto_trusted_veriscope_key_count: 0,
      trusted_coverage_count: 25,
      evidence_verified_aligned_count: 25,
      metadata_conflict_semantic_match_count: 0,
      metadata_conflict_count: 0,
      partial_support_count: 0,
      suggested_count: 0,
      no_candidate_count: 0,
      missing_candidate_count: 0,
      rejected_count: 0,
      review_required_count: 0,
      summary_integrity: "PASS",
      metadata_quality_status: "PASS",
      metadata_quality_detail: "PASS — all test refs align with accepted ACs.",
      metadata_quality_score: 1.0,
      mapping_discovery_score: 15,
      mapping_discovery_max_score: 15,
      blocking_reasons: [],
      ...((overrides.details as Record<string, unknown>) ?? {}),
    },
    actions: (overrides.actions as any[]) ?? [{ label: "View Mappings", action: "OPEN_MAPPING_REVIEW" }],
  };
}

const riskFixtureDetails: Record<string, unknown> = {
  status: "REVIEW_REQUIRED",
  trusted_coverage_percent: 8.0,
  confirmed_coverage_percent: 8.0,
  coverage_progress_pct: 8.0,
  auto_trusted_coverage_count: 2,
  auto_trusted_evidence_aligned_count: 2,
  auto_trusted_veriscope_key_count: 0,
  trusted_coverage_count: 2,
  evidence_verified_aligned_count: 2,
  metadata_conflict_semantic_match_count: 16,
  metadata_conflict_count: 16,
  partial_support_count: 3,
  suggested_count: 0,
  no_candidate_count: 4,
  missing_candidate_count: 4,
  review_required_count: 23,
  metadata_quality_status: "FAIL",
  metadata_quality_detail: "FAIL — 16 JUnit AC refs conflict with semantic evidence.",
  metadata_quality_score: 0.0,
  mapping_discovery_score: 1.2,
  blocking_reasons: [
    "16 metadata conflicts require resolution",
    "3 partial support mappings require review",
    "4 ACs have no candidate tests",
  ],
};

function makeRiskInput5(): InputReadinessItemViewModel {
  return makeInput5({
    status: "REVIEW_REQUIRED",
    earned_score: 1.2,
    summary: "Trusted coverage: 8.0%. Auto-trusted: 2. User-confirmed: 0. Review required: 23.",
    details: riskFixtureDetails,
    actions: [{ label: "Review Mappings", action: "OPEN_MAPPING_REVIEW" }],
  });
}

describe("Input5MappingCard — auto-trusted coverage model", () => {
  it("card_shows_ready_for_all_evidence_aligned", () => {
    render(<Input5MappingCard input={makeInput5()} repositoryId="repo-1" pullRequestId="pr-1" />);
    expect(screen.getByText("READY")).toBeInTheDocument();
    expect(screen.queryByText("REVIEW_REQUIRED")).not.toBeInTheDocument();
  });

  it("card_shows_trusted_coverage_100", () => {
    render(<Input5MappingCard input={makeInput5()} repositoryId="repo-1" pullRequestId="pr-1" />);
    const labels = screen.getAllByText("Trusted coverage:");
    // The first label is in the header summary; the second is the breakdown row.
    expect(labels[1].closest("div")).toHaveTextContent("100%");
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("card_shows_user_confirmed_optional_zero", () => {
    render(<Input5MappingCard input={makeInput5()} repositoryId="repo-1" pullRequestId="pr-1" />);
    const row = screen.getByText("User-confirmed:").closest("div");
    expect(row).toHaveTextContent("0");
    expect(row).toHaveTextContent("optional");
  });

  it("card_does_not_show_25_pending_review", () => {
    render(<Input5MappingCard input={makeInput5()} repositoryId="repo-1" pullRequestId="pr-1" />);
    expect(screen.queryByText(/pending review/i)).not.toBeInTheDocument();
    expect(screen.getByText("Review required:").closest("div")).toHaveTextContent("0");
  });

  it("card_button_says_view_mappings_when_no_review_required", () => {
    render(<Input5MappingCard input={makeInput5()} repositoryId="repo-1" pullRequestId="pr-1" />);
    const button = screen.getByRole("button", { name: /View Mappings/i });
    expect(button).toBeInTheDocument();
    expect(button).not.toHaveTextContent(/Review Mappings/i);
  });

  it("card_metadata_quality_pass_when_conflicts_zero", () => {
    render(<Input5MappingCard input={makeInput5()} repositoryId="repo-1" pullRequestId="pr-1" />);
    expect(screen.getByText("PASS — all test refs align with accepted ACs.")).toBeInTheDocument();
    expect(screen.queryByText(/FAIL/)).not.toBeInTheDocument();
  });

  it("card_review_badge_zero_when_only_auto_trusted", () => {
    render(<Input5MappingCard input={makeInput5()} repositoryId="repo-1" pullRequestId="pr-1" />);
    const button = screen.getByRole("button", { name: /View Mappings/i });
    expect(button).not.toHaveTextContent(/\d+/);
  });

  it("card_shows_auto_trusted_and_review_required_breakdown", () => {
    render(<Input5MappingCard input={makeRiskInput5()} repositoryId="repo-1" pullRequestId="pr-1" />);
    const labels = screen.getAllByText("Trusted coverage:");
    expect(labels[1].closest("div")).toHaveTextContent("8%");
    expect(screen.getByText("Auto-trusted:").closest("div")).toHaveTextContent("2");
    expect(screen.getByText("Review required:").closest("div")).toHaveTextContent("23");
  });

  it("card_button_says_review_mappings_when_review_required", () => {
    render(<Input5MappingCard input={makeRiskInput5()} repositoryId="repo-1" pullRequestId="pr-1" />);
    const button = screen.getByRole("button", { name: /Review Mappings/i });
    expect(button).toBeInTheDocument();
    expect(button).toHaveTextContent("23");
  });

  it("card_renders_fail_metadata_quality_for_conflict_fixture", () => {
    render(<Input5MappingCard input={makeRiskInput5()} repositoryId="repo-1" pullRequestId="pr-1" />);
    expect(screen.getByText(/FAIL/)).toBeInTheDocument();
  });

  it("card_renders_review_required_for_conflict_fixture", () => {
    render(<Input5MappingCard input={makeRiskInput5()} repositoryId="repo-1" pullRequestId="pr-1" />);
    expect(screen.getByText("REVIEW_REQUIRED")).toBeInTheDocument();
  });
});
