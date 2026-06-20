"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { 
  ArrowLeft, 
  Settings, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Plug, 
  Unplug,
  RefreshCw,
  Loader2,
  AlertCircle
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import Link from "next/link";
import ProviderCapabilityCard from "@/components/ProviderCapabilityCard";
import IntegrationHealthPanel from "@/components/IntegrationHealthPanel";
import IntegrationSyncActivityFeed from "@/components/IntegrationSyncActivityFeed";

export const dynamic = "force-dynamic";

interface IntegrationConnection {
  provider: string;
  is_connected: boolean;
  last_synced_at: string | null;
  config: {
    base_url?: string;
    username?: string;
  } | null;
}

interface ProviderCapability {
  provider: string;
  supportsExecutionSync: boolean;
  supportsBidirectionalSync: boolean;
  supportsTestImport: boolean;
  supportsWorkItemImport: boolean;
  supportsWebhooks: boolean;
}

interface HealthStatus {
  provider: string;
  health: 'HEALTHY' | 'DISCONNECTED' | 'CONFIGURATION_REQUIRED' | 'AUTHENTICATION_FAILED' | 'SYNC_FAILURES_PRESENT';
  isConnected: boolean;
  lastSyncStatus: string | null;
  lastSyncError: string | null;
  missingConfiguration: string | null;
}

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
}

const PROVIDERS = [
  {
    id: "JIRA",
    name: "Jira",
    description: "Import work items and acceptance criteria from Jira",
    icon: "🔵",
    implemented: true,
    configFields: [
      { name: "base_url", label: "Base URL", placeholder: "https://your-domain.atlassian.net", type: "url" },
      { name: "username", label: "Username", placeholder: "your-email@company.com", type: "text" },
      { name: "api_token", label: "API Token", placeholder: "Your Jira API token", type: "password" }
    ]
  },
  {
    id: "AZURE_DEVOPS",
    name: "Azure DevOps",
    description: "Import work items from Azure Boards",
    icon: "🔷",
    implemented: true,
    configFields: [
      { name: "organization_url", label: "Organization URL", placeholder: "https://dev.azure.com/your-org", type: "url" },
      { name: "project", label: "Project", placeholder: "Your project name", type: "text" },
      { name: "pat_token", label: "Personal Access Token", placeholder: "Your PAT token", type: "password" }
    ]
  },
  {
    id: "TESTRAIL",
    name: "TestRail",
    description: "Import managed test cases from TestRail",
    icon: "🟢",
    implemented: true,
    configFields: [
      { name: "base_url", label: "Base URL", placeholder: "https://your-instance.testrail.io", type: "url" },
      { name: "username", label: "Username", placeholder: "your-email@company.com", type: "text" },
      { name: "api_key", label: "API Key", placeholder: "Your TestRail API key", type: "password" }
    ]
  },
  {
    id: "XRAY",
    name: "Xray",
    description: "Import test cases from Xray (Jira plugin)",
    icon: "🟣",
    implemented: false,
    configFields: []
  },
  {
    id: "ZEPHYR",
    name: "Zephyr",
    description: "Import test cases from Zephyr (Jira plugin)",
    icon: "🟡",
    implemented: false,
    configFields: []
  },
  {
    id: "MANUAL_CSV",
    name: "CSV Import",
    description: "Import manual test cases from CSV files",
    icon: "📄",
    implemented: true,
    configFields: []
  }
];

