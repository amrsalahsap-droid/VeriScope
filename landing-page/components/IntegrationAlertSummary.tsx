/**
 * IntegrationAlertSummary Component
 * 
 * Displays integration alert states including:
 * - HIGH_FAILURE_RATE
 * - DEAD_LETTER_PRESENT
 * - NO_RECENT_SUCCESS
 * - SYNC_BACKLOG_GROWING
 * - PROVIDER_COOLDOWN_ACTIVE
 */

import React from 'react';

interface Alert {
  code: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  message: string;
}

interface IntegrationAlertSummaryProps {
  alerts: Alert[];
}

const IntegrationAlertSummary: React.FC<IntegrationAlertSummaryProps> = ({
  alerts
}) => {
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'HIGH':
        return 'bg-red-50 border-red-200 text-red-800';
      case 'MEDIUM':
        return 'bg-yellow-50 border-yellow-200 text-yellow-800';
      case 'LOW':
        return 'bg-blue-50 border-blue-200 text-blue-800';
      default:
        return 'bg-gray-50 border-gray-200 text-gray-800';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'HIGH':
        return '⚠';
      case 'MEDIUM':
        return '⚡';
      case 'LOW':
        return 'ℹ';
      default:
        return '•';
    }
  };

  const getAlertTitle = (code: string) => {
    switch (code) {
      case 'HIGH_FAILURE_RATE':
        return 'High Failure Rate';
      case 'DEAD_LETTER_PRESENT':
        return 'Dead Letter Present';
      case 'NO_RECENT_SUCCESS':
        return 'No Recent Success';
      case 'SYNC_BACKLOG_GROWING':
        return 'Sync Backlog Growing';
      case 'PROVIDER_COOLDOWN_ACTIVE':
        return 'Provider Cooldown Active';
      default:
        return code;
    }
  };

  if (alerts.length === 0) {
    return (
      <div className="border rounded-lg p-4 bg-white shadow-sm">
        <h3 className="text-lg font-semibold mb-3">Alert Status</h3>
        <div className="text-center text-green-600 py-4">
          <div className="text-2xl mb-2">✓</div>
          <div>No active alerts</div>
        </div>
      </div>
    );
  }

  const highAlerts = alerts.filter(a => a.severity === 'HIGH');
  const mediumAlerts = alerts.filter(a => a.severity === 'MEDIUM');
  const lowAlerts = alerts.filter(a => a.severity === 'LOW');

  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm">
      <h3 className="text-lg font-semibold mb-3">Alert Status</h3>
      
      <div className="space-y-3">
        {highAlerts.length > 0 && (
          <div>
            <div className="text-sm font-medium text-red-600 mb-2">
              High Severity ({highAlerts.length})
            </div>
            {highAlerts.map((alert, index) => (
              <div
                key={`${alert.code}-${index}`}
                className={`p-3 rounded border mb-2 ${getSeverityColor(alert.severity)}`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-lg">{getSeverityIcon(alert.severity)}</span>
                  <div>
                    <div className="font-medium">{getAlertTitle(alert.code)}</div>
                    <div className="text-sm mt-1">{alert.message}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {mediumAlerts.length > 0 && (
          <div>
            <div className="text-sm font-medium text-yellow-600 mb-2">
              Medium Severity ({mediumAlerts.length})
            </div>
            {mediumAlerts.map((alert, index) => (
              <div
                key={`${alert.code}-${index}`}
                className={`p-3 rounded border mb-2 ${getSeverityColor(alert.severity)}`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-lg">{getSeverityIcon(alert.severity)}</span>
                  <div>
                    <div className="font-medium">{getAlertTitle(alert.code)}</div>
                    <div className="text-sm mt-1">{alert.message}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {lowAlerts.length > 0 && (
          <div>
            <div className="text-sm font-medium text-blue-600 mb-2">
              Low Severity ({lowAlerts.length})
            </div>
            {lowAlerts.map((alert, index) => (
              <div
                key={`${alert.code}-${index}`}
                className={`p-3 rounded border mb-2 ${getSeverityColor(alert.severity)}`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-lg">{getSeverityIcon(alert.severity)}</span>
                  <div>
                    <div className="font-medium">{getAlertTitle(alert.code)}</div>
                    <div className="text-sm mt-1">{alert.message}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default IntegrationAlertSummary;
