/**
 * Quality Gate Badge Component
 * Displays the quality gate status (PASSED, PASSED_WITH_OVERRIDE, PARTIAL, BLOCKED, UNKNOWN)
 */

import React from 'react';

interface QualityGateBadgeProps {
  gateStatus: 'PASSED' | 'PASSED_WITH_OVERRIDE' | 'PARTIAL' | 'BLOCKED' | 'UNKNOWN';
}

export function QualityGateBadge({ gateStatus }: QualityGateBadgeProps) {
  const getDisplayLabel = (): string => {
    switch (gateStatus) {
      case 'PASSED':
        return 'PASSED';
      case 'PASSED_WITH_OVERRIDE':
        return 'PASSED (Override)';
      case 'PARTIAL':
        return 'PARTIAL';
      case 'BLOCKED':
        return 'BLOCKED';
      case 'UNKNOWN':
      default:
        return 'UNKNOWN';
    }
  };

  const getBadgeStyle = () => {
    switch (gateStatus) {
      case 'PASSED':
        return 'bg-emerald-950/20 text-emerald-400 border-emerald-800/40';
      case 'PASSED_WITH_OVERRIDE':
        return 'bg-amber-950/20 text-amber-400 border-amber-800/40';
      case 'PARTIAL':
        return 'bg-amber-950/20 text-amber-400 border-amber-800/40';
      case 'BLOCKED':
        return 'bg-rose-950/20 text-rose-400 border-rose-800/40';
      case 'UNKNOWN':
      default:
        return 'bg-zinc-950/20 text-zinc-400 border-zinc-800/40';
    }
  };

  return (
    <span className={`px-2 py-1 text-xs font-semibold rounded border ${getBadgeStyle()}`}>
      Quality Gate: {getDisplayLabel()}
    </span>
  );
}
