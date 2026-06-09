"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import { redirect, useRouter } from "next/navigation";
import Link from "next/link";
import { 
  ArrowLeft, 
  BarChart2, 
  Upload, 
  FileText, 
  CheckCircle, 
  AlertCircle, 
  X, 
  AlertTriangle, 
  Info, 
  Database,
  Calendar,
  ShieldCheck,
  Code,
  Sparkles,
  Play,
  RefreshCw,
  Loader2,
  GitBranch,
  ChevronRight
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export const dynamic = "force-dynamic";

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "Not synced yet";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "Not synced yet";
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
}


interface PageProps {
  params: Promise<{ repositoryId: string }>;
  searchParams: Promise<{ from?: string }>;
}

interface Repository {
  id: string;
  full_name: string;
  coverage_reports_count: number;
  readiness_state: string;
}

interface UploadResult {
  coverage_report_id: string;
  format: string;
  files_total: number;
  covered_lines_total: number;
  uncovered_lines_total: number;
  total_lines: number;
  line_coverage_ratio: number;
  coverage_confidence: string;
  parser_version: string;
  normalization_schema_version: string;
  repository_readiness: {
    readiness_state: string;
    next_action: string;
  };
  evidence_health_status?: string;
}

interface SummaryData {
  repository_id: string;
  coverage_reports_count: number;
  latest_coverage_at: string | null;
  latest_report: {
    id: string;
    format: string;
    commit_sha: string | null;
    branch: string | null;
    files_total: number;
    covered_lines_total: number;
    uncovered_lines_total: number;
    total_lines: number;
    line_coverage_ratio: number | null;
    coverage_confidence: string;
    evidence_health_status: string;
    source: string;
  } | null;
}

