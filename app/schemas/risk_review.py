from typing import Optional, List
from pydantic import BaseModel, Field

class RiskReviewSubmit(BaseModel):
    sourceRequirementId: Optional[str] = Field(default=None)
    sourceAcNumber: Optional[int] = Field(default=None)
    readableId: Optional[str] = Field(default=None)
    reviewStatus: str
    reviewedRiskLevel: Optional[str] = Field(default=None)
    reviewedPriority: Optional[str] = Field(default=None)
    reviewNote: Optional[str] = Field(default=None)
    snapshotHash: str

class BulkAcceptRequest(BaseModel):
    snapshotHash: str

class ResetReviewRequest(BaseModel):
    sourceRequirementId: Optional[str] = Field(default=None)
    sourceAcNumber: Optional[int] = Field(default=None)
    snapshotHash: str

class RiskReviewHistoryEvent(BaseModel):
    reviewId: Optional[str] = Field(default=None)
    eventType: str
    reviewStatus: str
    originalRiskLevel: str
    originalPriority: str
    reviewedRiskLevel: str
    reviewedPriority: str
    reviewerName: Optional[str] = Field(default=None)
    reviewerId: Optional[str] = Field(default=None)
    reviewNote: Optional[str] = Field(default=None)
    sourceSnapshotHash: Optional[str] = Field(default=None)
    createdAt: str
    isActive: bool

class GapReviewHistoryItem(BaseModel):
    sourceAcNumber: Optional[int] = Field(default=None)
    readableId: Optional[str] = Field(default=None)
    sourceRequirementId: Optional[str] = Field(default=None)
    title: str
    currentEffectiveRiskLevel: str
    currentReviewStatus: str
    firstReviewedAt: Optional[str] = Field(default=None)
    lastReviewedAt: Optional[str] = Field(default=None)
    lastReviewerName: Optional[str] = Field(default=None)
    activeStatus: str
    totalEvents: int
    resetCount: int
    overrideCount: int
    needsDiscussionCount: int
    acceptedCount: int
    history: List[RiskReviewHistoryEvent]

class RiskReviewHistoryResponse(BaseModel):
    recommendationRunId: Optional[str] = Field(default=None)
    snapshotHash: Optional[str] = Field(default=None)
    totalHistoryEvents: int
    items: List[GapReviewHistoryItem]

