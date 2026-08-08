import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { PRPackageSummaryCard } from "@/components/pr-package-readiness";

describe("PR package changed-file evidence UI", () => {
  it("does not present a count-only PR package as ready", () => {
    render(
      <PRPackageSummaryCard
        prPackage={{
          status: "PARTIAL",
          prNumber: 5,
          title: "Provider-neutral update",
          headSha: "abcdef012345",
          headShaShort: "abcdef0",
          changedFilesCount: 6,
          changedFiles: [],
          changedFilePathsAvailable: false,
          evidenceSuccessful: false,
          evidenceError: "File details fetch failed",
          snapshotStatus: "MISSING",
          blockers: [],
          warnings: ["CHANGED_FILE_PATHS_UNAVAILABLE"],
          canGenerateDraftPlan: true,
          canGenerateConfidentPlan: false,
        }}
      />,
    );

    expect(screen.getByText("PARTIAL")).toBeInTheDocument();
    expect(screen.queryByText("READY")).not.toBeInTheDocument();
    expect(screen.getByText("Changed file details unavailable. PR impact analysis may be incomplete.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /show changed files/i }));
    expect(screen.getByText(/Provider reported 6 changed file/i)).toBeInTheDocument();
    expect(screen.getAllByText("File details fetch failed")).toHaveLength(2);
  });

  it("shows cached provenance when stored paths remain usable", () => {
    render(
      <PRPackageSummaryCard
        prPackage={{
          status: "READY",
          changedFilesCount: 1,
          changedFiles: [{ file_path: "src/service.ts", status: "modified", additions: 1, deletions: 0 }],
          changedFilePathsAvailable: true,
          changedFilesSource: "cached_pr_package",
          evidenceSuccessful: true,
          snapshotStatus: "CURRENT",
          blockers: [],
          warnings: ["CHANGED_FILES_FROM_CACHE"],
          canGenerateDraftPlan: true,
          canGenerateConfidentPlan: true,
        }}
      />,
    );

    expect(screen.getByText("Changed files loaded from cached PR package.")).toBeInTheDocument();
  });
});
