import React from "react";
import { Shield, CheckCircle2, XCircle, AlertCircle, RefreshCw, Activity } from "lucide-react";

interface GovernanceSummary {
  activeReviews: number;
  activeAccepted: number;
  activeOverridden: number;
  activeNeedsDiscussion: number;
  resetEvents: number;
  totalHistoryEvents: number;
}

interface RiskReviewGovernancePanelProps {
  governance: GovernanceSummary;
  compact?: boolean;
}

export function RiskReviewGovernancePanel({ governance, compact = false }: RiskReviewGovernancePanelProps) {
  const StatItem = ({ icon: Icon, label, value, color }: { icon: any, label: string, value: number, color: string }) => (
    <div className="flex items-center gap-2">
      <Icon className={`w-4 h-4 ${color}`} />
      <div className="flex flex-col">
        <span className="text-xs text-zinc-500">{label}</span>
        <span className="text-sm font-semibold text-zinc-300">{value}</span>
      </div>
    </div>
  );

  if (compact) {
    return (
      <div className="flex items-center gap-4 text-xs">
        <StatItem
          icon={Activity}
          label="Active"
          value={governance.activeReviews}
          color="text-zinc-400"
        />
        <StatItem
          icon={CheckCircle2}
          label="Accepted"
          value={governance.activeAccepted}
          color="text-green-400"
        />
        <StatItem
          icon={XCircle}
          label="Overridden"
          value={governance.activeOverridden}
          color="text-purple-400"
        />
        <StatItem
          icon={AlertCircle}
          label="Discussion"
          value={governance.activeNeedsDiscussion}
          color="text-yellow-400"
        />
        <StatItem
          icon={RefreshCw}
          label="Resets"
          value={governance.resetEvents}
          color="text-zinc-400"
        />
      </div>
    );
  }

  return (
    <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-800">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-5 h-5 text-zinc-400" />
        <h3 className="text-sm font-semibold text-zinc-300">Governance Summary</h3>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <StatItem
          icon={Activity}
          label="Active Reviews"
          value={governance.activeReviews}
          color="text-zinc-400"
        />
        <StatItem
          icon={CheckCircle2}
          label="Accepted"
          value={governance.activeAccepted}
          color="text-green-400"
        />
        <StatItem
          icon={XCircle}
          label="Overridden"
          value={governance.activeOverridden}
          color="text-purple-400"
        />
        <StatItem
          icon={AlertCircle}
          label="Needs Discussion"
          value={governance.activeNeedsDiscussion}
          color="text-yellow-400"
        />
        <StatItem
          icon={RefreshCw}
          label="Reset Events"
          value={governance.resetEvents}
          color="text-zinc-400"
        />
        <StatItem
          icon={Activity}
          label="Total History Events"
          value={governance.totalHistoryEvents}
          color="text-zinc-400"
        />
      </div>
    </div>
  );
}
