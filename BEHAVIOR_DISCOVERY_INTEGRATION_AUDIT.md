# Behavior Discovery Integration Audit

**Date**: 2026-06-02  
**Deliverable**: 6B - Behavior Discovery Integration  
**Status**: AUDIT COMPLETE (NO IMPLEMENTATION)

---

## Executive Summary

Behavior and Journey discovery services are **FULLY IMPLEMENTED** but **COMPLETELY ORPHANED**. The discovery engines exist, persist data correctly, but are **NOT WIREDED** into the repository sync flow or recommendation generation. Recommendations currently read only **MANUAL/STATIC behaviors** from the database, not **AUTO-DISCOVERED behaviors**.

**Critical Finding**: The entire behavior discovery pipeline is dead code. No automatic discovery occurs on repository sync.

---

## Component Status Matrix

### Behavior Discovery Components

| Component | Implemented | Executed Automatically | Persisted | Consumed by Recommendations | Orphaned/Dead | Partially Wired |
|-----------|-------------|----------------------|-----------|----------------------------|---------------|----------------|
| **BehaviorDiscoveryEngine** | ✅ YES | ❌ NO | ❌ NO (candidates only) | ❌ NO | ⚠️ PARTIALLY ORPHANED | ⚠️ YES |
| **BehaviorCatalogBuilder** | ✅ YES | ❌ NO | ✅ YES (to DB) | ❌ NO | ❌ ORPHANED | ❌ NO |
| **BehaviorDiscoveryRefreshPipeline** | ✅ YES | ❌ NO | ✅ YES (via CatalogBuilder) | ❌ NO | ❌ ORPHANED | ❌ NO |
| **BehaviorEvidenceAggregator** | ✅ YES | ❌ NO | ❌ NO | ❌ NO | ❌ ORPHANED | ❌ NO |
| **BehaviorConfidenceEngine** | ✅ YES | ❌ NO | ❌ NO | ❌ NO | ❌ ORPHANED | ❌ NO |
| **BehaviorRelationshipEngine** | ✅ YES | ❌ NO | ❌ NO | ❌ NO | ❌ ORPHANED | ❌ NO |
| **BehaviorMergeService** | ✅ YES | ❌ NO | ❌ NO | ❌ NO | ❌ ORPHANED | ❌ NO |

### Journey Discovery Components

| Component | Implemented | Executed Automatically | Persisted | Consumed by Recommendations | Orphaned/Dead | Partially Wired |
|-----------|-------------|----------------------|-----------|----------------------------|---------------|----------------|
| **JourneyDiscoveryEngine** | ✅ YES | ❌ NO | ❌ NO (candidates only) | ❌ NO | ❌ ORPHANED | ❌ NO |
| **JourneyCandidate** | ✅ YES | ❌ NO | ❌ NO | ❌ NO | ❌ ORPHANED | ❌ NO |

### Integration Points

| Integration Point | Behavior Discovery Wired | Journey Discovery Wired | Status |
|-------------------|-------------------------|------------------------|--------|
| **Repository Sync Flow** (github_app.py execute_sync_job) | ❌ NO | ❌ NO | ❌ NOT INTEGRATED |
| **GitHub Sync Flow** (github_app.py sync_repositories_task_wrapper) | ❌ NO | ❌ NO | ❌ NOT INTEGRATED |
| **RecommendationInputBuilder** | ❌ NO | ❌ NO | ❌ NOT INTEGRATED |
| **RecommendationEngine** (recommendation.py) | ⚠️ PARTIAL (reads manual behaviors) | ⚠️ PARTIAL (reads manual journeys) | ⚠️ STATIC ONLY |
| **SMEOrchestrator** | ❌ NO | ❌ NO | ❌ NOT INTEGRATED |
| **BehaviorImpactAnalyzer** | ⚠️ PARTIAL (consumes from DB) | ⚠️ PARTIAL (consumes from DB) | ⚠️ STATIC ONLY |
| **JourneyImpactAnalyzer** | ⚠️ PARTIAL (consumes from DB) | ⚠️ PARTIAL (consumes from DB) | ⚠️ STATIC ONLY |

