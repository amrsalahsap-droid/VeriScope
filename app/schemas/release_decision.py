"""Release Decision Schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class DecisionStatusEnum(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONDITIONALLY_APPROVED = "CONDITIONALLY_APPROVED"


class HistoryEventTypeEnum(str, Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONDITIONALLY_APPROVED = "CONDITIONALLY_APPROVED"
    RESET = "RESET"
    CANCELLED = "CANCELLED"


class ReleaseDecisionState(BaseModel):
    """Current release decision state."""
    decisionId: Optional[str] = None
    decisionStatus: str
    approverId: Optional[str] = None
    approverName: Optional[str] = None
    decisionNote: Optional[str] = None
    snapshotHash: Optional[str] = None
    evidenceHealthStatus: Optional[str] = None
    readinessState: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class ReleaseDecisionSubmit(BaseModel):
    """Request model for submitting a release decision."""
    decision_status: DecisionStatusEnum
    snapshot_hash: str
    decision_note: Optional[str] = None
    live_evidence_health: Optional[str] = None


class ReleaseDecisionReset(BaseModel):
    """Request model for resetting a release decision."""
    snapshot_hash: str
    note: Optional[str] = None
    live_evidence_health: Optional[str] = None


class ReleaseHistoryEvent(BaseModel):
    """Single event in release decision history."""
    eventType: str
    actorName: Optional[str] = None
    previousStatus: Optional[str] = None
    newStatus: Optional[str] = None
    note: Optional[str] = None
    createdAt: Optional[str] = None
    historyId: Optional[str] = None  # Only in audit mode
    actorId: Optional[str] = None  # Only in audit mode
    snapshotHash: Optional[str] = None  # Only in audit mode


class ReleaseDecisionHistoryResponse(BaseModel):
    """Response model for release decision history."""
    decisionId: Optional[str] = None
    decisionStatus: str
    approverName: Optional[str] = None
    snapshotHash: Optional[str] = None
    evidenceHealthStatus: Optional[str] = None
    readinessState: Optional[str] = None
    history: List[ReleaseHistoryEvent] = []
    totalEvents: int = 0
