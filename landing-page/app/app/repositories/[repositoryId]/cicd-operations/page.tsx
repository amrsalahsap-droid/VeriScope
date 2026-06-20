"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertCircle, CheckCircle, Clock, RefreshCw, XCircle, Activity, AlertTriangle, FileText, Settings } from "lucide-react";

interface HealthCheck {
  name: string;
  status: "healthy" | "degraded" | "critical";
  message: string;
}

interface Alert {
  id: string;
  alert_type: string;
  severity: "INFO" | "WARNING" | "HIGH" | "CRITICAL";
  title: string;
  message: string;
  recommended_action: string | null;
  created_at: string;
  resolved_at: string | null;
}

interface DeadLetterJob {
  id: string;
  pipeline_run_id: string;
  repository_id: string;
  status: string;
  last_error: string;
  last_error_type: string;
  attempt_count: number;
  created_at: string;
}

interface WebhookEvent {
  id: string;
  github_delivery_id: string;
  event_type: string;
  processing_status: string;
  signature_valid: boolean;
  error_message: string | null;
  created_at: string;
}

interface AuditEvent {
  id: string;
  event_type: string;
  repository_id: string | null;
  metadata_json: Record<string, any>;
  created_at: string;
}

interface Metrics {
  pipeline_runs_total: number;
  pipeline_runs_completed: number;
  pipeline_runs_failed: number;
  jobs_total: number;
  jobs_completed: number;
  jobs_failed: number;
  jobs_dead_letter: number;
  avg_processing_time_seconds: number;
  github_publishing_success_rate: number;
  artifact_downloads: number;
  artifact_failures: number;
  ci_token_rejections: number;
}

