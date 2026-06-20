import React, { useState } from "react";


interface DevConsistencyCheckProps {
  regressionEvidence?: any;
  run?: any;
  result?: any;
}

export function DevConsistencyCheck({ regressionEvidence, run, result }: DevConsistencyCheckProps) {
  const [expanded, setExpanded] = useState(false);

  // Only show in development
  if (process.env.NODE_ENV !== "development") return null;

  // Run consistency assertions
  const errors: string[] = [];
  const warnings: string[] = [];

  if (result) {
    if (result.errors) {
      result.errors.forEach((e: any) => errors.push(e.message || String(e)));
    }
    if (result.warnings) {
      result.warnings.forEach((w: any) => warnings.push(w.message || String(w)));
    }
  }

  if (regressionEvidence) {
    const counts = regressionEvidence.counts || {};
    const verifiedByCurrentPr = regressionEvidence.verifiedByCurrentPr || [];
    const missingTests = regressionEvidence.missingTests || [];
    const acTraceability = regressionEvidence.acTraceability || [];
    const coverageGaps = regressionEvidence.coverageGaps || [];

    // Assertion 1: Executive counts equal rendered section counts
    const executiveVerified = counts.verifiedByCurrentPr || 0;
    const executiveFailed = counts.failedTests || 0;
    const executiveSkipped = counts.skippedTests || 0;
    const executiveNotRun = counts.requiredTestsNotRun || 0;
    const executiveMissing = counts.missingAutomatedCoverage || 0;
    const executiveGaps = counts.coverageGaps || 0;

    if (executiveVerified !== verifiedByCurrentPr.length) {
      errors.push(`Executive verified count (${executiveVerified}) != rendered section (${verifiedByCurrentPr.length})`);
    }
    if (executiveMissing !== missingTests.length) {
      errors.push(`Executive missing count (${executiveMissing}) != rendered section (${missingTests.length})`);
    }

    // Assertion 2: No internal AC IDs visible in normal UI
    const hasInternalIds = acTraceability.some((ac: any) => {
      const id = ac.id || ac.readableId;
      return id && !id.startsWith('AC-') && id.length > 10;
    });
    if (hasInternalIds) {
      warnings.push("Internal AC IDs may be visible in normal UI");
    }

    // Assertion 3: No missing test has currentPrResult = Passed
    const missingWithPassed = missingTests.filter((mt: any) => 
      mt.currentPrResult === 'Passed' || mt.status === 'Passed'
    );
    if (missingWithPassed.length > 0) {
      errors.push(`${missingWithPassed.length} missing tests have currentPrResult = Passed`);
    }

    // Assertion 4: No missing test is also in verifiedByCurrentPr
    const verifiedIds = new Set(verifiedByCurrentPr.map((t: any) => t.id));
    const missingInVerified = missingTests.filter((mt: any) => 
      verifiedIds.has(mt.requirementId)
    );
    if (missingInVerified.length > 0) {
      errors.push(`${missingInVerified.length} missing tests are also in verifiedByCurrentPr`);
    }

    // Assertion 5: Not mapped rows must not be fragments/test data
    const notMapped = acTraceability.filter((ac: any) => ac.coverageStatus === 'Not mapped');
    const fragmentsInNotMapped = notMapped.filter((ac: any) => 
      ac.title?.toLowerCase().includes('fragment') || 
      ac.title?.toLowerCase().includes('test data') ||
      ac.notes?.toLowerCase().includes('fragment')
    );
    if (fragmentsInNotMapped.length > 0) {
      warnings.push(`${fragmentsInNotMapped.length} Not mapped rows may be fragments/test data`);
    }

    // Assertion 6: "18 of 37" must not appear
    const decisionCopy = regressionEvidence.decisionCopy?.explanation || "";
    if (decisionCopy.includes("of") && /\d+\s+of\s+\d+/.test(decisionCopy)) {
      warnings.push(`Decision copy contains "X of Y" pattern: ${decisionCopy}`);
    }

    // Assertion 7: "No remaining tests" must not appear while missing tests > 0
    if (missingTests.length > 0 && decisionCopy.toLowerCase().includes("no remaining")) {
      errors.push(`"No remaining tests" appears while ${missingTests.length} missing tests exist`);
    }

    // Assertion 8: Coverage gap linked test must share flow or explanation
    const gapsWithWrongFlow = coverageGaps.filter((gap: any) => {
      if (!gap.linkedTest) return false;
      // Simple check - in production this would need more sophisticated flow matching
      return gap.reason && !gap.reason.toLowerCase().includes("shared policy");
    });
    if (gapsWithWrongFlow.length > 0) {
      warnings.push(`${gapsWithWrongFlow.length} coverage gaps may have incorrectly linked tests`);
    }
  }

  // Only show if there are errors or warnings
  if (errors.length === 0 && warnings.length === 0) return null;

  return (
    <div className="border border-amber-700/50 bg-amber-950/20 rounded-lg text-xs font-mono overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-amber-950/30 transition-colors"
      >
        <span className="text-amber-400 font-semibold">
          🛠 Dev Consistency:{" "}
          {errors.length > 0 && (
            <span className="text-rose-400">{errors.length} error{errors.length !== 1 ? "s" : ""}</span>
          )}
          {errors.length > 0 && warnings.length > 0 && <span className="text-amber-600">, </span>}
          {warnings.length > 0 && (
            <span className="text-amber-400">{warnings.length} warning{warnings.length !== 1 ? "s" : ""}</span>
          )}
        </span>
        <span className="text-zinc-500 text-[10px]">{expanded ? "▲ hide" : "▼ show"}</span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-1 border-t border-amber-700/30 pt-2">
          {errors.map((e, i) => (
            <div key={i} className="flex items-start gap-1.5 text-rose-400">
              <span className="shrink-0">❌</span>
              <span>{e}</span>
            </div>
          ))}
          {warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-1.5 text-amber-400">
              <span className="shrink-0">⚠</span>
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
