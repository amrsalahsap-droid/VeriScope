# Workspace Governance Safety Invariants

This document establishes the safety boundaries and immutable constraints of the Workspace Governance system.

---

## Safety Invariants Register

| Safety Invariant | Status | Where Enforced | Known Risk | Remaining Validation |
| :--- | :--- | :--- | :--- | :--- |
| **Evidence snapshots are immutable** | **ENFORCED** | Database constraints & write-once patterns. | Unauthorized direct database manipulation. | Periodic checksum validation script. |
| **Recommendation Health is not changed by governance** | **ENFORCED** | Read-only references inside `RecommendationEngine`. | Accidental override in code integration. | Integration tests covering code paths. |
| **Release Decision is not changed by governance** | **ENFORCED** | Separated router layers and state constraints. | Misleading admin instructions causing user confusion. | Operations runbook instruction audit. |
| **Quality Gate is not changed by governance** | **ENFORCED** | Quality gate calculator is isolated from policy tables. | Dynamic override flags injected in pipeline context. | Regression suite validation. |
| **Regression Scope is not changed by governance** | **ENFORCED** | Scoping resolver relies strictly on test metrics. | Code leakage between governance and scoping models. | Static code analysis check. |
| **GitHub status publishing is not changed by governance** | **ENFORCED** | Committer status dispatch module uses isolated checks. | Integration webhook trigger side-effects. | GAP-001 (Real GitHub app validation). |
| **Notifications are informational only** | **ENFORCED** | Dispatcher holds no execution capabilities. | Actor mistaking warning message for executed change. | Clarifying tooltips on notifications panel. |
| **Security posture score is advisory only** | **ENFORCED** | Dashboard view holds no linkage to release gates. | User assuming low score blocks release candidate. | Advisory labels on dashboard UI. |
| **Access review decisions are advisory only** | **ENFORCED** | Snapshot decisions are recommendation references only. | Admin assuming `REVOKE` action is applied instantly. | Confirmation check on completion page. |
| **Manual remediation requires preview & CONFIRM** | **ENFORCED** | `confirm_remediation_action` status checks. | Confirming draft action bypassing preview data. | Lifecycle sequence test (verified). |
| **No automatic remediation exists** | **ENFORCED** | Absence of auto-triggers in codebase. | Code drifts over time introducing background cleaners. | Strict code review policy. |
| **No automatic role revocation exists** | **ENFORCED** | Roles remain active until manually marked inactive. | Scheduled cron task revoking expired roles. | Verify scan loops do not modify database states. |
| **No automatic policy mutation exists** | **ENFORCED** | Policy updates require explicit service executor. | Drift resolution automatically copying preset values. | Validation checks in bulk scheduler. |
| **No automatic exception mutation exists** | **ENFORCED** | Exceptions remain approved until manual revoke/expire. | Expired exceptions auto-deleting. | Exception worker loop audit. |
| **Evidence packs redact secrets** | **ENFORCED** | Exporter regex filters and serialization scrubbing. | Edge-case password strings escaping standard match filters. | Penetration test using custom test credentials. |
| **Compatibility routes do not query Organization** | **ENFORCED** | Routers explicitly filter and query `Workspace` table. | Missing legacy route registration failing integration. | End-to-end integration mapping test. |
| **Workspace is the tenant boundary** | **ENFORCED** | Scoped `workspace_id` parameters on database queries. | Cross-workspace leak due to missing repository checks. | Unit test verifying repository checks. |