export default function CoveragePage({ params, searchParams }: PageProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const [repositoryId, setRepositoryId] = useState<string | null>(null);
  const [repo, setRepo] = useState<Repository | null>(null);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  
  // State Fields mapping to the required contract:
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState(""); // mapping to selectedFormat
  const [fileValidationStatus, setFileValidationStatus] = useState<"VALID" | "INVALID" | null>(null);
  const [fileValidationMessage, setFileValidationMessage] = useState<string | null>(null);
  
  const [dragActive, setDragActive] = useState(false);
  const [commitSha, setCommitSha] = useState("");
  const [branch, setBranch] = useState("");
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [pullRequests, setPullRequests] = useState<any[]>([]);
  const [runningRecommendation, setRunningRecommendation] = useState<string | null>(null);
  const [from, setFrom] = useState<string>("details");

  // PR context states
  const [pullRequestId, setPullRequestId] = useState<string | null>(null);
  const [prNumber, setPrNumber] = useState<number | null>(null);
  const [returnTo, setReturnTo] = useState<string | null>(null);
  const [sourceParam, setSourceParam] = useState<string | null>(null);
  const [inputTypeParam, setInputTypeParam] = useState<string | null>(null);
  const [beforeReadiness, setBeforeReadiness] = useState<any>(null);
  
  // File input trigger ref
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Parse from parameter on mount
  useEffect(() => {
    searchParams.then(sp => {
      setFrom(sp.from || "details");
    });

    if (typeof window !== "undefined") {
      const searchParamsObj = new URLSearchParams(window.location.search);
      const prId = searchParamsObj.get("pullRequestId");
      if (prId) setPullRequestId(prId);

      const retTo = searchParamsObj.get("returnTo");
      if (retTo) setReturnTo(retTo);

      const src = searchParamsObj.get("source");
      if (src) setSourceParam(src);

      const inType = searchParamsObj.get("inputType");
      if (inType) setInputTypeParam(inType);
    }
  }, [searchParams]);

  const getBackHref = () => {
    if (returnTo === "readiness") {
      return `/app/repositories/${repositoryId}?openReadiness=true${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}`;
    }
    if (from === "repositories") return "/app/repositories";
    if (from === "test-history") return `/app/repositories/${repositoryId}/test-history?from=details`;
    return `/app/repositories/${repositoryId}`;
  };

  const fetchPullRequests = useCallback(async () => {
    if (!repositoryId || !session?.backendToken) return;
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/repositories/${repositoryId}/pull-requests`,
        { headers: { Authorization: `Bearer ${session.backendToken}` }, cache: "no-store" }
      );
      if (res.ok) {
        const data = await res.json();
        setPullRequests(data.pull_requests || []);
      }
    } catch (e) {
      console.error("Failed to fetch pull requests", e);
    }
  }, [repositoryId, session?.backendToken]);

  const triggerRecommendation = useCallback(async (prId: string) => {
    if (!repositoryId || !session?.backendToken) return;
    setRunningRecommendation(prId);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/repositories/${repositoryId}/pull-requests/${prId}/recommendation`,
        { method: "POST", headers: { Authorization: `Bearer ${session.backendToken}` }, cache: "no-store" }
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        let description = "Veriscope could not generate the recommendation. Please retry or check backend logs.";
        if (
          body?.error_code === "RECOMMENDATION_GENERATION_FAILED" ||
          (body?.detail && (body.detail.includes("Recommendation engine error") || body.detail.includes("UndefinedTable")))
        ) {
          description = "Veriscope could not generate the recommendation. Please retry or check backend logs.";
        } else if (body?.detail || body?.error) {
          description = body?.detail || body?.error;
        }
        toast.error("Recommendation failed", {
          description,
        });
        return;
      }
      toast.success("Recommendation triggered successfully");
      
      // Refetch pull requests to update state before navigating
      await fetchPullRequests();
      
      router.push(`/app/recommendations/${body.recommendation_run_id}`);
    } catch (err: any) {
      toast.error(err?.message || "Failed to create recommendation");
    } finally {
      setRunningRecommendation(null);
    }
  }, [repositoryId, session?.backendToken, router, fetchPullRequests]);

  const getCtaState = () => {
    if (uploading) {
      return {
        text: "Uploading…",
        disabled: true,
        helper: "Uploading coverage report…",
        variant: "State5"
      };
    }
    if (uploadResult) {
      return {
        text: "Upload Succeeded",
        disabled: true,
        helper: "Coverage evidence is now active.",
        variant: "State6"
      };
    }
    if (!format) {
      return {
        text: "Upload Coverage Report",
        disabled: true,
        helper: "Select a coverage format first.",
        variant: "State1"
      };
    }
    if (!file) {
      return {
        text: "Upload Coverage Report",
        disabled: true,
        helper: "Select a coverage file before uploading.",
        variant: "State2"
      };
    }
    if (fileValidationStatus === "INVALID") {
      return {
        text: "Upload Coverage Report",
        disabled: true,
        helper: "Selected file does not match the chosen coverage format.",
        variant: "State3"
      };
    }
    return {
      text: "Upload Coverage Report",
      disabled: false,
      helper: `Ready to upload ${file.name}.`,
      variant: "State4"
    };
  };

  // Fetch repository metadata
  const fetchRepository = useCallback(async () => {
    if (!repositoryId || !session?.backendToken) return;
    
    if (!session?.user) {
      redirect("/login");
      return;
    }

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/github/repositories/${repositoryId}`,
        { headers: { Authorization: `Bearer ${session.backendToken}` }, cache: "no-store" }
      );
      if (!res.ok) {
        setRepo(null);
        return;
      }
      const data = await res.json();
      setRepo(data);
    } catch {
      setRepo(null);
    }
  }, [repositoryId, session?.backendToken, session?.user]);

  // Fetch coverage summary data from our newly created summary endpoint
  const fetchSummary = useCallback(async () => {
    if (!repositoryId || !session?.backendToken) return;
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/repositories/${repositoryId}/coverage/summary`,
        { headers: { Authorization: `Bearer ${session.backendToken}` }, cache: "no-store" }
      );
      if (res.ok) {
        const data = await res.json();
        setSummary(data);
      }
    } catch (err) {
      console.error("Failed to fetch coverage summary", err);
    } finally {
      setLoading(false);
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

  // Fetch data when repositoryId is set
  useEffect(() => {
    if (repositoryId) {
      setLoading(true);
      const searchParamsObj = new URLSearchParams(window.location.search);
      const prId = searchParamsObj.get("pullRequestId");

      const promises: Promise<any>[] = [fetchRepository(), fetchSummary(), fetchPullRequests()];
      if (prId) {
        promises.push(fetchPrDetails(repositoryId, prId));
        promises.push(fetchBeforeReadiness(repositoryId, prId));
      } else {
        promises.push(fetchBeforeReadiness(repositoryId, null));
      }

      Promise.all(promises).then(() => {
        setLoading(false);
      });
    }
  }, [repositoryId, fetchRepository, fetchSummary, fetchPullRequests, fetchPrDetails, fetchBeforeReadiness]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleSelectedFile = useCallback((selectedFile: File) => {
    if (!selectedFile) return;

    if (process.env.NODE_ENV === "development") {
      console.log("[FILE SELECT]", {
        name: selectedFile.name,
        type: selectedFile.type,
        size: selectedFile.size,
        selectedFormat: format
      });
    }

    setFile(selectedFile);
    setError(null);

    // Validate (windows empty MIME type is allowed, so validate extension primarily)
    const validExtensions = format === "LCOV" 
      ? ['.info', '.lcov'] 
      : format === "COBERTURA" 
        ? ['.xml'] 
        : ['.info', '.lcov', '.xml'];
        
    const hasValidExtension = validExtensions.some(ext => selectedFile.name.toLowerCase().endsWith(ext));
    
    let isValid = true;
    let msg = null;

    if (!hasValidExtension) {
      isValid = false;
      msg = "Selected file does not match the chosen coverage format.";
    } else {
      const maxSizeBytes = 10 * 1024 * 1024;
      if (selectedFile.size > maxSizeBytes) {
        isValid = false;
        const sizeMb = (selectedFile.size / (1024 * 1024)).toFixed(2);
        msg = `File is too large (${sizeMb} MB): maximum allowed size is 10 MB.`;
      }
    }

    if (process.env.NODE_ENV === "development") {
      console.log("[VALIDATION RESULT]", { valid: isValid, error: msg });
    }

    if (isValid) {
      setFileValidationStatus("VALID");
      setFileValidationMessage(null);
    } else {
      setFileValidationStatus("INVALID");
      setFileValidationMessage(msg);
    }
  }, [format]);

  const handleFormatChange = (newFormat: string) => {
    if (process.env.NODE_ENV === "development") {
      console.log("[FORMAT SELECT]", newFormat);
    }
    setFormat(newFormat);
    setError(null);

    if (file) {
      // Revalidate same file against new format
      const validExtensions = newFormat === "LCOV" 
        ? ['.info', '.lcov'] 
        : newFormat === "COBERTURA" 
          ? ['.xml'] 
          : ['.info', '.lcov', '.xml'];
          
      const hasValidExtension = validExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
      
      let isValid = true;
      let msg = null;

      if (!hasValidExtension) {
        isValid = false;
        msg = "Selected file does not match the chosen coverage format.";
      } else {
        const maxSizeBytes = 10 * 1024 * 1024;
        if (file.size > maxSizeBytes) {
          isValid = false;
          const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
          msg = `File is too large (${sizeMb} MB): maximum allowed size is 10 MB.`;
        }
      }

      if (process.env.NODE_ENV === "development") {
        console.log("[FORMAT CHANGE REVALIDATION]", { format: newFormat, file: file.name, valid: isValid, error: msg });
      }

      if (isValid) {
        setFileValidationStatus("VALID");
        setFileValidationMessage(null);
      } else {
        setFileValidationStatus("INVALID");
        setFileValidationMessage(msg);
      }
    } else {
      setFileValidationStatus(null);
      setFileValidationMessage(null);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      handleSelectedFile(droppedFile);
    }
  }, [handleSelectedFile]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      handleSelectedFile(selectedFile);
    }
  };

  const handleUpload = async () => {
    if (!file || !format || fileValidationStatus !== "VALID" || !repositoryId || !session?.backendToken) return;

    setUploading(true);
    setError(null);
    setUploadResult(null);

    if (process.env.NODE_ENV === "development") {
      console.log("[UPLOAD SUBMIT]", {
        format,
        fileName: file.name,
        endpoint: `/api/repositories/${repositoryId}/coverage/upload`
      });
    }

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("format", format);
      formData.append("commit_sha", commitSha || "");
      formData.append("branch", branch || "");
      formData.append("source", "MANUAL_UPLOAD");
      if (pullRequestId) formData.append("pull_request_id", pullRequestId);
      if (sourceParam) formData.append("source_context", sourceParam);

      const res = await fetch(
        `/api/repositories/${repositoryId}/coverage/upload`,
        { method: "POST", body: formData }
      );

      let data;
      try {
        data = await res.json();
      } catch {
        data = {};
      }

      if (!res.ok) {
        let errorMessage = "Veriscope could not reach the backend. Please retry.";
        let toastTitle = "Backend unavailable";
        let toastDescription = "Veriscope could not reach the backend. Please retry.";

        const errDetail = (data.error || data.detail || "").toLowerCase();

        if (res.status === 400) {
          if (errDetail.includes("unsupported format") || errDetail.includes("unsupported coverage format")) {
            errorMessage = "Choose LCOV or Cobertura before uploading.";
            toastTitle = "Unsupported format";
            toastDescription = "Choose LCOV or Cobertura before uploading.";
          } else if (errDetail.includes("test history") || errDetail.includes("test-history") || errDetail.includes("missing test") || errDetail.includes("junit")) {
            errorMessage = "Upload test history before coverage to make this repository recommendation-ready.";
            toastTitle = "Missing test history";
            toastDescription = "Upload test history before coverage to make this repository recommendation-ready.";
          } else if (errDetail.includes("parse") || errDetail.includes("invalid") || errDetail.includes("malformed") || errDetail.includes("content")) {
            errorMessage = data.error || data.detail || "Veriscope could not parse this coverage report.";
            toastTitle = "Invalid coverage content";
            toastDescription = errorMessage;
          } else if (errDetail.includes("duplicate") || errDetail.includes("already") || errDetail.includes("conflict")) {
            errorMessage = "This coverage report appears to have already been uploaded.";
            toastTitle = "Duplicate artifact";
            toastDescription = "This coverage report appears to have already been uploaded.";
          } else if (errDetail.includes("selected") || errDetail.includes("enable") || errDetail.includes("workspace")) {
            errorMessage = "Enable this repository before uploading coverage evidence.";
            toastTitle = "Repository not selected";
            toastDescription = "Enable this repository before uploading coverage evidence.";
          } else {
            errorMessage = data.error || data.detail || "Veriscope could not reach the backend. Please retry.";
            toastTitle = "Upload failed";
            toastDescription = errorMessage;
          }
        } else if (res.status === 409) {
          errorMessage = "This coverage report appears to have already been uploaded.";
          toastTitle = "Duplicate artifact";
          toastDescription = "This coverage report appears to have already been uploaded.";
        } else if (res.status === 422) {
          errorMessage = "Veriscope could not parse this coverage report.";
          toastTitle = "Invalid coverage content";
          toastDescription = "Veriscope could not parse this coverage report.";
        } else if (res.status >= 500) {
          errorMessage = "Veriscope could not reach the backend. Please retry.";
          toastTitle = "Backend unavailable";
          toastDescription = "Veriscope could not reach the backend. Please retry.";
        }

        setError(errorMessage);
        toast.error(toastTitle, {
          description: toastDescription
        });
        
        console.warn("Coverage upload error:", {
          status: res.status,
          detail: data.error || data.detail,
          timestamp: new Date().toISOString()
        });
        return;
      }

      setUploadResult(data);
      setFile(null);
      setCommitSha("");
      setBranch("");
      setFileValidationStatus(null);
      setFileValidationMessage(null);
      
      toast.success("Upload successful", {
        description: `Successfully ingested ${data.files_total} files (${data.covered_lines_total} lines covered)`
      });
      
      if (data.repository_readiness && repo) {
        setRepo({
          ...repo,
          readiness_state: data.repository_readiness.readiness_state
        });
      }
      
      fetchSummary();
      fetchPullRequests();
    } catch (err: any) {
      const errorMessage = "Veriscope could not reach the backend. Please retry.";
      setError(errorMessage);
      toast.error("Backend unavailable", {
        description: "Veriscope could not reach the backend. Please retry."
      });
      
      console.warn("Coverage upload network error:", {
        error: err?.message,
        timestamp: new Date().toISOString()
      });
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 max-w-5xl">
        <div className="flex items-center gap-4 animate-pulse">
          <div className="h-8 w-8 bg-zinc-800 rounded-lg" />
          <div className="h-6 w-48 bg-zinc-800 rounded-lg" />
        </div>
        <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-4 animate-pulse">
          <div className="h-4 w-64 bg-zinc-800 rounded" />
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-6">
            <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-6 h-40 animate-pulse" />
            <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-6 h-60 animate-pulse" />
          </div>
          <div className="space-y-6">
            <div className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-6 h-80 animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  if (!repo) {
    return (
      <div className="space-y-6 max-w-5xl">
        <div className="flex items-center gap-4">
          <Link href="/app/repositories">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white">Repository Not Found</h1>
            <p className="text-sm text-zinc-500">The repository does not exist or you don't have access</p>
          </div>
        </div>
      </div>
    );
  }

  const cta = getCtaState();

  return (
    <div className="space-y-6 max-w-6xl text-zinc-200">
      
      {/* 1. Header */}
      <div className="flex items-start gap-4">
        <Link href={getBackHref()}>
          <Button variant="ghost" size="icon" className="h-10 w-10 border border-zinc-800/80 bg-zinc-900/50 hover:bg-zinc-800 text-zinc-400 hover:text-white rounded-xl">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400 px-2 py-0.5 rounded bg-emerald-950/40 border border-emerald-900/50">
              Repository
            </span>
            <span className="text-sm text-zinc-500 font-mono truncate">{repo.full_name}</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            {pullRequestId && prNumber 
              ? `Upload coverage for PR #${prNumber}` 
              : "Coverage Evidence"}
          </h1>
          {pullRequestId && prNumber && (
            <div className="mt-2 text-xs text-indigo-400 bg-indigo-950/20 border border-indigo-900/30 rounded-lg p-2.5 max-w-3xl">
              PR context detected. Veriscope will automatically associate this upload with PR #{prNumber} and its head commit.
            </div>
          )}
        </div>
      </div>

      <p className="text-sm text-zinc-400 max-w-3xl">
        Upload coverage reports so Veriscope can map changed files to tested code paths and improve recommendation confidence.
      </p>

      {/* 2. Readiness banner */}
      {repo.readiness_state === "NEEDS_COVERAGE" ? (
        <div className="bg-amber-950/20 border border-amber-900/40 rounded-xl p-4 flex items-start gap-3.5 shadow-lg shadow-amber-950/5">
          <div className="w-8 h-8 rounded-lg bg-amber-950/60 border border-amber-900/60 flex items-center justify-center shrink-0 text-amber-400">
            <AlertTriangle className="w-4.5 h-4.5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-amber-200">Coverage evidence recommended</p>
            <p className="text-xs text-amber-300/80 mt-1 leading-relaxed">
              Coverage helps Veriscope connect code changes to tested paths. Without it, recommendations remain conservative.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-emerald-950/25 border border-emerald-900/40 rounded-xl p-4 flex items-start gap-3.5 shadow-lg shadow-emerald-950/5">
          <div className="w-8 h-8 rounded-lg bg-emerald-950/60 border border-emerald-900/60 flex items-center justify-center shrink-0 text-emerald-400">
            <ShieldCheck className="w-4.5 h-4.5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-emerald-200">Coverage evidence active</p>
            <p className="text-xs text-emerald-300/80 mt-1 leading-relaxed">
              Veriscope has active coverage evidence for this repository. Recommendations leverage precise direct and heuristic mappings.
            </p>
          </div>
        </div>
      )}

      {/* Main Grid Layout */}
      <div className="grid md:grid-cols-3 gap-6">
        
        {/* Left Column: Form & Interaction Cards */}
        <div className="md:col-span-2 space-y-6">
          {uploadResult ? (
            /* Premium Success Panel */
            <div className="bg-zinc-950/40 border border-zinc-800/80 rounded-2xl p-6 shadow-xl backdrop-blur-md space-y-6">
              
              {/* Success title */}
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-emerald-950/80 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0 shadow-lg shadow-emerald-950/20">
                  <CheckCircle className="w-5 h-5 animate-pulse" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white tracking-tight">Coverage evidence uploaded</h3>
                  <p className="text-xs text-zinc-400 mt-0.5">The coverage report has been successfully parsed and normalized.</p>
                </div>
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
                          Coverage Report: <span className="text-zinc-500 line-through">Missing</span> <span className="text-emerald-400">→ Available</span>
                        </li>
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {/* Summary cards */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 p-4 bg-zinc-900/15 border border-zinc-850 rounded-xl">
                <div className="bg-zinc-900/20 border border-zinc-850/65 p-3 rounded-lg flex flex-col justify-between">
                  <p className="text-xxs uppercase tracking-wider text-zinc-500 mb-1">Files Parsed</p>
                  <p className="text-lg font-bold text-zinc-100">{uploadResult.files_total}</p>
                </div>
                <div className="bg-zinc-900/20 border border-zinc-850/65 p-3 rounded-lg flex flex-col justify-between">
                  <p className="text-xxs uppercase tracking-wider text-zinc-500 mb-1">Covered Lines</p>
                  <p className="text-lg font-bold text-emerald-400">{uploadResult.covered_lines_total}</p>
                </div>
                <div className="bg-zinc-900/20 border border-zinc-850/65 p-3 rounded-lg flex flex-col justify-between">
                  <p className="text-xxs uppercase tracking-wider text-zinc-500 mb-1">Uncovered Lines</p>
                  <p className="text-lg font-bold text-rose-450">{uploadResult.uncovered_lines_total}</p>
                </div>
                <div className="bg-zinc-900/20 border border-zinc-850/65 p-3 rounded-lg flex flex-col justify-between">
                  <p className="text-xxs uppercase tracking-wider text-zinc-500 mb-1">Coverage Confidence</p>
                  <p className={`text-lg font-bold ${
                    uploadResult.coverage_confidence === "HIGH" ? "text-emerald-400" :
                    uploadResult.coverage_confidence === "MODERATE" ? "text-amber-400" :
                    "text-rose-400"
                  }`}>
                    {uploadResult.coverage_confidence}
                  </p>
                </div>
                <div className="bg-zinc-900/20 border border-zinc-850/65 p-3 rounded-lg flex flex-col justify-between">
                  <p className="text-xxs uppercase tracking-wider text-zinc-500 mb-1">Format</p>
                  <p className="text-lg font-bold text-zinc-100">{uploadResult.format}</p>
                </div>
                <div className="bg-zinc-900/20 border border-zinc-850/65 p-3 rounded-lg flex flex-col justify-between">
                  <p className="text-xxs uppercase tracking-wider text-zinc-500 mb-1">Evidence Health</p>
                  <p className={`text-lg font-bold ${
                    (uploadResult.evidence_health_status || "HEALTHY") === "HEALTHY" ? "text-emerald-400" :
                    (uploadResult.evidence_health_status || "HEALTHY") === "STALE" ? "text-amber-400" :
                    "text-rose-400"
                  }`}>
                    {uploadResult.evidence_health_status || "HEALTHY"}
                  </p>
                </div>
              </div>

              {/* Technical metadata */}
              <div className="p-4 bg-zinc-900/10 border border-zinc-850 rounded-xl space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-zinc-500" />
                  Technical Metadata
                </h4>
                <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2.5 text-xs">
                  <div className="flex justify-between items-center py-1 border-b border-zinc-900/60">
                    <span className="text-zinc-500 font-medium">Parser Version</span>
                    <span className="font-mono text-zinc-300 font-medium">{uploadResult.parser_version}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-zinc-900/60">
                    <span className="text-zinc-500 font-medium">Normalization Schema</span>
                    <span className="font-mono text-zinc-300 font-medium">{uploadResult.normalization_schema_version}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-zinc-900/60">
                    <span className="text-zinc-500 font-medium">Source</span>
                    <span className="text-zinc-300 font-medium">Manual upload</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-zinc-900/60">
                    <span className="text-zinc-500 font-medium">Report Hash</span>
                    <span className="font-mono text-zinc-300 font-medium">{(uploadResult.coverage_report_id || "").slice(0, 8)}</span>
                  </div>
                </div>
              </div>

              {/* Readiness transition */}
              <div className="p-4 bg-zinc-900/10 border border-zinc-850 rounded-xl flex items-start gap-3">
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                  uploadResult.repository_readiness?.readiness_state === "READY" 
                    ? (uploadResult.coverage_confidence === "LOW" ? "bg-amber-950/40 text-amber-400 border border-amber-900/50" : "bg-emerald-950/40 text-emerald-400 border border-emerald-900/50")
                    : "bg-zinc-900 text-zinc-400 border border-zinc-800"
                }`}>
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1">Readiness Transition</h4>
                  {uploadResult.repository_readiness?.readiness_state === "READY" ? (
                    uploadResult.coverage_confidence === "LOW" ? (
                      <p className="text-sm font-semibold text-amber-300 leading-normal">
                        Repository readiness updated with low coverage confidence
                      </p>
                    ) : (
                      <p className="text-sm font-semibold text-emerald-300 leading-normal">
                        Repository readiness updated to READY
                      </p>
                    )
                  ) : (
                    <p className="text-sm font-semibold text-zinc-300 leading-normal">
                      Repository readiness: {uploadResult.repository_readiness?.readiness_state}
                    </p>
                  )}
                </div>
              </div>

              {/* Next actions */}
              <div className="pt-4 border-t border-zinc-900/80 space-y-4">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-455">Next Steps</h4>
                
                {uploadResult.repository_readiness?.readiness_state === "READY" && pullRequests.length > 0 ? (
                  <div className="space-y-4">
                    <div className="p-4 bg-emerald-950/5 border border-emerald-900/30 rounded-xl space-y-3">
                      <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4 text-emerald-400" />
                        Run PR Recommendation
                      </span>
                      <p className="text-xs text-zinc-400 leading-normal font-medium">
                        Ingested coverage successfully mapped code statements to tests. Select an active pull request to run recommendations.
                      </p>
                      <div className="space-y-2">
                        {pullRequests.slice(0, 3).map(pr => (
                          <div key={pr.id} className="flex items-center justify-between p-3 bg-zinc-900/40 border border-zinc-850/80 rounded-xl text-xs gap-4 hover:border-zinc-850/100 transition-colors">
                            <div className="min-w-0">
                              <p className="font-semibold text-zinc-200 truncate">#{pr.number} - {pr.title}</p>
                              <div className="flex items-center gap-2 text-xxs text-zinc-500 mt-0.5 flex-wrap">
                                <span>{pr.changed_files_count} files changed • {pr.source_branch}</span>
                                {pr.recommendation_status === "GENERATED" && pr.latest_recommendation_at && (
                                  <>
                                    <span>•</span>
                                    <span className="text-emerald-400 font-medium">
                                      Recommended {formatRelativeTime(pr.latest_recommendation_at)}
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              {pr.recommendation_status === "GENERATED" && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  disabled={runningRecommendation !== null}
                                  onClick={() => triggerRecommendation(pr.id)}
                                  className="text-zinc-400 hover:text-white shrink-0 font-semibold text-xs border-none"
                                >
                                  <RefreshCw className="w-3.5 h-3.5 mr-1" />
                                  Re-run
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant={pr.recommendation_status === "GENERATED" ? "outline" : "default"}
                                onClick={() => {
                                  if (pr.recommendation_status === "GENERATED" && pr.latest_recommendation_run_id) {
                                    router.push(`/app/recommendations/${pr.latest_recommendation_run_id}`);
                                  } else {
                                    triggerRecommendation(pr.id);
                                  }
                                }}
                                disabled={runningRecommendation === pr.id}
                                className={`shrink-0 font-semibold text-xs ${
                                  pr.recommendation_status === "GENERATED" 
                                    ? "border-zinc-800 text-zinc-400 hover:text-white" 
                                    : "bg-emerald-500 text-zinc-950 hover:bg-emerald-400 border-none"
                                }`}
                              >
                                {runningRecommendation === pr.id ? (
                                  <>
                                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                    Generating...
                                  </>
                                ) : pr.recommendation_status === "GENERATED" ? (
                                  <>
                                    <Sparkles className="w-3 h-3 mr-1" />
                                    View Recommendation
                                  </>
                                ) : pr.recommendation_status === "FAILED" ? (
                                  <>
                                    <Play className="w-3 h-3 mr-1" />
                                    Retry Recommendation
                                  </>
                                ) : (
                                  <>
                                    <Play className="w-3 h-3 mr-1" />
                                    Run Recommendation
                                  </>
                                )}
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    
                    <div className="flex justify-end gap-2">
                      <Link href={returnTo === "readiness"
                        ? `/app/repositories/${repositoryId}?openReadiness=true${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}`
                        : `/app/repositories/${repositoryId}`
                      } className="w-full sm:w-auto">
                        <Button variant="outline" className="w-full sm:w-auto border-zinc-800 hover:bg-zinc-850 hover:text-white text-zinc-300 rounded-xl font-semibold">
                          {returnTo === "readiness" ? "Back to Readiness" : "View Repository Readiness"}
                        </Button>
                      </Link>
                    </div>
                  </div>
                ) : uploadResult.repository_readiness?.readiness_state === "READY" ? (
                  <div className="p-4 bg-zinc-900/10 border border-zinc-850 rounded-xl space-y-4">
                    <div className="space-y-1">
                      <h5 className="text-xs font-semibold text-zinc-200">No active pull requests found</h5>
                      <p className="text-xs text-zinc-400 leading-normal">
                        Open or update a pull request in GitHub to run a recommendation.
                      </p>
                    </div>
                    <div className="flex justify-start gap-2">
                      <Link href={returnTo === "readiness"
                        ? `/app/repositories/${repositoryId}?openReadiness=true${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}`
                        : `/app/repositories/${repositoryId}`
                      } className="w-full sm:w-auto">
                        <Button className="w-full sm:w-auto bg-white text-zinc-950 hover:bg-zinc-100 font-semibold rounded-xl">
                          {returnTo === "readiness" ? "Back to Readiness" : "View Repository Readiness"}
                        </Button>
                      </Link>
                    </div>
                  </div>
                ) : uploadResult.repository_readiness?.readiness_state === "NEEDS_TEST_HISTORY" ? (
                  <div className="p-4 bg-zinc-900/10 border border-zinc-850 rounded-xl space-y-4">
                    <div className="space-y-1">
                      <h5 className="text-xs font-semibold text-zinc-200">Test history required</h5>
                      <p className="text-xs text-zinc-400 leading-normal">
                        Veriscope has coverage mapping data but needs JUnit test results history to calculate recommendable test priorities.
                      </p>
                    </div>
                    <div className="flex justify-start gap-2">
                      <Link href={`/app/repositories/${repositoryId}/test-history${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}${returnTo ? `&returnTo=${returnTo}` : ""}${sourceParam ? `&source=${sourceParam}` : ""}`} className="w-full sm:w-auto">
                        <Button className="w-full sm:w-auto bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-xl">
                          Upload Test Results
                        </Button>
                      </Link>
                      <Link href={returnTo === "readiness"
                        ? `/app/repositories/${repositoryId}?openReadiness=true${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}`
                        : `/app/repositories/${repositoryId}`
                      } className="w-full sm:w-auto">
                        <Button variant="outline" className="w-full sm:w-auto border-zinc-850 text-zinc-300 hover:bg-zinc-900 font-semibold rounded-xl">
                          {returnTo === "readiness" ? "Back to Readiness" : "View Repository Readiness"}
                        </Button>
                      </Link>
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-start gap-2">
                    <Link href={returnTo === "readiness"
                      ? `/app/repositories/${repositoryId}?openReadiness=true${pullRequestId ? `&pullRequestId=${pullRequestId}` : ""}`
                      : `/app/repositories/${repositoryId}`
                    } className="w-full sm:w-auto">
                      <Button className="w-full sm:w-auto bg-white text-zinc-950 hover:bg-zinc-100 font-semibold rounded-xl">
                        {returnTo === "readiness" ? "Back to Readiness" : "View Repository Readiness"}
                      </Button>
                    </Link>
                  </div>
                )}
              </div>

              {/* Reset/Retry micro-action */}
              <div className="flex justify-center pt-2 border-t border-zinc-900/40">
                <button
                  type="button"
                  onClick={() => {
                    setUploadResult(null);
                    setFile(null);
                    setError(null);
                  }}
                  className="text-xs text-zinc-500 hover:text-zinc-350 underline underline-offset-4 transition-colors font-medium cursor-pointer"
                >
                  Upload another report
                </button>
              </div>

            </div>
          ) : (
            <>
              {/* 4. Format selector */}
              <div className="bg-zinc-950/40 border border-zinc-800/80 rounded-2xl p-6 shadow-xl backdrop-blur-md">
                <h3 className="text-sm font-semibold text-zinc-300 mb-4 flex items-center gap-2">
                  <Code className="w-4.5 h-4.5 text-zinc-400" />
                  1. Select Coverage Format
                </h3>
                <div className="flex gap-4">
                  <button
                    type="button"
                    onClick={() => handleFormatChange("LCOV")}
                    className={`flex-1 p-4 rounded-xl border text-left transition-all ${
                      format === "LCOV"
                        ? "border-emerald-400/60 bg-emerald-950/15 shadow-md shadow-emerald-950/10"
                        : "border-zinc-800/80 bg-zinc-900/20 hover:border-zinc-700 hover:bg-zinc-900/40"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg ${format === "LCOV" ? "bg-emerald-900/40" : "bg-zinc-800/40"} shrink-0`}>
                        <FileText className={`w-5 h-5 ${format === "LCOV" ? "text-emerald-400" : "text-zinc-400"}`} />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-zinc-100">LCOV format</p>
                        <p className="text-xs text-zinc-500 mt-0.5">Parsed via SF/DA metrics (.info, .lcov)</p>
                      </div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleFormatChange("COBERTURA")}
                    className={`flex-1 p-4 rounded-xl border text-left transition-all ${
                      format === "COBERTURA"
                        ? "border-emerald-400/60 bg-emerald-950/15 shadow-md shadow-emerald-950/10"
                        : "border-zinc-800/80 bg-zinc-900/20 hover:border-zinc-700 hover:bg-zinc-900/40"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg ${format === "COBERTURA" ? "bg-emerald-900/40" : "bg-zinc-800/40"} shrink-0`}>
                        <FileText className={`w-5 h-5 ${format === "COBERTURA" ? "text-emerald-400" : "text-zinc-400"}`} />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-zinc-100">Cobertura format</p>
                        <p className="text-xs text-zinc-500 mt-0.5">Parsed via safe XML structure (.xml)</p>
                      </div>
                    </div>
                  </button>
                </div>
              </div>

              {/* 5. Upload card */}
              <div className="bg-zinc-950/40 border border-zinc-800/80 rounded-2xl p-6 shadow-xl backdrop-blur-md space-y-6">
                <h3 className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
                  <Upload className="w-4.5 h-4.5 text-zinc-400" />
                  2. Upload Coverage Report
                </h3>
                
                <div 
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  onClick={(e) => {
                    const target = e.target as HTMLElement;
                    if (target.closest("button") || target.closest("a") || target.closest("input")) {
                      return;
                    }
                    fileInputRef.current?.click();
                  }}
                  className={`border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
                    dragActive 
                      ? "border-emerald-400/80 bg-emerald-950/15" 
                      : "border-zinc-800 hover:border-zinc-700 bg-zinc-900/10 hover:bg-zinc-900/25"
                  }`}
                >
                  <div className="w-10 h-10 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-3 text-zinc-400">
                    <BarChart2 className="w-5 h-5" />
                  </div>
                  <p className="text-sm font-semibold text-zinc-100 mb-1">
                    Drag & drop your {format || "coverage"} file here
                  </p>
                  <p className="text-xs text-zinc-500 mb-4 max-w-sm mx-auto">
                    Or browse from your local disk. Maximum upload size is 10 MB.
                  </p>

                  <input
                    type="file"
                    id="file-select"
                    ref={fileInputRef}
                    accept={
                      format === "LCOV" 
                        ? ".info,.lcov,text/plain,application/octet-stream" 
                        : format === "COBERTURA" 
                          ? ".xml,text/xml,application/xml" 
                          : ".info,.lcov,.xml,text/xml,application/xml"
                    }
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  <Button 
                    type="button"
                    variant="outline" 
                    size="sm" 
                    onClick={() => fileInputRef.current?.click()}
                    className="border-zinc-850 hover:bg-zinc-805 hover:text-white cursor-pointer bg-zinc-900/40 font-semibold"
                  >
                    Select Coverage File
                  </Button>

                  {file && (
                    <div className="mt-4 p-4 bg-zinc-900/40 border border-zinc-800/80 rounded-xl max-w-md mx-auto space-y-3 text-left">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <FileText className={`w-5 h-5 ${fileValidationStatus === "VALID" ? "text-emerald-400" : "text-rose-450"} shrink-0`} />
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-zinc-300">Selected file:</p>
                            <p className="text-xs font-mono text-zinc-100 truncate mt-0.5">{file.name}</p>
                          </div>
                        </div>
                        <button 
                          type="button" 
                          onClick={() => {
                            setFile(null);
                            setFileValidationStatus(null);
                            setFileValidationMessage(null);
                          }} 
                          className="text-zinc-500 hover:text-zinc-300 p-1 rounded-lg hover:bg-zinc-800 transition-colors"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-3 text-xxs border-t border-zinc-900 pt-2.5">
                        <div>
                          <p className="text-zinc-500 font-medium">Size:</p>
                          <p className="text-zinc-300 mt-0.5">{formatBytes(file.size)}</p>
                        </div>
                        <div>
                          <p className="text-zinc-500 font-medium">Format:</p>
                          <p className="text-zinc-300 mt-0.5">{format === "LCOV" ? "LCOV" : format === "COBERTURA" ? "Cobertura" : "None"}</p>
                        </div>
                        <div className="col-span-2">
                          <p className="text-zinc-500 font-medium">Status:</p>
                          <p className={`font-semibold mt-0.5 ${fileValidationStatus === "VALID" ? "text-emerald-400" : "text-rose-400"}`}>
                            {fileValidationStatus === "VALID" ? "Ready to upload" : "Invalid format"}
                          </p>
                        </div>
                      </div>

                      <div className="flex justify-end gap-2 pt-1">
                        <Button 
                          type="button"
                          variant="ghost" 
                          size="sm"
                          onClick={() => fileInputRef.current?.click()}
                          className="h-7 text-xxs text-zinc-400 hover:text-white border border-zinc-850 hover:bg-zinc-800 rounded-lg px-2.5 font-semibold"
                        >
                          Change file
                        </Button>
                        <Button 
                          type="button"
                          variant="ghost" 
                          size="sm"
                          onClick={() => {
                            setFile(null);
                            setFileValidationStatus(null);
                            setFileValidationMessage(null);
                          }}
                          className="h-7 text-xxs text-rose-400 hover:text-rose-300 hover:bg-rose-950/20 rounded-lg px-2.5 font-semibold"
                        >
                          Remove
                        </Button>
                      </div>
                    </div>
                  )}
                </div>

                {/* 6. Optional metadata */}
                <div className="pt-4 border-t border-zinc-900 space-y-4">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Optional Metadata
                  </h4>
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-zinc-500 mb-1.5">Commit SHA</label>
                      <input
                        type="text"
                        value={commitSha}
                        onChange={(e) => setCommitSha(e.target.value)}
                        placeholder="e.g. 5fa7ab81..."
                        className="w-full bg-zinc-900/30 border border-zinc-850 rounded-xl px-3.5 py-2.5 text-xs text-zinc-250 placeholder-zinc-600 focus:outline-none focus:border-zinc-700 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-zinc-500 mb-1.5">Target Branch</label>
                      <input
                        type="text"
                        value={branch}
                        onChange={(e) => setBranch(e.target.value)}
                        placeholder="e.g. main"
                        className="w-full bg-zinc-900/30 border border-zinc-850 rounded-xl px-3.5 py-2.5 text-xs text-zinc-250 placeholder-zinc-600 focus:outline-none focus:border-zinc-700"
                      />
                    </div>
                  </div>
                </div>

                {/* Error messaging inside form */}
                {error && (
                  <div className="p-3.5 bg-rose-950/25 border border-rose-900/50 rounded-xl flex items-start gap-2.5 text-rose-300 text-xs">
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span className="leading-normal flex-1">{error}</span>
                    <button type="button" onClick={() => setError(null)} className="text-rose-500 hover:text-rose-300">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}

                {/* CTA action button and deterministic helper */}
                <div className="flex flex-col gap-3 pt-2">
                  <div className="flex justify-end">
                    <Button
                      onClick={handleUpload}
                      disabled={cta.disabled}
                      className={`w-full sm:w-auto px-6 py-2.5 font-semibold rounded-xl transition-all ${
                        cta.disabled 
                          ? "bg-zinc-800 text-zinc-500 cursor-not-allowed" 
                          : "bg-emerald-500 text-zinc-950 hover:bg-emerald-400"
                      }`}
                    >
                      {uploading && <span className="w-3.5 h-3.5 border-2 border-zinc-950 border-t-transparent rounded-full animate-spin mr-2 inline-block shrink-0" />}
                      {cta.text}
                    </Button>
                  </div>
                  <p className={`text-xxs text-right font-medium tracking-wide ${
                    cta.variant === "State1" || cta.variant === "State2" ? "text-zinc-500" :
                    cta.variant === "State3" || cta.variant === "State7" ? "text-rose-450 font-semibold" :
                    cta.variant === "State4" ? "text-emerald-400 font-semibold animate-pulse" :
                    "text-zinc-400"
                  }`}>
                    {cta.helper}
                  </p>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Right Column: Reference info cards */}
        <div className="space-y-6">
          
          {/* 7. Current evidence summary */}
          <div className="bg-zinc-950/40 border border-zinc-800/80 rounded-2xl p-6 shadow-xl backdrop-blur-md space-y-4">
            <h3 className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
              <Database className="w-4.5 h-4.5 text-zinc-400" />
              Coverage Evidence
            </h3>
            
            <div className="space-y-4 text-xs">
              <div className="flex justify-between items-center py-2.5 border-b border-zinc-900">
                <span className="text-zinc-500 font-medium">Coverage Reports Count</span>
                <span className="font-bold text-zinc-200">{summary?.coverage_reports_count ?? 0}</span>
              </div>

              <div className="flex justify-between items-center py-2.5 border-b border-zinc-900">
                <span className="text-zinc-500 font-medium flex items-center gap-1"><Calendar className="w-3.5 h-3.5" /> Latest Upload</span>
                <span className="font-semibold text-zinc-350">
                  {summary?.latest_coverage_at 
                    ? new Date(summary.latest_coverage_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      }) 
                    : "No uploads"}
                </span>
              </div>

              <div className="flex justify-between items-center py-2.5 border-b border-zinc-900">
                <span className="text-zinc-500 font-medium">Latest Scored Confidence</span>
                <span className={`font-bold ${
                  summary?.latest_report?.coverage_confidence === "HIGH" ? "text-emerald-400" :
                  summary?.latest_report?.coverage_confidence === "MODERATE" ? "text-amber-400" :
                  summary?.latest_report?.coverage_confidence === "LOW" ? "text-rose-400/80" :
                  "text-zinc-500"
                }`}>
                  {summary?.latest_report?.coverage_confidence ?? "N/A"}
                </span>
              </div>

              <div className="flex justify-between items-center py-2.5">
                <span className="text-zinc-500 font-medium">Active Normalizer Format</span>
                <span className="font-bold text-zinc-250 font-mono">
                  {summary?.latest_report?.format ?? "None"}
                </span>
              </div>
            </div>
          </div>

          {/* 3. How to get this file card */}
          <div className="bg-zinc-950/40 border border-zinc-800/80 rounded-2xl p-6 shadow-xl backdrop-blur-md space-y-4">
            <h3 className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
              <Info className="w-4.5 h-4.5 text-zinc-400" />
              How to generate reports
            </h3>
            <p className="text-xs text-zinc-500 leading-relaxed">
              Export coverage reports in standard Cobertura XML or LCOV formats using your development stack:
            </p>

            <div className="space-y-3.5">
              <div className="p-3 bg-zinc-900/15 border border-zinc-850 rounded-xl space-y-1">
                <p className="text-xs font-semibold text-zinc-300">Jest / Istanbul</p>
                <code className="block text-xxs font-mono text-emerald-400/90 bg-zinc-950/40 p-1.5 rounded leading-relaxed overflow-x-auto">
                  jest --coverage
                </code>
                <span className="block text-xxs text-zinc-500 mt-1">Outputs coverage/lcov.info</span>
              </div>

              <div className="p-3 bg-zinc-900/15 border border-zinc-850 rounded-xl space-y-1">
                <p className="text-xs font-semibold text-zinc-300">Pytest (coverage.py)</p>
                <code className="block text-xxs font-mono text-emerald-400/90 bg-zinc-950/40 p-1.5 rounded leading-relaxed overflow-x-auto">
                  pytest --cov=. --cov-report=xml
                </code>
                <span className="block text-xxs text-zinc-500 mt-1">Outputs coverage.xml</span>
              </div>

              <div className="p-3 bg-zinc-900/15 border border-zinc-850 rounded-xl space-y-1">
                <p className="text-xs font-semibold text-zinc-300">Maven JaCoCo</p>
                <code className="block text-xxs font-mono text-emerald-400/90 bg-zinc-950/40 p-1.5 rounded leading-relaxed overflow-x-auto">
                  mvn jacoco:report
                </code>
                <span className="block text-xxs text-zinc-500 mt-1">Outputs target/site/jacoco/jacoco.xml</span>
              </div>

              <div className="p-3 bg-zinc-900/15 border border-zinc-850 rounded-xl space-y-1">
                <p className="text-xs font-semibold text-zinc-300">Gradle JaCoCo</p>
                <code className="block text-xxs font-mono text-emerald-400/90 bg-zinc-950/40 p-1.5 rounded leading-relaxed overflow-x-auto">
                  ./gradlew jacocoTestReport
                </code>
                <span className="block text-xxs text-zinc-500 mt-1">Outputs build/reports/jacoco/...xml</span>
              </div>

              <div className="p-3 bg-zinc-900/10 border border-zinc-850/50 rounded-xl">
                <p className="text-xs font-semibold text-zinc-400">CI Artifacts</p>
                <p className="text-xxs text-zinc-500 mt-1 leading-normal">
                  Configure your CI pipelines to build code coverage and download LCOV or Cobertura XML outputs from your pipeline artifacts list.
                </p>
              </div>
            </div>
          </div>

        </div>

      </div>

    </div>
  );
}
