# Outcome Learning API Specification

All outcome learning endpoints are protected by workspace-level role permissions (RBAC). Callers must present a valid JWT Bearer token in the `Authorization` header.

---

## 1. Ingest Outcome Event
Ingest a post-decision event from GitHub webhooks, CI runners, or manual reporting tools.

* **Method**: `POST`
* **URL**: `/api/v1/workspaces/{workspace_id}/repositories/{repository_id}/outcome-learning/events`
* **Role Allowed**: `security_officer`, `admin`
* **Request Body**:
```json
{
  "event_type": "PR_MERGED",
  "event_source": "github",
  "event_status": "completed",
  "severity": "CRITICAL",
  "occurred_at": "2026-06-21T05:00:00Z",
  "external_event_id": "gh-delivery-12345",
  "metadata_json": {
    "merged_by": "developer1",
    "secret_token_to_redact": "1234abcd"
  },
  "pull_request_id": "00000000-0000-0000-0000-000000000000",
  "github_pr_number": 42,
  "commit_sha": "a1b2c3d4"
}
```
* **Response (201 Created)**:
```json
{
  "id": "11111111-1111-1111-1111-111111111111",
  "workspace_id": "22222222-2222-2222-2222-222222222222",
  "repository_id": "33333333-3333-3333-3333-333333333333",
  "pull_request_id": "00000000-0000-0000-0000-000000000000",
  "recommendation_run_id": "44444444-4444-4444-4444-444444444444",
  "event_type": "PR_MERGED",
  "event_source": "github",
  "occurred_at": "2026-06-21T05:00:00Z",
  "detected_at": "2026-06-21T05:01:00Z",
  "external_event_id": "gh-delivery-12345",
  "metadata_json": {
    "merged_by": "developer1",
    "secret_token_to_redact": "***REDACTED***"
  }
}
```

---

## 2. Apply human / system outcome label
Label a recommendation run with accuracy assessments. If a label already exists for the run and type, it is updated in-place (versioning the decision).

* **Method**: `POST`
* **URL**: `/api/v1/workspaces/{workspace_id}/repositories/{repository_id}/outcome-learning/runs/{recommendation_run_id}/labels`
* **Role Allowed**: `security_officer`, `admin`
* **Request Body**:
```json
{
  "label_type": "regression_scope_accurate",
  "label_value": "true",
  "confidence": 1.0,
  "metadata_json": {
    "comment": "Confirmed by regression testing team."
  }
}
```
* **Response (201 Created / 200 OK)**:
```json
{
  "id": "55555555-5555-5555-5555-555555555555",
  "workspace_id": "22222222-2222-2222-2222-222222222222",
  "repository_id": "33333333-3333-3333-3333-333333333333",
  "recommendation_run_id": "44444444-4444-4444-4444-444444444444",
  "label_type": "regression_scope_accurate",
  "label_value": "true",
  "confidence": 1.0,
  "source": "human",
  "created_by_user_id": "66666666-6666-6666-6666-666666666666",
  "created_at": "2026-06-21T05:05:00Z",
  "metadata_json": {
    "comment": "Confirmed by regression testing team."
  }
}
```

---

## 3. Get Recommendation Outcome Summary
Retrieve the aggregated outcome summary for a recommendation run.

* **Method**: `GET`
* **URL**: `/api/v1/workspaces/{workspace_id}/repositories/{repository_id}/outcome-learning/runs/{recommendation_run_id}/summary`
* **Role Allowed**: `security_officer`, `admin`, `auditor`
* **Response (200 OK)**:
```json
{
  "id": "77777777-7777-7777-7777-777777777777",
  "recommendation_run_id": "44444444-4444-4444-4444-444444444444",
  "workspace_id": "22222222-2222-2222-2222-222222222222",
  "repository_id": "33333333-3333-3333-3333-333333333333",
  "merged": true,
  "reverted": false,
  "deployment_failed": false,
  "incident_found": false,
  "bug_found": false,
  "regression_found": false,
  "missed_critical_test": false,
  "missed_high_test": false,
  "scope_accuracy": "accurate",
  "quality_gate_accuracy": "correct",
  "learning_status": "PROCESSED"
}
```

---

## 4. Get Workspace Outcome Analytics
Get high-level aggregated metrics for the workspace, calculating calibration accuracy ratios and post-merge failure rates.

* **Method**: `GET`
* **URL**: `/api/v1/workspaces/{workspace_id}/outcome-learning/analytics`
* **Role Allowed**: `security_officer`, `admin`, `auditor`
* **Response (200 OK)**:
```json
{
  "recommendation_accuracy": 0.985,
  "quality_gate_accuracy": 0.97,
  "regression_scope_accuracy": 0.95,
  "safe_to_skip_accuracy": 0.99,
  "post_merge_failure_rate": 0.015,
  "post_deployment_failure_rate": 0.01,
  "revert_rate": 0.005,
  "incident_linked_rate": 0.002
}
```

---

## 5. Outcome Learning Audit Export

`OUTCOME_LEARNING_EXPORT_CREATED` is NOT_APPLICABLE in Phase 9 because Phase 9 does not implement an outcome-learning export endpoint. Export support is deferred to a future reporting/export phase. No export action exists, so no export-created audit event is emitted in Phase 9.
