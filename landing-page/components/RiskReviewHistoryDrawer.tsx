import { History, Clock, User, AlertCircle, CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface HistoryEvent {
  eventType: string;
  reviewStatus: string;
  originalRiskLevel: string;
  originalPriority: string;
  reviewedRiskLevel: string;
  reviewedPriority: string;
  reviewerName: string;
  reviewerId?: string | null;
  reviewNote?: string | null;
  sourceSnapshotHash?: string | null;
  createdAt: string;
  isActive: boolean;
  reviewId?: string | null;
}

interface TransitionSummary {
  firstReviewedAt: string | null;
  lastReviewedAt: string | null;
  lastReviewerName: string | null;
  activeStatus: string;
  totalEvents: number;
  resetCount: number;
  overrideCount: number;
  needsDiscussionCount: number;
  acceptedCount: number;
}

interface HistoryItem {
  sourceAcNumber: number | null;
  readableId: string;
  sourceRequirementId?: string | null;
  title: string;
  currentEffectiveRiskLevel: string;
  currentReviewStatus: string;
  history: HistoryEvent[];
  transitionSummary: TransitionSummary;
}

interface RiskReviewHistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  item: HistoryItem | null;
  auditMode?: boolean;
}

export function RiskReviewHistoryDrawer({ isOpen, onClose, item, auditMode = false }: RiskReviewHistoryDrawerProps) {
  if (!item) return null;

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'ACCEPTED':
        return <CheckCircle2 className="w-4 h-4 text-green-400" />;
      case 'OVERRIDDEN':
        return <XCircle className="w-4 h-4 text-purple-400" />;
      case 'NEEDS_DISCUSSION':
        return <AlertCircle className="w-4 h-4 text-yellow-400" />;
      case 'RESET':
        return <RefreshCw className="w-4 h-4 text-zinc-400" />;
      default:
        return <Clock className="w-4 h-4 text-zinc-400" />;
    }
  };

  const getEventColor = (eventType: string) => {
    switch (eventType) {
      case 'ACCEPTED':
        return 'border-green-500/20 bg-green-950/20';
      case 'OVERRIDDEN':
        return 'border-purple-500/20 bg-purple-950/20';
      case 'NEEDS_DISCUSSION':
        return 'border-yellow-500/20 bg-yellow-950/20';
      case 'RESET':
        return 'border-zinc-500/20 bg-zinc-950/20';
      default:
        return 'border-zinc-500/20 bg-zinc-950/20';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const hasEvents = item.history.length > 0;
  const onlyResets = hasEvents && item.history.every(e => e.eventType === 'RESET');

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 h-full w-full max-w-md bg-zinc-950 border-l border-zinc-800 z-50 shadow-2xl overflow-hidden flex flex-col"
          >
            {/* Header */}
            <div className="p-6 border-b border-zinc-800 bg-zinc-950">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <History className="w-5 h-5 text-zinc-400" />
                  <h2 className="text-lg font-semibold text-white">Review History</h2>
                </div>
                <button
                  onClick={onClose}
                  className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
                >
                  <XCircle className="w-5 h-5 text-zinc-400" />
                </button>
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-zinc-500">{item.readableId}</span>
                  {item.sourceAcNumber && (
                    <span className="text-xs text-zinc-600">AC #{item.sourceAcNumber}</span>
                  )}
                </div>
                <h3 className="text-sm font-medium text-zinc-300">{item.title}</h3>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Empty State */}
              {!hasEvents && (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Clock className="w-12 h-12 text-zinc-600 mb-4" />
                  <p className="text-sm text-zinc-400">
                    No risk review history yet. Generated business risk is currently being used.
                  </p>
                </div>
              )}

              {/* Reset Only State */}
              {onlyResets && (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <RefreshCw className="w-12 h-12 text-zinc-600 mb-4" />
                  <p className="text-sm text-zinc-400">
                    Risk review was reset. Generated risk is currently being used.
                  </p>
                </div>
              )}

              {/* Transition Summary */}
              {hasEvents && !onlyResets && (
                <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-800">
                  <h4 className="text-sm font-semibold text-zinc-300 mb-3 flex items-center gap-2">
                    <User className="w-4 h-4" />
                    Transition Summary
                  </h4>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-zinc-500">First Reviewed:</span>
                      <p className="text-zinc-300">
                        {item.transitionSummary.firstReviewedAt
                          ? formatTimestamp(item.transitionSummary.firstReviewedAt)
                          : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <span className="text-zinc-500">Last Reviewed:</span>
                      <p className="text-zinc-300">
                        {item.transitionSummary.lastReviewedAt
                          ? formatTimestamp(item.transitionSummary.lastReviewedAt)
                          : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <span className="text-zinc-500">Last Reviewer:</span>
                      <p className="text-zinc-300">{item.transitionSummary.lastReviewerName || 'N/A'}</p>
                    </div>
                    <div>
                      <span className="text-zinc-500">Current Status:</span>
                      <p className="text-zinc-300">{item.transitionSummary.activeStatus}</p>
                    </div>
                    <div>
                      <span className="text-zinc-500">Total Events:</span>
                      <p className="text-zinc-300">{item.transitionSummary.totalEvents}</p>
                    </div>
                    <div>
                      <span className="text-zinc-500">Resets:</span>
                      <p className="text-zinc-300">{item.transitionSummary.resetCount}</p>
                    </div>
                    <div>
                      <span className="text-zinc-500">Overrides:</span>
                      <p className="text-zinc-300">{item.transitionSummary.overrideCount}</p>
                    </div>
                    <div>
                      <span className="text-zinc-500">Discussions:</span>
                      <p className="text-zinc-300">{item.transitionSummary.needsDiscussionCount}</p>
                    </div>
                    <div>
                      <span className="text-zinc-500">Accepted:</span>
                      <p className="text-zinc-300">{item.transitionSummary.acceptedCount}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* History Timeline */}
              {hasEvents && (
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    History Timeline
                  </h4>
                  <div className="space-y-3">
                    {item.history.map((event, index) => (
                      <div
                        key={index}
                        className={`p-4 rounded-lg border ${getEventColor(event.eventType)} ${
                          !event.isActive ? 'opacity-60' : ''
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3 mb-2">
                          <div className="flex items-center gap-2">
                            {getEventIcon(event.eventType)}
                            <span className="text-sm font-medium text-zinc-200">
                              {event.eventType}
                            </span>
                          </div>
                          <span className="text-xs text-zinc-500">
                            {formatTimestamp(event.createdAt)}
                          </span>
                        </div>

                        <div className="space-y-2 text-xs">
                          <div className="flex items-center gap-2">
                            <User className="w-3 h-3 text-zinc-500" />
                            <span className="text-zinc-400">
                              {event.reviewerName}
                              {auditMode && event.reviewerId && (
                                <span className="text-zinc-600 ml-1">(ID: {event.reviewerId})</span>
                              )}
                            </span>
                          </div>

                          {event.reviewNote && (
                            <div className="text-zinc-400 italic">
                              "{event.reviewNote}"
                            </div>
                          )}

                          {(event.eventType === 'OVERRIDDEN' || event.eventType === 'NEEDS_DISCUSSION') && (
                            <div className="flex items-center gap-2 text-zinc-500">
                              <span>
                                Risk: {event.originalRiskLevel} → {event.reviewedRiskLevel}
                              </span>
                              <span>
                                Priority: {event.originalPriority} → {event.reviewedPriority}
                              </span>
                            </div>
                          )}

                          {auditMode && (
                            <div className="space-y-1 text-zinc-600 pt-2 border-t border-zinc-800">
                              {event.reviewId && <div>Review ID: {event.reviewId}</div>}
                              {event.sourceSnapshotHash && (
                                <div>Snapshot: {event.sourceSnapshotHash.slice(0, 8)}...</div>
                              )}
                            </div>
                          )}

                          {!event.isActive && (
                            <div className="text-zinc-500 italic">
                              (Inactive history event)
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Current Effective Risk */}
              {hasEvents && !onlyResets && (
                <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-800">
                  <h4 className="text-sm font-semibold text-zinc-300 mb-2">Current Effective Risk</h4>
                  <div className="flex items-center gap-3">
                    <span className={`text-sm font-medium px-2 py-1 rounded ${
                      item.currentEffectiveRiskLevel === 'CRITICAL' ? 'bg-rose-500/10 text-rose-400' :
                      item.currentEffectiveRiskLevel === 'HIGH' ? 'bg-orange-500/10 text-orange-400' :
                      item.currentEffectiveRiskLevel === 'MEDIUM' ? 'bg-amber-500/10 text-amber-400' :
                      item.currentEffectiveRiskLevel === 'LOW' ? 'bg-blue-500/10 text-blue-400' :
                      'bg-zinc-500/10 text-zinc-400'
                    }`}>
                      {item.currentEffectiveRiskLevel}
                    </span>
                    <span className="text-xs text-zinc-500">
                      Status: {item.currentReviewStatus}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-zinc-800 bg-zinc-950">
              <button
                onClick={onClose}
                className="w-full py-2 px-4 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors text-sm"
              >
                Close
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
