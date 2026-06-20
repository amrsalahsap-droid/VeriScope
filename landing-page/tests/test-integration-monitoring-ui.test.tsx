/**
 * Integration Monitoring UI Tests
 * 
 * Tests for:
 * - IntegrationMetricsPanel
 * - IntegrationAlertSummary
 * - IntegrationSyncActivityFeed with pagination
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import IntegrationMetricsPanel from '../components/IntegrationMetricsPanel';
import IntegrationAlertSummary from '../components/IntegrationAlertSummary';
import IntegrationSyncActivityFeed from '../components/IntegrationSyncActivityFeed';

describe('IntegrationMetricsPanel', () => {
  const mockProviders = [
    {
      provider: 'TESTRAIL',
      totalSyncs: 100,
      successfulSyncs: 80,
      failedSyncs: 20,
      retryPendingSyncs: 5,
      deadLetterSyncs: 2,
      successRate: 80.0,
      failureRate: 20.0,
      averageAttempts: 1.2,
      lastSuccessAt: new Date(Date.now() - 3600000).toISOString(),
      lastFailureAt: new Date(Date.now() - 7200000).toISOString()
    }
  ];

  const mockOverall = {
    totalSyncs: 100,
    successfulSyncs: 80,
    failedSyncs: 20,
    retryPendingSyncs: 5,
    deadLetterSyncs: 2,
    successRate: 80.0,
    failureRate: 20.0,
    averageAttempts: 1.2
  };

  it('renders overall metrics correctly', () => {
    render(<IntegrationMetricsPanel providers={mockProviders} overall={mockOverall} />);
    
    expect(screen.getByText('Integration Metrics')).toBeInTheDocument();
    expect(screen.getByText('Total Syncs')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getByText('Success Rate')).toBeInTheDocument();
    // Use getAllByText since 80% appears in both overall and provider breakdown
    const eightyPercentElements = screen.getAllByText('80%');
    expect(eightyPercentElements.length).toBeGreaterThan(0);
    expect(screen.getByText('Failure Rate')).toBeInTheDocument();
    // Use getAllByText since 20% appears in both overall and provider breakdown
    const twentyPercentElements = screen.getAllByText('20%');
    expect(twentyPercentElements.length).toBeGreaterThan(0);
  });

  it('renders provider breakdown', () => {
    render(<IntegrationMetricsPanel providers={mockProviders} overall={mockOverall} />);
    
    expect(screen.getByText('Provider Breakdown')).toBeInTheDocument();
    expect(screen.getByText('TESTRAIL')).toBeInTheDocument();
    expect(screen.getByText('100 syncs')).toBeInTheDocument();
  });

  it('displays correct color for high failure rate', () => {
    const highFailureMetrics = {
      ...mockOverall,
      failureRate: 25.0
    };
    
    render(<IntegrationMetricsPanel providers={mockProviders} overall={highFailureMetrics} />);
    
    const failureRateElement = screen.getByText('25%');
    expect(failureRateElement).toHaveClass('text-red-600');
  });

  it('displays correct color for good success rate', () => {
    const goodSuccessMetrics = {
      ...mockOverall,
      successRate: 95.0
    };
    
    render(<IntegrationMetricsPanel providers={mockProviders} overall={goodSuccessMetrics} />);
    
    const successRateElement = screen.getByText('95%');
    expect(successRateElement).toHaveClass('text-green-600');
  });
});

describe('IntegrationAlertSummary', () => {
  it('renders no alerts state correctly', () => {
    render(<IntegrationAlertSummary alerts={[]} />);
    
    expect(screen.getByText('Alert Status')).toBeInTheDocument();
    expect(screen.getByText('No active alerts')).toBeInTheDocument();
    expect(screen.getByText('✓')).toBeInTheDocument();
  });

  it('renders high severity alerts', () => {
    const alerts = [
      {
        code: 'HIGH_FAILURE_RATE',
        severity: 'HIGH' as const,
        message: 'Overall failure rate is 25% over the selected period.'
      }
    ];
    
    render(<IntegrationAlertSummary alerts={alerts} />);
    
    expect(screen.getByText('High Severity (1)')).toBeInTheDocument();
    expect(screen.getByText('High Failure Rate')).toBeInTheDocument();
    expect(screen.getByText('Overall failure rate is 25% over the selected period.')).toBeInTheDocument();
    expect(screen.getByText('⚠')).toBeInTheDocument();
  });

  it('renders medium severity alerts', () => {
    const alerts = [
      {
        code: 'NO_RECENT_SUCCESS',
        severity: 'MEDIUM' as const,
        message: 'No successful syncs in the last 24 hours.'
      }
    ];
    
    render(<IntegrationAlertSummary alerts={alerts} />);
    
    expect(screen.getByText('Medium Severity (1)')).toBeInTheDocument();
    expect(screen.getByText('No Recent Success')).toBeInTheDocument();
    expect(screen.getByText('⚡')).toBeInTheDocument();
  });

  it('renders low severity alerts', () => {
    const alerts = [
      {
        code: 'PROVIDER_COOLDOWN_ACTIVE',
        severity: 'LOW' as const,
        message: 'Provider cooldown active for: TESTRAIL.'
      }
    ];
    
    render(<IntegrationAlertSummary alerts={alerts} />);
    
    expect(screen.getByText('Low Severity (1)')).toBeInTheDocument();
    expect(screen.getByText('Provider Cooldown Active')).toBeInTheDocument();
    expect(screen.getByText('ℹ')).toBeInTheDocument();
  });

  it('renders multiple alerts grouped by severity', () => {
    const alerts = [
      {
        code: 'HIGH_FAILURE_RATE',
        severity: 'HIGH' as const,
        message: 'High failure rate detected.'
      },
      {
        code: 'DEAD_LETTER_PRESENT',
        severity: 'HIGH' as const,
        message: 'Dead letter events present.'
      },
      {
        code: 'NO_RECENT_SUCCESS',
        severity: 'MEDIUM' as const,
        message: 'No recent success.'
      }
    ];
    
    render(<IntegrationAlertSummary alerts={alerts} />);
    
    expect(screen.getByText('High Severity (2)')).toBeInTheDocument();
    expect(screen.getByText('Medium Severity (1)')).toBeInTheDocument();
  });
});

describe('IntegrationSyncActivityFeed', () => {
  const mockActivities = [
    {
      id: '1',
      provider: 'TESTRAIL',
      executionId: 'exec-123',
      status: 'SYNCED',
      error: null,
      externalRunId: 'run-1',
      externalExecutionId: 'ext-1',
      createdAt: new Date(Date.now() - 3600000).toISOString(),
      lastSyncedAt: new Date(Date.now() - 3600000).toISOString(),
      attemptCount: 1,
      maxAttempts: 5
    },
    {
      id: '2',
      provider: 'JIRA',
      executionId: 'exec-456',
      status: 'FAILED',
      error: 'Connection timeout',
      externalRunId: 'run-2',
      externalExecutionId: 'ext-2',
      createdAt: new Date(Date.now() - 7200000).toISOString(),
      lastSyncedAt: new Date(Date.now() - 7200000).toISOString(),
      attemptCount: 2,
      maxAttempts: 5
    }
  ];

  it('renders activities list', () => {
    render(<IntegrationSyncActivityFeed activities={mockActivities} />);
    
    expect(screen.getByText('Sync Activity')).toBeInTheDocument();
    expect(screen.getByText('TESTRAIL')).toBeInTheDocument();
    expect(screen.getByText('JIRA')).toBeInTheDocument();
    expect(screen.getByText('SYNCED')).toBeInTheDocument();
    expect(screen.getByText('FAILED')).toBeInTheDocument();
  });

  it('renders provider filter dropdown', () => {
    const onProviderFilterChange = jest.fn();
    render(
      <IntegrationSyncActivityFeed 
        activities={mockActivities} 
        onProviderFilterChange={onProviderFilterChange}
      />
    );
    
    const select = screen.getByRole('combobox');
    expect(select).toBeInTheDocument();
    expect(screen.getByText('All Providers')).toBeInTheDocument();
  });

  it('calls onProviderFilterChange when provider is selected', () => {
    const onProviderFilterChange = jest.fn();
    render(
      <IntegrationSyncActivityFeed 
        activities={mockActivities} 
        onProviderFilterChange={onProviderFilterChange}
      />
    );
    
    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'TESTRAIL' } });
    
    expect(onProviderFilterChange).toHaveBeenCalledWith('TESTRAIL');
  });

  it('renders status filter dropdown', () => {
    const onStatusFilterChange = jest.fn();
    render(
      <IntegrationSyncActivityFeed 
        activities={mockActivities} 
        onStatusFilterChange={onStatusFilterChange}
      />
    );
    
    const statusSelect = screen.getByRole('combobox');
    expect(statusSelect).toBeInTheDocument();
    expect(screen.getByText('All Statuses')).toBeInTheDocument();
  });

  it('filters activities by provider', () => {
    render(
      <IntegrationSyncActivityFeed 
        activities={mockActivities} 
        providerFilter="TESTRAIL"
      />
    );
    
    expect(screen.getByText('TESTRAIL')).toBeInTheDocument();
    expect(screen.queryByText('JIRA')).not.toBeInTheDocument();
  });

  it('filters activities by status', () => {
    render(
      <IntegrationSyncActivityFeed 
        activities={mockActivities} 
        statusFilter="SYNCED"
      />
    );
    
    expect(screen.getByText('SYNCED')).toBeInTheDocument();
    expect(screen.queryByText('FAILED')).not.toBeInTheDocument();
  });

  it('renders paginated response format', () => {
    const paginatedResponse = {
      items: mockActivities,
      nextCursor: 'cursor-123',
      hasMore: true,
      limit: 50
    };
    
    const onLoadMore = jest.fn();
    render(
      <IntegrationSyncActivityFeed 
        activities={paginatedResponse} 
        onLoadMore={onLoadMore}
      />
    );
    
    expect(screen.getByText('Load More')).toBeInTheDocument();
  });

  it('calls onLoadMore when Load More button is clicked', () => {
    const paginatedResponse = {
      items: mockActivities,
      nextCursor: 'cursor-123',
      hasMore: true,
      limit: 50
    };
    
    const onLoadMore = jest.fn();
    render(
      <IntegrationSyncActivityFeed 
        activities={paginatedResponse} 
        onLoadMore={onLoadMore}
      />
    );
    
    const loadMoreButton = screen.getByText('Load More');
    fireEvent.click(loadMoreButton);
    
    expect(onLoadMore).toHaveBeenCalledWith('cursor-123');
  });

  it('disables Load More button when loading', () => {
    const paginatedResponse = {
      items: mockActivities,
      nextCursor: 'cursor-123',
      hasMore: true,
      limit: 50
    };
    
    const onLoadMore = jest.fn();
    render(
      <IntegrationSyncActivityFeed 
        activities={paginatedResponse} 
        onLoadMore={onLoadMore}
        loading={true}
      />
    );
    
    const loadMoreButton = screen.getByText('Loading...');
    expect(loadMoreButton).toBeDisabled();
  });

  it('does not show Load More button when hasMore is false', () => {
    const paginatedResponse = {
      items: mockActivities,
      nextCursor: null,
      hasMore: false,
      limit: 50
    };
    
    render(
      <IntegrationSyncActivityFeed 
        activities={paginatedResponse} 
        onLoadMore={jest.fn()}
      />
    );
    
    expect(screen.queryByText('Load More')).not.toBeInTheDocument();
  });

  it('renders empty state when no activities', () => {
    render(<IntegrationSyncActivityFeed activities={[]} />);
    
    expect(screen.getByText('No sync activity found')).toBeInTheDocument();
  });

  it('displays attempt count information', () => {
    render(<IntegrationSyncActivityFeed activities={mockActivities} />);
    
    expect(screen.getByText('Attempt 1/5')).toBeInTheDocument();
    expect(screen.getByText('Attempt 2/5')).toBeInTheDocument();
  });

  it('displays error message for failed syncs', () => {
    render(<IntegrationSyncActivityFeed activities={mockActivities} />);
    
    expect(screen.getByText('Connection timeout')).toBeInTheDocument();
  });
});
