# Deliverable 6B Phase 3: Outcome Tracking Audit

## Inspection Summary

### 1. Does every recommendation run have an outcome record?

**NO** - `RecommendationRun.outcome` is an optional relationship (uselist=False, nullable in DB). A `RecommendationOutcome` record is only created when:
- Manual API call to `POST /recommendations/{id}/outcome`
- Manual API call to `POST /recommendations/{id}/feedback`

Most recommendation runs do NOT have an outcome record automatically.

### 2. Are recommended tests linked to actual executed tests?

**PARTIALLY** - Two mechanisms exist but are not automatically connected:

**Mechanism 1: RecommendationTestOutcome (granular)**
- `RecommendationTestOutcome.test_case_id` links to `TestCase`
- `RecommendationTestOutcome.actually_executed` boolean flag
- `RecommendationTestOutcome.execution_result` (PASSED, FAILED, SKIPPED, QUARANTINED, UNKNOWN)
- `RecommendationTestOutcome.execution_presence_status` (EXECUTED, PRESENT_SKIPPED, ABSENT, UNKNOWN)
- Service: `RecommendationExecutedTestCollector` exists to join RecommendationRun → RecommendationTest against TestRun → TestResult
- **NOT automatically called** - requires manual invocation with both `recommendation_run_id` and `test_run_id`

**Mechanism 2: RecommendationOutcome (legacy JSONB)**
- `executed_tests_legacy` (JSONB list of test identifiers)
- Properties: `executed_tests` returns list from either legacy or granular
- **NOT automatically populated** - requires manual API call

### 3. Are manually added tests captured?

**YES** - Via `RecommendationOutcome`:
- `manually_added_tests_legacy` (JSONB)
- Property `manually_added_tests` returns from legacy or granular `RecommendationTestOutcome`
- Granular: `RecommendationTestOutcome.manually_added` boolean flag
- **Requires manual API call** to populate

### 4. Are manually removed tests captured?

**YES** - Via `RecommendationOutcome`:
- `manually_removed_tests_legacy` (JSONB)
- Property `manually_removed_tests` returns from legacy or granular
- Granular: `RecommendationTestOutcome.manually_removed` boolean flag
- **Requires manual API call** to populate

### 5. Is ignored recommendation captured?

**YES** - Via `RecommendationOutcome`:
- `outcome_status` field: PENDING, ACKNOWLEDGED, PARTIALLY_FOLLOWED, FOLLOWED, IGNORED, OVERRIDDEN, ESCAPED_DEFECT_LINKED, ROLLBACK_LINKED
- Property `classification` dynamically computes: trusted, ignored, widened, narrowed, overridden
- Service: `RecommendationIgnoreDetector` exists
- **Requires manual API call** to set outcome_status

### 6. Is engineer feedback captured?

**YES** - Via `RecommendationEngineerFeedback`:
- `feedback_type`: USEFUL, NOT_USEFUL, MISSING_TESTS, TOO_MANY_TESTS, UNCLEAR_REASONING
- `feedback_text`: free text
- `created_by`: engineer identifier
- Relationship: `RecommendationOutcome.feedbacks`
- Properties: `feedback`, `feedback_state` on RecommendationOutcome
- **Requires manual API call** to `POST /recommendations/{id}/feedback`

### 7. Are escaped defects/rollbacks captured?

**YES** - Via `RecommendationOutcome`:
- `escaped_defect_detected` boolean
- `rollback_occurred` boolean
- `RecommendationOutcomeEvidence` table stores evidence snapshots (TEST_RUN, INCIDENT, ROLLBACK, FEEDBACK, OVERRIDE)
- **Requires manual API call** to set these flags

### 8. Is outcome learning connected to future recommendations?

