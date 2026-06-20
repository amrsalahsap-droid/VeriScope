/**
 * IntegrationHealthPanel Component
 * 
 * Displays health status for integrations:
 * - Connected
 * - Disconnected
 * - Configuration Required
 * - Authentication Failed
 * - Sync Failures Present
 * - Healthy
 */

import React from 'react';

interface HealthStatus {
  provider: string;
  health: 'HEALTHY' | 'DISCONNECTED' | 'CONFIGURATION_REQUIRED' | 'AUTHENTICATION_FAILED' | 'SYNC_FAILURES_PRESENT' | 'COOLDOWN_ACTIVE';
  isConnected: boolean;
  lastSyncStatus: string | null;
  lastSyncError: string | null;
  missingConfiguration: string | null;
  cooldownRemaining?: number | null;
  cooldownReason?: string | null;
}

interface IntegrationHealthPanelProps {
  healthStatuses: HealthStatus[];
  onRetryFailedSyncs?: (provider: string) => void;
  retryingProvider?: string | null;
}

const IntegrationHealthPanel: React.FC<IntegrationHealthPanelProps> = ({ 
  healthStatuses, 
  onRetryFailedSyncs,
  retryingProvider 
}) => {
  const getHealthColor = (health: string) => {
    switch (health) {
      case 'HEALTHY':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'DISCONNECTED':
        return 'bg-gray-100 text-gray-600 border-gray-200';
      case 'CONFIGURATION_REQUIRED':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'AUTHENTICATION_FAILED':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'SYNC_FAILURES_PRESENT':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'COOLDOWN_ACTIVE':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      default:
        return 'bg-gray-100 text-gray-600 border-gray-200';
    }
  };

  const getHealthIcon = (health: string) => {
    switch (health) {
      case 'HEALTHY':
        return '✓';
      case 'DISCONNECTED':
        return '○';
      case 'CONFIGURATION_REQUIRED':
        return '⚠';
      case 'AUTHENTICATION_FAILED':
        return '✕';
      case 'SYNC_FAILURES_PRESENT':
        return '!';
      case 'COOLDOWN_ACTIVE':
        return '⏸';
      default:
        return '?';
    }
  };

  const getHealthLabel = (health: string) => {
    switch (health) {
      case 'HEALTHY':
        return 'Healthy';
      case 'DISCONNECTED':
        return 'Disconnected';
      case 'CONFIGURATION_REQUIRED':
        return 'Configuration Required';
      case 'AUTHENTICATION_FAILED':
        return 'Authentication Failed';
      case 'SYNC_FAILURES_PRESENT':
        return 'Sync Failures Present';
      case 'COOLDOWN_ACTIVE':
        return 'Cooldown Active';
      default:
        return 'Unknown';
    }
  };

  const formatCooldownTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm">
      <h3 className="text-lg font-semibold mb-3">Integration Health</h3>
      <div className="space-y-2">
        {healthStatuses.map((status) => (
          <div
            key={status.provider}
            className={`flex items-center justify-between p-3 rounded border ${getHealthColor(status.health)}`}
          >
            <div className="flex items-center gap-2">
              <span className="text-lg">{getHealthIcon(status.health)}</span>
              <span className="font-medium">{status.provider}</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-sm">
                {status.health === 'COOLDOWN_ACTIVE' && status.cooldownRemaining && (
                  <div className="text-blue-700">
                    Cooldown: {formatCooldownTime(status.cooldownRemaining)}
                    {status.cooldownReason && ` (${status.cooldownReason})`}
                  </div>
                )}
                {status.missingConfiguration && (
                  <div className="text-yellow-700">
                    Missing: {status.missingConfiguration}
                  </div>
                )}
                {status.lastSyncError && status.health !== 'COOLDOWN_ACTIVE' && (
                  <div className="text-red-700 truncate max-w-xs">
                    {status.lastSyncError}
                  </div>
                )}
                {!status.missingConfiguration && !status.lastSyncError && status.health !== 'COOLDOWN_ACTIVE' && (
                  <div>{getHealthLabel(status.health)}</div>
                )}
              </div>
              {status.health === 'SYNC_FAILURES_PRESENT' && onRetryFailedSyncs && (
                <button
                  onClick={() => onRetryFailedSyncs(status.provider)}
                  disabled={retryingProvider === status.provider}
                  className="px-3 py-1 text-xs bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
                >
                  {retryingProvider === status.provider ? 'Retrying...' : 'Retry All'}
                </button>
              )}
              {status.health === 'COOLDOWN_ACTIVE' && onRetryFailedSyncs && (
                <button
                  disabled
                  className="px-3 py-1 text-xs bg-gray-100 border border-gray-300 rounded text-gray-500 cursor-not-allowed"
                >
                  Retry Disabled
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default IntegrationHealthPanel;
