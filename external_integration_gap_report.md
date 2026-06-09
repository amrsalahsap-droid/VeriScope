# External Work Item and Test Management Integration Gap Report

**Date:** 2026-06-02
**Purpose:** Assess current Veriscope support for external work items (Jira, Azure DevOps) and test management tools (TestRail, Xray, Zephyr)

---

## Executive Summary

Veriscope has foundational infrastructure for external integrations but lacks critical implementation for Jira/Azure work item extraction and test management system connectors. The system has:

- **Existing:** AcceptanceCriteriaExtractor, ExternalTestCaseReference model, TestManagementConnector interface
- **Missing:** Issue key extraction, credential storage, TMS connector implementations, recommendation integration

**Gap Status:** 7/9 critical features missing

---

## Detailed Findings

### 1. Jira/Azure Issue Key Extraction

**Status:** ❌ NOT IMPLEMENTED

**Current State:**
- PullRequest model has `title`, `source_branch`, `target_branch` fields
- No service for extracting issue keys from PR title/body/branch
- No storage for linked issue URLs
- No pattern matching for Jira (e.g., `PROJ-123`) or Azure (e.g., `12345`) formats

**Gap:**
- No `linked_issue_keys` field on PullRequest
- No `linked_issue_urls` field on PullRequest
- No `IssueKeyExtractor` service
- No integration with GitHub API to fetch linked issues

**Impact:** Cannot trace PRs to Jira/Azure work items for business context

---

### 2. Linked Issue URL Storage

**Status:** ❌ NOT IMPLEMENTED

**Current State:**
- PullRequest model has no fields for linked issue URLs
- No relationship to external work item system
- No GitHub API integration to fetch linked issues from PR body

**Gap:**
- No `linked_issue_urls` field (JSONB array)
- No `IssueReference` model
- No GitHub API client method to fetch linked issues

**Impact:** Cannot display or link to external work items in recommendations

---

### 3. Business Intent Extraction

**Status:** ❌ NOT IMPLEMENTED

**Current State:**
- No `BusinessIntentExtractor` service found
- AcceptanceCriteriaExtractor exists but focuses on AC lists, not business intent
- No classification of business impact (e.g., "customer-facing", "internal tool")

**Gap:**
- No business intent classification
- No business impact scoring
- No integration with work item business priority fields

**Impact:** Cannot prioritize recommendations based on business impact

---

### 4. Acceptance Criteria Import

**Status:** ✅ PARTIALLY IMPLEMENTED

**Current State:**
- `AcceptanceCriteriaExtractor` service exists
- Can extract from PR description and linked story text
- Supports classification (FUNCTIONAL, VALIDATION, SECURITY, UI, API, etc.)
- `AcceptanceCriterion` model exists with repository and PR relationships
- Normalization and deduplication implemented

**Gap:**
- No integration with Jira/Azure API to fetch AC from work items
- No mapping from external AC to test scenarios
- No AC coverage tracking in recommendations

**Impact:** AC extraction works for PR descriptions but not external work items

---

### 5. External Test Case Support

**Status:** ✅ MODEL EXISTS, ❌ NO CONNECTORS

**Current State:**
- `ExternalTestCaseReference` model exists with:
  - `provider` (TESTRAIL, XRAY, ZEPHYR, JIRA, MANUAL)
  - `external_project_id`, `external_test_case_id`
  - `title`, `tags`, `priority`, `business_criticality`
  - Repository-scoped with relationship
- `TestManagementConnector` abstract interface exists
- No concrete implementations (TestRailConnector, XrayConnector, etc.)

**Gap:**
- No TMS connector implementations
- No credential storage for TMS APIs
- No sync jobs for TMS data
- No mapping from ExternalTestCaseReference to TestCase

**Impact:** Model ready but cannot import data from external systems

---

### 6. Manual Test Case Support

**Status:** ✅ SUPPORTED

**Current State:**
- `ExternalTestCaseReference` supports `provider = "MANUAL"`
- Can store manual test metadata (priority, business_criticality)
- Recommendation system can suggest manual validation scenarios

**Gap:**
- No manual test execution tracking
- No manual test result integration

**Impact:** Manual tests can be referenced but execution not tracked

---

### 7. Test Priority/Business Criticality

**Status:** ✅ MODEL EXISTS, ❌ NOT USED IN RECOMMENDATIONS

**Current State:**
- `ExternalTestCaseReference` has `priority` and `business_criticality` fields
- TestCase model has no priority fields
- RecommendationInputBuilder does not include external test case references
- Recommendation logic does not weight by business criticality

**Gap:**
- No priority field on TestCase model
- No business criticality field on TestCase model
- RecommendationInputBuilder does not load ExternalTestCaseReference
- Recommendation scoring does not consider priority/criticality

**Impact:** Cannot boost high-priority tests in recommendations

---

### 8. External Tool Credential Storage

**Status:** ❌ NOT IMPLEMENTED

**Current State:**
- No `IntegrationCredential` model
- No `WorkspaceSetting` model for integration settings
- No `RepositorySetting` model for repository-level credentials
- No encrypted credential storage
- Repository model has no integration fields

