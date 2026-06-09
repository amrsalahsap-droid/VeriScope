# Architecture V2 Migration Plan

## Current State

### Legacy System (FileDependency)
- **Table**: `file_dependencies`
- **Engine**: `ArchitecturalImpactEngine`, `DependencyImpactEngine`
- **Used by**: 9 services in recommendation generation
- **Status**: Active and primary

### Architecture V2 (ArchitectureNode/ArchitectureEdge)
- **Tables**: `architecture_nodes`, `architecture_edges`
- **Services**: `ArchitectureGraphBuilder`, `RepositoryArchitectureIndexer`, `ArchitectureNodeService`, `ArchitectureEdgeService`, `ImportParser`, `PathAliasResolver`
- **Used by**: Only written during repository sync, never read
- **Status**: Implemented but NOT WIRED

## Migration Strategy

### Phase 1: Create Architecture V2 Impact Engine
Create `ArchitectureV2ImpactEngine` that provides the same interface as legacy engines but reads from ArchitectureNode/ArchitectureEdge.

### Phase 2: Feature Flag Integration
Add feature flag to toggle between legacy and V2 engines in recommendation generation.

### Phase 3: Wire into Recommendation Flow
- Update `recommendation_logic_v3.py` to use V2 engine when flag is enabled
- Update `BehaviorImpactAnalyzer` to enrich with architecture data
- Update `JourneyImpactAnalyzer` to enrich with architecture data
- Update `TestingScopeGenerator` to use architecture impact

### Phase 4: Response Payload Enhancement
Add `architecture_impact` section to recommendation response with:
- changed_nodes
- direct_impacts
- indirect_impacts
- impacted_layers
- impacted_behaviors
- impacted_journeys
- confidence

### Phase 5: Verification
Create integration tests proving:
- Signup file change impacts registration behavior/journey
- Billing tests NOT boosted when signup changes
- Architecture contribution explanations appear

## Services Using FileDependency (to be migrated)

1. `recommendation.py` - line 160
2. `project_context_index_extractor.py` - line 44
3. `fragility_memory_service.py` - line 65
4. `failure_neighborhood_correlation_engine.py` - line 147
5. `dependency_proximity_fragility_engine.py` - line 113
6. `dependency_impact_engine.py` - line 106
7. `dependency_extraction.py` - line 222
8. `dependency_expansion_resolver.py` - line 24
9. `architectural_impact_engine.py` - line 66

## Backward Compatibility

- Keep legacy engines intact
- Use feature flag: `USE_ARCHITECTURE_V2` (default: false)
- Fallback to legacy if V2 graph is empty or error occurs
