import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class BusinessIntentOverride(Base):
    """Business intent override for PRs and recommendations to improve recommendation accuracy."""
    __tablename__ = "business_intent_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=True, index=True)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Business intent fields
    business_change_summary = Column(Text, nullable=False)
    affected_users_journeys = Column(Text, nullable=True)  # Optional, comma-separated
    acceptance_criteria = Column(Text, nullable=False)
    risk_notes = Column(Text, nullable=True)  # Optional
    testing_notes = Column(Text, nullable=True)  # Optional
    
    # Processing results
    extracted_scenarios = Column(JSON, nullable=True)  # Structured acceptance criteria
    mapped_behaviors = Column(JSON, nullable=True)  # Business behavior mappings
    extraction_confidence = Column(String, nullable=True)  # HIGH/MEDIUM/LOW
    
    # Metadata
    source = Column(String, nullable=False, default="manual_paste")  # manual_paste, jira_sync, etc.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String, nullable=True)  # User who created the override
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_processed = Column(Boolean, nullable=False, default=False)  # Whether extraction/mapping has been run
    
    # Relationships
    repository = relationship("Repository", backref="business_intent_overrides")
    pull_request = relationship("PullRequest", backref="business_intent_overrides")
    recommendation_run = relationship("RecommendationRun", backref="business_intent_overrides")

    def __repr__(self):
        return f"<BusinessIntentOverride(id={self.id}, repository_id={self.repository_id}, source={self.source})>"


class AcceptanceCriteriaExtraction(Base):
    """Structured extraction results from acceptance criteria text."""
    __tablename__ = "acceptance_criteria_extractions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_intent_override_id = Column(UUID(as_uuid=True), ForeignKey("business_intent_overrides.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Extraction results
    scenario_title = Column(String, nullable=False)
    scenario_description = Column(Text, nullable=True)
    preconditions = Column(JSON, nullable=True)  # List of precondition strings
    steps = Column(JSON, nullable=True)  # List of step strings
    expected_results = Column(JSON, nullable=True)  # List of expected result strings
    test_data = Column(JSON, nullable=True)  # Dict of test data
    
    # Classification
    testing_type = Column(String, nullable=True)  # functional, integration, etc.
    priority = Column(String, nullable=True)  # must_run, should_run, could_run
    automation_candidate = Column(Boolean, nullable=True, default=True)
    
    # Confidence scores
    extraction_confidence = Column(String, nullable=True)  # HIGH/MEDIUM/LOW
    completeness_score = Column(String, nullable=True)  # COMPLETE/PARTIAL/MINIMAL
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    extraction_method = Column(String, nullable=False, default="llm_extraction")
    
    # Relationships
    business_intent_override = relationship("BusinessIntentOverride", backref="extractions")

    def __repr__(self):
        return f"<AcceptanceCriteriaExtraction(id={self.id}, scenario={self.scenario_title})>"
