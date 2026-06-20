"""Regression Scope schemas for targeted scope creation."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from app.schemas.business_context import BusinessContext


class ScopeItemType(str, Enum):
    """Type of scope item."""
    REQUIRED_MISSING_COVERAGE = "REQUIRED_MISSING_COVERAGE"
    REVIEW_PARTIAL_COVERAGE = "REVIEW_PARTIAL_COVERAGE"
    OPTIONAL_SAFETY_NET = "OPTIONAL_SAFETY_NET"
    EXCLUDED_ALREADY_VERIFIED_REQUIREMENT = "EXCLUDED_ALREADY_VERIFIED_REQUIREMENT"
    EXCLUDED_ALREADY_PASSED_TEST = "EXCLUDED_ALREADY_PASSED_TEST"


class ScopeItem(BaseModel):
    """Individual scope item."""
    id: str
    item_type: ScopeItemType
    source_requirement_id: Optional[str] = None
    readable_id: Optional[str] = None
    source_ac_number: Optional[int] = None
    title: Optional[str] = None
    flow: Optional[str] = None
    classification: Optional[str] = None
    suggested_action: Optional[str] = None
    suggested_test_title: Optional[str] = None
    suggested_layer: Optional[str] = None
    risk_if_skipped: Optional[str] = None
    evidence_summary: Optional[Dict[str, Any]] = None
    matched_tests: Optional[List[Dict[str, Any]]] = None
    diagnostics: Optional[Dict[str, Any]] = None
    businessContext: Optional[BusinessContext] = None
    # For excluded items
    reason_excluded: Optional[str] = None
    # For test items
    test_id: Optional[str] = None
    class_name: Optional[str] = None


class EvidenceGraphSnapshotReference(BaseModel):
    """Reference to the evidence graph snapshot used for scope creation."""
    recommendation_run_id: str
    snapshot_hash: str
    generated_at: datetime
    source_hash: Optional[str] = None
    evidence_version: Optional[str] = None


class RegressionScope(BaseModel):
    """Targeted regression scope generated from evidence graph."""
    id: str
    recommendation_run_id: str
    source_evidence_graph_snapshot: Optional[EvidenceGraphSnapshotReference] = None
    created_at: datetime
    scope_type: str = "TARGETED_FROM_EVIDENCE"
    health_at_creation: str
    summary: str
    required_items: List[ScopeItem] = Field(default_factory=list)
    review_items: List[ScopeItem] = Field(default_factory=list)
    optional_safety_net_items: List[ScopeItem] = Field(default_factory=list)
    excluded_already_verified_requirements: List[ScopeItem] = Field(default_factory=list)
    excluded_already_passed_tests: List[ScopeItem] = Field(default_factory=list)
    generation_rules_applied: List[str] = Field(default_factory=list)
    diagnostics: List[str] = Field(default_factory=list)


class CreateTargetedScopeRequest(BaseModel):
    """Request body for creating targeted scope."""
    scope_type: str = "TARGETED_FROM_EVIDENCE"
    include_optional_safety_net: bool = False
    include_already_passed_tests: bool = False
    include_audit_diagnostics: bool = False
    include_business_context: bool = True


class CreateTargetedScopeResponse(BaseModel):
    """Response for creating targeted scope."""
    status: str
    scope: Optional[RegressionScope] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
