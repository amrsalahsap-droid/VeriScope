/**
 * CI/CD Pipeline Runs Panel Component
 * Displays pipeline runs associated with a recommendation
 */

import React from 'react';

import { GitBranch } from 'lucide-react';
import { GitHubActionsSnippet } from './GitHubActionsSnippet';
import { QualityGateBadge } from './QualityGateBadge';
import { EvidenceArtifactDownloadButton } from './EvidenceArtifactDownloadButton';
import type {
  QualityGateProfileStatus,
  EvidenceReadiness,
} from '@/lib/quality-gate';

interface PipelineRun {
  id: string;
  provider: string;
  externalRunId: string;
  commitSha: string;
  branch?: string;
  status: string;
  qualityGate: string;
  createdAt: string;
  githubStatusPublished?: boolean;
  githubStatusState?: string;
  prCommentPosted?: boolean;
  failureReason?: string;
  // Async job fields
  jobStatus?: 'PENDING' | 'IN_PROGRESS' | 'RETRY_PENDING' | 'COMPLETED' | 'FAILED' | 'DEAD_LETTER' | 'CANCELLED';
  attemptCount?: number;
  nextAttemptAt?: string;
  artifactStatus?: 'ready' | 'pending' | 'unavailable';
  // Admin fields
  ciTokenName?: string;
  ciTokenScopes?: string;
  triggeredBy?: string;
  rateLimitState?: 'normal' | 'cooldown' | 'retry';
  webhookEventId?: string;
  auditEventCount?: number;
}

interface CICDPipelineRunsPanelProps {
  pipelineRuns: PipelineRun[];
  qualityGateProfileStatus: QualityGateProfileStatus;
  evidenceReadiness: EvidenceReadiness;
  hasTestResults?: boolean;
  hasCoverageReport?: boolean;
}

