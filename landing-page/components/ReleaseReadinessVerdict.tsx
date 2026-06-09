"use client";

import { CheckCircle2, AlertTriangle, XCircle, Clock, Shield, Info } from "lucide-react";

interface ReleaseReadinessVerdictProps {
  verdict: "READY_WITH_RISK" | "NOT_READY" | "NEEDS_MORE_EVIDENCE" | "VERIFIED" | "PARTIALLY_VERIFIED";
  reason: string[];
  impactedAreas: string[];
  confidence?: string;
  className?: string;
}

export default function ReleaseReadinessVerdict({ 
  verdict, 
  reason, 
  impactedAreas, 
  confidence,
  className = "" 
}: ReleaseReadinessVerdictProps) {
  const verdictConfig = {
    READY_WITH_RISK: {
      icon: AlertTriangle,
      color: "text-amber-400",
      bgColor: "bg-amber-950/20",
      borderColor: "border-amber-800/40",
      title: "Release Ready with Risk",
      description: "Ready to proceed with identified risks"
    },
    NOT_READY: {
      icon: XCircle,
      color: "text-rose-400",
      bgColor: "bg-rose-950/20",
      borderColor: "border-rose-800/40",
      title: "Not Ready",
      description: "Critical issues must be addressed before release"
    },
    NEEDS_MORE_EVIDENCE: {
      icon: Clock,
      color: "text-blue-400",
      bgColor: "bg-blue-950/20",
      borderColor: "border-blue-800/40",
      title: "Needs More Evidence",
      description: "Additional testing or information required"
    },
    VERIFIED: {
      icon: CheckCircle2,
      color: "text-emerald-400",
      bgColor: "bg-emerald-950/20",
      borderColor: "border-emerald-800/40",
      title: "Verified Ready",
      description: "Fully tested and ready for release"
    },
    PARTIALLY_VERIFIED: {
      icon: Shield,
      color: "text-purple-400",
      bgColor: "bg-purple-950/20",
      borderColor: "border-purple-800/40",
      title: "Partially Verified",
      description: "Core functionality verified, some areas need attention"
    }
  };

  const config = verdictConfig[verdict];
  const Icon = config.icon;

  return (
    <div className={`bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-5 ${className}`}>
      <div className="flex items-start gap-4">
        <div className={`p-3 rounded-lg ${config.bgColor} ${config.borderColor} border`}>
          <Icon className={`w-6 h-6 ${config.color}`} />
        </div>
        
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h2 className="text-lg font-semibold text-white">{config.title}</h2>
            {confidence && (
              <span className="text-xs text-zinc-400 bg-zinc-800/40 px-2 py-1 rounded">
                {confidence} confidence
              </span>
            )}
          </div>
          
          <p className="text-sm text-zinc-300 mb-4">{config.description}</p>
          
          {/* Reason Section */}
          <div className="mb-4">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Reason</h3>
            <ul className="space-y-1">
              {reason.map((point, index) => (
                <li key={index} className="text-sm text-zinc-300 flex items-start gap-2">
                  <span className="text-zinc-500 mt-1">•</span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
          
          {/* Impacted Areas */}
          {impactedAreas.length > 0 && (
            <div className="bg-zinc-800/40 rounded-lg p-3 border border-zinc-700/50">
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Impacted Areas</h3>
              <div className="flex flex-wrap gap-2">
                {impactedAreas.map((area, index) => (
                  <span 
                    key={index}
                    className="text-xs px-2 py-1 bg-zinc-700/50 text-zinc-300 rounded border border-zinc-600/50"
                  >
                    {area}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Helper function to determine verdict from recommendation data
export function determineReleaseReadinessVerdict(
  recommendedTests: any[],
  missingScenarios: any[],
  evidenceQuality: string,
  coverageRatio: number | null,
  hasFailures: boolean
): "READY_WITH_RISK" | "NOT_READY" | "NEEDS_MORE_EVIDENCE" | "VERIFIED" | "PARTIALLY_VERIFIED" {
  // Normalize coverageRatio: backend may store as 0-1 fraction or 0-100 percentage.
  // Values > 1 are treated as percentage and divided by 100.
  const normalizedCoverage = coverageRatio != null
    ? (coverageRatio > 1 ? coverageRatio / 100 : coverageRatio)
    : null;

  // Check for critical failures
  if (hasFailures) {
    return "NOT_READY";
  }

  // Contradiction guard: HIGH confidence evidence is by definition sufficient.
  // Never return NEEDS_MORE_EVIDENCE when confidence is HIGH.
  const isHighConfidence = evidenceQuality === "HIGH";

  // Non-HIGH confidence with insufficient evidence
  if (!isHighConfidence && (evidenceQuality === "LOW" || normalizedCoverage == null || normalizedCoverage < 0.3)) {
    return "NEEDS_MORE_EVIDENCE";
  }

  // Check for missing critical scenarios
  const criticalMissing = missingScenarios.filter(s => s.priority === "must_run" || s.priority === "BLOCKER");
  if (criticalMissing.length > 0 && !isHighConfidence) {
    return "NOT_READY";
  }

  // HIGH confidence path: verdict is based on code coverage and missing scenario count only
  if (isHighConfidence) {
    const coverageValue = normalizedCoverage ?? 0;
    if (coverageValue >= 0.8 && missingScenarios.length === 0) {
      return "VERIFIED";
    } else if (coverageValue >= 0.6) {
      return missingScenarios.length === 0 ? "VERIFIED" : "PARTIALLY_VERIFIED";
    } else {
      return "READY_WITH_RISK";
    }
  }

  // Medium confidence path: use test coverage percentage against total
  const totalScenarios = recommendedTests.length + missingScenarios.length;
  const testCoveragePercent = totalScenarios > 0 ? (recommendedTests.length / totalScenarios) * 100 : 0;
  const coverageValue = normalizedCoverage ?? 0;

  if (testCoveragePercent >= 70 && coverageValue >= 0.6) {
    return "PARTIALLY_VERIFIED";
  } else if (testCoveragePercent >= 50) {
    return "READY_WITH_RISK";
  } else {
    return "NEEDS_MORE_EVIDENCE";
  }
}

// Helper function to generate reason text
export function generateVerdictReason(
  verdict: string,
  impactedBehaviors: string[],
  recommendedTests: any[],
  missingScenarios: any[],
  coverageRatio: number | null
): string[] {
  const reasons: string[] = [];
  
  // Add behavior impact reasons
  if (impactedBehaviors.length > 0) {
    const behaviorList = impactedBehaviors.slice(0, 3).join(", ");
    reasons.push(`${impactedBehaviors.length > 3 ? "Key behaviors" : "Behaviors"} impacted: ${behaviorList}${impactedBehaviors.length > 3 ? ` and ${impactedBehaviors.length - 3} more` : ""}.`);
  }
  
  // Add test coverage reasons
  if (verdict === "VERIFIED") {
    reasons.push(`All ${recommendedTests.length} recommended tests are available and passing.`);
  } else if (verdict === "PARTIALLY_VERIFIED") {
    reasons.push(`${recommendedTests.length} of ${recommendedTests.length + missingScenarios.length} required tests are available.`);
  } else if (verdict === "READY_WITH_RISK") {
    reasons.push(`Core functionality covered by ${recommendedTests.length} tests, but ${missingScenarios.length} scenarios need attention.`);
  } else if (verdict === "NOT_READY") {
    const criticalMissing = missingScenarios.filter(s => s.priority === "must_run" || s.priority === "BLOCKER");
    reasons.push(`${criticalMissing.length} critical test scenarios are missing coverage.`);
  } else if (verdict === "NEEDS_MORE_EVIDENCE") {
    const normalizedForDisplay = coverageRatio != null
      ? (coverageRatio > 1 ? coverageRatio : Math.round(coverageRatio * 100))
      : 0;
    reasons.push(`Additional evidence needed. Current code coverage: ${normalizedForDisplay}%.`);
  }
  
  return reasons;
}
