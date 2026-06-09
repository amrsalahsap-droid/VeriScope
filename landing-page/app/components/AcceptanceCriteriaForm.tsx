"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { 
  X,
  FileText,
  Users,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw
} from "lucide-react";

interface AcceptanceCriteriaFormData {
  business_change_summary: string;
  affected_users_journeys: string;
  acceptance_criteria: string;
  risk_notes: string;
  testing_notes: string;
}

interface AcceptanceCriteriaFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: AcceptanceCriteriaFormData) => Promise<void>;
  repositoryId: string;
  pullRequestId?: string;
  recommendationRunId?: string;
  initialData?: Partial<AcceptanceCriteriaFormData>;
  title?: string;
}

export default function AcceptanceCriteriaForm({ 
  isOpen, 
  onClose, 
  onSubmit,
  repositoryId,
  pullRequestId,
  recommendationRunId,
  initialData,
  title = "Improve This Recommendation"
}: AcceptanceCriteriaFormProps) {
  const [formData, setFormData] = useState<AcceptanceCriteriaFormData>({
    business_change_summary: "",
    affected_users_journeys: "",
    acceptance_criteria: "",
    risk_notes: "",
    testing_notes: "",
    ...initialData
  });
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFormData({
        business_change_summary: "",
        affected_users_journeys: "",
        acceptance_criteria: "",
        risk_notes: "",
        testing_notes: "",
        ...initialData
      });
      setError(null);
      setSuccess(false);
    }
  }, [isOpen, initialData]);

  const handleInputChange = (field: keyof AcceptanceCriteriaFormData, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.business_change_summary.trim()) {
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
      await onSubmit(formData);
      setSuccess(true);
      
      // Close after success
      setTimeout(() => {
        onClose();
        setSuccess(false);
      }, 2000);
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-zinc-400" />
            <h2 className="text-xl font-semibold text-white">{title}</h2>
          </div>
          <Button variant="ghost" size="icon" onClick={handleCancel} disabled={isSubmitting}>
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Content */}
        <div className="p-6">
          {success ? (
            <div className="text-center py-8">
              <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-white mb-2">Acceptance Criteria Saved</h3>
              <p className="text-zinc-400 mb-4">
                Your acceptance criteria have been processed and will improve recommendation accuracy.
              </p>
              <div className="text-sm text-zinc-500">
                Closing automatically...
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Business Change Summary */}
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Business Change Summary <span className="text-rose-400">*</span>
                </label>
                <textarea
                  value={formData.business_change_summary}
                  onChange={(e) => handleInputChange('business_change_summary', e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                  rows={3}
                  placeholder="Describe what this change accomplishes in business terms..."
                  required
                />
              </div>

              {/* Affected Users/Journeys */}
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Affected Users/Journeys <span className="text-zinc-500">(optional)</span>
                </label>
                <div className="flex items-center gap-2 mb-2">
                  <Users className="w-4 h-4 text-zinc-500" />
                  <span className="text-xs text-zinc-500">Comma-separated list of user types or journey names</span>
                </div>
                <input
                  type="text"
                  value={formData.affected_users_journeys}
                  onChange={(e) => handleInputChange('affected_users_journeys', e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="e.g., Customer checkout, Admin dashboard, Mobile users"
                />
              </div>

              {/* Acceptance Criteria */}
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Acceptance Criteria <span className="text-rose-400">*</span>
                </label>
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-4 h-4 text-zinc-500" />
                  <span className="text-xs text-zinc-500">Paste your acceptance criteria - one per line or numbered list</span>
                </div>
                <textarea
                  value={formData.acceptance_criteria}
                  onChange={(e) => handleInputChange('acceptance_criteria', e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none font-mono text-sm"
                  rows={8}
                  placeholder="1. User can successfully complete checkout&#10;2. Payment is processed securely&#10;3. Order confirmation email is sent&#10;4. Inventory is updated accordingly"
                  required
                />
              </div>

              {/* Risk Notes */}
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Risk Notes <span className="text-zinc-500">(optional)</span>
                </label>
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-zinc-500" />
                  <span className="text-xs text-zinc-500">Any risks, edge cases, or concerns to consider</span>
                </div>
                <textarea
                  value={formData.risk_notes}
                  onChange={(e) => handleInputChange('risk_notes', e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                  rows={3}
                  placeholder="Potential risks, edge cases, or areas requiring special attention..."
                />
              </div>

              {/* Testing Notes */}
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Testing Notes <span className="text-zinc-500">(optional)</span>
                </label>
                <div className="flex items-center gap-2 mb-2">
                  <RefreshCw className="w-4 h-4 text-zinc-500" />
                  <span className="text-xs text-zinc-500">Testing considerations, environments, or special requirements</span>
                </div>
                <textarea
                  value={formData.testing_notes}
                  onChange={(e) => handleInputChange('testing_notes', e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                  rows={3}
                  placeholder="Testing environments, data requirements, or special test scenarios..."
                />
              </div>

              {/* Error Message */}
              {error && (
                <div className="bg-rose-950/20 border border-rose-800/30 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-rose-400" />
                    <span className="text-sm text-rose-400">{error}</span>
                  </div>
                </div>
              )}

              {/* Form Actions */}
              <div className="flex items-center justify-between pt-4 border-t border-zinc-800">
                <div className="text-xs text-zinc-500">
                  This improves recommendation accuracy without requiring Jira/Azure integration
                </div>
                <div className="flex gap-3">
                  <Button 
                    type="button" 
                    variant="outline" 
                    onClick={handleCancel}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                  <Button 
                    type="submit" 
                    disabled={isSubmitting}
                    className="bg-white text-zinc-950 hover:bg-zinc-100"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      "Save & Improve"
                    )}
                  </Button>
                </div>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
