// ── Coverage Gap Grouping Logic ─────────────────────────────────────────────

interface GapItem {
  id: string;
  type: 'requirement' | 'behavior' | 'automation';
  name: string;
  coverageStatus: 'covered' | 'partial' | 'missing';
  suggestedAction: string;
  priority: 'critical' | 'must' | 'recommended' | 'optional';
  whyItMatters: string;
  linkedTestId?: string;
  linkedTestTitle?: string;
  source: string;
  requirementId?: string;
  behaviorId?: string;
}

/**
 * Groups coverage gaps into actionable subsections
 * - Critical gaps: High severity, security-related, blocking issues
 * - Missing automated tests: Tests that need to be created
 * - Partial coverage: Areas with some coverage but gaps remain
 * - Optional improvements: Nice-to-have enhancements
 */
export function groupCoverageGaps(gaps: any[], existingTests: any[]): {
  critical: GapItem[];
  missingAutomated: GapItem[];
  partialCoverage: GapItem[];
  optional: GapItem[];
} {
  const result = {
    critical: [] as GapItem[],
    missingAutomated: [] as GapItem[],
    partialCoverage: [] as GapItem[],
    optional: [] as GapItem[]
  };

  // Create a map of existing tests for linking
  const testMap = new Map(
    existingTests.map(t => [t.stable_identity, t])
  );

  gaps.forEach((gap, index) => {
    const gapItem: GapItem = {
      id: `gap-${index}`,
      type: gap.type?.toLowerCase() || 'requirement',
      name: gap.name || 'Unknown gap',
      coverageStatus: normalizeCoverageStatus(gap.coverageStatus),
      suggestedAction: gap.suggestedScenario || gap.suggestedAction || 'Add test coverage',
      priority: normalizePriority(gap.priority, gap.severity),
      whyItMatters: gap.reason || gap.whyItMatters || 'Coverage gap detected',
      source: gap.sourceEvidence || gap.source || 'Analysis',
      requirementId: gap.requirement_id,
      behaviorId: gap.behavior_id
    };

    // Link to existing test if available
    const linkedTest = findLinkedTest(gapItem, testMap);
    if (linkedTest) {
      gapItem.linkedTestId = linkedTest.stable_identity;
      gapItem.linkedTestTitle = linkedTest.display_name || linkedTest.stable_identity;
    }

    // Categorize based on priority and type
    if (gapItem.priority === 'critical') {
      result.critical.push(gapItem);
    } else if (gapItem.coverageStatus === 'missing' && gapItem.type !== 'automation') {
      result.missingAutomated.push(gapItem);
    } else if (gapItem.coverageStatus === 'partial') {
      result.partialCoverage.push(gapItem);
    } else {
      result.optional.push(gapItem);
    }
  });

  return result;
}

function normalizeCoverageStatus(status: string): 'covered' | 'partial' | 'missing' {
  if (!status) return 'missing';
  const s = status.toLowerCase();
  if (s === 'covered' || s === 'full') return 'covered';
  if (s === 'partial' || s === 'partially_covered') return 'partial';
  return 'missing';
}

function normalizePriority(priority: string, severity?: string): 'critical' | 'must' | 'recommended' | 'optional' {
  if (severity === 'CRITICAL' || severity === 'BLOCKER') return 'critical';
  if (severity === 'HIGH' || priority === 'Must') return 'must';
  if (severity === 'MEDIUM' || priority === 'Recommended') return 'recommended';
  return 'optional';
}

function findLinkedTest(gap: GapItem, testMap: Map<string, any>): any | null {
  // Try to find a test that covers this requirement or behavior
  for (const [id, test] of testMap) {
    if (test.requirement_id === gap.requirementId) return test;
    if (test.behavior_id === gap.behaviorId) return test;
    if (test.scenario_intent === gap.name) return test;
  }
  return null;
}

/**
 * Groups AC fragments under consolidated requirements
 */
export function consolidateACFragments(gaps: GapItem[]): GapItem[] {
  const consolidated = new Map<string, GapItem>();

  gaps.forEach(gap => {
    // For requirement gaps, group by requirement ID or similar names
    if (gap.type === 'requirement' && gap.requirementId) {
      const existing = consolidated.get(gap.requirementId);
      if (existing) {
        // Merge into existing requirement
        existing.suggestedAction += `, ${gap.suggestedAction}`;
        existing.whyItMatters += ` ${gap.whyItMatters}`;
      } else {
        consolidated.set(gap.requirementId, gap);
      }
    } else {
      // Keep non-requirement gaps as-is
      consolidated.set(gap.id, gap);
    }
  });

  return Array.from(consolidated.values());
}
