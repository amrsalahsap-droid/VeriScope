import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class JourneyIntelligenceSnapshot(Base):
    """Reusable journey intelligence summary for recommendation runs."""
    __tablename__ = "journey_intelligence_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_run_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Affected Journeys
    affected_journeys = Column(JSONB, nullable=False)  # List of journey impact data
    
    # Affected Behaviors
    affected_behaviors = Column(JSONB, nullable=False)  # List of behavior names affected
    
    # Journey Risks
    journey_risks = Column(JSONB, nullable=False)  # Journey risk summary
    
    # Coverage Gaps
    coverage_gaps = Column(JSONB, nullable=False)  # Journey coverage gaps
    
    # Testing Scope
    testing_scope = Column(JSONB, nullable=False)  # Journey-based testing scope
    
    # Confidence
    confidence = Column(String, nullable=False)  # HIGH, MODERATE, LOW
    
    # Audit timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    recommendation_run = relationship("RecommendationRun", back_populates="journey_intelligence_snapshot")
