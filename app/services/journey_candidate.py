from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class JourneyCandidate:
    """Candidate journey discovered from behavior analysis."""
    name: str
    confidence: str  # HIGH, MODERATE, LOW
    behaviors: List[str]  # List of behavior names
    evidence: List[str]  # List of evidence strings
    source_confidence_score: float = 0.0  # Raw score (0-100)
    description: Optional[str] = None
    business_value: Optional[str] = None
    risk_level: Optional[str] = None  # LOW, MEDIUM, HIGH, CRITICAL
    
    def get_behavior_count(self) -> int:
        """Get the number of behaviors in this journey."""
        return len(self.behaviors)
    
    def get_evidence_count(self) -> int:
        """Get the number of evidence items."""
        return len(self.evidence)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert candidate to dictionary for serialization."""
        return {
            "name": self.name,
            "confidence": self.confidence,
            "behaviors": self.behaviors,
            "evidence": self.evidence,
            "source_confidence_score": self.source_confidence_score,
            "description": self.description,
            "business_value": self.business_value,
            "risk_level": self.risk_level,
        }
