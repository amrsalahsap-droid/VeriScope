"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { 
  X,
  FileText,
  Users,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Sparkles
} from "lucide-react";

interface PasteAcceptanceCriteriaModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updatedReadiness: any, recommendationStale: boolean) => void;
  repositoryId: string;
  pullRequestId?: string;
  initialData?: {
    business_change?: string;
    affected_users?: string;
    acceptance_criteria?: string;
    risk_notes?: string;
    testing_notes?: string;
  };
}

export default function PasteAcceptanceCriteriaModal({ 
  isOpen, 
  onClose, 
  onSuccess,
  repositoryId,
  pullRequestId,
  initialData
}: PasteAcceptanceCriteriaModalProps) {
  const [formData, setFormData] = useState({
    business_change: "",
    affected_users: "",
    acceptance_criteria: "",
    risk_notes: "",
    testing_notes: "",
  });
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFormData({
        business_change: initialData?.business_change || "",
        affected_users: initialData?.affected_users || "",
        acceptance_criteria: initialData?.acceptance_criteria || "",
        risk_notes: initialData?.risk_notes || "",
        testing_notes: initialData?.testing_notes || "",
      });
      setError(null);
      setSuccess(false);
    }
  }, [isOpen, initialData]);

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.business_change.trim()) {
      setError("Business change summary is required");
      return;
    }
    
    if (!formData.acceptance_criteria.trim()) {
      setError("Acceptance criteria is required");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch(`/api/repositories/${repositoryId}/pull-requests/${pullRequestId}/acceptance-criteria/manual`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || `Failed to submit: ${response.status}`);
      }

      const updatedReadiness = await response.json();
      setSuccess(true);

      // Immediately trigger the refresh - no delay needed since backend returns updated readiness
      // Pass the full backend response so the gate can decide what to use.
      // The gate will re-fetch authoritative state from the API, but we pass
      // the full object (not just .readiness) so no partial-shape crash occurs.
      onSuccess(updatedReadiness, true);
      onClose();
      setSuccess(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save acceptance criteria");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    if (isSubmitting) return;
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleCancel}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          />

          {/* Modal Container */}
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
            <motion.div 
              initial={{ scale: 0.96, y: 15, opacity: 0 }}
              animate={{ scale: 1, y: 0, opacity: 1 }}
              exit={{ scale: 0.96, y: 15, opacity: 0 }}
              transition={{ type: "spring", duration: 0.4 }}
              className="bg-zinc-950 border border-zinc-800/80 rounded-2xl max-w-2xl w-full max-h-[92vh] flex flex-col overflow-hidden pointer-events-auto shadow-2xl shadow-black/80"
            >
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-zinc-900 bg-zinc-950">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-indigo-400" />
                  <h2 className="text-xl font-bold text-white tracking-tight">Paste Acceptance Criteria</h2>
                </div>
                <Button variant="ghost" size="icon" onClick={handleCancel} disabled={isSubmitting} className="text-zinc-400 hover:text-white rounded-lg">
                  <X className="w-5 h-5" />
                </Button>
              </div>

              {/* Scrollable Content */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {success ? (
                  <div className="text-center py-16 space-y-4">
                    <motion.div
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ type: "spring", stiffness: 200, damping: 15 }}
                    >
                      <CheckCircle2 className="w-16 h-16 text-emerald-400 mx-auto" />
                    </motion.div>
                    <h3 className="text-lg font-bold text-white tracking-tight">Acceptance Criteria Added</h3>
                    <p className="text-zinc-400 text-sm max-w-sm mx-auto leading-relaxed">
                      Your requirements have been saved. Regenerate the recommendation to include requirement coverage.
                    </p>
                  </div>
                ) : (
                  <form id="manual-ac-form" onSubmit={handleSubmit} className="space-y-5">
                    {/* Business Change Summary */}
                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider">
                        Business Change Summary <span className="text-rose-400">*</span>
                      </label>
                      <textarea
                        value={formData.business_change}
                        onChange={(e) => handleInputChange('business_change', e.target.value)}
                        className="w-full px-3.5 py-2.5 bg-zinc-900/60 border border-zinc-800 focus:border-zinc-700 rounded-xl text-zinc-100 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-700 placeholder-zinc-600 transition-colors resize-none"
                        rows={3}
                        placeholder="Describe what this change accomplishes in business terms..."
                        required
                      />
                    </div>

                    {/* Affected Users/Journeys */}
                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider">
                        Affected Users/Journeys <span className="text-zinc-500 font-normal">(optional)</span>
                      </label>
                      <div className="flex items-center gap-2 px-3.5 py-2.5 bg-zinc-900/60 border border-zinc-800 focus-within:border-zinc-700 rounded-xl transition-colors">
                        <Users className="w-4 h-4 text-zinc-500 shrink-0" />
                        <input
                          type="text"
                          value={formData.affected_users}
                          onChange={(e) => handleInputChange('affected_users', e.target.value)}
                          className="flex-1 bg-transparent text-zinc-100 text-sm focus:outline-none placeholder-zinc-600"
                          placeholder="e.g., Customer checkout, Admin settings, Mobile users"
                        />
                      </div>
                    </div>

                    {/* Acceptance Criteria */}
                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider">
                        Acceptance Criteria <span className="text-rose-400">*</span>
                      </label>
                      <textarea
                        value={formData.acceptance_criteria}
                        onChange={(e) => handleInputChange('acceptance_criteria', e.target.value)}
                        className="w-full px-3.5 py-2.5 bg-zinc-900/60 border border-zinc-800 focus:border-zinc-700 rounded-xl text-zinc-100 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-700 placeholder-zinc-600 transition-colors resize-none font-mono"
                        rows={6}
                        placeholder="1. User can successfully complete checkout&#10;2. Payment is processed securely&#10;3. Order confirmation email is sent"
                        required
                      />
                    </div>

                    {/* Risk Notes */}
                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider">
                        Risk Notes <span className="text-zinc-500 font-normal">(optional)</span>
                      </label>
                      <textarea
                        value={formData.risk_notes}
                        onChange={(e) => handleInputChange('risk_notes', e.target.value)}
                        className="w-full px-3.5 py-2.5 bg-zinc-900/60 border border-zinc-800 focus:border-zinc-700 rounded-xl text-zinc-100 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-700 placeholder-zinc-600 transition-colors resize-none"
                        rows={2}
                        placeholder="Potential risks, edge cases, or areas requiring special attention..."
                      />
                    </div>

                    {/* Testing Notes */}
                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider">
                        Testing Notes <span className="text-zinc-500 font-normal">(optional)</span>
                      </label>
                      <textarea
                        value={formData.testing_notes}
                        onChange={(e) => handleInputChange('testing_notes', e.target.value)}
                        className="w-full px-3.5 py-2.5 bg-zinc-900/60 border border-zinc-800 focus:border-zinc-700 rounded-xl text-zinc-100 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-700 placeholder-zinc-600 transition-colors resize-none"
                        rows={2}
                        placeholder="Testing environments, data requirements, or special test scenarios..."
                      />
                    </div>

                    {/* Error Message */}
                    {error && (
                      <motion.div 
                        initial={{ opacity: 0, y: -5 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-rose-950/10 border border-rose-900/30 rounded-xl p-4 flex gap-3 items-start"
                      >
                        <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-xs font-semibold text-rose-200">Submission Error</p>
                          <p className="text-xs text-rose-300 mt-0.5">{error}</p>
                        </div>
                      </motion.div>
                    )}
                  </form>
                )}
              </div>

              {/* Footer */}
              {!success && (
                <div className="flex items-center justify-between p-6 border-t border-zinc-900 bg-zinc-950">
                  <div className="text-xs text-zinc-500 max-w-[280px] leading-relaxed">
                    Improves requirement coverage without requiring Jira / Azure integrations.
                  </div>
                  <div className="flex gap-3">
                    <Button 
                      type="button" 
                      variant="ghost" 
                      onClick={handleCancel}
                      disabled={isSubmitting}
                      className="text-zinc-400 hover:text-white rounded-lg"
                    >
                      Cancel
                    </Button>
                    <Button 
                      type="submit"
                      form="manual-ac-form"
                      disabled={isSubmitting}
                      className="bg-white text-zinc-950 hover:bg-zinc-100 rounded-lg font-semibold tracking-tight shadow-md shadow-white/5 active:scale-[0.98] transition-all"
                    >
                      {isSubmitting ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        "Save & Recalculate"
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
