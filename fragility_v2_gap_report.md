# Fragility V2 Technical Gap Report

## Executive Summary

Current implementation has robust file-based fragility detection with pattern types like FILE_FAILURE_FREQUENCY, CO_FAILURE_PATTERN, DEPENDENCY_PROXIMITY, ESCAPED_DEFECT_PATTERN, TEST_CLUSTER_FAILURE, RISKY_COMBINATION, UNSTABLE_MODULE, and ROLLBACK_INVOLVEMENT. However, Behavior/Journey-aware fragility is partially implemented but not fully integrated into recommendation scoring.

---

## 1. What Fragility Data Is Currently Stored?

### Core Models

**FragilityPattern** (`app/models/fragility_pattern.py`)
- Pattern types: FILE_FAILURE_FREQUENCY, CO_FAILURE_PATTERN, DEPENDENCY_PROXIMITY, ESCAPED_DEFECT_PATTERN, TEST_CLUSTER_FAILURE, RISKY_COMBINATION, UNSTABLE_MODULE, ROLLBACK_INVOLVEMENT
- Fields: pattern_type, normalized_pattern_key, fragility_score (0-100), risk_level (LOW/MODERATE/HIGH/CRITICAL), confidence_level, score_components, replayable_evidence_snapshot
- Scoping: repository_id
- Tracking: evidence_count, incident_count, related_failure_count, first_seen_at, last_seen_at

**FragilityEvidenceLink** (`app/models/fragility_pattern.py`)
- Links patterns to evidence sources:
  - source_test_run_id
  - source_test_result_id
  - source_incident_id
  - source_recommendation_run_id
  - source_pull_request_id
- Evidence types: TEST_FAILURE, INCIDENT, ROLLBACK, RECOMMENDATION_DEGRADATION, DEPENDENCY_EXPANSION, QUARANTINED_TEST

**FragilitySnapshot** (`app/models/fragility_pattern.py`)
- Immutable ledger of active patterns
- Links to recommendation_run_id
- Tracks: total_patterns, active_patterns, stale_patterns
- Generation triggers: MANUAL_RECALCULATION, SCHEDULED_RECALCULATION, RECOMMENDATION_RUN, DEBUG_REPLAY

**RecommendationOutcome** (`app/models/recommendation.py`)
- Tracks: defect_escaped (boolean), rollback_occurred (boolean)
- Links: pull_request_id, recommendation_run_id
- Stores: fragility_snapshot_hash

**PatternMemory** (`app/models/pattern_memory.py`)
- File-based: pattern_key, changed_file_pattern, test_identifier
- Metrics: confidence, usage_count, success_count, defect_count
- Scoping: workspace_id, repository_id

**PatternMemoryV2** (`app/models/pattern_memory_v2.py`)
- Enhanced with: behavior_id, journey_id, scenario_intent_key
- Signal types: MANUAL_ADDITION, MANUAL_REMOVAL, ACCEPTED_SCENARIO, DISMISSED_SCENARIO, ESCAPED_DEFECT, ROLLBACK, EXECUTION_RESULT
- Metrics: strength, confidence, usage_count, success_count, failure_count, dismissed_count, defect_count, rollback_count
- Scoping: workspace_id, repository_id

**BehaviorImpactRun/Item** (`app/models/behavior_impact.py`)
- BehaviorImpactRun: Links to pull_request_id, recommendation_run_id
- BehaviorImpactItem: behavior_id, journey_id, impact_level, confidence, impact_reason, source_signals, impacted_files, affected_scenarios

**TestRun/TestResult** (`app/models/test_result.py`)
- TestRun: Links to pull_request_id, commit_sha
- TestResult: Links to test_case, test_run

**PullRequestChangedFile** (`app/models/pull_request.py`)
- Links to pull_request_id
- Fields: file_path, status, additions, deletions, patch_hash

---

## 2. Is Fragility File-Based, Test-Based, Behavior-Based, or Journey-Based?

**Current State: Primarily File-Based**

