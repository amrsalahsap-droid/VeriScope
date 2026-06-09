"""
Work Item Behavior Mapping Model

Stores mappings between external work items (Jira, Azure DevOps, etc.)
and Veriscope Behavior Catalog and Journeys.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint, Index
from app.db.base import Base


class WorkItemBehaviorMapping(Base):
    """
    Mapping between external work items and Veriscope behaviors/journeys.
    
    This model stores the results of mapping external work items (stories, requirements)
    to discovered behaviors and journeys in Veriscope.
    
    Confidence levels:
    - HIGH: Strong title/AC behavior match
    - MEDIUM: Description/domain match
    - LOW: Broad journey match
    
    Rules:
    - Do not overclaim - evidence required
    - Track matched terms for explainability
    - Store reason for mapping decision
    """
    __tablename__ = "work_item_behavior_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # External work item reference
    external_work_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("external_work_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Behavior mapping (nullable if no match found)
    behavior_id = Column(
        UUID(as_uuid=True),
        ForeignKey("behaviors.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Journey mapping (nullable if no match found)
    journey_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journeys.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Mapping confidence
    confidence = Column(
        Float,
        nullable=False
    )  # 0.0 to 1.0
    
    # Matched terms for explainability
    matched_terms = Column(
        JSONB,
        nullable=True,
        default=list
    )  # List of terms that contributed to the match
    
    # Reason for mapping decision
    reason = Column(
        Text,
        nullable=True
    )  # Human-readable explanation of why this mapping was made
    
    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    
    # Constraints
    __table_args__ = (
        # Unique constraint: external_work_item_id
        # Each work item can have at most one mapping (we update if better match found)
        UniqueConstraint(
            'external_work_item_id',
            name='uq_work_item_mapping'
        ),
        # Index for filtering by behavior
        Index('ix_work_item_behavior_mappings_behavior', 'behavior_id'),
        # Index for filtering by journey
        Index('ix_work_item_behavior_mappings_journey', 'journey_id'),
        # Index for filtering by confidence
        Index('ix_work_item_behavior_mappings_confidence', 'confidence'),
    )
    
    # Relationships
    external_work_item = relationship("ExternalWorkItem", back_populates="behavior_mappings")
    behavior = relationship("Behavior", back_populates="work_item_mappings")
    journey = relationship("Journey", back_populates="work_item_mappings")
    
    def __repr__(self):
        return (
            f"<WorkItemBehaviorMapping(id={self.id}, external_work_item_id={self.external_work_item_id}, "
            f"behavior_id={self.behavior_id}, journey_id={self.journey_id}, confidence={self.confidence})>"
        )
