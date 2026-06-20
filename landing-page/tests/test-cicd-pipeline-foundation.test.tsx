/**
 * CI/CD Pipeline Foundation Tests (Phase 8.0A)
 *
 * Tests for CI/CD pipeline integration in the frontend.
 */

import React from 'react';
import { describe, it, expect, jest } from '@jest/globals';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { GitHubActionsSnippet, githubActionsSnippet } from '../components/GitHubActionsSnippet';
import { QualityGateBadge } from '../components/QualityGateBadge';
import { EvidenceArtifactDownloadButton } from '../components/EvidenceArtifactDownloadButton';
import { CICDPipelineRunsPanel } from '../components/CICDPipelineRunsPanel';

describe('GitHubActionsSnippet', () => {
  it('renders GitHub Actions snippet', () => {
    render(<GitHubActionsSnippet />);
    expect(screen.getByText('GitHub Actions Integration')).toBeInTheDocument();
  });

  it('snippet uses placeholder environment variables', () => {
    expect(githubActionsSnippet).toContain('$VERISCOPE_API_URL');
    expect(githubActionsSnippet).toContain('$VERISCOPE_TOKEN');
    expect(githubActionsSnippet).toContain('$VERISCOPE_REPOSITORY_ID');
  });

  it('snippet does not expose real secrets', () => {
    expect(githubActionsSnippet).not.toContain('sk-');
    expect(githubActionsSnippet).not.toContain('ghp_');
    expect(githubActionsSnippet).not.toContain('gho_');
    expect(githubActionsSnippet).not.toContain('ghu_');
    expect(githubActionsSnippet).not.toContain('ghs_');
    expect(githubActionsSnippet).not.toContain('ghr_');
  });
});

describe('QualityGateBadge', () => {
  it('renders quality gate badge', () => {
    render(<QualityGateBadge hasRequiredItems={false} isApproved={true} />);
    expect(screen.getByText(/Quality Gate:/)).toBeInTheDocument();
  });

  it('shows PASSED when approved with no required items', () => {
    render(<QualityGateBadge hasRequiredItems={false} isApproved={true} />);
    expect(screen.getByText('Quality Gate: PASSED')).toBeInTheDocument();
  });

  it('shows PARTIAL when required items exist', () => {
    render(<QualityGateBadge hasRequiredItems={true} isApproved={false} />);
    expect(screen.getByText('Quality Gate: PARTIAL')).toBeInTheDocument();
  });

  it('shows UNKNOWN when no decision and no required items', () => {
    render(<QualityGateBadge hasRequiredItems={false} isApproved={false} />);
    expect(screen.getByText('Quality Gate: UNKNOWN')).toBeInTheDocument();
  });

  it('PARTIAL quality gate is distinct from PASSED', () => {
    const { rerender } = render(<QualityGateBadge hasRequiredItems={true} isApproved={false} />);
    expect(screen.getByText('Quality Gate: PARTIAL')).toBeInTheDocument();
    
    rerender(<QualityGateBadge hasRequiredItems={false} isApproved={true} />);
    expect(screen.getByText('Quality Gate: PASSED')).toBeInTheDocument();
  });
});

describe('EvidenceArtifactDownloadButton', () => {
  it('renders download button', () => {
    render(<EvidenceArtifactDownloadButton pipelineRunId="test-id" />);
    expect(screen.getByText('Download Evidence Artifact')).toBeInTheDocument();
  });

  it('button calls correct endpoint on click', () => {
    global.fetch = jest.fn() as jest.Mock;
    render(<EvidenceArtifactDownloadButton pipelineRunId="test-run-id" />);
    
    const button = screen.getByText('Download Evidence Artifact');
    button.click();
    
    expect(fetch).toHaveBeenCalledWith('/api/pipeline-runs/test-run-id/artifact');
  });
});

describe('CICDPipelineRunsPanel', () => {
  it('renders CI/CD Runs section', () => {
    render(<CICDPipelineRunsPanel pipelineRuns={[]} hasRequiredItems={false} isApproved={false} />);
    expect(screen.getByText('CI/CD Pipeline Runs')).toBeInTheDocument();
  });

  it('shows empty state when no pipeline runs exist', () => {
    render(<CICDPipelineRunsPanel pipelineRuns={[]} hasRequiredItems={false} isApproved={false} />);
    expect(screen.getByText((content) => content.includes('No CI/CD runs yet'))).toBeInTheDocument();
  });

  it('renders pipeline run row when runs exist', () => {
    const mockRuns = [
      {
        id: '1',
        provider: 'GITHUB_ACTIONS',
        externalRunId: '12345',
        commitSha: 'abc123def456',
        status: 'COMPLETED',
        qualityGate: 'PARTIAL',
        createdAt: '2024-01-01T00:00:00Z'
      }
    ];
    
    render(<CICDPipelineRunsPanel pipelineRuns={mockRuns} hasRequiredItems={true} isApproved={false} />);
    expect(screen.getByText('GITHUB_ACTIONS')).toBeInTheDocument();
    expect(screen.getByText('Run #12345')).toBeInTheDocument();
    expect(screen.getByText('abc123d')).toBeInTheDocument();
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
    expect(screen.getAllByText('Quality Gate: PARTIAL')).toHaveLength(2); // Header + row
  });

  it('renders artifact download button for pipeline runs', () => {
    const mockRuns = [
      {
        id: '1',
        provider: 'GITHUB_ACTIONS',
        externalRunId: '12345',
        commitSha: 'abc123def456',
        status: 'COMPLETED',
        qualityGate: 'PARTIAL',
        createdAt: '2024-01-01T00:00:00Z'
      }
    ];
    
    render(<CICDPipelineRunsPanel pipelineRuns={mockRuns} hasRequiredItems={true} isApproved={false} />);
    expect(screen.getByText('Download Evidence Artifact')).toBeInTheDocument();
  });

  it('hides artifact download button when no pipeline runs exist', () => {
    render(<CICDPipelineRunsPanel pipelineRuns={[]} hasRequiredItems={false} isApproved={false} />);
    expect(screen.queryByText('Download Evidence Artifact')).not.toBeInTheDocument();
  });

  it('Quality Gate: PARTIAL does not display as PASSED', () => {
    const mockRuns = [
      {
        id: '1',
        provider: 'GITHUB_ACTIONS',
        externalRunId: '12345',
        commitSha: 'abc123def456',
        status: 'COMPLETED',
        qualityGate: 'PARTIAL',
        createdAt: '2024-01-01T00:00:00Z'
      }
    ];
    
    render(<CICDPipelineRunsPanel pipelineRuns={mockRuns} hasRequiredItems={true} isApproved={false} />);
    expect(screen.getAllByText('Quality Gate: PARTIAL')).toHaveLength(2); // Header + row
    expect(screen.queryByText('Quality Gate: PASSED')).not.toBeInTheDocument();
  });
});