- **File-Based**: YES (primary)
  - FragilityPattern pattern types are file-centric (FILE_FAILURE_FREQUENCY, CO_FAILURE_PATTERN, DEPENDENCY_PROXIMITY, UNSTABLE_MODULE)
  - PatternMemory tracks changed_file_pattern → test_identifier associations
  - Dependency proximity is file-based

- **Test-Based**: PARTIAL
  - TEST_CLUSTER_FAILURE pattern type exists
  - TestResult/TestRun tracking with pull_request linkage
  - FragilityEvidenceLink can link to source_test_result_id

- **Behavior-Based**: PARTIAL (infrastructure exists, not fully utilized)
  - BehaviorImpactRun/Item models exist with behavior_id
  - PatternMemoryV2 has behavior_id field
  - BehaviorImpactAnalyzer service exists
  - RecommendationLogicV3 loads Behavior and BehaviorEvidence
  - **GAP**: No Behavior-specific fragility pattern type
  - **GAP**: Behavior fragility not integrated into FragilityMemoryService

- **Journey-Based**: PARTIAL (infrastructure exists, not fully utilized)
  - BehaviorImpactItem has journey_id field
  - PatternMemoryV2 has journey_id field
  - JourneyBehavior model exists
  - **GAP**: No Journey-specific fragility pattern type
  - **GAP**: Journey fragility not integrated into FragilityMemoryService

---

## 3. Are Escaped Defects Linked to PRs?

**YES**

- RecommendationOutcome has `defect_escaped` boolean flag
- RecommendationOutcome links to `pull_request_id`
- RecommendationOutcome links to `recommendation_run_id`
- FragilityEvidenceLink can link to `source_pull_request_id` and `source_recommendation_run_id`
- ESCAPED_DEFECT_PATTERN pattern type exists in FragilityPattern
- EscapedDefectLinker service links escaped defects to outcomes
- RecommendationOutcomeLearningEngine processes escaped defects (Rule 6)

---

## 4. Are Rollbacks Linked to PRs?

**YES**

- RecommendationOutcome has `rollback_occurred` boolean flag
- RecommendationOutcome links to `pull_request_id`
- RecommendationOutcome links to `recommendation_run_id`
- FragilityEvidenceLink can link to `source_pull_request_id` and `source_recommendation_run_id`
- ROLLBACK_INVOLVEMENT pattern type exists in FragilityPattern
- RollbackOutcomeTracker service links rollbacks to outcomes
- RecommendationOutcomeLearningEngine processes rollbacks (Rule 7)

---

## 5. Are Historical Failures Linked to Changed Files?

**YES**

- FailureEvidenceAggregator collects historical failure evidence within time window
- FragilityEvidenceLink has source_test_result_id → TestResult → TestCase → test runs
- TestRun links to pull_request_id
- PullRequestChangedFile links to pull_request_id with file_path
- FragilityPattern stores normalized_pattern_key (can include file patterns)
- PatternMemory stores changed_file_pattern → test_identifier associations
- FileFailureFrequencyEngine generates file-based fragility patterns

---

## 6. Are Fragility Signals Used in Recommendations?

**YES (File-Based Only)**

- `recommendation.py` line 577-593: Calls `FragilityMemoryService.resolve_fragility_recommendations()`
- Fragility candidates are added to recommendation candidates with base_priority=0.95
- Fragility patterns are matched against changed_files
- **GAP**: Behavior/Journey fragility not integrated into recommendation scoring
- **GAP**: PatternMemoryV2 behavior/journey signals not used in fragility detection

---

## 7. Are Reasons/Evidence Persisted?

**YES**

- FragilityPattern: explanation, score_components, replayable_evidence_snapshot
- FragilityEvidenceLink: evidence_summary, source links
- RecommendationOutcome: feedback_comment, ignored_reason
- BehaviorImpactItem: impact_reason, source_signals
- PatternMemoryV2: signal_type, strength, confidence

---

## 8. What Is Missing for Behavior/Journey-Aware Fragility?

### Critical Gaps

1. **No Behavior-Specific Fragility Pattern Type**
   - Current pattern types are all file/test/dependency-based
   - Need: BEHAVIOR_FAILURE_PATTERN, JOURNEY_FAILURE_PATTERN

