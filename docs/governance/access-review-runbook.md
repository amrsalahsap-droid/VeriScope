# Workspace Governance Access Review Runbook

## Introduction
Access reviews are structured audits of user roles and workspace privileges. They detect stale or expired accounts, policy drift, and general role assignments that violate security policies.

## When to Create Access Reviews
* **Regular Intervals**: Monthly or quarterly.
* **Organizational Events**: Staff changes, role switches, or offboarding.
* **Audit Events**: Triggered prior to external compliance audits.

## Review Types
* **Role Verification**: Evaluates workspace and repository user roles.
* **Policy Compliance**: Evaluates policy defaults, overrides, and drift states.
* **Exceptions Assessment**: Audits active policy exemptions.

## Finding Types
* **Stale Role**: User has not logged in or active session is inactive for an extended period.
* **Expired Role**: Role expiration date is in the past.
* **Policy Drift**: Repository settings do not match workspace default policy settings.
* **Stale Exception**: Active exceptions exceeding standard timelines or whose reason is no longer valid.

## Risk Levels
* **LOW**: Stale repository viewer roles.
* **MEDIUM**: Stale repository managers or policy admins.
* **HIGH**: Stale workspace admins or policy exceptions on critical repositories.
* **CRITICAL**: Stale GOVERNANCE_OWNER roles or expired exception policies.

## Review Item Decisions
Each item in a review must be marked with a decision:
* **KEEP**: Confirm the current role, scope, or exception is correct and necessary.
* **REVOKE_RECOMMENDED**: Flag the item for removal.
* **CHANGE_SCOPE_RECOMMENDED**: Flag the item to adjust its scope (e.g. restrict to a single repository).

## Review Completion
Once all items have decisions, the administrator completes the review, locking the choices and generating remediation recommendations.

## What Decisions Do and Do Not Do
> [!IMPORTANT]
> **Advisory Nature of Decisions**
> * **Decisions do not apply changes automatically**: Marking a role assignment as `REVOKE_RECOMMENDED` does NOT revoke the role.
> * **Decisions do not modify evidence**: Active settings, repository access, and compliance matrices are not altered by the decision.
> * **Remediation action is required**: To apply changes, an administrator must manually create and execute a remediation action from the recommendation.

## How to Convert a Finding into a Manual Remediation
1. Go to the completed **Access Review Summary** page.
2. Select any item marked `REVOKE_RECOMMENDED` or `CHANGE_SCOPE_RECOMMENDED`.
3. Click **Initiate Remediation**. This opens the wizard to create a remediation action in `DRAFT` state.
4. Preview, confirm, and execute the action.

## How to Avoid Last-Owner Lockout
Before applying a `REVOKE_RECOMMENDED` or `DEACTIVATE_ROLE` decision to a `GOVERNANCE_OWNER`:
1. Verify there is at least one other active workspace-level `GOVERNANCE_OWNER`.
2. Do not proceed if the user is the last owner. (The system will block execution of the remediation action, but administrators should identify this early during reviews).

## How to Document Decision Reasons
Always include a clear justification string when recording decisions (e.g., "User transferred to another team" or "Exception no longer required after standard pipeline migration"). This forms part of the immutable audit trail.
