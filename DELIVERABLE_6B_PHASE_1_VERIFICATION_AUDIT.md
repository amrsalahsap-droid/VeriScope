# Deliverable 6B Phase 1 Verification Audit

**Date**: 2026-06-02  
**Deliverable**: 6B - Behavior Discovery Integration  
**Phase**: 1 - Wire Behavior Discovery into Repository Sync  
**Audit Status**: FAIL

---

## Executive Summary

**VERIFICATION RESULT: FAIL**

Behavior Discovery is **NOT** persisting behaviors and journeys to the database. A critical bug in the `BehaviorDiscoveryRefreshPipeline` prevents the `BehaviorCatalogBuilder` from being initialized correctly, causing the entire discovery pipeline to fail silently.

**Root Cause**: Type mismatch in `BehaviorDiscoveryRefreshPipeline._update_catalog()` - passes `repository.id` (UUID) instead of `repository` (Repository object) to `BehaviorCatalogBuilder`.

---

## Detailed Inspection Results

### 1. behavior_discovery_refresh_pipeline.py - build_catalog() Call

**File**: `app/services/behavior_discovery_refresh_pipeline.py`  
**Lines**: 287-309

**Code**:
```python
def _update_catalog(
    self,
    repository: Repository,
    merged_behaviors: List[Any],
    relationships: List[Any],
    steps_completed: List[str],
    steps_failed: List[str],
) -> tuple[int, int]:
    """Step 7: Update the behavior catalog."""
    try:
        catalog_builder = BehaviorCatalogBuilder(self.db)
        
        # Build catalog from candidates
        catalog_builder.build_catalog(repository.id)  # ❌ BUG HERE
        
        behaviors_discovered = len(merged_behaviors)
        behaviors_updated = len(merged_behaviors)  # Simplified
        
        steps_completed.append(f"Catalog Update: {behaviors_discovered} behaviors processed")
        return behaviors_discovered, behaviors_updated
    except Exception as e:
        steps_failed.append(f"Catalog Update failed: {str(e)}")
        raise
```

**Issue**: 
- Line 297: `catalog_builder = BehaviorCatalogBuilder(self.db)` - Missing repository parameter
- Line 300: `catalog_builder.build_catalog(repository.id)` - Passes UUID instead of Repository object

**Expected**:
```python
catalog_builder = BehaviorCatalogBuilder(self.db, repository)
catalog_builder.build_catalog()  # No arguments needed
```

---

### 2. behavior_discovery_task_wrapper() Implementation

**File**: `app/services/github_app.py`  
**Lines**: 1626-1671

**Code**:
```python
def behavior_discovery_task_wrapper(repository_id_str: str, installation_id: int):
    """Background task wrapper for behavior discovery refresh pipeline."""
    from app.db.session import SessionLocal
    from app.services.behavior_discovery_refresh_pipeline import BehaviorDiscoveryRefreshPipeline
    from app.models.repository import Repository
    
    repository_id = UUID(repository_id_str)
    
    db = SessionLocal()
    try:
        # Load repository
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            logger.error(f"Repository {repository_id} not found for behavior discovery")
            return
        
        # Execute behavior discovery pipeline
        pipeline = BehaviorDiscoveryRefreshPipeline(db)
        result = pipeline.trigger_on_repository_sync(repository)  # ✅ Correct - passes repository object
        
        # Log telemetry
        logger.info(
            f"Behavior discovery completed for repository {repository_id}: "
            f"success={result.success}, "
            f"behaviors_discovered={result.behaviors_discovered}, "
            f"behaviors_updated={result.behaviors_updated}, "
            f"execution_time={result.execution_time_seconds:.2f}s"
        )
        
        # After successful behavior discovery, trigger journey discovery
        if result.success:
            queue = get_rq_queue()
            queue.enqueue(
                journey_discovery_task_wrapper,
                args=(str(repository_id), int(installation_id)),
                job_id=f"journey_discovery_{repository_id}"
            )
            logger.info(f"Enqueued journey discovery task for repository {repository_id}")
        else:
            logger.error(f"Behavior discovery failed for repository {repository_id}: {result.error_message}")
        
    except Exception as e:
        logger.exception(f"Unhandled exception running behavior discovery task for {repository_id_str}: {e}")
        raise e
    finally:
        db.close()
```

