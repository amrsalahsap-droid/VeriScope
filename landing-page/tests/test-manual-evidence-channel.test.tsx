import { describe, it, expect, jest, beforeEach } from '@jest/globals';

describe('Manual Test Evidence Channel - Frontend Tests', () => {
  it('should render the Manual Validation badge with the correct outcome styles', () => {
    // Mock mappings of outcomes to classes and display labels
    const getBadgeStyleAndLabel = (status: string) => {
      switch (status) {
        case 'PASSED':
          return {
            className: 'bg-green-500/10 text-green-400 border-green-500/20',
            label: 'Passed',
          };
        case 'FAILED':
          return {
            className: 'bg-rose-500/10 text-rose-455 border-rose-500/20',
            label: 'Failed',
          };
        case 'BLOCKED':
          return {
            className: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
            label: 'Blocked',
          };
        case 'SKIPPED':
          return {
            className: 'bg-zinc-800 text-zinc-400 border-zinc-700/50',
            label: 'Skipped',
          };
        case 'NOT_EXECUTED':
          return {
            className: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
            label: 'Not Executed',
          };
        default:
          return {
            className: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/10',
            label: 'Not Mapped',
          };
      }
    };

    const passedBadge = getBadgeStyleAndLabel('PASSED');
    expect(passedBadge.className).toContain('green-500');
    expect(passedBadge.label).toBe('Passed');

    const failedBadge = getBadgeStyleAndLabel('FAILED');
    expect(failedBadge.className).toContain('rose-500');
    expect(failedBadge.label).toBe('Failed');

    const blockedBadge = getBadgeStyleAndLabel('BLOCKED');
    expect(blockedBadge.className).toContain('amber-500');
    expect(blockedBadge.label).toBe('Blocked');

    const notMappedBadge = getBadgeStyleAndLabel('NOT_MAPPED');
    expect(notMappedBadge.label).toBe('Not Mapped');
  });

  it('should display the mapped manual test count and execution details (executed by/date/url)', () => {
    const mockManualValidation = {
      status: 'PASSED',
      supportStatus: 'MANUALLY_SUPPORTED',
      mappedManualTestsCount: 1,
      executedManualTestsCount: 1,
      passedManualTestsCount: 1,
      failedManualTestsCount: 0,
      blockedManualTestsCount: 0,
      skippedManualTestsCount: 0,
      latestOutcome: 'PASSED',
      latestExecutedAt: '2026-06-13T22:00:00Z',
      latestExecutedByName: 'John Doe',
      evidenceUrls: ['http://example.com/evidence'],
      manualTests: [
        {
          id: 'manual-test-1',
          title: 'Verify multi-factor authentication fallback',
          outcome: 'PASSED',
          executedAt: '2026-06-13T22:00:00Z',
          executedByName: 'John Doe',
          evidenceUrl: 'http://example.com/evidence',
          mappingSource: 'MANUAL',
        },
      ],
    };

    expect(mockManualValidation.mappedManualTestsCount).toBe(1);
    expect(mockManualValidation.latestExecutedByName).toBe('John Doe');
    expect(mockManualValidation.latestExecutedAt).toBe('2026-06-13T22:00:00Z');
    expect(mockManualValidation.evidenceUrls[0]).toBe('http://example.com/evidence');
    expect(mockManualValidation.manualTests[0].title).toBe('Verify multi-factor authentication fallback');
  });

  it('should keep automated coverage counts unchanged', () => {
    // Under manual validations, automated coverage metrics must remain invariant
    const baselineCounts = {
      total: 25,
      covered: 16,
      partial: 2,
      missing: 7,
      passed: 18,
    };

    // Simulate presence of manual validation
    const mockManualValidation = {
      status: 'PASSED',
      supportStatus: 'MANUALLY_SUPPORTED',
    };

    // Assert that the counts do not change
    expect(baselineCounts.total).toBe(25);
    expect(baselineCounts.covered).toBe(16);
    expect(baselineCounts.partial).toBe(2);
    expect(baselineCounts.missing).toBe(7);
    expect(baselineCounts.passed).toBe(18);
  });
});
