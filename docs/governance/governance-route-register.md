# Workspace Governance Route Register

## Compatibility Route Policy
> [!IMPORTANT]
> **Compatibility Scoping Rule**
> Routes matching `/organizations/{workspace_id}/...` are registered for compatibility purposes only.
> * They treat the path parameter as `workspace_id` and query the `Workspace` table.
> * They must NOT query the deprecated `Organization` table.
> * They map directly to workspace-scoped actions.

---

## Route Register

| Route Group | Workspace Route | Compatibility Route | Method | Permission | Workspace Scoped | Repository Scoped | Mutates | Audit Event | Status |
| :--- | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :--- | :--- |
| **policy defaults** | `/workspaces/{workspace_id}/cicd/governance/defaults` | `/organizations/{workspace_id}/cicd/governance/defaults` | GET | `governance.policy.view` | Yes | No | No | - | Verified |
| **policy defaults** | `/workspaces/{workspace_id}/cicd/governance/defaults` | `/organizations/{workspace_id}/cicd/governance/defaults` | PUT | `governance.policy.update` | Yes | No | Yes | `GOVERNANCE_POLICY_REMEDIATION_EXECUTED` | Verified |
| **repository policies** | `/workspaces/{workspace_id}/cicd/governance/repositories/{repository_id}/policy` | `/organizations/{workspace_id}/cicd/governance/repositories/{repository_id}/policy` | GET | `governance.policy.view` | Yes | Yes | No | - | Verified |
| **repository policies** | `/workspaces/{workspace_id}/cicd/governance/repositories/{repository_id}/policy` | `/organizations/{workspace_id}/cicd/governance/repositories/{repository_id}/policy` | PUT | `governance.policy.update` | Yes | Yes | Yes | `GOVERNANCE_POLICY_REMEDIATION_EXECUTED` | Verified |
| **policy presets** | `/workspaces/{workspace_id}/cicd/governance/presets` | `/organizations/{workspace_id}/cicd/governance/presets` | GET | `governance.policy.view` | Yes | No | No | - | Verified |
| **governance analytics** | `/workspaces/{workspace_id}/cicd/governance/compliance` | `/organizations/{workspace_id}/cicd/governance/compliance` | GET | `governance.policy.view` | Yes | No | No | - | Verified |
| **executive reports** | `/workspaces/{workspace_id}/cicd/governance/reports` | `/organizations/{workspace_id}/cicd/governance/reports` | POST | `governance.policy.view` | Yes | No | Yes | `GOVERNANCE_REPORT_EXPORTED` | Verified |
| **RBAC roles** | `/workspaces/{workspace_id}/cicd/governance/roles` | `/organizations/{workspace_id}/cicd/governance/roles` | GET | `governance.roles.assign` | Yes | No | No | - | Verified |
| **RBAC roles** | `/workspaces/{workspace_id}/cicd/governance/roles` | `/organizations/{workspace_id}/cicd/governance/roles` | POST | `governance.roles.assign` | Yes | No | Yes | `GOVERNANCE_ROLE_ASSIGNED` | Verified |
| **audit events** | `/workspaces/{workspace_id}/cicd/governance/audit` | `/organizations/{workspace_id}/cicd/governance/audit` | GET | `governance.audit.view` | Yes | No | No | - | Verified |
| **notifications** | `/workspaces/{workspace_id}/cicd/governance/notifications` | `/organizations/{workspace_id}/cicd/governance/notifications` | GET | `governance.remediation.view` | Yes | No | No | - | Verified |
| **notification preferences** | `/workspaces/{workspace_id}/cicd/governance/notifications/preferences` | `/organizations/{workspace_id}/cicd/governance/notifications/preferences` | PUT | `governance.remediation.view` | Yes | No | Yes | `NOTIFICATION_PREFERENCE_UPDATED` | Verified |
| **notification scans** | `/workspaces/{workspace_id}/cicd/governance/notifications/scan` | `/organizations/{workspace_id}/cicd/governance/notifications/scan` | POST | `governance.remediation.confirm` | Yes | No | Yes | `NOTIFICATION_SCAN_EXECUTED` | Verified |
| **security posture** | `/workspaces/{workspace_id}/cicd/governance/posture` | `/organizations/{workspace_id}/cicd/governance/posture` | GET | `governance.policy.view` | Yes | No | No | - | Verified |
| **security signals** | `/workspaces/{workspace_id}/cicd/governance/posture/signals` | `/organizations/{workspace_id}/cicd/governance/posture/signals` | GET | `governance.policy.view` | Yes | No | No | - | Verified |
| **access reviews** | `/workspaces/{workspace_id}/cicd/governance/reviews` | `/organizations/{workspace_id}/cicd/governance/reviews` | GET | `governance.remediation.view` | Yes | No | No | - | Verified |
| **access reviews** | `/workspaces/{workspace_id}/cicd/governance/reviews` | `/organizations/{workspace_id}/cicd/governance/reviews` | POST | `governance.remediation.confirm` | Yes | No | Yes | `GOVERNANCE_REVIEW_SNAPSHOT_CREATED` | Verified |
| **evidence packs** | `/workspaces/{workspace_id}/cicd/governance/evidence/export` | `/organizations/{workspace_id}/cicd/governance/evidence/export` | POST | `governance.audit.view` | Yes | No | Yes | `EVIDENCE_PACK_EXPORTED` | Verified |
| **manual remediation** | `/workspaces/{workspace_id}/cicd/governance/remediation/actions` | `/organizations/{workspace_id}/cicd/governance/remediation/actions` | POST | `governance.remediation.confirm` | Yes | No | Yes | `GOVERNANCE_REMEDIATION_ACTION_CREATED` | Verified |
| **manual remediation** | `/workspaces/{workspace_id}/cicd/governance/remediation/actions/{id}/preview` | `/organizations/{workspace_id}/cicd/governance/remediation/actions/{id}/preview` | POST | `governance.remediation.preview` | Yes | No | Yes | `GOVERNANCE_REMEDIATION_PREVIEWED` | Verified |
| **manual remediation** | `/workspaces/{workspace_id}/cicd/governance/remediation/actions/{id}/confirm` | `/organizations/{workspace_id}/cicd/governance/remediation/actions/{id}/confirm` | POST | `governance.remediation.confirm` | Yes | No | Yes | `GOVERNANCE_REMEDIATION_CONFIRMED` | Verified |
| **manual remediation** | `/workspaces/{workspace_id}/cicd/governance/remediation/actions/{id}/execute` | `/organizations/{workspace_id}/cicd/governance/remediation/actions/{id}/execute` | POST | `governance.remediation.execute` | Yes | No | Yes | `GOVERNANCE_ROLE_REMEDIATION_EXECUTED` (or policy/exception) | Verified |
| **bulk remediation** | `/workspaces/{workspace_id}/cicd/governance/remediation/bulk/preview` | `/organizations/{workspace_id}/cicd/governance/remediation/bulk/preview` | POST | `governance.remediation.preview` | Yes | No | Yes | `GOVERNANCE_BULK_REMEDIATION_PREVIEWED` | Verified |
| **bulk remediation** | `/workspaces/{workspace_id}/cicd/governance/remediation/bulk/execute` | `/organizations/{workspace_id}/cicd/governance/remediation/bulk/execute` | POST | `governance.remediation.bulk_execute` | Yes | No | Yes | `GOVERNANCE_BULK_REMEDIATION_EXECUTED` | Verified |
