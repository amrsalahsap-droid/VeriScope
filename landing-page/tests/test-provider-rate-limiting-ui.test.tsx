/**
 * Tests for Provider Rate Limiting UI
 * 
 * Tests UI components for rate limiting and cooldown behavior:
 * - IntegrationHealthPanel cooldown state
 * - IntegrationSyncActivityFeed retry metadata
 * - Retry button behavior during cooldown
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import IntegrationHealthPanel from '../components/IntegrationHealthPanel';
import IntegrationSyncActivityFeed from '../components/IntegrationSyncActivityFeed';

describe('Provider Rate Limiting UI', () => {
  describe('IntegrationHealthPanel', () => {
    it('renders cooldown active state', () => {
      const healthStatuses = [
        {
          provider: 'TESTRAIL',
          health: 'COOLDOWN_ACTIVE' as const,
          isConnected: true,
          lastSyncStatus: 'FAILED',
          lastSyncError: null,
          missingConfiguration: null,
          cooldownRemaining: 900,
          cooldownReason: 'RATE_LIMITED'
        }
      ];

      render(<IntegrationHealthPanel healthStatuses={healthStatuses} />);

      expect(screen.getByText(/Cooldown:/)).toBeInTheDocument();
      expect(screen.getByText(/15m 0s/)).toBeInTheDocument();
      expect(screen.getByText(/(RATE_LIMITED)/)).toBeInTheDocument();
    });

    it('renders retry disabled during cooldown', () => {
      const healthStatuses = [
        {
          provider: 'TESTRAIL',
          health: 'COOLDOWN_ACTIVE' as const,
          isConnected: true,
          lastSyncStatus: 'FAILED',
          lastSyncError: null,
          missingConfiguration: null,
          cooldownRemaining: 300,
          cooldownReason: 'RATE_LIMITED'
        }
      ];

      const onRetryFailedSyncs = jest.fn();
      render(
        <IntegrationHealthPanel 
          healthStatuses={healthStatuses} 
          onRetryFailedSyncs={onRetryFailedSyncs}
        />
      );

      const retryButton = screen.getByText('Retry Disabled');
      expect(retryButton).toBeInTheDocument();
      expect(retryButton).toBeDisabled();
    });

    it('formats cooldown time correctly', () => {
      const healthStatuses = [
        {
          provider: 'TESTRAIL',
          health: 'COOLDOWN_ACTIVE' as const,
          isConnected: true,
          lastSyncStatus: 'FAILED',
          lastSyncError: null,
          missingConfiguration: null,
          cooldownRemaining: 45,
          cooldownReason: 'RATE_LIMITED'
        }
      ];

      render(<IntegrationHealthPanel healthStatuses={healthStatuses} />);

      expect(screen.getByText(/45s/)).toBeInTheDocument();
    });

    it('shows cooldown reason when provided', () => {
      const healthStatuses = [
        {
          provider: 'TESTRAIL',
          health: 'COOLDOWN_ACTIVE' as const,
          isConnected: true,
          lastSyncStatus: 'FAILED',
          lastSyncError: null,
          missingConfiguration: null,
          cooldownRemaining: 600,
          cooldownReason: 'REPEATED_FAILURES'
        }
      ];

      render(<IntegrationHealthPanel healthStatuses={healthStatuses} />);

      expect(screen.getByText(/(REPEATED_FAILURES)/)).toBeInTheDocument();
    });

    it('renders healthy state when no cooldown', () => {
      const healthStatuses = [
        {
          provider: 'TESTRAIL',
          health: 'HEALTHY' as const,
          isConnected: true,
          lastSyncStatus: 'SYNCED',
          lastSyncError: null,
          missingConfiguration: null
        }
      ];

      render(<IntegrationHealthPanel healthStatuses={healthStatuses} />);

      expect(screen.getByText('Healthy')).toBeInTheDocument();
      expect(screen.queryByText(/Cooldown:/)).not.toBeInTheDocument();
    });
  });

  describe('IntegrationSyncActivityFeed', () => {
    it('displays attempt count', () => {
      const activities = [
        {
          id: '1',
          provider: 'TESTRAIL',
          executionId: 'exec-123',
          status: 'RETRY_PENDING',
          error: null,
          externalRunId: null,
          externalExecutionId: null,
          createdAt: '2026-06-15T10:00:00Z',
          lastSyncedAt: null,
          attemptCount: 2,
          maxAttempts: 5
        }
      ];

      render(<IntegrationSyncActivityFeed activities={activities} />);

      expect(screen.getByText('Attempt 2/5')).toBeInTheDocument();
    });

    it('displays next attempt time', () => {
      const activities = [
        {
          id: '1',
          provider: 'TESTRAIL',
          executionId: 'exec-123',
          status: 'RETRY_PENDING',
          error: null,
          externalRunId: null,
          externalExecutionId: null,
          createdAt: '2026-06-15T10:00:00Z',
          lastSyncedAt: null,
          attemptCount: 1,
          maxAttempts: 5,
          nextAttemptAt: '2026-06-15T10:05:00Z'
        }
      ];

      render(<IntegrationSyncActivityFeed activities={activities} />);

      expect(screen.getByText(/Retry:/)).toBeInTheDocument();
    });

    it('displays cooldown information', () => {
      const activities = [
        {
          id: '1',
          provider: 'TESTRAIL',
          executionId: 'exec-123',
          status: 'RETRY_PENDING',
          error: null,
          externalRunId: null,
          externalExecutionId: null,
          createdAt: '2026-06-15T10:00:00Z',
          lastSyncedAt: null,
          attemptCount: 1,
          maxAttempts: 5,
          cooldownUntil: '2026-06-15T10:15:00Z',
          cooldownReason: 'RATE_LIMITED'
        }
      ];

      render(<IntegrationSyncActivityFeed activities={activities} />);

      expect(screen.getByText(/Cooldown until/)).toBeInTheDocument();
      expect(screen.getByText(/(RATE_LIMITED)/)).toBeInTheDocument();
    });

    it('hides error when cooldown is active', () => {
      const activities = [
        {
          id: '1',
          provider: 'TESTRAIL',
          executionId: 'exec-123',
          status: 'RETRY_PENDING',
          error: 'Too many requests',
          externalRunId: null,
          externalExecutionId: null,
          createdAt: '2026-06-15T10:00:00Z',
          lastSyncedAt: null,
          attemptCount: 1,
          maxAttempts: 5,
          cooldownUntil: '2026-06-15T10:15:00Z',
          cooldownReason: 'RATE_LIMITED'
        }
      ];

      render(<IntegrationSyncActivityFeed activities={activities} />);

      // Error should be hidden when cooldown is active
      expect(screen.queryByText('Too many requests')).not.toBeInTheDocument();
      // Cooldown info should be shown instead
      expect(screen.getByText(/Cooldown until/)).toBeInTheDocument();
    });

    it('renders new queue statuses', () => {
      const activities = [
        {
          id: '1',
          provider: 'TESTRAIL',
          executionId: 'exec-123',
          status: 'IN_PROGRESS',
          error: null,
          externalRunId: null,
          externalExecutionId: null,
          createdAt: '2026-06-15T10:00:00Z',
          lastSyncedAt: null
        },
        {
          id: '2',
          provider: 'TESTRAIL',
          executionId: 'exec-456',
          status: 'DEAD_LETTER',
          error: 'Max attempts reached',
          externalRunId: null,
          externalExecutionId: null,
          createdAt: '2026-06-15T10:00:00Z',
          lastSyncedAt: null
        }
      ];

      render(<IntegrationSyncActivityFeed activities={activities} />);

      expect(screen.getByText('IN_PROGRESS')).toBeInTheDocument();
      expect(screen.getByText('DEAD_LETTER')).toBeInTheDocument();
    });

    it('displays error when no cooldown', () => {
      const activities = [
        {
          id: '1',
          provider: 'TESTRAIL',
          executionId: 'exec-123',
          status: 'FAILED',
          error: 'Connection timeout',
          externalRunId: null,
          externalExecutionId: null,
          createdAt: '2026-06-15T10:00:00Z',
          lastSyncedAt: null
        }
      ];

      render(<IntegrationSyncActivityFeed activities={activities} />);

      expect(screen.getByText('Connection timeout')).toBeInTheDocument();
    });
  });

  describe('Retry Button Behavior', () => {
    it('enables retry when no cooldown', () => {
      const healthStatuses = [
        {
          provider: 'TESTRAIL',
          health: 'SYNC_FAILURES_PRESENT' as const,
          isConnected: true,
          lastSyncStatus: 'FAILED',
          lastSyncError: 'Connection timeout',
          missingConfiguration: null
        }
      ];

      const onRetryFailedSyncs = jest.fn();
      render(
        <IntegrationHealthPanel 
          healthStatuses={healthStatuses} 
          onRetryFailedSyncs={onRetryFailedSyncs}
        />
      );

      const retryButton = screen.getByText('Retry All');
      expect(retryButton).toBeInTheDocument();
      expect(retryButton).not.toBeDisabled();
    });

    it('disables retry during cooldown', () => {
      const healthStatuses = [
        {
          provider: 'TESTRAIL',
          health: 'COOLDOWN_ACTIVE' as const,
          isConnected: true,
          lastSyncStatus: 'FAILED',
          lastSyncError: null,
          missingConfiguration: null,
          cooldownRemaining: 300,
          cooldownReason: 'RATE_LIMITED'
        }
      ];

      const onRetryFailedSyncs = jest.fn();
      render(
        <IntegrationHealthPanel 
          healthStatuses={healthStatuses} 
          onRetryFailedSyncs={onRetryFailedSyncs}
        />
      );

      const retryButton = screen.getByText('Retry Disabled');
      expect(retryButton).toBeDisabled();
    });
  });
});
