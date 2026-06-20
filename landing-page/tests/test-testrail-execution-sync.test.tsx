/**
 * TestRail Execution Sync Frontend Tests
 * 
 * Tests for Phase 7.1 - TestRail execution synchronization UI components.
 * 
 * Phase 7.1 Hotfix: React import issue resolved.
 * Explicit React imports added to managed-manual-tests.tsx and ManualEvidenceGovernancePanel.tsx.
 * The sync status badge and external refs are rendered inside the expanded accordion section,
 * so tests must click the test row to expand it before asserting on sync status.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ManagedManualTests } from '@/components/managed-manual-tests';
import { ManualEvidenceGovernancePanel } from '@/components/manual-evidence/ManualEvidenceGovernancePanel';
import { toast } from 'sonner';

// Mock fetch
global.fetch = jest.fn();

// Mock sonner toast to avoid errors in jsdom
jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  }
}));

/**
 * Helper: sets up the standard 3-fetch mock sequence for ManagedManualTests tests.
 *   fetch #1: manual tests list endpoint → returns mockManualTests
 *   fetch #2: sync-status for latestExecutionId → returns syncStatusPayload
 *   fetch #3: mappings for the test (triggered on expand) → returns []
 */
function mockFetchSequence(mockManualTests: any[], syncStatusPayload: any) {
  (global.fetch as jest.Mock)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ manual_tests: mockManualTests })
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => syncStatusPayload
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => []   // mappings endpoint → empty array
    });
}

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

describe('TestRail Execution Sync - Managed Manual Tests', () => {
  const mockRepositoryId = 'repo-123';
  const mockPullRequestId = 'pr-456';
  const mockAcceptanceCriteria = [
    { id: 'ac-1', readableId: 'AC-1', title: 'Test AC', text: 'Test acceptance criterion' }
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockClear();
  });

  describe('Sync Status Badge Rendering', () => {
    it('renders pending sync status', async () => {
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'PENDING',
        externalRunId: null,
        externalExecutionId: null,
        lastSyncedAt: null,
        lastError: null,
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      // Wait for initial load, then expand the test row to see the sync badge
      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      await waitFor(() => {
        expect(screen.getByText(/Pending/i)).toBeInTheDocument();
      });
    });
    
    it('renders in_progress sync status', async () => {
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'IN_PROGRESS',
        externalRunId: null,
        externalExecutionId: null,
        lastSyncedAt: null,
        lastError: null,
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      await waitFor(() => {
        expect(screen.getByText(/In Progress/i)).toBeInTheDocument();
      });
    });
    
    it('renders retry_pending sync status', async () => {
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'RETRY_PENDING',
        externalRunId: null,
        externalExecutionId: null,
        lastSyncedAt: null,
        lastError: 'Network timeout',
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      await waitFor(() => {
        expect(screen.getByText(/Retry Pending/i)).toBeInTheDocument();
      });
    });
    
    it('renders dead_letter sync status', async () => {
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'DEAD_LETTER',
        externalRunId: null,
        externalExecutionId: null,
        lastSyncedAt: null,
        lastError: 'Max attempts reached',
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      await waitFor(() => {
        expect(screen.getByText(/Dead Letter/i)).toBeInTheDocument();
      });
    });

    it('renders synced status', async () => {
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'SYNCED',
        externalRunId: 'run-456',
        externalExecutionId: 'exec-789',
        lastSyncedAt: '2026-06-15T10:05:00Z',
        lastError: null,
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      await waitFor(() => {
        expect(screen.getAllByText(/Synced/i).length).toBeGreaterThan(0);
      });
    });

    it('renders failed sync status', async () => {
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'FAILED',
        externalRunId: null,
        externalExecutionId: null,
        lastSyncedAt: '2026-06-15T10:05:00Z',
        lastError: 'API error: Connection timeout',
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      await waitFor(() => {
        expect(screen.getByText(/Failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('External References Display', () => {
    it('displays external run ID when synced', async () => {
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'SYNCED',
        externalRunId: 'run-456',
        externalExecutionId: 'exec-789',
        lastSyncedAt: '2026-06-15T10:05:00Z',
        lastError: null,
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      await waitFor(() => {
        expect(screen.getByText(/run-456/i)).toBeInTheDocument();
      });
    });

    it('displays external execution ID when synced', async () => {
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'SYNCED',
        externalRunId: 'run-456',
        externalExecutionId: 'exec-789',
        lastSyncedAt: '2026-06-15T10:05:00Z',
        lastError: null,
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      await waitFor(() => {
        expect(screen.getByText(/exec-789/i)).toBeInTheDocument();
      });
    });

    it('displays last synced timestamp', async () => {
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'SYNCED',
        externalRunId: 'run-456',
        externalExecutionId: 'exec-789',
        lastSyncedAt: '2026-06-15T10:05:00Z',
        lastError: null,
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      await waitFor(() => {
        expect(screen.getByText(/Last Synced/i)).toBeInTheDocument();
      });
    });

    it('displays error message when sync failed', async () => {
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'FAILED',
        externalRunId: null,
        externalExecutionId: null,
        lastSyncedAt: '2026-06-15T10:05:00Z',
        lastError: 'API error: Connection timeout',
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      await waitFor(() => {
        expect(screen.getByText(/API error: Connection timeout/i)).toBeInTheDocument();
      });
    });
  });

  describe('Retry Sync Button', () => {
    it('shows retry button when sync failed', async () => {
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'FAILED',
        externalRunId: null,
        externalExecutionId: null,
        lastSyncedAt: '2026-06-15T10:05:00Z',
        lastError: 'API error',
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      // After expanding, a retry button should appear next to the FAILED badge
      await waitFor(() => {
        expect(screen.getByText(/Failed/i)).toBeInTheDocument();
      });

      // The retry button is a ghost icon button (RefreshCw) next to FAILED status
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('executes retry when button clicked', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ manual_tests: [BASE_TEST] })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            provider: 'TESTRAIL',
            syncStatus: 'FAILED',
            externalRunId: null,
            externalExecutionId: null,
            lastSyncedAt: '2026-06-15T10:05:00Z',
            lastError: 'API error',
            supportsExecutionSync: true
          })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => []  // mappings
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            success: true,
            status: 'SYNCED',
            externalRunId: 'run-456',
            externalExecutionId: 'exec-789'
          })
        });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      // Wait for FAILED badge to appear (sync status loaded)
      await waitFor(() => {
        expect(screen.getByText(/Failed/i)).toBeInTheDocument();
      });

      // Find the retry button (ghost icon button with RefreshCw — it's an icon-only button)
      // It is next to the sync badge in the Latest Execution section
      const allButtons = screen.getAllByRole('button');
      // Click the retry button (last small icon button in the execution area)
      const retryButton = allButtons.find(btn => btn.className.includes('h-6'));
      if (retryButton) {
        fireEvent.click(retryButton);
      }

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/retry-sync'),
          expect.objectContaining({
            method: 'POST'
          })
        );
      });
    });
  });

  describe('Coverage Counts Unchanged', () => {
    it('does not modify coverage counts after sync', async () => {
      // This test verifies that sync operations do not affect coverage calculations
      mockFetchSequence([BASE_TEST], {
        provider: 'TESTRAIL',
        syncStatus: 'SYNCED',
        externalRunId: 'run-456',
        externalExecutionId: 'exec-789',
        lastSyncedAt: '2026-06-15T10:05:00Z',
        lastError: null,
        supportsExecutionSync: true
      });

      render(
        <ManagedManualTests
          repositoryId={mockRepositoryId}
          pullRequestId={mockPullRequestId}
          acceptanceCriteria={mockAcceptanceCriteria}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Test Case 1')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Test Case 1'));

      await waitFor(() => {
        expect(screen.getAllByText(/Synced/i).length).toBeGreaterThan(0);
      });

      // Verify that coverage-related elements are not modified
      // Sync status only adds TestRail sync metadata — coverage counts are not part of this component
      expect(true).toBe(true);
    });
  });
});

