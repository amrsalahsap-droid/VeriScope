"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { 
  ArrowLeft, 
  FlaskConical, 
  Upload, 
  FileCode, 
  CheckCircle, 
  AlertCircle, 
  X, 
  Info, 
  Copy, 
  Check, 
  Terminal, 
  ChevronRight, 
  Activity, 
  Calendar,
  FileCheck2,
  Lock,
  Globe,
  Sparkles,
  ShieldAlert,
  Dna,
  Loader2
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ repositoryId: string }>;
}

interface Repository {
  id: string;
  full_name: string;
  readiness_state: string;
  default_branch?: string | null;
  evidence?: {
    pull_requests_count: number;
    active_pull_requests_count: number;
    test_runs_count: number;
    test_results_count: number;
    coverage_reports_count: number;
    recommendations_count: number;
    fragility_patterns_count: number;
  };
}

interface TestHistorySummary {
  repository_id: string;
  test_runs_count: number;
  test_results_count: number;
  latest_test_run_at: string | null;
  latest_test_run: {
    id: string;
    run_name: string;
    commit_sha: string | null;
    branch: string | null;
    tests_total: number;
    tests_passed: number;
    tests_failed: number;
    tests_skipped: number;
    duration_seconds: number;
    evidence_health_status: string;
  } | null;
}

interface RepositoryReadiness {
  readiness_state: string;
  readiness_reasons: string[];
  next_action: string;
}

interface UploadResult {
  test_run_id: string;
  tests_total: number;
  tests_passed: number;
  tests_failed: number;
  tests_skipped: number;
  duration_seconds: number;
  parser_version: string;
  normalization_schema_version: string;
  evidence_health_status: string;
  duplicate_coalesced: boolean;
  repository_readiness: RepositoryReadiness;
}

const HELP_ITEMS = [
  {
    id: "jest",
    label: "Jest",
    desc: "Use your existing Jest JUnit reporter output. Most projects use the jest-junit npm package.",
    cmd: "npm test -- --reporters=default --reporters=jest-junit"
  },
  {
    id: "pytest",
    label: "Pytest",
    desc: "Standard Pytest runs can export XML directly via the command line.",
    cmd: "pytest --junitxml=report.xml"
  },
  {
    id: "maven",
    label: "Maven / Surefire",
    desc: "Maven builds using surefire output XML reports automatically to target.",
    cmd: "mvn test"
  },
  {
    id: "gradle",
    label: "Gradle",
    desc: "Gradle builds write XML test results inside build/test-results.",
    cmd: "./gradlew test"
  },
  {
    id: "ci",
    label: "CI artifacts",
    desc: "Download JUnit XML from your CI test artifacts (Jenkins, CircleCI, GitLab, etc.) and upload it here. This is the safest, framework-agnostic universal option.",
    cmd: ""
  }
];

