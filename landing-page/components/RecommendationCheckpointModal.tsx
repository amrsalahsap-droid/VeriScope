import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, AlertTriangle, XCircle, Play, Eye, Settings, RefreshCw } from 'lucide-react';

interface Signal {
  name: string;
  present: boolean;
  impact: number;
  description?: string;
  optional?: boolean;
  benefit?: string;
  estimated_gain?: string;
  effort?: string;
}

interface CheckpointAction {
  action: string;
  benefit: string;
  estimated_gain: string;
  effort: string;
}

interface CheckpointModalProps {
  isOpen: boolean;
  onClose: () => void;
  onContinue: () => void;
  onAction?: (action: string) => void;
  readinessLevel: string;
  expectedConfidence: string;
  availableSignals: Signal[];
  missingSignals: Signal[];
  canContinue: boolean;
  recommendedActions?: CheckpointAction[];
  actionType?: 'generate' | 'view' | 'rerun';
}

export default function RecommendationCheckpointModal({
  isOpen,
  onClose,
  onContinue,
  onAction,
  readinessLevel = 'CONNECTED',
  expectedConfidence = 'LOW',
  availableSignals = [],
  missingSignals = [],
  canContinue = true,
  recommendedActions = [],
  actionType = 'generate'
}: CheckpointModalProps) {
  const [selectedAction, setSelectedAction] = useState<string | null>(null);

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
          icon: AlertTriangle
        };
    }
  };

  const getActionIcon = (action: string) => {
    if (action.includes('Acceptance Criteria')) return Settings;
    if (action.includes('Coverage')) return RefreshCw;
    if (action.includes('Test')) return Play;
    return Settings;
  };

  const getActionButtonText = () => {
    switch (actionType) {
      case 'generate':
        return 'Generate Recommendation';
      case 'view':
        return 'View Recommendation';
      case 'rerun':
        return 'Regenerate Recommendation';
      default:
        return 'Continue';
    }
  };

  const readinessStyling = getReadinessStyling(readinessLevel);
  const ReadinessIcon = readinessStyling.icon;

  const handleAction = (action: string) => {
    setSelectedAction(action);
    if (onAction) {
      onAction(action);
    }
  };

  const handleContinue = () => {
    onContinue();
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-zinc-900 border-zinc-700 text-zinc-100 max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            Pre-Recommendation Checkpoint
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Readiness Summary */}
          <Card className="bg-zinc-800/40 border-zinc-700/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-medium text-zinc-100">Readiness Assessment</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-zinc-400">Readiness Level</span>
                <div className={`inline-flex items-center gap-1 px-2 py-1 rounded ${readinessStyling.bgColor} ${readinessStyling.borderColor} border`}>
                  <ReadinessIcon className="w-3 h-3" />
                  <span className={`text-xs font-medium ${readinessStyling.textColor}`}>
                    {(readinessLevel || 'CONNECTED').replace('_', ' ')}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-zinc-400">Expected Confidence</span>
                <Badge variant="outline" className="text-amber-400 border-amber-800/50">
                  {expectedConfidence}
                </Badge>
              </div>

              <div className="text-sm text-zinc-300">
                <span className="font-medium">Available Signals: {availableSignals.length}</span> | 
                <span className="font-medium ml-2">Missing Signals: {missingSignals.length}</span>
              </div>
            </CardContent>
          </Card>

          {/* Available Signals */}
          {availableSignals.length > 0 && (
            <Card className="bg-zinc-800/40 border-zinc-700/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-emerald-400">Available Signals</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {availableSignals.map((signal, index) => (
                    <div key={index} className="flex items-center justify-between text-sm">
                      <span className="text-emerald-400 flex items-center gap-2">
                        <CheckCircle2 className="w-3 h-3" />
                        {signal.name}
                      </span>
                      <span className="text-zinc-500 text-xs">+{signal.impact}% confidence</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Missing Signals */}
          {missingSignals.length > 0 && (
            <Card className="bg-zinc-800/40 border-zinc-700/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-amber-400">Missing Signals</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  {missingSignals.map((signal, index) => (
                    <div key={index} className="flex items-center justify-between text-sm">
                      <span className="text-amber-400 flex items-center gap-2">
                        <AlertTriangle className="w-3 h-3" />
                        {signal.name}
                        {signal.optional && (
                          <Badge variant="secondary" className="text-xs">Optional</Badge>
                        )}
                      </span>
                      <span className="text-zinc-500 text-xs">-{signal.impact}% confidence</span>
                    </div>
                  ))}
                </div>

                {recommendedActions.length > 0 && (
                  <div className="pt-3 border-t border-zinc-700/50">
                    <h4 className="text-sm font-medium text-zinc-300 mb-3">Recommended Actions</h4>
                    <div className="space-y-2">
                      {recommendedActions.map((action, index) => {
                        const ActionIcon = getActionIcon(action.action);
                        return (
                          <div key={index} className="bg-zinc-900/50 border border-zinc-700/50 rounded-lg p-3">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  <ActionIcon className="w-4 h-4 text-zinc-400" />
                                  <span className="text-sm font-medium text-zinc-200">{action.action}</span>
                                </div>
                                <p className="text-xs text-zinc-400 mb-2">{action.benefit}</p>
                                <div className="flex items-center gap-3 text-xs">
                                  <span className="text-emerald-400">{action.estimated_gain}</span>
                                  <span className="text-zinc-500">Effort: {action.effort}</span>
                                </div>
                              </div>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleAction(action.action)}
                                className="border-zinc-600 text-zinc-300 hover:bg-zinc-700"
                              >
                                Add
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-between pt-4 border-t border-zinc-700/50">
            <Button
              variant="ghost"
              onClick={onClose}
              className="text-zinc-400 hover:text-white"
            >
              Cancel
            </Button>
            
            <div className="flex items-center gap-3">
              {missingSignals.length > 0 && (
                <div className="text-sm text-zinc-400">
                  {canContinue ? 'You can continue anyway' : 'Additional signals required'}
                </div>
              )}
              
              <Button
                onClick={handleContinue}
                disabled={!canContinue}
                className={canContinue 
                  ? "bg-emerald-600 hover:bg-emerald-500 text-white" 
                  : "bg-zinc-700 text-zinc-500 cursor-not-allowed"
                }
              >
                {actionType === 'generate' && <Play className="w-4 h-4 mr-2" />}
                {actionType === 'view' && <Eye className="w-4 h-4 mr-2" />}
                {actionType === 'rerun' && <RefreshCw className="w-4 h-4 mr-2" />}
                {getActionButtonText()}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
