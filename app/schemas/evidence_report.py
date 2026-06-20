from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.business_context import BusinessContext, BusinessRiskSummary


class EvidenceReportRequest(BaseModel):
    """Request parameters for evidence report generation."""
    format: str = Field(default="markdown", description="Report format: markdown or json")
    audit: bool = Field(default=False, description="Include internal IDs and diagnostics")
    include_scope: bool = Field(default=True, description="Include targeted regression scope")
    include_diagnostics: bool = Field(default=False, description="Include diagnostic information")


class CoveredRequirement(BaseModel):
    """Requirement covered by passed PR tests."""
    readable_id: str
    source_ac_number: Optional[int] = None
    title: str
    matched_test_name: str
    test_classname: str
    evidence_type: str
    confidence_score: Optional[float] = None
    reason: str
    internal_requirement_id: Optional[str] = None  # Only in audit mode
    businessContext: Optional[BusinessContext] = None


class PartiallySupportedRequirement(BaseModel):
    """Requirement with partial support."""
    readable_id: str
    source_ac_number: Optional[int] = None
    title: str
    supporting_evidence: str
    why_not_fully_verified: str
    what_would_make_it_verified: str
    suggested_strengthening_action: str
    internal_requirement_id: Optional[str] = None  # Only in audit mode
    businessContext: Optional[BusinessContext] = None


class MissingCoverageRequirement(BaseModel):
    """Requirement missing automated coverage."""
    readable_id: str
    source_ac_number: Optional[int] = None
    title: str
    flow: str
    why_not_covered: str
    suggested_test_title: str
    suggested_layer: str
    risk_if_skipped: str
    closest_candidate: Optional[str] = None
    rejection_reason: Optional[str] = None
    internal_requirement_id: Optional[str] = None  # Only in audit mode
    businessContext: Optional[BusinessContext] = None


class ExcludedPassedTest(BaseModel):
    """Test excluded from rerun."""
    test_name: str
    classname: str
    status: str
    reason_excluded: str
    internal_test_id: Optional[str] = None  # Only in audit mode


class EvidenceGraphSnapshotInfo(BaseModel):
    """Evidence graph snapshot reference."""
    recommendation_run_id: str
    snapshot_hash: str
    generated_at: datetime
    source_hash: Optional[str] = None
    evidence_version: Optional[str] = None


class UploadedEvidence(BaseModel):
    """Summary of uploaded evidence."""
    acceptance_criteria_source: str
    junit_execution_summary: Dict[str, Any]
    coverage_summary: Dict[str, Any]
    evidence_graph_snapshot: EvidenceGraphSnapshotInfo


class TargetedScopeSummary(BaseModel):
    """Summary of targeted regression scope."""
    required_items_count: int
    review_items_count: int
    excluded_verified_requirements_count: int
    excluded_passed_tests_count: int
    passed_tests_recommended_for_rerun: bool
    generation_rules_applied: List[str]


class EvidenceReport(BaseModel):
    """Complete QA evidence report."""
    title: str
    generated_at: datetime
    pr_title: Optional[str] = None
    pr_number: Optional[int] = None
    
    # Executive Summary
    health: str
    decision_status: str
    current_pr_test_results: Dict[str, int]
    acceptance_criteria_coverage: Dict[str, int]
    executive_summary_text: str
    
    # Release Decision
    release_decision_text: str
    
    # Uploaded Evidence
    uploaded_evidence: UploadedEvidence
    
    # Coverage Details
    covered_by_passed_pr_tests: List[CoveredRequirement]
    partially_supported_requirements: List[PartiallySupportedRequirement]
    missing_automated_coverage: List[MissingCoverageRequirement]
    
    # Targeted Scope
    targeted_scope: Optional[TargetedScopeSummary] = None
    
    # Business Risk Summary (only when business context enabled)
    business_risk_summary: Optional[BusinessRiskSummary] = None
    risk_review_decisions: Optional[Dict[str, Any]] = None
    
    # Risks and Actions
    remaining_risks: List[str]
    recommended_next_actions: List[str]
    
    # Audit Appendix (only when audit=true)
    audit_appendix: Optional[Dict[str, Any]] = None
    
    # Optimization Summary (only when include_optimization_summary=true)
    optimization_summary: Optional[Dict[str, Any]] = None


class EvidenceReportResponse(BaseModel):
    """Response for evidence report endpoint."""
    status: str
    report: Optional[EvidenceReport] = None
    markdown_content: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    can_render_report: Optional[bool] = None
