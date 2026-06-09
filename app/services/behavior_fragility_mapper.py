"""
BehaviorFragilityMapper Service

Maps file/test/incident fragility to Behavior Catalog and Journey Catalog.
Creates BehaviorFragilitySignal outputs.
"""

import uuid
import logging
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.behavior_scenario import BehaviorScenario
from app.models.behavior_evidence import BehaviorEvidence
from app.models.behavior_impact import BehaviorImpactItem
from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent
from app.schemas.behavior_fragility_signal import BehaviorFragilitySignal

logger = logging.getLogger(__name__)


class BehaviorFragilityMapper:
    """Maps fragility to behavior/journey level."""
    
    # Confidence levels for different mapping types
    DIRECT_BEHAVIOR_CONFIDENCE = 1.0
    FILE_TO_BEHAVIOR_CONFIDENCE = 0.8
    TEST_TO_SCENARIO_CONFIDENCE = 0.6
    JOURNEY_CONFIDENCE = 0.4
    
    def __init__(self, db: Session):
        self.db = db
    
    def map_fragility_to_behaviors(
        self,
        repository_id: uuid.UUID,
        fragility_memory_id: uuid.UUID,
    ) -> List[BehaviorFragilitySignal]:
        """
        Map fragility memory to behavior/journey signals.
        
        Args:
            repository_id: Repository to map
            fragility_memory_id: FragilityMemory to map
            
        Returns:
            List of BehaviorFragilitySignal objects
        """
        logger.info(f"Mapping fragility {fragility_memory_id} to behaviors for repository {repository_id}")
        
        # Get fragility memory
        memory = self.db.query(FragilityMemoryV2).filter(
            FragilityMemoryV2.id == fragility_memory_id
        ).first()
        
        if not memory:
            logger.warning(f"FragilityMemory {fragility_memory_id} not found")
            return []
        
        # Get evidence events for this memory
        evidence_events = self.db.query(FragilityEvidenceEvent).filter(
            FragilityEvidenceEvent.fragility_memory_id == fragility_memory_id
        ).all()
        
        signals = []
        
        # Map based on memory type and subject type
        if memory.subject_type == "BEHAVIOR":
            # Direct behavior mapping
            signal = self._map_direct_behavior(memory, evidence_events)
            if signal:
                signals.append(signal)
        
        elif memory.subject_type == "JOURNEY":
            # Direct journey mapping
            signal = self._map_direct_journey(memory, evidence_events)
            if signal:
                signals.append(signal)
        
        elif memory.subject_type == "TEST":
            # Test → behavior scenario mapping
            signals.extend(self._map_test_to_behavior(memory, evidence_events))
        
        elif memory.subject_type == "FILE":
            # File → behavior impact mapping
            signals.extend(self._map_file_to_behavior(memory, evidence_events))
        
        elif memory.subject_type == "SCENARIO":
            # Scenario → behavior mapping
            signals.extend(self._map_scenario_to_behavior(memory, evidence_events))
        
        elif memory.subject_type == "PR_PATTERN":
            # PR pattern → behavior/journey via changed files
            signals.extend(self._map_pr_pattern_to_behavior(memory, evidence_events))
        
        logger.info(f"Generated {len(signals)} behavior fragility signals")
        return signals
    
    def _map_direct_behavior(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
    ) -> Optional[BehaviorFragilitySignal]:
        """
        Map direct behavior fragility (strongest mapping).
        """
        if not memory.subject_id:
            return None
        
        behavior = self.db.query(Behavior).filter(Behavior.id == memory.subject_id).first()
        if not behavior:
            return None
        
        # Get journey
        journey_id = behavior.journey_id
        
        return BehaviorFragilitySignal(
            behavior_id=behavior.id,
            journey_id=journey_id,
            scenario_id=None,
            signal_type=memory.memory_type,
            score=memory.fragility_score,
            confidence=memory.confidence * self.DIRECT_BEHAVIOR_CONFIDENCE,
            evidence_event_ids=[e.id for e in evidence_events],
            reason=f"Direct behavior fragility: {memory.subject_name} has {memory.memory_type} pattern",
        )
    
    def _map_direct_journey(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
    ) -> Optional[BehaviorFragilitySignal]:
        """
        Map direct journey fragility.
        """
        if not memory.subject_id:
            return None
        
        journey = self.db.query(Journey).filter(Journey.id == memory.subject_id).first()
        if not journey:
            return None
        
        # Get behaviors in this journey
        behaviors = self.db.query(Behavior).filter(
            Behavior.journey_id == journey.id,
            Behavior.is_deleted == False
        ).all()
        
        if not behaviors:
            return None
        
        # Create signal for each behavior in the journey
        signals = []
        for behavior in behaviors:
            signal = BehaviorFragilitySignal(
                behavior_id=behavior.id,
                journey_id=journey.id,
                scenario_id=None,
                signal_type=memory.memory_type,
                score=memory.fragility_score,
                confidence=memory.confidence * self.JOURNEY_CONFIDENCE,
                evidence_event_ids=[e.id for e in evidence_events],
                reason=f"Journey fragility: {memory.subject_name} has {memory.memory_type} pattern affecting behavior {behavior.name}",
            )
            signals.append(signal)
        
        return signals[0] if signals else None  # Return first signal for simplicity
    
    def _map_test_to_behavior(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
    ) -> List[BehaviorFragilitySignal]:
        """
        Map test fragility to behavior via BehaviorScenario.
        """
        test_name = memory.subject_name
        
        # Find behavior scenarios matching this test
        behavior_scenarios = self.db.query(BehaviorScenario).filter(
            BehaviorScenario.test_identifier == test_name
        ).all()
        
        if not behavior_scenarios:
            return []
        
        signals = []
        for bs in behavior_scenarios:
            behavior = self.db.query(Behavior).filter(Behavior.id == bs.behavior_id).first()
            if not behavior:
                continue
            
            journey_id = behavior.journey_id
            
            signal = BehaviorFragilitySignal(
                behavior_id=behavior.id,
                journey_id=journey_id,
                scenario_id=bs.id,
                signal_type=memory.memory_type,
                score=memory.fragility_score,
                confidence=memory.confidence * self.TEST_TO_SCENARIO_CONFIDENCE,
                evidence_event_ids=[e.id for e in evidence_events],
                reason=f"Test {test_name} linked to behavior {behavior.name} has {memory.memory_type} pattern",
            )
            signals.append(signal)
        
        return signals
    
    def _map_file_to_behavior(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
    ) -> List[BehaviorFragilitySignal]:
        """
        Map file fragility to behavior via BehaviorImpact.
        """
        file_path = memory.subject_name
        
        # Find behavior impact items matching this file
        behavior_impact_items = self.db.query(BehaviorImpactItem).filter(
            BehaviorImpactItem.repository_id == memory.repository_id,
            BehaviorImpactItem.impacted_files.contains([file_path])
        ).all()
        
        if not behavior_impact_items:
            return []
        
        signals = []
        for item in behavior_impact_items:
            behavior = self.db.query(Behavior).filter(Behavior.id == item.behavior_id).first()
            if not behavior:
                continue
            
            journey_id = item.journey_id or behavior.journey_id
            
            signal = BehaviorFragilitySignal(
                behavior_id=behavior.id,
                journey_id=journey_id,
                scenario_id=None,
                signal_type=memory.memory_type,
                score=memory.fragility_score,
                confidence=memory.confidence * self.FILE_TO_BEHAVIOR_CONFIDENCE,
                evidence_event_ids=[e.id for e in evidence_events],
                reason=f"File {file_path} impacts behavior {behavior.name} and has {memory.memory_type} pattern",
            )
            signals.append(signal)
        
        return signals
    
    def _map_scenario_to_behavior(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
    ) -> List[BehaviorFragilitySignal]:
        """
        Map scenario fragility to behavior via BehaviorScenario.
        """
        scenario_key = memory.subject_name
        
        # Find behavior scenarios matching this scenario key
        behavior_scenarios = self.db.query(BehaviorScenario).filter(
            BehaviorScenario.scenario_key == scenario_key
        ).all()
        
        if not behavior_scenarios:
            return []
        
        signals = []
        for bs in behavior_scenarios:
            behavior = self.db.query(Behavior).filter(Behavior.id == bs.behavior_id).first()
            if not behavior:
                continue
            
            journey_id = behavior.journey_id
            
            signal = BehaviorFragilitySignal(
                behavior_id=behavior.id,
                journey_id=journey_id,
                scenario_id=bs.id,
                signal_type=memory.memory_type,
                score=memory.fragility_score,
                confidence=memory.confidence * self.TEST_TO_SCENARIO_CONFIDENCE,
                evidence_event_ids=[e.id for e in evidence_events],
                reason=f"Scenario {scenario_key} linked to behavior {behavior.name} has {memory.memory_type} pattern",
            )
            signals.append(signal)
        
        return signals
    
    def _map_pr_pattern_to_behavior(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
    ) -> List[BehaviorFragilitySignal]:
        """
        Map PR pattern fragility to behavior via changed files.
        """
        # Get changed files from evidence events
        changed_files = set()
        for event in evidence_events:
            if event.changed_files:
                changed_files.update(event.changed_files)
        
        if not changed_files:
            return []
        
        signals = []
        
        # Map each changed file to behavior via BehaviorImpact
        for file_path in changed_files:
            behavior_impact_items = self.db.query(BehaviorImpactItem).filter(
                BehaviorImpactItem.repository_id == memory.repository_id,
                BehaviorImpactItem.impacted_files.contains([file_path])
            ).all()
            
            for item in behavior_impact_items:
                behavior = self.db.query(Behavior).filter(Behavior.id == item.behavior_id).first()
                if not behavior:
                    continue
                
                journey_id = item.journey_id or behavior.journey_id
                
                signal = BehaviorFragilitySignal(
                    behavior_id=behavior.id,
                    journey_id=journey_id,
                    scenario_id=None,
                    signal_type=memory.memory_type,
                    score=memory.fragility_score,
                    confidence=memory.confidence * self.FILE_TO_BEHAVIOR_CONFIDENCE,
                    evidence_event_ids=[e.id for e in evidence_events],
                    reason=f"PR pattern with changed file {file_path} impacts behavior {behavior.name} and has {memory.memory_type} pattern",
                )
                signals.append(signal)
        
        return signals
    
    def aggregate_behavior_signals(
        self,
        signals: List[BehaviorFragilitySignal],
    ) -> Dict[uuid.UUID, BehaviorFragilitySignal]:
        """
        Aggregate multiple signals for the same behavior.
        
        Args:
            signals: List of BehaviorFragilitySignal objects
            
        Returns:
            Dict mapping behavior_id to aggregated signal
        """
        aggregated = {}
        
        for signal in signals:
            behavior_id = signal.behavior_id
            
            if behavior_id not in aggregated:
                aggregated[behavior_id] = signal
            else:
                # Aggregate: take max score, combine evidence, update reason
                existing = aggregated[behavior_id]
                existing.score = max(existing.score, signal.score)
                existing.confidence = max(existing.confidence, signal.confidence)
                existing.evidence_event_ids = list(set(existing.evidence_event_ids + signal.evidence_event_ids))
                existing.reason = f"{existing.reason}; {signal.reason}"
        
        return aggregated
