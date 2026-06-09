"""
FragilityExplanationGenerator Service

Turns fragility signals into readable, non-alarmist explanations.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent
from app.models.behavior import Behavior
from app.models.journey import Journey

logger = logging.getLogger(__name__)


class FragilityExplanationGenerator:
    """Generates human-readable explanations for fragility signals."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_explanation(
        self,
        memory: FragilityMemoryV2,
        include_evidence_count: bool = True,
        include_timeframe: bool = True,
    ) -> str:
        """
        Generate a human-readable explanation for a fragility memory.
        
        Args:
            memory: FragilityMemoryV2 record
            include_evidence_count: Whether to include evidence count
            include_timeframe: Whether to include timeframe
            
        Returns:
            Human-readable explanation string
        """
        # Get evidence events for this memory
        evidence_events = self.db.query(FragilityEvidenceEvent).filter(
            FragilityEvidenceEvent.fragility_memory_id == memory.id
        ).all()
        
        # Generate explanation based on memory type
        if memory.memory_type == "BEHAVIOR_FRAGILITY":
            return self._generate_behavior_explanation(memory, evidence_events, include_evidence_count, include_timeframe)
        elif memory.memory_type == "JOURNEY_FRAGILITY":
            return self._generate_journey_explanation(memory, evidence_events, include_evidence_count, include_timeframe)
        elif memory.memory_type == "MISSING_COVERAGE_PATTERN":
            return self._generate_missing_coverage_explanation(memory, evidence_events, include_evidence_count, include_timeframe)
        elif memory.memory_type == "FILE_FAILURE_HOTSPOT":
            return self._generate_file_hotspot_explanation(memory, evidence_events, include_evidence_count, include_timeframe)
        elif memory.memory_type == "REPEATED_TEST_FAILURE":
            return self._generate_repeated_failure_explanation(memory, evidence_events, include_evidence_count, include_timeframe)
        elif memory.memory_type == "ESCAPED_DEFECT_PATTERN":
            return self._generate_escaped_defect_explanation(memory, evidence_events, include_evidence_count, include_timeframe)
        elif memory.memory_type == "ROLLBACK_PATTERN":
            return self._generate_rollback_explanation(memory, evidence_events, include_evidence_count, include_timeframe)
        elif memory.memory_type == "CO_FAILURE_PATTERN":
            return self._generate_co_failure_explanation(memory, evidence_events, include_evidence_count, include_timeframe)
        elif memory.memory_type == "RISKY_CHANGE_COMBINATION":
            return self._generate_risky_combination_explanation(memory, evidence_events, include_evidence_count, include_timeframe)
        else:
            return self._generate_generic_explanation(memory, evidence_events, include_evidence_count, include_timeframe)
    
    def _generate_behavior_explanation(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
        include_evidence_count: bool,
        include_timeframe: bool,
    ) -> str:
        """Generate explanation for behavior fragility."""
        behavior_name = memory.subject_name or "this behavior"
        
        # Get behavior for journey context
        behavior = None
        journey_name = None
        if memory.subject_id:
            behavior = self.db.query(Behavior).filter(Behavior.id == memory.subject_id).first()
            if behavior and behavior.journey_id:
                journey = self.db.query(Journey).filter(Journey.id == behavior.journey_id).first()
                if journey:
                    journey_name = journey.name
        
        # Count evidence by type
        evidence_counts = self._count_evidence_by_type(evidence_events)
        
        # Build explanation
        parts = []
        
        # Status indicator
        if memory.status == "STALE":
            parts.append(f"{behavior_name} has historical fragility evidence (stale).")
        else:
            parts.append(f"{behavior_name} has fragility signals.")
        
        # Evidence type explanations
        if evidence_counts.get("ESCAPED_DEFECT", 0) > 0:
            count = evidence_counts["ESCAPED_DEFECT"]
            parts.append(f"Prior escaped-defect evidence from {count} recent PR{'s' if count > 1 else ''}.")
        
        if evidence_counts.get("ROLLBACK", 0) > 0:
            count = evidence_counts["ROLLBACK"]
            parts.append(f"Rollback occurred in {count} related change{'s' if count > 1 else ''}.")
        
        if evidence_counts.get("TEST_FAILURE", 0) > 0:
            count = evidence_counts["TEST_FAILURE"]
            parts.append(f"Test failures occurred in {count} related run{'s' if count > 1 else ''}.")
        
        if evidence_counts.get("MISSING_COVERAGE", 0) > 0:
            count = evidence_counts["MISSING_COVERAGE"]
            parts.append(f"Missing coverage patterns detected in {count} instance{'s' if count > 1 else ''}.")
        
        # Journey context
        if journey_name:
            parts.append(f"Part of the {journey_name} journey.")
        
        # Timeframe
        if include_timeframe and evidence_events:
            most_recent = max(evidence_events, key=lambda e: e.occurred_at)
            days_ago = (datetime.utcnow() - most_recent.occurred_at).days
            if days_ago < 7:
                parts.append("Most recent evidence within the last week.")
            elif days_ago < 30:
                parts.append(f"Most recent evidence within the last {days_ago} days.")
            elif days_ago < 90:
                parts.append(f"Most recent evidence within the last {days_ago} days.")
        
        # Risk level
        if memory.risk_level == "CRITICAL":
            parts.append("High-risk pattern detected.")
        elif memory.risk_level == "HIGH":
            parts.append("Elevated risk pattern.")
        
        return " ".join(parts)
    
    def _generate_journey_explanation(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
        include_evidence_count: bool,
        include_timeframe: bool,
    ) -> str:
        """Generate explanation for journey fragility."""
        journey_name = memory.subject_name or "this journey"
        
        # Count evidence by type
        evidence_counts = self._count_evidence_by_type(evidence_events)
        
        parts = []
        
        if memory.status == "STALE":
            parts.append(f"{journey_name} has historical fragility evidence (stale).")
        else:
            parts.append(f"{journey_name} shows fragility patterns.")
        
        if evidence_counts.get("ESCAPED_DEFECT", 0) > 0:
            count = evidence_counts["ESCAPED_DEFECT"]
            parts.append(f"Prior escaped-defect evidence from {count} recent PR{'s' if count > 1 else ''}.")
        
        if evidence_counts.get("ROLLBACK", 0) > 0:
            count = evidence_counts["ROLLBACK"]
            parts.append(f"Rollback occurred in {count} related change{'s' if count > 1 else ''}.")
        
        if include_timeframe and evidence_events:
            most_recent = max(evidence_events, key=lambda e: e.occurred_at)
            days_ago = (datetime.utcnow() - most_recent.occurred_at).days
            if days_ago < 30:
                parts.append(f"Most recent evidence within the last {days_ago} days.")
        
        return " ".join(parts)
    
    def _generate_missing_coverage_explanation(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
        include_evidence_count: bool,
        include_timeframe: bool,
    ) -> str:
        """Generate explanation for missing coverage pattern."""
        scenario_name = memory.subject_name or "this scenario"
        
        parts = []
        
        if memory.status == "STALE":
            parts.append(f"{scenario_name} had missing coverage in past PRs (stale).")
        else:
            parts.append(f"{scenario_name} has missing coverage patterns.")
        
        if include_evidence_count:
            count = len(evidence_events)
            parts.append(f"Detected in {count} recent PR{'s' if count > 1 else ''}.")
        
        if include_timeframe and evidence_events:
            most_recent = max(evidence_events, key=lambda e: e.occurred_at)
            days_ago = (datetime.utcnow() - most_recent.occurred_at).days
            if days_ago < 30:
                parts.append(f"Most recent within the last {days_ago} days.")
        
        return " ".join(parts)
    
    def _generate_file_hotspot_explanation(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
        include_evidence_count: bool,
        include_timeframe: bool,
    ) -> str:
        """Generate explanation for file failure hotspot."""
        file_path = memory.subject_name or "this file"
        
        parts = []
        
        if memory.status == "STALE":
            parts.append(f"{file_path} was a failure hotspot in past changes (stale).")
        else:
            parts.append(f"{file_path} is a failure hotspot.")
        
        if include_evidence_count:
            count = len(evidence_events)
            parts.append(f"Changed before failed test runs in {count} recent PR{'s' if count > 1 else ''}.")
        
        if include_timeframe and evidence_events:
            most_recent = max(evidence_events, key=lambda e: e.occurred_at)
            days_ago = (datetime.utcnow() - most_recent.occurred_at).days
            if days_ago < 30:
                parts.append(f"Most recent within the last {days_ago} days.")
        
        return " ".join(parts)
    
    def _generate_repeated_failure_explanation(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
        include_evidence_count: bool,
        include_timeframe: bool,
    ) -> str:
        """Generate explanation for repeated test failure."""
        test_name = memory.subject_name or "this test"
        
        parts = []
        
        if memory.status == "STALE":
            parts.append(f"{test_name} had repeated failures in the past (stale).")
        else:
            parts.append(f"{test_name} shows repeated failure patterns.")
        
        if include_evidence_count:
            count = len(evidence_events)
            parts.append(f"Failed in {count} recent run{'s' if count > 1 else ''}.")
        
        if include_timeframe and evidence_events:
            most_recent = max(evidence_events, key=lambda e: e.occurred_at)
            days_ago = (datetime.utcnow() - most_recent.occurred_at).days
            if days_ago < 30:
                parts.append(f"Most recent within the last {days_ago} days.")
        
        return " ".join(parts)
    
    def _generate_escaped_defect_explanation(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
        include_evidence_count: bool,
        include_timeframe: bool,
    ) -> str:
        """Generate explanation for escaped defect pattern."""
        parts = []
        
        if memory.status == "STALE":
            parts.append("Historical escaped defect evidence (stale).")
        else:
            parts.append("Prior escaped defect detected.")
        
        if include_evidence_count:
            count = len(evidence_events)
            parts.append(f"Recorded in {count} recent PR{'s' if count > 1 else ''}.")
        
        if include_timeframe and evidence_events:
            most_recent = max(evidence_events, key=lambda e: e.occurred_at)
            days_ago = (datetime.utcnow() - most_recent.occurred_at).days
            if days_ago < 30:
                parts.append(f"Most recent within the last {days_ago} days.")
        
        return " ".join(parts)
    
    def _generate_rollback_explanation(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
        include_evidence_count: bool,
        include_timeframe: bool,
    ) -> str:
        """Generate explanation for rollback pattern."""
        parts = []
        
        if memory.status == "STALE":
            parts.append("Historical rollback evidence (stale).")
        else:
            parts.append("Rollback occurred in related changes.")
        
        if include_evidence_count:
            count = len(evidence_events)
            parts.append(f"Recorded in {count} recent PR{'s' if count > 1 else ''}.")
        
        if include_timeframe and evidence_events:
            most_recent = max(evidence_events, key=lambda e: e.occurred_at)
            days_ago = (datetime.utcnow() - most_recent.occurred_at).days
            if days_ago < 30:
                parts.append(f"Most recent within the last {days_ago} days.")
        
        return " ".join(parts)
    
    def _generate_co_failure_explanation(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
        include_evidence_count: bool,
        include_timeframe: bool,
    ) -> str:
        """Generate explanation for co-failure pattern."""
        subject = memory.subject_name or "these components"
        
        parts = []
        
        if memory.status == "STALE":
            parts.append(f"{subject} failed together in the past (stale).")
        else:
            parts.append(f"{subject} show co-failure patterns.")
        
        if include_evidence_count:
            count = len(evidence_events)
            parts.append(f"Detected in {count} recent run{'s' if count > 1 else ''}.")
        
        if include_timeframe and evidence_events:
            most_recent = max(evidence_events, key=lambda e: e.occurred_at)
            days_ago = (datetime.utcnow() - most_recent.occurred_at).days
            if days_ago < 30:
                parts.append(f"Most recent within the last {days_ago} days.")
        
        return " ".join(parts)
    
    def _generate_risky_combination_explanation(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
        include_evidence_count: bool,
        include_timeframe: bool,
    ) -> str:
        """Generate explanation for risky change combination."""
        combination = memory.subject_name or "this combination"
        
        parts = []
        
        if memory.status == "STALE":
            parts.append(f"{combination} was risky in past changes (stale).")
        else:
            parts.append(f"{combination} is a risky change pattern.")
        
        if include_evidence_count:
            count = len(evidence_events)
            parts.append(f"Led to failures in {count} recent PR{'s' if count > 1 else ''}.")
        
        if include_timeframe and evidence_events:
            most_recent = max(evidence_events, key=lambda e: e.occurred_at)
            days_ago = (datetime.utcnow() - most_recent.occurred_at).days
            if days_ago < 30:
                parts.append(f"Most recent within the last {days_ago} days.")
        
        return " ".join(parts)
    
    def _generate_generic_explanation(
        self,
        memory: FragilityMemoryV2,
        evidence_events: List[FragilityEvidenceEvent],
        include_evidence_count: bool,
        include_timeframe: bool,
    ) -> str:
        """Generate generic explanation for unknown memory types."""
        subject = memory.subject_name or "this item"
        
        parts = []
        
        if memory.status == "STALE":
            parts.append(f"{subject} has historical fragility evidence (stale).")
        else:
            parts.append(f"{subject} has fragility signals.")
        
        if include_evidence_count:
            count = len(evidence_events)
            parts.append(f"Based on {count} evidence event{'s' if count > 1 else ''}.")
        
        return " ".join(parts)
    
    def _count_evidence_by_type(
        self,
        evidence_events: List[FragilityEvidenceEvent],
    ) -> Dict[str, int]:
        """Count evidence events by type."""
        counts = {}
        for event in evidence_events:
            counts[event.evidence_type] = counts.get(event.evidence_type, 0) + 1
        return counts
    
    def generate_batch_explanations(
        self,
        memories: List[FragilityMemoryV2],
    ) -> Dict[uuid.UUID, str]:
        """
        Generate explanations for multiple fragility memories.
        
        Args:
            memories: List of FragilityMemoryV2 records
            
        Returns:
            Dict mapping memory_id to explanation string
        """
        explanations = {}
        for memory in memories:
            explanations[memory.id] = self.generate_explanation(memory)
        return explanations
