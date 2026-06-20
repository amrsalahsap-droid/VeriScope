"use client";

import React from "react";
import { CheckCircle2, AlertTriangle, XCircle, Clock, Shield, Info } from "lucide-react";

interface ReleaseReadinessVerdictProps {
  verdict: "READY_WITH_RISK" | "NOT_READY" | "NEEDS_MORE_EVIDENCE" | "VERIFIED" | "PARTIALLY_VERIFIED";
  reason: string[];
  impactedAreas: string[];
  confidence?: string;
  className?: string;
  regressionEvidence?: any;
}

export default function ReleaseReadinessVerdict({ 
  verdict, 
  reason, 
  impactedAreas, 
  confidence,
  className = "",
  regressionEvidence
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
      description: "Core tests passed, but critical requirements still need review before release."
    }
  };

  const config = verdictConfig[verdict];
  
  let title = config.title;
  let description = config.description;
  let iconColor = config.color;
  let iconBgColor = config.bgColor;
  let iconBorderColor = config.borderColor;
  let Icon = config.icon;

  const summarySource = regressionEvidence && regressionEvidence.decisionSummary
    ? {
        health: regressionEvidence.decisionSummary.health,
        decisionCopy: regressionEvidence.decisionSummary.decisionCopy,
        graphQuality: regressionEvidence.graphQuality || { traceabilityQuality: 0.8 },
        counts: {
          verifiedByCurrentPr: regressionEvidence.decisionSummary.coveredByPassedPrTests ?? 0,
          failedTests: regressionEvidence.decisionSummary.failedCurrentPrTests ?? 0,
          requiredTestsNotRun: 0,
          missingTests: regressionEvidence.decisionSummary.missingAutomatedCoverage ?? 0,
          notMappedTraceabilityRisks: regressionEvidence.decisionSummary.traceabilityReviewNeeded ?? 0,
        }
      }
    : regressionEvidence;

  let decCopy = {};
  if (summarySource && summarySource.health) {
    const health = summarySource.health;
    decCopy = summarySource.decisionCopy || {};
    
    if (health === "READY") {
      Icon = CheckCircle2;
      iconColor = "text-emerald-400";
      iconBgColor = "bg-emerald-950/20";
      iconBorderColor = "border-emerald-800/40";
      title = decCopy.headline || "All Required Evidence Covered";
      description = decCopy.explanation || "All required regression evidence is covered.";
    } else if (health === "READY_WITH_TRACEABILITY_ISSUES" || health === "VALIDATION_PASSED_TRACEABILITY_INCOMPLETE") {
      Icon = AlertTriangle;
      iconColor = "text-amber-400";
      iconBgColor = "bg-amber-950/20";
      iconBorderColor = "border-emerald-800/40";
      title = decCopy.headline || "Validation Passed, Traceability Incomplete";
      description = decCopy.explanation || "Current PR execution passed tests, but Veriscope could not reliably map many requirements to evidence.";
    } else if (health === "NEEDS_TRACEABILITY_REVIEW") {
      Icon = AlertTriangle;
      iconColor = "text-rose-400";
      iconBgColor = "bg-rose-950/20";
      iconBorderColor = "border-rose-800/40";
      title = decCopy.headline || "Traceability Review Needed";
      description = decCopy.explanation || "Current PR execution passed tests, but requirement mapping is incomplete. Review unmapped requirements before trusting missing-test recommendations.";
    } else if (health === "STALE_INPUTS") {
      Icon = AlertTriangle;
      iconColor = "text-amber-400";
      iconBgColor = "bg-amber-950/20";
      iconBorderColor = "border-amber-800/40";
      title = decCopy.headline || "Stale Inputs — Regeneration Required";
      description = decCopy.explanation || "Current PR execution passed tests, but traceability is incomplete. Regenerate the recommendation to rebuild evidence mapping from the latest inputs.";
    } else if (health === "BLOCKED_BY_FAILED_TESTS") {
      Icon = XCircle;
      iconColor = "text-rose-400";
      iconBgColor = "bg-rose-950/20";
      iconBorderColor = "border-rose-800/40";
      title = decCopy.headline || "Evidence Review Blocked by Failed Tests";
      description = decCopy.explanation || "Current PR execution has failed test(s). Fix failing tests before proceeding with regression scope creation.";
    } else if (health === "BLOCKED_BY_SKIPPED_REQUIRED_TESTS") {
      Icon = XCircle;
      iconColor = "text-rose-400";
      iconBgColor = "bg-rose-950/20";
      iconBorderColor = "border-rose-800/40";
      title = decCopy.headline || "Evidence Review Blocked by Skipped Required Tests";
      description = decCopy.explanation || "Current PR execution skipped required test(s). Run skipped tests before proceeding with regression scope creation.";
    } else if (health === "BLOCKED") {
      // Legacy health state
      Icon = XCircle;
      iconColor = "text-rose-400";
      iconBgColor = "bg-rose-950/20";
      iconBorderColor = "border-rose-800/40";
      title = decCopy.headline || "Evidence Review Blocked";
      description = decCopy.explanation || "No current PR execution tests passed, or critical failures block validation.";
    } else if (health === "READY_WITH_GAPS" || health === "VALIDATION_PASSED_COVERAGE_INCOMPLETE") {
      // Legacy or V2 health state
      const missing = summarySource.counts?.missingTests || summarySource.counts?.missingAutomatedCoverage || 0;
      if (missing > 0) {
        Icon = Shield;
        iconColor = "text-purple-400";
        iconBgColor = "bg-purple-950/20";
        iconBorderColor = "border-purple-800/40";
      } else {
        Icon = Shield;
        iconColor = "text-emerald-400";
        iconBgColor = "bg-emerald-950/20";
        iconBorderColor = "border-emerald-800/40";
      }
      title = decCopy.headline || "Verified with Missing Automation";
      description = decCopy.explanation || "Current PR execution passed all tests. Veriscope found required scenarios without automated evidence.";
    }
  }

  // Filter out the misleading "X of Y required tests are available" reason text
  let displayReasons = reason.filter(r => !r.includes("required tests are available"));

  // Show the parent requirement breakdown when traceability is below threshold
  if (summarySource) {
    const isBelowThreshold = summarySource.health === "NEEDS_TRACEABILITY_REVIEW" || 
                             summarySource.health === "READY_WITH_TRACEABILITY_ISSUES" || 
                             summarySource.health === "VALIDATION_PASSED_TRACEABILITY_INCOMPLETE" || 
                             summarySource.health === "VALIDATION_PASSED_COVERAGE_INCOMPLETE" || 
                             (summarySource.graphQuality?.traceabilityQuality ?? 1.0) < 0.8;
    
    if (isBelowThreshold) {
      const counts = summarySource.counts || {};
      const verified = counts.verifiedByCurrentPr || 0;
      const failed = counts.failedTests || 0;
      const notRun = counts.requiredTestsNotRun || 0;
      const missing = counts.missingTests || 0;
      const unmapped = counts.notMappedTraceabilityRisks || 0;
      const total = verified + failed + notRun + missing + unmapped;
      
      const parts = [
        `${verified} verified`,
        missing > 0 ? `${missing} missing automation` : null,
        unmapped > 0 ? `${unmapped} unmapped/needs review` : null,
        failed > 0 ? `${failed} failed` : null,
        notRun > 0 ? `${notRun} not run` : null
      ].filter(Boolean).join(", ");
      
      const breakdown = `${total} parent requirements analyzed: ${parts}.`;
      displayReasons.push(breakdown);
    }
  }

  return (
    <div className={`bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-5 ${className}`}>
      <div className="flex items-start gap-4">
        <div className={`p-3 rounded-lg ${iconBgColor} ${iconBorderColor} border`}>
          <Icon className={`w-6 h-6 ${iconColor}`} />
        </div>
        
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h2 className="text-lg font-semibold text-white">{title}</h2>
            {confidence && (
              <span className="text-xs text-zinc-400 bg-zinc-800/40 px-2 py-1 rounded">
                {confidence} confidence
              </span>
            )}
          </div>
          
          <p className="text-sm text-zinc-300 mb-4">{description}</p>
          
          {/* Reason Section */}
          {displayReasons.length > 0 && (
            <div className="mb-4">
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Reason</h3>
              <ul className="space-y-1">
                {displayReasons.map((point, index) => (
                  <li key={index} className="text-sm text-zinc-300 flex items-start gap-2">
                    <span className="text-zinc-500 mt-1">•</span>
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          
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
          
          {/* CTA Buttons */}
          {decCopy && ((decCopy as any).primaryCta || (decCopy as any).secondaryCta) && (
            <div className="mt-5 flex flex-wrap gap-3">
              {(decCopy as any).primaryCta && (
                <button className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-semibold transition-all">
                  {(decCopy as any).primaryCta}
                </button>
              )}
              {(decCopy as any).secondaryCta && (
                <button className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs font-semibold transition-all">
                  {(decCopy as any).secondaryCta}
                </button>
              )}
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
  coverageRatio: number | null,
  regressionEvidence?: any
): string[] {
  const reasons: string[] = [];
  
  const summarySource = regressionEvidence && regressionEvidence.decisionSummary
    ? {
        health: regressionEvidence.decisionSummary.health,
        decisionCopy: regressionEvidence.decisionSummary.decisionCopy,
        counts: {
          verifiedByCurrentPr: regressionEvidence.decisionSummary.coveredByPassedPrTests ?? 0,
          failedTests: regressionEvidence.decisionSummary.failedCurrentPrTests ?? 0,
          requiredTestsNotRun: 0,
          missingTests: regressionEvidence.decisionSummary.missingAutomatedCoverage ?? 0,
          notMappedTraceabilityRisks: regressionEvidence.decisionSummary.traceabilityReviewNeeded ?? 0,
        }
      }
    : regressionEvidence;

  // Add behavior impact reasons
  if (impactedBehaviors.length > 0) {
    const behaviorList = impactedBehaviors.slice(0, 3).join(", ");
    reasons.push(`${impactedBehaviors.length > 3 ? "Key behaviors" : "Behaviors"} impacted: ${behaviorList}${impactedBehaviors.length > 3 ? ` and ${impactedBehaviors.length - 3} more` : ""}.`);
  }
  
  // Add test coverage reasons - use backend decision copy if available
  if (summarySource && summarySource.decisionCopy && summarySource.decisionCopy.explanation) {
    // Use backend-provided explanation instead of generating our own
    const backendExplanation = summarySource.decisionCopy.explanation;
    if (backendExplanation && !backendExplanation.includes("required tests are available")) {
      // Only use backend explanation if it doesn't contain the problematic "X of Y" pattern
      reasons.push(backendExplanation);
      return reasons;
    }
  }
  
  // Fallback to legacy reason generation
  if (verdict === "VERIFIED") {
    reasons.push(`All ${recommendedTests.length} recommended tests are available and passing.`);
  } else if (verdict === "PARTIALLY_VERIFIED") {
    // Use count of visible required items for alignment
    const verified = summarySource?.counts?.verifiedByCurrentPr || recommendedTests.length;
    const missing = summarySource?.counts?.missingTests || missingScenarios.length;
    const notMapped = summarySource?.counts?.notMappedTraceabilityRisks || 0;
    // Use the visible required items count (from regression scope) for the reason
    const requiredCount = missing; // This aligns with the visible required items count
    reasons.push(`${verified} tests passed. ${requiredCount} critical requirements still lack automated coverage and require review or execution.`);
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
