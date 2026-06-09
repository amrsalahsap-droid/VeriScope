from dataclasses import dataclass
from typing import List


@dataclass
class JourneyCoverage:
    """Coverage metrics for a journey."""
    journey_id: str
    journey_name: str
    covered_behaviors: List[str]  # Behaviors with full test coverage
    partially_covered_behaviors: List[str]  # Behaviors with partial test coverage
    uncovered_behaviors: List[str]  # Behaviors with no test coverage
    coverage_score: float  # 0-100 percentage
    confidence: str  # HIGH, MODERATE, LOW
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "journey_id": self.journey_id,
            "journey_name": self.journey_name,
            "covered_behaviors": self.covered_behaviors,
            "partially_covered_behaviors": self.partially_covered_behaviors,
            "uncovered_behaviors": self.uncovered_behaviors,
            "coverage_score": self.coverage_score,
            "confidence": self.confidence,
        }
