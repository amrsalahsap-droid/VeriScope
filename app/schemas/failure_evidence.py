from datetime import datetime
from uuid import UUID
from typing import List, Optional, Any, Dict
from pydantic import BaseModel

class FailureEvidenceTestResult(BaseModel):
    test_result_id: UUID
    test_run_id: UUID
    test_case_id: UUID
    status: str
    duration: float
    created_at: datetime

    class Config:
        from_attributes = True

class FailureEvidenceTestRun(BaseModel):
    test_run_id: UUID
    repository_id: UUID
    commit_sha: Optional[str] = None
    pull_request_id: Optional[UUID] = None
    status: str
    failed_tests: int
    passed_tests: int
    total_tests: int
    
    # Evidence Quality Metadata
    evidence_health_status: str
    consistency_status: str
    parser_version: str
    normalization_schema_version: str
    replay_verification_status: str
    parser_support_status: str
    created_at: datetime

    class Config:
        from_attributes = True

class FailureEvidencePullRequest(BaseModel):
    pull_request_id: UUID
    repository_id: UUID
    github_pr_id: int
    number: int
    title: str
    author: str
    state: str
    head_commit_sha: str
    created_at: datetime

    class Config:
        from_attributes = True

class FailureEvidenceChangedFile(BaseModel):
    changed_file_id: UUID
    pull_request_id: UUID
    file_path: str
    status: str
    additions: int
    deletions: int
    previous_filename: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class FailureEvidenceRecommendationRun(BaseModel):
    recommendation_run_id: UUID
    repository_id: UUID
    pr_id: str
    pull_request_id: Optional[UUID] = None
    triggered_by: str
    evidence_quality: str
    recommendation_mode: Optional[str] = None
    unsafe_for_optimization: bool = False
    created_at: datetime


    class Config:
        from_attributes = True

class FailureEvidenceRecommendationOutcome(BaseModel):
    recommendation_outcome_id: UUID
    recommendation_run_id: UUID
    executed_tests: List[str]
    manually_added_tests: List[str]
    manually_removed_tests: List[str]
    was_followed: bool
    override_reason: Optional[str] = None
    rollback_occurred: bool = False
    escaped_defect: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

class FailureEvidenceBundle(BaseModel):
    # Normalized Lists
    failed_test_results: List[FailureEvidenceTestResult]
    related_test_runs: List[FailureEvidenceTestRun]
    related_pull_requests: List[FailureEvidencePullRequest]
    related_changed_files: List[FailureEvidenceChangedFile]
    linked_incidents: List[FailureEvidenceRecommendationOutcome]
    linked_recommendations: List[FailureEvidenceRecommendationRun]
    
    # Window Metadata
    repository_id: UUID
    repository_status: str # ACTIVE, STALE, or INACTIVE
    evidence_window_start: datetime
    evidence_window_end: datetime
    history_window_days: int
    generated_at: datetime
    generation_version: str
    
    # Summary Densities & Denominators
    total_failed_results: int
    total_failed_runs: int
    distinct_pull_request_count: int
    rollback_count: int
    escaped_defect_count: int
    total_runs_in_window: int
    total_test_results_in_window: int
    
    # Truncation Metadata
    truncated: bool
    truncation_reason: Optional[str]
    max_failed_runs_applied: int
    
    # Diagnostics & Lineage versioning
    excluded_evidence_summary: Dict[str, int]
    normalization_rules_version: str
    evidence_filter_policy_version: str

    class Config:
        from_attributes = True
