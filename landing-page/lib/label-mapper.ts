// ── Label Mapper for Raw Enums ─────────────────────────────────────────────

/**
 * Maps raw backend enum keys to user-friendly labels
 */
export function mapRawLabel(rawLabel: string): string {
  const labelMap: Record<string, string> = {
    // Recommendation modes
    'FULL_SUITE': 'Full suite',
    'TARGETED': 'Targeted regression',
    'SMOKE': 'Smoke validation',
    'NO_RUN': 'No regression recommended',
    
    // Confidence levels
    'HIGH': 'High',
    'MODERATE': 'Medium',
    'LOW': 'Low',
    
    // Coverage status
    'MISSING_AUTOMATED_COVERAGE': 'Automated coverage missing',
    'PARTIALLY_COVERED': 'Partially covered',
    'MISSING': 'Missing',
    'COVERED': 'Covered',
    
    // Evidence sources
    'acceptance_criteria': 'Acceptance criteria',
    'current_pr_execution': 'Current PR test results',
    'pull_request_diff': 'PR diff',
    'source_signal': 'Evidence source',
    'behavior_mapping_unavailable': 'Business behavior not mapped',
    
    // Priority levels
    'BLOCKER': 'Critical',
    'MUST': 'Must',
    'SHOULD': 'Recommended',
    'OPTIONAL': 'Optional',
    'MEDIUM': 'Medium',
    
    // Test tiers
    'must_run': 'Must run',
    'should_run': 'Should run',
    'fallback': 'Optional',
    
    // Gap types
    'Requirement': 'Requirement',
    'Behavior': 'Behavior',
    'Automation': 'Automation',
    'Scenario': 'Scenario',
    
    // Status
    'FAILED': 'Failed',
    'SUCCESS': 'Success',
    'PENDING': 'Pending',
    'IN_PROGRESS': 'In progress',
  };
  
  // Check if exact match exists
  if (labelMap[rawLabel]) {
    return labelMap[rawLabel];
  }
  
  // Convert snake_case to Title Case as fallback
  return rawLabel
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Converts snake_case to readable Title Case
 */
export function toTitleCase(snakeCase: string): string {
  return snakeCase
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Generates business impact description based on changed files
 */
export function generateBusinessImpact(changedFiles: string[]): string {
  const hasAuth = changedFiles.some(f => 
    f.toLowerCase().includes('auth') || f.toLowerCase().includes('password') || 
    f.toLowerCase().includes('login') || f.toLowerCase().includes('token')
  );
  const hasUI = changedFiles.some(f => 
    f.toLowerCase().includes('form') || f.toLowerCase().includes('component') || 
    f.toLowerCase().includes('ui') || f.toLowerCase().includes('view')
  );
  const hasAPI = changedFiles.some(f => 
    f.toLowerCase().includes('route') || f.toLowerCase().includes('api') || 
    f.toLowerCase().includes('controller') || f.toLowerCase().includes('service')
  );
  const hasTest = changedFiles.some(f => 
    f.toLowerCase().includes('test') || f.toLowerCase().includes('spec')
  );
  
  const impacts: string[] = [];
  
  if (hasAuth) {
    impacts.push('Authentication/account security behavior may be affected');
  }
  if (hasUI) {
    impacts.push('User interface validation changed');
  }
  if (hasAPI) {
    impacts.push('API endpoints or business logic modified');
  }
  if (hasTest) {
    impacts.push('Test coverage updated');
  }
  
  if (impacts.length === 0) {
    return 'Code changes require regression testing';
  }
  
  return impacts.join('. ');
}

/**
 * Generates impacted flows based on changed files
 */
export function generateImpactedFlows(changedFiles: string[]): string[] {
  const flows: string[] = [];
  
  if (changedFiles.some(f => f.toLowerCase().includes('signup') || f.toLowerCase().includes('sign-up'))) {
    flows.push('Sign-up');
  }
  if (changedFiles.some(f => f.toLowerCase().includes('reset') || f.toLowerCase().includes('password'))) {
    flows.push('Password reset');
  }
  if (changedFiles.some(f => f.toLowerCase().includes('password') || f.toLowerCase().includes('update'))) {
    flows.push('Update password');
  }
  if (changedFiles.some(f => f.toLowerCase().includes('login') || f.toLowerCase().includes('auth'))) {
    flows.push('Login/session safety');
  }
  if (changedFiles.some(f => f.toLowerCase().includes('form') || f.toLowerCase().includes('validation'))) {
    flows.push('UI/API validation consistency');
  }
  
  if (flows.length === 0) {
    return ['General application flows'];
  }
  
  return flows;
}

/**
 * Generates technical areas based on changed files
 */
export function generateTechnicalAreas(changedFiles: string[]): string[] {
  const areas: string[] = [];
  
  if (changedFiles.some(f => f.toLowerCase().includes('route') || f.toLowerCase().includes('api'))) {
    areas.push('API routes');
  }
  if (changedFiles.some(f => f.toLowerCase().includes('form') || f.toLowerCase().includes('component'))) {
    areas.push('UI validation components');
  }
  if (changedFiles.some(f => f.toLowerCase().includes('user') || f.toLowerCase().includes('auth'))) {
    areas.push('User/auth modules');
  }
  if (changedFiles.some(f => f.toLowerCase().includes('test'))) {
    areas.push('Test suites');
  }
  if (changedFiles.some(f => f.toLowerCase().includes('service') || f.toLowerCase().includes('controller'))) {
    areas.push('Business logic layer');
  }
  
  if (areas.length === 0) {
    return ['Core application modules'];
  }
  
  return areas;
}

/**
 * Generates "why it matters" description
 */
export function generateWhyItMatters(changedFiles: string[]): string[] {
  const reasons: string[] = [];
  
  if (changedFiles.some(f => f.toLowerCase().includes('password') || f.toLowerCase().includes('auth'))) {
    reasons.push('Weak passwords could be accepted');
    reasons.push('UI-only validation could be bypassed');
    reasons.push('Reset token handling may regress');
  }
  if (changedFiles.some(f => f.toLowerCase().includes('login'))) {
    reasons.push('Existing login behavior must remain stable');
  }
  if (changedFiles.some(f => f.toLowerCase().includes('form'))) {
    reasons.push('Form validation consistency across UI and API');
  }
  
  if (reasons.length === 0) {
    reasons.push('Business functionality could regress');
    reasons.push('User experience may be affected');
  }
  
  return reasons;
}
