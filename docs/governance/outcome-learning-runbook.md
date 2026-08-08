# Outcome Learning Operational Runbook

This guide covers operational setup, database checks, API testing, and troubleshooting for the Veriscope Outcome Learning module.

---

## 1. Initial Setup & DB Migrations
To upgrade the database to include outcome learning tables:

```bash
# Run migrations using Alembic
.venv\Scripts\alembic upgrade head
```

### Verification
Connect to PostgreSQL and verify the tables:
```sql
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'outcome%';
```
Expected output:
- `outcome_events`
- `outcome_labels`

---

## 2. Ingesting Events (CLI Example)
You can ingest events manually via HTTP using curl:

```bash
curl -X POST "http://localhost:8000/api/v1/workspaces/{workspace_id}/repositories/{repository_id}/outcome-learning/events" \
     -H "Authorization: Bearer $JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "INCIDENT_REPORTED",
       "event_source": "manual",
       "event_status": "completed",
       "severity": "CRITICAL",
       "metadata_json": {
         "description": "Production API Outage in payment processing gateway."
       },
       "commit_sha": "a1b2c3d4"
     }'
```

---

## 3. Labeling Recommendation Runs
Security officers can submit accuracy assessments:

```bash
curl -X POST "http://localhost:8000/api/v1/workspaces/{workspace_id}/repositories/{repository_id}/outcome-learning/runs/{recommendation_run_id}/labels" \
     -H "Authorization: Bearer $JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "label_type": "quality_gate_correct",
       "label_value": "true",
       "confidence": 1.0
     }'
```

---

## 4. Querying Database for Audit Logging
All events, label assignments, and recomputation triggers log a record to `workspace_governance_audit_events`. Use the following query to check outcome learning audit trails:

```sql
SELECT event_type, actor_id, repository_id, decision, reason, audit_metadata
FROM workspace_governance_audit_events
WHERE event_type LIKE 'OUTCOME%' OR event_type LIKE '%LABEL%'
ORDER BY created_at DESC;
```

---

## 5. Troubleshooting Mappings & Ambiguous Links
If an event fails to link to a recommendation run, look up the unresolved reason:

```sql
SELECT id, event_type, commit_sha, github_pr_number, recommendation_run_id, metadata_json
FROM outcome_events
WHERE recommendation_run_id IS NULL;
```

### Common Causes of Unlinked Events
1. **Repository Mismatch**: The event was sent to the wrong repository endpoint.
2. **Commit SHA Mismatch**: The commit SHA in the check suite or pull request does not match the recommendation run head snapshot hash.
3. **Ambiguity**: Multiple recommendation runs exist for the same commit SHA/PR combination. Check `workspace_governance_audit_events` for the `Ambiguous match` reason metadata.

---

## 6. Outcome Learning Audit Export

`OUTCOME_LEARNING_EXPORT_CREATED` is NOT_APPLICABLE in Phase 9 because Phase 9 does not implement an outcome-learning export endpoint. Export support is deferred to a future reporting/export phase. No export action exists, so no export-created audit event is emitted in Phase 9.
