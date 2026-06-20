# Workspace Governance Notification Operations Guide

## Notification Types
* **POLICY_DRIFT**: Triggered when a repository policy drifts from the workspace default.
* **PENDING_EXCEPTION**: Triggered when a repository manager requests a CI/CD policy exception.
* **ROLE_EXPIRING**: Alerts when an administrative role is within 14 days of expiration.
* **ROLE_EXPIRED**: Alerts when a role assignment expiration date has passed.
* **ACCESS_REVIEW_REQUIRED**: Alerts when a new governance access review cycle begins.

## Recipient Resolution Rules
* **Workspace Alerts**: Sent to all users holding `GOVERNANCE_OWNER` or `POLICY_ADMIN` roles at the workspace level.
* **Repository Alerts**: Sent to `REPOSITORY_POLICY_MANAGER` users assigned to the specific repository, with fallback to workspace owners.

## Workspace & Repository Notification Rules
* **Workspace-Level Rules**: Manage broad alerts (e.g. access reviews, role expirations).
* **Repository-Level Rules**: Restrict policy drift or exception alerts to repository owners unless they remain unresolved, escalating to workspace owners.

## Preference Behavior
Users can customize notification channels (e.g. system dashboard, email) or mute specific alert categories in their profile preferences.

## Critical Owner Notification Rule
> [!WARNING]
> Workspace-level `GOVERNANCE_OWNER` users cannot mute critical notifications, including last active owner warnings and high-risk policy drift alerts. These remain active to prevent lockouts.

## Read/Dismiss Behavior
System notifications are marked as read individually or in bulk. Dismissing an alert removes it from the active dashboard feed but does not delete the underlying audit record.

## Manual Scan Operations
Admins can manually trigger scans for role expirations and policy drift through the admin settings tab. This runs the scanning workers immediately.

## Deduplication Behavior
Scanning engines use a unique hash of the finding type, target ID, and timestamp to prevent duplicate notifications. An active alert must be dismissed or resolved before a new notification for the same issue is emitted.

## Audit Events
All notification creations, dispatches, and preferences changes log searchable events in the workspace audit table.

## Safe Diagnostics
To verify notification delivery paths without exposing production credentials:
1. Trigger a diagnostics scan via the settings panel.
2. Review the sanitised logs showing recipient counts and channel routing.

## Safe Operating Principles
> [!IMPORTANT]
> **Notifications are informational only**
> * Notifications do not mutate policies or configurations.
> * Notifications do not modify evidence graph snapshots.
> * Notifications do not change release decisions.
> * Notifications do not affect quality gates or commit statuses.