2. **Behavior/Journey Fragility Detection Missing**
   - No service to detect behavior-level fragility
   - No service to detect journey-level fragility
   - BehaviorImpactAnalyzer exists but not integrated with fragility

3. **PatternMemoryV2 Behavior/Journey Signals Not Used in Fragility**
   - PatternMemoryV2 has behavior_id, journey_id fields
   - ESCAPED_DEFECT and ROLLBACK signal types exist
   - **GAP**: No service to aggregate these into behavior/journey fragility patterns

4. **Behavior/Journey Evidence Linking Missing**
   - FragilityEvidenceLink has no behavior_id or journey_id fields
   - Cannot link evidence to specific behaviors/journeys

5. **Behavior/Journey Scoring Missing**
   - FragilityScoringEngine has no behavior/journey scoring inputs
   - No behavior/journey-specific risk calculations

6. **Behavior/Journey Recommendation Integration Missing**
   - FragilityMemoryService.resolve_fragility_recommendations() only returns file-based candidates
   - No behavior/journey fragility candidate resolution

### Secondary Gaps

7. **Behavior/Journey Impact Not Used in Recommendations**
   - BehaviorImpactRun/Item data exists
   - RecommendationLogicV3 loads behavior data
   - **GAP**: Behavior impact not used to boost/reduce test/scenario scores

8. **No Behavior/Journey Time-Bound Decay**
   - File patterns have STALE_AFTER_DAYS decay
   - **GAP**: No decay logic for behavior/journey fragility

9. **No Behavior/Journey Confidence Tracking**
   - File patterns have confidence_level based on evidence_count
   - **GAP**: No behavior/journey confidence calculation

---

## Implementation Order

### Phase 1: Extend Data Models (Week 1)
1. Add behavior_id, journey_id to FragilityEvidenceLink
2. Add BEHAVIOR_FAILURE_PATTERN, JOURNEY_FAILURE_PATTERN to FragilityPattern pattern_type validation
3. Add behavior/journey scoring inputs to FragilityScoringEngine

### Phase 2: Behavior/Journey Fragility Detection (Week 2)
1. Create BehaviorFragilityDetector service
   - Aggregate PatternMemoryV2 signals by behavior_id
   - Detect behavior-level failure patterns
   - Create BEHAVIOR_FAILURE_PATTERN patterns
2. Create JourneyFragilityDetector service
   - Aggregate PatternMemoryV2 signals by journey_id
   - Detect journey-level failure patterns
   - Create JOURNEY_FAILURE_PATTERN patterns

### Phase 3: Integrate with FragilityMemoryService (Week 3)
1. Extend FragilityMemoryService.resolve_fragility_recommendations()
   - Return behavior-based candidates
   - Return journey-based candidates
2. Add behavior/journey pattern matching to recommendation candidates
3. Add behavior/journey evidence linking

### Phase 4: Integrate with Recommendation Scoring (Week 4)
1. Extend RecommendationLogicV3
   - Use behavior fragility to boost scenario scores
   - Use journey fragility to boost scenario scores
2. Add behavior/journey impact to test/scenario scoring
3. Add behavior/journey decay logic

### Phase 5: Testing & Validation (Week 5)
1. Create behavior/journey fragility verification tests
2. Create end-to-end learning scenario tests
3. Validate behavior/journey fragility affects recommendations

---

## Summary

**Current State:**
- Robust file-based fragility detection with 8 pattern types
- Escaped defects and rollbacks are tracked and linked to PRs
- Historical failures are linked to changed files
- Fragility signals are used in recommendations (file-based only)
- Reasons/evidence are persisted

**Gaps:**
- No Behavior/Journey-specific fragility pattern types
- Behavior/Journey fragility detection services missing
- PatternMemoryV2 behavior/journey signals not used in fragility
- Behavior/Journey evidence linking missing
- Behavior/Journey scoring missing
- Behavior/Journey recommendation integration missing

**Implementation Priority:**
1. Extend data models (add behavior/journey fields)
2. Create behavior/journey fragility detection services
3. Integrate with FragilityMemoryService
4. Integrate with recommendation scoring
5. Testing & validation
