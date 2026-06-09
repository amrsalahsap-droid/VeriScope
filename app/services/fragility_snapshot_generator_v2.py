"""
FragilitySnapshotGeneratorV2 Service

Produces stable fragility snapshots used during recommendations.
Uses FragilityMemoryV2 instead of legacy FragilityPattern.
"""

import uuid
import logging
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.fragility_pattern import FragilitySnapshot
from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent

logger = logging.getLogger(__name__)


class FragilitySnapshotGeneratorV2:
    """Generates stable fragility snapshots for recommendations."""
    
    GENERATION_VERSION = "v2.0.0"
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_snapshot(
        self,
        repository_id: uuid.UUID,
        recommendation_run_id: Optional[uuid.UUID] = None,
        generation_trigger: str = "RECOMMENDATION_RUN",
    ) -> FragilitySnapshot:
        """
        Generate a fragility snapshot for a repository.
        
        Args:
            repository_id: Repository to snapshot
            recommendation_run_id: Optional recommendation run to link
            generation_trigger: Trigger type (RECOMMENDATION_RUN, MANUAL_RECALCULATION, etc.)
            
        Returns:
            FragilitySnapshot record
        """
        logger.info(f"Generating fragility snapshot v2 for repository {repository_id}")
        
        # Validate repository
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise ValueError(f"Repository {repository_id} not found")
        
        # Get all fragility memories for repository
        all_memories = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id
        ).all()
        
        # Categorize memories
        categorized = self._categorize_memories(all_memories)
        
        # Calculate statistics
        total_memories = len(all_memories)
        active_memories = len([m for m in all_memories if m.status == "ACTIVE"])
        stale_memories = len([m for m in all_memories if m.status == "STALE"])
        critical_memories = len([m for m in all_memories if m.risk_level == "CRITICAL"])
        
        # Generate evidence summary
        evidence_summary = self._generate_evidence_summary(all_memories)
        
        # Build snapshot data for hash calculation
        snapshot_data = {
            "repository_id": str(repository_id),
            "generation_version": self.GENERATION_VERSION,
            "total_memories": total_memories,
            "active_memories": active_memories,
            "stale_memories": stale_memories,
            "critical_memories": critical_memories,
            "behavior_fragility": categorized["behavior_fragility"],
            "journey_fragility": categorized["journey_fragility"],
            "scenario_fragility": categorized["scenario_fragility"],
            "file_hotspots": categorized["file_hotspots"],
            "risky_combinations": categorized["risky_combinations"],
        }
        
        # Calculate stable hash
        snapshot_hash = self._calculate_stable_hash(snapshot_data)
        
        # Create snapshot record
        snapshot = FragilitySnapshot(
            repository_id=repository_id,
            recommendation_run_id=recommendation_run_id,
            snapshot_hash=snapshot_hash,
            generated_at=datetime.utcnow(),
            total_patterns=total_memories,  # Using legacy field name
            active_patterns=active_memories,
            stale_patterns=stale_memories,
            generation_version=self.GENERATION_VERSION,
            scoring_version="v2.0",
            evidence_window={"start": None, "end": None},
            generation_trigger=generation_trigger,
            snapshot_metadata={
                "v2": True,
                "total_memories": total_memories,
                "active_memories": active_memories,
                "stale_memories": stale_memories,
                "critical_memories": critical_memories,
                "behavior_fragility": categorized["behavior_fragility"],
                "journey_fragility": categorized["journey_fragility"],
                "scenario_fragility": categorized["scenario_fragility"],
                "file_hotspots": categorized["file_hotspots"],
                "risky_combinations": categorized["risky_combinations"],
                "evidence_summary": evidence_summary,
            },
            active_pattern_ids=[str(m.id) for m in all_memories if m.status == "ACTIVE"],
            pattern_hashes=[self._calculate_memory_hash(m) for m in all_memories],
        )
        
        self.db.add(snapshot)
        self.db.flush()
        
        logger.info(
            f"Snapshot generated: hash={snapshot_hash[:8]}, "
            f"total={total_memories}, active={active_memories}, "
            f"stale={stale_memories}, critical={critical_memories}"
        )
        
        return snapshot
    
    def _categorize_memories(
        self,
        memories: List[FragilityMemoryV2],
    ) -> Dict:
        """
        Categorize memories by type with deterministic ordering.
        
        Returns:
            Dict with categorized memory lists
        """
        categorized = {
            "behavior_fragility": [],
            "journey_fragility": [],
            "scenario_fragility": [],
            "file_hotspots": [],
            "risky_combinations": [],
        }
        
        for memory in memories:
            if memory.status != "ACTIVE":
                continue
            
            memory_data = {
                "id": str(memory.id),
                "memory_type": memory.memory_type,
                "subject_type": memory.subject_type,
                "subject_id": str(memory.subject_id) if memory.subject_id else None,
                "subject_name": memory.subject_name,
                "risk_level": memory.risk_level,
                "fragility_score": memory.fragility_score,
                "confidence": memory.confidence,
                "last_seen_at": memory.last_seen_at.isoformat() if memory.last_seen_at else None,
            }
            
            # Categorize by memory_type and subject_type
            if memory.subject_type == "BEHAVIOR" and memory.memory_type == "BEHAVIOR_FRAGILITY":
                categorized["behavior_fragility"].append(memory_data)
            elif memory.subject_type == "JOURNEY" and memory.memory_type == "JOURNEY_FRAGILITY":
                categorized["journey_fragility"].append(memory_data)
            elif memory.subject_type == "SCENARIO":
                categorized["scenario_fragility"].append(memory_data)
            elif memory.subject_type == "FILE" and memory.memory_type == "FILE_FAILURE_HOTSPOT":
                categorized["file_hotspots"].append(memory_data)
            elif memory.memory_type in ["RISKY_CHANGE_COMBINATION", "CO_FAILURE_PATTERN"]:
                categorized["risky_combinations"].append(memory_data)
        
        # Sort each category deterministically (by score descending, then by subject_name)
        for key in categorized:
            categorized[key].sort(
                key=lambda x: (-x["fragility_score"], x["subject_name"] or "")
            )
        
        return categorized
    
    def _calculate_stable_hash(self, snapshot_data: Dict) -> str:
        """
        Calculate a stable hash for the snapshot.
        
        Uses deterministic JSON serialization and SHA256.
        """
        # Convert to JSON with sorted keys
        json_str = json.dumps(snapshot_data, sort_keys=True)
        
        # Calculate SHA256 hash
        hash_obj = hashlib.sha256(json_str.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def _calculate_memory_hash(self, memory: FragilityMemoryV2) -> str:
        """
        Calculate a hash for a single memory record.
        """
        memory_data = {
            "memory_type": memory.memory_type,
            "subject_type": memory.subject_type,
            "subject_name": memory.subject_name,
            "fragility_score": memory.fragility_score,
            "risk_level": memory.risk_level,
            "confidence": memory.confidence,
            "status": memory.status,
        }
        json_str = json.dumps(memory_data, sort_keys=True)
        hash_obj = hashlib.sha256(json_str.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def _generate_evidence_summary(
        self,
        memories: List[FragilityMemoryV2],
    ) -> Dict:
        """
        Generate evidence summary for the snapshot.
        """
        summary = {
            "total_evidence_count": 0,
            "evidence_by_type": {},
            "most_recent_evidence": None,
        }
        
        for memory in memories:
            # Get evidence events for this memory
            evidence_events = self.db.query(FragilityEvidenceEvent).filter(
                FragilityEvidenceEvent.fragility_memory_id == memory.id
            ).all()
            
            summary["total_evidence_count"] += len(evidence_events)
            
            for event in evidence_events:
                evidence_type = event.evidence_type
                summary["evidence_by_type"][evidence_type] = summary["evidence_by_type"].get(evidence_type, 0) + 1
                
                # Track most recent evidence
                if summary["most_recent_evidence"] is None or event.occurred_at > summary["most_recent_evidence"]:
                    summary["most_recent_evidence"] = event.occurred_at.isoformat()
        
        return summary
    
    def get_snapshot_by_hash(
        self,
        repository_id: uuid.UUID,
        snapshot_hash: str,
    ) -> Optional[FragilitySnapshot]:
        """
        Retrieve a snapshot by its hash.
        
        Args:
            repository_id: Repository
            snapshot_hash: Snapshot hash
            
        Returns:
            FragilitySnapshot or None
        """
        return self.db.query(FragilitySnapshot).filter(
            FragilitySnapshot.repository_id == repository_id,
            FragilitySnapshot.snapshot_hash == snapshot_hash,
        ).first()
    
    def get_latest_snapshot(
        self,
        repository_id: uuid.UUID,
    ) -> Optional[FragilitySnapshot]:
        """
        Get the latest snapshot for a repository.
        
        Args:
            repository_id: Repository
            
        Returns:
            FragilitySnapshot or None
        """
        return self.db.query(FragilitySnapshot).filter(
            FragilitySnapshot.repository_id == repository_id
        ).order_by(FragilitySnapshot.generated_at.desc()).first()