**Gap:**
- No credential model (api_key, api_url, username, password)
- No encryption for sensitive credentials
- No workspace-level integration settings
- No repository-level integration settings
- No credential validation service

**Impact:** Cannot securely store API keys for Jira/Azure/TestRail

---

### 9. Recommendation Integration

**Status:** ❌ NOT INTEGRATED

**Current State:**
- `RecommendationInputBuilder` loads:
  - Changed files
  - Test inventory (TestCase)
  - Coverage reports
  - Fragility patterns
- Does NOT load:
  - ExternalTestCaseReference
  - AcceptanceCriterion
  - Linked issue keys/URLs
- Recommendation response schemas do not include external references

**Gap:**
- RecommendationInputBuilder does not include external test case references
- Recommendation response does not show linked issues
- Recommendation response does not show acceptance criteria coverage
- No priority boosting based on external metadata

**Impact:** Recommendations cannot consume imported external data

---

## Missing Models/APIs/UI

### Models Needed

1. **IntegrationCredential** - Store encrypted API credentials
   ```python
   - id, workspace_id, provider (JIRA, AZURE, TESTRAIL, XRAY, ZEPHYR)
   - api_url, api_key_encrypted, username_encrypted
   - is_active, last_validated_at
   ```

2. **WorkspaceIntegrationSetting** - Workspace-level integration config
   ```python
   - id, workspace_id, provider, is_enabled
   - default_project_id, sync_frequency
   ```

3. **RepositoryIntegrationSetting** - Repository-level integration config
   ```python
   - id, repository_id, provider, external_project_id
   - sync_enabled, last_synced_at
   ```

4. **LinkedIssueReference** - Track linked Jira/Azure issues
   ```python
   - id, pull_request_id, issue_key, issue_url, provider
   - title, status, priority, business_impact
   ```

5. **TestCasePriority** - Add priority to TestCase model
   ```python
   - Add priority field to TestCase
   - Add business_criticality field to TestCase
   ```

### Services Needed

1. **IssueKeyExtractor** - Extract Jira/Azure keys from PR
   ```python
   - extract_from_title(title)
   - extract_from_body(body)
   - extract_from_branch(branch)
   - normalize_issue_key(key)
   ```

2. **JiraConnector** - Implement TestManagementConnector for Jira
   ```python
   - connect(credentials)
   - list_projects()
   - list_test_cases(project_id)
   - list_test_runs(project_id)
   - get_acceptance_criteria(issue_key)
   ```

3. **AzureDevOpsConnector** - Implement TestManagementConnector for Azure
   ```python
   - connect(credentials)
   - list_projects()
   - list_work_items(project_id)
   - get_test_cases(project_id)
   ```

4. **TestRailConnector** - Implement TestManagementConnector for TestRail
   ```python
   - connect(credentials)
   - list_projects()
   - list_test_cases(project_id)
   - list_test_runs(project_id)
   ```

5. **XrayConnector** - Implement TestManagementConnector for Xray
   ```python
   - connect(credentials)
   - list_projects()
   - list_test_cases(project_id)
   - get_test_execution_results(project_id)
   ```

6. **CredentialService** - Manage encrypted credentials
   ```python
   - encrypt_credential(plaintext)
   - decrypt_credential(encrypted)
   - validate_credentials(provider, credentials)
   ```

7. **IntegrationSyncService** - Orchestrate TMS sync jobs
   ```python
   - sync_test_cases(repository_id, provider)
   - sync_acceptance_criteria(repository_id, provider)
   - sync_linked_issues(pull_request_id)
   ```

### API Endpoints Needed

1. **Integration Settings API**
   ```
   POST /api/integrations/credentials - Store credentials
   GET /api/integrations/credentials - List credentials
   PUT /api/integrations/credentials/{id} - Update credentials
   DELETE /api/integrations/credentials/{id} - Delete credentials
   POST /api/integrations/validate - Validate credentials
   ```

2. **Repository Integration Settings API**
   ```
   POST /api/repositories/{id}/integrations - Configure repo integration
   GET /api/repositories/{id}/integrations - Get repo integration config
   PUT /api/repositories/{id}/integrations - Update repo integration
   POST /api/repositories/{id}/integrations/sync - Trigger sync
   ```

3. **Linked Issues API**
   ```
   GET /api/pull-requests/{id}/linked-issues - Get linked issues
   POST /api/pull-requests/{id}/linked-issues/sync - Sync linked issues
   ```

4. **External Test Cases API**
   ```
   GET /api/repositories/{id}/external-test-cases - List external test cases
   POST /api/repositories/{id}/external-test-cases/sync - Sync test cases
   ```

### UI Components Needed

1. **Integration Settings Page** - Configure Jira/Azure/TestRail credentials
2. **Repository Integration Config** - Map repositories to external projects
3. **Linked Issues Panel** - Show Jira/Azure issues linked to PR
4. **External Test Cases Table** - View imported test cases
5. **Sync Status Dashboard** - Monitor integration sync jobs

---

## Implementation Order

### Phase 1: Foundation (Week 1-2)
**Priority: CRITICAL**

