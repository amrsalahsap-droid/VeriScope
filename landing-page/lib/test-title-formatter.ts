// ── Test Title Formatter ─────────────────────────────────────────────

/**
 * Converts technical test identifiers to professional, human-readable titles
 * Examples:
 * - should_reject_weak_password_during_signup → Reject weak password during sign-up
 * - test_accept_strong_password → Accept strong password during sign-up
 * - validate_password_complexity → Validate password complexity requirements
 */
export function formatTestTitle(testId: string | undefined | null, displayName?: string | null): string {
  // If display name is already provided and looks professional, use it
  if (displayName && isProfessionalTitle(displayName)) {
    return displayName;
  }

  // Start with the display name if available, otherwise use test ID
  const input = (displayName || testId || "").trim();
  if (!input) return "Unnamed Test";

  // Remove common test prefixes
  let title = input
    .replace(/^(test_|should_|it_|when_|given_)/i, '')
    .replace(/_test$/i, '')
    .replace(/\.test$/i, '');

  // Convert snake_case to Title Case with spaces
  title = title
    .replace(/_/g, ' ')
    .replace(/-/g, ' ')
    .split(' ')
    .map(word => {
      // Handle common abbreviations
      const lower = word.toLowerCase();
      if (lower === 'id') return 'ID';
      if (lower === 'api') return 'API';
      if (lower === 'ui') return 'UI';
      if (lower === 'url') return 'URL';
      if (lower === 'sql') return 'SQL';
      if (lower === 'json') return 'JSON';
      if (lower === 'xml') return 'XML';
      if (lower === 'http') return 'HTTP';
      if (lower === 'https') return 'HTTPS';
      if (lower === 'jwt') return 'JWT';
      if (lower === 'oauth') return 'OAuth';
      if (lower === '2fa') return '2FA';
      if (lower === 'mfa') return 'MFA';
      
      // Capitalize first letter
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(' ');

  // Common word replacements for better readability
  title = title
    .replace(/\bsignup\b/gi, 'sign-up')
    .replace(/\bsign in\b/gi, 'sign-in')
    .replace(/\blogin\b/gi, 'sign-in')
    .replace(/\breset\b/gi, 'reset')
    .replace(/\bauth\b/gi, 'authentication')
    .replace(/\bvalidate\b/gi, 'Validate')
    .replace(/\bcheck\b/gi, 'Check')
    .replace(/\bverify\b/gi, 'Verify')
    .replace(/\bensure\b/gi, 'Ensure')
    .replace(/\bshould\b/gi, '')
    .replace(/\bwhen\b/gi, '')
    .replace(/\bgiven\b/gi, '');

  // Clean up extra spaces
  title = title.replace(/\s+/g, ' ').trim();

  // If result is empty, return a default
  if (!title) {
    return 'Test validation';
  }

  return title;
}

/**
 * Checks if a title appears to be already professionally formatted
 */
function isProfessionalTitle(title: string): boolean {
  // Professional titles typically:
  // - Don't have underscores
  // - Are Title Case
  // - Don't start with test prefixes
  // - Are reasonably long (not just a single word)
  
  if (title.includes('_')) return false;
  if (/^(test_|should_|it_|when_|given_)/i.test(title)) return false;
  if (title.length < 10) return false;
  
  // Check if it's Title Case (rough check)
  const words = title.split(' ');
  const titleCaseCount = words.filter(w => 
    w.length > 0 && w[0] === w[0].toUpperCase()
  ).length;
  
  return titleCaseCount >= words.length * 0.5;
}

/**
 * Generates a meaningful title for a missing test/scenario
 * Falls back through: requirement title → behavior name → risk area → scenario intent
 */
export function generateMissingTestTitle(scenario: any): string {
  // Try to get a meaningful title from various fields
  // Support both snake_case (API) and camelCase (scenario-coverage-matrix) field names
  const requirementTitle = scenario.requirement_title || scenario.requirement_id;
  const behaviorName = scenario.behavior_name || scenario.scenario_intent
    || scenario.requiredScenario || scenario.required_scenario;
  const riskArea = scenario.impacted_area || scenario.risk_area
    || scenario.impactedArea;
  const scenarioIntent = scenario.scenario_intent || scenario.behavior_description
    || scenario.purpose;

  // Build title from available information
  let base = '';
  
  if (requirementTitle && typeof requirementTitle === 'string') {
    // Extract key words from requirement title
    base = requirementTitle
      .replace(/^(AC-|AC\d+[:\s]*)/i, '') // Remove AC prefix
      .replace(/\b(test|check|validate|verify)\b/gi, '') // Remove test-related words
      .trim();
  }
  
  if (!base && behaviorName && typeof behaviorName === 'string') {
    base = behaviorName.trim();
  }
  
  if (!base && riskArea && typeof riskArea === 'string') {
    base = riskArea.trim();
  }
  
  if (!base && scenarioIntent && typeof scenarioIntent === 'string') {
    base = scenarioIntent.trim();
  }

  // If still no base, use a generic fallback
  if (!base) {
    return 'Create validation test';
  }

  // Clean up the base - make it suitable for a test title
  base = base
    .replace(/\bthe\b/gi, '')
    .replace(/\ba\b/gi, '')
    .replace(/\ban\b/gi, '')
    .replace(/\bfor\b/gi, '')
    .replace(/\bto\b/gi, '')
    .replace(/\bwith\b/gi, '')
    .replace(/\bby\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim();

  // Capitalize first letter
  base = base.charAt(0).toUpperCase() + base.slice(1).toLowerCase();

  // Limit length
  if (base.length > 50) {
    base = base.substring(0, 47) + '...';
  }

  return `Create ${base} validation test`;
}

/**
 * Generates a specific "why selected" reason for a test
 */
export function generateTestWhySelected(test: any, changedFiles: string[]): string {
  const impactedArea = test.impacted_area || 'general functionality';
  const testingType = test.testing_type || 'regression';
  
  // If test has a specific reason, use it
  if (test.reason && test.reason.length > 20) {
    return test.reason;
  }

  // Generate based on test properties
  const fileCount = changedFiles.length;
  const fileContext = fileCount === 1 
    ? `the changed file (${changedFiles[0]})` 
    : `${fileCount} changed files`;

  if (test.tier === 'must_run') {
    return `Selected as must-run because it validates ${impactedArea} for ${fileContext} and maps to critical acceptance criteria.`;
  }

  if (test.tier === 'should_run') {
    return `Recommended because it covers ${impactedArea} impacted by ${fileContext} with moderate risk.`;
  }

  return `Suggested as optional coverage for ${impactedArea} affected by ${fileContext}.`;
}
