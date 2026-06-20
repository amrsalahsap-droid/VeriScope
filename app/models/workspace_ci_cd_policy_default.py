"""
Workspace CI/CD Policy Default Model

Stores workspace-level default CI/CD policy configuration.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.base import Base


class WorkspaceCICDPolicyDefault(Base):
    """Workspace-level CI/CD policy default configuration."""
    
    __tablename__ = "workspace_ci_cd_policy_defaults"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Default preset
    preset_name = Column(String(50), nullable=False, default="STANDARD")
    
    # Custom default policy JSON (if default_preset is CUSTOM)
    default_policy_json = Column(JSON, nullable=True)
    
    # Inheritance settings
    auto_apply_to_new_repositories = Column(Boolean, nullable=False, default=True)
    allow_repository_override = Column(Boolean, nullable=False, default=True)
    require_override_reason = Column(Boolean, nullable=False, default=True)
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="ci_cd_policy_default")
