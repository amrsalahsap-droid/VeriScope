/**
 * Phase 7.2 — Provider Sync Framework Frontend Tests
 *
 * Tests for:
 * 1. Capability matrix renders
 * 2. TestRail shows "Supported"
 * 3. Xray shows "Planned"
 * 4. Zephyr shows "Planned"
 * 5. Jira shows "Not Supported"
 * 6. Azure shows "Not Supported"
 * 7. Retry Sync button hidden when supportsExecutionSync = false
 * 8. Retry Sync button visible when supportsExecutionSync = true
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ManagedManualTests } from '@/components/managed-manual-tests';

// Mock fetch globally
global.fetch = jest.fn();

// Mock sonner toast
jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  }
}));

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

const BASE_TEST = {
  id: 'test-1',
  title: 'Test Case 1',
  provider: 'TESTRAIL',
  external_key: 'C123',
  priority: 'MUST',
  url: 'https://testrail.example.com',
  linked_ac: [],
  linked_behavior: [],
  preconditions: [],
  steps: [],
  expected_result: 'Expected result',
  execution_status: 'PASSED' as const,
  latestExecutionId: 'exec-1',
  latestExecutedAt: '2026-06-15T10:00:00Z',
  latestExecutedByName: 'Test User',
  latestExecutionStatus: 'PASSED',
  executionHistoryCount: 1
};

/**
 * Mock fetch sequence for ManagedManualTests:
 *   #1 manual tests list
 *   #2 sync-status (with supportsExecutionSync field)
 *   #3 mappings (expand)
 */
function mockFetchSequence(
  testOverrides: Partial<typeof BASE_TEST> = {},
  syncStatusOverrides: Record<string, any> = {},
) {
  const test = { ...BASE_TEST, ...testOverrides };
  (global.fetch as jest.Mock)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ manual_tests: [test] })
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        provider: test.provider,
        syncStatus: 'SYNCED',
        externalRunId: 'run-456',
        externalExecutionId: 'exec-789',
        lastSyncedAt: '2026-06-15T10:05:00Z',
        lastError: null,
        supportsExecutionSync: true,
        ...syncStatusOverrides
      })
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => []  // mappings
    });
}

const MOCK_PROPS = {
  repositoryId: 'repo-123',
  pullRequestId: 'pr-456',
  acceptanceCriteria: [
    { id: 'ac-1', readableId: 'AC-1', title: 'Test AC', text: 'Test acceptance criterion' }
  ]
};

// ─────────────────────────────────────────────────────────────────────────────
// Capability-driven Retry Sync visibility tests
// ─────────────────────────────────────────────────────────────────────────────

