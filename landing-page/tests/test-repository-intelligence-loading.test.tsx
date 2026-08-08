/**
 * Repository Intelligence Loading Indicator Tests
 *
 * Tests for ensuring that the Run Repository Intelligence button
 * shows immediate loading state while the API request is pending.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock next/navigation before importing the component
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

// Mock fetch globally
global.fetch = jest.fn();

const mockFetch = global.fetch as jest.Mock;

function createReadinessData() {
  return {
    readiness_level: "BLOCKED",
    expected_confidence: "LOW",
    readiness_score: 0,
    can_generate: false,
    available_inputs: [],
    missing_inputs: [
      {
        key: "architecture_graph",
        label: "Architecture Graph",
        severity: "REQUIRED",
        impact: "Repository architecture has not been analyzed.",
        estimated_confidence_gain: 10,
        actions: [],
      },
      {
        key: "behavior_catalog",
        label: "Behavior Catalog",
        severity: "REQUIRED",
        impact: "System behavior catalog has not been discovered.",
        estimated_confidence_gain: 10,
        actions: [],
      },
      {
        key: "journey_catalog",
        label: "Journey Catalog",
        severity: "REQUIRED",
        impact: "User journey catalog has not been discovered.",
        estimated_confidence_gain: 10,
        actions: [],
      },
    ],
    next_best_actions: [],
    primary_message: "System intelligence is missing.",
  };
}

describe('Repository Intelligence Loading Indicator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should show loading state immediately after clicking Run Repository Intelligence', async () => {
    // Mock the legacy readiness endpoint response (no pullRequestId)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => createReadinessData(),
    });

    const { default: RecommendationReadinessGate } = await import(
      '@/components/recommendations/recommendation-readiness-gate'
    );

    let resolveRefresh: (() => void) | undefined;
    const runRepositoryIntelligence = jest.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveRefresh = resolve;
        })
    );

    render(
      <RecommendationReadinessGate
        isOpen={true}
        onClose={() => {}}
        onContinue={() => {}}
        repositoryId="repo-123"
        action="generate"
        runRepositoryIntelligence={runRepositoryIntelligence}
      />
    );

    // Wait for the button to appear
    await waitFor(() => {
      expect(screen.getByText('Run Repository Intelligence')).toBeInTheDocument();
    });

    const button = screen.getByText('Run Repository Intelligence');

    // Click the button
    fireEvent.click(button);

    // Loading state should appear immediately
    await waitFor(() => {
      expect(screen.getByTestId('ri-refresh-loading')).toBeInTheDocument();
    });

    expect(screen.getByText('Refreshing Product Behavior Map…')).toBeInTheDocument();
    expect(screen.getByText(/Repository intelligence is running/)).toBeInTheDocument();

    // Second click should not trigger another refresh
    fireEvent.click(button);
    expect(runRepositoryIntelligence).toHaveBeenCalledTimes(1);

    // Cleanup: resolve the refresh promise
    if (resolveRefresh) {
      resolveRefresh();
    }
  });

  it('should render failed state when refresh fails', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => createReadinessData(),
    });

    const { default: RecommendationReadinessGate } = await import(
      '@/components/recommendations/recommendation-readiness-gate'
    );

    const runRepositoryIntelligence = jest.fn(() => Promise.reject(new Error('Refresh failed')));

    render(
      <RecommendationReadinessGate
        isOpen={true}
        onClose={() => {}}
        onContinue={() => {}}
        repositoryId="repo-123"
        action="generate"
        runRepositoryIntelligence={runRepositoryIntelligence}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Run Repository Intelligence')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Run Repository Intelligence'));

    await waitFor(() => {
      expect(screen.getByText(/Refresh failed/)).toBeInTheDocument();
    });
  });
});
