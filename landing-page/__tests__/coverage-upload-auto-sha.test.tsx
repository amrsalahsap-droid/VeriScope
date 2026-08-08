import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CoverageUploadPage from "@/app/app/repositories/[repositoryId]/coverage/page";

// Mock the Next.js router
jest.mock("next/navigation", () => ({
  useParams: jest.fn(() => ({ repositoryId: "repo-123" })),
  useSearchParams: jest.fn(() => new URLSearchParams()),
  useRouter: jest.fn(() => ({ push: jest.fn() })),
}));

// Mock fetch
global.fetch = jest.fn() as jest.MockedFunction<typeof fetch>;

function mockFetchResponse(data: any, ok = true) {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok,
    json: async () => data,
  } as Response);
}

describe("Coverage Upload — Auto PR Head SHA Attachment", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows PR head SHA as read-only when PR context is loaded", async () => {
    const prHeadSha = "F7ff6d2068268c4a0b74d80c4ade238e1fc47d72";
    mockFetchResponse({
      pull_requests: [
        { id: "pr-1", number: 42, head_commit_sha: prHeadSha, source_branch: "feature/auth" },
      ],
    });

    render(<CoverageUploadPage params={Promise.resolve({ repositoryId: "repo-123" })} searchParams={Promise.resolve({})} />);

    await waitFor(() => {
      expect(screen.getByText(/PR Context/i)).toBeInTheDocument();
    });

    expect(screen.getByText(prHeadSha)).toBeInTheDocument();
    expect(screen.getByText("Coverage will be attached to this PR head SHA automatically")).toBeInTheDocument();
  });

  it("hides manual SHA input by default when PR is selected", async () => {
    mockFetchResponse({
      pull_requests: [
        { id: "pr-1", number: 42, head_commit_sha: "abc123", source_branch: "feature" },
      ],
    });

    render(<CoverageUploadPage params={Promise.resolve({ repositoryId: "repo-123" })} searchParams={Promise.resolve({})} />);

    await waitFor(() => {
      expect(screen.getByText(/PR Context/i)).toBeInTheDocument();
    });

    // Manual SHA input should not be visible by default
    expect(screen.queryByPlaceholderText(/e.g. 5fa7ab81/i)).not.toBeInTheDocument();
  });

  it("shows manual SHA override when Advanced options is toggled", async () => {
    mockFetchResponse({
      pull_requests: [
        { id: "pr-1", number: 42, head_commit_sha: "abc123", source_branch: "feature" },
      ],
    });

    render(<CoverageUploadPage params={Promise.resolve({ repositoryId: "repo-123" })} searchParams={Promise.resolve({})} />);

    await waitFor(() => {
      expect(screen.getByText(/PR Context/i)).toBeInTheDocument();
    });

    const advancedButton = screen.getByText(/Advanced options/i);
    fireEvent.click(advancedButton);

    expect(screen.getByPlaceholderText(/e.g. 5fa7ab81/i)).toBeInTheDocument();
    expect(screen.getByText(/Commit SHA override/i)).toBeInTheDocument();
  });

  it("sends pull_request_id in upload request when PR is selected", async () => {
    mockFetchResponse({
      pull_requests: [
        { id: "pr-1", number: 42, head_commit_sha: "abc123", source_branch: "feature" },
      ],
    });

    mockFetchResponse({
      coverage_report_id: "report-1",
      commit_sha: "abc123",
      current_pr_head_sha: "abc123",
      commit_sha_source: "AUTO_FROM_SELECTED_PR",
      sha_mismatch: false,
      is_current: true,
      overall_coverage_pct: 75.0,
      files_total: 10,
      changed_files_total: 5,
      changed_files_with_coverage: 5,
      changed_files_without_coverage: 0,
      file_to_test_link_count: 8,
      confidence_score: "HIGH",
      current_pr_coverage_confidence: "HIGH",
      repository_readiness: { readiness_state: "READY", next_action: "Generate" },
    });

    render(<CoverageUploadPage params={Promise.resolve({ repositoryId: "repo-123" })} searchParams={Promise.resolve({})} />);

    await waitFor(() => {
      expect(screen.getByText(/PR Context/i)).toBeInTheDocument();
    });

    // Simulate file selection and upload
    const fileInput = screen.getByLabelText(/upload coverage/i);
    const file = new File(["SF:app.ts\nLF:10\nLH:8\nend_of_record"], "coverage.info", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    const uploadButton = screen.getByText(/Upload/i);
    fireEvent.click(uploadButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/repositories/repo-123/coverage/upload"),
        expect.objectContaining({
          method: "POST",
        })
      );
    });

    const uploadCall = (global.fetch as jest.Mock).mock.calls.find((call) =>
      call[0].toString().includes("/coverage/upload")
    );
    const formData = uploadCall?.[1]?.body as FormData;

    expect(formData?.get("pull_request_id")).toBe("pr-1");
    expect(formData?.get("commit_sha")).toBeNull(); // Should not send commit_sha when auto
  });

  it("sends manual commit_sha when Advanced override is used", async () => {
    mockFetchResponse({
      pull_requests: [
        { id: "pr-1", number: 42, head_commit_sha: "abc123", source_branch: "feature" },
      ],
    });

    mockFetchResponse({
      coverage_report_id: "report-1",
      commit_sha: "def456",
      current_pr_head_sha: "abc123",
      commit_sha_source: "MANUAL",
      sha_mismatch: true,
      is_current: false,
      overall_coverage_pct: 75.0,
      files_total: 10,
      changed_files_total: 5,
      changed_files_with_coverage: 5,
      changed_files_without_coverage: 0,
      file_to_test_link_count: 8,
      confidence_score: "HIGH",
      current_pr_coverage_confidence: "NONE",
      repository_readiness: { readiness_state: "READY", next_action: "Generate" },
    });

    render(<CoverageUploadPage params={Promise.resolve({ repositoryId: "repo-123" })} searchParams={Promise.resolve({})} />);

    await waitFor(() => {
      expect(screen.getByText(/PR Context/i)).toBeInTheDocument();
    });

    // Open advanced options
    const advancedButton = screen.getByText(/Advanced options/i);
    fireEvent.click(advancedButton);

    // Enter manual SHA
    const shaInput = screen.getByPlaceholderText(/e.g. 5fa7ab81/i);
    fireEvent.change(shaInput, { target: { value: "def456" } });

    // Simulate file selection and upload
    const fileInput = screen.getByLabelText(/upload coverage/i);
    const file = new File(["SF:app.ts\nLF:10\nLH:8\nend_of_record"], "coverage.info", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    const uploadButton = screen.getByText(/Upload/i);
    fireEvent.click(uploadButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/repositories/repo-123/coverage/upload"),
        expect.objectContaining({
          method: "POST",
        })
      );
    });

    const uploadCall = (global.fetch as jest.Mock).mock.calls.find((call) =>
      call[0].toString().includes("/coverage/upload")
    );
    const formData = uploadCall?.[1]?.body as FormData;

    expect(formData?.get("pull_request_id")).toBe("pr-1");
    expect(formData?.get("commit_sha")).toBe("def456");
  });

  it("shows SHA mismatch warning when manual override differs from PR head SHA", async () => {
    mockFetchResponse({
      pull_requests: [
        { id: "pr-1", number: 42, head_commit_sha: "abc123", source_branch: "feature" },
      ],
    });

    render(<CoverageUploadPage params={Promise.resolve({ repositoryId: "repo-123" })} searchParams={Promise.resolve({})} />);

    await waitFor(() => {
      expect(screen.getByText(/PR Context/i)).toBeInTheDocument();
    });

    const advancedButton = screen.getByText(/Advanced options/i);
    fireEvent.click(advancedButton);

    const shaInput = screen.getByPlaceholderText(/e.g. 5fa7ab81/i);
    fireEvent.change(shaInput, { target: { value: "wrong-sha" } });

    expect(screen.getByText(/overriding the selected PR head SHA/i)).toBeInTheDocument();
    expect(screen.getByText(/coverage will be marked Historical Only/i)).toBeInTheDocument();
  });

  it("displays PR SHA context in upload success response", async () => {
    mockFetchResponse({
      pull_requests: [
        { id: "pr-1", number: 42, head_commit_sha: "abc123", source_branch: "feature" },
      ],
    });

    mockFetchResponse({
      coverage_report_id: "report-1",
      commit_sha: "abc123",
      current_pr_head_sha: "abc123",
      commit_sha_source: "AUTO_FROM_SELECTED_PR",
      sha_mismatch: false,
      is_current: true,
      overall_coverage_pct: 75.0,
      files_total: 10,
      changed_files_total: 5,
      changed_files_with_coverage: 5,
      changed_files_without_coverage: 0,
      file_to_test_link_count: 8,
      confidence_score: "HIGH",
      current_pr_coverage_confidence: "HIGH",
      repository_readiness: { readiness_state: "READY", next_action: "Generate" },
    });

    render(<CoverageUploadPage params={Promise.resolve({ repositoryId: "repo-123" })} searchParams={Promise.resolve({})} />);

    await waitFor(() => {
      expect(screen.getByText(/PR Context/i)).toBeInTheDocument();
    });

    const fileInput = screen.getByLabelText(/upload coverage/i);
    const file = new File(["SF:app.ts\nLF:10\nLH:8\nend_of_record"], "coverage.info", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    const uploadButton = screen.getByText(/Upload/i);
    fireEvent.click(uploadButton);

    await waitFor(() => {
      expect(screen.getByText(/Auto from selected PR/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Yes/i)).toBeInTheDocument(); // Is Current
    expect(screen.getByText(/No/i)).toBeInTheDocument(); // SHA Mismatch
    expect(screen.getByText("5 / 5")).toBeInTheDocument(); // Changed Files Covered
  });
});
