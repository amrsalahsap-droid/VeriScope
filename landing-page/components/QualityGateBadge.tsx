/**
 * Quality Gate Badge Component
 * Displays the quality gate status (PASSED, PARTIAL, FAILED, BLOCKED, UNKNOWN)
 */

import React from 'react';

interface QualityGateBadgeProps {
  hasRequiredItems: boolean;
  isApproved: boolean;
}

export function QualityGateBadge({ hasRequiredItems, isApproved }: QualityGateBadgeProps) {
  const getQualityGate = (): string => {
    if (isApproved && !hasRequiredItems) return 'PASSED';
    if (hasRequiredItems) return 'PARTIAL';
    return 'UNKNOWN';
  };

  const getBadgeStyle = () => {
    const qualityGate = getQualityGate();
    switch (qualityGate) {
      case 'PASSED':
        return 'bg-emerald-950/20 text-emerald-400 border-emerald-800/40';
      case 'PARTIAL':
        return 'bg-amber-950/20 text-amber-400 border-amber-800/40';
      case 'FAILED':
        return 'bg-red-950/20 text-red-400 border-red-800/40';
      case 'BLOCKED':
        return 'bg-rose-950/20 text-rose-400 border-rose-800/40';
      default:
        return 'bg-zinc-950/20 text-zinc-400 border-zinc-800/40';
    }
  };

  return (
    <span className={`px-2 py-1 text-xs font-semibold rounded border ${getBadgeStyle()}`}>
      Quality Gate: {getQualityGate()}
    </span>
  );
}
