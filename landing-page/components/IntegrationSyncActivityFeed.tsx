/**
 * IntegrationSyncActivityFeed Component
 * 
 * Displays sync activity feed showing:
 * - Provider
 * - Execution
 * - Status
 * - Time
 */

import React from 'react';

interface SyncActivity {
  id: string;
  provider: string;
  executionId: string;
  status: string;
  error: string | null;
  externalRunId: string | null;
  externalExecutionId: string | null;
  createdAt: string | null;
  lastSyncedAt: string | null;
  attemptCount?: number;
  maxAttempts?: number;
  nextAttemptAt?: string | null;
  cooldownUntil?: string | null;
  cooldownReason?: string | null;
}

interface PaginatedSyncActivityResponse {
  items: SyncActivity[];
  nextCursor: string | null;
  hasMore: boolean;
  limit: number;
}

interface IntegrationSyncActivityFeedProps {
  activities: SyncActivity[] | PaginatedSyncActivityResponse;
  providerFilter?: string;
  statusFilter?: string;
  onProviderFilterChange?: (provider: string | null) => void;
  onStatusFilterChange?: (status: string | null) => void;
  onLoadMore?: (cursor: string) => void;
  loading?: boolean;
}

const IntegrationSyncActivityFeed: React.FC<IntegrationSyncActivityFeedProps> = ({
  activities,
  providerFilter,
  statusFilter,
  onProviderFilterChange,
  onStatusFilterChange,
  onLoadMore,
  loading
}) => {
  // Handle both array and paginated response formats
  const activitiesList = Array.isArray(activities) ? activities : activities.items;
  const nextCursor = Array.isArray(activities) ? null : activities.nextCursor;
  const hasMore = Array.isArray(activities) ? false : activities.hasMore;
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'SYNCED':
        return 'text-green-600 bg-green-50';
      case 'FAILED':
        return 'text-red-600 bg-red-50';
      case 'PENDING':
        return 'text-yellow-600 bg-yellow-50';
      case 'IN_PROGRESS':
        return 'text-blue-600 bg-blue-50';
      case 'RETRY_PENDING':
        return 'text-orange-600 bg-orange-50';
      case 'DEAD_LETTER':
        return 'text-gray-600 bg-gray-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'SYNCED':
        return '✓';
      case 'FAILED':
        return '✕';
      case 'PENDING':
        return '○';
      case 'IN_PROGRESS':
        return '⟳';
      case 'RETRY_PENDING':
        return '↻';
      case 'DEAD_LETTER':
        return '⊘';
      default:
        return '?';
    }
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

  const filteredActivities = activitiesList.filter((a: SyncActivity) => {
    if (providerFilter && a.provider !== providerFilter) return false;
    if (statusFilter && a.status !== statusFilter) return false;
    return true;
  });

  const uniqueProviders = Array.from(new Set(activitiesList.map((a: SyncActivity) => a.provider)));

  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold">Sync Activity</h3>
        <div className="flex gap-2">
          {onProviderFilterChange && (
            <select
              value={providerFilter || 'all'}
              onChange={(e) => onProviderFilterChange(e.target.value === 'all' ? null : e.target.value)}
              className="text-sm border rounded px-2 py-1"
            >
              <option value="all">All Providers</option>
              {uniqueProviders.map(provider => (
                <option key={provider} value={provider}>{provider}</option>
              ))}
            </select>
          )}
          {onStatusFilterChange && (
            <select
              value={statusFilter || 'all'}
              onChange={(e) => onStatusFilterChange(e.target.value === 'all' ? null : e.target.value)}
              className="text-sm border rounded px-2 py-1"
            >
              <option value="all">All Statuses</option>
              <option value="SYNCED">Synced</option>
              <option value="FAILED">Failed</option>
              <option value="RETRY_PENDING">Retry Pending</option>
              <option value="DEAD_LETTER">Dead Letter</option>
            </select>
          )}
        </div>
      </div>

      {filteredActivities.length === 0 ? (
        <div className="text-center text-gray-500 py-4">
          No sync activity found
        </div>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {filteredActivities.map((activity: SyncActivity) => (
            <div
              key={activity.id}
              className="flex items-center justify-between p-3 rounded border hover:bg-gray-50"
            >
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${getStatusColor(activity.status)}`}>
                  {getStatusIcon(activity.status)}
                </div>
                <div>
                  <div className="font-medium">{activity.provider}</div>
                  <div className="text-sm text-gray-600">
                    Execution #{activity.executionId.slice(-6)}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className={`text-sm font-medium ${getStatusColor(activity.status).split(' ')[0]}`}>
                  {activity.status}
                </div>
                {activity.attemptCount && activity.maxAttempts && (
                  <div className="text-xs text-gray-500">
                    Attempt {activity.attemptCount}/{activity.maxAttempts}
                  </div>
                )}
                {activity.nextAttemptAt && (
                  <div className="text-xs text-blue-600">
                    Retry: {formatTime(activity.nextAttemptAt)}
                  </div>
                )}
                {activity.cooldownUntil && (
                  <div className="text-xs text-blue-700">
                    Cooldown until {formatTime(activity.cooldownUntil)}
                    {activity.cooldownReason && ` (${activity.cooldownReason})`}
                  </div>
                )}
                {activity.error && !activity.cooldownUntil && (
                  <div className="text-xs text-red-600 truncate max-w-xs">
                    {activity.error}
                  </div>
                )}
                <div className="text-xs text-gray-500">
                  {formatTime(activity.lastSyncedAt || activity.createdAt)}
                </div>
              </div>
            </div>
          ))}
          {hasMore && onLoadMore && nextCursor && (
            <button
              onClick={() => onLoadMore(nextCursor)}
              disabled={loading}
              className="w-full py-2 text-sm text-blue-600 hover:text-blue-800 disabled:opacity-50"
            >
              {loading ? 'Loading...' : 'Load More'}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default IntegrationSyncActivityFeed;