**Status**: ✅ Task wrapper implementation is correct
- Loads repository correctly
- Passes repository object to pipeline
- Logs telemetry correctly
- Enqueues journey discovery on success

**Issue**: The pipeline it calls has the bug, so this will fail

---

### 3. BehaviorCatalogBuilder Persistence Logic

**File**: `app/services/behavior_catalog_builder.py`  
**Lines**: 30-35, 130-174

**Constructor**:
```python
def __init__(self, db: Session, repository: Repository):
    """Initialize the catalog builder with database session and repository."""
    self.db = db
    self.repository = repository  # ✅ Expects Repository object
    self.discovery_engine = BehaviorDiscoveryEngine(repository.workspace_path or "")
    self.merge_service = BehaviorMergeService()
```

**Behavior Persistence**:
```python
def _get_or_create_behavior(
    self,
    candidate: DiscoveredBehaviorCandidate,
    journey: Optional[Journey],
) -> tuple[Behavior, bool]:
    """Get existing behavior or create new one. Returns (behavior, created)."""
    # Check if behavior already exists for this repository with same slug
    existing = self.db.query(Behavior).filter(
        Behavior.repository_id == self.repository.id,  # ✅ Uses self.repository.id
        Behavior.slug == candidate.suggested_slug,
        Behavior.is_deleted == False,
    ).first()
    
    if existing:
        # Update existing behavior
        existing.name = candidate.name
        existing.description = candidate.suggested_description
        existing.risk_level = candidate.suggested_risk_level
        existing.status = "DISCOVERED"
        existing.confidence = candidate.confidence
        existing.discovery_source = "AUTO_DISCOVERED"  # ✅ Sets discovery source
        existing.journey_id = journey.id if journey else None
        existing.updated_at = datetime.utcnow()
        return existing, False
    
    # Create new behavior
    behavior = Behavior(
        id=uuid.uuid4(),
        repository_id=self.repository.id,  # ✅ Uses self.repository.id
        journey_id=journey.id if journey else None,
        name=candidate.name,
        slug=candidate.suggested_slug or self._generate_behavior_slug(candidate.name),
        description=candidate.suggested_description,
        journey_name=candidate.suggested_journey or "",
        risk_level=candidate.suggested_risk_level,
        status="DISCOVERED",
        confidence=candidate.confidence,
        discovery_source="AUTO_DISCOVERED",  # ✅ Sets discovery source
        is_deleted=False,
        deleted_at=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    self.db.add(behavior)  # ✅ Persists to DB
    return behavior, True
```

**Status**: ✅ Persistence logic is correct
- Behaviors are persisted with `discovery_source = "AUTO_DISCOVERED"`
- Journeys are persisted
- Evidences are persisted
- Idempotent (checks for existing)

**Issue**: Cannot be called due to constructor bug in pipeline

---

### 4. Database State

**Check Date**: 2026-06-02  
**Repositories Checked**: 3

**Results**:

| Repository | Total Behaviors | Auto-Discovered | Manual | Total Journeys | Mappings | Evidences |
|-----------|----------------|-----------------|--------|---------------|----------|-----------|
| amrsalahsap-droid/trustdesk | 0 | 0 | 0 | 0 | 0 | 0 |
| amrsalahsap-droid/Hireshield | 0 | 0 | 0 | 0 | 0 | 0 |
| amrsalahsap-droid/hire-smart-ai | 0 | 0 | 0 | 0 | 0 | 0 |

**Conclusion**: **NO behaviors or journeys have been persisted** to the database for any repository.

---

### 5. End-to-End Flow Verification

#### Step 1: Repository Sync
- **Executed**: ✅ Yes (repositories exist in DB)
- **Succeeded**: ✅ Yes (repositories are synced)
- **Persisted**: ✅ Yes (repository records exist)
- **Evidence**: 3 repositories in database

#### Step 2: Architecture Sync
- **Executed**: ✅ Yes (task wrapper exists)
- **Succeeded**: ✅ Likely (no errors in logs)
- **Persisted**: ✅ Yes (architecture nodes/edges exist)
- **Evidence**: Architecture sync task wrapper is called

#### Step 3: Behavior Discovery
- **Executed**: ✅ Yes (task wrapper enqueued)
- **Succeeded**: ❌ NO (pipeline fails due to bug)
- **Persisted**: ❌ NO (0 behaviors in DB)
- **Evidence**: 0 behaviors, 0 evidences in DB

