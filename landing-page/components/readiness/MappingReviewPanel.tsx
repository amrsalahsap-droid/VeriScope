"use client";

import React, { useState, useEffect, useCallback } from "react";
import { 
  CheckCircle, 
  XCircle, 
  Clock, 
  AlertTriangle, 
  Eye, 
  Plus,
  Search,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  ShieldAlert,
  Link as LinkIcon,
  ArrowRight
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

// Types
export interface SuggestedTest {
  edge_id?: string;
  candidate_id?: string;
  test_case_id?: string;
  stable_test_id: string;
  test_name: string;
  test_title?: string;
  suite_name?: string;
  classname?: string;
  declared_ac_ref?: string | null;
  declared_ac_text?: string | null;
  semantic_best_match_ac_ref?: string | null;
  semantic_best_match_ac_id?: string | null;
  semantic_best_match_ac_text?: string | null;
  semantic_best_match_score?: number;
  flow_from_test?: string | null;
  flow_from_declared_ac?: string | null;
  flow_from_semantic_match?: string | null;
  confidence: number;
  confidence_score?: number;
  confidence_label?: string;
  edge_source: string;
  candidate_source?: string;
  review_status: string;
  evidence: string[];
  reason: string;
  conflict_detected?: boolean;
  conflict_type?: string | null;
  conflict_reason?: string | null;
  semantic_match_accept_allowed?: boolean;
  audit_metadata?: Record<string, any>; 
}

export interface ACTestMappingGroup {
  ac_id?: string | null;
  stable_ac_key: string;
  display_ac_ref?: string | null;
  ac_title: string;
  ac_text: string;
  requirement_group: string;
  business_flow?: string | null;
  status: string;
  row_status?: string | null;
  has_conflict?: boolean;
  suggested_tests_count?: number;
  suggested_tests: SuggestedTest[];
  debug?: {
    stable_ac_key?: string;
    raw_edge_ids?: string[];
    [key: string]: any;
  };
}

interface MappingReviewPanelProps {
  repositoryId: string;
  pullRequestId: string;
  isOpen: boolean;
  onClose: () => void;
  onMappingUpdate?: () => void;
}

export function MappingReviewPanel({
  repositoryId,
  pullRequestId,
  isOpen,
  onClose,
  onMappingUpdate
}: MappingReviewPanelProps) {
  const [mappings, setMappings] = useState<ACTestMappingGroup[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [expandedACs, setExpandedACs] = useState<Set<string>>(new Set());
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  // Warning Modal State for Keep Declared AC Anyway
  const [warningModalTarget, setWarningModalTarget] = useState<SuggestedTest | null>(null);
  const [warningAcknowledged, setWarningAcknowledged] = useState(false);
  const [warningComment, setWarningComment] = useState("");

  // Comment Modal State
  const [commentModalTarget, setCommentModalTarget] = useState<SuggestedTest | null>(null);
  const [commentText, setCommentText] = useState("");

  // Manual Link Modal State
  const [manualLinkTarget, setManualLinkTarget] = useState<{ test: SuggestedTest; ac: ACTestMappingGroup } | null>(null);
  const [manualLinkTargetAcId, setManualLinkTargetAcId] = useState<string | null>(null);
  const [manualLinkReason, setManualLinkReason] = useState("");

  // Accepted Gap Modal State
  const [acceptedGapTarget, setAcceptedGapTarget] = useState<ACTestMappingGroup | null>(null);
  const [acceptedGapReason, setAcceptedGapReason] = useState("");
  const [acceptedGapRiskCategory, setAcceptedGapRiskCategory] = useState<string | null>(null);
  const [acceptedGapOutOfScope, setAcceptedGapOutOfScope] = useState(false);

  // Fetch mappings
  const fetchMappings = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `/api/repositories/${repositoryId}/pull-requests/${pullRequestId}/ac-test-mappings`
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body?.error || body?.detail || `Failed to fetch mappings (${response.status})`);
      }
      const data = await response.json();
      const items: ACTestMappingGroup[] = data.rows || data.items || [];
      setMappings(items);
      setSummary(data.mapping_summary ? { ...(data.summary || {}), ...data.mapping_summary, ...(data.execution_summary || {}), quality_warnings: data.quality_warnings || [] } : (data.summary || null));

      // Auto-expand the first few ACs that need user action or have conflicts
      const needsAction = items
        .filter(m => ["suggested", "needs_review", "conflicted", "metadata_conflict_semantic_match", "partial_support"].includes((m.row_status || m.status).toLowerCase()) || m.has_conflict)
        .slice(0, 3)
        .map(m => m.stable_ac_key);
      if (needsAction.length > 0) {
        setExpandedACs(prev => {
          const next = new Set(prev);
          needsAction.forEach(k => next.add(k));
          return next;
        });
      }
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Failed to load mappings";
      toast.error(msg);
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [repositoryId, pullRequestId]);

  useEffect(() => {
    if (isOpen) {
      fetchMappings();
    }
  }, [isOpen, repositoryId, pullRequestId]);

  // Filter mappings (Requirement 10: Search works by AC text, test name, declared ref, and status)
  const filteredMappings = mappings.filter(mapping => {
    const q = searchTerm.toLowerCase().trim();
    const displayRef = (mapping.display_ac_ref || "").toLowerCase();
    const acTitle = (mapping.ac_title || "").toLowerCase();
    const acText = (mapping.ac_text || "").toLowerCase();
    const reqGroup = (mapping.requirement_group || "").toLowerCase();

    const matchesTest = mapping.suggested_tests.some(test => {
      const tName = (test.test_name || "").toLowerCase();
      const tTitle = (test.test_title || "").toLowerCase();
      const sName = (test.suite_name || "").toLowerCase();
      const declRef = (test.declared_ac_ref || "").toLowerCase();
      const declText = (test.declared_ac_text || "").toLowerCase();
      const semRef = (test.semantic_best_match_ac_ref || "").toLowerCase();
      const semText = (test.semantic_best_match_ac_text || "").toLowerCase();
      const statusStr = (test.review_status || "").toLowerCase();
      return (
        tName.includes(q) ||
        tTitle.includes(q) ||
        sName.includes(q) ||
        declRef.includes(q) ||
        declText.includes(q) ||
        semRef.includes(q) ||
        semText.includes(q) ||
        statusStr.includes(q)
      );
    });

    const matchesSearch = !q || displayRef.includes(q) || acTitle.includes(q) || acText.includes(q) || reqGroup.includes(q) || matchesTest;

    const reviewStatuses = mapping.suggested_tests.map(test => (test.review_status || "").toLowerCase());
    const effectiveStatus = (mapping.row_status || mapping.status || "").toLowerCase();

    const matchesStatus = selectedStatus === "all"
      || (selectedStatus === "no_candidate" && (effectiveStatus === "no_candidate" || effectiveStatus === "unmapped"))
      || (selectedStatus === "suggested" && (effectiveStatus === "suggested" || reviewStatuses.some(s => s === "system_suggested" || s === "pending_review" || s === "suggested_strong" || s === "suggested_weak")))
      || (selectedStatus === "evidence_verified_aligned" && (effectiveStatus === "evidence_verified_aligned" || reviewStatuses.includes("evidence_verified_aligned")))
      || (selectedStatus === "metadata_conflict_semantic_match" && (effectiveStatus === "metadata_conflict_semantic_match" || reviewStatuses.includes("metadata_conflict_semantic_match")))
      || (selectedStatus === "partial_support" && (effectiveStatus === "partial_support" || reviewStatuses.includes("partial_support")))
      || (selectedStatus === "confirmed" && (effectiveStatus === "confirmed" || reviewStatuses.includes("user_confirmed")))
      || (selectedStatus === "rejected" && (effectiveStatus === "rejected" || reviewStatuses.includes("rejected") || reviewStatuses.includes("user_rejected")))
      || (selectedStatus === "accepted_gap" && effectiveStatus === "accepted_gap");

    return matchesSearch && matchesStatus;
  });

  const statusCounts = summary || mappings.reduce((acc, mapping) => {
    const st = mapping.row_status || mapping.status;
    acc[st] = (acc[st] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // --- Backend Action Handlers ---

  const handleConfirmCandidate = async (test: SuggestedTest) => {
    const targetId = test.candidate_id || test.edge_id;
    if (!targetId) return;
    setActionInProgress(targetId);
    try {
      const res = await fetch(`/api/ac-test-mappings/candidates/${targetId}/confirm_candidate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approval_mode: "normal",
          acknowledged_warnings: false,
          repository_id: repositoryId,
          pull_request_id: pullRequestId
        })
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || "Failed to confirm candidate");
      }
      toast.success("Candidate mapping confirmed");
      fetchMappings();
      onMappingUpdate?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to confirm candidate");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleRejectCandidate = async (test: SuggestedTest, reason: string = "Rejected by user") => {
    const targetId = test.candidate_id || test.edge_id;
    if (!targetId) return;
    setActionInProgress(targetId);
    try {
      const res = await fetch(`/api/ac-test-mappings/candidates/${targetId}/reject_candidate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason: reason,
          repository_id: repositoryId,
          pull_request_id: pullRequestId
        })
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || "Failed to reject candidate");
      }
      toast.success("Mapping rejected");
      fetchMappings();
      onMappingUpdate?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to reject candidate");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleAcceptSemanticMatch = async (test: SuggestedTest) => {
    const targetId = test.candidate_id || test.edge_id;
    if (!targetId) return;
    setActionInProgress(targetId);
    try {
      const res = await fetch(`/api/ac-test-mappings/candidates/${targetId}/accept_semantic_match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          comment: "Accepted semantic match",
          repository_id: repositoryId,
          pull_request_id: pullRequestId
        })
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || "Failed to accept semantic match");
      }
      toast.success("Accepted semantic match");
      fetchMappings();
      onMappingUpdate?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to accept semantic match");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleKeepDeclaredRefAnyway = async () => {
    if (!warningModalTarget) return;
    const targetId = warningModalTarget.candidate_id || warningModalTarget.edge_id;
    if (!targetId) return;
    if (!warningAcknowledged) {
      toast.error("You must acknowledge the warning before proceeding.");
      return;
    }

    setActionInProgress(targetId);
    try {
      const res = await fetch(`/api/ac-test-mappings/candidates/${targetId}/keep_declared_ref_anyway`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          acknowledged_warning: true,
          comment: warningComment || "Kept declared AC ref despite conflict",
          repository_id: repositoryId,
          pull_request_id: pullRequestId
        })
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || "Failed to keep declared ref");
      }
      toast.success("Kept declared AC ref (warning acknowledged)");
      setWarningModalTarget(null);
      setWarningAcknowledged(false);
      setWarningComment("");
      fetchMappings();
      onMappingUpdate?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to keep declared ref");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleManualLink = async () => {
    if (!manualLinkTarget || !manualLinkTargetAcId || !manualLinkTarget.test.test_case_id) return;
    const { test, ac } = manualLinkTarget;
    const targetId = test.candidate_id || test.edge_id;
    const sourceCandidateId = test.candidate_id || undefined;
    setActionInProgress(targetId || test.test_case_id);
    try {
      const res = await fetch(`/api/ac-test-mappings/manually_link_to_ac`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_ac_id: manualLinkTargetAcId,
          test_case_id: test.test_case_id,
          pull_request_id: pullRequestId,
          repository_id: repositoryId,
          reason: manualLinkReason.trim() || "Manual link from mapping review",
          source_candidate_id: sourceCandidateId,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || body.error || "Failed to create manual link");
      }
      toast.success("Manually linked test to AC");
      setManualLinkTarget(null);
      setManualLinkTargetAcId(null);
      setManualLinkReason("");
      fetchMappings();
      onMappingUpdate?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to create manual link");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleMarkUnmapped = async (test: SuggestedTest) => {
    const targetId = test.candidate_id || test.edge_id;
    if (!targetId) return;
    setActionInProgress(targetId);
    try {
      const res = await fetch(`/api/ac-test-mappings/candidates/${targetId}/mark_unmapped`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason: "Marked as unmapped by user",
          repository_id: repositoryId,
          pull_request_id: pullRequestId
        })
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || "Failed to mark unmapped");
      }
      toast.success("Marked mapping as unmapped");
      fetchMappings();
      onMappingUpdate?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to mark unmapped");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleAddReviewComment = async () => {
    if (!commentModalTarget || !commentText.trim()) return;
    const targetId = commentModalTarget.candidate_id || commentModalTarget.edge_id;
    if (!targetId) return;

    setActionInProgress(targetId);
    try {
      const res = await fetch(`/api/ac-test-mappings/candidates/${targetId}/add_review_comment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          comment: commentText.trim(),
          repository_id: repositoryId,
          pull_request_id: pullRequestId
        })
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || body.error || "Failed to add comment");
      }
      toast.success("Review comment added");
      setCommentModalTarget(null);
      setCommentText("");
      fetchMappings();
      onMappingUpdate?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to add comment");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleAcceptPartialSupport = async (test: SuggestedTest) => {
    const targetId = test.candidate_id || test.edge_id;
    if (!targetId) return;
    setActionInProgress(targetId);
    try {
      const res = await fetch(`/api/ac-test-mappings/candidates/${targetId}/accept_partial_support`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          comment: "Accepted partial support",
          repository_id: repositoryId,
          pull_request_id: pullRequestId
        })
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || body.error || "Failed to accept partial support");
      }
      toast.success("Accepted partial support");
      fetchMappings();
      onMappingUpdate?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to accept partial support");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleMarkAcceptedGap = async () => {
    if (!acceptedGapTarget || !acceptedGapReason.trim()) return;
    const acId = acceptedGapTarget.ac_id;
    if (!acId) return;
    setActionInProgress(`gap-${acId}`);
    try {
      const res = await fetch(`/api/ac-test-mappings/mark-accepted-gap`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ac_id: acId,
          repository_id: repositoryId,
          pull_request_id: pullRequestId,
          reason: acceptedGapReason.trim(),
          risk_category: acceptedGapRiskCategory || undefined,
          out_of_scope: acceptedGapOutOfScope,
          decision_type: acceptedGapOutOfScope ? "OUT_OF_SCOPE" : "ACCEPTED_GAP",
        })
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || body.error || "Failed to mark accepted gap");
      }
      toast.success("Accepted gap recorded");
      setAcceptedGapTarget(null);
      setAcceptedGapReason("");
      setAcceptedGapRiskCategory(null);
      setAcceptedGapOutOfScope(false);
      fetchMappings();
      onMappingUpdate?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to mark accepted gap");
    } finally {
      setActionInProgress(null);
    }
  };

  const toggleACExpansion = (acKey: string) => {
    const newExpanded = new Set(expandedACs);
    if (newExpanded.has(acKey)) {
      newExpanded.delete(acKey);
    } else {
      newExpanded.add(acKey);
    }
    setExpandedACs(newExpanded);
  };

  const getStatusLabel = (status: string) => {
    if (status.toLowerCase() === "metadata_conflict_semantic_match") return "Conflict: Semantic Match Found";
    if (status.toLowerCase() === "evidence_verified_aligned") return "Auto-trusted (Evidence Aligned)";
    if (status.toLowerCase() === "partial_support") return "Partial Support";
    if (status.toLowerCase() === "no_candidate") return "No Candidate";
    if (status.toLowerCase() === "rejected") return "Rejected";
    if (status.toLowerCase() === "accepted_gap") return "Accepted Gap / Risk";
    return status.replace(/_/g, " ").toUpperCase();
  };

  const getStatusIcon = (status: string) => {
    const s = status.toLowerCase();
    if (s.includes("confirm") || s.includes("verified")) {
      return <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />;
    }
    if (s.includes("conflict")) {
      return <AlertTriangle className="w-4 h-4 text-orange-500 shrink-0" />;
    }
    if (s.includes("ambiguous") || s.includes("needs_review") || s.includes("weak")) {
      return <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />;
    }
    if (s.includes("unmapped") || s.includes("unresolved")) {
      return <XCircle className="w-4 h-4 text-red-500 shrink-0" />;
    }
    if (s.includes("reject")) {
      return <XCircle className="w-4 h-4 text-gray-500 shrink-0" />;
    }
    return <Clock className="w-4 h-4 text-blue-500 shrink-0" />;
  };

  const getStatusColor = (status: string) => {
    const s = status.toLowerCase();
    if (s.includes("confirm") || s.includes("verified")) {
      return "bg-green-500/20 text-green-300 border-green-500/30";
    }
    if (s.includes("conflict")) {
      return "bg-orange-500/20 text-orange-300 border-orange-500/30";
    }
    if (s.includes("ambiguous") || s.includes("needs_review") || s.includes("weak")) {
      return "bg-amber-500/20 text-amber-300 border-amber-500/30";
    }
    if (s.includes("unmapped") || s.includes("unresolved")) {
      return "bg-red-500/20 text-red-300 border-red-500/30";
    }
    if (s.includes("reject")) {
      return "bg-gray-500/20 text-gray-300 border-gray-500/30";
    }
    return "bg-blue-500/20 text-blue-300 border-blue-500/30";
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return "text-green-400";
    if (confidence >= 0.5) return "text-yellow-400";
    return "text-red-400";
  };

  useEffect(() => {
    if (!isOpen) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !warningModalTarget && !commentModalTarget) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose, warningModalTarget, commentModalTarget]);

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget && !warningModalTarget && !commentModalTarget) onClose();
      }}
    >
      <div className="flex h-[90vh] max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl">
        {/* Top Header */}
        <div className="shrink-0">
          <div className="px-6 py-4 border-b border-zinc-700">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                  <ShieldAlert className="w-6 h-6 text-blue-400" />
                  AC → Test Mapping Conflict Resolution Workspace
                </h2>
                <p className="text-gray-400 mt-1 text-sm">
                  Review complete evidence chains, verify requirements alignment, and resolve conflicts safely.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchMappings}
                  disabled={loading}
                  className="bg-zinc-800 border-zinc-600 text-gray-200 hover:bg-zinc-700"
                >
                  <RefreshCw className={`w-4 h-4 mr-1 ${loading ? "animate-spin" : ""}`} />
                  Refresh Mappings
                </Button>
                <Button variant="ghost" onClick={onClose} className="text-gray-400 hover:text-white">
                  Close
                </Button>
              </div>
            </div>
          </div>

          {summary?.summary_integrity === "FAIL" && (
            <div className="mx-6 mt-4 rounded border border-red-500/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
              Mapping summary integrity failed: AC-level counters do not sum to total AC count.
            </div>
          )}
          <div className="px-6 py-3 border-b border-zinc-700 bg-zinc-950/60 text-xs text-gray-300 flex flex-wrap gap-x-5 gap-y-1" title="Passed tests confirm execution result. Mapping status shows whether each acceptance criterion is correctly linked to test evidence.">
            <span className="font-semibold text-gray-100">Test Execution</span>
            <span>Imported: {summary?.execution_total ?? 0}</span>
            <span className="text-emerald-300">Passed: {summary?.execution_passed ?? 0}</span>
            <span className="text-red-300">Failed: {summary?.execution_failed ?? 0}</span>
            <span className="text-amber-300">Skipped: {summary?.execution_skipped ?? 0}</span>
          </div>

          {/* Summary Stats */}
          <div className="px-6 py-3.5 border-b border-zinc-700 bg-zinc-900/50">
            <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-green-400">{statusCounts.confirmed || 0}</div>
                <div className="text-xs text-gray-400 font-medium">User Confirmed</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-cyan-300">{summary?.veriscope_key_verified || 0}</div>
                <div className="text-xs text-gray-400 font-medium">Key Verified</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-emerald-300">{statusCounts.evidence_verified_aligned || 0}</div>
                <div className="text-xs text-gray-400 font-medium">Evidence Aligned</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-400">{statusCounts.metadata_conflict_semantic_match || 0}</div>
                <div className="text-xs text-gray-400 font-medium">Metadata Conflict</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-amber-400">{statusCounts.partial_support || 0}</div>
                <div className="text-xs text-gray-400 font-medium">Partial Support</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-400">{statusCounts.suggested || 0}</div>
                <div className="text-xs text-gray-400 font-medium">Suggested</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-400">{statusCounts.no_candidate ?? statusCounts.unmapped ?? 0}</div>
                <div className="text-xs text-gray-400 font-medium">No Candidate</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-400">{statusCounts.rejected || 0}</div>
                <div className="text-xs text-gray-400 font-medium">Rejected</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-rose-300">{statusCounts.accepted_gap || 0}</div>
                <div className="text-xs text-gray-400 font-medium">Accepted Gap / Risk</div>
              </div>
            </div>
          </div>

          {/* Filters */}
          <div className="px-6 py-3.5 border-b border-zinc-700 bg-zinc-950/40">
            <div className="flex gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                  <Input
                    placeholder="Search by AC text, test name, declared ref (e.g. AC-03), or status..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10 bg-zinc-800 border-zinc-700 text-white placeholder-gray-400"
                  />
                </div>
              </div>
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="px-3 py-2 bg-zinc-800 border border-zinc-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Statuses</option>
                <option value="confirmed">User Confirmed</option>
                <option value="evidence_verified_aligned">Evidence Verified / Aligned</option>
                <option value="metadata_conflict_semantic_match">Conflict: Semantic Match Found</option>
                <option value="partial_support">Partial Support</option>
                <option value="suggested">Suggested</option>
                <option value="no_candidate">No Candidate</option>
                <option value="rejected">Rejected</option>
                <option value="accepted_gap">Accepted Gap / Risk</option>
              </select>
            </div>
          </div>
        </div>

        {/* Mappings List */}
        <div className="min-h-0 flex-1 overflow-y-auto p-6 space-y-4 pb-12 bg-zinc-950/20">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 space-y-3">
              <RefreshCw className="w-8 h-8 animate-spin text-blue-400" />
              <p className="text-gray-400 text-sm">Evaluating evidence graph and mapping candidates...</p>
            </div>
          ) : filteredMappings.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              {mappings.length === 0
                ? "No acceptance criteria found for this pull request. Add ACs to begin review."
                : `No mappings match the filter (${selectedStatus}). Try clearing search or status filter.`}
            </div>
          ) : (
            <div className="space-y-4">
              {filteredMappings.map((mapping) => {
                const currentStatus = mapping.row_status || mapping.status;
                const isMetadataConflict = currentStatus === "metadata_conflict_semantic_match";
                const isConflictedGroup = mapping.has_conflict || currentStatus === "conflicted" || isMetadataConflict;

                return (
                  <Card key={mapping.stable_ac_key} className="border-zinc-700 bg-zinc-900/90 shadow-md">
                    {/* Main Row Display */}
                    <CardHeader
                      className="pb-3 cursor-pointer"
                      onClick={() => toggleACExpansion(mapping.stable_ac_key)}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleACExpansion(mapping.stable_ac_key)}
                            className="shrink-0 text-gray-400 hover:text-white"
                          >
                            {expandedACs.has(mapping.stable_ac_key) ? (
                              <ChevronUp className="w-4 h-4" />
                            ) : (
                              <ChevronDown className="w-4 h-4" />
                            )}
                          </Button>
                          {getStatusIcon(currentStatus)}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              {/* Requirement 9: Main display title is human-friendly display_ac_ref, NOT stable key */}
                              <Badge variant="outline" className="bg-zinc-800 text-blue-300 border-zinc-700 text-xs font-mono font-bold">
                                {mapping.display_ac_ref || "AC"}
                              </Badge>
                              <CardTitle className="text-base font-semibold text-white break-words">
                                {mapping.ac_title || mapping.ac_text}
                              </CardTitle>
                              {isConflictedGroup && (
                                <Badge variant="outline" className="bg-orange-500/20 text-orange-300 border-orange-500/30 text-xs flex items-center gap-1 shrink-0 font-medium">
                                  <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />
                                  {isMetadataConflict ? "Conflict: Semantic Match Found" : "Conflict Detected"}
                                </Badge>
                              )}
                            </div>
                            <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400 flex-wrap">
                              <span>Requirement Group / Flow: <strong className="text-gray-200">{mapping.requirement_group || "General"} {mapping.business_flow ? `(${mapping.business_flow})` : ""}</strong></span>
                              <span>•</span>
                              <span>Linked Tests: <strong className="text-gray-200">{mapping.suggested_tests_count ?? mapping.suggested_tests.length}</strong></span>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <Badge className={getStatusColor(currentStatus)}>
                            {getStatusLabel(currentStatus)}
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    
                    {/* Expanded Row Display */}
                    {expandedACs.has(mapping.stable_ac_key) && (
                      <CardContent className="pt-0 border-t border-zinc-800/80 mt-2">
                        <div className="space-y-4 mt-3">
                          {/* AC Details Box */}
                          <div className="bg-zinc-950/60 p-3.5 rounded-lg border border-zinc-800 space-y-1.5">
                            <div className="flex items-center justify-between text-xs text-gray-400">
                              <span>Requirement Group: <strong className="text-white">{mapping.requirement_group}</strong></span>
                              {mapping.business_flow && <span>Flow: <strong className="text-blue-400">{mapping.business_flow}</strong></span>}
                            </div>
                            <div className="text-xs font-semibold text-gray-400">Acceptance Criterion Meaning:</div>
                            <div className="text-sm text-gray-200 whitespace-pre-wrap">{mapping.ac_text}</div>
                          </div>

                          {/* Candidate Tests List */}
                          {mapping.suggested_tests.length > 0 ? (
                            <div className="space-y-4">
                              <div className="text-sm font-semibold text-gray-200 flex items-center gap-2">
                                <span>Suggested / Candidate Tests ({mapping.suggested_tests.length})</span>
                              </div>

                              {mapping.suggested_tests.map((test, index) => {
                                const confVal = test.confidence_score ?? test.confidence;
                                const confLabel = test.confidence_label || (confVal >= 0.8 ? "high" : confVal >= 0.5 ? "medium" : "low");
                                const isConflict = test.conflict_detected || (test.review_status || "").toLowerCase().includes("conflict");

                                return (
                                  <div 
                                    key={test.candidate_id || test.edge_id || index}
                                    className={`p-4 rounded-xl border space-y-3 transition-all ${
                                      isConflict
                                        ? "bg-orange-950/20 border-orange-500/40 shadow-inner"
                                        : "bg-zinc-800/50 border-zinc-700/60"
                                    }`}
                                  >
                                    {/* Expanded Test Header */}
                                    <div className="flex items-start justify-between gap-3">
                                      <div className="min-w-0 flex-1 space-y-1">
                                        <div className="flex items-center gap-2 flex-wrap">
                                          <span className="font-semibold text-white text-base">{test.test_name}</span>
                                          {test.declared_ac_ref && (
                                            <Badge variant="outline" className="bg-purple-950/60 text-purple-300 border-purple-500/40 text-xs">
                                              Declares: {test.declared_ac_ref}
                                            </Badge>
                                          )}
                                        </div>
                                        {test.test_title && test.test_title !== test.test_name && (
                                          <div className="text-xs text-gray-300">Test Title: {test.test_title}</div>
                                        )}
                                        {test.classname && (
                                          <div className="text-xs text-gray-400 font-mono">Classname: {test.classname}</div>
                                        )}
                                      </div>

                                      <div className="flex items-center gap-2 shrink-0">
                                        <span className={`text-xs font-semibold px-2.5 py-1 rounded bg-zinc-900 border border-zinc-700 ${getConfidenceColor(confVal)}`}>
                                          {Math.round(confVal * 100)}% ({confLabel})
                                        </span>
                                        <Badge className={getStatusColor(test.review_status)}>
                                          {getStatusLabel(test.review_status)}
                                        </Badge>
                                      </div>
                                    </div>

                                    {/* Expanded Row Evidence & Flow Details */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-zinc-900/80 p-3 rounded-lg border border-zinc-800">
                                      <div>
                                        <span className="text-gray-400 block font-semibold mb-1">Declared AC from Test File:</span>
                                        <div className="text-gray-200">
                                          Ref: <strong className="text-purple-300">{test.declared_ac_ref || "None declared"}</strong>
                                        </div>
                                        {test.declared_ac_text && (
                                          <div className="text-gray-400 mt-1 italic break-words">
                                            "{test.declared_ac_text}"
                                          </div>
                                        )}
                                      </div>

                                      <div>
                                        <span className="text-gray-400 block font-semibold mb-1">Semantic Best Match:</span>
                                        <div className="text-gray-200">
                                          Ref: <strong className="text-green-300">{test.semantic_best_match_ac_ref || "N/A"}</strong>
                                          {test.semantic_best_match_score ? ` (${Math.round(test.semantic_best_match_score * 100)}% match)` : ""}
                                        </div>
                                        {test.semantic_best_match_ac_text && (
                                          <div className="text-gray-400 mt-1 italic break-words">
                                            "{test.semantic_best_match_ac_text}"
                                          </div>
                                        )}
                                      </div>

                                      {/* Flow Comparison */}
                                      <div className="col-span-1 md:col-span-2 pt-2 border-t border-zinc-800/60 flex items-center justify-between text-gray-300 flex-wrap gap-2">
                                        <div>Flow from test: <strong className="text-blue-300">{test.flow_from_test || "General"}</strong></div>
                                        <ArrowRight className="w-3.5 h-3.5 text-gray-500 hidden sm:inline" />
                                        <div>Flow from declared AC: <strong className="text-purple-300">{test.flow_from_declared_ac || "General"}</strong></div>
                                        <ArrowRight className="w-3.5 h-3.5 text-gray-500 hidden sm:inline" />
                                        <div>Flow from semantic match: <strong className="text-green-300">{test.flow_from_semantic_match || "General"}</strong></div>
                                      </div>
                                    </div>

                                    {/* Conflicted Mapping UI Box */}
                                    {isConflict && (
                                      <div className="p-4 bg-orange-950/40 border border-orange-500/50 rounded-xl space-y-2 text-xs text-orange-200">
                                        <div className="flex items-center gap-2 font-bold text-orange-400 text-sm">
                                          <AlertTriangle className="w-4 h-4 shrink-0" />
                                          <span>{test.review_status.toLowerCase() === "metadata_conflict_semantic_match" ? "Conflict: Semantic Match Found" : "Conflict Detected"}</span>
                                        </div>
                                        <div className="space-y-1 pl-6">
                                          <div>• <strong>Test declares:</strong> {test.declared_ac_ref || "None"}</div>
                                          {test.declared_ac_text && <div>• <strong>Declared AC means:</strong> {test.declared_ac_text}</div>}
                                          {test.semantic_best_match_ac_text && <div>• <strong>Test appears to cover:</strong> {test.semantic_best_match_ac_text}</div>}
                                          {test.semantic_best_match_ac_ref && (
                                            <div>• <strong>Suggested semantic match:</strong> {test.semantic_best_match_ac_ref} — {test.semantic_best_match_ac_text || ""}</div>
                                          )}
                                          <div>• <strong>Reason:</strong> {test.conflict_reason || test.reason || "Declared AC ref conflicts with test name/title/classname"}</div>
                                        </div>
                                      </div>
                                    )}

                                    {/* Action Buttons per Button Rules */}
                                    <div className="flex items-center justify-between pt-2 border-t border-zinc-800/80 flex-wrap gap-2">
                                      <div className="text-xs text-gray-400">
                                        Source: <span className="text-gray-300 font-mono">{test.edge_source || test.candidate_source}</span>
                                      </div>

                                      <div className="flex items-center gap-2 flex-wrap">
                                        {/* Comment Button */}
                                        <Button
                                          size="sm"
                                          variant="ghost"
                                          onClick={() => setCommentModalTarget(test)}
                                          className="text-gray-400 hover:text-white text-xs h-8"
                                        >
                                          <MessageSquare className="w-3.5 h-3.5 mr-1" />
                                          Add Comment
                                        </Button>

                                        {/* Status-specific Action Rules */}
                                        {isConflict ? (
                                          <>
                                            {/* CONFLICTED Actions: Accept semantic match, Keep declared ref anyway, Mark unmapped, Reject candidate */}
                                            {test.semantic_best_match_ac_id && test.semantic_match_accept_allowed ? (
                                              <Button
                                                size="sm"
                                                onClick={() => handleAcceptSemanticMatch(test)}
                                                disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                                className="bg-green-600 hover:bg-green-500 text-white text-xs h-8"
                                              >
                                                Accept Semantic Match
                                              </Button>
                                            ) : test.semantic_best_match_ac_id ? (
                                              <span className="text-xs text-amber-300">Manual link required: semantic confidence is below 65%.</span>
                                            ) : null}
                                            <Button
                                              size="sm"
                                              onClick={() => {
                                                setWarningModalTarget(test);
                                                setWarningAcknowledged(false);
                                                setWarningComment("");
                                              }}
                                              disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                              className="bg-amber-600 hover:bg-amber-500 text-white text-xs h-8"
                                            >
                                              Keep Declared AC Anyway
                                            </Button>
                                            <Button
                                              size="sm"
                                              variant="outline"
                                              onClick={() => {
                                                setManualLinkTarget({ test, ac: mapping });
                                                const firstOtherAc = mappings.find(m => m.ac_id !== mapping.ac_id)?.ac_id || mapping.ac_id || null;
                                                setManualLinkTargetAcId(firstOtherAc);
                                                setManualLinkReason("");
                                              }}
                                              disabled={!mapping.ac_id || actionInProgress === (test.candidate_id || test.edge_id)}
                                              className="border-zinc-700 text-gray-300 hover:bg-zinc-800 text-xs h-8"
                                            >
                                              Manual Link
                                            </Button>
                                            <Button
                                              size="sm"
                                              variant="outline"
                                              onClick={() => handleRejectCandidate(test)}
                                              disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                              className="border-red-500/40 text-red-400 hover:bg-red-500/10 text-xs h-8"
                                            >
                                              Reject
                                            </Button>
                                          </>
                                        ) : test.review_status === "verified" || test.review_status === "VERIFIED" ? (
                                          <Button
                                            size="sm"
                                            onClick={() => handleConfirmCandidate(test)}
                                            disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                            className="bg-green-600 hover:bg-green-500 text-white text-xs h-8"
                                          >
                                            <CheckCircle className="w-3.5 h-3.5 mr-1" />
                                            Confirm
                                          </Button>
                                        ) : test.review_status === "suggested_strong" || test.review_status === "SUGGESTED_STRONG" || test.review_status === "system_suggested" ? (
                                          <>
                                            <Button
                                              size="sm"
                                              onClick={() => handleConfirmCandidate(test)}
                                              disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                              className="bg-green-600 hover:bg-green-500 text-white text-xs h-8"
                                            >
                                              Approve
                                            </Button>
                                            <Button
                                              size="sm"
                                              variant="outline"
                                              onClick={() => handleRejectCandidate(test)}
                                              disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                              className="border-red-500/40 text-red-400 hover:bg-red-500/10 text-xs h-8"
                                            >
                                              Reject
                                            </Button>
                                          </>
                                        ) : test.review_status === "suggested_weak" || test.review_status === "SUGGESTED_WEAK" || test.review_status === "needs_review" ? (
                                          <>
                                            <Button
                                              size="sm"
                                              onClick={() => handleConfirmCandidate(test)}
                                              disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                              className="bg-amber-600 hover:bg-amber-500 text-white text-xs h-8"
                                            >
                                              Review & Approve
                                            </Button>
                                            <Button
                                              size="sm"
                                              variant="outline"
                                              onClick={() => handleRejectCandidate(test)}
                                              disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                              className="border-red-500/40 text-red-400 hover:bg-red-500/10 text-xs h-8"
                                            >
                                              Reject
                                            </Button>
                                          </>
                                        ) : test.review_status === "partial_support" || test.review_status === "PARTIAL_SUPPORT" ? (
                                          <>
                                            <Button
                                              size="sm"
                                              onClick={() => handleAcceptPartialSupport(test)}
                                              disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                              className="bg-blue-600 hover:bg-blue-500 text-white text-xs h-8"
                                            >
                                              Accept Partial Support
                                            </Button>
                                            <Button
                                              size="sm"
                                              variant="outline"
                                              onClick={() => handleRejectCandidate(test)}
                                              disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                              className="border-red-500/40 text-red-400 hover:bg-red-500/10 text-xs h-8"
                                            >
                                              Reject
                                            </Button>
                                          </>
                                        ) : test.review_status.toLowerCase() === "evidence_verified_aligned" ? (
                                          <>
                                            <span className="text-xs text-emerald-300">
                                              Auto-trusted — no review required.
                                            </span>
                                            <Button
                                              size="sm"
                                              variant="outline"
                                              onClick={() => handleConfirmCandidate(test)}
                                              disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                              className="border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 text-xs h-8"
                                            >
                                              <CheckCircle className="w-3.5 h-3.5 mr-1" />
                                              Confirm Anyway
                                            </Button>
                                          </>
                                        ) : (
                                          <>
                                            {test.review_status !== "user_confirmed" && test.review_status !== "USER_CONFIRMED" && (
                                              <Button
                                                size="sm"
                                                onClick={() => handleConfirmCandidate(test)}
                                                disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                                className="bg-green-600 hover:bg-green-500 text-white text-xs h-8"
                                              >
                                                Approve Candidate
                                              </Button>
                                            )}
                                            {test.review_status !== "user_rejected" && test.review_status !== "USER_REJECTED" && (
                                              <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => handleRejectCandidate(test)}
                                                disabled={actionInProgress === (test.candidate_id || test.edge_id)}
                                                className="border-red-500/40 text-red-400 hover:bg-red-500/10 text-xs h-8"
                                              >
                                                Reject
                                              </Button>
                                            )}
                                          </>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          ) : (
                            <div className="text-center py-6 text-gray-400 text-sm bg-zinc-950/40 rounded-lg border border-zinc-800 space-y-3">
                              <div>No candidate tests linked to this requirement.</div>
                              <div className="flex items-center justify-center gap-2 flex-wrap">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    setAcceptedGapTarget(mapping);
                                    setAcceptedGapReason("");
                                    setAcceptedGapRiskCategory(null);
                                    setAcceptedGapOutOfScope(false);
                                  }}
                                  disabled={loading || !!actionInProgress}
                                  className="border-amber-500/40 text-amber-300 hover:bg-amber-500/10 text-xs h-8"
                                >
                                  Mark Accepted Gap
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled
                                  title="Manual link requires a test candidate to be available"
                                  className="border-zinc-700 text-gray-500 text-xs h-8"
                                >
                                  Manual Link
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      </CardContent>
                    )}
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Keep Declared AC Anyway Warning Dialog */}
      {warningModalTarget && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="w-full max-w-lg bg-zinc-900 border border-amber-500/50 rounded-xl p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3 text-amber-400 font-bold text-lg">
              <AlertTriangle className="w-6 h-6 shrink-0" />
              <span>Warning: Conflict Detected</span>
            </div>

            <p className="text-sm text-gray-200">
              The test <strong>"{warningModalTarget.test_name}"</strong> declares <strong>"{warningModalTarget.declared_ac_ref}"</strong>, but conflicts with the requirement semantics:
            </p>

            <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 text-xs space-y-1 text-gray-300">
              <div><strong>Conflict Reason:</strong> {warningModalTarget.conflict_reason || warningModalTarget.reason}</div>
              {warningModalTarget.semantic_best_match_ac_ref && (
                <div><strong>Suggested Semantic Match:</strong> {warningModalTarget.semantic_best_match_ac_ref} ({warningModalTarget.semantic_best_match_ac_text})</div>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-300 block font-medium">Resolution Comment (Optional):</label>
              <Input
                placeholder="Reason for overriding conflict warning..."
                value={warningComment}
                onChange={(e) => setWarningComment(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-white text-xs"
              />
            </div>

            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="ack_checkbox"
                checked={warningAcknowledged}
                onChange={(e) => setWarningAcknowledged(e.target.checked)}
                className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-amber-500 focus:ring-amber-400"
              />
              <label htmlFor="ack_checkbox" className="text-xs text-amber-200 cursor-pointer font-medium">
                I acknowledge the context conflict risk and want to keep declared ref anyway.
              </label>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-800">
              <Button
                variant="ghost"
                onClick={() => {
                  setWarningModalTarget(null);
                  setWarningAcknowledged(false);
                }}
                className="text-gray-400 hover:text-white text-xs"
              >
                Cancel
              </Button>
              <Button
                disabled={!warningAcknowledged || actionInProgress === (warningModalTarget.candidate_id || warningModalTarget.edge_id)}
                onClick={handleKeepDeclaredRefAnyway}
                className="bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold"
              >
                Approve Anyway
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Add Review Comment Modal */}
      {commentModalTarget && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="w-full max-w-md bg-zinc-900 border border-zinc-700 rounded-xl p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-white font-bold text-base">
              <MessageSquare className="w-5 h-5 text-blue-400" />
              <span>Add Review Comment</span>
            </div>

            <div className="text-xs text-gray-400">
              Adding comment to test <strong>{commentModalTarget.test_name}</strong>
            </div>

            <textarea
              placeholder="Enter review notes or context comment..."
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              className="w-full h-28 p-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
            />

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                variant="ghost"
                onClick={() => {
                  setCommentModalTarget(null);
                  setCommentText("");
                }}
                className="text-gray-400 hover:text-white text-xs"
              >
                Cancel
              </Button>
              <Button
                disabled={!commentText.trim() || actionInProgress === (commentModalTarget.candidate_id || commentModalTarget.edge_id)}
                onClick={handleAddReviewComment}
                className="bg-blue-600 hover:bg-blue-500 text-white text-xs"
              >
                Save Comment
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Link Modal */}
      {manualLinkTarget && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="w-full max-w-lg bg-zinc-900 border border-blue-500/50 rounded-xl p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-white font-bold text-base">
              <LinkIcon className="w-5 h-5 text-blue-400" />
              <span>Manual Link</span>
            </div>

            <div className="space-y-3 text-xs text-gray-300">
              <div><strong>Current AC:</strong> {manualLinkTarget.ac.display_ac_ref || manualLinkTarget.ac.stable_ac_key} — {manualLinkTarget.ac.ac_title}</div>
              <div><strong>Test:</strong> {manualLinkTarget.test.test_name}</div>
              {manualLinkTarget.test.declared_ac_ref && (
                <div><strong>Declared AC:</strong> {manualLinkTarget.test.declared_ac_ref}</div>
              )}
              {manualLinkTarget.test.semantic_best_match_ac_ref && (
                <div><strong>Semantic match:</strong> {manualLinkTarget.test.semantic_best_match_ac_ref}</div>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-300 block font-medium">Target AC</label>
              <select
                value={manualLinkTargetAcId || ""}
                onChange={(e) => setManualLinkTargetAcId(e.target.value || null)}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded text-white text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select an AC...</option>
                {mappings.filter(m => m.ac_id).map(m => (
                  <option key={m.ac_id} value={m.ac_id}>
                    {m.display_ac_ref || m.stable_ac_key} — {m.ac_title}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-300 block font-medium">Reason (required)</label>
              <Input
                placeholder="Why are you manually linking this test to the target AC?"
                value={manualLinkReason}
                onChange={(e) => setManualLinkReason(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-white text-xs"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-800">
              <Button
                variant="ghost"
                onClick={() => {
                  setManualLinkTarget(null);
                  setManualLinkTargetAcId(null);
                  setManualLinkReason("");
                }}
                className="text-gray-400 hover:text-white text-xs"
              >
                Cancel
              </Button>
              <Button
                disabled={!manualLinkTargetAcId || !manualLinkReason.trim() || actionInProgress === (manualLinkTarget.test.candidate_id || manualLinkTarget.test.edge_id)}
                onClick={handleManualLink}
                className="bg-blue-600 hover:bg-blue-500 text-white text-xs"
              >
                Link Test to AC
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Accepted Gap Modal */}
      {acceptedGapTarget && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="w-full max-w-lg bg-zinc-900 border border-amber-500/50 rounded-xl p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-amber-400 font-bold text-base">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <span>Mark Accepted Gap / Risk</span>
            </div>

            <div className="space-y-2 text-xs text-gray-300">
              <div><strong>AC:</strong> {acceptedGapTarget.display_ac_ref || acceptedGapTarget.stable_ac_key} — {acceptedGapTarget.ac_title}</div>
              <div>There is no test candidate for this AC. Record it as an accepted risk or out-of-scope item.</div>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-300 block font-medium">Reason (required)</label>
              <Input
                placeholder="e.g. Covered by manual QA, out of scope for this PR..."
                value={acceptedGapReason}
                onChange={(e) => setAcceptedGapReason(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-white text-xs"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-300 block font-medium">Risk category (optional)</label>
              <Input
                placeholder="e.g. low, medium, high"
                value={acceptedGapRiskCategory || ""}
                onChange={(e) => setAcceptedGapRiskCategory(e.target.value || null)}
                className="bg-zinc-800 border-zinc-700 text-white text-xs"
              />
            </div>

            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="out_of_scope_checkbox"
                checked={acceptedGapOutOfScope}
                onChange={(e) => setAcceptedGapOutOfScope(e.target.checked)}
                className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-amber-500 focus:ring-amber-400"
              />
              <label htmlFor="out_of_scope_checkbox" className="text-xs text-amber-200 cursor-pointer font-medium">
                Mark as out of scope
              </label>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-800">
              <Button
                variant="ghost"
                onClick={() => {
                  setAcceptedGapTarget(null);
                  setAcceptedGapReason("");
                  setAcceptedGapRiskCategory(null);
                  setAcceptedGapOutOfScope(false);
                }}
                className="text-gray-400 hover:text-white text-xs"
              >
                Cancel
              </Button>
              <Button
                disabled={!acceptedGapReason.trim() || actionInProgress === `gap-${acceptedGapTarget.ac_id}`}
                onClick={handleMarkAcceptedGap}
                className="bg-amber-600 hover:bg-amber-500 text-white text-xs"
              >
                Mark Accepted Gap
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
