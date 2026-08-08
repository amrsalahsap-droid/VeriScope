from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid

class RequirementGroup(Base):
    __tablename__ = "requirement_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requirement_package_id = Column(UUID(as_uuid=True), ForeignKey("requirement_packages.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    group_number = Column(Integer, nullable=False)
    group_type = Column(String(50), nullable=False, default="UNKNOWN") # ENHANCEMENT, BUG_FIX, TECH_DEBT, etc.
    stable_group_key = Column(String(500), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    business_flow = Column(Text, nullable=True)
    priority = Column(String(50), nullable=True)
    risk_level = Column(String(50), nullable=True)
    source_type = Column(String(100), nullable=True)
    source_id = Column(String(200), nullable=True)
    status = Column(String(50), nullable=False, default="NEEDS_REVIEW")

    package = relationship("RequirementPackage", back_populates="groups")
    acceptance_criteria = relationship("AcceptanceCriterion", back_populates="group", cascade="all, delete-orphan")