export function CICDPipelineRunsPanel({
  pipelineRuns,
  qualityGateProfileStatus,
  evidenceReadiness,
  hasTestResults = false,
  hasCoverageReport = false,
}: CICDPipelineRunsPanelProps) {
  const hasManualEvidence = hasTestResults || hasCoverageReport;
  return (
    <div id="cicd-pipeline-runs" className="bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-zinc-800/40 pb-3">
        <div className="flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-bold text-white">CI/CD Pipeline Runs</h2>
        </div>
        <QualityGateBadge qualityGateProfileStatus={qualityGateProfileStatus} evidenceReadiness={evidenceReadiness} />
      </div>
      
      {/* Empty State - shown when no pipeline runs exist */}
      {!pipelineRuns || pipelineRuns.length === 0 ? (
        <div className="text-sm text-zinc-400 space-y-2">
          {hasManualEvidence ? (
            <>
              <p>
                <span className="font-semibold text-zinc-300">CI/CD runs:</span> Not connected
              </p>
              <p className="font-semibold text-zinc-300">Manual evidence:</p>
              <ul className="list-disc list-inside text-zinc-400">
                {hasTestResults && <li>Test results uploaded</li>}
                {hasCoverageReport && <li>Coverage uploaded</li>}
              </ul>
            </>
          ) : (
            <p>No CI/CD runs or manual evidence yet.</p>
          )}
          {!hasManualEvidence && (
            <p>Trigger Veriscope from GitHub Actions to create a pipeline run.</p>
          )}
        </div>
      ) : (
        /* Pipeline Run Rows - shown when pipeline runs exist */
        <div className="space-y-3">
          {pipelineRuns.map((run) => (
            <div key={run.id} className="bg-zinc-950/40 border border-zinc-800/30 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-medium text-zinc-400">{run.provider}</span>
                  <span className="text-xs text-zinc-500">Run #{run.externalRunId}</span>
                  <span className="text-xs font-mono text-zinc-500">{run.commitSha?.substring(0, 7)}</span>
                  {run.branch && <span className="text-xs text-zinc-500">{run.branch}</span>}
                </div>
                <div className="flex items-center gap-2">
                  {/* Async job status badge */}
                  {run.jobStatus && (
                    <span className={`px-2 py-1 text-xs font-semibold rounded ${
                      run.jobStatus === 'COMPLETED' ? 'bg-emerald-950/20 text-emerald-400 border-emerald-800/40' :
                      run.jobStatus === 'IN_PROGRESS' ? 'bg-blue-950/20 text-blue-400 border-blue-800/40' :
                      run.jobStatus === 'PENDING' ? 'bg-yellow-950/20 text-yellow-400 border-yellow-800/40' :
                      run.jobStatus === 'RETRY_PENDING' ? 'bg-orange-950/20 text-orange-400 border-orange-800/40' :
                      run.jobStatus === 'FAILED' || run.jobStatus === 'DEAD_LETTER' ? 'bg-red-950/20 text-red-400 border-red-800/40' :
                      'bg-zinc-950/20 text-zinc-400 border-zinc-800/40'
                    }`}>
                      {run.jobStatus}
                    </span>
                  )}
                  <span className="px-2 py-1 text-xs font-semibold rounded bg-emerald-950/20 text-emerald-400 border-emerald-800/40">
                    {run.status}
                  </span>
                  <span className="px-2 py-1 text-xs font-semibold rounded bg-amber-950/20 text-amber-400 border-amber-800/40">
                    Quality Gate: {run.qualityGate}
                  </span>
                </div>
              </div>
              
              {/* Async job details */}
              {run.jobStatus && run.jobStatus !== 'COMPLETED' && (
                <div className="flex items-center gap-4 mb-2 text-xs text-zinc-500">
                  {run.attemptCount !== undefined && run.attemptCount > 0 && (
                    <span>Attempt: {run.attemptCount}</span>
                  )}
                  {run.nextAttemptAt && (
                    <span>Next retry: {new Date(run.nextAttemptAt).toLocaleString()}</span>
                  )}
                </div>
              )}
              
              {/* GitHub Integration Status */}
              <div className="flex items-center gap-4 mb-2 text-xs text-zinc-500">
                {run.githubStatusPublished && (
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-green-500"></span>
                    GitHub Status: {run.githubStatusState || 'published'}
                  </span>
                )}
                {run.prCommentPosted && (
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                    PR Comment: posted
                  </span>
                )}
                {run.failureReason && (
                  <span className="flex items-center gap-1 text-red-400">
                    <span className="w-2 h-2 rounded-full bg-red-500"></span>
                    Error: {run.failureReason}
                  </span>
                )}
              </div>
              
              {/* Admin Details */}
              {(run.ciTokenName || run.triggeredBy || run.rateLimitState || run.webhookEventId || run.auditEventCount) && (
                <div className="mt-3 pt-3 border-t border-zinc-800/40">
                  <div className="text-xs font-semibold text-zinc-400 mb-2">Admin Details</div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-zinc-500">
                    {run.ciTokenName && (
                      <div className="flex items-center gap-1">
                        <span className="text-zinc-600">CI Token:</span>
                        <span className="text-zinc-400">{run.ciTokenName}</span>
                      </div>
                    )}
                    {run.ciTokenScopes && (
                      <div className="flex items-center gap-1">
                        <span className="text-zinc-600">Scopes:</span>
                        <span className="text-zinc-400">{run.ciTokenScopes}</span>
                      </div>
                    )}
                    {run.triggeredBy && (
                      <div className="flex items-center gap-1">
                        <span className="text-zinc-600">Triggered By:</span>
                        <span className="text-zinc-400">{run.triggeredBy}</span>
                      </div>
                    )}
                    {run.rateLimitState && (
                      <div className="flex items-center gap-1">
                        <span className="text-zinc-600">Rate Limit:</span>
                        <span className={`${
                          run.rateLimitState === 'normal' ? 'text-green-400' :
                          run.rateLimitState === 'cooldown' ? 'text-orange-400' :
                          'text-yellow-400'
                        }`}>{run.rateLimitState}</span>
                      </div>
                    )}
                    {run.webhookEventId && (
                      <div className="flex items-center gap-1">
                        <span className="text-zinc-600">Webhook Event:</span>
                        <span className="text-zinc-400 font-mono">{run.webhookEventId.substring(0, 8)}...</span>
                      </div>
                    )}
                    {run.auditEventCount !== undefined && (
                      <div className="flex items-center gap-1">
                        <span className="text-zinc-600">Audit Events:</span>
                        <span className="text-zinc-400">{run.auditEventCount}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">{new Date(run.createdAt).toLocaleString()}</span>
                {run.artifactStatus === 'pending' ? (
                  <span className="text-xs text-zinc-500">Artifact not ready yet</span>
                ) : run.artifactStatus === 'unavailable' ? (
                  <span className="text-xs text-red-400">Artifact unavailable</span>
                ) : (
                  <EvidenceArtifactDownloadButton pipelineRunId={run.id} />
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      
      <GitHubActionsSnippet />
    </div>
  );
}
