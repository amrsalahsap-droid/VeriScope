import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { CheckCircle2, AlertTriangle, XCircle, Clock, Upload, FileText } from 'lucide-react';
import { toast } from 'sonner';

interface Signal {
  name: string;
  present: boolean;
  impact: number;
  description?: string;
}

interface ReadinessPanelProps {
  readinessLevel: string;
  expectedConfidence: string;
  availableSignals: Signal[];
  missingSignals: Signal[];
  completenessScore: number;
  canGenerate: boolean;
  repositoryId?: string;
  onReadinessUpdated?: () => void;
}

export default function RecommendationReadinessPanel({
  readinessLevel,
  expectedConfidence,
  availableSignals = [],
  missingSignals = [],
  completenessScore = 0,
  canGenerate = false,
  repositoryId,
  onReadinessUpdated
}: ReadinessPanelProps) {
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);

  const handleUpload = async (file: File) => {
    if (!repositoryId) {
      toast.error("Cannot upload", { description: "No repository ID available" });
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(
        `/api/repositories/${repositoryId}/manual-test-cases/import`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) throw new Error("Failed to upload manual test cases");

      const data = await response.json();
      toast.success("Manual test cases imported", {
        description: `${data.successful_imports} test cases imported successfully`,
      });

      if (data.errors && data.errors.length > 0) {
        toast.warning("Some rows had errors", {
          description: `${data.failed_rows} rows failed to import`,
        });
      }

      setShowUpload(false);
      onReadinessUpdated?.();
    } catch (error) {
      toast.error("Failed to upload manual test cases", { description: "Please try again later." });
    } finally {
      setUploading(false);
    }
  };

  const getReadinessStyling = (level: string) => {
    switch (level) {
      case 'HIGH_CONFIDENCE_READY':
        return {
          bgColor: 'bg-emerald-950/20',
          textColor: 'text-emerald-400',
          borderColor: 'border-emerald-800/40',
          icon: CheckCircle2
        };
      case 'PARTIAL':
        return {
          bgColor: 'bg-amber-950/20',
          textColor: 'text-amber-400',
          borderColor: 'border-amber-800/40',
          icon: AlertTriangle
        };
      case 'LIMITED':
        return {
          bgColor: 'bg-rose-950/20',
          textColor: 'text-rose-400',
          borderColor: 'border-rose-800/40',
          icon: XCircle
        };
      default:
        return {
          bgColor: 'bg-zinc-950/20',
          textColor: 'text-zinc-400',
          borderColor: 'border-zinc-800/40',
          icon: Clock
        };
    }
  };

  const getConfidenceStyling = (level: string) => {
    switch (level) {
      case 'HIGH':
        return {
          bgColor: 'bg-emerald-950/30',
          textColor: 'text-emerald-400',
          borderColor: 'border-emerald-800/50'
        };
      case 'MEDIUM':
        return {
          bgColor: 'bg-amber-950/30',
          textColor: 'text-amber-400',
          borderColor: 'border-amber-800/50'
        };
      case 'LOW':
        return {
          bgColor: 'bg-rose-950/30',
          textColor: 'text-rose-400',
          borderColor: 'border-rose-800/50'
        };
      default:
        return {
          bgColor: 'bg-zinc-950/30',
          textColor: 'text-zinc-400',
          borderColor: 'border-zinc-800/50'
        };
    }
  };

  const readinessStyling = getReadinessStyling(readinessLevel || 'CONNECTED');
  const confidenceStyling = getConfidenceStyling(expectedConfidence || 'LOW');
  const ReadinessIcon = readinessStyling.icon;

  return (
    <Card className="bg-zinc-800/40 border border-zinc-700/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-medium text-zinc-100 flex items-center gap-2">
          <ReadinessIcon className="w-5 h-5" />
          Recommendation Readiness
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Readiness Level */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-zinc-400">Readiness Level</span>
          <div className={`inline-flex items-center gap-1 px-2 py-1 rounded ${readinessStyling.bgColor} ${readinessStyling.borderColor} border`}>
            <ReadinessIcon className="w-3 h-3" />
            <span className={`text-xs font-medium ${readinessStyling.textColor}`}>
              {(readinessLevel || 'CONNECTED').replace('_', ' ')}
            </span>
          </div>
        </div>

        {/* Expected Confidence */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-zinc-400">Expected Confidence</span>
          <div className={`inline-flex items-center gap-1 px-2 py-1 rounded ${confidenceStyling.bgColor} ${confidenceStyling.borderColor} border`}>
            <span className={`text-xs font-medium ${confidenceStyling.textColor}`}>
              {expectedConfidence}
            </span>
          </div>
        </div>

        {/* Completeness Score */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-zinc-400">Intelligence Completeness</span>
          <span className="text-sm font-medium text-zinc-200">{completenessScore}%</span>
        </div>

        {/* Available Signals */}
        {availableSignals.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-zinc-300 mb-2">Available Signals</h4>
            <div className="space-y-1">
              {availableSignals.map((signal, index) => (
                <div key={index} className="flex items-center justify-between text-xs">
                  <span className="text-emerald-400">✓ {signal.name}</span>
                  <span className="text-zinc-500">+{signal.impact}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Missing Signals */}
        {missingSignals.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-zinc-300 mb-2">Missing Signals</h4>
            <div className="space-y-1">
              {missingSignals.map((signal, index) => (
                <div key={index} className="flex items-center justify-between text-xs">
                  <span className="text-amber-400">○ {signal.name}</span>
                  <span className="text-zinc-500">-{signal.impact}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Manual Test Cases Upload */}
        {repositoryId && (
          <div className="pt-2 border-t border-zinc-700/50">
            {showUpload ? (
              <div className="space-y-3">
                <div className="border-2 border-dashed border-zinc-700 rounded-lg p-4 text-center">
                  <FileText className="w-6 h-6 text-zinc-500 mx-auto mb-2" />
                  <p className="text-xs text-zinc-400 mb-2">Upload CSV with manual test cases</p>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleUpload(file);
                    }}
                    disabled={uploading}
                    className="hidden"
                    id="manual-csv-upload"
                  />
                  <label
                    htmlFor="manual-csv-upload"
                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded text-xs cursor-pointer ${
                      uploading
                        ? "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                        : "bg-blue-600 hover:bg-blue-700 text-white"
                    }`}
                  >
                    {uploading ? "Uploading..." : "Select CSV File"}
                  </label>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowUpload(false)}
                  className="text-zinc-500 hover:text-white text-xs"
                >
                  Cancel
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowUpload(true)}
                className="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700 text-xs"
              >
                <Upload className="w-3 h-3 mr-2" />
                Upload Manual Test Cases
              </Button>
            )}
          </div>
        )}

        {/* Generation Status */}
        <div className="pt-2 border-t border-zinc-700/50">
          <div className="flex items-center justify-between">
            <span className="text-sm text-zinc-400">Can Generate</span>
            <Badge variant={canGenerate ? "default" : "secondary"}>
              {canGenerate ? "Yes" : "No"}
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
