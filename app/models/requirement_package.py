from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.db.base import Base

class RequirementPackage(Base):
    __tablename__ = "requirement_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(100), nullable=False) # e.g., "PR_DESCRIPTION", "LINKED_STORY", "MANUAL_USER_INPUT"
    source_id = Column(String(200), nullable=True) # ID from external source (e.g. Jira issue ID)
    package_version = Column(String(50), nullable=False, default="1.0.0")
    status = Column(String(50), nullable=False, default="NEEDS_REVIEW") # NEEDS_REVIEW, READY, BLOCKED
    
    # Separated business requirement sections
    business_change_summary = Column(Text, nullable=True)
    affected_journeys = Column(JSON, nullable=True) # Array of journey names
    risk_notes = Column(Text, nullable=True)
    invalid_test_data_examples = Column(JSON, nullable=True) # Array of invalid test data
    valid_test_data_examples = Column(JSON, nullable=True) # Array of valid test data
    security_notes = Column(JSON, nullable=True) # Array of security notes
    integration_notes = Column(Text, nullable=True)
    out_of_scope_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    repository = relationship("Repository")
    pull_request = relationship("PullRequest")
    groups = relationship("RequirementGroup", back_populates="package", cascade="all, delete-orphan")
