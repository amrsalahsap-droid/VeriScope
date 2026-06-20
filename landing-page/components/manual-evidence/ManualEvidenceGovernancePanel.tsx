"use client";

import React, { useState, useEffect } from "react";
import { CheckCircle, XCircle, AlertTriangle, Clock, Shield, Loader2, Cloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export interface GovernanceStatus {
  governanceStatus: "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "CHALLENGED" | "EXPIRED";
  reviewerName?: string;
  reviewedAt?: string;
  reviewNote?: string;
  isExpired?: boolean;
  expiresAt?: string;
  syncStatus?: string | null;
  externalRunId?: string | null;
  externalExecutionId?: string | null;
  lastSyncedAt?: string | null;
}

export interface ManualEvidenceGovernancePanelProps {
  executionId: string;
  repositoryId: string;
  initialGovernance?: GovernanceStatus;
  onUpdated?: (governance: GovernanceStatus) => void;
  readOnly?: boolean;
  compact?: boolean;
}

export function ManualEvidenceGovernancePanel({
  executionId,
  repositoryId,
  initialGovernance,
  onUpdated,
  readOnly = false,
  compact = false
}: ManualEvidenceGovernancePanelProps) {
  const [governance, setGovernance] = useState<GovernanceStatus | null>(initialGovernance || null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [showNoteInput, setShowNoteInput] = useState(false);

  useEffect(() => {
    loadGovernance();
  }, [executionId, repositoryId]);

  const loadGovernance = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/repositories/${repositoryId}/manual-executions/${executionId}/governance`);
      if (response.ok) {
        const data = await response.json();
        setGovernance(data);
        onUpdated?.(data);
      }
    } catch (error) {
      console.error("Failed to load governance status:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    setActionLoading("approve");
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/manual-executions/${executionId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewNote: note || undefined })
      });

      if (response.ok) {
        toast.success("Manual evidence approved");
        setNote("");
        setShowNoteInput(false);
        loadGovernance();
      } else {
        const error = await response.json();
        toast.error(error.detail || "Failed to approve");
      }
    } catch (error) {
      toast.error("Failed to approve");
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async () => {
    if (!note.trim()) {
      toast.error("Review note is required for rejection");
      setShowNoteInput(true);
      return;
    }

    setActionLoading("reject");
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/manual-executions/${executionId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewNote: note })
      });

      if (response.ok) {
        toast.success("Manual evidence rejected");
        setNote("");
        setShowNoteInput(false);
        loadGovernance();
      } else {
        const error = await response.json();
        toast.error(error.detail || "Failed to reject");
      }
    } catch (error) {
      toast.error("Failed to reject");
    } finally {
      setActionLoading(null);
    }
  };

  const handleChallenge = async () => {
    if (!note.trim()) {
      toast.error("Review note is required for challenge");
      setShowNoteInput(true);
      return;
    }

    setActionLoading("challenge");
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/manual-executions/${executionId}/challenge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewNote: note })
      });

      if (response.ok) {
        toast.success("Manual evidence challenged");
        setNote("");
        setShowNoteInput(false);
        loadGovernance();
      } else {
        const error = await response.json();
        toast.error(error.detail || "Failed to challenge");
      }
    } catch (error) {
      toast.error("Failed to challenge");
    } finally {
      setActionLoading(null);
    }
  };

  const getGovernanceBadge = () => {
    if (loading) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-zinc-500/10 text-zinc-400 border border-zinc-500/20">
          <Loader2 className="w-3 h-3 animate-spin" />
          Loading
        </span>
      );
    }

    if (!governance) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-zinc-500/10 text-zinc-400 border border-zinc-500/20">
          <Clock className="w-3 h-3" />
          PENDING REVIEW
        </span>
      );
    }

    const status = governance.governanceStatus;
    const config = {
      PENDING_REVIEW: {
        bg: "bg-zinc-500/10",
        text: "text-zinc-400",
        border: "border-zinc-500/20",
        icon: Clock,
        label: "PENDING REVIEW"
      },
      APPROVED: {
        bg: "bg-green-500/10",
        text: "text-green-400",
        border: "border-green-500/20",
        icon: CheckCircle,
        label: "APPROVED"
      },
      REJECTED: {
        bg: "bg-red-500/10",
        text: "text-red-400",
        border: "border-red-500/20",
        icon: XCircle,
        label: "REJECTED"
      },
      CHALLENGED: {
        bg: "bg-amber-500/10",
        text: "text-amber-400",
        border: "border-amber-500/20",
        icon: AlertTriangle,
        label: "CHALLENGED"
      },
      EXPIRED: {
        bg: "bg-zinc-500/10",
        text: "text-zinc-400",
        border: "border-zinc-500/20",
        icon: Clock,
        label: "EXPIRED"
      }
    };

    const configItem = config[status] || config.PENDING_REVIEW;
    const Icon = configItem.icon;

    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${configItem.bg} ${configItem.text} ${configItem.border}`}>
        <Icon className="w-3 h-3" />
        {configItem.label}
      </span>
    );
  };

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        {getGovernanceBadge()}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Governance Status Badge */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-zinc-500 uppercase font-semibold">Governance Status</span>
        {getGovernanceBadge()}
      </div>

      {/* Governance Details */}
      {governance && (
        <div className="space-y-1.5 text-xs">
          {governance.reviewerName && (
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Reviewer:</span>
              <span className="text-zinc-300">{governance.reviewerName}</span>
            </div>
          )}
          {governance.reviewedAt && (
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Reviewed At:</span>
              <span className="text-zinc-300">{new Date(governance.reviewedAt).toLocaleString()}</span>
            </div>
          )}
          {governance.expiresAt && (
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Expires At:</span>
              <span className="text-zinc-300">{new Date(governance.expiresAt).toLocaleString()}</span>
            </div>
          )}
          {governance.reviewNote && (
            <div className="pt-1">
              <span className="text-zinc-500 block mb-1">Review Note:</span>
              <p className="text-zinc-300 italic bg-zinc-900/40 p-2 rounded border border-zinc-800/30">
                "{governance.reviewNote}"
              </p>
            </div>
          )}
        </div>
      )}

      {/* TestRail Sync Indicator */}
      {governance && governance.governanceStatus === "APPROVED" && governance.syncStatus === "SYNCED" && (
        <div className="flex items-center gap-2 p-2 bg-green-500/5 border border-green-500/10 rounded text-[10px] text-green-400/80">
          <Cloud className="w-3.5 h-3.5 shrink-0" />
          <span>Synced to TestRail</span>
        </div>
      )}

      {/* Advisory Warning */}
      <div className="flex items-start gap-2 p-2 bg-amber-500/5 border border-amber-500/10 rounded text-[10px] text-amber-500/80 leading-relaxed">
        <Shield className="w-3.5 h-3.5 shrink-0 mt-0.5" />
        <span>Only approved manual evidence can adjust residual risk. Manual evidence never counts as automated coverage.</span>
      </div>

      {/* Governance Actions */}
      {!readOnly && (
        <div className="space-y-2 pt-2 border-t border-zinc-800/30">
          {showNoteInput && (
            <div className="space-y-1.5">
              <label className="text-[10px] text-zinc-500 uppercase block">Review Note</label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Add a note for this review..."
                className="w-full text-xs bg-zinc-900/60 border border-zinc-800 rounded px-2.5 py-1.5 text-zinc-300 focus:outline-none focus:border-zinc-700 resize-none"
                rows={2}
              />
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleApprove}
              disabled={actionLoading !== null}
              className="flex-1 bg-green-500/10 hover:bg-green-500/20 text-green-400 border-green-500/20"
            >
              {actionLoading === "approve" ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-2" /> : <CheckCircle className="w-3.5 h-3.5 mr-2" />}
              Approve
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowNoteInput(!showNoteInput)}
              disabled={actionLoading !== null}
              className="flex-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 border-red-500/20"
            >
              {actionLoading === "reject" ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-2" /> : <XCircle className="w-3.5 h-3.5 mr-2" />}
              Reject
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowNoteInput(!showNoteInput)}
              disabled={actionLoading !== null}
              className="flex-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border-amber-500/20"
            >
              {actionLoading === "challenge" ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-2" /> : <AlertTriangle className="w-3.5 h-3.5 mr-2" />}
              Challenge
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
