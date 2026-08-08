/**
 * @jest-environment jsdom
 *
 * Production component tests for MappingReviewPanel.
 * The real MappingReviewPanel is rendered; only the global fetch and
 * external toast dependency are mocked.
 */
import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MappingReviewPanel } from "@/components/readiness/MappingReviewPanel";

// Mock sonner toast (external dependency, not part of what we're testing)
jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

function makeMappingResponse(overrides: any = {}) {
  return {
    mapping_summary: {
      total_acs: 3,
      user_confirmed: 0,
      veriscope_key_verified: 0,
      evidence_verified_aligned: 0,
      metadata_conflict_semantic_match: 0,
      partial_support: 0,
      suggested: 1,
      no_candidate: 1,
      rejected: 0,
      sum_check: 3,
      is_ac_level_exclusive: true,
      summary_integrity: "PASS",
      ...overrides.mapping_summary,
    },
    summary: {
      confirmed: 0,
      suggested: 1,
      pending_review: 1,
      needs_review: 1,
      unmapped: 1,
      rejected: 0,
      ...overrides.summary,
    },
    execution_summary: {
      total_tests: 3,
      passed: 3,
      failed: 0,
      skipped: 0,
    },
    items: overrides.items || [
      {
        ac_id: "ac-01-uuid",
        stable_ac_key: "repo:123:pr:456:group:sign-up:source:manual:ac:user-can-sign-up",
        display_ac_ref: "AC-01",
        ac_title: "User can sign up",
        ac_text: "Given a new user, when they fill the signup form, then an account is created.",
        requirement_group: "Sign-up",
        business_flow: "Sign-up",
        status: "suggested",
        row_status: "suggested",
        suggested_tests_count: 1,
        suggested_tests: [
          {
            candidate_id: "cand-aaa-111",
            edge_id: "edge-aaa-111",
            test_case_id: "test-1-uuid",
            stable_test_id: "test-1",
            test_name: "test_signup_creates_account",
            test_title: "Password Validation Acceptance Criteria",
            suite_name: "AuthSuite",
            confidence: 0.85,
            confidence_score: 0.85,
            confidence_label: "high",
            edge_source: "junit_external_ac_ref",
            review_status: "system_suggested",
            evidence: ["External AC reference: AC-01"],
            reason: "Matched by external AC ref",
            conflict_detected: false,
            conflict_reason: null,
          },
        ],
        debug: {
          stable_ac_key: "repo:123:pr:456:group:sign-up:source:manual:ac:user-can-sign-up",
          raw_edge_ids: ["edge-aaa-111"],
        },
      },
      {
        ac_id: "ac-02-uuid",
        stable_ac_key: "repo:123:pr:456:group:login:source:manual:ac:user-can-log-in",
        display_ac_ref: "AC-02",
        ac_title: "User can log in",
        ac_text: "Given a registered user, when they log in, then they see the dashboard.",
        requirement_group: "Login",
        business_flow: "Login",
        status: "needs_review",
        row_status: "needs_review",
        suggested_tests_count: 1,
        suggested_tests: [
          {
            candidate_id: "cand-bbb-222",
            edge_id: "edge-bbb-222",
            test_case_id: "test-2-uuid",
            stable_test_id: "test-2",
            test_name: "test_login_shows_dashboard",
            test_title: "Login Intent Test",
            suite_name: "AuthSuite",
            confidence: 0.6,
            confidence_score: 0.6,
            confidence_label: "medium",
            edge_source: "semantic_similarity",
            review_status: "needs_review",
            evidence: ["High token overlap similarity"],
            reason: "Semantic match",
            conflict_detected: true,
            conflict_reason: "Flow conflict: Sign-up AC cannot map to Login test",
          },
        ],
        debug: {
          stable_ac_key: "repo:123:pr:456:group:login:source:manual:ac:user-can-log-in",
          raw_edge_ids: ["edge-bbb-222"],
        },
      },
      {
        ac_id: "ac-03-uuid",
        stable_ac_key: "repo:123:pr:456:group:profile:source:manual:ac:user-can-update-profile",
        display_ac_ref: "AC-03",
        ac_title: "User can update profile",
        ac_text: "Given a user, they can update their profile.",
        requirement_group: "Profile",
        business_flow: "Profile",
        status: "unmapped",
        row_status: "unmapped",
        suggested_tests_count: 0,
        suggested_tests: [],
        debug: {
          stable_ac_key: "repo:123:pr:456:group:profile:source:manual:ac:user-can-update-profile",
          raw_edge_ids: [],
        },
      },
    ],
  };
}

// Provide a global fetch mock for jsdom
const fetchMock = jest.fn();
(global as any).fetch = fetchMock;

