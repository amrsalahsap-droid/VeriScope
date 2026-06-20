# CI/CD Production Readiness Checklist

This checklist must be completed before deploying Veriscope CI/CD integration to production.

## Prerequisites

- [ ] Veriscope backend deployed and accessible
- [ ] Database migrations applied
- [ ] Redis available (if token cache is used)
- [ ] GitHub organization admin access
- [ ] Target repositories identified

---

## GitHub App Configuration

### App Installation

- [ ] GitHub App created in organization
- [ ] App permissions configured:
  - [ ] `checks:write` - for status check publishing
  - [ ] `pull_requests:write` - for PR comment publishing
  - [ ] `contents:read` - for repository access
  - [ ] `members:read` - for organization access (if needed)
- [ ] Webhook URL configured: `https://<your-domain>/api/github/webhook`
- [ ] Webhook secret generated and stored securely
- [ ] Private key downloaded and stored securely
- [ ] App installed to target organization
- [ ] App installed to target repositories

### Backend Configuration

- [ ] Environment variables set:
  - [ ] `GITHUB_APP_ID` - GitHub App ID
  - [ ] `GITHUB_PRIVATE_KEY` - Path to or contents of private key
  - [ ] `GITHUB_WEBHOOK_SECRET` - Webhook secret
- [ ] Backend service restarted after configuration
- [ ] Webhook endpoint accessible from GitHub
- [ ] Webhook signature verification tested

---

## CI Token Management

### Token Creation

- [ ] CI token created for each target repository
- [ ] Token stored securely in GitHub repository secrets
- [ ] Secret name: `VERISCOPE_CI_TOKEN`
- [ ] Token expiration date noted (default 90 days)
- [ ] Token rotation schedule defined

### Token Verification

- [ ] Token can be used to trigger pipeline runs
- [ ] Token is scoped to correct repository
- [ ] Token cannot be used across repositories
- [ ] Token audit events are being logged

---

## GitHub Actions Configuration

### Workflow Setup

- [ ] GitHub Actions workflow created
- [ ] Workflow triggers on PR events (opened, synchronize, reopened)
- [ ] Workflow calls Veriscope trigger endpoint
- [ ] CI token passed as secret
- [ ] Workflow tested with sample PR

### Workflow Verification

- [ ] Workflow triggers on PR creation
- [ ] Veriscope analysis completes
- [ ] Status check appears on PR
- [ ] PR comment appears on PR
- [ ] Quality gate result is accurate

---

## Worker Process

### Worker Deployment

- [ ] Async worker process deployed
- [ ] Worker configured with correct database connection
- [ ] Worker configured with correct Redis connection (if used)
- [ ] Worker process running and stable
- [ ] Worker process monitored (health checks, logs)

### Worker Verification

- [ ] Worker can claim pending jobs
- [ ] Worker can process jobs successfully
- [ ] Worker handles retry logic correctly
- [ ] Worker moves failed jobs to dead-letter
- [ ] Worker logs are being captured

---

## Database

### Migrations

- [ ] All database migrations applied
- [ ] `pipeline_runs` table exists
- [ ] `pipeline_execution_jobs` table exists
- [ ] `cicd_alerts` table exists
- [ ] `ci_tokens` table exists
- [ ] `ci_token_audit_events` table exists
- [ ] `webhook_events` table exists

### Database Verification

- [ ] Database connection stable
- [ ] Database backup strategy in place
- [ ] Database replication configured (if needed)
- [ ] Database performance monitored

---

## Redis (if used)

### Redis Configuration

- [ ] Redis instance deployed
- [ ] Redis connection configured in backend
- [ ] Redis connection tested
- [ ] Redis persistence configured
- [ ] Redis backup strategy in place

### Redis Verification

- [ ] Token caching works correctly
- [ ] Cache invalidation works correctly
- [ ] Redis connection stable
- [ ] Redis performance monitored

---

## Monitoring and Observability

### Metrics

- [ ] Metrics endpoint accessible: `GET /api/repositories/{id}/cicd/metrics`
- [ ] Metrics return correct data
- [ ] Metrics include pipeline runs, jobs, performance
- [ ] Metrics include GitHub publishing, artifacts, CI tokens

### Health Checks

- [ ] Health endpoint accessible: `GET /api/repositories/{id}/cicd/health`
- [ ] Health checks return correct status
- [ ] Health checks include worker, backlog, dead-letter
- [ ] Health checks include publishing, artifacts, tokens

### Alerts

- [ ] Alerts endpoint accessible: `GET /api/repositories/{id}/cicd/alerts`
- [ ] Alert evaluation works: `POST /api/repositories/{id}/cicd/alerts/evaluate`
- [ ] Alerts are created for degraded/critical states
- [ ] Alerts include recommended actions

### Webhook Diagnostics

- [ ] Webhook events endpoint accessible: `GET /api/repositories/{id}/cicd/github/webhook-events`
- [ ] Webhook events are logged
- [ ] Webhook signature status is tracked
- [ ] Webhook processing status is tracked

### Audit Trail

- [ ] Audit endpoint accessible: `GET /api/repositories/{id}/cicd/audit`
- [ ] CI token operations are audited
- [ ] Pipeline operations are audited
- [ ] Artifact access is audited
- [ ] Sensitive fields are redacted

---

## Security

### Secret Management

- [ ] GitHub App private key stored securely
- [ ] Webhook secret stored securely
- [ ] CI tokens stored securely in GitHub secrets
- [ ] No secrets in code or configuration files
- [ ] Secret rotation schedule defined

### Access Control

- [ ] Only authorized users can access CI/CD endpoints
- [ ] Repository-level access control enforced
- [ ] CI tokens scoped to repositories
- [ ] Artifact access controlled by CI tokens

### Security Verification