export default function CICDOperationsPage() {
  const params = useParams();
  const repositoryId = params.repositoryId as string;
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<{ overall_status: string; checks: HealthCheck[] } | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [deadLetterJobs, setDeadLetterJobs] = useState<DeadLetterJob[]>([]);
  const [webhookEvents, setWebhookEvents] = useState<WebhookEvent[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchData = async () => {
    setLoading(true);
    try {
      const headers = {
        "Content-Type": "application/json",
      };

      // Fetch health
      const healthRes = await fetch(`${apiUrl}/api/repositories/${repositoryId}/cicd/health`, { headers });
      if (healthRes.ok) {
        const healthData = await healthRes.json();
        setHealth(healthData);
      }

      // Fetch metrics
      const metricsRes = await fetch(`${apiUrl}/api/repositories/${repositoryId}/cicd/metrics`, { headers });
      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setMetrics(metricsData);
      }

      // Fetch alerts
      const alertsRes = await fetch(`${apiUrl}/api/repositories/${repositoryId}/cicd/alerts`, { headers });
      if (alertsRes.ok) {
        const alertsData = await alertsRes.json();
        setAlerts(alertsData.alerts || []);
      }

      // Fetch dead-letter jobs
      const deadLetterRes = await fetch(`${apiUrl}/api/repositories/${repositoryId}/cicd/pipeline-jobs/dead-letter`, { headers });
      if (deadLetterRes.ok) {
        const deadLetterData = await deadLetterRes.json();
        setDeadLetterJobs(deadLetterData.jobs || []);
      }

      // Fetch webhook events
      const webhookRes = await fetch(`${apiUrl}/api/repositories/${repositoryId}/cicd/github/webhook-events`, { headers });
      if (webhookRes.ok) {
        const webhookData = await webhookRes.json();
        setWebhookEvents(webhookData.events || []);
      }

      // Fetch audit events
      const auditRes = await fetch(`${apiUrl}/api/repositories/${repositoryId}/cicd/audit`, { headers });
      if (auditRes.ok) {
        const auditData = await auditRes.json();
        setAuditEvents(auditData.events || []);
      }
    } catch (error) {
      console.error("Failed to fetch CI/CD data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [repositoryId, apiUrl]);

  const handleRetryJob = async (jobId: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/repositories/${repositoryId}/cicd/pipeline-jobs/${jobId}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error("Failed to retry job:", error);
    }
  };

  const handleCancelJob = async (jobId: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/repositories/${repositoryId}/cicd/pipeline-jobs/${jobId}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error("Failed to cancel job:", error);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return "bg-red-500";
      case "HIGH":
        return "bg-orange-500";
      case "WARNING":
        return "bg-yellow-500";
      case "INFO":
        return "bg-blue-500";
      default:
        return "bg-gray-500";
    }
  };

  const getHealthIcon = (status: string) => {
    switch (status) {
      case "healthy":
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case "degraded":
        return <AlertTriangle className="h-5 w-5 text-yellow-500" />;
      case "critical":
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <Clock className="h-5 w-5 text-gray-500" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">CI/CD Operations</h1>
          <p className="text-gray-500 mt-1">Monitor and manage CI/CD pipeline health and operations</p>
        </div>
        <Button onClick={fetchData} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Health Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Health Summary
          </CardTitle>
          <CardDescription>Overall CI/CD integration health status</CardDescription>
        </CardHeader>
        <CardContent>
          {health ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                {getHealthIcon(health.overall_status)}
                <span className="text-lg font-semibold capitalize">{health.overall_status}</span>
              </div>
              <div className="grid gap-3">
                {health.checks.map((check, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      {getHealthIcon(check.status)}
                      <div>
                        <div className="font-medium">{check.name}</div>
                        <div className="text-sm text-gray-500">{check.message}</div>
                      </div>
                    </div>
                    <Badge variant={check.status === "healthy" ? "default" : "destructive"}>
                      {check.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-gray-500">No health data available</div>
          )}
        </CardContent>
      </Card>

      {/* Pipeline Metrics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Pipeline Metrics
          </CardTitle>
          <CardDescription>Key performance metrics for CI/CD operations</CardDescription>
        </CardHeader>
        <CardContent>
          {metrics ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-blue-50 rounded-lg">
                <div className="text-2xl font-bold text-blue-600">{metrics.pipeline_runs_total}</div>
                <div className="text-sm text-gray-600">Total Pipeline Runs</div>
              </div>
              <div className="p-4 bg-green-50 rounded-lg">
                <div className="text-2xl font-bold text-green-600">{metrics.pipeline_runs_completed}</div>
                <div className="text-sm text-gray-600">Completed</div>
              </div>
              <div className="p-4 bg-red-50 rounded-lg">
                <div className="text-2xl font-bold text-red-600">{metrics.pipeline_runs_failed}</div>
                <div className="text-sm text-gray-600">Failed</div>
              </div>
              <div className="p-4 bg-purple-50 rounded-lg">
                <div className="text-2xl font-bold text-purple-600">{metrics.avg_processing_time_seconds.toFixed(1)}s</div>
                <div className="text-sm text-gray-600">Avg Processing Time</div>
              </div>
              <div className="p-4 bg-yellow-50 rounded-lg">
                <div className="text-2xl font-bold text-yellow-600">{metrics.jobs_dead_letter}</div>
                <div className="text-sm text-gray-600">Dead-Letter Jobs</div>
              </div>
              <div className="p-4 bg-indigo-50 rounded-lg">
                <div className="text-2xl font-bold text-indigo-600">{(metrics.github_publishing_success_rate * 100).toFixed(0)}%</div>
                <div className="text-sm text-gray-600">GitHub Success Rate</div>
              </div>
              <div className="p-4 bg-teal-50 rounded-lg">
                <div className="text-2xl font-bold text-teal-600">{metrics.artifact_downloads}</div>
                <div className="text-sm text-gray-600">Artifact Downloads</div>
              </div>
              <div className="p-4 bg-orange-50 rounded-lg">
                <div className="text-2xl font-bold text-orange-600">{metrics.ci_token_rejections}</div>
                <div className="text-sm text-gray-600">CI Token Rejections</div>
              </div>
            </div>
          ) : (
            <div className="text-gray-500">No metrics data available</div>
          )}
        </CardContent>
      </Card>

      {/* Alerts */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            Active Alerts
          </CardTitle>
          <CardDescription>Operational alerts requiring attention</CardDescription>
        </CardHeader>
        <CardContent>
          {alerts.length > 0 ? (
            <div className="space-y-3">
              {alerts.map((alert) => (
                <div key={alert.id} className="p-4 border rounded-lg">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Badge className={getSeverityColor(alert.severity)}>{alert.severity}</Badge>
                      <span className="font-medium">{alert.title}</span>
                    </div>
                    <span className="text-sm text-gray-500">
                      {new Date(alert.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">{alert.message}</p>
                  {alert.recommended_action && (
                    <p className="text-sm text-blue-600">
                      <strong>Action:</strong> {alert.recommended_action}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-500">No active alerts</div>
          )}
        </CardContent>
      </Card>

      {/* Dead-Letter Jobs */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <XCircle className="h-5 w-5" />
            Dead-Letter Jobs
          </CardTitle>
          <CardDescription>Failed jobs requiring manual intervention</CardDescription>
        </CardHeader>
        <CardContent>
          {deadLetterJobs.length > 0 ? (
            <div className="space-y-3">
              {deadLetterJobs.map((job) => (
                <div key={job.id} className="p-4 border rounded-lg">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-medium">{job.id.slice(0, 8)}...</div>
                      <div className="text-sm text-gray-500">
                        Attempt {job.attempt_count} • {new Date(job.created_at).toLocaleString()}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => handleRetryJob(job.id)}>
                        <RefreshCw className="h-4 w-4 mr-1" />
                        Retry
                      </Button>
                      <Button size="sm" variant="destructive" onClick={() => handleCancelJob(job.id)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                  <div className="text-sm text-red-600 mb-1">
                    <strong>Error:</strong> {job.last_error_type}
                  </div>
                  <p className="text-sm text-gray-600">{job.last_error}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-500">No dead-letter jobs</div>
          )}
        </CardContent>
      </Card>

      {/* Webhook Diagnostics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Webhook Diagnostics
          </CardTitle>
          <CardDescription>Recent GitHub webhook delivery events</CardDescription>
        </CardHeader>
        <CardContent>
          {webhookEvents.length > 0 ? (
            <div className="space-y-3">
              {webhookEvents.map((event) => (
                <div key={event.id} className="p-4 border rounded-lg">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-medium">{event.event_type}</div>
                      <div className="text-sm text-gray-500">
                        {event.github_delivery_id} • {new Date(event.created_at).toLocaleString()}
                      </div>
                    </div>
                    <Badge variant={event.signature_valid ? "default" : "destructive"}>
                      {event.signature_valid ? "Valid" : "Invalid"}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={event.processing_status === "processed" ? "default" : "destructive"}>
                      {event.processing_status}
                    </Badge>
                    {event.error_message && (
                      <span className="text-sm text-red-600">{event.error_message}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-500">No webhook events</div>
          )}
        </CardContent>
      </Card>

      {/* Audit Events */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Audit Trail
          </CardTitle>
          <CardDescription>CI/CD action audit log (sensitive data redacted)</CardDescription>
        </CardHeader>
        <CardContent>
          {auditEvents.length > 0 ? (
            <div className="space-y-3">
              {auditEvents.map((event) => (
                <div key={event.id} className="p-4 border rounded-lg">
                  <div className="flex items-start justify-between mb-2">
                    <div className="font-medium">{event.event_type}</div>
                    <span className="text-sm text-gray-500">
                      {new Date(event.created_at).toLocaleString()}
                    </span>
                  </div>
                  <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                    {JSON.stringify(event.metadata_json, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-500">No audit events</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