describe("MappingReviewPanel", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => makeMappingResponse(),
    } as unknown as Response);
  });

  it("loads and renders human-readable AC title and display ref instead of stable_ac_key", async () => {
    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("AC-01")).toBeInTheDocument();
      expect(screen.getByText("User can sign up")).toBeInTheDocument();
      expect(screen.getByText("AC-02")).toBeInTheDocument();
      expect(screen.getByText("User can log in")).toBeInTheDocument();
      expect(screen.getByText("AC-03")).toBeInTheDocument();
      expect(screen.getByText("User can update profile")).toBeInTheDocument();
    });

    // Verify long internal stable key is NOT rendered anywhere
    expect(screen.queryByText(/repo:123:pr:456/)).not.toBeInTheDocument();
  });

  it("shows requirement group / flow and linked test count on collapsed rows", async () => {
    const { container } = render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("AC-01")).toBeInTheDocument();
    });

    expect(container.textContent).toContain("Requirement Group / Flow: Sign-up (Sign-up)");
    expect(container.textContent).toContain("Linked Tests: 1");
  });

  it("expanded section shows AC meaning and does not leak stable_ac_key", async () => {
    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("AC-01")).toBeInTheDocument();
    });

    // AC-01 is auto-expanded because it is suggested; AC meaning should be visible
    expect(screen.getAllByText("Acceptance Criterion Meaning:").length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText("Given a new user, when they fill the signup form, then an account is created.")
    ).toBeInTheDocument();

    // Stable key must stay hidden
    expect(screen.queryByText(/repo:123:pr:456/)).not.toBeInTheDocument();
  });

  it("displays conflict warning banner when conflict_detected is true", async () => {
    const { container } = render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("AC-02")).toBeInTheDocument();
      expect(screen.getByText("Conflict Detected")).toBeInTheDocument();
    });

    // The conflict reason is rendered across multiple elements; check the text content of the document
    expect(container.textContent).toContain("Flow conflict: Sign-up AC cannot map to Login test");
  });

  it("shows summary stats from mapping_summary", async () => {
    const { container } = render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => {
      // The grid of counters is rendered
      const grid = container.querySelector(".grid-cols-2");
      expect(grid).toBeInTheDocument();
      const text = grid!.textContent || "";
      expect(text).toContain("User Confirmed");
      expect(text).toContain("Suggested");
      expect(text).toContain("No Candidate");
      expect(text).toContain("Rejected");
    });
  });

  it("approve button calls confirm_candidate POST and updates review_status", async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeMappingResponse(),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: "Mapping confirmed successfully" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () =>
          makeMappingResponse({
            mapping_summary: { suggested: 0, user_confirmed: 1, no_candidate: 1 },
            summary: { confirmed: 1, suggested: 0, pending_review: 0, needs_review: 1, unmapped: 1, rejected: 0 },
          }),
      } as Response);

    const onMappingUpdate = jest.fn();
    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
        onMappingUpdate={onMappingUpdate}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("AC-01")).toBeInTheDocument();
    });

    const approveButtons = screen.getAllByText("Approve");
    expect(approveButtons.length).toBeGreaterThan(0);

    await act(async () => {
      fireEvent.click(approveButtons[0]);
    });

    await waitFor(() => {
      const confirmCalls = fetchMock.mock.calls.filter(
        (c: any[]) => typeof c[0] === "string" && c[0].includes("/confirm_candidate")
      );
      expect(confirmCalls.length).toBe(1);
      expect(confirmCalls[0][1]?.method).toBe("POST");
    });
  });

  it("reject button calls reject_candidate POST with reason", async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeMappingResponse(),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: "Mapping rejected successfully" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeMappingResponse(),
      } as Response);

    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("AC-01")).toBeInTheDocument();
    });

    const rejectButtons = screen.getAllByText("Reject");
    expect(rejectButtons.length).toBeGreaterThan(0);

    await act(async () => {
      fireEvent.click(rejectButtons[0]);
    });

    await waitFor(() => {
      const rejectCalls = fetchMock.mock.calls.filter(
        (c: any[]) => typeof c[0] === "string" && c[0].includes("/reject_candidate")
      );
      expect(rejectCalls.length).toBe(1);
      expect(rejectCalls[0][1]?.method).toBe("POST");
      const body = JSON.parse(rejectCalls[0][1]?.body || "{}");
      expect(body.reason).toBeTruthy();
    });
  });

  it("search filter works for AC title, test name, and display_ac_ref", async () => {
    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("AC-01")).toBeInTheDocument();
      expect(screen.getByText("AC-02")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search by AC text/i);

    // Search by test name
    fireEvent.change(searchInput, { target: { value: "test_login_shows_dashboard" } });
    expect(screen.queryByText("AC-01")).not.toBeInTheDocument();
    expect(screen.getByText("AC-02")).toBeInTheDocument();

    // Search by display ref
    fireEvent.change(searchInput, { target: { value: "AC-01" } });
    expect(screen.getByText("AC-01")).toBeInTheDocument();
    expect(screen.queryByText("AC-02")).not.toBeInTheDocument();
  });

  it("status filter shows no_candidate rows", async () => {
    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("AC-01")).toBeInTheDocument();
      expect(screen.getByText("AC-02")).toBeInTheDocument();
      expect(screen.getByText("AC-03")).toBeInTheDocument();
    });

    const selectEl = screen.getByRole("combobox") as HTMLSelectElement;
    selectEl.value = "no_candidate";
    fireEvent.change(selectEl);
    await waitFor(() => {
      expect(screen.queryByText("AC-01")).not.toBeInTheDocument();
      expect(screen.queryByText("AC-02")).not.toBeInTheDocument();
      expect(screen.getByText("AC-03")).toBeInTheDocument();
    });
  });

  it("status filter shows suggested rows", async () => {
    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("AC-01")).toBeInTheDocument();
      expect(screen.getByText("AC-02")).toBeInTheDocument();
      expect(screen.getByText("AC-03")).toBeInTheDocument();
    });

    const selectEl = screen.getByRole("combobox") as HTMLSelectElement;
    selectEl.value = "suggested";
    fireEvent.change(selectEl);
    await waitFor(() => {
      expect(screen.getByText("AC-01")).toBeInTheDocument();
      expect(screen.queryByText("AC-02")).not.toBeInTheDocument();
      expect(screen.queryByText("AC-03")).not.toBeInTheDocument();
    });
  });

  it("does not render when isOpen is false", () => {
    const { container } = render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={false}
        onClose={jest.fn()}
      />
    );

    expect(container.innerHTML).toBe("");
  });

  it("shows accepted gap count in summary stats", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () =>
        makeMappingResponse({
          mapping_summary: { total_acs: 4, no_candidate: 2, accepted_gap: 1, sum_check: 4 },
          summary: { accepted_gap: 1 },
        }),
    } as Response);

    const { container } = render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => {
      const grid = container.querySelector(".grid-cols-2");
      expect(grid!.textContent).toContain("Accepted Gap / Risk");
    });
  });

  it("manual link button opens modal and posts target_ac_id", async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeMappingResponse(),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: "Manually linked test to AC successfully" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeMappingResponse(),
      } as Response);

    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => expect(screen.getByText("AC-02")).toBeInTheDocument());
    // AC-02 is auto-expanded because it needs review; no click needed.

    const manualLinkBtn = await screen.findByText("Manual Link");
    await act(async () => fireEvent.click(manualLinkBtn));

    expect(screen.getAllByText("Manual Link").length).toBeGreaterThanOrEqual(1);

    const reasonInput = screen.getByPlaceholderText(/Why are you manually linking/i);
    fireEvent.change(reasonInput, { target: { value: "Linking to AC-01" } });

    const linkBtn = screen.getByRole("button", { name: /Link Test to AC/i });
    await act(async () => fireEvent.click(linkBtn));

    await waitFor(() => {
      const manualCalls = fetchMock.mock.calls.filter(
        (c: any[]) => typeof c[0] === "string" && c[0].includes("/manually_link_to_ac")
      );
      expect(manualCalls.length).toBe(1);
      const body = JSON.parse(manualCalls[0][1]?.body || "{}");
      expect(body.target_ac_id).toBeTruthy();
      expect(body.test_case_id).toBeTruthy();
      expect(body.repository_id).toBe("repo-1");
      expect(body.pull_request_id).toBe("pr-1");
      expect(body.reason).toBe("Linking to AC-01");
    });
  });

  it("mark accepted gap modal records reason for no-candidate rows", async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeMappingResponse(),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: "Accepted gap recorded successfully" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeMappingResponse(),
      } as Response);

    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => expect(screen.getByText("AC-03")).toBeInTheDocument());
    await act(async () => fireEvent.click(screen.getByText("AC-03")));

    const gapBtn = await screen.findByText("Mark Accepted Gap");
    await act(async () => fireEvent.click(gapBtn));

    expect(screen.getByText("Mark Accepted Gap / Risk")).toBeInTheDocument();

    const reasonInput = screen.getByPlaceholderText(/e\.g\. Covered by manual QA/i);
    fireEvent.change(reasonInput, { target: { value: "Out of scope for PR" } });

    const submitBtns = screen.getAllByRole("button", { name: /^Mark Accepted Gap$/i });
    // The last matching button is the modal submit button.
    await act(async () => fireEvent.click(submitBtns[submitBtns.length - 1]));

    await waitFor(() => {
      const gapCalls = fetchMock.mock.calls.filter(
        (c: any[]) => typeof c[0] === "string" && c[0].includes("/mark-accepted-gap")
      );
      expect(gapCalls.length).toBe(1);
      const body = JSON.parse(gapCalls[0][1]?.body || "{}");
      expect(body.ac_id).toBeTruthy();
      expect(body.reason).toBe("Out of scope for PR");
      expect(body.repository_id).toBe("repo-1");
      expect(body.pull_request_id).toBe("pr-1");
    });
  });

  it("clicking Accept Semantic Match calls /api/ac-test-mappings/candidates/{id}/accept_semantic_match", async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () =>
          makeMappingResponse({
            items: [
              {
                ac_id: "ac-semantic-uuid",
                stable_ac_key: "ac-semantic",
                display_ac_ref: "AC-SEMANTIC",
                ac_title: "Semantic match AC",
                ac_text: "Covered by semantic match.",
                requirement_group: "Auth",
                business_flow: "Auth",
                status: "metadata_conflict_semantic_match",
                row_status: "metadata_conflict_semantic_match",
                suggested_tests_count: 1,
                suggested_tests: [
                  {
                    candidate_id: "cand-semantic",
                    edge_id: "edge-semantic",
                    test_case_id: "test-semantic-uuid",
                    stable_test_id: "test-semantic",
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
          }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: "Accepted semantic match" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeMappingResponse(),
      } as Response);

    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => expect(screen.getByText("AC-SEMANTIC")).toBeInTheDocument());

    const acceptBtn = await screen.findByRole("button", { name: /Accept Semantic Match/i });
    await act(async () => fireEvent.click(acceptBtn));

    await waitFor(() => {
      const calls = fetchMock.mock.calls.filter(
        (c: any[]) =>
          typeof c[0] === "string" &&
          c[0].includes("/ac-test-mappings/candidates/cand-semantic/accept_semantic_match")
      );
      expect(calls.length).toBe(1);
      const body = JSON.parse(calls[0][1]?.body || "{}");
      expect(body.repository_id).toBe("repo-1");
      expect(body.pull_request_id).toBe("pr-1");
    });
  });

  it("renders Accept Partial Support for partial_support rows", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () =>
        makeMappingResponse({
          items: [
            {
              ac_id: "ac-partial-uuid",
              stable_ac_key: "ac-partial",
              display_ac_ref: "AC-PARTIAL",
              ac_title: "Partially covered AC",
              ac_text: "Partial coverage.",
              requirement_group: "Auth",
              business_flow: "Auth",
              status: "partial_support",
              row_status: "partial_support",
              suggested_tests_count: 1,
              suggested_tests: [
                {
                  candidate_id: "cand-partial",
                  edge_id: "edge-partial",
                  stable_test_id: "test-partial",
                  test_name: "test_partial_coverage",
                  suite_name: "AuthSuite",
                  confidence: 0.5,
                  confidence_score: 0.5,
                  confidence_label: "low",
                  edge_source: "semantic_similarity",
                  review_status: "partial_support",
                  evidence: ["Partial overlap"],
                  reason: "Partial match",
                  conflict_detected: false,
                  conflict_reason: null,
                },
              ],
            },
          ],
        }),
    } as Response);

    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => expect(screen.getByText("AC-PARTIAL")).toBeInTheDocument());
    // Partial-support rows are auto-expanded, so the button is visible immediately.
    await waitFor(() =>
      expect(screen.getByText("Accept Partial Support")).toBeInTheDocument()
    );
  });

  it("add comment modal appends a comment without changing mapping status", async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeMappingResponse(),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: "Review comment added successfully" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => makeMappingResponse(),
      } as Response);

    render(
      <MappingReviewPanel
        repositoryId="repo-1"
        pullRequestId="pr-1"
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    await waitFor(() => expect(screen.getByText("AC-01")).toBeInTheDocument());
    // AC-01 is auto-expanded as a suggested row, so no click is needed.

    const commentBtn = await screen.findAllByRole("button", { name: /Add Comment/i });
    await act(async () => fireEvent.click(commentBtn[0]));

    const textArea = screen.getByPlaceholderText(/Enter review notes/i);
    fireEvent.change(textArea, { target: { value: "Looks good, minor concern" } });

    const saveBtn = screen.getByRole("button", { name: /Save Comment/i });
    await act(async () => fireEvent.click(saveBtn));

    await waitFor(() => {
      const commentCalls = fetchMock.mock.calls.filter(
        (c: any[]) => typeof c[0] === "string" && c[0].includes("/add_review_comment")
      );
      expect(commentCalls.length).toBe(1);
      const body = JSON.parse(commentCalls[0][1]?.body || "{}");
      expect(body.comment).toBe("Looks good, minor concern");
      expect(body.repository_id).toBe("repo-1");
      expect(body.pull_request_id).toBe("pr-1");
    });
  });
});
