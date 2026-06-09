"""Expected Behavior Scenario model for generated expected scenarios from business intent."""
from sqlalchemy import Column, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.base import Base


class ExpectedBehaviorScenario(Base):
    """Represents an expected behavior scenario generated from business intent or AC."""
    
    __tablename__ = "expected_behavior_scenarios"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Scenario title
    title = Column(String(500), nullable=False)
    
    # Target behavior (nullable if behavior not yet identified)
    behavior_id = Column(UUID(as_uuid=True), ForeignKey("behaviors.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Journey context
    journey_id = Column(UUID(as_uuid=True), ForeignKey("journeys.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Source acceptance criterion (nullable if from business intent)
    acceptance_criterion_id = Column(UUID(as_uuid=True), ForeignKey("acceptance_criteria.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Priority
    priority = Column(String(50), nullable=False, default="MUST")  # MUST, SHOULD, OPTIONAL
    
    # Testing type
    testing_type = Column(String(50), nullable=False, default="AUTOMATED")  # AUTOMATED, MANUAL, HYBRID
    
    # Scenario type
    scenario_type = Column(String(50), nullable=False, default="FUNCTIONAL")  # FUNCTIONAL, VALIDATION, SECURITY, UI, API, INTEGRATION, PERFORMANCE
    
    # Preconditions
    preconditions = Column(JSON, nullable=False, default=list)
    
    # Test data
    test_data = Column(JSON, nullable=True)
    
    # Test steps
    steps = Column(JSON, nullable=False, default=list)
    
    # Expected result
    expected_result = Column(Text, nullable=True)
    
    # Source
    source = Column(String(100), nullable=False)  # BUSINESS_INTENT, ACCEPTANCE_CRITERIA, PR_DESCRIPTION
    
    # Confidence in generation (0.0 to 1.0)
    confidence = Column(Float, nullable=False, default=0.5)
    
    # Whether this scenario matches an existing automated test
    matches_existing_test = Column(String, nullable=False, default="false")
    
    # Recommendation run context
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    behavior = relationship("Behavior", backref="expected_scenarios")
    journey = relationship("Journey", backref="expected_scenarios")
    acceptance_criterion = relationship("AcceptanceCriterion", backref="expected_scenarios")
    recommendation_run = relationship("RecommendationRun", backref="expected_scenarios")
    
    def __repr__(self):
        return f"<ExpectedBehaviorScenario(id={self.id}, title='{self.title[:50]}...', source={self.source})>"
