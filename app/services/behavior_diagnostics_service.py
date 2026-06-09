from typing import List, Dict, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.behavior import Behavior
from app.models.behavior_evidence import BehaviorEvidence
from app.models.repository_semantic_entry import RepositorySemanticEntry
from app.schemas.behavior_diagnostics import (
    BehaviorDiagnosticsSummary,
    BehaviorDiagnosticsDetail,
    BehaviorDiagnosticsResponse,
)


class BehaviorDiagnosticsService:
    """Service to generate behavior discovery diagnostics."""
    
    def __init__(self, db: Session):
        """Initialize the diagnostics service with database session."""
        self.db = db
    
    def get_diagnostics(self, repository_id: str) -> BehaviorDiagnosticsResponse:
        """Get complete diagnostics for a repository."""
        repository = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            raise ValueError(f"Repository {repository_id} not found")
        
        # Get summary
        summary = self._get_summary(repository_id)
        
        # Get behavior details
        behaviors = self._get_behavior_details(repository_id)
        
        return BehaviorDiagnosticsResponse(
            repository_id=str(repository_id),
            summary=summary,
            behaviors=behaviors,
        )
    
    def _get_summary(self, repository_id: str) -> BehaviorDiagnosticsSummary:
        """Generate summary diagnostics."""
        # Get all behaviors for repository
        behaviors = self.db.query(Behavior).filter(
            Behavior.repository_id == repository_id
        ).all()
        
        total = len(behaviors)
        high = sum(1 for b in behaviors if b.confidence == "HIGH")
        medium = sum(1 for b in behaviors if b.confidence == "MODERATE")
        low = sum(1 for b in behaviors if b.confidence == "LOW")
        
        # Get evidence sources
        evidence_sources = self._get_evidence_sources(repository_id)
        
        # Calculate discovery coverage
        coverage = self._calculate_coverage(repository_id)
        
        # Get last updated timestamp
        last_updated = self._get_last_updated(repository_id)
        
        return BehaviorDiagnosticsSummary(
            total_behaviors=total,
            high_confidence=high,
            medium_confidence=medium,
            low_confidence=low,
            evidence_sources=evidence_sources,
            discovery_coverage=coverage,
            last_updated=last_updated,
        )
    
    def _get_behavior_details(self, repository_id: str) -> List[BehaviorDiagnosticsDetail]:
        """Generate detailed diagnostics for each behavior."""
        behaviors = self.db.query(Behavior).filter(
            Behavior.repository_id == repository_id
        ).all()
        
        details = []
        for behavior in behaviors:
            # Get evidence count
            evidence_count = self.db.query(BehaviorEvidence).filter(
                BehaviorEvidence.behavior_id == behavior.id
            ).count()
            
            # Get discovery sources
            discovery_sources = self._get_behavior_sources(behavior.id)
            
            # Get confidence breakdown if available
            confidence_breakdown = self._get_confidence_breakdown(behavior)
            
            detail = BehaviorDiagnosticsDetail(
                behavior_id=str(behavior.id),
                behavior_name=behavior.name,
                confidence=behavior.confidence,
                evidence_count=evidence_count,
                discovery_sources=discovery_sources,
                confidence_breakdown=confidence_breakdown,
                journey=behavior.journey_name,
                risk_level=behavior.risk_level,
            )
            details.append(detail)
        
        return details
    
    def _get_evidence_sources(self, repository_id: str) -> Dict[str, int]:
        """Get count of evidences by source type."""
        evidences = self.db.query(BehaviorEvidence).join(Behavior).filter(
            Behavior.repository_id == repository_id
        ).all()
        
        sources = {}
        for evidence in evidences:
            source = evidence.evidence_type
            if source not in sources:
                sources[source] = 0
            sources[source] += 1
        
        return sources
    
    def _get_behavior_sources(self, behavior_id: str) -> List[str]:
        """Get unique source types for a behavior."""
        evidences = self.db.query(BehaviorEvidence).filter(
            BehaviorEvidence.behavior_id == behavior_id
        ).all()
        
        sources = list(set(e.evidence_type for e in evidences))
        return sorted(sources)
    
    def _calculate_coverage(self, repository_id: str) -> float:
        """Calculate discovery coverage percentage."""
        # Get total semantic entries for repository
        total_entries = self.db.query(RepositorySemanticEntry).filter(
            RepositorySemanticEntry.repository_id == repository_id
        ).count()
        
        if total_entries == 0:
            return 0.0
        
        # Get behaviors with evidence
        behaviors = self.db.query(Behavior).filter(
            Behavior.repository_id == repository_id
        ).all()
        
        behaviors_with_evidence = 0
        for behavior in behaviors:
            evidence_count = self.db.query(BehaviorEvidence).filter(
                BehaviorEvidence.behavior_id == behavior.id
            ).count()
            if evidence_count > 0:
                behaviors_with_evidence += 1
        
        # Coverage = behaviors with evidence / total entries * 100
        coverage = (behaviors_with_evidence / total_entries) * 100.0
        return round(coverage, 2)
    
    def _get_last_updated(self, repository_id: str) -> datetime:
        """Get last updated timestamp."""
        behavior = self.db.query(Behavior).filter(
            Behavior.repository_id == repository_id
        ).order_by(Behavior.updated_at.desc()).first()
        
        if behavior:
            return behavior.updated_at
        else:
            return datetime.utcnow()
    
    def _get_confidence_breakdown(self, behavior: Behavior) -> Optional[Dict[str, Any]]:
        """Get confidence breakdown for a behavior."""
        # This would integrate with BehaviorConfidenceEngine
        # For now, return a simple breakdown
        evidences = self.db.query(BehaviorEvidence).filter(
            BehaviorEvidence.behavior_id == behavior.id
        ).all()
        
        high_conf = sum(1 for e in evidences if e.confidence == "HIGH")
        medium_conf = sum(1 for e in evidences if e.confidence == "MODERATE")
        low_conf = sum(1 for e in evidences if e.confidence == "LOW")
        
        return {
            "evidence_count": len(evidences),
            "high_confidence_evidence": high_conf,
            "medium_confidence_evidence": medium_conf,
            "low_confidence_evidence": low_conf,
        }
