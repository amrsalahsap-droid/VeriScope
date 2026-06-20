/**
 * Integration UI Enhancements Tests (Phase 7.4)
 * 
 * Tests for the new integration UI components:
 * - ProviderCapabilityCard
 * - IntegrationHealthPanel
 * - IntegrationSyncActivityFeed
 * - ExecutionSyncDiagnosticsDrawer
 * - Integrations page enhancements
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ProviderCapabilityCard from '@/components/ProviderCapabilityCard';
import IntegrationHealthPanel from '@/components/IntegrationHealthPanel';
import IntegrationSyncActivityFeed from '@/components/IntegrationSyncActivityFeed';
import ExecutionSyncDiagnosticsDrawer from '@/components/ExecutionSyncDiagnosticsDrawer';

// Mock global fetch
global.fetch = jest.fn();

describe('ProviderCapabilityCard', () => {
  it('renders provider capability card with all capabilities', () => {
    render(
      <ProviderCapabilityCard
        provider="TESTRAIL"
        providerName="TestRail"
        isConnected={true}
        supportsExecutionSync={true}
        supportsTestImport={true}
        supportsWorkItemImport={false}
        supportsWebhooks={false}
        supportsBidirectionalSync={false}
        icon="🟢"
      />
    );

    expect(screen.getByText('TestRail')).toBeInTheDocument();
    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('Execution Sync')).toBeInTheDocument();
    expect(screen.getAllByText('Yes')).toHaveLength(2); // Execution Sync and Test Import
  });

  it('shows disconnected status when not connected', () => {
    render(
      <ProviderCapabilityCard
        provider="TESTRAIL"
        providerName="TestRail"
        isConnected={false}
        supportsExecutionSync={true}
        supportsTestImport={true}
        supportsWorkItemImport={false}
        supportsWebhooks={false}
        supportsBidirectionalSync={false}
      />
    );

    expect(screen.getByText('Disconnected')).toBeInTheDocument();
  });

  it('shows No for unsupported capabilities', () => {
    render(
      <ProviderCapabilityCard
        provider="TESTRAIL"
        providerName="TestRail"
        isConnected={true}
        supportsExecutionSync={true}
        supportsTestImport={true}
        supportsWorkItemImport={false}
        supportsWebhooks={false}
        supportsBidirectionalSync={false}
      />
    );

    const workItemImportText = screen.getByText('Work Item Import').parentElement?.textContent;
    expect(workItemImportText).toContain('No');
  });
});

describe('IntegrationHealthPanel', () => {
  const mockHealthStatuses = [
    {
      provider: 'TESTRAIL',
      health: 'HEALTHY' as const,
      isConnected: true,
      lastSyncStatus: 'SYNCED',
      lastSyncError: null,
      missingConfiguration: null
    },
    {
      provider: 'XRAY',
      health: 'CONFIGURATION_REQUIRED' as const,
      isConnected: true,
      lastSyncStatus: 'FAILED',
      lastSyncError: null,
      missingConfiguration: 'testExecutionKey'
    },
    {
      provider: 'ZEPHYR',
      health: 'SYNC_FAILURES_PRESENT' as const,
      isConnected: true,
      lastSyncStatus: 'FAILED',
      lastSyncError: 'ZEPHYR_TEST_CYCLE_KEY_REQUIRED',
      missingConfiguration: null
    }
  ];

  it('renders health panel with all statuses', () => {
    render(<IntegrationHealthPanel healthStatuses={mockHealthStatuses} />);

    expect(screen.getByText('Integration Health')).toBeInTheDocument();
    expect(screen.getByText('TESTRAIL')).toBeInTheDocument();
    expect(screen.getByText('XRAY')).toBeInTheDocument();
    expect(screen.getByText('ZEPHYR')).toBeInTheDocument();
  });

  it('shows missing configuration warning', () => {
    render(<IntegrationHealthPanel healthStatuses={mockHealthStatuses} />);

    expect(screen.getByText('Missing: testExecutionKey')).toBeInTheDocument();
  });

  it('shows sync error when present', () => {
    render(<IntegrationHealthPanel healthStatuses={mockHealthStatuses} />);

    expect(screen.getByText('ZEPHYR_TEST_CYCLE_KEY_REQUIRED')).toBeInTheDocument();
  });

  it('shows retry button for sync failures', () => {
    const mockRetry = jest.fn();
    render(
      <IntegrationHealthPanel 
        healthStatuses={mockHealthStatuses}
        onRetryFailedSyncs={mockRetry}
      />
    );

    const retryButton = screen.getByText('Retry All');
    expect(retryButton).toBeInTheDocument();

    fireEvent.click(retryButton);
    expect(mockRetry).toHaveBeenCalledWith('ZEPHYR');
  });

  it('disables retry button while retrying', () => {
    const mockRetry = jest.fn();
    render(
      <IntegrationHealthPanel 
        healthStatuses={mockHealthStatuses}
        onRetryFailedSyncs={mockRetry}
        retryingProvider="ZEPHYR"
      />
    );

    const retryButton = screen.getByText('Retrying...');
    expect(retryButton).toBeDisabled();
  });
});

describe('IntegrationSyncActivityFeed', () => {
  const mockActivities = [
    {
      id: '1',
      provider: 'TESTRAIL',
      executionId: 'exec-1',
      status: 'SYNCED',
      error: null,
      externalRunId: 'RUN-123',
      externalExecutionId: 'EXEC-456',
      createdAt: '2024-01-01T00:00:00Z',
      lastSyncedAt: '2024-01-01T00:00:00Z'
    },
    {
      id: '2',
      provider: 'XRAY',
      executionId: 'exec-2',
      status: 'FAILED',
      error: 'XRAY_TEST_EXECUTION_KEY_REQUIRED',
      externalRunId: null,
      externalExecutionId: null,
      createdAt: '2024-01-01T00:00:00Z',
      lastSyncedAt: '2024-01-01T00:00:00Z'
    }
  ];

  it('renders sync activity feed', () => {
    render(<IntegrationSyncActivityFeed activities={mockActivities} />);

    expect(screen.getByText('Sync Activity')).toBeInTheDocument();
    expect(screen.getByText('TESTRAIL')).toBeInTheDocument();
    expect(screen.getByText('XRAY')).toBeInTheDocument();
  });

  it('shows empty state when no activities', () => {
    render(<IntegrationSyncActivityFeed activities={[]} />);

    expect(screen.getByText('No sync activity found')).toBeInTheDocument();
  });

  it('filters by provider when filter selected', () => {
    const mockFilterChange = jest.fn();
    render(
      <IntegrationSyncActivityFeed 
        activities={mockActivities}
        providerFilter="TESTRAIL"
        onProviderFilterChange={mockFilterChange}
      />
    );

    const select = screen.getByRole('combobox');
    expect(select).toHaveValue('TESTRAIL');
  });

  it('shows error message for failed syncs', () => {
    render(<IntegrationSyncActivityFeed activities={mockActivities} />);

    expect(screen.getByText('XRAY_TEST_EXECUTION_KEY_REQUIRED')).toBeInTheDocument();
  });
  
  it('renders PENDING status', () => {
    const pendingActivity = {
      id: '3',
      provider: 'TESTRAIL',
      executionId: 'exec-3',
      status: 'PENDING',
      error: null,
      externalRunId: null,
      externalExecutionId: null,
      createdAt: '2024-01-01T00:00:00Z',
      lastSyncedAt: null,
      attemptCount: 0,
      maxAttempts: 3
    };
    
    render(<IntegrationSyncActivityFeed activities={[pendingActivity]} />);
    
    expect(screen.getByText('PENDING')).toBeInTheDocument();
  });
  
  it('renders IN_PROGRESS status', () => {
    const inProgressActivity = {
      id: '4',
      provider: 'XRAY',
      executionId: 'exec-4',
      status: 'IN_PROGRESS',
      error: null,
      externalRunId: null,
      externalExecutionId: null,
      createdAt: '2024-01-01T00:00:00Z',
      lastSyncedAt: null,
      attemptCount: 1,
      maxAttempts: 3
    };
    
    render(<IntegrationSyncActivityFeed activities={[inProgressActivity]} />);
    
    expect(screen.getByText('IN_PROGRESS')).toBeInTheDocument();
  });
  
  it('renders RETRY_PENDING status', () => {
    const retryPendingActivity = {
      id: '5',
      provider: 'ZEPHYR',
      executionId: 'exec-5',
      status: 'RETRY_PENDING',
      error: 'Network timeout',
      externalRunId: null,
      externalExecutionId: null,
      createdAt: '2024-01-01T00:00:00Z',
      lastSyncedAt: null,
      attemptCount: 1,
      maxAttempts: 3
    };
    
    render(<IntegrationSyncActivityFeed activities={[retryPendingActivity]} />);
    
    expect(screen.getByText('RETRY_PENDING')).toBeInTheDocument();
  });
  
  it('renders DEAD_LETTER status', () => {
    const deadLetterActivity = {
      id: '6',
      provider: 'TESTRAIL',
      executionId: 'exec-6',
      status: 'DEAD_LETTER',
      error: 'Max attempts reached',
      externalRunId: null,
      externalExecutionId: null,
      createdAt: '2024-01-01T00:00:00Z',
      lastSyncedAt: null,
      attemptCount: 3,
      maxAttempts: 3
    };
    
    render(<IntegrationSyncActivityFeed activities={[deadLetterActivity]} />);
    
    expect(screen.getByText('DEAD_LETTER')).toBeInTheDocument();
  });
});

describe('ExecutionSyncDiagnosticsDrawer', () => {
  const mockDiagnostics = {
    provider: 'TESTRAIL',
    executionId: 'exec-1',
    requestPayload: { test: 'data' },
    responsePayload: { success: true },
    error: null,
    timestamp: '2024-01-01T00:00:00Z'
  };

  it('renders drawer when open', () => {
    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={mockDiagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    expect(screen.getByText('Sync Diagnostics')).toBeInTheDocument();
    expect(screen.getByText('TESTRAIL')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={mockDiagnostics}
        isOpen={false}
        onClose={jest.fn()}
      />
    );

    expect(screen.queryByText('Sync Diagnostics')).not.toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const mockClose = jest.fn();
    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={mockDiagnostics}
        isOpen={true}
        onClose={mockClose}
      />
    );

    const closeButton = screen.getByText('×');
    fireEvent.click(closeButton);
    expect(mockClose).toHaveBeenCalled();
  });

  it('displays error when present', () => {
    const errorDiagnostics = {
      ...mockDiagnostics,
      error: 'XRAY_TEST_EXECUTION_KEY_REQUIRED'
    };

    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={errorDiagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    expect(screen.getByText('XRAY_TEST_EXECUTION_KEY_REQUIRED')).toBeInTheDocument();
  });

  it('displays request and response payloads', () => {
    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={mockDiagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    expect(screen.getByText('Request Payload')).toBeInTheDocument();
    expect(screen.getByText('Response Payload')).toBeInTheDocument();
  });
});

describe('Provider Configuration Validation', () => {
  it('displays TestRail configuration warning when default_test_run_id missing', () => {
    const healthStatuses = [
      {
        provider: 'TESTRAIL',
        health: 'CONFIGURATION_REQUIRED' as const,
        isConnected: true,
        lastSyncStatus: null,
        lastSyncError: null,
        missingConfiguration: 'default_test_run_id'
      }
    ];

    render(<IntegrationHealthPanel healthStatuses={healthStatuses} />);

    expect(screen.getByText('Missing: default_test_run_id')).toBeInTheDocument();
  });

  it('displays Xray configuration warning when testExecutionKey missing', () => {
    const healthStatuses = [
      {
        provider: 'XRAY',
        health: 'CONFIGURATION_REQUIRED' as const,
        isConnected: true,
        lastSyncStatus: null,
        lastSyncError: null,
        missingConfiguration: 'testExecutionKey'
      }
    ];

    render(<IntegrationHealthPanel healthStatuses={healthStatuses} />);

    expect(screen.getByText('Missing: testExecutionKey')).toBeInTheDocument();
  });

  it('displays Zephyr configuration warning when testCycleKey missing', () => {
    const healthStatuses = [
      {
        provider: 'ZEPHYR',
        health: 'CONFIGURATION_REQUIRED' as const,
        isConnected: true,
        lastSyncStatus: null,
        lastSyncError: null,
        missingConfiguration: 'testCycleKey'
      }
    ];

    render(<IntegrationHealthPanel healthStatuses={healthStatuses} />);

    expect(screen.getByText('Missing: testCycleKey')).toBeInTheDocument();
  });
});

describe('Provider-Specific Error Rendering', () => {
  it('displays XRAY_TEST_EXECUTION_KEY_REQUIRED error', () => {
    const healthStatuses = [
      {
        provider: 'XRAY',
        health: 'SYNC_FAILURES_PRESENT' as const,
        isConnected: true,
        lastSyncStatus: 'FAILED',
        lastSyncError: 'XRAY_TEST_EXECUTION_KEY_REQUIRED',
        missingConfiguration: null
      }
    ];

    render(<IntegrationHealthPanel healthStatuses={healthStatuses} />);

    expect(screen.getByText('XRAY_TEST_EXECUTION_KEY_REQUIRED')).toBeInTheDocument();
  });

  it('displays ZEPHYR_TEST_CYCLE_KEY_REQUIRED error', () => {
    const healthStatuses = [
      {
        provider: 'ZEPHYR',
        health: 'SYNC_FAILURES_PRESENT' as const,
        isConnected: true,
        lastSyncStatus: 'FAILED',
        lastSyncError: 'ZEPHYR_TEST_CYCLE_KEY_REQUIRED',
        missingConfiguration: null
      }
    ];

    render(<IntegrationHealthPanel healthStatuses={healthStatuses} />);

    expect(screen.getByText('ZEPHYR_TEST_CYCLE_KEY_REQUIRED')).toBeInTheDocument();
  });
});
