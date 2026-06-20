"""
CI Token Schemas
"""
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional


class CITokenCreate(BaseModel):
    """Request to create a new CI token."""
    name: str
    scopes: Optional[str] = "pipeline:trigger,artifact:read"


class CITokenResponse(BaseModel):
    """Response with CI token details (raw token shown only once)."""
    id: UUID
    repository_id: UUID
    name: str
    scopes: str
    created_at: datetime
    last_used_at: Optional[datetime]
    is_active: bool
    raw_token: Optional[str] = None  # Only included on creation


class CITokenListResponse(BaseModel):
    """Response listing CI tokens for a repository."""
    tokens: list[CITokenResponse]


class CITokenRevokeResponse(BaseModel):
    """Response after revoking a CI token."""
    id: UUID
    revoked: bool
