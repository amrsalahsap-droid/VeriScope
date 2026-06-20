"""Manual Evidence dataclasses and structures for the evidence graph."""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

@dataclass
class ManualEvidenceNode:
    """Represents a manual validation mapping and execution outcome in the evidence graph."""
    manual_test_id: str
    manual_test_title: str
    acceptance_criterion_id: str
    source_ac_number: Optional[int]
    outcome: Optional[str]  # PASSED, FAILED, SKIPPED, BLOCKED, or None
    executed_by: Optional[str]
    executed_at: Optional[str]  # ISO timestamp
    notes: Optional[str]
    evidence_url: Optional[str]
    mapping_source: str = "MANUAL"
    evidence_source: str = "MANUAL"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a standardized dictionary serialization."""
        return {
            "manualTestId": self.manual_test_id,
            "manualTestTitle": self.manual_test_title,
            "acceptanceCriterionId": self.acceptance_criterion_id,
            "sourceAcNumber": self.source_ac_number,
            "outcome": self.outcome or "NOT_EXECUTED",
            "executedBy": self.executed_by,
            "executedAt": self.executed_at,
            "notes": self.notes,
            "evidenceUrl": self.evidence_url,
            "mappingSource": self.mapping_source,
            "evidenceSource": self.evidence_source,
        }
