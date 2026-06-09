from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field

class IngestionJobCreate(BaseModel):
    job_type: str = Field(..., min_length=1)
    repository_id: UUID

class IngestionJobResponse(BaseModel):
    id: UUID
    job_type: str
    repository_id: UUID
    status: str
    error_message: Optional[str]
    retry_count: int
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True
