"""
Repository CI/CD Policy Model

Stores repository-level CI/CD quality gate policies for controlling
how Veriscope maps release decisions into CI results, GitHub statuses/checks,
PR comments, and branch protection behavior.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class RepositoryCICDPolicy(Base):
    """CI/CD policy for repository-level quality gate configuration."""
    
    __tablename__ = "repository_ci_cd_policies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Policy enablement
    enabled = Column(Boolean, nullable=False, default=True)
    
    # GitHub check configuration
    required_check_name = Column(String(255), nullable=False, default="Veriscope Quality Gate")
    
    # Quality gate behavior
    ci_fail_on_partial = Column(Boolean, nullable=False, default=False)
    fail_on_unknown_gate = Column(Boolean, nullable=False, default=True)
    fail_on_missing_recommendation = Column(Boolean, nullable=False, default=True)
    
    # Artifact and comment requirements
    require_artifact = Column(Boolean, nullable=False, default=True)
    require_pr_comment = Column(Boolean, nullable=False, default=True)
    
    # Manual override configuration
    allow_manual_override = Column(Boolean, nullable=False, default=False)
    manual_override_requires_reason = Column(Boolean, nullable=False, default=True)
    
    # Strict mode (fails PARTIAL and UNKNOWN gates)
    strict_mode = Column(Boolean, nullable=False, default=False)
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
