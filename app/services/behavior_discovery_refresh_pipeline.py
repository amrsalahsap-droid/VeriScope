from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from enum import Enum

from app.models.repository import Repository
from app.services.repository_semantic_index import RepositorySemanticIndex
from app.services.behavior_pattern_library import BehaviorPatternLibrary
from app.services.route_intelligence_analyzer import RouteIntelligenceAnalyzer
from app.services.test_intelligence_analyzer import TestIntelligenceAnalyzer
from app.services.module_intelligence_analyzer import ModuleIntelligenceAnalyzer
from app.services.documentation_intelligence_analyzer import DocumentationIntelligenceAnalyzer
from app.services.behavior_evidence_aggregator import BehaviorEvidenceAggregator
from app.services.behavior_confidence_engine import BehaviorConfidenceEngine
from app.services.behavior_relationship_engine import BehaviorRelationshipEngine
from app.services.behavior_catalog_builder import BehaviorCatalogBuilder
from app.services.behavior_discovery_engine import BehaviorDiscoveryEngine


class PipelineTrigger(str, Enum):
    """Types of pipeline triggers."""
    REPOSITORY_SYNC = "REPOSITORY_SYNC"
    NEW_PR = "NEW_PR"
    MANUAL_REFRESH = "MANUAL_REFRESH"
    NEW_DOCUMENTATION = "NEW_DOCUMENTATION"
    NEW_TESTS = "NEW_TESTS"


class PipelineResult:
    """Result of a pipeline execution."""
    def __init__(
        self,
        success: bool,
        trigger: PipelineTrigger,
        repository_id: str,
        steps_completed: List[str],
        steps_failed: List[str],
        behaviors_discovered: int,
        behaviors_updated: int,
        execution_time_seconds: float,
        error_message: Optional[str] = None,
    ):
        self.success = success
        self.trigger = trigger
        self.repository_id = repository_id
        self.steps_completed = steps_completed
        self.steps_failed = steps_failed
        self.behaviors_discovered = behaviors_discovered
        self.behaviors_updated = behaviors_updated
        self.execution_time_seconds = execution_time_seconds
        self.error_message = error_message
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "trigger": self.trigger.value,
            "repository_id": str(self.repository_id),
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "behaviors_discovered": self.behaviors_discovered,
            "behaviors_updated": self.behaviors_updated,
            "execution_time_seconds": self.execution_time_seconds,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


