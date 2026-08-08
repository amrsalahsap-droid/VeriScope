# Outcome Learning Data Model

## Database Schemas

Outcome learning introduces three tables to the database. These tables are isolated from the main recommendation engine run tables to enforce the advisory-only invariant.

---

### 1. `outcome_events`

Stores ingested events representing actions occurring in GitHub, CI pipelines, or reported manually post-merge.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID (PK) | Unique primary key. |
| `workspace_id` | UUID (FK) | Reference to organization workspace context. |
| `repository_id` | UUID (FK) | Reference to Repository. |
| `pull_request_id` | UUID (FK, Nullable) | Linked PullRequest if resolved. |
| `pipeline_run_id` | UUID (FK, Nullable) | Linked CI Pipeline Run if resolved. |
| `recommendation_run_id` | UUID (FK, Nullable) | Linked RecommendationRun if strictly resolved. |
| `github_pr_number` | Integer (Nullable) | GitHub pull request number. |
| `commit_sha` | String (Nullable) | Git head commit hash. |
| `event_type` | String | Type code (e.g., `PR_MERGED`, `CI_FAILED_AFTER_RECOMMENDATION`, `DEPLOYMENT_FAILED`, `INCIDENT_REPORTED`). |
| `event_source` | String | Trigger source (e.g., `github`, `ci`, `manual`). |
| `event_status` | String (Nullable) | Processing status from source (e.g. `completed`, `failed`). |
| `severity` | String (Nullable) | Severity level (e.g. `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`). |
| `occurred_at` | DateTime | Timestamp when event actually occurred. |
| `detected_at` | DateTime | Timestamp when Veriscope detected/ingested the event. |
| `external_event_id` | String (Nullable) | Webhook delivery ID or external trigger signature key. Used for deduplication. |
| `metadata_json` | JSONB (Nullable) | Sanitized context payload. |
| `created_at` | DateTime | DB creation timestamp. |
| `updated_at` | DateTime | DB update timestamp. |

---

### 2. `outcome_labels`

Stores human-applied or system-classified quality metrics regarding recommendation run predictions.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID (PK) | Unique primary key. |
| `workspace_id` | UUID (FK) | Workspace isolation context. |
| `repository_id` | UUID (FK) | Repository context. |
| `recommendation_run_id` | UUID (FK) | Reference to RecommendationRun. |
| `outcome_event_id` | UUID (FK, Nullable) | Associated triggering event. |
| `label_type` | String | Dimension (e.g., `missed_required_test`, `regression_scope_accurate`, `quality_gate_correct`). |
| `label_value` | String | Value (e.g., `true`, `false`, `accurate`, `too_strict`, `too_lenient`, `too_large`, `too_small`). |
| `confidence` | Float (Nullable) | Optional classification confidence rating (0.0 to 1.0). |
| `source` | String | Origin (e.g., `human`, `system`). |
| `created_by_user_id` | UUID (FK, Nullable) | Identity of user entering the label. |
| `metadata_json` | JSONB (Nullable) | Sanitized audit logs context. |
| `created_at` | DateTime | DB creation timestamp. |

---

### 3. `recommendation_outcome_summaries`

Aggregates multiple outcome events and labels into a single unified summary per recommendation run. Used for final analytics recomputations.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID (PK) | Unique primary key. |
| `recommendation_run_id` | UUID (FK, Unique) | Reference to RecommendationRun. |
| `pipeline_run_id` | UUID (FK, Nullable) | Associated Pipeline Run. |
| `workspace_id` | UUID (FK) | Workspace isolation context. |
| `repository_id` | UUID (FK) | Repository context. |
| `pull_request_id` | UUID (FK, Nullable) | Pull request ID. |
| `github_pr_number` | Integer (Nullable) | PR number. |
| `commit_sha` | String (Nullable) | Commit SHA. |
| `merged` | Boolean | True if PR merged successfully. |
| `reverted` | Boolean | True if code reverted after merge. |
| `deployment_failed` | Boolean | True if post-merge deploy failed. |
| `incident_found` | Boolean | True if production incident reported. |
| `bug_found` | Boolean | True if defect found post-merge. |
| `regression_found` | Boolean | True if regression was missed by test suite. |
| `missed_critical_test` | Boolean | True if critical test failure occurred. |
| `missed_high_test` | Boolean | True if high test failure occurred. |
| `scope_accuracy` | String (Nullable) | Quality score (e.g. `accurate`, `too_large`, `too_small`). |
| `quality_gate_accuracy` | String (Nullable) | Quality score (e.g. `correct`, `incorrect`). |
| `learning_status` | String | Recompute state (`PROCESSED`, `PENDING`). |
| `created_at` | DateTime | DB creation timestamp. |
| `updated_at` | DateTime | DB update timestamp. |

## Relationships & Isolation
- Each table includes `workspace_id` and `repository_id` columns to guarantee scoping isolation.
- SQL foreign key constraints link to `recommendation_runs` and other core tables with cascading deletion configurations.