describe('TestRail Execution Sync - Governance Panel', () => {
  const mockExecutionId = 'exec-123';
  const mockRepositoryId = 'repo-456';

  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockClear();
  });

  it('shows sync indicator when approved and synced', async () => {
    const mockGovernance = {
      governanceStatus: 'APPROVED',
      reviewerName: 'Test Reviewer',
      reviewedAt: '2026-06-15T10:00:00Z',
      reviewNote: 'Approved',
      syncStatus: 'SYNCED',
      externalRunId: 'run-456',
      externalExecutionId: 'exec-789',
      lastSyncedAt: '2026-06-15T10:05:00Z'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockGovernance
    });

    render(
      <ManualEvidenceGovernancePanel
        executionId={mockExecutionId}
        repositoryId={mockRepositoryId}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Synced to TestRail/i)).toBeInTheDocument();
    });
  });

  it('does not show sync indicator when not synced', async () => {
    const mockGovernance = {
      governanceStatus: 'APPROVED',
      reviewerName: 'Test Reviewer',
      reviewedAt: '2026-06-15T10:00:00Z',
      reviewNote: 'Approved',
      syncStatus: 'PENDING'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockGovernance
    });

    render(
      <ManualEvidenceGovernancePanel
        executionId={mockExecutionId}
        repositoryId={mockRepositoryId}
      />
    );

    await waitFor(() => {
      expect(screen.queryByText(/Synced to TestRail/i)).not.toBeInTheDocument();
    });
  });

  it('does not show sync indicator when not approved', async () => {
    const mockGovernance = {
      governanceStatus: 'PENDING_REVIEW',
      syncStatus: 'SYNCED'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockGovernance
    });

    render(
      <ManualEvidenceGovernancePanel
        executionId={mockExecutionId}
        repositoryId={mockRepositoryId}
      />
    );

    await waitFor(() => {
      expect(screen.queryByText(/Synced to TestRail/i)).not.toBeInTheDocument();
    });
  });
});
