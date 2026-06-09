from dataclasses import dataclass
from typing import List


@dataclass
class JourneyTestingScope:
    """Testing scope for a journey."""
    journey: str  # Journey name
    journey_id: str  # Journey ID
    must_test: List[str]  # Critical tests that must be run
    should_test: List[str]  # Important tests that should be run
    optional: List[str]  # Optional tests for coverage
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "journey": self.journey,
            "journey_id": self.journey_id,
            "must_test": self.must_test,
            "should_test": self.should_test,
            "optional": self.optional,
        }
