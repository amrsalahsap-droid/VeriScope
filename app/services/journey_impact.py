from dataclasses import dataclass
from typing import List, Optional


@dataclass
class JourneyImpact:
    """Impact of a PR on a journey."""
    journey_id: str
    journey_name: str
    impact_level: str  # CRITICAL, HIGH, MEDIUM, LOW
    affected_behaviors: List[str]  # List of behavior names
    affected_files: List[str]  # List of changed files
    risk_changes: List[str]  # List of risk change descriptions
    confidence: str  # HIGH, MODERATE, LOW
    impact_reason: str  # Explainable reason for impact
    risk: Optional[str] = None  # Journey risk level (CRITICAL, HIGH, MEDIUM, LOW)
    evidence: Optional[List[dict]] = None  # Evidence supporting the impact
    impacted_behavior_details: Optional[List[dict]] = None  # Detailed impacted behaviors
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "journey_id": self.journey_id,
            "journey_name": self.journey_name,
            "impact_level": self.impact_level,
            "affected_behaviors": self.affected_behaviors,
            "affected_files": self.affected_files,
            "risk_changes": self.risk_changes,
            "confidence": self.confidence,
            "impact_reason": self.impact_reason,
            "risk": self.risk,
            "evidence": self.evidence or [],
            "impacted_behavior_details": self.impacted_behavior_details or [],
        }
