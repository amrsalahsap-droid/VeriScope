# Workspace Governance Pre-RC Execution Plan

This execution plan outlines the exact next steps required to resolve active blockers and verify the Workspace Governance system for Release Candidate (RC) readiness.

---

## Next-Step Execution Sequence

### Step 1: Complete Phase 8.11D RBAC Actual HTTP Proof
* **Goal**: Prove RBAC roles and path permissions enforce security boundaries over real HTTP requests.
* **Required Environment**: Deployed staging environment with test clients.
* **Required Users/Tokens**: Staging test users (GOVERNANCE_OWNER, POLICY_ADMIN, no_role_user) with valid OAuth tokens.
* **Required Data**: Seeded role assignments database.
* **Expected Evidence**: Automated HTTP test runner execution logs showing correct status code returns.
* **Pass/Fail Criteria**:
  * **Pass**: 100% of tested routes enforce role limits and return 401/403 for unauthorized users.
  * **Fail**: Any endpoint allows access to unauthorized users or fails with internal 500 errors.

---

### Step 2: Complete Phase 8.12 Live Notification Validation
* **Goal**: Validate notification worker loops, preference handlers, and SMTP dispatch functionality.
* **Required Environment**: Connected staging mailserver (SMTP) with notification loop worker active.
* **Required Users/Tokens**: Test admin user accounts with verified email addresses.
* **Required Data**: Triggered repository policy drift or expiring role configuration in database.
* **Expected Evidence**: Staging SMTP delivery logs showing notifications sent and corresponding user inbox receipts.
* **Pass/Fail Criteria**:
  * **Pass**: Email alerts are delivered successfully, match template parameters, and obey user preferences.
  * **Fail**: Emails are lost, system crashes on worker scans, or muted alerts are still dispatched.

---

### Step 3: Complete Phase 8.6D Real GitHub App RC Validation
* **Goal**: Validate real commit status updates, webhook receptions, and repository selections using a live GitHub App setup.
* **Required Environment**: GitHub App connected to staging server via public proxy/tunnel (e.g. ngrok).
* **Required Users/Tokens**: Staging repository with installed GitHub App credentials.
* **Required Data**: Triggered commit pushes and pull request operations.
* **Expected Evidence**: GitHub commit check logs showing published status check indicators from VeriScope.
* **Pass/Fail Criteria**:
  * **Pass**: Commit status matches quality gate score; webhook receives payloads without missing events.
  * **Fail**: Webhook parsing errors, status checks not published, or security credentials exposed in payloads.

---

### Step 4: Re-run Final Governance Smoke Checks
* **Goal**: Confirm that all manual remediation and access review controls operate as expected.
* **Required Environment**: Local or staging testing database.
* **Required Users/Tokens**: Staging test owners and policy managers.
* **Required Data**: Seeded review findings and policy exceptions.
* **Expected Evidence**: Test execution reports confirming draft workflows, confirmation text validations, and lockout safety behaviors.
* **Pass/Fail Criteria**:
  * **Pass**: All manual remediations transition through states correctly; last owner lockout blocks deactivations.
  * **Fail**: Any automated mutations, database inconsistencies, or lockout bypass.

---

### Step 5: Produce RC Readiness Decision
* **Goal**: Sign off and mark the CI/CD module Release Candidate (RC) ready.
* **Required Environment**: Release sign-off dashboard.
* **Required Users/Tokens**: Release Manager.
* **Required Data**: Staging validation reports from Step 1, Step 2, and Step 3.
* **Expected Evidence**: Consolidated QA sign-off document with updated status checklist.
* **Pass/Fail Criteria**:
  * **Pass**: All GAP blockers resolved, checklists complete, and release tag published.
  * **Fail**: Missing validation logs or outstanding blocker status still active.
