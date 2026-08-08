from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class TestAlignmentResult(BaseModel):
    """Alignment evaluation result for a single TestCase against the uploaded AC package."""
    __test__ = False
    test_case_id: str
    test_name: str
    test_title: Optional[str] = ""
    classname: Optional[str] = ""
    declared_ac_ref: Optional[str] = None
    declared_ac_exists: bool = False
    declared_ac_text: Optional[str] = None
    semantic_best_match_ac_ref: Optional[str] = None
    semantic_best_match_ac_text: Optional[str] = None
    semantic_best_match_score: float = 0.0
    declared_ref_matches_semantics: bool = False
    flow_from_test: Optional[str] = ""
    flow_from_declared_ac: Optional[str] = ""
    flow_from_semantic_match: Optional[str] = ""
    conflict_detected: bool = False
    conflict_type: str = Field(
        ...,
        description="NONE | EXTERNAL_REF_SEMANTIC_CONFLICT | AMBIGUOUS_REF | UNKNOWN_REF | LOW_CONFIDENCE"
    )
    confidence_score: float = 0.0
    partial_support_ac_refs: List[str] = Field(default_factory=list)
    partial_support_reason: Optional[str] = None
    review_status: str = Field(
        ...,
        description=(
            "verified | evidence_verified_aligned | suggested_strong | suggested_weak | "
            "conflicted | metadata_conflict_semantic_match | partial_support | unresolved"
        )
    )
    reason: str

    # ── New fields for METADATA_CONFLICT_SEMANTIC_MATCH routing ──────────────
    # When review_status == "metadata_conflict_semantic_match", these carry the
    # semantically-correct AC so that candidates can be linked to it instead of
    # the wrong declared ref.
    semantic_ac_ref_for_conflict: Optional[str] = None
    semantic_ac_text_for_conflict: Optional[str] = None

    def to_evidence_json(self) -> Dict[str, Any]:
        """Convert alignment result to required candidate evidence_json payload."""
        status_upper = self.review_status.upper()
        if status_upper == "VERIFIED":
            status_enum = "VERIFIED"
        elif status_upper == "EVIDENCE_VERIFIED_ALIGNED":
            status_enum = "EVIDENCE_VERIFIED_ALIGNED"
        elif status_upper == "SUGGESTED_STRONG":
            status_enum = "SUGGESTED_STRONG"
        elif status_upper == "SUGGESTED_WEAK":
            status_enum = "SUGGESTED_WEAK"
        elif status_upper == "METADATA_CONFLICT_SEMANTIC_MATCH":
            status_enum = "METADATA_CONFLICT_SEMANTIC_MATCH"
        elif status_upper == "PARTIAL_SUPPORT":
            status_enum = "PARTIAL_SUPPORT"
        elif status_upper == "CONFLICTED" or self.conflict_detected:
            status_enum = "CONFLICTED"
        elif self.conflict_type == "AMBIGUOUS_REF":
            status_enum = "AMBIGUOUS"
        elif status_upper == "UNRESOLVED":
            status_enum = "UNRESOLVED"
        elif status_upper in ("USER_CONFIRMED", "CONFIRMED"):
            status_enum = "USER_CONFIRMED"
        elif status_upper in ("USER_REJECTED", "REJECTED"):
            status_enum = "USER_REJECTED"
        else:
            status_enum = status_upper

        payload: Dict[str, Any] = {
            "declared_ref": self.declared_ac_ref,
            "declared_ref_exists": self.declared_ac_exists,
            "declared_ac_text": self.declared_ac_text,
            "test_name": self.test_name,
            "test_title": self.test_title or "",
            "classname": self.classname or "",
            "semantic_best_match": {
                "ac_ref": self.semantic_best_match_ac_ref,
                "ac_text": self.semantic_best_match_ac_text,
                "score": round(float(self.semantic_best_match_score), 2)
            },
            "flow_evidence": {
                "test_flow": self.flow_from_test or "",
                "declared_ac_flow": self.flow_from_declared_ac or "",
                "semantic_match_flow": self.flow_from_semantic_match or "",
                "flow_match": bool(self.declared_ref_matches_semantics and not self.conflict_detected)
            },
            "partial_support": {
                "ac_refs": self.partial_support_ac_refs,
                "reason": self.partial_support_reason
            },
            "decision": {
                "status": status_enum,
                "confidence": round(float(self.confidence_score), 2),
                "reason": self.reason
            }
        }

        # Carry conflict routing evidence for METADATA_CONFLICT_SEMANTIC_MATCH
        if status_enum == "METADATA_CONFLICT_SEMANTIC_MATCH":
            payload["conflict_routing"] = {
                "declared_wrong_ac_ref": self.declared_ac_ref,
                "declared_wrong_ac_text": self.declared_ac_text,
                "semantic_correct_ac_ref": self.semantic_ac_ref_for_conflict,
                "semantic_correct_ac_text": self.semantic_ac_text_for_conflict,
                "semantic_score": round(float(self.semantic_best_match_score), 2),
            }

        return payload


class ImportAlignmentSummary(BaseModel):
    """Aggregate alignment validation summary produced after importing/evaluating test results."""
    tests_total: int
    tests_with_declared_ac_ref: int
    verified_mappings: int
    # ── New status-model counts ───────────────────────────────────────────────
    evidence_verified_aligned: int = 0
    metadata_conflict_semantic_match: int = 0
    partial_support_emitted: int = 0
    # ── Legacy counts (kept for backward compat) ──────────────────────────────
    suggested_strong: int
    suggested_weak: int
    conflicted: int
    unresolved: int
    ambiguous: int
    metadata_quality: str = Field(..., description="PASS | PARTIAL | FAIL")
    confidence_impact: str = Field(..., description="NONE | LOW | MEDIUM | HIGH")
    partial_mappings: List[Dict[str, Any]] = Field(default_factory=list)
    no_candidate_ac_refs: List[str] = Field(default_factory=list)
    alignment_matrix: List[Dict[str, Any]] = Field(default_factory=list)
    alignment_results: Optional[List[TestAlignmentResult]] = None
