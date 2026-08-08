import { normalizePRPackage } from "@/lib/adapters/prPackageAdapter";

describe("PR package changed-file evidence", () => {
  const pullRequest = {
    id: "pr-1",
    number: 42,
    title: "Generic change",
    source_branch: "feature/change",
    target_branch: "main",
    head_commit_sha: "abcdef0123456789",
    changed_files_count: 2,
  };

  it("is READY when a head SHA and usable provider paths are available", () => {
    const packageView = normalizePRPackage(pullRequest, {
      inputs: [{
        input_id: "INPUT_1",
        details: {
          changed_files_count: 2,
          changed_file_paths_available: true,
          changed_files_source: "github_api",
          evidence_successful: true,
          changed_files: [{ path: "src/feature.ts", status: "modified", additions: 3, deletions: 1 }],
        },
      }],
    });

    expect(packageView.status).toBe("READY");
    expect(packageView.changedFilePathsAvailable).toBe(true);
    expect(packageView.evidenceSuccessful).toBe(true);
    expect(packageView.changedFiles).toHaveLength(1);
  });

  it("is PARTIAL when the provider reports only a count without paths", () => {
    const packageView = normalizePRPackage(pullRequest, {
      inputs: [{
        input_id: "INPUT_1",
        details: {
          changed_files_count: 2,
          changed_file_paths_available: false,
          changed_files: [],
          evidence_successful: false,
          evidence_error: "Provider timed out",
        },
      }],
    });

    expect(packageView.status).toBe("PARTIAL");
    expect(packageView.warnings).toContain("CHANGED_FILE_PATHS_UNAVAILABLE");
    expect(packageView.evidenceSuccessful).toBe(false);
  });

  it("keeps cached paths usable and identifies their provenance", () => {
    const packageView = normalizePRPackage(pullRequest, {
      inputs: [{
        input_id: "INPUT_1",
        details: {
          changed_files_count: 2,
          changed_file_paths_available: true,
          changed_files_source: "cached_pr_package",
          evidence_successful: true,
          changed_files: [{ path: "src/cached.ts", status: "added", additions: 4, deletions: 0 }],
        },
      }],
    });

    expect(packageView.status).toBe("READY");
    expect(packageView.changedFilesSource).toBe("cached_pr_package");
    expect(packageView.warnings).toContain("CHANGED_FILES_FROM_CACHE");
  });
});
