"""
PR Regression Decision Schema.

Redesigned output structure for PR-level regression decisions,
focused on test buckets rather than input scores.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class RegressionBucket(str, Enum):
    """Regression test buckets."""
    ALREADY_VERIFIED = "ALREADY_VERIFIED"
    MUST_RUN = "MUST_RUN"
    SHOULD_RUN = "SHOULD_RUN"
    FAILED_CURRENT_PR = "FAILED_CURRENT_PR"
    STALE_RERUN_REQUIRED = "STALE_RERUN_REQUIRED"
    MAPPING_REVIEW_NEEDED = "MAPPING_REVIEW_NEEDED"
    COVERAGE_GAP = "COVERAGE_GAP"
    SAFE_TO_SKIP = "SAFE_TO_SKIP"


class ActiveAction(str, Enum):
    """Active action for the test."""
    RUN = "RUN"
    RERUN = "RERUN"
    REVIEW = "REVIEW"
    CREATE = "CREATE"
    NONE = "NONE"


class MappingReviewStatus(str, Enum):
    """Mapping review status."""
    CONFIRMED = "CONFIRMED"
    SUGGESTED = "SUGGESTED"
    AMBIGUOUS = "AMBIGUOUS"
    MISSING = "MISSING"
    REVIEW_NEEDED = "REVIEW_NEEDED"


class ExecutionStatus(str, Enum):
    """Test execution status."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    NOT_RUN = "NOT_RUN"
    UNKNOWN = "UNKNOWN"


class EvidenceEdge(BaseModel):
    """Single edge in the evidence path."""
    edge_type: str = Field(..., description="Type of edge (e.g., 'changed_file -> dependency')")
    source: str = Field(..., description="Source node")
    target: str = Field(..., description="Target node")
    confidence: Optional[float] = Field(default=None, description="Confidence score for this edge")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class EvidencePath(BaseModel):
    """Evidence path for a regression candidate."""
    edges: List[EvidenceEdge] = Field(default_factory=list, description="Edges in the evidence path")
    complete: bool = Field(default=False, description="Whether the evidence path is complete")
    missing_evidence_reason: Optional[str] = Field(default=None, description="Reason if evidence is missing")


class RegressionCandidate(BaseModel):
    """Regression test candidate with full decision context."""
    stable_test_id: str = Field(..., description="Stable test identifier")
    test_name: str = Field(..., description="Test name")
    bucket: RegressionBucket = Field(..., description="Regression bucket")
    active_action: ActiveAction = Field(..., description="Active action for this test")
    would_have_been_priority: Optional[int] = Field(default=None, description="Priority score")
    reason_codes: List[str] = Field(default_factory=list, description="Reason codes for bucket assignment")
    evidence_path: EvidencePath = Field(default_factory=EvidencePath, description="Evidence path")
    mapping_review_status: MappingReviewStatus = Field(default=MappingReviewStatus.MISSING, description="Mapping review status")
    execution_status: ExecutionStatus = Field(default=ExecutionStatus.NOT_RUN, description="Test execution status")
    execution_commit_sha: Optional[str] = Field(default=None, description="Commit SHA of execution")
    current_head_sha: Optional[str] = Field(default=None, description="Current head commit SHA")
    confidence: float = Field(default=0.0, description="Confidence score for this decision")
    
    # Additional context
    linked_ac_ids: List[str] = Field(default_factory=list, description="Linked AC IDs")
    linked_behavior_ids: List[str] = Field(default_factory=list, description="Linked behavior IDs")
    linked_file_paths: List[str] = Field(default_factory=list, description="Linked file paths")


class PRRegressionDecision(BaseModel):
    """PR-level regression decision output.
    
    Redesigned output focused on test buckets rather than input scores.
    """
    recommendation_run_id: str = Field(..., description="Recommendation run ID")
    pull_request_id: str = Field(..., description="Pull request ID")
    repository_id: str = Field(..., description="Repository ID")
    current_head_sha: str = Field(..., description="Current head commit SHA")
    
    # Output mode
    is_draft: bool = Field(default=True, description="Whether this is a draft output")
    is_confident: bool = Field(default=False, description="Whether this is a confident output")
    readiness_blocker: Optional[str] = Field(default=None, description="Readiness blocker if not confident")
    
    # Buckets
    already_verified: List[RegressionCandidate] = Field(default_factory=list, description="Tests already verified on current PR")
    must_run: List[RegressionCandidate] = Field(default_factory=list, description="Tests that must run")
    should_run: List[RegressionCandidate] = Field(default_factory=list, description="Tests that should run")
    failed_current_pr: List[RegressionCandidate] = Field(default_factory=list, description="Tests that failed on current PR")
    stale_rerun_required: List[RegressionCandidate] = Field(default_factory=list, description="Tests requiring stale rerun")
    mapping_review_needed: List[RegressionCandidate] = Field(default_factory=list, description="Tests needing mapping review")
    coverage_gaps: List[RegressionCandidate] = Field(default_factory=list, description="Coverage gaps")
    safe_to_skip: List[RegressionCandidate] = Field(default_factory=list, description="Tests safe to skip")
    
    # Summary counts
    total_candidates: int = Field(default=0, description="Total number of candidates")
    already_verified_count: int = Field(default=0, description="Count of already verified tests")
    must_run_count: int = Field(default=0, description="Count of must run tests")
    should_run_count: int = Field(default=0, description="Count of should run tests")
    failed_current_pr_count: int = Field(default=0, description="Count of failed tests")
    stale_rerun_required_count: int = Field(default=0, description="Count of stale rerun tests")
    mapping_review_needed_count: int = Field(default=0, description="Count of mapping review needed")
    coverage_gaps_count: int = Field(default=0, description="Count of coverage gaps")
    safe_to_skip_count: int = Field(default=0, description="Count of safe to skip tests")
    
    # Evidence path coverage
    evidence_path_coverage: float = Field(default=0.0, description="Percentage of candidates with complete evidence paths")
    missing_evidence_count: int = Field(default=0, description="Count of candidates with missing evidence")
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")
    structural_impact_used: bool = Field(default=False, description="Whether structural impact was used")
    coverage_level: Optional[str] = Field(default=None, description="Coverage level used")
    
    class Config:
        json_schema_extra = {
            "example": {
                "recommendation_run_id": "uuid",
                "pull_request_id": "uuid",
                "repository_id": "uuid",
                "current_head_sha": "abc123",
                "is_draft": False,
                "is_confident": True,
                "already_verified": [
                    {
                        "stable_test_id": "test-001",
                        "test_name": "Password validation test",
                        "bucket": "ALREADY_VERIFIED",
                        "active_action": "NONE",
                        "reason_codes": ["STRUCTURAL_FRESH_PASS"],
                        "evidence_path": {
                            "edges": [
                                {"edge_type": "changed_file -> dependency", "source": "auth.ts", "target": "validatePassword"},
                                {"edge_type": "function -> test", "source": "validatePassword", "target": "test-001"},
                                {"edge_type": "test -> execution", "source": "test-001", "target": "PASSED"}
                            ],
                            "complete": True
                        },
                        "mapping_review_status": "CONFIRMED",
                        "execution_status": "PASSED",
                        "execution_commit_sha": "abc123",
                        "current_head_sha": "abc123",
                        "confidence": 0.95
                    }
                ],
                "must_run": [],
                "should_run": [],
                "failed_current_pr": [],
                "stale_rerun_required": [],
                "mapping_review_needed": [],
                "coverage_gaps": [],
                "safe_to_skip": [],
                "total_candidates": 1,
                "already_verified_count": 1,
                "evidence_path_coverage": 1.0
            }
        }