---

## Detailed Component Analysis

### 1. BehaviorDiscoveryEngine

**File**: `app/services/behavior_discovery_engine.py`

**Status**: 
- ✅ Fully implemented (329 lines)
- ✅ Pattern matching for behavior detection
- ✅ Evidence aggregation
- ✅ Journey mapping
- ✅ Risk level assignment
- ❌ NOT called anywhere in codebase
- ❌ NOT executed automatically
- ❌ Does NOT persist to DB (only returns candidates)

**Key Methods**:
- `discover_behaviors()` - Main discovery method
- `_scan_routes()`, `_scan_pages()`, `_scan_modules()`, `_scan_test_names()` - Evidence collection
- `_finalize_candidates()` - Confidence calculation

**Wiring Status**: DEAD CODE - Never invoked

---

### 2. BehaviorCatalogBuilder

**File**: `app/services/behavior_catalog_builder.py`

**Status**:
- ✅ Fully implemented (264 lines)
- ✅ Persists behaviors to DB (Behavior model)
- ✅ Persists journeys to DB (Journey model)
- ✅ Persists evidences to DB (BehaviorEvidence model)
- ✅ Idempotent (checks for existing records)
- ❌ NOT called anywhere in codebase
- ❌ NOT executed automatically

**Key Methods**:
- `build_catalog()` - Main catalog building method
- `_get_or_create_journey()` - Journey persistence
- `_get_or_create_behavior()` - Behavior persistence
- `_create_evidence()` - Evidence persistence
- `scan_repository_files()` - File scanning
- `build_from_repository_scan()` - End-to-end catalog build

**Wiring Status**: DEAD CODE - Never invoked

---

### 3. BehaviorDiscoveryRefreshPipeline

**File**: `app/services/behavior_discovery_refresh_pipeline.py`

**Status**:
- ✅ Fully implemented (330 lines)
- ✅ Orchestrates full discovery pipeline
- ✅ Multiple trigger types (REPOSITORY_SYNC, NEW_PR, MANUAL_REFRESH, etc.)
- ✅ Step-by-step pipeline with error handling
- ✅ Returns PipelineResult with statistics
- ❌ NOT called anywhere in codebase
- ❌ NOT executed automatically

**Key Methods**:
- `execute()` - Main pipeline execution
- `trigger_on_repository_sync()` - Repository sync trigger
- `trigger_on_new_pr()` - New PR trigger
- `trigger_manual_refresh()` - Manual refresh trigger

**Pipeline Steps**:
1. Refresh Semantic Index
2. Collect Evidence (Route, Test, Module, Documentation)
3. Aggregate Evidence
4. Calculate Confidence
5. Discover Relationships
6. Merge Behaviors
7. Update Catalog

**Wiring Status**: DEAD CODE - Never invoked

---

### 4. JourneyDiscoveryEngine

**File**: `app/services/journey_discovery_engine.py`

**Status**:
- ✅ Fully implemented (287 lines)
- ✅ Pattern-based journey inference
- ✅ Behavior-to-journey mapping
- ✅ Confidence calculation
- ✅ Risk level determination
- ❌ NOT called anywhere in codebase
- ❌ NOT executed automatically
- ❌ Does NOT persist to DB (only returns candidates)

**Key Methods**:
- `discover_journeys()` - Main discovery method
- `_group_behaviors_by_journey()` - Behavior grouping
- `_infer_journey_from_behavior()` - Journey inference
- `_create_journey_candidate()` - Candidate creation
- `get_discovery_stats()` - Statistics

**Wiring Status**: DEAD CODE - Never invoked

---

### 5. Repository Sync Flow

**File**: `app/services/github_app.py` - `execute_sync_job()`

**Status**:
- ✅ Repository sync implemented
- ✅ Architecture sync triggered after repository sync (line 1578-1590)
- ❌ Behavior discovery NOT triggered
- ❌ Journey discovery NOT triggered

