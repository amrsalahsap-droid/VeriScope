# Workspace Governance Incident Response Guide

## Incident Playbooks

### 1. Unauthorized Governance Access Attempt
* **Symptom**: Repeated 403 Forbidden responses on governance routes for a user.
* **Where to Inspect**: **Governance Audit Logs** or database `workspace_governance_audit_events`.
* **Audit Events to Check**: Check for `event_type = 'PERMISSION_DENIED'` or `decision = 'DENIED'`.
* **Safe Manual Action**: Review the user's role assignment. If incorrect access was requested, notify security.
* **What NOT to Do**: Do not temporarily elevate user privilege to resolve the error.
* **Escalation Owner**: Workspace Security Lead.

### 2. Permission Abuse Spike
* **Symptom**: Unusually high rate of role updates or policy mutations in a short time.
* **Where to Inspect**: **Compliance Dashboard / Audit Timeline**.
* **Audit Events to Check**: `GOVERNANCE_ROLE_REMEDIATION_EXECUTED` or `GOVERNANCE_POLICY_REMEDIATION_EXECUTED`.
* **Safe Manual Action**: Deactivate the actor's role assignment manually.
* **What NOT to Do**: Do not delete audit logs to clean up entries.
* **Escalation Owner**: Workspace Owner.

### 3. Self-Approval Attempt
* **Symptom**: User tries to approve their own policy exception, generating a block error.
* **Where to Inspect**: Exception list and audit trail.
* **Audit Events to Check**: `CI_CD_POLICY_SELF_APPROVAL_BLOCKED`.
* **Safe Manual Action**: Reject the exception.
* **What NOT to Do**: Do not override settings to bypass segregation of duties.
* **Escalation Owner**: Exception Approver Lead.

### 4. Last Owner Risk
* **Symptom**: Attempt to revoke or deactivate the sole remaining workspace `GOVERNANCE_OWNER`.
* **Where to Inspect**: Active role assignments table.
* **Audit Events to Check**: `GOVERNANCE_REMEDIATION_FAILED` (containing `last active GOVERNANCE_OWNER` in metadata).
* **Safe Manual Action**: Assign another user as `GOVERNANCE_OWNER` before modifying the target's role.
* **What NOT to Do**: Do not attempt to bypass the check via direct SQL updates.
* **Escalation Owner**: IT Operations Manager.

### 5. Expired Role Access Attempt
* **Symptom**: User with expired role attempts to execute administrative actions and receives 403.
* **Where to Inspect**: Workspace active/expired role list.
* **Audit Events to Check**: Check audit events matching the user ID.
* **Safe Manual Action**: Create a remediation action to extend or reactivate the role if legitimate.
* **What NOT to Do**: Do not mutate dates directly; use manual remediation workflows.
* **Escalation Owner**: IT Operations Manager.

### 6. Inactive Role Access Attempt
* **Symptom**: User whose role was deactivated attempts administrative changes and receives 403.
* **Where to Inspect**: Role assignment state.
* **Audit Events to Check**: Permission logs for user.
* **Safe Manual Action**: Reactivate the role assignment using `REACTIVATE_ROLE` remediation.
* **What NOT to Do**: Do not assign a new duplicate role assignment without cleaning up the inactive one.
* **Escalation Owner**: IT Operations Manager.

### 7. Policy Drift Spike
* **Symptom**: Compliance score drops suddenly due to multiple repositories drifting.
* **Where to Inspect**: Repository Policy Compliance list.
* **Audit Events to Check**: `CI_CD_POLICY_DRIFT_DETECTED`.
* **Safe Manual Action**: Use bulk remediation to re-align repositories to defaults.
* **What NOT to Do**: Do not edit presets to silence drift alerts.
* **Escalation Owner**: Policy Admin Lead.

### 8. Bulk Remediation Partial Failure
* **Symptom**: Bulk run returns some failed items, leaving partial drift or stale roles.
* **Where to Inspect**: **Bulk Action Results Dashboard**.
* **Audit Events to Check**: `GOVERNANCE_BULK_REMEDIATION_EXECUTED` (check metadata for failed counts).
* **Safe Manual Action**: Inspect individual item failure reasons (e.g. invalid dates, lockouts) and remediate them one by one.
* **What NOT to Do**: Do not re-run the entire batch immediately without addressing the failure reasons.
* **Escalation Owner**: IT Operations Lead.

### 9. Evidence Pack Export Concern
* **Symptom**: Concern that sensitive data might leak in exported packs.
* **Where to Inspect**: Exported evidence JSON.
* **Audit Events to Check**: `EVIDENCE_PACK_EXPORTED`.
* **Safe Manual Action**: Confirm redaction filters are applied. Export using a different template (e.g., Executive).
* **What NOT to Do**: Do not modify/bypass redaction regex in backend config.
* **Escalation Owner**: Compliance Officer.

### 10. Notification Recipient Issue
* **Symptom**: Workspace owners are not receiving drift alerts or exception notifications.
* **Where to Inspect**: User Notification Preferences page.
* **Audit Events to Check**: `NOTIFICATION_DISPATCH_FAILED`.
* **Safe Manual Action**: Verify SMTP/mailserver configurations and check user preferences settings.
* **What NOT to Do**: Do not bypass user settings to force-spam notifications.
* **Escalation Owner**: Systems Administrator.

### 11. Audit Event Inconsistency
* **Symptom**: Gap in audit event numbers or timestamps.
* **Where to Inspect**: Audit log database tables directly.
* **Audit Events to Check**: Compare table rows against sequentially generated IDs.
* **Safe Manual Action**: Verify database replication logs and check for unauthorized SQL mutations.
* **What NOT to Do**: Do not insert mock records to fill the gaps.
* **Escalation Owner**: Database Administrator.
