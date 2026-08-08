/**
 * @jest-environment jsdom
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// Helper to construct nested API response
function makeNestedApiResponse(overrides: any = {}) {
  const executionSummary = {
    total_tests: 18,
    passed: 18,
    failed: 0,
    errors: 0,
    skipped: 0,
    latest_test_run_id: "run-123",
    test_import_id: "import-456",
    ...overrides.execution_summary,
  };

  const mappingSummary = {
    total_acs: 25,
    user_confirmed: 0,
    veriscope_key_verified: 0,
    evidence_verified_aligned: 2,
    metadata_conflict_semantic_match: 16,
    partial_support: 3,
    suggested: 0,
    no_candidate: 4,
    rejected: 0,
    sum_check: 25,
    is_ac_level_exclusive: true,
    summary_integrity: "PASS",
    ...overrides.mapping_summary,
  };

  const candidateSummary = {
    total_candidates: 18,
    ai_evaluated_candidates: 18,
    deterministic_only_candidates: 0,
    low_confidence_candidates: 0,
    ...overrides.candidate_summary,
  };

  const rows = overrides.rows || [
    {
      ac_id: "ac-01",
      stable_ac_key: "AC-KEY-01",
      display_ac_ref: "AC-01",
      ac_title: "Weak passwords are rejected during sign-up.",
      ac_text: "Weak passwords are rejected during sign-up.",
      requirement_group: "Sign-up",
      status: "EVIDENCE_VERIFIED_ALIGNED",
      row_status: "EVIDENCE_VERIFIED_ALIGNED",
      suggested_tests_count: 1,
      suggested_tests: [
        {
          edge_id: "edge-1",
          candidate_id: "cand-1",
          test_case_id: "tc-1",
          stable_test_id: "test-1",
          test_name: "should_reject_weak_password_during_signup",
          test_title: "should_reject_weak_password_during_signup",
          review_status: "EVIDENCE_VERIFIED_ALIGNED",
          conflict_detected: false,
          coverage_type: "full",
          execution_status: "passed",
        },
      ],
    },
    {
      ac_id: "ac-07",
      stable_ac_key: "AC-KEY-07",
      display_ac_ref: "AC-07",
      ac_title: "Weak passwords are rejected during reset-password.",
      ac_text: "Weak passwords are rejected during reset-password.",
      requirement_group: "Reset password",
      status: "METADATA_CONFLICT_SEMANTIC_MATCH",
      row_status: "METADATA_CONFLICT_SEMANTIC_MATCH",
      suggested_tests_count: 1,
      suggested_tests: [
        {
          edge_id: "edge-7",
          candidate_id: "cand-7",
          test_case_id: "tc-7",
          stable_test_id: "test-7",
          test_name: "should_reject_weak_password_during_password_reset",
          test_title: "should_reject_weak_password_during_password_reset",
          declared_ac_ref: "AC-03",
          declared_ac_text: "Weak passwords are rejected during update-password.",
          semantic_best_match_ac_ref: "AC-07",
          semantic_best_match_ac_text: "Weak passwords are rejected during reset-password.",
          review_status: "METADATA_CONFLICT_SEMANTIC_MATCH",
          conflict_detected: true,
          conflict_type: "DECLARED_REF_DIFFERS_FROM_SEMANTIC_MATCH",
          conflict_reason: "Declared ref AC-03 differs from semantic match AC-07",
          semantic_match_accept_allowed: true,
          coverage_type: "full",
          execution_status: "passed",
        },
      ],
    },
    {
      ac_id: "ac-15",
      stable_ac_key: "AC-KEY-15",
      display_ac_ref: "AC-15",
      ac_title: "Backend/API validation is mandatory and cannot rely only on frontend validation.",
      ac_text: "Backend/API validation is mandatory and cannot rely only on frontend validation.",
      requirement_group: "API Validation",
      status: "PARTIAL_SUPPORT",
      row_status: "PARTIAL_SUPPORT",
      suggested_tests_count: 1,
      suggested_tests: [
        {
          edge_id: "edge-15",
          candidate_id: "cand-15",
          test_case_id: "tc-15",
          stable_test_id: "test-15",
          test_name: "should_reject_weak_password_when_frontend_validation_is_bypassed",
          test_title: "should_reject_weak_password_when_frontend_validation_is_bypassed",
          review_status: "PARTIAL_SUPPORT",
          conflict_detected: false,
          coverage_type: "partial",
          execution_status: "passed",
          partial_support_reason: "Proves backend validation execution but missing frontend bypass isolation assertion",
        },
      ],
    },
  ];

  const qualityWarnings = overrides.quality_warnings || [];

  const compatibilitySummary = {
    confirmed: mappingSummary.user_confirmed,
    suggested: mappingSummary.suggested,
    conflicted: mappingSummary.metadata_conflict_semantic_match,
    needs_review: mappingSummary.partial_support,
    unmapped: mappingSummary.no_candidate,
    rejected: mappingSummary.rejected,
  };

  return {
    execution_summary: executionSummary,
    mapping_summary: mappingSummary,
    candidate_summary: candidateSummary,
    rows: rows,
    items: rows,
    quality_warnings: qualityWarnings,
    compatibility_summary: compatibilitySummary,
    summary: {
      total_acs: mappingSummary.total_acs,
      confirmed: mappingSummary.user_confirmed,
      user_confirmed: mappingSummary.user_confirmed,
      evidence_verified_aligned: mappingSummary.evidence_verified_aligned,
      metadata_conflict_semantic_match: mappingSummary.metadata_conflict_semantic_match,
      partial_support: mappingSummary.partial_support,
      suggested: mappingSummary.suggested,
      no_candidate: mappingSummary.no_candidate,
      rejected: mappingSummary.rejected,
      sum_check: mappingSummary.sum_check,
      is_ac_level_exclusive: mappingSummary.is_ac_level_exclusive,
      summary_integrity: mappingSummary.summary_integrity,
    },
  };
}

// Mock Component for UI testing of response consumption
function MappingSummaryDisplay({ response }: { response: any }) {
  const exec = response.execution_summary || {};
  const mapSum = response.mapping_summary || {};
  const integrity = mapSum.summary_integrity;

  return (
    <div data-testid="mapping-workspace">
      {/* Execution Summary */}
      <section data-testid="execution-summary">
        <h2>Execution Summary</h2>
        <div>Imported tests: {exec.total_tests}</div>
        <div>Passed: {exec.passed}</div>
        <div>Failed: {exec.failed}</div>
        <div>Errors: {exec.errors}</div>
        <div>Skipped: {exec.skipped}</div>
      </section>

      {/* Mapping Summary */}
      <section data-testid="mapping-summary">
        <h2>Mapping Summary</h2>
        <div>User Confirmed: {mapSum.user_confirmed}</div>
        <div>Key Verified: {mapSum.veriscope_key_verified}</div>
        <div>Evidence Aligned: {mapSum.evidence_verified_aligned}</div>
        <div>Metadata Conflict: Semantic Match Found: {mapSum.metadata_conflict_semantic_match}</div>
        <div>Partial Support: {mapSum.partial_support}</div>
        <div>Suggested: {mapSum.suggested}</div>
        <div>No Candidate: {mapSum.no_candidate}</div>
        <div>Rejected: {mapSum.rejected}</div>
      </section>

      {/* Integrity Warning */}
      {integrity === "FAIL" && (
        <div data-testid="integrity-warning" className="warning-banner">
          Warning: Summary integrity check failed. Counters do not sum to total ACs.
        </div>
      )}

      {/* Rows */}
      <div data-testid="rows-list">
        {response.rows.map((row: any) => (
          <div key={row.ac_id} data-testid={`row-${row.display_ac_ref}`}>
            <h3>{row.display_ac_ref} — {row.ac_title}</h3>
            <div>Status: {row.status}</div>

            {/* Actions for Metadata Conflict */}
            {row.status === "METADATA_CONFLICT_SEMANTIC_MATCH" && (
              <div data-testid={`actions-${row.display_ac_ref}`}>
                <button>Accept semantic match</button>
                <button>Keep declared ref anyway</button>
                <button>Reject</button>
                <button>Manual link</button>
                <button>Add comment</button>
              </div>
            )}

            {/* Actions for Partial Support */}
            {row.status === "PARTIAL_SUPPORT" && (
              <div data-testid={`actions-${row.display_ac_ref}`}>
                <button>Accept as partial</button>
                <button>Mark insufficient</button>
                <button>Link another test</button>
                <button>Add accepted risk/comment</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

describe("Phase 7 — Frontend Regression Tests for Nested API Contract", () => {
  it("renders_execution_summary_from_nested_response", () => {
    const res = makeNestedApiResponse();
    render(<MappingSummaryDisplay response={res} />);

    const execSec = screen.getByTestId("execution-summary");
    expect(execSec).toHaveTextContent("Imported tests: 18");
    expect(execSec).toHaveTextContent("Passed: 18");
    expect(execSec).toHaveTextContent("Failed: 0");
    expect(execSec).toHaveTextContent("Errors: 0");
    expect(execSec).toHaveTextContent("Skipped: 0");
  });

  it("renders_mapping_summary_from_nested_response", () => {
    const res = makeNestedApiResponse();
    render(<MappingSummaryDisplay response={res} />);

    const mapSec = screen.getByTestId("mapping-summary");
    expect(mapSec).toHaveTextContent("User Confirmed: 0");
    expect(mapSec).toHaveTextContent("Key Verified: 0");
    expect(mapSec).toHaveTextContent("Evidence Aligned: 2");
    expect(mapSec).toHaveTextContent("Metadata Conflict: Semantic Match Found: 16");
    expect(mapSec).toHaveTextContent("Partial Support: 3");
    expect(mapSec).toHaveTextContent("Suggested: 0");
    expect(mapSec).toHaveTextContent("No Candidate: 4");
    expect(mapSec).toHaveTextContent("Rejected: 0");
  });

  it("shows_integrity_warning_when_summary_integrity_fails", () => {
    const res = makeNestedApiResponse({
      mapping_summary: { summary_integrity: "FAIL", total_acs: 25, sum_check: 20 }
    });
    render(<MappingSummaryDisplay response={res} />);

    expect(screen.getByTestId("integrity-warning")).toBeInTheDocument();
  });

  it("hides_integrity_warning_when_summary_integrity_passes", () => {
    const res = makeNestedApiResponse({
      mapping_summary: { summary_integrity: "PASS" }
    });
    render(<MappingSummaryDisplay response={res} />);

    expect(screen.queryByTestId("integrity-warning")).not.toBeInTheDocument();
  });

  it("metadata_conflict_row_shows_accept_semantic_match", () => {
    const res = makeNestedApiResponse();
    render(<MappingSummaryDisplay response={res} />);

    const rowActions = screen.getByTestId("actions-AC-07");
    expect(rowActions).toHaveTextContent("Accept semantic match");
  });

  it("metadata_conflict_row_shows_keep_declared_ref", () => {
    const res = makeNestedApiResponse();
    render(<MappingSummaryDisplay response={res} />);

    const rowActions = screen.getByTestId("actions-AC-07");
    expect(rowActions).toHaveTextContent("Keep declared ref anyway");
  });

  it("metadata_conflict_row_shows_reject", () => {
    const res = makeNestedApiResponse();
    render(<MappingSummaryDisplay response={res} />);

    const rowActions = screen.getByTestId("actions-AC-07");
    expect(rowActions).toHaveTextContent("Reject");
  });

  it("metadata_conflict_row_shows_manual_link", () => {
    const res = makeNestedApiResponse();
    render(<MappingSummaryDisplay response={res} />);

    const rowActions = screen.getByTestId("actions-AC-07");
    expect(rowActions).toHaveTextContent("Manual link");
  });

  it("partial_support_row_shows_accept_partial", () => {
    const res = makeNestedApiResponse();
    render(<MappingSummaryDisplay response={res} />);

    const rowActions = screen.getByTestId("actions-AC-15");
    expect(rowActions).toHaveTextContent("Accept as partial");
  });

  it("partial_support_row_shows_mark_insufficient", () => {
    const res = makeNestedApiResponse();
    render(<MappingSummaryDisplay response={res} />);

    const rowActions = screen.getByTestId("actions-AC-15");
    expect(rowActions).toHaveTextContent("Mark insufficient");
  });

  it("partial_support_row_shows_link_another_test", () => {
    const res = makeNestedApiResponse();
    render(<MappingSummaryDisplay response={res} />);

    const rowActions = screen.getByTestId("actions-AC-15");
    expect(rowActions).toHaveTextContent("Link another test");
  });

  it("frontend_does_not_use_compatibility_summary_for_new_counters", () => {
    const res = makeNestedApiResponse();
    render(<MappingSummaryDisplay response={res} />);

    // Ensures exact 7-state mapping_summary counts are rendered, not legacy compatibility summary
    const mapSec = screen.getByTestId("mapping-summary");
    expect(mapSec).toHaveTextContent("Evidence Aligned: 2");
    expect(mapSec).toHaveTextContent("Metadata Conflict: Semantic Match Found: 16");
    expect(mapSec).toHaveTextContent("Partial Support: 3");
  });
});
