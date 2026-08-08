"""
Pydantic schemas for AC Test Mapping Review API.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class EvidenceItem(BaseModel):
    """Individual evidence item for a mapping."""
    type: str
    description: str


class SuggestedTest(BaseModel):
    """Suggested test mapping for an AC with full evidence chain details."""
    edge_id: Optional[str] = None
    candidate_id: Optional[str] = None
    test_case_id: Optional[str] = None
    stable_test_id: str
    test_name: str
    test_title: Optional[str] = ""
    suite_name: Optional[str] = ""
    classname: Optional[str] = ""
    declared_ac_ref: Optional[str] = None
    declared_ac_text: Optional[str] = None
    semantic_best_match_ac_ref: Optional[str] = None
    semantic_best_match_ac_id: Optional[str] = None
    semantic_best_match_ac_text: Optional[str] = None
    semantic_best_match_score: Optional[float] = 0.0
    flow_from_test: Optional[str] = None
    flow_from_declared_ac: Optional[str] = None
    flow_from_semantic_match: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_score: Optional[float] = Field(default=0.0, ge=0.0, le=1.0)
    confidence_label: Optional[str] = "low"
    edge_source: str
    candidate_source: Optional[str] = None
    review_status: str
    evidence: List[str] = []
    reason: str = ""
    conflict_detected: bool = False
    conflict_type: Optional[str] = None
    conflict_reason: Optional[str] = None
    semantic_match_accept_allowed: bool = False
    coverage_type: str = "none"
    execution_status: str = "unknown"
    partial_support_reason: Optional[str] = None
    recommended_action: Optional[str] = None
    audit_metadata: Optional[Dict[str, Any]] = None


class ACTestMappingGroup(BaseModel):
    """Group of mappings for a single AC."""
    ac_id: Optional[str] = None
    stable_ac_key: str
    display_ac_ref: Optional[str] = None
    ac_title: str
    ac_text: str
    requirement_group: str
    business_flow: Optional[str] = None
    repository_id: Optional[str] = None
    pull_request_id: Optional[str] = None
    status: str = Field(..., description="USER_CONFIRMED | VERISCOPE_KEY_VERIFIED | EVIDENCE_VERIFIED_ALIGNED | METADATA_CONFLICT_SEMANTIC_MATCH | PARTIAL_SUPPORT | SUGGESTED | NO_CANDIDATE | REJECTED")
    row_status: Optional[str] = None
    has_conflict: bool = False
    suggested_tests_count: int = 0
    suggested_tests: List[SuggestedTest] = []
    debug: Optional[Dict[str, Any]] = None


class ACTestMappingResponse(BaseModel):
    """Response for AC test mappings endpoint."""
    mappings: List[ACTestMappingGroup]
    total_acs: int
    confirmed_acs: int
    suggested_acs: int
    needs_review_acs: int
    unmapped_acs: int
    rejected_acs: int


class MappingApprovalRequest(BaseModel):
    """Request to approve a mapping."""
    approval_mode: Optional[str] = Field(default="normal", description="normal | approve_anyway")
    acknowledged_warnings: Optional[bool] = Field(default=False, description="Whether user acknowledged uncertainty/conflict warnings")
    comment: Optional[str] = None
    notes: Optional[str] = None
    repository_id: Optional[str] = None
    pull_request_id: Optional[str] = None


class MappingRejectionRequest(BaseModel):
    """Request to reject a mapping."""
    reason: str = Field(..., description="Reason for rejection")
    comment: Optional[str] = None
    repository_id: Optional[str] = None
    pull_request_id: Optional[str] = None


class ManualMappingRequest(BaseModel):
    """Request to create a manual mapping."""
    ac_id: Optional[str] = None
    test_id: Optional[str] = None
    target_ac_id: Optional[str] = None
    test_case_id: Optional[str] = None
    source_candidate_id: Optional[str] = None
    pull_request_id: str
    repository_id: Optional[str] = None
    reason: Optional[str] = None
    comment: Optional[str] = None


class MarkAcceptedGapRequest(BaseModel):
    """Request to mark an AC with no candidate as an accepted gap/risk."""
    ac_id: str
    repository_id: str
    pull_request_id: str
    reason: str = Field(..., description="Required reason for accepting the gap")
    decision_type: Optional[str] = Field(default="ACCEPTED_GAP", description="ACCEPTED_GAP | ACCEPTED_RISK | OUT_OF_SCOPE")
    risk_category: Optional[str] = Field(default=None, description="Optional risk classification")
    out_of_scope: Optional[bool] = Field(default=False, description="Whether the AC is considered out of scope")


class AcceptPartialSupportRequest(BaseModel):
    """Request to accept partial evidence for an AC-test mapping."""
    comment: Optional[str] = None
    repository_id: Optional[str] = None
    pull_request_id: Optional[str] = None


class AcceptSemanticMatchRequest(BaseModel):
    """Request to accept the semantic match for a candidate."""
    comment: Optional[str] = None
    repository_id: Optional[str] = None
    pull_request_id: Optional[str] = None


class KeepDeclaredRefRequest(BaseModel):
    """Request to keep declared AC ref despite conflict."""
    acknowledged_warning: bool = Field(True, description="Explicit warning acknowledgment")
    comment: Optional[str] = None
    repository_id: Optional[str] = None
    pull_request_id: Optional[str] = None


class MarkUnmappedRequest(BaseModel):
    """Request to mark candidate or AC mapping as unmapped."""
    reason: Optional[str] = None
    comment: Optional[str] = None
    repository_id: Optional[str] = None
    pull_request_id: Optional[str] = None


class AddCommentRequest(BaseModel):
    """Request to add a review comment."""
    comment: str = Field(..., description="Review comment text")
    repository_id: Optional[str] = None
    pull_request_id: Optional[str] = None


class MappingReviewSummary(BaseModel):
    """Summary of mapping review status."""
    total_mappings: int
    confirmed_mappings: int
    suggested_mappings: int
    needs_review_mappings: int
    rejected_mappings: int
    last_updated: datetime


class MappingAction(BaseModel):
    """Action taken on a mapping."""
    edge_id: str
    action: str = Field(..., description="approved | rejected | created")
    user_id: str
    timestamp: datetime
    notes: Optional[str] = None


class MappingSummary(BaseModel):
    """Summary of mapping review counts — 7-state evidence-aware model."""
    # ── User-actioned ──────────────────────────────────────────────────────────
    total_acs: int = 0
    confirmed: int = 0                       # USER_CONFIRMED (human approval)
    user_confirmed: int = 0
    veriscope_key_verified: int = 0
    # ── Evidence-level states (no user action required) ───────────────────────
    evidence_verified_aligned: int = 0       # Declared ref + semantics agree
    # ── Needs-resolution states ───────────────────────────────────────────────
    metadata_conflict_semantic_match: int = 0  # XML ref wrong, semantic match strong
    partial_support: int = 0                 # Partial evidence only
    # ── System suggestions ────────────────────────────────────────────────────
    suggested: int = 0
    needs_review: int = 0
    conflicted: int = 0                      # True semantic conflict (no viable candidate)
    # ── No evidence ───────────────────────────────────────────────────────────
    no_candidate: int = 0                    # Zero test support
    rejected: int = 0
    accepted_gap: int = 0                    # Accepted risk/out-of-scope gap
    # ── Backward compat aliases ───────────────────────────────────────────────
    pending_review: int = 0
    unmapped: int = 0                        # Alias for no_candidate
    # ── Execution summary (separate from mapping status) ──────────────────────
    execution_total: int = 0
    execution_passed: int = 0
    execution_failed: int = 0
    execution_skipped: int = 0
    sum_check: int = 0
    is_ac_level_exclusive: bool = True
    summary_integrity: str = "PASS"
    quality_warnings: List[str] = Field(default_factory=list)


class ACTestMappingGroupedResponse(BaseModel):
    """Grouped mappings response with nested product contract and compatibility fields."""
    summary: MappingSummary
    items: List[ACTestMappingGroup]
    execution_summary: Dict[str, Any] = Field(default_factory=dict)
    mapping_summary: Dict[str, Any] = Field(default_factory=dict)
    candidate_summary: Dict[str, int] = Field(default_factory=dict)
    rows: List[ACTestMappingGroup] = Field(default_factory=list)
    quality_warnings: List[str] = Field(default_factory=list)
    compatibility_summary: Dict[str, int] = Field(default_factory=dict)


