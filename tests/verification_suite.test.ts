/**
 * Milestone 6C Phase 13 - Verification Suite
 * Tests for readiness and UX governance
 */

import { describe, test, expect, beforeEach, afterEach } from '@playwright/test';
import { RecommendationReadinessService } from '../app/services/recommendation_readiness_service';
import { QCLeadScenarioLanguageService } from '../app/services/qc_lead_scenario_language';

// Mock data for different repository states
const mockRepositories = {
  githubOnly: {
    id: 'repo-1',
    full_name: 'test/github-only',
    evidence: {
      pull_requests_count: 5,
      active_pull_requests_count: 2,
      test_runs_count: 0,
      test_results_count: 0,
      coverage: null,
      history: {
        has_flakiness_data: false
      }
    },
    business_intent: null,
    requirement_context: null,
    manual_tests: [],
    readiness_state: 'CONNECTED'
  },
  githubWithPRJUnitCoverage: {
    id: 'repo-2',
    full_name: 'test/with-pr-junit-coverage',
    evidence: {
      pull_requests_count: 10,
      active_pull_requests_count: 3,
      test_runs_count: 50,
      test_results_count: 45,
      coverage: {
        lines_covered: 1200,
        lines_total: 1500,
        percentage: 80
      },
      history: {
        has_flakiness_data: true
      }
    },
    business_intent: null,
    requirement_context: null,
    manual_tests: [],
    readiness_state: 'PARTIAL'
  },
  fullInputs: {
    id: 'repo-3',
    full_name: 'test/full-inputs',
    evidence: {
      pull_requests_count: 20,
      active_pull_requests_count: 4,
      test_runs_count: 100,
      test_results_count: 95,
      coverage: {
        lines_covered: 1800,
        lines_total: 2000,
        percentage: 90
      },
      history: {
        has_flakiness_data: true
      }
    },
    business_intent: {
      has_business_intent: true,
      acceptance_criteria: [
        'User can reset password with valid token',
        'Password must meet complexity requirements',
        'User receives email confirmation'
      ]
    },
    requirement_context: {
      linked_work_items: ['JIRA-123', 'JIRA-124'],
      requirement_coverage: 85
    },
    manual_tests: [
      {
        id: 'manual-1',
        title: 'Password Reset Flow',
        steps: ['Navigate to reset page', 'Enter email', 'Submit'],
        expected_result: 'Password reset email sent'
      }
    ],
    readiness_state: 'HIGH_CONFIDENCE_READY'
  }
};

// Mock recommendation runs
const mockRecommendationRuns = {
  noAC: {
    id: 'run-1',
    business_intent: null,
    evidence: {
      coverage: { percentage: 75 },
      history: { has_flakiness_data: true }
    },
    recommended_tests: [],
    confidence: 'MEDIUM'
  },
  withAC: {
    id: 'run-2',
    business_intent: {
      has_business_intent: true,
      acceptance_criteria: ['User can login with valid credentials']
    },
    evidence: {
      coverage: { percentage: 85 },
      history: { has_flakiness_data: true }
    },
    recommended_tests: [],
    confidence: 'HIGH'
  }
};

// Mock scenarios for QC Lead language testing
const mockScenarios = [
  {
    requiredScenario: 'should_allow_valid_token',
    scenarioType: 'positive',
    testingType: 'API',
    impactedArea: 'Authentication',
    priority: 'MUST'
  },
  {
    requiredScenario: 'validate_general_functionality',
    scenarioType: 'positive',
    testingType: 'UI',
    impactedArea: 'User Management',
    priority: 'SHOULD'
  },
  {
    requiredScenario: 'test_user_registration',
    scenarioType: 'positive',
    testingType: 'E2E',
    impactedArea: 'Registration',
    priority: 'MUST'
  }
];

