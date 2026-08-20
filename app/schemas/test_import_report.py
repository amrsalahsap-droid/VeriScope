from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ImportQualityConflictExample(BaseModel):
    test_name: str
    declared_ac_ref: Optional[str] = None
    declared_ac_text: Optional[str] = None
    semantic_best_match_ref: Optional[str] = None
    semantic_best_match_text: Optional[str] = None
    status: str = Field(..., description="CONFLICTED | AMBIGUOUS | UNRESOLVED")
    recommended_action: str = "Review and resolve mapping"

class TestImportQualityReportResponse(BaseModel):
    import_id: str
    tests_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    tests_with_declared_ac_refs: int = 0
    verified_mappings: int = 0
    suggested_strong: int = 0
    suggested_weak: int = 0
    conflicted_refs: int = 0
    ambiguous_refs: int = 0
    unresolved_refs: int = 0
    metadata_quality_status: str = Field(..., description="PASS | PARTIAL | FAIL")
    mapping_confidence_impact: str = Field(..., description="NONE | LOW | MEDIUM | HIGH")
    warnings: List[str] = Field(default_factory=list)
    examples: List[ImportQualityConflictExample] = Field(default_factory=list)

    # Ignore pytest test class warning
    __test__ = False