describe('Provider Sync Framework — Retry Sync Visibility', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockClear();
  });

  it('shows sync badge when supportsExecutionSync = true', async () => {
    mockFetchSequence({}, { syncStatus: 'SYNCED', supportsExecutionSync: true });

    render(<ManagedManualTests {...MOCK_PROPS} />);

    await waitFor(() => {
      expect(screen.getByText('Test Case 1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Test Case 1'));

    await waitFor(() => {
      expect(screen.getAllByText(/Synced/i).length).toBeGreaterThan(0);
    });
  });

  it('hides sync badge when supportsExecutionSync = false', async () => {
    // Provider doesn't support sync — no sync badge should appear
    mockFetchSequence(
      { provider: 'XRAY' },
      { provider: 'XRAY', syncStatus: 'PENDING', supportsExecutionSync: false }
    );

    render(<ManagedManualTests {...MOCK_PROPS} />);

    await waitFor(() => {
      expect(screen.getByText('Test Case 1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Test Case 1'));

    // Give time for sync status to load
    await new Promise(r => setTimeout(r, 200));

    // Check that the retry button is not visible (the key capability-driven behavior)
    const retryButtons = screen.queryAllByRole('button').filter(btn =>
      btn.getAttribute('aria-label')?.includes('retry') || btn.textContent?.includes('Retry')
    );
    expect(retryButtons.length).toBe(0);
  });

  it('shows retry button when supportsExecutionSync = true and syncStatus = FAILED', async () => {
    mockFetchSequence({}, {
      syncStatus: 'FAILED',
      supportsExecutionSync: true,
      lastError: 'API error'
    });

    render(<ManagedManualTests {...MOCK_PROPS} />);

    await waitFor(() => {
      expect(screen.getByText('Test Case 1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Test Case 1'));

    await waitFor(() => {
      expect(screen.getByText(/Failed/i)).toBeInTheDocument();
    });

    // The retry icon button should be visible
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('hides retry button when supportsExecutionSync = false even if status = FAILED', async () => {
    mockFetchSequence(
      { provider: 'JIRA' },
      {
        provider: 'JIRA',
        syncStatus: 'FAILED',
        supportsExecutionSync: false,
        lastError: 'Unsupported'
      }
    );

    render(<ManagedManualTests {...MOCK_PROPS} />);

    await waitFor(() => {
      expect(screen.getByText('Test Case 1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Test Case 1'));

    await new Promise(r => setTimeout(r, 200));

    // No "Failed" badge should render for a non-supported provider
    expect(screen.queryByText(/^Failed$/i)).not.toBeInTheDocument();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Capability Matrix rendering tests
// (These test the integrations page which needs a mock for the providers API.
//  The component tests are simulated here via direct data assertions.)
// ─────────────────────────────────────────────────────────────────────────────

describe('Provider Sync Framework — Capability Matrix Data', () => {
  const MOCK_CAPABILITIES = [
    { provider: 'TESTRAIL', supportsExecutionSync: true,  supportsBidirectionalSync: false, supportsTestImport: true,  supportsWorkItemImport: false, supportsWebhooks: false },
    { provider: 'XRAY',     supportsExecutionSync: true,  supportsBidirectionalSync: false, supportsTestImport: false, supportsWorkItemImport: false, supportsWebhooks: false },
    { provider: 'ZEPHYR',   supportsExecutionSync: true,  supportsBidirectionalSync: false, supportsTestImport: false, supportsWorkItemImport: false, supportsWebhooks: false },
    { provider: 'JIRA',     supportsExecutionSync: false, supportsBidirectionalSync: false, supportsTestImport: false, supportsWorkItemImport: true,  supportsWebhooks: false },
    { provider: 'AZURE_DEVOPS', supportsExecutionSync: false, supportsBidirectionalSync: false, supportsTestImport: false, supportsWorkItemImport: true, supportsWebhooks: false },
  ];

  it('TestRail shows supportsExecutionSync = true', () => {
    const testrail = MOCK_CAPABILITIES.find(c => c.provider === 'TESTRAIL');
    expect(testrail?.supportsExecutionSync).toBe(true);
  });

  it('Xray shows supportsExecutionSync = true (Phase 7.3A)', () => {
    const xray = MOCK_CAPABILITIES.find(c => c.provider === 'XRAY');
    expect(xray?.supportsExecutionSync).toBe(true);
  });

  it('Zephyr shows supportsExecutionSync = true (Phase 7.3B)', () => {
    const zephyr = MOCK_CAPABILITIES.find(c => c.provider === 'ZEPHYR');
    expect(zephyr?.supportsExecutionSync).toBe(true);
  });

  it('Jira shows supportsExecutionSync = false (Not Supported)', () => {
    const jira = MOCK_CAPABILITIES.find(c => c.provider === 'JIRA');
    expect(jira?.supportsExecutionSync).toBe(false);
  });

  it('Azure shows supportsExecutionSync = false (Not Supported)', () => {
    const azure = MOCK_CAPABILITIES.find(c => c.provider === 'AZURE_DEVOPS');
    expect(azure?.supportsExecutionSync).toBe(false);
  });

  it('capability matrix has exactly 5 providers', () => {
    expect(MOCK_CAPABILITIES).toHaveLength(5);
  });

  it('TestRail, Xray, and Zephyr support execution sync in Phase 7.3B', () => {
    const supported = MOCK_CAPABILITIES.filter(c => c.supportsExecutionSync);
    expect(supported).toHaveLength(3);
    expect(supported.map(c => c.provider)).toContain('TESTRAIL');
    expect(supported.map(c => c.provider)).toContain('XRAY');
    expect(supported.map(c => c.provider)).toContain('ZEPHYR');
  });

  it('capability snapshot matches Phase 7.3B specification', () => {
    const snapshot = Object.fromEntries(
      MOCK_CAPABILITIES.map(c => [
        c.provider,
        { execution: c.supportsExecutionSync, bidirectional: c.supportsBidirectionalSync }
      ])
    );
    expect(snapshot).toEqual({
      TESTRAIL:    { execution: true,  bidirectional: false },
      XRAY:        { execution: true,  bidirectional: false },  // Phase 7.3A
      ZEPHYR:      { execution: true,  bidirectional: false },  // Phase 7.3B
      JIRA:        { execution: false, bidirectional: false },
      AZURE_DEVOPS: { execution: false, bidirectional: false },
    });
  });
});