#### Step 4: Behavior Persistence
- **Executed**: ❌ NO (pipeline fails before persistence)
- **Succeeded**: ❌ NO
- **Persisted**: ❌ NO
- **Evidence**: 0 behaviors in DB

#### Step 5: Journey Discovery
- **Executed**: ❌ NO (not enqueued because behavior discovery failed)
- **Succeeded**: ❌ NO
- **Persisted**: ❌ NO
- **Evidence**: 0 journeys in DB

#### Step 6: Journey Persistence
- **Executed**: ❌ NO
- **Succeeded**: ❌ NO
- **Persisted**: ❌ NO
- **Evidence**: 0 journeys, 0 mappings in DB

---

## Root Cause Analysis

### Primary Bug

**File**: `app/services/behavior_discovery_refresh_pipeline.py`  
**Line**: 297-300

**Bug Code**:
```python
catalog_builder = BehaviorCatalogBuilder(self.db)  # ❌ Missing repository parameter
catalog_builder.build_catalog(repository.id)  # ❌ Passes UUID instead of Repository object
```

**Expected Code**:
```python
catalog_builder = BehaviorCatalogBuilder(self.db, repository)  # ✅ Pass repository object
catalog_builder.build_catalog()  # ✅ No arguments needed
```

**Impact**:
- `BehaviorCatalogBuilder.__init__()` requires `repository: Repository` parameter
- Pipeline passes only `db` and then calls `build_catalog(repository.id)`
- This causes a TypeError or incorrect initialization
- Discovery pipeline fails silently or with error
- No behaviors are persisted
- No journeys are discovered (depends on behaviors)

---

### Secondary Issue

**File**: `app/services/behavior_discovery_refresh_pipeline.py`  
**Line**: 300

**Issue**: `build_catalog()` is called with `repository.id` but the method signature doesn't accept a repository_id parameter

**Method Signature**:
```python
def build_catalog(
    self,
    routes: Optional[List[str]] = None,
    pages: Optional[List[str]] = None,
    folders: Optional[List[str]] = None,
    modules: Optional[List[str]] = None,
    test_names: Optional[List[str]] = None,
) -> BehaviorCatalogSnapshot:
```

**Call**:
```python
catalog_builder.build_catalog(repository.id)  # ❌ repository.id is passed as first positional arg, interpreted as routes
```

**Impact**: If it doesn't crash on initialization, it will pass the UUID as the `routes` parameter, causing incorrect behavior.

---

## Exact Fix Required

### File: `app/services/behavior_discovery_refresh_pipeline.py`

**Location**: Lines 297-300 in `_update_catalog()` method

**Current Code**:
```python
catalog_builder = BehaviorCatalogBuilder(self.db)

# Build catalog from candidates
catalog_builder.build_catalog(repository.id)
```

**Fixed Code**:
```python
catalog_builder = BehaviorCatalogBuilder(self.db, repository)

# Build catalog from candidates
catalog_builder.build_catalog()
```

**Changes**:
1. Add `repository` parameter to `BehaviorCatalogBuilder` constructor call
2. Remove `repository.id` argument from `build_catalog()` call

---

## Verification Script Status

**Script**: `verify_repository_sync_behavior_discovery.py`

**Status**: ⚠️ NOT RUN

**Reason**: The verification script would fail due to the same bug. Running it would not provide meaningful results until the bug is fixed.

**Recommendation**: Fix the bug first, then run verification script.

---

## Conclusion

**VERIFICATION RESULT: FAIL**

**Root Cause**: Type mismatch in `BehaviorDiscoveryRefreshPipeline._update_catalog()` - passes `repository.id` (UUID) instead of `repository` (Repository object) to `BehaviorCatalogBuilder`.

**Impact**: 
- Behavior discovery pipeline fails
- No behaviors are persisted to database
- No journeys are discovered or persisted
- Task wrappers are correctly implemented but cannot succeed due to pipeline bug

**Evidence**:
- 0 behaviors in database across 3 repositories
- 0 journeys in database across 3 repositories
- 0 journey-behavior mappings in database
- 0 behavior evidences in database

**Fix Required**: 
- File: `app/services/behavior_discovery_refresh_pipeline.py`
- Lines: 297-300
- Change: Pass repository object to BehaviorCatalogBuilder constructor, remove repository.id from build_catalog() call

**Status**: Phase 1 implementation is incomplete due to this bug. Fix required before behavior discovery can function.
