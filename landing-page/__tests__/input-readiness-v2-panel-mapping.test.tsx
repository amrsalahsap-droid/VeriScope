/**
 * @jest-environment jsdom
 */

import React from "react";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import "@testing-library/jest-dom";
import { InputReadinessV2Panel } from "@/components/readiness/InputReadinessV2Panel";

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

function makeReadinessResponse(overrides: any = {}) {
  const input5Details = {
    total_acs: 1,
    test_case_count: 1,
    tests_with_external_ac_refs: 0,
    mapping_attempt_count: 1,
    candidate_edge_count: 1,
    user_confirmed_count: 0,
    veriscope_key_verified_count: 0,
    evidence_verified_aligned_count: 0,
    metadata_conflict_semantic_match_count: 1,
    partial_support_count: 0,
    suggested_count: 0,
    no_candidate_count: 0,
    rejected_count: 0,
    confirmed_coverage_percent: 0,
    mapping_discovery_score: 0,
    mapping_discovery_max_score: 15,
    summary_integrity: "PASS",
    ...overrides.input5Details,
  };

  return {
    generation_status: "DRAFT_ONLY",
    can_generate: "DRAFT_ONLY",
    confident_generation: false,
    confidence_score: 75,
    confidence_level: "HIGH",
    confidence_ceiling: "LOW",
    primary_message: "Incomplete readiness assessment.",
    blockers: [],
    warnings: [],
    inputs: [
      { input_id: "INPUT_1", label: "PR Change Package", status: "READY", weight: 10, earned_score: 10, max_score: 10, is_hard_blocker: true, summary: "Ready", details: {}, actions: [] },
      { input_id: "INPUT_2", label: "Business Requirements", status: "READY", weight: 20, earned_score: 20, max_score: 20, is_hard_blocker: true, summary: "Ready", details: {}, actions: [] },
      { input_id: "INPUT_3", label: "Product Behavior Map", status: "READY", weight: 10, earned_score: 10, max_score: 10, is_hard_blocker: false, summary: "Ready", details: {}, actions: [] },
      { input_id: "INPUT_4", label: "Test Case Inventory", status: "READY", weight: 12, earned_score: 12, max_score: 12, is_hard_blocker: true, summary: "Ready", details: {}, actions: [] },
      { input_id: "INPUT_5", label: "AC → Test Mapping", status: "MISSING", weight: 15, earned_score: 0, max_score: 15, is_hard_blocker: true, summary: "Missing mapping", details: input5Details, actions: [] },
      { input_id: "INPUT_6", label: "Current PR Test Results", status: "READY", weight: 15, earned_score: 15, max_score: 15, is_hard_blocker: true, summary: "Ready", details: {}, actions: [] },
      { input_id: "INPUT_7", label: "Test Coverage Mapping", status: "READY", weight: 8, earned_score: 8, max_score: 8, is_hard_blocker: false, summary: "Ready", details: {}, actions: [] },
      { input_id: "INPUT_8", label: "Release Context", status: "MISSING", weight: 3, earned_score: 0, max_score: 3, is_hard_blocker: false, summary: "Missing", details: {}, actions: [] },
      { input_id: "INPUT_9", label: "Environment Support Matrix", status: "MISSING", weight: 3, earned_score: 0, max_score: 3, is_hard_blocker: false, summary: "Missing", details: {}, actions: [] },
      { input_id: "INPUT_10", label: "Quality Gate Profile", status: "MISSING", weight: 2, earned_score: 0, max_score: 2, is_hard_blocker: false, summary: "Missing", details: {}, actions: [] },
      { input_id: "INPUT_11", label: "Known Defects / Accepted Risks", status: "MISSING", weight: 1, earned_score: 0, max_score: 1, is_hard_blocker: false, summary: "Missing", details: {}, actions: [] },
      { input_id: "INPUT_12", label: "Out-of-Scope Declaration", status: "MISSING", weight: 1, earned_score: 0, max_score: 1, is_hard_blocker: false, summary: "Missing", details: {}, actions: [] },
    ],
    next_best_actions: [],
    ...overrides,
  };
}

function makeMappingResponse(overrides: any = {}) {
  return {
    mapping_summary: {
      total_acs: 1,
      user_confirmed: 0,
      veriscope_key_verified: 0,
      evidence_verified_aligned: 0,
      metadata_conflict_semantic_match: 1,
      partial_support: 0,
      suggested: 0,
      no_candidate: 0,
      rejected: 0,
      accepted_gap: 0,
      sum_check: 1,
      is_ac_level_exclusive: true,
      summary_integrity: "PASS",
      ...overrides.mapping_summary,
    },
    summary: {
      confirmed: 0,
      suggested: 0,
      pending_review: 0,
      needs_review: 0,
      unmapped: 0,
      rejected: 0,
      ...overrides.summary,
    },
    execution_summary: {
      total_tests: 1,
      passed: 1,
      failed: 0,
      skipped: 0,
    },
    items: overrides.items || [
      {
        ac_id: "ac-07-uuid",
        stable_ac_key: "ac-07",
        display_ac_ref: "AC-07",
        ac_title: "Metadata conflict AC",
        ac_text: "Semantic match available.",
        requirement_group: "Auth",
        business_flow: "Auth",
        status: "metadata_conflict_semantic_match",
        row_status: "metadata_conflict_semantic_match",
        suggested_tests_count: 1,
        suggested_tests: [
          {
            candidate_id: "cand-semantic-07",
            edge_id: "edge-semantic-07",
            test_case_id: "tc-07",
            stable_test_id: "test-07",
            test_name: "test_semantic_match",
            suite_name: "AuthSuite",
            confidence: 0.88,
            confidence_score: 0.88,
            confidence_label: "high",
            edge_source: "semantic_similarity",
            review_status: "metadata_conflict_semantic_match",
            evidence: ["Semantic match 88%"],
            semantic_best_match_ac_id: "ac-other-uuid",
            semantic_best_match_ac_ref: "AC-OTHER",
            semantic_match_accept_allowed: true,
          },
        ],
      },
    ],
  };
}

