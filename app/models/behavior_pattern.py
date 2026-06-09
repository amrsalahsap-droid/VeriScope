import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, ARRAY, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class BehaviorPattern(Base):
    """Reusable business capability patterns for behavior discovery."""
    __tablename__ = "behavior_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Pattern identity
    name = Column(String, nullable=False, unique=True, index=True)
    version = Column(Integer, nullable=False, default=1, index=True)

    # Pattern matching
    aliases = Column(ARRAY(String), nullable=False)  # Keyword aliases for matching
    description = Column(Text, nullable=True)

    # Classification
    journey = Column(String, nullable=False, index=True)  # Associated journey
    risk_level = Column(String, nullable=False, index=True)  # LOW, MEDIUM, HIGH, CRITICAL

    # Default scenarios
    default_scenarios = Column(JSONB, nullable=True)  # Array of default scenario templates

    # Metadata
    is_active = Column(Integer, nullable=False, default=1, index=True)  # Soft delete flag
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_behavior_pattern_name_version"),
        Index("ix_behavior_patterns_journey_risk", "journey", "risk_level"),
    )
