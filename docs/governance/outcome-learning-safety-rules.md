# Outcome Learning Safety Rules & Invariants

To maintain absolute compliance and verify governance integrity, Outcome Learning implements a set of strict safety rules and execution boundaries.

---

## 1. Advisory-Only Principle & Invariant
Outcome Learning acts strictly as a **downstream passive calibration channel**. It is isolated from the main evaluation pipeline.

> [!IMPORTANT]
> **Safety Invariant**: Under no circumstances shall outcome events, labels, summaries, or analytics update or mutate:
> - Existing recommendation runs or their quality gate/release decisions.
> - Historical evidence snapshots (`RequirementEvidence` or snapshot JSON fields).
> - active GitHub statuses, checks, or comment decisions.
>
> All recommendation run fields compiled at evaluation time must remain write-once (immutable).

---

## 2. Multi-Tenant Scoping & Isolation
- All database tables contain `workspace_id` and `repository_id` columns.
- The router checks that the user's role grants permission to the specific workspace.
- If an operation requests a recommendation run, the run's `workspace_id` must match the URL path parameters exactly. If there is a mismatch, the request is denied with a `403 Forbidden` response to prevent cross-workspace mapping attempts.

---

## 3. Strict Recommendation Linking Rules
Outcome events are linked to the correct recommendation only when the system can safely resolve:
1. `workspace_id`
2. `repository_id`
3. `pull_request_id` (or `github_pr_number` mapped cleanly to a single PR ID)
4. `commit_sha` (matched against the recommendation's head snapshot hash)

### Ambiguity Handling
- If multiple recommendation runs match the filter, the linkage is marked **Ambiguous**.
- If no recommendation runs match, the linkage is marked **No Match**.
- In both cases:
  - The event is stored in the database as an **unresolved** outcome event.
  - The event's `recommendation_run_id` field is set to `None`.
  - The event's summary recomputation is skipped.
  - An audit event is logged with the specific unresolved reason to assist administrators.

---

## 4. Recursive Secret Redaction
All incoming payloads (`metadata_json` on events and labels) are scanned recursively to scrub credentials before any database write or audit log persistence.

### Scrubbing Keys
Any key containing any of the following substrings (case-insensitive) is scrubbed to `***REDACTED***`:
- `token`
- `authorization`
- `password`
- `secret`
- `key`
- `jwt`
- `apikey`
- `api_key`
- `pwd`
- `auth`
- `signature`
- `credential`
- `connection` (e.g., connection strings)
- `private` (e.g., private keys)

---

## 5. Expired and Inactive Role Enforcement
The routing layers verify security officer role assignments for:
1. **Activity**: Inactive assignments (`is_active = False`) are rejected.
2. **Expiration**: Assignments with `expires_at` in the past are rejected.
- Any request from an expired or inactive role produces a `403 Forbidden` exception.
- Expired/inactive access denials are fully audited in the workspace logs.

---

## 6. Outcome Learning Audit Export Safety

`OUTCOME_LEARNING_EXPORT_CREATED` is NOT_APPLICABLE in Phase 9 because Phase 9 does not implement an outcome-learning export endpoint. Export support is deferred to a future reporting/export phase. No export action exists, so no export-created audit event is emitted in Phase 9.
