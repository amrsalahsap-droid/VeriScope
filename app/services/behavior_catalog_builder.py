from typing import List, Optional, Dict
from dataclasses import dataclass
from pathlib import Path
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.behavior_evidence import BehaviorEvidence
from app.models.journey import Journey
from app.models.repository import Repository
from app.services.behavior_discovery_engine import BehaviorDiscoveryEngine, DiscoveredBehaviorCandidate
from app.services.behavior_merge_service import BehaviorMergeService


@dataclass
class BehaviorCatalogSnapshot:
    """Snapshot of the behavior catalog after a build."""
    repository_id: str
    behaviors_created: int
    behaviors_updated: int
    journeys_created: int
    evidences_created: int
    scan_timestamp: datetime


class BehaviorCatalogBuilder:
    """Service to build behavior catalog from repository scan."""
    
    def __init__(self, db: Session, repository: Repository):
        """Initialize the catalog builder with database session and repository."""
        self.db = db
        self.repository = repository
        # Handle missing workspace_path attribute gracefully
        workspace_path = getattr(repository, 'workspace_path', None) or ""
        self.discovery_engine = BehaviorDiscoveryEngine(workspace_path)
        self.merge_service = BehaviorMergeService()
    
    def _convert_candidates(self, candidates: List[Any]) -> List[Any]:
        """Convert BehaviorCandidate from pipeline to DiscoveredBehaviorCandidate format."""
        from app.services.behavior_evidence_aggregator import BehaviorCandidate, UnifiedEvidence
        from app.services.behavior_discovery_engine import DiscoveredBehaviorCandidate, BehaviorEvidence
        
        converted = []
        for candidate in candidates:
            if isinstance(candidate, DiscoveredBehaviorCandidate):
                # Already in correct format
                converted.append(candidate)
            elif isinstance(candidate, BehaviorCandidate):
                # Convert from pipeline format
                # Convert UnifiedEvidence to BehaviorEvidence
                evidences = []
                for ue in candidate.evidences:
                    evidence = BehaviorEvidence(
                        evidence_type=ue.source_type,
                        source_path=ue.source_identifier,
                        source_name=ue.source_identifier,
                        excerpt=ue.excerpt,
                        confidence=ue.confidence,
                    )
                    evidences.append(evidence)
                
                discovered = DiscoveredBehaviorCandidate(
                    name=candidate.name,
                    confidence=candidate.confidence,
                    evidences=evidences,
                    suggested_journey=candidate.journey,
                    suggested_risk_level=candidate.risk_level,
                    suggested_description=candidate.description,
                )
                converted.append(discovered)
            else:
                # Unknown format, skip
                continue
        
        return converted
    
    def build_catalog(
        self,
        routes: Optional[List[str]] = None,
        pages: Optional[List[str]] = None,
        folders: Optional[List[str]] = None,
        modules: Optional[List[str]] = None,
        test_names: Optional[List[str]] = None,
        candidates: Optional[List[Any]] = None,
    ) -> BehaviorCatalogSnapshot:
        """Build behavior catalog from repository scan or pre-discovered candidates."""
        scan_timestamp = datetime.utcnow()
        
        # Step 1: Discover behavior candidates (if not provided)
        if candidates is not None:
            # Use pre-discovered candidates from pipeline
            # Convert BehaviorCandidate to DiscoveredBehaviorCandidate format
            merged_candidates = self._convert_candidates(candidates)
        else:
            # Discover from scratch
            candidates = self.discovery_engine.discover_behaviors(
                routes=routes,
                pages=pages,
                folders=folders,
                modules=modules,
                test_names=test_names,
            )
            # Step 2: Merge duplicate candidates
            merged_candidates = self.merge_service.merge_candidates(candidates)
        
        # Step 3: Process each merged candidate
        behaviors_created = 0
        behaviors_updated = 0
        journeys_created = 0
        evidences_created = 0
        
        for candidate in merged_candidates:
            # Step 4: Assign or create journey
            journey = self._get_or_create_journey(candidate.suggested_journey)
            if journey and journey.created_at == scan_timestamp:
                journeys_created += 1
            
            # Step 5: Create or update behavior
            behavior, created = self._get_or_create_behavior(candidate, journey)
            if created:
                behaviors_created += 1
            else:
                behaviors_updated += 1
            
            # Step 6: Create evidences
            for evidence in candidate.evidences:
                self._create_evidence(behavior, evidence)
                evidences_created += 1
        
        # Commit changes
        self.db.commit()
        
        return BehaviorCatalogSnapshot(
            repository_id=str(self.repository.id),
            behaviors_created=behaviors_created,
            behaviors_updated=behaviors_updated,
            journeys_created=journeys_created,
            evidences_created=evidences_created,
            scan_timestamp=scan_timestamp,
        )
    
    def _get_or_create_journey(self, journey_name: Optional[str]) -> Optional[Journey]:
        """Get existing journey or create new one."""
        if not journey_name:
            return None
        
        # Check if journey already exists for this repository
        existing = self.db.query(Journey).filter(
            Journey.repository_id == self.repository.id,
            Journey.name == journey_name,
        ).first()
        
        if existing:
            return existing
        
        # Create new journey
        slug = self._generate_journey_slug(journey_name)
        journey = Journey(
            id=uuid.uuid4(),
            repository_id=self.repository.id,
            name=journey_name,
            slug=slug,
            description=f"Journey: {journey_name}",
            risk_level="MEDIUM",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        self.db.add(journey)
        return journey
    
    def _generate_journey_slug(self, journey_name: str) -> str:
        """Generate a URL-friendly slug from journey name."""
        return journey_name.lower().replace(" ", "-").replace("_", "-")
    
    def _get_or_create_behavior(
        self,
        candidate: DiscoveredBehaviorCandidate,
        journey: Optional[Journey],
    ) -> tuple[Behavior, bool]:
        """Get existing behavior or create new one. Returns (behavior, created)."""
        # Determine the slug to use for lookup
        slug = candidate.suggested_slug or self._generate_behavior_slug(candidate.name)
        
        # Check if behavior already exists for this repository with same slug
        existing = self.db.query(Behavior).filter(
            Behavior.repository_id == self.repository.id,
            Behavior.slug == slug,
            Behavior.is_deleted == False,
        ).first()
        
        if existing:
            # Update existing behavior
            existing.name = candidate.name
            existing.description = candidate.suggested_description
            existing.risk_level = candidate.suggested_risk_level
            existing.status = "DISCOVERED"
            existing.confidence = candidate.confidence
            existing.discovery_source = "AUTO_DISCOVERED"
            existing.journey_id = journey.id if journey else None
            existing.updated_at = datetime.utcnow()
            return existing, False
        
        # Create new behavior
        behavior = Behavior(
            id=uuid.uuid4(),
            repository_id=self.repository.id,
            journey_id=journey.id if journey else None,
            name=candidate.name,
            slug=slug,
            description=candidate.suggested_description,
            journey_name=candidate.suggested_journey or "",
            risk_level=candidate.suggested_risk_level,
            status="DISCOVERED",
            confidence=candidate.confidence,
            discovery_source="AUTO_DISCOVERED",
            is_deleted=False,
            deleted_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        self.db.add(behavior)
        return behavior, True
    
    def _generate_behavior_slug(self, behavior_name: str) -> str:
        """Generate a URL-friendly slug from behavior name."""
        return behavior_name.lower().replace(" ", "-").replace("_", "-")
    
    def _create_evidence(self, behavior: Behavior, candidate_evidence) -> None:
        """Create evidence record for a behavior."""
        # Check if evidence already exists to maintain idempotency
        existing = self.db.query(BehaviorEvidence).filter(
            BehaviorEvidence.behavior_id == behavior.id,
            BehaviorEvidence.evidence_type == candidate_evidence.evidence_type,
            BehaviorEvidence.source_path == candidate_evidence.source_path,
        ).first()
        
        if existing:
            return  # Evidence already exists, skip
        
        evidence = BehaviorEvidence(
            id=uuid.uuid4(),
            behavior_id=behavior.id,
            evidence_type=candidate_evidence.evidence_type,
            source_path=candidate_evidence.source_path,
            source_name=candidate_evidence.source_name,
            excerpt=candidate_evidence.excerpt,
            confidence=candidate_evidence.confidence,
            created_at=datetime.utcnow(),
        )
        
        self.db.add(evidence)
    
    def scan_repository_files(self, repository_path: str) -> Dict[str, List[str]]:
        """Scan repository files for behavior-related artifacts."""
        repo_path = Path(repository_path)
        
        routes = []
        pages = []
        folders = []
        modules = []
        test_names = []
        
        # Scan for routes (API routes)
        for route_file in repo_path.rglob("*route*"):
            if route_file.is_file():
                routes.append(str(route_file.relative_to(repo_path)))
        
        # Scan for pages (page files)
        for page_file in repo_path.rglob("*page*"):
            if page_file.is_file():
                pages.append(str(page_file.relative_to(repo_path)))
        
        # Scan for folders with behavior-related names
        for folder in repo_path.rglob("*"):
            if folder.is_dir():
                folder_name = folder.name.lower()
                if any(keyword in folder_name for keyword in ["auth", "user", "billing", "checkout", "admin"]):
                    folders.append(str(folder.relative_to(repo_path)))
        
        # Scan for modules (Python files)
        for module_file in repo_path.rglob("*.py"):
            if module_file.is_file():
                modules.append(str(module_file.relative_to(repo_path)))
        
        # Scan for test files
        for test_file in repo_path.rglob("*test*.py"):
            if test_file.is_file():
                test_names.append(test_file.stem)
        
        return {
            "routes": routes,
            "pages": pages,
            "folders": folders,
            "modules": modules,
            "test_names": test_names,
        }
    
    def build_from_repository_scan(self, repository_path: str) -> BehaviorCatalogSnapshot:
        """Build behavior catalog by scanning repository files."""
        # Scan repository
        artifacts = self.scan_repository_files(repository_path)
        
        # Build catalog
        return self.build_catalog(
            routes=artifacts.get("routes"),
            pages=artifacts.get("pages"),
            folders=artifacts.get("folders"),
            modules=artifacts.get("modules"),
            test_names=artifacts.get("test_names"),
        )
