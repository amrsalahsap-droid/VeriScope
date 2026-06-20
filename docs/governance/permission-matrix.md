# Workspace Governance Permission Matrix

## Role-to-Permission Mapping

| Permission / Action | GOVERNANCE_OWNER | POLICY_ADMIN | EXCEPTION_APPROVER | REPOSITORY_POLICY_MANAGER | GOVERNANCE_VIEWER | EXECUTIVE_VIEWER | AUDITOR | no_role_user |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **policy view** | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No |
| **policy update** | Yes | Yes | No | Yes (repo-only) | No | No | No | No |
| **policy preset apply** | Yes | Yes | No | Yes (repo-only) | No | No | No | No |
| **workspace default update** | Yes | Yes | No | No | No | No | No | No |
| **bulk policy operation** | Yes | Yes | No | No | No | No | No | No |
| **exception request** | Yes | Yes | Yes | Yes | No | No | No | No |
| **exception approve** | Yes | No | Yes | No | No | No | No | No |
| **exception reject** | Yes | No | Yes | No | No | No | No | No |
| **exception revoke** | Yes | No | Yes | No | No | No | No | No |
| **role assign** | Yes | No | No | No | No | No | No | No |
| **audit view** | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No |
| **analytics view** | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No |
| **executive report view/export**| Yes | Yes | Yes | Yes | Yes | Yes | Yes | No |
| **notifications view/manage** | Yes | Yes | Yes | Yes | Yes | No | Yes | No |
| **security posture view** | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No |
| **security signals view** | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No |
| **access review create** | Yes | No | No | No | No | No | No | No |
| **access review decide** | Yes | No | No | No | No | No | No | No |
| **access review complete** | Yes | No | No | No | No | No | No | No |
| **evidence pack export** | Yes | No | No | No | No | No | Yes | No |
| **remediation view** | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No |
| **remediation preview** | Yes | Yes | Yes | Yes | No | No | No | No |
| **remediation confirm** | Yes | Yes | Yes | Yes (repo-only) | No | No | No | No |
| **remediation execute** | Yes | Yes | Yes | Yes (repo-only) | No | No | No | No |
| **remediation cancel** | Yes | Yes | Yes | Yes (repo-only) | No | No | No | No |
| **bulk remediation execute** | Yes | Yes | No | No | No | No | No | No |

## Scope Rules
1. **Workspace-Scoped Role**: Applies across all repositories belonging to the workspace.
2. **Repository-Scoped Role**: Applies only to the repository assigned. Permissions do not leak to other repositories.
3. **Repository Workspace Ownership Check**: Any repository target must explicitly belong to the current workspace.
4. **Expired Roles**: An expired role grants no access (is_active resolves to false / datetime validation blocks access).
5. **Inactive Roles**: Explicitly deactivated roles grant no permissions.
6. **Repository-Scoped Privileges**: Repository-scoped managers do not receive workspace-wide privileges unless explicitly granted.