**YES** - Via `LearningEngineV2` and `PatternMemory`:
- `LearningEngineV2.learn(outcome, workspace_id)` updates `PatternMemory`
- `PatternMemory` stores: pattern_key, changed_file_pattern, test_identifier, confidence, usage_count, success_count, defect_count
- Signals processed: MANUAL_ADD, REMOVED, FOLLOWED, DEFECT_ESCAPE, SKIPPED
- Confidence scoring: base + (usage_count * step), capped at 1.0
- **NOT automatically called** - requires manual invocation after outcome finalization

### 9. What models/API/UI are missing?

**Missing Models:**
- None - all necessary models exist

**Missing API Endpoints:**
- Automatic PR execution detection webhook (CI → Veriscope)
- Automatic escaped defect detection webhook (incident system → Veriscope)
- Automatic rollback detection webhook (deployment system → Veriscope)
- Automatic LearningEngineV2 trigger after outcome recording

**Missing UI Components:**
- Feedback buttons on recommendation detail page (useful/not_useful/missing_tests/too_many_tests/unclear_reasoning)
- Manual test addition/removal UI
- Outcome status visualization (FOLLOWED/IGNORED/OVERRIDDEN/etc.)
- Learning diagnostics visualization

**Missing Integrations:**
- Automatic TestRun → RecommendationRun linking via PR
- Automatic outcome creation when TestRun is detected for a PR
- Automatic LearningEngineV2 invocation after outcome finalization
- Behavior/journey intelligence integration into outcome tracking (Phase 2 additions not in outcome models)

---

## Implementation Gaps

### Gap 1: No Automatic Outcome Creation
**Current State:** Outcome records only created via manual API calls
**Impact:** Most recommendation runs have no outcome data for learning
**Severity:** HIGH

### Gap 2: No Automatic PR Execution Detection
**Current State:** TestRun has pull_request_id FK, but no automatic detection
**Impact:** Executed tests not linked to recommendations automatically
**Severity:** HIGH

### Gap 3: No UI Feedback Mechanism
**Current State:** Recommendation detail page has no feedback buttons
**Impact:** Engineers cannot provide feedback from the UI
**Severity:** MEDIUM

### Gap 4: LearningEngineV2 Not Automatically Triggered
**Current State:** LearningEngineV2 exists but requires manual invocation
**Impact:** PatternMemory not updated automatically from outcomes
**Severity:** HIGH

### Gap 5: No Behavior/Journey Intelligence in Outcomes
**Current State:** Phase 2 behavior/journey enhancements not integrated into outcome tracking
**Impact:** Learning cannot leverage behavior/journey signals
**Severity:** MEDIUM

### Gap 6: No SuggestedTestScenario Outcome Tracking
**Current State:** SuggestedTestScenario has no outcome tracking
**Impact:** Cannot learn which scenarios were useful/automated
**Severity:** LOW

### Gap 7: No Automatic Escaped Defect/Rollback Detection
**Current State:** Requires manual API call to set flags
**Impact:** Critical negative events not captured for learning
**Severity:** MEDIUM

---

## Recommended Implementation Sequence

### Phase 3A: Automatic PR Execution Detection
1. Create webhook endpoint: `POST /webhooks/ci/test-run` to receive TestRun completion events
2. On TestRun receipt:
   - Find matching PullRequest via pull_request_id
   - Find RecommendationRun via repository_id + pr_id
   - If match found, call `RecommendationExecutedTestCollector.collect(recommendation_run_id, test_run_id)`
   - Create/update RecommendationOutcome with executed_tests
3. Add fallback polling for CI systems without webhooks

### Phase 3B: UI Feedback Buttons
1. Add feedback component to recommendation detail page
2. Implement feedback buttons: Useful, Not Useful, Missing Tests, Too Many Tests, Unclear Reasoning
3. Add optional text input for feedback details
4. Call `POST /recommendations/{id}/feedback` on button click
5. Display feedback state after submission

### Phase 3C: Automatic Learning Trigger
1. Modify `RecommendationService.record_outcome` to automatically call `LearningEngineV2.learn`
2. Add background job to process pending outcomes without learning
3. Add learning diagnostics endpoint to show PatternMemory state