export default function IntegrationsPage() {
  const params = useParams();
  const repositoryId = params.repositoryId as string;

  const [connections, setConnections] = useState<IntegrationConnection[]>([]);
  const [providerCapabilities, setProviderCapabilities] = useState<ProviderCapability[]>([]);
  const [healthStatuses, setHealthStatuses] = useState<HealthStatus[]>([]);
  const [syncActivities, setSyncActivities] = useState<SyncActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [testingConnection, setTestingConnection] = useState<string | null>(null);
  const [connectingProvider, setConnectingProvider] = useState<string | null>(null);
  const [retryingProvider, setRetryingProvider] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<any>(null);
  const [formData, setFormData] = useState<Record<string, string>>({});

  const loadIntegrations = async () => {
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/integrations`);
      if (response.ok) {
        const data = await response.json();
        setConnections(data);
      }
    } catch (error) {
      console.error("Failed to load integrations:", error);
      toast.error("Failed to load integrations");
    } finally {
      setLoading(false);
    }
  };

  const loadCapabilities = async () => {
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/integrations/providers`);
      if (response.ok) {
        const data = await response.json();
        setProviderCapabilities(data);
      }
    } catch (error) {
      // Non-blocking: capabilities are decorative, not critical
      console.warn("Failed to load provider capabilities:", error);
    }
  };

  const loadHealth = async () => {
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/integrations/health`);
      if (response.ok) {
        const data = await response.json();
        setHealthStatuses(data);
      }
    } catch (error) {
      console.warn("Failed to load integration health:", error);
    }
  };

  const loadSyncActivity = async () => {
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/integrations/sync-activity?limit=20`);
      if (response.ok) {
        const data = await response.json();
        setSyncActivities(data);
      }
    } catch (error) {
      console.warn("Failed to load sync activity:", error);
    }
  };

  useEffect(() => {
    loadIntegrations();
    loadCapabilities();
    loadHealth();
    loadSyncActivity();
  }, [repositoryId]);

  const handleTestConnection = async (provider: string) => {
    setTestingConnection(provider);
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/integrations/${provider}/test`, {
        method: "POST"
      });
      const result = await response.json();
      
      if (result.is_valid) {
        toast.success(`${provider} connection successful`);
      } else {
        toast.error(`${provider} connection failed: ${result.message}`);
      }
    } catch (error) {
      toast.error(`Failed to test ${provider} connection`);
    } finally {
      setTestingConnection(null);
    }
  };

  const handleConnect = async (provider: string) => {
    setConnectingProvider(provider);
    try {
      const providerConfig = PROVIDERS.find(p => p.id === provider);
      if (!providerConfig) return;

      const config: Record<string, string> = {};
      providerConfig.configFields.forEach(field => {
        config[field.name] = formData[field.name];
      });

      const response = await fetch(`/api/repositories/${repositoryId}/integrations/${provider}/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config)
      });

      if (response.ok) {
        toast.success(`${provider} connected successfully`);
        setShowModal(false);
        setFormData({});
        loadIntegrations();
      } else {
        const error = await response.json();
        toast.error(`Failed to connect ${provider}: ${error.detail}`);
      }
    } catch (error) {
      toast.error(`Failed to connect ${provider}`);
    } finally {
      setConnectingProvider(null);
    }
  };

  const handleDisconnect = async (provider: string) => {
    if (!confirm(`Are you sure you want to disconnect ${provider}?`)) return;
    
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/integrations/${provider}/disconnect`, {
        method: "POST"
      });

      if (response.ok) {
        toast.success(`${provider} disconnected`);
        loadIntegrations();
      } else {
        toast.error(`Failed to disconnect ${provider}`);
      }
    } catch (error) {
      toast.error(`Failed to disconnect ${provider}`);
    }
  };

  const handleRetryFailedSyncs = async (provider: string) => {
    if (!confirm(`Retry all failed ${provider} syncs?`)) return;
    
    setRetryingProvider(provider);
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/integrations/retry-failed-syncs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider })
      });

      if (response.ok) {
        const result = await response.json();
        toast.success(`Retried ${result.retriedCount} ${provider} syncs${result.failedCount > 0 ? `, ${result.failedCount} failed` : ''}`);
        loadSyncActivity();
        loadHealth();
      } else {
        toast.error(`Failed to retry ${provider} syncs`);
      }
    } catch (error) {
      toast.error(`Failed to retry ${provider} syncs`);
    } finally {
      setRetryingProvider(null);
    }
  };

  const openConnectModal = (provider: any) => {
    setSelectedProvider(provider);
    setFormData({});
    setShowModal(true);
  };

  const getConnection = (provider: string) => {
    return connections.find(c => c.provider === provider);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href={`/app/repositories/${repositoryId}`}>
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Integration Settings
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              Connect external tools to enrich recommendations with work items and test cases
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-6">
        {PROVIDERS.map((provider) => {
          const connection = getConnection(provider.id);
          const isImplemented = provider.implemented;
          
          return (
            <div
              key={provider.id}
              className="bg-zinc-900/10 border border-zinc-900 rounded-xl p-6 space-y-4"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <div className="text-3xl">{provider.icon}</div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-semibold text-white">
                        {provider.name}
                      </h3>
                      {!isImplemented && (
                        <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-800">
                          Coming Soon
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-zinc-400 mt-1">
                      {provider.description}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  {connection?.is_connected ? (
                    <>
                      <CheckCircle className="w-5 h-5 text-green-400" />
                      <span className="text-sm text-green-400">Connected</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-5 h-5 text-zinc-500" />
                      <span className="text-sm text-zinc-500">Not Connected</span>
                    </>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-6 text-sm text-zinc-400">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  <span>Last sync: {formatDate(connection?.last_synced_at || null)}</span>
                </div>
                {connection?.config?.base_url && (
                  <div className="flex items-center gap-2">
                    <span>URL: {connection.config.base_url}</span>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-3 pt-2">
                {isImplemented ? (
                  <>
                    {connection?.is_connected ? (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleTestConnection(provider.id)}
                          disabled={testingConnection === provider.id}
                        >
                          {testingConnection === provider.id ? (
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          ) : (
                            <RefreshCw className="w-4 h-4 mr-2" />
                          )}
                          Test Connection
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDisconnect(provider.id)}
                        >
                          <Unplug className="w-4 h-4 mr-2" />
                          Disconnect
                        </Button>
                      </>
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => openConnectModal(provider)}
                      >
                        <Plug className="w-4 h-4 mr-2" />
                        Setup
                      </Button>
                    )}
                  </>
                ) : (
                  <Button variant="outline" size="sm" disabled>
                    <AlertCircle className="w-4 h-4 mr-2" />
                    Coming Soon
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Phase 7.4: Provider Capability Dashboard */}
      {providerCapabilities.length > 0 && (
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-white">Provider Capabilities</h2>
            <p className="text-sm text-zinc-400 mt-1">
              Detailed capability information for each provider
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {providerCapabilities.map((cap) => {
              const provider = PROVIDERS.find(p => p.id === cap.provider);
              if (!provider) return null;
              const connection = getConnection(cap.provider);
              return (
                <ProviderCapabilityCard
                  key={cap.provider}
                  provider={cap.provider}
                  providerName={provider.name}
                  isConnected={connection?.is_connected || false}
                  supportsExecutionSync={cap.supportsExecutionSync}
                  supportsTestImport={cap.supportsTestImport}
                  supportsWorkItemImport={cap.supportsWorkItemImport}
                  supportsWebhooks={cap.supportsWebhooks}
                  supportsBidirectionalSync={cap.supportsBidirectionalSync}
                  icon={provider.icon}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Phase 7.4: Integration Health Panel */}
      {healthStatuses.length > 0 && (
        <IntegrationHealthPanel 
          healthStatuses={healthStatuses}
          onRetryFailedSyncs={handleRetryFailedSyncs}
          retryingProvider={retryingProvider}
        />
      )}

      {/* Phase 7.4: Sync Activity Feed */}
      {syncActivities.length > 0 && (
        <IntegrationSyncActivityFeed
          activities={syncActivities}
          onProviderFilterChange={(provider) => {
            // Reload sync activity with filter
            const url = provider 
              ? `/api/repositories/${repositoryId}/integrations/sync-activity?provider=${provider}&limit=20`
              : `/api/repositories/${repositoryId}/integrations/sync-activity?limit=20`;
            fetch(url)
              .then(res => res.json())
              .then(data => setSyncActivities(data))
              .catch(err => console.warn("Failed to load filtered sync activity:", err));
          }}
        />
      )}

      {/* Provider Capability Matrix */}
      {providerCapabilities.length > 0 && (
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-white">Sync Capability Matrix</h2>
            <p className="text-sm text-zinc-400 mt-1">
              Which providers support execution result synchronization in the current phase.
            </p>
          </div>
          <div className="bg-zinc-900/10 border border-zinc-900 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left px-6 py-3 text-zinc-400 font-medium">Provider</th>
                  <th className="text-left px-6 py-3 text-zinc-400 font-medium">Execution Sync</th>
                  <th className="text-left px-6 py-3 text-zinc-400 font-medium">Bidirectional Sync</th>
                </tr>
              </thead>
              <tbody>
                {providerCapabilities.map((cap, idx) => (
                  <tr
                    key={cap.provider}
                    className={`border-b border-zinc-900 ${
                      idx === providerCapabilities.length - 1 ? "border-b-0" : ""
                    }`}
                  >
                    <td className="px-6 py-3 font-medium text-zinc-200">
                      {PROVIDERS.find(p => p.id === cap.provider)?.name || cap.provider}
                    </td>
                    <td className="px-6 py-3">
                      {cap.supportsExecutionSync ? (
                        <span className="inline-flex items-center gap-1.5 text-green-400 text-xs font-medium">
                          <CheckCircle className="w-3.5 h-3.5" />
                          Supported
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-zinc-500 text-xs font-medium">
                          {["XRAY", "ZEPHYR"].includes(cap.provider) ? (
                            <>
                              <Clock className="w-3.5 h-3.5" />
                              Planned
                            </>
                          ) : (
                            <>
                              <XCircle className="w-3.5 h-3.5" />
                              Not Supported
                            </>
                          )}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3">
                      <span className="inline-flex items-center gap-1.5 text-zinc-500 text-xs font-medium">
                        <XCircle className="w-3.5 h-3.5" />
                        Not Supported
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Connection Modal */}
      {showModal && selectedProvider && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 w-full max-w-md space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">
                Connect {selectedProvider.name}
              </h2>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowModal(false)}
              >
                <XCircle className="w-5 h-5" />
              </Button>
            </div>

            <div className="space-y-4">
              {selectedProvider.configFields.map((field: { name: string; label: string; placeholder: string; type: string }) => (
                <div key={field.name} className="space-y-2">
                  <label className="text-sm font-medium text-zinc-300">
                    {field.label}
                  </label>
                  <input
                    type={field.type}
                    placeholder={field.placeholder}
                    value={formData[field.name] || ""}
                    onChange={(e) => setFormData({ ...formData, [field.name]: e.target.value })}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                onClick={() => setShowModal(false)}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={() => handleConnect(selectedProvider.id)}
                disabled={connectingProvider === selectedProvider.id}
                className="flex-1"
              >
                {connectingProvider === selectedProvider.id ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Plug className="w-4 h-4 mr-2" />
                )}
                Connect
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