**Current Flow**:
```
Repository Sync
→ Architecture Graph Build (sync_repository_architecture_task_wrapper)
→ [MISSING] Behavior Discovery
→ [MISSING] Journey Discovery
```

**Missing Integration**:
- No call to `BehaviorDiscoveryRefreshPipeline.trigger_on_repository_sync()`
- No call to `BehaviorCatalogBuilder.build_from_repository_scan()`
- No call to `JourneyDiscoveryEngine.discover_journeys()`

---

### 6. GitHub Sync Flow

**File**: `app/services/github_app.py` - `sync_repositories_task_wrapper()`

**Status**:
- ✅ GitHub sync implemented
- ✅ Architecture sync enqueued for all repositories (line 1584-1590)
- ❌ Behavior discovery NOT enqueued
- ❌ Journey discovery NOT enqueued

**Current Flow**:
```
GitHub Sync
→ Architecture Sync Task (sync_repository_architecture_task_wrapper)
→ [MISSING] Behavior Discovery Task
→ [MISSING] Journey Discovery Task
```

---

### 7. RecommendationInputBuilder

**File**: `app/services/recommendation_input_builder.py`

**Status**:
- ✅ Implemented (175 lines)
- ✅ Gathers changed files, test inventory, coverage, readiness, fragility
- ❌ Does NOT load behaviors
- ❌ Does NOT load journeys
- ❌ Does NOT load behavior evidences
- ❌ Does NOT load behavior scenarios

**Current Data Gathered**:
- Changed files
- Test inventory
- Coverage reports
- Test runs
- Repository readiness
- Fragility patterns

**Missing Data**:
- Behaviors
- Journeys
- Behavior evidences
- Behavior scenarios
- Journey-behavior mappings

---

### 8. RecommendationEngine

**File**: `app/services/recommendation.py`

**Status**:
- ✅ Loads behaviors from DB (line 953-956)
- ✅ Loads journeys from DB (line 947-950)
- ✅ Loads behavior evidences (line 962)
- ✅ Loads behavior scenarios (line 965)
- ✅ Loads journey-behavior mappings (line 959)
- ⚠️ BUT: These are MANUAL/STATIC behaviors, NOT auto-discovered
- ⚠️ BehaviorImpactAnalyzer uses these behaviors (line 980-991)
- ⚠️ JourneyImpactAnalyzer uses these journeys (line 994-999)

**Current Behavior Source**:
```python
behaviors = db.query(Behavior).filter(
    Behavior.repository_id == run_in.repository_id,
    Behavior.is_deleted == False,
).all()
```

**Problem**: This query returns ALL behaviors (manual + discovered), but since discovery never runs, only manual behaviors exist.

---

### 9. SMEOrchestrator

**File**: `app/services/sme_orchestrator.py`

**Status**:
- ✅ Orchestrates Product, QA Lead, Security, Architecture, Domain SME analyzers
- ❌ Does NOT use BehaviorDiscoveryEngine
- ❌ Does NOT use JourneyDiscoveryEngine
- ❌ Does NOT load behaviors from DB
- ❌ Does NOT load journeys from DB

**Current SMEs**:
- ProductSMEAnalyzer
- QALeadSMEAnalyzer
- SecuritySMEAnalyzer
- ArchitectureSMEAnalyzer
- DomainSMEAnalyzer

**Missing SME Integration**:
- Behavior SME (could use discovered behaviors)
- Journey SME (could use discovered journeys)

---

### 10. BehaviorImpactAnalyzer

**File**: `app/services/behavior_impact_analyzer.py`

**Status**:
- ✅ Implemented (405 lines)
- ✅ Consumes behaviors from DB (passed as parameter)
- ✅ Consumes journeys from DB (passed as parameter)
- ✅ Matches changed files to behaviors
- ✅ Calculates impact levels
- ⚠️ PARTIALLY WIRED: Called by recommendation.py (line 980)
- ⚠️ BUT: Only uses behaviors that exist in DB (manual only)