### Phase 3D: Behavior/Journey Intelligence Integration
1. Add behavior/journey fields to RecommendationTestOutcome:
   - `behavior_id`, `behavior_name`, `impact_type`, `impact_level`
   - `journey_id`, `journey_name`, `journey_risk`
2. Update `RecommendationExecutedTestCollector` to populate these from impact_profile
3. Update `LearningEngineV2` to use behavior/journey signals in confidence scoring

### Phase 3E: SuggestedTestScenario Outcome Tracking
1. Add `SuggestedScenarioOutcome` model
2. Track: scenario_id, automation_status (NOT_AUTOMATED, IN_PROGRESS, AUTOMATED), usefulness_feedback
3. Add UI to mark scenarios as automated/useful
4. Integrate into learning for scenario prioritization

### Phase 3F: Automatic Escaped Defect/Rollback Detection
1. Create webhook endpoint: `POST /webhooks/incidents` for escaped defects
2. Create webhook endpoint: `POST /webhooks/deployments` for rollbacks
3. On incident receipt:
   - Find related PullRequest via commit_sha
   - Find RecommendationOutcome via pull_request_id
   - Set `escaped_defect_detected = True`
   - Create RecommendationOutcomeEvidence record
4. On rollback receipt:
   - Find related PullRequest via commit_sha
   - Find RecommendationOutcome via pull_request_id
   - Set `rollback_occurred = True`
   - Create RecommendationOutcomeEvidence record

### Phase 3G: Outcome Status Visualization
1. Add outcome status badge to recommendation detail page
2. Show classification (trusted/ignored/widened/narrowed/overridden)
3. Display override record if present
4. Show learning impact (PatternMemory changes)

---

## Existing Services Summary

| Service | Purpose | Status |
|---------|---------|--------|
| `RecommendationOutcomeTracker` | Orchestrates learning from finalized outcomes | EXISTS, not auto-triggered |
| `RecommendationExecutedTestCollector` | Links executed tests to recommendations | EXISTS, not auto-triggered |
| `RecommendationOverrideTracker` | Detects and records override lineage | EXISTS |
| `LearningEngineV2` | Updates PatternMemory from outcomes | EXISTS, not auto-triggered |
| `ManualOverrideLearner` | Creates TestCoverageLink from manual additions | EXISTS |
| `RecommendationIgnoreDetector` | Detects ignored recommendations | EXISTS |
| `RecommendationOutcomeDriftDetector` | Detects historical lineage drift | EXISTS |
| `RecommendationOutcomeRecoveryService` | Repairs broken lineage | EXISTS |

---

## Existing API Endpoints Summary

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `POST /recommendations/{id}/outcome` | Record executed/added/removed tests | Public |
| `POST /recommendations/{id}/feedback` | Record engineer feedback | Public |
| `GET /internal/recommendations/{id}/feedback` | Retrieve feedback timeline | Internal |
| `GET /internal/recommendations/{repo_id}/analytics` | Outcome analytics | Internal |
| `GET /internal/recommendations/outcomes/{outcome_id}/drift` | Drift diagnostics | Internal |
| `POST /internal/recommendations/outcomes/{outcome_id}/replay` | Replay classification | Internal |
| `POST /internal/recommendations/outcomes/{outcome_id}/rebuild-snapshot` | Rebuild snapshot | Internal |
| `POST /internal/recommendations/outcomes/{outcome_id}/repair` | Repair broken lineage | Internal |
| `GET /internal/recommendations/repository/{repo_id}/drift` | Repository drift scan | Internal |

---

## Conclusion

**Current State:** The infrastructure for outcome tracking is comprehensive (models, services, APIs exist), but **nothing is automatic**. All outcome data requires manual API calls or manual service invocation.

**Primary Blocker:** No automatic detection of PR execution events from CI systems.

**Recommended First Step:** Implement Phase 3A (Automatic PR Execution Detection) to create the foundation for automatic outcome tracking. Without this, all other enhancements cannot be automatically triggered.
