# Workspace Governance Admin Runbook

## Purpose
This runbook provides administrative procedures, lifecycles, and safe operating guidelines for managing the Workspace Governance system within VeriScope.

## Supported Personas
* **GOVERNANCE_OWNER**: Ultimate workspace authority, has full read/write permissions for all governance, roles, exceptions, and remediation actions.
* **POLICY_ADMIN**: Manages policy defaults and overrides across the workspace.
* **EXCEPTION_APPROVER**: Reviews, approves, or rejects requested CI/CD policy exceptions.
* **REPOSITORY_POLICY_MANAGER**: Manages policy overrides and settings on specific repositories.
* **GOVERNANCE_VIEWER**: Read-only access to policies, findings, and reviews.
* **AUDITOR**: Inspects compliance history, audit logs, and exports evidence.

## Workspace Governance Lifecycle
1. **Initial Setup**: Define workspace policies and defaults.
2. **Assigning Roles**: Assign RBAC roles to control access.
3. **Monitoring & Review**: Regular access reviews and checking of security posture.
4. **Remediation**: Manual review, preview, confirmation, and execution of remediations.

## Initial Setup
To initialize governance:
1. Navigate to the Workspace Governance dashboard.
2. Select **Settings** and specify default CI/CD Policy Preset values (e.g., standard, strict).
3. Save workspace defaults.

## Role Assignment Process
Roles are assigned at either:
* **Workspace Scope**: Scopes permissions across all repositories in the workspace.
* **Repository Scope**: Scopes permissions only to a specific repository.
To assign a role:
1. Navigate to **Governance Roles & Assignments**.
2. Click **Add Role Assignment**, specify the user, role, scope type, and optional expiration date.
3. Save assignment.

## Policy Default Setup
Workspace default policy acts as the baseline preset. Any repository without custom overrides inherits these settings automatically.

## Repository Policy Override Process
To create repository overrides:
1. Select the target repository under the compliance list.
2. Choose a different preset or check "Custom".
3. Save override.

## Exception Lifecycle
1. **Request**: Repository-scoped user requests an exception with justification and expiry.
2. **Approve/Reject**: Exception Approver approves or rejects. Segregation of duties prevents self-approval.
3. **Revocation/Expiry**: Admins can revoke exceptions manually, or they transition to expired status when the expiration date passes.

## Access Review Lifecycle
1. **Initiate**: Establish an access review snapshot.
2. **Evaluate**: Check stale, expired, or misplaced permissions.
3. **Decide**: Mark items as `KEEP` or `REVOKE_RECOMMENDED` / `CHANGE_SCOPE_RECOMMENDED`.
4. **Complete**: Lock decisions. Note that review decisions are advisory; recommendations must be manually executed.

## Remediation Lifecycle
Manual remediations progress strictly through:
`DRAFT -> PENDING_CONFIRMATION -> CONFIRMED -> EXECUTED/FAILED`
Users can transition drafts to `CANCELLED`.

## Notification Lifecycle
Notifications alert administrators to policy drift, pending exception requests, and role expirations. They are informational and do not trigger automatic mutations.

## Evidence Pack Export Process
Auditors can export evidence snapshots to verify system compliance states. Select the desired export scope (Executive, Auditor, etc.) and download the generated JSON/PDF format.

## Audit Review Process
Review the `WorkspaceGovernanceAuditEvent` log to search by actor, workspace, target user, repository, permission, or role, ensuring no configuration changes occur without full visibility.

## Common Operational Risks
* **Lockout**: Deactivating the last workspace GOVERNANCE_OWNER. (The system contains strict logic to prevent this).
* **Drift**: Repository policies drifting from workspace standards. Remedied by manual default policy application.

## Safe Operating Principles
> [!IMPORTANT]
> The VeriScope Workspace Governance module enforces manual-only workflows:
> * **Manual remediation only**: No system action will automatically alter role state or policy settings.
> * **No automatic role revocation**: Expirations and stales are flagged; revocation must be explicitly initiated by an administrator.
> * **No automatic policy mutation**: Drift must be resolved manually by an authorized policy manager.
> * **Security scores are advisory only**: Posture metrics do not influence quality gates.
> * **Notifications are informational only**: Email or system alerts carry no logic executing runtime changes.
> * **Evidence history is immutable**: Once written, audit events and evidence graph historical snapshots cannot be overwritten.
> * **Quality gate history is not rewritten**: Remediation does not mutate past quality gate calculations.
> * **Release decision history is not rewritten**: Decisions concerning previous releases are preserved.
> * **GitHub status history is not rewritten**: Past published commit status checks are immutable.
