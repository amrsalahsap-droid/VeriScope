"use client";

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Shield, AlertTriangle, CheckCircle, XCircle, Download, Settings, FileText, TrendingUp, Bell, BellRing, Filter, Check, X } from 'lucide-react';

interface OrganizationComplianceDashboard {
  total_repositories: number;
  repositories_with_policy: number;
  repositories_inheriting_org_default: number;
  repositories_with_overrides: number;
  repositories_with_drift: number;
  repositories_with_high_risk_drift: number;
  repositories_with_critical_risk_drift: number;
  repositories_using_each_preset: Record<string, number>;
  repositories_missing_required_artifact_policy: number;
  repositories_allowing_manual_override: number;
  repositories_not_ready_for_branch_protection: number;
  overall_compliance_score: number;
}

interface RepositoryCompliance {
  repository_id: string;
  repository_name: string;
  policy_source: string;
  current_preset: string | null;
  organization_default_preset: string | null;
  drift_detected: boolean;
  drift_risk_level: string;
  branch_protection_ready: boolean;
  manual_override_enabled: boolean;
  artifact_required: boolean;
  pr_comment_required: boolean;
  unknown_gate_fails: boolean;
  partial_gate_fails: boolean;
  compliance_score: number;
  compliance_status: string;
  recommended_action: string;
}

interface PolicyException {
  id: string;
  organization_id: string;
  repository_id: string;
  requested_by: string;
  approved_by: string | null;
  status: string;
  reason: string;
  exception_fields: string[];
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  decision_reason: string | null;
}

interface GovernanceReviewSnapshot {
  id: string;
  organization_id: string;
  created_at: string;
  created_by: string;
  total_repositories: number;
  compliance_score: number;
  critical_count: number;
  high_risk_count: number;
  drifted_count: number;
  compliant_count: number;
}