1. **Create credential storage model**
   - `IntegrationCredential` model with encryption
   - `WorkspaceIntegrationSetting` model
   - `RepositoryIntegrationSetting` model
   - `CredentialService` for encryption/decryption

2. **Create credential management API**
   - CRUD endpoints for credentials
   - Validation endpoint
   - UI for credential management

3. **Add issue extraction to PullRequest**
   - Add `linked_issue_keys` field (JSONB array)
   - Add `linked_issue_urls` field (JSONB array)
   - Create `IssueKeyExtractor` service
   - Integrate extraction into PR sync pipeline

**Deliverable:** Secure credential storage and issue key extraction

---

### Phase 2: Jira Integration (Week 3-4)
**Priority: HIGH**

4. **Implement JiraConnector**
   - Implement TestManagementConnector interface
   - Add Jira API client
   - Implement project/test case/test run listing
   - Implement acceptance criteria fetching

5. **Create Jira sync service**
   - `IntegrationSyncService` for Jira
   - Sync job scheduling
   - Sync to ExternalTestCaseReference
   - Sync to AcceptanceCriterion

6. **Integrate Jira into recommendations**
   - Update RecommendationInputBuilder to load ExternalTestCaseReference
   - Update RecommendationInputBuilder to load AcceptanceCriterion
   - Add priority boosting based on business_criticality
   - Update recommendation response schemas

**Deliverable:** Full Jira integration with recommendation consumption

---

### Phase 3: Azure DevOps Integration (Week 5-6)
**Priority: HIGH**

7. **Implement AzureDevOpsConnector**
   - Implement TestManagementConnector interface
   - Add Azure DevOps API client
   - Implement work item/test case listing
   - Implement acceptance criteria fetching

8. **Create Azure sync service**
   - Extend IntegrationSyncService for Azure
   - Sync job scheduling
   - Sync to ExternalTestCaseReference
   - Sync to AcceptanceCriterion

**Deliverable:** Full Azure DevOps integration

---

### Phase 4: Test Management Tools (Week 7-8)
**Priority: MEDIUM**

9. **Implement TestRailConnector**
   - Implement TestManagementConnector interface
   - Add TestRail API client
   - Implement project/test case/test run listing

10. **Implement XrayConnector**
    - Implement TestManagementConnector interface
    - Add Xray API client
    - Implement project/test case/test execution listing

11. **Create TMS sync services**
    - Sync to ExternalTestCaseReference
    - Sync job scheduling
    - Manual test execution tracking

**Deliverable:** TestRail and Xray integrations

---

### Phase 5: Recommendation Enhancement (Week 9-10)
**Priority: HIGH**

12. **Add priority to TestCase model**
    - Add `priority` field
    - Add `business_criticality` field
    - Migration script to populate from ExternalTestCaseReference

13. **Enhance recommendation scoring**
    - Weight recommendations by test priority
    - Weight recommendations by business criticality
    - Boost MUST scenarios for high-criticality areas

14. **Update recommendation UI**
    - Show linked issues in recommendation detail
    - Show acceptance criteria coverage
    - Show external test case references
    - Show priority/criticality indicators

**Deliverable:** Priority-aware recommendations with external context

---

### Phase 6: Advanced Features (Week 11-12)
**Priority: LOW**

15. **Business intent extraction**
    - Create BusinessIntentExtractor service
    - Classify business impact from work items
    - Integrate into recommendation prioritization

16. **Automated sync scheduling**
    - Cron jobs for periodic sync
    - Webhook-based sync triggers
    - Sync conflict resolution

17. **Advanced reporting**
    - Coverage reports by business criticality
    - Fragility reports by business impact
    - Integration health dashboards

**Deliverable:** Advanced business intelligence features

---

## Risk Assessment

### High Risk Items

1. **Credential Security** - Must implement proper encryption
   - Use AWS KMS or similar for encryption
   - Never log credentials
   - Rotate credentials periodically

2. **API Rate Limits** - External APIs have rate limits
   - Implement exponential backoff
   - Cache responses where possible
   - Monitor rate limit usage

3. **Data Consistency** - Sync conflicts between systems
   - Implement conflict resolution strategy
   - Use last-write-wins with timestamps
   - Provide manual override capability

### Medium Risk Items

1. **Mapping Complexity** - Mapping external entities to Veriscope entities
   - Allow manual mapping configuration
   - Provide mapping suggestions
   - Support custom mapping rules

2. **Performance Impact** - Sync jobs may slow down recommendations
   - Run sync jobs asynchronously
   - Use background workers
   - Cache sync results

---

## Summary

**Current State:** Foundation exists (models, interfaces) but critical implementations missing

**Critical Gaps:**
1. Issue key extraction from PRs
2. Credential storage for external APIs
3. TMS connector implementations
4. Recommendation integration with external data

**Implementation Timeline:** 12 weeks for full implementation

**Recommended Start:** Phase 1 (Foundation) - Credential storage and issue extraction

**Success Criteria:**
- Jira/Azure issue keys extracted from PRs
- External test cases imported and visible in recommendations
- Priority/criticality influences recommendation scoring
- Credentials stored securely with encryption
