from dataclasses import dataclass
from typing import List, Optional


@dataclass
class JourneyRisk:
    """Risk assessment for a journey."""
    journey_id: str
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    risk_reason: str  # Explainable reason for risk assignment
    affected_users: str  # Description of affected users
    confidence: str  # HIGH, MODERATE, LOW
    contributing_behaviors: List[str]  # List of behavior names contributing to risk
    risk_factors: List[str]  # List of specific risk factors
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "journey_id": self.journey_id,
            "risk_level": self.risk_level,
            "risk_reason": self.risk_reason,
            "affected_users": self.affected_users,
            "confidence": self.confidence,
            "contributing_behaviors": self.contributing_behaviors,
            "risk_factors": self.risk_factors,
        }
