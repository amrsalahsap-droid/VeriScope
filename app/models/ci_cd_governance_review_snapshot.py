"""
CI/CD Governance Review Snapshot Model

Stores periodic snapshots of workspace governance compliance state.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid


class CICDGovernanceReviewSnapshot(Base):
    """Governance review snapshot for workspace compliance tracking."""
    
    __tablename__ = "ci_cd_governance_review_snapshots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    total_repositories = Column(Integer, nullable=False, default=0)
    compliance_score = Column(Integer, nullable=False, default=0)  # 0-100
    critical_count = Column(Integer, nullable=False, default=0)
    high_risk_count = Column(Integer, nullable=False, default=0)
    drifted_count = Column(Integer, nullable=False, default=0)
    compliant_count = Column(Integer, nullable=False, default=0)
    snapshot_json = Column(JSON, nullable=True)  # Full snapshot data
    
    # Relationships
    workspace = relationship("Workspace", backref="governance_review_snapshots")
