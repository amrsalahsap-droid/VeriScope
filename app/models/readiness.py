"""Recommendation Readiness Domain Models."""
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
from app.db.base import Base

# Enums
ReadinessLevel = ENUM(
    'CONNECTED',
    'EVIDENCE_READY', 
    'RECOMMENDATION_READY',
    'HIGH_CONFIDENCE_READY',
    'PARTIAL',
    'BLOCKED',
    name='readiness_level'
)

ExpectedConfidence = ENUM(
    'LOW',
    'MEDIUM', 
    'HIGH',
    name='expected_confidence'
)

SignalType = ENUM(
    'source_code',
    'pull_request_diff',
    'junit_test_history',
    'coverage_report',
    'architecture_graph',
    'behavior_catalog',
    'journey_catalog',
    'acceptance_criteria',
    'linked_work_item',
    'managed_manual_tests',
    'historical_outcomes',
    'fragility_memory',
    'current_pr_execution',
    'github_connection',
    'webhook_activity',
    name='signal_type'
)

GapType = ENUM(
    'BLOCKING',
    'OPTIONAL',
    name='gap_type'
)

class RecommendationReadinessAssessment(Base):
    """Assessment of repository/PR readiness for recommendation generation."""
    __tablename__ = "recommendation_readiness_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Core assessment fields
    readiness_level = Column(ReadinessLevel, nullable=False)
    expected_confidence = Column(ExpectedConfidence, nullable=False)
    readiness_score = Column(Float, nullable=False)  # 0.0 to 1.0
    
    # Signal analysis
    available_signals = Column(JSON, nullable=False, default=list)  # List of SignalType
    missing_signals = Column(JSON, nullable=False, default=list)   # List of SignalType
    
    # Gap analysis
    blocking_gaps = Column(JSON, nullable=False, default=list)     # List of gap descriptions
    optional_gaps = Column(JSON, nullable=False, default=list)    # List of gap descriptions
    
    # Recommendations
    recommended_actions = Column(JSON, nullable=False, default=list)
    confidence_impact_summary = Column(String, nullable=False)
    
    # Generation decision
    can_generate = Column(Boolean, nullable=False)
    can_generate_reason = Column(String, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    repository = relationship("Repository")
    pull_request = relationship("PullRequest")

    def __repr__(self):
        return f"<RecommendationReadinessAssessment(repo_id={self.repository_id}, level={self.readiness_level}, score={self.readiness_score})>"
