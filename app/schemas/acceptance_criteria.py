"""Acceptance Criteria schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime


class AcceptanceCriteriaCoverageStatus(BaseModel):
    """Coverage status for an acceptance criterion."""
    
    acceptance_criterion_id: str
    coverage_status: str = Field(
        ...,
        description="Coverage status: COVERED_BY_EXISTING_TEST, PARTIALLY_COVERED, MISSING_TEST_COVERAGE, VERIFIED_ON_CURRENT_PR, MANUAL_VALIDATION_REQUIRED, UNKNOWN"
    )
    existing_tests: List[str] = Field(default_factory=list, description="List of existing test IDs that cover this AC")
    suggested_scenarios: List[str] = Field(default_factory=list, description="List of suggested scenario IDs for this AC")
    current_pr_execution_status: str = Field(default="NOT_EXECUTED", description="Execution status on current PR: EXECUTED, NOT_EXECUTED, UNKNOWN")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in coverage assessment")
    reason: Optional[str] = Field(None, description="Reason for the coverage status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "acceptance_criterion_id": "123e4567-e89b-12d3-a456-426614174000",
                "coverage_status": "COVERED_BY_EXISTING_TEST",
                "existing_tests": ["test_1", "test_2"],
                "suggested_scenarios": [],
                "current_pr_execution_status": "NOT_EXECUTED",
                "confidence": 0.9,
                "reason": "Direct test match found in JUnit results"
            }
        }


class AcceptanceCriteriaCoverageReport(BaseModel):
    """Complete coverage report for all acceptance criteria."""
    
    total_criteria: int
    covered_by_existing_test: int
    partially_covered: int
    missing_test_coverage: int
    verified_on_current_pr: int
    manual_validation_required: int
    unknown: int
    coverage_statuses: List[AcceptanceCriteriaCoverageStatus]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_criteria": 10,
                "covered_by_existing_test": 5,
                "partially_covered": 2,
                "missing_test_coverage": 2,
                "verified_on_current_pr": 1,
                "manual_validation_required": 0,
                "unknown": 0,
                "coverage_statuses": [],
                "generated_at": "2024-01-01T00:00:00Z"
            }
        }
