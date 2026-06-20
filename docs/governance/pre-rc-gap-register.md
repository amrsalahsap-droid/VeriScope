# Workspace Governance Pre-RC Gap Register

This document registers all outstanding gaps that block marking the CI/CD module Release Candidate (RC) ready.

---

## GAP-001: Phase 8.6D Real GitHub RC Validation Pending
* **Gap ID**: GAP-001
* **Title**: Phase 8.6D Real GitHub RC Validation Pending
* **Severity**: `RC_BLOCKER`
* **Area**: CI/CD GitHub App Integration
* **Why it matters**: Without validation against a live GitHub App setup, webhook event delivery, status check updates, and branch protection configurations cannot be verified in a real multi-tenant setting.
* **Current Status**: Backend structure is complete; mock tests pass. Real execution is pending credentials.
* **Owner Role**: Lead Systems Engineer
* **Entry Criteria**: Configured GitHub App with webhook URL pointed to staging server.
* **Exit Criteria**: Successful end-to-end webhook delivery and status publishing verification on a real commit.
* **Evidence Required**: Webhook delivery logs, published status check badge on GitHub commit.
* **Recommended Next Phase**: Phase 8.6D Live Integrations.

---

## GAP-002: Phase 8.11D RBAC Actual HTTP Proof Pending
* **Gap ID**: GAP-002
* **Title**: Phase 8.11D RBAC Actual HTTP Proof Pending
* **Severity**: `RC_BLOCKER`
* **Area**: RBAC / REST API Security
* **Why it matters**: Verify that the FastAPI routers enforce authentication, token verification, and permission checks over actual HTTP requests (and not just client mock clients).
* **Current Status**: All routes contain auth dependencies; unit tests verify service calls. Integration HTTP proof is pending.
* **Owner Role**: Security Engineer
* **Entry Criteria**: Deployed staging environment with test clients.
* **Exit Criteria**: Automated test run confirming 100% of routes return 401/403 when tokens are missing/invalid.
* **Evidence Required**: Test runner HTTP report verifying status codes.
* **Recommended Next Phase**: Phase 8.11D Live Integrations.

---

## GAP-003: Phase 8.12 Live Notification Validation Pending
* **Gap ID**: GAP-003
* **Title**: Phase 8.12 Live Notification Validation Pending
* **Severity**: `RC_BLOCKER`
* **Area**: Alerting & Notifications
* **Why it matters**: Ensures the notification scanning worker loops do not lag, database deduplication logic operates, and email delivery actually triggers under normal load.
* **Current Status**: Scan loops and tables implemented. SMTP mock validation passes. Staging mailserver verification is pending.
* **Owner Role**: DevOps Engineer
* **Entry Criteria**: Connected SMTP mailserver credentials and configured preferences in staging.
* **Exit Criteria**: Verify email receipt for policy drift and exception requests.
* **Evidence Required**: Staging SMTP server dispatch logs.
* **Recommended Next Phase**: Phase 8.12 Live Integrations.

---

## GAP-004: CI/CD Module RC Readiness Blocked
* **Gap ID**: GAP-004
* **Title**: CI/CD Module RC Readiness Blocked
* **Severity**: `RC_BLOCKER`
* **Area**: Release Management / Compliance
* **Why it matters**: Standard safety requirement. No Release Candidate can be signed off while outstanding validation gaps (GAP-001, GAP-002, GAP-003) remain open.
* **Current Status**: Blocked.
* **Owner Role**: Release Manager
* **Entry Criteria**: Resolution and closure of GAP-001, GAP-002, and GAP-003.
* **Exit Criteria**: Quality gate reviews pass and sign-off signature updated.
* **Evidence Required**: Signed RC verification checklist.
* **Recommended Next Phase**: Phase 8.17 Sign-off.