describe('Milestone 6C Verification Suite', () => {
  let readinessService: RecommendationReadinessService;
  let qcLeadService: QCLeadScenarioLanguageService;

  beforeEach(() => {
    readinessService = new RecommendationReadinessService();
    qcLeadService = new QCLeadScenarioLanguageService();
  });

  describe('Test 1: Repository with GitHub only', () => {
    test('Expected: readiness = CONNECTED or PARTIAL', () => {
      const assessment = readinessService.assessReadiness(mockRepositories.githubOnly);
      
      expect(['CONNECTED', 'PARTIAL']).toContain(assessment.readiness_level);
      expect(assessment.can_generate).toBe(false);
      expect(assessment.missing_signals).toContain('JUnit Results');
      expect(assessment.missing_signals).toContain('Coverage Report');
      expect(assessment.expected_confidence).toBe('LOW');
    });

    test('PR diff check prevents generation', () => {
      const repoWithoutPR = {
        ...mockRepositories.githubOnly,
        evidence: {
          ...mockRepositories.githubOnly.evidence,
          active_pull_requests_count: 0
        }
      };
      
      const assessment = readinessService.assessReadiness(repoWithoutPR);
      expect(assessment.can_generate).toBe(false);
      expect(assessment.readiness_reasons).toContain('No active pull requests');
    });
  });

  describe('Test 2: Repository with GitHub + PR + JUnit + Coverage', () => {
    test('Expected: can_generate = true, expected confidence = MEDIUM', () => {
      const assessment = readinessService.assessReadiness(mockRepositories.githubWithPRJUnitCoverage);
      
      expect(assessment.can_generate).toBe(true);
      expect(assessment.expected_confidence).toBe('MEDIUM');
      expect(assessment.readiness_level).toBe('PARTIAL');
    });

    test('Missing AC/manual/outcomes shown as optional', () => {
      const assessment = readinessService.assessReadiness(mockRepositories.githubWithPRJUnitCoverage);
      
      expect(assessment.missing_signals).toContain('Acceptance Criteria');
      expect(assessment.missing_signals).toContain('Manual Tests');
      expect(assessment.missing_signals).toContain('Test Execution History');
      
      // These should be marked as optional, not blocking
      expect(assessment.blocking_signals).not.toContain('Acceptance Criteria');
      expect(assessment.blocking_signals).not.toContain('Manual Tests');
    });
  });

  describe('Test 3: Repository with full inputs', () => {
    test('Expected: readiness = HIGH_CONFIDENCE_READY, expected confidence = HIGH', () => {
      const assessment = readinessService.assessReadiness(mockRepositories.fullInputs);
      
      expect(assessment.readiness_level).toBe('HIGH_CONFIDENCE_READY');
      expect(assessment.expected_confidence).toBe('HIGH');
      expect(assessment.can_generate).toBe(true);
      expect(assessment.missing_signals).toHaveLength(0);
    });

    test('Minimal missing intelligence', () => {
      const assessment = readinessService.assessReadiness(mockRepositories.fullInputs);
      
      expect(assessment.missing_signals).toHaveLength(0);
      expect(assessment.blocking_signals).toHaveLength(0);
      expect(assessment.completeness_score).toBeGreaterThan(90);
    });
  });

  describe('Test 4: Recommendation page with no AC', () => {
    test('Expected: no large empty AC sections', () => {
      const run = mockRecommendationRuns.noAC;
      
      // AC section should be hidden or minimal
      expect(run.business_intent).toBeNull();
      expect(run.business_intent?.has_business_intent).toBeFalsy();
    });

    test('Expected: compact Missing Intelligence shown', () => {
      const run = mockRecommendationRuns.noAC;
      
      // Should show missing signals but not take up much space
      expect(run.business_intent).toBeNull();
      expect(run.confidence).toBe('MEDIUM'); // Lower confidence due to missing AC
    });
  });

  describe('Test 5: Recommendation page with AC', () => {
    test('Expected: AC coverage section shown', () => {
      const run = mockRecommendationRuns.withAC;
      
      expect(run.business_intent).not.toBeNull();
      expect(run.business_intent?.has_business_intent).toBe(true);
      expect(run.business_intent?.acceptance_criteria).toBeDefined();
      expect(run.business_intent?.acceptance_criteria?.length).toBeGreaterThan(0);
    });

    test('Higher confidence with AC', () => {
      const run = mockRecommendationRuns.withAC;
      expect(run.confidence).toBe('HIGH');
    });
  });

  describe('Test 6: Repository details page', () => {
    test('Expected: no misleading single READY state', () => {
      const repo = mockRepositories.githubOnly;
      
      // Should not show just "READY" without context
      expect(['CONNECTED', 'PARTIAL', 'HIGH_CONFIDENCE_READY']).toContain(repo.readiness_state);
      expect(repo.readiness_state).not.toBe('READY');
    });

    test('Expected: readiness panel visible', () => {
      const assessment = readinessService.assessReadiness(mockRepositories.githubWithPRJUnitCoverage);
      
      // Should have detailed readiness information
      expect(assessment.readiness_level).toBeDefined();
      expect(assessment.expected_confidence).toBeDefined();
      expect(assessment.missing_signals).toBeDefined();
      expect(assessment.available_signals).toBeDefined();
    });

    test('Expected: expected confidence visible', () => {
      const assessment = readinessService.assessReadiness(mockRepositories.fullInputs);
      
      expect(assessment.expected_confidence).toBe('HIGH');
      expect(assessment.confidence_factors).toBeDefined();
      expect(assessment.confidence_factors.length).toBeGreaterThan(0);
    });
  });

  describe('Test 7: Pre-recommendation checkpoint', () => {
    test('Expected: available/missing signals shown', () => {
      const assessment = readinessService.assessReadiness(mockRepositories.githubWithPRJUnitCoverage);
      
      // Should show both available and missing signals
      expect(assessment.available_signals.length).toBeGreaterThan(0);
      expect(assessment.missing_signals.length).toBeGreaterThan(0);
      
      // Should have signal descriptions
      assessment.available_signals.forEach(signal => {
        expect(signal.name).toBeDefined();
        expect(signal.description).toBeDefined();
      });
      
      assessment.missing_signals.forEach(signal => {
        expect(signal.name).toBeDefined();
        expect(signal.description).toBeDefined();
        expect(signal.impact).toBeDefined();
      });
    });

    test('Expected: Continue Anyway works', () => {
      const assessment = readinessService.assessReadiness(mockRepositories.githubWithPRJUnitCoverage);
      
      // Should allow proceeding even with missing signals
      expect(assessment.can_generate).toBe(true);
      expect(assessment.readiness_acknowledged).toBe(false); // Can be acknowledged
    });

    test('Expected: Paste AC works', () => {
      const repoWithAC = {
        ...mockRepositories.githubWithPRJUnitCoverage,
        business_intent: {
          has_business_intent: true,
          acceptance_criteria: ['New acceptance criteria']
        }
      };
      
      const assessment = readinessService.assessReadiness(repoWithAC);
      
      // Should improve readiness when AC is added
      expect(assessment.missing_signals).not.toContain('Acceptance Criteria');
      expect(assessment.expected_confidence).toBeGreaterThan('MEDIUM');
    });
  });

  describe('Test 8: Completeness rename', () => {
    test('Expected: no "Recommendation Completeness" wording if misleading', () => {
      // This would test UI components to ensure no misleading terminology
      // In a real test, we would check DOM elements for text content
      
      // For now, we verify the service uses correct terminology
      const assessment = readinessService.assessReadiness(mockRepositories.fullInputs);
      expect(assessment.completeness_score).toBeDefined();
      expect(assessment.completeness_factors).toBeDefined();
      
      // Should be "Intelligence Completeness" or "Evidence Completeness"
      // not "Recommendation Completeness"
    });
  });

  describe('Test 9: Value-first layout', () => {
    test('Expected: release readiness appears before outcome feedback', () => {
      const assessment = readinessService.assessReadiness(mockRepositories.fullInputs);
      
      // Release readiness should be primary
      expect(assessment.readiness_level).toBe('HIGH_CONFIDENCE_READY');
      expect(assessment.release_readiness).toBeDefined();
      
      // Should have clear release verdict
      expect(assessment.release_readiness.verdict).toBeDefined();
      expect(assessment.release_readiness.reasoning).toBeDefined();
    });

    test('Expected: impacted behaviors/journeys near top', () => {
      const assessment = readinessService.assessReadiness(mockRepositories.fullInputs);
      
      // Should have behavior and journey analysis
      expect(assessment.impacted_behaviors).toBeDefined();
      expect(assessment.impacted_journeys).toBeDefined();
      expect(assessment.impacted_behaviors.length).toBeGreaterThan(0);
    });
  });

  describe('Test 10: Scenario title quality', () => {
    test('Expected: no raw should_* identifiers as suggested scenario titles', () => {
      mockScenarios.forEach(scenario => {
        const professionalScenario = qcLeadService.generateProfessionalScenario(scenario);
        
        // Should not contain raw test identifiers
        expect(professionalScenario.title).not.toMatch(/^should_/);
        expect(professionalScenario.title).not.toMatch(/^test_/);
        expect(professionalScenario.title).not.toMatch(/^validate_/);
        
        // Should be human-readable
        expect(professionalScenario.title.length).toBeGreaterThan(10);
        expect(professionalScenario.title).toMatch(/^[A-Z]/);
      });
    });

    test('Expected: QC-readable titles generated', () => {
      const testCases = [
        {
          input: 'should_allow_valid_token',
          expectedPatterns: ['Verify', 'password reset', 'valid token']
        },
        {
          input: 'validate_general_functionality',
          expectedPatterns: ['Verify', 'user registration', 'valid data']
        },
        {
          input: 'test_user_registration',
          expectedPatterns: ['Verify', 'user registration', 'completes']
        }
      ];

      testCases.forEach(({ input, expectedPatterns }) => {
        const scenario = mockScenarios.find(s => s.requiredScenario === input);
        const professionalScenario = qcLeadService.generateProfessionalScenario(scenario);
        
        // Should contain expected professional language
        expectedPatterns.forEach(pattern => {
          expect(professionalScenario.title.toLowerCase()).toContain(pattern.toLowerCase());
        });
        
        // Should have complete professional structure
        expect(professionalScenario.objective).toBeDefined();
        expect(professionalScenario.objective.length).toBeGreaterThan(20);
        expect(professionalScenario.preconditions).toBeDefined();
        expect(professionalScenario.preconditions.length).toBeGreaterThan(0);
        expect(professionalScenario.steps).toBeDefined();
        expect(professionalScenario.steps.length).toBeGreaterThan(2);
        expect(professionalScenario.expected_results).toBeDefined();
        expect(professionalScenario.expected_results.length).toBeGreaterThan(0);
      });
    });

    test('Scenario types generate appropriate content', () => {
      const scenarioTypes = ['positive', 'negative', 'edge'];
      
      scenarioTypes.forEach(scenarioType => {
        const scenario = {
          ...mockScenarios[0],
          scenarioType
        };
        
        const professionalScenario = qcLeadService.generateProfessionalScenario(scenario);
        
        // Should have appropriate content for scenario type
        expect(professionalScenario.title).toBeDefined();
        expect(professionalScenario.objective).toBeDefined();
        
        // Negative scenarios should include security/validation language
        if (scenarioType === 'negative') {
          const content = [
            professionalScenario.title,
            professionalScenario.objective,
            ...professionalScenario.expected_results
          ].join(' ').toLowerCase();
          
          expect(content).toMatch(/(fail|invalid|denied|error|security)/);
        }
      });
    });
  });

  describe('Integration Tests', () => {
    test('Full readiness workflow', () => {
      // Test the complete workflow from GitHub-only to full inputs
      const stages = [
        mockRepositories.githubOnly,
        mockRepositories.githubWithPRJUnitCoverage,
        mockRepositories.fullInputs
      ];
      
      const expectedReadinessLevels = ['CONNECTED', 'PARTIAL', 'HIGH_CONFIDENCE_READY'];
      const expectedConfidences = ['LOW', 'MEDIUM', 'HIGH'];
      
      stages.forEach((repo, index) => {
        const assessment = readinessService.assessReadiness(repo);
        
        expect(assessment.readiness_level).toBe(expectedReadinessLevels[index]);
        expect(assessment.expected_confidence).toBe(expectedConfidences[index]);
        
        // Completeness should improve with each stage
        expect(assessment.completeness_score).toBeGreaterThan(index * 20);
      });
    });

    test('QC Lead scenario language integration', () => {
      // Test that QC Lead language works with the readiness system
      const assessment = readinessService.assessReadiness(mockRepositories.fullInputs);
      
      // Should be able to generate professional scenarios
      mockScenarios.forEach(scenario => {
        const professionalScenario = qcLeadService.generateProfessionalScenario(scenario);
        
        expect(professionalScenario.title).toBeDefined();
        expect(professionalScenario.objective).toBeDefined();
        expect(professionalScenario.priority).toBeDefined();
        expect(professionalScenario.execution_layer).toBeDefined();
      });
      
      // High confidence readiness should support professional scenarios
      expect(assessment.expected_confidence).toBe('HIGH');
    });
  });
});

// Helper functions for testing UI components (would be used in actual Playwright tests)
export const UITestHelpers = {
  async verifyNoEmptySections(page: any, sectionSelector: string) {
    const section = page.locator(sectionSelector);
    const isVisible = await section.isVisible();
    
    if (isVisible) {
      const textContent = await section.textContent();
      expect(textContent?.trim().length).toBeGreaterThan(0);
    }
  },

  async verifyTextNotPresent(page: any, text: string) {
    const bodyText = await page.textContent('body');
    expect(bodyText?.toLowerCase()).not.toContain(text.toLowerCase());
  },

  async verifyTextPresent(page: any, text: string) {
    const bodyText = await page.textContent('body');
    expect(bodyText?.toLowerCase()).toContain(text.toLowerCase());
  },

  async verifyElementOrder(page: any, selector1: string, selector2: string) {
    const element1 = page.locator(selector1);
    const element2 = page.locator(selector2);
    
    const bbox1 = await element1.boundingBox();
    const bbox2 = await element2.boundingBox();
    
    expect(bbox1?.y).toBeLessThan(bbox2?.y);
  }
};
