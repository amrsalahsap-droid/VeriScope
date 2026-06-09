from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class BehaviorEvidenceSchema(BaseModel):
    """Schema for behavior evidence."""
    id: str
    evidence_type: str
    source_path: Optional[str] = None
    source_name: Optional[str] = None
    excerpt: Optional[str] = None
    confidence: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class BehaviorScenarioSchema(BaseModel):
    """Schema for behavior scenario."""
    id: str
    title: str
    description: Optional[str] = None
    priority: str
    scenario_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BehaviorRiskSchema(BaseModel):
    """Schema for behavior risk information."""
    risk_level: str
    risk_reason: Optional[str] = None
    risk_evidence: Optional[str] = None


class BehaviorSchema(BaseModel):
    """Schema for behavior."""
    id: str
    repository_id: str
    journey_id: Optional[str] = None
    name: str
    slug: str
    description: Optional[str] = None
    journey_name: Optional[str] = None
    risk_level: str
    risk_reason: Optional[str] = None
    risk_evidence: Optional[str] = None
    status: str
    confidence: Optional[str] = None
    discovery_source: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BehaviorDetailSchema(BehaviorSchema):
    """Schema for behavior with nested details."""
    journey: Optional[dict] = None
    risk: BehaviorRiskSchema
    evidences: List[BehaviorEvidenceSchema] = []
    scenarios: List[BehaviorScenarioSchema] = []


class JourneySchema(BaseModel):
    """Schema for journey."""
    id: str
    repository_id: str
    name: str
    slug: str
    description: Optional[str] = None
    risk_level: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class JourneyDetailSchema(JourneySchema):
    """Schema for journey with nested behaviors."""
    behaviors: List[BehaviorSchema] = []


class PaginatedResponse(BaseModel):
    """Schema for paginated response."""
    items: List
    total: int
    page: int
    page_size: int
    total_pages: int
