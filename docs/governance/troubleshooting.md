# Workspace Governance Troubleshooting Guide

## Troubleshooting Playbooks

### 1. 403 Permission Denied
* **Likely Cause**: User lacks required RBAC role or role has expired/is inactive.
* **Checks**: Verify role status and expiration date in the Governance Roles dashboard.
* **Safe Fix**: Extend the role expiration date or reactivate the role using manual remediation.
* **Unsafe Fix to Avoid**: Editing the source DB row directly to mark active or bypassing RBAC checks.

### 2. Repository-Scoped User Cannot Access Repository
* **Likely Cause**: Role is mapped with incorrect `repository_id` or repository is not in the active workspace.
* **Checks**: Check `GovernanceRoleAssignment.repository_id` and ensure repository workspace match.
* **Safe Fix**: Update role assignment repository scope using the role edit wizard.
* **Unsafe Fix to Avoid**: Promoting the user to a workspace-wide admin role.

### 3. Workspace User Cannot See Notifications
* **Likely Cause**: Preferences are set to mute the notification type, or email/dashboard settings are disabled.
* **Checks**: View the user's notification preferences database state.
* **Safe Fix**: Guide the user to update their notifications panel settings.
* **Unsafe Fix to Avoid**: Hardcoding recipient emails in the alert service code.

### 4. Owner Cannot Disable Critical Notifications
* **Likely Cause**: The system enforces mandatory critical alerts for workspace `GOVERNANCE_OWNER` to prevent security lockouts.
* **Checks**: Confirm user's active role is `GOVERNANCE_OWNER`.
* **Safe Fix**: This is expected behavior and should not be disabled. Ensure another owner is available to split notifications.
* **Unsafe Fix to Avoid**: Modifying preference filter logic to bypass critical checks.

### 5. Access Review Item Not Generating Remediation Action
* **Likely Cause**: The access review has not been completed, or the item decision is not `REVOKE_RECOMMENDED` / `CHANGE_SCOPE_RECOMMENDED` (e.g. is `KEEP`).
* **Checks**: Check review status (must be `COMPLETED`).
* **Safe Fix**: Fully complete the access review to lock decisions and generate remediation options.
* **Unsafe Fix to Avoid**: Inserting manual draft rows in the remediation database table.

### 6. Remediation Execution Blocked
* **Likely Cause**: Action status is not `CONFIRMED` or execution user lacks required execution permission at the boundary.
* **Checks**: Check action status field (must be exactly `CONFIRMED`).
* **Safe Fix**: Ensure the action was previewed, and have an authorized user confirm it.
* **Unsafe Fix to Avoid**: Forcing status transitions using backend shell scripts.

### 7. Cannot Revoke Last Owner
* **Likely Cause**: System lockout guard blocks mutating the workspace's sole remaining `GOVERNANCE_OWNER`.
* **Checks**: Count active non-expired owners.
* **Safe Fix**: Add another workspace-level owner first, then proceed with the revocation.
* **Unsafe Fix to Avoid**: Modifying the deactivation SQL query to exclude owner checks.

### 8. Policy Remediation Does Not Affect Historical Quality Gate
* **Likely Cause**: Policy remediations only apply to future quality gate runs. Historical gate records are immutable evidence.
* **Checks**: Check quality gate run timestamps.
* **Safe Fix**: This is expected behavior. Trigger a new commit or pipeline run to run the gate with the new policy.
* **Unsafe Fix to Avoid**: Modifying past database rows in pipeline run histories.

### 9. Evidence Pack Missing Expected Section
* **Likely Cause**: Selected export type (e.g. Executive) does not include the detailed section, or target data is empty.
* **Checks**: Review the export type definition and table content.
* **Safe Fix**: Run the export using the `AUDITOR` or `FULL` pack settings.
* **Unsafe Fix to Avoid**: Manually pasting records into the exported file.

### 10. Redaction Removes Expected Field
* **Likely Cause**: Data content matches a strict security redaction pattern (e.g. contains strings like "secret", "token", or key hashes).
* **Checks**: Check if input fields contain credential keywords.
* **Safe Fix**: Rephrase the reason/justification without including credentials.
* **Unsafe Fix to Avoid**: Disabling redaction filters.

### 11. Notification Scan Creates Zero Records
* **Likely Cause**: Scan task is already running, or there is no policy drift or expiring roles in the workspace.
* **Checks**: Run diagnostics check to inspect drift presence.
* **Safe Fix**: No action needed if workspace is fully compliant.
* **Unsafe Fix to Avoid**: Faking drift logs to test dispatcher behavior.

### 12. Workspace Route Works but Organization Compatibility Route Fails
* **Likely Cause**: Organization compatibility route was not registered correctly, or workspace mapping lookup failed.
* **Checks**: Check path parameters and router setup.
* **Safe Fix**: Confirm the compatibility router routes request parameters correctly.
* **Unsafe Fix to Avoid**: Re-adding the Organization database model.
