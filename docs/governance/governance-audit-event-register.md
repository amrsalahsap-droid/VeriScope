# Workspace Governance Audit Event Register

## Schema Reference
All governance audit events are written to the `WorkspaceGovernanceAuditEvent` table and contain the following fields:
* **event_type**: Event name (e.g. `GOVERNANCE_ROLE_REMEDIATION_EXECUTED`).
* **workspace_id**: UUID of the tenant workspace.
* **actor_id**: UUID of the triggering user.
* **repository_id**: Nullable UUID of the affected repository.
* **target_user_id**: Nullable UUID of the user whose role was affected.
* **permission**: Nullable name of permission required/checked.
* **role**: Nullable name of the affected role (e.g. `GOVERNANCE_OWNER`).
* **decision**: Nullable decision classification (`EXECUTED`, `DENIED`, `FAILED`, etc.).
* **reason**: Descriptive text justification.
* **audit_metadata**: JSON metadata.
* **secret_exposure_risk**: Verified NONE (Strict data scrubbing filters all sensitive fields).

---

## Audit Event Register

| Event Type | Trigger | Actor | Target | Workspace Scoped | Repository Scoped | Metadata Logged | Secret Risk |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- | :---: |
| **policy preset applied** | Preset applied to repo | Policy Admin | Repository | Yes | Yes | Preset name, previous values | NONE |
| **workspace default updated** | Workspace preset updated | Policy Admin | Workspace | Yes | No | Preset settings JSON | NONE |
| **bulk policy previewed** | Bulk operation previewed | Policy Admin | Repositories | Yes | No | Count of repos, preset name | NONE |
| **bulk policy applied** | Bulk operation executed | Policy Admin | Repositories | Yes | No | Execution counts, repo list | NONE |
| **bulk policy partial failure**| Some repos failed in bulk | Policy Admin | Repositories | Yes | No | Failed repo IDs, exceptions | NONE |
| **policy exception requested**| Exception requested | Repo Manager | Repository | Yes | Yes | Exception fields, expiry, justification | NONE |
| **policy exception approved** | Exception approved | Approver | Exception | Yes | Yes | Approver ID, justification | NONE |
| **policy exception rejected** | Exception rejected | Approver | Exception | Yes | Yes | Reject reason | NONE |
| **policy exception revoked** | Exception revoked | Approver | Exception | Yes | Yes | Revocation timestamp | NONE |
| **governance role assigned** | Role assignment created | Owner | Target User | Yes | Yes | Role, scope, expiry | NONE |
| **governance role revoked** | Role assignment revoked | Owner | Target User | Yes | Yes | Previous role, revocation reason | NONE |
| **permission checked** | Permission verified | Service | Actor | Yes | Yes | Checked permission string | NONE |
| **permission denied** | 403 Forbidden trigger | User | Route | Yes | Yes | User ID, target route | NONE |
| **self-approval blocked** | Self-approval attempted | User | Exception | Yes | Yes | User ID, exception ID | NONE |
| **notification created** | Notification generated | Worker | Recipient | Yes | Yes | Notification type | NONE |
| **notification read** | Alert marked as read | User | Notification | Yes | Yes | Notification ID | NONE |
| **notification dismissed** | Alert dismissed | User | Notification | Yes | Yes | Dismiss reason | NONE |
| **notification scan executed** | Drift or expiry scan runs | Cron/User | Workspace | Yes | No | Scan duration, count found | NONE |
| **notification preference updated** | Preferences updated | User | Preferences | Yes | No | Muted categories list | NONE |
| **governance access review created** | Review cycle started | Owner | Snapshot | Yes | No | Snap stats count | NONE |
| **access review item decided** | Decision made on item | Owner | Review Item | Yes | Yes | Recommended choice, comment | NONE |
| **access review completed** | Review cycle closed | Owner | Snapshot | Yes | No | Complete timestamp, status | NONE |
| **access review cancelled** | Review cycle aborted | Owner | Snapshot | Yes | No | Cancel reason | NONE |
| **security posture viewed** | Posture dashboard opened | Admin | Workspace | Yes | No | Viewer ID | NONE |
| **security signals viewed** | Posture signals loaded | Admin | Workspace | Yes | No | Viewer ID | NONE |
| **evidence pack exported** | Exporter triggered | Auditor | Export File | Yes | No | Template type, export hash | NONE |
| **remediation action created** | Remediation draft created | Admin | Action | Yes | Yes | Source type, action type | NONE |
| **remediation previewed** | Action preview generated | Admin | Action | Yes | Yes | Impact JSON | NONE |
| **remediation confirmed** | Confirmation submitted | Admin | Action | Yes | Yes | Confirm text validation | NONE |
| **remediation executed** | Action applied successfully | Admin | Action | Yes | Yes | Result summary | NONE |
| **remediation cancelled** | Action draft cancelled | Admin | Action | Yes | Yes | Cancel timestamp | NONE |
| **remediation failed** | Action execution failed | Admin | Action | Yes | Yes | Failure exception string | NONE |
| **bulk remediation previewed** | Bulk preview generated | Admin | Previews | Yes | No | Previews count, type | NONE |
| **bulk remediation executed** | Bulk run executed | Admin | Results | Yes | No | Execution outputs list | NONE |
| **role remediation executed** | Role change executed | Admin | Assignment | Yes | Yes | Before/after state | NONE |
| **policy remediation executed** | Policy re-align executed | Admin | Policy | Yes | Yes | Re-align values diff | NONE |
| **exception remediation executed**| Exception status updated | Admin | Exception | Yes | Yes | Expired/Revoked states | NONE |
| **governance report exported** | Analytics report exported | Admin | Report File | Yes | No | Report metadata | NONE |
| **governance review created** | Snapshot snapshot completed | Owner | Review | Yes | No | Snapshot count and score | NONE |
