import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Clock, User, FileText, AlertCircle, X } from 'lucide-react';

interface ReleaseHistoryEvent {
  eventType: string;
  actorName: string | null;
  previousStatus: string | null;
  newStatus: string | null;
  note: string | null;
  createdAt: string | null;
  historyId: string | null;
  actorId: string | null;
  snapshotHash: string | null;
}

interface ReleaseDecisionHistoryDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  history: ReleaseHistoryEvent[];
  decisionStatus: string;
  auditMode?: boolean;
}

const getEventColor = (eventType: string): string => {
  switch (eventType) {
    case 'APPROVED':
      return 'bg-green-500';
    case 'REJECTED':
      return 'bg-red-500';
    case 'CONDITIONALLY_APPROVED':
      return 'bg-yellow-500';
    case 'RESET':
      return 'bg-blue-500';
    case 'REQUESTED':
      return 'bg-purple-500';
    case 'CANCELLED':
      return 'bg-gray-500';
    default:
      return 'bg-gray-400';
  }
};

const formatTimestamp = (timestamp: string | null): string => {
  if (!timestamp) return 'Unknown';
  try {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC'
    }) + ' UTC';
  } catch {
    return timestamp;
  }
};

export const ReleaseDecisionHistoryDrawer: React.FC<ReleaseDecisionHistoryDrawerProps> = ({
  open,
  onOpenChange,
  history,
  decisionStatus,
  auditMode = false
}) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Release Decision History</DialogTitle>
        </DialogHeader>
        <div className="flex-1 overflow-y-auto px-1">
          {history.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Clock className="h-12 w-12 text-gray-400 mb-4" />
              <p className="text-gray-500">No history events yet.</p>
            </div>
          ) : (
            <div className="space-y-4 pb-4">
              {history.map((event, index) => (
                <div
                  key={event.historyId || index}
                  className="relative pl-8 pb-4 border-l-2 border-gray-200 last:border-0"
                >
                  <div className={`absolute left-0 top-0 -translate-x-1/2 w-4 h-4 rounded-full ${getEventColor(event.eventType)}`} />
                  
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline" className="text-xs">
                            {event.eventType}
                          </Badge>
                          {auditMode && event.historyId && (
                            <span className="text-xs text-gray-400">ID: {event.historyId.slice(0, 8)}...</span>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <User className="h-4 w-4" />
                          <span className="font-medium">{event.actorName || 'Unknown'}</span>
                          {auditMode && event.actorId && (
                            <span className="text-xs text-gray-400">({event.actorId.slice(0, 8)}...)</span>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-2 text-sm text-gray-500">
                          <Clock className="h-3 w-3" />
                          <span>{formatTimestamp(event.createdAt)}</span>
                        </div>
                        
                        {event.previousStatus && event.newStatus && (
                          <div className="text-sm text-gray-600">
                            <span className="font-medium">{event.previousStatus}</span>
                            <span className="mx-1">→</span>
                            <span className="font-medium">{event.newStatus}</span>
                          </div>
                        )}
                        
                        {event.note && (
                          <div className="flex items-start gap-2 text-sm bg-gray-50 p-2 rounded">
                            <FileText className="h-4 w-4 text-gray-400 mt-0.5 flex-shrink-0" />
                            <span className="text-gray-700">{event.note}</span>
                          </div>
                        )}
                        
                        {auditMode && event.snapshotHash && (
                          <div className="text-xs text-gray-400 font-mono">
                            Snapshot: {event.snapshotHash.slice(0, 12)}...
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          
          {auditMode && (
            <div className="mt-6 p-3 bg-yellow-50 border border-yellow-200 rounded">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-yellow-600 mt-0.5" />
                <div className="text-xs text-yellow-800">
                  <strong>Audit Mode:</strong> Internal IDs and snapshot hashes are exposed for governance purposes.
                </div>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
