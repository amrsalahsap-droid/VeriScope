"""
FragilityDashboardService Service

Aggregates fragility data for repository-level dashboard.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.repository import Repository
from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent
from app.models.behavior import Behavior
from app.models.journey import Journey

logger = logging.getLogger(__name__)


class FragilityDashboardService:
    """Aggregates fragility data for dashboard display."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_dashboard_data(
        self,
        repository_id: uuid.UUID,
        status_filter: Optional[str] = None,  # ACTIVE, STALE, or None for all
        behavior_id: Optional[uuid.UUID] = None,
        journey_id: Optional[uuid.UUID] = None,
        timeframe_days: Optional[int] = None,
    ) -> Dict:
        """
        Get aggregated fragility data for dashboard.
        
        Args:
            repository_id: Repository to query
            status_filter: Filter by status (ACTIVE, STALE, or None)
            behavior_id: Filter by specific behavior
            journey_id: Filter by specific journey
            timeframe_days: Filter by timeframe (days since last_seen)
            
        Returns:
            Dict with dashboard data
        """
        # Base query for fragility memories
        query = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id
        )
        
        # Apply filters
        if status_filter:
            query = query.filter(FragilityMemoryV2.status == status_filter)
        
        if behavior_id:
            query = query.filter(
                or_(
                    FragilityMemoryV2.subject_id == behavior_id,
                    FragilityMemoryV2.subject_id == str(behavior_id)
                )
            )
        
        if journey_id:
            # Filter by journey via behavior
            behaviors_in_journey = self.db.query(Behavior.id).filter(
                Behavior.journey_id == journey_id
            ).all()
            behavior_ids = [b.id for b in behaviors_in_journey]
            if behavior_ids:
                query = query.filter(FragilityMemoryV2.subject_id.in_(behavior_ids))
        
        if timeframe_days:
            cutoff = datetime.utcnow() - timedelta(days=timeframe_days)
            query = query.filter(FragilityMemoryV2.last_seen_at >= cutoff)
        
        memories = query.all()
        
        # Aggregate by category
        result = {
            "summary": self._get_summary(memories),
            "top_fragile_behaviors": self._get_top_behaviors(memories),
            "top_fragile_journeys": self._get_top_journeys(memories),
            "repeated_failing_tests": self._get_repeated_failures(memories),
            "file_hotspots": self._get_file_hotspots(memories),
            "risky_combinations": self._get_risky_combinations(memories),
            "missing_coverage_patterns": self._get_missing_coverage(memories),
            "escaped_defect_patterns": self._get_escaped_defects(memories),
            "stale_patterns": self._get_stale_patterns(memories),
        }
        
        return result
    
    def _get_summary(self, memories: List[FragilityMemoryV2]) -> Dict:
        """Get summary statistics."""
        total = len(memories)
        active = len([m for m in memories if m.status == "ACTIVE"])
        stale = len([m for m in memories if m.status == "STALE"])
        critical = len([m for m in memories if m.risk_level == "CRITICAL"])
        high = len([m for m in memories if m.risk_level == "HIGH"])
        
        # Calculate average score
        avg_score = 0.0
        if memories:
            avg_score = sum(m.fragility_score for m in memories) / len(memories)
        
        return {
            "total_memories": total,
            "active_memories": active,
            "stale_memories": stale,
            "critical_count": critical,
            "high_count": high,
            "average_score": round(avg_score, 2),
        }
    
    def _get_top_behaviors(self, memories: List[FragilityMemoryV2]) -> List[Dict]:
        """Get top fragile behaviors."""
        behavior_memories = [m for m in memories if m.subject_type == "BEHAVIOR"]
        
        # Sort by score descending
        behavior_memories.sort(key=lambda m: m.fragility_score, reverse=True)
        
        # Get behavior names
        behavior_ids = [m.subject_id for m in behavior_memories if m.subject_id]
        behaviors = {}
        if behavior_ids:
            behavior_objs = self.db.query(Behavior).filter(Behavior.id.in_(behavior_ids)).all()
            behaviors = {str(b.id): b.name for b in behavior_objs}
        
        result = []
        for memory in behavior_memories[:10]:  # Top 10
            result.append({
                "id": str(memory.id),
                "subject_id": str(memory.subject_id) if memory.subject_id else None,
                "subject_name": behaviors.get(str(memory.subject_id)) or memory.subject_name,
                "memory_type": memory.memory_type,
                "risk_level": memory.risk_level,
                "fragility_score": memory.fragility_score,
                "confidence": memory.confidence,
                "status": memory.status,
                "last_seen_at": memory.last_seen_at.isoformat() if memory.last_seen_at else None,
                "evidence_count": self._count_evidence(memory.id),
            })
        
        return result
    
    def _get_top_journeys(self, memories: List[FragilityMemoryV2]) -> List[Dict]:
        """Get top fragile journeys."""
        journey_memories = [m for m in memories if m.subject_type == "JOURNEY"]
        
        # Sort by score descending
        journey_memories.sort(key=lambda m: m.fragility_score, reverse=True)
        
        # Get journey names
        journey_ids = [m.subject_id for m in journey_memories if m.subject_id]
        journeys = {}
        if journey_ids:
            journey_objs = self.db.query(Journey).filter(Journey.id.in_(journey_ids)).all()
            journeys = {str(j.id): j.name for j in journey_objs}
        
        result = []
        for memory in journey_memories[:10]:  # Top 10
            result.append({
                "id": str(memory.id),
                "subject_id": str(memory.subject_id) if memory.subject_id else None,
                "subject_name": journeys.get(str(memory.subject_id)) or memory.subject_name,
                "memory_type": memory.memory_type,
                "risk_level": memory.risk_level,
                "fragility_score": memory.fragility_score,
                "confidence": memory.confidence,
                "status": memory.status,
                "last_seen_at": memory.last_seen_at.isoformat() if memory.last_seen_at else None,
                "evidence_count": self._count_evidence(memory.id),
            })
        
        return result
    
    def _get_repeated_failures(self, memories: List[FragilityMemoryV2]) -> List[Dict]:
        """Get repeated failing tests."""
        test_memories = [m for m in memories if m.subject_type == "TEST" and m.memory_type == "REPEATED_TEST_FAILURE"]
        
        # Sort by score descending
        test_memories.sort(key=lambda m: m.fragility_score, reverse=True)
        
        result = []
        for memory in test_memories[:10]:  # Top 10
            result.append({
                "id": str(memory.id),
                "subject_name": memory.subject_name,
                "memory_type": memory.memory_type,
                "risk_level": memory.risk_level,
                "fragility_score": memory.fragility_score,
                "confidence": memory.confidence,
                "status": memory.status,
                "last_seen_at": memory.last_seen_at.isoformat() if memory.last_seen_at else None,
                "evidence_count": self._count_evidence(memory.id),
            })
        
        return result
    
    def _get_file_hotspots(self, memories: List[FragilityMemoryV2]) -> List[Dict]:
        """Get file hotspots."""
        file_memories = [m for m in memories if m.subject_type == "FILE" and m.memory_type == "FILE_FAILURE_HOTSPOT"]
        
        # Sort by score descending
        file_memories.sort(key=lambda m: m.fragility_score, reverse=True)
        
        result = []
        for memory in file_memories[:10]:  # Top 10
            result.append({
                "id": str(memory.id),
                "subject_name": memory.subject_name,
                "memory_type": memory.memory_type,
                "risk_level": memory.risk_level,
                "fragility_score": memory.fragility_score,
                "confidence": memory.confidence,
                "status": memory.status,
                "last_seen_at": memory.last_seen_at.isoformat() if memory.last_seen_at else None,
                "evidence_count": self._count_evidence(memory.id),
            })
        
        return result
    
    def _get_risky_combinations(self, memories: List[FragilityMemoryV2]) -> List[Dict]:
        """Get risky combinations."""
        combo_memories = [m for m in memories if m.memory_type in ["RISKY_CHANGE_COMBINATION", "CO_FAILURE_PATTERN"]]
        
        # Sort by score descending
        combo_memories.sort(key=lambda m: m.fragility_score, reverse=True)
        
        result = []
        for memory in combo_memories[:10]:  # Top 10
            result.append({
                "id": str(memory.id),
                "subject_name": memory.subject_name,
                "memory_type": memory.memory_type,
                "risk_level": memory.risk_level,
                "fragility_score": memory.fragility_score,
                "confidence": memory.confidence,
                "status": memory.status,
                "last_seen_at": memory.last_seen_at.isoformat() if memory.last_seen_at else None,
                "evidence_count": self._count_evidence(memory.id),
            })
        
        return result
    
    def _get_missing_coverage(self, memories: List[FragilityMemoryV2]) -> List[Dict]:
        """Get missing coverage patterns."""
        coverage_memories = [m for m in memories if m.memory_type == "MISSING_COVERAGE_PATTERN"]
        
        # Sort by score descending
        coverage_memories.sort(key=lambda m: m.fragility_score, reverse=True)
        
        result = []
        for memory in coverage_memories[:10]:  # Top 10
            result.append({
                "id": str(memory.id),
                "subject_name": memory.subject_name,
                "memory_type": memory.memory_type,
                "risk_level": memory.risk_level,
                "fragility_score": memory.fragility_score,
                "confidence": memory.confidence,
                "status": memory.status,
                "last_seen_at": memory.last_seen_at.isoformat() if memory.last_seen_at else None,
                "evidence_count": self._count_evidence(memory.id),
            })
        
        return result
    
    def _get_escaped_defects(self, memories: List[FragilityMemoryV2]) -> List[Dict]:
        """Get escaped defect patterns."""
        defect_memories = [m for m in memories if m.memory_type == "ESCAPED_DEFECT_PATTERN"]
        
        # Sort by score descending
        defect_memories.sort(key=lambda m: m.fragility_score, reverse=True)
        
        result = []
        for memory in defect_memories[:10]:  # Top 10
            result.append({
                "id": str(memory.id),
                "subject_name": memory.subject_name,
                "memory_type": memory.memory_type,
                "risk_level": memory.risk_level,
                "fragility_score": memory.fragility_score,
                "confidence": memory.confidence,
                "status": memory.status,
                "last_seen_at": memory.last_seen_at.isoformat() if memory.last_seen_at else None,
                "evidence_count": self._count_evidence(memory.id),
            })
        
        return result
    
    def _get_stale_patterns(self, memories: List[FragilityMemoryV2]) -> List[Dict]:
        """Get stale patterns."""
        stale_memories = [m for m in memories if m.status == "STALE"]
        
        # Sort by last_seen_at descending (most recent stale first)
        stale_memories.sort(key=lambda m: m.last_seen_at or datetime.min, reverse=True)
        
        result = []
        for memory in stale_memories[:10]:  # Top 10
            result.append({
                "id": str(memory.id),
                "subject_name": memory.subject_name,
                "subject_type": memory.subject_type,
                "memory_type": memory.memory_type,
                "risk_level": memory.risk_level,
                "fragility_score": memory.fragility_score,
                "confidence": memory.confidence,
                "status": memory.status,
                "last_seen_at": memory.last_seen_at.isoformat() if memory.last_seen_at else None,
                "evidence_count": self._count_evidence(memory.id),
            })
        
        return result
    
    def _count_evidence(self, memory_id: uuid.UUID) -> int:
        """Count evidence events for a memory."""
        return self.db.query(FragilityEvidenceEvent).filter(
            FragilityEvidenceEvent.fragility_memory_id == memory_id
        ).count()