**Wiring Status**: PARTIALLY WIRED - Consumes behaviors, but behaviors are never auto-discovered

---

### 11. JourneyImpactAnalyzer

**File**: `app/services/pr_journey_impact_analyzer.py`

**Status**:
- ✅ Implemented (308 lines)
- ✅ Consumes behaviors from DB (passed as parameter)
- ✅ Consumes journeys from DB (passed as parameter)
- ✅ Maps files to behaviors
- ✅ Maps behaviors to journeys
- ✅ Calculates journey impact
- ⚠️ PARTIALLY WIRED: Called by recommendation.py (line 994)
- ⚠️ BUT: Only uses journeys that exist in DB (manual only)

**Wiring Status**: PARTIALLY WIRED - Consumes journeys, but journeys are never auto-discovered

---

## Answers to Audit Questions

### 1. When repository sync completes, are behaviors discovered automatically?

**Answer**: ❌ **NO**

**Evidence**:
- `github_app.py` line 1578-1590: Only architecture sync is triggered
- No call to `BehaviorDiscoveryRefreshPipeline.trigger_on_repository_sync()`
- No call to `BehaviorCatalogBuilder.build_from_repository_scan()`

---

### 2. When repository sync completes, are journeys discovered automatically?

**Answer**: ❌ **NO**

**Evidence**:
- `github_app.py` line 1578-1590: Only architecture sync is triggered
- No call to `JourneyDiscoveryEngine.discover_journeys()`
- No journey discovery task enqueued

---

### 3. Are discovered behaviors stored in DB?

**Answer**: ⚠️ **YES, BUT NEVER EXECUTED**

**Evidence**:
- `BehaviorCatalogBuilder._get_or_create_behavior()` (line 130-175) persists to DB
- `BehaviorCatalogBuilder._create_evidence()` (line 181-204) persists to DB
- `BehaviorCatalogBuilder._get_or_create_journey()` (line 96-124) persists to DB
- BUT: `BehaviorCatalogBuilder` is never called, so no behaviors are ever discovered/persisted

---

### 4. Are recommendations reading discovered behaviors or static/manual behaviors?

**Answer**: ⚠️ **STATIC/MANUAL BEHAVIORS ONLY**

**Evidence**:
- `recommendation.py` line 953-956: Queries ALL behaviors from DB
- Since discovery never runs, only manual behaviors exist
- No distinction between discovered vs manual behaviors in query

---

### 5. Are journeys affecting recommendations?

**Answer**: ⚠️ **YES, BUT ONLY MANUAL JOURNEYS**

**Evidence**:
- `recommendation.py` line 947-950: Queries ALL journeys from DB
- `recommendation.py` line 994-999: Passes journeys to JourneyImpactAnalyzer
- Since discovery never runs, only manual journeys exist
- Journey impact is calculated, but based on manual data only

---

## Missing Integration Points

### Critical Missing Wires

1. **Repository Sync → Behavior Discovery**
   - Location: `github_app.py` `execute_sync_job()` or `sync_repositories_task_wrapper()`
   - Missing: Call to `BehaviorDiscoveryRefreshPipeline.trigger_on_repository_sync()`

2. **Repository Sync → Journey Discovery**
   - Location: `github_app.py` `execute_sync_job()` or `sync_repositories_task_wrapper()`
   - Missing: Call to `JourneyDiscoveryEngine.discover_journeys()`

3. **RecommendationInputBuilder → Behavior Loading**
   - Location: `recommendation_input_builder.py` `build_snapshot()`
   - Missing: Load behaviors from DB
   - Missing: Load journeys from DB
   - Missing: Load behavior evidences
   - Missing: Load behavior scenarios

4. **SMEOrchestrator → Behavior/Journey Integration**
   - Location: `sme_orchestrator.py` `orchestrate()`
   - Missing: Use discovered behaviors in ProductSMEAnalyzer
   - Missing: Use discovered journeys in ProductSMEAnalyzer

### Secondary Missing Wires

