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
  it('renders quality gate badge with profile and evidence readiness', () => {
    render(<QualityGateBadge qualityGateProfileStatus="MISSING" evidenceReadiness="BLOCKED" />);
    expect(screen.getByText(/Quality Gate/)).toBeInTheDocument();
  });

  it('shows READY when evidence readiness is READY', () => {
    render(<QualityGateBadge qualityGateProfileStatus="CONFIGURED" evidenceReadiness="READY" />);
    expect(screen.getByText('Evidence Readiness: READY')).toBeInTheDocument();
  });

  it('shows REVIEW when evidence readiness is READY_WITH_REVIEW', () => {
    render(<QualityGateBadge qualityGateProfileStatus="CONFIGURED" evidenceReadiness="READY_WITH_REVIEW" />);
    expect(screen.getByText('Evidence Readiness: REVIEW')).toBeInTheDocument();
  });

  it('shows BLOCKED when evidence readiness is BLOCKED', () => {
    render(<QualityGateBadge qualityGateProfileStatus="MISSING" evidenceReadiness="BLOCKED" />);
    expect(screen.getByText('Evidence Readiness: BLOCKED')).toBeInTheDocument();
  });

  it('shows Profile: Missing when quality gate profile is MISSING', () => {
    render(<QualityGateBadge qualityGateProfileStatus="MISSING" evidenceReadiness="READY" />);
    expect(screen.getByText('Quality Gate Profile: Missing')).toBeInTheDocument();
  });

  it('shows Profile: Configured when quality gate profile is CONFIGURED', () => {
    render(<QualityGateBadge qualityGateProfileStatus="CONFIGURED" evidenceReadiness="READY" />);
    expect(screen.getByText('Quality Gate Profile: Configured')).toBeInTheDocument();
  });

  it('READY is distinct from BLOCKED', () => {
    const { rerender } = render(<QualityGateBadge qualityGateProfileStatus="CONFIGURED" evidenceReadiness="READY" />);
    expect(screen.getByText('Evidence Readiness: READY')).toBeInTheDocument();

    rerender(<QualityGateBadge qualityGateProfileStatus="CONFIGURED" evidenceReadiness="BLOCKED" />);
    expect(screen.getByText('Evidence Readiness: BLOCKED')).toBeInTheDocument();
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
    render(<CICDPipelineRunsPanel pipelineRuns={[]} qualityGateProfileStatus="MISSING" evidenceReadiness="BLOCKED" />);
    expect(screen.getByText('CI/CD Pipeline Runs')).toBeInTheDocument();
  });

  it('shows empty state when no pipeline runs or manual evidence exist', () => {
    render(<CICDPipelineRunsPanel pipelineRuns={[]} qualityGateProfileStatus="MISSING" evidenceReadiness="BLOCKED" />);
    expect(screen.getByText((content) => content.includes('No CI/CD runs or manual evidence yet'))).toBeInTheDocument();
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
    
    render(<CICDPipelineRunsPanel pipelineRuns={mockRuns} qualityGateProfileStatus="CONFIGURED" evidenceReadiness="READY_WITH_REVIEW" />);
    expect(screen.getByText('GITHUB_ACTIONS')).toBeInTheDocument();
    expect(screen.getByText('Run #12345')).toBeInTheDocument();
    expect(screen.getByText('abc123d')).toBeInTheDocument();
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
    expect(screen.getAllByText('Quality Gate: PARTIAL')).toHaveLength(1); // Row only
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
    
    render(<CICDPipelineRunsPanel pipelineRuns={mockRuns} qualityGateProfileStatus="CONFIGURED" evidenceReadiness="READY_WITH_REVIEW" />);
    expect(screen.getByText('Download Evidence Artifact')).toBeInTheDocument();
  });

  it('hides artifact download button when no pipeline runs exist', () => {
    render(<CICDPipelineRunsPanel pipelineRuns={[]} qualityGateProfileStatus="MISSING" evidenceReadiness="BLOCKED" />);
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
    
    render(<CICDPipelineRunsPanel pipelineRuns={mockRuns} qualityGateProfileStatus="CONFIGURED" evidenceReadiness="READY_WITH_REVIEW" />);
    expect(screen.getAllByText('Quality Gate: PARTIAL')).toHaveLength(1); // Row only
    expect(screen.queryByText('Quality Gate: PASSED')).not.toBeInTheDocument();
  });

  it('cicd_section_shows_manual_evidence_when_uploaded', () => {
    render(
      <CICDPipelineRunsPanel
        pipelineRuns={[]}
        qualityGateProfileStatus="MISSING"
        evidenceReadiness="BLOCKED"
        hasTestResults={true}
        hasCoverageReport={true}
      />
    );
    expect(screen.getByText('CI/CD runs:')).toBeInTheDocument();
    expect(screen.getByText('Not connected')).toBeInTheDocument();
    expect(screen.getByText('Manual evidence:')).toBeInTheDocument();
    expect(screen.getByText('Test results uploaded')).toBeInTheDocument();
    expect(screen.getByText('Coverage uploaded')).toBeInTheDocument();
  });

  it('cicd_section_does_not_say_no_evidence_when_manual_results_exist', () => {
    render(
      <CICDPipelineRunsPanel
        pipelineRuns={[]}
        qualityGateProfileStatus="MISSING"
        evidenceReadiness="BLOCKED"
        hasTestResults={true}
      />
    );
    expect(screen.queryByText((content) => content.includes('No CI/CD runs or manual evidence yet'))).not.toBeInTheDocument();
    expect(screen.getByText('Test results uploaded')).toBeInTheDocument();
  });

  it('cicd_section_shows_not_connected_when_no_ci_provider', () => {
    render(
      <CICDPipelineRunsPanel
        pipelineRuns={[]}
        qualityGateProfileStatus="MISSING"
        evidenceReadiness="BLOCKED"
        hasTestResults={true}
        hasCoverageReport={false}
      />
    );
    expect(screen.getByText('CI/CD runs:')).toBeInTheDocument();
    expect(screen.getByText('Not connected')).toBeInTheDocument();
    expect(screen.getByText('Manual evidence:')).toBeInTheDocument();
    expect(screen.getByText('Test results uploaded')).toBeInTheDocument();
    expect(screen.queryByText('Coverage uploaded')).not.toBeInTheDocument();
  });

  it('cicd_section_shows_ci_runs_when_available', () => {
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

    render(
      <CICDPipelineRunsPanel
        pipelineRuns={mockRuns}
        qualityGateProfileStatus="CONFIGURED"
        evidenceReadiness="READY_WITH_REVIEW"
        hasTestResults={true}
        hasCoverageReport={true}
      />
    );
    expect(screen.getByText('GITHUB_ACTIONS')).toBeInTheDocument();
    expect(screen.getByText('Run #12345')).toBeInTheDocument();
    expect(screen.queryByText('Not connected')).not.toBeInTheDocument();
    expect(screen.queryByText('Manual evidence:')).not.toBeInTheDocument();
  });
});
