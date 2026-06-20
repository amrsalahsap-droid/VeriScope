# CI/CD Production Runbook

This runbook provides operational guidance for managing Veriscope CI/CD integration in production.

## Table of Contents

1. [GitHub App Installation](#github-app-installation)
2. [CI Token Management](#ci-token-management)
3. [GitHub Actions Configuration](#github-actions-configuration)
4. [Quality Gate Interpretation](#quality-gate-interpretation)
5. [Failed Pipeline Investigation](#failed-pipeline-investigation)
6. [GitHub Publishing Failure Investigation](#github-publishing-failure-investigation)
7. [Dead-Letter Job Management](#dead-letter-job-management)
8. [CI Token Revocation](#ci-token-revocation)
9. [Artifact Redaction Verification](#artifact-redaction-verification)
10. [GitHub Rate Limit Response](#github-rate-limit-response)
11. [Known Limitations](#known-limitations)

---

## GitHub App Installation

### Prerequisites

- GitHub organization admin access
- Veriscope backend deployed and accessible
- Webhook endpoint configured

### Installation Steps

1. **Create GitHub App**
   - Navigate to GitHub Settings → Developer settings → GitHub Apps
   - Create new app with appropriate permissions:
     - Repository permissions: `checks:write`, `pull_requests:write`, `contents:read`
     - Organization permissions: `members:read`
   - Generate webhook secret
   - Download private key

2. **Configure Webhook**
   - Set webhook URL to: `https://<your-domain>/api/github/webhook`
   - Set webhook secret
   - Select events: `pull_request`, `push`, `check_run`

3. **Install App**
   - Install app to target organization
   - Select repositories to enable

4. **Configure Backend**
   - Set environment variables:
     - `GITHUB_APP_ID`: Your GitHub App ID
     - `GITHUB_PRIVATE_KEY`: Path to or contents of private key
     - `GITHUB_WEBHOOK_SECRET`: Webhook secret
   - Restart backend service

### Verification

```bash
# Test webhook delivery
curl -X POST https://<your-domain>/api/github/webhook \
  -H "X-Hub-Signature-256: <signature>" \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

---

## CI Token Management

### Creating a CI Token

1. Navigate to repository settings in Veriscope UI
2. Go to "CI/CD Integration" → "CI Tokens"
3. Click "Create Token"
4. Token is displayed once - copy it immediately
5. Store token in GitHub repository secrets as `VERISCOPE_CI_TOKEN`

### Token Scoping

- Tokens are scoped to a specific repository
- Tokens cannot be used across repositories
- Tokens have an expiration date (configurable, default 90 days)

### Token Rotation

1. Create new token before old token expires
2. Update GitHub repository secret
3. Verify new token works
4. Revoke old token

### Monitoring Token Usage

```bash
# Check token usage metrics
GET /api/repositories/{repository_id}/cicd/metrics
```

---

## GitHub Actions Configuration

### Basic Workflow

```yaml
name: Veriscope Quality Gate

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  veriscope-check:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Veriscope Analysis
        run: |
          curl -X POST https://<your-domain>/api/repositories/${{ github.repository }}/trigger \
            -H "Authorization: Bearer ${{ secrets.VERISCOPE_CI_TOKEN }}" \
            -H "X-GitHub-Event: pull_request" \
            -d '{"pr_number": ${{ github.event.pull_request.number }}}'
```

### Required Secrets

- `VERISCOPE_CI_TOKEN`: CI token for the repository

### Optional Configuration

- Custom branch filters
- Custom trigger conditions
- Integration with other CI steps

---

## Quality Gate Interpretation

### Quality Gate States

| State | Meaning | Action |
|-------|---------|--------|
| PASSED | All required evidence present, recommendation healthy | Safe to merge |
| PARTIAL | Some required evidence missing or recommendation degraded | Review before merge |
| FAILED | Critical evidence missing or recommendation unhealthy | Do not merge |
| BLOCKED | Release decision blocks merge | Do not merge |
| UNKNOWN | Analysis incomplete or error | Investigate |

### Quality Gate Components

- **Recommendation Health**: Overall health of the recommendation (Ready, Needs Attention, Critical)
- **Release Decision**: Final release decision (Verified, Partially Verified, Not Verified)
- **Required Before Release**: Evidence items required before release
- **Regression Scope Required**: Evidence items required for regression testing
- **Optional**: Nice-to-have evidence items
- **Safe to Skip**: Evidence items that can be safely skipped

### Interpreting Results

1. **Check Recommendation Health**
   - If `Ready`: Proceed to check Release Decision
   - If `Needs Attention` or `Critical`: Investigate gaps

2. **Check Release Decision**
   - If `Verified`: Safe to merge
   - If `Partially Verified`: Review gaps before merge
   - If `Not Verified`: Do not merge

3. **Review Evidence Gaps**
   - Check `Required Before Release` items
   - Check `Regression Scope Required` items
   - Address gaps before merging

---

## Failed Pipeline Investigation

### Common Failure Modes

1. **Webhook Not Received**
   - Check GitHub App installation
   - Verify webhook URL is accessible
   - Check webhook secret matches

2. **Job Processing Failed**
   - Check dead-letter jobs: `GET /api/repositories/{id}/cicd/pipeline-jobs/dead-letter`
   - Review job error messages
   - Check worker logs

3. **GitHub Publishing Failed**
   - Check GitHub API rate limits
   - Verify GitHub App permissions
   - Check authentication credentials

### Investigation Steps

1. **Check Health Status**
   ```bash
   GET /api/repositories/{id}/cicd/health
   ```

2. **Review Alerts**
   ```bash
   GET /api/repositories/{id}/cicd/alerts
   ```

3. **Check Webhook Events**
   ```bash
   GET /api/repositories/{id}/cicd/github/webhook-events
   ```

4. **Review Audit Trail**
   ```bash
   GET /api/repositories/{id}/cicd/audit
   ```

### Recovery Actions

- **Webhook Issues**: Reinstall GitHub App, update webhook secret
- **Job Failures**: Retry dead-letter jobs, check worker status
- **Publishing Failures**: Wait for rate limit cooldown, verify credentials

---

## GitHub Publishing Failure Investigation

### Status Check Publishing Failures

**Symptoms**: Status checks not appearing on PR

**Investigation**:
1. Check GitHub App has `checks:write` permission
2. Verify GitHub API authentication
3. Check rate limit status
4. Review webhook event processing status

**Recovery**:
1. Update GitHub App permissions
2. Rotate private key
3. Wait for rate limit cooldown (typically 1 hour)

### PR Comment Publishing Failures

**Symptoms**: PR comments not appearing

**Investigation**:
1. Check GitHub App has `pull_requests:write` permission
2. Verify PR is not locked
3. Check rate limit status
4. Review webhook event processing status

**Recovery**:
1. Update GitHub App permissions
2. Unlock PR if necessary
3. Wait for rate limit cooldown

---

## Dead-Letter Job Management

### Viewing Dead-Letter Jobs

```bash
GET /api/repositories/{id}/cicd/pipeline-jobs/dead-letter
```

### Retrying a Job

```bash
POST /api/repositories/{id}/cicd/pipeline-jobs/{job_id}/retry
```

**Rules**:
- Job moves to `RETRY_PENDING` status
- Worker will pick up job on next cycle
- Max retry attempts: 5 (configurable)
- Audit event logged

### Canceling a Job

```bash
POST /api/repositories/{id}/cicd/pipeline-jobs/{job_id}/cancel
```

**Rules**:
- Job moves to `CANCELLED` status
- Cannot cancel completed jobs
- Audit event logged

### When to Retry vs Cancel

- **Retry**: Transient failures (network issues, rate limits)
- **Cancel**: Permanent failures (invalid configuration, revoked tokens)

---

## CI Token Revocation

### When to Revoke

- Token compromised or leaked
- Token no longer needed
- Repository access revoked
- Security incident

### Revocation Steps

1. Navigate to repository settings
2. Go to "CI/CD Integration" → "CI Tokens"
3. Find token to revoke
4. Click "Revoke"
5. Confirm revocation

### Post-Revocation

- Remove token from GitHub repository secrets
- Create new token if needed
- Update GitHub Actions workflow
- Verify new token works

### Audit Trail

All revocations are logged in audit trail:
```bash
GET /api/repositories/{id}/cicd/audit
```

---

## Artifact Redaction Verification

### What Gets Redacted

- Raw CI tokens
- Token hashes
- Authorization headers
- GitHub tokens
- GitHub private keys
- Webhook secrets
- Secret environment variables

### Verification Steps

1. **Generate Artifact**
   ```bash
   GET /api/repositories/{id}/artifacts/{artifact_id}
   ```

2. **Inspect Artifact**
   - Check for redacted fields
   - Verify no secrets in plain text
   - Verify no sensitive metadata

3. **Audit Trail Review**
   ```bash
   GET /api/repositories/{id}/cicd/audit
   ```
   - Verify redaction in metadata_summary
   - Verify sensitive fields show `[REDACTED]`

---

## GitHub Rate Limit Response

### Rate Limit States

- **Normal**: Under rate limit
- **Cooldown**: Rate limit exceeded, in cooldown period
- **Blocked**: Exceeded cooldown threshold

### Checking Rate Limit Status

```bash
GET /api/repositories/{id}/cicd/health
```

Look for "GitHub publishing" health check.

### Cooldown Duration

- Default: 15 minutes
- Configurable via environment variables

### During Cooldown

- Status checks may be delayed
- PR comments may be delayed
- Webhook processing continues
- Jobs queue but don't publish

### Recovery

- Wait for cooldown to expire
- Reduce API call frequency
- Consider caching strategies
- Contact GitHub for rate limit increase if needed

---

## Known Limitations

### 1. Webhook Event Filtering

- Webhook events are not filtered by repository_id in diagnostics
- All webhook events are returned (limited to 100 most recent)
- Future enhancement: Add proper repository filtering

### 2. Real-Time Metrics

- Metrics are calculated on-demand
- Not cached (may be slow for large repositories)
- Future enhancement: Add metrics caching

### 3. Alert Deduplication

- Similar alerts may be created if not resolved
- No automatic alert suppression
- Future enhancement: Add alert deduplication logic

### 4. Dead-Letter Job Automation

- No automatic retry of dead-letter jobs
- Manual operator intervention required
- Future enhancement: Add automatic retry policies

### 5. SLO Monitoring

- SLO thresholds are defined in code
- No real-time SLO monitoring/alerting
- Future enhancement: Add SLO monitoring dashboard

### 6. Artifact Storage

- Artifacts stored in database (not scalable)
- Future enhancement: Move to object storage (S3, GCS)

### 7. Worker Scaling

- Single worker instance
- No automatic scaling
- Future enhancement: Add worker pool and scaling

---

## Emergency Contacts

- **Platform Operations**: [contact]
- **GitHub Integration**: [contact]
- **Security Team**: [contact]

---

## Appendix: API Reference

### Metrics Endpoint

```
GET /api/repositories/{repository_id}/cicd/metrics
```

Returns pipeline runs, jobs, performance, GitHub publishing, artifacts, and CI token metrics.

### Health Endpoint

```
GET /api/repositories/{repository_id}/cicd/health
```

Returns overall health status and individual health checks.

### Alerts Endpoint

```
GET /api/repositories/{repository_id}/cicd/alerts
POST /api/repositories/{repository_id}/cicd/alerts/evaluate
```

Get active alerts or evaluate health and create alerts.

### Dead-Letter Jobs Endpoint

```
GET /api/repositories/{repository_id}/cicd/pipeline-jobs/dead-letter
POST /api/repositories/{repository_id}/cicd/pipeline-jobs/{job_id}/retry
POST /api/repositories/{repository_id}/cicd/pipeline-jobs/{job_id}/cancel
```

List, retry, or cancel dead-letter jobs.

### Webhook Events Endpoint

```
GET /api/repositories/{repository_id}/cicd/github/webhook-events
```

Get webhook delivery diagnostics.

### Audit Endpoint

```
GET /api/repositories/{repository_id}/cicd/audit
```

Get CI/CD audit events with sensitive fields redacted.