5. **New PR Trigger → Behavior Discovery**
   - Location: PR sync flow
   - Missing: Call to `BehaviorDiscoveryRefreshPipeline.trigger_on_new_pr()`

6. **Manual Refresh API → Behavior Discovery**
   - Location: API endpoint (needs creation)
   - Missing: Call to `BehaviorDiscoveryRefreshPipeline.trigger_manual_refresh()`

---

## Exact Files to Modify

### Priority 1: Critical Wires (Must Modify)

1. **`app/services/github_app.py`**
   - Line ~1578-1590 (in `sync_repositories_task_wrapper`)
   - Add behavior discovery task enqueue
   - Add journey discovery task enqueue

2. **`app/services/recommendation_input_builder.py`**
   - Line ~128-138 (in `build_snapshot()`)
   - Add behavior loading
   - Add journey loading
   - Add behavior evidence loading
   - Add behavior scenario loading

3. **`app/services/sme_orchestrator.py`**
   - Line ~31-68 (in `orchestrate()`)
   - Add behavior discovery integration
   - Add journey discovery integration
   - Pass discovered behaviors/journeys to SME analyzers

### Priority 2: Secondary Wires (Should Modify)

4. **`app/services/recommendation.py`**
   - Line ~947-965 (behavior/journey loading)
   - Add distinction between discovered vs manual behaviors
   - Add confidence filtering for discovered behaviors

5. **`app/routers/behavior.py`** (or create new router)
   - Add manual refresh endpoint
   - Add behavior discovery status endpoint

6. **`app/services/behavior_discovery_refresh_pipeline.py`**
   - Line ~297-300 (in `_update_catalog()`)
   - Fix bug: `build_catalog()` called without repository parameter
   - Add journey discovery integration

---

## Deliverable 6B Completion Plan

### Phase 1: Wire Repository Sync (2-3 hours)

**Goal**: Enable automatic behavior/journey discovery on repository sync

**Steps**:
1. Modify `github_app.py` `sync_repositories_task_wrapper()`:
   - After architecture sync, enqueue behavior discovery task
   - After behavior discovery, enqueue journey discovery task
   - Add error handling and logging

2. Create background task wrappers:
   - `behavior_discovery_task_wrapper(repository_id_str, installation_id)`
   - `journey_discovery_task_wrapper(repository_id_str, installation_id)`

3. Test:
   - Trigger repository sync
   - Verify behaviors are discovered and persisted
   - Verify journeys are discovered and persisted

**Files Modified**:
- `app/services/github_app.py` (+30 lines)
- New: `app/services/github_app.py` task wrappers (+40 lines)

---

### Phase 2: Wire Recommendation Input (1-2 hours)

**Goal**: Load discovered behaviors/journeys in recommendation input snapshot

**Steps**:
1. Modify `recommendation_input_builder.py` `build_snapshot()`:
   - Add behavior loading from DB
   - Add journey loading from DB
   - Add behavior evidence loading
   - Add behavior scenario loading
   - Add journey-behavior mapping loading
   - Add to `content_state` for hash calculation

2. Update `RecommendationInputSnapshotResponse` schema:
   - Add behaviors field
   - Add journeys field
   - Add behavior_evidences field
   - Add behavior_scenarios field

3. Test:
   - Generate recommendation
   - Verify input snapshot includes behaviors/journeys
   - Verify hash changes with behavior data

**Files Modified**:
- `app/services/recommendation_input_builder.py` (+50 lines)
- `app/schemas/recommendation.py` (+20 lines)

---

### Phase 3: Wire SME Orchestrator (1-2 hours)

**Goal**: Use discovered behaviors/journeys in SME analysis

**Steps**:
1. Modify `sme_orchestrator.py` `orchestrate()`:
   - Add behavior discovery call
   - Add journey discovery call
   - Pass discovered behaviors to ProductSMEAnalyzer
   - Pass discovered journeys to ProductSMEAnalyzer
   - Add behavior/journey intelligence to snapshot

