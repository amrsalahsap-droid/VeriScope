"""
FragilityDecayService Service

Applies time-based decay to fragility scores to avoid permanent punishment from old history.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent

logger = logging.getLogger(__name__)


class FragilityDecayService:
    """Applies time-based decay to fragility scores."""
    
    # Time windows for weight calculation
    FULL_WEIGHT_DAYS = 30
    MODERATE_WEIGHT_DAYS = 90
    REDUCED_WEIGHT_DAYS = 180
    STALE_THRESHOLD_DAYS = 180
    
    # Weight multipliers
    FULL_WEIGHT = 1.0
    MODERATE_WEIGHT = 0.6
    REDUCED_WEIGHT = 0.3
    STALE_WEIGHT = 0.1
    
    # Exception thresholds
    CRITICAL_ROLLBACK_RECENCY_DAYS = 90
    
    def __init__(self, db: Session):
        self.db = db
    
    def apply_decay_to_repository(
        self,
        repository_id: uuid.UUID,
    ) -> Dict[str, int]:
        """
        Apply decay to all active fragility memories in a repository.
        
        Args:
            repository_id: Repository to process
            
        Returns:
            Dict with decay results:
            - memories_processed: count of memories processed
            - memories_decayed: count of memories with score reduced
            - memories_marked_stale: count of memories marked STALE
            - memories_exempted: count of memories exempted from decay
        """
        logger.info(f"Applying decay to repository {repository_id}")
        
        results = {
            "memories_processed": 0,
            "memories_decayed": 0,
            "memories_marked_stale": 0,
            "memories_exempted": 0,
        }
        
        # Get all active memories
        active_memories = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id,
            FragilityMemoryV2.status == "ACTIVE",
        ).all()
        
        for memory in active_memories:
            results["memories_processed"] += 1
            
            # Check if memory should be exempted
            if self._should_exempt_from_decay(memory):
                results["memories_exempted"] += 1
                logger.debug(f"Memory {memory.id} exempted from decay (critical/rollback recurring)")
                continue
            
            # Calculate decay
            decay_result = self._calculate_decay_for_memory(memory)
            
            if decay_result["should_mark_stale"]:
                # Mark as STALE
                memory.status = "STALE"
                memory.last_seen_at = datetime.utcnow()
                results["memories_marked_stale"] += 1
                logger.info(f"Memory {memory.id} marked STALE (no evidence in {decay_result['days_since_last_seen']} days)")
            
            elif decay_result["decay_amount"] > 0:
                # Apply score decay
                memory.fragility_score = max(0.0, memory.fragility_score - decay_result["decay_amount"])
                memory.risk_level = self._determine_risk_level(memory.fragility_score)
                memory.last_seen_at = datetime.utcnow()
                results["memories_decayed"] += 1
                logger.debug(f"Memory {memory.id} decayed by {decay_result['decay_amount']} points")
        
        self.db.commit()
        
        logger.info(
            f"Decay complete: processed={results['memories_processed']}, "
            f"decayed={results['memories_decayed']}, "
            f"stale={results['memories_marked_stale']}, "
            f"exempted={results['memories_exempted']}"
        )
        
        return results
    
    def calculate_evidence_weight(
        self,
        evidence_occurred_at: datetime,
    ) -> float:
        """
        Calculate weight multiplier for evidence based on age.
        
        Args:
            evidence_occurred_at: When the evidence occurred
            
        Returns:
            Weight multiplier (0.0-1.0)
        """
        days_since = (datetime.utcnow() - evidence_occurred_at).days
        
        if days_since <= self.FULL_WEIGHT_DAYS:
            return self.FULL_WEIGHT
        elif days_since <= self.MODERATE_WEIGHT_DAYS:
            return self.MODERATE_WEIGHT
        elif days_since <= self.REDUCED_WEIGHT_DAYS:
            return self.REDUCED_WEIGHT
        else:
            return self.STALE_WEIGHT
    
    def _calculate_decay_for_memory(
        self,
        memory: FragilityMemoryV2,
    ) -> Dict:
        """
        Calculate decay for a single memory.
        
        Returns:
            Dict with:
            - days_since_last_seen: days since last evidence
            - decay_amount: points to subtract
            - should_mark_stale: whether to mark as STALE
        """
        days_since_last_seen = (datetime.utcnow() - memory.last_seen_at).days
        
        result = {
            "days_since_last_seen": days_since_last_seen,
            "decay_amount": 0.0,
            "should_mark_stale": False,
        }
        
        # Check if should mark as STALE
        if days_since_last_seen >= self.STALE_THRESHOLD_DAYS:
            result["should_mark_stale"] = True
            return result
        
        # Calculate decay amount based on time window
        if days_since_last_seen <= self.FULL_WEIGHT_DAYS:
            # No decay for recent evidence
            result["decay_amount"] = 0.0
        elif days_since_last_seen <= self.MODERATE_WEIGHT_DAYS:
            # Moderate decay: 40% reduction
            result["decay_amount"] = memory.fragility_score * 0.4
        elif days_since_last_seen <= self.REDUCED_WEIGHT_DAYS:
            # Reduced weight: 70% reduction
            result["decay_amount"] = memory.fragility_score * 0.7
        else:
            # Approaching stale: 90% reduction
            result["decay_amount"] = memory.fragility_score * 0.9
        
        return result
    
    def _should_exempt_from_decay(
        self,
        memory: FragilityMemoryV2,
    ) -> bool:
        """
        Check if memory should be exempted from decay.
        
        Exemption criteria:
        - Critical risk level with recent rollback/escaped defect evidence
        """
        if memory.risk_level != "CRITICAL":
            return False
        
        # Check for recent rollback or escaped defect evidence
        recent_evidence = self.db.query(FragilityEvidenceEvent).filter(
            FragilityEvidenceEvent.fragility_memory_id == memory.id,
            FragilityEvidenceEvent.occurred_at >= datetime.utcnow() - timedelta(days=self.CRITICAL_ROLLBACK_RECENCY_DAYS),
            FragilityEvidenceEvent.evidence_type.in_(["ROLLBACK", "ESCAPED_DEFECT"]),
        ).first()
        
        return recent_evidence is not None
    
    def _determine_risk_level(self, score: float) -> str:
        """Determine risk level from score."""
        if score >= 75.0:
            return "CRITICAL"
        elif score >= 50.0:
            return "HIGH"
        elif score >= 25.0:
            return "MEDIUM"
        else:
            return "LOW"
    
    def reactivate_stale_memory(
        self,
        memory_id: uuid.UUID,
    ) -> bool:
        """
        Reactivate a STALE memory if new evidence is added.
        
        Args:
            memory_id: Memory to reactivate
            
        Returns:
            True if reactivated, False otherwise
        """
        memory = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.id == memory_id
        ).first()
        
        if not memory:
            logger.warning(f"Memory {memory_id} not found")
            return False
        
        if memory.status != "STALE":
            logger.debug(f"Memory {memory_id} is not STALE")
            return False
        
        # Check for recent evidence
        recent_evidence = self.db.query(FragilityEvidenceEvent).filter(
            FragilityEvidenceEvent.fragility_memory_id == memory_id,
            FragilityEvidenceEvent.occurred_at >= datetime.utcnow() - timedelta(days=self.FULL_WEIGHT_DAYS),
        ).first()
        
        if recent_evidence:
            memory.status = "ACTIVE"
            memory.last_seen_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Memory {memory_id} reactivated with new evidence")
            return True
        
        return False
    
    def get_decay_summary(
        self,
        repository_id: uuid.UUID,
    ) -> Dict:
        """
        Get summary of decay state for a repository.
        
        Returns:
            Dict with decay statistics
        """
        all_memories = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.repository_id == repository_id
        ).all()
        
        summary = {
            "total_memories": len(all_memories),
            "active_memories": 0,
            "stale_memories": 0,
            "invalidated_memories": 0,
            "avg_score": 0.0,
            "avg_days_since_last_seen": 0.0,
        }
        
        if not all_memories:
            return summary
        
        total_score = 0.0
        total_days = 0
        
        for memory in all_memories:
            if memory.status == "ACTIVE":
                summary["active_memories"] += 1
            elif memory.status == "STALE":
                summary["stale_memories"] += 1
            elif memory.status == "INVALIDATED":
                summary["invalidated_memories"] += 1
            
            total_score += memory.fragility_score
            total_days += (datetime.utcnow() - memory.last_seen_at).days
        
        summary["avg_score"] = round(total_score / len(all_memories), 2)
        summary["avg_days_since_last_seen"] = round(total_days / len(all_memories), 2)
        
        return summary
