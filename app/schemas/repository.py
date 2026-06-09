from datetime import datetime
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel, Field

class RepositoryBase(BaseModel):
    organization_id: UUID
    github_repo_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=255)
    default_branch: str = Field("main", min_length=1, max_length=100)
    is_active: bool = True

class RepositoryCreate(RepositoryBase):
    pass

class RepositoryResponse(RepositoryBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RepositoryTestRunItem(BaseModel):
    id: str
    repository_id: str
    pull_request_id: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    run_name: Optional[str] = None
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    duration: float
    created_at: datetime
    is_current_pr: bool
    is_stale: bool
    evidence_health_status: str

    class Config:
        from_attributes = True

class RepositoryTestRunsResponse(BaseModel):
    test_runs: List[RepositoryTestRunItem]