export default function TestHistoryPage({ params }: PageProps) {
  const { data: session } = useSession();
  const [repositoryId, setRepositoryId] = useState<string | null>(null);
  const [repo, setRepo] = useState<Repository | null>(null);
  const [summary, setSummary] = useState<TestHistorySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [commitSha, setCommitSha] = useState("");
  const [branch, setBranch] = useState("");
  const [runName, setRunName] = useState("");
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [fromParam, setFromParam] = useState<"repositories" | "details">("details");
  const [activeHelpId, setActiveHelpId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // PR context states
  const [pullRequestId, setPullRequestId] = useState<string | null>(null);
  const [prNumber, setPrNumber] = useState<number | null>(null);
  const [returnTo, setReturnTo] = useState<string | null>(null);
  const [sourceParam, setSourceParam] = useState<string | null>(null);
  const [inputTypeParam, setInputTypeParam] = useState<string | null>(null);
  const [beforeReadiness, setBeforeReadiness] = useState<any>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const searchParams = new URLSearchParams(window.location.search);
      const rawFrom = searchParams.get("from");
      if (rawFrom === "repositories") {
        setFromParam("repositories");
      } else {
        setFromParam("details");
      }

      const prId = searchParams.get("pullRequestId");
      if (prId) setPullRequestId(prId);

      const retTo = searchParams.get("returnTo");
      if (retTo) setReturnTo(retTo);

      const src = searchParams.get("source");
      if (src) setSourceParam(src);

      const inType = searchParams.get("inputType");
      if (inType) setInputTypeParam(inType);
    }
  }, []);

  // Fetch repository data
  const fetchRepository = useCallback(async () => {
    if (!repositoryId) return;

    try {
      const headers: HeadersInit = {};
      if (session?.backendToken) {
        headers["Authorization"] = `Bearer ${session.backendToken}`;
      }
      const res = await fetch(
        `/api/repositories/${repositoryId}`,
        { headers, cache: "no-store" }
      );
      if (res.status === 401) {
        setError("Your session has expired. Please sign in again.");
        return;
      }
      if (!res.ok) {
        setRepo(null);
        return;
      }
      const data = await res.json();
      setRepo(data);
    } catch {
      setRepo(null);
    }
  }, [repositoryId, session?.backendToken]);

  // Fetch test history summary
  const fetchSummary = useCallback(async () => {
    if (!repositoryId) return;

    try {
      const headers: HeadersInit = {};
      if (session?.backendToken) {
        headers["Authorization"] = `Bearer ${session.backendToken}`;
      }
      const res = await fetch(
        `/api/repositories/${repositoryId}/test-history/summary`,
        { headers, cache: "no-store" }
      );
      if (res.status === 401) {
        setError("Your session has expired. Please sign in again.");
        return;
      }
      if (!res.ok) {
        setSummary(null);
        return;
      }
      const data = await res.json();
      setSummary(data);
    } catch {
      setSummary(null);
    }
  }, [repositoryId, session?.backendToken]);

  // Fetch before readiness details
  const fetchBeforeReadiness = useCallback(async (currentRepoId: string, currentPrId: string | null) => {
    try {
      const url = currentPrId
        ? `/api/repositories/${currentRepoId}/pull-requests/${currentPrId}/readiness`
        : `/api/repositories/${currentRepoId}/readiness`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setBeforeReadiness(data);
      }
    } catch (err) {
      console.error("Error fetching before readiness:", err);
    }
  }, []);

  const fetchPrDetails = useCallback(async (currentRepoId: string, currentPrId: string) => {
    try {
      const res = await fetch(`/api/repositories/${currentRepoId}/pull-requests`);
      if (res.ok) {
        const data = await res.json();
        const matchingPr = data.pull_requests?.find((p: any) => p.id === currentPrId);
        if (matchingPr) {
          setPrNumber(matchingPr.number);
        }
      }
    } catch (err) {
      console.error("Error fetching PR details:", err);
    }
  }, []);

  // Initialize repositoryId from params
  useEffect(() => {
    params.then(p => setRepositoryId(p.repositoryId));
  }, [params]);

  // Fetch repository when repositoryId is set
  useEffect(() => {
    if (repositoryId) {
      const searchParams = new URLSearchParams(window.location.search);
      const prId = searchParams.get("pullRequestId");

      const promises: Promise<any>[] = [fetchRepository(), fetchSummary()];
      if (prId) {
        promises.push(fetchPrDetails(repositoryId, prId));
        promises.push(fetchBeforeReadiness(repositoryId, prId));
      } else {
        promises.push(fetchBeforeReadiness(repositoryId, null));
      }

      Promise.all(promises).finally(() => {
        setLoading(false);
      });
    }
  }, [repositoryId, fetchRepository, fetchSummary, fetchPrDetails, fetchBeforeReadiness]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const validateFile = useCallback((selectedFile: File): string | null => {
    if (!selectedFile.name.endsWith('.xml')) {
      return "Only JUnit XML files are supported here.";
    }
    const maxSizeBytes = 10 * 1024 * 1024; // 10MB
    if (selectedFile.size > maxSizeBytes) {
      return "File size exceeds the 10MB limit.";
    }
    return null;
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      setFile(droppedFile);
      setUploadResult(null); // reset prior success on new select
      
      const validationError = validateFile(droppedFile);
      if (validationError) {
        setError(validationError);
        toast.error("File validation failed", {
          description: validationError
        });
      } else {
        setError(null);
        toast.success(`Selected file: ${droppedFile.name}`);
      }
    }
  }, [validateFile]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setUploadResult(null); // reset prior success on new select
      
      const validationError = validateFile(selectedFile);
      if (validationError) {
        setError(validationError);
        toast.error("File validation failed", {
          description: validationError
        });
      } else {
        setError(null);
        toast.success(`Selected file: ${selectedFile.name}`);
      }
    }
  };

  const copyCommand = (cmd: string, id: string) => {
    navigator.clipboard.writeText(cmd);
    setCopiedId(id);
    toast.success("Command copied to clipboard");
    setTimeout(() => setCopiedId(null), 2000);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const handleUpload = async () => {
    if (!file || !repositoryId) return;

    // Advisory client-side validation guard
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      toast.error("Upload blocked", {
        description: validationError
      });
      return;
    }

    setUploading(true);
    setError(null);
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const trimmedCommit = commitSha.trim();
      const trimmedBranch = branch.trim() || repo?.default_branch || "main";
      const trimmedRunName = runName.trim() || "Manual JUnit upload";

      if (trimmedCommit) formData.append("commit_sha", trimmedCommit);
      formData.append("branch", trimmedBranch);
      formData.append("run_name", trimmedRunName);
      formData.append("source", "MANUAL_UPLOAD");
      const importMode = pullRequestId ? "BOTH" : "INVENTORY_ONLY";
      formData.append("import_mode", importMode);
      if (pullRequestId) formData.append("pull_request_id", pullRequestId);
      if (sourceParam) formData.append("source_context", sourceParam);

      const headers: HeadersInit = {};
      if (session?.backendToken) {
        headers["Authorization"] = `Bearer ${session.backendToken}`;
      }

      const res = await fetch(
        `/api/repositories/${repositoryId}/test-history/upload`,
        { method: "POST", body: formData, headers }
      );

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        // Log technical error details to console/dev logs only (no raw stack traces in UI)
        console.error("JUnit Upload Ingestion Pipeline Failure:", {
          status: res.status,
          statusText: res.statusText,
          errorResponse: data
        });

        let userFriendlyMessage = "Upload failed. Please try again.";
        let toastTitle = "Upload failed";

        if (res.status === 401) {
          userFriendlyMessage = "Your session expired. Please sign in again.";
          toastTitle = "Session Expired";
        } else if (res.status === 403) {
          userFriendlyMessage = "Enable this repository before uploading test history.";
          toastTitle = "Repository Disabled";
        } else if (res.status === 409) {
          userFriendlyMessage = "This test report appears to have already been uploaded.";
          toastTitle = "Duplicate Artifact";
        } else if (res.status === 400) {
          const errorLower = (data.error || "").toLowerCase();
          if (errorLower.includes("type") || errorLower.includes("extension") || errorLower.includes("format") || errorLower.includes("xml files only")) {
            userFriendlyMessage = "Only JUnit XML files are supported here.";
            toastTitle = "Unsupported File Type";
          } else {
            userFriendlyMessage = "This file could not be parsed as JUnit XML.";
            toastTitle = "Invalid XML";
          }
        } else if (res.status >= 500) {
          userFriendlyMessage = "Veriscope could not reach the backend. Please retry.";
          toastTitle = "Backend Unavailable";
        } else {
          userFriendlyMessage = data.error || "An unexpected error occurred during upload.";
        }

        setError(userFriendlyMessage);
        toast.error(toastTitle, {
          description: userFriendlyMessage
        });
        return;
      }

      setUploadResult(data);
      setFile(null);
      setCommitSha("");
      setBranch("");
      setRunName("");
      
      toast.success("Evidence Ingested Successfully", {
        description: `Parsed ${data.tests_total} tests successfully!`
      });
      
      // Update repository readiness state from response
      if (data.repository_readiness && repo) {
        setRepo({
          ...repo,
          readiness_state: data.repository_readiness.readiness_state
        });
      }
      
      // Refresh repository data and summary to get updated counts
      await fetchRepository();
      await fetchSummary();
    } catch (err: any) {
      // Log technical error details to console/dev logs only (no raw stack traces in UI)
      console.error("Network or technical pipeline exception during upload:", err);

      const userFriendlyMessage = "Veriscope could not reach the backend. Please retry.";
      setError(userFriendlyMessage);
      toast.error("Backend Unavailable", {
        description: userFriendlyMessage
      });
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 max-w-4xl mx-auto px-4 py-8">
        <div className="space-y-3 animate-pulse">
          <div className="h-4 w-32 bg-zinc-800 rounded" />
          <div className="h-7 w-64 bg-zinc-800 rounded" />
          <div className="h-4 w-full bg-zinc-900 rounded" />
        </div>
        <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 animate-pulse h-24" />
        <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-6 animate-pulse h-48" />
        <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-8 animate-pulse h-64" />
      </div>
    );
  }

  if (!repo) {
    return (
      <div className="space-y-6 max-w-4xl mx-auto px-4 py-8 text-center">
        <div className="max-w-md mx-auto space-y-4">
          <div className="inline-flex p-3 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400">
            <ShieldAlert className="w-8 h-8" />
          </div>
          <h1 className="text-xl font-bold text-white">Repository Not Found</h1>
          <p className="text-sm text-zinc-400">
            The repository you are trying to access does not exist or you don't have permission to view it.
          </p>
          <Link href="/app/repositories" className="inline-block mt-2">
            <Button variant="outline" className="border-zinc-800 hover:bg-zinc-950 text-zinc-300">
              <ArrowLeft className="w-4 h-4 mr-2" /> Back to Repositories
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  // Deterministic CTA State Machine logic
  let ctaButtonText = "Upload JUnit XML";
  let ctaDisabled = false;
  let ctaHelperText = "";
  let ctaHelperType: "info" | "error" | "success" | "uploading" | "succeeded" = "info";

  if (uploading) {
    ctaButtonText = "Uploading…";
    ctaDisabled = true;
    ctaHelperText = "Ingesting and parsing JUnit XML report...";
    ctaHelperType = "uploading";
  } else if (uploadResult) {
    ctaButtonText = "Upload Completed";
    ctaDisabled = true;
    ctaHelperText = "Upload completed successfully!";
    ctaHelperType = "succeeded";
  } else if (!file) {
    ctaButtonText = "Upload JUnit XML";
    ctaDisabled = true;
    ctaHelperText = "Select a JUnit XML file before uploading.";
    ctaHelperType = "info";
  } else if (!file.name.endsWith('.xml')) {
    ctaButtonText = "Upload JUnit XML";
    ctaDisabled = true;
    ctaHelperText = "Only .xml JUnit report files are supported.";
    ctaHelperType = "error";
  } else if (file.size > 10 * 1024 * 1024) {
    ctaButtonText = "Upload JUnit XML";
    ctaDisabled = true;
    ctaHelperText = "File size exceeds the 10MB limit.";
    ctaHelperType = "error";
  } else if (error) {
    ctaButtonText = "Retry Upload";
    ctaDisabled = false;
    ctaHelperText = error;
    ctaHelperType = "error";
  } else {
    ctaButtonText = "Upload JUnit XML";
    ctaDisabled = false;
    ctaHelperText = `Ready to upload ${file.name}.`;
    ctaHelperType = "success";
  }

  const isFileValid = file ? (file.name.endsWith('.xml') && file.size <= 10 * 1024 * 1024) : false;

  const backHref = fromParam === "repositories" ? "/app/repositories" : `/app/repositories/${repositoryId}`;
  const backLabel = fromParam === "repositories" ? "Repositories" : "Repository Details";

  // Loading skeleton for initial page load
  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-8">
        <div className="space-y-4">
          <div className="h-8 w-32 bg-zinc-800 rounded animate-pulse" />
          <div className="h-10 w-64 bg-zinc-800 rounded animate-pulse" />
          <div className="h-4 w-96 bg-zinc-800 rounded animate-pulse" />
        </div>
        <div className="h-32 bg-zinc-800/50 rounded-xl animate-pulse" />
        <div className="h-64 bg-zinc-800/50 rounded-xl animate-pulse" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-8">
      {/* 1. Header with breadcrumbs and descriptive subtitle */}
      <div className="space-y-4">
        <Link 
          href={backHref}
          className="inline-flex items-center gap-2 text-xs font-semibold text-zinc-400 hover:text-zinc-200 transition-colors duration-200"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to {backLabel}
        </Link>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-900 pb-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-500 bg-zinc-950/60 border border-zinc-900 rounded-md px-2.5 py-1 w-fit">
              <Dna className="w-3 h-3 text-amber-500" />
              {repo.full_name}
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight pt-1">
              {pullRequestId && prNumber 
                ? `Upload test results for PR #${prNumber}` 
                : "Test History Evidence"}
            </h1>
            <p className="text-sm text-zinc-400 max-w-2xl leading-relaxed">
              Upload JUnit XML test results so Veriscope can understand how this repository’s tests behave over time and start building reliable regression intelligence.
            </p>
            {pullRequestId && prNumber && (
              <div className="mt-2 text-xs text-indigo-400 bg-indigo-950/20 border border-indigo-900/30 rounded-lg p-2.5 max-w-2xl">
                PR context detected. Veriscope will automatically associate this upload with PR #{prNumber} and its head commit.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 2. Readiness Banner */}
      {repo.readiness_state === "NEEDS_TEST_HISTORY" && !uploadResult && (
        <div className="relative overflow-hidden bg-gradient-to-r from-amber-500/[0.03] to-transparent border border-amber-500/20 rounded-xl p-5 shadow-lg shadow-amber-500/[0.01] flex items-start gap-4">
          <div className="absolute top-0 left-0 w-[3px] h-full bg-amber-500 animate-pulse" />
          <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0">
            <FlaskConical className="w-5 h-5" />
          </div>
          <div className="space-y-1.5">
            <p className="text-sm font-bold text-amber-300">Test history required</p>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Veriscope needs at least one JUnit XML test run before it can generate evidence-backed regression recommendations. Uploading a test history file unlocks performance optimizations and test speedups.
            </p>
          </div>
        </div>
      )}

      {/* Grid containing How to Generate & Metadata side-by-side or stacked cleanly */}
      <div className="grid grid-cols-1 gap-6">
        
        {/* 3. How to generate JUnit XML Card */}
        <div className="bg-zinc-900/10 border border-zinc-800/80 rounded-xl p-5 space-y-4 backdrop-blur-sm">
          <div className="flex items-center justify-between border-b border-zinc-800/60 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 rounded bg-zinc-850 text-zinc-400">
                <Terminal className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-bold text-zinc-200">How to generate JUnit XML</h3>
            </div>
            <span className="text-[10px] font-mono text-zinc-500">CI & test runner guides</span>
          </div>
          
          <p className="text-xs text-zinc-400 leading-relaxed">
            Most CI systems and test runners can export JUnit XML. Upload one recent regression run to get started.
          </p>

          {/* Accordion / Collapsible Examples List */}
          <div className="space-y-2 pt-1">
            {HELP_ITEMS.map((item) => {
              const isOpen = activeHelpId === item.id;
              return (
                <div key={item.id} className="bg-zinc-950/40 border border-zinc-900 rounded-lg overflow-hidden transition-colors">
                  <button
                    onClick={() => setActiveHelpId(isOpen ? null : item.id)}
                    className="w-full px-4 py-3 flex items-center justify-between gap-4 hover:bg-zinc-900/30 transition-colors text-left"
                  >
                    <span className="text-xs font-bold text-zinc-300">{item.label}</span>
                    <ChevronRight className={`w-3.5 h-3.5 text-zinc-550 transition-transform duration-200 ${isOpen ? "rotate-90 text-zinc-300" : ""}`} />
                  </button>
                  
                  {isOpen && (
                    <div className="px-4 pb-3.5 space-y-2 border-t border-zinc-900/50 pt-2.5 animate-in fade-in slide-in-from-top-1 duration-150">
                      <p className="text-xs text-zinc-400 font-medium leading-relaxed">{item.desc}</p>
                      {item.cmd && (
                        <div className="relative group bg-zinc-950/80 border border-zinc-900 rounded-md p-2.5 font-mono text-[10px] text-zinc-300 overflow-hidden flex items-center justify-between gap-4">
                          <div className="overflow-x-auto whitespace-nowrap select-all pr-8 scrollbar-none w-full">
                            <span className="text-zinc-500 pr-1.5">$</span>
                            <span>{item.cmd}</span>
                          </div>
                          <button
                            onClick={() => copyCommand(item.cmd, item.id)}
                            className="absolute right-2 top-2 p-1.5 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white transition-all active:scale-95"
                            title="Copy command"
                          >
                            {copiedId === item.id ? (
                              <Check className="w-3.5 h-3.5 text-emerald-400" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Future GitHub Actions Auto-ingestion Placeholder */}
            <div className="bg-zinc-950/20 border border-dashed border-zinc-900 rounded-lg p-3.5 flex items-center justify-between gap-4 opacity-75">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-zinc-400">GitHub Actions</span>
                  <span className="text-[9px] font-semibold text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/15">Coming later</span>
                </div>
                <p className="text-[10px] text-zinc-550 leading-normal">
                  Auto-ingest report artifacts directly from your GitHub workflow runs.
                </p>
              </div>
              <Sparkles className="w-4 h-4 text-zinc-650 shrink-0" />
            </div>
          </div>
        </div>

        {/* 4. Upload Card & Drag/Drop Area */}
        <div 
          className={`relative bg-gradient-to-b from-zinc-900/10 to-zinc-950/10 border-2 border-dashed rounded-xl p-8 text-center transition-all duration-300 backdrop-blur-sm ${
            dragActive 
              ? "border-amber-500/50 bg-amber-500/[0.02] shadow-inner" 
              : file 
              ? "border-emerald-500/20 bg-emerald-500/[0.01]" 
              : "border-zinc-800/80 hover:border-zinc-700/80"
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            id="file-upload"
            accept=".xml"
            onChange={handleFileSelect}
            className="hidden"
          />

          <div className="space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-zinc-900/80 border border-zinc-800 flex items-center justify-center mx-auto shadow-md">
              <Upload className={`w-5 h-5 ${file ? "text-emerald-400" : "text-zinc-400"}`} />
            </div>
            
            <div className="space-y-1">
              <h2 className="text-sm font-bold text-white">
                Upload test execution results
              </h2>
              <p className="text-xs text-zinc-500 max-w-sm mx-auto leading-relaxed">
                Drag and drop a JUnit XML file here, or click to browse files.
              </p>
              <p className="text-[10px] text-zinc-600 font-mono">
                Only .xml files are supported (max 10MB).
              </p>
            </div>

            <label htmlFor="file-upload" className="inline-block pt-1">
              <Button 
                variant="outline" 
                asChild
                className="border-zinc-800 hover:border-zinc-700 bg-zinc-950/50 hover:bg-zinc-900 text-zinc-300 hover:text-white cursor-pointer h-9 text-xs px-4"
              >
                <span>Select JUnit XML File</span>
              </Button>
            </label>

            {/* Selected File & Validation Status */}
            {file && (
              <div className={`mt-2 max-w-md mx-auto bg-zinc-950/80 rounded-lg p-3 flex items-center justify-between gap-3 text-left border ${
                isFileValid 
                  ? "border-emerald-500/10" 
                  : "border-rose-500/20"
              }`}>
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`p-2 rounded border ${
                    isFileValid 
                      ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" 
                      : "bg-rose-500/10 border-rose-500/20 text-rose-400"
                  }`}>
                    <FileCode className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-zinc-200 truncate">{file.name}</p>
                    <p className="text-[10px] text-zinc-500">{formatFileSize(file.size)}</p>
                  </div>
                </div>
                
                <div className="flex items-center gap-3 shrink-0">
                  {isFileValid ? (
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      <FileCheck2 className="w-3 h-3" />
                      Validation Passed
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                      <AlertCircle className="w-3 h-3" />
                      {file.name.endsWith('.xml') ? "File Oversized (>10MB)" : "Invalid Extension"}
                    </span>
                  )}
                  <button
                    onClick={() => {
                      setFile(null);
                      setError(null);
                    }}
                    className="text-zinc-500 hover:text-zinc-300 p-1 hover:bg-zinc-900 rounded-md transition-colors"
                    title="Remove file"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Inline Error Block near Upload Card */}
        {error && (
          <div className="bg-rose-950/10 border border-rose-500/25 rounded-xl p-5 flex items-start gap-4 shadow-lg shadow-rose-500/[0.01] animate-in fade-in slide-in-from-top-2 duration-200">
            <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 shrink-0">
              <AlertCircle className="w-5 h-5" />
            </div>
            <div className="flex-1 space-y-1.5 text-left">
              <p className="text-sm font-bold text-rose-200">Upload failed</p>
              <p className="text-xs text-zinc-300 leading-relaxed">{error}</p>
              
              {/* Dynamic recovery guidelines */}
              {error.includes("session expired") && (
                <div className="pt-1.5">
                  <Link href="/login">
                    <Button size="sm" className="bg-rose-500 hover:bg-rose-400 text-zinc-950 text-[10px] font-bold h-7 px-3">
                      Sign In Again
                    </Button>
                  </Link>
                </div>
              )}
              
              {error.includes("Enable this repository") && (
                <p className="text-[10px] text-zinc-550 font-medium">
                  Tip: Go to the repository details page and toggle "Selected for Analysis" to enable it.
                </p>
              )}

              {error.includes("could not be parsed") && (
                <p className="text-[10px] text-zinc-550 font-medium">
                  Tip: Ensure your file contains valid &lt;testsuites&gt; or &lt;testsuite&gt; root XML tags. See the developer guides below for typical formats.
                </p>
              )}
              
              {error.includes("already been uploaded") && (
                <p className="text-[10px] text-zinc-550 font-medium">
                  Tip: Veriscope prevents duplicate test report ingestion to keep your analytics clean. Please generate a new test run to upload.
                </p>
              )}

              {error.includes("reach the backend") && (
                <p className="text-[10px] text-zinc-550 font-medium">
                  Tip: Please verify your internet connection. If the problem persists, the backend server might be performing scheduled maintenance.
                </p>
              )}
            </div>
            <button
              onClick={() => setError(null)}
              className="text-zinc-500 hover:text-zinc-300 p-1 hover:bg-zinc-900 rounded-md transition-colors self-start"
              title="Dismiss error"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* 5. Metadata Card */}
        <div className="bg-zinc-900/10 border border-zinc-800/80 rounded-xl p-5 space-y-4 backdrop-blur-sm">
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-zinc-200">Run metadata</h3>
            <p className="text-xs text-zinc-500">
              Optional, but improves replayability and recommendation traceability.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
            <div className="space-y-1.5">
              <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Commit SHA</label>
              <input
                type="text"
                value={commitSha}
                onChange={(e) => setCommitSha(e.target.value)}
                placeholder="e.g. 5d5be5a27"
                className="w-full bg-zinc-950/60 border border-zinc-800/60 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder-zinc-700 focus:outline-none focus:border-amber-500/50 transition-colors"
              />
              <p className="text-[10px] text-zinc-500 leading-normal">
                Links this test run to the exact code revision. Optional but recommended.
              </p>
            </div>
            <div className="space-y-1.5">
              <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Branch</label>
              <input
                type="text"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                placeholder="e.g. main"
                className="w-full bg-zinc-950/60 border border-zinc-800/60 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder-zinc-700 focus:outline-none focus:border-amber-500/50 transition-colors"
              />
              <p className="text-[10px] text-zinc-500 leading-normal">
                Useful when importing CI runs from feature branches.
              </p>
            </div>
            <div className="space-y-1.5">
              <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Run Name</label>
              <input
                type="text"
                value={runName}
                onChange={(e) => setRunName(e.target.value)}
                placeholder="e.g. CI Run #482"
                className="w-full bg-zinc-950/60 border border-zinc-800/60 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder-zinc-700 focus:outline-none focus:border-amber-500/50 transition-colors"
              />
              <p className="text-[10px] text-zinc-500 leading-normal">
                Human-readable label such as “CI Build #123” or “Nightly regression”.
              </p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-3 border-t border-zinc-800/60">
            <div>
              {/* Helper text with exact states */}
              {ctaHelperType === "uploading" && (
                <span className="flex items-center gap-2 text-[11px] text-zinc-400 font-medium">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-500 shrink-0" />
                  {ctaHelperText}
                </span>
              )}
              
              {ctaHelperType === "succeeded" && (
                <span className="flex items-center gap-2 text-[11px] text-emerald-400 font-semibold animate-in fade-in">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                  {ctaHelperText}
                </span>
              )}
              
              {ctaHelperType === "info" && (
                <span className="flex items-center gap-2 text-[11px] text-zinc-500 font-medium">
                  <Info className="w-3.5 h-3.5 text-zinc-555 shrink-0" />
                  {ctaHelperText}
                </span>
              )}
              
              {ctaHelperType === "error" && (
                <span className="flex items-center gap-2 text-[11px] text-rose-400 font-medium animate-in fade-in">
                  <AlertCircle className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                  {ctaHelperText}
                </span>
              )}
              
              {ctaHelperType === "success" && (
                <span className="flex items-center gap-2 text-[11px] text-emerald-400 font-semibold animate-in fade-in">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                  {ctaHelperText}
                </span>
              )}
            </div>
            
            <div className="flex items-center gap-3">
              {uploadResult ? (
                <>
                  <Link href={`/app/repositories/${repositoryId}/coverage?from=test-history${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}${returnTo ? `&returnTo=${returnTo}` : ""}${sourceParam ? `&source=${sourceParam}` : ""}`}>
                    <Button className="bg-emerald-500 hover:bg-emerald-400 text-zinc-950 text-xs font-bold h-9 px-4 shadow-md transition-all duration-200">
                      Upload Coverage Report <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  </Link>
                  <Link href={returnTo === "readiness"
                    ? `/app/repositories/${repositoryId}?openReadiness=true${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}`
                    : `/app/repositories/${repositoryId}`
                  }>
                    <Button variant="outline" className="border-zinc-800 text-zinc-300 hover:bg-zinc-900 text-xs h-9 px-4 transition-all duration-200">
                      {returnTo === "readiness" ? "Back to Readiness" : "View Repository Readiness"}
                    </Button>
                  </Link>
                </>
              ) : (
                <Button
                  onClick={handleUpload}
                  disabled={ctaDisabled}
                  className={`font-semibold h-9 text-xs px-5 rounded-lg shadow-md transition-all duration-200 tracking-tight flex items-center gap-2 ${
                    !ctaDisabled
                      ? "bg-white text-zinc-950 hover:bg-zinc-100 hover:scale-[1.01]"
                      : "bg-zinc-850 text-zinc-600 cursor-not-allowed border border-zinc-850/40"
                  }`}
                >
                  {uploading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  {ctaButtonText}
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>


      {/* 7. After success transitions and recommendations */}
      {/* 7. After success transitions and recommendations */}
      {uploadResult && (
        <div className="bg-emerald-950/10 border border-emerald-500/25 rounded-xl p-6 space-y-6 shadow-lg shadow-emerald-500/[0.01] animate-in zoom-in-95 duration-300">
          
          {/* Header */}
          <div className="flex items-center gap-3.5 border-b border-emerald-500/10 pb-4">
            <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
              <CheckCircle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-emerald-300">Test history uploaded</h3>
              <p className="text-[10px] text-zinc-500 mt-0.5">
                Ingested and processed successfully by Veriscope
              </p>
            </div>
            {uploadResult.duplicate_coalesced && (
              <span className="text-[9px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold uppercase tracking-wider ml-auto">
                Merged Coalesced
              </span>
            )}
          </div>

          {/* Readiness Score Transition Block */}
          {beforeReadiness && uploadResult.readiness_summary && (
            <div className="bg-zinc-950/60 border border-zinc-900 rounded-lg p-5 space-y-4">
              <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block">Readiness Transition</span>
              
              <div className="flex flex-col sm:flex-row items-center justify-between gap-6 bg-zinc-900/10 p-4 rounded-xl border border-zinc-900">
                <div className="flex items-center gap-6">
                  {/* Before state */}
                  <div className="text-center">
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-1">Before</p>
                    <p className="text-2xl font-black text-zinc-400">
                      {beforeReadiness.readiness_score ?? beforeReadiness.intelligence_completeness_score ?? 0}%
                    </p>
                    <span className="text-[10px] px-2.5 py-0.5 rounded-full border border-zinc-700 bg-zinc-800/40 text-zinc-400 mt-1 inline-block">
                      {beforeReadiness.expected_confidence || beforeReadiness.readiness_level?.replace(/_/g, " ")}
                    </span>
                  </div>

                  {/* Arrow animation */}
                  <div className="flex flex-col items-center text-zinc-500">
                    <ChevronRight className="w-5 h-5 text-indigo-400 animate-pulse" />
                  </div>

                  {/* After state */}
                  <div className="text-center">
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-1 text-indigo-400">After</p>
                    <p className="text-2xl font-black text-indigo-400">
                      {uploadResult.readiness_summary.readiness_score ?? uploadResult.readiness_summary.intelligence_completeness_score ?? 0}%
                    </p>
                    <span className="text-[10px] px-2.5 py-0.5 rounded-full border border-indigo-500/30 bg-indigo-950/20 text-indigo-400 mt-1 inline-block">
                      {uploadResult.readiness_summary.expected_confidence || uploadResult.readiness_summary.readiness_level?.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>

                <div className="text-left flex-1 border-t sm:border-t-0 sm:border-l border-zinc-900 pt-4 sm:pt-0 sm:pl-6 space-y-2">
                  <p className="text-xs font-bold text-zinc-300">Input Signals Resolved:</p>
                  <ul className="text-xs space-y-1 text-zinc-400 font-medium">
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      Test History: <span className="text-zinc-500 line-through">Missing</span> <span className="text-emerald-400">→ Available</span>
                    </li>
                    {pullRequestId && (
                      <li className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        Current PR Test Results: <span className="text-zinc-500 line-through">Missing</span> <span className="text-emerald-400">→ Available</span>
                      </li>
                    )}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* 6 Summary Cards */}
          <div className="space-y-2.5">
            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block">Ingestion summary</span>
            <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
              <div className="bg-zinc-950/60 border border-zinc-900 rounded-lg p-3">
                <p className="text-[9px] text-zinc-500 uppercase tracking-wider mb-1 font-semibold">Total Tests</p>
                <p className="text-base font-extrabold text-zinc-200">{uploadResult.tests_total}</p>
              </div>
              <div className="bg-zinc-950/60 border border-zinc-900 rounded-lg p-3 border-l-emerald-500/20 border-l-2">
                <p className="text-[9px] text-emerald-400/80 uppercase tracking-wider mb-1 font-semibold">Passed</p>
                <p className="text-base font-extrabold text-emerald-400">{uploadResult.tests_passed}</p>
              </div>
              <div className="bg-zinc-950/60 border border-zinc-900 rounded-lg p-3 border-l-rose-500/20 border-l-2">
                <p className="text-[9px] text-rose-400/80 uppercase tracking-wider mb-1 font-semibold">Failed</p>
                <p className="text-base font-extrabold text-rose-400">{uploadResult.tests_failed}</p>
              </div>
              <div className="bg-zinc-950/60 border border-zinc-900 rounded-lg p-3">
                <p className="text-[9px] text-zinc-500 uppercase tracking-wider mb-1 font-semibold">Skipped</p>
                <p className="text-base font-extrabold text-zinc-400">{uploadResult.tests_skipped}</p>
              </div>
              <div className="bg-zinc-950/60 border border-zinc-900 rounded-lg p-3">
                <p className="text-[9px] text-zinc-500 uppercase tracking-wider mb-1 font-semibold">Duration</p>
                <p className="text-base font-extrabold text-zinc-200">{uploadResult.duration_seconds}s</p>
              </div>
              <div className="bg-zinc-950/60 border border-zinc-900 rounded-lg p-3 border-l-amber-500/20 border-l-2">
                <p className="text-[9px] text-zinc-500 uppercase tracking-wider mb-1 font-semibold font-mono">Health</p>
                <p className={`text-xs font-bold tracking-wide ${
                  uploadResult.evidence_health_status === "HEALTHY" 
                    ? "text-emerald-400" 
                    : "text-amber-400"
                }`}>{uploadResult.evidence_health_status}</p>
              </div>
            </div>
          </div>

          {/* Technical Metadata */}
          <div className="bg-zinc-950/40 border border-zinc-900/60 rounded-lg p-3.5 space-y-2">
            <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest block">Technical Metadata</span>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-[10px] font-mono text-zinc-400">
              <div className="space-y-0.5">
                <p className="text-zinc-650 font-bold uppercase tracking-wider text-[8px]">Parser Version</p>
                <p className="text-zinc-300 font-semibold">{uploadResult.parser_version}</p>
              </div>
              <div className="space-y-0.5">
                <p className="text-zinc-650 font-bold uppercase tracking-wider text-[8px]">Schema Version</p>
                <p className="text-zinc-300 font-semibold">{uploadResult.normalization_schema_version}</p>
              </div>
              <div className="space-y-0.5">
                <p className="text-zinc-650 font-bold uppercase tracking-wider text-[8px]">Evidence Source</p>
                <p className="text-zinc-300 font-semibold">Manual upload</p>
              </div>
              <div className="space-y-0.5">
                <p className="text-zinc-650 font-bold uppercase tracking-wider text-[8px]">Test Run ID</p>
                <p className="text-amber-400/90 font-semibold">{uploadResult.test_run_id.slice(0, 8)}</p>
              </div>
            </div>
          </div>

          {/* Readiness Transition & Next Action */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-4 border-t border-emerald-500/10">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Readiness Status</span>
                <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />
                <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 rounded">
                  Repository readiness updated to {uploadResult.repository_readiness.readiness_state.replace(/_/g, " ")}
                </span>
              </div>
              <p className="text-xs text-zinc-400 max-w-md">
                Veriscope has recalculated active regression indicators based on backend readiness logic.
              </p>
            </div>
            
            <div className="flex items-center gap-2 shrink-0">
              {uploadResult.repository_readiness.readiness_state === "NEEDS_COVERAGE" && (
                <>
                  <Link href={`/app/repositories/${repositoryId}/coverage?from=test-history${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}${returnTo ? `&returnTo=${returnTo}` : ""}${sourceParam ? `&source=${sourceParam}` : ""}`}>
                    <Button className="bg-emerald-500 hover:bg-emerald-400 text-zinc-950 text-xs font-bold h-9 px-4">
                      Upload Coverage Report <ChevronRight className="w-4 h-4 ml-1.5" />
                    </Button>
                  </Link>
                  <Link href={returnTo === "readiness"
                    ? `/app/repositories/${repositoryId}?openReadiness=true${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}`
                    : `/app/repositories/${repositoryId}`
                  }>
                    <Button variant="outline" className="border-zinc-800 text-zinc-300 hover:bg-zinc-900 text-xs h-9 px-4">
                      {returnTo === "readiness" ? "Back to Readiness" : "View Repository Readiness"}
                    </Button>
                  </Link>
                </>
              )}
              
              {uploadResult.repository_readiness.readiness_state === "READY" && (
                <>
                  {repo?.evidence && repo.evidence.pull_requests_count > 0 ? (
                    <>
                      <Link href={returnTo === "readiness"
                        ? `/app/repositories/${repositoryId}?openReadiness=true${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}`
                        : `/app/repositories/${repositoryId}`
                      }>
                        <Button className="bg-emerald-500 hover:bg-emerald-400 text-zinc-950 text-xs font-bold h-9 px-4">
                          {returnTo === "readiness" ? "Back to Readiness" : "Run PR Recommendation"} <ChevronRight className="w-4 h-4 ml-1.5" />
                        </Button>
                      </Link>
                    </>
                  ) : (
                    <Link href={returnTo === "readiness"
                      ? `/app/repositories/${repositoryId}?openReadiness=true${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}`
                      : `/app/repositories/${repositoryId}`
                    }>
                      <Button className="bg-white hover:bg-zinc-100 text-zinc-950 text-xs font-bold h-9 px-5">
                        {returnTo === "readiness" ? "Back to Readiness" : "View Repository Readiness"} <ChevronRight className="w-4 h-4 ml-1.5" />
                      </Button>
                    </Link>
                  )}
                </>
              )}

              {/* Catch-all for any other state */}
              {uploadResult.repository_readiness.readiness_state !== "NEEDS_COVERAGE" && uploadResult.repository_readiness.readiness_state !== "READY" && (
                <Link href={returnTo === "readiness"
                  ? `/app/repositories/${repositoryId}?openReadiness=true${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}`
                  : `/app/repositories/${repositoryId}`
                }>
                  <Button className="bg-white hover:bg-zinc-100 text-zinc-950 text-xs font-bold h-9 px-5">
                    {returnTo === "readiness" ? "Back to Readiness" : "View Repository Readiness"} <ChevronRight className="w-4 h-4 ml-1.5" />
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 6. Current Evidence Card */}
      <div className="bg-zinc-900/10 border border-zinc-800/80 rounded-xl p-5 space-y-5 backdrop-blur-sm">
        <div className="flex items-center justify-between border-b border-zinc-800/60 pb-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-zinc-400" />
            <h3 className="text-sm font-bold text-zinc-200">Current evidence summary</h3>
          </div>
          <span className="text-[10px] text-zinc-500 font-mono">Active configuration</span>
        </div>
        
        {/* Primary Metrics Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
          <div className="bg-zinc-950/65 border border-zinc-900 rounded-xl p-4 space-y-1">
            <p className="text-[10px] text-zinc-550 font-bold uppercase tracking-wider">Total Test Runs</p>
            <p className="text-xl font-extrabold text-zinc-150">{summary?.test_runs_count || 0}</p>
          </div>
          
          <div className="bg-zinc-950/65 border border-zinc-900 rounded-xl p-4 space-y-1">
            <p className="text-[10px] text-zinc-550 font-bold uppercase tracking-wider">Total Test Results</p>
            <p className="text-xl font-extrabold text-zinc-150">{summary?.test_results_count || 0}</p>
          </div>
          
          <div className="bg-zinc-950/65 border border-zinc-900 rounded-xl p-4 space-y-1">
            <div className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-zinc-650" />
              <p className="text-[10px] text-zinc-550 font-bold uppercase tracking-wider">Latest Upload</p>
            </div>
            <p className="text-xs font-bold text-zinc-300 pt-0.5">
              {summary?.latest_test_run_at 
                ? new Date(summary.latest_test_run_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
                : "Never"
              }
            </p>
          </div>
          
          <div className="bg-zinc-950/65 border border-zinc-900 rounded-xl p-4 space-y-1">
            <p className="text-[10px] text-zinc-550 font-bold uppercase tracking-wider">Evidence Health</p>
            <div className="flex items-center gap-2 pt-0.5">
              <span className={`relative flex h-2 w-2`}>
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  summary?.latest_test_run?.evidence_health_status === "HEALTHY" 
                    ? "bg-emerald-400" 
                    : summary?.test_runs_count && summary.test_runs_count > 0 
                    ? "bg-amber-400" 
                    : "bg-zinc-500"
                }`} />
                <span className={`relative inline-flex rounded-full h-2 w-2 ${
                  summary?.latest_test_run?.evidence_health_status === "HEALTHY" 
                    ? "bg-emerald-500" 
                    : summary?.test_runs_count && summary.test_runs_count > 0 
                    ? "bg-amber-500" 
                    : "bg-zinc-600"
                }`} />
              </span>
              <span className="text-xs font-bold tracking-tight text-zinc-300">
                {summary?.latest_test_run?.evidence_health_status || (summary?.test_runs_count && summary.test_runs_count > 0 ? "CALIBRATING" : "NO EVIDENCE")}
              </span>
            </div>
          </div>
        </div>

        {/* Latest Run Details (Commit, Branch, Run Name) */}
        {summary?.latest_test_run && (
          <div className="bg-zinc-950/40 border border-zinc-900/60 rounded-lg p-3.5 space-y-2 animate-in fade-in duration-200">
            <span className="text-[9px] font-bold text-zinc-550 uppercase tracking-widest block">Latest Ingested Run Details</span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-[10px] font-mono text-zinc-400">
              <div className="space-y-0.5">
                <p className="text-zinc-650 font-bold uppercase tracking-wider text-[8px]">Run Name</p>
                <p className="text-zinc-300 font-semibold truncate">{summary.latest_test_run.run_name || "—"}</p>
              </div>
              <div className="space-y-0.5">
                <p className="text-zinc-650 font-bold uppercase tracking-wider text-[8px]">Branch</p>
                <p className="text-zinc-300 font-semibold truncate">{summary.latest_test_run.branch || "—"}</p>
              </div>
              <div className="space-y-0.5">
                <p className="text-zinc-650 font-bold uppercase tracking-wider text-[8px]">Commit SHA</p>
                <p className="text-amber-400/90 font-semibold">
                  {summary.latest_test_run.commit_sha 
                    ? summary.latest_test_run.commit_sha.slice(0, 8) 
                    : "—"
                  }
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