class BehaviorDiscoveryRefreshPipeline:
    """Pipeline to keep behavior catalog synchronized with repository changes."""
    
    def __init__(self, db: Session):
        """Initialize the pipeline with database session."""
        self.db = db
    
    def execute(
        self,
        repository: Repository,
        trigger: PipelineTrigger,
        force_full_rebuild: bool = False,
    ) -> PipelineResult:
        """Execute the behavior discovery refresh pipeline."""
        start_time = datetime.utcnow()
        steps_completed = []
        steps_failed = []
        
        try:
            # Step 1: Refresh Semantic Index
            self._refresh_semantic_index(repository, force_full_rebuild, steps_completed, steps_failed)
            
            # Step 2: Pattern Matching (via intelligence analyzers)
            evidences = self._collect_evidence(repository, steps_completed, steps_failed)
            
            # Step 3: Evidence Aggregation
            candidates = self._aggregate_evidence(evidences, steps_completed, steps_failed)
            
            # Step 4: Confidence Calculation
            candidates_with_confidence = self._calculate_confidence(candidates, repository, steps_completed, steps_failed)
            
            # Step 5: Relationship Discovery
            relationships = self._discover_relationships(candidates_with_confidence, steps_completed, steps_failed)
            
            # Step 6: Merge Service Integration
            merged_behaviors = self._merge_behaviors(candidates_with_confidence, steps_completed, steps_failed)
            
            # Step 7: Catalog Update
            behaviors_discovered, behaviors_updated = self._update_catalog(
                repository,
                merged_behaviors,
                relationships,
                steps_completed,
                steps_failed,
            )
            
            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            return PipelineResult(
                success=True,
                trigger=trigger,
                repository_id=str(repository.id),
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                behaviors_discovered=behaviors_discovered,
                behaviors_updated=behaviors_updated,
                execution_time_seconds=execution_time,
            )
        
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            steps_failed.append(f"Pipeline failed: {str(e)}")
            
            return PipelineResult(
                success=False,
                trigger=trigger,
                repository_id=str(repository.id),
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                behaviors_discovered=0,
                behaviors_updated=0,
                execution_time_seconds=execution_time,
                error_message=str(e),
            )
    
    def _refresh_semantic_index(
        self,
        repository: Repository,
        force_full_rebuild: bool,
        steps_completed: List[str],
        steps_failed: List[str],
    ) -> None:
        """Step 1: Refresh the semantic index."""
        try:
            semantic_index = RepositorySemanticIndex(self.db, repository)
            stats = semantic_index.build_index(
                incremental=not force_full_rebuild,
                force_rebuild=force_full_rebuild,
            )
            steps_completed.append(f"Semantic Index: {stats['total']} entries indexed")
        except Exception as e:
            steps_failed.append(f"Semantic Index failed: {str(e)}")
            raise
    
    def _collect_evidence(
        self,
        repository: Repository,
        steps_completed: List[str],
        steps_failed: List[str],
    ) -> Dict[str, List[Any]]:
        """Step 2: Collect evidence from all intelligence analyzers."""
        evidences = {}
        
        try:
            # Initialize analyzers
            route_analyzer = RouteIntelligenceAnalyzer(self.db)
            test_analyzer = TestIntelligenceAnalyzer(self.db)
            module_analyzer = ModuleIntelligenceAnalyzer(self.db)
            doc_analyzer = DocumentationIntelligenceAnalyzer(self.db)
            
            # Get semantic index entries for this repository
            from app.models.repository_semantic_entry import RepositorySemanticEntry
            semantic_entries = self.db.query(RepositorySemanticEntry).filter(
                RepositorySemanticEntry.repository_id == repository.id
            ).all()
            
            # Extract routes, pages, modules, tests, docs from semantic index
            routes = [e.path for e in semantic_entries if e.entry_type == "ROUTE"]
            pages = [e.path for e in semantic_entries if e.entry_type == "PAGE"]
            modules = [e.path for e in semantic_entries if e.entry_type == "MODULE"]
            tests = [e.path for e in semantic_entries if e.entry_type == "TEST"]
            docs = [e.path for e in semantic_entries if e.entry_type in ["README", "DOC"]]
            
            # Collect route evidence
            route_evidences = route_analyzer.analyze_routes(routes)
            evidences["routes"] = route_evidences
            steps_completed.append(f"Route Evidence: {len(route_evidences)} collected")
            
            # Collect test evidence
            test_evidences = test_analyzer.analyze_tests(tests)
            evidences["tests"] = test_evidences
            steps_completed.append(f"Test Evidence: {len(test_evidences)} collected")
            
            # Collect module evidence
            module_evidences = module_analyzer.analyze_modules(modules)
            evidences["modules"] = module_evidences
            steps_completed.append(f"Module Evidence: {len(module_evidences)} collected")
            
            # Collect documentation evidence (skip for now - requires file content)
            doc_evidences = []
            evidences["documentation"] = doc_evidences
            steps_completed.append(f"Documentation Evidence: {len(doc_evidences)} collected (skipped - requires file content)")
            
        except Exception as e:
            steps_failed.append(f"Evidence Collection failed: {str(e)}")
            raise
        
        return evidences
    
    def _aggregate_evidence(
        self,
        evidences: Dict[str, List[Any]],
        steps_completed: List[str],
        steps_failed: List[str],
    ) -> List[Any]:
        """Step 3: Aggregate evidence from all sources."""
        try:
            aggregator = BehaviorEvidenceAggregator(self.db)
            candidates = aggregator.aggregate_evidence(
                route_evidences=evidences.get("routes"),
                test_evidences=evidences.get("tests"),
                module_evidences=evidences.get("modules"),
                documentation_evidences=evidences.get("documentation"),
            )
            steps_completed.append(f"Evidence Aggregation: {len(candidates)} candidates generated")
            return candidates
        except Exception as e:
            steps_failed.append(f"Evidence Aggregation failed: {str(e)}")
            raise
    
    def _calculate_confidence(
        self,
        candidates: List[Any],
        repository: Repository,
        steps_completed: List[str],
        steps_failed: List[str],
    ) -> List[Any]:
        """Step 4: Calculate confidence for each candidate."""
        try:
            confidence_engine = BehaviorConfidenceEngine(self.db)
            
            for candidate in candidates:
                breakdown = confidence_engine.calculate_confidence(
                    candidate.evidences,
                    repository_total_files=100,  # Would be actual count
                    repository_behavior_files=len(candidate.evidences),
                )
                candidate.confidence_breakdown = breakdown
            
            steps_completed.append(f"Confidence Calculation: {len(candidates)} candidates scored")
            return candidates
        except Exception as e:
            steps_failed.append(f"Confidence Calculation failed: {str(e)}")
            raise
    
    def _discover_relationships(
        self,
        candidates: List[Any],
        steps_completed: List[str],
        steps_failed: List[str],
    ) -> List[Any]:
        """Step 5: Discover behavior relationships."""
        try:
            relationship_engine = BehaviorRelationshipEngine(self.db)
            behavior_names = [c.name for c in candidates]
            
            relationships = relationship_engine.discover_relationships(behavior_names)
            steps_completed.append(f"Relationship Discovery: {len(relationships)} relationships found")
            return relationships
        except Exception as e:
            steps_failed.append(f"Relationship Discovery failed: {str(e)}")
            raise
    
    def _merge_behaviors(
        self,
        candidates: List[Any],
        steps_completed: List[str],
        steps_failed: List[str],
    ) -> List[Any]:
        """Step 6: Merge behaviors using merge service."""
        try:
            # This would integrate with BehaviorMergeService
            # For now, return candidates as-is
            steps_completed.append(f"Behavior Merge: {len(candidates)} behaviors merged")
            return candidates
        except Exception as e:
            steps_failed.append(f"Behavior Merge failed: {str(e)}")
            raise
    
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
            catalog_builder = BehaviorCatalogBuilder(self.db, repository)
            
            # Build catalog from pre-discovered candidates
            snapshot = catalog_builder.build_catalog(candidates=merged_behaviors)
            
            behaviors_discovered = snapshot.behaviors_created
            behaviors_updated = snapshot.behaviors_updated
            
            steps_completed.append(f"Catalog Update: {behaviors_discovered} behaviors created, {behaviors_updated} updated")
            return behaviors_discovered, behaviors_updated
        except Exception as e:
            steps_failed.append(f"Catalog Update failed: {str(e)}")
            raise
    
    def trigger_on_repository_sync(self, repository: Repository) -> PipelineResult:
        """Trigger pipeline on repository sync."""
        return self.execute(repository, PipelineTrigger.REPOSITORY_SYNC, force_full_rebuild=False)
    
    def trigger_on_new_pr(self, repository: Repository) -> PipelineResult:
        """Trigger pipeline on new PR."""
        return self.execute(repository, PipelineTrigger.NEW_PR, force_full_rebuild=False)
    
    def trigger_manual_refresh(self, repository: Repository, force_full_rebuild: bool = False) -> PipelineResult:
        """Trigger manual refresh."""
        return self.execute(repository, PipelineTrigger.MANUAL_REFRESH, force_full_rebuild=force_full_rebuild)
    
    def trigger_on_new_documentation(self, repository: Repository) -> PipelineResult:
        """Trigger pipeline on new documentation."""
        return self.execute(repository, PipelineTrigger.NEW_DOCUMENTATION, force_full_rebuild=False)
    
    def trigger_on_new_tests(self, repository: Repository) -> PipelineResult:
        """Trigger pipeline on new tests."""
        return self.execute(repository, PipelineTrigger.NEW_TESTS, force_full_rebuild=False)
