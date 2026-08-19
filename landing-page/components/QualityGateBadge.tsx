/**
 * Quality Gate Badge Component
 *
 * Displays the live quality gate status derived from the regression scope
 * release decision — not the stale readiness snapshot.
 *
 * Two pieces of information are shown:
 * 1. Quality Gate Profile: CONFIGURED | MISSING
 * 2. Evidence Readiness: READY | READY_WITH_REVIEW | BLOCKED
 */

import React from 'react';
import type {
  QualityGateProfileStatus,
  EvidenceReadiness,
} from '@/lib/quality-gate';

interface QualityGateBadgeProps {
  qualityGateProfileStatus: QualityGateProfileStatus;
  evidenceReadiness: EvidenceReadiness;
}

export function QualityGateBadge({
  qualityGateProfileStatus,
  evidenceReadiness,
}: QualityGateBadgeProps) {
  const profileLabel =
    qualityGateProfileStatus === 'CONFIGURED'
      ? 'Profile: Configured'
      : 'Profile: Missing';

  const profileStyle =
    qualityGateProfileStatus === 'CONFIGURED'
      ? 'bg-emerald-950/20 text-emerald-400 border-emerald-800/40'
      : 'bg-amber-950/20 text-amber-400 border-amber-800/40';

  const readinessLabel: Record<EvidenceReadiness, string> = {
    READY: 'Evidence Readiness: READY',
    READY_WITH_REVIEW: 'Evidence Readiness: REVIEW',
    BLOCKED: 'Evidence Readiness: BLOCKED',
  };

  const readinessStyle: Record<EvidenceReadiness, string> = {
    READY: 'bg-emerald-950/20 text-emerald-400 border-emerald-800/40',
    READY_WITH_REVIEW: 'bg-amber-950/20 text-amber-400 border-amber-800/40',
    BLOCKED: 'bg-rose-950/20 text-rose-400 border-rose-800/40',
  };

  return (
    <div className="flex items-center gap-2">
      <span
        className={`px-2 py-1 text-xs font-semibold rounded border ${profileStyle}`}
      >
        Quality Gate {profileLabel}
      </span>
      <span
        className={`px-2 py-1 text-xs font-semibold rounded border ${readinessStyle[evidenceReadiness]}`}
      >
        {readinessLabel[evidenceReadiness]}
      </span>
    </div>
  );
}
