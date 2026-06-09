from datetime import datetime
from uuid import UUID
from typing import Dict, Any, List
from pydantic import BaseModel, Field

class PilotReportCreate(BaseModel):
    start_date: datetime = Field(..., description="Start date of the pilot evaluation period")
    end_date: datetime = Field(..., description="End date of the pilot evaluation period")

class PilotReportResponse(BaseModel):
    id: UUID
    repository_id: UUID
    start_date: datetime
    end_date: datetime
    
    total_runs: int
    followed_runs: int
    overridden_runs: int
    ignored_runs: int
    
    ci_runtime_saved_seconds: float
    ci_runtime_total_seconds: float
    
    escaped_defects_count: int
    rollbacks_count: int
    
    trust_adherence_rate: float
    trust_lower_bound: float
    trust_upper_bound: float
    
    created_at: datetime

    class Config:
        from_attributes = True

class PilotSnapshotResponse(BaseModel):
    id: UUID
    pilot_report_id: UUID
    snapshot_hash: str
    payload: Dict[str, Any]
    generated_at: datetime
    snapshot_version: int

    class Config:
        from_attributes = True
