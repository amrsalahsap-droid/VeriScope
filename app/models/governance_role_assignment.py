"""
Governance Role Assignment Model

Defines role assignments for governance access control.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class ScopeType(str, enum.Enum):
    """Scope type for role assignment."""
    WORKSPACE = "WORKSPACE"
    REPOSITORY = "REPOSITORY"


class GovernanceRole(str, enum.Enum):
    """Governance roles."""
    GOVERNANCE_OWNER = "GOVERNANCE_OWNER"
    POLICY_ADMIN = "POLICY_ADMIN"
    EXCEPTION_APPROVER = "EXCEPTION_APPROVER"
    REPOSITORY_POLICY_MANAGER = "REPOSITORY_POLICY_MANAGER"
    GOVERNANCE_VIEWER = "GOVERNANCE_VIEWER"
    EXECUTIVE_VIEWER = "EXECUTIVE_VIEWER"
    AUDITOR = "AUDITOR"


class GovernanceRoleAssignment(Base):
    """Governance role assignment model."""
    
    __tablename__ = "governance_role_assignments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(SQLEnum(GovernanceRole), nullable=False, index=True)
    scope_type = Column(SQLEnum(ScopeType), nullable=False, index=True)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Relationships
    workspace = relationship("Workspace", foreign_keys=[workspace_id])
    repository = relationship("Repository", foreign_keys=[repository_id])
    # Note: user and assigner relationships removed to avoid foreign key ambiguity
    # Use explicit joins in queries instead
    
    def __repr__(self):
        return f"<GovernanceRoleAssignment {self.role} for user {self.user_id} in {self.scope_type} {self.workspace_id}>"
