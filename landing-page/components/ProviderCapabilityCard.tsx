/**
 * ProviderCapabilityCard Component
 * 
 * Displays provider capability information including:
 * - Provider name
 * - Connection status
 * - Execution sync support
 * - Test import support
 * - Work item import support
 * - Webhooks support
 * - Bidirectional sync support
 */

import React from 'react';

interface ProviderCapabilityCardProps {
  provider: string;
  providerName: string;
  isConnected: boolean;
  supportsExecutionSync: boolean;
  supportsTestImport: boolean;
  supportsWorkItemImport: boolean;
  supportsWebhooks: boolean;
  supportsBidirectionalSync: boolean;
  icon?: React.ReactNode;
}

const ProviderCapabilityCard: React.FC<ProviderCapabilityCardProps> = ({
  provider,
  providerName,
  isConnected,
  supportsExecutionSync,
  supportsTestImport,
  supportsWorkItemImport,
  supportsWebhooks,
  supportsBidirectionalSync,
  icon
}) => {
  const getStatusColor = (supported: boolean) => {
    return supported ? 'text-green-600' : 'text-gray-400';
  };

  const getStatusText = (supported: boolean) => {
    return supported ? 'Yes' : 'No';
  };

  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {icon && <div className="text-2xl">{icon}</div>}
          <h3 className="text-lg font-semibold">{providerName}</h3>
        </div>
        <div className={`px-2 py-1 rounded text-xs font-medium ${
          isConnected ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
        }`}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-600">Execution Sync</span>
          <span className={getStatusColor(supportsExecutionSync)}>
            {getStatusText(supportsExecutionSync)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Test Import</span>
          <span className={getStatusColor(supportsTestImport)}>
            {getStatusText(supportsTestImport)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Work Item Import</span>
          <span className={getStatusColor(supportsWorkItemImport)}>
            {getStatusText(supportsWorkItemImport)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Webhooks</span>
          <span className={getStatusColor(supportsWebhooks)}>
            {getStatusText(supportsWebhooks)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Bidirectional Sync</span>
          <span className={getStatusColor(supportsBidirectionalSync)}>
            {getStatusText(supportsBidirectionalSync)}
          </span>
        </div>
      </div>
    </div>
  );
};

export default ProviderCapabilityCard;