export default function OrganizationGovernancePage({ params }: { params: { organizationId: string } }) {
  const [dashboard, setDashboard] = useState<OrganizationComplianceDashboard | null>(null);
  const [repositories, setRepositories] = useState<RepositoryCompliance[]>([]);
  const [exceptions, setExceptions] = useState<PolicyException[]>([]);
  const [snapshots, setSnapshots] = useState<GovernanceReviewSnapshot[]>([]);

  // Remediation states
  const [remediationSummary, setRemediationSummary] = useState<any>({
    total: 0, pending_confirmation: 0, confirmed: 0, executed: 0, failed: 0, cancelled: 0
  });
  const [remediationActions, setRemediationActions] = useState<any[]>([]);
  const [remediationLoading, setRemediationLoading] = useState<boolean>(false);
  const [selectedAction, setSelectedAction] = useState<any>(null);
  const [confirmText, setConfirmText] = useState<string>("");
  
  // Bulk remediation states
  const [bulkRemediationType, setBulkRemediationType] = useState<string>("expired_role_cleanup");
  const [bulkRemediationReason, setBulkRemediationReason] = useState<string>("");
  const [bulkPreviewItems, setBulkPreviewItems] = useState<any[]>([]);
  const [bulkExecutionResults, setBulkExecutionResults] = useState<any[]>([]);
  const [bulkRemediationLoading, setBulkRemediationLoading] = useState<boolean>(false);
  const [showBulkRemediationConfirm, setShowBulkRemediationConfirm] = useState<boolean>(false);
  
  // Create manual remediation action states
  const [showCreateAction, setShowCreateAction] = useState<boolean>(false);
  const [createActionType, setCreateActionType] = useState<string>("REVOKE_ROLE");
  const [createActionTargetUserId, setCreateActionTargetUserId] = useState<string>("");
  const [createActionTargetRole, setCreateActionTargetRole] = useState<string>("");
  const [createActionTargetAssignmentId, setCreateActionTargetAssignmentId] = useState<string>("");
  const [createActionTargetExceptionId, setCreateActionTargetExceptionId] = useState<string>("");
  const [createActionTargetPolicyId, setCreateActionTargetPolicyId] = useState<string>("");
  const [createActionRepoId, setCreateActionRepoId] = useState<string>("");
  const [createActionConfirmationMessage, setCreateActionConfirmationMessage] = useState<string>("");
  const [createActionSourceType, setCreateActionSourceType] = useState<string>("MANUAL");
  const [createActionSourceId, setCreateActionSourceId] = useState<string>("");
  
  // Filter states for remediation action table
  const [filterRemediationStatus, setFilterRemediationStatus] = useState<string>("ALL");
  const [filterRemediationType, setFilterRemediationType] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);
  const [selectedRepositories, setSelectedRepositories] = useState<string[]>([]);
  const [bulkOperation, setBulkOperation] = useState<string>("APPLY_PRESET");
  const [bulkPreset, setBulkPreset] = useState<string>("STANDARD");
  const [bulkReason, setBulkReason] = useState<string>("");
  const [bulkPreview, setBulkPreview] = useState<any>(null);
  const [bulkResult, setBulkResult] = useState<any>(null);
  const [showBulkConfirm, setShowBulkConfirm] = useState(false);
  const [decisionReason, setDecisionReason] = useState<string>("");
  const [filterStatus, setFilterStatus] = useState<string>("ALL");
  const [filterDrift, setFilterDrift] = useState<string>("ALL");
  const [filterPreset, setFilterPreset] = useState<string>("ALL");
  const [filterRisk, setFilterRisk] = useState<string>("ALL");
  const [analytics, setAnalytics] = useState<any>(null);
  const [executiveSummary, setExecutiveSummary] = useState<any>(null);
  const [maturityScore, setMaturityScore] = useState<any>(null);
  const [complianceTrend, setComplianceTrend] = useState<any>(null);
  const [policyAdoption, setPolicyAdoption] = useState<any>(null);
  const [driftTrend, setDriftTrend] = useState<any>(null);
  const [exceptionAnalytics, setExceptionAnalytics] = useState<any>(null);
  const [riskHeatmap, setRiskHeatmap] = useState<any>([]);
  const [heatmapFilterRisk, setHeatmapFilterRisk] = useState<string>("ALL");
  const [heatmapFilterPreset, setHeatmapFilterPreset] = useState<string>("ALL");
  const [heatmapFilterDrift, setHeatmapFilterDrift] = useState<string>("ALL");
  const [heatmapFilterException, setHeatmapFilterException] = useState<string>("ALL");
  const [heatmapFilterBranch, setHeatmapFilterBranch] = useState<string>("ALL");
  
  // Access control state
  const [roleAssignments, setRoleAssignments] = useState<any[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [selectedRole, setSelectedRole] = useState<string>("");
  const [selectedScope, setSelectedScope] = useState<string>("WORKSPACE");
  const [selectedRepository, setSelectedRepository] = useState<string>("");
  const [roleExpiry, setRoleExpiry] = useState<string>("");
  const [roleReason, setRoleReason] = useState<string>("");
  const [effectivePermissions, setEffectivePermissions] = useState<any>(null);
  const [permissionCheckUser, setPermissionCheckUser] = useState<string>("");
  const [permissionCheckPermission, setPermissionCheckPermission] = useState<string>("");
  const [permissionCheckResult, setPermissionCheckResult] = useState<any>(null);
  const [filterRole, setFilterRole] = useState<string>("ALL");
  const [filterScope, setFilterScope] = useState<string>("ALL");
  const [filterActive, setFilterActive] = useState<boolean>(true);
  const [auditEvents, setAuditEvents] = useState<any[]>([]);
  
  // Notification state
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [highestSeverity, setHighestSeverity] = useState<string>("INFO");
  const [showNotifications, setShowNotifications] = useState(false);
  const [notificationFilterSeverity, setNotificationFilterSeverity] = useState<string>("ALL");
  const [notificationFilterType, setNotificationFilterType] = useState<string>("ALL");
  const [notificationFilterRead, setNotificationFilterRead] = useState<string>("ALL");
  const [notificationPreferences, setNotificationPreferences] = useState<any[]>([]);
  const [scanResults, setScanResults] = useState<any>(null);
  
  // Organization notifications state (admin view)
  const [organizationNotifications, setOrganizationNotifications] = useState<any[]>([]);
  const [showOrgNotifications, setShowOrgNotifications] = useState(false);
  const [orgNotificationFilterRecipient, setOrgNotificationFilterRecipient] = useState<string>("ALL");
  const [orgNotificationFilterSeverity, setOrgNotificationFilterSeverity] = useState<string>("ALL");
  const [orgNotificationFilterType, setOrgNotificationFilterType] = useState<string>("ALL");
  const [orgNotificationFilterStatus, setOrgNotificationFilterStatus] = useState<string>("ALL");
  const [canViewOrgNotifications, setCanViewOrgNotifications] = useState(false);

  // Security & Access Reviews state
  const [securityPosture, setSecurityPosture] = useState<any>(null);
  const [accessReviews, setAccessReviews] = useState<any[]>([]);
  const [selectedReview, setSelectedReview] = useState<any>(null);
  const [reviewItems, setReviewItems] = useState<any[]>([]);
  const [showCreateReview, setShowCreateReview] = useState(false);
  const [newReviewName, setNewReviewName] = useState<string>("");
  const [newReviewType, setNewReviewType] = useState<string>("QUARTERLY_ACCESS_REVIEW");
  const [newReviewPeriodStart, setNewReviewPeriodStart] = useState<string>("");
  const [newReviewPeriodEnd, setNewReviewPeriodEnd] = useState<string>("");
  const [securitySignals, setSecuritySignals] = useState<any>(null);
  const [evidencePack, setEvidencePack] = useState<any>(null);
  const [evidencePackType, setEvidencePackType] = useState<string>("EXECUTIVE");
  const [itemDecision, setItemDecision] = useState<string>("");
  const [itemDecisionReason, setItemDecisionReason] = useState<string>("");
  const [accessDenied, setAccessDenied] = useState<string | null>(null);

  useEffect(() => {
    loadGovernanceData();
  }, [params.organizationId]);

  const loadGovernanceData = async () => {
    setLoading(true);
    try {
      // Load compliance dashboard
      const dashboardResponse = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/compliance`);
      if (dashboardResponse.ok) {
        const dashboardData = await dashboardResponse.json();
        setDashboard(dashboardData);
      }

      // Load repositories
      const reposResponse = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/repositories`);
      if (reposResponse.ok) {
        const reposData = await reposResponse.json();
        setRepositories(reposData);
      }

      // Load remediation actions data
      loadRemediationData();

      // Load exceptions
      const exceptionsResponse = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/exceptions`);
      if (exceptionsResponse.ok) {
        const exceptionsData = await exceptionsResponse.json();
        setExceptions(exceptionsData);
      }

      // Load review snapshots
      const snapshotsResponse = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/review-snapshots`);
      if (snapshotsResponse.ok) {
        const snapshotsData = await snapshotsResponse.json();
        setSnapshots(snapshotsData);
      }
      
      // Load analytics data
      const analyticsResponse = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/analytics`);
      if (analyticsResponse.ok) {
        const analyticsData = await analyticsResponse.json();
        setAnalytics(analyticsData);
        setComplianceTrend(analyticsData.compliance_trend);
        setPolicyAdoption(analyticsData.policy_adoption);
        setDriftTrend(analyticsData.drift_trend);
        setExceptionAnalytics(analyticsData.exception_analytics);
        setRiskHeatmap(analyticsData.risk_heatmap);
        setMaturityScore(analyticsData.maturity_score);
      }
      
      // Load executive summary
      const summaryResponse = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/executive-summary`);
      if (summaryResponse.ok) {
        const summaryData = await summaryResponse.json();
        setExecutiveSummary(summaryData);
      }
      
      // Load role assignments
      loadRoleAssignments();
      
      // Load audit events
      loadAuditEvents();
      
      // Load notifications
      loadNotifications();
      
      // Load notification preferences
      loadNotificationPreferences();
      
      // Check if user can view organization notifications
      checkOrgNotificationPermission();
      
      // Load organization notifications if authorized
      loadOrganizationNotifications();
      
      // Load security posture
      loadSecurityPosture();
      
      // Load access reviews
      loadAccessReviews();
      
      // Load security signals
      loadSecuritySignals();
    } catch (err) {
      console.error('Failed to load governance data:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadRemediationData = async () => {
    try {
      setRemediationLoading(true);
      const summaryRes = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/remediation/summary`);
      if (summaryRes.ok) {
        const summaryData = await summaryRes.json();
        setRemediationSummary(summaryData);
      }
      
      const actionsRes = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/remediation/actions`);
      if (actionsRes.ok) {
        const actionsData = await actionsRes.json();
        setRemediationActions(actionsData);
      }
    } catch (err) {
      console.error("Failed to load remediation data:", err);
    } finally {
      setRemediationLoading(false);
    }
  };

  const handleCreateRemediationAction = async (payload: any) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/remediation/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (response.ok) {
        setShowCreateAction(false);
        loadRemediationData();
        // Reset creation inputs
        setCreateActionTargetUserId("");
        setCreateActionTargetRole("");
        setCreateActionTargetAssignmentId("");
        setCreateActionTargetExceptionId("");
        setCreateActionTargetPolicyId("");
        setCreateActionRepoId("");
        setCreateActionConfirmationMessage("");
        setCreateActionSourceType("MANUAL");
        setCreateActionSourceId("");
      } else {
        const data = await response.json();
        alert(`Failed to create remediation action: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error("Error creating remediation action:", err);
    }
  };

  const handlePreviewRemediationAction = async (actionId: string) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/remediation/actions/${actionId}/preview`, {
        method: 'POST'
      });
      if (response.ok) {
        const data = await response.json();
        setSelectedAction(data);
        loadRemediationData();
      } else {
        const data = await response.json();
        alert(`Failed to generate preview: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error("Error previewing remediation action:", err);
    }
  };

  const handleConfirmRemediationAction = async (actionId: string) => {
    if (confirmText !== "CONFIRM") {
      alert("Please type CONFIRM exactly to proceed.");
      return;
    }
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/remediation/actions/${actionId}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm_text: confirmText })
      });
      if (response.ok) {
        const data = await response.json();
        setSelectedAction(data);
        setConfirmText("");
        loadRemediationData();
      } else {
        const data = await response.json();
        alert(`Failed to confirm action: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error("Error confirming remediation action:", err);
    }
  };

  const handleExecuteRemediationAction = async (actionId: string) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/remediation/actions/${actionId}/execute`, {
        method: 'POST'
      });
      const data = await response.json();
      if (response.ok) {
        setSelectedAction(data);
        loadRemediationData();
        loadRoleAssignments();
        loadGovernanceData();
      } else {
        alert(`Failed to execute remediation action: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error("Error executing remediation action:", err);
    }
  };

  const handleCancelRemediationAction = async (actionId: string) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/remediation/actions/${actionId}/cancel`, {
        method: 'POST'
      });
      if (response.ok) {
        const data = await response.json();
        setSelectedAction(null);
        loadRemediationData();
      } else {
        const data = await response.json();
        alert(`Failed to cancel action: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error("Error cancelling remediation action:", err);
    }
  };

  const handlePreviewBulkRemediation = async () => {
    try {
      setBulkRemediationLoading(true);
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/remediation/bulk/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bulk_type: bulkRemediationType, reason: bulkRemediationReason })
      });
      if (response.ok) {
        const data = await response.json();
        setBulkPreviewItems(data);
        setBulkExecutionResults([]);
      } else {
        const data = await response.json();
        alert(`Failed to preview bulk remediation: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error("Error previewing bulk remediation:", err);
    } finally {
      setBulkRemediationLoading(false);
    }
  };

  const handleExecuteBulkRemediation = async () => {
    if (bulkPreviewItems.length === 0) {
      alert("No items to remediate.");
      return;
    }
    try {
      setBulkRemediationLoading(true);
      const executionItems = bulkPreviewItems.map(item => ({
        item_id: item.item_id,
        action_type: item.action_type,
        target_id: item.target_id
      }));
      
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/remediation/bulk/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: executionItems, reason: bulkRemediationReason })
      });
      if (response.ok) {
        const data = await response.json();
        setBulkExecutionResults(data);
        setBulkPreviewItems([]);
        setShowBulkRemediationConfirm(false);
        loadRemediationData();
        loadRoleAssignments();
        loadGovernanceData();
      } else {
        const data = await response.json();
        alert(`Failed to execute bulk remediation: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error("Error executing bulk remediation:", err);
    } finally {
      setBulkRemediationLoading(false);
    }
  };
  
  const loadAuditEvents = async () => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/audit`);
      if (response.ok) {
        const data = await response.json();
        setAuditEvents(data);
      }
    } catch (error) {
      console.error("Error loading audit events:", error);
    }
  };
  
  const loadNotifications = async () => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/notifications/mine`);
      if (response.ok) {
        const data = await response.json();
        setNotifications(data);
        
        // Calculate unread count and highest severity
        const unread = data.filter((n: any) => n.status === "UNREAD");
        setUnreadCount(unread.length);
        
        const severityOrder = { "CRITICAL": 4, "HIGH": 3, "WARNING": 2, "INFO": 1 };
        let maxSeverity = "INFO";
        unread.forEach((n: any) => {
          if (severityOrder[n.severity] > severityOrder[maxSeverity]) {
            maxSeverity = n.severity;
          }
        });
        setHighestSeverity(maxSeverity);
      }
    } catch (error) {
      console.error("Error loading notifications:", error);
    }
  };
  
  const loadNotificationPreferences = async () => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/notifications/preferences`);
      if (response.ok) {
        const data = await response.json();
        setNotificationPreferences(data);
      }
    } catch (error) {
      console.error("Error loading notification preferences:", error);
    }
  };
  
  const markNotificationRead = async (notificationId: string) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/notifications/${notificationId}/read`, {
        method: "POST"
      });
      if (response.ok) {
        loadNotifications();
      }
    } catch (error) {
      console.error("Error marking notification as read:", error);
    }
  };
  
  const dismissNotification = async (notificationId: string) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/notifications/${notificationId}/dismiss`, {
        method: "POST"
      });
      if (response.ok) {
        loadNotifications();
      }
    } catch (error) {
      console.error("Error dismissing notification:", error);
    }
  };
  
  const updateNotificationPreference = async (notificationType: string, enabled: boolean, minimumSeverity: string) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/notifications/preferences?notification_type=${notificationType}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled, minimum_severity: minimumSeverity })
      });
      if (response.ok) {
        loadNotificationPreferences();
      } else {
        const error = await response.json();
        alert(error.detail || "Failed to update preference");
      }
    } catch (error) {
      console.error("Error updating notification preference:", error);
      alert("Failed to update preference");
    }
  };
  
  const runScan = async (scanType: string) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/notifications/scan-${scanType}`, {
        method: "POST"
      });
      if (response.ok) {
        const data = await response.json();
        setScanResults(data);
        loadNotifications();
      } else {
        const error = await response.json();
        alert(error.detail || "Scan failed");
      }
    } catch (error) {
      console.error("Error running scan:", error);
      alert("Scan failed");
    }
  };
  
  const checkOrgNotificationPermission = async () => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/notifications`);
      if (response.ok) {
        setCanViewOrgNotifications(true);
      } else if (response.status === 403) {
        setCanViewOrgNotifications(false);
      }
    } catch (error) {
      console.error("Error checking org notification permission:", error);
      setCanViewOrgNotifications(false);
    }
  };
  
  const loadOrganizationNotifications = async () => {
    if (!canViewOrgNotifications) return;
    
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/notifications`);
      if (response.ok) {
        const data = await response.json();
        setOrganizationNotifications(data);
      }
    } catch (error) {
      console.error("Error loading organization notifications:", error);
    }
  };

  const loadSecurityPosture = async () => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/security/posture`);
      if (response.ok) {
        const data = await response.json();
        setSecurityPosture(data);
        setAccessDenied(null);
      } else if (response.status === 403) {
        setAccessDenied("You do not have permission to view security posture. Contact your governance owner.");
      }
    } catch (error) {
      console.error("Error loading security posture:", error);
    }
  };

  const loadAccessReviews = async () => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/access-reviews`);
      if (response.ok) {
        const data = await response.json();
        setAccessReviews(data);
      }
    } catch (error) {
      console.error("Error loading access reviews:", error);
    }
  };

  const loadSecuritySignals = async () => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/security/signals`);
      if (response.ok) {
        const data = await response.json();
        setSecuritySignals(data);
      } else if (response.status === 403) {
        setAccessDenied("You do not have permission to view security signals. Contact your governance owner.");
      }
    } catch (error) {
      console.error("Error loading security signals:", error);
    }
  };

  const createAccessReview = async () => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/access-reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          review_name: newReviewName,
          review_type: newReviewType,
          period_start: newReviewPeriodStart,
          period_end: newReviewPeriodEnd
        })
      });

      if (response.ok) {
        setShowCreateReview(false);
        setNewReviewName("");
        setNewReviewType("QUARTERLY_ACCESS_REVIEW");
        setNewReviewPeriodStart("");
        setNewReviewPeriodEnd("");
        loadAccessReviews();
      } else if (response.status === 403) {
        setAccessDenied("You do not have permission to create access reviews. Contact your governance owner.");
      } else {
        const error = await response.json();
        alert(error.detail || "Failed to create access review");
      }
    } catch (error) {
      console.error("Error creating access review:", error);
      alert("Failed to create access review");
    }
  };

  const openReview = async (reviewId: string) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/access-reviews/${reviewId}`);
      if (response.ok) {
        const data = await response.json();
        setSelectedReview(data);
        
        // Load review items
        const itemsResponse = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/access-reviews/${reviewId}/items`);
        if (itemsResponse.ok) {
          const itemsData = await itemsResponse.json();
          setReviewItems(itemsData);
        }
      }
    } catch (error) {
      console.error("Error opening review:", error);
    }
  };

  const completeReview = async (reviewId: string) => {
    if (!confirm("Are you sure you want to complete this access review? This will mark it as finished.")) return;
    
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/access-reviews/${reviewId}/complete`, {
        method: "POST"
      });

      if (response.ok) {
        loadAccessReviews();
        setSelectedReview(null);
        setReviewItems([]);
      } else if (response.status === 403) {
        setAccessDenied("You do not have permission to complete access reviews. Contact your governance owner.");
      } else {
        alert("Failed to complete review");
      }
    } catch (error) {
      console.error("Error completing review:", error);
      alert("Failed to complete review");
    }
  };

  const cancelReview = async (reviewId: string) => {
    if (!confirm("Are you sure you want to cancel this access review?")) return;
    
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/access-reviews/${reviewId}/cancel`, {
        method: "POST"
      });

      if (response.ok) {
        loadAccessReviews();
        setSelectedReview(null);
        setReviewItems([]);
      } else if (response.status === 403) {
        setAccessDenied("You do not have permission to cancel access reviews. Contact your governance owner.");
      } else {
        alert("Failed to cancel review");
      }
    } catch (error) {
      console.error("Error cancelling review:", error);
      alert("Failed to cancel review");
    }
  };

  const updateItemDecision = async (itemId: string) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/access-reviews/${selectedReview.id}/items/${itemId}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision: itemDecision,
          reason: itemDecisionReason
        })
      });

      if (response.ok) {
        setItemDecision("");
        setItemDecisionReason("");
        openReview(selectedReview.id); // Reload items
      } else if (response.status === 403) {
        setAccessDenied("You do not have permission to decide on review items. Contact your governance owner.");
      } else {
        alert("Failed to update item decision");
      }
    } catch (error) {
      console.error("Error updating item decision:", error);
      alert("Failed to update item decision");
    }
  };

  const exportEvidencePack = async () => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/evidence-pack`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pack_type: evidencePackType })
      });

      if (response.ok) {
        const data = await response.json();
        setEvidencePack(data);
        
        // Download JSON
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `evidence-pack-${evidencePackType.toLowerCase()}-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
      } else if (response.status === 403) {
        setAccessDenied("You do not have permission to export evidence packs. Contact your governance owner.");
      } else {
        const error = await response.json();
        alert(error.detail || "Failed to export evidence pack");
      }
    } catch (error) {
      console.error("Error exporting evidence pack:", error);
      alert("Failed to export evidence pack");
    }
  };
  
  const loadRoleAssignments = async () => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/roles?active_only=${filterActive}`);
      if (response.ok) {
        const data = await response.json();
        setRoleAssignments(data);
      }
    } catch (error) {
      console.error("Error loading role assignments:", error);
    }
  };
  
  const assignRole = async () => {
    try {
      const payload: any = {
        user_id: selectedUserId,
        role: selectedRole,
        scope_type: selectedScope,
        reason: roleReason
      };
      
      if (selectedScope === "REPOSITORY" && selectedRepository) {
        payload.repository_id = selectedRepository;
      }
      
      if (roleExpiry) {
        payload.expires_at = roleExpiry;
      }
      
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/roles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      if (response.ok) {
        loadRoleAssignments();
        setSelectedUserId("");
        setSelectedRole("");
        setSelectedScope("WORKSPACE");
        setSelectedRepository("");
        setRoleExpiry("");
        setRoleReason("");
      } else {
        const error = await response.json();
        alert(error.detail || "Failed to assign role");
      }
    } catch (error) {
      console.error("Error assigning role:", error);
      alert("Failed to assign role");
    }
  };
  
  const revokeRole = async (assignmentId: string) => {
    if (!confirm("Are you sure you want to revoke this role assignment?")) return;
    
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/roles/${assignmentId}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Role revoked by admin" })
      });
      
      if (response.ok) {
        loadRoleAssignments();
      } else {
        alert("Failed to revoke role");
      }
    } catch (error) {
      console.error("Error revoking role:", error);
      alert("Failed to revoke role");
    }
  };
  
  const loadEffectivePermissions = async (userId: string) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/users/${userId}/permissions`);
      if (response.ok) {
        const data = await response.json();
        setEffectivePermissions(data);
      }
    } catch (error) {
      console.error("Error loading effective permissions:", error);
    }
  };
  
  const checkPermission = async () => {
    try {
      const payload: any = {
        user_id: permissionCheckUser,
        permission: permissionCheckPermission
      };
      
      if (selectedRepository) {
        payload.repository_id = selectedRepository;
      }
      
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/permissions/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      if (response.ok) {
        const data = await response.json();
        setPermissionCheckResult(data);
      }
    } catch (error) {
      console.error("Error checking permission:", error);
    }
  };

  const handleExportReport = async (format: string) => {
    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/report?format=${format}`);
      if (response.ok) {
        const data = await response.json();
        
        if (format === 'JSON') {
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'governance-report.json';
          a.click();
        } else if (format === 'CSV') {
          const blob = new Blob([data.csv], { type: 'text/csv' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'governance-report.csv';
          a.click();
        } else if (format === 'MARKDOWN') {
          const blob = new Blob([data.markdown], { type: 'text/markdown' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'governance-report.md';
          a.click();
        }
      }
    } catch (err) {
      console.error('Failed to export report:', err);
    }
  };

  const handleBulkPreview = async () => {
    if (selectedRepositories.length === 0) {
      alert('Please select at least one repository');
      return;
    }

    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/bulk-preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repository_ids: selectedRepositories,
          operation: bulkOperation,
          preset_name: bulkOperation === 'APPLY_PRESET' ? bulkPreset : undefined
        })
      });

      if (response.ok) {
        const data = await response.json();
        setBulkPreview(data);
      }
    } catch (err) {
      console.error('Failed to preview bulk operation:', err);
    }
  };

  const handleBulkApply = async () => {
    if (selectedRepositories.length === 0) {
      alert('Please select at least one repository');
      return;
    }

    if (!showBulkConfirm) {
      setShowBulkConfirm(true);
      return;
    }

    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/bulk-operations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repository_ids: selectedRepositories,
          operation: bulkOperation,
          preset_name: bulkOperation === 'APPLY_PRESET' ? bulkPreset : undefined,
          reason: bulkReason
        })
      });

      if (response.ok) {
        const data = await response.json();
        setBulkResult(data);
        setShowBulkConfirm(false);
        loadGovernanceData();
      }
    } catch (err) {
      console.error('Failed to apply bulk operation:', err);
    }
  };

  const handleExceptionAction = async (exceptionId: string, action: 'approve' | 'reject' | 'revoke') => {
    if (action !== 'revoke' && !decisionReason.trim()) {
      alert('Please provide a decision reason');
      return;
    }

    try {
      const response = await fetch(`/api/organizations/${params.organizationId}/cicd/governance/exceptions/${exceptionId}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision_reason: decisionReason })
      });

      if (response.ok) {
        setDecisionReason('');
        loadGovernanceData();
      }
    } catch (err) {
      console.error(`Failed to ${action} exception:`, err);
    }
  };

  const handleSelectAll = () => {
    if (selectedRepositories.length === repositories.length) {
      setSelectedRepositories([]);
    } else {
      setSelectedRepositories(repositories.map(r => r.repository_id));
    }
  };

  const filteredRepositories = repositories.filter(repo => {
    if (filterStatus !== 'ALL' && repo.compliance_status !== filterStatus) return false;
    if (filterDrift !== 'ALL' && (filterDrift === 'true' ? !repo.drift_detected : repo.drift_detected)) return false;
    if (filterPreset !== 'ALL' && repo.current_preset !== filterPreset) return false;
    if (filterRisk !== 'ALL' && repo.drift_risk_level !== filterRisk) return false;
    return true;
  });

  if (loading) {
    return <div className="p-6">Loading governance data...</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">CI/CD Governance</h1>
        <p className="text-muted-foreground">Workspace-level policy compliance and management</p>
      </div>

      {/* Compliance Overview */}
      {dashboard && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Overall Compliance Score</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{dashboard.overall_compliance_score}%</div>
              <div className={`text-sm ${dashboard.overall_compliance_score >= 90 ? 'text-green-600' : dashboard.overall_compliance_score >= 70 ? 'text-yellow-600' : 'text-red-600'}`}>
                {dashboard.overall_compliance_score >= 90 ? 'Compliant' : dashboard.overall_compliance_score >= 70 ? 'Needs Attention' : 'Critical'}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Total Repositories</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{dashboard.total_repositories}</div>
              <div className="text-sm text-muted-foreground">{dashboard.repositories_with_policy} with policy</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Drift Detected</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{dashboard.repositories_with_drift}</div>
              <div className="text-sm text-muted-foreground">{dashboard.repositories_with_high_risk_drift} high risk</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Branch Protection Ready</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{dashboard.total_repositories - dashboard.repositories_not_ready_for_branch_protection}</div>
              <div className="text-sm text-muted-foreground">{dashboard.repositories_not_ready_for_branch_protection} not ready</div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">
            <Shield className="w-4 h-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="repositories">
            <FileText className="w-4 h-4 mr-2" />
            Repositories
          </TabsTrigger>
          <TabsTrigger value="bulk">
            <Settings className="w-4 h-4 mr-2" />
            Bulk Operations
          </TabsTrigger>
          <TabsTrigger value="exceptions">
            <AlertTriangle className="w-4 h-4 mr-2" />
            Exceptions
          </TabsTrigger>
          <TabsTrigger value="reviews">
            <CheckCircle className="w-4 h-4 mr-2" />
            Reviews
          </TabsTrigger>
          <TabsTrigger value="report">
            <Download className="w-4 h-4 mr-2" />
            Report
          </TabsTrigger>
          <TabsTrigger value="analytics">
            <TrendingUp className="w-4 h-4 mr-2" />
            Analytics
          </TabsTrigger>
          <TabsTrigger value="access-control">
            <Shield className="w-4 h-4 mr-2" />
            Access Control
          </TabsTrigger>
          <TabsTrigger value="notifications">
            <Bell className="w-4 h-4 mr-2" />
            Notifications
            {unreadCount > 0 && (
              <Badge variant="destructive" className="ml-2">{unreadCount}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="security">
            <Shield className="w-4 h-4 mr-2" />
            Security & Access Reviews
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {dashboard && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Preset Distribution</CardTitle>
                  <CardDescription>Repositories using each policy preset</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {Object.entries(dashboard.repositories_using_each_preset).map(([preset, count]) => (
                      <div key={preset} className="flex justify-between items-center">
                        <span className="text-sm">{preset}</span>
                        <Badge variant="outline">{count}</Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Policy Issues</CardTitle>
                  <CardDescription>Repositories with policy configuration issues</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm">Missing artifact requirement</span>
                      <Badge variant="destructive">{dashboard.repositories_missing_required_artifact_policy}</Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm">Manual override enabled</span>
                      <Badge variant="outline">{dashboard.repositories_allowing_manual_override}</Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm">Not ready for branch protection</span>
                      <Badge variant="destructive">{dashboard.repositories_not_ready_for_branch_protection}</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="repositories" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Repository Compliance</CardTitle>
              <CardDescription>Compliance status for all repositories</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 mb-4">
                <div className="flex gap-2 flex-wrap">
                  <select 
                    className="p-2 border rounded"
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                  >
                    <option value="ALL">All Statuses</option>
                    <option value="COMPLIANT">Compliant</option>
                    <option value="DRIFTED">Drifted</option>
                    <option value="HIGH_RISK">High Risk</option>
                    <option value="CRITICAL">Critical</option>
                  </select>
                  <select 
                    className="p-2 border rounded"
                    value={filterDrift}
                    onChange={(e) => setFilterDrift(e.target.value)}
                  >
                    <option value="ALL">All Drift Status</option>
                    <option value="true">Drift Detected</option>
                    <option value="false">No Drift</option>
                  </select>
                  <select 
                    className="p-2 border rounded"
                    value={filterPreset}
                    onChange={(e) => setFilterPreset(e.target.value)}
                  >
                    <option value="ALL">All Presets</option>
                    <option value="PERMISSIVE">Permissive</option>
                    <option value="STANDARD">Standard</option>
                    <option value="STRICT">Strict</option>
                    <option value="REGULATED">Regulated</option>
                  </select>
                  <select 
                    className="p-2 border rounded"
                    value={filterRisk}
                    onChange={(e) => setFilterRisk(e.target.value)}
                  >
                    <option value="ALL">All Risk Levels</option>
                    <option value="NONE">None</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                    <option value="CRITICAL">Critical</option>
                  </select>
                </div>
              </div>
              <div className="space-y-4">
                {filteredRepositories.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No repository compliance data available</p>
                ) : (
                  filteredRepositories.map((repo) => (
                    <div key={repo.repository_id} className="flex items-center justify-between p-4 border rounded">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={selectedRepositories.includes(repo.repository_id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedRepositories([...selectedRepositories, repo.repository_id]);
                            } else {
                              setSelectedRepositories(selectedRepositories.filter(id => id !== repo.repository_id));
                            }
                          }}
                        />
                        <div className="flex-1">
                          <div className="font-medium">{repo.repository_name}</div>
                          <div className="text-sm text-muted-foreground">
                            {repo.current_preset || 'No preset'} • {repo.policy_source}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <div className="text-sm font-medium">{repo.compliance_score}%</div>
                          <Badge variant={repo.compliance_status === 'COMPLIANT' ? 'default' : repo.compliance_status === 'HIGH_RISK' ? 'destructive' : 'secondary'}>
                            {repo.compliance_status}
                          </Badge>
                        </div>
                        {repo.drift_detected && (
                          <AlertTriangle className="w-4 h-4 text-yellow-600" />
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="bulk" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Bulk Operations</CardTitle>
              <CardDescription>Apply policy changes to multiple repositories</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium">Select Operation</label>
                <select 
                  className="w-full p-2 border rounded mt-1"
                  value={bulkOperation}
                  onChange={(e) => setBulkOperation(e.target.value)}
                >
                  <option value="APPLY_PRESET">Apply Preset</option>
                  <option value="RESTORE_ORG_DEFAULT">Restore Workspace Default</option>
                  <option value="ACKNOWLEDGE_DRIFT">Acknowledge Drift</option>
                  <option value="EXPORT_POLICIES">Export Policies</option>
                  <option value="SCAN_COMPLIANCE">Scan Compliance</option>
                </select>
              </div>
              
              {bulkOperation === 'APPLY_PRESET' && (
                <div>
                  <label className="text-sm font-medium">Select Preset</label>
                  <select 
                    className="w-full p-2 border rounded mt-1"
                    value={bulkPreset}
                    onChange={(e) => setBulkPreset(e.target.value)}
                  >
                    <option value="PERMISSIVE">Permissive</option>
                    <option value="STANDARD">Standard</option>
                    <option value="STRICT">Strict</option>
                    <option value="REGULATED">Regulated</option>
                  </select>
                </div>
              )}
              
              <div>
                <label className="text-sm font-medium">Select Repositories</label>
                <div className="mt-1 p-4 border rounded bg-gray-50">
                  <div className="flex items-center gap-2 mb-2">
                    <input
                      type="checkbox"
                      checked={selectedRepositories.length === repositories.length && repositories.length > 0}
                      onChange={handleSelectAll}
                    />
                    <span className="text-sm font-medium">Select All ({selectedRepositories.length} selected)</span>
                  </div>
                  <div className="max-h-60 overflow-y-auto space-y-2">
                    {repositories.map((repo) => (
                      <div key={repo.repository_id} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={selectedRepositories.includes(repo.repository_id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedRepositories([...selectedRepositories, repo.repository_id]);
                            } else {
                              setSelectedRepositories(selectedRepositories.filter(id => id !== repo.repository_id));
                            }
                          }}
                        />
                        <span className="text-sm">{repo.repository_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              
              <div>
                <label className="text-sm font-medium">Reason (optional)</label>
                <input
                  type="text"
                  className="w-full p-2 border rounded mt-1"
                  value={bulkReason}
                  onChange={(e) => setBulkReason(e.target.value)}
                  placeholder="Reason for this operation"
                />
              </div>
              
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleBulkPreview} disabled={selectedRepositories.length === 0}>
                  Preview
                </Button>
                <Button onClick={handleBulkApply} disabled={selectedRepositories.length === 0}>
                  {showBulkConfirm ? 'Confirm Apply' : 'Apply'}
                </Button>
              </div>
              
              {bulkPreview && (
                <Card className="mt-4">
                  <CardHeader>
                    <CardTitle>Bulk Preview</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div><strong>Repositories Affected:</strong> {bulkPreview.repositories_affected.length}</div>
                      <div><strong>Repositories Skipped:</strong> {bulkPreview.repositories_skipped.length}</div>
                      {bulkPreview.repositories_affected.length > 0 && (
                        <div className="mt-2">
                          <strong>Affected Repositories:</strong>
                          <ul className="list-disc list-inside">
                            {bulkPreview.repositories_affected.map((repo: any) => (
                              <li key={repo.repositoryId}>{repo.repositoryName}: {repo.currentPreset} → {repo.targetPreset}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {bulkResult && (
                <Card className="mt-4">
                  <CardHeader>
                    <CardTitle>Bulk Operation Result</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div><strong>Operation:</strong> {bulkResult.operation}</div>
                      <div><strong>Requested:</strong> {bulkResult.requestedCount}</div>
                      <div><strong>Succeeded:</strong> {bulkResult.succeededCount}</div>
                      <div><strong>Failed:</strong> {bulkResult.failedCount}</div>
                      <div><strong>Skipped:</strong> {bulkResult.skippedCount}</div>
                      {bulkResult.results.length > 0 && (
                        <div className="mt-2">
                          <strong>Per-Repository Results:</strong>
                          <ul className="list-disc list-inside">
                            {bulkResult.results.map((result: any, idx: number) => (
                              <li key={idx}>
                                {result.repositoryId}: {result.status} - {result.message}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="exceptions" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Policy Exceptions</CardTitle>
              <CardDescription>Approved and pending policy exceptions</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {exceptions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No policy exceptions</p>
                ) : (
                  exceptions.map((exc) => (
                    <div key={exc.id} className="flex items-center justify-between p-4 border rounded">
                      <div className="flex-1">
                        <div className="font-medium">{exc.repository_id}</div>
                        <div className="text-sm text-muted-foreground">
                          {exc.exception_fields.join(', ')} • {exc.reason}
                        </div>
                        {exc.expires_at && (
                          <div className="text-xs text-muted-foreground">
                            Expires: {new Date(exc.expires_at).toLocaleString()}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={exc.status === 'APPROVED' ? 'default' : exc.status === 'PENDING' ? 'secondary' : 'destructive'}>
                          {exc.status}
                        </Badge>
                        {exc.status === 'PENDING' && (
                          <div className="flex gap-1">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleExceptionAction(exc.id, 'approve')}
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleExceptionAction(exc.id, 'reject')}
                            >
                              Reject
                            </Button>
                          </div>
                        )}
                        {exc.status === 'APPROVED' && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleExceptionAction(exc.id, 'revoke')}
                          >
                            Revoke
                          </Button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
              {exceptions.some(e => e.status === 'PENDING') && (
                <div className="mt-4">
                  <label className="text-sm font-medium">Decision Reason</label>
                  <input
                    type="text"
                    className="w-full p-2 border rounded mt-1"
                    value={decisionReason}
                    onChange={(e) => setDecisionReason(e.target.value)}
                    placeholder="Reason for approve/reject decision"
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="reviews" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Governance Review Snapshots</CardTitle>
              <CardDescription>Historical compliance snapshots</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {snapshots.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No review snapshots available</p>
                ) : (
                  snapshots.map((snap) => (
                    <div key={snap.id} className="flex items-center justify-between p-4 border rounded">
                      <div className="flex-1">
                        <div className="font-medium">{new Date(snap.created_at).toLocaleString()}</div>
                        <div className="text-sm text-muted-foreground">
                          Compliance: {snap.compliance_score}% • Critical: {snap.critical_count} • High Risk: {snap.high_risk_count}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
              <Button className="mt-4">Create New Snapshot</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="report" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Export Governance Report</CardTitle>
              <CardDescription>Download compliance report in various formats</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => handleExportReport('JSON')}>
                  Export JSON
                </Button>
                <Button variant="outline" onClick={() => handleExportReport('CSV')}>
                  Export CSV
                </Button>
                <Button variant="outline" onClick={() => handleExportReport('MARKDOWN')}>
                  Export Markdown
                </Button>
              </div>
              <p className="text-sm text-muted-foreground">
                Reports do not contain secrets or sensitive information.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analytics" className="space-y-6">
          {executiveSummary && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Executive Summary</CardTitle>
                  <CardDescription>High-level governance overview for leadership</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div>
                      <div className="text-sm text-muted-foreground">Compliance Score</div>
                      <div className="text-2xl font-bold">{executiveSummary.overall_compliance_score}%</div>
                    </div>
                    <div>
                      <div className="text-sm text-muted-foreground">Maturity Score</div>
                      <div className="text-2xl font-bold">{executiveSummary.maturity_score}/100</div>
                      <div className="text-sm">{executiveSummary.maturity_level}</div>
                    </div>
                    <div>
                      <div className="text-sm text-muted-foreground">Critical Repos</div>
                      <div className="text-2xl font-bold text-red-600">{executiveSummary.critical_repositories}</div>
                    </div>
                    <div>
                      <div className="text-sm text-muted-foreground">Active Exceptions</div>
                      <div className="text-2xl font-bold">{executiveSummary.active_exceptions}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {maturityScore && (
                <Card>
                  <CardHeader>
                    <CardTitle>Governance Maturity Score</CardTitle>
                    <CardDescription>Workspace governance maturity assessment</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="text-lg font-bold">Total Score: {maturityScore.score}/100</span>
                        <Badge variant={maturityScore.score >= 80 ? 'default' : maturityScore.score >= 60 ? 'secondary' : 'destructive'}>
                          {maturityScore.level}
                        </Badge>
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span>Policy Coverage</span>
                          <span>{maturityScore.dimension_scores.policy_coverage}/20</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Policy Consistency</span>
                          <span>{maturityScore.dimension_scores.policy_consistency}/20</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Branch Protection Readiness</span>
                          <span>{maturityScore.dimension_scores.branch_protection_readiness}/20</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Exception Hygiene</span>
                          <span>{maturityScore.dimension_scores.exception_hygiene}/20</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Operational Observability</span>
                          <span>{maturityScore.dimension_scores.operational_observability}/10</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Evidence Preservation</span>
                          <span>{maturityScore.dimension_scores.evidence_preservation}/10</span>
                        </div>
                      </div>
                      {maturityScore.strengths.length > 0 && (
                        <div>
                          <div className="font-medium mb-2">Strengths:</div>
                          <ul className="list-disc list-inside text-sm">
                            {maturityScore.strengths.map((s: string, i: number) => (
                              <li key={i}>{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {maturityScore.weaknesses.length > 0 && (
                        <div>
                          <div className="font-medium mb-2">Weaknesses:</div>
                          <ul className="list-disc list-inside text-sm">
                            {maturityScore.weaknesses.map((w: string, i: number) => (
                              <li key={i}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {complianceTrend && (
                <Card>
                  <CardHeader>
                    <CardTitle>Compliance Trend</CardTitle>
                    <CardDescription>Compliance score changes over time</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {complianceTrend.trend_direction === "INSUFFICIENT_DATA" ? (
                      <p className="text-sm text-muted-foreground">Not enough snapshots yet</p>
                    ) : (
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span>Current Score</span>
                          <span className="font-bold">{complianceTrend.current_compliance_score}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Previous Score</span>
                          <span>{complianceTrend.previous_compliance_score}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Delta</span>
                          <span className={complianceTrend.score_delta > 0 ? 'text-green-600' : complianceTrend.score_delta < 0 ? 'text-red-600' : ''}>
                            {complianceTrend.score_delta > 0 ? '+' : ''}{complianceTrend.score_delta}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Trend</span>
                          <Badge variant={complianceTrend.trend_direction === 'IMPROVING' ? 'default' : complianceTrend.trend_direction === 'DECLINING' ? 'destructive' : 'secondary'}>
                            {complianceTrend.trend_direction}
                          </Badge>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {policyAdoption && (
                <Card>
                  <CardHeader>
                    <CardTitle>Policy Adoption Distribution</CardTitle>
                    <CardDescription>Preset usage across repositories</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {Object.entries(policyAdoption.preset_distribution).map(([preset, data]: [string, any]) => (
                        <div key={preset} className="flex justify-between items-center">
                          <span className="text-sm">{preset}</span>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">{data.count}</Badge>
                            <span className="text-sm text-muted-foreground">{data.percentage}%</span>
                          </div>
                        </div>
                      ))}
                    </div>
                    {policyAdoption.insights.length > 0 && (
                      <div className="mt-4">
                        <div className="font-medium mb-2">Insights:</div>
                        <ul className="list-disc list-inside text-sm">
                          {policyAdoption.insights.map((insight: string, i: number) => (
                            <li key={i}>{insight}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {exceptionAnalytics && (
                <Card>
                  <CardHeader>
                    <CardTitle>Exception Analytics</CardTitle>
                    <CardDescription>Policy exception metrics and aging</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                      <div>
                        <div className="text-sm text-muted-foreground">Active</div>
                        <div className="text-xl font-bold">{exceptionAnalytics.active_exceptions}</div>
                      </div>
                      <div>
                        <div className="text-sm text-muted-foreground">Pending</div>
                        <div className="text-xl font-bold text-yellow-600">{exceptionAnalytics.pending_exceptions}</div>
                      </div>
                      <div>
                        <div className="text-sm text-muted-foreground">Expired</div>
                        <div className="text-xl font-bold text-red-600">{exceptionAnalytics.expired_exceptions}</div>
                      </div>
                      <div>
                        <div className="text-sm text-muted-foreground">Expiring in 7d</div>
                        <div className="text-xl font-bold">{exceptionAnalytics.exceptions_expiring_in_7_days}</div>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="font-medium">Exception Aging:</div>
                      {Object.entries(exceptionAnalytics.exception_aging_buckets).map(([bucket, count]: [string, number]) => (
                        <div key={bucket} className="flex justify-between text-sm">
                          <span>{bucket.replace('_', ' ')}</span>
                          <span>{count}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {riskHeatmap && riskHeatmap.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Repository Risk Heatmap</CardTitle>
                    <CardDescription>Repository-level risk assessment</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4 mb-4">
                      <div className="flex gap-2 flex-wrap">
                        <select 
                          className="p-2 border rounded"
                          value={heatmapFilterRisk}
                          onChange={(e) => setHeatmapFilterRisk(e.target.value)}
                        >
                          <option value="ALL">All Risk Bands</option>
                          <option value="CRITICAL">Critical</option>
                          <option value="HIGH">High</option>
                          <option value="MEDIUM">Medium</option>
                          <option value="LOW">Low</option>
                        </select>
                        <select 
                          className="p-2 border rounded"
                          value={heatmapFilterPreset}
                          onChange={(e) => setHeatmapFilterPreset(e.target.value)}
                        >
                          <option value="ALL">All Presets</option>
                          <option value="PERMISSIVE">Permissive</option>
                          <option value="STANDARD">Standard</option>
                          <option value="STRICT">Strict</option>
                          <option value="REGULATED">Regulated</option>
                        </select>
                      </div>
                    </div>
                    <div className="space-y-2">
                      {riskHeatmap
                        .filter(repo => 
                          (heatmapFilterRisk === 'ALL' || repo.risk_band === heatmapFilterRisk) &&
                          (heatmapFilterPreset === 'ALL' || repo.current_preset === heatmapFilterPreset)
                        )
                        .slice(0, 10)
                        .map((repo: any, i: number) => (
                        <div key={i} className="flex items-center justify-between p-3 border rounded">
                          <div className="flex-1">
                            <div className="font-medium">{repo.repository_name}</div>
                            <div className="text-sm text-muted-foreground">{repo.current_preset || 'No preset'}</div>
                          </div>
                          <div className="flex items-center gap-4">
                            <Badge variant={repo.risk_band === 'CRITICAL' ? 'destructive' : repo.risk_band === 'HIGH' ? 'destructive' : repo.risk_band === 'MEDIUM' ? 'secondary' : 'default'}>
                              {repo.risk_band}
                            </Badge>
                            <div className="text-sm font-bold">{repo.risk_score}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardHeader>
                  <CardTitle>Export Executive Report</CardTitle>
                  <CardDescription>Download executive governance report</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex gap-2">
                    <Button variant="outline" onClick={() => handleExportReport('JSON')}>
                      Export JSON
                    </Button>
                    <Button variant="outline" onClick={() => handleExportReport('CSV')}>
                      Export CSV
                    </Button>
                    <Button variant="outline" onClick={() => handleExportReport('MARKDOWN')}>
                      Export Markdown
                    </Button>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Reports do not contain secrets or sensitive information.
                  </p>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="access-control" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Role Assignments</CardTitle>
              <CardDescription>Manage governance roles for users</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <select 
                  className="p-2 border rounded"
                  value={filterRole}
                  onChange={(e) => setFilterRole(e.target.value)}
                >
                  <option value="ALL">All Roles</option>
                  <option value="GOVERNANCE_OWNER">Governance Owner</option>
                  <option value="POLICY_ADMIN">Policy Admin</option>
                  <option value="EXCEPTION_APPROVER">Exception Approver</option>
                  <option value="REPOSITORY_POLICY_MANAGER">Repository Policy Manager</option>
                  <option value="GOVERNANCE_VIEWER">Governance Viewer</option>
                  <option value="EXECUTIVE_VIEWER">Executive Viewer</option>
                  <option value="AUDITOR">Auditor</option>
                </select>
                <select 
                  className="p-2 border rounded"
                  value={filterScope}
                  onChange={(e) => setFilterScope(e.target.value)}
                >
                  <option value="ALL">All Scopes</option>
                  <option value="WORKSPACE">Workspace</option>
                  <option value="REPOSITORY">Repository</option>
                </select>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={filterActive}
                    onChange={(e) => setFilterActive(e.target.checked)}
                  />
                  <span className="text-sm">Active Only</span>
                </label>
                <Button onClick={loadRoleAssignments}>Refresh</Button>
              </div>
              
              <div className="space-y-2">
                {roleAssignments.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No role assignments found</p>
                ) : (
                  roleAssignments
                    .filter(assignment => 
                      (filterRole === 'ALL' || assignment.role === filterRole) &&
                      (filterScope === 'ALL' || assignment.scope_type === filterScope)
                    )
                    .map((assignment: any) => (
                    <div key={assignment.id} className="flex items-center justify-between p-3 border rounded">
                      <div className="flex-1">
                        <div className="font-medium">{assignment.user_id}</div>
                        <div className="text-sm text-muted-foreground">
                          {assignment.role} • {assignment.scope_type}
                          {assignment.repository_id && ` • ${assignment.repository_id}`}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Assigned: {new Date(assignment.created_at).toLocaleDateString()}
                          {assignment.expires_at && ` • Expires: ${new Date(assignment.expires_at).toLocaleDateString()}`}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={assignment.is_active ? 'default' : 'secondary'}>
                          {assignment.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                        {assignment.is_active && (
                          <Button variant="destructive" size="sm" onClick={() => revokeRole(assignment.id)}>
                            Revoke
                          </Button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Assign Role</CardTitle>
              <CardDescription>Assign a governance role to a user</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium">User ID</label>
                  <input
                    type="text"
                    className="w-full p-2 border rounded"
                    value={selectedUserId}
                    onChange={(e) => setSelectedUserId(e.target.value)}
                    placeholder="Enter user UUID"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Role</label>
                  <select
                    className="w-full p-2 border rounded"
                    value={selectedRole}
                    onChange={(e) => setSelectedRole(e.target.value)}
                  >
                    <option value="">Select role</option>
                    <option value="GOVERNANCE_OWNER">Governance Owner</option>
                    <option value="POLICY_ADMIN">Policy Admin</option>
                    <option value="EXCEPTION_APPROVER">Exception Approver</option>
                    <option value="REPOSITORY_POLICY_MANAGER">Repository Policy Manager</option>
                    <option value="GOVERNANCE_VIEWER">Governance Viewer</option>
                    <option value="EXECUTIVE_VIEWER">Executive Viewer</option>
                    <option value="AUDITOR">Auditor</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium">Scope</label>
                  <select
                    className="w-full p-2 border rounded"
                    value={selectedScope}
                    onChange={(e) => setSelectedScope(e.target.value)}
                  >
                    <option value="WORKSPACE">Workspace</option>
                    <option value="REPOSITORY">Repository</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium">Repository ID (if Repository scope)</label>
                  <input
                    type="text"
                    className="w-full p-2 border rounded"
                    value={selectedRepository}
                    onChange={(e) => setSelectedRepository(e.target.value)}
                    placeholder="Enter repository UUID"
                    disabled={selectedScope !== 'REPOSITORY'}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Expiry Date (optional)</label>
                  <input
                    type="date"
                    className="w-full p-2 border rounded"
                    value={roleExpiry}
                    onChange={(e) => setRoleExpiry(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Reason</label>
                  <input
                    type="text"
                    className="w-full p-2 border rounded"
                    value={roleReason}
                    onChange={(e) => setRoleReason(e.target.value)}
                    placeholder="Reason for assignment"
                  />
                </div>
              </div>
              <Button onClick={assignRole}>Assign Role</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Effective Permissions</CardTitle>
              <CardDescription>View effective permissions for a user</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  className="flex-1 p-2 border rounded"
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                  placeholder="Enter user UUID"
                />
                <Button onClick={() => loadEffectivePermissions(selectedUserId)}>View Permissions</Button>
              </div>
              
              {effectivePermissions && (
                <div className="space-y-4">
                  <div>
                    <h4 className="font-medium mb-2">Assigned Roles</h4>
                    <div className="space-y-2">
                      {effectivePermissions.roles.map((role: any, i: number) => (
                        <div key={i} className="p-2 border rounded">
                          <div className="font-medium">{role.role}</div>
                          <div className="text-sm text-muted-foreground">
                            {role.scope_type}
                            {role.repository_id && ` • ${role.repository_id}`}
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            Permissions: {role.permissions.join(', ')}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="font-medium mb-2">Effective Permissions ({effectivePermissions.effective_permissions.length})</h4>
                    <div className="flex flex-wrap gap-2">
                      {effectivePermissions.effective_permissions.map((perm: string, i: number) => (
                        <Badge key={i} variant="outline">{perm}</Badge>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Permission Preview</CardTitle>
              <CardDescription>Check if a user has a specific permission</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium">User ID</label>
                  <input
                    type="text"
                    className="w-full p-2 border rounded"
                    value={permissionCheckUser}
                    onChange={(e) => setPermissionCheckUser(e.target.value)}
                    placeholder="Enter user UUID"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Permission</label>
                  <select
                    className="w-full p-2 border rounded"
                    value={permissionCheckPermission}
                    onChange={(e) => setPermissionCheckPermission(e.target.value)}
                  >
                    <option value="">Select permission</option>
                    <option value="governance.policy.view">governance.policy.view</option>
                    <option value="governance.policy.update">governance.policy.update</option>
                    <option value="governance.policy.apply_preset">governance.policy.apply_preset</option>
                    <option value="governance.policy.bulk_apply">governance.policy.bulk_apply</option>
                    <option value="governance.exception.approve">governance.exception.approve</option>
                    <option value="governance.exception.reject">governance.exception.reject</option>
                    <option value="governance.analytics.view">governance.analytics.view</option>
                    <option value="governance.executive_report.export">governance.executive_report.export</option>
                    <option value="governance.roles.assign">governance.roles.assign</option>
                  </select>
                </div>
              </div>
              <Button onClick={checkPermission}>Check Permission</Button>
              
              {permissionCheckResult && (
                <div className={`p-4 border rounded ${permissionCheckResult.allowed ? 'bg-green-50' : 'bg-red-50'}`}>
                  <div className="font-medium mb-2">
                    {permissionCheckResult.allowed ? '✓ Allowed' : '✗ Denied'}
                  </div>
                  <div className="text-sm space-y-1">
                    <div><strong>Permission Required:</strong> {permissionCheckResult.permission_required}</div>
                    <div><strong>Scope Checked:</strong> {permissionCheckResult.scope_checked}</div>
                    <div><strong>Reason:</strong> {permissionCheckResult.reason}</div>
                    <div><strong>How to Request Access:</strong> {permissionCheckResult.how_to_request_access}</div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Governance Access Audit</CardTitle>
              <CardDescription>Audit log of governance access events</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                {auditEvents.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No audit events found</p>
                ) : (
                  auditEvents.slice(0, 20).map((event: any, i: number) => (
                    <div key={i} className="p-3 border rounded">
                      <div className="flex items-center justify-between">
                        <div className="font-medium">{event.event_type}</div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(event.timestamp).toLocaleString()}
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground mt-1">
                        Actor: {event.actor_id}
                        {event.metadata?.target_user_id && ` • Target: ${event.metadata.target_user_id}`}
                      </div>
                      {event.reason && (
                        <div className="text-sm text-muted-foreground mt-1">
                          Reason: {event.reason}
                        </div>
                      )}
                      {event.metadata?.decision && (
                        <Badge variant={event.metadata.decision === 'ALLOWED' ? 'default' : 'destructive'} className="mt-2">
                          {event.metadata.decision}
                        </Badge>
                      )}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>My Governance Notifications</CardTitle>
              <CardDescription>Your governance notifications and alerts</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2 items-center">
                <Filter className="w-4 h-4" />
                <select
                  className="p-2 border rounded"
                  value={notificationFilterSeverity}
                  onChange={(e) => setNotificationFilterSeverity(e.target.value)}
                >
                  <option value="ALL">All Severities</option>
                  <option value="CRITICAL">Critical</option>
                  <option value="HIGH">High</option>
                  <option value="WARNING">Warning</option>
                  <option value="INFO">Info</option>
                </select>
                <select
                  className="p-2 border rounded"
                  value={notificationFilterRead}
                  onChange={(e) => setNotificationFilterRead(e.target.value)}
                >
                  <option value="ALL">All Status</option>
                  <option value="UNREAD">Unread</option>
                  <option value="READ">Read</option>
                </select>
              </div>
              
              {notifications.length === 0 ? (
                <p className="text-sm text-muted-foreground">No notifications found</p>
              ) : (
                <div className="space-y-2">
                  {notifications
                    .filter((n: any) => 
                      (notificationFilterSeverity === 'ALL' || n.severity === notificationFilterSeverity) &&
                      (notificationFilterRead === 'ALL' || n.status === notificationFilterRead)
                    )
                    .map((notification: any) => (
                      <div key={notification.id} className={`p-4 border rounded ${notification.status === 'UNREAD' ? 'bg-blue-50' : ''}`}>
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <Badge variant={
                                notification.severity === 'CRITICAL' ? 'destructive' :
                                notification.severity === 'HIGH' ? 'destructive' :
                                notification.severity === 'WARNING' ? 'secondary' : 'outline'
                              }>
                                {notification.severity}
                              </Badge>
                              <Badge variant="outline">{notification.notification_type}</Badge>
                              {notification.status === 'UNREAD' && (
                                <Badge variant="default">Unread</Badge>
                              )}
                            </div>
                            <div className="font-medium">{notification.title}</div>
                            <div className="text-sm text-muted-foreground mt-1">{notification.message}</div>
                            {notification.repository_id && (
                              <div className="text-xs text-muted-foreground mt-1">Repository: {notification.repository_id}</div>
                            )}
                            <div className="text-xs text-muted-foreground mt-1">
                              {new Date(notification.created_at).toLocaleString()}
                            </div>
                          </div>
                          <div className="flex gap-2">
                            {notification.status === 'UNREAD' && (
                              <Button variant="outline" size="sm" onClick={() => markNotificationRead(notification.id)}>
                                <Check className="w-4 h-4 mr-1" />
                                Mark Read
                              </Button>
                            )}
                            <Button variant="outline" size="sm" onClick={() => dismissNotification(notification.id)}>
                              <X className="w-4 h-4 mr-1" />
                              Dismiss
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Notification Preferences</CardTitle>
              <CardDescription>Configure your notification settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {notificationPreferences.length === 0 ? (
                <p className="text-sm text-muted-foreground">No preferences configured</p>
              ) : (
                <div className="space-y-2">
                  {notificationPreferences.map((pref: any) => (
                    <div key={pref.id} className="p-3 border rounded flex items-center justify-between">
                      <div>
                        <div className="font-medium">{pref.notification_type}</div>
                        <div className="text-sm text-muted-foreground">
                          Enabled: {pref.enabled ? 'Yes' : 'No'} • Min Severity: {pref.minimum_severity}
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => updateNotificationPreference(pref.notification_type, !pref.enabled, pref.minimum_severity)}
                      >
                        {pref.enabled ? 'Disable' : 'Enable'}
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Notification Scans</CardTitle>
              <CardDescription>Run manual scans to create notifications</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => runScan('exceptions')}>
                  Scan Exception Expiry
                </Button>
                <Button variant="outline" onClick={() => runScan('role-expiry')}>
                  Scan Role Expiry
                </Button>
                <Button variant="outline" onClick={() => runScan('compliance')}>
                  Scan Compliance Drops
                </Button>
              </div>
              
              {scanResults && (
                <div className="p-4 border rounded bg-blue-50">
                  <div className="font-medium mb-2">Scan Results: {scanResults.scan_type}</div>
                  <div className="text-sm space-y-1">
                    <div>Notifications Created: {scanResults.notifications_created}</div>
                    {scanResults.details && (
                      <>
                        {scanResults.details.expiring_soon && (
                          <div>Expiring Soon: {scanResults.details.expiring_soon.length}</div>
                        )}
                        {scanResults.details.expired && (
                          <div>Expired: {scanResults.details.expired.length}</div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {canViewOrgNotifications && (
            <Card>
              <CardHeader>
                <CardTitle>Workspace Notifications</CardTitle>
                <CardDescription>View all notifications across the workspace (Admin View)</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2 items-center flex-wrap">
                  <Filter className="w-4 h-4" />
                  <select
                    className="p-2 border rounded"
                    value={orgNotificationFilterRecipient}
                    onChange={(e) => setOrgNotificationFilterRecipient(e.target.value)}
                  >
                    <option value="ALL">All Recipients</option>
                    {Array.from(new Set(organizationNotifications.map((n: any) => n.recipient_user_id))).map((recipient) => (
                      <option key={recipient} value={recipient}>{recipient}</option>
                    ))}
                  </select>
                  <select
                    className="p-2 border rounded"
                    value={orgNotificationFilterSeverity}
                    onChange={(e) => setOrgNotificationFilterSeverity(e.target.value)}
                  >
                    <option value="ALL">All Severities</option>
                    <option value="CRITICAL">Critical</option>
                    <option value="HIGH">High</option>
                    <option value="WARNING">Warning</option>
                    <option value="INFO">Info</option>
                  </select>
                  <select
                    className="p-2 border rounded"
                    value={orgNotificationFilterType}
                    onChange={(e) => setOrgNotificationFilterType(e.target.value)}
                  >
                    <option value="ALL">All Types</option>
                    {Array.from(new Set(organizationNotifications.map((n: any) => n.notification_type))).map((type) => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                  <select
                    className="p-2 border rounded"
                    value={orgNotificationFilterStatus}
                    onChange={(e) => setOrgNotificationFilterStatus(e.target.value)}
                  >
                    <option value="ALL">All Status</option>
                    <option value="UNREAD">Unread</option>
                    <option value="READ">Read</option>
                    <option value="DISMISSED">Dismissed</option>
                  </select>
                </div>
                
                {organizationNotifications.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No workspace notifications found</p>
                ) : (
                  <div className="space-y-2">
                    {organizationNotifications
                      .filter((n: any) => 
                        (orgNotificationFilterRecipient === 'ALL' || n.recipient_user_id === orgNotificationFilterRecipient) &&
                        (orgNotificationFilterSeverity === 'ALL' || n.severity === orgNotificationFilterSeverity) &&
                        (orgNotificationFilterType === 'ALL' || n.notification_type === orgNotificationFilterType) &&
                        (orgNotificationFilterStatus === 'ALL' || n.status === orgNotificationFilterStatus)
                      )
                      .map((notification: any) => (
                        <div key={notification.id} className="p-4 border rounded">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <Badge variant={
                                  notification.severity === 'CRITICAL' ? 'destructive' :
                                  notification.severity === 'HIGH' ? 'destructive' :
                                  notification.severity === 'WARNING' ? 'secondary' : 'outline'
                                }>
                                  {notification.severity}
                                </Badge>
                                <Badge variant="outline">{notification.notification_type}</Badge>
                                <Badge variant={notification.status === 'UNREAD' ? 'default' : 'secondary'}>
                                  {notification.status}
                                </Badge>
                              </div>
                              <div className="font-medium">{notification.title}</div>
                              <div className="text-sm text-muted-foreground mt-1">{notification.message}</div>
                              <div className="text-xs text-muted-foreground mt-1">
                                Recipient: {notification.recipient_user_id}
                              </div>
                              {notification.repository_id && (
                                <div className="text-xs text-muted-foreground">Repository: {notification.repository_id}</div>
                              )}
                              {notification.source_entity_type && (
                                <div className="text-xs text-muted-foreground">
                                  Source: {notification.source_entity_type} {notification.source_entity_id && `(${notification.source_entity_id})`}
                                </div>
                              )}
                              <div className="text-xs text-muted-foreground mt-1">
                                {new Date(notification.created_at).toLocaleString()}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="security" className="space-y-6">
          {accessDenied && (
            <Card className="border-yellow-500 bg-yellow-50">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-yellow-800">
                  <AlertTriangle className="w-5 h-5" />
                  <span className="font-medium">Access Denied</span>
                </div>
                <p className="text-sm text-yellow-700 mt-1">{accessDenied}</p>
              </CardContent>
            </Card>
          )}

          {/* Security Posture */}
          <Card>
            <CardHeader>
              <CardTitle>Security Posture</CardTitle>
              <CardDescription>Advisory security score and findings (does not affect quality gates or release decisions)</CardDescription>
            </CardHeader>
            <CardContent>
              {securityPosture ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="p-4 border rounded">
                      <div className="text-sm text-muted-foreground">Security Score</div>
                      <div className="text-3xl font-bold">{securityPosture.security_score}/100</div>
                      <div className={`text-sm ${securityPosture.security_grade === 'A' ? 'text-green-600' : securityPosture.security_grade === 'B' ? 'text-blue-600' : securityPosture.security_grade === 'C' ? 'text-yellow-600' : 'text-red-600'}`}>
                        Grade: {securityPosture.security_grade}
                      </div>
                    </div>
                    <div className="p-4 border rounded">
                      <div className="text-sm text-muted-foreground">Privileged Roles</div>
                      <div className="text-2xl font-bold">{securityPosture.privileged_roles}</div>
                    </div>
                    <div className="p-4 border rounded">
                      <div className="text-sm text-muted-foreground">Expired Roles</div>
                      <div className="text-2xl font-bold text-red-600">{securityPosture.expired_roles}</div>
                    </div>
                    <div className="p-4 border rounded">
                      <div className="text-sm text-muted-foreground">Stale Roles</div>
                      <div className="text-2xl font-bold text-yellow-600">{securityPosture.stale_roles}</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="p-4 border rounded">
                      <div className="text-sm text-muted-foreground">Inactive Roles</div>
                      <div className="text-2xl font-bold">{securityPosture.inactive_roles}</div>
                    </div>
                    <div className="p-4 border rounded">
                      <div className="text-sm text-muted-foreground">Open Reviews</div>
                      <div className="text-2xl font-bold">{securityPosture.open_reviews}</div>
                    </div>
                    <div className="p-4 border rounded">
                      <div className="text-sm text-muted-foreground">Permission Denials (7d)</div>
                      <div className="text-2xl font-bold text-orange-600">{securityPosture.permission_denials_7d}</div>
                    </div>
                    <div className="p-4 border rounded">
                      <div className="text-sm text-muted-foreground">Self-Approval Blocks (7d)</div>
                      <div className="text-2xl font-bold text-orange-600">{securityPosture.self_approval_attempts_7d}</div>
                    </div>
                  </div>
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-800">
                    <strong>Advisory Only:</strong> This security score is for monitoring purposes only. It does not affect quality gates, release decisions, recommendation health, or GitHub status checks.
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Loading security posture...</p>
              )}
            </CardContent>
          </Card>

          {/* Access Reviews */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Access Reviews</CardTitle>
                  <CardDescription>Periodic reviews of role assignments and access patterns</CardDescription>
                </div>
                <Button onClick={() => setShowCreateReview(true)}>
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Create Review
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {showCreateReview && (
                <div className="p-4 border rounded mb-4 space-y-4">
                  <div>
                    <label className="text-sm font-medium">Review Name</label>
                    <input
                      type="text"
                      className="w-full p-2 border rounded mt-1"
                      value={newReviewName}
                      onChange={(e) => setNewReviewName(e.target.value)}
                      placeholder="Q1 2026 Access Review"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Review Type</label>
                    <select
                      className="w-full p-2 border rounded mt-1"
                      value={newReviewType}
                      onChange={(e) => setNewReviewType(e.target.value)}
                    >
                      <option value="QUARTERLY_ACCESS_REVIEW">Quarterly Access Review</option>
                      <option value="PRIVILEGED_ROLE_REVIEW">Privileged Role Review</option>
                      <option value="EXPIRED_ROLE_REVIEW">Expired Role Review</option>
                      <option value="REPOSITORY_SCOPE_REVIEW">Repository Scope Review</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium">Period Start</label>
                      <input
                        type="datetime-local"
                        className="w-full p-2 border rounded mt-1"
                        value={newReviewPeriodStart}
                        onChange={(e) => setNewReviewPeriodStart(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Period End</label>
                      <input
                        type="datetime-local"
                        className="w-full p-2 border rounded mt-1"
                        value={newReviewPeriodEnd}
                        onChange={(e) => setNewReviewPeriodEnd(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button onClick={createAccessReview}>Create Review</Button>
                    <Button variant="outline" onClick={() => setShowCreateReview(false)}>Cancel</Button>
                  </div>
                </div>
              )}

              {selectedReview ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 border rounded bg-muted">
                    <div>
                      <div className="font-medium">{selectedReview.review_name}</div>
                      <div className="text-sm text-muted-foreground">
                        {selectedReview.review_type} • Status: {selectedReview.status}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={() => setSelectedReview(null)}>Back to List</Button>
                      {selectedReview.status === 'DRAFT' || selectedReview.status === 'IN_PROGRESS' ? (
                        <>
                          <Button size="sm" onClick={() => completeReview(selectedReview.id)}>Complete Review</Button>
                          <Button variant="outline" size="sm" onClick={() => cancelReview(selectedReview.id)}>Cancel</Button>
                        </>
                      ) : null}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <h3 className="font-medium">Review Findings</h3>
                    {reviewItems.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No findings in this review</p>
                    ) : (
                      reviewItems.map((item) => (
                        <div key={item.id} className="p-4 border rounded">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <Badge variant={
                                  item.risk_level === 'CRITICAL' ? 'destructive' :
                                  item.risk_level === 'HIGH' ? 'destructive' :
                                  item.risk_level === 'MEDIUM' ? 'secondary' : 'outline'
                                }>
                                  {item.risk_level}
                                </Badge>
                                <Badge variant="outline">{item.finding_type}</Badge>
                                <Badge variant={item.review_status === 'PENDING' ? 'default' : 'secondary'}>
                                  {item.review_status}
                                </Badge>
                              </div>
                              <div className="font-medium">{item.finding_message}</div>
                              <div className="text-sm text-muted-foreground mt-1">
                                User: {item.user_id} • Role: {item.role} • Scope: {item.scope_type}
                              </div>
                              {item.repository_id && (
                                <div className="text-sm text-muted-foreground">Repository: {item.repository_id}</div>
                              )}
                              <div className="text-sm text-muted-foreground mt-1">
                                Recommendation: {item.recommendation}
                              </div>
                            </div>
                          </div>
                          {item.review_status === 'PENDING' && (
                            <div className="mt-3 p-3 border rounded space-y-2">
                              <div className="text-sm font-medium">Advisory Decision (Manual Action Required)</div>
                              <select
                                className="w-full p-2 border rounded"
                                value={itemDecision}
                                onChange={(e) => setItemDecision(e.target.value)}
                              >
                                <option value="">Select decision...</option>
                                <option value="APPROVED">Approved - Access is appropriate</option>
                                <option value="REVOKE_RECOMMENDED">Revoke Recommended - Manual admin action required</option>
                                <option value="CHANGE_SCOPE_RECOMMENDED">Change Scope Recommended - Manual admin action required</option>
                                <option value="ACKNOWLEDGED">Acknowledged - Finding noted, no action needed</option>
                              </select>
                              <input
                                type="text"
                                className="w-full p-2 border rounded"
                                placeholder="Decision reason (optional)"
                                value={itemDecisionReason}
                                onChange={(e) => setItemDecisionReason(e.target.value)}
                              />
                              <Button size="sm" onClick={() => updateItemDecision(item.id)}>Submit Decision</Button>
                              <div className="text-xs text-muted-foreground">
                                Note: Decisions are advisory only. Roles are not automatically revoked or changed.
                              </div>
                            </div>
                          )}
                          {item.review_status !== 'PENDING' && (
                            <div className="mt-2 text-sm text-muted-foreground flex flex-col gap-2">
                              <div>
                                Decision: {item.review_status} by {item.reviewed_by} on {new Date(item.reviewed_at).toLocaleString()}
                                {item.decision_reason && ` - ${item.decision_reason}`}
                              </div>
                              {(item.review_status === 'REVOKE_RECOMMENDED' || item.review_status === 'CHANGE_SCOPE_RECOMMENDED') && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="w-fit"
                                  onClick={() => {
                                    setCreateActionType(item.review_status === 'REVOKE_RECOMMENDED' ? 'REVOKE_ROLE' : 'CHANGE_ROLE_SCOPE');
                                    setCreateActionTargetUserId(item.user_id);
                                    setCreateActionTargetRole(item.role);
                                    // Find role assignment id by matching user and role if possible
                                    const matchingAssign = roleAssignments.find(
                                      ra => ra.user_id === item.user_id && ra.role === item.role
                                    );
                                    if (matchingAssign) {
                                      setCreateActionTargetAssignmentId(matchingAssign.id);
                                    }
                                    setCreateActionSourceType("ACCESS_REVIEW_ITEM");
                                    setCreateActionSourceId(item.id);
                                    setShowCreateAction(true);
                                    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
                                  }}
                                >
                                  <Shield className="w-4 h-4 mr-2 text-red-500" />
                                  Initiate Remediation Workflow
                                </Button>
                              )}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  {accessReviews.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No access reviews found</p>
                  ) : (
                    accessReviews.map((review) => (
                      <div key={review.id} className="flex items-center justify-between p-4 border rounded">
                        <div className="flex-1">
                          <div className="font-medium">{review.review_name}</div>
                          <div className="text-sm text-muted-foreground">
                            {review.review_type} • Status: {review.status}
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            Created: {new Date(review.created_at).toLocaleString()}
                            {review.completed_at && ` • Completed: ${new Date(review.completed_at).toLocaleString()}`}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm" onClick={() => openReview(review.id)}>Open Review</Button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Security Signals */}
          <Card>
            <CardHeader>
              <CardTitle>Security Signals</CardTitle>
              <CardDescription>Advisory abuse indicators detected from audit logs</CardDescription>
            </CardHeader>
            <CardContent>
              {securitySignals ? (
                <div className="space-y-2">
                  {securitySignals.signals.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No security signals detected</p>
                  ) : (
                    securitySignals.signals.map((signal: any, index: number) => (
                      <div key={index} className="p-4 border rounded">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant={
                            signal.severity === 'HIGH' ? 'destructive' :
                            signal.severity === 'MEDIUM' ? 'secondary' : 'outline'
                          }>
                            {signal.severity}
                          </Badge>
                          <Badge variant="outline">{signal.signal_type}</Badge>
                        </div>
                        <div className="font-medium">{signal.description}</div>
                        <div className="text-sm text-muted-foreground mt-1">
                          Recommendation: {signal.recommendation}
                        </div>
                        {signal.affected_user_id && (
                          <div className="text-sm text-muted-foreground">User: {signal.affected_user_id}</div>
                        )}
                        {signal.count && (
                          <div className="text-sm text-muted-foreground">Count: {signal.count}</div>
                        )}
                        <div className="text-xs text-muted-foreground mt-1">
                          Detected: {new Date(signal.detected_at).toLocaleString()}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Loading security signals...</p>
              )}
            </CardContent>
          </Card>

          {/* Governance Remediation Actions */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Governance Remediation Center</CardTitle>
                  <CardDescription>Controlled manual workflows for executing policy and role remediations</CardDescription>
                </div>
                <Button onClick={() => setShowCreateAction(!showCreateAction)}>
                  <Shield className="w-4 h-4 mr-2" />
                  {showCreateAction ? "Hide Form" : "Create Remediation"}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
                <div className="p-3 border rounded text-center">
                  <div className="text-xs text-muted-foreground">Total Actions</div>
                  <div className="text-xl font-bold">{remediationSummary.total}</div>
                </div>
                <div className="p-3 border rounded text-center bg-gray-50">
                  <div className="text-xs text-muted-foreground">Pending Preview</div>
                  <div className="text-xl font-bold text-blue-600">
                    {remediationSummary.draft || 0}
                  </div>
                </div>
                <div className="p-3 border rounded text-center bg-yellow-50/50">
                  <div className="text-xs text-muted-foreground">Pending Confirm</div>
                  <div className="text-xl font-bold text-yellow-600">
                    {remediationSummary.pending_confirmation}
                  </div>
                </div>
                <div className="p-3 border rounded text-center bg-yellow-50">
                  <div className="text-xs text-muted-foreground">Confirmed</div>
                  <div className="text-xl font-bold text-orange-600">
                    {remediationSummary.confirmed}
                  </div>
                </div>
                <div className="p-3 border rounded text-center bg-green-50">
                  <div className="text-xs text-muted-foreground">Executed</div>
                  <div className="text-xl font-bold text-green-600">
                    {remediationSummary.executed}
                  </div>
                </div>
                <div className="p-3 border rounded text-center bg-red-50">
                  <div className="text-xs text-muted-foreground">Failed</div>
                  <div className="text-xl font-bold text-red-600">
                    {remediationSummary.failed}
                  </div>
                </div>
              </div>

              {/* Action Creator Form */}
              {showCreateAction && (
                <div className="p-4 border rounded bg-muted/30 space-y-4">
                  <h3 className="font-semibold text-sm">Create Manual Remediation Action</h3>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-medium">Remediation Action Type</label>
                      <select
                        className="w-full p-2 border rounded mt-1 text-sm bg-white"
                        value={createActionType}
                        onChange={(e) => {
                          setCreateActionType(e.target.value);
                          setCreateActionTargetAssignmentId("");
                          setCreateActionTargetExceptionId("");
                          setCreateActionRepoId("");
                        }}
                      >
                        <option value="REVOKE_ROLE">Revoke Role Assignment</option>
                        <option value="CHANGE_ROLE_SCOPE">Change Role Assignment Scope</option>
                        <option value="EXTEND_ROLE_EXPIRY">Extend Role Expiry Date</option>
                        <option value="DISABLE_STALE_ROLE">Disable Stale Role Assignment</option>
                        <option value="REMOVE_REPOSITORY_POLICY_OVERRIDE">Remove Repository Policy Override</option>
                        <option value="REVOKE_POLICY_EXCEPTION">Revoke Policy Exception</option>
                        <option value="EXPIRE_POLICY_EXCEPTION">Expire Policy Exception</option>
                      </select>
                    </div>

                    {(createActionType === "REVOKE_ROLE" || createActionType === "CHANGE_ROLE_SCOPE" || createActionType === "EXTEND_ROLE_EXPIRY" || createActionType === "DISABLE_STALE_ROLE") && (
                      <div>
                        <label className="text-xs font-medium">Select Target Role Assignment</label>
                        <select
                          className="w-full p-2 border rounded mt-1 text-sm bg-white"
                          value={createActionTargetAssignmentId}
                          onChange={(e) => {
                            const val = e.target.value;
                            setCreateActionTargetAssignmentId(val);
                            const match = roleAssignments.find(ra => ra.id === val);
                            if (match) {
                              setCreateActionTargetUserId(match.user_id);
                              setCreateActionTargetRole(match.role);
                              setCreateActionRepoId(match.repository_id || "");
                            }
                          }}
                        >
                          <option value="">-- Choose active role --</option>
                          {roleAssignments.map(ra => (
                            <option key={ra.id} value={ra.id}>
                              User: {ra.user_id.slice(0, 8)}... | {ra.role} | {ra.scope_type} {ra.repository_id ? `(Repo: ${ra.repository_id.slice(0, 8)}...)` : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}

                    {(createActionType === "REVOKE_POLICY_EXCEPTION" || createActionType === "EXPIRE_POLICY_EXCEPTION") && (
                      <div>
                        <label className="text-xs font-medium">Select Target Exception</label>
                        <select
                          className="w-full p-2 border rounded mt-1 text-sm bg-white"
                          value={createActionTargetExceptionId}
                          onChange={(e) => {
                            const val = e.target.value;
                            setCreateActionTargetExceptionId(val);
                            const match = exceptions.find(ex => ex.id === val);
                            if (match) {
                              setCreateActionRepoId(match.repository_id);
                            }
                          }}
                        >
                          <option value="">-- Choose approved policy exception --</option>
                          {exceptions.filter(ex => ex.status === 'APPROVED').map(ex => (
                            <option key={ex.id} value={ex.id}>
                              Repo: {ex.repository_id.slice(0, 8)}... | Reason: {ex.reason.slice(0, 30)}...
                            </option>
                          ))}
                        </select>
                      </div>
                    )}

                    {createActionType === "REMOVE_REPOSITORY_POLICY_OVERRIDE" && (
                      <div>
                        <label className="text-xs font-medium">Select Target Repository Policy</label>
                        <select
                          className="w-full p-2 border rounded mt-1 text-sm bg-white"
                          value={createActionRepoId}
                          onChange={(e) => {
                            setCreateActionRepoId(e.target.value);
                            setCreateActionTargetPolicyId(e.target.value); // Maps to repo id or override policy id
                          }}
                        >
                          <option value="">-- Choose repository override policy --</option>
                          {repositories.filter(repo => repo.policy_source === "REPOSITORY_OVERRIDE").map(repo => (
                            <option key={repo.repository_id} value={repo.repository_id}>
                              {repo.repository_name} (Preset: {repo.current_preset || "CUSTOM"})
                            </option>
                          ))}
                        </select>
                      </div>
                    )}

                    {createActionType === "CHANGE_ROLE_SCOPE" && (
                      <div>
                        <label className="text-xs font-medium">New Scope Role (Optional)</label>
                        <select
                          className="w-full p-2 border rounded mt-1 text-sm bg-white"
                          value={createActionTargetRole}
                          onChange={(e) => setCreateActionTargetRole(e.target.value)}
                        >
                          <option value="GOVERNANCE_OWNER">Governance Owner</option>
                          <option value="POLICY_ADMIN">Policy Admin</option>
                          <option value="EXCEPTION_APPROVER">Exception Approver</option>
                          <option value="REPOSITORY_POLICY_MANAGER">Repository Policy Manager</option>
                          <option value="GOVERNANCE_VIEWER">Governance Viewer</option>
                        </select>
                      </div>
                    )}
                  </div>

                  <div>
                    <label className="text-xs font-medium">Custom Confirmation Details / Rationale</label>
                    <input
                      type="text"
                      className="w-full p-2 border rounded mt-1 text-sm bg-white"
                      placeholder="Why is this remediation action necessary?"
                      value={createActionConfirmationMessage}
                      onChange={(e) => setCreateActionConfirmationMessage(e.target.value)}
                    />
                  </div>

                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => {
                        const payload: any = {
                          source_type: createActionSourceType,
                          source_id: createActionSourceId || undefined,
                          action_type: createActionType,
                          confirmation_message: createActionConfirmationMessage || undefined
                        };
                        if (createActionTargetAssignmentId) payload.target_assignment_id = createActionTargetAssignmentId;
                        if (createActionTargetExceptionId) payload.target_exception_id = createActionTargetExceptionId;
                        if (createActionTargetPolicyId) payload.target_policy_id = createActionTargetPolicyId;
                        if (createActionRepoId) payload.repository_id = createActionRepoId;
                        if (createActionTargetUserId) payload.target_user_id = createActionTargetUserId;
                        if (createActionTargetRole) payload.target_role = createActionTargetRole;

                        handleCreateRemediationAction(payload);
                      }}
                      disabled={
                        (createActionType.includes("ROLE") && !createActionTargetAssignmentId) ||
                        (createActionType.includes("EXCEPTION") && !createActionTargetExceptionId) ||
                        (createActionType === "REMOVE_REPOSITORY_POLICY_OVERRIDE" && !createActionRepoId)
                      }
                    >
                      Create Draft Action
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setShowCreateAction(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {/* Actions List Filters */}
              <div className="flex gap-2 items-center">
                <Filter className="w-4 h-4 text-muted-foreground" />
                <select
                  className="p-1.5 border rounded text-xs bg-white"
                  value={filterRemediationStatus}
                  onChange={(e) => setFilterRemediationStatus(e.target.value)}
                >
                  <option value="ALL">All Statuses</option>
                  <option value="DRAFT">Draft</option>
                  <option value="PENDING_CONFIRMATION">Pending Confirmation</option>
                  <option value="CONFIRMED">Confirmed</option>
                  <option value="EXECUTED">Executed</option>
                  <option value="FAILED">Failed</option>
                  <option value="CANCELLED">Cancelled</option>
                </select>

                <select
                  className="p-1.5 border rounded text-xs bg-white"
                  value={filterRemediationType}
                  onChange={(e) => setFilterRemediationType(e.target.value)}
                >
                  <option value="ALL">All Action Types</option>
                  <option value="REVOKE_ROLE">Revoke Role</option>
                  <option value="CHANGE_ROLE_SCOPE">Change Scope</option>
                  <option value="EXTEND_ROLE_EXPIRY">Extend Expiry</option>
                  <option value="DISABLE_STALE_ROLE">Disable Stale Role</option>
                  <option value="REMOVE_REPOSITORY_POLICY_OVERRIDE">Remove Policy Override</option>
                  <option value="REVOKE_POLICY_EXCEPTION">Revoke Exception</option>
                  <option value="EXPIRE_POLICY_EXCEPTION">Expire Exception</option>
                </select>
              </div>

              {/* Actions Table */}
              <div className="border rounded overflow-hidden">
                <table className="w-full text-left text-sm">
                  <thead className="bg-muted text-xs font-semibold uppercase text-muted-foreground border-b">
                    <tr>
                      <th className="p-3">Action Details</th>
                      <th className="p-3">Type</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Requested</th>
                      <th className="p-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {remediationActions.filter(a => {
                      if (filterRemediationStatus !== "ALL" && a.status !== filterRemediationStatus) return false;
                      if (filterRemediationType !== "ALL" && a.action_type !== filterRemediationType) return false;
                      return true;
                    }).length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-6 text-center text-muted-foreground">
                          No remediation actions found matching filters.
                        </td>
                      </tr>
                    ) : (
                      remediationActions.filter(a => {
                        if (filterRemediationStatus !== "ALL" && a.status !== filterRemediationStatus) return false;
                        if (filterRemediationType !== "ALL" && a.action_type !== filterRemediationType) return false;
                        return true;
                      }).map((action) => (
                        <tr key={action.id} className="hover:bg-muted/30">
                          <td className="p-3">
                            <div className="font-semibold text-xs">{action.action_type}</div>
                            <div className="text-xs text-muted-foreground mt-0.5">
                              {action.target_user_id && `Target User: ${action.target_user_id.slice(0, 8)}...`}
                              {action.target_role && ` | Target Role: ${action.target_role}`}
                              {action.repository_id && ` | Repo: ${action.repository_id.slice(0, 8)}...`}
                            </div>
                          </td>
                          <td className="p-3">
                            <Badge variant="outline" className="text-[10px]">
                              {action.source_type}
                            </Badge>
                          </td>
                          <td className="p-3">
                            <Badge
                              variant={
                                action.status === "EXECUTED" ? "default" :
                                action.status === "FAILED" ? "destructive" :
                                action.status === "PENDING_CONFIRMATION" ? "secondary" : "outline"
                              }
                              className="text-[10px]"
                            >
                              {action.status}
                            </Badge>
                          </td>
                          <td className="p-3 text-xs text-muted-foreground">
                            {new Date(action.requested_at).toLocaleDateString()}
                          </td>
                          <td className="p-3 text-right">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setSelectedAction(action)}
                            >
                              Inspect
                            </Button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Action Inspector Drawer / Modal */}
              {selectedAction && (
                <Card className="border-2 border-primary bg-muted/10">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-bold flex items-center gap-2">
                        <Shield className="w-4 h-4 text-primary" />
                        Remediation Action Inspector
                      </CardTitle>
                      <Button size="sm" variant="ghost" onClick={() => setSelectedAction(null)}>
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4 text-xs">
                    <div className="grid grid-cols-2 gap-4 border-b pb-3">
                      <div>
                        <div className="font-semibold text-muted-foreground">Action Type</div>
                        <div className="font-medium mt-0.5">{selectedAction.action_type}</div>
                      </div>
                      <div>
                        <div className="font-semibold text-muted-foreground">Status</div>
                        <div className="font-medium mt-0.5">
                          <Badge variant="outline">{selectedAction.status}</Badge>
                        </div>
                      </div>
                      <div>
                        <div className="font-semibold text-muted-foreground">Requested By</div>
                        <div className="font-medium mt-0.5">{selectedAction.requested_by}</div>
                      </div>
                      <div>
                        <div className="font-semibold text-muted-foreground">Requested At</div>
                        <div className="font-medium mt-0.5">
                          {new Date(selectedAction.requested_at).toLocaleString()}
                        </div>
                      </div>
                    </div>

                    {selectedAction.confirmation_message && (
                      <div className="p-2 border bg-amber-50 border-amber-200 text-amber-900 rounded">
                        <strong>Confirmation Note:</strong> {selectedAction.confirmation_message}
                      </div>
                    )}

                    {selectedAction.failure_reason && (
                      <div className="p-2 border bg-red-50 border-red-200 text-red-900 rounded">
                        <strong>Execution Failure Reason:</strong> {selectedAction.failure_reason}
                      </div>
                    )}

                    {/* Impact Preview Data */}
                    {selectedAction.impact_preview_json && Object.keys(selectedAction.impact_preview_json).length > 0 && (
                      <div className="space-y-2 border-t pt-3">
                        <h4 className="font-bold text-muted-foreground uppercase text-[10px]">Impact Preview</h4>
                        <div className="p-3 border rounded bg-white font-mono space-y-2">
                          <div className="grid grid-cols-2 border-b pb-1 mb-1 font-bold text-muted-foreground">
                            <div>Property</div>
                            <div>Value</div>
                          </div>
                          {Object.entries(selectedAction.impact_preview_json).map(([key, val]: [string, any]) => (
                            <div key={key} className="grid grid-cols-2 border-b pb-1 last:border-0">
                              <div className="text-muted-foreground">{key}</div>
                              <div>{typeof val === 'object' ? JSON.stringify(val) : String(val)}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Safety warnings */}
                    <div className="p-3 border bg-blue-50/50 border-blue-200 text-blue-800 rounded space-y-1">
                      <div className="font-bold flex items-center gap-1">
                        <AlertTriangle className="w-3.5 h-3.5 text-blue-600" />
                        Configuration Safety Disclaimer
                      </div>
                      <p>
                        This manual workflow only mutates the target configuration parameters (e.g. role access, exception expiry, policy presets). It does not alter historical quality gate evidence, recommendations health indexes, or GitHub checks publishing logs.
                      </p>
                    </div>

                    {/* Stage Buttons */}
                    <div className="flex gap-2 border-t pt-3 justify-end">
                      {selectedAction.status === "DRAFT" && (
                        <>
                          <Button
                            size="sm"
                            onClick={() => handlePreviewRemediationAction(selectedAction.id)}
                          >
                            Generate Impact Preview
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleCancelRemediationAction(selectedAction.id)}
                          >
                            Cancel Action
                          </Button>
                        </>
                      )}

                      {selectedAction.status === "PENDING_CONFIRMATION" && (
                        <div className="w-full space-y-3">
                          <div className="p-3 border bg-yellow-50/50 border-yellow-200 text-yellow-800 rounded space-y-2">
                            <div className="font-bold">Explicit intent confirmation required</div>
                            <p>Please type <strong>CONFIRM</strong> in the box below to authorize this configuration change.</p>
                            <input
                              type="text"
                              className="w-full p-2 border border-yellow-300 rounded text-sm bg-white"
                              placeholder="Type CONFIRM"
                              value={confirmText}
                              onChange={(e) => setConfirmText(e.target.value)}
                            />
                          </div>
                          <div className="flex gap-2 justify-end">
                            <Button
                              size="sm"
                              disabled={confirmText !== "CONFIRM"}
                              onClick={() => handleConfirmRemediationAction(selectedAction.id)}
                            >
                              Confirm Action
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleCancelRemediationAction(selectedAction.id)}
                            >
                              Cancel Action
                            </Button>
                          </div>
                        </div>
                      )}

                      {selectedAction.status === "CONFIRMED" && (
                        <>
                          <Button
                            size="sm"
                            className="bg-green-600 hover:bg-green-700 text-white"
                            onClick={() => handleExecuteRemediationAction(selectedAction.id)}
                          >
                            Execute Remediation Now
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleCancelRemediationAction(selectedAction.id)}
                          >
                            Cancel Action
                          </Button>
                        </>
                      )}

                      {(selectedAction.status === "EXECUTED" || selectedAction.status === "FAILED" || selectedAction.status === "CANCELLED") && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setSelectedAction(null)}
                        >
                          Close Details
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}
            </CardContent>
          </Card>

          {/* Bulk Governance Remediation */}
          <Card>
            <CardHeader>
              <CardTitle>Bulk Remediation Board</CardTitle>
              <CardDescription>Run automated filters to find stale/expired records and remediate in isolated batch pipelines</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium">Bulk Remediation Strategy</label>
                <select
                  className="w-full p-2 border rounded mt-1 bg-white text-sm"
                  value={bulkRemediationType}
                  onChange={(e) => {
                    setBulkRemediationType(e.target.value);
                    setBulkPreviewItems([]);
                    setBulkExecutionResults([]);
                  }}
                >
                  <option value="expired_role_cleanup">Expired Workspace Role Cleanup</option>
                  <option value="expired_exception_cleanup">Expired Policy Exceptions Cleanup</option>
                  <option value="policy_drift_remediation">Active Policy Drift Alignment</option>
                </select>
              </div>

              <div>
                <label className="text-sm font-medium">Reason for Bulk Remediation</label>
                <input
                  type="text"
                  className="w-full p-2 border rounded mt-1 text-sm bg-white"
                  placeholder="e.g. Regular governance audit cleanup"
                  value={bulkRemediationReason}
                  onChange={(e) => setBulkRemediationReason(e.target.value)}
                />
              </div>

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handlePreviewBulkRemediation}
                  disabled={bulkRemediationLoading}
                >
                  {bulkRemediationLoading ? "Scanning..." : "Identify Targets"}
                </Button>

                {bulkPreviewItems.length > 0 && (
                  <Button
                    onClick={() => setShowBulkRemediationConfirm(true)}
                    disabled={bulkRemediationLoading}
                  >
                    Remediate Batch ({bulkPreviewItems.length} items)
                  </Button>
                )}
              </div>

              {/* Bulk Preview List */}
              {bulkPreviewItems.length > 0 && (
                <div className="space-y-2 border-t pt-3">
                  <h4 className="font-bold text-xs">Identified Targets ({bulkPreviewItems.length})</h4>
                  <div className="border rounded overflow-hidden max-h-60 overflow-y-auto">
                    <table className="w-full text-left text-xs bg-white">
                      <thead className="bg-muted text-muted-foreground border-b font-semibold">
                        <tr>
                          <th className="p-2">Target ID</th>
                          <th className="p-2">Action Type</th>
                          <th className="p-2">Details</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {bulkPreviewItems.map((item, index) => (
                          <tr key={index} className="hover:bg-muted/10">
                            <td className="p-2 font-mono">{item.target_id.slice(0, 8)}...</td>
                            <td className="p-2">{item.action_type}</td>
                            <td className="p-2 text-muted-foreground">{item.details}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Bulk Execution Results */}
              {bulkExecutionResults.length > 0 && (
                <div className="space-y-2 border-t pt-3">
                  <h4 className="font-bold text-xs text-green-700">Bulk Execution Results</h4>
                  <div className="border rounded overflow-hidden max-h-60 overflow-y-auto">
                    <table className="w-full text-left text-xs bg-white">
                      <thead className="bg-muted text-muted-foreground border-b font-semibold">
                        <tr>
                          <th className="p-2">Item ID</th>
                          <th className="p-2">Status</th>
                          <th className="p-2">Result Details</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y font-mono">
                        {bulkExecutionResults.map((res, index) => (
                          <tr key={index} className={res.success ? "bg-green-50/30 hover:bg-green-50/50" : "bg-red-50/30 hover:bg-red-50/50"}>
                            <td className="p-2">{res.item_id}</td>
                            <td className="p-2">
                              <Badge variant={res.success ? "default" : "destructive"} className="text-[10px]">
                                {res.status}
                              </Badge>
                            </td>
                            <td className="p-2 text-muted-foreground font-sans">
                              {res.success ? "Success" : `Failed: ${res.failure_reason}`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Bulk Confirmation Modal Dialog */}
              {showBulkRemediationConfirm && (
                <div className="p-4 border border-yellow-300 bg-yellow-50 rounded space-y-3 text-xs">
                  <div className="font-bold flex items-center gap-1 text-yellow-800">
                    <AlertTriangle className="w-4 h-4 text-yellow-600" />
                    Warning: Bulk Write Confirmation Required
                  </div>
                  <p className="text-yellow-700">
                    You are about to execute <strong>{bulkPreviewItems.length}</strong> manual remediation actions in a batch. Each item runs in an isolated sub-transaction: failed items will fail gracefully and write detailed audit failures without affecting successful items.
                  </p>
                  <p className="text-yellow-700 font-semibold">
                    Workspace safety limits (e.g. preventing owner lockout) will be strictly evaluated. Evidence files, recommendation builds, and check suite runs are preserved.
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={handleExecuteBulkRemediation}
                    >
                      Proceed with Batch Execution
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setShowBulkRemediationConfirm(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Evidence Pack Export */}
          <Card>
            <CardHeader>
              <CardTitle>Evidence Pack Export</CardTitle>
              <CardDescription>Export governance evidence with automatic redaction of sensitive data</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Pack Type</label>
                  <select
                    className="w-full p-2 border rounded mt-1"
                    value={evidencePackType}
                    onChange={(e) => setEvidencePackType(e.target.value)}
                  >
                    <option value="EXECUTIVE">Executive - Policy defaults, exceptions, roles, reviews</option>
                    <option value="AUDITOR">Auditor - Executive + notifications</option>
                    <option value="FULL">Full - Auditor + audit events</option>
                  </select>
                </div>
                <Button onClick={exportEvidencePack}>
                  <Download className="w-4 h-4 mr-2" />
                  Export Evidence Pack
                </Button>
                <div className="p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-800">
                  <strong>Redaction Status:</strong> Secrets, credentials, tokens, authorization headers, and connection strings are automatically redacted from all exports.
                </div>
                {evidencePack && (
                  <div className="p-4 border rounded bg-green-50">
                    <div className="font-medium text-green-800">Evidence Pack Generated</div>
                    <div className="text-sm text-green-700 mt-1">
                      Type: {evidencePack.pack_type} • Generated: {new Date(evidencePack.exported_at).toLocaleString()}
                    </div>
                    <div className="text-sm text-green-700">
                      Sections: {Object.keys(evidencePack.sections).join(', ')}
                    </div>
                    <div className="text-xs text-green-600 mt-1">
                      ✓ Secrets redacted ✓ Credentials redacted ✓ Tokens redacted ✓ Authorization headers redacted
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
