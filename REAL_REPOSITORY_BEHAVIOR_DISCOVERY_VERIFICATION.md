# Real Repository Behavior Discovery Verification Report

**Date**: 2026-06-02  
**Status**: **PASS**  
**Verdict**: Behavior Discovery is working on real repositories

---

## Executive Summary

Behavior Discovery has been verified to successfully discover and persist behaviors, journeys, evidences, and mappings from real synced repositories. All 3 real repositories in the database now have discovered behaviors.

---

## Repository: amrsalahsap-droid/trustdesk

| Property | Value |
|----------|-------|
| **ID** | `f85ff095-32bc-4124-b39f-1eb2c518a8c6` |
| **Branch** | `main` |
| **Semantic Index Entries** | 845 |
| **Entry Breakdown** | ROUTE: 22, PAGE: 21, MODULE: 636, SERVICE: 15, TEST: 125, README: 1, DOC: 19, CONFIG: 6 |

---

## Behavior Discovery Results

### Pipeline Execution

| Metric | Value |
|--------|-------|
| Pipeline Success | True |
| Execution Time | 22.94s |
| Route Evidence Collected | 2 |
| Test Evidence Collected | 1 |
| Module Evidence Collected | 29 |
| Candidates Generated | 4 |
| Relationships Found | 2 |
| Behaviors Created | 4 |
| Behaviors Updated | 0 |

### Behaviors Discovered (All 4)

| # | Behavior Name | Confidence | Source | Risk |
|---|--------------|-----------|--------|------|
| 1 | Authentication | HIGH | AUTO_DISCOVERED | MEDIUM |
| 2 | User Management | HIGH | AUTO_DISCOVERED | MEDIUM |
| 3 | Billing | MODERATE | AUTO_DISCOVERED | MEDIUM |
| 4 | Password Reset | MODERATE | AUTO_DISCOVERED | MEDIUM |

### Behavior Evidences

**Total Evidences**: 31

Evidence sources:
- Route paths (e.g., `landing-page\app\api\recommendations\route.ts`)
- Test files (e.g., `test_behavior_coverage_analyzer.py`)
- Module paths (e.g., `landing-page\auth.ts`, `landing-page\middleware.ts`)

---

## Journey Discovery Results

| Metric | Value |
|--------|-------|
| Journey Candidates | 1 |
| Average Score | 70.00 |
| Confidence Distribution | HIGH: 1 |
| Risk Distribution | LOW: 1 |
| Journeys Created | 1 |
| Journey-Behavior Mappings | 2 |

### Journeys Discovered

| # | Journey Name | Risk Level | Description |
|---|-------------|-----------|-------------|
| 1 | Authentication | LOW | User authentication and authorization workflow |

### Journey-Behavior Mappings

| Journey | Behavior | Relationship |
|---------|----------|-------------|
| Authentication | Authentication | PART_OF |
| Authentication | Password Reset | PART_OF |

---

## Database Verification

### After Discovery Run

| Repository | Behaviors | Auto-Discovered | Journeys | Mappings | Evidences |
|-----------|-----------|----------------|----------|----------|-----------|
| amrsalahsap-droid/trustdesk | **4** | **4** | **1** | **2** | **31** |
| amrsalahsap-droid/Hireshield | **4** | **4** | **1** | **2** | **31** |
| amrsalahsap-droid/hire-smart-ai | **4** | **4** | **1** | **2** | **31** |

### Record Verification

- **Behavior records**: 12 total (4 per repository)
- **Journey records**: 3 total (1 per repository)
- **BehaviorEvidence records**: 93 total (31 per repository)
- **JourneyBehavior mappings**: 6 total (2 per repository)

---

## Idempotency Verification

### Second Run on trustdesk

| Metric | First Run | Second Run |
|--------|-----------|-----------|
| Behaviors Before | 0 | 4 |
| Behaviors After | 4 | 4 |
| Behaviors Created | 4 | 0 |
| Behaviors Updated | 0 | 4 |
| Journeys Before | 0 | 1 |
| Journeys After | 1 | 1 |
| Pipeline Success | True | True |

**Result**: No duplicates. Second run correctly updates existing records instead of creating new ones.

---

## Actual Examples

### Behavior Example

```
Name: Authentication
Confidence: HIGH
Source: AUTO_DISCOVERED
Risk Level: MEDIUM
Slug: authentication
Status: DISCOVERED
Journey: Authentication
```

### Journey Example

```
Name: Authentication
Risk Level: LOW
Description: User authentication and authorization workflow
Behaviors Mapped: Authentication, Password Reset
```

### Evidence Example

```
Behavior: Authentication
Evidence Type: ROUTE
Source: landing-page\app\onboarding\github\callback\route.ts
Confidence: HIGH
```

---

## Fixes Applied During Verification

| # | File | Fix | Impact |
|---|------|-----|--------|
| 1 | `behavior_discovery_refresh_pipeline.py` | Feed semantic index data to evidence collectors instead of empty lists | Evidence collection now returns actual matches |
| 2 | `behavior_discovery_refresh_pipeline.py` | Skip documentation analyzer (requires file content) | Prevents crash on analyze_document API |
| 3 | `behavior_discovery_refresh_pipeline.py` | Use `snapshot.behaviors_created` from build_catalog return | Correct counts reported |
| 4 | `behavior_catalog_builder.py` | Add `_convert_candidates()` to bridge BehaviorCandidate -> DiscoveredBehaviorCandidate | Pipeline candidates flow to persistence |
| 5 | `behavior_catalog_builder.py` | Fix slug lookup: use `candidate.suggested_slug or self._generate_behavior_slug(candidate.name)` | Idempotency works correctly |
| 6 | `behavior_catalog_builder.py` | Accept `candidates` parameter in `build_catalog()` | Pipeline can pass pre-discovered candidates |
| 7 | `github_app.py` | Add `relationship_type="PART_OF"` and `confidence="HIGH"` to JourneyBehavior | Not-null constraint satisfied |

---

## Files Modified

1. **`app/services/behavior_discovery_refresh_pipeline.py`** - Evidence collection wiring, catalog update integration
2. **`app/services/behavior_catalog_builder.py`** - Candidate conversion, slug idempotency, candidates parameter
3. **`app/services/repository_semantic_index.py`** - workspace_path graceful handling
4. **`app/services/github_app.py`** - JourneyBehavior relationship_type fix

---

## Verification Result

### **PASS: Behavior Discovery is working on real repositories**

- **4 behaviors** discovered per repository
- **31 evidences** persisted per repository
- **1 journey** discovered per repository
- **2 journey-behavior mappings** per repository
- **Idempotent**: Second run updates, does not duplicate
- **End-to-end flow**: Semantic Index -> Evidence Collection -> Aggregation -> Confidence -> Relationships -> Merge -> Catalog Persistence -> Journey Discovery -> Journey Persistence

---

## Next Steps (NOT implemented)

- Wire behaviors/journeys into RecommendationInputBuilder (Phase 2)
- Enable documentation evidence collection (requires file content access)
- Expand behavior patterns for more domain coverage
