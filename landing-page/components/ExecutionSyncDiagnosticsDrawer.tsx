/**
 * ExecutionSyncDiagnosticsDrawer Component
 * 
 * Expandable drawer displaying sync diagnostics:
 * - Request payload
 * - Response payload
 * - Error
 * - Provider
 * - Execution
 * - Timestamp
 * 
 * Credentials and sensitive data are redacted before display.
 */

import React, { useState } from 'react';

interface DiagnosticsData {
  provider: string;
  executionId: string;
  requestPayload: any;
  responsePayload: any;
  error: string | null;
  timestamp: string;
}

interface ExecutionSyncDiagnosticsDrawerProps {
  diagnostics: DiagnosticsData | null;
  isOpen: boolean;
  onClose: () => void;
}

// Sensitive keys to redact from payloads
const REDACTED_KEYS = new Set([
  'password', 'api_key', 'apiKey', 'token', 'client_secret', 'clientSecret',
  'access_token', 'accessToken', 'refresh_token', 'refreshToken',
  'authorization', 'Authorization', 'secret', 'private_key', 'privateKey'
]);

/**
 * Recursively redact sensitive keys from a data structure
 */
function redactSensitiveData(data: any, replacement: string = '***REDACTED***'): any {
  if (typeof data !== 'object' || data === null) {
    return data;
  }

  if (Array.isArray(data)) {
    return data.map(item => redactSensitiveData(item, replacement));
  }

  const redacted: any = {};
  for (const [key, value] of Object.entries(data)) {
    if (REDACTED_KEYS.has(key)) {
      redacted[key] = replacement;
    } else if (typeof value === 'object' && value !== null) {
      redacted[key] = redactSensitiveData(value, replacement);
    } else {
      redacted[key] = value;
    }
  }

  return redacted;
}

const ExecutionSyncDiagnosticsDrawer: React.FC<ExecutionSyncDiagnosticsDrawerProps> = ({
  diagnostics,
  isOpen,
  onClose
}) => {
  if (!isOpen || !diagnostics) return null;

  // Redact sensitive data from payloads before rendering
  const redactedRequestPayload = redactSensitiveData(diagnostics.requestPayload);
  const redactedResponsePayload = redactSensitiveData(diagnostics.responsePayload);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold">Sync Diagnostics</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="p-4 overflow-y-auto max-h-[calc(90vh-60px)]">
          <div className="space-y-4">
            {/* Summary */}
            <div className="bg-gray-50 p-3 rounded">
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="font-medium text-gray-600">Provider:</span>
                  <span className="ml-2">{diagnostics.provider}</span>
                </div>
                <div>
                  <span className="font-medium text-gray-600">Execution ID:</span>
                  <span className="ml-2">{diagnostics.executionId}</span>
                </div>
                <div>
                  <span className="font-medium text-gray-600">Timestamp:</span>
                  <span className="ml-2">{new Date(diagnostics.timestamp).toLocaleString()}</span>
                </div>
                <div>
                  <span className="font-medium text-gray-600">Status:</span>
                  <span className={`ml-2 ${diagnostics.error ? 'text-red-600' : 'text-green-600'}`}>
                    {diagnostics.error ? 'FAILED' : 'SUCCESS'}
                  </span>
                </div>
              </div>
            </div>

            {/* Error */}
            {diagnostics.error && (
              <div className="bg-red-50 border border-red-200 p-3 rounded">
                <h4 className="font-medium text-red-800 mb-2">Error</h4>
                <pre className="text-sm text-red-700 whitespace-pre-wrap break-all">
                  {diagnostics.error}
                </pre>
              </div>
            )}

            {/* Request Payload */}
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Request Payload</h4>
              <div className="bg-gray-900 text-green-400 p-3 rounded overflow-x-auto">
                <pre className="text-xs whitespace-pre-wrap">
                  {JSON.stringify(redactedRequestPayload, null, 2)}
                </pre>
              </div>
            </div>

            {/* Response Payload */}
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Response Payload</h4>
              <div className="bg-gray-900 text-blue-400 p-3 rounded overflow-x-auto">
                <pre className="text-xs whitespace-pre-wrap">
                  {JSON.stringify(redactedResponsePayload, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExecutionSyncDiagnosticsDrawer;
