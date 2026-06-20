/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import RecommendationRunDetail from '../app/app/recommendations/[recommendationRunId]/page';

// Mock the useRouter hook
jest.mock('next/navigation', () => ({
  useRouter() {
    return {
      push: jest.fn(),
      replace: jest.fn(),
      prefetch: jest.fn(),
    };
  },
}));

// Mock Link component
jest.mock('next/link', () => {
  return ({ children, href }: { children: React.ReactNode, href: string }) => {
    return <a href={href}>{children}</a>;
  };
});

// Mock fetch globally
global.fetch = jest.fn() as jest.Mock;

describe('RecommendationRunDetail Fallback Behavior', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('renders "Evidence graph unavailable" blocking state when backend fails (500)', async () => {
    // Setup fetch mock to return a fake recommendation run but fail the regression evidence call
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/api/recommendations/run-123/regression-evidence')) {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({
            status: 'ERROR',
            error_code: 'REGRESSION_EVIDENCE_BUILD_FAILED',
            message: 'Graph build failure',
            recommendationRunId: 'run-123',
            canRenderRecommendation: false
          })
        });
      }
      
      // Mock the main run fetch to succeed so the component doesn't early exit with "Recommendation not found"
      if (url.includes('/api/recommendations/run-123')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            id: 'run-123',
            recommended_tests: [],
            evidence_gaps: [],
            warnings: [],
            scenario_coverage_matrix: { items: [] },
            impact_profile: { behavior_coverage_matrix: [] }
          })
        });
      }
      
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const params = Promise.resolve({ recommendationRunId: 'run-123' });
    render(<RecommendationRunDetail params={params} />);

    // Wait for the blocking state to appear
    await waitFor(() => {
      expect(screen.getByText('Evidence graph unavailable')).toBeInTheDocument();
    });

    // Verify blocking text exists
    expect(screen.getByText(/Veriscope could not build the backend requirement evidence graph/)).toBeInTheDocument();
    
    // Verify it does NOT show Ready or Create Regression Scope
    expect(screen.queryByText('Ready')).not.toBeInTheDocument();
    expect(screen.queryByText('Create Regression Scope')).not.toBeInTheDocument();
    
    // Verify technical details are accessible
    expect(screen.getByText(/REGRESSION_EVIDENCE_BUILD_FAILED/)).toBeInTheDocument();
    expect(screen.getByText(/Graph build failure/)).toBeInTheDocument();
  });

  it('renders normally using backend payload when regression evidence succeeds', async () => {
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/api/recommendations/run-123/regression-evidence')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            status: 'SUCCESS',
            health: 'HEALTHY',
            canRenderRecommendation: true,
            missing_tests: [{ title: 'Backend Missing Test 1' }],
            scenarios: [],
            counts: { verifiedTests: 5, missingTests: 1 }
          })
        });
      }
      
      if (url.includes('/api/recommendations/run-123')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            id: 'run-123',
            recommended_tests: [],
            evidence_gaps: [],
            warnings: [],
            scenario_coverage_matrix: { items: [] },
            impact_profile: { behavior_coverage_matrix: [] }
          })
        });
      }
      
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const params = Promise.resolve({ recommendationRunId: 'run-123' });
    render(<RecommendationRunDetail params={params} />);

    await waitFor(() => {
      // It shouldn't show the error blocking state
      expect(screen.queryByText('Evidence graph unavailable')).not.toBeInTheDocument();
    });
  });
});
