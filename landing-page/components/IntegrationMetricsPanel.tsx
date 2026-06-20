/**
 * IntegrationMetricsPanel Component
 * 
 * Displays integration sync metrics including:
 * - Overall metrics (total syncs, success/failure rates)
 * - Provider-level breakdown
 * - Dead letter counts
 * - Retry pending counts
 */

import React from 'react';

interface ProviderMetrics {
  provider: string;
  totalSyncs: number;
  successfulSyncs: number;
  failedSyncs: number;
  retryPendingSyncs: number;
  deadLetterSyncs: number;
  successRate: number;
  failureRate: number;
  averageAttempts: number;
  lastSuccessAt: string | null;
  lastFailureAt: string | null;
}

interface OverallMetrics {
  totalSyncs: number;
  successfulSyncs: number;
  failedSyncs: number;
  retryPendingSyncs: number;
  deadLetterSyncs: number;
  successRate: number;
  failureRate: number;
  averageAttempts: number;
}

interface IntegrationMetricsPanelProps {
  providers: ProviderMetrics[];
  overall: OverallMetrics;
}

const IntegrationMetricsPanel: React.FC<IntegrationMetricsPanelProps> = ({
  providers,
  overall
}) => {
  const getRateColor = (rate: number, isFailure: boolean = false) => {
    if (isFailure) {
      if (rate > 20) return 'text-red-600';
      if (rate > 10) return 'text-orange-600';
      return 'text-green-600';
    }
    if (rate < 80) return 'text-red-600';
    if (rate < 90) return 'text-orange-600';
    return 'text-green-600';
  };

  const formatTime = (timestamp: string | null) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours} hr ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm">
      <h3 className="text-lg font-semibold mb-4">Integration Metrics</h3>
      
      {/* Overall Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="p-3 bg-blue-50 rounded">
          <div className="text-sm text-gray-600">Total Syncs</div>
          <div className="text-2xl font-bold text-blue-600">{overall.totalSyncs}</div>
        </div>
        <div className="p-3 bg-green-50 rounded">
          <div className="text-sm text-gray-600">Success Rate</div>
          <div className={`text-2xl font-bold ${getRateColor(overall.successRate)}`}>
            {overall.successRate}%
          </div>
        </div>
        <div className="p-3 bg-red-50 rounded">
          <div className="text-sm text-gray-600">Failure Rate</div>
          <div className={`text-2xl font-bold ${getRateColor(overall.failureRate, true)}`}>
            {overall.failureRate}%
          </div>
        </div>
        <div className="p-3 bg-orange-50 rounded">
          <div className="text-sm text-gray-600">Avg Attempts</div>
          <div className="text-2xl font-bold text-orange-600">
            {overall.averageAttempts.toFixed(1)}
          </div>
        </div>
      </div>

      {/* Status Counts */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="p-3 bg-gray-50 rounded">
          <div className="text-sm text-gray-600">Retry Pending</div>
          <div className="text-xl font-bold text-orange-600">{overall.retryPendingSyncs}</div>
        </div>
        <div className="p-3 bg-gray-50 rounded">
          <div className="text-sm text-gray-600">Dead Letters</div>
          <div className="text-xl font-bold text-red-600">{overall.deadLetterSyncs}</div>
        </div>
        <div className="p-3 bg-gray-50 rounded">
          <div className="text-sm text-gray-600">Successful</div>
          <div className="text-xl font-bold text-green-600">{overall.successfulSyncs}</div>
        </div>
      </div>

      {/* Provider Breakdown */}
      {providers.length > 0 && (
        <div>
          <h4 className="text-md font-semibold mb-3">Provider Breakdown</h4>
          <div className="space-y-3">
            {providers.map((provider) => (
              <div key={provider.provider} className="p-3 border rounded">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-medium">{provider.provider}</div>
                  <div className="text-sm text-gray-600">{provider.totalSyncs} syncs</div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-gray-600">Success: </span>
                    <span className={getRateColor(provider.successRate)}>
                      {provider.successRate}%
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-600">Failure: </span>
                    <span className={getRateColor(provider.failureRate, true)}>
                      {provider.failureRate}%
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-600">Retry Pending: </span>
                    <span className="text-orange-600">{provider.retryPendingSyncs}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Dead Letter: </span>
                    <span className="text-red-600">{provider.deadLetterSyncs}</span>
                  </div>
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  Last success: {formatTime(provider.lastSuccessAt)} | 
                  Last failure: {formatTime(provider.lastFailureAt)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default IntegrationMetricsPanel;
