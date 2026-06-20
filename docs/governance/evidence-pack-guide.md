# Workspace Governance Evidence Pack Export Guide

## Pack Types
* **EXECUTIVE**: Summary of compliance scores, overall grade, active policy overrides, and key recommendations. Suitable for management reporting.
* **AUDITOR**: Formal documentation containing policy drift, role assignments, exception logs, access review completion timestamps, and decision reasons.
* **SECURITY_REVIEW**: Technical details on policy configurations, branch protection readiness, exception justifications, and raw security posture signals.
* **ACCESS_REVIEW**: Contains completed access review histories, recommended vs. executed remediation actions, and lockout mitigations.
* **FULL**: Comprehensive capture of all workspace policies, repositories, exceptions, reviews, and remediation details.

## Included Sections
* **Workspace Summary**: Compliance score, grades, total repositories.
* **Policy Preset Summary**: Active presets usage statistics.
* **Workspace Default Policy**: Configuration values for default rules.
* **Repository Policy Overrides**: Detailed list of customized repository policies.
* **Policy Drift Summary**: List of repositories with drift, including drift fields and risk levels.
* **Exception Summary**: Approved, requested, and revoked policy exceptions.
* **Role Assignment Summary**: Active workspace and repository role listings.
* **Access Review Summary**: Completed access reviews and decision lists.
* **Notification Summary**: Alert dispatch metrics.
* **Audit Event Summary**: Historical timeline of configuration mutations.
* **Security Posture Summary**: Metrics on stale/expired roles and posture risks.
* **Open Findings**: Unremediated access review recommendations or active policy drifts.
* **Recommendations**: Recommended remediation steps.

## Redaction Rules
> [!CAUTION]
> **Strict Redaction of Sensitive Data**
> The evidence pack exporter automatically scrubs data fields to prevent exposure. Export files MUST NOT contain:
> * **No raw tokens**: All API, CI/CD, and personal access tokens are stripped.
> * **No secrets**: Secret values and keys are completely removed.
> * **No credentials**: Username/password strings or credentials are redacted.
> * **No Authorization headers**: Request headers containing auth values are omitted.
> * **No webhook secrets**: GitHub app or custom webhook secret configurations are blanked.
> * **No private keys**: Private cryptographic keys are filtered.
> * **No database connection strings**: DBMS URIs, hosts, ports, and usernames are redacted.
> * **No SQL internals**: Raw SQL queries are excluded from logs.
> * **No stack traces**: Raw Python or framework tracebacks are stripped.
