# Workspace Governance Manual Remediation Runbook

## Remediation Lifecycle
All manual remediation actions follow a strict state-transition path:
* **DRAFT**: The action has been created but not yet evaluated.
* **PENDING_CONFIRMATION**: Generated when `preview_remediation_action()` is called. The impact preview is stored, showing the before/after states.
* **CONFIRMED**: Transitioned when `confirm_remediation_action()` is called with the exact confirmation text "CONFIRM".
* **EXECUTED**: Transitioned when the action completes successfully.
* **FAILED**: Transitioned if the execution encounters errors or permission checks fail.
* **CANCELLED**: Transitioned if the user cancels the action (permitted from DRAFT, PENDING_CONFIRMATION, or CONFIRMED).

## Action Types
* **REVOKE_ROLE**: Disables the active role assignment.
* **CHANGE_ROLE_SCOPE**: Switches role scope between WORKSPACE and REPOSITORY (requires target repository).
* **EXTEND_ROLE_EXPIRY**: Extends the expiration date of a role by 1 year.
* **REACTIVATE_ROLE**: Re-enables a deactivated role (safely sets a 30-day default expiry if the role was expired).
* **DEACTIVATE_ROLE**: Deactivates a role assignment.
* **REMOVE_REPOSITORY_POLICY_OVERRIDE**: Deletes custom repository policy to inherit workspace defaults.
* **APPLY_WORKSPACE_DEFAULT_POLICY**: Updates repository policy settings to match workspace defaults.
* **REVOKE_EXCEPTION**: Revokes an approved policy exception immediately.
* **MARK_EXCEPTION_EXPIRED**: Updates exception status to EXPIRED.
* **ACKNOWLEDGE_FINDING**: Marks a review finding as acknowledged.
* **MARK_REMEDIATION_NOT_REQUIRED**: Dismisses finding remediation requirement.

## Required Controls

### 1. Preview Before Execution
An action cannot be executed or confirmed in `DRAFT` state. Calling the preview generates the impact analysis and transitions the action to `PENDING_CONFIRMATION`.

### 2. Typed CONFIRM Before Execution
The confirmation endpoint requires the exact string `"CONFIRM"`. Any other text (such as "yes", "true", or "confirmed") is rejected.

### 3. Service-Level Permission Recheck
Permissions are checked when the action is created, and re-evaluated strictly inside `execute_remediation_action()` at the service boundary. Even if a user has configured an action, it will fail if they lack permission at the moment of execution.

### 4. Workspace & Repository Ownership Checks
* **Workspace Check**: The target role assignment, exception, or policy must belong to the active workspace.
* **Repository Check**: The repository must explicitly belong to the active workspace.

### 5. Last GOVERNANCE_OWNER Protection
The system counts active, non-expired workspace-level owners. Any action that attempts to revoke, deactivate, or change the scope of the last remaining owner is rejected with a `ValueError` during execution.

### 6. Per-Item Bulk Isolation
Bulk actions execute items inside isolated try-except scopes. If one action fails (e.g. last owner lockout or invalid date), it does not halt or roll back other successful items in the batch.

### 7. Audit Event Creation
Every lifecycle transition generates a dedicated, searchable audit event in the `WorkspaceGovernanceAuditEvent` table.
