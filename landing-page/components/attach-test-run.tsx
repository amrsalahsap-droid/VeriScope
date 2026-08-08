"use client";

import { useState } from "react";
import { Play, AlertTriangle, Clock, CheckCircle2, X, Upload, FileText, ArrowRight, Archive } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface TestRun {
  id: string;
  run_name?: string;
  commit_sha: string;
  branch?: string;
  created_at: string;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  skipped_tests: number;
  is_current_pr?: boolean;
}

interface AttachTestRunProps {
  recommendationRunId: string;
  repositoryId: string;
  pullRequestId?: string;
  currentCommitSha?: string;
  currentBranch?: string;
  onAttached?: () => void;
}

export function AttachTestRun({
  recommendationRunId,
  repositoryId,
  pullRequestId,
  currentCommitSha,
  currentBranch,
  onAttached,
}: AttachTestRunProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [testRuns, setTestRuns] = useState<TestRun[]>([]);
  const [selectedTestRun, setSelectedTestRun] = useState<TestRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [attaching, setAttaching] = useState(false);
  const [showMismatchWarning, setShowMismatchWarning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [importMode, setImportMode] = useState<"INVENTORY_ONLY" | "CURRENT_PR_EXECUTION_RESULTS" | "BOTH">("INVENTORY_ONLY");

  const fetchTestRuns = async () => {
    setLoading(true);
    try {
      const url = pullRequestId
        ? `/api/repositories/${repositoryId}/test-runs?pull_request_id=${pullRequestId}&include_historical=true`
        : `/api/repositories/${repositoryId}/test-runs?limit=10`;
      const response = await fetch(url);
      if (!response.ok) throw new Error("Failed to fetch test runs");
      const data = await response.json();
      setTestRuns(data.test_runs || []);
    } catch (error) {
      toast.error("Failed to load test runs", { description: "Please try again later." });
    } finally {
      setLoading(false);
    }
  };

  const handleOpen = () => {
    setIsOpen(true);
    if (testRuns.length === 0) {
      fetchTestRuns();
    }
  };

  const handleSelectTestRun = (testRun: TestRun) => {
    // Check for commit/branch mismatch
    if (currentCommitSha && testRun.commit_sha !== currentCommitSha) {
      setShowMismatchWarning(true);
    }
    setSelectedTestRun(testRun);
  };

  const handleAttach = async () => {
    if (!selectedTestRun) return;

    setAttaching(true);
    try {
      const response = await fetch(`/api/recommendations/${recommendationRunId}/attach-test-run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ test_run_id: selectedTestRun.id }),
      });

      if (!response.ok) throw new Error("Failed to attach test run");

      const data = await response.json();
      toast.success("Test run attached", {
        description: `Matched ${data.results.matched_tests} tests, ${data.results.extra_executed} extra tests`,
      });

      setIsOpen(false);
      setSelectedTestRun(null);
      setShowMismatchWarning(false);
      onAttached?.();
    } catch (error) {
      toast.error("Failed to attach test run", { description: "Please try again later." });
    } finally {
      setAttaching(false);
    }
  };

  const handleUpload = async (file: File) => {
    // Validate requirements for CURRENT_PR_EXECUTION_RESULTS or BOTH modes
    if (importMode === "CURRENT_PR_EXECUTION_RESULTS" || importMode === "BOTH") {
      if (!pullRequestId) {
        toast.error("Cannot upload", { description: "Pull request ID is required for this import mode" });
        return;
      }
      if (!currentCommitSha) {
        toast.error("Cannot upload", { description: "Commit SHA is required for this import mode" });
        return;
      }
    }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("import_mode", importMode);
    
    if (currentCommitSha) formData.append("commit_sha", currentCommitSha);
    if (currentBranch) formData.append("branch", currentBranch);
    if (pullRequestId) formData.append("pull_request_id", pullRequestId);

    try {
      const response = await fetch(
        `/api/test-results/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to upload test run");
      }

      const data = await response.json();
      
      if (importMode === "INVENTORY_ONLY") {
        toast.success("Test inventory updated", {
          description: `${data.correlation_id ? `ID: ${data.correlation_id.slice(0, 8)}` : "Inventory updated successfully"}`,
        });
      } else {
        toast.success("Test run uploaded", {
          description: `${data.total_tests} tests processed (${data.passed_tests} passed)`,
        });
      }

      // Refresh test runs list if not INVENTORY_ONLY
      if (importMode !== "INVENTORY_ONLY") {
        await fetchTestRuns();
      }
      setShowUpload(false);
    } catch (error) {
      toast.error("Failed to upload test run", { description: error instanceof Error ? error.message : "Please try again later." });
    } finally {
      setUploading(false);
    }
  };

  const formatRelative = (iso: string) => {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    const hrs = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    if (hrs < 24) return `${hrs}h ago`;
    return `${days}d ago`;
  };

  const isStale = (testRun: TestRun) => {
    const diff = Date.now() - new Date(testRun.created_at).getTime();
    return diff > 86400000 * 7; // More than 7 days
  };

  if (!isOpen) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={handleOpen}
        className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700"
      >
        <Play className="w-3.5 h-3.5 mr-1.5" />
        Attach Current PR Test Results
      </Button>
    );
  }

  return (
    <div className="bg-zinc-950/40 border border-zinc-800/60 rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-zinc-200">Attach Current PR Test Results</h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsOpen(false)}
          className="text-zinc-500 hover:text-white"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      {showUpload ? (
        <div className="space-y-3">
          <div className="space-y-2">
            <label className="text-xs text-zinc-400 font-medium">Import Mode</label>
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => setImportMode("INVENTORY_ONLY")}
                className={`px-3 py-2 rounded-lg text-xs border transition-colors ${
                  importMode === "INVENTORY_ONLY"
                    ? "bg-blue-950/30 border-blue-500/30 text-blue-300"
                    : "bg-zinc-900/40 border-zinc-800/60 text-zinc-400 hover:bg-zinc-900/60"
                }`}
              >
                <div className="font-medium mb-1">Inventory Only</div>
                <div className="text-[9px] text-zinc-500">Update test inventory</div>
              </button>
              <button
                onClick={() => setImportMode("CURRENT_PR_EXECUTION_RESULTS")}
                className={`px-3 py-2 rounded-lg text-xs border transition-colors ${
                  importMode === "CURRENT_PR_EXECUTION_RESULTS"
                    ? "bg-blue-950/30 border-blue-500/30 text-blue-300"
                    : "bg-zinc-900/40 border-zinc-800/60 text-zinc-400 hover:bg-zinc-900/60"
                }`}
              >
                <div className="font-medium mb-1">PR Results</div>
                <div className="text-[9px] text-zinc-500">Current PR execution</div>
              </button>
              <button
                onClick={() => setImportMode("BOTH")}
                className={`px-3 py-2 rounded-lg text-xs border transition-colors ${
                  importMode === "BOTH"
                    ? "bg-blue-950/30 border-blue-500/30 text-blue-300"
                    : "bg-zinc-900/40 border-zinc-800/60 text-zinc-400 hover:bg-zinc-900/60"
                }`}
              >
                <div className="font-medium mb-1">Both</div>
                <div className="text-[9px] text-zinc-500">Inventory + execution</div>
              </button>
            </div>
            {(importMode === "CURRENT_PR_EXECUTION_RESULTS" || importMode === "BOTH") && (
              <div className="text-[10px] text-zinc-500">
                Requires pull request ID and commit SHA
              </div>
            )}
          </div>
          <div className="border-2 border-dashed border-zinc-700 rounded-lg p-6 text-center">
            <Upload className="w-8 h-8 text-zinc-500 mx-auto mb-2" />
            <p className="text-sm text-zinc-400 mb-3">Upload JUnit XML test results</p>
            <input
              type="file"
              accept=".xml"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleUpload(file);
              }}
              disabled={uploading}
              className="hidden"
              id="junit-upload"
            />
            <label
              htmlFor="junit-upload"
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm cursor-pointer ${
                uploading
                  ? "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                  : "bg-blue-600 hover:bg-blue-700 text-white"
              }`}
            >
              {uploading ? "Uploading..." : "Select File"}
            </label>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowUpload(false)}
            className="text-zinc-400 hover:text-white"
          >
            <ArrowRight className="w-3 h-3 mr-1 rotate-180" />
            Back to test runs
          </Button>
        </div>
      ) : loading ? (
        <div className="text-center py-4 text-zinc-500 text-sm">Loading test runs...</div>
      ) : testRuns.length === 0 ? (
        <div className="space-y-3">
          <div className="text-center py-6 text-zinc-500 text-sm">
            <FileText className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
            <p className="mb-4">No test runs found for this PR</p>
          </div>
          <div className="space-y-2">
            {pullRequestId && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowUpload(true)}
                className="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700"
              >
                <Upload className="w-4 h-4 mr-2" />
                Upload JUnit XML for this PR
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                // Reload without PR filter to show historical runs
                const url = `/api/repositories/${repositoryId}/test-runs?limit=10`;
                fetch(url).then(res => res.json()).then(data => {
                  setTestRuns(data.test_runs || []);
                });
              }}
              className="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700"
            >
              <Archive className="w-4 h-4 mr-2" />
              Select historical test run
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsOpen(false)}
              className="w-full text-zinc-500 hover:text-white"
            >
              Continue without current execution
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {testRuns.map((testRun) => (
            <div
              key={testRun.id}
              onClick={() => handleSelectTestRun(testRun)}
              className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                selectedTestRun?.id === testRun.id
                  ? "bg-blue-950/30 border-blue-500/30"
                  : "bg-zinc-900/40 border-zinc-800/60 hover:bg-zinc-900/60"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    {testRun.is_current_pr && (
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    )}
                    <span className="text-xs font-mono text-zinc-400 truncate">
                      {testRun.commit_sha.slice(0, 8)}
                    </span>
                    {testRun.branch && (
                      <span className="text-[9px] text-zinc-500">{testRun.branch}</span>
                    )}
                    {isStale(testRun) && (
                      <span className="text-[9px] text-amber-400 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Stale
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                    <span>{formatRelative(testRun.created_at)}</span>
                    <span>•</span>
                    <span>{testRun.total_tests} tests</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-[10px]">
                  <span className="text-emerald-400">{testRun.passed_tests} passed</span>
                  {testRun.failed_tests > 0 && (
                    <span className="text-rose-400">{testRun.failed_tests} failed</span>
                  )}
                  {testRun.skipped_tests > 0 && (
                    <span className="text-amber-400">{testRun.skipped_tests} skipped</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showMismatchWarning && selectedTestRun && (
        <div className="bg-amber-950/20 border border-amber-800/40 rounded-lg p-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs text-amber-300 font-medium mb-1">Commit SHA Mismatch</p>
              <p className="text-[10px] text-amber-300/80">
                This test run was executed on a different commit ({selectedTestRun.commit_sha.slice(0, 8)}) than the current recommendation ({currentCommitSha?.slice(0, 8)}).
              </p>
            </div>
          </div>
        </div>
      )}

      {selectedTestRun && isStale(selectedTestRun) && (
        <div className="bg-amber-950/20 border border-amber-800/40 rounded-lg p-3">
          <div className="flex items-start gap-2">
            <Clock className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs text-amber-300 font-medium mb-1">Stale Test Run</p>
              <p className="text-[10px] text-amber-300/80">
                This test run is over 7 days old. Results may not reflect current code state.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-800/50">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsOpen(false)}
          className="text-zinc-400 hover:text-white"
        >
          Cancel
        </Button>
        <Button
          size="sm"
          onClick={handleAttach}
          disabled={!selectedTestRun || attaching}
          className="bg-blue-600 hover:bg-blue-700 text-white"
        >
          {attaching ? "Attaching..." : "Attach"}
        </Button>
      </div>
    </div>
  );
}