- [ ] Webhook signature verification works
- [ ] CI token verification works
- [ ] Artifact redaction works
- [ ] Audit trail redaction works
- [ ] No secrets exposed in API responses

---

## Rate Limiting

### GitHub API Rate Limits

- [ ] Rate limit handling configured
- [ ] Cooldown mechanism works
- [ ] Rate limit status tracked
- [ ] Cooldown duration configured (default 15 minutes)

### Rate Limit Verification

- [ ] Rate limits are respected
- [ ] Cooldown activates when limit exceeded
- [ ] Jobs queue during cooldown
- [ ] Publishing resumes after cooldown

---

## Artifact Security

### Artifact Generation

- [ ] Artifacts can be generated
- [ ] Artifacts include required data
- [ ] Artifacts are stored securely
- [ ] Artifacts have expiration (if applicable)

### Artifact Access

- [ ] Artifacts accessible with valid CI token
- [ ] Artifacts inaccessible without valid token
- [ ] Artifacts inaccessible with wrong repository token
- [ ] Artifact access is audited

### Artifact Redaction

- [ ] Raw CI tokens redacted
- [ ] Token hashes redacted
- [ ] Authorization headers redacted
- [ ] GitHub tokens redacted
- [ ] Webhook secrets redacted
- [ ] Environment variables redacted

---

## Dead-Letter Job Management

### Dead-Letter Operations

- [ ] Dead-letter jobs can be listed: `GET /api/repositories/{id}/cicd/pipeline-jobs/dead-letter`
- [ ] Dead-letter jobs can be retried: `POST /api/repositories/{id}/cicd/pipeline-jobs/{job_id}/retry`
- [ ] Jobs can be cancelled: `POST /api/repositories/{id}/cicd/pipeline-jobs/{job_id}/cancel`
- [ ] Retry/cancel actions are audited

### Dead-Letter Verification

- [ ] Failed jobs move to dead-letter
- [ ] Retry moves job to RETRY_PENDING
- [ ] Cancel moves job to CANCELLED
- [ ] Audit events logged for actions

---

## Evidence Preservation

### Evidence Invariants

- [ ] Recommendation Health: Ready
- [ ] Release Decision: Partially Verified
- [ ] Required Before Release: 6
- [ ] Regression Scope Required: 6
- [ ] Optional: 2
- [ ] Safe to Skip: 16
- [ ] Quality Gate: PARTIAL
- [ ] PR changes: 6

### Evidence Verification

- [ ] Evidence preservation tests pass (38/38)
- [ ] No changes to recommendation health semantics
- [ ] No changes to release decision logic
- [ ] No changes to regression scope logic
- [ ] No changes to quality gate mapping
- [ ] Invariant maintained: Ready ≠ PASSED

---

## E2E Verification

### Real/Sandbox Verification

- [ ] GitHub App installed in test/sandbox environment
- [ ] Test repository configured with webhooks
- [ ] CI token created for test repository
- [ ] GitHub Actions workflow configured
- [ ] Test PR created
- [ ] Pipeline run triggered
- [ ] Status check published
- [ ] PR comment published
- [ ] Quality gate result accurate
- [ ] Artifact accessible with CI token
- [ ] Audit events logged

### Verification Results

- [ ] All E2E verification steps passed
- [ ] No critical issues found
- [ ] All known issues documented

---

## Documentation

### Runbook

- [ ] Production runbook created: `docs/cicd-production-runbook.md`
- [ ] Runbook includes GitHub App installation
- [ ] Runbook includes CI token management
- [ ] Runbook includes GitHub Actions configuration
- [ ] Runbook includes Quality Gate interpretation
- [ ] Runbook includes failure investigation
- [ ] Runbook includes dead-letter management
- [ ] Runbook includes token revocation
- [ ] Runbook includes artifact redaction verification
- [ ] Runbook includes rate limit response
- [ ] Runbook includes known limitations

### Readiness Checklist

- [ ] Production readiness checklist created: `docs/cicd-production-readiness-checklist.md`
- [ ] All checklist items completed
- [ ] Checklist reviewed by operations team
- [ ] Checklist approved for production

---

## Operational Readiness

### Monitoring

- [ ] Metrics dashboard configured
- [ ] Health monitoring configured
- [ ] Alert monitoring configured
- [ ] Log aggregation configured
- [ ] Performance monitoring configured

### Incident Response

- [ ] Incident response plan defined
- [ ] On-call rotation established
- [ ] Escalation path defined
- [ ] Emergency contacts documented

### Backup and Recovery

- [ ] Database backup strategy in place
- [ ] Redis backup strategy in place (if used)
- [ ] Configuration backup strategy in place
- [ ] Recovery procedures tested
- [ ] Recovery time objectives defined

---

## Final Sign-Off

### Pre-Production Review

- [ ] All checklist items completed
- [ ] All tests passing
- [ ] All documentation complete
- [ ] All security measures in place
- [ ] All monitoring configured
- [ ] All backup strategies in place

### Production Deployment

- [ ] Deployment to staging completed
- [ ] Staging verification passed
- [ ] Deployment to production scheduled
- [ ] Production deployment completed
- [ ] Production verification passed

### Post-Deployment

- [ ] Production monitoring active
- [ ] Production logs being captured
- [ ] Production metrics being collected
- [ ] Production alerts being received
- [ ] Production health status green

---

## Signatures

- [ ] **Engineering Lead**: ______________________ Date: _______
- [ ] **Operations Lead**: ______________________ Date: _______
- [ ] **Security Lead**: ______________________ Date: _______
- [ ] **Product Owner**: ______________________ Date: _______

---

## Notes

Additional notes, exceptions, or special considerations:

_________________________________________________________________________

_________________________________________________________________________

_________________________________________________________________________