2. Modify `ProductSMEAnalyzer`:
   - Accept behaviors parameter
   - Accept journeys parameter
   - Use discovered behaviors for journey inference
   - Use discovered journeys for capability mapping

3. Test:
   - Generate recommendation with SME orchestration
   - Verify product impact uses discovered behaviors
   - Verify journey intelligence uses discovered journeys

**Files Modified**:
- `app/services/sme_orchestrator.py` (+30 lines)
- `app/services/product_sme_analyzer.py` (+40 lines)

---

### Phase 4: Add Confidence Filtering (1 hour)

**Goal**: Filter low-confidence discovered behaviors in recommendations

**Steps**:
1. Modify `recommendation.py` behavior loading:
   - Add confidence filter (HIGH/MODERATE only)
   - Add discovery_source filter (AUTO_DISCOVERED only)
   - Log behavior count by confidence

2. Modify `BehaviorImpactAnalyzer`:
   - Add confidence weighting
   - Low-confidence behaviors have reduced impact

3. Test:
   - Generate recommendation with mixed confidence behaviors
   - Verify low-confidence behaviors are filtered
   - Verify impact scores reflect confidence

**Files Modified**:
- `app/services/recommendation.py` (+10 lines)
- `app/services/behavior_impact_analyzer.py` (+15 lines)

---

### Phase 5: Add Manual Refresh API (1 hour)

**Goal**: Allow manual trigger of behavior/journey discovery

**Steps**:
1. Create new router or add to existing:
   - `POST /api/repositories/{repository_id}/behaviors/refresh`
   - `POST /api/repositories/{repository_id}/journeys/refresh`

2. Implement endpoints:
   - Call `BehaviorDiscoveryRefreshPipeline.trigger_manual_refresh()`
   - Call `JourneyDiscoveryEngine.discover_journeys()`
   - Return discovery statistics

3. Test:
   - Call manual refresh endpoint
   - Verify behaviors are refreshed
   - Verify journeys are refreshed

**Files Modified**:
- `app/routers/behavior.py` (+50 lines) or new router

---

### Phase 6: Verification & Testing (2-3 hours)

**Goal**: Verify end-to-end behavior discovery integration

**Steps**:
1. Create verification test:
   - Test repository sync triggers discovery
   - Test behaviors are persisted
   - Test journeys are persisted
   - Test recommendations use discovered behaviors
   - Test recommendations use discovered journeys

2. Manual testing:
   - Sync a real repository
   - Verify behavior discovery logs
   - Verify journey discovery logs
   - Generate recommendation
   - Verify behavior impact in recommendation
   - Verify journey impact in recommendation

3. Performance testing:
   - Measure discovery time for large repos
   - Measure recommendation time with behaviors
   - Optimize if needed

**Files Created**:
- `verify_behavior_discovery_integration.py` (+200 lines)

---

## Total Implementation Effort

**Estimated Time**: 8-12 hours  
**Files Modified**: 6-8 files  
**New Files**: 1-2 files  
**Lines Added**: ~200-300 lines

---

## Risk Assessment

### Low Risk
- Adding behavior discovery to repository sync (non-blocking)
- Loading behaviors in recommendation input (non-breaking)
- Adding manual refresh API (new feature)

### Medium Risk
- Modifying SME Orchestrator (affects SME analysis)
- Confidence filtering (may reduce behavior count)

### Mitigation
- Feature flag for behavior discovery (default: false)
- Gradual rollout per repository
- Monitoring of discovery statistics
- Fallback to manual behaviors if discovery fails

---

## Conclusion

**Current State**: Behavior and Journey discovery is **FULLY IMPLEMENTED** but **COMPLETELY ORPHANED**. No automatic discovery occurs.

**Root Cause**: Discovery services were built but never wired into the repository sync flow or recommendation generation.

**Solution**: Wire discovery services into repository sync, recommendation input, and SME orchestrator following the 6-phase plan above.

**Impact**: Once wired, recommendations will automatically use discovered behaviors and journeys, improving test selection accuracy and business intent coverage.

**Next Step**: Begin Phase 1 - Wire Repository Sync.
