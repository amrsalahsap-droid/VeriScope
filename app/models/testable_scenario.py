from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid

class TestableScenario(Base):
    __tablename__ = "testable_scenarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    acceptance_criterion_id = Column(UUID(as_uuid=True), ForeignKey("acceptance_criteria.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_key = Column(String(500), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    preconditions = Column(Text, nullable=True)
    steps = Column(Text, nullable=True)
    expected_result = Column(Text, nullable=True)
    scenario_type = Column(String(50), nullable=False, default="POSITIVE") # POSITIVE, NEGATIVE, EDGE, etc.
    status = Column(String(50), nullable=False, default="NEEDS_REVIEW")

    acceptance_criterion = relationship("AcceptanceCriterion", back_populates="testable_scenarios")
