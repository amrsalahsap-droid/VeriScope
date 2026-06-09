"""
PatternMemoryV2 Upsert Service

Handles upsert operations for PatternMemoryV2 records.
"""

import logging
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.pattern_memory_v2 import (
    PatternMemoryV2,
    SIGNAL_TYPE_MANUAL_ADDITION,
    SIGNAL_TYPE_MANUAL_REMOVAL,
    SIGNAL_TYPE_ACCEPTED_SCENARIO,
    SIGNAL_TYPE_DISMISSED_SCENARIO,
    SIGNAL_TYPE_ESCAPED_DEFECT,
    SIGNAL_TYPE_ROLLBACK,
    SIGNAL_TYPE_EXECUTION_RESULT,
)

logger = logging.getLogger(__name__)


class PatternMemoryV2Upsert:
    """
    Service for upserting PatternMemoryV2 records.
    
    Handles creating or updating pattern memory records based on
    repository, pattern_key, and signal target identifiers.
    """

    def __init__(self, db: Session):
        self.db = db

    def upsert_signal(
        self,
        repository_id: str,
        workspace_id: Optional[str],
        pattern_key: str,
        signal_type: str,
        strength: float = 0.0,
        confidence: float = 0.0,
        behavior_id: Optional[str] = None,
        journey_id: Optional[str] = None,
        scenario_intent_key: Optional[str] = None,
        test_identifier: Optional[str] = None,
        increment_usage: bool = True,
        increment_success: bool = False,
        increment_failure: bool = False,
        increment_dismissed: bool = False,
        increment_defect: bool = False,
        increment_rollback: bool = False,
    ) -> Optional[PatternMemoryV2]:
        """
        Upsert a pattern memory signal.
        
        Args:
            repository_id: Repository ID
            workspace_id: Optional workspace ID
            pattern_key: Pattern key for lookup
            signal_type: Type of signal
            strength: Signal strength [0, 1]
            confidence: Signal confidence [0, 1]
            behavior_id: Optional behavior identifier
            journey_id: Optional journey identifier
            scenario_intent_key: Optional scenario intent key
            test_identifier: Optional test identifier
            increment_usage: Whether to increment usage_count
            increment_success: Whether to increment success_count
            increment_failure: Whether to increment failure_count
            increment_dismissed: Whether to increment dismissed_count
            increment_defect: Whether to increment defect_count
            increment_rollback: Whether to increment rollback_count
            
        Returns:
            PatternMemoryV2 record (created or updated), or None if failed
        """
        try:
            # Find existing record
            existing = self.db.query(PatternMemoryV2).filter(
                and_(
                    PatternMemoryV2.repository_id == repository_id,
                    PatternMemoryV2.pattern_key == pattern_key,
                    PatternMemoryV2.behavior_id == behavior_id,
                    PatternMemoryV2.journey_id == journey_id,
                    PatternMemoryV2.scenario_intent_key == scenario_intent_key,
                    PatternMemoryV2.test_identifier == test_identifier,
                )
            ).first()
            
            if existing:
                # Update existing record (append-only)
                if increment_usage:
                    existing.usage_count += 1
                if increment_success:
                    existing.success_count += 1
                if increment_failure:
                    existing.failure_count += 1
                if increment_dismissed:
                    existing.dismissed_count += 1
                if increment_defect:
                    existing.defect_count += 1
                if increment_rollback:
                    existing.rollback_count += 1
                
                # Update strength and confidence (bounded)
                existing.strength = max(0.0, min(1.0, strength))
                existing.confidence = max(0.0, min(1.0, confidence))
                existing.last_seen_at = datetime.utcnow()
                
                logger.debug(f"Updated PatternMemoryV2: {pattern_key} for signal {signal_type}")
            else:
                # Create new record
                pattern_memory = PatternMemoryV2(
                    workspace_id=workspace_id,
                    repository_id=repository_id,
                    pattern_key=pattern_key,
                    behavior_id=behavior_id,
                    journey_id=journey_id,
                    scenario_intent_key=scenario_intent_key,
                    test_identifier=test_identifier,
                    signal_type=signal_type,
                    strength=strength,
                    confidence=confidence,
                    usage_count=1 if increment_usage else 0,
                    success_count=1 if increment_success else 0,
                    failure_count=1 if increment_failure else 0,
                    dismissed_count=1 if increment_dismissed else 0,
                    defect_count=1 if increment_defect else 0,
                    rollback_count=1 if increment_rollback else 0,
                    last_seen_at=datetime.utcnow(),
                )
                self.db.add(pattern_memory)
                
                logger.debug(f"Created PatternMemoryV2: {pattern_key} for signal {signal_type}")
                existing = pattern_memory
            
            return existing
        except Exception as exc:
            # Log error without exposing SQL details
            logger.warning(
                f"PatternMemoryV2 upsert failed for pattern {pattern_key} signal {signal_type}: {str(exc)}"
            )
            return None

    def strengthen_signal(
        self,
        repository_id: str,
        workspace_id: Optional[str],
        pattern_key: str,
        signal_type: str,
        behavior_id: Optional[str] = None,
        journey_id: Optional[str] = None,
        scenario_intent_key: Optional[str] = None,
        test_identifier: Optional[str] = None,
        strength_increment: float = 0.1,
        confidence_increment: float = 0.05,
    ) -> Optional[PatternMemoryV2]:
        """
        Strengthen an existing signal by incrementing strength and confidence.
        
        Args:
            repository_id: Repository ID
            workspace_id: Optional workspace ID
            pattern_key: Pattern key for lookup
            signal_type: Type of signal
            behavior_id: Optional behavior identifier
            journey_id: Optional journey identifier
            scenario_intent_key: Optional scenario intent key
            test_identifier: Optional test identifier
            strength_increment: Amount to increment strength
            confidence_increment: Amount to increment confidence
            
        Returns:
            PatternMemoryV2 record (created or updated), or None if failed
        """
        try:
            existing = self.db.query(PatternMemoryV2).filter(
                and_(
                    PatternMemoryV2.repository_id == repository_id,
                    PatternMemoryV2.pattern_key == pattern_key,
                    PatternMemoryV2.behavior_id == behavior_id,
                    PatternMemoryV2.journey_id == journey_id,
                    PatternMemoryV2.scenario_intent_key == scenario_intent_key,
                    PatternMemoryV2.test_identifier == test_identifier,
                )
            ).first()
            
            if existing:
                # Strengthen existing
                existing.strength = min(1.0, existing.strength + strength_increment)
                existing.confidence = min(1.0, existing.confidence + confidence_increment)
                existing.usage_count += 1
                existing.last_seen_at = datetime.utcnow()
            else:
                # Create with initial strength
                pattern_memory = PatternMemoryV2(
                    workspace_id=workspace_id,
                    repository_id=repository_id,
                    pattern_key=pattern_key,
                    behavior_id=behavior_id,
                    journey_id=journey_id,
                    scenario_intent_key=scenario_intent_key,
                    test_identifier=test_identifier,
                    signal_type=signal_type,
                    strength=min(1.0, strength_increment),
                    confidence=min(1.0, confidence_increment),
                    usage_count=1,
                    success_count=0,
                    failure_count=0,
                    dismissed_count=0,
                    defect_count=0,
                    rollback_count=0,
                    last_seen_at=datetime.utcnow(),
                )
                self.db.add(pattern_memory)
                existing = pattern_memory
            
            return existing
        except Exception as exc:
            logger.warning(
                f"PatternMemoryV2 strengthen failed for pattern {pattern_key} signal {signal_type}: {str(exc)}"
            )
            return None

    def weaken_signal(
        self,
        repository_id: str,
        pattern_key: str,
        signal_type: str,
        behavior_id: Optional[str] = None,
        journey_id: Optional[str] = None,
        scenario_intent_key: Optional[str] = None,
        test_identifier: Optional[str] = None,
        strength_decrement: float = 0.2,
        confidence_decrement: float = 0.1,
    ) -> Optional[PatternMemoryV2]:
        """
        Weaken an existing signal by decrementing strength and confidence.
        
        Args:
            repository_id: Repository ID
            pattern_key: Pattern key for lookup
            signal_type: Type of signal
            behavior_id: Optional behavior identifier
            journey_id: Optional journey identifier
            scenario_intent_key: Optional scenario intent key
            test_identifier: Optional test identifier
            strength_decrement: Amount to decrement strength
            confidence_decrement: Amount to decrement confidence
            
        Returns:
            PatternMemoryV2 record if found, None otherwise
        """
        try:
            existing = self.db.query(PatternMemoryV2).filter(
                and_(
                    PatternMemoryV2.repository_id == repository_id,
                    PatternMemoryV2.pattern_key == pattern_key,
                    PatternMemoryV2.behavior_id == behavior_id,
                    PatternMemoryV2.journey_id == journey_id,
                    PatternMemoryV2.scenario_intent_key == scenario_intent_key,
                    PatternMemoryV2.test_identifier == test_identifier,
                )
            ).first()
            
            if existing:
                # Weaken existing (don't go below 0)
                existing.strength = max(0.0, existing.strength - strength_decrement)
                existing.confidence = max(0.0, existing.confidence - confidence_decrement)
                existing.dismissed_count += 1
                existing.last_seen_at = datetime.utcnow()
                return existing
            
            return None
        except Exception as exc:
            logger.warning(
                f"PatternMemoryV2 weaken failed for pattern {pattern_key} signal {signal_type}: {str(exc)}"
            )
            return None
