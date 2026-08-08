# Phase 10 — Production Deployment Readiness

## Overview
Phase 10 validates production deployment readiness through comprehensive verification of external integrations, infrastructure dependencies, secret safety, and operational procedures.

## Verification Components

### 1. Secret Safety Verification
**Script:** `scripts/verify_secret_safety.py`

**Purpose:** Scans the repository for hardcoded credentials and classifies findings into:
- `REAL_SECRET`: Actual credentials exposed in code or docs
- `PLACEHOLDER`: Fake/sample values or documentation examples
- `FALSE_POSITIVE`: Substring matches that are code logic
- `ACCEPTED_ENV_REFERENCE`: Code fetching keys from environment variables

**Execution:**
```bash
.venv\Scripts\python scripts/verify_secret_safety.py
```

**Success Criteria:**
- Zero `REAL_SECRET` findings
- All other classifications are acceptable

**Failure Action:**
- Review and remediate any real secrets found
- Re-run verification until clean

---

### 2. Production HTTP Readiness Verification
**Script:** `scripts/verify_production_readiness_real_http.py`

**Purpose:** E2E HTTP smoke tests against running FastAPI backend with PostgreSQL

**Validates:**
- Health and Auth APIs
- Governance RBAC boundaries (expired roles, inactive roles, cross-workspace rejections)
- Audit logs (structured JSON payloads, request/correlation IDs, searchable fields)
- Artifact Storage (authorized access passes, unauthorized/cross-workspace/expired access rejected with 403)
- Notification dismissal
- Outcome ingestion and retrieval
- Evidence preservation invariants

**Execution:**
```bash
.venv\Scripts\python scripts/verify_production_readiness_real_http.py
```

**Success Criteria:**
- All HTTP tests pass
- All DB invariants verified
- Audit logs created with proper structure
- Evidence counts preserved

**Failure Action:**
- Review failed tests
- Fix RBAC, audit, or artifact access issues
- Re-run verification

---

### 3. Worker Queue Readiness Verification
**Script:** `scripts/verify_worker_queue_readiness.py`

**Purpose:** Validates background queue subsystem

**Validates:**
- Redis connectivity
- RQ queue "veriscope_sync" existence
- RQ worker running status
- Inline fallback disabled in production mode
- Test job enqueue and execution
- Failed job visibility and retry policies

**Execution:**
```bash
.venv\Scripts\python scripts/verify_worker_queue_readiness.py
```

**Success Criteria:**
- Redis connection successful
- Worker active on "veriscope_sync" queue
- Test job executes successfully
- Inline fallback configuration verified

**Failure Action:**
- Start Redis server if not running
- Start RQ worker if not active
- Verify production environment configuration
- Re-run verification

---

### 4. GitHub App Production Readiness Verification
**Script:** `scripts/verify_github_app_production_readiness.py`

**Purpose:** Validates GitHub integration using real API calls

**Validates:**
- Installation resolution
- Changeset fetching (changed files list)
- Check status/run posting
- PR comment posting
- Webhook signature validation (invalid signatures rejected)

**Execution:**
```bash
.venv\Scripts\python scripts/verify_github_app_production_readiness.py
```

**Success Criteria:**
- GitHub App installation resolves
- API calls succeed with proper authentication
- Webhook signatures validated correctly
- Invalid signatures rejected

**Failure Action:**
- Verify GitHub App credentials
- Check GitHub App permissions and scopes
- Verify webhook secret configuration
- Re-run verification

---

### 5. Database Migration Readiness
**Command:** Alembic current

**Purpose:** Verifies database migration status

**Execution:**
```bash
.venv\Scripts\python -m alembic current
```

**Success Criteria:**
- Current revision matches head
- Single head confirmed
- No pending migrations

**Failure Action:**
- Run pending migrations: `alembic upgrade head`
- Verify migration success
- Re-run verification

---

## Deployment Documentation

### Required Documentation
All deployment documentation is located in `docs/deployment/`:

1. **environment-config-checklist.md** - Environment variables, CORS, and limits validation
2. **migration-runbook.md** - Alembic operations, rollback commands, backup procedures
3. **worker-queue-runbook.md** - Redis/RQ configuration, worker daemon, retry policies
4. **github-app-production-runbook.md** - App permissions, scopes, webhooks, key rotation
5. **rollback-plan.md** - Code rollbacks, DB downgrade, worker recovery, webhook settings
6. **incident-response-runbook.md** - Outages, manual recovery, audit trail scans

---

## Verification Sequence

### Pre-Deployment Checklist
1. ✅ Run secret safety scan
2. ✅ Verify database migration head
3. ✅ Verify worker queue readiness
4. ✅ Verify GitHub App production readiness
5. ✅ Run production HTTP smoke tests
6. ✅ Review all deployment documentation
7. ✅ Confirm environment configuration checklist complete

### Production Deployment Decision
**Option A (RC READY):** All verification tests pass with real infrastructure (no simulation)
- Real PostgreSQL database
- Real Redis/RQ queue
- Real GitHub App API access
- Production environment URLs
- No secrets exposed

**Option B (READY WITH ACCEPTED RISKS):** All tests pass but with simulation/fallback
- Local PostgreSQL instead of production
- Mock Redis/RQ instead of real queue
- Test GitHub App instead of production
- Documented risks accepted

**Option C (BLOCKED):** Any critical test fails
- Secret safety scan finds real secrets
- Migration not at head
- Worker queue not operational
- GitHub App API failures
- HTTP smoke test failures

---

## Final Output

After completing all verification steps, generate the final result:
```bash
# Manual compilation of verification results into:
PHASE_10_PRODUCTION_DEPLOYMENT_READINESS_RESULT.md
```

This document should include:
- All verification script outputs
- Pass/fail status for each component
- Any issues found and remediation steps
- Final deployment decision (A/B/C)
- Remaining risks if Option B selected
