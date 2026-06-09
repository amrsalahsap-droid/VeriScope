"use client";

import { useState } from "react";
import { AlertTriangle, RotateCcw, ExternalLink, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface PostMergeOutcomeProps {
  recommendationRunId: string;
  existingData?: {
    defect_escaped?: boolean;
    rollback_occurred?: boolean;
    production_incident_url?: string;
    feedback_comment?: string;
  };
}

export function PostMergeOutcome({
  recommendationRunId,
  existingData,
}: PostMergeOutcomeProps) {
  const [defectEscaped, setDefectEscaped] = useState(existingData?.defect_escaped || false);
  const [rollbackOccurred, setRollbackOccurred] = useState(existingData?.rollback_occurred || false);
  const [incidentUrl, setIncidentUrl] = useState(existingData?.production_incident_url || "");
  const [notes, setNotes] = useState(existingData?.feedback_comment || "");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const response = await fetch(`/api/recommendations/${recommendationRunId}/outcome`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          defect_escaped: defectEscaped,
          rollback_occurred: rollbackOccurred,
          production_incident_url: incidentUrl || null,
          feedback_comment: notes || null,
        }),
      });

      if (!response.ok) throw new Error("Failed to update outcome");

      toast.success("Post-merge outcome updated", {
        description: "Defect and rollback information saved",
      });
    } catch (error) {
      toast.error("Failed to update outcome", { description: "Please try again later." });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-4 space-y-4">
      <div className="flex items-center gap-2">
        <MessageSquare className="w-4 h-4 text-zinc-400" />
        <h3 className="text-sm font-medium text-zinc-200">Post-Merge Outcome</h3>
      </div>

      <div className="space-y-3">
        {/* Defect Escaped */}
        <div className="flex items-center justify-between p-3 bg-zinc-900/40 rounded-lg border border-zinc-800/60">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            <div>
              <p className="text-sm text-zinc-200">Defect escaped to production?</p>
              <p className="text-[10px] text-zinc-500">Did a bug slip through despite testing?</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={!defectEscaped ? "default" : "outline"}
              size="sm"
              onClick={() => setDefectEscaped(false)}
              className={
                !defectEscaped
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-600"
                  : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700"
              }
            >
              No
            </Button>
            <Button
              variant={defectEscaped ? "default" : "outline"}
              size="sm"
              onClick={() => setDefectEscaped(true)}
              className={
                defectEscaped
                  ? "bg-rose-600 hover:bg-rose-700 text-white border-rose-600"
                  : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700"
              }
            >
              Yes
            </Button>
          </div>
        </div>

        {/* Rollback Occurred */}
        <div className="flex items-center justify-between p-3 bg-zinc-900/40 rounded-lg border border-zinc-800/60">
          <div className="flex items-center gap-3">
            <RotateCcw className="w-4 h-4 text-amber-400" />
            <div>
              <p className="text-sm text-zinc-200">Rollback occurred?</p>
              <p className="text-[10px] text-zinc-500">Was this change rolled back?</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={!rollbackOccurred ? "default" : "outline"}
              size="sm"
              onClick={() => setRollbackOccurred(false)}
              className={
                !rollbackOccurred
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-600"
                  : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700"
              }
            >
              No
            </Button>
            <Button
              variant={rollbackOccurred ? "default" : "outline"}
              size="sm"
              onClick={() => setRollbackOccurred(true)}
              className={
                rollbackOccurred
                  ? "bg-amber-600 hover:bg-amber-700 text-white border-amber-600"
                  : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700"
              }
            >
              Yes
            </Button>
          </div>
        </div>

        {/* Incident URL */}
        {(defectEscaped || rollbackOccurred) && (
          <div className="space-y-2">
            <label className="text-xs text-zinc-400">Incident/Defect Link (optional)</label>
            <div className="flex gap-2">
              <input
                type="url"
                value={incidentUrl}
                onChange={(e) => setIncidentUrl(e.target.value)}
                placeholder="https://incident-tracker.example.com/..."
                className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              {incidentUrl && (
                <a
                  href={incidentUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg border border-zinc-700 flex items-center gap-1.5 text-sm"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Open
                </a>
              )}
            </div>
          </div>
        )}

        {/* Notes */}
        <div className="space-y-2">
          <label className="text-xs text-zinc-400">Notes (optional)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add any additional context about the post-merge outcome..."
            rows={3}
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
        </div>
      </div>

      <div className="flex items-center justify-end pt-2 border-t border-zinc-800/50">
        <Button
          size="sm"
          onClick={handleSubmit}
          disabled={isSubmitting}
          className="bg-blue-600 hover:bg-blue-700 text-white"
        >
          {isSubmitting ? "Saving..." : "Save Outcome"}
        </Button>
      </div>
    </div>
  );
}