describe("InputReadinessV2Panel + MappingReviewPanel integration", () => {
  const fetchMock = jest.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock as any;
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("keeps the mapping workspace open after Accept Semantic Match and refreshes counters", async () => {
    const onReadinessDataChange = jest.fn();

    fetchMock
      // 1. initial readiness
      .mockResolvedValueOnce({
        ok: true,
        json: async () =>
          makeReadinessResponse({
            input5Details: { metadata_conflict_semantic_match_count: 1, confirmed_coverage_percent: 0 },
          }),
      } as Response)
      // 2. initial mappings
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeMappingResponse(),
      } as Response)
      // 3. accept semantic match action
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: "Accepted semantic match" }),
      } as Response)
      // 4. refreshed mappings
      .mockResolvedValueOnce({
        ok: true,
        json: async () =>
          makeMappingResponse({
            mapping_summary: {
              total_acs: 1,
              user_confirmed: 1,
              metadata_conflict_semantic_match: 0,
              sum_check: 1,
              summary_integrity: "PASS",
            },
            items: [
              {
                ac_id: "ac-07-uuid",
                stable_ac_key: "ac-07",
                display_ac_ref: "AC-07",
                ac_title: "Metadata conflict AC",
                ac_text: "Semantic match available.",
                requirement_group: "Auth",
                business_flow: "Auth",
                status: "user_confirmed",
                row_status: "user_confirmed",
                suggested_tests_count: 1,
                suggested_tests: [
                  {
                    candidate_id: "cand-semantic-07",
                    edge_id: "edge-semantic-07",
                    test_case_id: "tc-07",
                    stable_test_id: "test-07",
                    test_name: "test_semantic_match",
                    suite_name: "AuthSuite",
                    confidence: 0.88,
                    confidence_score: 0.88,
                    confidence_label: "high",
                    edge_source: "semantic_similarity",
                    review_status: "user_confirmed",
                    evidence: ["Semantic match 88%"],
                    semantic_best_match_ac_id: "ac-other-uuid",
                    semantic_best_match_ac_ref: "AC-OTHER",
                    semantic_match_accept_allowed: true,
                  },
                ],
              },
            ],
          }),
      } as Response)
      // 5. refreshed readiness
      .mockResolvedValueOnce({
        ok: true,
        json: async () =>
          makeReadinessResponse({
            input5Details: {
              total_acs: 1,
              user_confirmed_count: 1,
              metadata_conflict_semantic_match_count: 0,
              confirmed_coverage_percent: 100,
              mapping_discovery_score: 15,
            },
          }),
      } as Response);

    render(
      <InputReadinessV2Panel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        onReadinessDataChange={onReadinessDataChange}
      />
    );

    // Wait for the Input 5 card and open the mapping workspace.
    await waitFor(() => expect(screen.getByText("AC → Test Mapping")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /Review Mappings/i })).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Review Mappings/i }));
    });

    // Workspace should open with the conflict row visible.
    await waitFor(() =>
      expect(screen.getByText("AC → Test Mapping Conflict Resolution Workspace")).toBeInTheDocument()
    );
    await waitFor(() => expect(screen.getByText("AC-07")).toBeInTheDocument());

    const acceptBtn = await screen.findByRole("button", { name: /Accept Semantic Match/i });
    await act(async () => {
      fireEvent.click(acceptBtn);
    });

    // All expected network calls are made.
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));

    const acceptCalls = fetchMock.mock.calls.filter(
      (c: any[]) =>
        typeof c[0] === "string" &&
        c[0].includes("/api/ac-test-mappings/candidates/cand-semantic-07/accept_semantic_match")
    );
    expect(acceptCalls).toHaveLength(1);

    // The workspace title remains visible, i.e. the panel was not closed.
    expect(screen.getByText("AC → Test Mapping Conflict Resolution Workspace")).toBeInTheDocument();

    // Counters refreshed: readiness emitted twice and the last emission has no conflicts.
    await waitFor(() => expect(onReadinessDataChange).toHaveBeenCalledTimes(2));
    const lastData = onReadinessDataChange.mock.calls[1][0];
    const input5 = lastData.inputs.find((i: any) => i.input_id === "INPUT_5");
    expect(input5.details.metadata_conflict_semantic_match_count).toBe(0);
    expect(input5.details.user_confirmed_count).toBe(1);
  });
});
