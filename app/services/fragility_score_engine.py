"""
FragilityScoreEngine Service

Calculates deterministic fragility scores.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from app.models.fragility_memory_v2 import FragilityMemoryV2
from app.models.fragility_evidence_event import FragilityEvidenceEvent

logger = logging.getLogger(__name__)


@dataclass
class FragilityScoreInputs:
    """Inputs for fragility score calculation."""
    evidence_count: int = 0
    recency_days: int = 0
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    escaped_defect_count: int = 0
    rollback_count: int = 0
    repeated_failure_count: int = 0
    co_failure_count: int = 0
    missing_coverage_count: int = 0
    affected_behavior_risk: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    base_confidence: float = 0.5
    
    # Evidence type breakdown
    test_failure_count: int = 0
    incident_count: int = 0
    manual_override_count: int = 0


@dataclass
class FragilityScoreResult:
    """Output of fragility score calculation."""
    fragility_score: float
    risk_level: str
    confidence_level: str
    score_breakdown: Dict
    decay_applied: bool = False
    decay_amount: float = 0.0


class FragilityScoreEngine:
    """Calculates deterministic fragility scores."""
    
    # Suggested weights
    ESCAPED_DEFECT_WEIGHT = 35.0
    ROLLBACK_WEIGHT = 30.0
    REPEATED_FAILURE_WEIGHT = 15.0
    RECENT_FAILURE_WEIGHT = 10.0
    CO_FAILURE_WEIGHT = 10.0
    MISSING_COVERAGE_WEIGHT = 10.0
    
    # Decay settings
    STALE_THRESHOLD_DAYS = 30
    DECAY_START_DAYS = 14
    MAX_DECAY_AMOUNT = 30.0
    DECAY_PER_DAY = 1.0
    
    # Risk level thresholds
    CRITICAL_THRESHOLD = 75.0
    HIGH_THRESHOLD = 50.0
    MEDIUM_THRESHOLD = 25.0
    
    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    MEDIUM_CONFIDENCE_THRESHOLD = 0.5
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_score(
        self,
        inputs: FragilityScoreInputs,
        last_seen_at: Optional[datetime] = None,
    ) -> FragilityScoreResult:
        """
        Calculate fragility score from inputs.
        
        Args:
            inputs: FragilityScoreInputs with evidence data
            last_seen_at: Last time this pattern was seen (for decay calculation)
            
        Returns:
            FragilityScoreResult with score, risk level, confidence, and breakdown
        """
        breakdown = {}
        
        # 1. Base score from escaped defects
        escaped_defect_score = min(100.0, inputs.escaped_defect_count * self.ESCAPED_DEFECT_WEIGHT)
        breakdown["escaped_defect_score"] = escaped_defect_score
        breakdown["escaped_defect_count"] = inputs.escaped_defect_count
        
        # 2. Rollback score
        rollback_score = min(100.0, inputs.rollback_count * self.ROLLBACK_WEIGHT)
        breakdown["rollback_score"] = rollback_score
        breakdown["rollback_count"] = inputs.rollback_count
        
        # 3. Repeated failure score
        repeated_failure_score = min(100.0, inputs.repeated_failure_count * self.REPEATED_FAILURE_WEIGHT)
        breakdown["repeated_failure_score"] = repeated_failure_score
        breakdown["repeated_failure_count"] = inputs.repeated_failure_count
        
        # 4. Recent failure score (based on recency)
        if inputs.recency_days <= 7:
            recent_failure_score = self.RECENT_FAILURE_WEIGHT
        elif inputs.recency_days <= 14:
            recent_failure_score = self.RECENT_FAILURE_WEIGHT * 0.7
        elif inputs.recency_days <= 30:
            recent_failure_score = self.RECENT_FAILURE_WEIGHT * 0.4
        else:
            recent_failure_score = 0.0
        breakdown["recent_failure_score"] = recent_failure_score
        breakdown["recency_days"] = inputs.recency_days
        
        # 5. Co-failure pattern score
        co_failure_score = min(100.0, inputs.co_failure_count * self.CO_FAILURE_WEIGHT)
        breakdown["co_failure_score"] = co_failure_score
        breakdown["co_failure_count"] = inputs.co_failure_count
        
        # 6. Missing coverage gap score
        missing_coverage_score = min(100.0, inputs.missing_coverage_count * self.MISSING_COVERAGE_WEIGHT)
        breakdown["missing_coverage_score"] = missing_coverage_score
        breakdown["missing_coverage_count"] = inputs.missing_coverage_count
        
        # 7. Affected behavior risk bonus
        behavior_risk_bonus = self._get_behavior_risk_bonus(inputs.affected_behavior_risk)
        breakdown["behavior_risk_bonus"] = behavior_risk_bonus
        breakdown["affected_behavior_risk"] = inputs.affected_behavior_risk
        
        # 8. Severity multiplier
        severity_multiplier = self._get_severity_multiplier(inputs.severity)
        breakdown["severity_multiplier"] = severity_multiplier
        breakdown["severity"] = inputs.severity
        
        # Calculate base score (sum of components)
        base_score = (
            escaped_defect_score +
            rollback_score +
            repeated_failure_score +
            recent_failure_score +
            co_failure_score +
            missing_coverage_score +
            behavior_risk_bonus
        ) * severity_multiplier
        
        breakdown["base_score"] = round(base_score, 2)
        
        # 9. Apply time decay if stale
        decay_applied = False
        decay_amount = 0.0
        if last_seen_at:
            decay_amount = self._calculate_decay(last_seen_at)
            if decay_amount > 0:
                base_score = max(0.0, base_score - decay_amount)
                decay_applied = True
                breakdown["decay_applied"] = True
                breakdown["decay_amount"] = decay_amount
                breakdown["days_since_last_seen"] = (datetime.utcnow() - last_seen_at).days
        
        # Cap at 100
        final_score = min(100.0, max(0.0, base_score))
        breakdown["final_score"] = round(final_score, 2)
        
        # 10. Determine risk level
        risk_level = self._determine_risk_level(final_score)
        breakdown["risk_level"] = risk_level
        
        # 11. Calculate confidence
        confidence_level = self._calculate_confidence(inputs, final_score)
        breakdown["confidence_level"] = confidence_level
        breakdown["confidence_score"] = inputs.base_confidence
        
        return FragilityScoreResult(
            fragility_score=round(final_score, 2),
            risk_level=risk_level,
            confidence_level=confidence_level,
            score_breakdown=breakdown,
            decay_applied=decay_applied,
            decay_amount=decay_amount,
        )
    
    def calculate_from_memory(
        self,
        memory: FragilityMemoryV2,
    ) -> FragilityScoreResult:
        """
        Calculate score from FragilityMemoryV2 record.
        
        Args:
            memory: FragilityMemoryV2 record
            
        Returns:
            FragilityScoreResult
        """
        # Get evidence events for this memory
        evidence_events = self.db.query(FragilityEvidenceEvent).filter(
            FragilityEvidenceEvent.fragility_memory_id == memory.id
        ).all()
        
        # Build inputs from evidence events
        inputs = self._build_inputs_from_evidence(evidence_events, memory)
        
        # Calculate score
        return self.calculate_score(inputs, memory.last_seen_at)
    
    def _build_inputs_from_evidence(
        self,
        evidence_events: List[FragilityEvidenceEvent],
        memory: FragilityMemoryV2,
    ) -> FragilityScoreInputs:
        """Build FragilityScoreInputs from evidence events."""
        inputs = FragilityScoreInputs()
        
        inputs.evidence_count = len(evidence_events)
        inputs.base_confidence = memory.confidence
        
        # Count evidence types
        for event in evidence_events:
            if event.evidence_type == "ESCAPED_DEFECT":
                inputs.escaped_defect_count += 1
            elif event.evidence_type == "ROLLBACK":
                inputs.rollback_count += 1
            elif event.evidence_type == "REPEATED_FAILURE":
                inputs.repeated_failure_count += 1
            elif event.evidence_type == "TEST_FAILURE":
                inputs.test_failure_count += 1
            elif event.evidence_type == "INCIDENT":
                inputs.incident_count += 1
            elif event.evidence_type == "CO_FAILURE":
                inputs.co_failure_count += 1
            elif event.evidence_type == "MISSING_COVERAGE":
                inputs.missing_coverage_count += 1
            elif event.evidence_type == "MANUAL_OVERRIDE":
                inputs.manual_override_count += 1
        
        # Calculate recency
        if evidence_events:
            most_recent = max(evidence_events, key=lambda e: e.occurred_at)
            inputs.recency_days = (datetime.utcnow() - most_recent.occurred_at).days
        
        # Determine severity based on memory risk level
        inputs.severity = self._memory_risk_to_severity(memory.risk_level)
        
        # Determine affected behavior risk
        if memory.subject_type == "BEHAVIOR":
            inputs.affected_behavior_risk = memory.risk_level
        
        return inputs
    
    def _get_behavior_risk_bonus(self, risk: str) -> float:
        """Get bonus score based on affected behavior risk."""
        risk_bonuses = {
            "CRITICAL": 15.0,
            "HIGH": 10.0,
            "MEDIUM": 5.0,
            "LOW": 0.0,
        }
        return risk_bonuses.get(risk, 0.0)
    
    def _get_severity_multiplier(self, severity: str) -> float:
        """Get multiplier based on severity."""
        severity_multipliers = {
            "CRITICAL": 1.5,
            "HIGH": 1.2,
            "MEDIUM": 1.0,
            "LOW": 0.8,
        }
        return severity_multipliers.get(severity, 1.0)
    
    def _memory_risk_to_severity(self, risk_level: str) -> str:
        """Convert memory risk level to severity."""
        return risk_level  # Same scale
    
    def _calculate_decay(self, last_seen_at: datetime) -> float:
        """
        Calculate decay amount based on time since last seen.
        
        Returns:
            Decay amount to subtract from score
        """
        days_since = (datetime.utcnow() - last_seen_at).days
        
        if days_since < self.DECAY_START_DAYS:
            return 0.0
        
        if days_since >= self.STALE_THRESHOLD_DAYS:
            # Max decay for stale patterns
            return self.MAX_DECAY_AMOUNT
        
        # Linear decay between start and threshold
        days_in_decay_window = days_since - self.DECAY_START_DAYS
        decay_amount = min(self.MAX_DECAY_AMOUNT, days_in_decay_window * self.DECAY_PER_DAY)
        
        return decay_amount
    
    def _determine_risk_level(self, score: float) -> str:
        """Determine risk level from score."""
        if score >= self.CRITICAL_THRESHOLD:
            return "CRITICAL"
        elif score >= self.HIGH_THRESHOLD:
            return "HIGH"
        elif score >= self.MEDIUM_THRESHOLD:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _calculate_confidence(
        self,
        inputs: FragilityScoreInputs,
        score: float,
    ) -> str:
        """
        Calculate confidence level.
        
        Confidence is based on:
        - Evidence count
        - Base confidence
        - Score (higher score = higher confidence)
        """
        # Evidence count contribution
        evidence_confidence = min(1.0, inputs.evidence_count / 10.0)
        
        # Score contribution
        score_confidence = min(1.0, score / 100.0)
        
        # Combined confidence
        combined_confidence = (
            inputs.base_confidence * 0.4 +
            evidence_confidence * 0.3 +
            score_confidence * 0.3
        )
        
        # Determine level
        if combined_confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            return "HIGH"
        elif combined_confidence >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            return "MEDIUM"
        else:
            return "LOW"
