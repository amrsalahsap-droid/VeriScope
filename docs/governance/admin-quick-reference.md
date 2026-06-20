# Workspace Governance Admin Quick Reference

## Quick Reference Table

| Admin Action | Required Permission | Where to Go in UI | What Happens | What Does NOT Happen | Audit Event Created |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Assign User Role** | `governance.roles.assign` | Governance -> Roles | Grants the specified role to a user for a given scope. | Does not automatically verify user's identity. | `GOVERNANCE_ROLE_REMEDIATION_EXECUTED` |
| **Set Policy Defaults** | `governance.policy.update` | Governance -> Settings | Updates default baseline preset values. | Does not overwrite custom repository overrides. | `GOVERNANCE_POLICY_REMEDIATION_EXECUTED` |
| **Override Repo Policy** | `governance.policy.update` | Governance -> Repositories | Creates a custom policy row on the repository. | Does not affect other repositories. | `GOVERNANCE_POLICY_REMEDIATION_EXECUTED` |
| **Request Exception** | `governance.exception.request`| Repository Settings -> Exceptions | Creates a pending policy exception for review. | Does not approve the exception automatically. | `CI_CD_POLICY_EXCEPTION_REQUESTED` |
| **Approve Exception** | `governance.exception.approve`| Governance -> Exceptions | Marks exception as APPROVED, allowing pipeline override. | Does not allow self-approval (blocked). | `CI_CD_POLICY_EXCEPTION_APPROVED` |
| **Revoke Exception** | `governance.exception.revoke` | Governance -> Exceptions | Sets exception status to REVOKED instantly. | Does not delete exception history. | `GOVERNANCE_EXCEPTION_REMEDIATION_EXECUTED` |
| **Start Access Review** | `governance.remediation.confirm`| Governance -> Access Reviews | Initiates snapshot capturing all user roles. | Does not lock or apply changes. | `GOVERNANCE_REVIEW_SNAPSHOT_CREATED` |
| **Remediate Stale Role** | `governance.remediation.confirm`| Access Reviews -> Recommendations | Opens wizard to preview, confirm, and execute deactivation. | Does not execute without a typed "CONFIRM" string. | `GOVERNANCE_ROLE_REMEDIATION_EXECUTED` |
| **Remediate Policy Drift**| `governance.remediation.confirm`| Governance -> Compliance List | Re-aligns drifted repository back to workspace defaults. | Does not alter historical commit status checks. | `GOVERNANCE_POLICY_REMEDIATION_EXECUTED` |
| **Export Evidence** | `governance.audit.view` | Governance -> Compliance | Downloads redaction-scrubbed JSON compliance metrics. | Does not include credentials, secrets, or SQL logs. | `EVIDENCE_PACK_EXPORTED` |
