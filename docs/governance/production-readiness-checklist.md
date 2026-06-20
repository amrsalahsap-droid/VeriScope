# Workspace Governance Production Readiness Checklist

## Production Readiness Checklist

### 1. Migration Readiness
* [ ] Database migration schema completed and registered via Alembic.
* [ ] Table backfills (`workspace_id`) completed with zero legacy orphaned records.
* [ ] DB indexes and foreign keys verified on SQLite and Postgres.

### 2. Route Readiness
* [ ] Workspace-scoped routes registered correctly.
* [ ] Organization compatibility `/organizations/{workspace_id}/...` endpoints map correctly without querying Organization model.

### 3. Permission Readiness
* [ ] Role assignments (`GOVERNANCE_OWNER`, `POLICY_ADMIN`, etc.) map correctly to action permissions.
* [ ] Repository-scoped boundary checks prevent cross-workspace access.

### 4. Audit Readiness
* [ ] Searchable audit events are emitted for all 11 lifecycle events.
* [ ] Redaction filters verified to scrub all tokens, keys, and authorization headers.

### 5. Notification Readiness
* [ ] System alerts trigger on drift, exceptions, and role expirations.
* [ ] Preference filters and critical owner warnings function correctly.

### 6. Access Review Readiness
* [ ] Access review snapshots capture all workspace roles.
* [ ] Completing a review generates recommendations without automatically revoking permissions.

### 7. Remediation Readiness
* [ ] Action state machine transitions through DRAFT, PENDING_CONFIRMATION, CONFIRMED, and EXECUTED.
* [ ] Lockout check blocks revoking the last active workspace owner.
* [ ] Action confirmations require the exact text `"CONFIRM"`.
* [ ] Bulk executes isolate failures and execute items inside individual try/except boundaries.

### 8. Evidence Pack Readiness
* [ ] Executive, Auditor, Security, and Access Review packs generate clean, valid formats.
* [ ] Redaction rules successfully remove secret strings.

### 9. Frontend Readiness
* [ ] React page components compile cleanly with zero TypeScript errors.
* [ ] User interface displays clear advisory warnings indicating that all actions are manual.

### 10. Security Readiness
* [ ] Segregation of duties prevents self-approval on policy exceptions.
* [ ] Permissions rechecked inside the service execution boundary.

### 11. Support Readiness
* [ ] Operations guides, runbooks, and troubleshooting guide published.
* [ ] Escalation paths and response playbooks configured.

---

## Known Blockers
The following phases and validations must be completed before marking the CI/CD module Release Candidate (RC) ready:
1. **Phase 8.6D real GitHub RC validation**: Pending verification of webhook events and status checks with live GitHub app setups.
2. **Phase 8.11D RBAC actual HTTP proof**: Pending end-to-end integration tests using full HTTP endpoints for authorization roles.
3. **Phase 8.12 notification live validation**: Pending live validation of email SMTP server connections and dashboard updates under high-load cycles.
4. **CI/CD Module Status**: Blocked from being marked Release Candidate ready until the above blockers are resolved.
